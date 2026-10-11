"""The scholars of hadith in isnady: who they are, and what the imported data shows of their work.

Three roles, each measured from the data rather than described:
  compiler  the author of an imported collection: its hadith, its chains, the teachers he narrates from;
  grader    a scholar whose grades of hadith are imported: how he grades, and how far he agrees with the
            others on the same hadith (agreement, Cohen's kappa, and a strictness index — the classical
            mutashaddid / mutasahil, measured: his grade group minus the mean of the others' on the same hadith);
  critic    a scholar whose verdicts on narrators are imported (Ibn Hajar's Taqrib): his ranks.
Life dates are given only where they are certain; the lives themselves are TODO H4.

Sunni and Shia scholars stand on the same page, each by his own road (SH1): a Shia compiler's chains end at a
Ma'sum, a Shia grader is compared only with Shia graders on the Imami categories (grades.imami_group), a Shia critic's
verdicts are counted in the Imami terms (shia_rijal) — never on the Sunni scales.
"""

import sqlite3
from collections import Counter, defaultdict

from isnady.core.grades import GROUP_LABELS, IMAMI_LABELS, group, imami_group, isnad_only

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
    {"id": "arnaut", "short": "al-Arna'ut", "known_ar": "الأرناؤوط", "tr": "Şuayb el-Arnaût", "name": "Shu'ayb al-Arna'ut", "full": "Shu'ayb al-Arna'ut", "arabic": "شعيب الأرناؤوط",
     "dates": "1928–2016 CE", "works": ["editions of the Sunan and the Musnad of Ahmad with grading"],
     "grader_names": ["Shuaib Al Arnaut"]},
    {"id": "zubairalizai", "known_ar": "زبير علي زئي", "tr": "Zübeyr Ali Zaî", "name": "Zubair 'Ali Za'i", "full": "Hafiz Zubair 'Ali Za'i", "arabic": "زبير علي زئي",
     "dates": "1957–2013 CE", "works": ["grading of the Sunan (Urdu editions)"], "grader_names": ["Zubair Ali Zai"]},
    {"id": "muhyialdin", "short": "Muhyi al-Din", "known_ar": "محمد محيي الدين عبد الحميد", "tr": "Muhammed Muhyiddin Abdülhamîd", "name": "Muhammad Muhyi al-Din 'Abd al-Hamid",
     "full": "Muhammad Muhyi al-Din 'Abd al-Hamid", "arabic": "محمد محيي الدين عبد الحميد", "dates": "",
     "works": ["edition of Sunan Abi Dawud"], "grader_names": ["Muhammad Muhyi Al-Din Abdul Hamid"]},
    # ---------------------------------------------------------------- Shia (road B): tradition "shia"
    {"id": "kulayni", "tradition": "shia", "known_ar": "الكليني", "tr": "Küleynî", "name": "al-Kulayni",
     "full": "Muhammad b. Ya'qub al-Kulayni", "arabic": "محمد بن يعقوب الكليني", "dates": "d. 329 AH (941 CE)",
     "works": ["al-Kafi"], "compiler_of": ["kafi"], "najashi": "محمد بن يعقوب بن إسحاق"},
    {"id": "saduq", "tradition": "shia", "known_ar": "الصدوق", "tr": "Şeyh Sadûk (İbn Bâbeveyh)", "name": "al-Shaykh al-Saduq",
     "full": "Muhammad b. 'Ali b. al-Husayn Ibn Babawayh al-Qummi", "arabic": "محمد بن علي بن الحسين بن بابويه القمي",
     "dates": "d. 381 AH (991 CE)",
     "works": ["Man la yahduruhu al-faqih", "'Uyun Akhbar al-Rida", "al-Amali", "al-Khisal", "al-Tawhid",
               "Ma'ani al-Akhbar", "Thawab al-A'mal", "Sifat al-Shi'a", "Fada'il al-Shi'a"],
     "compiler_of": ["uyun", "amali-saduq", "khisal", "tawhid", "maani", "thawab", "sifat-shia", "fadail-shia", "faqih"],
     "najashi": "محمد بن علي بن الحسين بن موسى بن بابويه"},
    {"id": "mufid", "tradition": "shia", "known_ar": "المفيد", "tr": "Şeyh Müfîd", "name": "al-Shaykh al-Mufid",
     "full": "Muhammad b. Muhammad b. al-Nu'man al-Mufid", "arabic": "محمد بن محمد بن النعمان المفيد",
     "dates": "d. 413 AH (1022 CE)", "works": ["al-Amali", "al-Irshad", "al-Muqni'a"], "compiler_of": ["amali-mufid"],
     "najashi": "محمد بن محمد بن النعمان"},
    {"id": "ibnqulawayh", "tradition": "shia", "known_ar": "ابن قولويه", "tr": "İbn Kulaveyh", "name": "Ibn Qulawayh",
     "full": "Ja'far b. Muhammad Ibn Qulawayh al-Qummi", "arabic": "جعفر بن محمد بن جعفر بن موسى بن قولويه القمي",
     "dates": "d. 368 AH (978 CE)", "works": ["Kamil al-Ziyarat"], "compiler_of": ["kamil-ziyarat"],
     "najashi": "جعفر بن محمد بن جعفر بن موسى بن قولويه"},
    {"id": "numani", "tradition": "shia", "known_ar": "النعماني", "tr": "Nu'mânî (İbn Ebî Zeyneb)", "name": "al-Nu'mani",
     "full": "Muhammad b. Ibrahim al-Nu'mani (Ibn Abi Zaynab)", "arabic": "محمد بن إبراهيم بن جعفر النعماني",
     "dates": "d. c. 360 AH (971 CE)", "works": ["Kitab al-Ghayba"], "compiler_of": ["ghayba-numani"],
     "najashi": "محمد بن إبراهيم بن جعفر"},
    {"id": "tusi", "tradition": "shia", "known_ar": "الطوسي", "tr": "Şeyh Tûsî (Şeyhü't-Tâife)", "name": "al-Shaykh al-Tusi",
     "full": "Muhammad b. al-Hasan al-Tusi (Shaykh al-Ta'ifa)", "arabic": "محمد بن الحسن بن علي الطوسي",
     "dates": "385–460 AH (995–1067 CE)",
     "works": ["Tahdhib al-Ahkam", "al-Istibsar", "Kitab al-Ghayba", "al-Rijal", "al-Fihrist"],
     "compiler_of": ["ghayba-tusi", "tahdhib", "istibsar"], "najashi": "محمد بن الحسن بن علي الطوسي"},
    {"id": "ahwazi", "tradition": "shia", "known_ar": "الحسين بن سعيد", "tr": "Hüseyin b. Saîd el-Ahvâzî",
     "name": "al-Husayn b. Sa'id al-Ahwazi", "full": "al-Husayn b. Sa'id b. Hammad al-Ahwazi",
     "arabic": "الحسين بن سعيد بن حماد الأهوازي", "dates": "3rd century AH",
     "works": ["Kitab al-Mu'min", "Kitab al-Zuhd"], "compiler_of": ["mumin", "zuhd"]},
    {"id": "muhsini", "short": "al-Muhsini", "tradition": "shia", "known_ar": "المحسني", "tr": "Âsıf Muhsinî", "name": "Asif al-Muhsini",
     "full": "Muhammad Asif al-Muhsini", "arabic": "محمد آصف المحسني", "dates": "1935–2019 CE",
     "works": ["Mu'jam al-Ahadith al-Mu'tabara", "Mashra'at Bihar al-Anwar"], "compiler_of": ["mujam-mutabara"],
     "grader_names": ["al-Muhsini (Mu'jam al-Ahadith al-Mu'tabara)"]},
    {"id": "majlisi", "short": "al-Majlisi", "tradition": "shia", "known_ar": "المجلسي", "tr": "Allâme Meclisî", "name": "al-'Allama al-Majlisi",
     "full": "Muhammad Baqir al-Majlisi", "arabic": "محمد باقر المجلسي", "dates": "1037–1110 AH (1627–1699 CE)",
     "works": ["Mir'at al-'Uqul (his grading of al-Kafi)", "Bihar al-Anwar", "Malaz al-Akhyar"],
     "grader_names": ["al-Majlisi (Mir'at al-'Uqul)"]},
    {"id": "behbudi", "short": "al-Behbudi", "tradition": "shia", "known_ar": "البهبودي", "tr": "Muhammed Bâkır Behbûdî", "name": "Muhammad Baqir al-Behbudi",
     "full": "Muhammad Baqir al-Behbudi", "arabic": "محمد باقر البهبودي", "dates": "1928–2015 CE",
     "works": ["Sahih al-Kafi (his selection of al-Kafi)"], "grader_names": ["al-Behbudi (Sahih al-Kafi)"]},
    {"id": "najashi", "tradition": "shia", "known_ar": "النجاشي", "tr": "Necâşî", "name": "al-Najashi",
     "full": "Ahmad b. 'Ali al-Najashi", "arabic": "أحمد بن علي بن أحمد بن العباس النجاشي", "dates": "372–450 AH (982–1058 CE)",
     "works": ["Rijal al-Najashi (Fihrist asma' musannifi al-Shi'a)"], "critic_names": ["al-Najashi"],
     "najashi": "أحمد بن علي بن أحمد بن العباس"},
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
    "imami": "The Imami grades: sahih — every narrator an Imami thiqa; hasan — a praised Imami among them; "
             "muwaththaq — a thiqa of another school among them; da'if — the rest (al-Majlisi's majhul, mursal and "
             "marfu' counted here). Compared only among the Shia graders, never with the Sunni ones.",
    "agreement": "Agreement: on how many of the hadith both scholars graded they gave the same group "
                 "(sahih, hasan, da'if, very weak, fabricated).",
    "kappa": "Cohen's kappa: agreement after removing what chance alone would give. 1 = always the same, 0 = no "
             "better than chance; above 0.8 is very strong, 0.6–0.8 strong, 0.4–0.6 moderate.",
    "strictness": "Strictness: comparing his grade with each other grader's on the same hadith, how often his is LOWER "
                  "minus how often it is HIGHER — by order only (grades are ordered categories, not numbers). Below "
                  "zero he is stricter (classically mutashaddid), above zero more lenient (mutasahil). Statistics → "
                  "Graders measures it against a model of the true grade, with intervals."}


