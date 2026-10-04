"""Rules of the rijal works, taken from the works themselves.

Ibn Hajar, Taqrib al-Tahdhib, introduction (quoted in the Handoff):
  * twelve RANKS (maratib) of narrators, each with the words that signal it;
  * twelve TABAQAT (generations) with his examples;
  * death years written without the hundreds: tabaqa 1-2 died before 100,
    3-8 after 100, 9-12 after 200 ("and I state the exceptions");
  * book marks (خ م د ت س ق ع 4 ...) naming where a narrator's hadith appear.

Nothing here decides who a narrator is; that is isnady.core.narrators.
"""

import re

# ---------------------------------------------------------------- ranks
RANK_LABELS = {
    1: ("الصحابة", "Companion"),
    2: ("من أكد مدحه", "praise confirmed (thiqa thiqa, thiqa hafiz, awthaq al-nas)"),
    3: ("ثقة", "trustworthy (thiqa, mutqin, thabt, 'adl)"),
    4: ("صدوق", "truthful (saduq, la ba's bih)"),
    5: ("صدوق يهم", "truthful with lapses (saduq yahim, lahu awham, yukhti', taghayyara)"),
    6: ("مقبول", "acceptable when followed, otherwise weak (maqbul)"),
    7: ("مستور", "unestablished (mastur, majhul al-hal)"),
    8: ("ضعيف", "weak (da'if)"),
    9: ("مجهول", "unknown (majhul)"),
    10: ("متروك", "abandoned (matruk, wahi, saqit)"),
    11: ("متهم بالكذب", "accused of lying"),
    12: ("كذاب", "liar, fabricator"),
}

_LAPSE = (r"يهم|أوهام|اوهام|يخطئ|يخطىء|يغرب|سيء الحفظ|سيىء الحفظ|تغير|اختلط|رمي|بدعة|يتشيع|تشيع|القدر|نصب|"
          r"إرجاء|ارجاء|يدلس|مدلس|مناكير|غرائب|أفراد")
# Ibn Hajar gives HIS verdict first; what follows these words reports or answers other critics
# ("وأفرط العقيلي فقال كذاب" = al-'Uqayli went too far and called him a liar). The rank is read
# from Ibn Hajar's own words only.
_OTHERS = re.compile(r"\s(?:و|ف)?(?:قال|قالوا|قيل|أفرط|ضعفه|ضعفوه|وثقه|وثقوه|لينه|كذبه|كذبوه|تكلم|تحامل|غمزه|"
                     r"وهاه|اتهمه|جرحه|عابه|أنكر|وثق|ضعف)(?!\w)")


def own_words(phrase: str) -> str:
    """The part of a Taqrib verdict that is Ibn Hajar's own judgement."""
    cut = _OTHERS.search(" " + phrase)
    return phrase[: cut.start() - 1].strip() if cut and cut.start() > 1 else phrase


def rank_of(phrase: str) -> int | None:
    """Ibn Hajar's rank for a verdict phrase from the Taqrib, or None if it cannot be read with confidence."""
    p = " " + re.sub(r"\s+", " ", own_words(phrase)) + " "

    def has(pattern: str) -> bool:
        return re.search(r"(?<![\w])(?:" + pattern + r")(?![\w])", p) is not None

    if has(r"(?:ال)?صحابي|(?:ال)?صحابية|له صحبة|لها صحبة|له رؤية|لها رؤية|صحب النبي|أم المؤمنين|زوج النبي|"
           r"من الصحابة|المكثرين من الصحابة|من السابقين الأولين|شهد بدرا|أحد العشرة"):
        return 1
    if has(r"كذاب|وضاع|يضع الحديث|كذبوه"):
        return 12
    if has(r"متهم|اتهم|اتهموه"):
        return 11
    if has(r"متروك|متروكة|متروكا|واه|ساقط|تركوه"):
        return 10
    if (has(r"مجهول|مجهولة|لا يعرف|لا تعرف|لا يعرفان") and not has(r"مجهول الحال|مجهولة الحال")):
        return 9
    if has(r"ضعيف|ضعيفة|ضعيفا"):
        return 8
    if has(r"مستور|مستورة|مجهول الحال|مجهولة الحال"):
        return 7
    if has(r"مقبول|مقبولة|لين الحديث|لين"):
        return 6
    if has(r"صدوق|صدوقة|صدوقا|لا بأس به|ليس به بأس"):
        return 5 if has(_LAPSE) else 4
    if has(r"ثقة|ثبت|متقن|عدل|حجة|حافظ|إمام|امام|أوثق|اوثق"):
        # Ibn Hajar: rank 3 is ONE attribute (ثقة, متقن, ثبت, عدل); rank 2 is praise confirmed by a
        # superlative (أوثق الناس), by repeating it (ثقة ثقة) or by a second attribute (ثقة حافظ).
        # فقيه, عابد, زاهد praise learning or worship, not hadith, and do not count.
        if has(r"أوثق|اوثق"):
            return 2
        attributes = re.findall(r"(?<![\w])(ثقة|ثبت|متقن|عدل|حجة|حافظ|إمام|امام)(?![\w])", p)
        return 2 if len(attributes) >= 2 else 3
    if has(r"أمير المؤمنين"):
        return 1
    return None


