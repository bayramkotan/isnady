"""Back to zero (RST1): the settings, the books, or everything of the profile in use. Qt-free: Settings → Reset and
`iy reset` both come here.

Bayram (2026-10-24): "Ayarlar altinda tum config'i silme olsun. Tum kitaplari silme de olsun. Sifir duruma
getirebilelim."

  settings   settings.json and state.json (what was chosen, where the reader was, recent searches): as at the first
             start. Bookmarks and profiles stay.
  books      every imported source — hadith books, rijal works, the user's own — out of the database, and the
             counts computed from them; the database file is made small again. Settings and bookmarks stay.
  everything both, and the bookmarks, the downloaded copies of the data repositories and the computed files: the
             profile as it was before isnady first ran.
"""

from __future__ import annotations

import shutil
import sqlite3


def settings() -> int:
    """Forget every setting and every remembered place; returns how many settings were stored."""
    from isnady import config

    n = config.reset("")
    config.state_forget("")
    config.forget()
    return n


def books(conn: sqlite3.Connection) -> int:
    """Remove every imported source and what came with it; returns how many sources there were."""
    from isnady.core import cache, search
    from isnady.data import db

    n = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    with conn:
        conn.execute("DELETE FROM sources")
        conn.execute("DELETE FROM persons")              # a narrator outlives his source (ON DELETE SET NULL)
    db.cleanup(conn)
    search.rebuild_index(conn)                           # the search index and its word list, now empty
    try:
        conn.execute("VACUUM")
    except sqlite3.Error:
        pass
    cache.clear()
    return n


def everything(conn: sqlite3.Connection) -> dict:
    """Books, settings, bookmarks, downloaded repositories and computed files: all of the profile in use."""
    from isnady.core import bookmarks, profiles

    out = {"books": books(conn), "settings": settings()}
    try:
        bookmarks.path().unlink()
        out["bookmarks"] = True
    except OSError:
        out["bookmarks"] = False
    repos = profiles.folder() / "repos"
    if repos.exists():
        shutil.rmtree(repos, ignore_errors=True)
    return out