def tradition_of(scholar: dict) -> str:
    return scholar.get("tradition", "sunni")


def grader_names(tradition: str) -> set[str]:
    """The grader names of one tradition's scholars (as the sources write them)."""
    return {n for s in SCHOLARS if tradition_of(s) == tradition for n in s.get("grader_names", [])}


def name_view(scholar: dict) -> dict:
    """The scholar's name laid out like a narrator's (core.name_parts): known-as, reading, the parts."""
    from isnady.core import name_parts

    view = name_parts.present(name_parts.parse(scholar["arabic"], known_as=scholar.get("known_ar") or None))
    # where isnady cannot read the name he is known by yet (al-Majlisi, al-Saduq …), the name it gives him
    if not view.get("reading"):
        view["reading"] = scholar["name"]
    if len((view.get("full_reading") or "").split()) < 2:
        view["full_reading"] = scholar["full"]
    return view


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
    # Sunni first, Shia after them (BK1 order), each in the order of the list above
    return sorted(out, key=lambda s: tradition_of(s) == "shia")


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
    if not found:
        found = _close_spellings(text, roles)
    found.sort(key=lambda f: (not f[1], not f[0]["roles"]))
    return [s for s, _n in found]


def _close_spellings(text: str, roles: dict) -> list[tuple[dict, bool]]:
    """Nothing found as typed: every query word close to a word of his names or works (S4) — the same once
    loosened (zübeyrr, Buhaari: letters typed twice, kh/h …) or, from four letters, one letter apart (Albnai)."""
    from isnady.core.narrators import fold_latin, loose, near

    def words(hay: str) -> list[str]:
        return [loose(w) for w in (fold_latin(hay.replace("-", " ")).split() + _fold(hay).split()) if w]

    def fits(q: str, ws: list[str]) -> bool:
        return any(w.startswith(q) or (len(q) >= 4 and (near(q, w) or near(q, w[:len(q)]))) for w in ws)

    wanted = [q for q in (loose(w) for w in fold_latin(text).split()) if len(q) >= 3] or \
             [q for q in (loose(w) for w in _fold(text).split()) if len(q) >= 3]
    if not wanted:
        return []
    out = []
    for s in SCHOLARS:
        names = " ".join([s["name"], s["full"], s["tr"], s["arabic"], s.get("known_ar", "")])
        name_words, all_words = words(names), words(names + " " + " ".join(s["works"]))
        if all(fits(q, all_words) for q in wanted):
            out.append(({**s, "roles": roles.get(s["id"], []), "close": True}, all(fits(q, name_words) for q in wanted)))
    if any(in_name for _s, in_name in out):          # a close name, then not the titles that happen to be close too
        out = [(s, in_name) for s, in_name in out if in_name]
    return out


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
    exact = [s for s in SCHOLARS
             if any(_squeeze(name).startswith(wanted) for name in (s["name"], s["tr"], s.get("known_ar", "")) if name)]
    if exact:
        return exact
    # a close spelling (S4): letters typed twice once, kh/h, sh/s … (Buhaari, Elbaany, Nevevii)
    from isnady.core.narrators import loose

    wanted = loose(wanted)
    return [s for s in SCHOLARS
            if any(loose(_squeeze(name)).startswith(wanted) for name in (s["name"], s["tr"], s.get("known_ar", ""))
                   if name)]


