"""The parts of an Arabic name (NM1), so a person can be shown by the name he is known by, with every other
part laid out clearly: ism (given name), nasab (lineage: b. …), kunya (Abu …), laqab (by-name), nisbas
(origin, tribe, trade), wala' (client of …), and which of them he is KNOWN BY (shuhra) — al-A'mash is
Sulayman b. Mihran, known by his laqab; Ibn 'Umar by his father's name; Abu Hurayra by his kunya.

Read from the rijal entry's own name, its kunya, the aliases the work gives ("الأعمش هو سليمان بن مهران"),
and phrases in the entry ("يلقب", "المعروف ب…"). Unrecognised words are left out rather than guessed.
"""

import re

from isnady.core.names import latin
from isnady.core.normalize import normalize

PLACES = {normalize(w) for w in (
    "الكوفي البصري المدني المكي الشامي البغدادي الواسطي الرازي المروزي البلخي المصري الحمصي الدمشقي اليماني "
    "الخراساني القمي النيسابوري البخاري السجستاني العسقلاني الأيلي الجزري الحلبي الطائفي الصنعاني الأصبهاني "
    "الترمذي النسائي القزويني الإفريقي الهروي البيروتي الأنطاكي الرملي الموصلي العراقي الحجازي الحراني "
    "الكرماني البلدي الأهوازي المدائني الكرخي التنيسي اليمامي الطرسوسي العسكري").split()}
PART_LABELS = {
    "ism": ("Name", "ism", "الاسم", "the given name"),
    "nasab": ("Lineage", "nasab", "النسب", "son of … (b. = ibn, son of)"),
    "kunya": ("Kunya", "kunya", "الكنية", "Abu … / Umm …: father or mother of …"),
    "laqab": ("By-name", "laqab", "اللقب", "a nickname or title"),
    "nisba": ("Nisbas", "nisba", "النسبة", "where he was from, his tribe or his trade"),
    "wala": ("Client of", "wala'", "الولاء", "a freedman or client of a tribe"),
    "also": ("Also called", "", "", "other names the work gives"),
}
KNOWN_BY = {"laqab": "his by-name (laqab)", "nisba": "his nisba", "ibn": "his father's or an ancestor's name",
            "kunya": "his kunya", "ism": "his name", "given": "this name"}
_KUNYA = ("أبو", "أبي", "أبا", "أم")
# the names of letters and the words of Ibn Hajar's reading notes: never a person's name
_NOT_NAMES = {normalize(w) for w in (
    "الألف الباء التاء الثاء الجيم الحاء الخاء الدال الذال الراء الزاي السين الشين الصاد الضاد الطاء الظاء العين "
    "الغين الفاء القاف الكاف اللام الميم النون الهاء الواو الياء المهملة المعجمة المثلثة الموحدة التحتانية "
    "الفوقانية المثناة المفتوحة المكسورة المضمومة الساكنة المشددة").split()}
# "يلقب …" gives a by-name (Mu'tamir b. Sulayman "يلقب الطفيل" is still known as Mu'tamir); only "المعروف ب…" /
# "يعرف ب…" says what he is KNOWN as (al-Najashi: "المعروف بابن عبدون")
_LAQAB_PHRASE = re.compile(r"(?:الملقب|لقبه|يلقب)\s+(?:ب)?([\u0621-\u064A]+(?:\s+[\u0621-\u064A]+)?)")
_KNOWN_PHRASE = re.compile(r"(?:المعروف|يعرف)\s+(?:ب)?((?:ابن\s+|بابن\s+)?[\u0621-\u064A]+(?:\s+[\u0621-\u064A]+)?)")


def _r(words: list[str]) -> str:
    """The English reading of a part, written as inside a name: "al-Kahili", "b. Mihran", not "Al-…", "B. …"."""
    text = latin(" ".join(words), "en", max_words=8) or ""
    if text.startswith(("Al-", "B. ")):
        text = text[0].lower() + text[1:]
    return text


def _take_name(words: list[str], i: int) -> int:
    """How many words the name starting at i takes: عبد الله, عبيد الله, أبي بكر are one name."""
    if i + 1 < len(words) and (words[i] in ("عبد", "عبيد") or words[i + 1] == "الله"):
        return 2                                         # عبد الله, ولي الله, نصر الله: one name
    if i + 1 < len(words) and words[i] in _KUNYA:
        return 3 if i + 2 < len(words) and words[i + 1] == "عبد" else 2
    return 1


