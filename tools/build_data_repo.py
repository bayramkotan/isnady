"""The repositories isnady reads its data from — defined here once, written as catalogs.

    python tools/build_data_repo.py --mirror ../isnady-data [--languages ara,eng,tur]
                                          build the isnady-data repository: every book, Sunni and Shia, converted to
                                          isnady's own format under our names (sunni/bukhari/, shia/kafi/,
                                          rijal/sunni/…), catalog.json and README.md; its catalog is also written as
                                          the copy shipped with isnady. Then commit and push that folder.
    python tools/build_data_repo.py --catalogs
                                          write the catalogs of the optional repositories shipped with isnady

isnady-data is isnady's own and default repository: everything is in it, in one format, under the names of the books
and their compilers; where a text was first published is said only in the credits. The optional repositories are
the datasets as their authors publish them, each with a catalog shipped inside isnady (they have none of their own).
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLED = ROOT / "src" / "isnady" / "data" / "repos"
SCHEMA = "isnady-catalog/1"
OWN = "https://github.com/bayramkotan/isnady-data"
OWN_CATALOG = "https://raw.githubusercontent.com/bayramkotan/isnady-data/main/catalog.json"
RAW = "https://raw.githubusercontent.com"
LANGUAGE_NAMES = {"ara": "Arabic", "tur": "Turkish", "eng": "English", "urd": "Urdu", "ind": "Indonesian",
                  "ben": "Bengali", "fra": "French", "rus": "Russian", "tam": "Tamil"}

# ------------------------------------------------------------------ fawazahmed0/hadith-api (Unlicense: tier A)
FAWAZ_INDEX = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions.json"
FAWAZ_RAW = f"{RAW}/fawazahmed0/hadith-api/1"
FAWAZ = {   # key: (title, Arabic title, languages offered, hadith)
    "bukhari": ("Sahih al-Bukhari", "صحيح البخاري", "ara tur eng urd ind ben fra rus tam", 7563),
    "muslim": ("Sahih Muslim", "صحيح مسلم", "ara tur eng urd ind ben fra rus tam", 7563),
    "abudawud": ("Sunan Abi Dawud", "سنن أبي داود", "ara tur eng urd ind ben fra rus", 5274),
    "tirmidhi": ("Jami' al-Tirmidhi", "جامع الترمذي", "ara tur eng urd ind ben", 3956),
    "nasai": ("Sunan al-Nasa'i", "سنن النسائي", "ara tur eng urd ind ben fra", 5758),
    "ibnmajah": ("Sunan Ibn Majah", "سنن ابن ماجه", "ara tur eng urd ind ben fra", 4341),
    "malik": ("Muwatta Malik", "موطأ مالك", "ara tur eng urd ind ben fra", 1858),
    "nawawi": ("Forty Hadith of al-Nawawi", "الأربعون النووية", "ara tur eng ben fra", 42),
    "qudsi": ("Forty Hadith Qudsi", "الأربعون القدسية", "ara eng fra", 40),
    "dehlawi": ("Forty Hadith of Shah Waliullah Dehlawi", "أربعون الدهلوي", "ara eng fra", 40),
}
FAWAZ_ORIGIN = {"name": "fawazahmed0/hadith-api", "url": "https://github.com/fawazahmed0/hadith-api"}

# ------------------------------------------------------------------ Open-Hadith-Data (ODbL: tier B)
OHD_URL = f"{RAW}/mhashim6/Open-Hadith-Data/master"
OHD_ORIGIN = {"name": "mhashim6/Open-Hadith-Data", "url": "https://github.com/mhashim6/Open-Hadith-Data"}
OHD = {     # key: (title, Arabic title, folder, file stem, file with commentary ("mufassala"))
    "bukhari": ("Sahih al-Bukhari", "صحيح البخاري", "Sahih_Al-Bukhari", "sahih_al-bukhari", True),
    "muslim": ("Sahih Muslim", "صحيح مسلم", "Sahih_Muslim", "sahih_muslim", True),
    "abudawud": ("Sunan Abi Dawud", "سنن أبي داود", "Sunan_Abu-Dawud", "sunan_abu-dawud", True),
    "tirmidhi": ("Jami' al-Tirmidhi", "جامع الترمذي", "Sunan_Al-Tirmidhi", "sunan_al-tirmidhi", True),
    "nasai": ("Sunan al-Nasa'i", "سنن النسائي", "Sunan_Al-Nasai", "sunan_al-nasai", True),
    "ibnmajah": ("Sunan Ibn Majah", "سنن ابن ماجه", "Sunan_Ibn-Maja", "sunan_ibn-maja", True),
    "malik": ("Muwatta Malik", "موطأ مالك", "Maliks_Muwataa", "maliks_muwataa", True),
    "ahmad": ("Musnad Ahmad ibn Hanbal", "مسند أحمد بن حنبل", "Musnad_Ahmad_Ibn-Hanbal", "musnad_ahmad_ibn-hanbal", False),
    "darimi": ("Sunan al-Darimi", "سنن الدارمي", "Sunan_Al-Darimi", "sunan_al-darimi", True),
}

# ------------------------------------------------------------------ AhmedBaset/hadith-json (no licence: tier C)
HJ_URL = f"{RAW}/AhmedBaset/hadith-json/v1.2.0/db/by_book"
HJ_ORIGIN = {"name": "AhmedBaset/hadith-json (from sunnah.com)", "url": "https://github.com/AhmedBaset/hadith-json"}
HJ = {      # key: (title, Arabic title, path)
    "bukhari": ("Sahih al-Bukhari", "صحيح البخاري", "the_9_books/bukhari"),
    "muslim": ("Sahih Muslim", "صحيح مسلم", "the_9_books/muslim"),
    "abudawud": ("Sunan Abi Dawud", "سنن أبي داود", "the_9_books/abudawud"),
    "tirmidhi": ("Jami' al-Tirmidhi", "جامع الترمذي", "the_9_books/tirmidhi"),
    "nasai": ("Sunan al-Nasa'i", "سنن النسائي", "the_9_books/nasai"),
    "ibnmajah": ("Sunan Ibn Majah", "سنن ابن ماجه", "the_9_books/ibnmajah"),
    "malik": ("Muwatta Malik", "موطأ مالك", "the_9_books/malik"),
    "ahmad": ("Musnad Ahmad", "مسند أحمد", "the_9_books/ahmed"),
    "darimi": ("Sunan al-Darimi", "سنن الدارمي", "the_9_books/darimi"),
    "riyad": ("Riyad al-Salihin", "رياض الصالحين", "other_books/riyad_assalihin"),
    "shamail": ("al-Shama'il al-Muhammadiyya", "الشمائل المحمدية", "other_books/shamail_muhammadiyah"),
    "bulugh": ("Bulugh al-Maram", "بلوغ المرام", "other_books/bulugh_almaram"),
    "adab": ("al-Adab al-Mufrad", "الأدب المفرد", "other_books/aladab_almufrad"),
    "mishkat": ("Mishkat al-Masabih", "مشكاة المصابيح", "other_books/mishkat_almasabih"),
    "nawawi": ("Forty Hadith of al-Nawawi", "الأربعون النووية", "forties/nawawi40"),
    "qudsi": ("Forty Hadith Qudsi", "الأربعون القدسية", "forties/qudsi40"),
    "dehlawi": ("Forty Hadith of Shah Waliullah", "أربعون الدهلوي", "forties/shahwaliullah40"),
}
HJ_MAPPING = {"type": "json", "records": "hadiths", "number": "idInBook", "section": "chapterId",
              "texts": [{"field": "arabic", "language": "Arabic"},
                        {"field": "english.text", "language": "English", "lead": "english.narrator"}]}

# ------------------------------------------------------------------ LK Hadith Corpus (no licence: tier C)
LK_URL = f"{RAW}/ShathaTm/LK-Hadith-Corpus/master"
LK_ORIGIN = {"name": "LK Hadith Corpus (Leeds University & King Saud University)",
             "url": "https://github.com/ShathaTm/LK-Hadith-Corpus"}
LK = {      # key: (title, Arabic title, folder, first chapter, last chapter)
    "bukhari": ("Sahih al-Bukhari", "صحيح البخاري", "Bukhari", 1, 97),
    "muslim": ("Sahih Muslim", "صحيح مسلم", "Muslim", 0, 56),
    "abudawud": ("Sunan Abi Dawud", "سنن أبي داود", "AbuDaud", 1, 43),
    "tirmidhi": ("Jami' al-Tirmidhi", "جامع الترمذي", "Tirmizi", 1, 49),
    "nasai": ("Sunan al-Nasa'i", "سنن النسائي", "Nesai", 1, 51),
    "ibnmajah": ("Sunan Ibn Majah", "سنن ابن ماجه", "IbnMaja", 0, 37),
}
LK_MAPPING = {"type": "csv", "header": True, "number": "Hadith_number", "section": "Chapter_Number",
              "section_titles": [{"field": "Chapter_Arabic", "language": "Arabic"},
                                 {"field": "Chapter_English", "language": "English"}],
              "texts": [{"field": "Arabic_Hadith", "language": "Arabic"},
                        {"field": "English_Hadith", "language": "English"}],
              "grades": [{"field": "English_Grade", "grader": "Grade in the LK corpus (sunnah.com)"}]}

# ------------------------------------------------------------------ abdelrahmaan/Hadith-Data-Sets (no licence: C)
HDS_URL = f"{RAW}/abdelrahmaan/Hadith-Data-Sets/master/All%20Hadith%20Books"
HDS_ORIGIN = {"name": "abdelrahmaan/Hadith-Data-Sets", "url": "https://github.com/abdelrahmaan/Hadith-Data-Sets"}
HDS = {
    "bukhari": ("Sahih al-Bukhari", "صحيح البخاري", "Sahih%20Bukhari.csv"),
    "muslim": ("Sahih Muslim", "صحيح مسلم", "Sahih%20Muslim.csv"),
    "abudawud": ("Sunan Abi Dawud", "سنن أبي داود", "Sunan%20Abu%20Dawud.csv"),
    "tirmidhi": ("Jami' al-Tirmidhi", "جامع الترمذي", "Sunan%20al%20Tirmidhi.csv"),
    "nasai": ("Sunan al-Nasa'i", "سنن النسائي", "Sunan%20al-Nasai.csv"),
    "ibnmajah": ("Sunan Ibn Majah", "سنن ابن ماجه", "Sunan%20Ibn%20Maja.csv"),
    "malik": ("Muwatta Malik", "موطأ مالك", "Maliks%20Muwatta.csv"),
    "ahmad": ("Musnad Ahmad ibn Hanbal", "مسند أحمد بن حنبل", "Musnad%20Ahmad%20ibn%20Hanbal.csv"),
    "darimi": ("Sunan al-Darimi", "سنن الدارمي", "Sunan%20al%20Darami.csv"),
}
HDS_MAPPING = {"type": "csv", "header": False, "skip_rows": 1, "number": "@row", "texts": [{"field": "#0", "language": "Arabic"}]}

# ------------------------------------------------------------------ Hugging Face meeAtif/hadith_datasets (MIT, declared)
HF_URL = "https://huggingface.co/datasets/meeAtif/hadith_datasets/resolve/main"
HF_ORIGIN = {"name": "meeAtif/hadith_datasets (Hugging Face; text from sunnah.com)",
             "url": "https://huggingface.co/datasets/meeAtif/hadith_datasets"}
HF = {
    "bukhari": ("Sahih al-Bukhari", "صحيح البخاري", "Sahih%20al-Bukhari.json"),
    "muslim": ("Sahih Muslim", "صحيح مسلم", "Sahih%20Muslim.json"),
    "abudawud": ("Sunan Abi Dawud", "سنن أبي داود", "Sunan%20Abi%20Dawud.json"),
    "tirmidhi": ("Jami' al-Tirmidhi", "جامع الترمذي", "Jami%60%20at-Tirmidhi.json"),
    "nasai": ("Sunan al-Nasa'i", "سنن النسائي", "Sunan%20an-Nasa%27i.json"),
    "ibnmajah": ("Sunan Ibn Majah", "سنن ابن ماجه", "Sunan%20Ibn%20Majah.json"),
}
HF_MAPPING = {"type": "json", "number": "Reference", "number_pattern": r"[:/](\d+[a-z]?)\s*$",
              "section": "Chapter_Number",
              "section_titles": [{"field": "Chapter_Title_Arabic", "language": "Arabic"},
                                 {"field": "Chapter_Title_English", "language": "English"}],
              "texts": [{"field": "Arabic_Text", "language": "Arabic"}, {"field": "English_Text", "language": "English"}],
              "grades": [{"field": "Grade", "grader": "Grade on sunnah.com (meeAtif dataset)"}],
              "url": "Reference"}

# ------------------------------------------------------------------ Thaqalayn (Shia; GPL code, text thaqalayn.net: C)
TQ_URL = f"{RAW}/MohammedArab1/ThaqalaynAPI/main/V1/ThaqalaynData"
TQ_ORIGIN = {"name": "Thaqalayn (thaqalayn.net, through MohammedArab1/ThaqalaynAPI)",
             "url": "https://github.com/MohammedArab1/ThaqalaynAPI"}
TQ = {      # key: (title, Arabic title, compiler, files (volumes in order))
    "kafi": ("al-Kafi — al-Kulayni", "الكافي", "al-Kulayni (d. 329)",
             [f"Al-Kafi-Volume-{v}-Kulayni" for v in range(1, 9)]),
    "uyun": ("'Uyun Akhbar al-Rida — al-Saduq", "عيون أخبار الرضا", "al-Saduq (d. 381)",
             ["Uyun-akhbar-al-Rida-Volume-1-Saduq", "Uyun-akhbar-al-Rida-Volume-2-Saduq"]),
    "amali-saduq": ("al-Amali — al-Saduq", "الأمالي (الصدوق)", "al-Saduq (d. 381)", ["Al-Amali-Saduq"]),
    "khisal": ("al-Khisal — al-Saduq", "الخصال", "al-Saduq (d. 381)", ["Al-Khisal-Saduq"]),
    "tawhid": ("al-Tawhid — al-Saduq", "التوحيد", "al-Saduq (d. 381)", ["Al-Tawhid-Saduq"]),
    "maani": ("Ma'ani al-Akhbar — al-Saduq", "معاني الأخبار", "al-Saduq (d. 381)", ["Maani-al-Akhbar-Saduq"]),
    "thawab": ("Thawab al-A'mal wa 'Iqab al-A'mal — al-Saduq", "ثواب الأعمال وعقاب الأعمال", "al-Saduq (d. 381)",
               ["Thawab-al-Amal-wa-iqab-al-Amal-Saduq"]),
    "sifat-shia": ("Sifat al-Shi'a — al-Saduq", "صفات الشيعة", "al-Saduq (d. 381)", ["Sifat-al-Shia-Saduq"]),
    "fadail-shia": ("Fada'il al-Shi'a — al-Saduq", "فضائل الشيعة", "al-Saduq (d. 381)", ["Fadail-al-Shia-Saduq"]),
    "amali-mufid": ("al-Amali — al-Mufid", "الأمالي (المفيد)", "al-Mufid (d. 413)", ["Al-Amali-Mufid"]),
    "kamil-ziyarat": ("Kamil al-Ziyarat — Ibn Qulawayh", "كامل الزيارات", "Ibn Qulawayh al-Qummi (d. 368)",
                      ["Kamil-al-Ziyarat-Qummi"]),
    "ghayba-numani": ("Kitab al-Ghayba — al-Nu'mani", "كتاب الغيبة (النعماني)", "al-Nu'mani (d. c. 360)",
                      ["Kitab-al-Ghayba-Numani"]),
    "ghayba-tusi": ("Kitab al-Ghayba — al-Tusi", "كتاب الغيبة (الطوسي)", "al-Tusi (d. 460)", ["Kitab-al-Ghayba-Tusi"]),
    "mumin": ("Kitab al-Mu'min — al-Ahwazi", "كتاب المؤمن", "al-Husayn b. Sa'id al-Ahwazi", ["Kitab-al-Mumin-Ahwazi"]),
    "zuhd": ("Kitab al-Zuhd — al-Ahwazi", "كتاب الزهد", "al-Husayn b. Sa'id al-Ahwazi", ["Kitab-al-Zuhd-Ahwazi"]),
    "mujam-mutabara": ("Mu'jam al-Ahadith al-Mu'tabara — al-Muhsini", "معجم الأحاديث المعتبرة", "Asif al-Muhsini",
                       ["Mujam-al-Ahadith-al-Mutabara-Muhsini"]),
}
TQ_GRADE = r":\s*([^\n]+)"
TQ_MAPPING = {"type": "json", "number": "id", "section": "categoryId",
              "section_titles": [{"field": "category", "language": "English"}],
              "texts": [{"field": "arabicText", "language": "Arabic"},
                        {"field": "englishText", "language": "English"}],
              "grades": [{"field": "majlisiGrading", "grader": "al-Majlisi (Mir'at al-'Uqul)", "pattern": TQ_GRADE,
                          "skip": ["لم يخرجه"]},
                         {"field": "behdudiGrading", "grader": "al-Behbudi (Sahih al-Kafi)", "pattern": TQ_GRADE,
                          "skip": ["لم يخرجه"]},
                         {"field": "mohseniGrading", "grader": "al-Muhsini (Mu'jam al-Ahadith al-Mu'tabara)",
                          "pattern": TQ_GRADE, "skip": ["لم يخرجه"]}],
              "url": "URL"}

# ------------------------------------------------------------------ OpenITI rijal (licence not stated there: C)
TAQRIB_URL = (f"{RAW}/OpenITI/0875AH/master/data/0852IbnHajarCasqalani/0852IbnHajarCasqalani.TaqribTahdhib/"
              "0852IbnHajarCasqalani.TaqribTahdhib.JK000121-ara1.completed")
NAJASHI_URL = f"{RAW}/OpenITI/0450AH/master/data/0450Najashi/0450Najashi.Rijal/0450Najashi.Rijal.Shia002931-ara1.mARkdown"
OPENITI_ORIGIN = {"name": "OpenITI corpus", "url": "https://github.com/OpenITI"}


# ================================================================== entries
def fawaz(key: str, location: str, fallback: bool) -> dict:
    title, ar, langs, n = FAWAZ[key]
    codes = langs.split()
    e = {"id": key, "aliases": [f"fawaz-{key}"], "title": title, "title_ar": ar, "kind": "hadith",
         "tradition": "sunni", "format": "fawazahmed0", "location": location, "book": key, "languages": codes,
         "license": "Unlicense", "source_name": "fawazahmed0/hadith-api", "source_key": "fawazahmed0-hadith-api",
         "origin": FAWAZ_ORIGIN, "hadith": n,
         "description": f"Arabic text and translations ({', '.join(LANGUAGE_NAMES[c] for c in codes)}); grades by "
                        "scholar where the source gives them (al-Albani, Shu'ayb al-Arna'ut, Zubair 'Ali Za'i …)."}
    if fallback:
        e["fallback"] = {"format": "fawazahmed0", "location": FAWAZ_INDEX}
    return e


def ohd_file(key: str) -> str:
    _t, _a, _folder, stem, sharh = OHD[key]
    return f"{stem}_ahadith_mushakkala{'_mufassala' if sharh else ''}.utf8.csv"


def ohd(key: str, location: str | None, suffix: str, fallback: bool) -> dict:
    title, ar, folder, stem, sharh = OHD[key]
    origin_file = f"{OHD_URL}/{folder}/{ohd_file(key)}"
    texts = [{"field": "#1", "language": "Arabic"}]
    if sharh:
        texts.append({"field": "#2", "language": "Arabic", "name": "Commentary", "comments": "Commentary (tafsil)"})
    e = {"id": f"{key}{suffix}", "title": title + (" — Open Hadith Data" if suffix else ""), "title_ar": ar,
         "kind": "hadith", "tradition": "sunni", "format": "table", "location": location or origin_file,
         "book": f"{key}{suffix}", "mapping": {"type": "csv", "header": False, "number": "#0", "texts": texts},
         "license": "ODbL-1.0", "source_name": "Open Hadith Data", "source_key": "open-hadith-data",
         "origin": OHD_ORIGIN,
         "description": "Arabic with full diacritics" + (" and a commentary (tafsil) of every hadith" if sharh else "")
                        + "; numbered as in the Sakhr / al-Islam edition. Open Database License: credit the "
                          "Open Hadith Data project; a database made from it stays under the ODbL."}
    if fallback:
        e["fallback"] = {"format": "table", "location": origin_file}
    return e


def hj(key: str, suffix: str) -> dict:
    title, ar, path = HJ[key]
    return {"id": f"{key}{suffix}", "title": title + (" — sunnah.com (hadith-json)" if suffix else ""), "title_ar": ar,
            "kind": "hadith", "tradition": "sunni", "format": "table", "location": f"{HJ_URL}/{path}.json",
            "book": f"{key}{suffix}", "mapping": HJ_MAPPING, "license": None, "source_name": "hadith-json (sunnah.com)",
            "source_key": "hadith-json", "origin": HJ_ORIGIN,
            "description": "Arabic and the sunnah.com English translation, by chapter. No licence is given, so it is "
                           "read from its author's repository and kept on this computer only."}


def lk(key: str) -> dict:
    title, ar, folder, first, last = LK[key]
    return {"id": f"{key}-lk", "title": f"{title} — LK corpus", "title_ar": ar, "kind": "hadith", "tradition": "sunni",
            "format": "table", "location": f"{LK_URL}/{folder}/Chapter{first}.csv",
            "parts": [f"{LK_URL}/{folder}/Chapter{c}.csv" for c in range(first, last + 1)],
            "book": f"{key}-lk", "mapping": LK_MAPPING, "license": None, "source_name": "LK Hadith Corpus",
            "source_key": "lk-hadith-corpus", "origin": LK_ORIGIN,
            "description": "Arabic and English in parallel, each hadith with its isnad and matn marked apart (al-Bukhari "
                           "checked by hand, the others by a segmenter, 92% accurate), and its grade. Cite: Altammami, "
                           "Atwell & Alsalka, The Arabic–English Parallel Corpus of Authentic Hadith (2019)."}


def hds(key: str) -> dict:
    title, ar, file = HDS[key]
    return {"id": f"{key}-hds", "title": f"{title} — Hadith-Data-Sets", "title_ar": ar, "kind": "hadith",
            "tradition": "sunni", "format": "table", "location": f"{HDS_URL}/{file}", "book": f"{key}-hds",
            "mapping": HDS_MAPPING, "license": None, "source_name": "Hadith-Data-Sets", "source_key": "hadith-data-sets",
            "origin": HDS_ORIGIN,
            "description": "Arabic with diacritics, one hadith per row, numbered in order (the nine books: 62,169 hadith)."}


def hf(key: str) -> dict:
    title, ar, file = HF[key]
    return {"id": f"{key}-hf", "title": f"{title} — Hugging Face", "title_ar": ar, "kind": "hadith",
            "tradition": "sunni", "format": "table", "location": f"{HF_URL}/{file}", "book": f"{key}-hf",
            "mapping": HF_MAPPING, "license": "MIT (as declared; text from sunnah.com)",
            "source_name": "meeAtif/hadith_datasets", "source_key": "hf-meeatif-hadith", "origin": HF_ORIGIN,
            "description": "Arabic, English, chapter titles in both and the sunnah.com grade, from the Hugging Face "
                           "dataset meeAtif/hadith_datasets."}


def tq(key: str) -> dict:
    title, ar, compiler, files = TQ[key]
    parts = ([{"location": f"{TQ_URL}/{f}.json", "volume": i} for i, f in enumerate(files, 1)] if len(files) > 1
             else [f"{TQ_URL}/{files[0]}.json"])
    return {"id": key, "title": title, "title_ar": ar, "kind": "hadith", "tradition": "shia", "format": "table",
            "location": f"{TQ_URL}/{files[0]}.json", "parts": parts, "book": key, "mapping": TQ_MAPPING,
            "license": None, "source_name": "Thaqalayn", "source_key": "thaqalayn", "origin": TQ_ORIGIN,
            "description": f"Compiled by {compiler}. Arabic and English from thaqalayn.net"
                           + (", with the grades of al-Majlisi (Mir'at al-'Uqul) and al-Behbudi (Sahih al-Kafi)"
                              if key == "kafi" else "")
                           + (f"; {len(files)} volumes, numbered volume:hadith" if len(files) > 1 else "")
                           + ". No licence is given, so it is read from its origin and kept on this computer only."}


def rijal() -> list[dict]:
    return [
        {"id": "taqrib", "title": "Taqrib al-Tahdhib — Ibn Hajar al-'Asqalani", "title_ar": "تقريب التهذيب",
         "kind": "rijal", "tradition": "sunni", "format": "taqrib", "location": TAQRIB_URL, "license": None,
         "source_name": "Ibn Hajar, Taqrib al-Tahdhib (OpenITI)", "source_key": "openiti-taqrib",
         "origin": OPENITI_ORIGIN,
         "description": "8,824 narrators of the six books with Ibn Hajar's verdict, rank, tabaqa, death year and book "
                        "marks; identifies the narrators in every chain. From the OpenITI corpus (licence not stated "
                        "there, so kept on this computer only)."},
        {"id": "najashi", "title": "Rijal al-Najashi — al-Najashi (Shia)", "title_ar": "رجال النجاشي",
         "kind": "rijal", "tradition": "shia", "format": "najashi", "location": NAJASHI_URL, "license": None,
         "source_name": "al-Najashi, Rijal (OpenITI)", "source_key": "openiti-najashi", "origin": OPENITI_ORIGIN,
         "description": "1,266 authors and narrators with al-Najashi's words, read on the Shia scale (thiqa, praised, "
                        "muwaththaq, weak; creed: Imami, Waqifi, Fathi, Zaydi …); readable in Books. From the OpenITI "
                        "corpus (licence not stated there, so kept on this computer only)."},
    ]


# ================================================================== isnady's own repository
# Every book under OUR names: sunni/<book>/, shia/<book>/, rijal/<tradition>/<work>; isnady's own book format
# (isnady-book/1, read by isnady.data.importers.isnady_book). Where each book was first published is said once,
# in the credits of README.md and in each book's "credit" — never in a path or a key.
LANG = {"ara": ("Arabic", "rtl"), "eng": ("English", "ltr"), "tur": ("Turkish", "ltr"), "urd": ("Urdu", "rtl"),
        "ind": ("Indonesian", "ltr"), "ben": ("Bengali", "ltr"), "fra": ("French", "ltr"), "rus": ("Russian", "ltr"),
        "tam": ("Tamil", "ltr")}
COMPILER = {"bukhari": "al-Bukhari (d. 256)", "muslim": "Muslim (d. 261)", "abudawud": "Abu Dawud (d. 275)",
            "tirmidhi": "al-Tirmidhi (d. 279)", "nasai": "al-Nasa'i (d. 303)", "ibnmajah": "Ibn Maja (d. 273)",
            "malik": "Malik (d. 179)", "nawawi": "al-Nawawi (d. 676)", "qudsi": "", "dehlawi": "Shah Waliullah (d. 1176)",
            "ahmad": "Ahmad ibn Hanbal (d. 241)", "darimi": "al-Darimi (d. 255)", "riyad": "al-Nawawi (d. 676)",
            "shamail": "al-Tirmidhi (d. 279)", "bulugh": "Ibn Hajar (d. 852)", "adab": "al-Bukhari (d. 256)",
            "mishkat": "al-Khatib al-Tabrizi (d. 741)"}
CREDIT = {
    "fawaz": "Text and translations: fawazahmed0/hadith-api (The Unlicense).",
    "ohd": "Text: the Open Hadith Data project (ODbL 1.0; contents under the Database Contents License). A database "
           "made from it stays under the ODbL.",
    "hj": "Text and English: sunnah.com, as collected by AhmedBaset/hadith-json.",
    "tq": "Text, English and grades: thaqalayn.net, as collected by MohammedArab1/ThaqalaynAPI.",
    "openiti": "Text: the OpenITI corpus.",
}
OWN_SUNNI = list(FAWAZ) + ["ahmad", "darimi", "riyad", "shamail", "bulugh", "adab", "mishkat"]
GRADERS_FAWAZ = "graded by al-Albani, Shu'ayb al-Arna'ut, Zubair 'Ali Za'i and others where they graded it"


def _book_entry(tradition: str, key: str, title: str, ar: str, languages: list[str], license: str | None,
                credit: str, hadith: int | None, description: str) -> dict:
    return {"id": key, "title": title, "title_ar": ar,
            "kind": "hadith", "tradition": tradition, "format": "isnady", "location": f"{tradition}/{key}/book.json",
            "book": key, "languages": languages, "license": license, "hadith": hadith,
            "source_name": f"isnady-data: {title}", "source_key": f"isnady-{key}", "description": description}


def own_entries(counts: dict | None = None, langs: dict | None = None) -> list[dict]:
    """The catalog entries of isnady-data. counts / langs: what a mirror actually holds (else the known values)."""
    counts, langs = counts or {}, langs or {}
    out = []
    for key in FAWAZ:
        title, ar, codes, n = FAWAZ[key]
        codes = langs.get(key) or codes.split()
        out.append(_book_entry("sunni", key, title, ar, codes, "Unlicense", CREDIT["fawaz"], counts.get(key, n),
                               (f"Compiled by {COMPILER[key]}. " if COMPILER[key] else "")
                               + f"Arabic and {len(codes) - 1} translations ("
                               + ", ".join(LANG[c][0] for c in codes if c != "ara") + f"); {GRADERS_FAWAZ}."))
    for key, n in (("ahmad", 26363), ("darimi", 3367)):
        title, ar, *_ = OHD[key]
        out.append(_book_entry("sunni", key, title, ar, langs.get(key) or ["ara"], "ODbL-1.0", CREDIT["ohd"],
                               counts.get(key, n), f"Compiled by {COMPILER[key]}. Arabic with full diacritics."))
    for key, n in (("riyad", 1896), ("shamail", 402), ("bulugh", 1358), ("adab", 1326), ("mishkat", 4427)):
        title, ar, _path = HJ[key]
        out.append(_book_entry("sunni", key, title, ar, langs.get(key) or ["ara", "eng"], None, CREDIT["hj"],
                               counts.get(key, n), f"Compiled by {COMPILER[key]}. Arabic and English, by chapter."))
    for key, (title, ar, compiler, files) in TQ.items():
        out.append(_book_entry("shia", key, title, ar, langs.get(key) or ["ara", "eng"], None, CREDIT["tq"],
                               counts.get(key),
                               f"Compiled by {compiler}. Arabic and English"
                               + (", with the grades of al-Majlisi (Mir'at al-'Uqul) and al-Behbudi (Sahih al-Kafi)"
                                  if key == "kafi" else "")
                               + (f"; {len(files)} volumes, numbered volume:hadith" if len(files) > 1 else "") + "."))
    for e in rijal():
        e = dict(e)
        for k in ("origin", "source_name", "source_key"):      # the database keys of the rijal works: in isnady's code
            e.pop(k, None)
        e["location"] = f"rijal/{e['tradition']}/{'taqrib-al-tahdhib' if e['id'] == 'taqrib' else 'rijal-al-najashi'}.md"
        e["description"] = e["description"].replace(" From the OpenITI corpus (licence not stated there, so kept on "
                                                    "this computer only).", "")
        out.append(e)
    return out


def own_catalog(counts: dict | None = None, langs: dict | None = None) -> dict:
    return {"schema": SCHEMA, "id": "isnady", "name": "isnady — all sources (default)",
            "description": "isnady's own repository: every hadith collection and rijal work isnady reads, Sunni and "
                           "Shia, in one place and one format.",
            "homepage": OWN, "url": OWN_CATALOG, "default": True, "entries": own_entries(counts, langs)}


def external_catalogs() -> list[dict]:
    def repo(rid, name, homepage, description, entries):
        return {"schema": SCHEMA, "id": rid, "name": name, "description": description, "homepage": homepage,
                "entries": entries}
    return [
        repo("fawazahmed0", "fawazahmed0/hadith-api", FAWAZ_ORIGIN["url"],
             "Ten collections in Arabic and up to eight translations, with grades (Unlicense).",
             [fawaz(k, FAWAZ_INDEX, False) for k in FAWAZ]),
        repo("open-hadith-data", "Open Hadith Data", OHD_ORIGIN["url"],
             "The nine books in Arabic with diacritics, seven with a commentary of every hadith (ODbL).",
             [ohd(k, None, "-ohd", False) for k in OHD]),
        repo("hadith-json", "hadith-json (sunnah.com)", HJ_ORIGIN["url"],
             "Seventeen books in Arabic and English from sunnah.com (50,884 hadith; no licence given).",
             [hj(k, "-hj") for k in HJ]),
        repo("lk-hadith-corpus", "LK Hadith Corpus", LK_ORIGIN["url"],
             "The six books in Arabic and English, isnad and matn marked apart, with grades (39,038 hadith).",
             [lk(k) for k in LK]),
        repo("hadith-data-sets", "Hadith-Data-Sets", HDS_ORIGIN["url"],
             "The nine books in Arabic (62,169 hadith).", [hds(k) for k in HDS]),
        repo("huggingface-meeatif", "Hugging Face — meeAtif/hadith_datasets", HF_ORIGIN["url"],
             "The six books in Arabic and English with chapter titles and grades (MIT, as declared).",
             [hf(k) for k in HF]),
        repo("thaqalayn", "Thaqalayn (Shia)", TQ_ORIGIN["url"],
             "Sixteen Shia collections — al-Kafi, al-Saduq's books, al-Mufid, al-Tusi, al-Nu'mani … — in Arabic and "
             "English, al-Kafi with al-Majlisi's and al-Behbudi's grades.", [tq(k) for k in TQ]),
        repo("openiti", "OpenITI (rijal)", OPENITI_ORIGIN["url"],
             "The rijal works isnady reads from the OpenITI corpus: Ibn Hajar's Taqrib and al-Najashi's Rijal.",
             rijal()),
    ]


# ================================================================== writing
def write_json(path: Path, data: dict, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")) if compact else \
        json.dumps(data, ensure_ascii=False, indent=1)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "isnady-data builder"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except OSError:
            if attempt == 2:
                raise
    raise RuntimeError(url)


def fetch_json(url: str):
    return json.loads(fetch(url).decode("utf-8-sig"))


def _clean(value) -> str:
    from isnady.data.importers.table import _clean as clean
    return clean(value)


def _num(value) -> tuple[str, float | None]:
    from isnady.data.importers.table import _number
    return _number(value)


def write_book(target: Path, tradition: str, key: str, title: str, ar: str, compiler: str, license: str | None,
               credit: str, hadiths: list[dict], langs: dict[str, dict]) -> tuple[int, list[str]]:
    """One book in isnady's format: book.json (numbers, chapters, references, grades) and a file per language."""
    folder = target / tradition / key
    codes = [c for c in LANG if c in langs and langs[c]["texts"]]
    book = {"schema": "isnady-book/1", "key": key, "title": title, "title_ar": ar, "tradition": tradition,
            "compiler": compiler, "license": license, "credit": credit,
            "languages": {c: {"file": f"{c}.json", "name": LANG[c][0], "direction": LANG[c][1],
                              **({"author": langs[c]["author"]} if langs[c].get("author")
                                 and langs[c]["author"] != "Unknown" else {})} for c in codes},
            "hadiths": hadiths}
    book.pop("credit")                             # credits are in README.md only: no other name in the data
    write_json(folder / "book.json", book, compact=True)
    for c in codes:
        write_json(folder / f"{c}.json", {"language": c, "sections": langs[c].get("sections", {}),
                                          "texts": langs[c]["texts"]}, compact=True)
    print(f"  {tradition}/{key}: {len(hadiths):,} hadith, {', '.join(codes)}")
    return len(hadiths), codes


