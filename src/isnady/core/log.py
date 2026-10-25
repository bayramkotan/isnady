"""isnady's log (LOG1): what it did and what went wrong, in the data folder, read in the window (Help → Log) and on
the command line (`iy log`). Qt-free.

Bayram (2026-10-25): "isnady icin bir log sistemi ---> venvstudio daki gibi!!!!"

  logs/isnady.log         every session: a banner (version, Python, Qt, system, data folder, profile, database,
                          books), then one line per event — a page built, a search, an import, an export, chains
                          read, a cache cleared, an error with its traceback. Kept to 2 MB, with five older files
                          beside it (isnady.log.1 … .5).
  logs/crash_<time>.log   a hard crash (a fault in Qt or Python itself, which no Python handler sees): the stack of
                          every thread, written by faulthandler. An empty one is removed when isnady ends normally.

A line: "2026-10-25 07:45:12.345  INFO   search    ✔ 'النيات' → 6 hadith in 41 ms". Each part of isnady logs under
its own name (`get("search")`), shown short in the log. The level is a setting (`log.level`: info, or debug for
more); errors are always written.
"""

from __future__ import annotations

import faulthandler
import logging
import logging.handlers
import os
import platform
import sys
import time
from pathlib import Path

from isnady import __version__

ROOT = "isnady"
FILE = "isnady.log"
FOLDER = "logs"
MAX_BYTES = 2_000_000
BACKUPS = 5
_FORMAT = "%(asctime)s.%(msecs)03d  %(levelname)-6s %(short)-9s %(message)s"
_DATE = "%Y-%m-%d %H:%M:%S"

_handler: logging.Handler | None = None
_crash_file = None
_crash_path: Path | None = None
_started = time.monotonic()


class _Short(logging.Filter):
    """The part of isnady a line comes from, short: "isnady.search" → "search"."""

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name
        record.short = name[len(ROOT) + 1:] if name.startswith(ROOT + ".") else ("isnady" if name == ROOT else name)
        return True


def folder() -> Path:
    from isnady.data.paths import data_dir

    return data_dir() / FOLDER


def path() -> Path:
    return folder() / FILE


def get(part: str = "") -> logging.Logger:
    """The logger of a part of isnady: get("search"), get("import"), get("export") …"""
    return logging.getLogger(f"{ROOT}.{part}" if part else ROOT)


def _level() -> int:
    try:
        from isnady import config

        return logging.DEBUG if str(config.get("log.level") or "info").lower() == "debug" else logging.INFO
    except Exception:
        return logging.INFO


def setup(kind: str = "window", banner: bool = True) -> Path | None:
    """Start the log for this run (the window, or the command line): the file, the banner, the crash file. Safe to
    call twice; never raises — isnady runs without a log when the folder cannot be written."""
    global _handler, _crash_file, _crash_path
    root = logging.getLogger(ROOT)
    if _handler is not None:
        return path()
    try:
        folder().mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(path(), maxBytes=MAX_BYTES, backupCount=BACKUPS,
                                                       encoding="utf-8", delay=False)
    except OSError:
        return None
    handler.setFormatter(logging.Formatter(_FORMAT, _DATE))
    handler.addFilter(_Short())
    root.addHandler(handler)
    root.setLevel(_level())
    root.propagate = False
    _handler = handler
    if banner:
        _banner(kind)
    if kind == "window":
        for old in folder().glob("crash_*.log"):    # empty ones of runs that ended without closing (killed, a test)
            try:
                if old.stat().st_size == 0:
                    old.unlink()
            except OSError:
                pass
        try:                                        # a hard crash: every thread's stack, in a file of its own
            _crash_path = folder() / time.strftime("crash_%Y%m%d_%H%M%S.log")
            _crash_file = _crash_path.open("w", encoding="utf-8")
            faulthandler.enable(_crash_file, all_threads=True)
        except (OSError, RuntimeError, ValueError):
            _crash_file = None
    return path()


def _banner(kind: str) -> None:
    log = get()
    if kind != "window":                # a command: one line, not a block before every `iy …`
        log.info("──── isnady %s · %s · Python %s · %s ────", __version__, kind, platform.python_version(),
                 platform.system())
        return
    line = "═" * 24
    log.info("%s isnady %s · %s · started %s %s", line, __version__, kind, time.strftime("%Y-%m-%d %H:%M"), line)
    log.info("▶ Python %s · %s %s (%s)", platform.python_version(), platform.system(), platform.release(),
             platform.machine())
    try:
        from PySide6 import __version__ as pyside

        log.info("▶ PySide6 %s", pyside)
    except ImportError:
        pass
    try:
        from isnady.data.paths import data_dir

        where = data_dir()
        log.info("▶ data folder %s", where)
        from isnady.core import profiles

        log.info("▶ profile %s", profiles.active())
        db_file = where / "isnady.db"
        if db_file.exists():
            log.info("▶ database %s (%.1f MB)", db_file, db_file.stat().st_size / 1e6)
        from isnady.core import language

        log.info("▶ interface %s · texts %s", language.ui_language(), ",".join(language.content_languages()) or "all")
    except Exception as exc:                       # the banner never stops isnady
        log.debug("banner: %s", exc)


