"""One way to import a source, used by the command line and the window alike.

After the importer has written its rows, everything derived from them is
brought up to date in the same order every time: orphan rows are removed, the
search index is extended, chains are read, and narrators are identified.
"""

import sqlite3
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


def run_import(conn: sqlite3.Connection, request: ImportRequest,
               progress: Callable[[str], None] | None = None) -> tuple[ImportReport, dict]:
    """Import and bring every derived table up to date. Raises ResourceError / KeyError on failure."""
    say = progress or (lambda _m: None)
    importer = get_importer(request.format_id)
    source = SourceInfo(location=request.location, name=request.name, license=request.license,
                        origin=request.origin, tier=request.tier, auth=request.auth)
    report = importer.run(conn, source, request.options, progress=say)
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
    say = progress or (lambda _m: None)
    imported, failed = [], []
    try:
        _import_each(conn, requests, say, imported, failed)
    finally:
        from isnady.data import fetch

        fetch.forget_prefetched()
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
