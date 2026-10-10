"""A ready database from a file on this computer: isnady.db, or the isnady-db-<date>.zip that
tools/publish_database.py makes for the isnady-data Release.

The file is checked (a zip must hold isnady.db; the database must be an isnady database this version can open;
a database.json beside the zip, when there is one, must give the same sha256) and STAGED in the data folder as
isnady.db.incoming. It takes the place of the current database the next time a database connection is opened in
a fresh start of isnady — the open database cannot be replaced under a running window, and on Windows not at all
while it is open. The database it replaces is kept as isnady.<date-time>.bak.db, never deleted.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from isnady.data.paths import db_path

INCOMING = ".incoming"


class ReadyError(Exception):
    """The file cannot be used; the message is meant for the user."""


def incoming_path() -> Path:
    return db_path().with_name(db_path().name + INCOMING)


def _check(path: Path) -> dict:
    from isnady.data.db import SCHEMA_VERSION

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        books = conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0]
        hadith = conn.execute("SELECT COUNT(*) FROM hadiths").fetchone()[0]
        conn.close()
    except sqlite3.Error as exc:
        raise ReadyError(f"Not an isnady database: {path.name} ({exc})") from exc
    if version > SCHEMA_VERSION:
        raise ReadyError(f"The database is newer (schema {version}) than this isnady reads ({SCHEMA_VERSION}). "
                         "Update isnady first.")
    return {"schema": version, "books": books, "hadith": hadith}


def stage(file: str | Path) -> dict:
    """Check a database file (isnady.db or a zip holding it) and stage it for the next start."""
    src = Path(file).expanduser()
    if not src.is_file():
        raise ReadyError(f"File not found: {src}")
    target = incoming_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".part")
    if zipfile.is_zipfile(src):
        sidecar = src.with_name("database.json")
        if sidecar.exists():
            try:
                expected = json.loads(sidecar.read_text(encoding="utf-8")).get("sha256")
            except (OSError, ValueError):
                expected = None
            if expected and hashlib.sha256(src.read_bytes()).hexdigest() != expected:
                raise ReadyError(f"{src.name} does not match the sha256 in database.json beside it: the download "
                                 "is incomplete or the file was changed.")
        with zipfile.ZipFile(src) as z:
            name = next((n for n in z.namelist() if n.endswith("isnady.db")), None)
            if name is None:
                raise ReadyError(f"{src.name} holds no isnady.db.")
            with z.open(name) as r, open(tmp, "wb") as w:
                shutil.copyfileobj(r, w, 1 << 20)
    else:
        shutil.copyfile(src, tmp)
    try:
        info = _check(tmp)
    except ReadyError:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(target)
    return info


def pending() -> bool:
    return incoming_path().exists()


def apply_pending() -> Path | None:
    """Put a staged database in place (called before the first connection of a start). Returns the backup."""
    incoming = incoming_path()
    if not incoming.exists():
        return None
    current = db_path()
    backup = None
    if current.exists():
        backup = current.with_name(f"isnady.{datetime.now():%Y%m%d-%H%M%S}.bak.db")
        current.replace(backup)
        for extra in ("-wal", "-shm"):
            side = current.with_name(current.name + extra)
            if side.exists():
                side.replace(backup.with_name(backup.name + extra))
    incoming.replace(current)
    return backup
