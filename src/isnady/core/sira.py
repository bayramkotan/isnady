"""The life of the Prophet ﷺ as a timeline (SIY1): the events of the sira in order, each with its date as the sira
gives it (and where the reports differ, said so), its place, the verses revealed about it, the chapter of Ibn Hisham's
Sira that tells it (when imported, LIB1) and the hadith of the Sunni books that name it.

The events and their dates follow Ibn Ishaq as Ibn Hisham edited him, the sira most of the later ones build on; where
others give another date it is said beside it. The hadith are found by a phrase of their own wording (\"يوم بدر\")
in the imported books — the hadith that name the event, not a judgement of which tell it best. The texts are
written for isnady (CC BY 4.0, like the lives).
"""

from __future__ import annotations

import sqlite3

from isnady.core.i18n import language
from isnady.core.normalize import normalize

PERIODS = {
    "before": {"en": "Before the mission", "tr": "Peygamberlikten önce", "ar": "قبل البعثة"},
    "mecca": {"en": "Mecca: the mission", "tr": "Mekke dönemi", "ar": "العهد المكي"},
    "medina": {"en": "Medina: after the Hijra", "tr": "Medine dönemi", "ar": "العهد المدني"},
}


def _e(id_, period, year, ce, when, place, title, text, quran=(), sira="", phrase="", differ=None):
    """year: years after the Hijra (AH); before it, negative (−13: thirteen years before)."""
    return {"id": id_, "period": period, "year": year, "ce": ce, "when": when, "place": place, "title": title,
            "text": text, "quran": list(quran), "sira": sira, "phrase": phrase, "differ": differ}


