"""The scholars of hadith in isnady: who they are, and what the imported data shows of their work.

Three roles, each measured from the data rather than described:
  compiler  the author of an imported collection: its hadith, its chains, the teachers he narrates from;
  grader    a scholar whose grades of hadith are imported: how he grades, and how far he agrees with the
            others on the same hadith (agreement, Cohen's kappa, and a strictness index — the classical
            mutashaddid / mutasahil, measured: his grade group minus the mean of the others' on the same hadith);
  critic    a scholar whose verdicts on narrators are imported (Ibn Hajar's Taqrib): his ranks.
Life dates are given only where they are certain; the lives themselves are TODO H4.
"""

import sqlite3
from collections import Counter, defaultdict

from isnady.core.grades import isnad_only, GROUP_LABELS, group

SCHOLARS = [
    {"id": "bukhari", "known_ar": "البخاري", "tr": "Buhârî (Muhammed b. İsmâil)", "name": "al-Bukhari", "full": "Muhammad b. Isma'il al-Bukhari",
     "arabic": "محمد بن إسماعيل بن إبراهيم البخاري", "dates": "194–256 AH (810–870 CE)",
     "works": ["al-Jami' al-Sahih"], "compiler_of": ["bukhari"], "taqrib": "محمد بن إسماعيل بن إبراهيم بن المغيرة"},
    {"id": "muslim", "known_ar": "مسلم", "tr": "Müslim b. Haccâc", "name": "Muslim", "full": "Muslim b. al-Hajjaj al-Naysaburi",
     "arabic": "مسلم بن الحجاج النيسابوري", "dates": "d. 261 AH (875 CE)",
     "works": ["al-Sahih"], "compiler_of": ["muslim"], "taqrib": "مسلم بن الحجاج"},
    {"id": "abudawud", "known_ar": "أبو داود", "tr": "Ebû Dâvûd es-Sicistânî", "name": "Abu Dawud", "full": "Abu Dawud Sulayman b. al-Ash'ath al-Sijistani",
     "arabic": "أبو داود سليمان بن الأشعث السجستاني", "dates": "202–275 AH (817–889 CE)",
     "works": ["al-Sunan", "al-Marasil"], "compiler_of": ["abudawud"], "taqrib": "سليمان بن الأشعث"},
    {"id": "tirmidhi", "known_ar": "الترمذي", "tr": "Tirmizî", "name": "al-Tirmidhi", "full": "Muhammad b. 'Isa al-Tirmidhi",
     "arabic": "محمد بن عيسى الترمذي", "dates": "d. 279 AH (892 CE)",
     "works": ["al-Jami'", "al-Shama'il"], "compiler_of": ["tirmidhi"], "taqrib": "محمد بن عيسى بن سورة"},
    {"id": "nasai", "known_ar": "النسائي", "tr": "Nesâî", "name": "al-Nasa'i", "full": "Ahmad b. Shu'ayb al-Nasa'i",
     "arabic": "أحمد بن شعيب النسائي", "dates": "d. 303 AH (915 CE)",
     "works": ["al-Sunan"], "compiler_of": ["nasai"], "taqrib": "أحمد بن شعيب بن علي"},
    {"id": "ibnmajah", "known_ar": "ابن ماجه", "tr": "İbn Mâce", "name": "Ibn Maja", "full": "Muhammad b. Yazid Ibn Maja al-Qazwini",
     "arabic": "محمد بن يزيد القزويني", "dates": "d. 273 AH (887 CE)",
     "works": ["al-Sunan"], "compiler_of": ["ibnmajah"], "taqrib": "محمد بن يزيد الربعي"},
    {"id": "malik", "known_ar": "مالك", "tr": "Mâlik b. Enes", "name": "Malik", "full": "Malik b. Anas", "arabic": "مالك بن أنس",
     "dates": "d. 179 AH (795 CE)", "works": ["al-Muwatta'"], "compiler_of": ["malik"], "taqrib": "مالك بن أنس بن مالك"},
    {"id": "nawawi", "known_ar": "النووي", "tr": "Nevevî", "name": "al-Nawawi", "full": "Yahya b. Sharaf al-Nawawi", "arabic": "يحيى بن شرف النووي",
     "dates": "631–676 AH (1233–1277 CE)", "works": ["al-Arba'un", "Riyad al-Salihin", "Sharh Sahih Muslim"],
     "compiler_of": ["nawawi"]},
    {"id": "dehlawi", "known_ar": "الدهلوي", "tr": "Şah Veliyyullah ed-Dihlevî", "name": "Shah Waliullah al-Dihlawi", "full": "Shah Waliullah al-Dihlawi",
     "arabic": "شاه ولي الله الدهلوي", "dates": "1114–1176 AH (1703–1762 CE)", "works": ["al-Arba'un", "Hujjat Allah al-Baligha"],
     "compiler_of": ["dehlawi"]},
    {"id": "ibnhajar", "known_ar": "ابن حجر", "tr": "İbn Hacer el-Askalânî", "name": "Ibn Hajar al-'Asqalani", "full": "Ahmad b. 'Ali Ibn Hajar al-'Asqalani",
     "arabic": "أحمد بن علي بن حجر العسقلاني", "dates": "773–852 AH (1372–1449 CE)",
     "works": ["Taqrib al-Tahdhib", "Tahdhib al-Tahdhib", "Fath al-Bari", "al-Isaba"],
     "critic_names": ["Ibn Hajar al-'Asqalani"]},
    {"id": "albani", "known_ar": "الألباني", "tr": "Nâsırüddîn el-Elbânî", "name": "al-Albani", "full": "Muhammad Nasir al-Din al-Albani", "arabic": "محمد ناصر الدين الألباني",
     "dates": "1333–1420 AH (1914–1999 CE)", "works": ["Silsilat al-Ahadith al-Sahiha", "Silsilat al-Ahadith al-Da'ifa",
                                                   "Sahih / Da'if Sunan Abi Dawud"], "grader_names": ["Al-Albani"]},
    {"id": "arnaut", "known_ar": "الأرناؤوط", "tr": "Şuayb el-Arnaût", "name": "Shu'ayb al-Arna'ut", "full": "Shu'ayb al-Arna'ut", "arabic": "شعيب الأرناؤوط",
     "dates": "1928–2016 CE", "works": ["editions of the Sunan and the Musnad of Ahmad with grading"],
     "grader_names": ["Shuaib Al Arnaut"]},
    {"id": "zubairalizai", "known_ar": "زبير علي زئي", "tr": "Zübeyr Ali Zaî", "name": "Zubair 'Ali Za'i", "full": "Hafiz Zubair 'Ali Za'i", "arabic": "زبير علي زئي",
     "dates": "1957–2013 CE", "works": ["grading of the Sunan (Urdu editions)"], "grader_names": ["Zubair Ali Zai"]},
    {"id": "muhyialdin", "known_ar": "محمد محيي الدين عبد الحميد", "tr": "Muhammed Muhyiddin Abdülhamîd", "name": "Muhammad Muhyi al-Din 'Abd al-Hamid",
     "full": "Muhammad Muhyi al-Din 'Abd al-Hamid", "arabic": "محمد محيي الدين عبد الحميد", "dates": "",
     "works": ["edition of Sunan Abi Dawud"], "grader_names": ["Muhammad Muhyi Al-Din Abdul Hamid"]},
]


