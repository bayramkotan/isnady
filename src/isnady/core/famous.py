"""The famous ones (FS1): the Companions everyone looks for — the four Caliphs, the Ten promised Paradise, the Mothers
of the Believers, the Prophet's household, those who narrated most — and, on road B, the Imami scholars' own famous
narrators (Ashab al-Ijma'). Each kept by his key in the rijal work (Ibn Hajar's Taqrib, al-Najashi), with the names
people type for him: Turkish, English and Arabic, with or without "Hz.", "bin" or "ibn", Hattab or Hattap.

Bayram (2026-10-20): "Ebubekir (Ebubekr)'in diğer isimlerini bilmeyen nasıl bulacak? … Ömer bin Hattab değil de
Omer ibn Hattap ya Umar bin Hattab da yazmış olabilirdim … 40-50 sahabeyi rahatlıkla bulmamız gerekmez mi. Yani bir
yerde listesi olması lazım, 4 halife ile beraber."

Qt-free: the Narrators and Genealogy pages, narrators.find and `iy narrator --famous` all read it. The two roads
are kept apart: a Sunni group holds Taqrib keys only, a Shia group al-Najashi's only (rule: never mixed).

The persons' rows are read from the database by key; the names here are only for finding them and for the list.
Khadija and Hamza (and Zaynab bt. Khuzayma) have no entry of their own in the Taqrib — they narrated nothing the six
books carry — so they are not in the list: a row that opens nothing would mislead.
"""

from __future__ import annotations

import re
import sqlite3

from isnady.core.i18n import N_

# (key, Turkish, English, Arabic, honour, other names people type)
# honour: "m" he, "f" she, "2" he and his father (Ibn 'Umar, Ibn 'Abbas …: رضي الله عنهما), "" none (road B)
_P = tuple[str, str, str, str, str, tuple[str, ...]]

ABU_BAKR: _P = ("taqrib:3467", "Ebû Bekir es-Sıddîk", "Abu Bakr al-Siddiq", "أبو بكر الصديق", "m",
                ("Ebubekir", "Ebubekr", "Ebu Bekir", "Ebû Bekr", "Abu Bakr", "Abubakar", "Abu Bakar", "Abubakr",
                 "Sıddîk", "Siddiq", "Abdullah b. Osman", "Abd Allah b. Uthman", "عبد الله بن عثمان", "الصديق"))
UMAR: _P = ("taqrib:4888", "Ömer b. el-Hattâb", "Umar b. al-Khattab", "عمر بن الخطاب", "m",
            ("Ömer", "Omar", "Umar", "Ömer bin Hattab", "Umar ibn al-Khattab", "Omar ibn al-Khattab", "Fârûk",
             "Faruk", "al-Faruq", "الفاروق"))
UTHMAN: _P = ("taqrib:4503", "Osman b. Affân", "Uthman b. Affan", "عثمان بن عفان", "m",
              ("Osman", "Uthman", "Othman", "Usman", "Osman bin Affan", "Uthman ibn Affan", "Zinnûreyn",
               "Zinnureyn", "Dhu al-Nurayn", "ذو النورين"))
ALI: _P = ("taqrib:4753", "Ali b. Ebî Tâlib", "Ali b. Abi Talib", "علي بن أبي طالب", "m",
           ("Ali", "Ali bin Ebi Talib", "Ali ibn Abi Talib", "Aliyy"))
TALHA: _P = ("taqrib:3027", "Talha b. Ubeydullah", "Talha b. Ubayd Allah", "طلحة بن عبيد الله", "m",
             ("Talha", "Talha bin Ubeydullah", "Talha ibn Ubaydullah"))
ZUBAYR: _P = ("taqrib:2003", "Zübeyr b. el-Avvâm", "al-Zubayr b. al-Awwam", "الزبير بن العوام", "m",
              ("Zübeyr", "Zubayr", "Zubair", "Zübeyr bin Avvam", "Zubayr ibn al-Awwam"))
IBN_AWF: _P = ("taqrib:3973", "Abdurrahman b. Avf", "Abd al-Rahman b. Awf", "عبد الرحمن بن عوف", "m",
               ("Abdurrahman bin Avf", "Abdurrahman ibn Awf", "Abd al-Rahman ibn Awf", "Abdur Rahman bin Auf"))
SAD: _P = ("taqrib:2259", "Sa'd b. Ebî Vakkâs", "Sa'd b. Abi Waqqas", "سعد بن أبي وقاص", "m",
           ("Sad bin Ebi Vakkas", "Saad ibn Abi Waqqas", "Sad ibn Abi Waqqas", "Sa'd b. Malik"))