# -------------------------------------------------------------- tabaqat
TABAQA_WORDS = {
    "الأولى": 1, "الثانية": 2, "الثالثة": 3, "الرابعة": 4, "الخامسة": 5, "السادسة": 6,
    "السابعة": 7, "الثامنة": 8, "التاسعة": 9, "العاشرة": 10, "الحادية عشرة": 11, "الثانية عشرة": 12,
}
TABAQA_LABELS = {
    1: "Companions",
    2: "senior Successors (e.g. Ibn al-Musayyab)",
    3: "middle Successors (e.g. al-Hasan, Ibn Sirin)",
    4: "Successors who narrate mostly from senior Successors (e.g. al-Zuhri, Qatada)",
    5: "junior Successors (e.g. al-A'mash)",
    6: "contemporaries of the junior Successors with no proven meeting with a Companion (e.g. Ibn Jurayj)",
    7: "senior Followers of the Successors (e.g. Malik, al-Thawri)",
    8: "middle Followers of the Successors (e.g. Ibn 'Uyayna, Ibn 'Ulayya)",
    9: "junior Followers of the Successors (e.g. Yazid b. Harun, al-Shafi'i, 'Abd al-Razzaq)",
    10: "senior narrators from the Followers' followers (e.g. Ahmad b. Hanbal)",
    11: "middle narrators from them (e.g. al-Dhuhli, al-Bukhari)",
    12: "junior narrators from them (e.g. al-Tirmidhi)",
}


def generation(tabaqa: int | None) -> str | None:
    if tabaqa is None:
        return None
    if tabaqa == 1:
        return "sahabi"
    if 2 <= tabaqa <= 5:
        return "tabi'i"
    if tabaqa == 6:
        return "contemporary of junior tabi'in"
    if 7 <= tabaqa <= 9:
        return "tabi' al-tabi'in"
    return "later"


# ---------------------------------------------------------- death years
_UNITS = {"واحد": 1, "واحدة": 1, "إحدى": 1, "احدى": 1, "اثنتين": 2, "اثنين": 2, "اثنتي": 2, "اثني": 2,
          "ثلاث": 3, "ثلاثة": 3, "أربع": 4, "اربع": 4, "أربعة": 4, "خمس": 5, "خمسة": 5, "ست": 6, "ستة": 6,
          "سبع": 7, "سبعة": 7, "ثمان": 8, "ثماني": 8, "ثمانية": 8, "تسع": 9, "تسعة": 9, "عشر": 10, "عشرة": 10}
_TENS = {"عشرين": 20, "ثلاثين": 30, "أربعين": 40, "اربعين": 40, "خمسين": 50, "ستين": 60, "سبعين": 70,
         "ثمانين": 80, "تسعين": 90}
_HUNDREDS = {"مائة": 100, "مئة": 100, "المائة": 100, "مائتين": 200, "المائتين": 200, "ثلاثمائة": 300,
             "أربعمائة": 400, "اربعمائة": 400}


def parse_year_words(words: str) -> tuple[int | None, bool]:
    """Arabic number words (or digits) -> (number, hundreds_written)."""
    digits = re.search(r"\d{1,3}", words)
    if digits:
        n = int(digits.group())
        return n, n >= 100
    total, seen, hundreds = 0, False, False
    for token in re.split(r"\s+", words.replace("و", " و ").strip()):
        token = token.strip("،,.")
        if token in ("و", ""):
            continue
        if token in _UNITS:
            total += _UNITS[token]
            seen = True
        elif token in _TENS:
            total += _TENS[token]
            seen = True
        elif token in _HUNDREDS:
            total += _HUNDREDS[token]
            seen, hundreds = True, True
        else:
            break
    return (total if seen else None), hundreds


def death_year(phrase: str, tabaqa: int | None) -> int | None:
    """Full hijri year from Ibn Hajar's wording, adding the hundreds his rule leaves out."""
    number, hundreds_written = parse_year_words(phrase)
    if number is None:
        return None
    if hundreds_written or tabaqa is None:
        return number if hundreds_written else None
    if tabaqa <= 2:
        return number
    if tabaqa <= 8:
        return number + 100
    return number + 200


