"""How isnady identifies the narrators of a chain, every way of it with its parameters (0.8.0).

Bayram (2026-11-15): "todo altına râvi tanımla ile ilgili bir detaylı form koy … râviyi nasıl tanımlıyoruz, ona ait
settingsler … hangi teknikler ve parametreleri neler ve bunları nasıl değiştirebiliyoruz". Tools → Narrator
Identification and `iy narrator-rules` show each way, what it reads, how many links it decided, and its parameters;
each can be changed, and the narrators are identified again.

Two groups, never mixed (the rule of 0.7.8: the books are shown as they are, the narrators named by the rijal works'
own words; isnady's own inference only when turned on, and marked):

* **source** — the rijal work's own words: a name as the work writes it, the book marks, the tabaqat, the compiler's
  teacher, a freedman ("مولى ابن عمر"), "عن أبيه" read from the son's own nasab, the order of the Shia rijal works,
  and the identifications the tabaqat or the years of death make impossible. On unless turned off one by one.
* **guess** — isnady's own inference: the bare names read by the narrators around them, the names it knows them by,
  a name found inside the entries, the famous one of a name, the pairs of teacher and student the other chains show,
  a father weighed from his son's nasab. Only when Narrator Guesses is on (`iy guess on`); each can then be turned
  off alone. The links they decide carry the confidence of a guess and are marked "≟ isnady's guess".

The values are kept in the database (core_meta 'narrator_rules': only what differs from the defaults, as compact
JSON with sorted keys) — the Python isnady and isnady-rs read the same values, and a change identifies every chain's
narrators again (the value is part of the matcher's stamp).
"""

import json
import math
import sqlite3

from isnady.core.i18n import N_

# key, group, can be turned off, [(parameter, default, lowest, highest, step)]
RULES: list[tuple[str, str, bool, list[tuple[str, float, float, float, float]]]] = [
    ("name", "source", False, []),
    ("marks", "source", True, []),
    ("order", "source", True, []),
    ("companion", "source", True, []),
    ("teacher", "source", True, [("min_tabaqa", 9, 1, 12, 1)]),
    ("mawla", "source", True, []),
    ("father", "source", True, []),
    ("shia_order", "source", True, []),
    ("impossible", "source", True, [("after", 4, 1, 12, 1), ("before", 6, 1, 12, 1), ("death_years", 80, 10, 300, 5)]),
    ("muhmal", "guess", True, []),
    ("known_as", "guess", True, []),
    ("elsewhere", "guess", True, []),
    ("neighbours", "guess", True, [("rounds", 3, 1, 10, 1), ("min_chains", 2, 1, 50, 1), ("lead", 3.0, 1.0, 20.0, 0.5)]),
    ("one_side", "guess", True, [("min_chains", 6, 1, 50, 1), ("lead", 5.0, 1.0, 20.0, 0.5)]),
    ("father_pair", "guess", True, [("min_chains", 1, 1, 50, 1), ("few", 3, 1, 20, 1)]),
    ("father_nasab", "guess", True, [("gap", 6, 0, 12, 1)]),
    ("famous", "guess", True, []),
    # (a guess stays below the rijal work's words, 0.8: what the chain shows as "≟ isnady's guess")
    ("confidence", "common", False, [("trust", 0.7, 0.1, 1.0, 0.05), ("guess", 0.7, 0.1, 0.75, 0.05),
                                     ("neighbours", 0.6, 0.1, 0.75, 0.05), ("famous", 0.5, 0.1, 0.75, 0.05)]),
]