SAID: _P = ("taqrib:2314", "Saîd b. Zeyd", "Sa'id b. Zayd", "سعيد بن زيد", "m",
            ("Said bin Zeyd", "Said ibn Zayd", "Saeed ibn Zaid"))
ABU_UBAYDA: _P = ("taqrib:3098", "Ebû Ubeyde b. el-Cerrâh", "Abu Ubayda b. al-Jarrah", "أبو عبيدة بن الجراح", "m",
                  ("Ebu Ubeyde", "Abu Ubayda", "Abu Ubaidah", "Ebu Ubeyde bin Cerrah", "Abu Ubayda ibn al-Jarrah",
                   "Âmir b. Abdullah b. el-Cerrâh", "عامر بن عبد الله بن الجراح"))
AISHA: _P = ("taqrib:8633", "Âişe", "A'isha", "عائشة", "f",
             ("Ayşe", "Aişe", "Aisha", "Ayesha", "Aysha", "Aishah", "Âişe bt. Ebî Bekr", "Aisha bint Abi Bakr",
              "عائشة بنت أبي بكر"))
HAFSA: _P = ("taqrib:8563", "Hafsa bt. Ömer", "Hafsa bt. Umar", "حفصة بنت عمر", "f",
             ("Hafsa", "Hafsah", "Hafsa bint Ömer", "Hafsa bint Umar"))
UMM_SALAMA: _P = ("taqrib:8694", "Ümmü Seleme", "Umm Salama", "أم سلمة", "f",
                  ("Ümmü Seleme", "Ummu Salama", "Umm Salamah", "Hind bt. Ebî Ümeyye", "Hind bint Abi Umayya",
                   "هند بنت أبي أمية"))
SAWDA: _P = ("taqrib:8612", "Sevde bt. Zem'a", "Sawda bt. Zam'a", "سودة بنت زمعة", "f",
             ("Sevde", "Sawda", "Sauda", "Sawdah"))
ZAYNAB: _P = ("taqrib:8594", "Zeyneb bt. Cahş", "Zaynab bt. Jahsh", "زينب بنت جحش", "f",
              ("Zeynep bint Cahş", "Zeyneb", "Zaynab bint Jahsh", "Zainab bint Jahsh"))
JUWAYRIYA: _P = ("taqrib:8554", "Cüveyriye bt. el-Hâris", "Juwayriya bt. al-Harith", "جويرية بنت الحارث", "f",
                 ("Cüveyriye", "Juwayriya", "Juwayriyah", "Juwairiya"))
UMM_HABIBA: _P = ("taqrib:8588", "Ümmü Habîbe", "Umm Habiba", "أم حبيبة", "f",
                  ("Ummu Habibe", "Umm Habibah", "Remle bt. Ebî Süfyân", "Ramla bint Abi Sufyan",
                   "رملة بنت أبي سفيان"))
SAFIYYA: _P = ("taqrib:8621", "Safiyye bt. Huyey", "Safiyya bt. Huyayy", "صفية بنت حيي", "f",
               ("Safiyye", "Safiyya", "Safiyyah", "Safiya"))
MAYMUNA: _P = ("taqrib:8688", "Meymûne bt. el-Hâris", "Maymuna bt. al-Harith", "ميمونة بنت الحارث", "f",
               ("Meymune", "Maymuna", "Maymunah", "Maimuna"))
FATIMA: _P = ("taqrib:8650", "Fâtıma ez-Zehrâ", "Fatima al-Zahra", "فاطمة الزهراء", "f",
              ("Fatma", "Fatıma", "Fatima", "Fatimah", "Fatima bint Muhammad", "فاطمة بنت رسول الله"))
HASAN: _P = ("taqrib:1260", "Hasan b. Ali", "al-Hasan b. Ali", "الحسن بن علي", "2",
             ("Hasan", "Hasan bin Ali", "Hasan ibn Ali", "Hassan ibn Ali"))
HUSAYN: _P = ("taqrib:1334", "Hüseyin b. Ali", "al-Husayn b. Ali", "الحسين بن علي", "2",
              ("Hüseyin", "Huseyin", "Husayn", "Hussein", "Husain", "Hüseyin bin Ali", "Husayn ibn Ali"))
ABBAS: _P = ("taqrib:3177", "Abbâs b. Abdülmuttalib", "al-Abbas b. Abd al-Muttalib", "العباس بن عبد المطلب", "m",
             ("Abbas", "Abbas bin Abdulmuttalib", "Abbas ibn Abd al-Muttalib"))
IBN_ABBAS: _P = ("taqrib:3409", "Abdullah b. Abbâs", "Abd Allah b. Abbas", "عبد الله بن عباس", "2",
                 ("İbn Abbas", "Ibn Abbas", "İbni Abbas", "Abdullah bin Abbas", "Abdullah ibn Abbas", "ابن عباس"))