def books_line(conn) -> None:
    """The books in the database, once per run (the window calls it when the database is open)."""
    try:
        n_books, n_hadith = conn.execute("SELECT COUNT(*), (SELECT COUNT(*) FROM hadiths) FROM collections").fetchone()
        n_people = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
        get().info("▶ %s books, %s hadith, %s narrators", f"{n_books:,}", f"{n_hadith:,}", f"{n_people:,}")
    except Exception:
        pass


def shutdown() -> None:
    """The end of a run: a closing line; the crash file removed when nothing was written to it."""
    global _crash_file
    get().info("■ closed after %s", _since(_started))
    if _crash_file is not None:
        try:
            faulthandler.disable()
            _crash_file.close()
            if _crash_path is not None and _crash_path.exists() and _crash_path.stat().st_size == 0:
                _crash_path.unlink()
        except OSError:
            pass
        _crash_file = None
    if _handler is not None:
        _handler.flush()


def _since(start: float) -> str:
    s = time.monotonic() - start
    return f"{s:.1f} s" if s < 60 else f"{int(s // 60)} min {int(s % 60)} s"


class timed:
    """with log.timed("search", "'النيات'") as t: … ; t.note = "6 hadith" — one line with the time it took."""

    def __init__(self, part: str, what: str, level: int = logging.INFO) -> None:
        self.log, self.what, self.level, self.note = get(part), what, level, ""

    def __enter__(self) -> "timed":
        self.start = time.perf_counter()
        return self

    def __exit__(self, kind, exc, _tb) -> None:
        ms = (time.perf_counter() - self.start) * 1000
        took = f"{ms:.0f} ms" if ms < 10000 else f"{ms / 1000:.1f} s"
        if kind is None:
            self.log.log(self.level, "✔ %s%s in %s", self.what, f" → {self.note}" if self.note else "", took)
        else:
            self.log.error("✖ %s failed after %s: %s: %s", self.what, took, kind.__name__, exc)


# ------------------------------------------------------------------ reading the log (Help → Log, `iy log`)
def files() -> list[Path]:
    """The log files, newest first: isnady.log, its older parts, then the crash reports."""
    where = folder()
    if not where.is_dir():
        return []
    main = [p for p in [where / FILE] + [where / f"{FILE}.{i}" for i in range(1, BACKUPS + 1)] if p.exists()]
    crashes = sorted(where.glob("crash_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return main + crashes


def read(file: Path | None = None, lines: int = 0, level: str = "", text: str = "") -> str:
    """The log (the last `lines` lines, 0 for all), only the lines of a level and above (warning, error) or holding
    a text; a traceback stays with its line."""
    file = file or path()
    try:
        content = file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    rows = content.splitlines()
    if level or text:
        order = {"debug": 0, "info": 1, "warning": 2, "error": 3}
        floor = order.get(level.lower(), 0)
        kept, keep = [], False
        for row in rows:
            head = row[25:31].strip().lower() if len(row) > 30 and row[4] == "-" and row[23:25] == "  " else None
            if head is not None:
                keep = order.get(head, 1) >= floor and (not text or text.lower() in row.lower())
            elif text and not level:
                keep = keep or text.lower() in row.lower()
            if keep:
                kept.append(row)
        rows = kept
    if lines:
        rows = rows[-lines:]
    return "\n".join(rows)


def clear() -> int:
    """Empty isnady.log and remove its older parts and the crash reports; returns how many files were touched."""
    n = 0
    for p in files():
        try:
            if p.name == FILE:
                if _handler is not None and hasattr(_handler, "stream") and _handler.stream:
                    _handler.stream.seek(0)
                    _handler.stream.truncate()
                else:
                    p.write_text("", encoding="utf-8")
            elif p != _crash_path:
                p.unlink()
            n += 1
        except OSError:
            pass
    return n


def delete_before(day: str) -> int:
    """Remove the lines of isnady.log older than a day ("2026-10-20"), the older parts and crash reports written
    before it; returns the lines removed from isnady.log."""
    removed = 0
    for p in files():
        if p.name == FILE:
            continue
        try:
            if time.strftime("%Y-%m-%d", time.localtime(p.stat().st_mtime)) < day and p != _crash_path:
                p.unlink()
        except OSError:
            pass
    main = path()
    if not main.exists():
        return 0
    rows = main.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    keep, cutting = [], True
    for row in rows:
        stamp = row[:10]
        if cutting and len(stamp) == 10 and stamp[4] == "-" and stamp[7] == "-":
            cutting = stamp < day
        if cutting:
            removed += 1
        else:
            keep.append(row)
    try:
        if _handler is not None and getattr(_handler, "stream", None):
            _handler.acquire()
            try:
                _handler.stream.seek(0)
                _handler.stream.truncate()
                _handler.stream.write("".join(keep))
                _handler.stream.flush()
            finally:
                _handler.release()
        else:
            main.write_text("".join(keep), encoding="utf-8")
    except OSError:
        return 0
    return removed


def open_folder_path() -> str:
    folder().mkdir(parents=True, exist_ok=True)
    return str(folder())


def environment_line() -> str:
    """For a report: version, Python, system, in one line."""
    return f"isnady {__version__} · Python {platform.python_version()} · {platform.system()} {platform.release()} · " \
           f"{os.environ.get('XDG_CURRENT_DESKTOP', '') or sys.platform}"
