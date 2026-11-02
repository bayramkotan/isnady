"""Written sources (SHF1): the hadith that were written down early, and how writing shows in the chains.

Most hadith came down by word of mouth, but some were written in the first generations. Three layers, each road on
its own (SH1):

1. A sahifa that came down whole: Hammam b. Munabbih's, from Abu Hurayra. Ahmad b. Hanbal copied it into his Musnad
   under one chain ('Abd al-Razzaq ← Ma'mar ← Hammam ← Abu Hurayra), the first hadith with the chain and the rest
   "and the Messenger of God ﷺ said …" — isnady finds those runs in the imported Musnad and shows each hadith beside
   its parallels in the other books that narrate it through Hammam.
2. Writings that live in later books: 'Abdullah b. 'Amr's al-Sahifa al-Sadiqa ('Amr b. Shu'ayb from his father from
   his grandfather), 'Ali's sahifa, Abu Bakr's letter on zakat, the letter for 'Amr b. Hazm; on the Shia road the
   Book of 'Ali, al-Jami'a and what the Shia books say of Mushaf Fatima. They did not reach us as books of their
   own: they are shown as the later books give them, and said so.
3. Writing in the chains: "he wrote to me", "I found in the book of …", "I read in the book of …".

Every list is isnady's reading of the texts as imported — a chain or a wording — and the page says so; nothing is
taken for a sahifa that its sources do not name.
"""

from __future__ import annotations

import re
import sqlite3

from isnady.core.i18n import language
from isnady.core.normalize import normalize

HAMMAM_NAME = "همام بن منبه"             # Hammam b. Munabbih, as Ibn Hajar's Taqrib names him