JAFAR: _P = ("taqrib:943", "Ca'fer b. Ebî Tâlib", "Ja'far b. Abi Talib", "جعفر بن أبي طالب", "m",
             ("Cafer", "Ca'fer-i Tayyâr", "Cafer-i Tayyar", "Jafar", "Jafar ibn Abi Talib", "Jafar al-Tayyar"))
ABU_HURAYRA: _P = ("taqrib:8426", "Ebû Hüreyre", "Abu Hurayra", "أبو هريرة", "m",
                   ("Ebu Hureyre", "Ebuhureyre", "Abu Hurairah", "Abu Huraira", "Abu Hurayrah"))
IBN_UMAR: _P = ("taqrib:3490", "Abdullah b. Ömer", "Abd Allah b. Umar", "عبد الله بن عمر", "2",
                ("İbn Ömer", "Ibn Umar", "İbni Ömer", "Ibn Omar", "Abdullah bin Ömer", "Abdullah ibn Umar",
                 "ابن عمر"))
ANAS: _P = ("taqrib:565", "Enes b. Mâlik", "Anas b. Malik", "أنس بن مالك", "m",
            ("Enes", "Anas", "Enes bin Malik", "Anas ibn Malik"))
JABIR: _P = ("taqrib:871", "Câbir b. Abdullah", "Jabir b. Abd Allah", "جابر بن عبد الله", "2",
             ("Cabir", "Jabir", "Cabir bin Abdullah", "Jabir ibn Abdullah"))
ABU_SAID: _P = ("taqrib:2253", "Ebû Saîd el-Hudrî", "Abu Sa'id al-Khudri", "أبو سعيد الخدري", "m",
                ("Ebu Said", "Ebu Said Hudri", "Abu Said", "Abu Saeed", "Abu Said al-Khudri", "Hudri", "Khudri",
                 "Sa'd b. Mâlik b. Sinân", "سعد بن مالك بن سنان"))
IBN_MASUD: _P = ("taqrib:3613", "Abdullah b. Mes'ûd", "Abd Allah b. Mas'ud", "عبد الله بن مسعود", "m",
                 ("İbn Mesud", "Ibn Masud", "İbni Mesud", "Abdullah bin Mesud", "Abdullah ibn Masud", "ابن مسعود"))
IBN_AMR: _P = ("taqrib:3499", "Abdullah b. Amr b. el-Âs", "Abd Allah b. Amr b. al-As", "عبد الله بن عمرو بن العاص",
               "2", ("Abdullah bin Amr", "Abdullah ibn Amr", "İbn Amr", "Ibn Amr"))
MUADH: _P = ("taqrib:6725", "Muâz b. Cebel", "Mu'adh b. Jabal", "معاذ بن جبل", "m",
             ("Muaz", "Muadh", "Muaz bin Cebel", "Muadh ibn Jabal", "Muaz ibn Jabal"))
ABU_DHARR: _P = ("taqrib:8087", "Ebû Zer el-Gıfârî", "Abu Dharr al-Ghifari", "أبو ذر الغفاري", "m",
                 ("Ebu Zer", "Ebuzer", "Abu Dhar", "Abu Dharr", "Abu Zar", "Gifari", "Ghifari", "Cündüb b. Cünâde",
                  "Jundub b. Junada", "جندب بن جنادة"))
SALMAN: _P = ("taqrib:2477", "Selmân-ı Fârisî", "Salman al-Farisi", "سلمان الفارسي", "m",
              ("Selman", "Selman-ı Farisi", "Selmani Farisi", "Salman", "Salman the Persian", "Salman al-Farsi"))
BILAL: _P = ("taqrib:779", "Bilâl b. Rebâh", "Bilal b. Rabah", "بلال بن رباح", "m",
             ("Bilal", "Bilal-i Habeşi", "Bilal-i Habeşî", "Bilal bin Rebah", "Bilal ibn Rabah"))
AMMAR: _P = ("taqrib:4836", "Ammâr b. Yâsir", "Ammar b. Yasir", "عمار بن ياسر", "m",
             ("Ammar", "Ammar bin Yasir", "Ammar ibn Yasir"))
ABU_MUSA: _P = ("taqrib:3542", "Ebû Mûsâ el-Eş'arî", "Abu Musa al-Ash'ari", "أبو موسى الأشعري", "m",
                ("Ebu Musa", "Abu Musa", "Eşari", "Ashari", "Abdullah b. Kays", "Abd Allah b. Qays",
                 "عبد الله بن قيس"))
