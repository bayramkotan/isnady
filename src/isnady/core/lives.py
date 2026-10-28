"""The lives of the Companions, the Successors, the narrators and the scholars (BIO2).

Bayram (2026-10-17): "Râvilerin, âlimlerin, sahâbenin... hayatlarından hiçbir şey anlamıyorum. Onları daha düzgün
ve detaylı yapabilir misin? Râvilerin detayları olmayabilir çoğunun ama sahâbîlerin, âlimlerin..... olması gerekiyor!"

Two kinds of life, both in the interface language:
  written    a life written for isnady (assets/lives/*.json; English, Turkish and Arabic): who he was, his family,
             where he lived, what he did, his teachers and students, what the scholars said of him, his death —
             summarised from the classical biographical works named under it (Ibn Sa'd, al-Mizzi, al-Dhahabi,
             Ibn Hajar … for road A; al-Najashi, al-Tusi, al-Kashshi … for road B). The Companions, the great
             Successors and their followers, the imams of hadith and the compilers of the books.
  read       for every other narrator, his life as far as the data says it: the name read in Latin letters, his
             generation (Ibn Hajar's tabaqa) in words, the year of his death with its Common Era year, his rank,
             the books his hadith are in, how often he is in the chains, his teachers and students most often
             met there, the compilers who heard from him.
Each road by its own works (SH1): a Shia narrator's life is from the Imami rijal works, never the Sunni ones.

Qt-free: the Narrators and Hadith Scholars pages, and `iy life NAME`.
"""

from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from importlib import resources

from isnady.core.i18n import N_, language, n_, t

KINDS = {
    "prophet": N_("The Prophet"),
    "companion": N_("Companion"),
    "mother": N_("Mother of the Believers"),
    "successor": N_("Successor (tabi'i)"),
    "follower": N_("Follower of the Successors"),
    "imam": N_("Imam of a school of law"),
    "critic": N_("Hadith critic"),
    "compiler": N_("Compiler of a hadith book"),
    "narrator": N_("Narrator"),
    "scholar": N_("Hadith scholar"),
    "shia_companion": N_("Companion of the Imams"),
    "shia_scholar": N_("Imami scholar"),
}

FACTS = {
    "name": N_("Full name"),
    "born": N_("Born"),
    "died": N_("Died"),
    "lived": N_("Lived in"),
    "family": N_("Family"),
    "islam": N_("Islam"),
    "teachers": N_("Teachers"),
    "students": N_("Students"),
    "works": N_("Works"),
    "known": N_("Known for"),
    "hadith": N_("Hadith"),
    "prophethood": N_("Prophethood"),
}

