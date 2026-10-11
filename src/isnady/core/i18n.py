"""The interface in the reader's language (I1).

Every text the window shows is written in English in the code and passed through t():

    t("Recompute")                                   → "Yeniden hesapla" in Turkish
    t("{n:,} hadith in {books} books", n=n, books=b) → the template translated, then filled

The English text IS the key: a catalog is one JSON file per language in isnady/assets/i18n/<code>.json,
{"English text": "translation"}. A text a catalog does not have yet is shown in English — a half-translated
language still works, and the language menu says how much of it is translated (coverage()).

What is never translated: the Arabic of the sources, the names of books and people as the data gives them, the
scholars' own words of grading (sahih, da'if …) where they are terms of the science — those are explained in the
reader's language, the term itself kept (the glossary, Learn).

Qt-free, like all of isnady.core: the window and, later, the command line read the same catalogs.

Tools: python tools/i18n.py extract (the English catalog from the code: every t("…") call),
python tools/i18n.py check (what each language still lacks).
"""

from __future__ import annotations

import json
import re
import string
from functools import lru_cache
from importlib import resources

# code → (its own name, its English name, written right to left)
LANGUAGES: dict[str, tuple[str, str, bool]] = {
    "en": ("English", "English", False),
    "tr": ("Türkçe", "Turkish", False),
    "ar": ("العربية", "Arabic", True),
    "de": ("Deutsch", "German", False),
    "fr": ("Français", "French", False),
    "es": ("Español", "Spanish", False),
    "pt": ("Português", "Portuguese", False),
    "ru": ("Русский", "Russian", False),
    "id": ("Bahasa Indonesia", "Indonesian", False),
    "ms": ("Bahasa Melayu", "Malay", False),
    "hi": ("हिन्दी", "Hindi", False),
    "ur": ("اردو", "Urdu", True),
    "bn": ("বাংলা", "Bengali", False),
    "zh": ("中文", "Chinese", False),
    "ja": ("日本語", "Japanese", False),
    "ko": ("한국어", "Korean", False),
    "fa": ("فارسی", "Persian", True),
    "prs": ("دری", "Dari", True),
    "ps": ("پښتو", "Pashto", True),
    "az": ("Azərbaycan türkcəsi", "Azerbaijani Turkish", False),
    "uz": ("Oʻzbekcha", "Uzbek", False),
    "kk": ("Қазақша", "Kazakh", False),
    "ky": ("Кыргызча", "Kyrgyz", False),
    "tk": ("Türkmençe", "Turkmen", False),
    "ug": ("ئۇيغۇرچە", "Uyghur", True),
    "tt": ("Татарча", "Tatar", False),
    "ba": ("Башҡортса", "Bashkir", False),
    "crh": ("Qırımtatarca", "Crimean Tatar", False),
    "bs": ("Bosanski", "Bosnian", False),
    "sw": ("Kiswahili", "Swahili", False),
    "ha": ("Hausa", "Hausa", False),
}

# The languages' names in the interface languages that have them (the menu shows a language by its own name and
# by this one; English otherwise). Bayram: the language of Azerbaijan is "Azerbaycan Türkçesi", never "Azerbaycanca".
NAMES: dict[str, dict[str, str]] = {
    "tr": {"en": "İngilizce", "tr": "Türkçe", "ar": "Arapça", "de": "Almanca", "fr": "Fransızca",
           "es": "İspanyolca", "pt": "Portekizce", "ru": "Rusça", "id": "Endonezce", "ms": "Malayca",
           "hi": "Hintçe", "ur": "Urduca", "bn": "Bengalce", "zh": "Çince", "ja": "Japonca", "ko": "Korece",
           "fa": "Farsça", "prs": "Darice", "ps": "Peştuca", "az": "Azerbaycan Türkçesi", "uz": "Özbekçe",
           "kk": "Kazakça", "ky": "Kırgızca", "tk": "Türkmence", "ug": "Uygurca", "tt": "Tatarca",
           "ba": "Başkurtça", "crh": "Kırım Tatarcası", "bs": "Boşnakça", "sw": "Svahili", "ha": "Hausaca"},
    "ar": {"en": "الإنجليزية", "tr": "التركية", "ar": "العربية", "de": "الألمانية", "fr": "الفرنسية",
           "es": "الإسبانية", "pt": "البرتغالية", "ru": "الروسية", "id": "الإندونيسية", "ms": "الملايوية",
           "hi": "الهندية", "ur": "الأردية", "bn": "البنغالية", "zh": "الصينية", "ja": "اليابانية",
           "ko": "الكورية", "fa": "الفارسية", "prs": "الدرية", "ps": "البشتوية", "az": "التركية الأذربيجانية",
           "uz": "الأوزبكية", "kk": "الكازاخية", "ky": "القيرغيزية", "tk": "التركمانية", "ug": "الأويغورية",
           "tt": "التتارية", "ba": "الباشكيرية", "crh": "تتارية القرم", "bs": "البوسنية", "sw": "السواحيلية",
           "ha": "الهوسا"},
}


