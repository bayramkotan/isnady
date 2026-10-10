"""The two roads (SH1): every value isnady derives from a chain — how the chain is read, where it ends, whose
rijal work identifies its narrators, which scale its grades use — is reached along the road of the book's own
tradition. Sunni books go by road A, Shia books by road B; the results meet on the same pages, each marked with
the tradition it came from, and are never mapped onto the other tradition's measure.

    profile("sunni")   road A: transmission terms open every link (حدثنا، أخبرنا، عن …); the chain ends at the
                       Prophet ﷺ; narrators are identified in Ibn Hajar's Taqrib; grades are those of the Sunni
                       critics (sahih, hasan, da'if …).
    profile("shia")    road B: al-Kulayni and his peers open with the teacher's name, without a term; groups
                       stand for named teachers ("عدة من أصحابنا"); two roads join ("جميعاً"); a chain may be
                       raised without its links ("رفعه") or name no one ("عن رجل"); it ends at one of the Fourteen
                       Ma'sumun, the Prophet or an Imam, most often an Imam named by his kunya ("أبو عبد الله" is
                       Ja'far al-Sadiq); narrators are identified in Shia rijal works only (al-Najashi; al-Tusi
                       when imported); grades are those of the Imami scholars (al-Majlisi, al-Behbudi …), in their
                       own words (shia_rijal.py).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from isnady.core.normalize import normalize

SUNNI, SHIA = "sunni", "shia"
TRADITIONS = (SUNNI, SHIA)
LABELS = {SUNNI: "Sunni", SHIA: "Shia"}


@dataclass(frozen=True)
class Masum:
    key: str
    name: str            # how isnady names him or her (NM2: never a bare name)
    name_ar: str
    note: str = ""


# The Fourteen Ma'sumun of the Imami tradition, in order; "abu_al_hasan" and "one_of_two" is al-Kulayni's "أحدهما": al-Baqir or al-Sadiq
MASUMIN = [
    Masum("prophet", "the Prophet Muhammad ﷺ", "رسول الله ﷺ"),
    Masum("fatima", "Fatima al-Zahra'", "فاطمة الزهراء عليها السلام"),
    Masum("ali", "Imam 'Ali ibn Abi Talib (Amir al-Mu'minin)", "أمير المؤمنين علي بن أبي طالب عليه السلام"),
    Masum("hasan", "Imam al-Hasan ibn 'Ali al-Mujtaba", "الحسن بن علي المجتبى عليه السلام"),
    Masum("husayn", "Imam al-Husayn ibn 'Ali", "الحسين بن علي عليه السلام"),
    Masum("sajjad", "Imam 'Ali ibn al-Husayn Zayn al-'Abidin", "علي بن الحسين زين العابدين عليه السلام"),
    Masum("baqir", "Imam Muhammad ibn 'Ali al-Baqir", "محمد بن علي الباقر عليه السلام", "Abu Ja'far"),
    Masum("sadiq", "Imam Ja'far ibn Muhammad al-Sadiq", "جعفر بن محمد الصادق عليه السلام", "Abu 'Abd Allah"),
    Masum("kazim", "Imam Musa ibn Ja'far al-Kazim", "موسى بن جعفر الكاظم عليه السلام",
          "Abu al-Hasan (the first), Abu Ibrahim, al-'Abd al-Salih"),
    Masum("rida", "Imam 'Ali ibn Musa al-Rida", "علي بن موسى الرضا عليه السلام", "Abu al-Hasan (the second)"),
    Masum("jawad", "Imam Muhammad ibn 'Ali al-Jawad", "محمد بن علي الجواد عليه السلام", "Abu Ja'far the second"),
    Masum("hadi", "Imam 'Ali ibn Muhammad al-Hadi", "علي بن محمد الهادي عليه السلام", "Abu al-Hasan the third"),
    Masum("askari", "Imam al-Hasan ibn 'Ali al-'Askari", "الحسن بن علي العسكري عليه السلام", "Abu Muhammad"),
    Masum("mahdi", "Imam Muhammad ibn al-Hasan al-Mahdi", "محمد بن الحسن المهدي عليه السلام", "Sahib al-Zaman"),
    Masum("abu_al_hasan", "Abu al-Hasan — Imam al-Kazim or Imam al-Rida", "أبو الحسن عليه السلام",
          "the kunya alone does not say which; al-Kazim is \"the first\", al-Rida \"the second\""),
    Masum("imam", "an Imam", "الإمام عليه السلام", "the honorific marks him; the name does not say which Imam"),
    Masum("mudmar", "an Imam not named (mudmar)", "مضمر",
          "\"سألته\", \"كتبت إليه\": the narrator does not name him; the chain is mudmar"),
    Masum("one_of_two", "one of the two Imams (al-Baqir or al-Sadiq)", "أحدهما عليهما السلام",
          "al-Kulayni's \"ahaduhuma\": the narrator did not say which"),
]
MASUM = {m.key: m for m in MASUMIN}

# how the chains name them (normalised, longer forms first); a kunya alone is ambiguous when no honorific
# follows ("أبو عبد الله" is also al-Barqi), so the honorific decides — these forms only say WHICH Ma'sum it is
_NAMES = [
    ("علي بن محمد العسكري", "hadi"), ("علي بن محمد الهادي", "hadi"), ("علي بن محمد النقي", "hadi"),
    ("محمد بن علي الجواد", "jawad"), ("محمد بن علي التقي", "jawad"), ("محمد بن علي الباقر", "baqir"),
    ("الحسن بن علي العسكري", "askari"), ("علي بن موسي الرضا", "rida"), ("جعفر بن محمد الصادق", "sadiq"),
    ("موسي بن جعفر الكاظم", "kazim"), ("علي بن الحسين زين العابدين", "sajjad"),
    ("ابي جعفر الثاني", "jawad"), ("ابو جعفر الثاني", "jawad"), ("ابي الحسن الثالث", "hadi"),
    ("ابو الحسن الثالث", "hadi"), ("ابي الحسن الرضا", "rida"), ("ابو الحسن الرضا", "rida"),
    ("ابي الحسن الثاني", "rida"), ("ابو الحسن الثاني", "rida"), ("ابي الحسن الاول", "kazim"),
    ("ابو الحسن الاول", "kazim"), ("ابي الحسن موسي", "kazim"), ("ابو الحسن موسي", "kazim"),
    ("ابي الحسن العسكري", "hadi"), ("ابي محمد العسكري", "askari"), ("ابو محمد العسكري", "askari"),
    ("ابي عبد الله", "sadiq"), ("ابو عبد الله", "sadiq"), ("ابا عبد الله", "sadiq"),
    ("ابي جعفر", "baqir"), ("ابو جعفر", "baqir"), ("ابا جعفر", "baqir"),
    ("ابي ابراهيم", "kazim"), ("ابو ابراهيم", "kazim"), ("ابا ابراهيم", "kazim"),
    ("ابي الحسن", "abu_al_hasan"), ("ابو الحسن", "abu_al_hasan"), ("ابا الحسن", "abu_al_hasan"),
    ("ابي محمد", "askari"), ("ابو محمد", "askari"), ("ابا محمد", "askari"),
    ("العبد الصالح", "kazim"), ("العالم", "kazim"),
    ("جعفر بن محمد", "sadiq"), ("الصادق", "sadiq"), ("محمد بن علي", "baqir"), ("الباقر", "baqir"),
    ("موسي بن جعفر", "kazim"), ("الكاظم", "kazim"), ("علي بن موسي", "rida"), ("الرضا", "rida"),
    ("علي بن الحسين", "sajjad"), ("زين العابدين", "sajjad"), ("الحسين بن علي", "husayn"), ("الحسين", "husayn"),
    ("الحسن بن علي", "hasan"), ("الحسن", "hasan"), ("امير المومنين", "ali"), ("علي بن ابي طالب", "ali"),
    ("علي", "ali"), ("فاطمه", "fatima"), ("رسول الله", "prophet"), ("النبي", "prophet"),
    ("نبي الله", "prophet"), ("احدهما", "one_of_two"), ("صاحب الزمان", "mahdi"), ("الحجه", "mahdi"),
]
# names that end a Shia chain even without an honorific after them: no other narrator is called so
ALWAYS_MASUM = ("احدهما", "امير المومنين", "رسول الله", "النبي", "نبي الله", "الرضا", "الصادق", "الباقر",
                "العبد الصالح", "ابي ابراهيم", "ابا ابراهيم", "ابي الحسن الرضا", "ابي جعفر الثاني",
                "ابي الحسن الثالث", "ابي الحسن الاول", "ابي الحسن الثاني", "صاحب الزمان")


def which_masum(name: str) -> str:
    """The key of the Ma'sum a (normalised) name refers to, "" when it names none of them."""
    n = re.sub(r"[()\[\]]", " ", normalize(name))
    n = re.sub(r"\s+", " ", n).strip(" ،,:")
    for form, key in _NAMES:
        if n == form or n.startswith(form + " "):
            return key
    return ""


