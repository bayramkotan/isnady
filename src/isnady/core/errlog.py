"""isnady.log in the data folder (ROB1, 2026-10-18): what went wrong, for a report — never shown unasked.

A page that cannot be built, or an error inside a click, is written here with its traceback and the version; the
window goes on. The file is kept short (the last 200 KB).
"""

from __future__ import annotations

import time
import traceback

from isnady import __version__
from isnady.data.paths import data_dir

FILE = "isnady.log"
LIMIT = 200_000


def path():
    return data_dir() / FILE


def write(what: str, exc: BaseException | None = None) -> None:
    try:
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        text = f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}  isnady {__version__}  {what}\n"
        if exc is not None:
            text += "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        old = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        p.write_text((old + text)[-LIMIT:], encoding="utf-8")
    except OSError:
        pass