ZAYD_THABIT: _P = ("taqrib:2120", "Zeyd b. Sâbit", "Zayd b. Thabit", "زيد بن ثابت", "m",
                   ("Zeyd bin Sabit", "Zayd ibn Thabit", "Zaid bin Thabit"))
UBAYY: _P = ("taqrib:283", "Übey b. Ka'b", "Ubayy b. Ka'b", "أبي بن كعب", "m",
             ("Übey", "Ubeyy", "Ubayy", "Ubay", "Übey bin Kab", "Ubayy ibn Kab", "Ubay ibn Kaab"))
KHALID: _P = ("taqrib:1684", "Hâlid b. el-Velîd", "Khalid b. al-Walid", "خالد بن الوليد", "m",
              ("Halid bin Velid", "Halid", "Khalid", "Khalid ibn al-Walid", "Seyfullah", "Sayf Allah"))
MUAWIYA: _P = ("taqrib:6758", "Muâviye b. Ebî Süfyân", "Mu'awiya b. Abi Sufyan", "معاوية بن أبي سفيان", "2",
               ("Muaviye", "Muawiya", "Muawiyah", "Muaviye bin Ebi Sufyan", "Muawiya ibn Abi Sufyan"))
AMR_AS: _P = ("taqrib:5053", "Amr b. el-Âs", "Amr b. al-As", "عمرو بن العاص", "m",
              ("Amr bin As", "Amr ibn al-As", "Amr ibn al-Aas"))
ABU_DARDA: _P = ("taqrib:5228", "Ebü'd-Derdâ", "Abu al-Darda'", "أبو الدرداء", "m",
                 ("Ebu Derda", "Ebüdderda", "Ebu'd-Derda", "Abu Darda", "Abu al-Darda", "Abud Darda",
                  "Uveymir", "Uwaymir", "عويمر بن زيد"))
BARA: _P = ("taqrib:648", "Berâ b. Âzib", "al-Bara' b. Azib", "البراء بن عازب", "m",
            ("Bera", "Bara", "Bera bin Azib", "Bara ibn Azib"))
HUDHAYFA: _P = ("taqrib:1156", "Huzeyfe b. el-Yemân", "Hudhayfa b. al-Yaman", "حذيفة بن اليمان", "m",
                ("Huzeyfe", "Hudhayfa", "Hudhaifa", "Huzeyfe bin Yeman", "Hudhayfa ibn al-Yaman"))
UBADA: _P = ("taqrib:3157", "Ubâde b. es-Sâmit", "Ubada b. al-Samit", "عبادة بن الصامت", "m",
             ("Ubade", "Ubada", "Ubade bin Samit", "Ubada ibn al-Samit", "Ubadah ibn as-Samit"))
ABU_AYYUB: _P = ("taqrib:1633", "Ebû Eyyûb el-Ensârî", "Abu Ayyub al-Ansari", "أبو أيوب الأنصاري", "m",
                 ("Ebu Eyyub", "Eyyub Sultan", "Eyüp Sultan", "Abu Ayyub", "Hâlid b. Zeyd", "Khalid b. Zayd",
                  "خالد بن زيد"))
IBN_ZUBAYR: _P = ("taqrib:3319", "Abdullah b. ez-Zübeyr", "Abd Allah b. al-Zubayr", "عبد الله بن الزبير", "2",
                  ("İbn Zübeyr", "Ibn Zubayr", "Ibn al-Zubayr", "Abdullah bin Zübeyr", "Abdullah ibn al-Zubayr",
                   "ابن الزبير"))
USAMA: _P = ("taqrib:316", "Üsâme b. Zeyd", "Usama b. Zayd", "أسامة بن زيد", "2",
             ("Usame", "Üsame", "Usama", "Osama", "Usame bin Zeyd", "Usama ibn Zayd"))
ZAYD_HARITHA: _P = ("taqrib:2123", "Zeyd b. Hârise", "Zayd b. Haritha", "زيد بن حارثة", "m",
                    ("Zeyd bin Harise", "Zayd ibn Haritha", "Zaid bin Harithah"))
ABU_TALHA: _P = ("taqrib:2139", "Ebû Talha el-Ensârî", "Abu Talha al-Ansari", "أبو طلحة الأنصاري", "m",
                 ("Ebu Talha", "Abu Talha", "Abu Talhah", "Zeyd b. Sehl", "Zayd b. Sahl", "زيد بن سهل"))
MUGHIRA: _P = ("taqrib:6840", "Mugîre b. Şu'be", "al-Mughira b. Shu'ba", "المغيرة بن شعبة", "m",
               ("Mugire", "Mughira", "Mugire bin Şube", "Mughira ibn Shuba"))