def _unique(hadiths: dict) -> list[dict]:
    out = []
    for h in hadiths.values():
        h = dict(h)
        h["grades"] = [list(g) for g in dict.fromkeys(tuple(g) for g in h.get("grades", []))]
        if not h["grades"]:
            h.pop("grades")
        if not h.get("refs"):
            h.pop("refs", None)
        out.append(h)
    return sorted(out, key=lambda h: (h.get("sort") is None, h.get("sort") or 0, h["n"]))


def convert_fawaz(target: Path, index: dict, key: str, only: set[str] | None):
    title, ar, _codes, _n = FAWAZ[key]
    hadiths: dict[str, dict] = {}
    langs: dict[str, dict] = {}
    for ed in index[key]["collection"]:
        code = ed["name"].split("-")[0]
        if (ed["name"].startswith("ara-") and ed["name"][-1].isdigit()) or code in langs or code not in LANG:
            continue
        if only and code not in only:
            continue
        data = fetch_json(f"{FAWAZ_RAW}/editions/{ed['name']}.min.json")
        texts = {}
        for item in data.get("hadiths", []):
            n, sort = _num(item.get("hadithnumber"))
            if not n:
                continue
            ref = item.get("reference") or {}
            h = hadiths.setdefault(n, {"n": n, "sort": sort, "refs": {}, "grades": []})
            if isinstance(ref.get("book"), int):
                h["s"] = ref["book"]
            if ref.get("book") is not None and ref.get("hadith") is not None:
                h["refs"]["in-book"] = f"{ref['book']}:{ref['hadith']}"
            an, _ = _num(item.get("arabicnumber"))
            if an:
                h["refs"]["arabic"] = an
            for g in item.get("grades") or []:
                if isinstance(g, dict) and g.get("grade"):
                    h["grades"].append(((g.get("name") or "Unknown").strip(), g["grade"].strip()))
            text = (item.get("text") or "").strip()
            if text:
                texts[n] = text
        sections = {str(k): v for k, v in (data["metadata"].get("sections") or {}).items() if v and str(k) != "0"}
        langs[code] = {"texts": texts, "sections": sections, "author": ed.get("author")}
    return write_book(target, "sunni", key, title, ar, COMPILER[key], "Unlicense", CREDIT["fawaz"], _unique(hadiths),
                      langs)


