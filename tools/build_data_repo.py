"""The repositories isnady reads its data from — defined here once, written as catalogs.

    python tools/build_data_repo.py --catalogs            write src/isnady/data/repos/*.json (shipped with isnady)
    python tools/build_data_repo.py --mirror ../isnady-data [--languages ara,eng,tur]
                                                          build the isnady-data repository: every source that may
                                                          be redistributed (tier A/B) copied into it, catalog.json,
                                                          README.md and SOURCES.md; then commit and push that folder

A REPOSITORY is a catalog.json (schema isnady-catalog/1) listing books and rijal works: where each file is, its
format, the column mapping of a table, the licence, the tradition. isnady's own repository (bayramkotan/isnady-data)
is the default and lists EVERY source, Sunni and Shia: the ones whose licence allows it are copied into the
repository (location relative to catalog.json) with the original as a fallback; the others are listed at their
origin, never copied (YAYIN KURALI: tier C is never redistributed). The other repositories are the datasets as
their authors publish them, each with its own catalog shipped inside isnady (they have none of their own).
"""

import argparse
import hashlib
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


def own_catalog(mirrored: bool) -> dict:
    """isnady's own repository: every source, Sunni and Shia, each book once (the best edition of it)."""
    entries = []
    for key in FAWAZ:
        entries.append(fawaz(key, f"fawazahmed0/{key}/editions.json" if mirrored else FAWAZ_INDEX, mirrored))
    for key in ("ahmad", "darimi"):
        _t, _a, folder, stem, _s = OHD[key]
        entries.append(ohd(key, f"open-hadith-data/{folder}/{ohd_file(key)}" if mirrored else None, "", mirrored))
    for key in ("riyad", "shamail", "bulugh", "adab", "mishkat"):
        entries.append(hj(key, ""))
    entries += [tq(k) for k in TQ]
    entries += rijal()
    return {"schema": SCHEMA, "id": "isnady", "name": "isnady — all sources (default)",
            "description": "isnady's own repository: every hadith collection and rijal work isnady can read, Sunni "
                           "and Shia. Sources whose licence allows it are kept in the repository itself; the others "
                           "are read from their origin and stay on your computer.",
            "homepage": OWN, "url": OWN_CATALOG, "default": True, "entries": entries}


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
def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def write_catalogs() -> None:
    write_json(BUNDLED / "isnady.json", own_catalog(mirrored=True))
    for cat in external_catalogs():
        write_json(BUNDLED / f"{cat['id']}.json", cat)
    print(f"Catalogs written to {BUNDLED}")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "isnady-data builder"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def mirror(target: Path, languages: set[str] | None) -> None:
    """Copy every tier A/B source into the isnady-data folder and write its catalog."""
    target.mkdir(parents=True, exist_ok=True)
    index = json.loads(fetch(f"{FAWAZ_RAW}/editions.json"))
    for key in FAWAZ:
        book = index[key]
        kept = []
        for ed in book["collection"]:
            if ed["name"].startswith("ara-") and ed["name"][-1].isdigit():
                continue                                # the diacritics-free copy
            if languages and ed["name"].split("-")[0] not in languages:
                continue
            name = f"{ed['name']}.min.json"
            out = target / "fawazahmed0" / key / name
            if not out.exists():
                print(f"  {key}: {name}")
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(fetch(f"{FAWAZ_RAW}/editions/{name}"))
            kept.append({**ed, "link": name, "linkmin": name})
        write_json(target / "fawazahmed0" / key / "editions.json", {key: {**book, "collection": kept}})
    for key in ("ahmad", "darimi"):
        folder = OHD[key][2]
        out = target / "open-hadith-data" / folder / ohd_file(key)
        if not out.exists():
            print(f"  {key}: Open Hadith Data")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(fetch(f"{OHD_URL}/{folder}/{out.name}"))
    cat = own_catalog(mirrored=True)
    for e in cat["entries"]:
        loc = target / e["location"] if not e["location"].startswith("http") else None
        if loc and loc.exists():
            e["sha256"] = hashlib.sha256(loc.read_bytes()).hexdigest()
    write_json(target / "catalog.json", cat)
    (target / "README.md").write_text(readme(cat), encoding="utf-8", newline="\n")
    (target / ".gitattributes").write_text("*.json -diff\n*.csv -diff\n", encoding="utf-8", newline="\n")
    print(f"isnady-data written to {target}: {len(cat['entries'])} sources")


def readme(cat: dict) -> str:
    lines = ["# isnady-data", "",
             "The default data repository of [isnady](https://github.com/bayramkotan/isnady): every hadith collection "
             "and rijal work isnady can read, Sunni and Shia, listed in one `catalog.json`.", "",
             "isnady reads this catalog first (Settings → Data sources, or `iy repo`). Sources whose licence allows "
             "it are kept here; the others are listed at their origin and read from there — they are never copied "
             "into this repository.", "",
             "| Source | Tradition | Kept here | Licence | Origin |", "|---|---|---|---|---|"]
    for e in cat["entries"]:
        here = "yes" if not e["location"].startswith("http") else "no — read from origin"
        lines.append(f"| {e['title']} ({e['title_ar']}) | {e['tradition']} | {here} | {e.get('license') or 'not stated'} "
                     f"| [{e['origin']['name']}]({e['origin']['url']}) |")
    lines += ["", "## Licences", "",
              "- fawazahmed0/hadith-api: The Unlicense (public domain).",
              "- Open Hadith Data (Musnad Ahmad, Sunan al-Darimi): Open Database License (ODbL 1.0); contents under "
              "the Database Contents License. Credit: the Open Hadith Data project (mhashim6). A database made from "
              "it stays under the ODbL.",
              "- Everything listed with “no — read from origin” belongs to its publisher and is not redistributed "
              "here.", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalogs", action="store_true", help="write the catalogs shipped with isnady")
    ap.add_argument("--mirror", metavar="DIR", help="build the isnady-data repository in DIR")
    ap.add_argument("--languages", help="with --mirror: only these fawazahmed0 languages, e.g. ara,eng,tur")
    a = ap.parse_args()
    if not (a.catalogs or a.mirror):
        ap.print_help()
        return 2
    if a.catalogs:
        write_catalogs()
    if a.mirror:
        mirror(Path(a.mirror).expanduser(), set(a.languages.split(",")) if a.languages else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
