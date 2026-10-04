"""Importer for Ibn Hajar's Taqrib al-Tahdhib in OpenITI mARkdown.

OpenITI version used and tested: 0852IbnHajarCasqalani.TaqribTahdhib.JK000121-ara1.completed
(reviewed; editors' paratext removed by OpenITI in 2023). The licence of the
OpenITI release is not stated in the repository; unless --license says
otherwise the source is stored as tier C (not redistributed).

Each numbered entry becomes a person with
  * the name as written, and the kunya when the name contains one;
  * Ibn Hajar's verdict exactly as written, with his rank (1-12) when the
    words map to one of the ranks he defines (isnady.core.rijal.rank_of);
  * the tabaqa (1-12) and the death year, completed with the hundreds by his
    own rule;
  * the book marks (خ م د ت س ق ع 4 ...).
Cross-reference entries ("X هو Y") become extra names of the person they point
to, only when that person can be found without doubt.
"""

import re
import sqlite3

from isnady.core import rijal
from isnady.core.normalize import normalize
from isnady.data.db import now_iso, tier_for_license
from isnady.data.fetch import ResourceError, read_bytes
from isnady.data.importers.base import ImportReport, Importer, ProgressCallback, SourceInfo, register

CRITIC = "Ibn Hajar al-'Asqalani"
WORK = "Taqrib al-Tahdhib"
SCHEME = "ibn-hajar-taqrib"

_NOISE = re.compile(r"PageV\d+P\d+|\bms\d+\b|\|")
_ENTRY = re.compile(r"^### \${1,2} (\d+)\s*(.*)$")   # "$ N" entries; the women's section uses "$$ N"
_XREF = re.compile(r"^### \$\$\$\s*(.*)$")
_TABAQA = re.compile(
    r"(?<!\w)من (?:(كبار|صغار|أوساط) )?(الحادية عشرة|الثانية عشرة|الأولى|الثانية|الثالثة|الرابعة|الخامسة|"
    r"السادسة|السابعة|الثامنة|التاسعة|العاشرة)(?!\w)")
_TABAQA_WORD = re.compile(
    r"(?<!\w)الطبقة ()(الحادية عشرة|الثانية عشرة|الأولى|الثانية|الثالثة|الرابعة|الخامسة|السادسة|السابعة|"
    r"الثامنة|التاسعة|العاشرة)(?!\w)")
_DEATH = re.compile(r"(?<!\w)(?:مات|قتل|استشهد|توفي)(?: سنة| في سنة)? (.+)$")
_VERDICT_START = re.compile(
    r"(?<!\w)(أم المؤمنين|الصحابي|الصحابية|صحابي|صحابية|له صحبة|لها صحبة|له رؤية|لها رؤية|ثقة|"
    r"صدوقة|صدوقا|صدوق|مقبولة|مقبول|مستورة|مستور|مجهولة|مجهول|ضعيفة|ضعيفا|ضعيف|متروكة|متروكا|متروك|لا يعرف|كذاب|"
    r"متهم|لين الحديث|لا بأس به|ليس به بأس|واه|ساقط|أمير المؤمنين)(?!\w)")
# a kunya is "أبو X" / "أم X" standing on its own, or "يكنى أبا X"; "بن أبي X" is lineage, not a kunya
_LIFE_START = re.compile(r"\s(?:ولد|وهو|كان|أسلم|اسلم|شهد|استصغر|قدم|نزل|سكن|روى|هاجر|أحد|من السابقين)(?!\w)")
_KUNYA = re.compile(r"(?<!بن )(?<!بنت )(?<!\w)(أبو|أم) (عبد \S+|\S+)|(?:يكنى|تكنى|كنيته) (أبا|أم) (عبد \S+|\S+)")
_XREF_SPLIT = re.compile(r"\s(?:هو|هي|اسمه|اسمها|صوابه|صوابها)\s")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _NOISE.sub(" ", text)).strip()


_ORDINALS_H = {w.replace("ة", "ه"): w for w in ("الأولى", "الثانية", "الثالثة", "الرابعة", "الخامسة", "السادسة",
                                                   "السابعة", "الثامنة", "التاسعة", "العاشرة", "الحادية", "عشرة")}


def _fix_ta_marbuta(text: str) -> str:
    """The digital text sometimes writes ordinals with ه for ة ("من الثالثه"); read them as written by Ibn Hajar."""
    return re.sub(r"(?<!\w)(" + "|".join(map(re.escape, _ORDINALS_H)) + r")(?!\w)", lambda m: _ORDINALS_H[m.group(1)], text)