# what each way does, in the words the window and the command show (translated by i18n)
TITLES = {
    "name": N_("The name as the rijal work writes it"),
    "marks": N_("The book's mark on the narrator"),
    "order": N_("The order of the tabaqat"),
    "companion": N_("The last link is a Companion"),
    "teacher": N_("The compiler's own teacher"),
    "mawla": N_("A freedman by his patron"),
    "father": N_("\"عن أبيه\" from the son's nasab"),
    "shia_order": N_("The order of the Shia rijal works"),
    "impossible": N_("What the tabaqat and the years of death rule out"),
    "muhmal": N_("Bare names by the narrators around them"),
    "known_as": N_("The names isnady knows them by"),
    "elsewhere": N_("A name found inside the entries"),
    "neighbours": N_("Teacher and student seen in other chains"),
    "one_side": N_("One known neighbour"),
    "father_pair": N_("A son and his father together"),
    "father_nasab": N_("A father weighed from his son's nasab"),
    "famous": N_("The famous one of a name"),
    "confidence": N_("Confidences"),
}
EXPLAINED = {
    "name": N_("The name in the chain is one of the narrator's names in the rijal work, or his ism and his father's "
               "name with the rest of the name in its order; the work's notes on the spelling (\"بفتح …\") are no part "
               "of the name. One narrator found: confidence 1.0; one left by the evidence below: 0.8. Always on."),
    "marks": N_("Ibn Hajar's Taqrib marks the books each narrator is in (خ م د ت س ق …): a narrator of this book must "
                "carry its mark."),
    "order": N_("Towards the Prophet ﷺ the tabaqa never grows: a link's narrator is of the tabaqa of the one after "
                "him or later, of the one before him or earlier."),
    "companion": N_("A chain that reaches the Prophet ﷺ ends with a Companion (tabaqa 1)."),
    "teacher": N_("The first link is the compiler's own teacher: of the lowest tabaqa below. The Muwatta's chains "
                  "begin with Malik himself."),
    "mawla": N_("\"نافع عن ابن عمر\": of the men of that name, the one whose entry calls him the freedman of the next "
                "narrator."),
    "father": N_("\"هشام عن أبيه\": once the son is known, his father is read from the son's own nasab in the rijal "
                 "work, and kept when one narrator of that name fits the generations."),
    "shia_order": N_("A name is looked up in al-Najashi first, then in al-Tusi's Fihrist, then in his Rijal: a man "
                     "found in an earlier book is that book's entry."),
    "impossible": N_("A narrator cannot be his own teacher, nor the student of a man so many tabaqat after him or "
                     "before him, nor of a man who died so many years after him: the less certain of the two is left "
                     "unidentified."),
    "muhmal": N_("isnady's list of bare names (\"سفيان\", \"حماد\") and the teachers and students that tell them apart."),
    "known_as": N_("isnady's list of the names the chains call some narrators by (\"غندر\" is Muhammad b. Ja'far)."),
    "elsewhere": N_("A kunya, a nisba or an ism with a nisba that begins no entry, found inside the entries' names."),
    "neighbours": N_("A name left open between several narrators: the one the other chains show with this link's "
                     "student and teacher, in at least so many chains and so many times more than the next."),
    "one_side": N_("A bare name whose neighbour on one side alone is known: the narrator that neighbour is seen with "
                   "far more than with any other."),
    "father_pair": N_("\"سالم عن أبيه\" with the son open between namesakes: the pair of son and father the other "
                      "chains show, both links."),
    "father_nasab": N_("The father found by the son's nasab weighed: the grandfather, the kunya, a tribe or a city, "
                       "the patron; a father up to so many tabaqat before his son."),
    "famous": N_("A bare name still open after everything else is the famous narrator of that name (isnady's list)."),
    "confidence": N_("Trust: the links whose teacher and student count as seen together for the other chains. Guess, "
                     "neighbours, famous: the confidence written on the links these ways decide."),
}
PARAMETERS = {
    "min_tabaqa": N_("Lowest tabaqa"), "after": N_("Tabaqat after the student"),
    "before": N_("Tabaqat before the student"), "death_years": N_("Years of death after the student"),
    "rounds": N_("Rounds"), "min_chains": N_("Chains at least"), "lead": N_("Times more than the next"),
    "few": N_("Namesakes at most"), "gap": N_("Tabaqat before the son"), "trust": N_("Trust"), "guess": N_("Guess"),
    "neighbours": N_("Neighbours"), "famous": N_("Famous"),
}
GROUPS = {"source": N_("The rijal work's own words"), "guess": N_("isnady's guesses"), "common": N_("Common")}

_KEY = "narrator_rules"
_BY_KEY = {key: (group, switch, params) for key, group, switch, params in RULES}


def defaults() -> dict:
    """Every way with its parameters as isnady ships it: {key: {"on": True, parameter: value}}."""
    return {key: {"on": True, **{p: d for p, d, _lo, _hi, _s in params}} for key, _g, _sw, params in RULES}


