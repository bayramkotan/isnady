"""Who is who in a chain: linking the names read from a chain to narrators
imported from a rijal work (today Ibn Hajar's Taqrib al-Tahdhib).

Evidence, in order; nothing is guessed:
  1. NAME — the words of the name in the chain appear, in order, in one of the
     person's names (full name, kunya, or a name the rijal work gives as
     pointing to him). Names written exactly as a known name are preferred.
  2. BOOK — the person has hadith in this collection (Ibn Hajar's marks:
     a narrator of al-Bukhari carries خ, خت or ع).
  3. ORDER — going towards the Prophet the tabaqa never grows; the last link
     before the Prophet is a Companion (tabaqa 1); the compiler's own teacher
     is from tabaqa 9 or later.
  4. RELATIVES — "عن أبيه", "عن جده" are read from the previous narrator's
     name (the father of Hisham b. 'Urwa is 'Urwa).

When more than one person remains, the link stays unidentified and the number
of candidates is stored, so the interface can say so. MATCHER_ID changes when
these rules change; links are then matched again.
"""

import re
import sqlite3
from collections import defaultdict
from typing import Callable

from isnady.core.normalize import normalize
from isnady.core.rijal import COLLECTION_MARKS

MATCHER_ID = "isnady-narrators-7"
_TEACHER_MIN_TABAQA = 9           # the compilers' own teachers (Ibn Hajar's tabaqat 9-12)
_HONORIFIC = re.compile(r"\s*(?:رضي الله (?:تعالي )?عن(?:ه|ها|هما|هم)|رحمه الله|عليه السلام|صلي الله عليه وسلم).*$")
_CLARIFY = re.compile(r"[،,]?\s*-?\s*(?:يعني|هو)\s+([^-]+?)\s*-?\s*$")
_RELATIVE = {"ابيه": "father", "ابوه": "father", "جده": "grandfather", "امه": "mother", "عمه": "uncle"}


def tokens(name: str) -> list[str]:
    words = normalize(name).replace("ابن ", "بن ").split()
    return [re.sub(r"^(ابا|ابي)$", "ابو", w) for w in words]


def _is_subsequence(short: list[str], long: list[str]) -> bool:
    it = iter(long)
    return all(any(w == x for x in it) for w in short)


