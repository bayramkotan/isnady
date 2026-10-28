"""The huffaz (HFZ1): al-Dhahabi's Tadhkirat al-Huffaz (d. 748 AH) — the masters of hadith memorisation and criticism,
1,176 of them in 21 generations (tabaqat), from Abu Bakr al-Siddiq to al-Dhahabi's own teachers.

What isnady keeps is an index read from the OpenITI text (tools/build_huffaz.py), never the text itself:
  n        al-Dhahabi's number of the entry, through the whole work;
  tabaqa   his generation, as his own headings divide the book;
  name     the name he heads the entry with (its first words), and head: the first twelve words of the heading;
  rumuz    the sigla he puts before the name: whose of the six books narrate from him (al-Mizzi's signs);
  death    the year of death as al-Dhahabi writes it in words ("tuwuffiya sanata arba' wa-'ishrin wa-mi'a"), read by
           the builder; none when the entry gives none in that form;
  taqrib   the narrator's entry in Ibn Hajar's Taqrib when the same man is there: the name, the father and the
           grandfather agree and the two years of death are within three years (ten when four names agree).
The text of an entry is read only when the reader downloads the work (core.source_entries, "tadhkira").
"""

import json
import re
import sqlite3
from functools import lru_cache
from importlib import resources

from isnady.core.i18n import N_

WORK = "tadhkira"

# al-Mizzi's sigla as al-Dhahabi uses them: in whose book this man narrates
RUMUZ = {
    "ع": N_("the six books"),
    "4": N_("the four Sunan"),
    "خ": N_("al-Bukhari"),
    "خت": N_("al-Bukhari, without a full chain (ta'liq)"),
    "م": N_("Muslim"),
    "د": N_("Abu Dawud"),
    "مد": N_("Abu Dawud's Marasil"),
    "ت": N_("al-Tirmidhi"),
    "س": N_("al-Nasa'i"),
    "ق": N_("Ibn Majah"),
}

# how many al-Dhahabi says a generation holds, where his heading says it ("al-tabaqa al-tasi'a wa-'iddatuhum mi'a wa-sitta
# anfus"): set beside the count read here, so the reader sees how far the index agrees with the book
STATED = {9: 106, 11: 72, 14: 30, 15: 40, 17: 24, 18: 26, 19: 12, 20: 10, 21: 8}


@lru_cache(maxsize=1)
def index() -> list[dict]:
    """Every entry of the index, in al-Dhahabi's order."""
    path = resources.files("isnady.assets").joinpath("scholars", "huffaz.json")
    return json.loads(path.read_text(encoding="utf-8"))["huffaz"]


def rumuz_text(rumuz: list[str]) -> list[str]:
    """What each sign means (untranslated msgids: the caller translates)."""
    return [RUMUZ.get(r, r) for r in rumuz]


def people(conn: sqlite3.Connection | None) -> list[dict]:
    """The index with each man's Taqrib entry joined: person (its id), taqrib_death, in_chains (how many chain links
    are his in the imported collections). Without a database the index alone."""
    rows = [dict(h) for h in index()]
    if conn is None:
        return rows
    from isnady.core import cache

    joined = cache.kept(conn, "huffaz-people", _joined, disk=False)
    for r in rows:
        r.update(joined.get(r["taqrib"] or "", {}))
    return rows


def _joined(conn: sqlite3.Connection) -> dict[str, dict]:
    keys = [h["taqrib"] for h in index() if h["taqrib"]]
    if not keys:
        return {}
    marks = ",".join("?" * len(keys))
    found = {k: {"person": pid, "taqrib_name": name, "taqrib_death": death, "in_chains": 0}
             for pid, k, name, death in conn.execute(
                 f"SELECT id, key, name_ar, death_year_ah FROM persons WHERE key IN ({marks})", keys)}
    by_id = {v["person"]: v for v in found.values()}
    if by_id:
        ids = ",".join(str(i) for i in by_id)
        for pid, n in conn.execute(f"SELECT person_id, COUNT(*) FROM isnad_links WHERE person_id IN ({ids}) "
                                   "GROUP BY person_id"):
            by_id[pid]["in_chains"] = n
    return found


