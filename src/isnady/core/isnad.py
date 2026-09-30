"""Isnad parser: separates the chain of transmission from the text (matn)
and splits it into narrators, using the transmission terms that link them.

    حَدَّثَنَا الْحُمَيْدِيُّ ... قَالَ حَدَّثَنَا سُفْيَانُ ... عَنْ ... سَمِعْتُ عُمَرَ ...
      -> [("haddathana", "الْحُمَيْدِيُّ عَبْدُ اللَّهِ بْنُ الزُّبَيْرِ"), ("haddathana", "سُفْيَانُ"), ...]

Names are kept EXACTLY as written (with diacritics and with clarifications such
as "- يعني ابن محمد -"), because identifying the narrator is a later, separate
step (matching against rijal works). No link is guessed: when the text does not
follow the expected pattern, the chain is stored raw with no links and a reason.

Version 1 limits, all reported rather than guessed:
  * tahwil (ح, a switch to a second chain) — stored raw, not split;
  * two teachers at one link (qiran: "عثمان وابو بكر ... قالا") — stored raw, not split;
  * a last narrator introduced only by "qala" ("عن علقمة، قال قال عبد الله ...") is NOT added:
    the same shape starts stories ("قال كنا مع النبي"), so the chain may stop one link early;
  * chains that do not start with a transmission term (e.g. "وقال", "وزاد").

PARSER_ID changes whenever the rules change; derived chains are then rebuilt.
"""

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Callable

from isnady.core.normalize import normalize as normalize_name
from isnady.core.normalize import normalize_with_map

PARSER_ID = "isnady-isnad-4"   # bump when rules change

# normalised form -> term id; longer forms first so "حدثني" is not read as "حدث"
TERMS = [
    ("حدثناه", "haddathana"), ("حدثنا", "haddathana"), ("حدثني", "haddathani"), ("ثنا", "haddathana"),
    ("اخبرنا", "akhbarana"), ("اخبرني", "akhbarani"), ("انبانا", "anba'ana"), ("انباني", "anba'ani"),
    ("سمعت", "sami'tu"), ("سمع", "sami'a"), ("قرات علي", "qara'tu 'ala"), ("قري علي", "quri'a 'ala"),
    ("زعم", "za'ama"), ("عن", "'an"), ("ان", "anna"),
]
_TERM_RE = re.compile(r"(?<!\w)و?(" + "|".join(t for t, _ in TERMS) + r")(?!\w)")
_TERM_ID = dict(TERMS)

# words that sit between a name and the next term and belong to neither
_FILLER_WORDS = ("قالوا", "قالت", "قالا", "قال", "يقولان", "يقول", "تقول", "انهما", "انها", "انه",
                 "حدثهم", "حدثها", "حدثه", "اخبرهم", "اخبره", "يحدث", "كلاهما", "جميعا")
_FILLER_RE = re.compile(
    r"(?:[\s،,:;.\u200f\u200e\"'-]|(?:" + "|".join(_FILLER_WORDS) + r")(?!\w)|و(?=\s))+"
)
_PROPHET_RE = re.compile(r"(?<!\w)(?:رسول الله|النبي|نبي الله)(?!\w)")
_HONORIFIC_RE = re.compile(r"\s*(?:رضي الله (?:تعالي )?عن(?:ه|ها|هما|هم)|رحمه الله|عليه السلام)")
_TAHWIL_RE = re.compile(r"(?<!\w)ح(?!\w)")
_JOINT_START_RE = re.compile(r"و(?!\s)\w")                    # "وابو بكر", "وهناد" ...
_JOINT_WORD_RE = re.compile(r"(?<!\w)(?:قالا|قالوا|كلاهما|جميعا|المعني|وحديثه|حديثهما|لفظ)(?!\w)")
_DESCRIPTOR_RE = re.compile(
    r"[،,]?\s*(?:مولي|ختن|زوج|صاحب|كاتب|قاضي|ابن اخي|ابن اخت|ابن عم|اخي|اخو|اخت|"
    r"(?:رجل|امراه|شيخ)?\s*من (?:بني|اهل|ابناء|اصحاب|الانصار|المهاجرين|قومه|ولد))(?!\w)")
