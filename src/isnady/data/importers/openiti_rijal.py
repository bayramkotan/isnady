"""Rijal works in OpenITI mARkdown, by PROFILE: the same reader for every book of narrators whose entries are
marked "### $ N - name …" (and headings "### |", "### ||"). Each profile says whose book it is, which tradition,
and how its words are judged. First profile: al-Najashi's Rijal (Shia). Each import writes:
  • the narrators (persons, tradition of the work), with the critic's own words and their reading
    (Shia rijal: core.shia_rijal — reliability and creed, the four classical categories);
  • the book itself, readable in Books (core.works), in its own order.
Narrators of a Shia work are never matched to the (Sunni) chains: core.narrators.Index keeps to Sunni ones.
"""

import re
import sqlite3

from isnady.core import shia_rijal
from isnady.data.db import now_iso, tier_for_license
from isnady.data.fetch import ResourceError, read_bytes
from isnady.data.importers.base import ImportReport, Importer, ProgressCallback, SourceInfo, register
from isnady.data.importers.openiti_taqrib import read_outline, write_work

PROFILES = {
    "najashi": {
        "title": "Rijal al-Najashi", "title_ar": "رجال النجاشي", "author": "najashi", "critic": "al-Najashi",
        "tradition": "shia", "scheme": "shia", "source_key": "openiti-najashi", "minimum": 1000,
        "name": "al-Najashi, Rijal (OpenITI)",
    },
    # 0.7.6 (narrator identity): al-Tusi's two books of men, the other pillars of Imami rijal. His Rijal lists the
    # companions of the Prophet and of each Imam and then "those who did not narrate from them" — numbered again in
    # each part, and a man of two Imams is listed under each; his Fihrist lists the authors with his roads to their
    # books. One man written the same way in several of these books is one narrator (core.narrators.Index).
    "tusi_rijal": {
        "title": "Rijal al-Tusi", "title_ar": "رجال الطوسي", "author": "tusi", "critic": "al-Tusi",
        "tradition": "shia", "scheme": "shia", "source_key": "openiti-tusi-rijal", "minimum": 5000,
        "name": "al-Tusi, Rijal (OpenITI)",
    },
    "tusi_fihrist": {
        "title": "al-Fihrist — al-Tusi", "title_ar": "الفهرست للطوسي", "author": "tusi", "critic": "al-Tusi",
        "tradition": "shia", "scheme": "shia", "source_key": "openiti-tusi-fihrist", "minimum": 800,
        "name": "al-Tusi, al-Fihrist (OpenITI)",
    },
}

# "### $ 12 - name", "### $$ 12 - name", "### $ [] 12 - name", "### $ 580 ms018 - name" (a page mark before the dash);
# the Fihrist's "### $ [12] 3 - name": its entry number in brackets, then the number within the letter (the dash or the
# name may be missing there: "### $ [885] 64", "### $ [895] 74 أبو هارون")
_ENTRY = re.compile(r"^### \$\$? (?:\[\])?\s*(\d+)\s*(?:ms\d+\s*)?-\s*(.*)$")
_ENTRY_NUMBERED = re.compile(r"^### \$\$? \[(\d+)\]\s*(?:\d+)?\s*(?:ms\d+\s*)?(?:-\s*)?(.*)$")
_NOISE = re.compile(r"PageV\d+P\d+|ms\d+|~~|^#\s*|\s#\s")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _NOISE.sub(" ", text)).strip()


def read_entries(text: str) -> list[dict]:
    """[{number, name, text}] — the name is what the entry's marker line gives after its number."""
    out, current = [], None
    for line in text.split("\n"):
        m = _ENTRY_NUMBERED.match(line) or _ENTRY.match(line)
        if m:
            if current:
                out.append(current)
            name = _clean(m.groups()[-1]).strip(" ،,.-")
            current = {"number": int(m.group(1)), "name": name, "lines": [m.groups()[-1]]}
        elif line.startswith("### "):
            if current:
                out.append(current)
            current = None
        elif current is not None:
            current["lines"].append(line)
    if current:
        out.append(current)
    for e in out:
        e["text"] = _clean(" ".join(e.pop("lines")))
        e["name"] = entry_name(e["text"]) or e["name"]
    return out