def convert_ohd(target: Path, key: str):
    import csv
    import io
    title, ar, folder, _stem, _s = OHD[key]
    rows = list(csv.reader(io.StringIO(fetch(f"{OHD_URL}/{folder}/{ohd_file(key)}").decode("utf-8-sig"))))
    hadiths, texts = {}, {}
    for r in rows:
        if len(r) < 2:
            continue
        n, sort = _num(r[0])
        text = _clean(r[1])
        if n and text:
            hadiths[n] = {"n": n, "sort": sort}
            texts[n] = text
    return write_book(target, "sunni", key, title, ar, COMPILER[key], "ODbL-1.0", CREDIT["ohd"], _unique(hadiths),
                      {"ara": {"texts": texts}})


def convert_hj(target: Path, key: str):
    title, ar, path = HJ[key]
    data = fetch_json(f"{HJ_URL}/{path}.json")
    hadiths, ara, eng = {}, {}, {}
    for item in data.get("hadiths", []):
        n, sort = _num(item.get("idInBook"))
        if not n:
            continue
        hadiths[n] = {"n": n, "sort": sort, "s": item.get("chapterId")}
        if item.get("arabic"):
            ara[n] = _clean(item["arabic"])
        en = item.get("english") or {}
        text = " ".join(x for x in (_clean(en.get("narrator")), _clean(en.get("text"))) if x)
        if text:
            eng[n] = text
    chapters = data.get("chapters") or []
    return write_book(target, "sunni", key, title, ar, COMPILER[key], None, CREDIT["hj"], _unique(hadiths),
                      {"ara": {"texts": ara, "sections": {str(c["id"]): c.get("arabic") for c in chapters if c.get("arabic")}},
                       "eng": {"texts": eng, "sections": {str(c["id"]): c.get("english") for c in chapters
                                                         if c.get("english")}}})


