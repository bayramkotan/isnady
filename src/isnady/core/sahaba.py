"""Companions and the Household (AM1, EB1): the ten promised Paradise, the people of the cloak, the Mothers of the
Believers — and, on the Shia road and apart from the Sunni one (SH1), the Fourteen held infallible.

Each group stands as the sources give it: the hadith that names it (shown from the books imported here), what the
scholars of its own road read in it, and its members with what the imported books hold of them — how many chain
links and hadith each is in (the Sunni road), or how many chains end at each (the Shia road). Nothing is said of a
group that its own road does not say; where the two roads read a word differently, each is given on its own page.
"""

import sqlite3

from isnady.core.i18n import language

# the texts are written for isnady (CC BY 4.0, like the lives), each line with its source
GROUPS: list[dict] = [
    {
        "id": "ten", "road": "sunni",
        "title": {"en": "The ten promised Paradise", "tr": "Aşere-i Mübeşşere", "ar": "العشرة المبشرون بالجنة"},
        "lead": {
            "en": "Ten Companions whom the Prophet ﷺ named together, in one saying, as people of Paradise. 'Abd "
                  "al-Rahman b. 'Awf narrates the list as it is best known (al-Tirmidhi); Sa'id b. Zayd narrates it "
                  "too, counting the Prophet ﷺ among the ten and naming himself last (Abu Dawud) — so Abu 'Ubayda "
                  "is in the first list and not in the second. Many other Companions were given the glad tidings "
                  "of Paradise one by one; these are the ten named together.",
            "tr": "Resûlullah'ın ﷺ bir arada, tek bir sözde cennetlik olarak adlarını saydığı on sahâbî. Meşhur "
                  "listeyi Abdurrahman b. Avf rivayet eder (Tirmizî); Saîd b. Zeyd de rivayet eder, onun "
                  "rivayetinde Resûlullah ﷺ onların arasında sayılır ve onuncu olarak kendini söyler (Ebû Dâvûd) — "
                  "bu yüzden Ebû Ubeyde ilk listede vardır, ikincisinde yoktur. Başka birçok sahâbî de tek tek "
                  "cennetle müjdelenmiştir; bu on kişi bir arada sayılanlardır.",
            "ar": "عشرة من الصحابة سمّاهم النبي ﷺ معًا في حديث واحد من أهل الجنة. يروي القائمة المشهورة عبد الرحمن "
                  "بن عوف (الترمذي)، ويرويها سعيد بن زيد فيعدّ النبيَّ ﷺ فيهم ويذكر نفسه عاشرًا (أبو داود)، فأبو عبيدة "
                  "في الأولى دون الثانية. وبُشّر غيرهم كثير بالجنة فرادى، وهؤلاء العشرة هم الذين ذُكروا معًا.",
        },
        "hadith": [("tirmidhi", "3747"), ("abudawud", "4649")],
        "lives": ["abu-bakr", "umar", "uthman", "ali", "talha", "zubayr", "abd-al-rahman-b-awf", "sad-b-abi-waqqas",
                  "said-b-zayd", "abu-ubayda"],
    },
    {
        "id": "kisa", "road": "sunni",
        "title": {"en": "The Household: the people of the cloak", "tr": "Ehl-i Beyt: Âl-i Abâ (kisâ ehli)",
                  "ar": "أهل البيت: أصحاب الكساء"},
        "lead": {
            "en": "When \"Allah only wishes to remove impurity from you, O people of the house, and to purify you "
                  "thoroughly\" (al-Ahzab 33:33) was revealed, the Prophet ﷺ gathered 'Ali, Fatima, al-Hasan and "
                  "al-Husayn under his cloak and said: \"O Allah, these are the people of my house\" ('A'isha, in "
                  "Muslim; 'Umar b. Abi Salama, in al-Tirmidhi, where Umm Salama asks: \"And am I with them?\"). In "
                  "the Sunni reading the verse, which stands among the verses addressed to the Prophet's wives "
                  "(33:28–34), takes in his wives as well (the next group). Zayd b. Arqam, narrating the sermon at "
                  "Ghadir Khumm — \"I leave among you two weighty things: the Book of Allah … and the people of my "
                  "house\" — says that his wives are of his household, and that the household meant there are those "
                  "to whom charity is forbidden: the families of 'Ali, 'Aqil, Ja'far and al-'Abbas (Muslim).",
            "tr": "\"Ey Ehl-i Beyt! Allah sizden ancak kiri gidermek ve sizi tertemiz kılmak istiyor\" (Ahzâb 33:33) "
                  "âyeti inince Resûlullah ﷺ Ali, Fâtıma, Hasan ve Hüseyin'i abasının altına aldı ve \"Allahım, "
                  "bunlar benim Ehl-i Beytimdir\" dedi (Hz. Âişe'den, Müslim; Ömer b. Ebî Seleme'den, Tirmizî — "
                  "Ümmü Seleme orada \"Ben de onlarla mıyım?\" diye sorar). Sünnî okuyuşta Resûlullah'ın ﷺ "
                  "hanımlarına hitap eden âyetlerin (33:28–34) arasında duran bu âyet hanımlarını da kapsar (sonraki "
                  "grup). Zeyd b. Erkam, Gadîr-i Hum hutbesini — \"Size iki ağır emanet bırakıyorum: Allah'ın Kitabı "
                  "… ve Ehl-i Beytim\" — rivayet ederken, hanımlarının da Ehl-i Beyt'ten olduğunu, orada kastedilen "
                  "Ehl-i Beyt'in ise sadaka haram kılınanlar olduğunu söyler: Ali, Akîl, Ca'fer ve Abbas'ın aileleri "
                  "(Müslim).",
            "ar": "لما نزلت ﴿إِنَّمَا يُرِيدُ اللَّهُ لِيُذْهِبَ عَنكُمُ الرِّجْسَ أَهْلَ الْبَيْتِ وَيُطَهِّرَكُمْ تَطْهِيرًا﴾ "
                  "(الأحزاب 33) جمع النبي ﷺ عليًّا وفاطمة والحسن والحسين تحت كسائه وقال: «اللهم هؤلاء أهل بيتي» "
                  "(عن عائشة في مسلم، وعن عمر بن أبي سلمة في الترمذي، وفيه سؤال أم سلمة: «وأنا معهم؟»). وفي قراءة "
                  "أهل السنة تشمل الآيةُ — وهي بين الآيات المخاطِبة لأزواج النبي ﷺ (28–34) — أزواجَه أيضًا "
                  "(المجموعة التالية). وزيد بن أرقم، وهو يروي خطبة غدير خم «إني تارك فيكم ثقلين: كتاب الله … وأهل "
                  "بيتي»، يقول إن نساءه من أهل بيته، وإن أهل بيته المقصودين هنا من حُرم الصدقة: آل علي وآل عقيل وآل "
                  "جعفر وآل العباس (مسلم).",
        },
        "hadith": [("muslim", "6261"), ("tirmidhi", "3787"), ("muslim", "6225")],
        "lives": ["ali", "fatima", "hasan-b-ali", "husayn-b-ali"],
    },
    {
        "id": "mothers", "road": "sunni",
        "title": {"en": "The Mothers of the Believers", "tr": "Ezvâc-ı Tâhirât — mü'minlerin anneleri",
                  "ar": "أمهات المؤمنين"},
        "lead": {
            "en": "\"The Prophet is closer to the believers than their own selves, and his wives are their "
                  "mothers\" (al-Ahzab 33:6); the verses that call them \"people of the house\" (33:28–34) are "
                  "addressed to them. Khadija, the first of them, died before the Hijra. Below are those whose "
                  "narrations are in the rijal work, with what the imported books hold of them — 'A'isha before all.",
            "tr": "\"Peygamber mü'minlere kendilerinden daha yakındır; hanımları da onların anneleridir\" (Ahzâb "
                  "33:6); onlara \"Ehl-i Beyt\" diye hitap eden âyetler (33:28–34) onlara yöneliktir. İlki Hz. "
                  "Hatice, hicretten önce vefat etti. Aşağıda rical kitabında rivayeti olanlar, buraya aktarılan "
                  "kitapların onlardan tuttuklarıyla — en başta Hz. Âişe.",
            "ar": "﴿النَّبِيُّ أَوْلَىٰ بِالْمُؤْمِنِينَ مِنْ أَنفُسِهِمْ وَأَزْوَاجُهُ أُمَّهَاتُهُمْ﴾ (الأحزاب 6)، والآيات التي "
                  "تخاطبهن بأهل البيت (28–34) موجّهة إليهن. وأولاهن خديجة توفيت قبل الهجرة. وفيما يلي من لهن رواية في "
                  "كتاب الرجال، مع ما في الكتب المستوردة عنهن — وعائشة أولاهن.",
        },
        "hadith": [],
        "famous": "mothers",
    },
    {
        "id": "masumin", "road": "shia",
        "title": {"en": "The Household on the Shia road: the Fourteen Infallibles",
                  "tr": "Ehl-i Beyt — Şiî (İmâmî) yol: On Dört Masum", "ar": "أهل البيت عند الإمامية: المعصومون الأربعة عشر"},
        "lead": {
            "en": "In the Imami reading the people of the house of 33:33 are the people of the cloak, and after them "
                  "the Imams of their line, each named by the one before him; with the Prophet ﷺ and Fatima, "
                  "fourteen held infallible (ma'sum). In al-Kafi (the Book of the Proof) Abu Basir asks Ja'far "
                  "al-Sadiq about \"obey Allah, obey the Messenger and those in authority among you\" (al-Nisa' "
                  "4:59) and is told it was revealed about 'Ali, al-Hasan and al-Husayn. In the Shia books a chain "
                  "ends at one of them: how many end at each is counted below from the books imported here. The "
                  "years are those of al-Mufid's al-Irshad.",
            "tr": "İmâmî okuyuşta 33:33'ün Ehl-i Beyt'i kisâ ehlidir, onlardan sonra da her biri kendinden öncekinin "
                  "adıyla bildirdiği soylarından gelen İmamlar; Resûlullah ﷺ ve Hz. Fâtıma ile birlikte masum "
                  "sayılan on dört kişi. el-Kâfî'de (Kitâbü'l-Hucce) Ebû Basîr, Ca'fer es-Sâdık'a \"Allah'a itaat "
                  "edin, Peygamber'e ve sizden olan emir sahiplerine itaat edin\" (Nisâ 4:59) âyetini sorar; Ali, "
                  "Hasan ve Hüseyin hakkında indiği cevabını alır. Şiî kitaplarda sened onlardan birinde biter: "
                  "her birinde kaç senedin bittiği aşağıda buraya aktarılan kitaplardan sayılmıştır. Yıllar "
                  "Müfîd'in el-İrşâd'ındaki gibidir.",
            "ar": "في قراءة الإمامية أهل البيت في آية التطهير هم أصحاب الكساء، ومن بعدهم الأئمة من ذريتهم، ينصّ كل "
                  "واحد على الذي بعده؛ ومع النبي ﷺ وفاطمة أربعة عشر معصومًا. وفي الكافي (كتاب الحجة) يسأل أبو بصير "
                  "أبا عبد الله جعفرًا الصادق عن ﴿أَطِيعُوا اللَّهَ وَأَطِيعُوا الرَّسُولَ وَأُولِي الْأَمْرِ مِنكُمْ﴾ (النساء "
                  "59) فيجيبه أنها نزلت في علي والحسن والحسين. وفي كتب الشيعة ينتهي الإسناد إلى أحدهم، وعدد ما ينتهي "
                  "إلى كل واحد محسوب أدناه من الكتب المستوردة هنا. والسنوات كما في الإرشاد للمفيد.",
        },
        "hadith": [("kafi", "1:754")],
        # the tree of Quraysh's boxes, with the years of al-Mufid's al-Irshad
        "nodes": [("muhammad", {"en": "d. 11 AH", "tr": "v. h. 11", "ar": "ت 11هـ"}),
                  ("fatima", {"en": "d. 11 AH", "tr": "v. h. 11", "ar": "ت 11هـ"}),
                  ("ali", {"en": "d. 40 AH", "tr": "v. h. 40", "ar": "ت 40هـ"}),
                  ("hasan", {"en": "d. 50 AH", "tr": "v. h. 50", "ar": "ت 50هـ"}),
                  ("husayn", {"en": "d. 61 AH", "tr": "v. h. 61", "ar": "ت 61هـ"}),
                  ("sajjad", {"en": "d. 95 AH", "tr": "v. h. 95", "ar": "ت 95هـ"}),
                  ("baqir", {"en": "d. 114 AH", "tr": "v. h. 114", "ar": "ت 114هـ"}),
                  ("sadiq", {"en": "d. 148 AH", "tr": "v. h. 148", "ar": "ت 148هـ"}),
                  ("kazim", {"en": "d. 183 AH", "tr": "v. h. 183", "ar": "ت 183هـ"}),
                  ("rida", {"en": "d. 203 AH", "tr": "v. h. 203", "ar": "ت 203هـ"}),
                  ("jawad", {"en": "d. 220 AH", "tr": "v. h. 220", "ar": "ت 220هـ"}),
                  ("hadi", {"en": "d. 254 AH", "tr": "v. h. 254", "ar": "ت 254هـ"}),
                  ("askari", {"en": "d. 260 AH", "tr": "v. h. 260", "ar": "ت 260هـ"}),
                  ("mahdi", {"en": "b. 255 AH; in occultation since 260",
                             "tr": "d. h. 255; 260'tan beri gaybette", "ar": "ولد 255هـ، وفي الغيبة منذ 260"})],
    },
]

