"""A ready database from a file on this computer: isnady.db, or the isnady-db-<date>.zip that
tools/publish_database.py makes for the isnady-data Release.

The file is checked (a zip must hold isnady.db; the database must be an isnady database this version can open;
a database.json beside the zip, when there is one, must give the same sha256) and STAGED in the data folder as
isnady.db.incoming. It takes the place of the current database the next time a database connection is opened in
a fresh start of isnady — the open database cannot be replaced under a running window, and on Windows not at all
while it is open. The database it replaces is kept as isnady.<date-time>.bak.db, never deleted.

Or from isnady-data itself (DB-READY, 0.7.5): available() reads isnady-data's database.json (what
tools/publish_database.py writes with each release: date, schema, books, hadith, size, sha256, url), download()
fetches that zip into the data folder, checks its size and sha256, and stages it as above. The first start offers it
when the database is empty, beside importing book by book; `iy database download` and Data Sources do the same.
ISNADY_DATABASE_INFO points to another database.json (a URL or a file: a copy of isnady-data, the tests).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from isnady.data.paths import db_path

INCOMING = ".incoming"
INFO_URL = "https://raw.githubusercontent.com/bayramkotan/isnady-data/main/database.json"


class ReadyError(Exception):
    """The file cannot be used; the message is meant for the user."""


def incoming_path() -> Path:
    return db_path().with_name(db_path().name + INCOMING)


def _check(path: Path) -> dict:
    from isnady.data.db import SCHEMA_VERSION

    try:
        # immutable: a database copied in WAL mode is read without leaving -wal and -shm files beside it
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
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


# ------------------------------------------------------------------ the ready database of isnady-data (DB-READY)
def info_location() -> str:
    return os.environ.get("ISNADY_DATABASE_INFO") or INFO_URL


def megabytes(size: int) -> int:
    """A size in whole megabytes (10^6), rounded half up — the same number in both isnady programs."""
    return (int(size) + 500_000) // 1_000_000


def available(timeout: float | None = 30) -> dict:
    """isnady-data's ready database as its database.json describes it, with "url" made absolute and "usable" True
    when this isnady can open it (its schema is not newer). ReadyError when it cannot be read."""
    from isnady.data import fetch
    from isnady.data.db import SCHEMA_VERSION

    where = info_location()
    try:
        info = json.loads(fetch.read_bytes(where, timeout=timeout).decode("utf-8"))
    except (fetch.ResourceError, ValueError) as exc:
        raise ReadyError(f"The ready database of isnady-data cannot be read: {exc}") from exc
    if not isinstance(info, dict) or not info.get("url"):
        raise ReadyError("The ready database of isnady-data cannot be read: database.json names no file.")
    info["url"] = fetch.resolve(where, str(info["url"]))
    info["file"] = str(info.get("file") or Path(info["url"]).name)
    for key in ("schema", "books", "hadith", "texts", "narrators", "grades", "size"):
        try:
            info[key] = int(info.get(key) or 0)
        except (TypeError, ValueError):
            info[key] = 0
    info["usable"] = info["schema"] <= SCHEMA_VERSION
    return info


def describe(info: dict) -> str:
    """One line: the date, the books, the hadith and the size (iy database download --check, the dialogs)."""
    return (f"{info.get('date') or '?'}: {info['books']} books, {info['hadith']:,} hadith, "
            f"{info['narrators']:,} narrators, {megabytes(info['size']):,} MB")


def download(info: dict | None = None, progress=None) -> dict:
    """Download isnady-data's ready database into the data folder, check it (size, sha256, an isnady database this
    version opens) and stage it for the next start. progress(done, total) while it comes. Returns stage()'s info."""
    from isnady.data import fetch
    from isnady.data.db import SCHEMA_VERSION

    info = info or available()
    if not info.get("usable"):
        raise ReadyError(f"The ready database of isnady-data is newer (schema {info['schema']}) than this isnady "
                         f"reads ({SCHEMA_VERSION}). Update isnady first.")
    target = incoming_path().with_name(Path(info["file"]).name)
    part = target.with_name(target.name + ".part")
    try:
        got = fetch.save_to(info["url"], part, progress)
    except fetch.ResourceError as exc:
        raise ReadyError(f"The ready database could not be downloaded: {exc}") from exc
    try:
        if info["size"] and got != info["size"]:
            raise ReadyError(f"The download is incomplete ({got:,} of {info['size']:,} bytes); try again.")
        expected = str(info.get("sha256") or "")
        if expected:
            digest = hashlib.sha256()
            with open(part, "rb") as f:
                for block in iter(lambda: f.read(1 << 20), b""):
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise ReadyError(f"{info['file']} does not match the sha256 in database.json: the download is "
                                 "incomplete or the file was changed; try again.")
        part.replace(target)
        return stage(target)
    finally:
        part.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