def parse_entry(number: int, text: str) -> dict:
    """One Taqrib entry -> its parts. Parts that cannot be read are None."""
    text = _fix_ta_marbuta(text)
    tokens = text.split()
    marks = []
    while tokens and tokens[-1] in rijal.BOOK_MARKS:
        marks.insert(0, tokens.pop())
    body = " ".join(tokens)

    death_phrase, death_at = None, len(body)
    death = _DEATH.search(body)
    if death:
        death_phrase, death_at = death.group(0), death.start()

    tabaqa, tabaqa_at, tabaqa_note = None, None, None
    before = list(_TABAQA.finditer(body[:death_at]))
    after = list(_TABAQA.finditer(body, death_at)) if death else []
    found = before[-1] if before else (after[0] if after else _TABAQA_WORD.search(body))
    if found:
        tabaqa, tabaqa_note = rijal.TABAQA_WORDS[found.group(2)], found.group(0)
        tabaqa_at = found.start() if found.start() < death_at else None

    head_end = tabaqa_at if tabaqa_at is not None else death_at
    head = body[:head_end].strip()
    verdict_at = _VERDICT_START.search(head)
    if verdict_at and verdict_at.start() > 0:
        name, verdict = head[:verdict_at.start()].strip(" ،,"), head[verdict_at.start():].strip(" ،,")
    else:
        name, verdict = head.strip(" ،,"), ""
    # some Companions are introduced by their life, not a verdict: "عبد الله بن عمر … ولد بعد المبعث … وهو أحد
    # المكثرين من الصحابة". The name ends where the life begins; "من الصحابة" says Companion.
    if not verdict:
        life = _LIFE_START.search(name)
        if life and life.start() > 0:
            name, verdict = name[:life.start()].strip(" ،,"), name[life.start():].strip(" ،,")

    rank = rijal.rank_of(verdict) if verdict else None
    if tabaqa is None and rank == 1:
        tabaqa, tabaqa_note = 1, "صحابي"             # Ibn Hajar: the first tabaqa are the Companions
    if tabaqa is None and re.search(r"(?<!\w)مخضرم(?!\w)", body):
        tabaqa, tabaqa_note = 2, "مخضرم"            # Ibn Hajar: mukhadram belong to the second tabaqa

    year = None
    if death_phrase:
        words = re.sub(r"^(?:مات|قتل|استشهد|توفي)(?: سنة| في سنة)? ", "", death_phrase)
        within = re.match(r"^(?:\S+ ){1,3}?سنة (.+)$", words)       # "قتل ظلما سنة ..."
        if within and not re.match(r"(?:قبل|بعد|في حدود)", words):
            words = within.group(1)
        year = rijal.death_year(words, tabaqa) if not re.match(r"(?:قبل|بعد|في حدود|بضع|سنة بضع)", words) else None

    kunyas = []
    for k in _KUNYA.finditer(body):
        first, second = (k.group(1), k.group(2)) if k.group(1) else ("أبو" if k.group(3) == "أبا" else "أم", k.group(4))
        second = second.strip(" ،,")
        if second and f"{first} {second}" not in kunyas:
            kunyas.append(f"{first} {second}")
    kunya = kunyas[0] if kunyas else None
    return {"number": number, "name": name, "verdict": verdict, "rank": rank,
            "tabaqa": tabaqa, "tabaqa_note": tabaqa_note, "death_year": year, "death_note": death_phrase,
            "kunya": kunya, "kunyas": kunyas, "marks": marks, "text": body}


_OUTLINE = re.compile(r"^### (\|{1,3}|\${1,3}|\$DIC_NIS\$)\s*(.*)$")


def read_outline(text: str) -> list[tuple]:
    """The book as Ibn Hajar ordered it, from the OpenITI markers: ("h", level, title) for "### |" … "### |||"
    headings (letters, then the names under each), ("e", number) for an entry ("### $" / "### $$"), and
    ("x", text) for a cross-reference ("### $$$")."""
    out = []
    for line in text.split("\n"):
        m = _OUTLINE.match(line)
        if not m:
            continue
        mark, rest = m.group(1), m.group(2).strip()
        if mark.startswith("|"):
            title = rest.strip(" ()")
            if title:
                out.append(("h", len(mark), title))
        elif mark in ("$", "$$"):
            n = re.search(r"\d+", rest)
            if n:
                out.append(("e", int(n.group(0))))
        elif mark == "$$$" and rest:
            out.append(("x", rest))
    return out