def name_of(code: str, lang: str | None = None) -> str:
    """A language's name in the interface language (or in English where that has no names yet)."""
    names = NAMES.get(lang or _current, {})
    return names.get(code) or LANGUAGES.get(code, (code, code, False))[1]


_current = "en"


@lru_cache(maxsize=None)
def catalog(code: str) -> dict[str, str]:
    """The translations of one language ({} for English or a language without a file)."""
    if code == "en":
        return {}
    try:
        path = resources.files("isnady") / "assets" / "i18n" / f"{code}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, FileNotFoundError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str) and v and not k.startswith("@")}


@lru_cache(maxsize=1)
def source() -> tuple[str, ...]:
    """Every English text of the interface (assets/i18n/en.json, written by tools/i18n.py extract)."""
    try:
        path = resources.files("isnady") / "assets" / "i18n" / "en.json"
        return tuple(k for k in json.loads(path.read_text(encoding="utf-8")) if not k.startswith("@"))
    except (OSError, ValueError, FileNotFoundError):
        return ()


def coverage(code: str) -> float:
    """The share of the interface translated into a language (1.0 for English)."""
    if code == "en":
        return 1.0
    keys = source()
    if not keys:
        return 0.0
    have = catalog(code)
    return sum(1 for k in keys if k in have) / len(keys)


def set_language(code: str) -> None:
    global _current
    _current = code if code in LANGUAGES else "en"


def language() -> str:
    return _current


def rtl(code: str | None = None) -> bool:
    return LANGUAGES.get(code or _current, ("", "", False))[2]


class _Keep(dict):
    """A template's {name} the caller did not give stays as it is, never an error."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _fill(text: str, values: dict) -> str | None:
    if not values:
        return text
    try:
        return string.Formatter().vformat(text, (), _Keep(values))
    except (ValueError, IndexError, KeyError, TypeError, AttributeError):
        return None


def t(text: str, /, **values) -> str:
    """text in the interface language, its {fields} filled from values (str.format, with format specs:
    t("{share:.1%} identified", share=0.43)). A translation that does not fill is shown in English."""
    translated = catalog(_current).get(text) if _current != "en" else None
    if translated:
        out = _fill(translated, values)
        if out is not None:
            return out
    out = _fill(text, values)
    return text if out is None else out


tr = t          # the name the window uses: "t" is too often a local name there (t = theme.current())


def n_(one: str, many: str, n: int, /, **values) -> str:
    """The singular or the plural template by n (n is passed to the template as {n})."""
    return t(one if n == 1 else many, n=n, **values)


def N_(text: str, /) -> str:
    """Marks a text for the catalog where it is defined (a table of labels at module level), translated where it
    is shown, with t(): the module is read once, the language can change after."""
    return text


_DATE_WORDS = re.compile(r"(?<![\w.])(d\.|c\.|AH|CE)(?![\w])")
_DATE_LABELS = {"d.": N_("d."), "c.": N_("c."), "AH": N_("AH"), "CE": N_("CE")}


def dates(text: str) -> str:
    """Translate the abbreviations of a date written in English ("d. 279 AH (892 CE)")."""
    if not text or language() == "en":
        return text
    return _DATE_WORDS.sub(lambda m: t(_DATE_LABELS[m.group(1)]), text)


def mark() -> str:
    """The direction mark of the interface (LRM, or RLM for a right-to-left language): put after Arabic words that
    are followed by a number, so "ثقة" and "rank 3 of 12" keep their order."""
    return "\u200f" if rtl() else "\u200e"
