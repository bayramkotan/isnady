"""isnady's cache: whatever is read from the database and costs time is counted once and kept — in memory, and for
the results worth keeping across starts in a JSON file in `<data folder>/cache/` — until the database changes.

Bayram (2026-10-12): "Ben tüm her şey için önbellek istiyorum. Ne var ne yok her şey kaydedilsin. Uygulamanın çok
hızlı çalışmasını istiyorum. Eğer bir işlem yapılırsa JSON dosyasından güncelleniyor ama read yapılacaksa sürekli
scan yapmanın bir anlamı yok."

How a value knows it is still right: the database's **stamp** (`stamp()`), a few counts and highest ids that change
whenever anything is imported, removed or read again (books, editions, hadiths, chains, narrators, grades, chapters).
Reading the stamp is itself kept: while SQLite says nothing was written (PRAGMA data_version for the other connections,
total_changes for this one) the last stamp is used without a query.

- `kept(conn, name, compute)` — kept in memory AND in `cache/<name>.json` (a new start reads the file, not the
  database). For results of the whole database or of one book, scholar or tradition.
- `memo(conn, name, key, compute)` — in memory only, the last few hundred per name. For many small results (a
  narrator's reading, a search).

JSON keeps what JSON cannot say plainly — dictionaries with number keys, tuples, sets, Counters — so a value comes
back from the file exactly as it was counted.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

_MEMORY: dict = {}            # (database, name) → (stamp, value)
_MEMO: dict = {}              # (database, name) → OrderedDict(key → (stamp, value))
_STAMPS: dict = {}            # id(conn) → (data_version, total_changes, stamp)
MEMO_SIZE = 400


# ---------------------------------------------------------------------- the stamp
def _full_stamp(conn: sqlite3.Connection) -> list:
    row = conn.execute(
        """SELECT (SELECT COUNT(*) FROM collections), (SELECT MAX(id) FROM collections),
                  (SELECT COUNT(*) FROM editions), (SELECT MAX(id) FROM editions),
                  (SELECT MAX(id) FROM hadiths), (SELECT COUNT(*) FROM works), (SELECT MAX(id) FROM works),
                  (SELECT MAX(id) FROM work_nodes), (SELECT MAX(id) FROM persons), (SELECT COUNT(*) FROM sources),
                  (SELECT MAX(id) FROM isnads), (SELECT COUNT(*) FROM isnads), (SELECT MAX(id) FROM grades),
                  (SELECT COUNT(*) FROM grades), (SELECT SUM(person_id) FROM isnad_links)"""
    ).fetchone()
    # SUM(person_id): the narrators identified in the chains change without new rows (narrators.link_narrators);
    # the sum moves whenever one is identified, changed or dropped — read from an index in a few milliseconds
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    return [version, *row]


def stamp(conn: sqlite3.Connection) -> list:
    """What the database holds, as a few numbers; the same numbers as long as nothing was written."""
    try:
        dv = conn.execute("PRAGMA data_version").fetchone()[0]
    except sqlite3.Error:
        return _full_stamp(conn)
    tc = conn.total_changes
    hit = _STAMPS.get(id(conn))
    if hit is not None and hit[0] == dv and hit[1] == tc:
        return hit[2]
    value = _full_stamp(conn)
    _STAMPS[id(conn)] = (dv, tc, value)
    return value


def _db(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA database_list").fetchone()
    return (row[2] if row else "") or ":memory:"


# ---------------------------------------------------------------------- JSON that keeps the types
def _pack(obj):
    if isinstance(obj, Counter):
        return {"__counter__": [[_pack(k), v] for k, v in obj.items()]}
    if isinstance(obj, dict):
        if all(isinstance(k, str) for k in obj) and not any(k.startswith("__") for k in obj):
            return {k: _pack(v) for k, v in obj.items()}
        return {"__map__": [[_pack(k), _pack(v)] for k, v in obj.items()]}
    if isinstance(obj, tuple):
        return {"__tuple__": [_pack(x) for x in obj]}
    if isinstance(obj, (set, frozenset)):
        return {"__set__": [_pack(x) for x in obj]}
    if isinstance(obj, list):
        return [_pack(x) for x in obj]
    return obj


def _unpack(obj):
    if isinstance(obj, list):
        return [_unpack(x) for x in obj]
    if isinstance(obj, dict):
        if "__counter__" in obj:
            return Counter({_hashable(_unpack(k)): v for k, v in obj["__counter__"]})
        if "__map__" in obj:
            return {_hashable(_unpack(k)): _unpack(v) for k, v in obj["__map__"]}
        if "__tuple__" in obj:
            return tuple(_unpack(x) for x in obj["__tuple__"])
        if "__set__" in obj:
            return {_hashable(_unpack(x)) for x in obj["__set__"]}
        return {k: _unpack(v) for k, v in obj.items()}
    return obj


def _hashable(x):
    return tuple(_hashable(i) for i in x) if isinstance(x, list) else x


def _plain(value):
    """A defaultdict is kept as a plain dict (what the callers read)."""
    if isinstance(value, defaultdict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(_plain(v) for v in value)
    return value


def _file(name: str) -> Path | None:
    try:
        from isnady.data.paths import data_dir

        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
        return data_dir() / "cache" / f"{safe}.json"
    except Exception:            # no data folder: memory only
        return None


# ---------------------------------------------------------------------- the two kinds
def kept(conn: sqlite3.Connection, name: str, compute, disk: bool = True):
    """compute(conn), counted again only when the database changed; kept in memory and (disk) in cache/<name>.json."""
    now = stamp(conn)
    db = _db(conn)
    key = (db, name)
    hit = _MEMORY.get(key)
    if hit is not None and hit[0] == now:
        return hit[1]
    path = _file(name) if disk and db != ":memory:" else None
    if path is not None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("stamp") == now and data.get("database") == db:
                value = _unpack(data["value"])
                _MEMORY[key] = (now, value)
                return value
        except (OSError, ValueError, KeyError, TypeError):
            pass
    value = _plain(compute(conn))
    _MEMORY[key] = (now, value)
    if path is not None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"database": db, "stamp": now, "value": _pack(value)}, ensure_ascii=False),
                           encoding="utf-8")
            tmp.replace(path)
        except (OSError, TypeError, ValueError):
            pass
    return value


def memo(conn: sqlite3.Connection, name: str, key, compute):
    """compute(), kept in memory for this key until the database changes (the last MEMO_SIZE keys per name)."""
    now = stamp(conn)
    table = _MEMO.setdefault((_db(conn), name), OrderedDict())
    hit = table.get(key)
    if hit is not None and hit[0] == now:
        table.move_to_end(key)
        return hit[1]
    value = compute()
    table[key] = (now, value)
    table.move_to_end(key)
    while len(table) > MEMO_SIZE:
        table.popitem(last=False)
    return value


def forget() -> None:
    """Drop everything kept in memory (the files are checked against the stamp anyway)."""
    _MEMORY.clear()
    _MEMO.clear()
    _STAMPS.clear()


def folder() -> Path | None:
    f = _file("x")
    return f.parent if f is not None else None


def info() -> tuple[int, int]:
    """(files, bytes) in the cache folder."""
    where = folder()
    if where is None or not where.exists():
        return 0, 0
    files = list(where.glob("*.json"))
    return len(files), sum(f.stat().st_size for f in files)


def clear() -> int:
    """Delete the kept files and forget what is in memory; everything is counted again when next asked for."""
    from isnady.core import log

    log.get("cache").info("⟲ kept files cleared")
    forget()
    where = folder()
    if where is None or not where.exists():
        return 0
    n = 0
    for f in where.glob("*.json"):
        try:
            f.unlink()
            n += 1
        except OSError:
            pass
    return n