SOURCES: list[dict] = [
    {
        "id": "hammam", "road": "sunni", "layer": 1,
        "title": {"en": "The Sahifa of Hammam b. Munabbih", "tr": "Hemmâm b. Münebbih'in Sahîfesi",
                  "ar": "صحيفة همام بن منبه"},
        "lead": {
            "en": "Hammam b. Munabbih (d. 132), a Successor of Yemen, wrote down what Abu Hurayra told him from the "
                  "Prophet ﷺ. The sahifa came down whole — Hammam to Ma'mar, Ma'mar to 'Abd al-Razzaq — and Ahmad "
                  "b. Hanbal copied it into his Musnad under that one chain: the first hadith with the chain "
                  "(\"This is what Abu Hurayra told us …\"), every other one \"And the Messenger of God ﷺ said …\". "
                  "A manuscript of the sahifa itself was published by Muhammad Hamidullah (1953) with the same 138 "
                  "hadith. Al-Bukhari and Muslim took many of them through the same chain; their parallels are "
                  "shown beside each.",
            "tr": "Yemenli tâbiî Hemmâm b. Münebbih (ö. 132), Ebû Hüreyre'nin Resûlullah'tan ﷺ anlattıklarını "
                  "yazdı. Sahîfe bütün olarak ulaştı — Hemmâm'dan Ma'mer'e, Ma'mer'den Abdürrezzâk'a — ve Ahmed b. "
                  "Hanbel onu Müsned'ine tek senedle aldı: ilk hadis senediyle (\"Bu, Ebû Hüreyre'nin bize "
                  "anlattıklarıdır …\"), diğerleri \"Ve Resûlullah ﷺ dedi ki …\" diye. Sahîfenin kendi yazmasını "
                  "Muhammed Hamîdullah aynı 138 hadisle yayımladı (1953). Buhârî ve Müslim bunların birçoğunu aynı "
                  "senedle aldı; her hadisin yanında karşılıkları gösterilir.",
            "ar": "كتب همام بن منبه (ت ١٣٢)، التابعي اليمني، ما حدّثه به أبو هريرة عن النبي ﷺ. ووصلت الصحيفة كاملة — "
                  "من همام إلى معمر، ومن معمر إلى عبد الرزاق — ونقلها أحمد بن حنبل في مسنده بإسناد واحد: الحديث "
                  "الأول بإسناده («هذا ما حدثنا به أبو هريرة …») وسائرها «وقال رسول الله ﷺ …». ونشر محمد حميد الله "
                  "مخطوطة الصحيفة نفسها (١٩٥٣) بالأحاديث المئة والثمانية والثلاثين نفسها. وأخرج البخاري ومسلم كثيرًا "
                  "منها بالإسناد نفسه، وتُعرض نظائرها بجانب كل حديث.",
        },
        "how": {"en": "Found in the imported Musnad: the runs of hadith under Ma'mar ← Hammam that go on with \"And "
                      "the Messenger of God ﷺ said\"; the parallels are the hadith of the other books whose chain "
                      "passes through Hammam, matched to one of them by their wording (isnady's reading).",
                "tr": "İçe aktarılan Müsned'de bulunur: Ma'mer ← Hemmâm senedinin altında \"Ve Resûlullah ﷺ dedi "
                      "ki\" diye süren hadis dizileri; karşılıklar, diğer kitaplarda senedi Hemmâm'dan geçen "
                      "hadislerdir, sözlerine göre biriyle eşleştirilir (isnady'nin okuyuşu).",
                "ar": "يُستخرج من المسند المستورد: السلاسل التي تحت إسناد معمر عن همام وتستمر بـ«وقال رسول الله ﷺ»؛ "
                      "والنظائر أحاديث الكتب الأخرى التي يمر إسنادها بهمام، تُطابَق بألفاظها (قراءة isnady)."},
    },
    {
        "id": "sadiqa", "road": "sunni", "layer": 2,
        "title": {"en": "al-Sahifa al-Sadiqa of 'Abdullah b. 'Amr", "tr": "Abdullah b. Amr'ın es-Sahîfetü's-Sâdıka'sı",
                  "ar": "الصحيفة الصادقة لعبد الله بن عمرو"},
        "lead": {
            "en": "'Abdullah b. 'Amr b. al-'As wrote what he heard from the Prophet ﷺ, who told him: \"Write — by "
                  "Him in whose hand my soul is, nothing comes out of it but the truth\" (Abu Dawud, Ahmad); he "
                  "called what he wrote al-Sadiqa, \"the truthful\". It did not reach us as a book of its own: it "
                  "lives in later books, above all through his great-grandson's chain — 'Amr b. Shu'ayb from his "
                  "father from his grandfather — which many critics held to be read from that written sahifa.",
            "tr": "Abdullah b. Amr b. Âs, Resûlullah'tan ﷺ işittiklerini yazdı; Resûlullah ona \"Yaz! Nefsim "
                  "elinde olana yemin olsun ki ondan haktan başka bir şey çıkmaz\" dedi (Ebû Dâvûd, Ahmed). "
                  "Yazdıklarına es-Sâdıka, \"doğru olan\" adını verdi. Ayrı bir kitap olarak ulaşmadı: sonraki "
                  "kitaplarda yaşar, en çok torununun torununun senediyle — Amr b. Şuayb, babasından, o da "
                  "dedesinden — ki birçok münekkit bu senedin o yazılı sahîfeden okunduğunu söyledi.",
            "ar": "كتب عبد الله بن عمرو بن العاص ما سمعه من النبي ﷺ، وقال له: «اكتب، فوالذي نفسي بيده ما يخرج منه إلا "
                  "حق» (أبو داود، أحمد)، وسمّى ما كتب «الصادقة». ولم تصل كتابًا مستقلًا، بل تعيش في الكتب اللاحقة، "
                  "وأكثر ذلك بإسناد حفيده: عمرو بن شعيب عن أبيه عن جده، وقد عدّه كثير من النقاد قراءةً من تلك "
                  "الصحيفة المكتوبة.",
        },
        "how": {"en": "The hadith whose chain reads \"'Amr b. Shu'ayb from his father from his grandfather\", and "
                      "those that tell of his writing (\"Write …\") — isnady's reading of the texts.",
                "tr": "Senedi \"Amr b. Şuayb, babasından, o da dedesinden\" diye giden hadisler ve yazmasını anlatan "
                      "hadisler (\"Yaz …\") — isnady'nin metinleri okuyuşu.",
                "ar": "الأحاديث التي إسنادها «عمرو بن شعيب عن أبيه عن جده»، وما يروي كتابته («اكتب …») — قراءة isnady "
                      "للنصوص."},
        "patterns": ["عمرو بن شعيب عن أبيه عن جده", "اكتب فوالذي نفسي بيده"],
    },
    {
        "id": "ali", "road": "sunni", "layer": 2,
        "title": {"en": "The sahifa of 'Ali", "tr": "Hz. Ali'nin sahîfesi", "ar": "صحيفة علي"},
        "lead": {
            "en": "Asked whether the Prophet's family had been given anything besides the Qur'an, 'Ali said: "
                  "nothing but the Book of God and what is in this sahifa — blood-money, the freeing of captives, "
                  "and that no Muslim is killed for a disbeliever (al-Bukhari); in other versions also the sanctity "
                  "of Medina. He kept it in the sheath of his sword. The hadith that name it, as the Sunni books "
                  "give them.",
            "tr": "Ehl-i Beyt'e Kur'an'dan başka bir şey verilip verilmediği sorulunca Hz. Ali: Allah'ın Kitabı "
                  "ve bu sahîfedekilerden başka bir şey yok, dedi — diyetler, esirlerin kurtarılması ve bir "
                  "Müslüman'ın bir kâfir için öldürülmemesi (Buhârî); başka rivayetlerde Medine'nin haremliği de. "
                  "Onu kılıcının kınında taşırdı. Onu anan hadisler, Sünnî kitapların verdiği gibi.",
            "ar": "سُئل عليّ: هل خصّكم رسول الله ﷺ بشيء سوى القرآن؟ فقال: ما عندنا إلا كتاب الله وما في هذه الصحيفة: "
                  "العقل، وفكاك الأسير، ولا يُقتل مسلم بكافر (البخاري)، وفي روايات أخرى حرم المدينة. وكانت في قراب "
                  "سيفه. والأحاديث التي تذكرها كما في الكتب السنية.",
        },
        "how": {"en": "The hadith of the Sunni books that speak of \"this sahifa\".",
                "tr": "Sünnî kitaplarda \"bu sahîfe\"den söz eden hadisler.",
                "ar": "أحاديث الكتب السنية التي تذكر «هذه الصحيفة»."},
        "patterns": ["هذه الصحيفة"],
    },
    {
        "id": "zakat", "road": "sunni", "layer": 2,
        "title": {"en": "Abu Bakr's letter on zakat", "tr": "Hz. Ebû Bekir'in zekât mektubu",
                  "ar": "كتاب أبي بكر في الصدقة"},
        "lead": {
            "en": "When Abu Bakr sent Anas b. Malik to Bahrain he wrote for him \"the obligation of zakat which the "
                  "Messenger of God ﷺ imposed on the Muslims\": how much is due on camels, sheep and silver "
                  "(al-Bukhari, through Anas's grandson Thumama, who had the letter).",
            "tr": "Hz. Ebû Bekir, Enes b. Mâlik'i Bahreyn'e gönderirken ona \"Resûlullah'ın ﷺ Müslümanlara farz "
                  "kıldığı zekât\"ı yazdı: deve, koyun ve gümüşte ne kadar verileceği (Buhârî; mektup Enes'in "
                  "torunu Sümâme'deydi).",
            "ar": "لما وجّه أبو بكر أنسَ بن مالك إلى البحرين كتب له «فريضة الصدقة التي فرض رسول الله ﷺ على "
                  "المسلمين»: ما يجب في الإبل والغنم والفضة (البخاري، من طريق ثمامة حفيد أنس، وكان الكتاب عنده).",
        },
        "how": {"en": "The hadith that quote the letter (\"he wrote for him this letter\", \"the obligation of zakat "
                      "which …\").",
                "tr": "Mektubu aktaran hadisler (\"ona bu mektubu yazdı\", \"farz kıldığı zekât …\").",
                "ar": "الأحاديث التي تنقل الكتاب («كتب له هذا الكتاب»، «فريضة الصدقة التي فرض …»)."},
        "patterns": ["كتب له هذا الكتاب", "فريضة الصدقة التي فرض"],
    },
    {
        "id": "hazm", "road": "sunni", "layer": 2,
        "title": {"en": "The letter for 'Amr b. Hazm", "tr": "Amr b. Hazm'a yazılan mektup",
                  "ar": "كتاب عمرو بن حزم"},
        "lead": {
            "en": "The letter the Prophet ﷺ had written for 'Amr b. Hazm when he sent him to Yemen: blood-money, "
                  "zakat, and that none but the pure touch the Qur'an. Malik and al-Nasa'i give parts of it; the "
                  "family of 'Amr b. Hazm kept it.",
            "tr": "Resûlullah'ın ﷺ Amr b. Hazm'ı Yemen'e gönderirken onun için yazdırdığı mektup: diyetler, "
                  "zekât ve Kur'an'a temizlerden başkasının dokunmaması. Mâlik ve Nesâî ondan parçalar verir; "
                  "mektup Amr b. Hazm'ın ailesinde saklandı.",
            "ar": "الكتاب الذي كتبه رسول الله ﷺ لعمرو بن حزم حين بعثه إلى اليمن: الديات والصدقة وألا يمسّ القرآن "
                  "إلا طاهر. يروي مالك والنسائي أجزاءً منه، وكان عند آل عمرو بن حزم.",
        },
        "how": {"en": "The hadith that name the letter \"for 'Amr b. Hazm\".",
                "tr": "\"Amr b. Hazm için\" yazılan mektubu anan hadisler.",
                "ar": "الأحاديث التي تذكر الكتاب «لعمرو بن حزم»."},
        "patterns": ["لعمرو بن حزم", "كتاب عمرو بن حزم"],
    },
    {
        "id": "chains-sunni", "road": "sunni", "layer": 3,
        "title": {"en": "Writing in the chains", "tr": "Senedlerde yazı", "ar": "الكتابة في الأسانيد"},
        "lead": {
            "en": "Most links of a chain say they heard (\"he told us\", \"from\"). Some say the text came in "
                  "writing: \"he wrote to me\" (mukataba), \"I found in the book of …\" (wijada — 'Abdullah b. "
                  "Ahmad's \"I found in my father's book, in his hand\" in the Musnad), \"I read in the book of …\". "
                  "These are the chains of the Sunni books that say so.",
            "tr": "Senedlerin çoğu halkası işittiğini söyler (\"bize anlattı\", \"…den\"). Bazıları metnin yazıyla "
                  "geldiğini söyler: \"bana yazdı\" (mükâtebe), \"…in kitabında buldum\" (vicâde — Müsned'de "
                  "Abdullah b. Ahmed'in \"babamın kitabında, onun el yazısıyla buldum\" sözü), \"…in kitabında "
                  "okudum\". Bunlar Sünnî kitaplarda bunu söyleyen senedlerdir.",
            "ar": "أكثر حلقات الإسناد تذكر السماع («حدثنا»، «عن»)، وبعضها يذكر أن النص جاء كتابةً: «كتب إليّ» "
                  "(المكاتبة)، «وجدت في كتاب …» (الوجادة — ومنها قول عبد الله بن أحمد في المسند «وجدت في كتاب أبي "
                  "بخط يده»)، «قرأت في كتاب …». هذه أسانيد الكتب السنية التي تذكر ذلك.",
        },
        "how": {"en": "Read from the chains as written: the words of writing in the chain itself, not in the text.",
                "tr": "Senedler yazıldığı gibi okunur: yazı sözleri metinde değil, senedin kendisinde.",
                "ar": "تُقرأ الأسانيد كما كُتبت: ألفاظ الكتابة في الإسناد نفسه لا في المتن."},
        "chain": ["كتب إلي", "كتب إلينا", "كتب إليه", "كتبت إلى", "وجدت في كتاب", "قرأت في كتاب", "في كتاب أبي"],
    },
    # ------------------------------------------------------------------ the Shia road, on its own
    {
        "id": "kitab-ali", "road": "shia", "layer": 2,
        "title": {"en": "The Book of 'Ali", "tr": "Kitâbu Alî", "ar": "كتاب علي"},
        "lead": {
            "en": "The Imams of the Shia books often answer from \"the Book of 'Ali\": what 'Ali wrote in his own "
                  "hand from the dictation of the Messenger of God ﷺ, as these books relate it. The hadith of the "
                  "Shia books that cite it.",
            "tr": "Şiî kitaplarda imamlar çoğu zaman \"Kitâbu Alî\"den cevap verir: bu kitapların anlattığına göre "
                  "Resûlullah'ın ﷺ yazdırdığını Hz. Ali'nin kendi eliyle yazdığı kitap. Onu anan Şiî rivayetler.",
            "ar": "كثيرًا ما يجيب الأئمة في الكتب الشيعية من «كتاب علي»: ما كتبه عليّ بخط يده من إملاء رسول الله ﷺ، "
                  "كما ترويه هذه الكتب. وهذه أحاديث الكتب الشيعية التي تذكره.",
        },
        "how": {"en": "The hadith of the Shia books that name \"the Book of 'Ali\" or \"this sahifa\".",
                "tr": "Şiî kitaplarda \"Kitâbu Alî\" ya da \"bu sahîfe\" diyen rivayetler.",
                "ar": "أحاديث الكتب الشيعية التي تذكر «كتاب علي» أو «هذه الصحيفة»."},
        "patterns": ["كتاب علي", "هذه الصحيفة"],
    },
    {
        "id": "jamia", "road": "shia", "layer": 2,
        "title": {"en": "al-Jami'a", "tr": "el-Câmia", "ar": "الجامعة"},
        "lead": {
            "en": "In al-Kafi (Kitab al-Hujja) the Imam describes al-Jami'a: a scroll seventy cubits long by the "
                  "cubit of the Messenger of God ﷺ, from his dictation and in 'Ali's hand, holding every lawful and "
                  "unlawful thing people need. The hadith of the Shia books that describe it.",
            "tr": "el-Kâfî'de (Kitâbü'l-Hucce) imam el-Câmia'yı anlatır: Resûlullah'ın ﷺ zirâıyla yetmiş zirâ "
                  "uzunluğunda, onun yazdırmasıyla ve Hz. Ali'nin eliyle yazılmış, insanların ihtiyaç duyduğu her "
                  "helâl ve haramı içeren bir sayfa. Onu anlatan Şiî rivayetler.",
            "ar": "في الكافي (كتاب الحجة) يصف الإمام الجامعة: صحيفة طولها سبعون ذراعًا بذراع رسول الله ﷺ، من إملائه "
                  "وخط علي، فيها كل حلال وحرام يحتاج إليه الناس. وهذه أحاديث الكتب الشيعية التي تصفها.",
        },
        "how": {"en": "The hadith of the Shia books that name al-Jami'a with its length in cubits.",
                "tr": "Şiî kitaplarda el-Câmia'yı zirâ ölçüsüyle anan rivayetler.",
                "ar": "أحاديث الكتب الشيعية التي تذكر الجامعة مع طولها بالذراع."},
        "all": ["الجامعة", "ذراع"],
    },
    {
        "id": "fatima", "road": "shia", "layer": 2,
        "title": {"en": "Mushaf Fatima, as the Shia books relate it", "tr": "Mushaf-ı Fâtıma (Şiî kitapların anlattığı gibi)",
                  "ar": "مصحف فاطمة كما ترويه الكتب الشيعية"},
        "lead": {
            "en": "The Shia books relate that the Imams had a book called Mushaf Fatima, and say in the same "
                  "breath that it is not a Qur'an: \"not one letter of your Qur'an is in it\" (al-Kafi). Shown as "
                  "these books give it, in their own words.",
            "tr": "Şiî kitaplar imamların yanında Mushaf-ı Fâtıma adlı bir kitap bulunduğunu anlatır ve aynı yerde "
                  "onun bir Kur'an olmadığını söyler: \"İçinde sizin Kur'an'ınızdan tek harf yoktur\" (el-Kâfî). "
                  "Bu kitapların kendi sözleriyle, verdikleri gibi gösterilir.",
            "ar": "تروي الكتب الشيعية أن عند الأئمة كتابًا يسمّى مصحف فاطمة، وتقول في الموضع نفسه إنه ليس قرآنًا: "
                  "«ما فيه من قرآنكم حرف واحد» (الكافي). ويُعرض كما تعطيه هذه الكتب بألفاظها.",
        },
        "how": {"en": "The hadith of the Shia books that name \"Mushaf Fatima\".",
                "tr": "Şiî kitaplarda \"Mushaf-ı Fâtıma\"yı anan rivayetler.",
                "ar": "أحاديث الكتب الشيعية التي تذكر «مصحف فاطمة»."},
        "patterns": ["مصحف فاطمة"],
    },
    {
        "id": "chains-shia", "road": "shia", "layer": 3,
        "title": {"en": "Writing in the chains, and letters to the Imams", "tr": "Senedlerde yazı ve imamlara mektuplar",
                  "ar": "الكتابة في الأسانيد والمكاتبة مع الأئمة"},
        "lead": {
            "en": "In the Shia books many answers came in writing: \"I wrote to him (the Imam) asking …, and he "
                  "wrote …\" (mukataba), besides \"he wrote to me\" and \"I found in the book of …\" in the chains. "
                  "These are the hadith of the Shia books that say so.",
            "tr": "Şiî kitaplarda birçok cevap yazıyla geldi: \"Ona (imama) yazıp sordum …, o da yazdı …\" "
                  "(mükâtebe); senedlerde de \"bana yazdı\", \"…in kitabında buldum\". Bunlar Şiî kitaplarda "
                  "bunu söyleyen rivayetlerdir.",
            "ar": "كثير من الأجوبة في الكتب الشيعية جاء كتابةً: «كتبت إليه أسأله … فكتب …» (المكاتبة)، ومعها في "
                  "الأسانيد «كتب إليّ» و«وجدت في كتاب …». وهذه أحاديث الكتب الشيعية التي تذكر ذلك.",
        },
        "how": {"en": "The words of writing at the head of the text (the chain and its first lines).",
                "tr": "Metnin başındaki (sened ve ilk satırlar) yazı sözleri.",
                "ar": "ألفاظ الكتابة في صدر النص (الإسناد وأوله)."},
        "head": ["كتبت إليه", "كتبت إلى", "كتب إلي", "كتب إليه", "وجدت في كتاب", "قرأت في كتاب"],
    },
]