EVENTS: list[dict] = [
    _e("elephant", "before", -53, "570/571",
       {"en": "The Year of the Elephant", "tr": "Fil Yılı", "ar": "عام الفيل"},
       {"en": "Mecca", "tr": "Mekke", "ar": "مكة"},
       {"en": "The Year of the Elephant", "tr": "Fil Vak'ası", "ar": "عام الفيل"},
       {"en": "Abraha, the Abyssinian ruler of Yemen, marched on Mecca with an elephant to destroy the Ka'ba, and "
              "his army was turned back. The Arabs dated the years from it; the Prophet ﷺ was born in that year.",
        "tr": "Habeşlilerin Yemen valisi Ebrehe, Kâbe'yi yıkmak için fille Mekke üzerine yürüdü ve ordusu geri "
              "çevrildi. Araplar yılları bu olaydan saydılar; Resûlullah ﷺ o yıl doğdu.",
        "ar": "سار أبرهة الحبشي صاحب اليمن بالفيل إلى مكة ليهدم الكعبة فرُدّ جيشه، وأرّخ العرب به، ووُلد النبي ﷺ في ذلك العام."},
       quran=[(105, 1, 5)], sira="أمر الفيل"),
    _e("birth", "before", -53, "570/571",
       {"en": "Rabi' al-Awwal, a Monday", "tr": "Rebîülevvel, bir pazartesi", "ar": "ربيع الأول، يوم الاثنين"},
       {"en": "Mecca", "tr": "Mekke", "ar": "مكة"},
       {"en": "The birth of the Prophet ﷺ", "tr": "Resûlullah'ın ﷺ doğumu", "ar": "مولد النبي ﷺ"},
       {"en": "Muhammad ﷺ was born in Mecca to Amina bt. Wahb; his father 'Abdullah had died before his birth. "
              "Asked about fasting on Monday, he said: \"That is the day I was born\" (Muslim).",
        "tr": "Muhammed ﷺ Mekke'de Âmine bt. Vehb'den doğdu; babası Abdullah onun doğumundan önce vefat etmişti. "
              "Pazartesi orucu sorulunca \"O, doğduğum gündür\" dedi (Müslim).",
        "ar": "وُلد محمد ﷺ بمكة من آمنة بنت وهب، وقد توفي أبوه عبد الله قبل مولده، وسئل عن صوم الاثنين فقال: «ذاك يوم ولدت فيه» (مسلم)."},
       sira="ولادة رسول الله", phrase="يوم ولدت فيه",
       differ={"en": "The day of the month: the 12th as Ibn Ishaq gives it; the 2nd, 8th and 10th are reported too.",
               "tr": "Ayın günü: İbn İshak'ın verdiği gibi 12'si; 2'si, 8'i ve 10'u da rivayet edilir.",
               "ar": "يوم الشهر: الثاني عشر كما عند ابن إسحاق، ورُوي الثاني والثامن والعاشر."}),
    _e("halima", "before", -52, "571–575",
       {"en": "His first years", "tr": "İlk yılları", "ar": "سنواته الأولى"},
       {"en": "The desert of Banu Sa'd", "tr": "Benî Sa'd çölü", "ar": "بادية بني سعد"},
       {"en": "With Halima among Banu Sa'd", "tr": "Benî Sa'd'da Halîme'nin yanında", "ar": "في بني سعد عند حليمة"},
       {"en": "He was nursed by Halima al-Sa'diyya in the desert of Banu Sa'd. There, as a child, his chest was "
              "opened and his heart washed (Muslim), and he was returned to his mother.",
        "tr": "Benî Sa'd çölünde Halîme es-Sa'diyye onu emzirdi. Orada çocukken göğsü yarılıp kalbi yıkandı "
              "(Müslim) ve annesine geri verildi.",
        "ar": "أرضعته حليمة السعدية في بادية بني سعد، وهناك شُقّ صدره وغُسل قلبه وهو صبي (مسلم)، ثم رُدّ إلى أمه."},
       sira="ولادة رسول الله", phrase="فشق عن قلبه"),
    _e("orphan", "before", -47, "576–578",
       {"en": "At six, and at eight", "tr": "Altı ve sekiz yaşında", "ar": "في السادسة والثامنة"},
       {"en": "al-Abwa' and Mecca", "tr": "Ebvâ ve Mekke", "ar": "الأبواء ومكة"},
       {"en": "His mother, then his grandfather, die", "tr": "Annesinin, sonra dedesinin vefatı", "ar": "وفاة أمه ثم جده"},
       {"en": "Amina died at al-Abwa' on the way back from Medina when he was six; his grandfather 'Abd al-Muttalib "
              "took him in and died two years later, and his uncle Abu Talib raised him.",
        "tr": "Âmine, o altı yaşındayken Medine dönüşünde Ebvâ'da vefat etti; dedesi Abdülmuttalib onu yanına aldı "
              "ve iki yıl sonra vefat etti; amcası Ebû Tâlib onu büyüttü.",
        "ar": "توفيت آمنة بالأبواء وهو ابن ست، فكفله جده عبد المطلب، ثم توفي بعد سنتين فكفله عمه أبو طالب."},
       sira="وفاة آمنة"),
    _e("bahira", "before", -41, "582",
       {"en": "At about twelve", "tr": "On iki yaşlarında", "ar": "في نحو الثانية عشرة"},
       {"en": "Busra, Syria", "tr": "Busrâ, Şam", "ar": "بصرى بالشام"},
       {"en": "The journey to Syria and Bahira", "tr": "Şam yolculuğu ve Bahîrâ", "ar": "الرحلة إلى الشام وبحيرى"},
       {"en": "He went with Abu Talib's caravan to Syria; at Busra the monk Bahira recognised in him the signs of "
              "a prophet and told Abu Talib to take him home.",
        "tr": "Ebû Tâlib'in kervanıyla Şam'a gitti; Busrâ'da rahip Bahîrâ onda peygamberlik alâmetlerini tanıdı ve "
              "Ebû Tâlib'e onu geri götürmesini söyledi.",
        "ar": "خرج مع أبي طالب في تجارة إلى الشام، فعرف فيه الراهب بحيرى ببصرى علامات النبوة وأمر عمه بردّه."},
       sira="قصة بحيرى",
       differ={"en": "al-Tirmidhi narrates the meeting with a monk; some critics doubted parts of its wording.",
               "tr": "Tirmizî bir rahiple karşılaşmayı rivayet eder; bazı münekkitler lafzının bir kısmında şüphe etti.",
               "ar": "روى الترمذي لقاءه بالراهب، وتكلم بعض النقاد في بعض ألفاظه."}),
    _e("fudul", "before", -33, "590",
       {"en": "At about twenty", "tr": "Yirmi yaşlarında", "ar": "في نحو العشرين"},
       {"en": "Mecca", "tr": "Mekke", "ar": "مكة"},
       {"en": "The pact of al-Fudul", "tr": "Hilfü'l-Fudûl", "ar": "حلف الفضول"},
       {"en": "The clans of Quraysh swore in the house of 'Abdullah b. Jud'an to stand with anyone wronged in "
              "Mecca until he had his right; he was present, and said he would answer such a call in Islam too.",
        "tr": "Kureyş kabileleri Abdullah b. Cüd'ân'ın evinde Mekke'de zulme uğrayan herkesin hakkını alana kadar "
              "yanında duracaklarına yemin ettiler; o da oradaydı ve İslâm'da da böyle bir çağrıya uyacağını söyledi.",
        "ar": "تحالفت بطون قريش في دار عبد الله بن جدعان على نصرة المظلوم بمكة حتى يؤخذ له حقه، وشهده ﷺ وقال إنه لو دُعي به في الإسلام لأجاب."},
       sira="حلف الفضول"),
    _e("khadija", "before", -28, "595",
       {"en": "At twenty-five", "tr": "Yirmi beş yaşında", "ar": "في الخامسة والعشرين"},
       {"en": "Mecca", "tr": "Mekke", "ar": "مكة"},
       {"en": "Marriage to Khadija", "tr": "Hz. Hatice ile evlilik", "ar": "زواجه بخديجة"},
       {"en": "He traded for Khadija bt. Khuwaylid in Syria, and she, having seen his honesty, asked to marry him. "
              "All his children but Ibrahim were hers; he married no other while she lived.",
        "tr": "Hz. Hatice bt. Huveylid adına Şam'da ticaret yaptı; onun dürüstlüğünü gören Hatice evlenmek istedi. "
              "İbrahim dışında bütün çocukları ondandır; o hayattayken başka biriyle evlenmedi.",
        "ar": "اتّجر لخديجة بنت خويلد في الشام، فرأت أمانته فخطبته. وولده كلهم منها إلا إبراهيم، ولم يتزوج عليها حتى ماتت."},
       sira="تزويج رسول الله صلى الله عليه وسلم خديجة",
       differ={"en": "Her age: forty in the best-known report (Ibn Sa'd); others make her younger, twenty-eight in one.",
               "tr": "Yaşı: en meşhur rivayette (İbn Sa'd) kırk; başkaları daha genç der, birinde yirmi sekiz.",
               "ar": "سنّها: أربعون في أشهر الروايات (ابن سعد)، وقيل أصغر، وفي رواية ثمان وعشرون."}),
    _e("kaaba", "before", -18, "605",
       {"en": "At thirty-five", "tr": "Otuz beş yaşında", "ar": "في الخامسة والثلاثين"},
       {"en": "Mecca", "tr": "Mekke", "ar": "مكة"},
       {"en": "The rebuilding of the Ka'ba", "tr": "Kâbe'nin yeniden yapılması", "ar": "بناء الكعبة"},
       {"en": "Quraysh rebuilt the Ka'ba and quarrelled over who would set the Black Stone; they agreed on the first "
              "to come in, and it was he: he laid it on a cloak, each clan lifted a corner, and he set it in place.",
        "tr": "Kureyş Kâbe'yi yeniden yaptı ve Hacerülesved'i kimin koyacağında anlaşamadı; ilk gelene razı oldular, "
              "o da Resûlullah ﷺ idi: taşı bir örtüye koydu, her kabile bir ucundan tuttu ve onu yerine o koydu.",
        "ar": "بنت قريش الكعبة واختلفوا فيمن يضع الحجر، فرضوا بأول داخل فكان هو ﷺ، فوضعه في ثوب ورفعته القبائل ثم وضعه بيده."},
       sira="بنيان الكعبة", phrase="لما بنيت الكعبة"),
    _e("revelation", "mecca", -13, "610",
       {"en": "Ramadan, at forty", "tr": "Ramazan, kırk yaşında", "ar": "رمضان، في الأربعين"},
       {"en": "The cave of Hira", "tr": "Hira mağarası", "ar": "غار حراء"},
       {"en": "The first revelation", "tr": "İlk vahiy", "ar": "بدء الوحي"},
       {"en": "In the cave of Hira the angel came to him: \"Read, in the name of your Lord who created\". He went "
              "home trembling to Khadija, who comforted him and took him to Waraqa b. Nawfal ('A'isha, in "
              "al-Bukhari).",
        "tr": "Hira mağarasında melek geldi: \"Yaratan Rabbinin adıyla oku\". Titreyerek Hatice'ye döndü; o, onu "
              "teselli edip Varaka b. Nevfel'e götürdü (Hz. Âişe'den, Buhârî).",
        "ar": "جاءه الملك في غار حراء: «اقرأ باسم ربك الذي خلق»، فرجع إلى خديجة يرجف فؤاده، فطمأنته وانطلقت به إلى ورقة بن نوفل (عائشة، البخاري)."},
       quran=[(96, 1, 5)], sira="مبعث النبي", phrase="غار حراء"),
    _e("call", "mecca", -10, "613",
       {"en": "After three years", "tr": "Üç yıl sonra", "ar": "بعد ثلاث سنين"},
       {"en": "Mecca, Mount Safa", "tr": "Mekke, Safâ tepesi", "ar": "مكة، جبل الصفا"},
       {"en": "The open call", "tr": "Açık davet", "ar": "الجهر بالدعوة"},
       {"en": "After calling in secret, he was told: \"Warn your nearest kin\" — he climbed al-Safa and called the "
              "clans of Quraysh (al-Bukhari, Muslim) — and \"Proclaim what you are commanded\".",
        "tr": "Gizli davetten sonra \"En yakın akrabanı uyar\" emri geldi; Safâ'ya çıkıp Kureyş kabilelerini çağırdı "
              "(Buhârî, Müslim) — ve \"Sana emredileni açıkça bildir\".",
        "ar": "بعد الدعوة سرًّا نزل «وأنذر عشيرتك الأقربين» فصعد الصفا ونادى بطون قريش (البخاري، مسلم)، و«فاصدع بما تؤمر»."},
       quran=[(26, 214, 214), (15, 94, 94)], sira="مباداة رسول الله", phrase="وأنذر عشيرتك الأقربين"),
    _e("abyssinia", "mecca", -8, "615",
       {"en": "Rajab, the fifth year of the mission", "tr": "Recep, peygamberliğin beşinci yılı", "ar": "رجب، السنة الخامسة من البعثة"},
       {"en": "Abyssinia", "tr": "Habeşistan", "ar": "الحبشة"},
       {"en": "The emigration to Abyssinia", "tr": "Habeşistan'a hicret", "ar": "الهجرة إلى الحبشة"},
       {"en": "Under persecution, a group of Muslims left for Abyssinia, where the Negus gave them protection; "
              "Ja'far b. Abi Talib spoke for them when Quraysh asked for them back.",
        "tr": "Baskı altında bir grup Müslüman Habeşistan'a gitti; Necâşî onları korudu. Kureyş onları geri "
              "isteyince onlar adına Ca'fer b. Ebî Tâlib konuştu.",
        "ar": "خرج نفر من المسلمين فرارًا من الأذى إلى الحبشة فأجارهم النجاشي، وتكلم عنهم جعفر بن أبي طالب حين طلبتهم قريش."},
       sira="الهجرة الأولى إلى أرض الحبشة", phrase="النجاشي"),
    _e("umar", "mecca", -7, "616",
       {"en": "The sixth year of the mission", "tr": "Peygamberliğin altıncı yılı", "ar": "السنة السادسة من البعثة"},
       {"en": "Mecca", "tr": "Mekke", "ar": "مكة"},
       {"en": "Hamza and 'Umar become Muslims", "tr": "Hz. Hamza ve Hz. Ömer'in Müslüman oluşu", "ar": "إسلام حمزة وعمر"},
       {"en": "Hamza, then 'Umar b. al-Khattab, became Muslims; \"we have been strong since 'Umar became a Muslim\", "
              "said Ibn Mas'ud (al-Bukhari).",
        "tr": "Önce Hz. Hamza, sonra Hz. Ömer Müslüman oldu; İbn Mes'ûd \"Ömer Müslüman olduğundan beri güçlüyüz\" "
              "dedi (Buhârî).",
        "ar": "أسلم حمزة ثم عمر بن الخطاب، وقال ابن مسعود: «ما زلنا أعزة منذ أسلم عمر» (البخاري)."},
       sira="إسلام عمر بن الخطاب", phrase="منذ أسلم عمر"),
    _e("boycott", "mecca", -6, "616/617–619",
       {"en": "From the seventh year of the mission", "tr": "Peygamberliğin yedinci yılından", "ar": "من السنة السابعة من البعثة"},
       {"en": "The valley of Abu Talib", "tr": "Ebû Tâlib mahallesi (Şi'b)", "ar": "شعب أبي طالب"},
       {"en": "The boycott", "tr": "Boykot", "ar": "الحصار في الشعب"},
       {"en": "Quraysh wrote a pact not to marry, trade or deal with Banu Hashim and Banu al-Muttalib and hung it in "
              "the Ka'ba; the clan held out in the valley of Abu Talib until the pact was broken.",
        "tr": "Kureyş, Hâşimoğulları ve Muttaliboğulları ile evlenmemek, alışveriş yapmamak üzere bir ahitname yazıp "
              "Kâbe'ye astı; aile, ahitname bozulana kadar Ebû Tâlib mahallesinde direndi.",
        "ar": "كتبت قريش صحيفة ألا يناكحوا بني هاشم وبني المطلب ولا يبايعوهم وعلّقوها في الكعبة، فحُصروا في شعب أبي طالب حتى نُقضت الصحيفة."},
       sira="خبر الصحيفة", phrase="تقاسموا على الكفر",
       differ={"en": "How long: two or three years — the reports differ.",
               "tr": "Süresi: iki ya da üç yıl — rivayetler farklıdır.",
               "ar": "مدته سنتان أو ثلاث على اختلاف الروايات."}),
    _e("sorrow", "mecca", -3, "619",
       {"en": "The tenth year of the mission", "tr": "Peygamberliğin onuncu yılı", "ar": "السنة العاشرة من البعثة"},
       {"en": "Mecca", "tr": "Mekke", "ar": "مكة"},
       {"en": "The death of Abu Talib and Khadija", "tr": "Ebû Tâlib ve Hz. Hatice'nin vefatı", "ar": "وفاة أبي طالب وخديجة"},
       {"en": "Abu Talib, who had protected him, and Khadija died within a short time of each other; after them "
              "Quraysh dared to harm him as they had not before.",
        "tr": "Onu koruyan Ebû Tâlib ve Hz. Hatice kısa aralıkla vefat ettiler; onlardan sonra Kureyş daha önce "
              "cesaret edemediği eziyetlere giriştiler.",
        "ar": "توفي أبو طالب الذي كان يمنعه، وخديجة، في مدة قصيرة، ونالت قريش منه بعدهما ما لم تكن تناله."},
       sira="وفاة أبي طالب وخديجة", phrase="لما حضرت أبا طالب الوفاة"),
    _e("taif", "mecca", -3, "619",
       {"en": "The tenth year of the mission", "tr": "Peygamberliğin onuncu yılı", "ar": "السنة العاشرة من البعثة"},
       {"en": "al-Ta'if", "tr": "Tâif", "ar": "الطائف"},
       {"en": "The journey to al-Ta'if", "tr": "Tâif yolculuğu", "ar": "الخروج إلى الطائف"},
       {"en": "He went to Thaqif in al-Ta'if to ask for support and was driven out with stones. Asked by 'A'isha "
              "about his hardest day, he named the day he went to Ibn 'Abd Yalil (al-Bukhari, Muslim).",
        "tr": "Destek istemek için Tâif'te Sakîf'e gitti ve taşlarla kovuldu. Hz. Âişe en zor gününü sorunca İbn "
              "Abdiyâlîl'e gittiği günü söyledi (Buhârî, Müslim).",
        "ar": "خرج إلى ثقيف بالطائف يطلب النصرة فرُدّ ورُمي بالحجارة، وسألته عائشة عن أشد يوم لقيه فذكر يوم عرض نفسه على ابن عبد ياليل (البخاري، مسلم)."},
       sira="سعي الرسول إلى ثقيف", phrase="عبد ياليل"),
    _e("isra", "mecca", -1, "620/621",
       {"en": "Before the Hijra", "tr": "Hicretten önce", "ar": "قبل الهجرة"},
       {"en": "Mecca, Jerusalem, the heavens", "tr": "Mekke, Kudüs, gökler", "ar": "مكة، بيت المقدس، السماوات"},
       {"en": "The Night Journey and the Ascension", "tr": "İsrâ ve Mi'rac", "ar": "الإسراء والمعراج"},
       {"en": "He was taken by night from the Sacred Mosque to al-Aqsa and raised through the heavens; the five "
              "prayers were made obligatory that night (al-Bukhari, Muslim).",
        "tr": "Bir gece Mescid-i Harâm'dan Mescid-i Aksâ'ya götürüldü ve göklere yükseltildi; beş vakit namaz o "
              "gece farz kılındı (Buhârî, Müslim).",
        "ar": "أُسري به ليلًا من المسجد الحرام إلى المسجد الأقصى وعُرج به إلى السماوات، وفُرضت الصلوات الخمس تلك الليلة (البخاري، مسلم)."},
       quran=[(17, 1, 1), (53, 13, 18)], sira="الإسراء والمعراج", phrase="أسري بي",
       differ={"en": "When: about a year before the Hijra in most reports; others put it earlier — they differ.",
               "tr": "Ne zaman: rivayetlerin çoğunda hicretten bir yıl kadar önce; başkaları daha önceye koyar.",
               "ar": "وقته: قبل الهجرة بنحو سنة في أكثر الروايات، وقيل قبل ذلك."}),
    _e("aqaba", "mecca", -1, "621–622",
       {"en": "The pilgrimage seasons before the Hijra", "tr": "Hicretten önceki hac mevsimleri", "ar": "مواسم الحج قبل الهجرة"},
       {"en": "al-'Aqaba, Mina", "tr": "Akabe, Minâ", "ar": "العقبة بمنى"},
       {"en": "The pledges of al-'Aqaba", "tr": "Akabe biatleri", "ar": "بيعتا العقبة"},
       {"en": "Twelve men of Medina pledged to him at al-'Aqaba, and he sent Mus'ab b. 'Umayr with them; the next "
              "year seventy-three men and two women pledged to protect him as their own.",
        "tr": "Medineli on iki kişi Akabe'de ona biat etti; Mus'ab b. Umeyr'i onlarla gönderdi. Ertesi yıl yetmiş "
              "üç erkek ve iki kadın onu kendilerini korudukları gibi korumak üzere biat etti.",
        "ar": "بايعه اثنا عشر رجلًا من أهل المدينة في العقبة وبعث معهم مصعب بن عمير، وفي العام التالي بايعه ثلاثة وسبعون رجلًا وامرأتان على أن يمنعوه مما يمنعون منه أنفسهم."},
       sira="العقبة الأولى", phrase="ليلة العقبة"),
    _e("hijra", "medina", 1, "622",
       {"en": "Rabi' al-Awwal, 1 AH", "tr": "Rebîülevvel, h. 1", "ar": "ربيع الأول سنة ١ هـ"},
       {"en": "The cave of Thawr, Quba', Medina", "tr": "Sevr mağarası, Kubâ, Medine", "ar": "غار ثور، قباء، المدينة"},
       {"en": "The Hijra", "tr": "Hicret", "ar": "الهجرة"},
       {"en": "He left Mecca with Abu Bakr, hid three nights in the cave of Thawr — \"the second of two, when they "
              "were in the cave\" — reached Quba' and then Medina, where the years of Islam are counted from.",
        "tr": "Hz. Ebû Bekir ile Mekke'den çıktı, Sevr mağarasında üç gece saklandı — \"ikinin ikincisi olarak, "
              "ikisi mağaradayken\" — Kubâ'ya, sonra Medine'ye ulaştı; İslâm takvimi buradan başlar.",
        "ar": "خرج من مكة مع أبي بكر فاختفيا في غار ثور ثلاث ليال «ثاني اثنين إذ هما في الغار»، ثم نزل قباء ثم المدينة، ومنها يؤرَّخ."},
       quran=[(9, 40, 40)], sira="هجرة الرسول صلى الله عليه وسلم", phrase="ثاني اثنين"),
    _e("brotherhood", "medina", 1, "622/623",
       {"en": "1 AH", "tr": "h. 1", "ar": "سنة ١ هـ"},
       {"en": "Medina", "tr": "Medine", "ar": "المدينة"},
       {"en": "The mosque, and the brotherhood", "tr": "Mescid ve kardeşlik", "ar": "المسجد والمؤاخاة"},
       {"en": "He built his mosque in Medina and made each emigrant from Mecca a brother to one of the Ansar.",
        "tr": "Medine'de mescidini yaptı ve Mekke'den gelen her muhâciri Ensâr'dan birine kardeş yaptı.",
        "ar": "بنى مسجده بالمدينة وآخى بين المهاجرين والأنصار."},
       sira="المؤاخاة بين المهاجرين والأنصار", phrase="آخى رسول الله"),
    _e("qibla", "medina", 2, "624",
       {"en": "Rajab or Sha'ban, 2 AH", "tr": "Recep ya da Şâban, h. 2", "ar": "رجب أو شعبان سنة ٢ هـ"},
       {"en": "Medina", "tr": "Medine", "ar": "المدينة"},
       {"en": "The qibla turned to the Ka'ba", "tr": "Kıblenin Kâbe'ye çevrilmesi", "ar": "تحويل القبلة"},
       {"en": "After praying towards Jerusalem for sixteen or seventeen months in Medina, the Muslims were turned to "
              "the Ka'ba: \"Turn your face towards the Sacred Mosque\" (al-Bara', in al-Bukhari).",
        "tr": "Medine'de on altı ya da on yedi ay Kudüs'e doğru namaz kıldıktan sonra Kâbe'ye çevrildiler: "
              "\"Yüzünü Mescid-i Harâm tarafına çevir\" (Berâ'dan, Buhârî).",
        "ar": "صلّوا نحو بيت المقدس ستة عشر أو سبعة عشر شهرًا ثم حُوّلوا إلى الكعبة «فولّ وجهك شطر المسجد الحرام» (البراء، البخاري)."},
       quran=[(2, 144, 144)], sira="صرف القبلة إلى الكعبة", phrase="ستة عشر شهرا"),
    _e("badr", "medina", 2, "624",
       {"en": "17 Ramadan, 2 AH", "tr": "17 Ramazan, h. 2", "ar": "١٧ رمضان سنة ٢ هـ"},
       {"en": "Badr", "tr": "Bedir", "ar": "بدر"},
       {"en": "The battle of Badr", "tr": "Bedir Savaşı", "ar": "غزوة بدر"},
       {"en": "Some three hundred and thirteen Muslims met an army of Quraysh three times their number at Badr and "
              "won; Abu Jahl was killed. Surat al-Anfal was revealed about it.",
        "tr": "Üç yüz on üç kadar Müslüman, Bedir'de kendilerinin üç katı Kureyş ordusuyla karşılaştı ve kazandı; "
              "Ebû Cehil öldürüldü. Enfâl sûresi bu savaş hakkında indi.",
        "ar": "لقي نحو ثلاثمئة وثلاثة عشر من المسلمين جيش قريش ببدر وهو ثلاثة أضعافهم فنُصروا، وقُتل أبو جهل، ونزلت فيها سورة الأنفال."},
       quran=[(8, 9, 12), (3, 123, 123)], sira="غزوة بدر الكبرى", phrase="يوم بدر"),
    _e("uhud", "medina", 3, "625",
       {"en": "Shawwal, 3 AH", "tr": "Şevval, h. 3", "ar": "شوال سنة ٣ هـ"},
       {"en": "Mount Uhud", "tr": "Uhud dağı", "ar": "جبل أحد"},
       {"en": "The battle of Uhud", "tr": "Uhud Savaşı", "ar": "غزوة أحد"},
       {"en": "Quraysh came to avenge Badr. The archers left the hill against his order, the battle turned, Hamza "
              "was killed and the Prophet ﷺ was wounded. Al 'Imran tells of it.",
        "tr": "Kureyş Bedir'in intikamını almaya geldi. Okçular emre rağmen tepeyi bıraktı, savaş döndü; Hz. Hamza "
              "şehit edildi ve Resûlullah ﷺ yaralandı. Âl-i İmrân bunu anlatır.",
        "ar": "جاءت قريش تثأر لبدر، فترك الرماة الجبل خلافًا لأمره فدارت الدائرة، واستُشهد حمزة وشُجّ النبي ﷺ، وفيها نزل من آل عمران."},
       quran=[(3, 121, 122), (3, 152, 155)], sira="غزوة أحد", phrase="يوم أحد",
       differ={"en": "The day: the 15th of Shawwal as Ibn Ishaq gives it; the 7th is reported too.",
               "tr": "Günü: İbn İshak'a göre Şevval'in 15'i; 7'si de rivayet edilir.",
               "ar": "يومها: النصف من شوال عند ابن إسحاق، وقيل السابع."}),
    _e("bir-mauna", "medina", 4, "625",
       {"en": "Safar, 4 AH", "tr": "Safer, h. 4", "ar": "صفر سنة ٤ هـ"},
       {"en": "Bi'r Ma'una", "tr": "Bi'r-i Maûne", "ar": "بئر معونة"},
       {"en": "al-Raji' and Bi'r Ma'una", "tr": "Recî' ve Bi'r-i Maûne", "ar": "الرجيع وبئر معونة"},
       {"en": "Companions sent to teach the tribes were betrayed and killed — some seventy reciters at Bi'r Ma'una; "
              "he prayed against their killers for a month in the dawn prayer (al-Bukhari).",
        "tr": "Kabilelere öğretmek için gönderilen sahâbîler ihanete uğrayıp öldürüldü — Bi'r-i Maûne'de yetmiş "
              "kadar kurrâ; Resûlullah ﷺ bir ay sabah namazında onları öldürenlere beddua etti (Buhârî).",
        "ar": "غُدر بالصحابة الذين بُعثوا لتعليم القبائل فقُتلوا، ومنهم نحو سبعين من القراء ببئر معونة، فقنت شهرًا يدعو على قاتليهم (البخاري)."},
       sira="بئر معونة", phrase="بئر معونة"),
    _e("nadir", "medina", 4, "625",
       {"en": "Rabi' al-Awwal, 4 AH", "tr": "Rebîülevvel, h. 4", "ar": "ربيع الأول سنة ٤ هـ"},
       {"en": "Medina", "tr": "Medine", "ar": "المدينة"},
       {"en": "The Banu al-Nadir leave Medina", "tr": "Nadîroğullarının sürgünü", "ar": "إجلاء بني النضير"},
       {"en": "The Jewish tribe of Banu al-Nadir broke their pact and plotted against his life; after a siege they "
              "left Medina with what their camels could carry. Surat al-Hashr was revealed about it.",
        "tr": "Yahudi Nadîroğulları anlaşmayı bozup ona suikast tasarladı; kuşatmadan sonra develerinin "
              "taşıyabildiğiyle Medine'den çıktılar. Haşr sûresi bu konuda indi.",
        "ar": "نقض بنو النضير العهد وهمّوا بقتله، فحوصروا ثم خرجوا من المدينة بما حملت إبلهم، ونزلت فيهم سورة الحشر."},
       quran=[(59, 2, 2)], sira="إجلاء بني النضير", phrase="بني النضير"),
    _e("khandaq", "medina", 5, "627",
       {"en": "Shawwal, 5 AH", "tr": "Şevval, h. 5", "ar": "شوال سنة ٥ هـ"},
       {"en": "Medina", "tr": "Medine", "ar": "المدينة"},
       {"en": "The Trench (al-Ahzab)", "tr": "Hendek (Ahzâb) Savaşı", "ar": "غزوة الخندق (الأحزاب)"},
       {"en": "Quraysh and their allies besieged Medina with ten thousand men; the Muslims dug a trench, and after "
              "weeks a wind scattered the besiegers. Surat al-Ahzab tells of it.",
        "tr": "Kureyş ve müttefikleri on bin kişiyle Medine'yi kuşattı; Müslümanlar hendek kazdı, haftalar sonra "
              "bir rüzgâr kuşatanları dağıttı. Ahzâb sûresi bunu anlatır.",
        "ar": "حاصرت قريش وأحزابها المدينة في عشرة آلاف، فحفر المسلمون الخندق، وبعد أسابيع فرّقتهم ريح، وفيها نزلت سورة الأحزاب."},
       quran=[(33, 9, 11)], sira="غزوة الخندق", phrase="يوم الخندق",
       differ={"en": "The year: 5 AH as Ibn Ishaq gives it; Musa b. 'Uqba puts it in 4 AH.",
               "tr": "Yılı: İbn İshak'a göre h. 5; Mûsâ b. Ukbe h. 4'e koyar.",
               "ar": "سنتها: الخامسة عند ابن إسحاق، وجعلها موسى بن عقبة في الرابعة."}),
    _e("qurayza", "medina", 5, "627",
       {"en": "Dhu al-Qa'da, 5 AH", "tr": "Zilkade, h. 5", "ar": "ذو القعدة سنة ٥ هـ"},
       {"en": "Medina", "tr": "Medine", "ar": "المدينة"},
       {"en": "The Banu Qurayza", "tr": "Kurayzaoğulları", "ar": "غزوة بني قريظة"},
       {"en": "The Banu Qurayza had sided with the besiegers during the Trench; they were besieged and accepted the "
              "judgement of Sa'd b. Mu'adh.",
        "tr": "Kurayzaoğulları Hendek sırasında kuşatanların tarafına geçmişti; kuşatıldılar ve Sa'd b. Muâz'ın "
              "hükmüne razı oldular.",
        "ar": "مالأ بنو قريظة الأحزاب في الخندق، فحوصروا ونزلوا على حكم سعد بن معاذ."},
       quran=[(33, 26, 27)], sira="غزوة بني قريظة", phrase="بني قريظة"),
    _e("ifk", "medina", 6, "627/628",
       {"en": "Sha'ban, 6 AH", "tr": "Şâban, h. 6", "ar": "شعبان سنة ٦ هـ"},
       {"en": "al-Muraysi'", "tr": "Müreysî'", "ar": "المريسيع"},
       {"en": "Banu al-Mustaliq, and the slander", "tr": "Mustalikoğulları ve İfk hadisesi", "ar": "بنو المصطلق وحديث الإفك"},
       {"en": "On the way back from the Banu al-Mustaliq, 'A'isha was left behind and slandered; after a month the "
              "verses of al-Nur declared her innocent ('A'isha, in al-Bukhari).",
        "tr": "Mustalikoğulları dönüşünde Hz. Âişe geride kaldı ve iftiraya uğradı; bir ay sonra Nûr sûresinin "
              "âyetleri onun suçsuzluğunu bildirdi (Hz. Âişe'den, Buhârî).",
        "ar": "في الرجوع من بني المصطلق تخلّفت عائشة فرُميت بالإفك، ثم نزلت براءتها في سورة النور بعد شهر (عائشة، البخاري)."},
       quran=[(24, 11, 20)], sira="غزوة بني المصطلق", phrase="أهل الإفك",
       differ={"en": "The year: 6 AH as Ibn Ishaq gives it; others say 5 or 4.",
               "tr": "Yılı: İbn İshak'a göre h. 6; başkaları 5 ya da 4 der.",
               "ar": "سنتها: السادسة عند ابن إسحاق، وقيل الخامسة أو الرابعة."}),
    _e("hudaybiya", "medina", 6, "628",
       {"en": "Dhu al-Qa'da, 6 AH", "tr": "Zilkade, h. 6", "ar": "ذو القعدة سنة ٦ هـ"},
       {"en": "al-Hudaybiya", "tr": "Hudeybiye", "ar": "الحديبية"},
       {"en": "al-Hudaybiya", "tr": "Hudeybiye Antlaşması", "ar": "صلح الحديبية"},
       {"en": "He set out for the 'umra; stopped at al-Hudaybiya, the Companions pledged under the tree (Bay'at "
              "al-Ridwan), and a ten-year truce was made with Quraysh. Surat al-Fath called it a clear victory.",
        "tr": "Umre için yola çıktı; Hudeybiye'de durduruldu, sahâbîler ağacın altında biat etti (Rıdvan Biatı) "
              "ve Kureyş'le on yıllık barış yapıldı. Fetih sûresi buna apaçık bir fetih dedi.",
        "ar": "خرج معتمرًا فصُدّ بالحديبية، وبايع الصحابة تحت الشجرة (بيعة الرضوان)، وعُقد الصلح مع قريش عشر سنين، وسمّته سورة الفتح فتحًا مبينًا."},
       quran=[(48, 1, 1), (48, 18, 18)], sira="أمر الحديبية", phrase="الحديبية"),
    _e("kings", "medina", 7, "628",
       {"en": "After al-Hudaybiya", "tr": "Hudeybiye'den sonra", "ar": "بعد الحديبية"},
       {"en": "Medina", "tr": "Medine", "ar": "المدينة"},
       {"en": "The letters to the kings", "tr": "Hükümdarlara mektuplar", "ar": "الكتب إلى الملوك"},
       {"en": "He wrote to Heraclius, Khusraw, the Negus, al-Muqawqis and other rulers, calling them to Islam; "
              "Abu Sufyan tells how Heraclius read the letter (al-Bukhari).",
        "tr": "Herakleios'a, Kisrâ'ya, Necâşî'ye, Mukavkıs'a ve diğer hükümdarlara İslâm'a davet mektupları "
              "yazdı; Herakleios'un mektubu nasıl okuduğunu Ebû Süfyân anlatır (Buhârî).",
        "ar": "كتب إلى هرقل وكسرى والنجاشي والمقوقس وغيرهم يدعوهم إلى الإسلام، ويحكي أبو سفيان قراءة هرقل للكتاب (البخاري)."},
       sira="خروج رسول الله إلى الملوك", phrase="هرقل"),
    _e("khaybar", "medina", 7, "628",
       {"en": "Muharram, 7 AH", "tr": "Muharrem, h. 7", "ar": "المحرم سنة ٧ هـ"},
       {"en": "Khaybar", "tr": "Hayber", "ar": "خيبر"},
       {"en": "Khaybar", "tr": "Hayber'in fethi", "ar": "غزوة خيبر"},
       {"en": "The fortresses of Khaybar were taken; the flag was given to 'Ali (al-Bukhari, Muslim). Ja'far and "
              "the emigrants to Abyssinia returned at that time.",
        "tr": "Hayber kaleleri alındı; sancak Hz. Ali'ye verildi (Buhârî, Müslim). Ca'fer ve Habeşistan "
              "muhâcirleri o sırada döndü.",
        "ar": "فُتحت حصون خيبر وأُعطيت الراية عليًّا (البخاري، مسلم)، وقدم جعفر ومهاجرو الحبشة حينئذ."},
       sira="المسير إلى خيبر", phrase="يوم خيبر"),
    _e("qada", "medina", 7, "629",
       {"en": "Dhu al-Qa'da, 7 AH", "tr": "Zilkade, h. 7", "ar": "ذو القعدة سنة ٧ هـ"},
       {"en": "Mecca", "tr": "Mekke", "ar": "مكة"},
       {"en": "The 'umra of fulfilment", "tr": "Kaza umresi", "ar": "عمرة القضاء"},
       {"en": "As the truce allowed, he performed the 'umra with the Companions and stayed three days in Mecca.",
        "tr": "Antlaşmanın izin verdiği gibi sahâbîlerle umre yaptı ve Mekke'de üç gün kaldı.",
        "ar": "اعتمر مع الصحابة كما نصّ الصلح وأقام بمكة ثلاثًا."},
       quran=[(48, 27, 27)], sira="عمرة القضاء", phrase="عمرة القضاء"),
    _e("muta", "medina", 8, "629",
       {"en": "Jumada al-Ula, 8 AH", "tr": "Cemâziyelevvel, h. 8", "ar": "جمادى الأولى سنة ٨ هـ"},
       {"en": "Mu'ta", "tr": "Mûte", "ar": "مؤتة"},
       {"en": "Mu'ta", "tr": "Mûte Savaşı", "ar": "غزوة مؤتة"},
       {"en": "Three thousand Muslims met a Byzantine army; Zayd b. Haritha, Ja'far and 'Abdullah b. Rawaha fell "
              "one after another, and Khalid b. al-Walid brought the army back.",
        "tr": "Üç bin Müslüman bir Bizans ordusuyla karşılaştı; Zeyd b. Hârise, Ca'fer ve Abdullah b. Revâha "
              "birbiri ardınca şehit düştü; orduyu Hâlid b. Velîd geri getirdi.",
        "ar": "لقي ثلاثة آلاف من المسلمين جيش الروم، فاستُشهد زيد بن حارثة ثم جعفر ثم عبد الله بن رواحة، ورجع خالد بن الوليد بالجيش."},
       sira="غزوة مؤتة", phrase="غزوة مؤتة"),
    _e("fath", "medina", 8, "630",
       {"en": "Ramadan, 8 AH", "tr": "Ramazan, h. 8", "ar": "رمضان سنة ٨ هـ"},
       {"en": "Mecca", "tr": "Mekke", "ar": "مكة"},
       {"en": "The conquest of Mecca", "tr": "Mekke'nin fethi", "ar": "فتح مكة"},
       {"en": "Quraysh broke the truce; he marched with ten thousand and entered Mecca almost without fighting, "
              "cleared the idols from the Ka'ba — \"truth has come and falsehood has vanished\" — and forgave his "
              "people.",
        "tr": "Kureyş antlaşmayı bozdu; on bin kişiyle yürüdü ve Mekke'ye neredeyse savaşmadan girdi, Kâbe'yi "
              "putlardan temizledi — \"Hak geldi, bâtıl yok oldu\" — ve halkını affetti.",
        "ar": "نقضت قريش الصلح، فسار في عشرة آلاف ودخل مكة بلا قتال يُذكر، وطهّر الكعبة من الأصنام «جاء الحق وزهق الباطل»، وعفا عن قومه."},
       quran=[(17, 81, 81), (110, 1, 3)], sira="فتح مكة", phrase="عام الفتح"),
    _e("hunayn", "medina", 8, "630",
       {"en": "Shawwal, 8 AH", "tr": "Şevval, h. 8", "ar": "شوال سنة ٨ هـ"},
       {"en": "Hunayn, al-Ta'if", "tr": "Huneyn, Tâif", "ar": "حنين، الطائف"},
       {"en": "Hunayn and al-Ta'if", "tr": "Huneyn ve Tâif", "ar": "غزوة حنين والطائف"},
       {"en": "Hawazin gathered against the Muslims; at Hunayn the army first broke and then won, \"when your "
              "numbers pleased you\". Al-Ta'if was besieged and left.",
        "tr": "Hevâzin Müslümanlara karşı toplandı; Huneyn'de ordu önce dağıldı, sonra kazandı — \"çokluğunuz "
              "sizi böbürlendirmişti\". Tâif kuşatıldı ve bırakıldı.",
        "ar": "اجتمعت هوازن على المسلمين، فانهزموا أول الأمر بحنين ثم نُصروا «إذ أعجبتكم كثرتكم»، وحوصرت الطائف ثم رُفع عنها."},
       quran=[(9, 25, 26)], sira="غزوة حنين", phrase="يوم حنين"),
    _e("tabuk", "medina", 9, "630",
       {"en": "Rajab, 9 AH", "tr": "Recep, h. 9", "ar": "رجب سنة ٩ هـ"},
       {"en": "Tabuk", "tr": "Tebük", "ar": "تبوك"},
       {"en": "Tabuk", "tr": "Tebük Seferi", "ar": "غزوة تبوك"},
       {"en": "In the heat of summer he led thirty thousand towards the Byzantine frontier; no battle was fought. "
              "Three Companions who stayed behind were forgiven after fifty days (Ka'b b. Malik, in al-Bukhari).",
        "tr": "Yaz sıcağında otuz bin kişiyle Bizans sınırına yürüdü; savaş olmadı. Geri kalan üç sahâbî elli gün "
              "sonra affedildi (Ka'b b. Mâlik'ten, Buhârî).",
        "ar": "سار في حرّ الصيف بثلاثين ألفًا نحو حدود الروم ولم يكن قتال، وتيب على الثلاثة الذين خُلّفوا بعد خمسين ليلة (كعب بن مالك، البخاري)."},
       quran=[(9, 38, 38), (9, 117, 118)], sira="غزوة تبوك", phrase="غزوة تبوك"),
    _e("delegations", "medina", 9, "630/631",
       {"en": "9 AH", "tr": "h. 9", "ar": "سنة ٩ هـ"},
       {"en": "Medina, Mecca", "tr": "Medine, Mekke", "ar": "المدينة، مكة"},
       {"en": "The year of delegations", "tr": "Heyetler yılı", "ar": "عام الوفود"},
       {"en": "The tribes of Arabia sent delegations to Medina. Abu Bakr led the pilgrimage, and the opening of "
              "Bara'a was proclaimed: after that year no idolater would make the pilgrimage (al-Bukhari).",
        "tr": "Arap kabileleri Medine'ye heyetler gönderdi. Hz. Ebû Bekir hac emîri oldu ve Berâe'nin başı ilan "
              "edildi: o yıldan sonra hiçbir müşrik hac yapmayacaktı (Buhârî).",
        "ar": "وفدت القبائل على المدينة، وحجّ أبو بكر بالناس ونودي بأول براءة: «لا يحج بعد العام مشرك» (البخاري)."},
       quran=[(9, 1, 3)], sira="حج أبي بكر بالناس", phrase="لا يحج بعد العام مشرك"),
    _e("farewell", "medina", 10, "632",
       {"en": "Dhu al-Hijja, 10 AH", "tr": "Zilhicce, h. 10", "ar": "ذو الحجة سنة ١٠ هـ"},
       {"en": "Mecca, 'Arafa", "tr": "Mekke, Arafat", "ar": "مكة، عرفة"},
       {"en": "The Farewell Pilgrimage", "tr": "Vedâ Haccı", "ar": "حجة الوداع"},
       {"en": "His only pilgrimage after the Hijra; at 'Arafa he gave the sermon on the sanctity of life, property "
              "and honour, and \"Today I have perfected your religion for you\" was revealed.",
        "tr": "Hicretten sonraki tek haccı; Arafat'ta can, mal ve namusun dokunulmazlığı üzerine hutbe verdi ve "
              "\"Bugün dininizi sizin için kemale erdirdim\" âyeti indi.",
        "ar": "حجّته الوحيدة بعد الهجرة، خطب بعرفة في حرمة الدماء والأموال والأعراض، ونزل «اليوم أكملت لكم دينكم»."},
       quran=[(5, 3, 3)], sira="حجة الوداع", phrase="حجة الوداع"),
    _e("death", "medina", 11, "632",
       {"en": "Rabi' al-Awwal, 11 AH, a Monday", "tr": "Rebîülevvel, h. 11, bir pazartesi", "ar": "ربيع الأول سنة ١١ هـ، يوم الاثنين"},
       {"en": "Medina, in 'A'isha's room", "tr": "Medine, Hz. Âişe'nin odası", "ar": "المدينة، في حجرة عائشة"},
       {"en": "His death ﷺ", "tr": "Resûlullah'ın ﷺ vefatı", "ar": "وفاة النبي ﷺ"},
       {"en": "He fell ill, was nursed in 'A'isha's room and died at sixty-three. Abu Bakr told the people: "
              "\"Muhammad is but a messenger; messengers have passed away before him.\"",
        "tr": "Hastalandı, Hz. Âişe'nin odasında bakıldı ve altmış üç yaşında vefat etti. Hz. Ebû Bekir halka şu "
              "âyeti okudu: \"Muhammed ancak bir peygamberdir; ondan önce de peygamberler gelip geçti.\"",
        "ar": "مرض ومُرّض في بيت عائشة وتوفي ابن ثلاث وستين، فقرأ أبو بكر على الناس «وما محمد إلا رسول قد خلت من قبله الرسل»."},
       quran=[(3, 144, 144)], sira="ابتداء شكوى رسول الله", phrase="توفي رسول الله",
       differ={"en": "The day of the month: the 12th as Ibn Ishaq gives it; the 1st and 2nd are reported too.",
               "tr": "Ayın günü: İbn İshak'a göre 12'si; 1'i ve 2'si de rivayet edilir.",
               "ar": "يوم الشهر: الثاني عشر عند ابن إسحاق، وقيل الأول أو الثاني."}),
]

