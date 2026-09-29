"""Text normalisation for search.

Arabic: diacritics (harakat, tanwin, shadda, sukun, Quranic marks), tatweel
and superscript alef are removed; alef forms become bare alef; alef maqsura
and hamza-on-ya become ya; hamza-on-waw becomes waw; ta marbuta becomes ha;
Persian kaf/ya become Arabic ones; Arabic-Indic digits become 0-9.

Latin scripts (Turkish, English, French ...): case-folded, accents removed,
dotless ı folded to i, apostrophes and ʿayn/hamza signs removed
("Mu'adh" = "Muadh", "Müslim" = "muslim").

normalize_with_map also returns, for every character of the normalised text,
the index of the original character it came from, so matches can be
highlighted in the original text.

NORMALIZER_VERSION must change whenever these rules change; the search index
is rebuilt when it does.
"""

import unicodedata
from functools import lru_cache

NORMALIZER_VERSION = 1

_REMOVE = set()
for lo, hi in ((0x0610, 0x061A), (0x064B, 0x065F), (0x06D6, 0x06DC), (0x06DF, 0x06E8), (0x06EA, 0x06ED)):
    _REMOVE.update(chr(c) for c in range(lo, hi + 1))
_REMOVE.update({"\u0640", "\u0670", "'", "`", "\u2018", "\u2019", "\u02bf", "\u02be", "\u02bc"})

_MAP = {
    "\u0623": "\u0627", "\u0625": "\u0627", "\u0622": "\u0627", "\u0671": "\u0627",  # أ إ آ ٱ -> ا
    "\u0649": "\u064a", "\u0626": "\u064a", "\u06cc": "\u064a",                      # ى ئ ی -> ي
    "\u0624": "\u0648",                                                               # ؤ -> و
    "\u0629": "\u0647",                                                               # ة -> ه
    "\u06a9": "\u0643",                                                               # ک -> ك
    "\u0131": "i",                                                                    # ı -> i
}
_MAP.update({chr(0x0660 + d): str(d) for d in range(10)})  # ٠..٩
_MAP.update({chr(0x06F0 + d): str(d) for d in range(10)})  # ۰..۹


@lru_cache(maxsize=4096)
def _fold_char(ch: str) -> str:
    if ch in _REMOVE:
        return ""
    if ch in _MAP:
        return _MAP[ch]
    if ord(ch) < 0x0600 or ord(ch) > 0x06FF:
        decomposed = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in decomposed if not unicodedata.combining(c))
        return base.casefold().replace("\u0131", "i")
    return ch


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    out: list[str] = []
    index_map: list[int] = []
    for i, ch in enumerate(text):
        folded = _fold_char(ch)
        for f in folded:
            out.append(f)
            index_map.append(i)
    return "".join(out), index_map


def normalize(text: str) -> str:
    return "".join(_fold_char(ch) for ch in text)