def _lang(lang: str | None) -> str:
    return lang or language()


def text(values: dict, lang: str | None = None) -> str:
    lang = _lang(lang)
    return values.get(lang) or values["en"]


def sources(road: str | None = None) -> list[dict]:
    return [s for s in SOURCES if road is None or s["road"] == road]


def find(source_id: str) -> dict | None:
    return next((s for s in SOURCES if s["id"] == source_id), None)


# ------------------------------------------------------------------ reading the books
_PROPHET = normalize("صلى الله عليه وسلم")
_FROM_MANY = normalize("فذكر أحاديث منها")
_GO_ON = (normalize("وقال"), normalize("وبإسناده"))


def _matn(n: str) -> str:
    """The words after the chain, as near as the text lets them be found (normalised text)."""
    k = n.find(_FROM_MANY)
    if k >= 0:
        n = n[k + len(_FROM_MANY):]
    k = n.find(_PROPHET)
    return n[k + len(_PROPHET):] if k >= 0 else n


def _words(n: str) -> set[str]:
    return {w for w in re.findall(r"[ء-ي]+", _matn(n)) if len(w) > 2}


def _arabic(conn: sqlite3.Connection, where: str = "", args: tuple = ()) -> list[tuple]:
    return conn.execute(
        f"""SELECT h.id, c.key, h.number, COALESCE(c.tradition, 'sunni'), t.text FROM texts t
            JOIN editions e ON e.id = t.edition_id JOIN hadiths h ON h.id = t.hadith_id
            JOIN collections c ON c.id = h.collection_id
            WHERE e.language = 'Arabic' {where} ORDER BY c.id, h.number_sort""", args).fetchall()