def convert_tq(target: Path, key: str):
    import re
    title, ar, compiler, files = TQ[key]
    hadiths, ara, eng, sections = {}, {}, {}, {}
    graders = [(g["field"], g["grader"]) for g in TQ_MAPPING["grades"]]
    for vol, f in enumerate(files, 1):
        multi = len(files) > 1
        for item in fetch_json(f"{TQ_URL}/{f}.json"):
            n, sort = _num(item.get("id"))
            if not n:
                continue
            if multi:
                n, sort = f"{vol}:{n}", vol * 100000 + (sort or 0)
            cat = item.get("categoryId")
            s = (vol * 1000 + cat) if multi and isinstance(cat, int) else cat
            h = {"n": n, "sort": sort, "s": s, "grades": []}
            for field, grader in graders:
                raw = _clean(item.get(field))
                m = re.search(r":\s*([^\n]+)", raw)
                grade = (m.group(1) if m else "").strip()
                grade = re.split(r"\s+-\s+", grade)[0].strip()
                if grade and "لم يخرجه" not in grade:
                    h["grades"].append((grader, grade))
            hadiths[n] = h
            if item.get("arabicText"):
                ara[n] = _clean(item["arabicText"])
            if item.get("englishText"):
                eng[n] = _clean(item["englishText"])
            if s is not None and item.get("category"):
                sections[str(s)] = item["category"] + (f" (volume {vol})" if multi else "")
    return write_book(target, "shia", key, title, ar, compiler, None, CREDIT["tq"], _unique(hadiths),
                      {"ara": {"texts": ara}, "eng": {"texts": eng, "sections": sections}})


