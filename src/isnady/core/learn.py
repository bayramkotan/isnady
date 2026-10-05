"""Learn (G7) and the glossary (S1): the terms of hadith and its sciences, written for isnady with their
classical sources — each with its Arabic, its reading, a one-sentence definition (for hover) and a longer one, in
English and Turkish (more languages with I1). Qt-free; the GUI, the hover texts and `iy term` read it here."""

import json
from functools import lru_cache
from importlib import resources

from isnady.core.normalize import normalize

LANGUAGES = {"en": "English", "tr": "Türkçe"}
# grade groups of core.grades → the term that explains them
GROUP_TERM = {4: "sahih", 3: "hasan", 2: "daif", 1: "daif", 0: "mawdu"}


@lru_cache(maxsize=1)
def _data() -> dict:
    path = resources.files("isnady") / "assets" / "learn" / "terms.json"
    return json.loads(path.read_text(encoding="utf-8"))


def categories() -> dict:
    return _data()["categories"]


def terms() -> list[dict]:
    return _data()["terms"]


def get(term_id: str) -> dict | None:
    return next((t for t in terms() if t["id"] == term_id), None)


def name(term: dict, lang: str = "en") -> str:
    return term["tr"] if lang == "tr" else term["en"]


def search(text: str, lang: str = "en") -> list[dict]:
    """Terms whose name (English, Turkish, Arabic) or definition contains the words — names first."""
    words = normalize(text).split()
    if not words:
        return terms()
    hits = []
    for t in terms():
        names = normalize(" ".join([t["en"], t["tr"], t["ar"], t["id"].replace("_", " ")]))
        body = normalize(" ".join([t["short"]["en"], t["short"]["tr"], t["long"]["en"], t["long"]["tr"]]))
        if all(w in names for w in words):
            hits.append((0, t))
        elif all(w in names or w in body for w in words):
            hits.append((1, t))
    return [t for _r, t in sorted(hits, key=lambda h: h[0])]


def short(term_id: str, lang: str = "en") -> str:
    t = get(term_id)
    return f"{name(t, lang)} ({t['ar']}): {t['short'][lang]}" if t else ""


def for_group(group: int | None, lang: str = "en") -> str:
    """The hover text of a grade group (sahih, hasan, da'if, very weak, fabricated)."""
    return short(GROUP_TERM[group], lang) if group in GROUP_TERM else ""