# what each role and each measure means — shown to the reader (isnady is a teaching tool)
ROLE_HELP = {
    "compiler": ("Compiler (musannif) · Kitap sahibi",
                 "A scholar who gathered hadith into a book, each with the chain he heard it through. The first "
                 "link of every chain is his own teacher; the last is usually the Companion who heard the Prophet."),
    "grader": ("Grader · Derece veren âlim",
               "A scholar who judged each hadith of a book: sahih (sound), hasan (good), da'if (weak), and so on. "
               "Different scholars can judge the same hadith differently; comparing them shows how strict each one is."),
    "critic": ("Critic of narrators (münekkit) · Ricâl âlimi",
               "A scholar who judged the narrators themselves — their honesty and the accuracy of their memory — "
               "in fixed words that rank them, from Companion down to liar (Ibn Hajar uses twelve ranks)."),
}
MEASURE_HELP = {
    "agreement": "Agreement: on how many of the hadith both scholars graded they gave the same group "
                 "(sahih, hasan, da'if, very weak, fabricated).",
    "kappa": "Cohen's kappa: agreement after removing what chance alone would give. 1 = always the same, 0 = no "
             "better than chance; above 0.8 is very strong, 0.6–0.8 strong, 0.4–0.6 moderate.",
    "strictness": "Strictness: comparing his grade with each other grader's on the same hadith, how often his is LOWER "
                  "minus how often it is HIGHER — by order only (grades are ordered categories, not numbers). Below "
                  "zero he is stricter (classically mutashaddid), above zero more lenient (mutasahil). Statistics → "
                  "Graders measures it against a model of the true grade, with intervals."}