def mirror(target: Path, languages: set[str] | None) -> None:
    """Build isnady-data in target: every book in isnady's format under our names, the rijal works, the catalog."""
    target.mkdir(parents=True, exist_ok=True)
    for child in target.iterdir():                 # a clean tree each time (the history stays in .git)
        if child.name != ".git":
            import shutil
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    counts, langs = {}, {}
    index = fetch_json(f"{FAWAZ_RAW}/editions.json")
    for key in FAWAZ:
        counts[key], langs[key] = convert_fawaz(target, index, key, languages)
    for key in ("ahmad", "darimi"):
        counts[key], langs[key] = convert_ohd(target, key)
    for key in ("riyad", "shamail", "bulugh", "adab", "mishkat"):
        counts[key], langs[key] = convert_hj(target, key)
    for key in TQ:
        counts[key], langs[key] = convert_tq(target, key)
    for e in rijal():
        path = target / "rijal" / e["tradition"] / ("taqrib-al-tahdhib.md" if e["id"] == "taqrib" else "rijal-al-najashi.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetch(e["location"]))
        print(f"  rijal/{e['tradition']}/{path.name}")
    cat = own_catalog(counts, langs)
    write_json(target / "catalog.json", cat)
    (target / "README.md").write_text(readme(cat), encoding="utf-8", newline="\n")
    (target / ".gitattributes").write_text("*.json -diff\n*.md -diff\nREADME.md diff\n", encoding="utf-8", newline="\n")
    write_json(BUNDLED / "isnady.json", cat)
    print(f"isnady-data written to {target}: {len(cat['entries'])} sources (and the shipped copy of its catalog)")


def readme(cat: dict) -> str:
    lines = ["# isnady-data", "",
             "The data of [isnady](https://github.com/bayramkotan/isnady): every hadith collection and rijal work it "
             "reads, Sunni and Shia, in one format. isnady imports from here (Settings → Data sources, or "
             "`iy catalog import ID`).", "",
             "- `sunni/<book>/`, `shia/<book>/` — `book.json` (numbers, chapters, references, grades) and one file "
             "per language (`ara.json`, `eng.json` …)",
             "- `rijal/sunni/`, `rijal/shia/` — the works on the narrators",
             "- `catalog.json` — the list isnady reads", ""]
    for tradition, heading in (("sunni", "Sunni collections"), ("shia", "Shia collections")):
        lines += [f"## {heading}", "", "| Book | | Compiler | Languages | Hadith |", "|---|---|---|---|---|"]
        for e in cat["entries"]:
            if e["kind"] == "hadith" and e["tradition"] == tradition:
                comp = e["description"].split(". ")[0].removeprefix("Compiled by ") if e["description"].startswith(
                    "Compiled by") else ""
                lines.append(f"| {e['title']} | {e['title_ar']} | {comp} | {', '.join(e['languages'])} | "
                             f"{(e.get('hadith') or 0):,} |")
        lines.append("")
    lines += ["## Narrators (rijal)", "", "| Work | | Tradition |", "|---|---|---|"]
    for e in cat["entries"]:
        if e["kind"] == "rijal":
            lines.append(f"| {e['title']} | {e['title_ar']} | {e['tradition']} |")
    lines += ["", "## Credits", "", "These texts were first made available by others; thank you.", ""]
    lines += [f"- {c}" for c in CREDIT.values()]
    lines.append("")
    return "\n".join(lines)


def write_catalogs() -> None:
    """The catalogs shipped with isnady: the optional repositories (and isnady-data's, unless a mirror wrote it)."""
    if not (BUNDLED / "isnady.json").exists():
        write_json(BUNDLED / "isnady.json", own_catalog())
    for cat in external_catalogs():
        write_json(BUNDLED / f"{cat['id']}.json", cat)
    print(f"Catalogs written to {BUNDLED}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalogs", action="store_true", help="write the catalogs shipped with isnady")
    ap.add_argument("--mirror", metavar="DIR", help="build the isnady-data repository in DIR (its catalog is also "
                                                    "written as the copy shipped with isnady)")
    ap.add_argument("--languages", help="with --mirror: only these languages of the translated books, e.g. ara,eng,tur")
    a = ap.parse_args()
    if not (a.catalogs or a.mirror):
        ap.print_help()
        return 2
    sys.path.insert(0, str(ROOT / "src"))
    if a.mirror:
        mirror(Path(a.mirror).expanduser(), set(a.languages.split(",")) if a.languages else None)
    if a.catalogs:
        write_catalogs()
    return 0


if __name__ == "__main__":
    sys.exit(main())