SHARED_KUNYAS = ("abu_al_hasan", "imam", "one_of_two", "mudmar")   # chain ends that name no one Imam


def _lang(lang: str | None) -> str:
    lang = lang or language()
    return lang if lang in ("en", "tr", "ar") else "en"


def text(values: dict, lang: str | None = None) -> str:
    lang = _lang(lang)
    return values.get(lang) or values["en"]


def groups(road: str | None = None) -> list[dict]:
    return [g for g in GROUPS if road is None or g["road"] == road]


def find(group_id: str) -> dict | None:
    return next((g for g in GROUPS if g["id"] == group_id), None)


def hadith(conn: sqlite3.Connection, group: dict) -> list[tuple[str, str, int]]:
    """(book, number, hadith id) of the hadith that name the group, those of them imported here."""
    out = []
    for book, number in group.get("hadith", []):
        row = conn.execute("SELECT h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id "
                           "WHERE c.key = ? AND h.number = ?", (book, number)).fetchone()
        if row:
            out.append((book, number, row[0]))
    return out


def _counts(conn: sqlite3.Connection, person_id: int) -> tuple[int, int]:
    links = conn.execute("SELECT COUNT(*) FROM isnad_links WHERE person_id = ?", (person_id,)).fetchone()[0]
    hadith_n = conn.execute("SELECT COUNT(DISTINCT i.hadith_id) FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id "
                            "WHERE l.person_id = ?", (person_id,)).fetchone()[0]
    return links, hadith_n


