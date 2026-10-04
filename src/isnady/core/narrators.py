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

    from isnady.core.names import latin

    shown = display_name(p["name_ar"])
    return {**dict(p), "display_name": shown, "latin_tr": latin(shown, "tr"), "latin_en": latin(shown, "en"),
            "tabaqa_label": TABAQA_LABELS.get(p["tabaqa"], ""), "verdicts": verdicts,
            "marks": [(m, BOOK_MARKS.get(m, m)) for m in marks], "other_names": names,
            "in_chains": narrations}


# Latin letters → the consonant skeleton of an Arabic name, so "Abu Hurayra" finds أبو هريرة (b·hrr) and
# "Bukhari" finds البخاري (bkhr). Vowels, long vowels (ا و ي), hamza, ʿayn and tā' marbūṭa are left out on
# both sides; letters a Latin spelling does not tell apart are merged (ح ه → h, ص س → s, ط ت → t, ض د → d,
# ظ ز → z, ق ك → k).
_AR_SKELETON = {"ب": "b", "ت": "t", "ط": "t", "ث": "th", "ج": "j", "ح": "h", "ه": "h", "خ": "kh", "د": "d",
                "ض": "d", "ذ": "dh", "ر": "r", "ز": "z", "ظ": "z", "س": "s", "ص": "s", "ش": "sh", "غ": "gh",
                "ف": "f", "ق": "k", "ك": "k", "ل": "l", "م": "m", "ن": "n"}
_LATIN_DIGRAPHS = (("th", "\x01"), ("kh", "\x02"), ("dh", "\x03"), ("sh", "\x04"), ("gh", "\x05"))
_ARABIC_LETTER = re.compile(r"[\u0600-\u06FF]")


def arabic_skeleton(word: str) -> str:
    """Consonants of an Arabic word. Long-vowel letters (ا, medial و ي) carry no consonant, EXCEPT a word-initial
    ي/و (يعمر Ya'mar is not عمر Umar) and a final ي, the nisba ending (الزهري zhry, not زهير zhr). A final ى
    (يحيى) and the tā' marbūṭa (هريرة) add nothing. Doubled letters are kept: Arabic writes them on purpose."""
    original = word.strip()
    w = normalize(original)
    if w.startswith("ال") and len(w) > 3:
        w = w[2:]
        original = original[2:] if original.startswith("ال") else original
    if original.endswith("ة") and w.endswith("ه"):
        w = w[:-1]
    out = []
    for i, ch in enumerate(w):
        if i == 0 and ch in ("ي", "و"):
            out.append("y" if ch == "ي" else "w")
        else:
            out.append(_AR_SKELETON.get(ch, ""))
    nisba = original.endswith("ي") and len(w) > 2
    return "".join(out) + ("y" if nisba else "")


def latin_skeleton(word: str) -> str:
    """Consonants of a Latin spelling, comparable with arabic_skeleton: the shadda written twice ("Abbas",
    "Musaddad") counts once, a word-initial y/w is a consonant, a final -i is the nisba ending."""
    import unicodedata

    w = "".join(c for c in unicodedata.normalize("NFKD", word.lower()) if not unicodedata.combining(c))
    w = re.sub(r"^(al|el|ad|an|ar|as|at|az|ash|adh)-", "", w)
    w = re.sub(r"[^a-z]", "", w)
    w = re.sub(r"(.)\1+", r"\1", w)                          # the shadda, written twice in Latin
    if not w:
        return ""
    nisba = w.endswith(("i", "iy"))
    initial = w[0] if w[0] in "yw" else ""
    body = w[1:] if initial else w
    for digraph, mark in _LATIN_DIGRAPHS:
        body = body.replace(digraph, mark)
    body = body.replace("q", "k").replace("c", "k")
    body = re.sub(r"[aeiouyw]", "", body)
    for digraph, mark in _LATIN_DIGRAPHS:
        body = body.replace(mark, digraph)
    return initial + body + ("y" if nisba and (initial + body) else "")


_skeleton_cache: dict = {}