SIRA_WORK = "al_sira_al_nabawiyya_ibn_hisham"


def _lang(lang: str | None) -> str:
    return lang or language()


def text(values: dict | None, lang: str | None = None) -> str:
    if not values:
        return ""
    lang = _lang(lang)
    return values.get(lang) or values["en"]


def events(period: str | None = None) -> list[dict]:
    return [e for e in EVENTS if period is None or e["period"] == period]


def find(event_id: str) -> dict | None:
    return next((e for e in EVENTS if e["id"] == event_id), None)


def year_label(e: dict, lang: str | None = None) -> str:
    """"2 AH · 624 CE"; before the Hijra: "13 years before the Hijra · 610 CE"."""
    lang = _lang(lang)
    y = e["year"]
    if y > 0:
        ah = {"tr": f"h. {y}", "ar": f"{y} هـ"}.get(lang, f"{y} AH")
    else:
        ah = {"tr": f"hicretten {-y} yıl önce", "ar": f"قبل الهجرة بـ{-y} سنة"}.get(
            lang, "1 year before the Hijra" if y == -1 else f"{-y} years before the Hijra")
    ce = {"tr": f"m. {e['ce']}", "ar": f"{e['ce']} م"}.get(lang, f"{e['ce']} CE")
    return f"{ah} · {ce}"


