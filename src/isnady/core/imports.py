"""One way to import a source, used by the command line and the window alike.

After the importer has written its rows, everything derived from them is
brought up to date in the same order every time: orphan rows are removed, the
search index is extended, chains are read, and narrators are identified.
"""

import json
import os
import sqlite3
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable

from isnady.core import isnad as core_isnad
from isnady.core import narrators as core_narrators
from isnady.core import search as core_search
from isnady.data import db
from isnady.data.fetch import Auth
from isnady.data.importers import ImportReport, SourceInfo, get_importer


@dataclass
class ImportRequest:
    format_id: str
    location: str
    name: str | None = None
    license: str | None = None
    tier: str | None = None
    origin: str = "user"
    auth: Auth = field(default_factory=Auth)
    options: dict = field(default_factory=dict)


# ---------------------------------------------------------------------- an import cut short (ROB1)
RUNNING_FILE = "import-running.json"


def _running_path():
    from isnady.data.paths import data_dir

    return data_dir() / RUNNING_FILE


@contextmanager
def _running(titles: list[str]):
    """A note in the data folder while an import runs, removed when it ends (well or not). Found at the next start,
    it says the import was cut short — the window was killed, the computer went off — and which books to import
    again (SQLite took back the book being written; the books before it stay)."""
    path = _running_path()
    try:
        path.write_text(json.dumps({"titles": titles, "pid": os.getpid(), "started": time.strftime("%Y-%m-%dT%H:%M:%S")},
                                   ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    try:
        yield
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def _alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except (OSError, ValueError, SystemError):
        return False
    return True


def interrupted() -> dict | None:
    """{"titles", "started"} of an import that did not finish, or None (none, or one still running elsewhere)."""
    path = _running_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    pid = data.get("pid")
    if isinstance(pid, int) and pid != os.getpid() and sys.platform != "win32" and _alive(pid):
        return None                      # another isnady is importing right now
    return {"titles": data.get("titles") or [], "started": data.get("started") or ""}


def forget_interrupted() -> None:
    try:
        _running_path().unlink()
    except OSError:
        pass


def run_import(conn: sqlite3.Connection, request: ImportRequest,
               progress: Callable[[str], None] | None = None) -> tuple[ImportReport, dict]:
    """Import and bring every derived table up to date. Raises ResourceError / KeyError on failure."""
    from isnady.core import log

    say = progress or (lambda _m: None)
    importer = get_importer(request.format_id)
    source = SourceInfo(location=request.location, name=request.name, license=request.license,
                        origin=request.origin, tier=request.tier, auth=request.auth)
    with log.timed("import", f"import {request.name or request.location} ({request.format_id})") as t, \
            _running([request.name or request.location]):
        report = importer.run(conn, source, request.options, progress=say)
        t.note = f"{getattr(report, 'hadith', '')} hadith, {getattr(report, 'texts', '')} texts".strip(", ")
    db.cleanup(conn)
    core_search.ensure_index(conn, progress=say)
    core_isnad.ensure_isnads(conn, progress=say)
    narrators = core_narrators.link_narrators(conn, progress=say)
    return report, narrators


def remove_source(conn: sqlite3.Connection, key: str) -> bool:
    with conn:
        removed = conn.execute("DELETE FROM sources WHERE key = ?", (key,)).rowcount
    db.cleanup(conn)
    return bool(removed)


def run_many(conn: sqlite3.Connection, requests: list[tuple[str, ImportRequest]],
             progress: Callable[[str], None] | None = None) -> tuple[list[tuple[str, ImportReport]], list[tuple[str, str]], dict]:
    """Import several sources, then bring the derived tables up to date ONCE.

    Returns (imported, failed, narrator stats). A source that fails does not stop the others.
    """
    from isnady.core import log

    say = progress or (lambda _m: None)
    imported, failed = [], []
    try:
        with log.timed("import", f"import of {len(requests)} source(s)") as t, \
                _running([label for label, _r in requests]):
            _import_each(conn, requests, say, imported, failed)
            t.note = f"{len(imported)} imported, {len(failed)} failed"
    finally:
        from isnady.data import fetch

        fetch.forget_prefetched()
    for label, why in failed:
        log.get("import").warning("⚠ %s: %s", label, why)
    db.cleanup(conn)
    core_search.ensure_index(conn, progress=say)
    core_isnad.ensure_isnads(conn, progress=say)
    narrators = core_narrators.link_narrators(conn, progress=say)
    return imported, failed, narrators


AHEAD = 3          # books downloaded ahead of the one being written (their files are held in memory until then)


def _ahead(request: ImportRequest) -> None:
    """Start downloading a public source before its turn."""
    from isnady.data import fetch

    if request.auth.kind != "none" or not fetch.is_url(request.location):
        return
    if request.format_id == "isnady":
        from isnady.data.importers import isnady_book

        isnady_book.prefetch(request.location, request.options)
    else:
        fetch.prefetch(request.location)


def _import_each(conn, requests, say, imported, failed) -> None:
    from isnady.data.fetch import ResourceError

    for i, (label, request) in enumerate(requests, 1):
        for _label, later in requests[i - 1: i + AHEAD]:
            _ahead(later)
        say(f"[{i}/{len(requests)}] {label}")
        try:
            importer = get_importer(request.format_id)
            source = SourceInfo(location=request.location, name=request.name, license=request.license,
                                origin=request.origin, tier=request.tier, auth=request.auth)
            imported.append((label, importer.run(conn, source, request.options, progress=say)))
        except (ResourceError, KeyError, ValueError) as exc:
            failed.append((label, str(exc.args[0] if exc.args else exc)))