# the works the written lives are summarised from: how each is named in every language
SOURCES = {
    "ibnsad": {"en": "Ibn Sa'd, al-Tabaqat al-Kubra", "tr": "İbn Sa'd, et-Tabakâtü'l-kübrâ", "ar": "ابن سعد، الطبقات الكبرى"},
    "istiab": {"en": "Ibn 'Abd al-Barr, al-Isti'ab", "tr": "İbn Abdilber, el-İstîâb", "ar": "ابن عبد البر، الاستيعاب"},
    "usd": {"en": "Ibn al-Athir, Usd al-Ghaba", "tr": "İbnü'l-Esîr, Üsdü'l-gâbe", "ar": "ابن الأثير، أسد الغابة"},
    "isaba": {"en": "Ibn Hajar, al-Isaba", "tr": "İbn Hacer, el-İsâbe", "ar": "ابن حجر، الإصابة في تمييز الصحابة"},
    "siyar": {"en": "al-Dhahabi, Siyar A'lam al-Nubala'", "tr": "Zehebî, Siyeru a'lâmi'n-nübelâ", "ar": "الذهبي، سير أعلام النبلاء"},
    "tadhkira": {"en": "al-Dhahabi, Tadhkirat al-Huffaz", "tr": "Zehebî, Tezkiretü'l-huffâz", "ar": "الذهبي، تذكرة الحفاظ"},
    "tarikh_islam": {"en": "al-Dhahabi, Tarikh al-Islam", "tr": "Zehebî, Târîhu'l-İslâm", "ar": "الذهبي، تاريخ الإسلام"},
    "tahdhib_kamal": {"en": "al-Mizzi, Tahdhib al-Kamal", "tr": "Mizzî, Tehzîbü'l-Kemâl", "ar": "المزي، تهذيب الكمال"},
    "tahdhib": {"en": "Ibn Hajar, Tahdhib al-Tahdhib", "tr": "İbn Hacer, Tehzîbü't-Tehzîb", "ar": "ابن حجر، تهذيب التهذيب"},
    "taqrib": {"en": "Ibn Hajar, Taqrib al-Tahdhib", "tr": "İbn Hacer, Takrîbü't-Tehzîb", "ar": "ابن حجر، تقريب التهذيب"},
    "tarikh_baghdad": {"en": "al-Khatib al-Baghdadi, Tarikh Baghdad", "tr": "Hatîb el-Bağdâdî, Târîhu Bağdâd", "ar": "الخطيب البغدادي، تاريخ بغداد"},
    "jarh": {"en": "Ibn Abi Hatim, al-Jarh wa'l-Ta'dil", "tr": "İbn Ebî Hâtim, el-Cerh ve't-ta'dîl", "ar": "ابن أبي حاتم، الجرح والتعديل"},
    "tabari": {"en": "al-Tabari, Tarikh al-Rusul wa'l-Muluk", "tr": "Taberî, Târîhu'r-rusül ve'l-mülûk", "ar": "الطبري، تاريخ الرسل والملوك"},
    "shamail_tirmidhi": {"en": "al-Tirmidhi, al-Shama'il al-Muhammadiyya", "tr": "Tirmizî, eş-Şemâilü'l-Muhammediyye", "ar": "الترمذي، الشمائل المحمدية"},
    "ibnhisham": {"en": "Ibn Hisham, al-Sira al-Nabawiyya", "tr": "İbn Hişâm, es-Sîretü'n-nebeviyye", "ar": "ابن هشام، السيرة النبوية"},
    "bidaya": {"en": "Ibn Kathir, al-Bidaya wa'l-Nihaya", "tr": "İbn Kesîr, el-Bidâye ve'n-nihâye", "ar": "ابن كثير، البداية والنهاية"},
    "wafayat": {"en": "Ibn Khallikan, Wafayat al-A'yan", "tr": "İbn Hallikân, Vefeyâtü'l-a'yân", "ar": "ابن خلكان، وفيات الأعيان"},
    "tabaqat_shafiiyya": {"en": "al-Subki, Tabaqat al-Shafi'iyya al-Kubra", "tr": "Sübkî, Tabakâtü'ş-Şâfiiyye", "ar": "السبكي، طبقات الشافعية الكبرى"},
    "daw": {"en": "al-Sakhawi, al-Daw' al-Lami' and al-Jawahir wa'l-Durar", "tr": "Sehâvî, ed-Dav'ü'l-lâmi' ve el-Cevâhir ve'd-dürer", "ar": "السخاوي، الضوء اللامع والجواهر والدرر"},
    "durar": {"en": "Ibn Hajar, al-Durar al-Kamina", "tr": "İbn Hacer, ed-Dürerü'l-kâmine", "ar": "ابن حجر، الدرر الكامنة"},
    "kashf": {"en": "Hajji Khalifa, Kashf al-Zunun", "tr": "Kâtib Çelebi, Keşfü'z-zunûn", "ar": "حاجي خليفة، كشف الظنون"},
    "nuzha": {"en": "'Abd al-Hayy al-Hasani, Nuzhat al-Khawatir", "tr": "Abdülhay el-Hasenî, Nüzhetü'l-havâtır", "ar": "عبد الحي الحسني، نزهة الخواطر"},
    "modern": {"en": "biographies published by his students and publishers", "tr": "talebelerinin ve yayıncılarının yayımladığı hayat hikâyeleri", "ar": "التراجم التي نشرها تلاميذه وناشرو كتبه"},
    "najashi": {"en": "al-Najashi, Rijal", "tr": "Necâşî, Ricâl", "ar": "النجاشي، رجال النجاشي"},
    "tusi_fihrist": {"en": "al-Tusi, al-Fihrist", "tr": "Tûsî, el-Fihrist", "ar": "الطوسي، الفهرست"},
    "tusi_rijal": {"en": "al-Tusi, Rijal", "tr": "Tûsî, Ricâl", "ar": "الطوسي، رجال الطوسي"},
    "kashshi": {"en": "al-Kashshi, Ikhtiyar Ma'rifat al-Rijal", "tr": "Keşşî, İhtiyâru ma'rifeti'r-ricâl", "ar": "الكشي، اختيار معرفة الرجال"},
    "khui": {"en": "al-Khu'i, Mu'jam Rijal al-Hadith", "tr": "Hûî, Mu'cemü ricâli'l-hadîs", "ar": "الخوئي، معجم رجال الحديث"},
    "ayan": {"en": "Muhsin al-Amin, A'yan al-Shi'a", "tr": "Muhsin el-Emîn, A'yânü'ş-Şîa", "ar": "محسن الأمين، أعيان الشيعة"},
    "talqih": {"en": "Ibn al-Jawzi, Talqih Fuhum Ahl al-Athar (the counts of Baqi b. Makhlad's Musnad)", "tr": "İbnü'l-Cevzî, Telkîhu fühûmi ehli'l-eser (Bakî b. Mahled'in Müsned'indeki sayılar)", "ar": "ابن الجوزي، تلقيح فهوم أهل الأثر (أعداد مسند بقي بن مخلد)"},
    "rawdat": {"en": "al-Khwansari, Rawdat al-Jannat", "tr": "Hânsârî, Ravzâtü'l-cennât", "ar": "الخوانساري، روضات الجنات"},
}