def as_narrator(conn: sqlite3.Connection, scholar: dict) -> int | None:
    """His entry as a narrator in his own tradition's rijal work (the Taqrib, or al-Najashi), when there is one."""
    prefix = scholar.get("taqrib") or scholar.get("najashi")
    if not prefix:
        return None
    row = conn.execute("SELECT id FROM persons WHERE name_ar LIKE ? AND COALESCE(tradition, 'sunni') = ? "
                       "ORDER BY id LIMIT 1", (prefix + "%", tradition_of(scholar))).fetchone()
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
        # road B: whom the chains reach — the Prophet or an Imam (isnads.ends_with), not "the Companions"
        ends = []
        if tradition_of(scholar) == "shia":
            from isnady.core import traditions

            companions = []
            ends = [{"key": k, "label": traditions.masum_label(k) or k, "count": n} for k, n in conn.execute(
                """SELECT i.ends_with, COUNT(*) FROM isnads i JOIN hadiths h ON h.id = i.hadith_id
                   WHERE h.collection_id = ? AND i.problem IS NULL AND i.ends_with IS NOT NULL
                   GROUP BY 1 ORDER BY 2 DESC""", (cid,))]
        out.append({"key": key, "book": name, "hadith": hadith, "chains": chains[0] or 0,
                    "split": chains[1] or 0, "reach": chains[2] or 0, "links": links[0] or 0,
                    "identified": links[1] or 0, "teachers": teachers, "companions": companions, "ends": ends,
                    "tradition": tradition_of(scholar)})
    return out