def parse(name: str, kunya: str | None = None, aliases: list[str] | None = None, text: str | None = None,
          known_as: str | None = None) -> dict:
    words = [w for w in re.sub(r"[،,.:؛()\[\]]", " ", name or "").split() if w]
    # the name ends where "يلقب …" begins: that phrase gives a by-name, not a part of his name
    for cut, w in enumerate(words):
        if w in ("يلقب", "ويلقب", "الملقب", "لقبه", "ولقبه"):
            words = words[:cut]
            break
    out = {"ism": None, "nasab": [], "kunya": None, "laqab": [], "nisba": [], "wala": [], "also": [], "known": None}
    i = 0
    if words and words[0] in _KUNYA:                       # an entry that begins with the kunya: known by it
        n = _take_name(words, 0)
        out["kunya"] = words[:n]
        i = n
        # "أبو داود سليمان بن الأشعث": the given name may follow the kunya
        if i + 1 < len(words) and not words[i].startswith("ال") and words[i + 1] in ("بن", "بنت"):
            m = _take_name(words, i)
            out["ism"] = words[i:i + m]
            i += m
    elif words:
        n = _take_name(words, 0)
        out["ism"] = words[:n]
        i = n
    # a given name of several words, with no "b." after it: شاه ولي الله, زبير علي زئي
    while out["ism"] and i < len(words) and words[i] not in ("بن", "بنت", "ابن", "مولى", "مولاهم") \
            and not words[i].startswith("ال") and words[i] not in _KUNYA \
            and not (i + 1 < len(words) and words[i + 1] == "الدين"):
        n = _take_name(words, i)
        out["ism"] = out["ism"] + words[i:i + n]
        i += n
    while i + 1 < len(words) and words[i] in ("بن", "بنت", "ابن"):
        n = _take_name(words, i + 1)
        out["nasab"].append(words[i:i + 1 + n])
        i += 1 + n
    while i < len(words):
        w = words[i]
        if w in _KUNYA and i + 1 < len(words):
            n = _take_name(words, i)
            if out["kunya"] is None:
                out["kunya"] = words[i:i + n]
            i += n
            continue
        if w == "مولى" and i + 1 < len(words):
            n = _take_name(words, i + 1)
            out["wala"].append(words[i:i + 1 + n])
            i += 1 + n
            continue
        if w in ("مولاهم", "مولاه"):
            out["wala"].append([w])
        elif w.startswith("ال") and len(w) > 3:
            (out["nisba"] if w.endswith(("ي", "ية")) else out["laqab"]).append([w])
        elif w in ("ثم",):
            pass
        elif out["ism"] and not out["nisba"] and not out["laqab"] and len(w) > 2 and i + 1 < len(words) \
                and words[i + 1] == "الدين":               # an honorific: ناصر الدين
            out["laqab"].append(words[i:i + 2])
            i += 2
            continue
        i += 1
    if not out["kunya"] and kunya:
        out["kunya"] = kunya.split()
    stated = None                                         # the name the entry says he is KNOWN as ("المعروف ب…")
    if text:
        m = _LAQAB_PHRASE.search(text)
        if m and m.group(1).split() not in out["laqab"]:
            out["laqab"].append(m.group(1).split())
        k = _KNOWN_PHRASE.search(text)
        if k:
            stated = k.group(1).replace("بابن", "ابن").split()
            if stated[0] != "ابن" and stated not in out["laqab"]:
                out["laqab"].append(stated)
    # the name he is known by: a short alias of a recognisable shape, else his kunya (when the entry opens with
    # it), else his by-name, else his name
    clean = []
    for a in aliases or []:
        aw = a.split()
        if not 1 <= len(aw) <= 3 or any(x in aw for x in ("عن", "هو", "و")):
            continue                                     # notes, not names ("عبد الملك عن مجاهد")
        if any(normalize(x) in _NOT_NAMES for x in aw):
            continue                                     # reading notes left as aliases: "الميم" of "بكسر الميم"
        clean.append(aw)
    known = None
    if known_as:                                          # given by the caller (the scholars' register)
        kw = known_as.split()
        if out["ism"] and kw == out["ism"][:len(kw)]:
            known = ("ism", kw)
        elif kw[0] in ("ابن", "بن"):
            known = ("ibn", kw)
        elif kw[0] in _KUNYA:
            known = ("kunya", kw)
        elif len(kw) == 1 and kw[0].startswith("ال"):
            known = ("nisba" if kw[0].endswith("ي") else "laqab", kw)
        else:
            known = ("given", kw)
    # among the aliases: a by-name first (الأعمش), then "Ibn …" (ابن جريج), then a nisba (الزهري) — so al-A'mash
    # is not shown as al-Kahili just because the tribe's name came first in the list
    ranked = []
    for aw in clean:
        if aw[0] in ("بن", "ابن") and len(aw) >= 2:
            ranked.append((1, ("ibn", aw)))
        elif len(aw) == 1 and aw[0].startswith("ال") and aw[0] in words:
            # a by-name or nisba he is KNOWN by is one Ibn Hajar writes inside the name itself
            # ("سليمان بن مهران … الأعمش", "… الزهري"); "يلقب الطفيل" outside it is a by-name, not his shuhra
            ranked.append((2, ("nisba", aw)) if aw[0].endswith("ي") else (0, ("laqab", aw)))
    if not known and ranked:
        known = min(ranked, key=lambda r: r[0])[1]
    if not known and words and words[0] in _KUNYA:
        known = ("kunya", out["kunya"])
    # a by-name only when the entry SAYS it is his: an "al-…" word inside a name may belong to his father
    # ("عائشة بنت أبي بكر الصديق": al-Siddiq is Abu Bakr's)
    if not known and stated:
        known = ("ibn", stated) if stated[0] == "ابن" else ("laqab", stated)
    if not known and out["ism"]:
        known = ("ism", out["ism"] + (out["nasab"][0] if out["nasab"] else []))
    if known and known[0] in ("laqab", "nisba") and known[1] not in out[known[0]]:
        out[known[0]].append(known[1])
    shown = {tuple(p) for key in ("laqab", "nisba", "wala") for p in out[key]}
    out["also"] = [aw for aw in clean if tuple(aw) not in shown and aw != (known or ("", []))[1]]
    out["known"] = known
    return out


