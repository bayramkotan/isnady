"""Narrators' names in Latin letters, Turkish and English, from the hand-written word list
(core.names_lexicon). A name is given only as far as its words are known: from the start up to the first
note ("ويقال", "مولاهم" …) — never half a name with Arabic left inside, never a guessed reading."""

from functools import lru_cache

from isnady.core.names_lexicon import COMPOUNDS, STOPS, WORDS
from isnady.core.normalize import normalize


@lru_cache(maxsize=1)
def _tables():
    words = {normalize(k): v for k, v in WORDS.items()}
    compounds = {tuple(normalize(w) for w in k.split()): v for k, v in COMPOUNDS.items()}
    stops = {normalize(w) for w in STOPS}
    return words, compounds, stops


def latin(name: str, language: str = "tr", max_words: int = 8) -> str | None:
    """'tr' or 'en' form of an Arabic name, or None when its first words are not all known.
    At least the first name and, if the Arabic has one, the father ("X b. Y") must be readable."""
    words, compounds, stops = _tables()
    index = 0 if language == "tr" else 1
    parts = [w for w in name.split() if w]
    out, i, read = [], 0, 0
    while i < len(parts) and read < max_words:
        key = normalize(parts[i])
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