ABU_UMAMA: _P = ("taqrib:2923", "Ebû Ümâme el-Bâhilî", "Abu Umama al-Bahili", "أبو أمامة الباهلي", "m",
                 ("Ebu Umame", "Ebu Ümame", "Abu Umama", "Abu Umamah", "Bahili", "Sudayy b. Ajlan", "صدي بن عجلان"))
SAHL: _P = ("taqrib:2658", "Sehl b. Sa'd es-Sâidî", "Sahl b. Sa'd al-Sa'idi", "سهل بن سعد الساعدي", "2",
            ("Sehl bin Sad", "Sahl ibn Sad", "Sahl ibn Saad"))
UQBA: _P = ("taqrib:4641", "Ukbe b. Âmir el-Cühenî", "Uqba b. Amir al-Juhani", "عقبة بن عامر الجهني", "m",
            ("Ukbe", "Uqba", "Ukbe bin Amir", "Uqba ibn Amir", "Uqbah ibn Amir"))
IMRAN: _P = ("taqrib:5150", "İmrân b. Husayn", "Imran b. Husayn", "عمران بن حصين", "m",
             ("İmran", "Imran", "Imran bin Husayn", "Imran ibn Husain", "Imran ibn Husayn"))
NUMAN: _P = ("taqrib:7152", "Nu'mân b. Beşîr", "al-Nu'man b. Bashir", "النعمان بن بشير", "2",
             ("Numan", "Nouman", "Numan bin Beşir", "Numan ibn Bashir", "Nu'man ibn Bashir"))
ABU_BAKRA: _P = ("taqrib:7180", "Ebû Bekre", "Abu Bakra", "أبو بكرة", "m",
                 ("Ebu Bekre", "Abu Bakrah", "Nüfey' b. el-Hâris", "Nufay' b. al-Harith", "نفيع بن الحارث"))
ASMA: _P = ("taqrib:8525", "Esmâ bt. Ebî Bekr", "Asma' bt. Abi Bakr", "أسماء بنت أبي بكر", "f",
            ("Esma", "Esma bint Ebi Bekir", "Asma", "Asma bint Abi Bakr", "Zâtü'n-Nitâkayn", "Dhat al-Nitaqayn"))
ABU_QATADA: _P = ("taqrib:8311", "Ebû Katâde el-Ensârî", "Abu Qatada al-Ansari", "أبو قتادة الأنصاري", "m",
                  ("Ebu Katade", "Abu Qatada", "Abu Qatadah"))
SALAMA: _P = ("taqrib:2503", "Seleme b. el-Ekva'", "Salama b. al-Akwa'", "سلمة بن الأكوع", "m",
              ("Seleme", "Salama", "Seleme bin Ekva", "Salama ibn al-Akwa", "Salamah ibn al-Akwa"))
IBN_ABI_AWFA: _P = ("taqrib:3219", "Abdullah b. Ebî Evfâ", "Abd Allah b. Abi Awfa", "عبد الله بن أبي أوفى", "2",
                    ("İbn Ebi Evfa", "Ibn Abi Awfa", "Abdullah bin Ebi Evfa", "Abdullah ibn Abi Awfa"))
ZAYD_ARQAM: _P = ("taqrib:2116", "Zeyd b. Erkam", "Zayd b. Arqam", "زيد بن أرقم", "m",
                  ("Zeyd bin Erkam", "Zayd ibn Arqam", "Zaid bin Arqam"))
ABU_MASUD: _P = ("taqrib:4647", "Ebû Mes'ûd el-Bedrî", "Abu Mas'ud al-Badri", "أبو مسعود البدري", "m",
                 ("Ebu Mesud", "Abu Masud", "Abu Masud al-Ansari", "Ukbe b. Amr", "Uqba b. Amr", "عقبة بن عمرو"))
IBN_UMM_MAKTUM: _P = ("taqrib:5031", "İbn Ümmü Mektûm", "Ibn Umm Maktum", "ابن أم مكتوم", "m",
                      ("İbni Ümmi Mektum", "Ibn Umm Maktoum", "Abdullah b. Ümmü Mektum", "Amr b. Ümmü Mektum"))
UMM_ATIYYA: _P = ("taqrib:8693", "Ümmü Atiyye", "Umm Atiyya", "أم عطية", "f",
                  ("Ummu Atiyye", "Umm Atiyyah", "Nüseybe bt. Ka'b", "Nusayba bint Ka'b", "نسيبة بنت كعب"))
WATHILA: _P = ("taqrib:7379", "Vâsile b. el-Eska'", "Wathila b. al-Asqa'", "واثلة بن الأسقع", "m",
               ("Vasile", "Wathila", "Vasile bin Eska", "Wathila ibn al-Asqa"))
