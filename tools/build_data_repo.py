"""The repositories isnady reads its data from — defined here once, written as catalogs.

    python tools/build_data_repo.py --mirror ../isnady-data [--languages ara,eng,tur]
                                          build the isnady-data repository: every book, Sunni and Shia, converted to
                                          isnady's own format under our names (sunni/bukhari/, shia/kafi/,
                                          rijal/sunni/…), catalog.json and README.md; its catalog is also written as
                                          the copy shipped with isnady. Then commit and push that folder.
    python tools/build_data_repo.py --quran ../isnady-data
                                          build only quran/: the Arabic (Tanzil) and the translations chosen in
                                          QURAN, in isnady's format, and the catalog's "quran" section
    python tools/build_data_repo.py --library ../isnady-data
                                          the Qur'an (--quran) and the works that are neither hadith nor rijal:
                                          sira/ (Ibn Hisham) and tabaqat/ (al-Dhahabi's Siyar and Tadhkira),
                                          and the catalog's "library"
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
    "uyun": ("ʿUyun Akhbar al-Rida — al-Saduq", "عيون أخبار الرضا", "al-Saduq (d. 381)",
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


# The folder of each book in isnady-data, and the id it is imported by: the book's full title with its compiler's
# full name — never a bare name ("ahmad"). The short key stays inside the database only (collections.key).
FOLDER = {
    "bukhari": "sahih_al_bukhari", "muslim": "sahih_muslim", "abudawud": "sunan_abi_dawud",
    "tirmidhi": "jami_al_tirmidhi", "nasai": "sunan_al_nasai", "ibnmajah": "sunan_ibn_majah",
    "malik": "muwatta_malik_ibn_anas", "nawawi": "al_arbain_al_nawawiyya", "qudsi": "al_arbain_al_qudsiyya",
    "dehlawi": "al_arbain_shah_waliullah_al_dehlawi", "ahmad": "musnad_ahmad_ibn_hanbal",
    "darimi": "sunan_al_darimi", "riyad": "riyad_al_salihin_al_nawawi",
    "shamail": "al_shamail_al_muhammadiyya_al_tirmidhi", "bulugh": "bulugh_al_maram_ibn_hajar_al_asqalani",
    "adab": "al_adab_al_mufrad_al_bukhari", "mishkat": "mishkat_al_masabih_al_khatib_al_tabrizi",
    "kafi": "al_kafi_al_kulayni", "uyun": "uyun_akhbar_al_rida_al_shaykh_al_saduq",
    "amali-saduq": "al_amali_al_shaykh_al_saduq", "khisal": "al_khisal_al_shaykh_al_saduq",
    "tawhid": "al_tawhid_al_shaykh_al_saduq", "maani": "maani_al_akhbar_al_shaykh_al_saduq",
    "thawab": "thawab_al_amal_wa_iqab_al_amal_al_shaykh_al_saduq", "sifat-shia": "sifat_al_shia_al_shaykh_al_saduq",
    "fadail-shia": "fadail_al_shia_al_shaykh_al_saduq", "amali-mufid": "al_amali_al_shaykh_al_mufid",
    "kamil-ziyarat": "kamil_al_ziyarat_ibn_qulawayh_al_qummi", "ghayba-numani": "kitab_al_ghayba_ibn_abi_zaynab_al_numani",
    "ghayba-tusi": "kitab_al_ghayba_al_shaykh_al_tusi", "mumin": "kitab_al_mumin_al_husayn_ibn_said_al_ahwazi",
    "zuhd": "kitab_al_zuhd_al_husayn_ibn_said_al_ahwazi",
    "mujam-mutabara": "mujam_al_ahadith_al_mutabara_asif_al_muhsini",
    "taqrib": "taqrib_al_tahdhib_ibn_hajar_al_asqalani", "najashi": "rijal_al_najashi_ahmad_ibn_ali_al_najashi",
}


def _book_entry(tradition: str, key: str, title: str, ar: str, languages: list[str], license: str | None,
                credit: str, hadith: int | None, description: str) -> dict:
    return {"id": FOLDER[key], "title": title, "title_ar": ar,
            "kind": "hadith", "tradition": tradition, "format": "isnady",
            "location": f"{tradition}/{FOLDER[key]}/book.json",
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
        e["location"] = f"rijal/{e['tradition']}/{FOLDER[e['id']]}.md"
        e["id"] = FOLDER[e["id"]]
        e["description"] = e["description"].replace(" From the OpenITI corpus (licence not stated there, so kept on "
                                                    "this computer only).", "")
        out.append(e)
    return out


OWN_DESCRIPTION = ("isnady's own repository: the Qur'an and its translations, every Sunni and Shia hadith collection, "
                   "the sira, the lives of the scholars and the rijal works isnady reads, in one place and one format.")


def own_catalog(counts: dict | None = None, langs: dict | None = None) -> dict:
    return {"schema": SCHEMA, "id": "isnady", "name": "isnady — all sources (default)",
            "description": OWN_DESCRIPTION,
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
    folder = target / tradition / FOLDER[key]
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


# ------------------------------------------------------------------ the Qur'an (Q1b)
QURAN_RAW = f"{RAW}/fawazahmed0/quran-api/1"
QURAN_ORIGIN = {"name": "fawazahmed0/quran-api", "url": "https://github.com/fawazahmed0/quran-api"}
QURAN_ARABIC = "ara-quransimple"
# the translations kept in isnady-data, each under the name its readers know it by (the source's own key kept, so a
# translation downloaded earlier stays the same one); any other of the 98 languages isnady still reads from the
# source itself (core.quran)
QURAN = {
    "Turkish": {
        "tur-diyanetisleri": "Diyanet İşleri", "tur-diyanetvakfi": "Diyanet Vakfı",
        "tur-elmalilihamdiya": "Elmalılı Hamdi Yazır", "tur-elmallsadelesti": "Elmalılı Hamdi Yazır (sadeleştirilmiş)",
        "tur-alibulac": "Ali Bulaç", "tur-suleymanates": "Süleyman Ateş", "tur-hasanbasricanta": "Hasan Basri Çantay",
        "tur-abdulbakigolpin": "Abdülbâki Gölpınarlı", "tur-ademugur": "Adem Uğur", "tur-alifikriyavuz": "Ali Fikri Yavuz",
        "tur-celalyldrm": "Celal Yıldırım", "tur-suatyildirim": "Suat Yıldırım", "tur-muhammedesed": "Muhammed Esed",
        "tur-ibnikesir": "İbn Kesîr (meal)", "tur-fizilalilkuran": "Fî Zılâli'l-Kur'ân", "tur-tefhimulkuran":
        "Tefhîmü'l-Kur'ân", "tur-gultekinonan": "Gültekin Onan", "tur-muhammetabay": "Muhammet Abay",
        "tur-sabanpiris": "Şaban Piriş", "tur-yasarnuriozturk": "Yaşar Nuri Öztürk",
    },
    "English": {
        "eng-ummmuhammad": "Saheeh International (Umm Muhammad)", "eng-abdelhaleem": "M. A. S. Abdel Haleem",
        "eng-mustafakhattaba": "Mustafa Khattab (The Clear Quran)", "eng-muftitaqiusmani": "Mufti Taqi Usmani",
        "eng-muhammadtaqiudd": "al-Hilali and Muhsin Khan", "eng-mohammedmarmadu": "Marmaduke Pickthall",
        "eng-abdullahyusufal": "Abdullah Yusuf Ali", "eng-muhammadasad": "Muhammad Asad",
        "eng-wahiduddinkhan": "Wahiduddin Khan", "eng-aliquliqarai": "Ali Quli Qara'i",
        "eng-mohammadhabibsh": "Mohammad Habib Shakir", "eng-muhammadsarwar": "Muhammad Sarwar",
    },
    "Urdu": {"urd-fatehmuhammadja": "Fateh Muhammad Jalandhry", "urd-muhammadjunagar": "Muhammad Junagarhi",
             "urd-abulaalamaududi": "Abul A'la Maududi"},
    "Indonesian": {"ind-indonesianislam": "Kementerian Agama RI", "ind-kingfahdcomplex": "King Fahd Complex"},
    "Bengali": {"ben-muhiuddinkhan": "Muhiuddin Khan", "ben-abubakrzakaria": "Abu Bakr Zakaria"},
    "French": {"fra-muhammadhamidul": "Muhammad Hamidullah", "fra-rashidmaash": "Rachid Maach"},
    "Russian": {"rus-elmirkuliev": "Elmir Kuliev", "rus-abuadel": "Abu Adel"},
    "Tamil": {"tam-janturstfoundat": "Jan Trust Foundation", "tam-abdulhameedbaqa": "Abdulhameed Baqavi"},
    "German": {"deu-asfbubenheimand": "A. S. F. Bubenheim and N. Elyas", "deu-amirzaidan": "Amir Zaidan"},
    "Persian": {"fas-hussainansarian": "Hussain Ansarian", "fas-mohammadmahdifo": "Mohammad Mahdi Fooladvand",
                "fas-nasermakaremshi": "Naser Makarem Shirazi"},
    "Spanish": {"spa-juliocortes": "Julio Cortés", "spa-muhammadisagarc": "Muhammad Isa García"},
    "Bosnian": {"bos-besimkorkut": "Besim Korkut"},
    "Albanian": {"sqi-sherifahmeti": "Sherif Ahmeti"},
    "Azerbaijani": {"aze-vasimmammadaliy": "Vasim Mammadaliyev and Ziya Bunyadov", "aze-alikhanmusayev": "Alikhan Musayev"},
    "Uzbek": {"uzb-muhammadsodikmu": "Muhammad Sodik Muhammad Yusuf"},
    "Kazakh": {"kaz-khalifahaltai": "Khalifah Altai"},
    "Tatar": {"tat-yakubibnnugman": "Yakub ibn Nugman"},
    "Malay": {"msa-abdullahmuhamma": "Abdullah Muhammad Basmeih"},
}
QURAN_TR = (    # the suras' names in Turkish, as the Diyanet gives them (core.quran.TR_NAMES)
    "Fâtiha", "Bakara", "Âl-i İmrân", "Nisâ", "Mâide", "En'âm", "A'râf", "Enfâl", "Tevbe", "Yûnus", "Hûd", "Yûsuf",
    "Ra'd", "İbrâhîm", "Hicr", "Nahl", "İsrâ", "Kehf", "Meryem", "Tâhâ", "Enbiyâ", "Hac", "Mü'minûn", "Nûr", "Furkân",
    "Şuarâ", "Neml", "Kasas", "Ankebût", "Rûm", "Lokmân", "Secde", "Ahzâb", "Sebe'", "Fâtır", "Yâsîn", "Sâffât", "Sâd",
    "Zümer", "Mü'min", "Fussilet", "Şûrâ", "Zuhruf", "Duhân", "Câsiye", "Ahkâf", "Muhammed", "Fetih", "Hucurât", "Kâf",
    "Zâriyât", "Tûr", "Necm", "Kamer", "Rahmân", "Vâkıa", "Hadîd", "Mücâdele", "Haşr", "Mümtehine", "Saf", "Cuma",
    "Münâfikûn", "Teğâbün", "Talâk", "Tahrîm", "Mülk", "Kalem", "Hâkka", "Meâric", "Nûh", "Cin", "Müzzemmil",
    "Müddessir", "Kıyâme", "İnsân", "Mürselât", "Nebe'", "Nâziât", "Abese", "Tekvîr", "İnfitâr", "Mutaffifîn",
    "İnşikâk", "Bürûc", "Târık", "A'lâ", "Gâşiye", "Fecr", "Beled", "Şems", "Leyl", "Duhâ", "İnşirâh", "Tîn", "Alak",
    "Kadr", "Beyyine", "Zilzâl", "Âdiyât", "Kâria", "Tekâsür", "Asr", "Hümeze", "Fîl", "Kureyş", "Mâûn", "Kevser",
    "Kâfirûn", "Nasr", "Tebbet", "İhlâs", "Felak", "Nâs")
QURAN_TERMS = ("The Arabic text is Tanzil's (tanzil.net), copied verbatim as its terms ask; each translation is its "
               "translator's, as its source gives it.")


def build_quran(target: Path) -> dict:
    """quran/ in isnady-data: the suras, the Arabic and the translations above, each verse as the source gives it,
    in isnady's format (isnady-quran/1); returns the catalog's "quran" section (also kept as quran/index.json)."""
    import hashlib

    folder = target / "quran"
    index = fetch_json(f"{QURAN_RAW}/editions.json")
    by_key = {v["name"]: v for v in index.values()}
    info = fetch_json(f"{QURAN_RAW}/info.json")
    suras = [{"n": c["chapter"], "name": c["name"], "english": c["englishname"], "arabic": c["arabicname"],
              "tr": QURAN_TR[c["chapter"] - 1], "place": c["revelation"], "verses": len(c["verses"])}
             for c in info["chapters"]]
    write_json(folder / "suras.json", {"schema": "isnady-quran-suras/1", "suras": suras})
    wanted = [("Arabic", QURAN_ARABIC, "The Qur'an — Tanzil (simple script)")] + \
        [(lang, key, name) for lang, keys in QURAN.items() for key, name in keys.items()]
    editions = []
    for lang, key, name in wanted:
        about = by_key.get(key)
        if about is None:
            print(f"  quran: no edition {key} in the source — left out")
            continue
        data = fetch_json(f"{QURAN_RAW}/editions/{key}.min.json")
        verses = [[v["chapter"], v["verse"], v["text"]] for v in data["quran"]]
        code = key.split("-")[0]
        path = folder / code / f"{key}.json"
        write_json(path, {"schema": "isnady-quran/1", "key": key, "language": lang, "translator": name,
                          "direction": about.get("direction", "ltr"), "verses": verses}, compact=True)
        raw = path.read_bytes()
        editions.append({"key": key, "language": lang, "author": name, "direction": about.get("direction", "ltr"),
                         "source": about.get("source") or "", "comments": about.get("comments") or "",
                         "location": f"quran/{code}/{key}.json", "verses": len(verses), "size": len(raw),
                         "sha256": hashlib.sha256(raw).hexdigest()})
        print(f"  quran/{code}/{key}.json  {lang:12} {name}  ({len(verses)} verses)")
    section = {"schema": "isnady-quran/1", "suras": "quran/suras.json", "arabic": QURAN_ARABIC, "terms": QURAN_TERMS,
               "editions": editions}
    write_json(folder / "index.json", section)
    return section


# ------------------------------------------------------------------ the library: sira and tabaqat (LIB1)
# Books that are neither hadith collections nor rijal: the Prophet's life (sira) and the lives of the scholars by
# generation (tabaqat). Kept in isnady-data verbatim, under our names; isnady reads them into its Books section
# (format "openiti-work": its headings as chapters, its entries and paragraphs as they stand). Listed in the
# catalog's "library" (not in "entries": an isnady before 0.6.9 reads only "entries" and would not know them).
OPENITI_RAW = f"{RAW}/OpenITI"
LIBRARY = [
    {"id": "al_sira_al_nabawiyya_ibn_hisham", "aliases": ["sira", "ibn-hisham"], "kind": "sira", "category": "sira",
     "title": "al-Sira al-Nabawiyya — Ibn Hisham", "title_ar": "السيرة النبوية لابن هشام",
     "compiler": "Ibn Hisham (d. 218; 213 in some sources), from Ibn Ishaq (d. 151)",
     "location": "sira/al_sira_al_nabawiyya_ibn_hisham.md",
     "origin_location": f"{OPENITI_RAW}/0225AH/master/data/0213IbnHisham/0213IbnHisham.SiraNabawiyya/"
                        "0213IbnHisham.SiraNabawiyya.Shamela0023833-ara1.completed",
     "edition": "ed. Mustafa al-Saqqa, Ibrahim al-Abyari and 'Abd al-Hafiz al-Shalabi (Cairo: al-Halabi, 1955)",
     "description": "The life of the Prophet ﷺ as Ibn Ishaq told it and Ibn Hisham edited it: his lineage, birth, "
                    "the revelation, Mecca, the Hijra, the campaigns and his death — 264 chapters, 2,109 sections, "
                    "each report with its chain as the author gives it."},
    {"id": "siyar_alam_al_nubala_al_dhahabi", "aliases": ["siyar"], "kind": "tabaqat", "category": "tabaqat", "entries": "siyar",
     "title": "Siyar A'lam al-Nubala' — al-Dhahabi", "title_ar": "سير أعلام النبلاء",
     "compiler": "al-Dhahabi (d. 748)",
     "location": "tabaqat/siyar_alam_al_nubala_al_dhahabi.md",
     "origin_location": f"{OPENITI_RAW}/0750AH/master/data/0748Dhahabi/0748Dhahabi.SiyarAclamNubala/"
                        "0748Dhahabi.SiyarAclamNubala.Shamela0010906-ara1.mARkdown",
     "edition": "the Risala edition",
     "description": "The lives of the Companions, the Successors and the scholars after them, generation by "
                    "generation, to al-Dhahabi's own time — 5,851 entries; the source of the written lives isnady "
                    "shows beside a narrator."},
    {"id": "tadhkirat_al_huffaz_al_dhahabi", "aliases": ["tadhkira"], "kind": "tabaqat", "category": "tabaqat", "entries": "tadhkira",
     "title": "Tadhkirat al-Huffaz — al-Dhahabi", "title_ar": "تذكرة الحفاظ",
     "compiler": "al-Dhahabi (d. 748)",
     "location": "tabaqat/tadhkirat_al_huffaz_al_dhahabi.md",
     "origin_location": f"{OPENITI_RAW}/0750AH/master/data/0748Dhahabi/0748Dhahabi.TadhkiratHuffaz/"
                        "0748Dhahabi.TadhkiratHuffaz.JK000532-ara1.mARkdown",
     "edition": "",
     "description": "The 1,176 hadith masters (huffaz) from Abu Bakr to al-Dhahabi's teachers, in 21 generations; "
                    "the source of the Huffaz of the Scholars page."},
]


def library_entries(target: Path | None = None) -> list[dict]:
    """The catalog's "library": the Qur'an (when quran/ is built) and the works above, each with its size and sha256
    when the folder holds it."""
    import hashlib

    out = []
    q = quran_section(target) if target else None
    if q:
        texts = [e for e in q["editions"] if e["key"] != q["arabic"]]
        out.append({"id": "al_quran_al_karim", "aliases": ["quran"], "kind": "quran", "category": "quran",
                    "format": "isnady-quran",
                    "title": "The Holy Qur'an", "title_ar": "القرآن الكريم", "tradition": "all",
                    "location": "quran/index.json", "license": "Tanzil (verbatim); translations as their sources give",
                    "languages": sorted({e["language"] for e in texts}), "translations": len(texts),
                    "size": sum(e.get("size", 0) for e in q["editions"]),
                    "description": f"The Arabic text (Tanzil, verbatim) and {len(texts)} translations in "
                                   f"{len({e['language'] for e in texts})} languages; the Arabic and one translation "
                                   "in the interface language are downloaded, the others when chosen."})
    for item in LIBRARY:
        e = {"id": item["id"], "aliases": item["aliases"], "kind": item["kind"], "category": item["category"],
             "format": "openiti-work",
             "title": item["title"], "title_ar": item["title_ar"], "tradition": "sunni", "location": item["location"],
             "book": item["id"], "license": None, "compiler": item["compiler"],
             "description": f"Compiled by {item['compiler']}. " + item["description"],
             "origin": OPENITI_ORIGIN, "fallback": {"format": "openiti-work", "location": item["origin_location"]}}
        if item.get("entries"):
            e["entries"] = item["entries"]
        path = (target / item["location"]) if target else None
        if path and path.exists():
            raw = path.read_bytes()
            e["size"], e["sha256"] = len(raw), hashlib.sha256(raw).hexdigest()
        out.append(e)
    return out


def build_library(target: Path) -> list[dict]:
    """sira/ and tabaqat/ in isnady-data: each work as the corpus gives it (verbatim), under our names."""
    for item in LIBRARY:
        path = target / item["location"]
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = fetch(item["origin_location"])
        path.write_bytes(raw)
        print(f"  {item['location']}  ({len(raw) / 2**20:.1f} MB)")
    return library_entries(target)


def library_into_catalogs(target: Path) -> None:
    """The "library" (and the "quran" section) into the folder's catalog.json and the copy shipped with isnady."""
    library = library_entries(target)
    for path in (target / "catalog.json", BUNDLED / "isnady.json"):
        cat = json.loads(path.read_text(encoding="utf-8")) if path.exists() else own_catalog()
        cat["library"] = library
        cat["description"] = OWN_DESCRIPTION
        if quran_section(target):
            cat["quran"] = quran_section(target)
        write_json(path, cat)
    if (target / "catalog.json").exists():
        (target / "README.md").write_text(readme(json.loads((target / "catalog.json").read_text(encoding="utf-8"))),
                                          encoding="utf-8", newline="\n")