def _skeleton_index(conn: sqlite3.Connection) -> list[tuple[int, list[str]]]:
    stamp = conn.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM person_names").fetchone()[:]
    if _skeleton_cache.get("stamp") != tuple(stamp):
        rows = []
        for pid, name in conn.execute("SELECT person_id, name FROM person_names"):
            words = name.split()
            rows.append((pid, [arabic_skeleton(w) for w in words]))
            # an entry that begins with its kunya ("أبو هريرة الدوسي") is also known by the kunya alone
            if len(words) > 2 and normalize(words[0]) in ("ابو", "ام", "ابي", "ابا"):
                kunya_words = words[:3] if normalize(words[1]) == "عبد" else words[:2]
                rows.append((pid, [arabic_skeleton(w) for w in kunya_words]))
        _skeleton_cache.update(stamp=tuple(stamp), rows=rows)
    return _skeleton_cache["rows"]


def _token_index(conn: sqlite3.Connection) -> list[tuple[int, list[str]]]:
    """Every name as normalized words, plus the kunya alone of an entry that begins with it."""
    stamp = tuple(conn.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM person_names").fetchone()[:])
    if _skeleton_cache.get("token_stamp") != stamp:
        rows = []
        for pid, name in conn.execute("SELECT person_id, name FROM person_names"):
            words = tokens(name)
            rows.append((pid, words))
            if len(words) > 2 and words[0] in ("ابو", "ام"):
                rows.append((pid, words[:3] if words[1] == "عبد" else words[:2]))
        _skeleton_cache.update(token_stamp=stamp, token_rows=rows)
    return _skeleton_cache["token_rows"]


def _ordered_score(wanted: list[str], name: list[str], whole: list[str], full_name: list[str]) -> int | None:
    """None when the query words do not occur IN ORDER in the name (each as a word or the start of one);
    otherwise a score: one point per whole word, two when the name begins with the query's first word,
    a hundred when the query is the whole name ("Ibn Umar" = بن عمر, "Zuhri" = الزهري).
    "Anas ibn Malik" is not "Malik ibn Anas", and "سعيد … والد سفيان" is not "سفيان بن سعيد"."""
    i, score = 0, 0
    for q in wanted:
        while i < len(name) and not name[i].startswith(q):
            i += 1
        if i == len(name):
            return None
        score += name[i] == q
        i += 1
    if name and wanted and name[0].startswith(wanted[0]):
        score += 2
    if full_name == whole:
        score += 100
    return score


def search_persons(conn: sqlite3.Connection, text: str, limit: int = 20) -> list[tuple[int, str]]:
    """Persons whose names contain the words typed, in that order (diacritics and letter forms ignored).
    Latin letters are matched on the consonant skeleton ("Abu Hurayra", "Zuhri", "Ibn Abbas")."""
    if not text.strip():
        return []
    best: dict[int, int] = {}
    if not _ARABIC_LETTER.search(text):
        whole = [latin_skeleton(w) for w in text.split() if latin_skeleton(w)]
        wanted = [w for w in whole if w not in ("bn", "bnt")]          # "ibn", "bint" carry nothing here
        if not wanted:
            return []
        for pid, words in _skeleton_index(conn):
            core = [w for w in words if w not in ("bn", "bnt")]
            score = _ordered_score(wanted, core, whole, words)
            if score is not None:
                best[pid] = max(best.get(pid, -1), score)
    else:
        whole = tokens(text)
        wanted = [w for w in whole if w != "بن"]
        if not wanted:
            return []
        for pid, words in _token_index(conn):
            core = [w for w in words if w != "بن"]
            score = _ordered_score(wanted, core, whole, words)
            if score is not None:
                best[pid] = max(best.get(pid, -1), score)
    uses = dict(conn.execute("SELECT person_id, COUNT(*) FROM isnad_links WHERE person_id IS NOT NULL "
                             "GROUP BY person_id").fetchall())
    order = sorted(best, key=lambda pid: (-best[pid], -uses.get(pid, 0)))[:limit]
    return [(pid, conn.execute("SELECT name_ar FROM persons WHERE id = ?", (pid,)).fetchone()[0]) for pid in order]


# ------------------------------------------------------------------ the Narrators page
def overview(conn: sqlite3.Connection) -> dict:
    persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    links = conn.execute("SELECT COUNT(*), SUM(person_id IS NOT NULL) FROM isnad_links").fetchone()
    works = [r[0] for r in conn.execute(
        "SELECT DISTINCT s.name FROM persons p JOIN sources s ON s.id = p.source_id ORDER BY s.name")]
    return {"persons": persons, "links": links[0] or 0, "identified": links[1] or 0, "works": works}


def browse(conn: sqlite3.Connection, text: str = "", tabaqa: int | None = None, rank: int | None = None,
           book: str | None = None, limit: int = 300) -> tuple[list[dict], int]:
    """Narrators for the list: (rows, total before the limit), most often in the chains first."""
    from isnady.core.rijal import COLLECTION_MARKS, display_name

    where, args = [], []
    if text.strip():
        ids = [pid for pid, _n in search_persons(conn, text, limit=5000)]
        if not ids:
            return [], 0
        where.append(f"p.id IN ({','.join(str(i) for i in ids)})")
    if tabaqa:
        where.append("p.tabaqa = ?")
        args.append(tabaqa)
    if rank:
        where.append("v.rank = ?")
        args.append(rank)
    if book and book in COLLECTION_MARKS:
        marks = sorted(COLLECTION_MARKS[book])
        where.append(f"EXISTS (SELECT 1 FROM person_marks m WHERE m.person_id = p.id AND m.mark IN "
                     f"({','.join('?' * len(marks))}))")
        args.extend(marks)
    sql = f"""SELECT p.id, p.name_ar, p.tabaqa, p.death_year_ah, v.phrase, v.rank,
                     (SELECT COUNT(*) FROM isnad_links l WHERE l.person_id = p.id) AS in_chains
              FROM persons p LEFT JOIN verdicts v ON v.id = (SELECT MIN(id) FROM verdicts WHERE person_id = p.id)
              {'WHERE ' + ' AND '.join(where) if where else ''}
              ORDER BY in_chains DESC, p.name_ar"""
    rows = conn.execute(sql, args).fetchall()
    if text.strip():
        # a search keeps its own order (best match first), not "most often in the chains"
        rank_of_id = {pid: i for i, pid in enumerate(ids)}
        rows.sort(key=lambda r: rank_of_id.get(r[0], len(ids)))
    out = [{"id": r[0], "name": display_name(r[1]), "tabaqa": r[2], "death": r[3], "verdict": r[4] or "",
            "rank": r[5], "in_chains": r[6]} for r in rows[:limit]]
    return out, len(rows)


def relations(conn: sqlite3.Connection, person_id: int, limit: int = 12) -> dict:
    """Teachers and students as the imported chains show them: the identified narrator one link closer
    to the Prophet (he narrates FROM him) and one link further (he narrated TO him), with how often."""
    from isnady.core.rijal import display_name

    def side(offset: int) -> list[dict]:
        rows = conn.execute(
            """SELECT o.person_id, p.name_ar, COUNT(*) AS n FROM isnad_links l
               JOIN isnad_links o ON o.isnad_id = l.isnad_id AND o.position = l.position + ?
               JOIN persons p ON p.id = o.person_id
               WHERE l.person_id = ? AND o.person_id IS NOT NULL
               GROUP BY o.person_id ORDER BY n DESC LIMIT ?""", (offset, person_id, limit)).fetchall()
        return [{"id": r[0], "name": display_name(r[1]), "count": r[2]} for r in rows]

    # the first link of a chain is the compiler's own teacher: the compiler is his student
    compilers = [{"book": r[0], "key": r[1], "count": r[2]} for r in conn.execute(
        """SELECT c.name, c.key, COUNT(DISTINCT i.hadith_id) FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id
           JOIN hadiths h ON h.id = i.hadith_id JOIN collections c ON c.id = h.collection_id
           WHERE l.person_id = ? AND l.position = 1 GROUP BY c.id ORDER BY 3 DESC""", (person_id,))]
    return {"teachers": side(+1), "students": side(-1), "compilers": compilers}


def hadiths_of(conn: sqlite3.Connection, person_id: int, limit: int = 60) -> tuple[list[dict], int]:
    """The hadith whose chains include this narrator: (rows, total)."""
    total = conn.execute("SELECT COUNT(DISTINCT i.hadith_id) FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id "
                         "WHERE l.person_id = ?", (person_id,)).fetchone()[0]
    rows = conn.execute(
        """SELECT DISTINCT i.hadith_id, c.name, h.number, h.number_sort, c.key FROM isnad_links l
           JOIN isnads i ON i.id = l.isnad_id JOIN hadiths h ON h.id = i.hadith_id
           JOIN collections c ON c.id = h.collection_id
           WHERE l.person_id = ? ORDER BY c.key, h.number_sort LIMIT ?""", (person_id, limit)).fetchall()
    return [{"hadith_id": r[0], "book": r[1], "number": r[2]} for r in rows], total