_FORM_RES = sorted(((re.compile(r"(?<!\w)(?:ل|ب|و|ف)?" + form + r"(?!\w)"), form, key) for form, key in _NAMES),
                   key=lambda x: -len(x[1]))


def masum_in(text: str) -> str:
    """The Ma'sum named in a few words ("قلت لأبي الحسن موسى بن جعفر"): the form that starts first, the longest
    of those that start there; "" when none is named."""
    n = re.sub(r"[()\[\]،,:]", " ", normalize(text))
    best = None
    for rx, form, key in _FORM_RES:
        m = rx.search(n)
        if m and (best is None or m.start() < best[0] or (m.start() == best[0] and len(form) > best[1])):
            best = (m.start(), len(form), key)
    return best[2] if best else ""


def masum_label(key: str) -> str:
    m = MASUM.get(key)
    return m.name if m else ""


# al-Kulayni's own explanation of his "عدة من أصحابنا" (reported from him by al-'Allama al-Hilli at the end of
# al-Khulasa): which teachers the group stands for depends on the narrator the group transmits from
KULAYNI_IDDA = {
    "احمد بن محمد بن عيسي": ["محمد بن يحيى العطار", "علي بن موسى الكمنداني", "داود بن كورة",
                             "أحمد بن إدريس", "علي بن إبراهيم بن هاشم"],
    "احمد بن محمد بن خالد": ["علي بن إبراهيم", "علي بن محمد بن عبد الله بن أذينة",
                             "أحمد بن عبد الله بن أمية", "علي بن الحسين السعدآبادي"],
    "سهل بن زياد": ["علي بن محمد بن علان", "محمد بن أبي عبد الله", "محمد بن الحسن", "محمد بن عقيل الكليني"],
}
# al-Kulayni's own teachers, as he names them at the head of his chains, with the names they have in the rijal works
# (teacher context: at the head of a chain of al-Kafi "محمد بن يحيى" is al-'Attar, no other Muhammad b. Yahya)
COMPILER_TEACHERS = {
    "kafi": {
        "علي بن ابراهيم": "علي بن ابراهيم بن هاشم",
        "محمد بن يحيي": "محمد بن يحيي العطار",
        "ابو علي الاشعري": "احمد بن ادريس",
        "الحسين بن محمد": "الحسين بن محمد بن عمران",
        "علي بن محمد": "علي بن محمد بن ابراهيم بن ابان",
        "حميد بن زياد": "حميد بن زياد",
        "احمد بن ادريس": "احمد بن ادريس",
    },
}
GROUP_FORMS = ("عده من اصحابنا", "جماعه من اصحابنا", "غير واحد من اصحابنا", "غير واحد")
PREVIOUS_FORMS = ("عنه", "عنهم", "وعنه")
VAGUE_FORMS = ("رجل", "رجل من اصحابنا", "بعض اصحابنا", "بعض اصحابه", "بعض اصحابهم", "من ذكره", "من حدثه",
               "بعض رجاله", "رجل من اهل", "من اخبره", "بعض من رواه", "بعض اصحابنا رفعه")