def quran_section(target: Path) -> dict | None:
    path = target / "quran" / "index.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def quran_into_catalogs(target: Path, section: dict) -> None:
    """The "quran" section into the folder's catalog.json and the copy shipped with isnady."""
    for path in (target / "catalog.json", BUNDLED / "isnady.json"):
        cat = json.loads(path.read_text(encoding="utf-8")) if path.exists() else own_catalog()
        cat["quran"] = section
        cat["library"] = library_entries(target)
        cat["description"] = OWN_DESCRIPTION
        write_json(path, cat)
    if (target / "catalog.json").exists():
        (target / "README.md").write_text(readme(json.loads((target / "catalog.json").read_text(encoding="utf-8"))),
                                          encoding="utf-8", newline="\n")


def mirror(target: Path, languages: set[str] | None) -> None:
    """Build isnady-data in target: every book in isnady's format under our names, the rijal works, the catalog."""
    target.mkdir(parents=True, exist_ok=True)
    for child in target.iterdir():                 # a clean tree each time (the history stays in .git)
        if child.name not in (".git", ".gitignore", "derived", "database.json", "release", "quran", "sira", "tabaqat"):   # DB1, Q1b, LIB1
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
        path = target / "rijal" / e["tradition"] / f"{FOLDER[e['id']]}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetch(e["location"]))
        print(f"  rijal/{e['tradition']}/{path.name}")
    cat = own_catalog(counts, langs)
    if quran_section(target):                      # the Qur'an is built on its own (--quran) and kept
        cat["quran"] = quran_section(target)
    if not all((target / item["location"]).exists() for item in LIBRARY):
        build_library(target)
    cat["library"] = library_entries(target)
    write_json(target / "catalog.json", cat)
    (target / "README.md").write_text(readme(cat), encoding="utf-8", newline="\n")
    (target / ".gitattributes").write_text("*.json -diff\n*.md -diff\nREADME.md diff\n", encoding="utf-8", newline="\n")
    write_json(BUNDLED / "isnady.json", cat)
    print(f"isnady-data written to {target}: {len(cat['entries'])} sources (and the shipped copy of its catalog)")