# where a name ends and the critic begins to describe him (al-Najashi: "عيسى بن الوليد الهمداني كوفي، ثقة")
_DESCRIBES = re.compile(r"\s(?:كوفي|بصري|مدني|قمي|بغدادي|عربي|ثقة|روى|يروي|له كتاب|له كتب|له نسخة|يكنى|كان|ذكره|وكان|"
                        r"من أصحاب|من اصحاب|ضعيف|عن|أصله|اصله|يعرف|المعروف|يقال|نزل|نزيل|سكن|"
                        r"أسند عنه|اسند عنه|روى عنه|روى عنهما|مات|قتل|شهد)(?=[\s،,.]|$)")


def entry_name(text: str) -> str:
    """The narrator's name from the start of his entry: up to the first comma or full stop, or the first word that
    describes him. The marker line alone is not enough: long names run on (684 "علي بن الحسين بن موسى" /
    "بن بابويه القمي أبو الحسن، شيخ القميين …")."""
    # the editions' footnote numbers and marks inside a name are no part of it ("إبراهيم بن سليمان بن داحة 1 المزني")
    text = re.sub(r"(?<!\S)(?:\d+|#)(?=[\s،,.:؛]|$)", " ", text)
    head = re.split(r"[،,.:؛]|\s-\s", text.lstrip(" -"), maxsplit=1)[0]
    m = _DESCRIBES.search(" " + head)
    if m and m.start() > 0:
        head = (" " + head)[:m.start()]
    words = head.split()[:16]
    while words and words[-1] in ("بن", "بنت", "أبو", "أبي", "ابن", "و"):
        words.pop()
    return " ".join(words).strip()


def _clip(text: str, limit: int = 420) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