def name_view(scholar: dict) -> dict:
    """The scholar's name laid out like a narrator's (core.name_parts): known-as, reading, the parts."""
    from isnady.core import name_parts

    return name_parts.present(name_parts.parse(scholar["arabic"], known_as=scholar.get("known_ar") or None))


def find(scholar_id: str) -> dict | None:
    return next((s for s in SCHOLARS if s["id"] == scholar_id), None)


def present(conn: sqlite3.Connection) -> list[dict]:
    """The scholars with something in this database, each with the roles the data gives him."""
    books = {r[0] for r in conn.execute("SELECT key FROM collections")}
    graders = {r[0] for r in conn.execute("SELECT DISTINCT grader_name FROM grades")}
    critics = {r[0] for r in conn.execute("SELECT DISTINCT critic_name FROM verdicts")}
    out = []
    for s in SCHOLARS:
        roles = []
        if set(s.get("compiler_of", [])) & books:
            roles.append("compiler")
        if set(s.get("grader_names", [])) & graders:
            roles.append("grader")
        if set(s.get("critic_names", [])) & critics:
            roles.append("critic")
        if roles:
            out.append({**s, "roles": roles})
    return out


def _fold(text: str) -> str:
    """Lower case, without accents or the marks of transliteration: "Buhârî" and "al-Bukhari" are compared as
    "buhari" and "albukhari"; Arabic letters are normalized (diacritics and letter forms ignored)."""
    import unicodedata

    from isnady.core.normalize import normalize

    text = normalize(text)
    text = "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))
    return "".join(c for c in text if c.isalnum() or c.isspace())


def search(conn: sqlite3.Connection, text: str) -> list[dict]:
    """The scholars whose names (Arabic, English, Turkish, the name he is known by) or works contain every word
    typed, those with something in this database first. Each has his roles here ([] when nothing is imported)."""
    from isnady.core.narrators import fold_latin

    words = [w.removeprefix("al").removeprefix("el") or w for w in _fold(text).split()]
    words = [w for w in words if w not in ("b", "bn", "ibn", "bin", "ب", "بن")]
    if not words:
        return []
    loose = fold_latin(text).split()          # Turkish and English spellings alike: "Sünen" finds "Sunan"

    def fits(hay: str) -> bool:
        exact = _fold(hay).replace(" ", "")
        return all(w in exact for w in words) or bool(loose) and all(
            w in fold_latin(hay.replace("-", " ")).replace(" ", "") for w in loose)

    roles = {s["id"]: s["roles"] for s in present(conn)}
    found = []
    for s in SCHOLARS:
        names = " ".join([s["name"], s["full"], s["tr"], s["arabic"], s.get("known_ar", "")])
        if fits(names + " " + " ".join(s["works"])):
            found.append(({**s, "roles": roles.get(s["id"], [])}, fits(names)))
    found.sort(key=lambda f: (not f[1], not f[0]["roles"]))
    return [s for s, _n in found]


