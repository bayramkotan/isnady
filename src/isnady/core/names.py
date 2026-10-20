"""Narrators' names in Latin letters, Turkish and English, from the hand-written word list
(core.names_lexicon). A name is read from the start up to the first note ("ويقال", "مولاهم" …). A word the list
does not know is spelled letter by letter (`spell`): the consonants and long vowels are those of the Arabic, the
short vowels a guess — `reading()` says when that happened, so the screen can say so."""

import re
from functools import lru_cache

from isnady.core.names_lexicon import COMPOUNDS, STOPS, WORDS
from isnady.core.normalize import normalize


_SHADDA = "\u0651"


@lru_cache(maxsize=1)
def _tables():
    # a word told apart only by its shadda keeps it: "أبيّ" (Ubayy, a given name) is not "أبي" (Abi, "the father
    # of" — Hind bt. Abi Umayya, 2026-10-20: read "Übey Ümeyye" since 0.3.5)
    words = {normalize(k) + (_SHADDA if _SHADDA in k else ""): v for k, v in WORDS.items()}
    compounds = {tuple(normalize(w) for w in k.split()): v for k, v in COMPOUNDS.items()}
    stops = {normalize(w) for w in STOPS}
    return words, compounds, stops


def _key(word: str, words: dict, after: str = "", before: str = "") -> str:
    """The word list's key for a word. "أبي" followed by "بن" is Ubayy, the given name ('Abd Allah b. Ubayy b.
    Ka'b): a kunya's "Abi" is never followed by "b."; nor does a kunya ("أبو أبي", Abu Ubayy) begin with it."""
    key = normalize(word)
    if key + _SHADDA in words and (_SHADDA in word or normalize(after) in ("بن", "ابن")
                                   or normalize(before) in ("ابو", "ابا", "ام")):
        return key + _SHADDA
    return key


def reading(name: str, language: str = "tr", max_words: int = 8) -> tuple[str, bool]:
    """(Latin form, spelled): the name word by word from the word list, any word it does not know spelled
    letter by letter; spelled is True when a word was. ("", False) for a name with nothing to read."""
    known = latin(name, language, max_words)
    parts = [w for w in name.split() if w]
    if known and len(known.split()) >= len(parts):
        return known, False
    words, compounds, stops = _tables()
    index = 0 if language == "tr" else 1
    out, spelled, i = [], False, 0
    while i < len(parts) and len(out) < max_words:
        key = _key(parts[i], words, parts[i + 1] if i + 1 < len(parts) else "", parts[i - 1] if i else "")
        if key in stops:
            break
        pair = tuple(normalize(w) for w in parts[i:i + 2])
        if len(pair) == 2 and pair in compounds:
            out.append(compounds[pair][index])
            i += 2
            continue
        if key in words:
            out.append(words[key][index])
        else:
            word = spell(parts[i], language)
            if word:
                out.append(word)
                spelled = True
        i += 1
    while out and out[-1] in ("b.", "bint", "Ebû", "Abu", "Abi", "Ümmü", "Umm", "Ebâ", "Aba"):
        out.pop()
    text = " ".join(out)
    return (text[0].upper() + text[1:] if text else ""), spelled


_HARAKAT = re.compile("[\u064B-\u0652\u0670\u0640]")
_EN = {"ء": "'", "أ": "'", "إ": "'", "آ": "'", "ؤ": "'", "ئ": "'", "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "h",
       "خ": "kh", "د": "d", "ذ": "dh", "ر": "r", "ز": "z", "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "t", "ظ": "z",
       "ع": "'", "غ": "gh", "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n", "ه": "h", "و": "w", "ي": "y"}
_TR = {**_EN, "ث": "s", "ج": "c", "خ": "h", "ذ": "z", "ش": "ş", "غ": "g", "ق": "k", "و": "v"}
_SUN = set("تثدذرزسشصضطظلن")


def spell(word: str, language: str = "tr") -> str:
    """One Arabic word in Latin letters, letter by letter: رومان → "Ruman" / "Rûmân", الكوفي → "al-Kufi".
    The short vowels are not written in Arabic, so they are guessed (an "a" after the first letter)."""
    w = _HARAKAT.sub("", word).replace("ى", "ا")
    tr_ = language == "tr"
    table = _TR if tr_ else _EN
    article = ""
    if w.startswith("ال") and len(w) > 3:
        w = w[2:]
        article = ("e" + (_TR.get(w[0], "l") if w[0] in _SUN else "l") + "-") if tr_ else "al-"
    out: list[str] = []
    run = 0                                                  # consonants in a row, to put a guessed "a" between
    n = len(w)
    for i, ch in enumerate(w):
        prev_cons = i == 1 or (i > 1 and w[i - 1] not in "اوي")
        nxt = w[i + 1] if i + 1 < n else ""
        vowel = ""
        if ch == "ا" or (ch == "آ" and i):
            vowel = "â" if tr_ else "a"
        elif ch in "أإآ" and i == 0:
            vowel = "i" if ch == "إ" else "a"
        elif ch == "ة":
            vowel = "e" if tr_ else "a"
        elif ch in "وي" and i > 0 and prev_cons and (not nxt or nxt not in "اوي"):
            vowel = ("û" if ch == "و" else "î") if tr_ else ("u" if ch == "و" else "i")
        if vowel:
            out.append(vowel)
            run = 0
            continue
        if ch not in table:
            continue                                         # a stray letter or sign is left out
        c = table[ch]
        if c == "'" and i == 0:
            c = ""                                           # no mark at the start: Ali, Umar
        # the short vowels are not written: "a" after the first letter, and never three consonants in a row
        if run and (i == 1 or run >= 2):
            out.append("a")
            run = 0
        out.append(c)
        run += 1
    text = "".join(out).strip("'")
    if not text:
        return ""
    return article + text[0].upper() + text[1:] if article else text[0].upper() + text[1:]


def latin(name: str, language: str = "tr", max_words: int = 8) -> str | None:
    """'tr' or 'en' form of an Arabic name from the word list, or None when its first words are not all known.
    At least the first name and, if the Arabic has one, the father ("X b. Y") must be readable."""
    words, compounds, stops = _tables()
    index = 0 if language == "tr" else 1
    parts = [w for w in name.split() if w]
    out, i, read = [], 0, 0
    while i < len(parts) and read < max_words:
        key = _key(parts[i], words, parts[i + 1] if i + 1 < len(parts) else "", parts[i - 1] if i else "")
        if key in stops:
            break
        pair = tuple(normalize(w) for w in parts[i:i + 2])
        if len(pair) == 2 and pair in compounds:
            out.append(compounds[pair][index])
            i, read = i + 2, read + 2
            continue
        if key in words:
            out.append(words[key][index])
            i, read = i + 1, read + 1
            continue
        break                                   # an unknown word: the name ends here, or is not given at all
    if not out:
        return None
    needs_father = len(parts) > 2 and normalize(parts[1]) == "بن"
    if needs_father and read < 3:
        return None                             # "X b." with the father unknown: not given
    while out and out[-1] in ("b.", "bint", "Ebû", "Abu", "Abi", "Ümmü", "Umm", "Ebâ", "Aba"):
        out.pop()
    text = " ".join(out)
    return text[0].upper() + text[1:] if text else None
