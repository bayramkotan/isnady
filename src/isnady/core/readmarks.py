"""Where the reader is in each book (BM3, 2026-10-25): "Kitaplarda nerede kaldım?".

Two things, both kept with the profile (state.json, so every profile has its own and a profile file carries them):

- the place each book was last read — its chapter and the hadith the reader had come to — kept by itself as the
  reader moves on, so a book opens where it was left ("continue where you left off");
- markers the reader puts himself and names ("Namaz bahsi", "Ramazan okuması"), as many as he wants, in any book.

They are not the bookmarks (BM1): a bookmark keeps a thing (a hadith, a narrator) in a folder; a marker keeps a
place in the reading of a book. Qt-free: the Books page and `iy book … --resume / --mark / --marks` use the same.

A place is kept by what survives a new import: the book's key, the chapter's label in the book ("3", "12") and the
hadith's number — never the database's row ids.
"""

from __future__ import annotations

import time
import uuid

from isnady import config

LAST = "reader.marks.last"            # {book key: place}
NAMED = "reader.marks.named"          # [place with "id" and "name"], the newest first
LIMIT = 200


def _place(book: str, chapter: str = "", number: str = "", title: str = "", place: int = 0) -> dict:
    return {"book": book, "chapter": str(chapter or ""), "number": str(number or ""), "title": title or "",
            "place": int(place or 0), "at": time.time()}


def _clean(raw) -> dict | None:
    if not isinstance(raw, dict) or not raw.get("book"):
        return None
    out = _place(str(raw["book"]), raw.get("chapter", ""), raw.get("number", ""), raw.get("title", ""),
                 raw.get("place") or 0)
    out["at"] = float(raw.get("at") or 0)
    if raw.get("id"):
        out["id"] = str(raw["id"])
        out["name"] = str(raw.get("name") or "")
    return out


# ---------------------------------------------------------------------- the last place in each book
def remember(book: str, chapter: str = "", number: str = "", title: str = "", place: int = 0) -> None:
    """The reader is here now (called as he reads; the same place again changes nothing but the time)."""
    if not book:
        return
    data = config.state_get(LAST, {}) or {}
    data = data if isinstance(data, dict) else {}
    data[book] = _place(book, chapter, number, title, place)
    config.state_set(LAST, data)


def last(book: str) -> dict | None:
    data = config.state_get(LAST, {}) or {}
    return _clean(data.get(book)) if isinstance(data, dict) else None


def recent(limit: int = 10) -> list[dict]:
    """The books read, the most recent first, each with its last place."""
    data = config.state_get(LAST, {}) or {}
    places = [p for p in (_clean(v) for v in (data.values() if isinstance(data, dict) else [])) if p]
    return sorted(places, key=lambda p: -p["at"])[:limit]


def forget(book: str | None = None) -> int:
    """Forget the last place of one book, or of every book; returns how many were forgotten."""
    data = config.state_get(LAST, {}) or {}
    data = data if isinstance(data, dict) else {}
    if book is None:
        n = len(data)
        data = {}
    else:
        n = int(data.pop(book, None) is not None)
    config.state_set(LAST, data)
    return n


# ---------------------------------------------------------------------- the reader's own markers
def marks(book: str | None = None) -> list[dict]:
    raw = config.state_get(NAMED, []) or []
    out = [m for m in (_clean(r) for r in (raw if isinstance(raw, list) else [])) if m and m.get("id")]
    return [m for m in out if book is None or m["book"] == book]


def add(name: str, book: str, chapter: str = "", number: str = "", title: str = "", place: int = 0) -> dict:
    """A marker at this place; a marker of the same name is moved here instead of kept twice."""
    name = " ".join((name or "").split()) or title or book
    mark = _place(book, chapter, number, title, place)
    mark["id"] = uuid.uuid4().hex[:10]
    mark["name"] = name
    kept = [m for m in marks() if _fold(m["name"]) != _fold(name)]
    config.state_set(NAMED, ([mark] + kept)[:LIMIT])
    return mark


def _fold(text: str) -> str:
    """Case left out, the Turkish İ/ı too ("İlim" is found by "ilim")."""
    return (text or "").replace("İ", "i").replace("ı", "i").replace("I", "i").casefold().replace("\u0307", "")


def find(text: str) -> dict | None:
    """A marker by its id, or by its name (whole, or the start of it)."""
    raw = (text or "").strip()
    text = _fold(raw)
    every = marks()
    if not text:
        return None
    return (next((m for m in every if m["id"] == raw or _fold(m["name"]) == text), None)
            or next((m for m in every if _fold(m["name"]).startswith(text)), None))


def rename(mark_id: str, name: str) -> bool:
    every = marks()
    for m in every:
        if m["id"] == mark_id and name.strip():
            m["name"] = " ".join(name.split())
            config.state_set(NAMED, every)
            return True
    return False


def remove(mark_id: str) -> bool:
    every = marks()
    kept = [m for m in every if m["id"] != mark_id]
    config.state_set(NAMED, kept)
    return len(kept) != len(every)


# ---------------------------------------------------------------------- a place in the database
def place_of(conn, book: str, chapter_id: int | None, hadith_id: int | None = None) -> dict:
    """What is kept for a chapter (and a hadith in it): the chapter's label, its place in the reading order, the
    hadith's number and a title to show."""
    from isnady.core import works

    out = {"book": book, "chapter": "", "number": "", "title": "", "place": 0}
    if chapter_id:
        node = works.node(conn, chapter_id)
        if node:
            out["chapter"] = node["label"] or ""
            out["title"] = node["title"] or ""
            work = works.find_work(conn, book)
            if work:
                order = works.reading_order(conn, work["id"])
                out["place"] = order.index(chapter_id) + 1 if chapter_id in order else 0
    if hadith_id:
        row = conn.execute("SELECT number FROM hadiths WHERE id = ?", (hadith_id,)).fetchone()
        out["number"] = row[0] if row else ""
    return out


def resolve(conn, mark: dict) -> tuple[int | None, int | None]:
    """(chapter id, hadith id) of a kept place in this database: by the hadith's number first, then the chapter's
    label, then its place in the reading order."""
    from isnady.core import isnad, works

    book = mark.get("book") or ""
    work = works.find_work(conn, book)
    if work is None:
        return None, None
    hid = isnad.hadith_id(conn, book, mark["number"]) if mark.get("number") else None
    if hid is not None:
        chapter = works.chapter_of_hadith(conn, hid)
        if chapter is not None:
            return chapter, hid
    if mark.get("chapter"):
        row = conn.execute("SELECT id FROM work_nodes WHERE work_id = ? AND label = ? ORDER BY id LIMIT 1",
                           (work["id"], mark["chapter"])).fetchone()
        if row:
            order = works.reading_order(conn, work["id"])
            if row[0] in order:
                return row[0], hid
    order = works.reading_order(conn, work["id"])
    if mark.get("place") and 0 < int(mark["place"]) <= len(order):
        return order[int(mark["place"]) - 1], hid
    return (order[0] if order else None), hid


def describe(mark: dict, book_title: str = "") -> str:
    """"Sahih al-Bukhari › 3. Knowledge · hadith 59" — plain words for a place."""
    from isnady.core.i18n import tr

    parts = [book_title or mark.get("book", "")]
    chapter = ((mark.get("chapter") + ". ") if mark.get("chapter") else "") + (mark.get("title") or "")
    if chapter.strip():
        parts.append(chapter.strip())
    text = " › ".join(parts)
    if mark.get("number"):
        text += " · " + tr("hadith {number}", number=mark["number"])
    return text