def write_work(conn: sqlite3.Connection, outline: list[tuple], entries: list[dict], person_of: dict, source_id: int,
               key: str = "taqrib", title: str = "Taqrib al-Tahdhib", title_ar: str = "تقريب التهذيب",
               author: str = "ibnhajar", stamp: str | None = None) -> int:
    """The Taqrib as a readable work (core.works): its headings as chapters, each entry with its text and its
    narrator, each cross-reference as it stands. Replaces the work's earlier tree."""
    conn.execute("DELETE FROM works WHERE key = ?", (key,))
    wid = conn.execute("INSERT INTO works (key, kind, title, title_ar, author, source_id, stamp) VALUES (?, 'rijal', ?, ?, ?, ?, ?)",
                       (key, title, title_ar, author, source_id, stamp or f"{key}|{len(entries)}")).lastrowid
    texts: dict = {}
    for e in entries:
        texts.setdefault(e["number"], []).append(e)
    stack: list[tuple[int, int]] = []          # (level, node id)
    ordinals: dict = {}
    current = None

    def add(parent, kind, label=None, title=None, person=None, text=None):
        ordinals[parent] = ordinals.get(parent, 0) + 1
        return conn.execute("INSERT INTO work_nodes (work_id, parent_id, ordinal, kind, label, title, person_id, text) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (wid, parent, ordinals[parent], kind, label, title, person, text)).lastrowid

    for item in outline:
        if item[0] == "h":
            _h, level, heading = item
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else None
            node_id = add(parent, "kitab" if level == 1 else "bab", title=heading)
            stack.append((level, node_id))
            current = node_id
        elif item[0] == "e":
            # one entry per marker: the edition gives four numbers to two narrators each (622, 2518, 4391, 6508)
            waiting = texts.get(item[1])
            if waiting:
                e = waiting.pop(0)
                if current is None:
                    current = add(None, "kitab", title="Introduction")
                add(current, "entry", label=str(e["number"]), title=e["name"], person=person_of.get(id(e)), text=e["text"])
        elif item[0] == "x" and current is not None:
            add(current, "reference", text=item[1])
    for rest in texts.values():                 # entries the outline did not place (none expected)
        for e in rest:
            if current is None:
                current = add(None, "kitab", title="Entries")
            add(current, "entry", label=str(e["number"]), title=e["name"], person=person_of.get(id(e)), text=e["text"])
    return wid


def read_entries(text: str) -> tuple[list[dict], list[str]]:
    lines = text.split("\n")
    try:
        start = next(i for i, l in enumerate(lines) if l.startswith("#META#Header#End"))
    except StopIteration as exc:
        raise ResourceError("Not an OpenITI mARkdown file (no #META#Header#End#).") from exc
    entries, xrefs, current = [], [], None

    def close():
        if current is None:
            return
        kind, number, parts = current
        text_ = _clean(" ".join(parts))
        if kind == "entry":
            entries.append(parse_entry(number, text_))
        elif text_:
            xrefs.append(text_)

    for line in lines[start + 1:]:
        m = _ENTRY.match(line)
        x = _XREF.match(line) if not m else None
        if m:
            close()
            current = ("entry", int(m.group(1)), [m.group(2)])
        elif x:
            close()
            current = ("xref", 0, [x.group(1)])
        elif line.startswith("~~") and current is not None:
            current[2].append(line[2:])
        elif line.startswith("#"):
            close()
            current = None
    close()
    return entries, xrefs


def _tokens(name: str) -> list[str]:
    words = normalize(name).replace("ابن ", "بن ").split()
    return [re.sub(r"^(ابا|ابي)$", "ابو", w) for w in words]


_COMMON = {"بن", "ابو", "ام", "بنت", "عبد", "الله"}
_EPITHETS = {"الحبر", "الفقيه", "مشهور", "المشهور", "الصحابي", "الحافظ", "الامام", "الإمام"}
_MAX_ALIAS_TARGETS = 8


def _read_xref(text: str) -> tuple[str, list[list[str]]]:
    """A cross-reference -> (alias as written, the name tokens of every person it points to).

    "بن عمر هو عبد الله مشهور"               -> ("بن عمر", [عبد الله بن عمر])
    "بن عيينة هو سفيان تقدم"                 -> ("بن عيينة", [سفيان بن عيينة])
    "أحمد بن حنبل هو بن محمد بن حنبل"         -> ("أحمد بن حنبل", [أحمد بن محمد بن حنبل])
    "الأعمش سليمان بن مهران"                  -> ("الأعمش", [سليمان بن مهران])
    "الزهري محمد بن مسلم بن شهاب وأبو مصعب"   -> ("الزهري", [محمد بن مسلم بن شهاب, أبو مصعب])
    The nisba and laqab sections (no هو) list EVERY person known by that name alone; all are kept.
    """
    parts = _XREF_SPLIT.split(text, maxsplit=1)
    listing = False
    if len(parts) == 2:
        alias, target = parts[0].strip(" ،,"), parts[1]
    else:
        words = text.split()
        if len(words) < 3 or not words[0].startswith("ال"):
            return "", []
        alias, target, listing = words[0], " ".join(words[1:]), True
    target = re.split(r"\s(?:وقيل|ويقال|أو|تقدم|تقدموا|يأتي|سيأتي|مشهور)(?!\w)", " " + target.strip())[0]
    pieces = re.split(r"\s(?:و(?=\S))", " " + target.strip()) if listing else [target]
    alias = " ".join(w for w in alias.split() if w not in _EPITHETS)
    alias_tokens = _tokens(alias)
    targets = []
    for piece in pieces:
        toks = [t for t in _tokens(piece) if t not in rijal.BOOK_MARKS and t not in _EPITHETS]
        while toks and toks[0] in ("ابنه", "اخوه", "ابوه", "اخته", "ابنته"):   # "وابنه معتمر"
            toks = toks[1:]
        if not toks:
            continue
        if toks[0] == "بن":                                        # "هو بن محمد بن حنبل"
            toks = alias_tokens[:1] + toks
        elif alias_tokens[:1] == ["بن"] and "بن" not in toks:      # "بن عمر هو عبد الله"
            toks = toks + alias_tokens[:2]
        targets.append(toks[:6])
    return alias, targets


def _is_subsequence(short: list[str], long: list[str]) -> bool:
    it = iter(long)
    return all(any(w == x for x in it) for w in short)


class TaqribImporter(Importer):
    format_id = "taqrib"
    title = "OpenITI mARkdown — Ibn Hajar, Taqrib al-Tahdhib"
    description = "Narrators with Ibn Hajar's verdict, rank, tabaqa, death year and book marks"

    def run(self, conn: sqlite3.Connection, source: SourceInfo, options: dict,
            progress: ProgressCallback | None = None) -> ImportReport:
        say = progress or (lambda _m: None)
        say(f"Reading {source.location}")
        try:
            text = read_bytes(source.location, source.auth).decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ResourceError(f"Not UTF-8 text: {source.location}") from exc
        entries, xrefs = read_entries(text)
        if len(entries) < 100:
            raise ResourceError(f"Only {len(entries)} entries found; is this the Taqrib al-Tahdhib?")
        say(f"{len(entries)} narrators and {len(xrefs)} cross-references")

        name = source.name or "Ibn Hajar, Taqrib al-Tahdhib (OpenITI)"
        # one canonical work: the source key is fixed, whatever display name the caller gives, so the
        # command line, the catalog and a re-import all update the same rows (the display name was
        # once part of the key and a second copy collided on persons.key)
        key = "openiti-taqrib"
        tier = source.tier or tier_for_license(source.license)
        report = ImportReport(source_key=key)
        with conn:
            conn.execute(
                """INSERT INTO sources (key, name, format, location, license, tier, origin, auth_type, imported_at)
                   VALUES (?, ?, 'taqrib', ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET name = excluded.name, location = excluded.location,
                       license = COALESCE(excluded.license, sources.license), tier = excluded.tier,
                       origin = excluded.origin, auth_type = excluded.auth_type, imported_at = excluded.imported_at""",
                (key, name, source.location, source.license, tier, source.origin, source.auth.describe(), now_iso()),
            )
            source_id = conn.execute("SELECT id FROM sources WHERE key = ?", (key,)).fetchone()[0]
            conn.execute("DELETE FROM persons WHERE source_id = ?", (source_id,))   # re-import replaces

            by_number, token_index, used, token_of, person_of = {}, [], set(), {}, {}
            for e in entries:
                # the edition gives four numbers to two different narrators each (622, 2518, 4391, 6508)
                person_key, suffix = f"taqrib:{e['number']}", "b"
                while person_key in used:
                    person_key, suffix = f"taqrib:{e['number']}{suffix}", chr(ord(suffix) + 1)
                used.add(person_key)
                pid = conn.execute(
                    """INSERT INTO persons (key, name_ar, kunya, death_year_ah, death_year_note, generation, tabaqa,
                                            tradition, source_id) VALUES (?, ?, ?, ?, ?, ?, ?, 'sunni', ?)""",
                    (person_key, e["name"], e["kunya"], e["death_year"], e["death_note"],
                     rijal.generation(e["tabaqa"]), e["tabaqa"], source_id),
                ).lastrowid
                by_number[e["number"]] = pid
                person_of[id(e)] = pid
                conn.execute("INSERT INTO person_names (person_id, name, kind, source_id) VALUES (?, ?, 'full', ?)",
                             (pid, e["name"], source_id))
                for kunya in e["kunyas"]:
                    if not e["name"].startswith(kunya):
                        conn.execute("INSERT INTO person_names (person_id, name, kind, source_id) VALUES (?, ?, 'kunya', ?)",
                                     (pid, kunya, source_id))
                conn.execute("INSERT OR IGNORE INTO person_roles (person_id, role) VALUES (?, 'narrator')", (pid,))
                for mark in e["marks"]:
                    conn.execute("INSERT OR IGNORE INTO person_marks (person_id, mark, source_id) VALUES (?, ?, ?)",
                                 (pid, mark, source_id))
                if e["verdict"]:
                    conn.execute(
                        """INSERT INTO verdicts (person_id, critic_name, work, phrase, rank_scheme, rank, tradition, source_id)
                           VALUES (?, ?, ?, ?, ?, ?, 'sunni', ?)""",
                        (pid, CRITIC, WORK, e["verdict"], SCHEME, e["rank"], source_id),
                    )
                token_index.append((pid, _tokens(e["name"])))
                token_of[pid] = set(token_index[-1][1])

            linked = 0
            for alias, targets in (_read_xref(x) for x in xrefs):
                if not alias or not targets:
                    continue
                distinctive = [w for w in _tokens(alias) if w not in _COMMON]
                persons = []
                for target_tokens in targets:
                    hits = [pid for pid, toks in token_index
                            if toks[:1] == target_tokens[:1] and _is_subsequence(target_tokens, toks)]
                    if len(hits) > _MAX_ALIAS_TARGETS:
                        # too many with words in between: keep those whose name BEGINS with the target
                        # ("بن عمر هو عبد الله" → the 7 entries beginning عبد الله بن عمر, the Companion among them)
                        hits = [pid for pid, toks in token_index if toks[:len(target_tokens)] == target_tokens] or hits
                    if len(hits) > 1 and distinctive:
                        # narrow with the alias's own words: "الزهري" is the Muhammad b. Muslim called al-Zuhri.
                        # All of them, else any of them; when NONE of the candidates carries any, the alias is not
                        # linked at all (it once fell back to every candidate: "بن غانم الإفريقي" landed on the
                        # Companion 'Abdullah b. 'Umar)
                        every = [pid for pid in hits if all(w in token_of[pid] for w in distinctive)]
                        some = [pid for pid in hits if any(w in token_of[pid] for w in distinctive)]
                        hits = every or some
                    if 1 <= len(hits) <= _MAX_ALIAS_TARGETS:
                        persons.extend(h for h in hits if h not in persons)
                # more than one person: the chain decides (tabaqa, book marks); nothing is picked here
                for pid in persons:
                    conn.execute("INSERT INTO person_names (person_id, name, kind, source_id) VALUES (?, ?, 'variant', ?)",
                                 (pid, alias, source_id))
                linked += bool(persons)
            # the book itself, readable in the Books section (core.works)
            write_work(conn, read_outline(text), entries, person_of, source_id)

        ranked = sum(1 for e in entries if e["rank"])
        report.editions.append(WORK)
        report.new_hadiths = 0
        report.texts = len(entries)
        report.warnings.append(
            f"{len(entries)} narrators; rank read for {ranked} ({100 * ranked / len(entries):.1f}%), "
            f"tabaqa for {sum(1 for e in entries if e['tabaqa'])}, death year for "
            f"{sum(1 for e in entries if e['death_year'])}; {linked} of {len(xrefs)} cross-references linked")
        say(report.warnings[-1])
        return report


register(TaqribImporter())