def present(parts: dict) -> dict:
    """For display: the known-as name (Arabic, reading, how), the full name, and one row per part."""
    kind, words = parts["known"] or ("ism", [])
    arabic = " ".join(words)
    if kind == "ibn":
        arabic = "ابن " + " ".join(words[1:])
        rest = _r(words[1:])
        reading = "Ibn " + rest if rest else ""          # never half a reading: "Ibn" alone is no name
    else:
        reading = _r(words)
    if reading and len(reading.split()) < len([w for w in words if w not in ("بن", "ابن")]) - 1:
        reading = ""                                     # part of the name could not be read: show the Arabic
    full = (parts["ism"] or []) + [w for p in parts["nasab"] for w in p]
    rows = []
    if parts["ism"]:
        rows.append(("ism", [(" ".join(parts["ism"]), _r(parts["ism"]))], kind == "ism"))
    if parts["nasab"]:
        rows.append(("nasab", [(" ".join(p), _r(p)) for p in parts["nasab"]], kind == "ibn"))
    if parts["kunya"]:
        rows.append(("kunya", [(" ".join(parts["kunya"]), _r(parts["kunya"]))], kind == "kunya"))
    if parts["laqab"]:
        rows.append(("laqab", [(" ".join(p), _r(p)) for p in parts["laqab"]], kind == "laqab"))
    if parts["nisba"]:
        rows.append(("nisba", [(" ".join(p), _r(p) + (" (place)" if normalize(p[0]) in PLACES else ""))
                               for p in parts["nisba"]], kind == "nisba"))
    if parts["wala"]:
        rows.append(("wala", [(" ".join(p), "their client" if p[0] == "مولاهم" else _r(p)) for p in parts["wala"]], False))
    if parts["also"]:
        rows.append(("also", [(" ".join(p), _r(p)) for p in parts["also"]], False))
    return {"arabic": arabic or " ".join(full), "reading": reading, "kind": kind,
            "how": KNOWN_BY.get(kind, ""), "full_arabic": " ".join(full), "full_reading": _r(full), "rows": rows}