class RijalImporter(Importer):
    def __init__(self, profile_key: str) -> None:
        self.profile_key = profile_key
        self.profile = PROFILES[profile_key]
        self.format_id = profile_key
        self.title = f"OpenITI mARkdown — {self.profile['title']}"
        self.description = f"Narrators of {self.profile['title']}, with the critic's words read on the {self.profile['tradition']} scale"

    def run(self, conn: sqlite3.Connection, source: SourceInfo, options: dict,
            progress: ProgressCallback | None = None) -> ImportReport:
        say = progress or (lambda _m: None)
        prof = self.profile
        say(f"Reading {source.location}")
        try:
            text = read_bytes(source.location, source.auth).decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ResourceError(f"Not UTF-8 text: {source.location}") from exc
        entries = read_entries(text)
        if len(entries) < prof["minimum"]:
            raise ResourceError(f"Only {len(entries)} entries found; is this {prof['title']}?")
        say(f"{len(entries)} entries")
        key = prof["source_key"]
        tier = source.tier or tier_for_license(source.license)
        report = ImportReport(source_key=key)
        counts = {}
        with conn:
            conn.execute(
                """INSERT INTO sources (key, name, format, location, license, tier, origin, auth_type, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET name = excluded.name, location = excluded.location,
                       license = COALESCE(excluded.license, sources.license), tier = excluded.tier,
                       origin = excluded.origin, auth_type = excluded.auth_type, imported_at = excluded.imported_at""",
                (key, source.name or prof["name"], self.format_id, source.location, source.license, tier, source.origin,
                 source.auth.describe(), now_iso()))
            source_id = conn.execute("SELECT id FROM sources WHERE key = ?", (key,)).fetchone()[0]
            conn.execute("DELETE FROM persons WHERE source_id = ?", (source_id,))      # re-import replaces
            person_of, used = {}, set()
            for e in entries:
                person_key, suffix = f"{self.profile_key}:{e['number']}", "b"
                while person_key in used:
                    person_key, suffix = f"{self.profile_key}:{e['number']}{suffix}", chr(ord(suffix) + 1)
                used.add(person_key)
                pid = conn.execute("INSERT INTO persons (key, name_ar, tradition, source_id) VALUES (?, ?, ?, ?)",
                                   (person_key, e["name"], prof["tradition"], source_id)).lastrowid
                person_of[id(e)] = pid
                conn.execute("INSERT INTO person_names (person_id, name, kind, source_id) VALUES (?, ?, 'full', ?)",
                             (pid, e["name"], source_id))
                conn.execute("INSERT OR IGNORE INTO person_roles (person_id, role) VALUES (?, 'narrator')", (pid,))
                words = shia_rijal.opening(e["text"])
                judged = shia_rijal.assess(words)
                counts[judged["rank"]] = counts.get(judged["rank"], 0) + 1
                conn.execute(
                    """INSERT INTO verdicts (person_id, critic_name, work, phrase, rank_scheme, rank, tradition, madhhab, source_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (pid, prof["critic"], prof["title"], _clip(words), prof["scheme"], judged["rank"], prof["tradition"],
                     judged["madhhab"], source_id))
            write_work(conn, read_outline(text), entries, person_of, source_id, key=self.profile_key,
                       title=prof["title"], title_ar=prof["title_ar"], author=prof["author"])
        judged = len(entries) - counts.get(None, 0)
        report.editions.append(prof["title"])
        report.new_hadiths = 0
        report.texts = len(entries)
        # a summary, said once: not a warning (iy printed it again as one)
        say(
            f"{len(entries)} narrators; a judgment read for {judged} ({100 * judged / len(entries):.1f}%): "
            + ", ".join(f"{shia_rijal.RANKS[k][1]} {counts.get(k, 0)}" for k in sorted(shia_rijal.RANKS)))
        return report


for _key in PROFILES:
    register(RijalImporter(_key))


# ---------------------------------------------------------------------------------------------------- al-Kashshi
# 0.8.1 (Bayram, 2026-11-23: "Keşşî ricâli"): al-Tusi's selection from al-Kashshi's book of men (اختيار معرفة الرجال),
# the third pillar of Imami rijal beside al-Najashi and al-Tusi. It is not a list of entries but of sections — "### |"
# and the men the section is about ("زرارة بن أعين", "في محمد بن مسلم الطائفي الثقفي", "ما روى في حريز وفضل بن عبد
# الملك البقباق وحذيفة بن منصور") — each with the reports about them, numbered through the book (1 … 1151). al-Kashshi
# gives the reports, not a grade: no rank is read from them; the reports are his words about the man.
# The men are read from the heading as it is written, nothing added: the heading without "في" / "ما روى في", up to a
# word that begins to describe ("وهو", "صاحب", "أيضا" …) or a comma, the men joined by "و" one by one ("وهب" is a name,
# not "and"), each up to a word that names a kinsman instead ("ابنه", "أخيه", "ابني" …). A heading about a group (the
# Zaydiyya, "بنو ذودان", "تسمية الفقهاء") names no one. An empty heading after the end of a part continues the man
# before it; the end of a part (PARATEXT) stays in the book under no one.
KASHSHI = {
    "title": "Ikhtiyar Ma'rifat al-Rijal — al-Kashshi", "title_ar": "اختيار معرفة الرجال (رجال الكشي)",
    "author": "kashshi", "critic": "al-Kashshi", "tradition": "shia", "source_key": "openiti-kashshi",
    "minimum": 300, "name": "al-Kashshi, Ikhtiyar Ma'rifat al-Rijal (OpenITI)",
}
_KASHSHI_OPENINGS = ("ما روى في ", "ما روي في ", "في ")
_KASHSHI_GROUPS = frozenset(["ابنا", "بنو", "بنى", "بني", "اخوة", "إخوة", "أصحاب", "اصحاب", "تسمية", "السبعين",
                             "الزهاد", "ومن", "الغلات", "الغلاة"])
_KASHSHI_TAIL = frozenset(["وهو", "وكان", "وكانا", "صاحب", "المعروف", "ويعرف", "ولقبه", "اسمه", "وقيل", "ويقال",
                           "أيضا", "بعد", "رحمه", "واحتجاج", "ودعوة", "وذكر", "وسبب", "وكلامه", "وغيره", "وغيرهما",
                           "وغيرهم", "منهم", "من", "رحمهما", "رحمهم", "عليه", "عليهم"])
_KASHSHI_KIN = frozenset(["ابني", "ابنا", "ابنه", "وابنه", "أخيه", "أخويه", "اخوته", "واخوته", "إخوته", "أخوه",
                          "موليان", "القميين", "الكوفيين", "الأهوازيين"])
_W_NAMES = frozenset(["وهب", "وهيب", "وكيع", "واصل", "وردان", "وضاح", "وائل", "وابصة", "وحشي", "ورقاء", "وثيمة",
                      "وزير", "وليد", "وداعة", "وبرة", "وصيف"])
_PARTICLES = ("بن", "بنت", "ابن", "أبو", "أبي", "أبى", "ابو", "ابي")
_SECTION = re.compile(r"^### \|+\s*(.*)$")


def kashshi_names(heading: str) -> list[str]:
    """The men a section of al-Kashshi is about, as its heading writes them (see above)."""
    h = re.sub(r"ms\d+|PageV\d+P\d+", " ", heading)
    h = re.sub(r"\([^)]*\)?", " ", h)
    h = re.sub(r"\s+", " ", h).strip(" |.،,:")
    for opening in _KASHSHI_OPENINGS:
        if h.startswith(opening):
            h = h[len(opening):]
            break
    h = re.split(r"[،,]", h, maxsplit=1)[0]
    words = h.split()
    if not words or words[0] in _KASHSHI_GROUPS or (
            len(words) == 1 and words[0].startswith("ال") and words[0].endswith(("ية", "ة", "ات"))):
        return []
    for i, w in enumerate(words):
        if w in _KASHSHI_TAIL:
            words = words[:i]
            break
    parts: list[list[str]] = [[]]
    for w in words:
        # (after "بن", "أبي", "عبد" a word in و is the name itself: "عامر بن واثلة")
        if w.startswith("و") and len(w) > 1 and w not in _W_NAMES and w not in _KASHSHI_KIN and parts[-1] \
                and parts[-1][-1] not in _PARTICLES + ("عبد",):
            parts.append([w[1:]])
        else:
            parts[-1].append(w)
    out: list[str] = []
    for part in parts:
        for i, w in enumerate(part):
            if w in _KASHSHI_KIN:
                part = part[:i]
                break
        while part and part[-1] in _PARTICLES:
            part = part[:-1]
        name = " ".join(part).strip(" .")
        if name and name not in out:
            out.append(name)
    return out


def read_kashshi(text: str) -> list[dict]:
    """[{number, heading, names, text}] — the sections in their order; an empty heading after the end of a part is
    the section before it going on; the end of a part (PARATEXT) is a section about no one."""
    out, current, started = [], None, False
    for line in text.split("\n"):
        if not started:
            started = line.startswith("#META#Header#End#")
            continue
        m = _SECTION.match(line)
        if m:
            heading = m.group(1).strip()
            if heading == "" and out and current is not None and current["paratext"]:
                current = out[-2] if len(out) > 1 else current       # the man before the part's end goes on
                continue
            current = {"heading": heading.strip("|").strip() if heading.startswith("PARATEXT") else heading,
                       "paratext": heading.startswith("PARATEXT"), "lines": []}
            out.append(current)
        elif current is not None:
            current["lines"].append(line)
    for n, s in enumerate(out, 1):
        s["number"] = n
        s["text"] = _clean(" ".join(s.pop("lines")))
        s["names"] = [] if s["paratext"] or n == 1 else kashshi_names(s["heading"])
    return out


class KashshiImporter(Importer):
    format_id = "kashshi"
    title = f"OpenITI mARkdown — {KASHSHI['title']}"
    description = "The men of al-Kashshi's book with the reports about them, readable in Books"

    def run(self, conn: sqlite3.Connection, source: SourceInfo, options: dict,
            progress: ProgressCallback | None = None) -> ImportReport:
        say = progress or (lambda _m: None)
        prof = KASHSHI
        say(f"Reading {source.location}")
        try:
            text = read_bytes(source.location, source.auth).decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ResourceError(f"Not UTF-8 text: {source.location}") from exc
        sections = read_kashshi(text)
        if len(sections) < prof["minimum"]:
            raise ResourceError(f"Only {len(sections)} sections found; is this {prof['title']}?")
        say(f"{len(sections)} sections")
        key = prof["source_key"]
        tier = source.tier or tier_for_license(source.license)
        report = ImportReport(source_key=key)
        men = 0
        with conn:
            conn.execute(
                """INSERT INTO sources (key, name, format, location, license, tier, origin, auth_type, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET name = excluded.name, location = excluded.location,
                       license = COALESCE(excluded.license, sources.license), tier = excluded.tier,
                       origin = excluded.origin, auth_type = excluded.auth_type, imported_at = excluded.imported_at""",
                (key, source.name or prof["name"], self.format_id, source.location, source.license, tier,
                 source.origin, source.auth.describe(), now_iso()))
            source_id = conn.execute("SELECT id FROM sources WHERE key = ?", (key,)).fetchone()[0]
            conn.execute("DELETE FROM persons WHERE source_id = ?", (source_id,))      # re-import replaces
            person_of, entries = {}, []
            for s in sections:
                first = None
                for i, name in enumerate(s["names"]):
                    person_key = f"kashshi:{s['number']}" + ("" if i == 0 else chr(ord("a") + i))
                    pid = conn.execute("INSERT INTO persons (key, name_ar, tradition, source_id) VALUES (?, ?, ?, ?)",
                                       (person_key, name, prof["tradition"], source_id)).lastrowid
                    conn.execute("INSERT INTO person_names (person_id, name, kind, source_id) VALUES (?, ?, 'full', ?)",
                                 (pid, name, source_id))
                    conn.execute("INSERT OR IGNORE INTO person_roles (person_id, role) VALUES (?, 'narrator')", (pid,))
                    # the reports about him are al-Kashshi's words; no grade is read from them (rank: none)
                    conn.execute(
                        """INSERT INTO verdicts (person_id, critic_name, work, phrase, rank_scheme, rank, tradition,
                                                 madhhab, source_id) VALUES (?, ?, ?, ?, 'shia', NULL, ?, NULL, ?)""",
                        (pid, prof["critic"], prof["title"], _clip(s["text"]), prof["tradition"], source_id))
                    first = first or pid
                    men += 1
                entry = {"number": s["number"], "name": s["heading"] or "—", "text": s["text"]}
                entries.append(entry)
                if first:
                    person_of[id(entry)] = first
            outline = [("h", 1, prof["title_ar"])] + [("e", e["number"]) for e in entries]
            write_work(conn, outline, entries, person_of, source_id, key="kashshi", title=prof["title"],
                       title_ar=prof["title_ar"], author=prof["author"])
        report.editions.append(prof["title"])
        report.new_hadiths = 0
        report.texts = len(sections)
        say(f"{men} men in {len(sections)} sections, with the reports about them (al-Kashshi gives reports, "
            "not a grade)")
        return report


register(KashshiImporter())