def _hammam(conn: sqlite3.Connection) -> dict:
    """The sahifa in the Musnad (its runs under Ma'mar ← Hammam) and each hadith's parallels elsewhere."""
    rows = _arabic(conn, "AND c.key = 'ahmad'")
    hm, mm = normalize("همام"), normalize("معمر")
    items: list[int] = []
    words: dict[int, set] = {}
    i = 0
    while i < len(rows):
        head = normalize(rows[i][4][:220])
        nxt = normalize(rows[i + 1][4][:40]) if i + 1 < len(rows) else ""
        if hm in head and mm in head and nxt.startswith(_GO_ON):
            j = i + 1
            while j < len(rows) and normalize(rows[j][4][:40]).startswith(_GO_ON):
                j += 1
            for r in rows[i:j]:
                items.append(r[0])
                words[r[0]] = _words(normalize(r[4]))
            i = j
        else:
            i += 1
    parallels: dict[str, list[int]] = {}
    person = conn.execute("SELECT id FROM persons WHERE name_ar LIKE ? ORDER BY id LIMIT 1",
                          (HAMMAM_NAME + "%",)).fetchone()
    if items and person:
        others = [r[0] for r in conn.execute(
            """SELECT DISTINCT i.hadith_id FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id
               JOIN hadiths h ON h.id = i.hadith_id JOIN collections c ON c.id = h.collection_id
               WHERE l.person_id = ? AND c.key != 'ahmad' AND COALESCE(c.tradition, 'sunni') = 'sunni'""",
            (person[0],))]
        if others:
            marks = ",".join("?" * len(others))
            for hid, _key, _num, _road, t in _arabic(conn, f"AND h.id IN ({marks})", tuple(others)):
                w = _words(normalize(t))
                best, at = 0.0, None
                for item in items:
                    s = words[item]
                    inter = len(w & s)
                    score = inter / max(1, min(len(w), len(s))) if inter >= 4 else 0.0
                    if score > best:
                        best, at = score, item
                if at is not None and best >= 0.6:
                    parallels.setdefault(str(at), []).append(hid)
    return {"items": items, "parallels": parallels}


