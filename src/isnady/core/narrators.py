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
        # only narrators of the chains' own tradition: every imported chain is Sunni, and a Shia rijal work's
        # narrator with the same name is a different source's judgment, not a candidate for these links
        for pid, tabaqa, name in conn.execute("SELECT id, tabaqa, name_ar FROM persons WHERE COALESCE(tradition, 'sunni') = 'sunni'"):
            self.tabaqa[pid] = tabaqa
            self.full[pid] = tokens(name)
        for pid, mark in conn.execute("SELECT person_id, mark FROM person_marks"):
            self.marks[pid].add(mark)
        for pid, name, kind in conn.execute("SELECT n.person_id, n.name, n.kind FROM person_names n JOIN persons p ON p.id = n.person_id "
                                            "WHERE COALESCE(p.tradition, 'sunni') = 'sunni'"):
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
_alias_cache: dict = {}


def known_aliases(conn: sqlite3.Connection, person_id: int) -> list[str]:
    """The aliases that may name this person by themselves. An alias of one narrator is his; an alias shared by
    several (التيمي: 7, بن عمر: 7) only for the one the chains cite most, at least twice as often as the next —
    "Ibn 'Umar" is the Companion, as the classical usage has it; the others are shown by their own names."""
    # nothing written since the last call, by this connection (total_changes) or another (data_version): the
    # answer stands, without counting the chains again — 200 rows of the Narrators list asked it 200 times (UI5-P)
    quick = (id(conn), conn.total_changes, conn.execute("PRAGMA data_version").fetchone()[0])
    if _alias_cache.get("quick") == quick and "allowed" in _alias_cache:
        return _alias_cache["allowed"].get(person_id, [])
    stamp = tuple(conn.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM person_names").fetchone()) + \
        tuple(conn.execute("SELECT COUNT(*), SUM(person_id IS NOT NULL) FROM isnad_links").fetchone())
    _alias_cache["quick"] = quick
    if _alias_cache.get("stamp") != stamp:
        uses = dict(conn.execute("SELECT person_id, COUNT(*) FROM isnad_links WHERE person_id IS NOT NULL "
                                 "GROUP BY person_id").fetchall())
        owners: dict = {}
        for pid, name in conn.execute("SELECT person_id, name FROM person_names WHERE kind = 'variant'"):
            owners.setdefault(name, []).append(pid)
        allowed: dict = {}
        for name, pids in owners.items():
            pids = sorted(set(pids), key=lambda p: -uses.get(p, 0))
            if len(pids) == 1:
                allowed.setdefault(pids[0], []).append(name)
            else:
                first, second = uses.get(pids[0], 0), uses.get(pids[1], 0)
                if first >= 10 and first >= 2 * second:
                    allowed.setdefault(pids[0], []).append(name)
        _alias_cache.update(stamp=stamp, allowed=allowed)
    return _alias_cache["allowed"].get(person_id, [])


def describe(conn: sqlite3.Connection, person_id: int) -> dict | None:
    """Everything the rijal works say about one person, for display."""
    from isnady.core.rijal import BOOK_MARKS, RANK_LABELS, TABAQA_LABELS

    p = conn.execute(
        """SELECT p.id, p.key, p.name_ar, p.kunya, p.tabaqa, p.generation, p.death_year_ah, p.death_year_note,
                  p.tradition, s.name AS source FROM persons p LEFT JOIN sources s ON s.id = p.source_id WHERE p.id = ?""",
        (person_id,),
    ).fetchone()
    if p is None:
        return None
    verdicts = [dict(v) for v in conn.execute(
        "SELECT critic_name, work, phrase, rank_scheme, rank, tradition, madhhab FROM verdicts WHERE person_id = ? ORDER BY id",
        (person_id,))]
    from isnady.core import shia_rijal

    for v in verdicts:
        if v["rank_scheme"] == "shia":
            v["rank_label"] = shia_rijal.RANKS[v["rank"]][1] if v["rank"] else ""
            v["madhhab_label"] = shia_rijal.MADHHAB_LABELS.get(v["madhhab"] or "", "")
        else:
            v["rank_label"] = RANK_LABELS.get(v["rank"], ("", ""))[1] if v["rank"] else ""
            v["madhhab_label"] = ""
    marks = [m[0] for m in conn.execute("SELECT mark FROM person_marks WHERE person_id = ?", (person_id,))]
    names = [n[0] for n in conn.execute(
        "SELECT name FROM person_names WHERE person_id = ? AND kind != 'full' ORDER BY kind, name", (person_id,))]
    narrations = conn.execute("SELECT COUNT(*) FROM isnad_links WHERE person_id = ?", (person_id,)).fetchone()[0]
    from isnady.core.rijal import display_name

    from isnady.core.names import latin

    shown = display_name(p["name_ar"])
    from isnady.core import name_parts

    view = name_parts.present(name_parts.parse(shown, p["kunya"], known_aliases(conn, person_id), p["name_ar"]))
    return {**dict(p), "display_name": shown, "latin_tr": latin(shown, "tr"), "latin_en": latin(shown, "en"),
            "name_view": view,
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
    "Musaddad") counts once, a word-initial y/w is a consonant, a final -i is the nisba ending.
    "b." and "bt." — how isnady itself writes ibn and bint — are ibn and bint."""
    bare = word.strip().strip(".").replace("İ", "i").replace("I", "ı").lower().replace("ı", "i")
    if bare in ("b", "bin", "ibn", "bn", "ben", "ibni", "ibnu", "ibnü", "bini"):     # Turkish İbni Abbas
        return "bn"
    if bare in ("bt", "bint", "binti", "bintu"):
        return "bnt"
    import unicodedata

    # Turkish spellings: ş is sh (Âişe), c is j (Câbir, Ca'fer), v is w (Dâvûd), dotless ı is i
    w = word.replace("I", "ı").replace("İ", "i").lower()
    w = w.replace("ş", "sh").replace("ı", "i").replace("c", "j").replace("ç", "ch").replace("v", "w")
    w = "".join(c for c in unicodedata.normalize("NFKD", w) if not unicodedata.combining(c))
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
    body = body.replace("q", "k")
    body = re.sub(r"[aeiouyw]", "", body)
    for digraph, mark in _LATIN_DIGRAPHS:
        body = body.replace(mark, digraph)
    return initial + body + ("y" if nisba and (initial + body) else "")


_skeleton_cache: dict = {}


def _skeleton_index(conn: sqlite3.Connection) -> list[tuple[int, list[str]]]:
    stamp = conn.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM person_names").fetchone()[:]
    if _skeleton_cache.get("stamp") != tuple(stamp):
        rows = []
        for pid, name, kind in conn.execute("SELECT person_id, name, kind FROM person_names"):
            words = name.split()
            own = kind == "full"           # the entry itself, not a name read from it or from elsewhere
            rows.append((pid, [arabic_skeleton(w) for w in words], own))
            # an entry that begins with its kunya ("أبو هريرة الدوسي") is also known by the kunya alone
            if len(words) > 2 and normalize(words[0]) in ("ابو", "ام", "ابي", "ابا"):
                kunya_words = words[:3] if normalize(words[1]) == "عبد" else words[:2]
                rows.append((pid, [arabic_skeleton(w) for w in kunya_words], own))
        _skeleton_cache.update(stamp=tuple(stamp), rows=rows)
    return _skeleton_cache["rows"]


def _token_index(conn: sqlite3.Connection) -> list[tuple[int, list[str]]]:
    """Every name as normalized words, plus the kunya alone of an entry that begins with it."""
    stamp = tuple(conn.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM person_names").fetchone()[:])
    if _skeleton_cache.get("token_stamp") != stamp:
        rows = []
        for pid, name, kind in conn.execute("SELECT person_id, name, kind FROM person_names"):
            words = tokens(name)
            own = kind == "full"
            rows.append((pid, words, own))
            if len(words) > 2 and words[0] in ("ابو", "ام"):
                rows.append((pid, words[:3] if words[1] == "عبد" else words[:2], own))
        _skeleton_cache.update(token_stamp=stamp, token_rows=rows)
    return _skeleton_cache["token_rows"]


def _exact(q: str, word: str) -> bool:
    # an Arabic query without the article finds the word with it: زبير finds الزبير
    if word.startswith("ال") and len(word) > 3 and not q.startswith("ال"):
        word = word[2:]
    # a short skeleton ("sh" of Aisha, "ns" of Anas) must be the whole word: as a beginning it fits hundreds
    return word == q if len(q) < 3 else word.startswith(q)


def _ordered_score(wanted: list[str], name: list[str], whole: list[str], full_name: list[str],
                   match=_exact) -> int | None:
    """None when the query words do not occur IN ORDER in the name (each as a word or the start of one);
    otherwise a score: one point per whole word, two when the name begins with the query's first word,
    a hundred when the query is the whole name ("Ibn Umar" = بن عمر, "Zuhri" = الزهري).
    "Anas ibn Malik" is not "Malik ibn Anas", and "سعيد … والد سفيان" is not "سفيان بن سعيد"."""
    i, score = 0, 0
    for q in wanted:
        while i < len(name) and not match(q, name[i]):
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


# ------------------------------------------------------------------ close spellings (S4)
def split_abd(text: str) -> str:
    """"Abdullah", "Abdurrahman", "Abdülaziz", "Abdulmelik", عبدالله — typed as one word — as the books write them,
    in two: abd + the name of God (عبد الله, عبد الرحمن). The article's l goes ("ulaziz" → aziz) unless it is
    Allah's ("ullah")."""
    def latin(m: re.Match) -> str:
        rest = re.sub(r"^[aeiouüı]", "", m.group(2))
        if rest.startswith("l") and not rest.startswith("ll"):
            rest = rest[1:]
        return f"{m.group(1)} {rest}" if rest else m.group(0)

    text = re.sub(r"\b([Aa]bd)([aeiouüı][a-zçğışöüâîû'-]{2,})", latin, text)
    return re.sub(r"(?<![\w])(عبد)(ال\w+)", r"\1 \2", text)



FUZZY_BELOW = 10        # fewer exact matches than this: look for close spellings too
_LOOSE_DIGRAPHS = (("kh", "h"), ("sh", "s"), ("th", "t"), ("dh", "z"), ("gh", "g"))


def loose(word: str) -> str:
    """A skeleton (or an Arabic word) with the distinctions a hurried or Turkish spelling loses: kh/h, sh/s, th/t,
    gh/g (Buhari = Bukhari), dh/z (Muaz = Mu'adh), a final h (Hurayrah = Hurayra), and a letter typed twice once
    (zuberyyyr → zbr). An Arabic word loses its article (زبيير → زبير finds الزبير)."""
    if word and not _ARABIC_LETTER.search(word):
        for digraph, single in _LOOSE_DIGRAPHS:
            word = word.replace(digraph, single)
        if len(word) > 2 and word.endswith("h"):
            word = word[:-1]
    elif word.startswith("ال") and len(word) > 3:
        word = word[2:]
    return re.sub(r"(.)\1+", r"\1", word)


def near(a: str, b: str) -> bool:
    """At most one letter apart: one added, dropped, changed, or two neighbours swapped (zübyer)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [i for i in range(la) if a[i] != b[i]]
        return len(diff) == 1 or (len(diff) == 2 and diff[1] == diff[0] + 1
                                  and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    if la > lb:
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def _same_loose(q: str, word: str) -> bool:
    """First pass: a query word (already loose) and a name word are the same once loosened (zuberyyyr = zbr,
    Buhaari = bhry = البخاري), or the query is the beginning of the name word (three letters or more)."""
    w = loose(word)
    return w == q or (len(q) >= 3 and w.startswith(q))


def _one_off(q: str, word: str) -> bool:
    """Second pass, only when the first finds too little: one letter apart, for words of four letters or more
    and with the first letter right — a consonant skeleton is short, and al-Zuhri (zhry) is one letter from
    al-Bukhari (bhry)."""
    w = loose(word)
    if w == q:
        return True
    if len(q) < 4 or not w or w[0] != q[0]:
        return False
    return near(q, w) or (len(w) > len(q) and near(q, w[:len(q)]))


def search_persons(conn: sqlite3.Connection, text: str, limit: int = 20,
                   close: set | None = None) -> list[tuple[int, str]]:
    """Persons whose names contain the words typed, in that order (diacritics and letter forms ignored).
    Latin letters are matched on the consonant skeleton ("Abu Hurayra", "Zuhri", "Ibn Abbas").
    A match in the person's own entry counts above the same match in a name read from elsewhere: Abu Hurayra
    himself ("أبو هريرة الدوسي") before an unnamed man the Taqrib describes through him.
    Fewer than FUZZY_BELOW matches: close spellings are looked for too (S4: zuberyyyr, Buhaari, زبيير), after
    every exact match; their ids are added to `close` when a set is given."""
    if not text.strip():
        return []
    best: dict[int, int] = {}
    latin_query = not _ARABIC_LETTER.search(text)
    text = split_abd(text)
    if latin_query:
        whole = [latin_skeleton(w) for w in text.split() if latin_skeleton(w)]
        wanted = [w for w in whole if w not in ("bn", "bnt")]          # "ibn", "bint" carry nothing here
        if not wanted:
            return []
        for pid, words, own in _skeleton_index(conn):
            core = [w for w in words if w not in ("bn", "bnt")]
            score = _ordered_score(wanted, core, whole, words)
            if score is not None:
                score += 10 * own
                best[pid] = max(best.get(pid, -1), score)
    else:
        whole = tokens(text)
        wanted = [w for w in whole if w != "بن"]
        if not wanted:
            return []
        for pid, words, own in _token_index(conn):
            core = [w for w in words if w != "بن"]
            score = _ordered_score(wanted, core, whole, words)
            if score is not None:
                score += 10 * own
                best[pid] = max(best.get(pid, -1), score)
    # close spellings, after every exact match: first the same letters loosened (scores from -1000), then — still
    # too few — one letter apart (from -2000)
    loose_wanted = [loose(w) for w in wanted]
    index = _skeleton_index(conn) if latin_query else _token_index(conn)
    ibn = ("bn", "bnt") if latin_query else ("بن",)
    for match, offset in ((_same_loose, -1000), (_one_off, -2000)):
        if len(best) >= FUZZY_BELOW:
            break
        for pid, words, own in index:
            if pid in best and best[pid] > offset + 500:
                continue
            core = [w for w in words if w not in ibn]
            score = _ordered_score(loose_wanted, core, whole, words, match=match)
            if score is not None:
                best[pid] = max(best.get(pid, -10**6), score + 10 * own + offset)
                if close is not None:
                    close.add(pid)
    uses = dict(conn.execute("SELECT person_id, COUNT(*) FROM isnad_links WHERE person_id IS NOT NULL "
                             "GROUP BY person_id").fetchall())
    order = sorted(best, key=lambda pid: (-best[pid], -uses.get(pid, 0)))[:limit]
    return [(pid, conn.execute("SELECT name_ar FROM persons WHERE id = ?", (pid,)).fetchone()[0]) for pid in order]


# ------------------------------------------------------------------ the Narrators page
def overview(conn: sqlite3.Connection, tradition: str = "sunni") -> dict:
    persons = conn.execute("SELECT COUNT(*) FROM persons WHERE COALESCE(tradition, 'sunni') = ?", (tradition,)).fetchone()[0]
    links = conn.execute("SELECT COUNT(*), SUM(person_id IS NOT NULL) FROM isnad_links").fetchone()
    works = [r[0] for r in conn.execute(
        "SELECT DISTINCT s.name FROM persons p JOIN sources s ON s.id = p.source_id WHERE COALESCE(p.tradition, 'sunni') = ? "
        "ORDER BY s.name", (tradition,))]
    return {"persons": persons, "links": links[0] or 0, "identified": links[1] or 0, "works": works}


def browse(conn: sqlite3.Connection, text: str = "", tabaqa: int | None = None, rank: int | None = None,
           book: str | None = None, limit: int = 300, tradition: str | None = "sunni",
           only: list[int] | None = None, close: set | None = None) -> tuple[list[dict], int]:
    """Narrators for the list: (rows, total before the limit), most often in the chains first.
    tradition None: both traditions (the Search page), each row saying which it belongs to."""
    from isnady.core.rijal import COLLECTION_MARKS, display_name

    where, args = [], []
    if tradition:
        where.append("COALESCE(p.tradition, 'sunni') = ?")
        args.append(tradition)
    if text.strip():
        ids = [pid for pid, _n in search_persons(conn, text, limit=5000, close=close)]
        if not ids:
            return [], 0
        where.append(f"p.id IN ({','.join(str(i) for i in ids)})")
    if only is not None:
        where.append(f"p.id IN ({','.join(str(int(i)) for i in only) or 'NULL'})")
    if tabaqa:
        where.append("p.tabaqa = ?")
        args.append(tabaqa)
    if rank == -1:
        where.append("v.rank IS NULL")                 # "no judgment" (a Shia rijal work silent on him)
    elif rank:
        where.append("v.rank = ?")
        args.append(rank)
    if book and book in COLLECTION_MARKS:
        marks = sorted(COLLECTION_MARKS[book])
        where.append(f"EXISTS (SELECT 1 FROM person_marks m WHERE m.person_id = p.id AND m.mark IN "
                     f"({','.join('?' * len(marks))}))")
        args.extend(marks)
    sql = f"""SELECT p.id, p.name_ar, p.tabaqa, p.death_year_ah, v.phrase, v.rank, v.madhhab,
                     (SELECT COUNT(*) FROM isnad_links l WHERE l.person_id = p.id) AS in_chains,
                     COALESCE(p.tradition, 'sunni'), (SELECT name FROM sources WHERE id = p.source_id)
              FROM persons p LEFT JOIN verdicts v ON v.id = (SELECT MIN(id) FROM verdicts WHERE person_id = p.id)
              {'WHERE ' + ' AND '.join(where) if where else ''}
              ORDER BY in_chains DESC, p.name_ar"""
    rows = conn.execute(sql, args).fetchall()
    if text.strip():
        # a search keeps its own order (best match first), not "most often in the chains"
        rank_of_id = {pid: i for i, pid in enumerate(ids)}
        rows.sort(key=lambda r: rank_of_id.get(r[0], len(ids)))
    from isnady.core import name_parts

    out = []
    for r in rows[:limit]:
        shown = display_name(r[1])
        kunya, = conn.execute("SELECT kunya FROM persons WHERE id = ?", (r[0],)).fetchone()
        view = name_parts.present(name_parts.parse(shown, kunya, known_aliases(conn, r[0]), r[1]))
        out.append({"id": r[0], "name": shown, "tabaqa": r[2], "death": r[3], "verdict": r[4] or "", "rank": r[5],
                    "madhhab": r[6], "in_chains": r[7], "view": view,
                    "tradition": r[8], "source": r[9] or ""})
    return out, len(rows)


def _query_words(text: str) -> tuple[list[str], bool]:
    """The words of a query as search_persons compares them, and whether they are Latin (skeletons)."""
    if _ARABIC_LETTER.search(text):
        return [w for w in tokens(text) if w != "بن"], False
    return [k for k in (latin_skeleton(w) for w in text.split()) if k and k not in ("bn", "bnt")], True


def _name_words(name: str, latin_query: bool, keep_ibn: bool = False) -> list[str]:
    """The words of a name, comparable with _query_words; keep_ibn keeps "b." / "ibn" (Ibn Abbas is not Abbas)."""
    if latin_query:
        words = [arabic_skeleton(w) for w in name.split()]
    else:
        words = ["بن" if w == "ابن" else w for w in tokens(name)]
    return words if keep_ibn else [w for w in words if w not in ("bn", "bnt", "بن", "بنت")]


def _whole_query(text: str, latin_query: bool) -> list[str]:
    if latin_query:
        return [k for k in (latin_skeleton(w) for w in text.split()) if k]
    return ["بن" if w == "ابن" else w for w in tokens(text)]


def fold_latin(text: str) -> str:
    """A Latin spelling reduced so that English and Turkish spellings of one name compare closely:
    "A'isha" and "Âişe" → "aisha", "Abu Hurayra" and "Ebû Hüreyre" → "abuhuraira" / "abuhurayra"."""
    import unicodedata

    w = text.replace("I", "ı").replace("İ", "i").lower()
    for a, b in (("ş", "sh"), ("ı", "i"), ("ç", "ch"), ("c", "j"), ("v", "w"), ("ğ", ""), ("q", "k")):
        w = w.replace(a, b)
    w = "".join(c for c in unicodedata.normalize("NFKD", w) if not unicodedata.combining(c))
    words = []
    for word in re.split(r"[\s]+", w):
        word = re.sub(r"^(al|el|an|ar|as|at|az|ad|ash|adh|en|er|es|et|ez|ed)-", "", word)
        word = re.sub(r"[^a-z]", "", word)
        if word in ("ibn", "bin", "bn", "b", "bint", "bt", "ibni", "ibnu", "bini", "binti"):
            continue
        words.append(word.replace("e", "a").replace("o", "u").replace("y", "i"))
    return " ".join(w for w in words if w)


def _closeness(query: str, reading: str) -> float:
    """How alike a Latin query and a name's reading are, letter by letter, over as many words as the query has."""
    import difflib

    q = fold_latin(query)
    r = " ".join(fold_latin(reading).split()[:max(1, len(q.split()))])
    return difflib.SequenceMatcher(None, q, r).ratio() if q and r else 0.0


SEARCH_RERANK = 400     # the best matches whose names are read (name_parts) to put the closest first


def find(conn: sqlite3.Connection, text: str, tradition: str | None = None) -> tuple[list[dict], int]:
    """Narrators for the Search page, both traditions unless one is asked for, the closest first:
      1. the query is the name he is known by ("Abu Hurayra", "al-Zuhri", "Ibn Umar");
      2. the query is in his name (Muhammad b. Ayyub, whose kunya is Abu Hurayra; "Aisha" → عائشة بنت …);
      3. the query occurs only in the words about him (a teacher his entry names).
    Within each, search_persons' own order (how well the words fit, then how often in the chains).
    Returns (rows, how many match in all); only the first SEARCH_RERANK matches are read and returned."""
    text = split_abd(text)
    wanted, latin_query = _query_words(text)
    if not wanted:
        return [], 0
    close: set = set()
    rows, total = browse(conn, text, limit=SEARCH_RERANK, tradition=tradition, close=close)

    whole = _whole_query(text, latin_query)

    def tier(row: dict, close_spelling: bool) -> int:
        # a close spelling (S4) is ranked the same way, on the loosened words, without asking for its vowels
        match = _one_off if close_spelling else _exact
        w_whole = [loose(w) for w in whole] if close_spelling else whole
        w_wanted = [loose(w) for w in wanted] if close_spelling else wanted
        known = _name_words(row["view"]["arabic"] or "", latin_query, keep_ibn=True)
        first = w_whole[0] if w_whole else ""
        begins = bool(known) and match(first, known[0])
        if begins and _ordered_score(w_whole, known, w_whole, known, match=match) is not None and (
                close_spelling or not latin_query or _closeness(text, row["view"]["reading"] or "") >= 0.8):
            return 0          # consonants alone confuse Umar and Amir, Aisha and Ayyash: a Latin query needs its vowels too
        # the name itself — ism, lineage, kunya, by-names, nisbas as name_parts reads them — not the words
        # about him that follow it in the entry ("… narrates from Abu Hurayra")
        parts = " ".join(arabic for _key, values, _star in row["view"]["rows"] for arabic, _latin in values)
        name = _name_words(parts, latin_query)
        if name and _ordered_score(w_wanted, name, w_wanted, name, match=match) is not None:
            return 1
        return 2

    for row in rows:
        row["close"] = row["id"] in close        # found by a close spelling, not the one typed (S4)
        row["tier"] = tier(row, row["close"]) + (10 if row["close"] else 0)    # close spellings after every exact match
        # a Latin query is matched on consonants only, so al-A'sha (الأعشى) fits "Aisha" as well as A'isha does;
        # the vowels of the readings put A'isha first
        row["closeness"] = (max(_closeness(text, row["view"]["reading"] or ""),
                                _closeness(text, row["view"]["full_reading"] or "")) if latin_query else 1.0)
    # a scholar known by the name typed ("Bukhari", "Abu Dawud") is first, when he is also a narrator here:
    # Muhammad b. Isma'il's entry begins with his name, not with "al-Bukhari"
    from isnady.core import scholars

    famous = {pid for pid in (scholars.as_narrator(conn, sc) for sc in scholars.named(text)) if pid}
    for row in rows:
        if row["id"] in famous:
            row["tier"] = -1
    missing = famous - {r["id"] for r in rows}
    if missing:
        more, _n = browse(conn, limit=len(missing), tradition=tradition, only=sorted(missing))
        rows.extend({**row, "tier": -1, "closeness": 1.0, "close": False} for row in more)
        total += len(more)
    order = {id(r): i for i, r in enumerate(rows)}
    rows.sort(key=lambda r: (r["tier"], -round(r["closeness"], 1), order[id(r)]))
    return rows, total


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