_IBN = ("b", "bn", "ibn", "bin", "ب", "بن", "ابن")


def _squeeze(text: str) -> str:
    """A name as one string of letters, without the article and without "ibn": Latin through
    narrators.fold_latin ("al-Albani", "el-Elbânî" and "Albani" are all "albani"), Arabic normalized."""
    from isnady.core.narrators import fold_latin
    from isnady.core.normalize import normalize

    if any("\u0600" <= c <= "\u06ff" for c in text):
        words = [w.removeprefix("ال") if len(w) > 4 else w for w in normalize(text).split()]
        return "".join(w for w in words if w not in _IBN)
    return fold_latin(text).replace(" ", "")


def named(text: str) -> list[dict]:
    """The scholars KNOWN by the words typed: the name he is known by (in English, Turkish or Arabic) begins with
    them — "Bukhari", "Buhârî", "Abu Dawud", "Ibn Hajar", "Malik". Not "Anas", which only ends Malik b. Anas."""
    wanted = _squeeze(text)
    if len(wanted) < 3:
        return []
    return [s for s in SCHOLARS
            if any(_squeeze(name).startswith(wanted) for name in (s["name"], s["tr"], s.get("known_ar", "")) if name)]


def as_narrator(conn: sqlite3.Connection, scholar: dict) -> int | None:
    prefix = scholar.get("taqrib")
    if not prefix:
        return None
    row = conn.execute("SELECT id FROM persons WHERE name_ar LIKE ? ORDER BY id LIMIT 1", (prefix + "%",)).fetchone()
    return row[0] if row else None


# ------------------------------------------------------------------ compiler
def compiler_stats(conn: sqlite3.Connection, scholar: dict) -> list[dict]:
    from isnady.core.rijal import display_name

    out = []
    for key in scholar.get("compiler_of", []):
        row = conn.execute("SELECT id, name FROM collections WHERE key = ?", (key,)).fetchone()
        if row is None:
            continue
        cid, name = row
        hadith = conn.execute("SELECT COUNT(*) FROM hadiths WHERE collection_id = ?", (cid,)).fetchone()[0]
        chains = conn.execute(
            """SELECT COUNT(*), SUM(i.problem IS NULL), SUM(i.reaches_prophet) FROM isnads i
               JOIN hadiths h ON h.id = i.hadith_id WHERE h.collection_id = ?""", (cid,)).fetchone()
        links = conn.execute(
            """SELECT COUNT(*), SUM(l.person_id IS NOT NULL) FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id
               JOIN hadiths h ON h.id = i.hadith_id WHERE h.collection_id = ?""", (cid,)).fetchone()
        teachers = [{"id": r[0], "name": display_name(r[1]), "count": r[2]} for r in conn.execute(
            """SELECT l.person_id, p.name_ar, COUNT(*) FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id
               JOIN hadiths h ON h.id = i.hadith_id JOIN persons p ON p.id = l.person_id
               WHERE h.collection_id = ? AND l.position = 1 GROUP BY l.person_id ORDER BY 3 DESC LIMIT 12""", (cid,))]
        companions = [{"id": r[0], "name": display_name(r[1]), "count": r[2]} for r in conn.execute(
            """SELECT l.person_id, p.name_ar, COUNT(*) FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id
               JOIN hadiths h ON h.id = i.hadith_id JOIN persons p ON p.id = l.person_id
               WHERE h.collection_id = ? AND p.tabaqa = 1
                 AND l.position = (SELECT MAX(position) FROM isnad_links x WHERE x.isnad_id = l.isnad_id)
               GROUP BY l.person_id ORDER BY 3 DESC LIMIT 12""", (cid,))]
        out.append({"key": key, "book": name, "hadith": hadith, "chains": chains[0] or 0,
                    "split": chains[1] or 0, "reach": chains[2] or 0, "links": links[0] or 0,
                    "identified": links[1] or 0, "teachers": teachers, "companions": companions})
    return out