def _counted(conn: sqlite3.Connection) -> dict:
    out: dict = {"hammam": _hammam(conn)}
    found: dict[str, list[int]] = {s["id"]: [] for s in SOURCES if s["id"] != "hammam"}
    plans = []
    for s in SOURCES:
        if s.get("patterns"):
            plans.append((s, "any", [normalize(p) for p in s["patterns"]]))
        elif s.get("all"):
            plans.append((s, "all", [normalize(p) for p in s["all"]]))
        elif s.get("head"):
            plans.append((s, "head", [normalize(p) for p in s["head"]]))
    for hid, _key, _num, road, t in _arabic(conn):
        n = normalize(t)
        for s, how, pats in plans:
            if s["road"] != road:
                continue
            hay = n[:400] if how == "head" else n
            if (all(p in hay for p in pats) if how == "all" else any(p in hay for p in pats)):
                found[s["id"]].append(hid)
    for s in SOURCES:
        if s.get("chain"):
            pats = [normalize(p) for p in s["chain"]]
            seen = []
            for hid, raw in conn.execute(
                    """SELECT i.hadith_id, i.raw_text FROM isnads i JOIN hadiths h ON h.id = i.hadith_id
                       JOIN collections c ON c.id = h.collection_id WHERE COALESCE(c.tradition, 'sunni') = ?
                       ORDER BY c.id, h.number_sort""", (s["road"],)):
                n = normalize(raw or "")
                if any(p in n for p in pats) and hid not in seen:
                    seen.append(hid)
            found[s["id"]] = seen
    out["found"] = found
    return out


