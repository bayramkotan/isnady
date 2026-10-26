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


# ------------------------------------------------------------------ searching by grade (GR-FLT, 2026-10-27)
# Bayram: "Hadisleri ararken guvenirliklerine gore de secebilmemiz lazim. Yani ben sadece sahih ya da hasen
# arayabilirim, ya da her ikisi, ya da daha fazlasi!" Each tradition keeps its own scale: a Sunni choice never
# matches a Shia book's grade and the reverse (road A / road B). A hadith is read by the grades the graders gave it,
# word for word grouped as above; a grade that fits no group counts for none.
SUNNI_FILTERS = (("sahih", 4, N_("sahih")), ("hasan", 3, N_("hasan")), ("daif", 2, N_("da'if")),
                 ("very-weak", 1, N_("very weak")), ("fabricated", 0, N_("fabricated")),
                 ("ungraded", None, N_("not graded")))
SHIA_FILTERS = (("imami-sahih", 4, N_("sahih")), ("imami-hasan", 3, N_("hasan")), ("muwaththaq", 2, N_("muwaththaq")),
                ("imami-daif", 1, N_("da'if")), ("imami-ungraded", None, N_("not graded")))
FILTER_CODES = tuple(c for c, _g, _l in SUNNI_FILTERS + SHIA_FILTERS)
_SUNNI_CODE = {g: c for c, g, _l in SUNNI_FILTERS if g is not None}
_SHIA_CODE = {g: c for c, g, _l in SHIA_FILTERS if g is not None}
# al-Bukhari's and Muslim's own books carry no grader's grade: the hadith they set down in them with their chains are
# sahih by the compiler's condition and by the community's acceptance of the two books (talaqqi bi-l-qabul). This is
# the rule of hadith science, not a grade of a later grader: it is said so wherever it is used, and it can be left out.
SAHIHAYN = ("bukhari", "muslim")


def code_of(grade: str, tradition: str | None) -> str | None:
    """The filter code of one grade in its own tradition's scale ("sahih", "imami-sahih", "muwaththaq" …)."""
    if (tradition or "sunni") == "shia":
        return _SHIA_CODE.get(imami_group(grade))
    return _SUNNI_CODE.get(group(grade))


def _codes(conn) -> dict:
    """{hadith id: [the code of each grade it was given]} — counted once per change of the database (core.cache)."""
    from isnady.core import cache

    def count(c):
        out: dict = {}
        for hid, tradition, grade in c.execute(
                "SELECT g.hadith_id, c.tradition, g.grade FROM grades g JOIN hadiths h ON h.id = g.hadith_id "
                "JOIN collections c ON c.id = h.collection_id"):
            out.setdefault(hid, []).append(code_of(grade, tradition))
        return out

    return cache.kept(conn, "grade-codes", count)


def passes(codes: list, tradition: str | None, book: str, wanted: set, every: bool = False,
           sahihayn: bool = True) -> bool:
    """Does a hadith with these grade codes pass the choice? every: each grade it was given is among those chosen
    (the graders agree), else one of them is enough."""
    shia = (tradition or "sunni") == "shia"
    known = [c for c in codes if c]
    if not known:
        if sahihayn and not shia and book in SAHIHAYN and not codes:
            return "sahih" in wanted
        return ("imami-ungraded" if shia else "ungraded") in wanted
    if every:
        return all(c in wanted for c in known)
    return any(c in wanted for c in known)


def allowed_ids(conn, wanted, every: bool = False, sahihayn: bool = True) -> set[int]:
    """The hadith that pass the choice, in every book (kept in memory per choice while the database is unchanged)."""
    from isnady.core import cache

    wanted = frozenset(wanted)

    def count():
        codes = _codes(conn)
        return {hid for hid, key, tradition in conn.execute(
                    "SELECT h.id, c.key, c.tradition FROM hadiths h JOIN collections c ON c.id = h.collection_id")
                if passes(codes.get(hid, []), tradition, key, wanted, every, sahihayn)}

    return cache.memo(conn, "grade-allowed", (tuple(sorted(wanted)), every, sahihayn), count)


def describe_choice(wanted, every: bool = False) -> str:
    """"sahih, hasan (Sunni) · sahih (Shia)" — the choice in words."""
    from isnady.core.i18n import tr

    wanted = set(wanted)
    parts = []
    for filters, road in ((SUNNI_FILTERS, N_("Sunni")), (SHIA_FILTERS, N_("Shia"))):
        names = [tr(label) for code, _g, label in filters if code in wanted]
        if names:
            parts.append(f"{', '.join(names)} ({tr(road)})")
    text = " · ".join(parts)
    return text + (" — " + tr("every grader agrees") if every and parts else "")