_NARRATES_RE = re.compile(r"(?<!\w)(?:قال|قالت|حدث|حدثه|حدثها|حدثهم|حدثته|اخبر|اخبره|اخبرهم|اخبرته|سمع|يقول|تقول|يحدث|رفعه)(?!\w)")
_GENERIC_SUBJECT_RE = re.compile(
    r"(?:رجلا|رجل|امراه|اعرابيا|اعرابي|ناسا|رهطا|قوما|نفرا|غلاما|جاريه|اصحاب|اهل|يهوديا|يهود)(?!\w)")
# a transmission term soon after the point where reading stopped: the chain goes on
_CONTINUES_RE = re.compile(r"^(?:\S+\s+){0,8}?(?:و)?(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|سمعت|زعم|عن)\s+[^،,\s]")
_MAX_NAME_WORDS = 10


@dataclass
class Link:
    position: int
    term: str
    raw_name: str


@dataclass
class ParsedIsnad:
    raw_isnad: str = ""
    links: list[Link] = field(default_factory=list)
    reaches_prophet: bool = False
    problem: str = ""                 # empty when parsed; otherwise why no links were stored


def _clean_name(original: str) -> str:
    return original.strip(" \t\n\u200f\u200e،,:;.-\"'").strip()


def parse(text: str) -> ParsedIsnad:
    norm, index_map = normalize_with_map(text)
    n = len(norm)

    def orig(a: int, b: int) -> str:
        start = index_map[a] if a < n else len(text)
        end = index_map[b] if b < n else len(text)
        return text[start:end]

    result = ParsedIsnad()
    head = norm[:1200]
    first = _TERM_RE.match(head.lstrip("{ "))
    if not first:
        result.problem = "does not start with a transmission term"
        return result

    pos = 0
    links: list[Link] = []
    ends: list[tuple[int, int]] = []      # (end before this link, end after it)
    end_of_chain = 0
    while pos < n:
        filler = _FILLER_RE.match(norm, pos)
        if filler:
            pos = filler.end()
        term = _TERM_RE.match(norm, pos)
        if not term:
            break
        term_id = _TERM_ID[term.group(1)]
        name_start = term.end()
        while name_start < n and norm[name_start] in " \t":
            name_start += 1

        # the Prophet ends the chain
        prophet = _PROPHET_RE.match(norm, name_start)
        if prophet:
            result.reaches_prophet = True
            break

        # the name runs to the next comma, the next term, or an honorific
        next_comma = min((i for i in (norm.find("،", name_start), norm.find(",", name_start)) if i != -1), default=n)
        next_term = _TERM_RE.search(norm, name_start)
        name_end = min(next_comma, next_term.start() if next_term else n)
        said = re.search(r"(?<!\w)(?:قال|قالت|يقول)(?!\w)", norm[name_start:name_end])
        if said and said.start() > 0:
            name_end = name_start + said.start()
        honor = _HONORIFIC_RE.search(norm, name_start, name_end)
        if honor:
            name_end = honor.start()
        # a clarification in dashes right after the comma belongs to the name: "- يعني ابن محمد -"
        after = name_end
        desc = _DESCRIPTOR_RE.match(norm, name_end)
        if desc:
            nxt = _TERM_RE.search(norm, desc.end())
            nxt_comma = min((i for i in (norm.find("،", desc.end()), norm.find(",", desc.end())) if i != -1), default=n)
            name_end = min(nxt.start() if nxt else n, nxt_comma)
        core_norm = norm[name_start:name_end]
        clar = re.match(r"[،,]?\s*-\s*(?:يعني|هو)\s[^-]{1,150}-", norm[after:after + 170])
        if clar:
            name_end = after + clar.end()

        words = core_norm.strip(" ،,:-").split()
        if re.search(r"\.\s*\S", core_norm.strip()):          # a sentence ends inside: a second chain follows
            result.raw_isnad = _clean_name(orig(0, min(n, name_end + 80)))
            result.problem = "a second chain follows the first; not split in version 1"
            return result
        if not words or len(words) > _MAX_NAME_WORDS:
            break                                   # narrative has begun
        if term_id == "anna" and links and len(words) > 6:
            break
        links.append(Link(len(links) + 1, term_id, _clean_name(orig(name_start, name_end))))
        ends.append((end_of_chain, name_end))
        end_of_chain = name_end
        pos = honor.end() if honor and honor.end() > name_end else name_end
        if _TAHWIL_RE.match(norm, pos) or _TAHWIL_RE.match(norm[pos:].lstrip(" ،,"), 0):
            break

    # "... عن عايشه، ان ابا بكر دخل ..." - after anna comes the subject of the story, not a narrator,
    # unless a transmission verb follows the name ("ان الحكم بن نافع حدثهم", "ان ابن عمر قال سمعت")
    if links and links[-1].term == "anna" and not result.reaches_prophet:
        after_name = norm[end_of_chain:end_of_chain + 60]
        generic = _GENERIC_SUBJECT_RE.match(normalize_name(links[-1].raw_name))
        if generic or not _NARRATES_RE.search(after_name):
            links.pop()
            end_of_chain = ends.pop()[0]

    tail = norm[end_of_chain:end_of_chain + 140].lstrip(" ،,")
    if links and not result.reaches_prophet:
        result.reaches_prophet = bool(_PROPHET_RE.search(norm[end_of_chain:end_of_chain + 90]))

    # two teachers at one link (qiran): "حدثنا عثمان، وابو بكر ابنا ابي شيبه قالا حدثنا ..."
    if links and not result.reaches_prophet and _JOINT_START_RE.match(tail) and _JOINT_WORD_RE.search(tail):
        result.raw_isnad = _clean_name(orig(0, min(n, end_of_chain + 140)))
        result.problem = "two narrators at one link (qiran); not split in version 1"
        return result

    if _TAHWIL_RE.search(norm[:end_of_chain + 60]):
        result.raw_isnad = _clean_name(orig(0, min(n, end_of_chain + 60)))
        result.problem = "tahwil (a second chain joins); not split in version 1"
        return result
    goes_on = _CONTINUES_RE.match(tail)
    prophet_at = _PROPHET_RE.search(tail)
    if links and goes_on and (not prophet_at or goes_on.end() <= prophet_at.start()):
        result.raw_isnad = _clean_name(orig(0, min(n, end_of_chain + 140)))
        result.problem = "chain continues after words that were not understood"
        return result

    region = norm[:max(end_of_chain, pos) + 40]
    if _TAHWIL_RE.search(region):
        result.raw_isnad = _clean_name(orig(0, max(end_of_chain, 1)))
        result.problem = "tahwil (a second chain joins); not split in version 1"
        return result
    if not links:
        result.problem = "no narrator found after the transmission term"
        return result
    result.raw_isnad = _clean_name(orig(0, end_of_chain))
    result.links = links
    return result