@lru_cache(maxsize=1)
def written() -> tuple[dict, ...]:
    """Every life written for isnady (assets/lives/*.json)."""
    out = []
    folder = resources.files("isnady.assets").joinpath("lives")
    try:
        files = sorted((f for f in folder.iterdir() if f.name.endswith(".json")), key=lambda f: f.name)
    except (FileNotFoundError, NotADirectoryError, OSError):
        return ()
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.extend(data.get("lives", []))
    return tuple(out)


@lru_cache(maxsize=1)
def _by_key() -> tuple[dict, dict, dict]:
    persons, scholars, ids = {}, {}, {}
    for life in written():
        ids[life["id"]] = life
        for key in life.get("persons", []):
            persons[key] = life
        if life.get("scholar"):
            scholars[life["scholar"]] = life
    return persons, scholars, ids


def of_person(conn: sqlite3.Connection, person_id: int) -> dict | None:
    """The written life of a narrator (by his stable key in the rijal work), or None."""
    row = conn.execute("SELECT key FROM persons WHERE id = ?", (person_id,)).fetchone()
    return _by_key()[0].get(row[0]) if row else None


def of_scholar(scholar_id: str) -> dict | None:
    return _by_key()[1].get(scholar_id)


def by_id(life_id: str) -> dict | None:
    return _by_key()[2].get(life_id)


def person_of(conn: sqlite3.Connection, life: dict) -> int | None:
    """The narrator a written life is about, when his rijal work is imported here."""
    for key in life.get("persons", []):
        row = conn.execute("SELECT id FROM persons WHERE key = ?", (key,)).fetchone()
        if row:
            return row[0]
    return None


