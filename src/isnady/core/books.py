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

TRADITIONS = (("sunni", "Sunni"), ("shia", "Shia"), ("other", "Other"))
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
    return order, rank, sort_name(row["name"]), row["key"]


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
    rows = [{"key": k, "name": n, "tradition": t or "sunni", "count": c, "active": k not in off}
            for k, n, t, c in conn.execute(
                """SELECT c.key, c.name, c.tradition, COUNT(DISTINCT h.id) FROM collections c
                   JOIN hadiths h ON h.collection_id = c.id
                   WHERE EXISTS (SELECT 1 FROM texts t WHERE t.hadith_id = h.id)
                   GROUP BY c.id""")]
    rows.sort(key=_key)
    return rows if include_inactive else [r for r in rows if r["active"]]


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
