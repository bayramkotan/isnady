"""Tables of contents isnady keeps for books whose data carry no chapters (BK2, 2026-10-17).

Musnad Ahmad (26,363 hadith) and Sunan al-Darimi (3,367) come from Open Hadith Data as numbered texts only, so
the Books page showed each as one chapter, "Without a chapter in the source". `isnady/assets/chapters/<key>.json`
holds the book's own headings, two levels deep:

    {"book": "ahmad", "version": 1, "about": …, "source": …,
     "parts":    [{"ar": "مسند العشرة المبشرين بالجنة", "en": "The Ten promised Paradise", "tr": "…"}, …],
     "chapters": [["1", 0, "مسند أبي بكر الصديق رضي الله عنه"], ["78", 0, "مسند عمر بن الخطاب …"], …]}

A chapter is [the number of its first hadith, its part, its Arabic title, (its Turkish title, its English title)]; it
runs to the hadith before the next chapter's first. The parts (the Musnad's thirteen parts, al-Darimi's books) are
written in English, Turkish and Arabic. The Musnad's chapters — each Companion's musnad — carry the Companion's name
in Turkish and English too (BK2b, written by hand and checked; "(r.a.)", "(RA)" as the heading has it, or for a
named Companion where it has none); al-Darimi's 1,382 chapter titles keep the Arabic of the edition. The headings were placed at their hadith by matching the texts with an edition in OpenITI
(tools: Handoff "BK2").

core.works builds the reader's tree from this table — part → chapter → hadith — only while the imported data
have no chapters of their own; nothing is written into the imported tables.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources

from isnady.core import i18n


@lru_cache(maxsize=None)
def table(key: str) -> dict | None:
    """The table of contents isnady keeps for a book, or None."""
    try:
        path = resources.files("isnady.assets").joinpath("chapters", f"{key}.json")
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ModuleNotFoundError):
        return None
    if not data.get("chapters") or not data.get("parts"):
        return None
    return data


def stamp(key: str) -> str:
    """Part of the reader tree's stamp: the tree is built again when the table changes."""
    data = table(key)
    return f"toc{data.get('version', 1)}:{len(data['chapters'])}" if data else ""


@lru_cache(maxsize=1)
def _part_names() -> dict[str, dict]:
    """{English part name: {"ar", "en", "tr"}} of every table, for showing a part in the interface language."""
    out: dict[str, dict] = {}
    try:
        folder = resources.files("isnady.assets").joinpath("chapters")
        for f in folder.iterdir():
            if f.name.endswith(".json"):
                for p in json.loads(f.read_text(encoding="utf-8")).get("parts", []):
                    out[p["en"]] = p
    except (OSError, ValueError, ModuleNotFoundError):
        pass
    return out


def part_title(title: str, lang: str | None = None) -> str | None:
    """A part's name in the language (the tree keeps it in English), or None when it is not a part of a table."""
    names = _part_names().get(title or "")
    if not names:
        return None
    code = lang or i18n.language()
    return names.get(code) or names["en"]


def plan(key: str, hadith: list[tuple[int, str, float | None]]) -> list[tuple[dict, list[tuple[int, list]]]] | None:
    """The book's hadith (id, number, sort) in reading order, laid out by the table:
    [(part, [(chapter number, Arabic title, [(hadith id, hadith number), …]), …]), …]; None without a table."""
    data = table(key)
    if data is None or not hadith:
        return None
    index = {number: i for i, (_hid, number, _sort) in enumerate(hadith)}
    starts = []
    for n, row in enumerate(data["chapters"], 1):
        first, part, title = row[0], row[1], row[2]
        if first in index:
            starts.append((index[first], n, part, title))
    if not starts:
        return None
    starts.sort()
    starts[0] = (0,) + starts[0][1:]                  # a hadith before the first heading goes to the first chapter
    out: list[tuple[dict, list]] = []
    for k, (begin, n, part, title) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(hadith)
        rows = [(hid, number) for hid, number, _s in hadith[begin:end]]
        if not rows:
            continue
        if not out or out[-1][0] is not data["parts"][part]:
            out.append((data["parts"][part], []))
        out[-1][1].append((n, title, rows))
    return out


def chapter_title(key: str, number: int, lang: str | None = None) -> str | None:
    """A chapter's title in the language (Turkish and English where the table has them), or None."""
    data = table(key)
    if data is None or not 1 <= number <= len(data["chapters"]):
        return None
    row = data["chapters"][number - 1]
    code = lang or i18n.language()
    if code == "tr" and len(row) > 3 and row[3]:
        return row[3]
    if code not in ("tr", "ar", "fa", "ur", "prs", "ps", "ug") and len(row) > 4 and row[4]:
        return row[4]
    return row[2]