# ------------------------------------------------------------------ grader
def _grade_groups(conn: sqlite3.Connection) -> dict[str, dict[int, int]]:
    """grader name -> {hadith id: group} (the first grade a grader gives a hadith)."""
    out: dict[str, dict[int, int]] = defaultdict(dict)
    seen: set = set()
    for name, hid, grade in conn.execute("SELECT grader_name, hadith_id, grade FROM grades ORDER BY id"):
        if (name, hid) in seen:
            continue
        seen.add((name, hid))
        if isnad_only(grade):          # a grade of the chain only is not compared with a grade of the hadith
            continue
        g = group(grade)
        if g is not None:
            out[name][hid] = g
    return out


def _kappa(pairs: list[tuple[int, int]]) -> float | None:
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def grader_stats(conn: sqlite3.Connection, scholar: dict) -> dict | None:
    groups = _grade_groups(conn)
    names = [n for n in scholar.get("grader_names", []) if n in groups]
    if not names:
        return None
    mine = {}
    for n in names:
        mine.update(groups[n])
    wordings = Counter(r[0] for r in conn.execute(
        f"SELECT grade FROM grades WHERE grader_name IN ({','.join('?' * len(names))})", names))
    distribution = Counter(mine.values())
    others = {}
    for other, theirs in groups.items():
        if other in names:
            continue
        pairs = [(mine[h], theirs[h]) for h in mine.keys() & theirs.keys()]
        if not pairs:
            continue
        others[other] = {"common": len(pairs), "agree": sum(a == b for a, b in pairs) / len(pairs),
                         "within_one": sum(abs(a - b) <= 1 for a, b in pairs) / len(pairs),
                         "kappa": _kappa(pairs),
                         # ORDER only (grades are ordinal — never numbers, never averaged: the SK rule)
                         "lower": sum(a < b for a, b in pairs) / len(pairs),
                         "higher": sum(a > b for a, b in pairs) / len(pairs)}
    # strictness, by order: over every comparison with another grader on the same hadith,
    # P(his grade is lower) − P(his grade is higher); negative = stricter (mutashaddid)
    lower = higher = compared = 0
    for h, g in mine.items():
        for o in groups:
            if o not in names and h in groups[o]:
                compared += 1
                lower += g < groups[o][h]
                higher += g > groups[o][h]
    books = [r[0] for r in conn.execute(
        f"""SELECT DISTINCT c.name FROM grades g JOIN hadiths h ON h.id = g.hadith_id
            JOIN collections c ON c.id = h.collection_id WHERE g.grader_name IN ({','.join('?' * len(names))})""", names)]
    return {"graded": len(mine), "books": books, "distribution": {GROUP_LABELS[k]: distribution[k] for k in sorted(GROUP_LABELS, reverse=True)},
            "wordings": wordings.most_common(8), "agreement": others,
            "strictness": ((higher - lower) / compared) if compared else None, "compared": compared,
            "lower": (lower / compared) if compared else None, "higher": (higher / compared) if compared else None}


# ------------------------------------------------------------------ critic
def critic_stats(conn: sqlite3.Connection, scholar: dict) -> dict | None:
    from isnady.core.rijal import RANK_LABELS

    names = scholar.get("critic_names", [])
    if not names:
        return None
    rows = conn.execute(f"SELECT rank, work FROM verdicts WHERE critic_name IN ({','.join('?' * len(names))})", names).fetchall()
    if not rows:
        return None
    ranks = Counter(r[0] for r in rows)
    return {"verdicts": len(rows), "works": sorted({r[1] for r in rows}),
            "ranks": [(k, RANK_LABELS[k][1].split(" (")[0], ranks[k]) for k in sorted(RANK_LABELS)],
            "unranked": ranks[None]}