def stored(conn: sqlite3.Connection) -> str:
    """The values kept in the database: compact JSON of what differs from the defaults ("" when nothing does)."""
    try:
        row = conn.execute("SELECT value FROM core_meta WHERE key = ?", (_KEY,)).fetchone()
    except sqlite3.OperationalError:
        return ""
    return row[0] if row and row[0] not in ("", "{}") else ""


def load(conn: sqlite3.Connection) -> dict:
    """The rules in force: the defaults with the database's values over them (a value out of range brought in)."""
    out = defaults()
    text = stored(conn)
    if not text:
        return out
    try:
        changed = json.loads(text)
    except ValueError:
        return out
    for key, values in changed.items() if isinstance(changed, dict) else ():
        if key in out and isinstance(values, dict):
            for name, value in values.items():
                fixed = _fit(key, name, value)
                if fixed is not None:
                    out[key][name] = fixed
    return out


def _fit(key: str, name: str, value):
    """A value made right for its parameter (the type of the default, within its range), or None."""
    _group, switch, params = _BY_KEY[key]
    if name == "on":
        return bool(value) if switch and isinstance(value, bool) else None
    for p, default, lo, hi, _step in params:
        if p == name:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            if not math.isfinite(value):
                return None
            value = min(max(value, lo), hi)
            # half up, never the banker's rounding (isnady-rs rounds the same way); two decimals at most
            return int(value + 0.5) if isinstance(default, int) else math.floor(value * 100 + 0.5) / 100
    return None


def canonical(rules: dict) -> str:
    """What differs from the defaults, as kept in the database: sorted keys, no spaces ("" for none)."""
    base = defaults()
    diff = {}
    for key in sorted(rules):
        if key not in base:
            continue
        values = {}
        for n, v in sorted(rules[key].items()):
            v = _fit(key, n, v) if n in base[key] else None
            if v is not None and v != base[key][n]:
                values[n] = v
        if values:
            diff[key] = values
    return json.dumps(diff, sort_keys=True, separators=(",", ":"), ensure_ascii=False) if diff else ""


def save(conn: sqlite3.Connection, rules: dict) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS core_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    text = canonical(rules)
    if text:
        conn.execute("INSERT OR REPLACE INTO core_meta (key, value) VALUES (?, ?)", (_KEY, text))
    else:
        conn.execute("DELETE FROM core_meta WHERE key = ?", (_KEY,))
    conn.commit()


def apply(rules: dict, setting: str) -> str | None:
    """One setting as the command writes it — "famous=off", "neighbours.rounds=4", "teacher=on" — put into rules.
    Returns what was wrong with it, or None."""
    if "=" not in setting:
        return f"not KEY=on|off or KEY.PARAMETER=VALUE: {setting}"
    left, value = (x.strip() for x in setting.split("=", 1))
    key, _, name = left.partition(".")
    if key not in _BY_KEY:
        return f"no such way: {key} (see iy narrator-rules)"
    _group, switch, params = _BY_KEY[key]
    if not name:
        if not switch:
            return f"{key} cannot be turned off"
        if value not in ("on", "off"):
            return f"{key}: on or off, not {value}"
        rules[key]["on"] = value == "on"
        return None
    if name not in {p for p, *_r in params}:
        return f"{key} has no parameter {name}"
    try:
        number = float(value)
    except ValueError:
        number = math.nan
    fitted = _fit(key, name, number)
    if fitted is None:
        return f"{key}.{name}: a number, not {value}"
    rules[key][name] = fitted
    return None


def counts(conn: sqlite3.Connection) -> dict:
    """How many links each way decided at the last identification: {"sunni": {key: n}, "shia": {...}}."""
    try:
        row = conn.execute("SELECT value FROM core_meta WHERE key = 'narrator_rule_counts'").fetchone()
        return json.loads(row[0]) if row else {}
    except (sqlite3.OperationalError, ValueError):
        return {}


def save_counts(conn: sqlite3.Connection, found: dict) -> None:
    conn.execute("INSERT OR REPLACE INTO core_meta (key, value) VALUES ('narrator_rule_counts', ?)",
                 (json.dumps(found, sort_keys=True, separators=(",", ":")),))