def counted(conn: sqlite3.Connection) -> dict:
    """Everything this page shows, read once per change of the database (core.cache) — some ten seconds."""
    from isnady.core import cache

    return cache.kept(conn, "sahifa", _counted)


def hadith(conn: sqlite3.Connection, source_id: str) -> list[int]:
    """The hadith ids of a written source, in the order of the books."""
    data = counted(conn)
    if source_id == "hammam":
        return list(data["hammam"]["items"])
    return list(data["found"].get(source_id, []))


def parallels(conn: sqlite3.Connection, hadith_id: int) -> list[int]:
    """The hadith of the other books matched to one hadith of Hammam's sahifa."""
    return list(counted(conn)["hammam"]["parallels"].get(str(hadith_id), []))


def by_book(conn: sqlite3.Connection, ids: list[int]) -> list[tuple[str, str, int]]:
    """(book key, book name, how many) of these hadith, in the order of the books."""
    if not ids:
        return []
    out: dict[str, list] = {}
    for start in range(0, len(ids), 900):
        part = ids[start:start + 900]
        for key, name, n in conn.execute(
                f"""SELECT c.key, c.name, COUNT(*) FROM hadiths h JOIN collections c ON c.id = h.collection_id
                    WHERE h.id IN ({','.join('?' * len(part))}) GROUP BY c.id ORDER BY c.id""", part):
            out.setdefault(key, [key, name, 0])[2] += n
    return [tuple(v) for v in out.values()]


def refs(conn: sqlite3.Connection, ids: list[int]) -> list[tuple[int, str, str]]:
    """(hadith id, book key, number) of these hadith."""
    if not ids:
        return []
    out = {}
    for start in range(0, len(ids), 900):
        part = ids[start:start + 900]
        for hid, key, num in conn.execute(
                f"""SELECT h.id, c.key, h.number FROM hadiths h JOIN collections c ON c.id = h.collection_id
                    WHERE h.id IN ({','.join('?' * len(part))})""", part):
            out[hid] = (hid, key, num)
    return [out[i] for i in ids if i in out]


def summary(conn: sqlite3.Connection) -> list[dict]:
    """Every source with how many hadith the imported books hold of it: [{id, road, count, parallels}]."""
    data = counted(conn)
    rows = []
    for s in SOURCES:
        ids = hadith(conn, s["id"])
        row = {"id": s["id"], "road": s["road"], "count": len(ids)}
        if s["id"] == "hammam":
            row["with_parallels"] = len(data["hammam"]["parallels"])
            row["parallels"] = sum(len(v) for v in data["hammam"]["parallels"].values())
        rows.append(row)
    return rows