LANG_NAMES = {"ara": "Arabic", "eng": "English", "tur": "Turkish", "urd": "Urdu", "ind": "Indonesian",
              "ben": "Bengali", "fra": "French", "rus": "Russian", "tam": "Tamil"}


def readme(cat: dict) -> str:
    """The README of isnady-data: what it is, what it holds, its layout and formats, and how isnady uses it."""
    import re

    def compiler(e: dict) -> str:
        m = re.match(r"Compiled by (.+?\))\.", e.get("description") or "") or \
            re.match(r"Compiled by (.+?)\. Arabic", e.get("description") or "")
        return m.group(1) if m else "—"

    hadith = [e for e in cat["entries"] if e["kind"] == "hadith"]
    rijal = [e for e in cat["entries"] if e["kind"] == "rijal"]
    by = {t: [e for e in hadith if e["tradition"] == t] for t in ("sunni", "shia")}
    total = {t: sum(e.get("hadith") or 0 for e in by[t]) for t in by}
    langs = sorted({c for e in hadith for c in e.get("languages", [])}, key=lambda c: (c != "ara", c))
    n_rijal = {e["id"]: (re.match(r"([\d,]+)", e.get("description") or "") or [None, "—"])[1] for e in rijal}
    L = []
    add = L.extend
    add(['<h1 align="center">📚 isnady-data</h1>', "",
         '<p align="center"><strong>The data of <a href="https://github.com/bayramkotan/isnady">isnady</a>: '
         'every hadith collection and rijal work it reads, Sunni and Shia, in one place and one format</strong></p>', "",
         '<p align="center">',
         f'  <img src="https://img.shields.io/badge/hadith%20collections-{len(hadith)}-1D4777?style=for-the-badge" alt="collections">',
         '  <img src="https://img.shields.io/badge/hadith-' + f"{sum(total.values()):,}".replace(",", "%2C")
         + '-A47E24?style=for-the-badge" alt="hadith">',
         f'  <img src="https://img.shields.io/badge/rijal%20works-{len(rijal)}-5B6878?style=for-the-badge" alt="rijal">',
         f'  <img src="https://img.shields.io/badge/languages-{len(langs)}-14304F?style=for-the-badge" alt="languages">',
         '</p>', "",
         "isnady ships without hadith data. It reads it from a **data repository**, and this one is its "
         "default: everything isnady can read — "
         f"**{len(by['sunni'])} Sunni and {len(by['shia'])} Shia hadith collections "
         f"({sum(total.values()):,} hadith)** and **{len(rijal)} works on the narrators** — converted once into "
         "isnady's own format, each book in a folder named by its full title and its compiler. Nothing here has "
         "to be prepared by hand: isnady lists these books in **Settings → Data sources** and imports any of them "
         "with one click, or all of them at once.", "",
         '<p align="center"><img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/'
         'screenshots/data-sources.png" alt="isnady — Settings → Data sources: this repository and its books, '
         'Sunni and Shia apart" width="760"></p>', "",
         "---", "",
         "## 🚀 Use it", "",
         "**In isnady (the default).** Open **File → Data Sources** (or **Settings → Data sources**): this "
         "repository is already chosen. Tick the books and the languages you want and press **Import**, or "
         "**Import all**. Every hadith keeps its number, chapter, references and grades; the search index, the "
         "chains of transmission and the narrators are built as part of the import.", "",
         "**From the command line** — the same engine:", "",
         "```bash",
         "iy catalog list                                           # every book of this repository",
         "iy catalog import sahih_al_bukhari --language ara --language tur",
         "iy catalog import al_kafi_al_kulayni                      # with al-Majlisi's and al-Behbudi's grades",
         "iy catalog import taqrib_al_tahdhib_ibn_hajar_al_asqalani # identifies the narrators of the Sunni chains",
         "iy catalog import rijal_al_najashi_ahmad_ibn_ali_al_najashi  # … and of the Shia chains",
         "iy catalog import --all                                   # everything",
         "```", "",
         "**Without the network.** Clone this repository once (a USB stick or a shared folder works too) and read "
         "every book from it:", "",
         "```bash",
         "git clone https://github.com/bayramkotan/isnady-data ~/isnady-data",
         "iy repo add ~/isnady-data      # in the window: Data sources → A folder on this computer…",
         "iy catalog import --all",
         "```", "",
         "**A whole ready database.** The [Releases](https://github.com/bayramkotan/isnady-data/releases) "
         "carry `isnady-db-<date>.zip`: a complete isnady database built from this repository, its chains read and "
         "its narrators identified (`database.json` beside it gives its date, size, sha256 and contents). Take it "
         "with **Data folder → Use a ready database…** or:", "",
         "```bash",
         "iy database use ~/Downloads/isnady-db-<date>.zip",
         "```", "",
         "isnady checks the file (the zip must hold `isnady.db`, the schema must be one it reads, the sha256 must "
         "match `database.json`), puts it in place at the next start and keeps your previous database beside it "
         "(`isnady.<date-time>.bak.db`). Nothing is deleted.", "",
         "---", "",
         "## 🗂️ What is inside", "",
         "```",
         "isnady-data/",
         "├── catalog.json                     the list isnady reads (schema isnady-catalog/1)",
         "├── sunni/",
         "│   ├── sahih_al_bukhari/",
         "│   │   ├── book.json                numbers, chapters, references, grades (schema isnady-book/1)",
         "│   │   ├── ara.json                 the Arabic text, chapter titles",
         "│   │   ├── eng.json  tur.json …     one file per translation",
         "│   ├── musnad_ahmad_ibn_hanbal/",
         "│   └── …",
         "├── shia/",
         "│   ├── al_kafi_al_kulayni/",
         "│   └── …",
         "├── rijal/",
         "│   ├── sunni/taqrib_al_tahdhib_ibn_hajar_al_asqalani.md",
         "│   └── shia/rijal_al_najashi_ahmad_ibn_ali_al_najashi.md",
         "├── derived/                         computations already made (statistics, models …), as JSON",
         "└── database.json                    the ready database of the latest Release",
         "```", "",
         "**Names.** Every folder and every id is the book's full title with its compiler's name — "
         "`musnad_ahmad_ibn_hanbal`, `al_kafi_al_kulayni`, `taqrib_al_tahdhib_ibn_hajar_al_asqalani` — never a "
         "bare name. The same ids are what isnady imports by, and what its exports and saved computations are "
         "named after.", "",
         "**Sunni and Shia apart.** Every book says its tradition. isnady keeps the two side by side and never mixes "
         "their measures: the chains of a Sunni book are read the Sunni way and their narrators identified in Ibn "
         "Hajar's *Taqrib*; the chains of a Shia book are read the Shia way (al-Kulayni's teacher named without a "
         "term, his groups, the chain ending at one of the Fourteen Ma'sumun) and their narrators identified only "
         "in the Shia rijal works, judged in the Imami critics' own terms.", "",
         "---", ""])
    for t, heading, note in (
            ("sunni", "📗 Sunni hadith collections",
             "The six books, the Muwatta and the Forties in Arabic and up to eight translations, with the grades of "
             "al-Albani, Shu'ayb al-Arna'ut, Zubair 'Ali Za'i and others where they graded them; Musnad Ahmad and "
             "Sunan al-Darimi in fully voweled Arabic; five more books in Arabic and English, by chapter."),
            ("shia", "📘 Shia hadith collections",
             "al-Kafi in its eight volumes with al-Majlisi's grade on nearly every hadith (*Mir'at al-'Uqul*, "
             "13,931) and al-Behbudi's selection (*Sahih al-Kafi*), and fifteen more works of al-Saduq, al-Mufid, Ibn Qulawayh, al-Nu'mani, al-Tusi, al-Ahwazi "
             "and al-Muhsini, in Arabic and English.")):
        add([f"## {heading}", "", note, "",
             "| Book | | Compiler | Hadith | Languages | Import id |", "|---|---|---|--:|---|---|"])
        for e in by[t]:
            add([f"| **{e['title']}** | {e['title_ar']} | {compiler(e)} | {(e.get('hadith') or 0):,} | "
                 f"{', '.join(LANG_NAMES.get(c, c) for c in e['languages'])} | `{e['id']}` |"])
        add([f"| | | **{len(by[t])} books** | **{total[t]:,}** | | |", ""])
    add(["## 👥 Narrators (rijal)", "",
         "| Work | | Tradition | Entries | What isnady does with it | Import id |", "|---|---|---|--:|---|---|"])
    uses = {"sunni": "every name in the Sunni chains is matched to its narrator; his rank on Ibn Hajar's twelve-step "
                     "scale, tabaqa, death year and book marks",
            "shia": "every name in the Shia chains is matched to its narrator; his reliability and creed in the "
                    "critic's own (Imami) terms — never on the Sunni scale"}
    for e in rijal:
        add([f"| **{e['title']}** | {e['title_ar']} | {e['tradition'].capitalize()} | {n_rijal[e['id']]} | "
             f"{uses.get(e['tradition'], '')} | `{e['id']}` |"])
    q = cat.get("quran")
    if q:
        by_lang: dict[str, list] = {}
        for e in q["editions"]:
            if e["key"] != q["arabic"]:
                by_lang.setdefault(e["language"], []).append(e["author"])
        add(["", "## 📖 The Qur'an", "",
             "The text isnady shows in **Books → The Qur'an**, downloaded only when the reader asks for it: the Arabic "
             f"(Tanzil's simple script) and **{sum(len(v) for v in by_lang.values())} translations in "
             f"{len(by_lang)} languages**, each verse as its translator gave it. isnady can also read any other "
             "translation of the 98 languages from the source named in the credits.", "",
             "| Language | Translations |", "|---|---|"])
        for lang, names in by_lang.items():
            add([f"| {lang} | {', '.join(names)} |"])
        add(["", "Layout: `quran/suras.json` (the 114 suras: names in Arabic, English and Turkish, Meccan or Medinan, "
             "verses), `quran/<language>/<key>.json` (`{\"schema\": \"isnady-quran/1\", \"key\", \"language\", "
             "\"translator\", \"direction\", \"verses\": [[sura, verse, text], …]}`), and the `quran` section of "
             "catalog.json listing them."])
    works = [e for e in cat.get("library", []) if e["kind"] in ("sira", "tabaqat")]
    if works:
        add(["", "## 📜 Sira and tabaqat", "",
             "The life of the Prophet ﷺ and the lives of the scholars, generation by generation — read in isnady's "
             "**Books** like the hadith collections, chapter by chapter; al-Dhahabi's two works also give the text "
             "beside a narrator's written life and the Huffaz of the Scholars page.", "",
             "| Work | | Compiler | What it holds | Import id |", "|---|---|---|---|---|"])
        for e in works:
            what = e["description"].split(". ", 1)[-1]
            add([f"| **{e['title'].split(' — ')[0]}** | {e['title_ar']} | {e.get('compiler', '')} | {what} | "
                 f"`{e['id']}` |"])
    add(["", "---", "",
         "## 🧩 The formats", "",
         "<details>", "<summary><b>catalog.json — <code>isnady-catalog/1</code></b></summary>", "",
         "```json",
         "{",
         '  "schema": "isnady-catalog/1",',
         '  "id": "isnady", "name": "isnady — all sources (default)",',
         '  "homepage": "https://github.com/bayramkotan/isnady-data",',
         '  "entries": [',
         '    { "id": "sahih_al_bukhari", "title": "Sahih al-Bukhari", "title_ar": "صحيح البخاري",',
         '      "kind": "hadith", "tradition": "sunni", "format": "isnady",',
         '      "location": "sunni/sahih_al_bukhari/book.json", "book": "bukhari",',
         '      "languages": ["ara", "eng", "tur"], "license": "Unlicense", "hadith": 7590 }',
         "  ]",
         "}",
         "```", "",
         "`location` is relative to the catalog, so the same catalog works on GitHub, in a clone and on a USB "
         "stick. `kind` is `hadith` or `rijal`; `tradition` is `sunni` or `shia`; `format` names the reader isnady "
         "uses (`isnady`, `taqrib`, `najashi` …).", "", "</details>", "",
         "<details>", "<summary><b>book.json and the language files — <code>isnady-book/1</code></b></summary>", "",
         "```json",
         "{",
         '  "schema": "isnady-book/1", "key": "kafi", "title": "al-Kafi — al-Kulayni", "title_ar": "الكافي",',
         '  "tradition": "shia", "compiler": "al-Kulayni (d. 329)",',
         '  "languages": { "ara": { "file": "ara.json", "name": "Arabic", "direction": "rtl" },',
         '                 "eng": { "file": "eng.json", "name": "English", "direction": "ltr" } },',
         '  "hadiths": [',
         '    { "n": "1:6", "sort": 100006.0, "s": 1002,',
         '      "grades": [["al-Majlisi (Mir\'at al-\'Uqul)", "موثق ول يقصر عن الصحيح"]] }',
         "  ]",
         "}",
         "```", "",
         "Each hadith: `n` its number as the book gives it, `sort` its place, `s` its chapter, `refs` other "
         "numberings, `grades` every grade as `[scholar, grade]`, exactly as written. Each language file "
         "(`ara.json`, `eng.json` …) holds `{\"language\", \"sections\": {chapter: title}, \"texts\": {number: text}}`.",
         "", "</details>", "",
         "---", "",
         "## 🔄 How it is made", "",
         "Both are tools in the isnady repository:", "",
         "```bash",
         "python tools/build_data_repo.py --mirror ~/Github/isnady-data   # convert every source into this repository",
         "python tools/publish_database.py ~/Github/isnady-data           # a ready database for a Release, and derived/",
         "```", "",
         "`publish_database.py` copies the database compactly, leaves out everything imported from a user's own "
         "files (they never leave that computer), zips it for a Release (`db-<date>`) and copies the saved "
         "computations into `derived/`, so they are not computed again for the same data.", "",
         "---", "",
         "## 📜 Licences and credits", "",
         "Every book records its licence, and isnady shows them all under **Help → Licences**. The texts here were "
         "first made available by others; thank you:", "",
         "| Texts | First published by | Licence |", "|---|---|---|",
         "| The six books, the Muwatta, the Forties — text and translations | fawazahmed0/hadith-api | The Unlicense |",
         "| Musnad Ahmad, Sunan al-Darimi — voweled text | Open Hadith Data | ODbL 1.0 (a database made from it stays under the ODbL) |",
         "| Riyad al-Salihin, al-Shama'il, Bulugh al-Maram, al-Adab al-Mufrad, Mishkat — text and English | sunnah.com, via AhmedBaset/hadith-json | not stated |",
         "| The Shia collections — text, English, grades | thaqalayn.net, via MohammedArab1/ThaqalaynAPI | not stated |",
         "| The Taqrib, al-Najashi's Rijal; Ibn Hisham's Sira; al-Dhahabi's Siyar and Tadhkira | the OpenITI corpus | not stated |",
         "| The Qur'an — the Arabic and the translations | fawazahmed0/quran-api; the Arabic from tanzil.net, the "
         "translations from Tanzil, QuranEnc and others, each named in catalog.json | The Unlicense (the collection); "
         "Tanzil's text verbatim, as its terms ask |", "",
         "isnady itself is MIT-licensed: [bayramkotan/isnady](https://github.com/bayramkotan/isnady).", ""])
    return "\n".join(L)