SAD_UBADA: _P = ("taqrib:2243", "Sa'd b. Ubâde", "Sa'd b. Ubada", "سعد بن عبادة", "m",
                 ("Sad bin Ubade", "Saad ibn Ubadah", "Sad ibn Ubada"))

# road B: Ashab al-Ijma' — the narrators the Imami scholars agreed to accept what reaches them soundly (al-Kashshi);
# al-Najashi's keys. Ma'ruf b. Kharrabudh and al-Hasan b. Mahbub have no entry in al-Najashi.
_SHIA: list[_P] = [
    ("najashi:463", "Zürâre b. A'yen", "Zurara b. A'yan", "زرارة بن أعين", "", ("Zurare", "Zurara")),
    ("najashi:882", "Muhammed b. Müslim", "Muhammad b. Muslim", "محمد بن مسلم", "", ()),
    ("najashi:287", "Bureyd b. Muâviye el-İclî", "Burayd b. Mu'awiya al-Ijli", "بريد بن معاوية العجلي", "",
     ("Bureyd", "Burayd")),
    ("najashi:1187", "Ebû Basîr el-Esedî", "Abu Basir al-Asadi", "أبو بصير الأسدي", "", ("Ebu Basir", "Abu Basir")),
    ("najashi:846", "Fudayl b. Yesâr", "al-Fudayl b. Yasar", "الفضيل بن يسار", "", ("Fudayl", "Fudail")),
    ("najashi:328", "Cemîl b. Derrâc", "Jamil b. Darraj", "جميل بن دراج", "", ("Cemil", "Jamil")),
    ("najashi:559", "Abdullah b. Müskân", "Abd Allah b. Muskan", "عبد الله بن مسكان", "",
     ("İbn Müskan", "Ibn Muskan")),
    ("najashi:581", "Abdullah b. Bükeyr", "Abd Allah b. Bukayr", "عبد الله بن بكير", "",
     ("İbn Bükeyr", "Ibn Bukayr")),
    ("najashi:371", "Hammâd b. Osman", "Hammad b. Uthman", "حماد بن عثمان", "", ()),
    ("najashi:370", "Hammâd b. Îsâ", "Hammad b. Isa", "حماد بن عيسى", "", ()),
    ("najashi:8", "Ebân b. Osman el-Ahmer", "Aban b. Uthman al-Ahmar", "أبان بن عثمان الأحمر", "", ("Eban", "Aban")),
    ("najashi:1208", "Yûnus b. Abdurrahman", "Yunus b. Abd al-Rahman", "يونس بن عبد الرحمن", "", ()),
    ("najashi:524", "Safvân b. Yahyâ", "Safwan b. Yahya", "صفوان بن يحيى", "", ("Safvan", "Safwan")),
    ("najashi:887", "Muhammed b. Ebî Umeyr", "Muhammad b. Abi Umayr", "محمد بن أبي عمير", "",
     ("İbn Ebi Umeyr", "Ibn Abi Umayr")),
    ("najashi:561", "Abdullah b. el-Mugîre", "Abd Allah b. al-Mughira", "عبد الله بن المغيرة", "", ()),
    ("najashi:180", "Ahmed b. Muhammed b. Ebî Nasr el-Bezantî", "Ahmad b. Muhammad b. Abi Nasr al-Bazanti",
     "أحمد بن محمد بن أبي نصر البزنطي", "", ("Bezanti", "Bazanti", "al-Bazanti")),
]

CALIPHS = [ABU_BAKR, UMAR, UTHMAN, ALI]
GROUPS: list[dict] = [
    {"id": "caliphs", "title": N_("The four Caliphs"), "tradition": "sunni", "people": CALIPHS},
    {"id": "ten", "title": N_("The ten promised Paradise"), "tradition": "sunni",
     "people": CALIPHS + [TALHA, ZUBAYR, IBN_AWF, SAD, SAID, ABU_UBAYDA]},
    {"id": "mothers", "title": N_("The Mothers of the Believers"), "tradition": "sunni",
     "people": [AISHA, HAFSA, UMM_SALAMA, SAWDA, ZAYNAB, JUWAYRIYA, UMM_HABIBA, SAFIYYA, MAYMUNA]},
    {"id": "household", "title": N_("The Prophet's household"), "tradition": "sunni",
     "people": [ALI, FATIMA, HASAN, HUSAYN, ABBAS, IBN_ABBAS, JAFAR]},
    {"id": "most", "title": N_("Those who narrated most"), "tradition": "sunni",
     "people": [ABU_HURAYRA, IBN_UMAR, ANAS, AISHA, IBN_ABBAS, JABIR, ABU_SAID]},
    {"id": "other", "title": N_("Other famous Companions"), "tradition": "sunni",
     "people": [IBN_MASUD, IBN_AMR, MUADH, ABU_DHARR, SALMAN, BILAL, AMMAR, ABU_MUSA, ZAYD_THABIT, UBAYY, KHALID,
                MUAWIYA, AMR_AS, ABU_DARDA, BARA, HUDHAYFA, UBADA, ABU_AYYUB, IBN_ZUBAYR, USAMA, ZAYD_HARITHA,
                ABU_TALHA, MUGHIRA, ABU_UMAMA, SAHL, UQBA, IMRAN, NUMAN, ABU_BAKRA, ASMA, ABU_QATADA, SALAMA,
                IBN_ABI_AWFA, ZAYD_ARQAM, ABU_MASUD, IBN_UMM_MAKTUM, UMM_ATIYYA, WATHILA, SAD_UBADA]},
    {"id": "ijma", "title": N_("Ashab al-Ijma'"), "tradition": "shia", "people": _SHIA},
]


