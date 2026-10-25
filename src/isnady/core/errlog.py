"""Errors, for a report — never shown unasked (ROB1, 2026-10-18). Since 0.4.8 they go to isnady's log (core.log,
logs/isnady.log in the data folder), with their traceback and the version, among everything else isnady did.

A page that cannot be built, or an error inside a click, is written here; the window goes on.
"""

from __future__ import annotations


def path():
    from isnady.core import log

    return log.path()


def write(what: str, exc: BaseException | None = None) -> None:
    try:
        from isnady.core import log

        if log._handler is None:
            log.setup("window")
        if exc is not None:
            log.get("error").error("✖ %s", what, exc_info=(type(exc), exc, exc.__traceback__))
        else:
            log.get("error").error("✖ %s", what)
    except Exception:
        pass