# ----------------------------------------------------------- book marks
BOOK_MARKS = {
    "خ": "al-Bukhari, Sahih", "خت": "al-Bukhari, Sahih (mu'allaq)", "بخ": "al-Bukhari, al-Adab al-Mufrad",
    "عخ": "al-Bukhari, Khalq Af'al al-'Ibad", "ر": "al-Bukhari, Juz' al-Qira'a", "ي": "al-Bukhari, Raf' al-Yadayn",
    "م": "Muslim, Sahih", "د": "Abu Dawud, Sunan", "مد": "Abu Dawud, al-Marasil", "صد": "Abu Dawud, Fada'il al-Ansar",
    "خد": "Abu Dawud, al-Nasikh", "قد": "Abu Dawud, al-Qadar", "ف": "Abu Dawud, al-Tafarrud", "ل": "Abu Dawud, al-Masa'il",
    "كد": "Abu Dawud, Musnad Malik", "ت": "al-Tirmidhi, Jami'", "تم": "al-Tirmidhi, al-Shama'il",
    "س": "al-Nasa'i, Sunan", "عس": "al-Nasa'i, Musnad 'Ali", "كن": "al-Nasa'i, Musnad Malik",
    "ق": "Ibn Maja, Sunan", "فق": "Ibn Maja, al-Tafsir", "ع": "all six books", "4": "the four Sunan",
    "تمييز": "no narration in these books; named to tell him apart",
}
# which marks mean "narrates in this collection" (collection keys as imported)
COLLECTION_MARKS = {
    "bukhari": {"خ", "خت", "ع"}, "muslim": {"م", "ع"}, "abudawud": {"د", "ع", "4"},
    "tirmidhi": {"ت", "ع", "4"}, "nasai": {"س", "ع", "4"}, "ibnmajah": {"ق", "ع", "4"},
}


# ------------------------------------------------------------ display name
# Ibn Hajar spells out hard names ("بفتح المعجمة وسكون الزاي", "بنون وفاء مصغر"); the notes are kept
# with the entry and shown on request, but a name on screen reads better without them.
_NOTE_START = re.compile(
    r"^[بو]?(?:بتقديم|بتأخير|تقديم|تأخير|بالضم|بالفتح|بالكسر|بالسكون|الضم|الفتح|الكسر|همزة|بهمزة|الهمزة|ياء|فتح|ضم|كسر|سكون|تشديد|تخفيف|التشديد|التخفيف|تثقيل|التثقيل|الموحدة|موحدة|المعجمة|معجمة|معجمتين|"
    r"المهملة|مهملة|مهملتين|مهملات|التحتانية|تحتانية|الفوقانية|فوقانية|المثناة|مثناة|المثلثة|مثلثة|نون|النون|"
    r"راء|الراء|زاي|الزاي|فاء|الفاء|قاف|القاف|جيم|الجيم|حاء|خاء|دال|ذال|سين|شين|صاد|ضاد|طاء|ظاء|عين|غين|"
    r"كاف|لام|ميم|هاء|واو|ياء|مصغر|مصغرا|مكبر|بالتصغير|بالتكبير|بوزن|بلفظ|وزن)$")
_NOTE_WORDS = re.compile(
    r"^(?:و|ثم|بعدها|قبلها|آخره|وآخره|أوله|ثانيه|ثالثه|الأولى|الثانية|خفيفة|ثقيلة|مفتوحة|مضمومة|مكسورة|ساكنة|"
    r"بعد|على|المشهور|الصحيح|وقيل|ويقال|أو|مثلها|كذلك|مخففة|مشددة|المضمومة|المفتوحة|المكسورة|الساكنة|"
    r"الخفيفة|الثقيلة|المشددة|المخففة|المثقلة|الأخيرة|الأخرى|مضمومة|مفتوحة|مكسورة|مثقلة)$")


def display_name(name: str) -> str:
    out, skipping = [], False
    for word in name.split():
        if _NOTE_START.match(word):
            skipping = True
            continue
        if skipping:
            if word in ("بن", "ابن", "أبو", "أبي", "أم", "بنت") or (word.startswith("ال") and not _NOTE_START.match(word)
                                                                      and not _NOTE_WORDS.match(word)):
                skipping = False
            else:
                continue
        out.append(word)
    return " ".join(out)


def short_name(name: str, words: int = 4) -> str:
    """The first words of a name for a list or a bar, never ending on a dangling "بن" / "بنت"."""
    parts = name.split()[:words]
    while parts and parts[-1] in ("بن", "بنت", "ابن", "أبو", "أبي", "أم"):
        parts.pop()
    return " ".join(parts)
