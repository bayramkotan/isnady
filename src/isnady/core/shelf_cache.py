"""The shelf's counts, kept — in memory and in a JSON file in the data folder — so the Books page, the book lists of
Search and every page that names the books do not count tens of thousands of hadith again each time.

Bayram (2026-10-12): "neden kitaplara geçince sürekli gecikmeler oluyor … Cache'lememiz çalışıyor mu? JSON'a kayıtlar
yoğun olacak ki tekrar tekrar scan olmayacak ki hızlı açılacak!"

A value is kept with the database's stamp (`stamp()`): a few counts and highest ids that change whenever a book, an
edition, a hadith, a chapter or a rijal entry is imported or removed. The stamp itself costs a few milliseconds; while
it is the same, the kept value is used — the first time after a start from `<data folder>/cache/<name>.json`, after
that from memory. Anything imported or removed changes the stamp and the value is counted again once.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_MEMORY: dict = {}        # (database file, name) → (stamp, value)


def stamp(conn: sqlite3.Connection) -> list:
    """What the database holds, in a few cheap numbers (rowid maxima and small counts)."""
    row = conn.execute(
        """SELECT (SELECT COUNT(*) FROM collections), (SELECT MAX(id) FROM collections),
                  (SELECT COUNT(*) FROM editions), (SELECT MAX(id) FROM editions),
                  (SELECT MAX(id) FROM hadiths), (SELECT COUNT(*) FROM works), (SELECT MAX(id) FROM works),
                  (SELECT MAX(id) FROM work_nodes), (SELECT MAX(id) FROM persons), (SELECT COUNT(*) FROM sources)"""
    ).fetchone()
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    return [version, *row]


def _db_file(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA database_list").fetchone()
    return (row[2] if row else "") or ":memory:"


def _file(name: str) -> Path | None:
    try:
        from isnady.data.paths import data_dir

        return data_dir() / "cache" / f"{name}.json"
    except Exception:       # no data folder (tests): memory only
        return None


def kept(conn: sqlite3.Connection, name: str, compute):
    """compute(conn)'s value (JSON-able), counted again only when the database changed."""
    now = stamp(conn)
    key = (_db_file(conn), name)
    hit = _MEMORY.get(key)
    if hit is not None and hit[0] == now:
        return hit[1]
    path = _file(name)
    if path is not None and key[0] != ":memory:":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("stamp") == now and data.get("database") == key[0]:
                _MEMORY[key] = (now, data["value"])
                return data["value"]
        except (OSError, ValueError, KeyError):
            pass
    value = compute(conn)
    _MEMORY[key] = (now, value)
    if path is not None and key[0] != ":memory:":
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"database": key[0], "stamp": now, "value": value}, ensure_ascii=False),
                           encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass
    return value


def forget() -> None:
    """Drop what is kept in memory (the files are checked against the stamp anyway)."""
    _MEMORY.clear()