def _in(values: dict | str | None, lang: str | None = None) -> str | list:
    """A text in the interface language: its own, else English, else Turkish, else Arabic."""
    if not isinstance(values, dict):
        return values or ""
    lang = lang or language()
    for code in (lang, "en", "tr", "ar"):
        if values.get(code):
            return values[code]
    return ""


def view(life: dict, lang: str | None = None) -> dict:
    """A written life in one language: {title, kind, facts: [(label, text)], paragraphs, sources}."""
    return {
        "id": life["id"],
        "title": _in(life.get("name"), lang),
        "kind": t(KINDS.get(life.get("kind", ""), "")),
        "road": life.get("road", "sunni"),
        "facts": [(t(FACTS.get(f["k"], f["k"])), _in(f, lang)) for f in life.get("facts", []) if _in(f, lang)],
        # which fact each is, for the names in "Teachers" and "Students" to open (2026-10-18)
        "fact_keys": [f["k"] for f in life.get("facts", []) if _in(f, lang)],
        "paragraphs": list(_in(life.get("text"), lang) or []),
        "sources": [_in(SOURCES.get(s, {"en": s}), lang) for s in life.get("sources", [])],
        # where to read more: a book in isnady ({"book": key}) or a free text on the web ({"url": …}) (GEN1-P)
        "read": [{"kind": r.get("kind", "url"), "book": r.get("book"), "url": r.get("url"), "text": _in(r, lang)}
                 for r in life.get("read", [])],
        # the entries of the classical works it is summarised from, to be read in their own words (BIO2b)
        "entries": _entries(life["id"], lang),
    }


def _entries(life_id: str, lang: str | None) -> list[dict]:
    from isnady.core import source_entries

    out = []
    for e in source_entries.of_life(life_id):
        out.append({**e, "title": source_entries.title(e["work"], lang or language()),
                    "where": t("vol. {volume}, no. {number}", volume=e["volume"], number=e["number"])})
    return out


def ce(year_ah: int) -> int:
    """The Common Era year in which a hijri year mostly falls."""
    return int(round(year_ah * 0.970229 + 621.5643))