def reading(r: dict, lang: str) -> str:
    """The name in Latin letters, only where every word of it can be read: al-Dhahabi's short name ("Abu Bakr
    al-Siddiq"), else the Taqrib's name of the same man; "" when neither reads whole (then the Arabic is shown).
    A name read only in part ("Abu Bakr" of "Abu Bakr al-Shafi'i") would name another man."""
    from isnady.core.names import latin
    from isnady.core.rijal import display_name

    if lang == "ar":
        return ""
    name = re.sub(r"^(?:أمير المؤمنين|أم المؤمنين)\s+", "", r["name"])      # the title is not part of the name
    words = name.split()
    whole = latin(name, lang)
    if whole and (len(words) == 1 or whole != latin(" ".join(words[:-1]), lang)):
        return whole
    if r.get("taqrib_name"):
        full = (latin(display_name(r["taqrib_name"]), lang) or "").split()
        while full and full[-1] in ("Abd", "b.", "bint"):
            full.pop()                     # "… b. Nufayl b. 'Abd" (al-'Uzza unread): end on the last whole name
        return " ".join(full)
    return ""


def entry(n: int) -> dict | None:
    return next((h for h in index() if h["n"] == n), None)


def of_key(key: str | None) -> dict | None:
    """The entry of a narrator, by his Taqrib key, when al-Dhahabi counts him among the huffaz."""
    if not key:
        return None
    return next((h for h in index() if h["taqrib"] == key), None)


def source_entry(h: dict, lang: str) -> dict:
    """The entry as core.source_entries reads it, for the life card's "In the source" (SourceEntry)."""
    from isnady.core import source_entries
    from isnady.core.i18n import t

    return {"work": WORK, "volume": 0, "number": h["n"], "title": source_entries.title(WORK, lang),
            "where": t("generation {tabaqa}, no. {number}", tabaqa=h["tabaqa"], number=h["n"])}


def death_of(h: dict) -> tuple[int | None, str]:
    """(year, whose): al-Dhahabi's year when he gives one in words, else the Taqrib's for the same man."""
    if h.get("death"):
        return h["death"], "dhahabi"
    if h.get("taqrib_death"):
        return h["taqrib_death"], "taqrib"
    return None, ""


def generations(conn: sqlite3.Connection | None = None) -> list[dict]:
    """Each tabaqa: how many entries, how many with a year of death, the median and the span of those years (the
    middle half, so one misread year does not stretch it), how many are found in the Taqrib, al-Dhahabi's own count."""
    rows = people(conn)
    out = []
    for t in sorted({r["tabaqa"] for r in rows}):
        rs = [r for r in rows if r["tabaqa"] == t]
        years = sorted(y for y in (death_of(r)[0] for r in rs) if y)
        q = lambda f: years[min(len(years) - 1, int(f * len(years)))] if years else None  # noqa: E731
        out.append({"tabaqa": t, "count": len(rs), "dated": len(years), "median": q(0.5), "from": q(0.25),
                    "to": q(0.75), "in_taqrib": sum(1 for r in rs if r.get("person") or (conn is None and r["taqrib"])),
                    "stated": STATED.get(t)})
    return out


def by_century(conn: sqlite3.Connection | None = None) -> list[tuple[int, int]]:
    """(century AH, how many huffaz died in it), counting only those with a known year."""
    counts: dict[int, int] = {}
    for r in people(conn):
        y = death_of(r)[0]
        if y:
            c = (y - 1) // 100 + 1
            counts[c] = counts.get(c, 0) + 1
    return sorted(counts.items())


def find(conn: sqlite3.Connection | None, text: str = "", tabaqa: int | None = None) -> list[dict]:
    """The entries whose Arabic heading (or Taqrib name, or reading) holds every word of the text; in one tabaqa."""
    from isnady.core.names import latin
    from isnady.core.narrators import fold_latin
    from isnady.core.rijal import display_name
    from isnady.core.normalize import normalize

    rows = [r for r in people(conn) if tabaqa is None or r["tabaqa"] == tabaqa]
    words = ["بن" if w in ("ابن", "إبن") else w for w in text.split() if w]   # al-Dhahabi writes "b." as بن
    if not words:
        return rows
    out = []
    for r in rows:
        arabic = normalize(f"{r['head']} {r.get('taqrib_name') or ''}")
        names = [r["name"]] + ([display_name(r["taqrib_name"])] if r.get("taqrib_name") else [])
        latin_hay = fold_latin(" ".join(x for n in names for x in (latin(n, "tr"), latin(n, "en")) if x))
        if all((normalize(w) in arabic) if any("؀" <= ch <= "ۿ" for ch in w) else (fold_latin(w) in latin_hay)
               for w in words):
            out.append(r)
    return out
