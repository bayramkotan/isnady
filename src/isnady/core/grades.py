"""Grades as the scholars gave them, grouped so that they can be compared.

The wording is always kept and shown; the GROUP is only for counting and comparing (ST3). Groups follow
the classical order: 4 sahih (incl. sahih li-ghayrihi, "hasan sahih"), 3 hasan (incl. hasan li-ghayrihi),
2 da'if (incl. shadhdh), 1 very weak (da'if jiddan, munkar), 0 fabricated (mawdu'). Two notes are read
beside the group: "isnad" (the grade is of the chain only: "Isnaad Hasan") and the attribution
("maqtu'" — the words of a Successor, "mawquf" — of a Companion), which is not a grade of the Prophet's
words. A wording that fits no group stays ungrouped (None) rather than being guessed.
"""

import re
from isnady.core.i18n import N_

GROUP_LABELS = {4: N_("sahih"), 3: N_("hasan"), 2: N_("da'if"), 1: N_("very weak"), 0: N_("fabricated")}


def group(grade: str) -> int | None:
    g = " " + re.sub(r"[^a-z ]", " ", (grade or "").lower()) + " "
    if re.search(r" (mawdu|mawdoo|maudu|fabricated) ", g):
        return 0
    if re.search(r" (very daif|daif jiddan|da if jiddan|munkar|matruk) ", g):
        return 1
    if re.search(r" (daif|da if|zaif|shadh|shaadh|sanad daif) ", g):
        return 2
    if re.search(r" hasan sahih ", g) or re.search(r" sahih ", g):
        return 4
    if re.search(r" hasan ", g):
        return 3
    return None


def isnad_only(grade: str) -> bool:
    return bool(re.search(r"\b(isnaad|isnad|sanad)\b", (grade or "").lower()))


def attribution(grade: str) -> str | None:
    g = (grade or "").lower()
    if re.search(r"\bmaqtu", g):
        return "maqtu'"
    if re.search(r"\bma?u?quf|\bmawquf|\bmuquf", g):
        return "mawquf"
    return None


# ------------------------------------------------------------------ the Imami grades (road B, SH1)
# The four categories of the later Imami scholars (from Ibn Tawus and al-'Allama al-Hilli), in their own order:
# sahih (every narrator an Imami thiqa), hasan (a praised Imami), muwaththaq (a thiqa of another school), da'if.
# majhul (an unknown narrator), mursal and marfu' (a gap in the chain) are counted among the da'if, as that usage
# does. These are NEVER mapped onto the Sunni groups above: each tradition is compared only within itself.
IMAMI_LABELS = {4: N_("sahih"), 3: N_("hasan"), 2: N_("muwaththaq"), 1: N_("da'if")}
_IMAMI_WORDS = (("صحيح", 4), ("حسن", 3), ("موثق", 2), ("ضعيف", 1), ("مجهول", 1), ("مهول", 1), ("مرسل", 1),
                ("مرفوع", 1))
_IMAMI_RE = re.compile(r"(?<![\w])(" + "|".join(w for w, _g in _IMAMI_WORDS) + r")(?![\w])")


def imami_group(grade: str) -> int | None:
    """The Imami category of a grade as al-Majlisi or al-Behbudi wrote it, by its first word of grade:
    "حسن كالصحيح" is hasan, "ضعيف على المشهور" da'if, "موثق" muwaththaq; "كالسابق" or "مختلف فيه" none."""
    m = _IMAMI_RE.search(re.sub(r"[\u064B-\u0652\u0670]", "", grade or ""))
    return dict(_IMAMI_WORDS)[m.group(1)] if m else None