def age(e: dict) -> int:
    """His age at the event, in lunar years, from the Year of the Elephant (53 years before the Hijra)."""
    return e["year"] + 53 - (0 if e["year"] <= 0 else 1)


def sira_chapter(conn: sqlite3.Connection, e: dict) -> int | None:
    """The chapter of Ibn Hisham's Sira that tells the event (when it is imported), by its heading."""
    if not e.get("sira") or conn is None:
        return None
    rows = conn.execute(
        """SELECT n.id, n.title FROM work_nodes n JOIN works w ON w.id = n.work_id
           WHERE w.key = ? AND n.kind IN ('kitab', 'bab') ORDER BY n.id""", (SIRA_WORK,)).fetchall()
    want = normalize(e["sira"])
    return next((nid for nid, title in rows if want in normalize(title or "")), None)


def _counted(conn: sqlite3.Connection) -> dict:
    phrases = {e["id"]: normalize(e["phrase"]) for e in EVENTS if e.get("phrase")}
    found: dict[str, int] = {k: 0 for k in phrases}
    for (t,) in conn.execute(
            """SELECT t.text FROM texts t JOIN editions e ON e.id = t.edition_id JOIN hadiths h ON h.id = t.hadith_id
               JOIN collections c ON c.id = h.collection_id
               WHERE e.language = 'Arabic' AND COALESCE(c.tradition, 'sunni') = 'sunni'"""):
        n = normalize(t)
        for k, p in phrases.items():
            if p in n:
                found[k] += 1
    return found


def hadith_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """How many hadith of the imported Sunni books hold each event's phrase — counted once per change (core.cache)."""
    from isnady.core import cache

    return cache.kept(conn, "sira-events", _counted)