def write_readme(target: Path) -> None:
    """The README of an isnady-data folder, from its catalog.json (no conversion, no download)."""
    cat = json.loads((target / "catalog.json").read_text(encoding="utf-8"))
    (target / "README.md").write_text(readme(cat), encoding="utf-8", newline="\n")
    print(f"README written to {target / 'README.md'}")


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
    ap.add_argument("--quran", metavar="DIR", help="build only quran/ in the isnady-data folder DIR: the Arabic and the "
                                                   "translations chosen above, and its section of the catalog")
    ap.add_argument("--library", metavar="DIR", help="build quran/, sira/ and tabaqat/ in the isnady-data folder DIR "
                                                     "and the catalog's library (everything that is not hadith or rijal)")
    ap.add_argument("--readme", metavar="DIR", help="write only the README of the isnady-data folder DIR, from its catalog")
    a = ap.parse_args()
    if a.readme:
        write_readme(Path(a.readme).expanduser())
        return 0
    if a.library:
        target = Path(a.library).expanduser()
        quran_into_catalogs(target, build_quran(target))
        build_library(target)
        library_into_catalogs(target)
        print(f"The library written to {target}: the Qur'an, {len(LIBRARY)} works, the catalog and its shipped copy")
        return 0
    if a.quran:
        target = Path(a.quran).expanduser()
        section = build_quran(target)
        quran_into_catalogs(target, section)
        print(f"quran/ written to {target}: {len(section['editions'])} texts (the catalog and its shipped copy too)")
        return 0
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