def read(conn: sqlite3.Connection, person_id: int) -> dict | None:
    """The life of any narrator as far as the data says it, in the interface language:
    {title, kind, facts: [(label, text)], paragraphs, sources}."""
    from isnady.core import narrators
    from isnady.core.rijal import TABAQA_LABELS

    who = narrators.describe(conn, person_id)
    if who is None:
        return None
    shia = (who.get("tradition") or "sunni") == "shia"
    view_ = who["name_view"]
    title = view_.get("reading") or view_.get("full_reading") or who["display_name"]
    facts, paras = [], []
    full = view_.get("full_reading")
    if full and full != title:
        facts.append((t(FACTS["name"]), full))
    year = who.get("death_year_ah")
    if year:
        facts.append((t(FACTS["died"]), t("{year} AH (about {ce} CE)", year=year, ce=ce(year))))
    first = []
    if who.get("tabaqa"):
        first.append(t("In Ibn Hajar's Taqrib he is in tabaqa {n}: {label}.", n=who["tabaqa"],
                       label=t(TABAQA_LABELS.get(who["tabaqa"], ""))))
    if year:
        first.append(t("He died in {year} AH, about {ce} CE.", year=year, ce=ce(year)))
    for v in who["verdicts"]:
        if v.get("rank_label"):
            if v["rank_scheme"] == "shia":
                first.append(t("{critic} counts him as {label}.", critic=t(v["critic_name"]), label=v["rank_label"])
                             + (" " + t("His creed, in the critic's words: {creed}.", creed=v["madhhab_label"])
                                if v.get("madhhab_label") else ""))
            else:
                first.append(t("{critic} ranks him {rank} of 12: {label}.", critic=t(v["critic_name"]),
                               rank=v["rank"], label=v["rank_label"]))
    if who["marks"]:
        first.append(t("His hadith are in: {books}.", books="; ".join(m[1] for m in who["marks"])))
    if first:
        paras.append(" ".join(first))

    rel = narrators.relations(conn, person_id, limit=5)
    _rows, hadith = narrators.hadiths_of(conn, person_id, limit=1)
    second = []
    if who["in_chains"]:
        second.append(n_("In the books imported here he is in {chains:,} chain, of {hadith:,} hadith.",
                         "In the books imported here he is in {chains:,} chains, of {hadith:,} hadith.",
                         who["in_chains"], chains=who["in_chains"], hadith=hadith))

    def names(items):
        out = []
        for r in items:
            reading, _ar = narrators.reading(conn, r["id"], r["name"])
            out.append(f"{reading or r['name']} ({r['count']:,})")
        return ", ".join(out)
    if rel["teachers"]:
        second.append(t("He narrates most often from {names}.", names=names(rel["teachers"])))
    if rel["students"]:
        second.append(t("Those who narrate most often from him: {names}.", names=names(rel["students"])))
    if rel["compilers"]:
        second.append(t("He is a teacher of the compilers themselves in: {books}.",
                        books=", ".join(f"{c['book']} ({c['count']:,})" for c in rel["compilers"][:6])))
    if second:
        paras.append(" ".join(second))
    if rel["teachers"]:
        facts.append((t(FACTS["teachers"]), names(rel["teachers"][:3])))
    if rel["students"]:
        facts.append((t(FACTS["students"]), names(rel["students"][:3])))
    sources = [_in(SOURCES["najashi" if shia else "taqrib"]), t("the chains of the books imported here")]
    entries = []
    from isnady.core import huffaz

    hafiz = None if shia else huffaz.of_key(who.get("key"))
    if hafiz:
        # al-Dhahabi counts him among the huffaz (HFZ1): where, and the entry itself on request
        facts.append((t(FACTS["known"]), t("a hafiz of hadith: al-Dhahabi's Tadhkirat al-Huffaz, generation {tabaqa}",
                                          tabaqa=hafiz["tabaqa"])))
        sources.append(_in(SOURCES["tadhkira"]))
        entries.append(huffaz.source_entry(hafiz, language()))
    return {"id": "", "title": title, "kind": t(KINDS["narrator"]), "road": "shia" if shia else "sunni",
            "facts": facts, "paragraphs": paras, "sources": sources, "entries": entries}


def life(conn: sqlite3.Connection, person_id: int) -> tuple[dict | None, bool]:
    """(the life of a narrator, written) — his written life when there is one, else the one read from the data."""
    found = of_person(conn, person_id)
    if found is not None:
        return view(found), True
    return read(conn, person_id), False


def find(conn: sqlite3.Connection | None, text: str) -> list[dict]:
    """Written lives whose name, in any language, holds the words typed (for `iy life NAME`); letters compared
    without diacritics, Turkish and English spellings alike ("Ebu Hureyre", "Abu Hurayra")."""
    from isnady.core.narrators import fold_latin
    from isnady.core.normalize import normalize

    def fold(s: str) -> str:
        arabic = " ".join("بن" if w == "ابن" else w for w in normalize(s).split())
        return " ".join(w for w in (fold_latin(s) + " " + arabic).split() if w)

    query = fold(text)
    words = query.split()
    scored = []
    for item in written():
        names = [str(v) for v in (item.get("name") or {}).values()] + [item["id"].replace("-", " ")]
        hay = " ".join(fold(n) for n in names)
        if words and all(w in hay for w in words):
            # the name that is the words typed, or ends with them, first; then the shortest name
            folded = [f for f in (fold(n) for n in names) if all(w in f for w in words)] or [hay]
            exact = any(f == query or f.endswith(" " + query) for f in folded)
            scored.append((not exact, min(len(f) for f in folded), item["id"], item))
    return [x[-1] for x in sorted(scored, key=lambda x: x[:3])]
