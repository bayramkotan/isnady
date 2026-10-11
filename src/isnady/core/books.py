"""The imported hadith collections as the reader sees them: in a fixed order, Sunni first and Shia after them,
and only the ones he keeps active.

  order      the six books, the Muwatta, the Musnad and al-Darimi first (in their classical order), then the
             others by name — a name read without its leading apostrophe or article ('Uyun → Uyun, al-Kafi → Kafi);
             Shia collections after all Sunni ones, al-Kafi first.
  active     a book can be switched off in Settings → Books (`books.disabled`): it stays in the database but is
             left out of searches, book lists and statistics until switched on again.

Qt-free: the window, the command line and the statistics read the same list.
"""

from __future__ import annotations

import re
import sqlite3

from isnady import config
from isnady.core.i18n import N_

TRADITIONS = (("sunni", N_("Sunni")), ("shia", N_("Shia")), ("other", N_("Other")))
CANON = {"sunni": ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah", "malik", "ahmad", "darimi"],
         "shia": ["kafi", "faqih", "tahdhib", "istibsar"]}


def sort_name(name: str) -> str:
    """A title as it is alphabetised: no leading quote marks or 'ayn signs, no article (al-, an-, as- …)."""
    n = re.sub(r"^[\s'‘’`ʿʾ\"]+", "", name or "").lower()
    n = re.sub(r"^(al|an|as|ash|at|ad|adh|ar|az|az-z)[- ]", "", n)
    return re.sub(r"^[\s'‘’`ʿʾ\"]+", "", n)


def _key(row: dict) -> tuple:
    tradition = row["tradition"] if row["tradition"] in CANON else "other"
    order = [t for t, _l in TRADITIONS].index(tradition)
    canon = CANON.get(tradition, [])
    base = row["key"].split("-")[0]
    rank = canon.index(base) if base in canon else len(canon)
    return order, rank, sort_name(row.get("source_name") or row["name"]), row["key"]


def disabled() -> set[str]:
    return {k for k in str(config.get("books.disabled") or "").split(",") if k}


def set_active(key: str, active: bool) -> None:
    off = disabled()
    off.discard(key) if active else off.add(key)
    config.set("books.disabled", ",".join(sorted(off)))


def is_active(key: str) -> bool:
    return key not in disabled()


def all_books(conn: sqlite3.Connection, include_inactive: bool = False) -> list[dict]:
    """Every collection that has texts: key, name, tradition, hadith count, active — in reading order."""
    off = disabled()
    from isnady.core import titles

    # "name": the title in the interface language (core.titles); "source_name": as the import named it
    rows = [{"key": k, "name": titles.book(k, n), "source_name": n, "tradition": t or "sunni", "count": c,
             "active": k not in off}
            for k, n, t, c in conn.execute(
                """SELECT c.key, c.name, c.tradition, COUNT(DISTINCT h.id) FROM collections c
                   JOIN hadiths h ON h.collection_id = c.id
                   WHERE EXISTS (SELECT 1 FROM texts t WHERE t.hadith_id = h.id)
                   GROUP BY c.id""")]
    rows.sort(key=_key)
    return rows if include_inactive else [r for r in rows if r["active"]]


def order_sql(conn: sqlite3.Connection, column: str = "c.key") -> str:
    """An SQL expression that sorts by the reading order of the books (Sunni first, in their classical order; Shia
    after them) — for ORDER BY, so results come book by book as the book lists show them, never by title (a title
    sorted alphabetically put al-Kafi and 'Uyun before Sahih al-Bukhari)."""
    keys = [r["key"] for r in all_books(conn, include_inactive=True)]
    if not keys:
        # no book known yet (a new installation): by key. Never a bare number — "ORDER BY 0" is read as a column
        # number and fails ("1st ORDER BY term out of range"), which stopped isnady at start on a new computer
        return column
    whens = " ".join(f"WHEN '{k.replace(chr(39), chr(39) * 2)}' THEN {i}" for i, k in enumerate(keys))
    return f"CASE {column} {whens} ELSE {len(keys)} END"


def active_keys(conn: sqlite3.Connection) -> list[str] | None:
    """The keys to search when "all books" is asked for: None when every book is active (no filter needed)."""
    off = disabled()
    if not off:
        return None
    return [r["key"] for r in all_books(conn)]


def grouped(conn: sqlite3.Connection, include_inactive: bool = False) -> list[tuple[str, str, list[dict]]]:
    """[(tradition, label, books)] — Sunni, then Shia, then any other; empty groups left out."""
    books = all_books(conn, include_inactive)
    return [(t, label, [b for b in books if (b["tradition"] if b["tradition"] in CANON else "other") == t])
            for t, label in TRADITIONS if any((b["tradition"] if b["tradition"] in CANON else "other") == t
                                              for b in books)]


# ------------------------------------------------------------------ full names (NM2)
_FULL: dict[str, str] | None = None


def _full_names() -> dict[str, str]:
    """database key → the book's full name as isnady-data names it (musnad_ahmad_ibn_hanbal), from the catalog
    shipped with isnady."""
    global _FULL
    if _FULL is None:
        _FULL = {}
        try:
            from isnady.core.repositories import bundled

            for e in bundled().get("isnady", {}).get("entries", []):
                if e.get("book"):
                    _FULL[e["book"]] = e["id"]
        except Exception:      # a broken install must not stop a file name
            pass
    return _FULL


def title(key: str, fallback: str = "") -> str:
    """The book's title as isnady writes it, in the interface language (core.titles.book)."""
    from isnady.core import titles

    return titles.book(key, fallback)


def full_name(key: str) -> str:
    """The name a book is written as in files and folders: its full title with its compiler (never a bare name)."""
    return _full_names().get(key, key)


def resolve(name: str) -> str:
    """The database key of a book given by its full name, its key, or the id of an earlier version."""
    name = (name or "").strip()
    name = name[len("fawaz-"):] if name.startswith("fawaz-") else name
    back = {v: k for k, v in _full_names().items()}
    return back.get(name, name)
