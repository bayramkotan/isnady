"""Book titles and chapter titles in the interface language (T1, 2026-10-11).

The sources give chapter titles in English only — every language file of isnady-data carries the same English
titles ("Revelation", "Belief" …) — so the Turkish of Sahih al-Bukhari was shown under English chapter titles.
isnady keeps its own titles: `isnady/assets/i18n/titles/<code>.json` holds {"chapters": {English: title},
"books": {book key: title}} for each language that has them (tr, ar). A title is looked for in this order:

1. a title the imported edition in that language really gives (al-Adab al-Mufrad, Bulugh al-Maram, Mishkat,
   Riyad al-Salihin and al-Shama'il give Arabic chapter titles of their own);
2. isnady's table for that language;
3. the title as the source wrote it (English).

Book titles: isnady's table, then the Arabic title of the catalog (ar), then the English title of the catalog
("Sahih al-Bukhari"), then the name the import gave the collection ("Sahih al Bukhari"). Qt-free; the command
line stays in English (the interface language there is English).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources

from isnady.core import i18n

# the language of an edition as the database names it → the interface language code
EDITION_LANGUAGE = {"tr": "Turkish", "ar": "Arabic", "en": "English", "ur": "Urdu", "id": "Indonesian",
                    "bn": "Bengali", "fr": "French", "ru": "Russian"}


@lru_cache(maxsize=None)
def _table(code: str) -> dict:
    try:
        path = resources.files("isnady.assets").joinpath("i18n", "titles", f"{code}.json")
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ModuleNotFoundError):
        return {"chapters": {}, "books": {}}
    return {"chapters": data.get("chapters", {}), "books": data.get("books", {})}


def _clean(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").replace("ـ", "")).strip()


def chapter(title: str, lang: str | None = None, own: str | None = None) -> str:
    """A chapter title in the language: own (the title the edition in that language gives, when it differs from
    the English one), else isnady's table, else the title as it is."""
    code = lang or i18n.language()
    if code == "en" or not title:
        return title
    if own and _clean(own) and _clean(own) != _clean(title):
        return _clean(own)
    return _table(code)["chapters"].get(_clean(title), title)


@lru_cache(maxsize=1)
def _catalog() -> dict[str, dict]:
    try:
        from isnady.core.repositories import bundled

        return {e["book"]: e for e in bundled().get("isnady", {}).get("entries", []) if e.get("book")}
    except Exception:      # a broken install must not stop a page
        return {}


def book(key: str, fallback: str = "", lang: str | None = None) -> str:
    """A book's title in the language ("Sahîh-i Buhârî", "صحيح البخاري", "Sahih al-Bukhari"); the compiler
    after a dash in the catalog's English title is left out."""
    code = lang or i18n.language()
    if code != "en":
        own = _table(code)["books"].get(key)
        if own:
            return own
        if code == "ar" and _catalog().get(key, {}).get("title_ar"):
            return _catalog()[key]["title_ar"]
    entry = _catalog().get(key)
    if entry and entry.get("title"):
        return entry["title"].split(" — ")[0]
    return fallback or key


@lru_cache(maxsize=1)
def _names() -> dict[str, str]:
    """Every English spelling of a book's title → its key: the catalog's titles and a folded form of them, so the
    name an import gave ("Sahih al Bukhari", "Jami At Tirmidhi") is found too."""
    out = {}
    for key, e in _catalog().items():
        for name in (e.get("title", ""), e.get("title", "").split(" — ")[0]):
            if name:
                out[name] = key
                out[_fold(name)] = key
    return out


def _fold(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower().replace("al-", "al").replace(" at ", " al").replace(" an ", " al"))


def book_named(name: str, lang: str | None = None, conn=None) -> str:
    """A title given by name (as the statistics keep them) in the language: the key is looked up by the name, by
    a folded spelling of it, or in the database; a name isnady cannot place is shown as it is."""
    key = _names().get(name) or _names().get(_fold(name))
    if key is None and conn is not None:
        row = conn.execute("SELECT key FROM collections WHERE name = ?", (name,)).fetchone()
        key = row[0] if row else None
    return book(key, name, lang) if key else name


def edition_titles(conn, collection_id: int, lang: str | None = None) -> dict[int, str]:
    """{chapter number: title} of one collection in the language: the chapter titles of the edition in that
    language where it gives its own, isnady's table for the rest."""
    code = lang or i18n.language()
    english, first, own = {}, {}, {}
    wanted = EDITION_LANGUAGE.get(code)
    for number, title, language in conn.execute(
            """SELECT s.number, t.title, e.language FROM sections s JOIN section_titles t ON t.section_id = s.id
               JOIN editions e ON e.id = t.edition_id WHERE s.collection_id = ?""", (collection_id,)):
        if not title or not title.strip():
            continue
        if language == "English":
            english[number] = title.strip()
        first.setdefault(number, title.strip())
        if wanted and language == wanted:
            own[number] = title.strip()
    return {n: chapter(english.get(n) or first[n], code, own.get(n)) for n in first}