# ------------------------------------------------------------------ storage
def ensure_isnads(conn: sqlite3.Connection, progress: Callable[[str], None] | None = None,
                  rebuild: bool = False) -> dict:
    """Parse the Arabic text of every hadith that has no derived chain yet."""
    say = progress or (lambda _m: None)
    conn.execute("CREATE TABLE IF NOT EXISTS core_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    row = conn.execute("SELECT value FROM core_meta WHERE key = 'isnad_parser'").fetchone()
    if rebuild or (row is not None and row[0] != PARSER_ID):
        say("Isnad rules changed; parsing every chain again")
        conn.execute("DELETE FROM isnads WHERE derived_by IS NOT NULL")
    conn.execute("INSERT OR REPLACE INTO core_meta (key, value) VALUES ('isnad_parser', ?)", (PARSER_ID,))

    todo = conn.execute(
        """SELECT h.id, t.text, e.source_id FROM hadiths h
           JOIN texts t ON t.hadith_id = h.id
           JOIN editions e ON e.id = t.edition_id
           WHERE e.language = 'Arabic'
             AND h.id NOT IN (SELECT hadith_id FROM isnads WHERE derived_by IS NOT NULL)
           GROUP BY h.id"""
    ).fetchall()
    stats = {"parsed": 0, "reaches_prophet": 0, "raw_only": 0, "links": 0, "problems": {}}
    if not todo:
        conn.commit()
        return stats
    say(f"Reading isnads of {len(todo)} hadith")
    for hadith_id, text, source_id in todo:
        p = parse(text)
        isnad_id = conn.execute(
            """INSERT INTO isnads (hadith_id, ordinal, raw_text, source_id, derived_by, reaches_prophet, problem)
               VALUES (?, 1, ?, ?, ?, ?, ?)""",
            (hadith_id, p.raw_isnad or None, source_id, PARSER_ID, int(p.reaches_prophet), p.problem or None),
        ).lastrowid
        conn.executemany(
            "INSERT INTO isnad_links (isnad_id, position, raw_name, transmission) VALUES (?, ?, ?, ?)",
            [(isnad_id, link.position, link.raw_name, link.term) for link in p.links],
        )
        if p.links:
            stats["parsed"] += 1
            stats["links"] += len(p.links)
            stats["reaches_prophet"] += int(p.reaches_prophet)
        else:
            stats["raw_only"] += 1
            stats["problems"][p.problem] = stats["problems"].get(p.problem, 0) + 1
    conn.commit()
    return stats


def chain(conn: sqlite3.Connection, hadith_id: int) -> list[dict]:
    """The stored chains of a hadith with their links, for display."""
    out = []
    for isnad in conn.execute(
        "SELECT id, raw_text, reaches_prophet, problem, derived_by FROM isnads WHERE hadith_id = ? ORDER BY ordinal",
        (hadith_id,),
    ):
        links = conn.execute(
            "SELECT position, raw_name, transmission, person_id, match_confidence, candidates "
            "FROM isnad_links WHERE isnad_id = ? ORDER BY position",
            (isnad["id"],),
        ).fetchall()
        out.append({"raw": isnad["raw_text"], "reaches_prophet": bool(isnad["reaches_prophet"]),
                    "problem": isnad["problem"], "derived_by": isnad["derived_by"],
                    "links": [dict(r) for r in links]})
    return out


# ----------------------------------------------------------------- reading aids
# How each transmission term reads, and what the critics took it to mean.
TERM_LABELS = {
    "haddathana": ("حدثنا", "narrated to us",
                   "The teacher recited it to a group that included the narrator: heard directly."),
    "haddathani": ("حدثني", "narrated to me",
                   "The teacher recited it to the narrator alone: heard directly."),
    "akhbarana": ("أخبرنا", "informed us",
                  "Many critics used it for a text read back to the teacher ('ard); others as haddathana."),
    "akhbarani": ("أخبرني", "informed me", "As akhbarana, received alone."),
    "anba'ana": ("أنبأنا", "told us", "Later scholars often used it for transmission by permission (ijaza)."),
    "anba'ani": ("أنبأني", "told me", "As anba'ana, received alone."),
    "sami'tu": ("سمعت", "I heard", "States direct hearing explicitly."),
    "sami'a": ("سمع", "heard", "Reports that the narrator heard it directly."),
    "qara'tu 'ala": ("قرأت على", "I read to", "The narrator read the text back to the teacher ('ard)."),
    "quri'a 'ala": ("قرئ على", "it was read to", "The text was read back to the teacher while the narrator listened."),
    "za'ama": ("زعم", "stated", "Reports a statement; says nothing about how it was received."),
    "'an": ("عن", "from",
            "Does not say how it was received ('an'ana). Counted as connected when the two narrators could "
            "have met and the narrator is not known for concealing a gap (tadlis)."),
    "anna": ("أن", "that", "Treated by most critics like 'an (mu'anna)."),
}


def term_label(term: str) -> tuple[str, str, str]:
    return TERM_LABELS.get(term, (term, term, ""))


def short_name(raw_name: str) -> str:
    """The name without clarifications ("- يعني ابن محمد -", "هو ابن اسلم") for compact display."""
    name = re.split(r"\s*[،,]?\s*-\s*(?:يَعْنِي|يعني|هُوَ|هو)\s", raw_name)[0]
    name = re.split(r"\s{2,}(?:هُوَ|هو)\s", name)[0]
    return name.strip(" ،,-")


def hadith_id(conn: sqlite3.Connection, book: str, number: str) -> int | None:
    row = conn.execute(
        "SELECT h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id WHERE c.key = ? AND h.number = ?",
        (book, number.strip()),
    ).fetchone()
    return row[0] if row else None


def describe(conn: sqlite3.Connection, hid: int) -> dict | None:
    """Book, number and neighbours of a hadith, for navigation."""
    row = conn.execute(
        """SELECT h.id, h.number, h.number_sort, h.collection_id, c.key, c.name FROM hadiths h
           JOIN collections c ON c.id = h.collection_id WHERE h.id = ?""", (hid,)
    ).fetchone()
    if row is None:
        return None
    prev = conn.execute(
        """SELECT id FROM hadiths WHERE collection_id = ? AND (number_sort < ? OR (number_sort = ? AND id < ?))
           ORDER BY number_sort DESC, id DESC LIMIT 1""", (row[3], row[2], row[2], row[0])
    ).fetchone()
    nxt = conn.execute(
        """SELECT id FROM hadiths WHERE collection_id = ? AND (number_sort > ? OR (number_sort = ? AND id > ?))
           ORDER BY number_sort, id LIMIT 1""", (row[3], row[2], row[2], row[0])
    ).fetchone()
    return {"id": row[0], "number": row[1], "book": row[4], "book_name": row[5],
            "prev": prev[0] if prev else None, "next": nxt[0] if nxt else None}


def arabic_text(conn: sqlite3.Connection, hid: int) -> str | None:
    row = conn.execute(
        """SELECT t.text FROM texts t JOIN editions e ON e.id = t.edition_id
           WHERE t.hadith_id = ? AND e.language = 'Arabic' ORDER BY e.id LIMIT 1""", (hid,)
    ).fetchone()
    return row[0] if row else None


def split_text(text: str, raw_isnad: str | None) -> tuple[str, str]:
    """(isnad part, matn part) of the Arabic text, using the stored raw chain."""
    if not raw_isnad:
        return "", text
    at = text.find(raw_isnad)
    if at == -1:
        return "", text
    end = at + len(raw_isnad)
    return text[:end], text[end:]


def book_stats(conn: sqlite3.Connection) -> list[dict]:
    """Per book: chains read, split into narrators, reaching the Prophet, and why the rest were not split."""
    out = []
    for r in conn.execute(
        """SELECT c.id, c.key, c.name, COUNT(*) AS chains, SUM(i.problem IS NULL) AS split,
                  SUM(i.problem IS NULL AND i.reaches_prophet = 1) AS marfu
           FROM isnads i JOIN hadiths h ON h.id = i.hadith_id JOIN collections c ON c.id = h.collection_id
           WHERE i.derived_by IS NOT NULL GROUP BY c.id ORDER BY c.name"""
    ):
        problems = conn.execute(
            """SELECT i.problem, COUNT(*) FROM isnads i JOIN hadiths h ON h.id = i.hadith_id
               WHERE h.collection_id = ? AND i.problem IS NOT NULL GROUP BY i.problem ORDER BY 2 DESC""", (r[0],)
        ).fetchall()
        links = conn.execute(
            """SELECT COUNT(*) FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id JOIN hadiths h ON h.id = i.hadith_id
               WHERE h.collection_id = ?""", (r[0],)
        ).fetchone()[0]
        out.append({"key": r[1], "name": r[2], "chains": r[3], "split": r[4] or 0, "marfu": r[5] or 0,
                    "links": links, "problems": [(p, n) for p, n in problems]})
    return out
