"""Shia rijal on its own terms (Shia Rijal section): what a Shia critic says of a narrator, read along the two
axes of the Imami tradition — reliability (thiqa, praised, weak) and creed (Imami or not: Waqifi, Fathi,
Zaydi, 'ammi …) — and the classical four-fold category those two make (later Imami usage, from Ibn Tawus and
al-'Allama al-Hilli): an Imami thiqa, a praised narrator (mamduh), a non-Imami thiqa (muwaththaq), a weak one.
This is NOT mapped onto Ibn Hajar's twelve ranks; each tradition is shown by its own measure.

Only the words that open an entry are read — before the critic's own chain to the narrator's books
("أخبرنا …", "حدثنا …"): later in an entry, "ضعيف" can be said of someone else. Creed is never assumed:
when the critic does not state it, it stays unknown.
"""

import re

RANKS = {
    1: ("ثقة إمامي", "trustworthy (thiqa)", "The critic calls him thiqa; his creed is Imami or not said to differ."),
    2: ("ممدوح", "praised (mamduh)", "Praised (jalil, wajh, 'ayn, la ba's bihi …) without the word thiqa."),
    3: ("موثق", "trustworthy, not Imami (muwaththaq)", "Called thiqa, but of another school: Waqifi, Fathi, Zaydi, 'ammi …"),
    4: ("ضعيف", "weak (da'if)", "Called weak, confused, a liar, an extremist (ghali) or the like."),
}
MADHHAB_LABELS = {"imami": "Imami", "waqifi": "Waqifi", "fathi": "Fathi", "zaydi": "Zaydi", "ammi": "'Ammi (Sunni)",
                  "nawusi": "Nawusi", "kaysani": "Kaysani", "ghali": "Ghali (extremist)"}
NON_IMAMI = {"waqifi", "fathi", "zaydi", "ammi", "nawusi", "kaysani"}

_CHAIN_START = re.compile(r"(?<!\w)(أخبرنا|أخبرني|أخبرناه|حدثنا|حدثني|حدثناه|أنبأنا|عنه بكتاب|بكتابه)(?!\w)")
_W = r"(?<![\w])"
_E = r"(?![\w])"


def _has(text: str, pattern: str) -> bool:
    # an optional و / ف before the word: "ولم يكن بذاك", "ووجهها"
    return re.search(_W + "(?:[وف])?(?:" + pattern + ")" + _E, text) is not None


def opening(entry_text: str) -> str:
    """The part of an entry in which the critic speaks of the narrator himself."""
    m = _CHAIN_START.search(entry_text)
    return entry_text[:m.start()] if m else entry_text


def assess(text: str) -> dict:
    """{'rank': 1–4 or None, 'madhhab': key or None, 'terms': [the words found]} for an entry's opening words."""
    t = re.sub(r"[\u064B-\u0652\u0670]", "", text)          # vowel marks off
    t = re.sub(r"[أإآ]", "ا", t)                              # hamza forms: "قريب الامر" is "قريب الأمر"
    terms = []

    def found(pattern: str, label: str) -> bool:
        if _has(t, pattern):
            terms.append(label)
            return True
        return False

    negated = found(r"ليس بثقة|غير ثقة|ليس بذاك|ليس بالثقة|لم يكن بذاك|لم يكن بذلك|ليس بذلك|ليس بالقوي|"
                    r"لم يكن بالمرضي|ليس بالمرضي|غير مرضي", "not thiqa")
    thiqa = (not negated) and found(r"ثقة ثقة|ثقة|ثقه|الثقة|ثقتهم|ثقتها|ثقتنا|ثقات|كلهم ثقات", "thiqa")
    weak = found(r"ضعيف|ضعيفا|ضعفه|ضعفوه|مضطرب الحديث|مضطرب|مخلط|يعرف وينكر|فاسد الحديث|غمز فيه|لين الحديث", "weak") or negated
    rejected = found(r"كذاب|كذابا|وضاع|يضع الحديث|متهم|ملعون|فاسد المذهب|مرتفع القول|غال|غاليا|من الغلاة|غلا", "rejected")
    # "صالح" is left out: it is also a name ("واسم مروك صالح")
    praised = found(r"جليل|جليل القدر|عين|وجه|وجها|وجههم|وجهها|وجيه|فقيههم|شيخ القميين|شيخ الطائفة|فاضل|خير|خيرا|صحيح الحديث|"
                    r"لا باس به|حسن الحديث|نقي الحديث|سليم الجنبة|قريب الامر|صدوق|شيخ اصحابنا|من وجوه اصحابنا|"
                    r"عظيم المنزلة|ممدوح|وجوه|جلة|من الجلة", "praised")
    madhhab = None
    # "رواه عدة من أصحابنا", "ذكره أصحابنا": said of those who transmit or mention him, not of his own creed
    t = re.sub(r"(عدة|جماعة|بعض|جماعه) من اصحابنا|ذكره اصحابنا|ذكرها اصحابنا|قال اصحابنا|رواه اصحابنا", " ", t)
    for pattern, key in ((r"واقف|واقفي|واقفيا|واقفا|وقف|من الواقفة", "waqifi"), (r"فطحي|فطحيا|من الفطحية", "fathi"),
                         (r"زيدي|زيديا|بتري|جارودي|من الزيدية", "zaydi"), (r"عامي|عاميا|من العامة|من رجال العامة", "ammi"),
                         (r"ناووسي|من الناووسية", "nawusi"), (r"كيساني|من الكيسانية", "kaysani"),
                         (r"غال|غاليا|من الغلاة|مرتفع القول", "ghali")):
        if _has(t, pattern):
            madhhab = key
            terms.append(MADHHAB_LABELS[key])
            break
    if madhhab is None and _has(t, r"من اصحابنا|احد اصحابنا|من جلة اصحابنا|شيخ اصحابنا|وجه اصحابنا|من وجوه اصحابنا|"
                                   r"من خيار الشيعة|امامي|من شيوخنا|شيخ الطائفة"):
        madhhab = "imami"
        terms.append("Imami")
    if thiqa and madhhab in NON_IMAMI:
        rank = 3
    elif thiqa and madhhab != "ghali":
        rank = 1
    elif weak or rejected:
        rank = 4
    elif praised:
        rank = 2
    else:
        rank = None
    return {"rank": rank, "madhhab": madhhab, "terms": terms}