def group_members(group: str, next_name: str) -> list[str]:
    """The teachers a group of al-Kulayni stands for, read from the narrator it transmits from; [] when unknown."""
    if normalize(group).strip() not in GROUP_FORMS[:1]:
        return []
    nxt = normalize(next_name)
    for head, members in KULAYNI_IDDA.items():
        if nxt.startswith(head):
            return members
    if nxt.startswith("سهل"):
        return KULAYNI_IDDA["سهل بن زياد"]
    return []


def teacher_name(collection: str, raw_name: str) -> str:
    """The fuller name of a compiler's teacher at the head of his chains ("" when not one of them)."""
    return COMPILER_TEACHERS.get(collection, {}).get(normalize(raw_name).strip(" ،,"), "")


def link_kind(raw_name: str) -> str:
    """'group' (عدة من أصحابنا), 'previous' (عنه: the narrator who heads the previous chain), 'vague' (عن رجل,
    بعض أصحابه: a narrator not named), or 'person'."""
    n = normalize(raw_name).strip(" ،,")
    if n in GROUP_FORMS:
        return "group"
    if n in PREVIOUS_FORMS:
        return "previous"
    if n in VAGUE_FORMS or n.startswith(("بعض اصحاب", "رجل من", "بعض من", "من ذكره", "من حدثه")):
        return "vague"
    return "person"


