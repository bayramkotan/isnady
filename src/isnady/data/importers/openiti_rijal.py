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
}

_ENTRY = re.compile(r"^### \$\$? (?:\[\])?\s*(\d+)\s*-\s*(.*)$")
_NOISE = re.compile(r"PageV\d+P\d+|ms\d+|~~|^#\s*|\s#\s")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _NOISE.sub(" ", text)).strip()


def read_entries(text: str) -> list[dict]:
    """[{number, name, text}] — the name is what the entry's marker line gives after its number."""
    out, current = [], None
    for line in text.split("\n"):
        m = _ENTRY.match(line)
        if m:
            if current:
                out.append(current)
            name = _clean(m.group(2)).strip(" ،,.")
            current = {"number": int(m.group(1)), "name": name, "lines": [m.group(2)]}
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
                        r"من أصحاب|من اصحاب|ضعيف|عن|أصله|اصله|يعرف|المعروف|يقال|نزل|نزيل|سكن)(?=[\s،,.]|$)")


def entry_name(text: str) -> str:
    """The narrator's name from the start of his entry: up to the first comma or full stop, or the first word that
    describes him. The marker line alone is not enough: long names run on (684 "علي بن الحسين بن موسى" /
    "بن بابويه القمي أبو الحسن، شيخ القميين …")."""
    head = re.split(r"[،,.:؛]|\s-\s", text, maxsplit=1)[0]
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
        report.warnings.append(
            f"{len(entries)} narrators; a judgment read for {judged} ({100 * judged / len(entries):.1f}%): "
            + ", ".join(f"{shia_rijal.RANKS[k][1]} {counts.get(k, 0)}" for k in sorted(shia_rijal.RANKS)))
        say(report.warnings[-1])
        return report


for _key in PROFILES:
    register(RijalImporter(_key))