def _all() -> list[tuple[_P, str]]:
    """Every person once, with his tradition, in the order of the groups."""
    seen, out = set(), []
    for g in GROUPS:
        for p in g["people"]:
            if p[0] not in seen:
                seen.add(p[0])
                out.append((p, g["tradition"]))
    return out


# ------------------------------------------------------------------ the names people type
# "Hz.", "Hazreti", "(r.a.)", "radıyallahu anh", "aleyhisselâm", "سيدنا", "رضي الله عنه" … are no part of the name
_HONOUR_RE = re.compile(
    r"\((?:[^)]{0,20})\)|(?<!\w)(?:hz|hzt|hazreti|hazret|hazrat|hadrat|hadhrat|sayyiduna|sayyidina|seyyidina|"
    r"seyyidüna|radıyallahu|radiyallahu|radhiyallahu|radiallahu|anh|anha|anhâ|anhu|anhuma|anhüma|anhum|"
    r"aleyhisselam|aleyhisselâm|alayhissalam|imam|imâm|sahabi|sahâbî|ra|r\.a|a\.s)(?!\w)\.?",
    re.IGNORECASE)
_HONOUR_AR_RE = re.compile(r"رضي الله (?:تعالى |تعالي )?عن(?:ه|ها|هما|هم)|سيد(?:نا|تنا)|عليه السلام|عليها السلام")
_IBN = {"b", "bn", "ibn", "bin", "ben", "ibni", "ibnu", "ibnü", "bini", "bt", "bint", "binti", "bintu"}
_TOO_SHORT = {"abu", "ab", "um", "umm", "umu", "abd", "b", "ibn", "abdla", "abdlab",
              "ابو", "ابا", "ابي", "ام", "عبد", "بن", "عبدالله", "عبداللهبن"}      # "Ebu", "Ümmü", "Abdullah" alone


def _arabic(text: str) -> bool:
    return any("؀" <= ch <= "ۿ" for ch in text)


def _compact(text: str) -> str:
    """A name as one string of letters: Turkish, English and the hurried spellings of it alike. "Hz. Ömer bin
    Hattab", "Umar ibn al-Khattab" and "Omer ibn Hattap" are all "umarbhatab"; "Ebubekr" and "Abu Bakr" "abubakr"."""
    from isnady.core.narrators import fold_latin, split_abd
    from isnady.core.normalize import normalize

    if _arabic(text):
        text = _HONOUR_AR_RE.sub(" ", normalize(text))
        words = [w.removeprefix("ال") if len(w) > 4 else w for w in text.replace("ابن", "بن").split()]
        return "".join(words)
    text = _HONOUR_RE.sub(" ", split_abd(text))
    text = re.sub(r"(?i)\b(ibn|bin)-i\b", r"\1", text).replace("-", " ").replace("’", "'")
    words = []
    for word in text.split():
        bare = word.strip(".").replace("İ", "i").replace("I", "ı").lower().replace("ı", "i")
        if bare in _IBN:
            words.append("b")
            continue
        # the article, written apart once its hyphen is a space ("es-Sıddîk", "al-Khattab"), goes
        folded = fold_latin(word)
        if folded in ("al", "el", "es", "as", "ad", "ed", "an", "en", "ar", "er", "at", "et", "az", "ez", "ash", "ul",
                      "ud", "us", "ur", "un"):
            continue
        words.append(folded.replace(" ", ""))
    w = "".join(words)
    for a, b in (("kh", "h"), ("sh", "s"), ("th", "s"), ("dh", "z"), ("gh", "g"), ("p", "b"), ("ou", "u"),
                 ("aa", "a"), ("ee", "i"), ("oo", "u")):
        w = w.replace(a, b)
    w = re.sub(r"(.)\1+", r"\1", w)
    w = re.sub(r"abd[aiu]?lah?", "abdla", w)                # Abdullah, Abd Allah, Abdillah
    if len(w) > 3 and w.endswith("h"):
        w = w[:-1]                                        # Hurayrah, Abu Bakrah
    return w