@dataclass(frozen=True)
class Profile:
    key: str
    label: str
    chain_end: str                        # what the chain reaches, in words
    rijal: tuple[str, ...]                # the rijal sources whose narrators may be identified in its chains
    grades: str                           # the grading scale of its scholars
    bare_start: bool                      # a chain may open with the teacher's name, without a term
    notes: list[str] = field(default_factory=list)


PROFILES = {
    SUNNI: Profile(SUNNI, "Sunni", "the Prophet ﷺ", ("openiti-taqrib",),
                   "sahih / hasan / da'if … (the Sunni critics: al-Albani, Shu'ayb al-Arna'ut …)", False,
                   ["Every link is opened by a transmission term (حدثنا، أخبرنا، عن، أن …).",
                    "The chain ends at the Prophet ﷺ (marfu') or at a Companion (mawquf).",
                    "Narrators are identified in Ibn Hajar's Taqrib al-Tahdhib, with his twelve ranks."]),
    SHIA: Profile(SHIA, "Shia", "one of the Fourteen Ma'sumun (the Prophet ﷺ or an Imam)",
                  ("openiti-najashi", "openiti-tusi-rijal", "openiti-tusi-fihrist"),
                  "sahih / hasan / muwaththaq / da'if … (the Imami scholars: al-Majlisi, al-Behbudi …)", True,
                  ["al-Kulayni opens with his teacher's name, without a term (\"علي بن إبراهيم عن أبيه …\").",
                   "\"عدة من أصحابنا\" stands for named teachers, as al-Kulayni explained them.",
                   "\"… جميعاً عن …\": two roads join; the first is followed.",
                   "\"رفعه\": the chain is raised without its links; \"عن رجل\": a narrator not named.",
                   "The chain ends at one of the Fourteen Ma'sumun — most often an Imam named by his kunya "
                   "(أبو عبد الله = Ja'far al-Sadiq, أبو جعفر = al-Baqir, أبو الحسن = al-Kazim or al-Rida).",
                   "Narrators are identified only in Shia rijal works (al-Najashi; al-Tusi when imported); "
                   "they are judged in the Imami terms of their own critics, never on Ibn Hajar's scale."]),
}


def profile(tradition: str | None) -> Profile:
    return PROFILES.get(tradition or SUNNI, PROFILES[SUNNI])


def of_collection(conn: sqlite3.Connection, key: str) -> str:
    row = conn.execute("SELECT tradition FROM collections WHERE key = ?", (key,)).fetchone()
    return (row[0] if row and row[0] in TRADITIONS else SUNNI)