class Index:
    """Every person's names as tokens, with tabaqa and book marks, for fast lookup."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.tabaqa, self.marks, self.full = {}, defaultdict(set), {}
        self.names: dict[str, list[tuple[int, list[str], bool]]] = defaultdict(list)   # first token -> entries
        self.exact: dict[str, set[int]] = defaultdict(set)
        for pid, tabaqa, name in conn.execute("SELECT id, tabaqa, name_ar FROM persons"):
            self.tabaqa[pid] = tabaqa
            self.full[pid] = tokens(name)
        for pid, mark in conn.execute("SELECT person_id, mark FROM person_marks"):
            self.marks[pid].add(mark)
        for pid, name, kind in conn.execute("SELECT person_id, name, kind FROM person_names"):
            toks = tokens(name)
            if toks:
                self.names[toks[0]].append((pid, toks, kind != "full"))
                self.exact[" ".join(toks)].add(pid)

    def candidates(self, toks: list[str]) -> set[int]:
        """Persons whose name can be the one written in the chain.

        Written exactly as one of the person's names: those persons. Otherwise the ism and the father
        must match without a gap ("محمد بن عوف" is Muhammad whose FATHER is 'Awf, not whose fourth
        ancestor is), and the remaining words (grandfather, nisba) must follow in order.
        """
        if not toks:
            return set()
        # names written exactly AND names that fit the rule, together: a shortcut to the exact ones alone
        # dropped Abu Dharr al-Ghifari (entry "أبو ذر الغفاري ...") in favour of 'Umar b. Dharr, kunya Abu Dharr
        found = set(self.exact.get(" ".join(toks), ()))
        for variant in _article_variants(toks):             # "الأشعث" in a chain is "أشعث" in the Taqrib
            found |= self._rule_matches(variant)
        return found

    def _rule_matches(self, toks: list[str]) -> set[int]:
        found = set(self.exact.get(" ".join(toks), ()))
        head = toks
        if "بن" in toks:
            i = toks.index("بن")
            head = toks[: i + 2]                       # ism (may be two words) + بن + father
        for pid, name, _alias in self.names.get(toks[0], []):
            if name[: len(head)] == head and _is_subsequence(toks[len(head):], name[len(head):]):
                found.add(pid)
        return found


def _article_variants(toks: list[str]) -> list[list[str]]:
    """The name as written; with the article on its first word added or removed; and with a nisba
    written first moved to the end ("الحميدي عبد الله بن الزبير" is "عبد الله بن الزبير ... الحميدي")."""
    out = [toks]
    if len(toks) > 3 and toks[0].startswith("ال") and "بن" in toks[1:]:
        out.append(toks[1:] + [toks[0]])
    if len(toks) > 4 and toks[0] in ("ابو", "ام") and "بن" in toks[2:]:
        out.append(toks[2:] + toks[:2])                  # "أبو اليمان الحكم بن نافع" is "الحكم بن نافع ... أبو اليمان"
    first = toks[0]
    if first.startswith("ال") and len(first) > 4:
        out.append([first[2:]] + toks[1:])
    elif not first.startswith("ال") and first not in ("ابو", "ام", "بن", "عبد") and len(first) > 2:
        out.append(["ال" + first] + toks[1:])
    return out


def name_tokens(raw_name: str, previous: list[str] | None) -> tuple[list[str], str]:
    """Tokens to look up for one link, and how they were formed."""
    text = _HONORIFIC.sub("", normalize(raw_name)).strip(" ،,-")
    clarification = _CLARIFY.search(text)
    base = text[: clarification.start()].strip(" ،,-") if clarification else text
    toks = tokens(base)
    how = "name"
    if clarification:
        extra = tokens(clarification.group(1))
        toks = toks + extra if extra[:1] == ["بن"] else (extra if len(extra) >= 2 else toks + extra)
        how = "name + clarification"
    if toks and toks[0] in _RELATIVE and previous:
        relation = _RELATIVE[toks[0]]
        if relation == "father" and "بن" in previous:
            i = previous.index("بن")
            toks, how = previous[i + 1:], "father of the previous narrator"
        elif relation == "grandfather" and previous.count("بن") >= 2:
            i = previous.index("بن")
            j = previous.index("بن", i + 1)
            toks, how = previous[j + 1:], "grandfather of the previous narrator"
        else:
            return [], "relative that cannot be read"
    return toks, how


def match_chain(index: Index, links: list[dict], collection: str, reaches_prophet: bool) -> list[tuple]:
    """For each link: (person_id or None, confidence or None, number of candidates)."""
    allowed_marks = COLLECTION_MARKS.get(collection)
    cands: list[set[int]] = []
    previous: list[str] | None = None
    for link in links:
        toks, _how = name_tokens(link["raw_name"], previous)
        found = index.candidates(toks)
        if allowed_marks and found:
            in_book = {p for p in found if index.marks[p] & allowed_marks}
            found = in_book                        # a narrator of this book must carry its mark
        cands.append(found)
        previous = index.full[next(iter(found))] if len(found) == 1 else toks

    first_counts = [len(c) for c in cands]
    n = len(cands)
    if n and cands[0]:
        teachers = {p for p in cands[0] if index.tabaqa.get(p) is None or index.tabaqa[p] >= _TEACHER_MIN_TABAQA}
        if teachers:
            cands[0] = teachers
    if reaches_prophet and n and cands[-1]:
        companions = {p for p in cands[-1] if index.tabaqa.get(p) in (1, None)}
        if companions:
            cands[-1] = companions

    def t(p):
        return index.tabaqa.get(p)

    changed = True
    while changed:                                  # the tabaqa never grows towards the Prophet
        changed = False
        for i in range(n):
            keep = set(cands[i])
            later = next((cands[j] for j in range(i + 1, n) if cands[j]), None)
            earlier = next((cands[j] for j in range(i - 1, -1, -1) if cands[j]), None)
            if later and all(t(q) is not None for q in later):
                keep = {p for p in keep if t(p) is None or any(t(q) <= t(p) for q in later)}
            if earlier and all(t(q) is not None for q in earlier):
                keep = {p for p in keep if t(p) is None or any(t(q) >= t(p) for q in earlier)}
            if keep and keep != cands[i]:
                cands[i] = keep
                changed = True

    out = []
    for i, c in enumerate(cands):
        if len(c) == 1:
            confidence = 1.0 if first_counts[i] == 1 else 0.8
            out.append((next(iter(c)), confidence, first_counts[i]))
        else:
            out.append((None, None, len(c)))
    return out


def link_narrators(conn: sqlite3.Connection, progress: Callable[[str], None] | None = None,
                   rebuild: bool = False) -> dict:
    """Identify the narrators of every chain read from the texts."""
    say = progress or (lambda _m: None)
    if conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0:
        return {"chains": 0, "links": 0, "identified": 0, "note": "no rijal work imported"}
    conn.execute("CREATE TABLE IF NOT EXISTS core_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    persons_now = str(tuple(conn.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM persons").fetchone()))
    stamp = f"{MATCHER_ID}|{persons_now}"
    row = conn.execute("SELECT value FROM core_meta WHERE key = 'narrator_matcher'").fetchone()
    pending = conn.execute(
        """SELECT COUNT(*) FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id
           WHERE i.problem IS NULL AND l.candidates IS NULL"""
    ).fetchone()[0]
    if not rebuild and row is not None and row[0] == stamp and pending == 0:
        return {"chains": 0, "links": 0, "identified": 0, "note": "up to date"}

    say("Identifying narrators")
    index = Index(conn)
    chains = conn.execute(
        """SELECT i.id, i.reaches_prophet, c.key FROM isnads i
           JOIN hadiths h ON h.id = i.hadith_id JOIN collections c ON c.id = h.collection_id
           WHERE i.problem IS NULL"""
    ).fetchall()
    total = identified = 0
    for isnad_id, reaches, collection in chains:
        links = [dict(r) for r in conn.execute(
            "SELECT position, raw_name FROM isnad_links WHERE isnad_id = ? ORDER BY position", (isnad_id,))]
        results = match_chain(index, links, collection, bool(reaches))
        for link, (pid, confidence, count) in zip(links, results):
            conn.execute("UPDATE isnad_links SET person_id = ?, match_confidence = ?, candidates = ? "
                         "WHERE isnad_id = ? AND position = ?", (pid, confidence, count, isnad_id, link["position"]))
            total += 1
            identified += pid is not None
    conn.execute("INSERT OR REPLACE INTO core_meta (key, value) VALUES ('narrator_matcher', ?)", (stamp,))
    conn.commit()
    return {"chains": len(chains), "links": total, "identified": identified}


# ------------------------------------------------------------------ reading
def describe(conn: sqlite3.Connection, person_id: int) -> dict | None:
    """Everything the rijal works say about one person, for display."""
    from isnady.core.rijal import BOOK_MARKS, RANK_LABELS, TABAQA_LABELS

    p = conn.execute(
        """SELECT p.id, p.key, p.name_ar, p.kunya, p.tabaqa, p.generation, p.death_year_ah, p.death_year_note,
                  s.name AS source FROM persons p LEFT JOIN sources s ON s.id = p.source_id WHERE p.id = ?""",
        (person_id,),
    ).fetchone()
    if p is None:
        return None
    verdicts = [dict(v) for v in conn.execute(
        "SELECT critic_name, work, phrase, rank_scheme, rank FROM verdicts WHERE person_id = ? ORDER BY id",
        (person_id,))]
    for v in verdicts:
        v["rank_label"] = RANK_LABELS.get(v["rank"], ("", ""))[1] if v["rank"] else ""
    marks = [m[0] for m in conn.execute("SELECT mark FROM person_marks WHERE person_id = ?", (person_id,))]
    names = [n[0] for n in conn.execute(
        "SELECT name FROM person_names WHERE person_id = ? AND kind != 'full' ORDER BY kind, name", (person_id,))]
    narrations = conn.execute("SELECT COUNT(*) FROM isnad_links WHERE person_id = ?", (person_id,)).fetchone()[0]
    from isnady.core.rijal import display_name

    return {**dict(p), "display_name": display_name(p["name_ar"]),
            "tabaqa_label": TABAQA_LABELS.get(p["tabaqa"], ""), "verdicts": verdicts,
            "marks": [(m, BOOK_MARKS.get(m, m)) for m in marks], "other_names": names,
            "in_chains": narrations}


def search_persons(conn: sqlite3.Connection, text: str, limit: int = 20) -> list[tuple[int, str]]:
    """Persons whose names contain every word typed (diacritics and letter forms ignored)."""
    words = tokens(text)
    if not words:
        return []
    seen, out = set(), []
    for pid, name in conn.execute("SELECT person_id, name FROM person_names"):
        if pid in seen:
            continue
        toks = tokens(name)
        if all(any(w == t or (len(w) > 2 and t.startswith(w)) for t in toks) for w in words):
            seen.add(pid)
            out.append(pid)
    out.sort(key=lambda pid: -conn.execute("SELECT COUNT(*) FROM isnad_links WHERE person_id = ?", (pid,)).fetchone()[0])
    return [(pid, conn.execute("SELECT name_ar FROM persons WHERE id = ?", (pid,)).fetchone()[0]) for pid in out[:limit]]