# ------------------------------------------------------------------ grader
def _grade_groups(conn: sqlite3.Connection, tradition: str = "sunni") -> dict[str, dict[int, int]]:
    """grader name -> {hadith id: group} (the first grade a grader gives a hadith), for the graders of ONE
    tradition: the Sunni groups for the Sunni graders, the Imami categories for the Shia ones."""
    out: dict[str, dict[int, int]] = defaultdict(dict)
    seen: set = set()
    shia = grader_names("shia")
    for name, hid, grade in conn.execute("SELECT grader_name, hadith_id, grade FROM grades ORDER BY id"):
        if (name in shia) != (tradition == "shia") or (name, hid) in seen:
            continue
        seen.add((name, hid))
        if tradition != "shia" and isnad_only(grade):   # a grade of the chain only is not compared with the hadith's
            continue
        g = imami_group(grade) if tradition == "shia" else group(grade)
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
    tradition = tradition_of(scholar)
    labels = IMAMI_LABELS if tradition == "shia" else GROUP_LABELS
    groups = _grade_groups(conn, tradition)
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
    return {"graded": len(mine), "books": books, "tradition": tradition,
            "distribution": {labels[k]: distribution[k] for k in sorted(labels, reverse=True)},
            "wordings": wordings.most_common(8), "agreement": others,
            "strictness": ((higher - lower) / compared) if compared else None, "compared": compared,
            "lower": (lower / compared) if compared else None, "higher": (higher / compared) if compared else None}


# ------------------------------------------------------------------ critic
def critic_stats(conn: sqlite3.Connection, scholar: dict) -> dict | None:
    from isnady.core.rijal import RANK_LABELS

    names = scholar.get("critic_names", [])
    if not names:
        return None
    rows = conn.execute(f"SELECT rank, work, madhhab FROM verdicts WHERE critic_name IN ({','.join('?' * len(names))})",
                        names).fetchall()
    if not rows:
        return None
    ranks = Counter(r[0] for r in rows)
    if tradition_of(scholar) == "shia":
        # the Imami terms: reliability and creed, never Ibn Hajar's twelve ranks
        from isnady.core import shia_rijal

        creeds = Counter(r[2] for r in rows if r[2])
        return {"verdicts": len(rows), "works": sorted({r[1] for r in rows}), "tradition": "shia",
                "ranks": [(k, shia_rijal.RANKS[k][1].split(" (")[0], ranks[k]) for k in sorted(shia_rijal.RANKS)],
                "creeds": [(shia_rijal.MADHHAB_LABELS.get(k, k), n) for k, n in creeds.most_common()],
                "unranked": ranks[None]}
    return {"verdicts": len(rows), "works": sorted({r[1] for r in rows}), "tradition": "sunni",
            "ranks": [(k, RANK_LABELS[k][1].split(" (")[0], ranks[k]) for k in sorted(RANK_LABELS)],
            "unranked": ranks[None]}