def _skeleton(compact: str) -> str:
    """Its consonants: what is left when the vowels are spelt any way at all (Ayşe, Aişe, Aisha)."""
    return compact if _arabic(compact) else re.sub(r"[aeiouyw']", "", compact)


_KEYS: list[tuple[str, str, str, str]] | None = None      # (key, tradition, compact, skeleton)


def _keys() -> list[tuple[str, str, str, str]]:
    global _KEYS
    if _KEYS is None:
        out = []
        for p, tradition in _all():
            for name in (p[1], p[2], p[3], *p[5]):
                c = _compact(name)
                if c:
                    out.append((p[0], tradition, c, _skeleton(c)))
        _KEYS = out
    return _KEYS


def named(text: str, tradition: str | None = None) -> list[str]:
    """The keys of the famous ones the words typed name, the closest first: the name begins with them as typed
    (any spelling: "Ebubekir", "Abu Bakr", "Hz. Ali", "Omer ibn Hattap"), else its consonants do ("Aysha").
    Empty for a query too short to say ("Ebu", "Ümmü")."""
    wanted = _compact(text)
    if len(wanted) < 3 or wanted in _TOO_SHORT:
        return []
    keys = [k for k in _keys() if tradition is None or k[1] == tradition]

    def found(pairs: list[str]) -> list[str]:
        out: list[str] = []
        for key in pairs:
            if key not in out:
                out.append(key)
        return out

    whole = [k[0] for k in keys if k[2] == wanted]
    begins = [k[0] for k in keys if k[2].startswith(wanted)]
    if whole or begins:
        return found(whole + begins)
    # his father's name alone ("Hattab", "Affan", "Ebi Talib"): the son of it
    if len(wanted) >= 4:
        sons = [k[0] for k in keys if "b" + wanted in k[2]]
        if sons:
            return found(sons)
    if _arabic(wanted):
        return []
    # the consonants alone, and the same first letter: "Aysha" is Aisha, "Bukhari" is not Abu Hurayra
    skel = _skeleton(wanted)
    if not skel:
        return []
    return found([k[0] for k in keys if k[3] == skel and k[2][0] == wanted[0]])


def ids(conn: sqlite3.Connection, keys: list[str]) -> list[int]:
    """The persons' row ids for the keys, in the same order (a key the database lacks is left out)."""
    if not keys:
        return []
    marks = ",".join("?" * len(keys))
    found = dict(conn.execute(f"SELECT key, id FROM persons WHERE key IN ({marks})", keys).fetchall())
    return [found[k] for k in keys if k in found]


def honour(person: _P, language: str) -> str:
    """The words of respect after a Companion's name, in the language shown ("(r.a.)", "(RA)", رضي الله عنه)."""
    kind = person[4]
    if not kind:
        return ""
    if language == "ar":
        return {"m": "رضي الله عنه", "f": "رضي الله عنها", "2": "رضي الله عنهما"}[kind]
    return "(r.a.)" if language == "tr" else "(RA)"


def title(person: _P, language: str) -> str:
    """The name to show in the list: "Hz. Ebû Bekir es-Sıddîk (r.a.)", "Abu Bakr al-Siddiq (RA)", "أبو بكر الصديق
    رضي الله عنه". Road B's narrators by their name alone."""
    name = {"tr": person[1], "ar": person[3]}.get(language, person[2])
    extra = honour(person, language)
    if language == "tr" and person[4]:
        name = "Hz. " + name
    return f"{name} {extra}".strip()


def groups(tradition: str | None = None) -> list[dict]:
    """The groups of a tradition (both when None), Sunni first."""
    return [g for g in GROUPS if tradition is None or g["tradition"] == tradition]


def person(key: str) -> _P | None:
    return next((p for p, _t in _all() if p[0] == key), None)


def titles(conn: sqlite3.Connection, language: str) -> dict[int, str]:
    """Row id → the name to show, for every famous one in the database (the Abu Bakr whose entry begins with
    'Abd Allah b. 'Uthman is shown as Abu Bakr al-Siddiq)."""
    everyone = [p for p, _t in _all()]
    by_key = {p[0]: p for p in everyone}
    marks = ",".join("?" * len(by_key))
    return {pid: title(by_key[key], language)
            for key, pid in conn.execute(f"SELECT key, id FROM persons WHERE key IN ({marks})", list(by_key))}