def members(conn: sqlite3.Connection | None, group: dict, lang: str | None = None) -> list[dict]:
    """Each member: name, arabic, died, summary (the first lines of his life), person (narrator id), life (its id),
    node (his box in the tree of Quraysh), links, hadith (Sunni road) or ends (Shia road: chains ending at him)."""
    from isnady.core import famous, genealogy, lives

    lang = _lang(lang)
    out = []
    if group.get("lives"):
        for life_id in group["lives"]:
            life = lives.by_id(life_id)
            if life is None:
                continue
            view = lives.view(life, lang)
            pid = lives.person_of(conn, life) if conn is not None else None
            died = next((v for k, (_label, v) in zip(view.get("fact_keys", []), view.get("facts", [])) if k == "died"), "")
            tree_node = genealogy.LIFE_NODES.get(life_id)
            row = {"name": view["title"], "arabic": life["name"].get("ar", ""), "died": died, "person": pid,
                   "life": life_id, "summary": (view.get("paragraphs") or [""])[0],
                   "node": tree_node[1] if tree_node and tree_node[0] == "quraysh" else None}
            if pid and conn is not None:
                row["links"], row["hadith"] = _counts(conn, pid)
            out.append(row)
    elif group.get("famous"):
        people = next(g["people"] for g in famous.groups(group["road"]) if g["id"] == group["famous"])
        for p in people:
            key = p[0]
            pid = None
            row = {"name": famous.title(p, lang), "arabic": p[3], "died": "", "person": None, "life": None,
                   "summary": "", "node": None}
            if conn is not None:
                found = conn.execute("SELECT id, death_year_ah FROM persons WHERE key = ?", (key,)).fetchone()
                if found:
                    pid = found[0]
                    row["person"] = pid
                    if found[1]:
                        row["died"] = text({"en": "d. {y} AH", "tr": "v. h. {y}", "ar": "ت {y}هـ"}, lang).format(y=found[1])
                    row["links"], row["hadith"] = _counts(conn, pid)
            life = lives.of_person(conn, pid) if conn is not None and pid else None
            if life:
                row["life"] = life["id"]
                row["summary"] = (lives.view(life, lang).get("paragraphs") or [""])[0]
            out.append(row)
        out.sort(key=lambda r: -(r.get("hadith") or 0))
    elif group.get("nodes"):
        tree = genealogy.written("quraysh", lang)
        ends = {}
        if conn is not None:
            ends = dict(conn.execute(
                "SELECT i.ends_with, COUNT(*) FROM isnads i JOIN hadiths h ON h.id = i.hadith_id "
                "JOIN collections c ON c.id = h.collection_id WHERE c.tradition = 'shia' AND i.ends_with IS NOT NULL "
                "GROUP BY i.ends_with").fetchall())
        for node_id, years in group["nodes"]:
            node = tree.nodes.get(node_id)
            if node is None:
                continue
            note = node.note.get(lang) or node.note.get("en") if isinstance(node.note, dict) else (node.note or "")
            out.append({"name": node.names.get(lang) or node.names["en"], "arabic": node.names.get("ar", ""),
                        "died": text(years, lang), "person": None, "life": None, "summary": note or "",
                        "node": node_id, "ends": ends.get("prophet" if node_id == "muhammad" else node_id, 0)})
    return out


def shared_ends(conn: sqlite3.Connection) -> int:
    """Chains of the Shia books ending at an Imam not named (al-Imam, Abu al-Hasan said of several, one of the two)."""
    marks = ",".join("?" * len(SHARED_KUNYAS))
    return conn.execute(
        f"SELECT COUNT(*) FROM isnads i JOIN hadiths h ON h.id = i.hadith_id JOIN collections c ON c.id = h.collection_id "
        f"WHERE c.tradition = 'shia' AND i.ends_with IN ({marks})", SHARED_KUNYAS).fetchone()[0]
