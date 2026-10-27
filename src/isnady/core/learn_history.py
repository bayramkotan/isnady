"""Learn → History and method (LRN-H1, 2026-10-27): how the hadith were written down and gathered, the logic of the
method that sifts them, and the numbers of the books imported — counted live from this database.

Bayram (2026-10-27): "Lean kısmında bu defayları eklemek istiyorum. Bir de hadislerin toplanma mushaf olma
tarihçesini ve mantığını hatta istatistikliklerini … Bunun dışında hadislerin yazı ile de aktarıldığını ve bunun
istatistikleri??"

The articles are written text (assets/learn/articles.json, English, Türkçe, العربية); a section may ask for a block of
live numbers ("corpus", "writing", "mutawatir", "timeline"), counted here. Every count is of what the books say in
their own words and is a lower bound: a chain the parser could not read, or a wording not looked for, is not counted.
Each tradition is counted on its own and never added to the other (road A / road B). Qt-free: the Learn page and
`iy learn` read the same.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources

ROADS = ("sunni", "shia")

# the wordings of transmission that say a written text stood between two narrators — found in the Arabic text as the
# normaliser writes it (no diacritics, ي for ى, ه for ة, ا for أ/إ/آ)
WRITING_FORMS = (
    ("qiraa", r"(?<!\w)(قرات علي|قري علي|قراه علي|قراءه علي|عرضت علي)(?!\w)"),
    ("mukataba", r"(?<!\w)(كتب الي|كتب الينا|كتب به الي|في كتاب كتبه)(?!\w)"),
    ("wijada", r"(?<!\w)(وجدت في كتاب|وجدت بخط|قرات في كتاب)(?!\w)"),
    ("imla", r"(?<!\w)(املي علي|املي علينا|املاه علي|املاه)(?!\w)"),
    ("from_book", r"(?<!\w)(من كتابه|من كتابي|في كتابي)(?!\w)"),
    ("amr_shuayb", r"(?<!\w)عمرو بن شعيب عن ابيه عن جده(?!\w)"),
)
# what the texts themselves say about writing (in the words of the hadith, not of the chain)
WRITING_IN_TEXT = (
    ("sahifa", r"(?<!\w)(صحيفه|الصحيفه|صحيفته|صحيفتي)(?!\w)"),
    ("letters", r"(?<!\w)(كتب رسول الله|كتب النبي|كتاب رسول الله|كتاب النبي|كتب الي النجاشي|كتب الي قيصر|"
                r"كتب الي كسري|كتب الي هرقل)(?!\w)"),
    ("write_it", r"(?<!\w)(اكتبوا|اكتب|كنت اكتب|قيدوا العلم)(?!\w)"),
    ("no_write", r"(?<!\w)(لا تكتبوا عني|لا تكتبوا)(?!\w)"),
)
# Muslim and al-Nasa'i keep "haddathana" for what they heard and "akhbarana" for what was read out to the teacher
# from a written copy ('ard) — their own usage, as al-Nawawi and Ibn al-Salah report it; it is counted in their two
# books alone
AKHBARANA_BOOKS = ("muslim", "nasai")
HAMMAM_KEY = "taqrib:7317"        # Hammam b. Munabbih, whose written Sahifa from Abu Hurayra survives
MUTAWATIR_FORMS = r"(?<!\w)(من كذب علي متعمدا|من تعمد علي كذبا|كذب علي متعمدا|من كذب علي فليتبوا|من يقل علي ما لم اقل|" \
                  r"من تقول علي ما لم اقل)"


@lru_cache(maxsize=1)
def _data() -> dict:
    path = resources.files("isnady") / "assets" / "learn" / "articles.json"
    return json.loads(path.read_text(encoding="utf-8"))


def articles() -> list[dict]:
    return _data()["articles"]


def get(article_id: str) -> dict | None:
    return next((a for a in articles() if a["id"] == article_id), None)


def labels() -> dict:
    return _data()["labels"]


def timeline() -> list[dict]:
    return _data()["timeline"]


def say(value, lang: str) -> str:
    """A text of the articles in a language (a dict of languages), English when the language has none."""
    if isinstance(value, dict):
        return value.get(lang) or value.get("en") or ""
    return value or ""


def label(key: str, lang: str) -> str:
    return say(labels().get(key, key), lang)


def search(text: str, lang: str) -> list[dict]:
    """The articles whose title or text has the words (case and Arabic letter forms aside)."""
    from isnady.core.normalize import normalize

    words = normalize(text or "").split()
    if not words:
        return articles()
    out = []
    for a in articles():
        hay = normalize(" ".join([say(a["title"], lang), say(a.get("lead"), lang)]
                                 + [say(s.get("heading"), lang) + " " + " ".join(say(s.get("text"), lang)
                                                                                 if isinstance(say(s.get("text"), lang), list)
                                                                                 else [say(s.get("text"), lang)])
                                    for s in a["sections"]]))
        if all(w in hay for w in words):
            out.append(a)
    return out


# ---------------------------------------------------------------------- the live numbers
def _texts(conn):
    """(hadith id, book key, book name, number, tradition, Arabic text normalised) of every hadith."""
    return conn.execute(
        """SELECT h.id, c.key, c.name, h.number, COALESCE(c.tradition, 'sunni'), n.norm FROM text_norm n
           JOIN texts t ON t.id = n.text_id JOIN editions e ON e.id = t.edition_id
           JOIN hadiths h ON h.id = t.hadith_id JOIN collections c ON c.id = h.collection_id
           WHERE e.language = 'Arabic' ORDER BY h.collection_id, h.number_sort""")


def writing(conn) -> dict:
    """The traces of writing in the chains and in the texts, per tradition: {road: {"texts": n, "forms": {id: {"n",
    "books": {name: n}, "examples": [[name, number], …]}}, "in_text": {…}, "akhbarana": {name: links},
    "hammam": {name: hadith}}}. Counted once per change of the database (core.cache)."""
    from isnady.core import cache

    return cache.kept(conn, "learn-writing", _writing_counted)


def _writing_counted(conn) -> dict:
    forms = [(k, re.compile(p)) for k, p in WRITING_FORMS]
    in_text = [(k, re.compile(p)) for k, p in WRITING_IN_TEXT]
    out = {road: {"texts": 0, "forms": {}, "in_text": {}, "akhbarana": {}, "hammam": {}} for road in ROADS}

    def note(slot: dict, key: str, name: str, number: str) -> None:
        row = slot.setdefault(key, {"n": 0, "books": {}, "examples": []})
        row["n"] += 1
        row["books"][name] = row["books"].get(name, 0) + 1
        if len(row["examples"]) < 4:
            row["examples"].append([name, number])

    seen = set()
    for hid, key, _name, number, tradition, norm in _texts(conn):
        road = "shia" if tradition == "shia" else "sunni"
        name = key                                  # the book by its key; its name in the reader's language later
        if hid in seen:
            continue
        seen.add(hid)
        out[road]["texts"] += 1
        for k, rx in forms:
            if rx.search(norm or ""):
                note(out[road]["forms"], k, name, number)
        for k, rx in in_text:
            if rx.search(norm or ""):
                note(out[road]["in_text"], k, name, number)
    for name, n in conn.execute(
            f"""SELECT c.key, COUNT(*) FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id
                JOIN hadiths h ON h.id = i.hadith_id JOIN collections c ON c.id = h.collection_id
                WHERE c.key IN ({','.join('?' * len(AKHBARANA_BOOKS))}) AND l.transmission IN ('akhbarana', 'akhbarani')
                GROUP BY c.id ORDER BY c.id""", AKHBARANA_BOOKS):
        out["sunni"]["akhbarana"][name] = n
    for name, n in conn.execute(
            """SELECT c.key, COUNT(DISTINCT i.hadith_id) FROM isnad_links l JOIN persons p ON p.id = l.person_id
               JOIN isnads i ON i.id = l.isnad_id JOIN hadiths h ON h.id = i.hadith_id
               JOIN collections c ON c.id = h.collection_id WHERE p.key = ? GROUP BY c.id ORDER BY 2 DESC""",
            (HAMMAM_KEY,)):
        out["sunni"]["hammam"][name] = n
    return out


def corpus(conn) -> dict:
    """The size of what was handed down, per tradition: books, hadith, chains, the names in them, the narrators
    identified, the generations they belong to, the grades given. Counted once per change of the database."""
    from isnady.core import cache

    return cache.kept(conn, "learn-corpus", _corpus_counted)


def _corpus_counted(conn) -> dict:
    from isnady.core import grades as core_grades

    out = {}
    for road in ROADS:
        where = "COALESCE(c.tradition, 'sunni') = ?"
        books, hadith = conn.execute(
            f"SELECT COUNT(DISTINCT c.id), COUNT(h.id) FROM hadiths h JOIN collections c ON c.id = h.collection_id "
            f"WHERE {where}", (road,)).fetchone()
        chains, links, known, people = conn.execute(
            f"""SELECT COUNT(DISTINCT i.id), COUNT(l.isnad_id), SUM(l.person_id IS NOT NULL), COUNT(DISTINCT l.person_id)
                FROM isnads i JOIN isnad_links l ON l.isnad_id = i.id JOIN hadiths h ON h.id = i.hadith_id
                JOIN collections c ON c.id = h.collection_id WHERE {where}""", (road,)).fetchone()
        lengths = [r[0] for r in conn.execute(
            f"""SELECT COUNT(*) FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id JOIN hadiths h ON h.id = i.hadith_id
                JOIN collections c ON c.id = h.collection_id
                WHERE {where} AND i.problem IS NULL AND i.reaches_prophet = 1 GROUP BY i.id""", (road,))]
        lengths.sort()
        generations = {}
        for gen, n in conn.execute(
                f"""SELECT COALESCE(p.generation, '?'), COUNT(DISTINCT p.id) FROM isnad_links l
                    JOIN persons p ON p.id = l.person_id JOIN isnads i ON i.id = l.isnad_id
                    JOIN hadiths h ON h.id = i.hadith_id JOIN collections c ON c.id = h.collection_id
                    WHERE {where} GROUP BY 1""", (road,)):
            generations[gen] = n
        # the Companions most often at the end of the chains that reach the Prophet ﷺ: marked Companions in the
        # Taqrib, and the famous Companions whose entry carries no generation (Anas, Ibn 'Abbas …: core.famous)
        from isnady.core import famous

        famous_ids = set(famous.titles(conn, "en"))
        top = [[pid, name, n] for pid, name, n, gen in conn.execute(
            f"""SELECT p.id, p.name_ar, COUNT(DISTINCT i.hadith_id), p.generation FROM isnads i
                JOIN isnad_links l ON l.isnad_id = i.id
                JOIN persons p ON p.id = l.person_id JOIN hadiths h ON h.id = i.hadith_id
                JOIN collections c ON c.id = h.collection_id
                WHERE {where} AND i.reaches_prophet = 1 AND i.problem IS NULL
                  AND COALESCE(p.generation, 'sahabi') = 'sahabi'
                  AND l.position = (SELECT MAX(x.position) FROM isnad_links x WHERE x.isnad_id = i.id)
                GROUP BY p.id ORDER BY 3 DESC LIMIT 30""", (road,))
            if gen == "sahabi" or pid in famous_ids][:8] if road == "sunni" else []
        graded = {}
        for _hid, tradition, grade in conn.execute(
                f"""SELECT g.hadith_id, c.tradition, g.grade FROM grades g JOIN hadiths h ON h.id = g.hadith_id
                    JOIN collections c ON c.id = h.collection_id WHERE {where}""", (road,)):
            code = core_grades.code_of(grade, tradition)
            if code:
                graded[code] = graded.get(code, 0) + 1
        graded_hadith = conn.execute(
            f"""SELECT COUNT(DISTINCT g.hadith_id) FROM grades g JOIN hadiths h ON h.id = g.hadith_id
                JOIN collections c ON c.id = h.collection_id WHERE {where}""", (road,)).fetchone()[0]
        out[road] = {"books": books, "hadith": hadith, "chains": chains, "links": links, "identified": known or 0,
                     "narrators": people, "median_length": lengths[len(lengths) // 2] if lengths else 0,
                     "chains_to_end": len(lengths), "generations": generations, "top_companions": top,
                     "grades": graded, "graded_hadith": graded_hadith}
    return out


def mutawatir(conn) -> dict:
    """"Whoever lies about me deliberately …": in how many hadith, books and chains the books imported carry it."""
    from isnady.core import cache

    def count(c):
        rx = re.compile(MUTAWATIR_FORMS)
        ids, books = set(), {}
        for hid, key, _name, _number, tradition, norm in _texts(c):
            if tradition != "shia" and rx.search(norm or "") and hid not in ids:
                ids.add(hid)
                books[key] = books.get(key, 0) + 1
        chains = c.execute(f"SELECT COUNT(*) FROM isnads WHERE hadith_id IN ({','.join(map(str, ids)) or 'NULL'})"
                           ).fetchone()[0]
        return {"hadith": len(ids), "books": books, "chains": chains}

    return cache.kept(conn, "learn-mutawatir", count)


# ---------------------------------------------------------------------- the blocks as rows, for the page and the CLI
def block(conn, kind: str, lang: str) -> list[tuple[str, str, str]]:
    """A block of live numbers as rows (label, value, note) in a language; [] when nothing is imported."""
    L = lambda k: label(k, lang)  # noqa: E731
    rows: list[tuple[str, str, str]] = []
    if kind == "timeline":
        for e in timeline():
            when = f"{e['ah']} AH" if lang == "en" else (f"h. {e['ah']}" if lang == "tr" else f"{e['ah']} هـ")
            if e.get("ce"):
                when += f" / {e['ce']}"
            rows.append((when, say(e["what"], lang), ""))
        return rows
    if conn is None:
        return []
    if kind == "corpus":
        data = corpus(conn)
        for road in ROADS:
            d = data[road]
            if not d["hadith"]:
                continue
            rows.append((L(road), "", ""))
            share = f"{100 * d['identified'] / d['links']:.1f}%" if d["links"] else "—"
            rows += [(L("books"), f"{d['books']:,}", ""), (L("hadith"), f"{d['hadith']:,}", ""),
                     (L("chains"), f"{d['chains']:,}", L("chains_note")),
                     (L("links"), f"{d['links']:,}", L("links_note")),
                     (L("identified"), f"{d['identified']:,} ({share})", ""),
                     (L("narrators"), f"{d['narrators']:,}", L("narrators_note"))]
            if d["median_length"]:
                rows.append((L("median_length"), str(d["median_length"]), L("median_note")))
            for gen in ("sahabi", "tabi'i", "contemporary of junior tabi'in", "tabi' al-tabi'in", "later"):
                if d["generations"].get(gen):
                    rows.append((L("gen:" + gen), f"{d['generations'][gen]:,}", ""))
            if d["top_companions"]:
                from isnady.core import famous

                shown = famous.titles(conn, lang)
                for pid, name, n in d["top_companions"]:
                    rows.append((L("top_companion"), shown.get(pid) or " ".join(name.split()[:4]),
                                 f"{n:,} " + L("hadith_unit")))
            if d["graded_hadith"]:
                rows.append((L("graded_hadith"), f"{d['graded_hadith']:,}", L("graded_note")))
                for code, n in sorted(d["grades"].items(), key=lambda kv: -kv[1]):
                    rows.append((L("grade:" + code), f"{n:,}", L("grade_unit")))
        return rows
    if kind == "writing":
        data = writing(conn)
        for road in ROADS:
            d = data[road]
            if not d["texts"]:
                continue
            rows.append((L(road), f"{d['texts']:,} " + L("hadith_unit"), ""))
            for key, _p in WRITING_FORMS:
                r = d["forms"].get(key)
                if r:
                    rows.append((L("w:" + key), f"{r['n']:,}", _examples(r, lang)))
            for key, n in d["akhbarana"].items():
                rows.append((L("w:akhbarana") + f" — {_book(key, lang)}", f"{n:,}", L("w:akhbarana_note")))
            if d["hammam"]:
                total = sum(d["hammam"].values())
                rows.append((L("w:hammam"), f"{total:,}",
                             ", ".join(f"{_book(k, lang)} {v}" for k, v in d["hammam"].items())))
            for key, _p in WRITING_IN_TEXT:
                r = d["in_text"].get(key)
                if r:
                    rows.append((L("t:" + key), f"{r['n']:,}", _examples(r, lang)))
        return rows
    if kind == "mutawatir":
        d = mutawatir(conn)
        if d["hadith"]:
            rows += [(L("m:hadith"), f"{d['hadith']:,}", ""),
                     (L("m:books"), f"{len(d['books']):,}",
                      ", ".join(f"{_book(k, lang)} {v}" for k, v in d["books"].items())),
                     (L("m:chains"), f"{d['chains']:,}", L("m:note"))]
        return rows
    return rows


def _book(key: str, lang: str) -> str:
    from isnady.core import titles

    return titles.book(key, key, lang)


def _examples(row: dict, lang: str) -> str:
    return label("e.g.", lang) + " " + "; ".join(f"{_book(key, lang)} {number}" for key, number in row["examples"][:3])
