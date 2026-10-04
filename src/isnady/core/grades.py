"""Grades as the scholars gave them, grouped so that they can be compared.

The wording is always kept and shown; the GROUP is only for counting and comparing (ST3). Groups follow
the classical order: 4 sahih (incl. sahih li-ghayrihi, "hasan sahih"), 3 hasan (incl. hasan li-ghayrihi),
2 da'if (incl. shadhdh), 1 very weak (da'if jiddan, munkar), 0 fabricated (mawdu'). Two notes are read
beside the group: "isnad" (the grade is of the chain only: "Isnaad Hasan") and the attribution
("maqtu'" — the words of a Successor, "mawquf" — of a Companion), which is not a grade of the Prophet's
words. A wording that fits no group stays ungrouped (None) rather than being guessed.
"""

import re

GROUP_LABELS = {4: "sahih", 3: "hasan", 2: "da'if", 1: "very weak", 0: "fabricated"}


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
