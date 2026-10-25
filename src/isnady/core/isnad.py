"""Isnad parser: separates the chain of transmission from the text (matn)
and splits it into narrators, using the transmission terms that link them.

    حَدَّثَنَا الْحُمَيْدِيُّ ... قَالَ حَدَّثَنَا سُفْيَانُ ... عَنْ ... سَمِعْتُ عُمَرَ ...
      -> [("haddathana", "الْحُمَيْدِيُّ عَبْدُ اللَّهِ بْنُ الزُّبَيْرِ"), ("haddathana", "سُفْيَانُ"), ...]

Names are kept EXACTLY as written (with diacritics and with clarifications such
as "- يعني ابن محمد -"), because identifying the narrator is a later, separate
step (matching against rijal works). No link is guessed: when the text does not
follow the expected pattern, the chain is stored raw with no links and a reason.

Version 1 limits, all reported rather than guessed:
  * tahwil (ح, a switch to a second chain) — stored raw, not split;
  * two teachers at one link (qiran: "عثمان وابو بكر ... قالا") — stored raw, not split;
  * a last narrator introduced only by "qala" ("عن علقمة، قال قال عبد الله ...") is NOT added:
    the same shape starts stories ("قال كنا مع النبي"), so the chain may stop one link early;
  * chains that do not start with a transmission term (e.g. "وقال", "وزاد").

Shia books are read along their own road (SH1, core/traditions.py): parse(text, "shia") — the teacher named
without a term, al-Kulayni's groups, two roads joined by "جميعاً", "رفعه", unnamed narrators, and a chain that
ends at one of the Fourteen Ma'sumun rather than only at the Prophet.

Who is not a narrator (2026-10-18, isnady-isnad-9): the Prophet ﷺ by his kunya or an epithet ("سمعت أبا القاسم ﷺ",
"حدثني خليلي", "الصادق المصدوق"); the subject of a story after "أنّ" — one who speaks to the Prophet or to someone
("عن أبي هريرة أن سعد بن عبادة قال لرسول الله"), or, after a Companion, one who does not go on to transmit; one a
Companion heard reciting ("سمعت هشام بن حكيم يقرأ"); an angel. Where a second road begins after a link — "وعن فلان",
"وحدثنا فلان", "قال وأخبرني فلان", "، وفلان" after a Companion — each road is its own chain, joined to the first where
they meet (a narrator named in both), never read on as one chain; a road begun again without a sign (one narrator
named twice) is cut there. core/companions.py tells the Companions by name.

PARSER_ID changes whenever the rules change; derived chains are then rebuilt.
"""

import functools
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Callable

from isnady.core.normalize import normalize as normalize_name
from isnady.core.normalize import normalize_with_map
from isnady.core.i18n import N_, t, tr
from isnady.core.companions import is_companion_name

PARSER_ID = "isnady-isnad-12"  # bump when rules change (7: tahwil split; 8: two narrators at a link, a chain kept as far as read;
#                                9: the Prophet by his kunya, the subject of a story, second roads after "وعن" / "وحدثنا")
#                               10: one man named twice with a comma between, "أبو خيثمة، زهير بن حرب"
#                               11: "- وهو ابن …-", an aside in dashes, "قال فلان أخبرنا", "قال قال ابن جريج أخبرني",
#                                   "سألت عائشة" / "سئل أنس", and where two roads of a tahwil meet)
#                               12: the Musnad without commas ("سفيان وشعبة عن", "عن عائشة أنها"), which teacher said
#                                   which word ("قال إسحاق أخبرنا وقال الآخران حدثنا"), "قال قال إسرائيل قال أبو إسحاق",
#                                   al-Bukhari's asides in "ـ … ـ", "أو عن أبي سعيد", "وجدت في كتاب أبي", "كتب إلي",
#                                   "بلغه عن", "وقال الليث حدثني" (ta'liq), two roads of one depth, the books that
#                                   cite without a chain (2026-10-25: "10bin senet az mı????!!!!")

# normalised form -> term id; longer forms first so "حدثني" is not read as "حدث"
TERMS = [
    ("حدثناه", "haddathana"), ("حدثنيه", "haddathani"), ("حدثنا", "haddathana"), ("حدثني", "haddathani"), ("ثنا", "haddathana"),
    ("حدثتنا", "haddathana"), ("حدثتني", "haddathani"), ("اخبرتنا", "akhbarana"), ("اخبرتني", "akhbarani"),
    ("اخبرنا", "akhbarana"), ("اخبرني", "akhbarani"), ("انبانا", "anba'ana"), ("انباني", "anba'ani"),
    ("سمعت", "sami'tu"), ("سمعا", "sami'a"), ("سمعوا", "sami'a"), ("سمعه من", "sami'a"), ("سمعته من", "sami'a"), ("سمعها من", "sami'a"), ("سمع", "sami'a"), ("قرات علي", "qara'tu 'ala"), ("قري علي", "quri'a 'ala"),
    ("وجدت في كتابي عن", "wajadtu"), ("وجدت في كتاب", "wajadtu"), ("وجدت هذا الحديث في كتاب", "wajadtu"), ("كتب الي", "kataba"), ("كتب الينا", "kataba"),
    ("انه بلغه عن", "balagha"), ("انه بلغه ان", "balagha"), ("اخبرت عن", "balagha"), ("نبيت عن", "balagha"),
    ("حفظناه من", "sami'tu"), ("احدثكم", "haddathana"), ("حدثكم", "haddathana"), ("اخبركم", "akhbarana"), ("حدثك", "haddathana"),
    ("اخبرك", "akhbarana"), ("بلغه عن", "balagha"), ("بلغني عن", "balagha"), ("بلغنا عن", "balagha"),
    ("زعم", "za'ama"), ("عن", "'an"), ("ان", "anna"),
]
_TERM_RE = re.compile(r"(?<!\w)و?(" + "|".join(t for t, _ in TERMS) + r")(?!\w)")
# the Shia books are read with the terms they were read with before isnady-isnad-12 (the new forms are the Sunni
# books' own: "سمعوا", "كتب إلي", "وجدت في كتاب" …, which al-Saduq's and al-Kulayni's chains say otherwise)
_SHIA_TERMS = ["حدثناه", "حدثنيه", "حدثنا", "حدثني", "ثنا", "اخبرنا", "اخبرني", "انبانا", "انباني", "سمعت", "سمع",
               "قرات علي", "قري علي", "زعم", "عن", "ان"]
_SHIA_TERM_RE = re.compile(r"(?<!\w)و?(" + "|".join(_SHIA_TERMS) + r")(?!\w)")
_TERM_ID = dict(TERMS)

# words that sit between a name and the next term and belong to neither
_FILLER_WORDS = ("قالوا", "قالت", "قالا", "قال", "يقولان", "يقول", "تقول", "انهما", "انها", "انه",
                 "حدثهم", "حدثها", "حدثه", "اخبرهم", "اخبره", "يحدث", "كلاهما", "جميعا",
                 "يحدثونه", "يحدثانه", "حدثاه", "حدثوه", "اخبراه", "اخبروه", "كلهم", "يخبر", "حدثته", "اخبرته",
                 "يحدثان", "اخبرتهم", "حدثتهم", "يذكر", "يحدثه", "يروي", "يرويه", "تحدث", "حدث", "اخبروني", "حدثوني")
_FILLER_RE = re.compile(
    r"(?:[\s،,:;.\u200f\u200e\"'-]|(?:" + "|".join(_FILLER_WORDS) + r")(?!\w)|و(?=\s))+"
)
# (the Sunni books also pass over an honorific: "أن ابن عباس ـ رضي الله عنهما ـ أخبره أن أبا سفيان أخبره")
_SUNNI_FILLER_RE = re.compile(
    r"(?:[\s،,:;.\u200f\u200e\"'-]|(?:" + "|".join(_FILLER_WORDS) + r"|رضي الله (?:تعالي )?عن(?:هما|هم|ها|ه)|رحمه الله)(?!\w)"
    r"|و(?=\s))+"
)
_PROPHET_RE = re.compile(r"(?<!\w)(?:رسول الله|النبي|نبي الله)(?!\w)")
# the Prophet named by his kunya or an epithet: "سمعت أبا القاسم ﷺ", "حدثني خليلي", "حدثنا الصادق المصدوق ﷺ",
# "سمعت حبي أبا القاسم ﷺ", "عن محمد ﷺ" — never a narrator (al-Siddiq's son Muhammad was also "Abu al-Qasim": 29
# links of Abu Hurayra had been given to him)
_SALAWAT = r"(?:صل[يى] الله عليه و?سلم|ﷺ)"
_PROPHET_NAME_RE = re.compile(
    r"(?<!\w)(?:(?:(?:حبي|خليلي)\s+)?(?:(?:ابا|ابو|ابي) القاسم|محمدا?|رسول رب العالمين)[\s،,]*(?:نبي التوبه[\s،,]*)?"
    r"(?:الصادق المصدوق[\s،,]*)?" + _SALAWAT + r"|(?:(?:حبي|خليلي)\s+)?الصادق المصدوق(?!\w)|(?:حبي|خليلي)(?!\w)(?!\s+(?:بن|ابن)(?!\w)))")
_HONORIFIC_TAIL_RE = re.compile(r"^[\s،,\-]*(?:رضي الله (?:تعالي )?عن(?:هما|هم|ها|ه)|رحمه الله|عليه السلام)[\s\-]*")
_COMPANION_HONOR_RE = re.compile(r"^[\s،,(\-]*رضي الله (?:تعالي )?عن(?:هما|هم|ها|ه)(?!\w)")
_OF_PROPHET = (r"(?:زوج|زوجه|مولي|مولاه|صاحب|خادم|ابنه|بنت|ابن عم|ابن اخي|عم|خال|ربيب|ربيبه|حب|حواري|كاتب|موذن|سفينه|"
               r"ختن|ابن|ام المومنين|من اصحاب|اصحاب|بعض اصحاب|بعض ازواج|ازواج|اهل) (?:النبي|رسول الله|نبي الله)(?:\s*" + _SALAWAT + ")?")
_OF_PROPHET_RE = re.compile(r"(?<!\w)" + _OF_PROPHET)
_OF_PROPHET_START_RE = re.compile(r"^[\s،,\-]*(?:" + _OF_PROPHET + r"|ام المومنين)[\s،,\-]*")
_GENERIC_TRANSMITS_RE = re.compile(r"^[\s،,:]*(?:حدث\w*|اخبر\w*|يحدث\w*|(?:قال|يقول)[\s،,:]*(?:سمعت|حدثني|اخبرني))(?!\w)")
# (but "أخبرني مَن شهد النبي ﷺ", "عن مَن سمعه", "مَن هو خير مني" are a narrator not named: "من" stays a name before a verb)
_SENTENCE_START_RE = re.compile(r"^(?:في|من(?=\s+(?:ال\w+|سنه|رسول|النبي|نبي|ابي|ابيه|ام|ابن|بني|عند|حديث)(?!\w))|ما|لا|لم|لن|قد|اذا|اذ|لما|هذا|هذه|ذلك|تلك|الذي|التي|الذين|اخر|اول|كل|بعد|قبل|حتي|ثم|"
                                r"كان|كانت|كانوا|ليس|حديث|اهل الجاهليه)(?!\w)")
_HEARD_FROM_RE = re.compile(r"من\s+(?!(?:شهد|سمع|سمعه|سمعها|مر|صلي|راي|حضر|لا|هو|اثق|اصدق|ادرك|كان|حدثه|اخبره|حدثني|اخبرني|"
                            r"سال|صحب|يرضي|لقي|السنه|سنه)(?!\w))(?=\S)")
_HA_END_RE = re.compile(r"[\s\u200f\u200e.(]+ح\)?[\s\u200f\u200e،,.]*$")
_LONE_HA_RE = re.compile(r"[\s\u200f\u200e.(]*ح\)?[\s\u200f\u200e،,.]*")
_PARALLEL_TERMS = ("'an", "haddathana", "haddathani", "akhbarana", "akhbarani", "anba'ana", "anba'ani", "sami'tu")
_FROM_PROPHET_RE = re.compile(r"^[\s،,:]*(?:ان|عن)\s+(?:النبي|رسول الله|نبي الله)(?!\w)")
_HEARD_DOING_RE = re.compile(r"^[\s،,]*(?:يقرا|يقرو\w*|يقرءو\w*|يتلو|يلبي|يوذن|يدعو|ينشد|يصلي|يرتجز|يغني|يصيح|ينادي)(?!\w)")
_LONE_GENERIC_RE = re.compile(r"^(?:رجلا|امراه|ناسا|اعرابيا|قوما|رهطا|نفرا|غلاما|جاريه|يهوديا)$")
_NOT_A_NAME_RE = re.compile(r"^(?:انه|انها|انهما|انهم|انهن)(?!\w)")
_BARE_KUNYA_RE = re.compile(r"^(?:ابا|ابو|ابي) القاسم$")
# what follows the subject of "أنّ" when he is the one the story is about, not the next narrator: he speaks TO the
# Prophet or to someone ("أن سعد بن عبادة قال لرسول الله ﷺ", "أن حمزة بن عمرو قال يا رسول الله", "أن فاطمة بنت أبي
# حبيش قالت يا رسول الله", "أن هرقل قال له") — 2026-10-18: these had made Abu Hurayra a student of Sa'd b. Ubada
_STORY_SPEECH_RE = re.compile(
    r"^[\s،,:\-]*(?:و|ف)?(?:قال|قالت|قالا|يقول|تقول)[\s،,:]*(?:يا(?!\w)|ل(?:رسول|لنبي|نبي)|للنبي|(?:له|لها|لهم|لهما)(?!\w))")
# the first word after that subject when he goes on to transmit: "أن ابن عمر قال", "أن أبا هريرة حدثه",
# "أن عائشة أخبرته", "أن جابرا كان يقول", "أن عمر رفعه"
_ANNA_NARRATES_RE = re.compile(
    r"^[\s،,:\-]*(?:(?:قد\s+)?كان(?:ت)?\s+)?(?:و|ف)?(?:قال|قالت|قالا|يقول|تقول|يقولان|حدث\w*|اخبر\w*|يحدث\w*|"
    r"يخبر\w*|سمع\w*|زعم|رفع\w*|يرفع\w*|يبلغ|بلغ\w*|حدثت\w*|انه|انها|انهما|انهم)(?!\w)")
_ANNA_NAME_VERB_RE = re.compile(r"(?<!\w)(?:حدث\w*|اخبر\w*|يحدث|سمع|سمعه|سمعها|سمعته|انه|انها|انهما)$")
_HONORIFIC_RE = re.compile(r"\s*(?:رضي الله (?:تعالي )?عن(?:هما|هم|ها|ه)|رحمه الله|عليه السلام)")
_TAHWIL_RE = re.compile(r"(?<!\w)ح(?!\w)")
_JOINT_START_RE = re.compile(r"و(?!(?:كان|كانت|هو|هي|قد|لم|لا|ذلك|في|كنا|كنت)(?!\w))(?!\s)\w")   # "وابو بكر", "وهناد" …
_JOINT_WORD_RE = re.compile(r"(?<!\w)(?:قالا|قالوا|كلاهما|جميعا|المعني|وحديثه|حديثهما|لفظ)(?!\w)")
_DESCRIPTOR_RE = re.compile(
    r"[،,]?\s*(?:مولي|ختن|زوج|صاحب|كاتب|قاضي|ابن اخي|ابن اخت|ابن عم|اخي|اخو|اخت|"
    r"(?:رجل|امراه|شيخ)?\s*من (?:بني|اهل|ابناء|اصحاب|الانصار|المهاجرين|قومه|ولد))(?!\w)")
_NARRATES_RE = re.compile(r"(?<!\w)(?:قال|قالت|حدث|حدثه|حدثها|حدثهم|حدثته|اخبر|اخبره|اخبرهم|اخبرته|سمع|يقول|تقول|يحدث|رفعه)(?!\w)")
_GENERIC_SUBJECT_RE = re.compile(
    r"(?:رجلا|رجل|امراه|اعرابيا|اعرابي|ناسا|رهطا|قوما|نفرا|غلاما|جاريه|اصحاب|اهل|يهوديا|يهود|جبريل|جبراييل|جبرييل|"
    r"ملكا|الملك|الملايكه)(?!\w)")
# a transmission term soon after the point where reading stopped: the chain goes on
_CONTINUES_RE = re.compile(r"^(?:[^\s.]+\s+){0,8}?(?:و)?(?:(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|سمعت|زعم)\s+(?!(?:من )?(?:النبي|رسول|نبي))[^،,\s]|عن\s+(?!(?:ال)?(?:"
                           # "عن" before what was asked about, not a narrator ("سئل عن نبيذ الجر", "عن يسار النبي ﷺ")
                           r"صلاه|صلاته|صوم|صيام|حديث|شيء|ذلك|هذا|هذه|الذي|التي|قول|قوله|قولها|رجل يصلي|دبر|مرض|يمين|يمينه|يسار|يساره|نبيذ|"
                           r"اتباع|اكل|حجه|حج|استلام|بيع|غسل|مسح|قراءه|مسير|وضوء|دم|ركوب|كراء|صدقه|وتر|متعه|قتل|رويا|فريضه|"
                           r"اشياء|حايض|مياثر|متلاعنين|امر|مساله|ثلاث|الطاعون|طاعون|الفطر|عزل|العزل|سبب|سنه|ماء|نوم|اللقطه|"
                           r"خمر|زكاه|شرب|نكاح|طلاق|عمره|ثمن|تفسير|معني|جنازه|الجنازه|اذان|غناء|ضب|ضباب|فرس|البعير|بعير)(?!\w))[^،,\s])")
_MAX_NAME_WORDS = 13
# what may stand before the first term: a number ("11 - ", "5ـ"), a brace or a quote, and the reporter's own "قال"
# (Abdullah b. Ahmad in the Musnad: "قال حدثنا عبد الصمد"; "قال قرأت على عبد الرحمن")
_SUNNI_PREAMBLE_RE = re.compile(
    r"^[\s{}\[\]().،,\"'\u200f\u200e\-]*(?:\d+\s*[-ـ.)]?\s*)?(?:و\s+(?=(?:حدثنا|حدثني|اخبرنا|اخبرني|قال|عن)(?!\w)))?"
    r"(?:و?قال\s*:?\s*(?=و?(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|انباني|"
    r"سمعت|قرات علي|قري علي|عن)(?!\w)))?")
# a second narrator at the same link, before the next term: "حدثنا أيوب، ويونس، عن الحسن",
# "حدثنا عثمان، وأبو بكر ابنا أبي شيبة قالا حدثنا", "عن أبيه، ونافع، عن ابن عمر" (qiran)
_CO_JOINED = (r"(?:(?:(?:ابنا|ابني) [^،,.:\-]{2,40}?|قالا|قالوا|كلاهما|كلهم|جميعا|انهما|انهم|اخبراه|حدثاه|اخبروه|حدثوه|يحدثان|حدثه|اخبره|حدثهم|"
              r"اخبرهم|اخبروني|حدثوني|اخبراني|حدثاني)[\s،,]*)*")
_CO_TERMS = r"(?:حدثنا|حدثني|ثنا|اخبرنا|اخبرني|انبانا|انباني|حدثتنا|حدثتني|اخبرتنا|اخبرتني|سمعت|سمعا|سمعوا|عن|ان)"
_CO_NEXT = (r"(?<!\w)(?:و?" + _CO_TERMS + r"(?!\w)|و?قال[\s،,]+(?:[^،,.:\-]{1,30}?[\s،,:]*)?" + _CO_TERMS + r"(?!\w)|-\s*قال\s)")
# (and "يحيى بن أيوب، وقتيبة، وابن حجر عن إسماعيل": the third named before the term)
# (a note in dashes may stand before "قالا": "حدثنا سليمان بن حرب، ومسدد، - المعنى - قالا حدثنا حماد", "- واللفظ لحرملة -")
_CO_NOTE = r"(?:-[^-]{1,80}-[\s،,]*)?"
_CO_NARRATOR_RE = re.compile(
    r"[\s،,]*و(?!\s)([^،,.:\-]{2,60}?)[\s،,]*" + _CO_NOTE + _CO_JOINED +
    r"(?=" + _CO_NEXT + r"|(?<![^\s،,])و(?!\s)[^،,.:]{2,60}?[\s،,]*" + _CO_NOTE + _CO_JOINED + "(?:" + _CO_NEXT +
    r"|(?<![^\s،,])و(?!\s)[^،,.:]{2,60}?[\s،,]*" + _CO_NOTE + _CO_JOINED + _CO_NEXT + "))")
# two at the last link, both telling it: "حدثني سعيد بن المسيب، وأبو سلمة قالا قال رسول الله ﷺ"
_CO_LAST_RE = re.compile(r"[\s،,]*و(?!\s)([^،,.:\-]{2,50}?)[\s،,]*" + _CO_NOTE + r"(?=(?:قالا|قالوا)(?!\w))")


@dataclass
class Link:
    position: int
    term: str
    raw_name: str
    fresh: bool = False               # a full stop or a tahwil sign stands before it: perhaps a road begun again


@dataclass
class ParsedIsnad:
    raw_isnad: str = ""
    links: list[Link] = field(default_factory=list)
    reaches_prophet: bool = False     # reaches the source of its tradition: the Prophet; on road B also an Imam
    problem: str = ""                 # empty when parsed; otherwise why no links were stored
    ends_with: str = ""               # traditions.MASUM key of whom the chain reaches ("prophet", "sadiq" …)
    raised: bool = False              # "رفعه": raised to the Ma'sum without the rest of its links
    joined: int = 0                   # roads joined by "جميعاً" (the first road is the one stored)
    alternates: list = field(default_factory=list)   # (link index, Link): a second narrator at that link (qiran)
    parallel_at: int = -1             # where a second road begins with "وعن" / "وحدثنا" … after a link (index in text)
    parallel_kind: str = ""           # "an" ("وعن فلان"), "first" ("وحدثنا فلان"), "said" ("قال وحدثنا فلان")


_NAME_COMMA_RE = re.compile(r"(?<!\w)(و?ابن)،|(?<=\S)،(?=\s*بن\s)|(?<!\w)(و?(?:ابي|ابو|ابا|ام|عبد|بن))،(?=\s*(?!(?:عن|ان|حدثنا|"
                            r"حدثني|اخبرنا|اخبرني|انبانا|قال|قالت|سمعت|يقول|رضي|ح)(?!\w))[^\s،,\-.])")
_TATWEEL_DASH_RE = re.compile(r"(?<=\s)\u0640(?=\s)")
_BLESSING_DASHES_RE = re.compile(r"-(\s*(?:صلي الله عليه و?سلم|رضي الله (?:تعالي )?عن(?:هما|هم|ها|ه)|عليه السلام)\s*)-")
# words in a chain that name no one and only say how it was heard, blanked (spaces, so every position still maps back):
# "قال هذا ما حدثنا أبو هريرة" (Hammam's sheet), "- فيما قرئ عليه -", "قراءة عليه وأنا أسمع", "{ عن هشام }"
_BLANK_RE = re.compile(r"(?<!\w)هذا ما(?=\s+حدثنا(?!\w))|-?[\s\u200f\u200e]*فيما (?:قري|قرا|قريت) عليه[\s\u200f\u200e]*-?|"
                       r"(?<!\w)قراءه عليه(?:\s+وانا اسمع)?(?!\w)|(?<!\w)وانا اسمع(?!\w)|[{}]|(?<!\w)بخط يده(?!\w)|"
                       # Abd Allah b. Ahmad: "قال عبد الله وسمعته أنا من هارون" (he heard it from the teacher himself too);
                       # "قال سمعته يقول سمعت النعمان": the narrator heard him say
                       r"(?<!\w)قال (?:عبد الله|ابو عبد الرحمن)(?: بن احمد)? وسمعته انا (?:منه|من \S+(?: بن \S+){0,3})(?: مثله سواء)?|"
                       r"(?<!\w)(?:سمعته وحدي|مضروب عليه|سمعته منه)(?!\w)|(?<!\w)(?:سمعته|سمعتها) (?:يقول|يحدث|يذكر|تقول|تحدث)(?!\w)|"
                       # "- واللفظ له -" in Nasa'i without its dashes; "في حديثه عن", "غير مرة عن الزهري", "ثقة حدثنا"
                       r"(?:-[\s،,]*)?(?<!\w)واللفظ[\s،,]*(?:له|لها|لهما)(?!\w)(?:[\s،,]*-)?|(?<!\w)وذكر[\s،,]*اخر(?:\s+قبله)?(?!\w)|"
                       r"(?<!\w)او\s+(?:قال\s+)?(?:حدثني|حدثنا|اخبرني|اخبرنا|سمعت)(?!\w)|-\s*او [^-]{1,30}-|(?<!\w)يزيد احدهما علي صاحبه(?!\w)|"
                       r"(?<!\w)من كتابه(?=[\s،,]*(?:حدثنا|اخبرنا|اخبرني|حدثني)(?!\w))|(?<!\w)(?:في حديثه|لم يسمه|لم يسمها|غير مره|مرارا|"
                       r"وكان ثقه|ثقه)(?=[\s،,:]*(?:قال[\s،,:]*)?(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|عن|سمعت)(?!\w))")


def _norm_map(text: str) -> tuple[str, list]:
    """The normal form for reading a Sunni chain, with the comma some editions put inside a name taken out ("وابن،
    عباس", "زهير، بن حرب": 1,300 in the first lines of the isnady-data texts) — a space in its place, so that every
    position still maps back to the text."""
    # al-Bukhari's asides stand between two "ـ" ("عن أبي عبيد ـ اسمه سعد بن عبيد ـ"), which the normal form drops:
    # read as dashes (one character for one, so every position still maps back)
    norm, index_map = normalize_with_map(_TATWEEL_DASH_RE.sub("-", text))
    norm = _NAME_COMMA_RE.sub(lambda m: (m.group(1) + " ") if m.group(1) else ((m.group(2) + " ") if m.group(2) else " "), norm)
    # (but "ـ صلى الله عليه وسلم ـ", "ـ رضي الله عنهما ـ" are a blessing in those marks, not an aside)
    norm = _BLESSING_DASHES_RE.sub(lambda m: " " + m.group(1) + " ", norm)
    return _BLANK_RE.sub(lambda m: " " * len(m.group(0)), norm), index_map


def _tahwil_before(norm: str, end: int) -> bool:
    """A tahwil sign (a lone ح) before `end`. Looked for in the whole text: a slice cut just after the first letter
    of "حدثنا" or "حتى" left a lone "ح" at its end, and 525 chains of the full isnady-data were taken for tahwil."""
    return any(m.start() < end for m in _TAHWIL_RE.finditer(norm))


def _tahwil_at(norm: str, pos: int) -> bool:
    """The tahwil sign right at pos (after spaces and commas)."""
    while pos < len(norm) and norm[pos] in " \t،,":
        pos += 1
    return (pos < len(norm) and norm[pos] == "ح" and (pos == 0 or not norm[pos - 1].isalnum())
            and (pos + 1 >= len(norm) or not norm[pos + 1].isalnum()))


def _clean_name(original: str) -> str:
    return original.strip(" \t\n\u200f\u200e،,:;.-\"'()").strip()


def parse(text: str, tradition: str | None = None) -> ParsedIsnad:
    """Read the chain at the head of an Arabic text, along the road of the book's tradition (the first road, when the
    text gives several: parse_all)."""
    if tradition == "shia":
        return _parse_shia(text)
    return parse_all_sunni(text)[0]


TAHWIL = N_("tahwil (a second chain joins); not split in version 1")
SECOND_CHAIN = N_("a second chain follows the first; not split in version 1")
# Bukhari's own voice before a second road: "ح قال أبو عبد الله: وقال ابن وهب أخبرنا يونس …"
_COMPILER_SAYS_RE = re.compile(
    r"^[\s،,:.()\u200f\u200e\"]*(?:و?قال\s+(?:ابو عبد الله|محمد بن اسماعيل|مسلم|ابو داود|ابو عيسي|ابو عبد الرحمن)"
    r"(?:\s+البخاري)?[\s،,:]*|و?قال[\s،,:]*(?=و?(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا)(?!\w)))?")
# "وقال ابن وهب، أخبرنا …": a narrator cited without a term of hearing (ta'liq) opens the second road
_SAID_LINK_RE = re.compile(r"^[\s،,:]*و?قال\s+([^،,:]{2,60}?)\s*[،,:]?\s*(?=و?(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|عن|سمعت)(?!\w))")
_JOINED_RE = re.compile(r"(?<!\w)(?:قالا|قالوا|كلاهما|كلهم|جميعا|جميعهم)(?!\w)")
# a narrator called by two names in the two roads of one tahwil
_SAME_PERSON = [{"الزهري", "ابن شهاب", "محمد بن مسلم", "محمد بن مسلم بن شهاب", "محمد بن مسلم الزهري"},
                {"الاعمش", "سليمان", "سليمان بن مهران"}, {"الثوري", "سفيان الثوري", "سفيان بن سعيد"},
                {"ابن عيينه", "سفيان بن عيينه"}, {"ابو اسامه", "حماد بن اسامه"}, {"ابن جريج", "عبد الملك بن جريج"},
                {"ابو الزبير", "محمد بن مسلم بن تدرس"}, {"ابن المبارك", "عبد الله بن المبارك"},
                {"ابن علیه", "ابن عليه", "اسماعيل بن ابراهيم"}, {"ابن نمير", "عبد الله بن نمير"},
                {"وكيع", "وكيع بن الجراح"}, {"شعبه", "شعبه بن الحجاج"}, {"مالك", "مالك بن انس"},
                {"ابن عون", "عبد الله بن عون"}, {"ابن ابي ذيب", "محمد بن عبد الرحمن بن ابي ذيب"},
                # the Companions called "the son of …" in one road and by their name in the other (2026-10-25)
                {"ابن عمر", "عبد الله بن عمر", "عبد الله بن عمر بن الخطاب"}, {"ابن عباس", "عبد الله بن عباس"},
                {"ابن مسعود", "عبد الله بن مسعود"}, {"ابن عمرو", "عبد الله بن عمرو", "عبد الله بن عمرو بن العاص"},
                {"ابن الزبير", "عبد الله بن الزبير"}, {"ابن ابي اوفي", "عبد الله بن ابي اوفي"},
                {"ابن المسيب", "سعيد بن المسيب"}, {"ابن سيرين", "محمد بن سيرين"}, {"ابن بريده", "عبد الله بن بريده"},
                {"ابن ابي مليكه", "عبد الله بن عبيد الله بن ابي مليكه"}, {"ابن المنكدر", "محمد بن المنكدر"},
                {"عايشه", "ام المومنين عايشه"},
                # the compilers' teachers and their teachers, "Ibn X" in one road, by name in the other
                {"ابن وهب", "عبد الله بن وهب"}, {"ابن المثني", "محمد بن المثني"}, {"ابن بشار", "محمد بن بشار"},
                {"ابن مهدي", "عبد الرحمن بن مهدي"}, {"ابن ابي عدي", "محمد بن ابي عدي"}, {"ابن رمح", "محمد بن رمح"},
                {"ابن ابي شيبه", "ابو بكر بن ابي شيبه"}, {"ابن السرح", "احمد بن عمرو بن السرح"},
                {"ابن ابي عمر", "محمد بن يحيي بن ابي عمر"}, {"ابن ابي زايده", "يحيي بن زكريا بن ابي زايده"},
                {"ابن ادريس", "عبد الله بن ادريس"}, {"ابن فضيل", "محمد بن فضيل"},
                {"ابن ابي حازم", "عبد العزيز بن ابي حازم"}, {"ابن لهيعه", "عبد الله بن لهيعه"},
                {"ابن عجلان", "محمد بن عجلان"}, {"ابن اسحاق", "محمد بن اسحاق"},
                {"ابن ابي ليلي", "عبد الرحمن بن ابي ليلي"}, {"غندر", "محمد بن جعفر"}]


def _name_key(raw: str) -> str:
    name = normalize_name(raw)
    name = _JOINED_RE.sub(" ", name)
    name = re.sub(r"(?<!\w)(?:ابن)(?=\s)", "ابن", name)
    return " ".join(name.replace("،", " ").replace(",", " ").split())


def _same_narrator(a: str, b: str) -> bool:
    a, b = _name_key(a), _name_key(b)
    if not a or not b:
        return False
    if a == b:
        return True
    # a name in the accusative after "سمعت" / "أن": "أنسا", "جابرا" — the same man as "أنس", "جابر"
    a_bare, b_bare = re.sub(r"(?<=\w\w)ا$", "", a), re.sub(r"(?<=\w\w)ا$", "", b)
    if a_bare == b_bare and " " not in a_bare:
        return True
    # "ليث" and "الليث"; "أبي حيان" and "أبو حيان" (the kunya in another case): one man (2026-10-25, tahwil)
    def plain(x: str) -> str:
        x = re.sub(r"^(?:ابي|ابا) ", "ابو ", x)
        return x[2:] if " " not in x and x.startswith("ال") and len(x) > 4 else x
    if plain(a) == plain(b):
        return True
    def named(x: str, g: str) -> bool:           # "عائشة" or "عائشة رضي الله عنها", not "عائشة بنت طلحة"
        return x == g or (x.startswith(g + " ") and not re.match(r"(?:بن|بنت|ابن) ", x[len(g) + 1:]))
    for group in _SAME_PERSON:
        if any(named(a, g) for g in group) and any(named(b, g) for g in group):
            return True
    # "هشام" and "هشام بن عروه": the shorter is the start of the longer, and long enough to mean one man
    short, long_ = sorted((a, b), key=len)
    # (but "عائشة" and "عائشة بنت طلحة" are two women)
    return len(short) >= 4 and long_.startswith(short + " ") and " بن " not in short + " " \
        and not long_.startswith(short + " بنت ")


def parse_all(text: str, tradition: str | None = None) -> list[ParsedIsnad]:
    """Every chain at the head of the text: one, or several when a tahwil (ح) joins a second road to the first.
    The first is the road written first, completed with the links the roads share (2026-10-13; before, such a
    hadith had no chain at all — 1,599 of the full isnady-data)."""
    if tradition == "shia":
        return [_parse_shia(text)]
    return parse_all_sunni(text)


def _split_tahwil(text: str, depth: int = 0) -> list[ParsedIsnad] | None:
    norm, index_map = _norm_map(text)
    n = len(norm)
    at = next((m.start() for m in _TAHWIL_RE.finditer(norm, 0, min(n, 1500))
               if (m.end() >= n or not norm[m.end()].isalnum())), None)
    if at is None or depth > 4:
        return None
    cut = index_map[at] if at < n else len(text)
    road_a = _parse_sunni(text[:cut])
    if not road_a.links or road_a.problem:
        return None
    rest_norm_at = at + 1
    rest_start = index_map[rest_norm_at] if rest_norm_at < n else len(text)
    rest = text[rest_start:]
    rest_n = normalize_name(rest)
    # the compiler's own "قال أبو عبد الله" before the second road is not a link
    lead = _COMPILER_SAYS_RE.match(rest_n)
    said_link = None
    if lead and lead.end():
        rest = rest[_orig_len(rest, lead.end()):]
        rest_n = normalize_name(rest)
    said = _SAID_LINK_RE.match(rest_n)
    if said:
        said_link = said.group(1).strip()
        rest = rest[_orig_len(rest, said.end()):]
    roads = parse_all_sunni(rest, depth + 1)
    if not roads or not roads[0].links or roads[0].problem and roads[0].problem != SECOND_CHAIN \
            and not any(_shared(l.raw_name, road_a.links[-1].raw_name) for l in roads[0].links) \
            and len(roads[0].links) <= len(road_a.links):
        return None
    road_b = roads[0]
    if said_link:
        road_b.links.insert(0, Link(0, "qala", _clean_name(said_link)))
        for i, link in enumerate(road_b.links, 1):
            link.position = i
    # where the roads meet: at the narrator road A ends with, or else after the link followed by "قالا / كلاهما /
    # جميعاً" (2026-10-18: that came first, and "ح وحدثنا ابن المثنى وابن بشار قالا حدثنا محمد بن جعفر حدثنا شعبة"
    # met road A — "… غندر، عن شعبة" — at the two teachers, making Shu'ba a student of Muhammad b. Ja'far)
    meet = next((j for j, link in enumerate(road_b.links) if _shared(link.raw_name, road_a.links[-1].raw_name)), None)
    if meet is None:
        # "ح وحدثني إبراهيم بن المنذر، حدثنا محمد بن فليح، حدثني أبي": the father of Ibn Fulayh is Fulayh, with whom
        # road A ended (2026-10-25)
        for j, link in enumerate(road_b.links[1:], 1):
            if _name_key(_strip_said(link.raw_name)) in ("ابي", "ابيه"):
                son = _name_key(_strip_said(road_b.links[j - 1].raw_name))
                father = re.search(r"(?<!\w)بن (.+)$", son)
                if father and _same_narrator(father.group(1).split(" بن ")[0], _strip_said(road_a.links[-1].raw_name)):
                    meet = j
                    break
    if meet is None:
        meet = _meeting(road_b, rest)
    if meet is None and len(road_b.links) > len(road_a.links):
        # nothing names where they meet ("حدثنا حامد بن يحيى، أخبرنا سفيان، ح وحدثنا مسدد، حدثنا يحيى، عن ابن عجلان"):
        # the two roads are of one depth to there — Sufyan and Yahya both from Ibn Ajlan (2026-10-25)
        meet = len(road_a.links) - 1
    if meet is None:
        return None
    tail = road_b.links[meet + 1:]
    first = ParsedIsnad(raw_isnad=_clean_name(text[:len(text) - len(rest)] + road_b.raw_isnad),
                        links=[Link(i, l.term, _clean_name(_JOINED_RE.sub("", l.raw_name)), l.fresh)
                               for i, l in enumerate(road_a.links + tail, 1)],
                        reaches_prophet=road_b.reaches_prophet, ends_with=road_b.ends_with, raised=road_b.raised)
    for road in roads:
        road.raw_isnad = first.raw_isnad
        for link in road.links:
            link.raw_name = _clean_name(_JOINED_RE.sub("", link.raw_name))
    # "حدثنا أبو معاوية، ووكيع، ح": road A's second narrator at a link is a road of its own too
    first.alternates = [(i, Link(i + 1, l.term, _clean_name(_JOINED_RE.sub("", l.raw_name))))
                        for i, l in road_a.alternates if i < len(road_a.links)]
    return _expand(first) + roads


def parse_all_sunni(text: str, depth: int = 0) -> list[ParsedIsnad]:
    first = _parse_sunni(text)
    if first.parallel_at >= 0:
        roads = _split_parallel(text, first, depth)
    elif first.problem != TAHWIL:
        roads = _expand(first)
    else:
        roads = _split_tahwil(text, depth) or [first]
    out = []
    for road in roads:
        out.append(road)
        again = _cut_repeat(road)
        if again is not None:
            out.append(again)
    for road in out:
        # each road its own links, numbered from 1 (roads that meet share the links they have in common)
        road.links = [Link(i, l.term, l.raw_name, l.fresh) for i, l in enumerate(road.links, 1)]
    return out


def _begun_again(links: list, j: int, i: int) -> bool:
    """The narrator at j named again at i is the same man because the road was begun again, not a namesake ("حدثنا
    عبد الرحمن، حدثنا سفيان، عن عبد الرحمن": Ibn Mahdi, then Ibn Abis): the man after him is the same in both, or
    both the restart and the second mention are heard in the first person, or a narrator joined by "و" stands between."""
    if i + 1 < len(links) and _same_narrator(_strip_said(links[j + 1].raw_name), _strip_said(links[i + 1].raw_name)):
        return True
    if links[j + 1].fresh:
        return True
    return any(re.search(r"\sو(?:\S|$)", normalize_name(l.raw_name).strip()) for l in links[j:i])


def _cut_repeat(road: ParsedIsnad) -> "ParsedIsnad | None":
    """One narrator twice in one road means a second road was begun without a sign ("… حدثنا شعبة، عن محمد بن أبي
    المجالد، حدثنا حفص بن عمر، حدثنا شعبة، قال أخبرني محمد"): the two roads meet at him, so the road is read to his
    first mention and goes on from his second — no one is made the teacher of a man of the other road (2026-10-18).
    Not for a name and the same name right after it ("حماد عن حماد": Ibn Salama from Ibn Abi Sulayman), and not for
    "عبد الله" (Abd Allah b. Ahmad opens the chains he adds to the Musnad; Ibn Mas'ud ends many)."""
    for _ in range(4):
        keys = []
        for i, link in enumerate(road.links):
            key = _name_key(_strip_said(link.raw_name))
            if not key or _RELATIVE_RE.match(key) or len(key) <= 2 or key == "عبد الله":
                continue
            j = next((j for j, earlier in keys if earlier == key and i > j + 1 and _begun_again(road.links, j, i)), None)
            if j == 0:
                # begun again from its first narrator ("عن حجاج، عن أبي الزبير، عن جابر … عبد الله بن سعيد، حدثنا أبو
                # خالد، عن حجاج، عن عطاء"): two whole roads
                again = ParsedIsnad(raw_isnad=road.raw_isnad, links=road.links[i:], reaches_prophet=road.reaches_prophet,
                                    ends_with=road.ends_with, raised=road.raised, problem=road.problem)
                road.links = road.links[:i]
                road.reaches_prophet, road.ends_with = False, ""
                _cut_repeat(again)
                return again
            if j is not None:
                road.links = road.links[:j + 1] + road.links[i + 1:]
                break
            keys.append((i, key))
        else:
            return None
    return None



# words that name someone only through the narrator before them: never the same man in two roads
_RELATIVE_RE = re.compile(r"^(?:ابيه|ابيها|ابي|اباه|ابوه|امه|امها|امي|جده|جدته|جدي|جدتي|عمه|عمي|عمته|خاله|خالته|اخيه|اخته|"
                          r"اخي|ابن اخي|ابنه|ابنته|مولاه|مولاته|زوجه|زوجها|رجل|رجلا|امراه|من)$|^(?:بعض|رجل|رجلا|امراه|شيخ)(?!\w)")


def _shared(a: str, b: str) -> bool:
    """One narrator named in two roads ("عائشة" … "عائشة"); "his father" in two roads is two different men."""
    a_n, b_n = _name_key(_strip_said(a)), _name_key(_strip_said(b))
    if not a_n or not b_n or _RELATIVE_RE.match(a_n) or _RELATIVE_RE.match(b_n):
        return False
    if _same_narrator(a_n, b_n):
        return True
    # "جعفر بن عمرو بن أمية" and "جعفر بن عمرو بن أمية الضمري": a nasab of three names and a nisba after it
    short, long_ = sorted((a_n, b_n), key=len)
    if " " not in short and len(short) >= 3 and long_.startswith(short + " بن "):
        return True                                 # "سعد" and "سعد بن أبي وقاص" in two roads of one hadith
    if short.count(" بن ") >= 2 and long_.startswith(short + " ") and " بن " not in long_[len(short):] + " ":
        return True
    # "عبد الله بن مسلمة" and "عبد الله بن مسلمة القعنبي": a name and its nisba
    return short.count(" بن ") == 1 and re.fullmatch(re.escape(short) + r" ال\w+", long_) is not None


def _strip_said(raw: str) -> str:
    """A name without what follows it in the text: "عائشة، زوج النبي ﷺ", "ابن عمر حدثه" -> "عائشة", "ابن عمر"."""
    name = _OF_PROPHET_RE.sub(" ", normalize_name(raw))
    name = re.sub(r"(?<!\w)(?:حدث\w*|اخبر\w*|يحدث\w*|انه|انها|قال|قالت|يقول|تقول|رضي الله.*)$", " ", name)
    return name.strip(" ،,-")


def _is_companion(link: Link) -> bool:
    return is_companion_name(_strip_said(link.raw_name))


def _attach(a: list, road: ParsedIsnad, kind: str, joined_said: bool = False) -> tuple[list | None, list]:
    """Where the second road `road` joins the first `a` (the links read before "وعن" / "وحدثنا"): the road written
    whole, and the first road completed from it (a, unchanged, when the second gives it nothing). None: no place
    for the second road can be told, and it is left out rather than guessed.
      * a narrator in both roads: they meet there ("عن الزهري، عن عروة، عن عائشة، وعن هشام، عن أبيه، عن عائشة");
      * "وعن" after a Successor: a second teacher of the same student ("عن الزهري، عن سعيد، وعن الأعرج، عن أبي هريرة");
      * "وعن" after a Companion, the second road ending with a Companion: two roads of one length from the same
        narrator ("عن القاسم، عن عائشة، وعن نافع، عن ابن عمر");
      * "قال وأخبرني فلان": the last narrator goes on with a second teacher ("عن ابن شهاب، قال وأخبرني ابن المسيب");
      * "وحدثنا فلان" with no narrator shared: a second teacher of the one before the last."""
    b = road.links
    if not b:
        return None, a
    pairs = [(k, j) for k in range(len(a)) for j in range(len(b)) if _shared(a[k].raw_name, b[j].raw_name)]
    if pairs:
        # the earliest narrator of the second road named in the first: there it leaves the first ("عن الحجاج، عن مكحول،
        # عن أبي ثعلبة، والحجاج، عن الوليد …، عن أبي ثعلبة": at al-Hajjaj, not at Abu Tha'laba)
        k, j = min(pairs, key=lambda kj: (kj[1], -kj[0]))
        if k - j >= 1:
            whole = a[:k - j] + b
        elif k - j == 0 or kind in ("first", "said"):
            whole = list(b)                             # a road of its own from where the first began, meeting it at k
        else:
            return None, a
        last = [jj for kk, jj in pairs if kk == len(a) - 1]
        done = a + b[max(last) + 1:] if last else a     # the first road ends where they meet: it goes on as the second
        return whole, done
    last_companion = _is_companion(a[-1])
    if kind == "an":
        if last_companion and _is_companion(b[-1]) and len(a) > len(b):
            return a[:len(a) - len(b)] + b, a
        if not last_companion:
            done = a + b[1:] if len(b) > 1 and not _RELATIVE_RE.match(_name_key(b[1].raw_name)) \
                and not _shared(b[1].raw_name, a[-1].raw_name) else a
            return a[:-1] + b, done
        return None, a
    if last_companion:
        return None, a                                  # a Companion does not say "and so-and-so told me"
    if kind == "said":
        return a + b, a + b                             # the same chain read on: one road
    # "حدثنا عفان، وحدثني بهز، قالا حدثنا أبو عوانة": two teachers of one student, both from the next
    joined = len(b) > 1 and (_JOINED_RE.search(normalize_name(b[0].raw_name)) or joined_said)
    if len(a) == 1 and not joined:
        return a + b, a + b                             # "حدثنا محمد بن عبد الله أبو أحمد وحدثنا مسعر": read on
    return a[:-1] + b, (a + b[1:] if joined else a)


def _split_parallel(text: str, first: ParsedIsnad, depth: int) -> list[ParsedIsnad]:
    """A chain with a second road joined by "وعن" / "وحدثنا" after a link: each road its own chain, the first
    completed from the second where they meet (2026-10-18)."""
    rest = text[first.parallel_at:]
    read = "عن " + rest[1:] if first.parallel_kind == "co" else rest       # "وأبي الزناد، عن …" → "عن أبي الزناد، عن …"
    roads = parse_all_sunni(read, depth + 1) if depth < 6 else []
    roads = [r for r in roads if r.links]
    a = first.links
    out_first = ParsedIsnad(raw_isnad=first.raw_isnad, links=list(a), reaches_prophet=first.reaches_prophet,
                            ends_with=first.ends_with, raised=first.raised, alternates=first.alternates)
    others: list[ParsedIsnad] = []
    completed = False
    for road in roads:
        whole, done = _attach(a, road, "an" if first.parallel_kind == "co" else first.parallel_kind,
                              bool(re.match(r"[^،,]{0,90}?(?<!\w)(?:قالا|قالوا|كلاهما|جميعا)(?!\w)", normalize_name(read)[3:])))
        if whole is None:
            continue
        if done is not a and not completed:
            out_first.links = done                      # it ends where the second road ends
            out_first.reaches_prophet = out_first.reaches_prophet or road.reaches_prophet
            out_first.ends_with = road.ends_with or out_first.ends_with
            completed = True
        if whole == done:
            continue                                    # "قال وأخبرني": one road read on
        others.append(ParsedIsnad(raw_isnad="", links=whole, reaches_prophet=road.reaches_prophet,
                                  ends_with=road.ends_with, raised=road.raised, problem=road.problem))
    if not out_first.reaches_prophet and out_first.links and _is_companion(out_first.links[-1]) \
            and any(r.reaches_prophet for r in roads):
        out_first.reaches_prophet, out_first.ends_with = True, "prophet"   # "… عن جابر، وعن أبي صالح، عن أبي هريرة، قالا"
    raw = _clean_name(text[:len(text) - len(rest)] + (roads[-1].raw_isnad if roads else ""))
    out = []
    for p in [out_first] + others:
        p.raw_isnad = raw
        p.links = [Link(i, l.term, _clean_name(_JOINED_RE.sub("", l.raw_name)), l.fresh) for i, l in enumerate(p.links, 1)]
        out.append(p)
    expanded = []
    for p in out:
        expanded.extend(_expand(p) if p is out_first else [p])
    return expanded


def _expand(p: ParsedIsnad) -> list[ParsedIsnad]:
    """A chain with a second narrator at a link (qiran: "حدثنا أيوب، ويونس، عن الحسن") is two chains: the same
    links, that one replaced (2026-10-13; before, such a hadith had no chain drawn at all)."""
    out = [p]
    for index, other in p.alternates:
        if index >= len(p.links):
            continue
        links = [Link(l.position, l.term, l.raw_name, l.fresh) for l in p.links]
        links[index] = Link(index + 1, links[index].term, other.raw_name, links[index].fresh)
        out.append(ParsedIsnad(raw_isnad=p.raw_isnad, links=links, reaches_prophet=p.reaches_prophet,
                               problem=p.problem, ends_with=p.ends_with, raised=p.raised))
    return out


def _orig_len(text: str, norm_len: int) -> int:
    """How many characters of the original text make the first norm_len characters of its normal form."""
    norm, index_map = normalize_with_map(text)
    return index_map[norm_len] if norm_len < len(index_map) else len(text)


def _meeting(road: ParsedIsnad, rest: str) -> int | None:
    """The link after which "كلهم / كلاهما / جميعاً" — or else "قالا / قالوا" — stands in the second road: there the
    roads meet. "قالا" after two narrators of the second road joins those two, not the roads (2026-10-18: "ح وحدثني
    زهير بن حرب وعبيد الله بن سعيد قالا حدثنا يحيى … كلهم عن عبيد الله" had met road A at Yahya, making him a
    teacher of the man road A ends with)."""
    norm = normalize_name(rest)
    found: list[tuple[int, str]] = []
    pos = 0
    for j, link in enumerate(road.links):
        key = normalize_name(link.raw_name)
        joined = _JOINED_RE.search(key)
        if joined:
            found.append((j, joined.group(0)))
            continue
        at = norm.find(key, pos) if key else -1
        if at == -1:
            continue
        pos = at + len(key)
        gap = norm[pos:pos + 25]
        nxt = _TERM_RE.search(gap)
        joined = _JOINED_RE.search(gap[:nxt.start()] if nxt else gap)
        if joined:
            found.append((j, joined.group(0)))
    def own(j: int, word: str) -> bool:
        """The word joins the second road's own narrators at link j ("حدثنا أبو كريب وإسحاق جميعاً عن وكيع")."""
        pair = sum(1 for index, _ in road.alternates if index == j)
        return pair >= (2 if word in ("قالوا", "كلهم", "جميعهم") else 1)

    for j, word in found:
        if word in ("كلهم", "كلاهما", "جميعا", "جميعهم") and not own(j, word):
            return j
    for j, word in found:
        if word in ("قالا", "قالوا") and not own(j, word):
            return j
    # "حدثنا أبي ومحمد بن بشر قالا جميعا حدثنا هشام": the word joins the pair, and the pair meets road A there
    return found[-1][0] if found else None


# an aside in dashes after a link: the compiler's note on whose wording it is, or how each teacher said it
_ASIDE_RE = re.compile(r"[\s،,]*-\s*(?:و?قال|و?اللفظ|ولفظ|لفظ|و?هذا (?:حديث|لفظ)|وتقاربا|وتقاربوا|و?في روايه|و?المعني)"
                       r"[^-]{0,160}-|"
                       # "- رجل من طيئ -", "- مولى لهم -", "- يعنيان الثقفي -", "- بصري -", "- في حديث هشام -": a word on
                       # the narrator just named, followed by the next term
                       r"[\s،,]*-\s*(?!(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|عن|سمعت|ح)(?!\w))[^-]{1,80}-"
                       r"(?=[\s،,]*(?:و?قال[\s،,]*)?(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|عن|سمعت|ان|قالا|قالوا|كلاهما|جميعا|ح)(?!\w))")
# where a name ends when no comma closes it (the Musnad has none): "عن أبي بكر أنه سمعه حين …", "عن عائشة أنها كانت
# تقول", "سمعت سليم بن عامر رجلا من أهل حمص وكان قد أدرك …" (2026-10-25)
_NAME_STOP_RE = re.compile(r"(?<!\w)(?<!عمن )(?:بهذا|بمثله|بمثل|بنحوه|نحوه|مثله|باسناد\w*|قال|قالت|قالا|يقول|تقول|انه|انها|انهما|انهم|كان|كانت|كنا|كنت|وكان|وكانت|يحدث|يخبر|"
                           r"حدثه|حدثها|حدثهم|اخبره|اخبرها|اخبرهم|فقال|فقالت|رجلا من|وهو من|وكان من|وقد|في|بخط|او|يساله|يسالها|يامره|اني|فكتب|يخبرني|حديث|وهما)(?!\w)|\s-|\s*[:؛(]")
# names that begin with "و" (not "and"): "وكيع", "وهب", "أبو وائل" …
_WAW_NAMES = {"وكيع", "وهب", "وهيب", "وايل", "واثله", "وداعه", "ورقاء", "وبره", "وحشي", "وابصه", "واقد", "وردان", "وضاح",
              "وهبان", "وعله", "وراد", "ورقه", "واصل", "وازع", "وقاص", "وقدان", "وكيل", "وهبه", "وليد", "ولاد", "وجزه",
              "وحوح", "وثاب", "وثيمه", "واسع", "وشاح", "وهب،"}
_ABOUT_RE = re.compile(r"[\s،,\-]*(?:(?:قال|قالت)\s+)?(?:وكان|وكانت|وهو|وهي|في (?:بيت|مسجد|سنه|مجلس|منزل|دار|قول)\S*|من اهل)\s(?:[^،,.:\-](?!(?:حدثنا|حدثني|اخبرنا|اخبرني|سمعت|عن)(?!\w))){2,70}?"
                       r"[\s،,\-]*(?:يقول|قال)?[\s،,]*(?=(?<!\w)(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|سمعت|عن)\s+\S)")
_TERMS_OF_HEARING = r"(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|انباني|سمعت|عن)"
# which teacher said which word, in a link of two or after it: "قال إسحاق أخبرنا وقال الآخران حدثنا جرير",
# "قال ابن أيوب حدثنا إسماعيل", "قال عفان عن ابن بريدة" — the words of one of the narrators already named
_WORDING_RE = re.compile(r"[\s،,\-]*و?قال[\s،,]*([^،,.:\-]{1,30}?)(?:[\s،,]+(?:وهو|وهي|يعني)\s[^،,.:\-]{1,60}?)?[\s،,:]*"
                         r"(?=" + _TERMS_OF_HEARING + r"(?!\w))")
_OTHERS = ("الاخران", "الاخرون", "الباقون", "الاخر", "الاخرين", "الباقيان")


_OR_RE = re.compile(r"[\s،,]*او\s+(?:عن\s+)?([^،,.:\-]{2,40}?)[\s،,]*(?:-\s*شك[^-]{0,40}-[\s،,]*|شك \S+[\s،,]*)?"
                    r"(?=(?<!\w)(?:قال|قالت|قالا|عن|حدثنا|حدثني|اخبرنا|اخبرني|ان|انه|انها|يقول|تقول|يحدث|يخبر|حدثه|اخبره|كان|"
                    r"كانت)(?!\w)|-|$)")


def _companion_prefix(norm: str, start: int, end: int) -> int | None:
    """Where a Companion's name ends when it opens a long run of words: "عائشة اختصم …" -> after "عائشة"."""
    spans = [m.span() for m in re.finditer(r"[^\s،,]+", norm[start:min(end, start + 80)])]
    for k in (4, 3, 2, 1):
        if len(spans) > k:
            name = norm[start:start + spans[k - 1][1]]
            if is_companion_name(name) and not _SENTENCE_START_RE.match(name):
                return start + spans[k - 1][1]
    return None


def _co_ok(co_name: str) -> bool:
    """A second narrator at a link, not a sentence ("وعمن حدثه", "وهو ابن …", the Prophet)."""
    return not (_TERM_RE.match(co_name) or _TERM_RE.search(co_name) or len(co_name.split()) > 7
                or _PROPHET_RE.search(co_name) or _NARRATES_RE.search(co_name)
                or re.match(r"(?:عمن|من|هو|هي|كان|غيره|غيرهما|غير واحد|ذكر)(?!\w)", co_name))


def _wording_of(name: str, named: list[str]) -> bool:
    """The name after "قال" is one of the narrators already named (or "the other two"): his wording, no link."""
    n = _name_key(_strip_said(name))
    if not n or len(n.split()) > 5:
        return False
    if n in _OTHERS:
        return True
    for other in named:
        o = _name_key(_strip_said(other))
        if not o:
            continue
        if _same_narrator(n, o) or o.startswith(n + " ") or o.endswith(" " + n) \
                or (n.startswith("ابن ") and (" بن " + n[4:]) in " " + o):
            return True
    return False


# "قال سألت عائشة", "قال سألنا جابرا", "قال سئل أنس" (normalised: سيل)
_ASKED_RE = re.compile(r"((?:سالت|سالنا|سيل|سيلت|سال)(?=\s)|قلت\s+ل(?=[^\s،,]+(?:\s+[^\s،,]+){0,4}?[\s،,:]+"
                       r"ا?(?:حدثكم|اخبركم|حدثك|اخبرك|اخبرني|اخبريني|حدثني|حدثيني)(?!\w)))\s*")
_ASKED_STOP_RE = re.compile(r"[،,.:]|(?<!\w)(?:عن|عما|فقال|فقالت|قال|قالت|هل|ما|كيف|في|اي|متي|اين|لم|ماذا|من|وهو|وهي|"
                            r"وانا|او|فقلت|قلت|رضي الله|حدثكم|اخبركم|احدثكم|اخبرك|حدثك|حدثني|اخبرني|حدثنا|اخبرنا|فحدثنا|فحدثني|"
                            r"فاخبرني|فقال|وهما|وهم|رجل|يوم|اخبريني|حدثيني|يا)(?!\w)")


# what is no one's name though it stands where a name would ("قال وعنه حدثنا", "وجدت في كتاب أبي: لم أسمعه منه")
_JUNK_NAME_RE = re.compile(r"(?:و|وعنه|وعنها|عنه|وباسناده|باسناده|بهذا|الا|وقد|قد|سمعته|سمعتها|مضروب|قلنا|قلت|هو|وهو|هي|وهي|"
                           r"انا|نحن|كان|وكان|لم|اكبر|اظن|ه|ها)(?!\w)")


def _said_name(norm: str, pos: int, allow_an: bool = False, depth: int = 0) -> tuple[str, int, int] | None:
    """After "قال": a name and right after it a term of transmission ("قال ابن جريج أخبرني", "قال إسحاق أخبرنا"):
    (the name as written, where the term begins, where the name begins); None when what follows is no such name.
    Also a name and "قال" again, when a term or another such name follows it: "قال قال إسرائيل قال أبو إسحاق عن زيد"
    (the Musnad); "قال لي ابن أبي نجيح عن مجاهد"; "قال كان محمد بن جبير يحدث عن معاوية"."""
    lead = re.match(r"[\s،,]*(?:لي|لنا|كان|و?ذكر)\s+", norm[pos:pos + 12])
    strong = allow_an or bool(lead)
    if lead:
        pos += lead.end()
    term = _TERM_RE.search(norm, pos, pos + 70)
    qala = re.compile(r"(?<!\w)قال(?!\w)").search(norm, pos, pos + 70)
    end_name = None
    if qala and (not term or qala.start() < term.start()) and depth < 4:
        after = qala.end()
        while after < len(norm) and norm[after] in " ،,:":
            after += 1
        nxt = _TERM_RE.match(norm, after)
        if not ((nxt and nxt.group(1) not in ("ان", "زعم")) or _said_name(norm, after, True, depth + 1)):
            return None
        end = qala.start()
    else:
        # "عن" after a name is too often "about" ("سئل سعيد عن الأعضب", "ذكر خلف عن …"): only the terms of hearing,
        # unless the name was itself quoted in a row of "قال", or said to the narrator, or tells it ("يحدث عن")
        if not term or term.group(1) in ("ان", "زعم"):
            return None
        end = term.start()
        verb = re.search(r"[\s،,]+(?:يحدث|يقول|يخبر|يذكر)[\s،,]*$", norm[pos:end])
        if verb:
            strong = True
            end_name = pos + verb.start()
        if term.group(1) == "عن" and not strong:
            # "قال الزهري عن سعيد، وأبي سلمة عن أبي هريرة": a chain goes on after the name he names
            if not re.match(r"عن\s+[^،,.:]{2,40}?[\s،,]+(?:و\S+[^،,.:]{0,30}?[\s،,]+)?(?:عن|حدثنا|حدثني|اخبرنا|اخبرني|ان|سمعت)(?!\w)",
                            norm[term.start():term.start() + 120]):
                return None
    name = norm[pos:end_name if end_name is not None else end]
    name = re.sub(r"(?:\s+و)+\s*$", "", name)          # "قال أبي و حدثنا": the "and" of a second road
    bare = name.strip(" ،,")
    words = bare.split()
    if _JUNK_NAME_RE.match(bare) or re.search(r"(?<!\w)(?:وسمعته|سمعته|وانا)(?!\w)", bare):
        return None
    if not words or len(words) > 6 or re.search(r"[.:]", bare) or _ASKED_RE.match(bare + " ") \
            or re.search(r"(?<!\w)(?:ممن|سل|اذهب|انظر|اسال|ايت)(?!\w)", bare) \
            or re.match(r"(?:قيل|ذكر|ذكره|ذكرت|بلغني|بلغنا|اتي|جاء|كتب|اخذ|راي|رايت|شهدت|وجدت|قرات|لما|ولما)(?!\w)", bare) or _PROPHET_RE.search(bare) \
            or _PROPHET_NAME_RE.search(bare) or _SENTENCE_START_RE.match(bare) or _NOT_A_NAME_RE.match(bare) \
            or re.search(r"(?<!\w)(?:قال|قالت|يقول|كان|كنا|كنت|لنا|لي|له|لها|في|ما|لا|اذا|حين|يوم|سمعت|حدث\w*)(?!\w)",
                         bare):
        return None
    return name.rstrip(" ،,"), end, pos


def _asked_name(norm: str, pos: int) -> tuple[int, int] | None:
    """The one asked ("سألت عائشة عن …"): (start, end) of his name, up to "عن", a question word or a comma."""
    stop = _ASKED_STOP_RE.search(norm, pos, pos + 80)
    end = stop.start() if stop else min(len(norm), pos + 40)
    honor = _HONORIFIC_RE.search(norm, pos, end)
    if honor:
        end = honor.start()
    while end > pos and norm[end - 1] in " ،,":
        end -= 1
    words = norm[pos:end].split()
    if not words or len(words) > 6 or _SENTENCE_START_RE.match(norm[pos:end]) or _GENERIC_SUBJECT_RE.match(norm[pos:end]) \
            or _LONE_GENERIC_RE.match(norm[pos:end]):
        return None
    return pos, end


def _parse_sunni(text: str) -> ParsedIsnad:
    norm, index_map = _norm_map(text)
    n = len(norm)

    def orig(a: int, b: int) -> str:
        start = index_map[a] if a < n else len(text)
        end = index_map[b] if b < n else len(text)
        return text[start:end]

    result = ParsedIsnad()
    head = norm[:1200]
    if not norm.strip():
        result.problem = N_("does not start with a transmission term")
        return result
    preamble = _SUNNI_PREAMBLE_RE.match(norm)
    pos = preamble.end() if preamble else 0
    first = _TERM_RE.match(head, pos) if pos < len(head) else None
    links: list[Link] = []
    ends: list[tuple[int, int]] = []      # (end before this link, end after it)
    end_of_chain = 0
    if not first:
        # "العاشر: عن ابن عباس" (Riyad numbers its hadith in words)
        ordinal = re.match(r"[\s\d{\[().،,\"'\u200f\u200e\-]*ال\w+(?:\s+\S+){0,2}?\s*:\s*", norm)
        if ordinal and _TERM_RE.match(head, ordinal.end()):
            pos = ordinal.end()
            first = _TERM_RE.match(head, pos)
    if not first:
        # al-Bukhari's own citations, and the like: "وقال الليث حدثني جعفر", "وقال لنا أحمد بن حنبل حدثنا يحيى",
        # "وزاد ابن أبي عدي عن شعبة" — the man cited is the first link, cited without a term (ta'liq)
        opening = re.match(r"[\s\d{\[().،,\"'\u200f\u200e\-]*و?(?:قال|زاد|رواه)\s+", norm)
        said = _said_name(norm, opening.end()) if opening else None
        if said is None and not opening and not _CITED_RE.match(norm):
            said = _said_name(norm, preamble.end() if preamble else 0)    # "عبد الصمد حدثني حماد" (its "حدثنا" lost)
        if said is None and _CITED_RE.match(norm):
            result.problem = NO_CHAIN
            return result
        if said is None:
            result.problem = N_("does not start with a transmission term")
            return result
        name_text, next_term_at, start = said
        links.append(Link(1, "qala", _clean_name(orig(start, start + len(name_text))), False))
        ends.append((0, start + len(name_text)))
        end_of_chain = start + len(name_text)
        pos = next_term_at
    skip_same = False                   # after "قال إسحاق أخبرنا جرير، وقال عثمان حدثنا جرير": Jarir once, not twice
    skipped_to = 0                      # the end of the last aside passed over
    while pos < n:
        wording = _WORDING_RE.match(norm, pos) if links else None
        if wording and _TERM_RE.match(norm, wording.end()) and _wording_of(wording.group(1), [l.raw_name for l in links] + [a.raw_name for _, a in result.alternates]):
            said_term = _TERM_RE.match(norm, wording.end())
            after_term = said_term.end()
            while after_term < n and norm[after_term] in " ،,-":
                after_term += 1
            if re.match(r"و?قال(?!\w)", norm[after_term:after_term + 5]):
                pos = after_term                    # "قال إسحاق أخبرنا وقال الآخران حدثنا جرير": the next wording
            else:
                pos = wording.end()                 # the term and the name the narrators share
                skip_same = True
            continue
        aside = _ASIDE_RE.match(norm, pos) if links else None
        if aside:
            # "- قال ابن نمير حدثنا سفيان -", "- واللفظ له -", "- وهذا حديثه -": the compiler's note on the wording,
            # no link (Muslim's way; 2026-10-25, "words not understood" in 26 + 23 + 18 … chains)
            pos = skipped_to = aside.end()
            continue
        about = _ABOUT_RE.match(norm, pos) if links else None
        if about and not _PROPHET_RE.search(about.group(0)) and not _PROPHET_NAME_RE.search(about.group(0)):
            # "حدثنا زهير بن عبد الله وكان عاملا على توج وأثنى عليه خيرا عن …", "سمعت كردوسا وكان قاصا يقول أخبرني":
            # a word on the narrator, no link
            pos = skipped_to = about.end()
            continue
        filler = _SUNNI_FILLER_RE.match(norm, pos)
        said_before = bool(filler and re.search(r"(?<!\w)قال(?!\w)", filler.group(0)))
        if filler:
            pos = filler.end()
        term = _TERM_RE.match(norm, pos)
        if not term and links:
            asked = _ASKED_RE.match(norm, pos)
            if asked and asked.group(1) == "سال" and not (filler and re.search(r"(?<!\w)(?:انه|انها)(?!\w)", filler.group(0))):
                asked = None                        # "سأل قتادة أنسًا": another asked, in the story
            if asked and not _PROPHET_RE.match(norm, asked.end()) and not _PROPHET_NAME_RE.match(norm, asked.end()):
                # "قال سألت عائشة عن صلاة …", "قال سئل أنس": the one asked is the narrator's teacher — the last link
                got = _asked_name(norm, asked.end())
                if got and norm[got[0]:got[1]].strip(" ،,"):
                    a, b = got
                    links.append(Link(len(links) + 1, "su'ila" if asked.group(1).startswith("سي") else
                                      "sa'ala" if asked.group(1) == "سال" else "sa'altu",
                                      _clean_name(orig(a, b)), False))
                    ends.append((end_of_chain, b))
                    end_of_chain = b
                    if asked.group(1).startswith("قلت") and re.match(r"[\s،,:]*ا?(?:حدثكم|اخبركم|حدثك|اخبرك)(?!\w)", norm[b:b + 12]):
                        pos = b                     # "قلت لأبي أسامة: حدثكم عبيد الله …؟": he goes on with his teacher
                        continue
            elif asked:
                result.reaches_prophet = True             # "سألت رسول الله ﷺ": the chain has reached him
            if asked:
                break
        told = filler and re.search(r"(?<!\w)(اخبره|حدثه|اخبرهم|حدثهم)[\s،,]*$", filler.group(0))
        colon = filler and ":" in filler.group(0) and links and links[-1].term in ("qara'tu 'ala", "quri'a 'ala")
        if not term and links and (told or colon):
            # "أنه أخبره أبو معبد مولى ابن عباس عن …"; "قرأت على عبد الرحمن: مالك عن أبي الزناد" (the Musnad)
            said = _said_name(norm, pos, True)
            if said is not None:
                name_text, next_term_at, start = said
                kind = ("haddathana" if told.group(1).startswith("حدث") else "akhbarana") if told else "'an"
                links.append(Link(len(links) + 1, kind, _clean_name(orig(start, start + len(name_text))), False))
                ends.append((end_of_chain, start + len(name_text)))
                end_of_chain = start + len(name_text)
                pos = next_term_at
                continue
        if not term and links and said_before:
            said = _said_name(norm, pos, links[-1].term == "qala")
            if said is not None:
                name_text, next_term_at, pos = said
                here = [links[-1].raw_name] + [alt.raw_name for i, alt in result.alternates if i == len(links) - 1]
                if any(_same_narrator(_strip_said(name_text), _strip_said(normalize_name(h))) for h in here):
                    # "حدثنا عثمان، وإسحاق، قال إسحاق أخبرنا جرير": which of the two said which word — no link
                    pos = next_term_at
                    skip_same = True
                    continue
                # "حدثنا حجاج، قال قال ابن جريج أخبرني محمد": Hajjaj quotes Ibn Jurayj, who goes on — a link
                start = pos
                links.append(Link(len(links) + 1, "qala", _clean_name(orig(start, start + len(name_text))), False))
                ends.append((end_of_chain, start + len(name_text)))
                end_of_chain = start + len(name_text)
                pos = next_term_at
                continue
        if not term:
            break
        term_id = _TERM_ID[term.group(1)]
        if links and term.group(0).startswith("و") and term_id in _PARALLEL_TERMS:
            # "… عن عروة، عن عائشة، وعن هشام بن عروة، عن أبيه، عن عائشة": a second road, not the next link
            # (2026-10-18: it had been read on as one chain — Hisham b. Urwa became a teacher of A'isha)
            result.parallel_at = pos
            result.parallel_kind = "an" if term_id == "'an" else ("said" if said_before else "first")
            break
        name_start = term.end()
        while name_start < n and norm[name_start] in " \t،,-":
            name_start += 1                         # ("حدثنا - سفيان": the close of a note on the wording)
        # "سمع من أبي هريرة", "سمعت من رسول الله ﷺ": "من" is "from", the name follows (but "أخبرني مَن شهد …",
        # "مَن هو خير مني" name someone not named)
        if term_id in ("sami'tu", "sami'a") and _HEARD_FROM_RE.match(norm, name_start):
            name_start = _HEARD_FROM_RE.match(norm, name_start).end()
        nxt_term = _TERM_RE.match(norm, name_start)
        if nxt_term and (links == [] or _TERM_ID[nxt_term.group(1)] not in ("anna", "za'ama")):
            # "وحدثني عن مالك" (the Muwatta): the one who says "haddathani" is not named; the chain starts at Malik.
            # So "قال هشام أخبرنا عن أبيه", "حدثني حدثنا سريج": the term with no name is the next one's
            pos = name_start
            continue

        # the Prophet ends the chain
        prophet = _PROPHET_RE.match(norm, name_start) or _PROPHET_NAME_RE.match(norm, name_start)
        if prophet:
            result.reaches_prophet = True
            break

        # the name runs to the next comma, the next term, or an honorific
        next_comma = min((i for i in (norm.find("،", name_start), norm.find(",", name_start)) if i != -1), default=n)
        next_term = _TERM_RE.search(norm, name_start)
        name_end = min(next_comma, next_term.start() if next_term else n)
        said = next((m for m in _NAME_STOP_RE.finditer(norm[name_start:name_end]) if m.start() > 0), None)
        if said:
            name_end = name_start + said.start()
        honor = _HONORIFIC_RE.search(norm, name_start, name_end)
        if honor:
            name_end = honor.start()
        elif next_term and name_end == next_comma < next_term.start() and _TERM_ID[next_term.group(1)] != "anna":
            # one man named twice, a comma between: "حدثني أبو خيثمة، زهير بن حرب حدثنا وكيع", "حدثنا محمد بن العلاء،
            # أبو كريب، حدثنا …" — his kunya and his name are one link (Bayram, 2026-10-24, Muslim 93: the chain
            # stopped at Abu Khaythama, "words not understood")
            seg_at = next_comma + 1
            while seg_at < next_term.start() and norm[seg_at] in " ،,":
                seg_at += 1
            seg = norm[seg_at:next_term.start()].strip(" ،,")
            # "حدثنا أبو أحمد، محمد بن عبد الله الزبيري قال حدثنا", "أبو الرجال، محمد بن عبد الرحمن حدثه عن": the
            # words of telling after the second name are not his
            seg = re.sub(r"(?:[\s،,]+(?:قال|قالت|يقول|حدثه|حدثهم|حدثها|حدثني|اخبره|اخبرهم|اخبرها|انه|انها|يحدث))+$", "", " " + seg).strip()
            first_words = norm[name_start:name_end].split()
            kunya_first = bool(first_words) and (first_words[0] in ("ابو", "ابا", "ابي", "ام", "ابن") or len(first_words) == 1)
            if seg and not seg.startswith("و") and len(seg.split()) <= 8 and not re.search(r"[،,.]", seg) \
                    and not re.search(r"(?<!\w)(?:قال|قالت|قالا|قالوا|يقول|يعني|هو|ح|حدث\w*|اخبر\w*|سمع\w*|يسال|يسل|"
                                      r"سال\w*|يقرا|يذكر|يخطب|يفتي|ام المومنين|زوج|يحدث\w*|يخبر\w*|انه|انها|انهم|انهما)(?!\w)", seg) \
                    and ((kunya_first and re.search(r" (?:بن|بنت) ", f" {seg} ")) or re.match(r"(?:ابو|ابا|ابي|ام) \S", seg)
                         or re.fullmatch(r"ال\S{2,}", seg)):        # "موسى بن سروان، المعلم حدثني": his nisba
                name_end = seg_at + len(seg)
        # a clarification in dashes right after the comma belongs to the name: "- يعني ابن محمد -"
        after = name_end
        desc = _DESCRIPTOR_RE.match(norm, name_end)
        if desc:
            nxt = _TERM_RE.search(norm, desc.end())
            nxt_comma = min((i for i in (norm.find("،", desc.end()), norm.find(",", desc.end())) if i != -1), default=n)
            name_end = min(nxt.start() if nxt else n, nxt_comma)
            # "أن عائشة، زوج النبي ﷺ قالت …": the descriptor ends where she speaks (2026-10-18: the whole sentence
            # had been taken for the name and the link dropped)
            said = re.search(r"(?<!\w)(?:قال|قالت|يقول|تقول|حدث\w*|اخبر\w*|انه|انها|انهما)(?!\w)|\s-", norm[desc.end():name_end])
            if said:
                name_end = desc.end() + said.start()
        if _LONE_HA_RE.fullmatch(norm[name_start:name_end]):
            break                                   # "قالا حدثنا ح، وحدثنا …": no name, a second road begins
        lone_ha = _HA_END_RE.search(norm[name_start:name_end])
        if lone_ha and lone_ha.start() > 0:
            name_end = name_start + lone_ha.start()         # "حدثنا أبي ح، وحدثنا …": the tahwil sign is no name
        core_norm = norm[name_start:name_end]
        clar = re.match(r"[،,]?\s*-\s*(?:و?يعني|و?هو)\s[^-]{1,150}-|[،,]?\s*(?:و?يعني|وهو)\s+(?:ابن|ابا|ابو|ال)[^،,.:\-]{0,60}?"
                        r"(?=[\s،,]*(?:حدثنا|حدثني|ثنا|اخبرنا|اخبرني|انبانا|سمعت|عن|قال)(?!\w))|[،,]\s*هو\s+(?:ابن|ال)"
                        r"[^،,.:\-]{0,60}?(?=[\s،,]*(?:حدثنا|حدثني|ثنا|اخبرنا|اخبرني|انبانا|سمعت|عن|قال|ان)(?!\w))",
                        norm[after:after + 170])
        if clar:
            name_end = after + clar.end()

        # two narrators at one link with no comma between (the Musnad): "حدثنا سفيان وشعبة عن …", "قتادة وثابت" —
        # the second is read as a second road at this link, as with a comma (2026-10-25)
        for waw in re.finditer(r"\sو(\S+)", core_norm):
            word = waw.group(1)
            if re.search(r"(?<!\w)(?:ابن|بن|ابي|ابو|ابا|ام|بنت|عبد)$", core_norm[:waw.start()]):
                continue                            # "ثابت بن وديعة", "أبي وائل": a name, not "and"
            if "و" + word in _WAW_NAMES or word in ("هو", "هي", "كان", "كانت", "سلم", "غيره", "غيرهما", "ذكر") \
                    or re.match(r"(?:اله|سلم)$", word):
                continue
            cut = name_start + waw.start()
            co = _CO_NARRATOR_RE.match(norm, cut) if cut > name_start else None
            if co and _co_ok(co.group(1).strip()):
                name_end = cut
                core_norm = norm[name_start:name_end]
            break
        words = core_norm.strip(" ،,:-").split()
        if links and term_id in ("wajadtu", "kataba", "balagha", "sa'ala") and _JUNK_NAME_RE.match(core_norm.strip(" ،,:-")):
            break
        if re.fullmatch(r"و?(?:قال|قالت|قالا|يقول)", core_norm.strip(" ،,:-")) and _TERM_RE.match(norm, name_end):
            pos = name_end                          # "أخبرني قال سمعت ابن أبي ليلى": no one is called "قال"
            continue
        if links and _NOT_A_NAME_RE.fullmatch(core_norm.strip(" ،,:-")) and _TERM_RE.match(norm, name_end):
            pos = name_end                          # "أخبرني أنه سمع جدته": "أنه" is no one; the chain goes on
            continue
        bare_core = _OF_PROPHET_RE.sub(" ", core_norm)      # "زوج النبي ﷺ", "مولى رسول الله ﷺ" name someone else
        if links and (_NOT_A_NAME_RE.match(core_norm.strip(" ،,:-")) or _SENTENCE_START_RE.match(core_norm.strip(" ،,:-"))
                      or term_id == "anna" and (
                _PROPHET_RE.search(bare_core) or _PROPHET_NAME_RE.search(bare_core))):
            break                                   # "زعم أنه سمعه منها", "أن إهلال رسول الله ﷺ …": the text has begun
        if re.search(r"\.\s*\S", core_norm.strip()):          # a sentence ends inside: a second chain follows
            result.raw_isnad = _clean_name(orig(0, min(n, name_end + 80)))
            result.problem = N_("a second chain follows the first; not split in version 1")
            result.links = links                     # the chain as far as it was read: shown, never hidden
            return result
        sons = sum(1 for w in words if w in ("بن", "بنت", "ابن"))
        if not words or (len(words) > _MAX_NAME_WORDS and not (len(words) <= 22 and sons * 3 >= len(words) - 2)) or (
                len(words) > 10 and sons < 3):
            # narrative has begun (a long name is a long nasab, 2026-10-25: "عبد الله بن أبي بكر بن محمد بن عمرو بن
            # حزم" is 11 words) — but a Companion named first is the last link: "عن عائشة اختصم عبد بن زمعة …" (the
            # Musnad has no comma to end the name)
            cut = _companion_prefix(norm, name_start, name_end) if links else None
            if cut is None:
                break
            name_end = cut
            core_norm = norm[name_start:name_end]
            bare_core = _OF_PROPHET_RE.sub(" ", core_norm)
            words = core_norm.split()
        if term_id == "anna" and links and _words(bare_core.strip(" ،,:-")) > 6:
            break
        fresh = bool(links) and bool(re.search(r"\.|(?<!\w)ح(?!\w)", norm[end_of_chain:term.start()]))
        if skip_same and links and _same_narrator(_strip_said(core_norm), _strip_said(normalize_name(links[-1].raw_name))):
            skip_same = False                             # the same man named again by the second teacher's wording
            end_of_chain = name_end
            pos = name_end
            continue
        skip_same = False
        while name_end > name_start + 1 and norm[name_end - 1] == " ":
            name_end -= 1                           # words blanked at its end ("بخط يده") are not his name
        if term_id == "kataba" and not re.match(r"[\s،,:]*(?:قال[\s،,:]*)?(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|عن|سمعت)(?!\w)",
                                                norm[name_end:name_end + 30]):
            break                                   # "كتب إلى عماله أن …": a letter in the story, not a link
        links.append(Link(len(links) + 1, term_id, _clean_name(orig(name_start, name_end)), fresh))
        ends.append((end_of_chain, name_end))
        end_of_chain = name_end
        pos = honor.end() if honor and honor.end() > name_end else name_end
        while True:                                  # another narrator at this same link: a second road (qiran)
            either = _OR_RE.match(norm, pos)
            if either and (re.fullmatch(r"ال\S+", either.group(1).strip()) or re.match(
                    r"(?:من|غير|غيره|غيرهما)(?!\w)", either.group(1).strip())):
                pos = end_of_chain = either.end()   # "هلالاً المزني أو المازني", "عن أبيه أو عن غيره": no second man
                continue
            if either and _co_ok(either.group(1).strip()):
                # "عن أبي هريرة أو عن أبي سعيد - شك الأعمش -": the narrator was not sure which: either is the link
                start = either.start(1)
                result.alternates.append((len(links) - 1, Link(len(links), term_id, _clean_name(
                    orig(start, start + len(either.group(1).rstrip()))))))
                pos = end_of_chain = either.end()
                continue
            co = _CO_NARRATOR_RE.match(norm, pos) or _CO_LAST_RE.match(norm, pos)
            if not co:
                break
            co_name = co.group(1).strip()
            if re.fullmatch(r"(?:غيره|غيرهما|غير واحد|غيرهم)", _JOINED_RE.sub("", co_name).strip(" ،,")):
                pos = end_of_chain = co.end()          # "عن مسعر، وغيره، عن قيس": one not named — no second road
                continue
            if not _co_ok(co_name):
                break
            if _is_companion(links[-1]) and not is_companion_name(_JOINED_RE.sub("", co_name)):
                # "عن أبي هريرة، وأبي الزناد، عن الأعرج، عن أبي هريرة": after a Companion, "و" + a Successor begins a
                # second road — not a second Companion at this link (2026-10-18: Abu Hurayra had become al-A'raj's
                # student)
                result.parallel_at = co.start(1) - 1
                result.parallel_kind = "co"
                break
            start = co.start(1)
            co_len = len(co.group(1))
            ha = _HA_END_RE.search(co.group(1))         # "حدثنا محمد بن بشر، وأبو أسامة ح وحدثني زهير": a tahwil
            if ha and ha.start() > 0:
                co_len = ha.start()
            result.alternates.append((len(links) - 1, Link(len(links), term_id, _clean_name(
                _JOINED_RE.sub("", orig(start, start + co_len)).strip()))))
            if ha and ha.start() > 0:
                pos = end_of_chain = start + co_len
                break
            pos = end_of_chain = co.end()
        if result.parallel_at >= 0:
            break
        if any(i == len(links) - 1 for i, _ in result.alternates):
            skip_same = True                        # "حدثنا شعبة ومحمد قال حدثنا شعبة": the first named again
        if _tahwil_at(norm, pos):
            break

    # "... عن عايشه، ان ابا بكر دخل ..." - after anna comes the subject of the story, not a narrator,
    # unless a transmission verb follows the name ("ان الحكم بن نافع حدثهم", "ان ابن عمر قال سمعت")
    # (2026-10-18: the verb must come right after the name — "أن فاطمة بنت أبي حبيش سألت النبي ﷺ … قالت" is a story —
    # and a subject who speaks to the Prophet or to someone is the story's own person: "أن سعد بن عبادة قال لرسول الله")
    # (one after another: "عن ابن عباس قال إن ناساً يزعمون أن هذه الآية …" — both subjects go)
    # (also when the Prophet is named after it: "أن ناساً سألوا أزواج النبي ﷺ …" is still the story)
    story_end = 0                                   # where the last link taken back for the story ended
    while links and links[-1].term == "anna":
        after_name = norm[end_of_chain:end_of_chain + 120]
        for _ in range(3):                              # "رضي الله عنها زوج النبي ﷺ أخبرته": past the honorific and title
            after_name = _OF_PROPHET_START_RE.sub("", _HONORIFIC_TAIL_RE.sub("", after_name))
            # and a word on him: "أن عمه، وكان من أصحاب النبي ﷺ، أن النبي ﷺ …"
            after_name = re.sub(r"^[\s،,\-]*(?:وكان|وكانت|وهو|وهي)\s[^.]{0,70}?(?=(?<!\w)(?:ان|عن|قال|قالت|يقول|حدث\w*|اخبر\w*)\s)",
                                "", after_name)
        last = normalize_name(links[-1].raw_name)
        # a man not named who transmits is a narrator ("أن رجلاً من أصحاب النبي ﷺ حدثه"); one who speaks is the story
        generic = _GENERIC_SUBJECT_RE.match(last) and not (
            _ANNA_NAME_VERB_RE.search(last.strip(" ،,")) or _GENERIC_TRANSMITS_RE.match(after_name))
        narrates = bool(_ANNA_NARRATES_RE.match(after_name) or _ANNA_NAME_VERB_RE.search(last.strip(" ،,"))
                        or _FROM_PROPHET_RE.match(after_name)
                        # "أن أبا هريرة وزيد بن خالد أخبراه": the verb was read with the second narrator at the link
                        or re.search(r"(?<!\w)(?:اخبراه|حدثاه|اخبروه|حدثوه|قالا|قالوا|حدثه|اخبره|حدثهم|اخبرهم)(?!\w)",
                                     norm[ends[-1][1]:end_of_chain]))
        before = links[-2].raw_name if len(links) > 1 else ""
        after_companion = bool(before) and (is_companion_name(before) or _COMPANION_HONOR_RE.match(
            norm[ends[-2][1]:ends[-2][1] + 30] if len(ends) > 1 else ""))
        story = after_companion and (not narrates or _STORY_SPEECH_RE.match(after_name))
        if not (generic or not (narrates or _NARRATES_RE.search(after_name[:60])) or story):
            break
        story_end = max(story_end, ends[-1][1])
        links.pop()
        end_of_chain = ends.pop()[0]
        # "عن جبلة بن سحيم أن رجلاً سأل ابن عمر عن الأضحية": the one asked answers — he is the source, asked
        if generic and not links[-1:] == [] and not result.reaches_prophet:
            whose = re.match(r"[\s،,]*سال\s+", norm[story_end:story_end + 12])
            got = _asked_name(norm, story_end + whose.end()) if whose else None
            if got and norm[got[0]:got[1]].strip(" ،,") and not _PROPHET_RE.match(norm, got[0]) \
                    and not _PROPHET_NAME_RE.match(norm, got[0]) and re.match(r"[\s،,]*عن(?!\w)", norm[got[1]:got[1] + 6]):
                links.append(Link(len(links) + 1, "su'ila", _clean_name(orig(got[0], got[1])), False))
                ends.append((end_of_chain, got[1]))
                end_of_chain = story_end = got[1]
                break

    # a man not named whom the last narrator only heard say something ("أنه سمع رجلاً يقول: لا والكعبة") is the story,
    # not a narrator — unless what he says is from the Prophet ("سمعت رجلاً يحدث عن النبي ﷺ")
    if links and not result.reaches_prophet and _LONE_GENERIC_RE.match(normalize_name(links[-1].raw_name).strip(" ،,")) \
            and not _PROPHET_RE.search(norm[end_of_chain:end_of_chain + 50]) \
            and not _PROPHET_NAME_RE.search(norm[end_of_chain:end_of_chain + 50]) \
            and not re.search(r"(?<!\w)(?:سمعت|سمع|حدثنا|حدثني|اخبرنا|اخبرني|انبانا|يحدث|حدث|يخبر)(?!\w)",
                              norm[end_of_chain:end_of_chain + 60]):
        story_end = max(story_end, ends[-1][1])
        links.pop()
        end_of_chain = ends.pop()[0]

    # one a Companion heard reciting or calling ("عن عمر قال سمعت هشام بن حكيم يقرأ سورة الفرقان") is the story, not
    # his teacher (a Successor who heard a Companion recite — "عن عطاء، سمع ابن عباس يقرأ" — has his teacher there)
    if len(links) > 1 and links[-1].term in ("sami'tu", "sami'a") and _is_companion(links[-2]) \
            and _HEARD_DOING_RE.match(norm[end_of_chain:end_of_chain + 30]):
        story_end = max(story_end, ends[-1][1])
        links.pop()
        end_of_chain = ends.pop()[0]

    # the Prophet by his bare kunya at the end of the chain: "سمعت أبا هريرة يقول سمعت أبا القاسم يقول …" (a narrator
    # called Abu al-Qasim is always followed by his own teacher: "عن الحكم عن أبي القاسم عن ابن عباس")
    if len(links) >= 3 and not result.reaches_prophet and _BARE_KUNYA_RE.match(normalize_name(links[-1].raw_name).strip(" ،,")) \
            and links[-1].term in ("sami'tu", "haddathani", "haddathana", "'an", "akhbarani", "akhbarana") \
            and re.match(r"^[\s،,:]*(?:يقول|قال)(?!\w)", norm[end_of_chain:end_of_chain + 20]):
        links.pop()
        end_of_chain = ends.pop()[0]
        result.reaches_prophet = True

    if result.parallel_at >= 0:
        if not links:
            result.parallel_at, result.parallel_kind = -1, ""
        else:
            if not result.reaches_prophet:
                result.reaches_prophet = bool(_PROPHET_RE.search(norm[end_of_chain:min(end_of_chain + 90, result.parallel_at)]))
            result.raw_isnad = _clean_name(orig(0, end_of_chain))
            result.links = links
            result.ends_with = "prophet" if result.reaches_prophet else ""
            result.parallel_at = index_map[result.parallel_at] if result.parallel_at < n else len(text)
            return result

    tail = _HONORIFIC_TAIL_RE.sub("", norm[end_of_chain:end_of_chain + 160]).lstrip(" ،,")
    if links and not result.reaches_prophet:
        result.reaches_prophet = bool(_PROPHET_RE.search(norm[end_of_chain:end_of_chain + 90]))

    # two teachers at one link (qiran): "حدثنا عثمان، وابو بكر ابنا ابي شيبه قالا حدثنا ..."
    if links and not result.reaches_prophet and _JOINT_START_RE.match(tail) and _JOINT_WORD_RE.search(tail):
        result.raw_isnad = _clean_name(orig(0, min(n, end_of_chain + 140)))
        result.problem = N_("two narrators at one link (qiran); not split in version 1")
        result.links = links                         # the chain as far as it was read: shown, never hidden
        return result

    if _tahwil_before(norm, end_of_chain + 60):
        result.raw_isnad = _clean_name(orig(0, min(n, end_of_chain + 60)))
        result.problem = TAHWIL
        result.links = links                         # the chain as far as it was read: shown, never hidden
        return result
    goes_on = _CONTINUES_RE.match(tail)
    if goes_on and skipped_to > end_of_chain:
        # "- قال أبو بكر ربما قال وكيع عن ابن عباس أن معاذا -": a note passed over, read after it
        goes_on = _CONTINUES_RE.match(_HONORIFIC_TAIL_RE.sub("", norm[skipped_to:skipped_to + 160]).lstrip(" ،,"))
    if goes_on and story_end > end_of_chain:
        # the words after the end are the story's own ("قال سمعت رجلاً قال لعبد الله بن عمرو …", "أن رجلاً قال للنبي"):
        # whether a chain goes on is read after its person
        goes_on = _CONTINUES_RE.match(_HONORIFIC_TAIL_RE.sub("", norm[story_end:story_end + 160]).lstrip(" ،,"))
    prophet_at = min((m for m in (_PROPHET_RE.search(tail), _PROPHET_NAME_RE.search(tail)) if m),
                     key=lambda m: m.start(), default=None)   # "قال سمعت أبا القاسم ﷺ": the chain has ended
    if goes_on and links and links[-1].term in ("sa'altu", "su'ila", "sa'ala") \
            and re.match(r"(?:[\s\-]*رضي الله \S+)?[\s\-،,]*(?:عن|حدثني|اخبرني|حدثيني|اخبريني)(?!\w)", tail):
        goes_on = None                              # "سألت ابن عمر عن صلاة الليل": what he was asked about
    if goes_on and re.match(r"(?:\S+\s+){0,3}?(?:سيل|سيلت|سال|سالته|سالها|يسال|سالت)\s+(?:\S+\s+){0,3}?عن\s", tail) \
            and goes_on.end() <= 40 + tail.find("عن"):
        goes_on = None                              # "عن أنس أنه سئل عن جرح النبي ﷺ": the question, not a narrator
    if links and goes_on and (not prophet_at or goes_on.end() <= prophet_at.start()):
        result.raw_isnad = _clean_name(orig(0, min(n, end_of_chain + 140)))
        result.problem = N_("chain continues after words that were not understood")
        result.links = links                         # the chain as far as it was read: shown, never hidden
        return result

    if _tahwil_before(norm, max(end_of_chain, pos) + 40):
        result.raw_isnad = _clean_name(orig(0, max(end_of_chain, 1)))
        result.problem = TAHWIL
        result.links = links                         # the chain as far as it was read: shown, never hidden
        return result
    if not links:
        result.problem = N_("no narrator found after the transmission term")
        return result
    result.raw_isnad = _clean_name(orig(0, end_of_chain))
    result.links = links
    if result.reaches_prophet:
        result.ends_with = "prophet"
    return result


# ------------------------------------------------------------------ road B: Shia chains
# "5ـ ", "30 - ", "{12}", then the compiler's student's "قال:" before a term ("قال: أخبرني …", al-Mufid's Amali)
_PREAMBLE_RE = re.compile(r"^[\s{\[(]*(?:\d+\s*[})\]]?\s*[-–.:]?\s*)?(?:\[?قال\]?\s*:?\s*(?=و?(?:اخبرني|اخبرنا|حدثني|حدثنا)))?")
# the honorific that marks a Ma'sum in Shia texts: (عليه السلام), (ع), عليهما السلام, صلى الله عليه وآله …
_MASUM_HONOR_RE = re.compile(
    r"[\s\u200c]*[(\[]?[\s\u200c]*(?:عليه[\s\u200c]*السلام|عليها[\s\u200c]*السلام|عليهما[\s\u200c]*السلام|"
    r"عليهم[\s\u200c]*السلام|صلوات الله عليه(?:ما|م)?|صلي الله عليه و?(?:اله|ال)(?: وسلم)?|صلي الله عليه وسلم|"
    r"(?<!\w)ع(?!\w))[\s\u200c]*[)\]]?")
_SHIA_STOP_RE = re.compile(r"(?<!\w)(?:قال|قالا|قالوا|قالت|يقول|رفعه|يرفعه|جميعا|باسناده|وباسناده|بهذا الاسناد|"
                           r"باسناده|مثله|نحوه|انه|انها|في حديث|قلت|سالت|سمعت|رضي الله|رحمه الله|رحمهم الله|"
                           r"اجازه|مناوله|فيما كتب|فيما اجاز)(?!\w)")
_JOIN_RE = re.compile(r"[\s،,؛]*و(?=[^\s])")
_ALL_RE = re.compile(r"[\s،,؛]*جميعا(?!\w)")
# a place or a date after a name: "بالكوفة سنة أربع وخمسين وثلاثمائة", "بمدينة السلام", "بسمرقند"
_PLACE_RE = re.compile(r"(?<!\w)(?:بال\w+|بمدينه|بسمرقند|بقم|ببلخ|بنيسابور|بمرو|ببغداد|بمكه|بفرغانه|في سنه|سنه)(?!\w)")
# "… قال: حدثنا" a little further on, after words that belong to no one (a place, a date, a praise)
_SAID_TERM_RE = re.compile(r"(?:قال|قالا|قالوا)\s*:?\s*(?=و?(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|انباني|سمعت)(?!\w))")
_PRAISE_RE = re.compile(r"[\s،,؛\-\[(]*(?:رضي ?الله (?:تعالي )?\s?عن(?:ه|هما|هم)|رحمه الله|رحمهم الله)(?:\s*تعالي)?(?!\w)[\s\-\])]*")
_ALL_START_RE = re.compile(r"[\s،,]*(?:و?بالاسناد|و?باسناده|و?بهذا الاسناد|و?عنه باسناده)(?!\w)")
_MUDMAR_RE = re.compile(r"^[\s،,:]*(?:قال|قالا)?[\s،,:]*(?:سالته|سمعته|كتبت اليه|قلت له|سال|سئل)(?!\w)")
# the teachers al-Kulayni opens his chains with: "و" + one of them after a link starts a second road from him
COMPILER_TEACHERS = ("محمد بن يحيي", "علي بن ابراهيم", "عده من اصحابنا", "محمد بن اسماعيل", "الحسين بن محمد",
                     "علي بن محمد", "احمد بن ادريس", "ابو علي الاشعري", "حميد بن زياد", "محمد بن جعفر",
                     "محمد بن الحسن", "احمد بن محمد بن سعيد", "محمد بن عبد الله", "محمد بن ابي عبد الله",
                     "علي بن محمد بن بندار", "الحسين بن الحسن", "داود بن كوره", "سهل بن زياد")
_DESCRIPTION_WORDS = ("كان", "هو", "هي", "قد", "لم", "كانت", "زاد", "في", "فيه", "ذكر", "ذكره", "رواه", "ليس")
_SAME_CHAIN_RE = re.compile(r"[\s،,]*(?:و?باسناده|بهذا الاسناد|بالاسناد|بهذا الاسناد مثله|مثله)(?!\w)")


def _masum_after(norm: str, at: int, window: int = 110) -> str:
    """The Ma'sum named just after the end of the chain ("قال قلت لأبي عبد الله (ع)", "سمعت أبا جعفر (ع)")."""
    from isnady.core import traditions

    tail = norm[at:at + window]
    honor = _MASUM_HONOR_RE.search(tail)
    if honor and honor.group(0).strip():
        words = re.sub(r"[()\[\]،,:]", " ", tail[:honor.start()]).split()
        return traditions.masum_in(" ".join(words[-6:])) or "imam"
    for form in ("رسول الله", "النبي", "امير المومنين"):
        if re.search(r"(?<!\w)(?:ل|ب)?" + form + r"(?!\w)", tail[:70]):
            return traditions.which_masum(form)
    return ""


def _words(name: str) -> int:
    """Words of a name, "بن" not counted: a nasab of seven generations is still one name."""
    return sum(1 for w in name.split() if w not in ("بن", "ابن", "بنت"))


def _second_road(norm: str, at: int, links_so_far: int) -> str:
    """What follows "و" after a link: "same link" (another narrator transmitting from the same next one), "new road"
    (a second road from the compiler), "joined" (a road that meets the first at "جميعاً"), or "end"."""
    head = norm[at:at + 120]
    word = head.split()[0] if head.split() else ""
    if not word or word in _DESCRIPTION_WORDS:
        return "end"
    nxt = _SHIA_TERM_RE.search(norm, at)
    if nxt is None:
        return "end"
    name = _PRAISE_RE.sub(" ", norm[at:nxt.start()])
    name = re.sub(r"(?<!\w)(?:قالا|قالوا|قال)(?!\w)|[-:؛]", " ", name).strip(" ،,")
    parts = [x for x in re.split(r"\sو(?=\S)", name) if x.strip()]
    if (not parts or any(_words(x) > 8 for x in parts) or _SHIA_STOP_RE.search(name)
            or _MASUM_HONOR_RE.search(name)):
        return "end"
    name = parts[0].strip()
    meet = _ALL_RE.search(norm, nxt.start(), nxt.start() + 400)
    if meet and not _MASUM_HONOR_RE.search(norm, nxt.start(), meet.start()):
        return "joined"
    if links_so_far >= 2 and any(name == t or name.startswith(t + " ") for t in COMPILER_TEACHERS):
        return "new road"
    return "same link"


def _parse_shia(text: str) -> ParsedIsnad:
    from isnady.core import traditions

    norm, index_map = normalize_with_map(text)
    n = len(norm)

    def orig(a: int, b: int) -> str:
        start = index_map[a] if a < n else len(text)
        end = index_map[b] if b < n else len(text)
        return text[start:end]

    result = ParsedIsnad()
    pre = _PREAMBLE_RE.match(norm)
    pos = pre.end() if pre else 0
    if _ALL_START_RE.match(norm, pos):
        result.problem = N_("refers to the chain of an earlier hadith (bi-isnadihi); not split")
        return result
    links: list[Link] = []
    end_of_chain = pos
    first = True
    met = False                                         # just past "جميعاً": the roads meet at the next narrator
    while pos < n:
        filler = _FILLER_RE.match(norm, pos)
        if filler and not (first and norm[pos:pos + 1] == "و" and _JOIN_RE.match(norm, pos) is None):
            pos = filler.end()
        term = _SHIA_TERM_RE.match(norm, pos)
        if term:
            term_id = _TERM_ID[term.group(1)]
            name_start = term.end()
        elif first:
            term_id, name_start = "bare", pos           # al-Kulayni names his teacher without a term
        else:
            break
        first = False
        while name_start < n and norm[name_start] in " \t":
            name_start += 1

        # the name runs to the next comma, the next term, an honorific or a word that ends it
        next_comma = min((i for i in (norm.find("،", name_start), norm.find(",", name_start)) if i != -1), default=n)
        next_term = _SHIA_TERM_RE.search(norm, name_start)
        name_end = min(next_comma, next_term.start() if next_term else n, name_start + 160)
        stop = _SHIA_STOP_RE.search(norm, name_start, name_end)
        if stop:
            name_end = stop.start()
        honor = _MASUM_HONOR_RE.search(norm, name_start, name_end)
        if honor:
            name_end = honor.start()
        join = re.search(r"\sو(?=[^\s])|؛|\[", norm[name_start:name_end])
        if join and join.start() > 0:
            name_end = name_start + join.start()
        place = _PLACE_RE.search(norm, name_start, name_end)
        if place and place.start() > name_start:
            name_end = place.start()
        core = norm[name_start:name_end].strip(" ،,:-()")
        words = core.split()

        # one of the Fourteen Ma'sumun ends the chain: with the honorific after the name, or a name no one else bears
        masum = traditions.which_masum(core) if core else ""
        honoured = honor is not None and honor.start() <= name_end + 1
        if masum and (honor is not None or any(core == f or core.startswith(f + " ") for f in traditions.ALWAYS_MASUM)):
            result.reaches_prophet, result.ends_with = True, masum
            break
        if honoured and words and len(words) <= 6:
            result.reaches_prophet, result.ends_with = True, "imam"
            break
        if not words or _words(core) > _MAX_NAME_WORDS:
            break                                       # the text has begun
        if met and links and _name_key(core) == _name_key(normalize_name(links[-1].raw_name)):
            # "عن أبيه، عن حماد بن عيسى، ومحمد بن يحيى …، جميعاً عن حماد بن عيسى": the first road already ends at him
            met = False
            end_of_chain = pos = name_end
            continue
        met = False
        links.append(Link(len(links) + 1, term_id, _clean_name(orig(name_start, name_end))))
        end_of_chain = name_end
        pos = name_end
        if honor is not None and honor.start() == name_end:
            pos = honor.end()                           # "… بن الحسين بن أبي طالب عليه السلام": an ancestor's honorific
        if links and len(links) == 1 and _SAME_CHAIN_RE.match(norm, pos):
            result.problem = N_("refers to the chain of an earlier hadith (bi-isnadihi); not split")
            result.raw_isnad = _clean_name(orig(0, min(n, pos + 30)))
            return result
        if re.match(r"[\s،,]*ي?رفعه(?!\w)", norm[pos:]):
            result.raised = True
            result.ends_with = _masum_after(norm, pos)
            result.reaches_prophet = bool(result.ends_with)
            break
        all_ = _ALL_RE.match(norm, pos)
        if all_:
            pos = all_.end()
            met = True
            continue
        joint = _JOIN_RE.match(norm, pos)
        if joint:
            road = _second_road(norm, joint.end(), len(links))
            if road == "same link":
                # two narrators at one link ("عن أبيه وعلي بن محمد القاساني عن القاسم"): both transmit from the
                # next; the first is followed
                result.joined += 1
                pos = _SHIA_TERM_RE.search(norm, joint.end()).start()
                continue
            if road == "new road":
                meet = _ALL_RE.search(norm, pos, min(n, pos + 400))
                if meet and not _MASUM_HONOR_RE.search(norm, pos, meet.start()):
                    result.joined += 1
                    pos = meet.end()
                    met = True
                    continue
                result.raw_isnad = _clean_name(orig(0, min(n, pos + 160)))
                result.problem = N_("two roads from the compiler join without \"jami'an\"; not split")
                return result
            if road == "joined":
                meet = _ALL_RE.search(norm, pos, min(n, pos + 400))
                result.joined += 1
                pos = meet.end()
                met = True
                continue
            break                                       # "وكان من الواقفة": a description, the chain has ended
        praise = _PRAISE_RE.match(norm, pos)
        if praise:
            pos = praise.end()
        filler = _FILLER_RE.match(norm, pos)
        if term_id != "bare" and not _SHIA_TERM_RE.match(norm, filler.end() if filler else pos):
            said = _SAID_TERM_RE.search(norm, pos, min(n, pos + 140))
            if said and not _MASUM_HONOR_RE.search(norm, pos, said.start()) and \
                    not re.search(r"(?<!\w)(?:وجدت|كتاب|كتب)(?!\w)", norm[pos:said.start()]):
                pos = said.end()

    if links and not result.reaches_prophet and not result.raised:
        key = _masum_after(norm, end_of_chain)
        if key:
            result.reaches_prophet, result.ends_with = True, key
        elif _MUDMAR_RE.match(norm[end_of_chain:end_of_chain + 40]):
            result.ends_with = "mudmar"             # "سألته": an Imam not named
    if not links:
        result.problem = N_("no narrator found before the text")
        return result
    if len(links) == 1 and links[0].term == "bare" and not result.reaches_prophet and not result.raised:
        result.problem = N_("no chain: a name without a transmission after it")
        return result
    result.raw_isnad = _clean_name(orig(0, end_of_chain))
    result.links = links
    return result


# ------------------------------------------------------------------ storage
# the parser a database was read with → the chains the new rules can change (the others stay as they are)
PARTIAL_UPGRADES = {
    # 8: two narrators at a link, a chain kept as far as read, "وعنه" / "بهذا الإسناد" — only chains that were not
    # split change (10 split ones would gain a second Companion at the last link; a full rebuild gives them that)
    "isnady-isnad-6": "problem IS NOT NULL",
    "isnady-isnad-7": "problem IS NOT NULL",
}


# the books that give their hadith without chains (the compiler names the Companion and the book it is in)
CITING_BOOKS = {"bulugh", "riyad", "mishkat", "dehlawi", "mumin"}
# a book whose edition splits one hadith into numbered pieces, the later ones without the chain: the Musnad
_SPLIT_BOOKS = {"ahmad"}
_NO_TERM = "does not start with a transmission term"
# a text the book cites without a chain of its own: "وفي رواية لمسلم", "ولأبي داود", "وأصله في", "زاد مسلم"
NO_CHAIN = N_("no chain: the book cites the text without one")
_CITED_RE = re.compile(r"^[\s\d{}\[\]().،,\"'\u200f\u200e\-]*(?:وفي (?:روايه|لفظ|حديث|الصحيح|\"?الصحيحين|اخري)|ول(?:مسلم|لبخاري|ابي داود|"
                       r"احمد|لترمذي|لنسايي|ابن ماجه|ابن حبان|لحاكم|لطبراني|لدارقطني|لبيهقي|ه|هما|هم|لخمسه|لاربعه|لسته)(?!\w)|"
                       r"و?زاد (?:مسلم|البخاري|احمد|ابو داود)|واصله|واخرجه|ونحوه|وعند|وعندهما|وله شاهد|وذكر|وقد روي|ورواه|رواه)")
BORROWED = N_("the chain of the hadith before it (\"from him\" / \"with this chain\")")
# "وعنه قال" (Mishkat, Riyad: from the Companion of the hadith before), "وبهذا الإسناد", "وبإسناده" (the same chain)
_FROM_HIM_RE = re.compile(r"^[\s\d{}\[\](\"'\u200f\u200e.ـ-]*(?:ال\w+(?:\s+\S+){0,2}?\s*:\s*)?و?(?:عنه|عنها|عنهما)(?!\w)")
_SAME_CHAIN_OLD_RE = re.compile(r"^[\s\d{\[(\"'\u200f\u200e.ـ-]*(?:قال\s+)?(?:و\s*)?(?:بهذا الاسناد|باسناده|بالاسناد|به)(?!\w)")
# the Musnad's sheets, one hadith after another under one chain: "وقال رسول الله ﷺ" (the Sunni books only)
_SHEET_RE = re.compile(r"^[\s\d{\[(\"'\u200f\u200e.ـ-]*(?:قال\s+)?و\s*(?:قال|كان) (?:رسول الله|النبي|عليه الصلاه|صلي الله)(?!\w)")
_SAME_CHAIN_START_RE = re.compile(_SAME_CHAIN_OLD_RE.pattern + "|" + _SHEET_RE.pattern)


def _borrow_previous(conn: sqlite3.Connection, hadith_ids: list[int], whole_ids: set | None = None) -> int:
    """A hadith that gives no chain of its own but points to the one before ("وعنه", "وبهذا الإسناد"): the chain of the
    nearest hadith before it in the book is drawn for it — the Companion alone for "from him", the whole chain for
    "with this chain". Kept apart from the statistics (problem BORROWED), so no chain is counted twice."""
    done = 0
    for hid in hadith_ids:
        row = conn.execute("SELECT h.collection_id, h.number_sort, t.text FROM hadiths h JOIN texts t ON t.hadith_id = h.id "
                           "JOIN editions e ON e.id = t.edition_id WHERE h.id = ? AND e.language = 'Arabic'", (hid,)).fetchone()
        if row is None:
            continue
        norm = normalize_name(row[2] or "")[:80]
        whole = bool(_SAME_CHAIN_START_RE.match(norm)) or hid in (whole_ids or ())
        if whole and hid not in (whole_ids or ()) and _SHEET_RE.match(norm) and not _SAME_CHAIN_OLD_RE.match(norm):
            tradition = conn.execute("SELECT tradition FROM collections WHERE id = ?", (row[0],)).fetchone()
            whole = not (tradition and tradition[0] == "shia")
        if not whole and not _FROM_HIM_RE.match(norm):
            continue
        prev = conn.execute(
            """SELECT i.id, i.reaches_prophet, i.ends_with FROM hadiths h JOIN isnads i ON i.hadith_id = h.id
               WHERE h.collection_id = ? AND h.number_sort < ? AND i.ordinal = 1
                 AND EXISTS (SELECT 1 FROM isnad_links l WHERE l.isnad_id = i.id)
               ORDER BY h.number_sort DESC LIMIT 1""", (row[0], row[1])).fetchone()
        if prev is None:
            continue
        links = conn.execute("SELECT position, raw_name, transmission FROM isnad_links WHERE isnad_id = ? "
                             "ORDER BY position", (prev[0],)).fetchall()
        if not whole:
            links = links[-1:]
        else:
            # "وبهذا الإسناد عن أحمد بن أبي عبد الله عن أبيه عن صفوان …": the chain before, to the narrator named, then
            # the narrators this one names after him (when he is not in it, the chain is left as it is)
            phrase = _SAME_CHAIN_START_RE.match(normalize_name(row[2] or ""))
            rest = (row[2] or "")[_orig_len(row[2] or "", phrase.end()):] if phrase else ""
            own = _parse_sunni("حدثنا فلان " + rest.lstrip(" ،,:")).links[1:] if re.match(r"[\s،,:]*عن(?!\w)",
                                                                                   normalize_name(rest)) else []
            if own:
                at = next((k for k, r in enumerate(links) if _shared(r[1], own[0].raw_name)), None)
                if at is None:
                    continue
                links = list(links[:at]) + [(0, l.raw_name, l.term) for l in own]
        mine = conn.execute("SELECT id FROM isnads WHERE hadith_id = ? AND ordinal = 1", (hid,)).fetchone()
        if mine is None or conn.execute("SELECT 1 FROM isnad_links WHERE isnad_id = ?", (mine[0],)).fetchone():
            continue
        conn.execute("UPDATE isnads SET problem = ?, reaches_prophet = ?, ends_with = ? WHERE id = ?",
                     (BORROWED, prev[1], prev[2], mine[0]))
        conn.executemany("INSERT INTO isnad_links (isnad_id, position, raw_name, transmission) VALUES (?, ?, ?, ?)",
                         [(mine[0], i, r[1], r[2]) for i, r in enumerate(links, 1)])
        done += 1
    return done


def ensure_isnads(conn: sqlite3.Connection, progress: Callable[[str], None] | None = None,
                  rebuild: bool = False) -> dict:
    """Parse the Arabic text of every hadith that has no derived chain yet."""
    say = progress or (lambda _m: None)
    conn.execute("CREATE TABLE IF NOT EXISTS core_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    row = conn.execute("SELECT value FROM core_meta WHERE key = 'isnad_parser'").fetchone()
    only = PARTIAL_UPGRADES.get(row[0]) if row is not None and not rebuild else None
    if only:
        # a change of rules that touches only some chains: those read again, not all 99,000 (a wait at start)
        conn.execute(f"DELETE FROM isnads WHERE derived_by IS NOT NULL AND hadith_id IN "
                     f"(SELECT hadith_id FROM isnads WHERE derived_by IS NOT NULL AND ({only}))")
    elif rebuild or (row is not None and row[0] != PARSER_ID):
        say(tr("Isnad rules changed; parsing every chain again"))
        conn.execute("DELETE FROM isnads WHERE derived_by IS NOT NULL")
    conn.execute("INSERT OR REPLACE INTO core_meta (key, value) VALUES ('isnad_parser', ?)", (PARSER_ID,))

    todo = conn.execute(
        """SELECT h.id, t.text, e.source_id, c.tradition, c.key FROM hadiths h
           JOIN collections c ON c.id = h.collection_id
           JOIN texts t ON t.hadith_id = h.id
           JOIN editions e ON e.id = t.edition_id
           WHERE e.language = 'Arabic'
             AND h.id NOT IN (SELECT hadith_id FROM isnads WHERE derived_by IS NOT NULL)
           GROUP BY h.id"""
    ).fetchall()
    stats = {"parsed": 0, "reaches_prophet": 0, "raw_only": 0, "links": 0, "problems": {}}
    if not todo:
        conn.commit()
        return stats
    say(tr("Reading isnads of {todo} hadith", todo=len(todo)))
    import time as _time

    from isnady.core import log

    started = _time.perf_counter()
    no_links: list[int] = []
    continued: set[int] = set()
    for hadith_id, text, source_id, tradition, book_key in todo:
        chains = parse_all(text, tradition)
        if chains[0].problem in (_NO_TERM, "no narrator found before the text") and not chains[0].links:
            if book_key in CITING_BOOKS:
                chains[0].problem = NO_CHAIN        # a book that cites its hadith without their chains
            elif book_key in _SPLIT_BOOKS and re.match(r"[\s\d.\-]*(?:قال\s+)?و", normalize_name(text or "")):
                continued.add(hadith_id)            # the Musnad's "وقال …", "ونهى عن …": the rest of the hadith before
        for ordinal, p in enumerate(chains, 1):         # a tahwil: each road its own chain (ordinal 1 written first)
            isnad_id = conn.execute(
                """INSERT INTO isnads (hadith_id, ordinal, raw_text, source_id, derived_by, reaches_prophet, problem,
                                       ends_with, raised)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (hadith_id, ordinal, p.raw_isnad or None, source_id, PARSER_ID, int(p.reaches_prophet),
                 p.problem or None, p.ends_with or None, int(p.raised)),
            ).lastrowid
            conn.executemany(
                "INSERT INTO isnad_links (isnad_id, position, raw_name, transmission) VALUES (?, ?, ?, ?)",
                [(isnad_id, link.position, link.raw_name, link.term) for link in p.links],
            )
        p = chains[0]
        if not p.links:
            no_links.append(hadith_id)
        if p.links:
            stats["parsed"] += 1
            stats["links"] += len(p.links)
            stats["reaches_prophet"] += int(p.reaches_prophet)
        else:
            stats["raw_only"] += 1
            stats["problems"][p.problem] = stats["problems"].get(p.problem, 0) + 1
    stats["borrowed"] = _borrow_previous(conn, sorted(no_links), continued)
    conn.commit()
    log.get("chains").info("✔ %s chains read by %s in %.1f s: %s with links, %s reaching the Prophet, %s kept whole",
                           f"{len(todo):,}", PARSER_ID, _time.perf_counter() - started, f"{stats['parsed']:,}",
                           f"{stats['reaches_prophet']:,}", f"{stats['raw_only']:,}")
    return stats


def chain(conn: sqlite3.Connection, hadith_id: int) -> list[dict]:
    """The stored chains of a hadith with their links, for display; each says the road of its book ("sunni" or
    "shia"), so that its words keep that road's manners (a Companion's "(r.a.)" on road A only)."""
    out = []
    row = conn.execute("SELECT COALESCE(c.tradition, 'sunni') FROM hadiths h JOIN collections c ON c.id = h.collection_id "
                       "WHERE h.id = ?", (hadith_id,)).fetchone()
    road = row[0] if row else "sunni"
    for isnad in conn.execute(
        "SELECT id, raw_text, reaches_prophet, problem, derived_by, ends_with, raised FROM isnads "
        "WHERE hadith_id = ? ORDER BY ordinal",
        (hadith_id,),
    ):
        links = conn.execute(
            "SELECT position, raw_name, transmission, person_id, match_confidence, candidates "
            "FROM isnad_links WHERE isnad_id = ? ORDER BY position",
            (isnad["id"],),
        ).fetchall()
        out.append({"raw": isnad["raw_text"], "reaches_prophet": bool(isnad["reaches_prophet"]),
                    "problem": isnad["problem"], "derived_by": isnad["derived_by"],
                    "ends_with": isnad["ends_with"] or "", "raised": bool(isnad["raised"]),
                    "links": [dict(r) for r in links], "tradition": road})
    return out


# ----------------------------------------------------------------- reading aids
# How each transmission term reads, and what the critics took it to mean.
TERM_LABELS = {
    "haddathana": ("حدثنا", N_("narrated to us"),
                   N_("The teacher recited it to a group that included the narrator: heard directly.")),
    "haddathani": ("حدثني", N_("narrated to me"),
                   N_("The teacher recited it to the narrator alone: heard directly.")),
    "akhbarana": ("أخبرنا", N_("informed us"),
                  N_("Many critics used it for a text read back to the teacher ('ard); others as haddathana.")),
    "akhbarani": ("أخبرني", N_("informed me"), N_("As akhbarana, received alone.")),
    "anba'ana": ("أنبأنا", N_("told us"), N_("Later scholars often used it for transmission by permission (ijaza).")),
    "anba'ani": ("أنبأني", N_("told me"), N_("As anba'ana, received alone.")),
    "sami'tu": ("سمعت", N_("I heard"), N_("States direct hearing explicitly.")),
    "sami'a": ("سمع", N_("heard"), N_("Reports that the narrator heard it directly.")),
    "qara'tu 'ala": ("قرأت على", N_("I read to"), N_("The narrator read the text back to the teacher ('ard).")),
    "quri'a 'ala": ("قرئ على", N_("it was read to"), N_("The text was read back to the teacher while the narrator listened.")),
    "za'ama": ("زعم", N_("stated"), N_("Reports a statement; says nothing about how it was received.")),
    "'an": ("عن", N_("from"),
            N_("Does not say how it was received ('an'ana). Counted as connected when the two narrators could "
            "have met and the narrator is not known for concealing a gap (tadlis).")),
    "anna": ("أن", N_("that"), N_("Treated by most critics like 'an (mu'anna).")),
    "qala": ("قال", N_("said"), N_("Cited without saying how it was received (ta'liq): the compiler or a narrator "
             "quotes him, as al-Bukhari does after a tahwil (\"وقال ابن وهب\").")),
    "sa'altu": ("سألت", N_("I asked"), N_("The narrator asked him and heard the answer from him: heard directly.")),
    "su'ila": ("سئل", N_("was asked"), N_("He was asked, and the narrator reports his answer; how the narrator "
               "received it is not said.")),
    "sa'ala": ("سأل", N_("asked"), N_("The narrator asked him and heard the answer from him: heard directly.")),
    "wajadtu": ("وجدت", N_("found in writing"), N_("The narrator found it in the teacher's writing (wijada), without "
                "hearing it from him: a weaker way of receiving.")),
    "kataba": ("كتب إلي", N_("wrote to me"), N_("The teacher wrote it to the narrator (mukataba): accepted by most "
               "critics, though not heard.")),
    "balagha": ("بلغه", N_("it reached him"), N_("The narrator says only that it reached him from that man: who "
                "brought it to him is not named (a balagh).")),
    "bare": ("—", N_("(his teacher)"), N_("The compiler names his teacher without a term, as al-Kulayni does: "
             "it is his own transmission from that teacher.")),
}


def link_note(raw_name: str, next_raw: str = "") -> str:
    """What a link of a Shia chain is when it names no one person: al-Kulayni's group (with the teachers he said it
    stands for), "عنه", or a narrator not named. "" for an ordinary name."""
    from isnady.core import traditions

    kind = traditions.link_kind(raw_name)
    if kind == "group":
        members = traditions.group_members(raw_name, next_raw)
        return (t("A group of al-Kulayni's teachers: {members} (as al-Kulayni explained it)", members="، ".join(members))
                if members else t("A group of al-Kulayni's teachers"))
    if kind == "previous":
        return t("\"From him\": the narrator who heads the previous chain in the book")
    if kind == "vague":
        return t("A narrator not named (mubham): the chain does not say who")
    return ""


def end_label(chain: dict) -> str:
    """Whom a stored chain reaches, in words: "the Prophet ﷺ", "Imam Ja'far ibn Muhammad al-Sadiq" …"""
    from isnady.core import traditions

    key = chain.get("ends_with") or ("prophet" if chain.get("reaches_prophet") else "")
    if not key:
        return ""
    label = t("an Imam") if key == "imam" else (traditions.masum_label(key) or key)
    if key == "prophet":
        label = t("the Prophet ﷺ")
    return t("raised (رفعه) to {whom}", whom=label) if chain.get("raised") else label


def term_label(term: str) -> tuple[str, str, str]:
    arabic, meaning, why = TERM_LABELS.get(term, (term, term, ""))
    return arabic, t(meaning), t(why)


def short_name(raw_name: str) -> str:
    """The name without clarifications ("- يعني ابن محمد -", "هو ابن اسلم") for compact display."""
    name = re.split(r"\s*[،,]?\s*-\s*(?:وَ?يَعْنِي|و?يعني|وَ?هُوَ|و?هو)\s", raw_name)[0]
    name = re.split(r"\s{2,}(?:هُوَ|هو)\s", name)[0]
    return name.strip(" ،,-")


# a link that names no one by name, only by kinship or as "a man": said in words, not spelled
_KIN = {
    "ابيه": ("babası", "his father"), "امه": ("annesi", "his mother"), "جده": ("dedesi", "his grandfather"),
    "جدته": ("ninesi", "his grandmother"), "عمه": ("amcası", "his paternal uncle"),
    "خاله": ("dayısı", "his maternal uncle"), "اخيه": ("kardeşi", "his brother"), "اخته": ("kız kardeşi", "his sister"),
    "ابنه": ("oğlu", "his son"), "مولاه": ("mevlâsı (azatlısı)", "his mawla"), "رجل": ("bir adam", "a man"),
    "شيخ": ("bir şeyh", "a shaykh"), "امراه": ("bir kadın", "a woman"),
    "غير واحد": ("birden çok râvi", "more than one narrator"),
    "بعض اصحابه": ("arkadaşlarından biri", "one of his companions"),
    "بعض اصحابنا": ("arkadaşlarımızdan biri", "one of our companions"),
    "عده من اصحابنا": ("arkadaşlarımızdan bir topluluk", "a group of our companions"),
    "جماعه من اصحابنا": ("arkadaşlarımızdan bir cemaat", "a number of our companions"),
}


# "حدثني أبي", "حدثني جدي": a relative in the first person, the whole link — never the first word of a name ("أبي
# هريرة" is Abu Hurayra)
_KIN_ALONE = {"ابي": ("babam", "my father"), "ابوي": ("babam", "my father"), "جدي": ("dedem", "my grandfather"),
              "امي": ("annem", "my mother"), "عمي": ("amcam", "my paternal uncle"), "خالي": ("dayım", "my maternal uncle"),
              "اخي": ("kardeşim", "my brother")}


_KIN_THIRD = {"ابي": "ابيه", "ابوي": "ابيه", "جدي": "جده", "امي": "امه", "عمي": "عمه", "خالي": "خاله", "اخي": "اخيه"}


def name_reading(raw_name: str, language: str = "tr") -> tuple[str, bool]:
    """A chain link's name in Latin letters as it is written in the chain — "حماد يعني ابن سلمة" → "Hammâd (yani
    İbn Seleme)", "أبيه" → "babası", "ابن أبي عتيق" → "İbn Ebî Atîk". (text, spelled): spelled when a word was not
    in the word list and was spelled letter by letter (its short vowels a guess). Turkish or English."""
    from isnady.core import names
    from isnady.core.normalize import normalize

    lang = "tr" if language == "tr" else "en"
    parts = re.split(r"\s*[،,]?\s*-?\s*(?:يَعْنِي|يعني)\s+", raw_name.strip(" ،,-"), maxsplit=1)
    outs, spelled = [], False
    for part in parts:
        part = re.split(r"\s*[،,]?\s*-\s*(?:وَ?هُوَ|و?هو)\s|\s{2,}(?:وَ?هُوَ|و?هو)\s", part)[0].strip(" ،,-")
        key = normalize(part)
        if key in _KIN or key in _KIN_ALONE:
            outs.append((_KIN.get(key) or _KIN_ALONE[key])[0 if lang == "tr" else 1])
            continue
        words = part.split()
        kin_word = normalize(words[0]) if len(words) > 1 else ""
        if kin_word in _KIN:
            # "عمه أبي سهيل بن مالك": his uncle, Abu Suhayl b. Malik (it was read "Amh Ebû Süheyl …")
            text, guessed = name_reading(" ".join(words[1:]), lang)
            kin_text = _KIN[kin_word][0 if lang == "tr" else 1]
            outs.append(f"{kin_text} {text}" if lang == "tr" else f"{kin_text}, {text}")
            spelled = spelled or guessed
            continue
        if words and normalize(words[0]) == "ابن":
            rest = words[1:]
            head = "İbn" if lang == "tr" else "Ibn"
            if rest and normalize(rest[0]) in ("ابي", "ابو", "ابا"):
                head += " Ebî" if lang == "tr" else " Abi"
                rest = rest[1:]
            text, guessed = names.reading(" ".join(rest), lang) if rest else ("", False)
            outs.append(f"{head} {text}".strip())
            spelled = spelled or guessed
            continue
        text, guessed = names.reading(part, lang)
        if text:
            outs.append(text)
            spelled = spelled or guessed
    if not outs:
        return "", False
    # after عن the name stands in the genitive (أبي هريرة); read as a name it is Abu Hurayra
    outs = [("Abu " + o[4:]) if o.startswith("Abi ") else o for o in outs]
    if lang == "tr":
        # after "b." and "bint" the kunya is in the genitive, as Turkish writes it: Mâlik b. Ebî Âmir, Ali b. Ebî Tâlib
        outs = [re.sub(r"\b(b\.|bint|İbn) Ebû ", r"\1 Ebî ", o) for o in outs]
    outs[0] = outs[0][:1].upper() + outs[0][1:]
    if len(outs) == 2:
        return f"{outs[0]} ({'yani' if lang == 'tr' else 'that is,'} {outs[1]})", spelled
    return outs[0], spelled


# read once per name and language: the same names come back in thousands of chains (a whole-library export, EX3)
name_reading = functools.lru_cache(maxsize=1 << 16)(name_reading)
short_name = functools.lru_cache(maxsize=1 << 16)(short_name)


# ----------------------------------------------------------------- the chain in words (ISN-TR1)
# Bayram (2026-10-20): "Senedlerin hepsi arapça ---> altina gosterilen dillerde de gosterilsin arapcasinin altina!"
# The chain as the Arabic says it, link by link, in a shown language: each name read from the chain's own wording
# (name_reading) with the term that brings it. Turkish puts the case on the name (Leys'ten, Ebû Hüreyre'den), so a
# template may use {name_abl} (from), {name_acc} (whom one heard) or {name_dat} (to whom one read); English {name}.
CHAIN_TEMPLATES = {
    "haddathana": N_("{name} narrated to us"), "haddathani": N_("{name} narrated to me"),
    "akhbarana": N_("{name} informed us"), "akhbarani": N_("{name} informed me"),
    "anba'ana": N_("{name} told us"), "anba'ani": N_("{name} told me"),
    "sami'tu": N_("I heard {name}"), "sami'a": N_("he heard {name}"),
    "qara'tu 'ala": N_("I read it to {name}"), "quri'a 'ala": N_("it was read to {name}"),
    "za'ama": N_("{name} stated"), "'an": N_("from {name}"), "anna": N_("that {name}"),
    "qala": N_("{name} said"), "bare": N_("{name} (his teacher)"),
    "sa'altu": N_("I asked {name}"), "su'ila": N_("{name} was asked"),
    "sa'ala": N_("he asked {name}"), "wajadtu": N_("I found it in the writing of {name}"), "kataba": N_("{name} wrote to me"),
    "balagha": N_("it reached him from {name}"),
}
CHAIN_END = N_("from {name}")                    # the Prophet ﷺ, or the Ma'sum a Shia chain reaches
CHAIN_RAISED = N_("raised (رفعه): the rest of the chain is not named")
CHAIN_CUT = N_("… (read as far as here)")
# the languages a chain can be said in: those whose names isnady reads (core.names: Turkish, English)
CHAIN_LANGUAGES = {"Turkish": "tr", "English": "en"}
_TR_POSSESSIVE = ("sı", "si", "su", "sü", "oğlu", "biri")
# the Ma'sumun as a Turkish chain names them (B yolu: in its own terms, without a Sunni honorific)
_MASUM_TR = {
    "prophet": "Hz. Peygamber (s.a.v.)", "fatima": "Fâtıma ez-Zehrâ", "ali": "İmam Ali b. Ebî Tâlib (Emîrü'l-mü'minîn)",
    "hasan": "İmam Hasan b. Ali el-Müctebâ", "husayn": "İmam Hüseyin b. Ali", "sajjad": "İmam Ali b. Hüseyin Zeynelâbidîn",
    "baqir": "İmam Muhammed b. Ali el-Bâkır", "sadiq": "İmam Ca'fer b. Muhammed es-Sâdık",
    "kazim": "İmam Mûsâ b. Ca'fer el-Kâzım", "rida": "İmam Ali b. Mûsâ er-Rızâ", "jawad": "İmam Muhammed b. Ali el-Cevâd",
    "hadi": "İmam Ali b. Muhammed el-Hâdî", "askari": "İmam Hasan b. Ali el-Askerî",
    "mahdi": "İmam Muhammed b. Hasan el-Mehdî", "abu_al_hasan": "Ebü'l-Hasan (İmam Kâzım ya da İmam Rızâ)",
    "imam": "bir İmam", "mudmar": "adı anılmayan bir İmam (mudmar)",
    "one_of_two": "iki İmamdan biri (Bâkır ya da Sâdık)",
}
_HONOUR_RE = re.compile(r"\s*(?:رضي الله|عليه السلام|عليها السلام|عليهما السلام|صلي الله عليه)")


def _tr_case(name: str, case: str) -> str:
    """A Turkish name with its case ending by vowel harmony: Leys'ten, Ebû Hüreyre'den, Saîd'i, babasından, bir
    adamdan. A proper name takes an apostrophe; a word of kinship ("babası") the buffer n of the possessive."""
    head, _sep, tail = name.partition(" (")
    word = head.rstrip()
    letters = [c for c in word.lower() if c.isalpha()]
    if not letters:
        return name
    vowels = [c for c in letters if c in "aeıioöuüâîû"]
    last = vowels[-1] if vowels else "e"
    back = last in "aıouâû"
    round_ = last in "ouöüû"
    ends_vowel = letters[-1] in "aeıioöuüâîû"
    # a word of kinship or a description ("babası", "bir adam") — not a name with its article ("ez-Zührî")
    last_word = next((w for w in reversed(word.split()) if any(c.isalpha() for c in w)), word)
    common = last_word[:1].islower() and not re.match(r"[ae][a-zş]{0,2}-", last_word)
    possessive = common and word.endswith(_TR_POSSESSIVE)
    if case == "abl":
        d = "d" if (possessive or letters[-1] not in "fstkçşhp") else "t"
        suffix = ("n" if possessive else "") + d + ("a" if back else "e") + "n"
    elif case == "gen":
        four = ("u" if back else "ü") if round_ else ("ı" if back else "i")
        suffix = ("n" + four + "n" if (possessive or ends_vowel) else four + "n")
    elif case == "acc":
        four = ("u" if back else "ü") if round_ else ("ı" if back else "i")
        suffix = ("n" if possessive else "y" if ends_vowel else "") + four
    else:
        suffix = ("n" if possessive else "y" if ends_vowel else "") + ("a" if back else "e")
    # a name ending in the sign of 'ayn ("Nâfi'", "Rufey'") has its apostrophe already: "Nâfi'den", not "Nâfi''den"
    out = word + ("" if common or word.endswith("'") else "'") + suffix
    return out + (" (" + tail if tail else "")


_tr_case = functools.lru_cache(maxsize=1 << 16)(_tr_case)       # the same names, thousands of times


def _said(text: str, code: str, **values) -> str:
    """A text of the interface in the language asked for, not the interface's own (the chain in Turkish under an
    English window)."""
    from isnady.core import i18n

    template = i18n.catalog(code).get(text, text) if code != "en" else text
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        return text.format(**{k: v for k, v in values.items() if k == "name"})


# a word of kinship that names someone's relative: whose, the narrator before it says ("هشام عن أبيه": Hisham's father)
_WHOSE = {"ابيه", "امه", "جده", "جدته", "عمه", "خاله", "اخيه", "اخته", "ابنه", "مولاه", "ابوه"}


def _known_as(person: dict | None, code: str) -> str:
    """An identified narrator by the short name he is known by, read in the language: "Urve b. ez-Zübeyr"."""
    if not person:
        return ""
    view = person.get("name_view") or {}
    arabic = view.get("arabic") or " ".join((person.get("display_name") or "").split()[:3])
    name, _spelled = name_reading(arabic, code) if arabic else ("", False)
    if code == "tr" and name.startswith("Ebî "):
        name = "Ebû " + name[4:]
    return name


def chain_in_words(chain: dict, code: str, people: dict | None = None) -> str:
    """The chain as the Arabic says it, in Turkish or English: "Kuteybe b. Saîd bize rivayet etti, Leys bize rivayet
    etti, Yezîd b. Ebî Habîb'den, … Hz. Peygamber ﷺ'den" / "Qutayba b. Sa'id narrated to us, Layth narrated to us,
    from Yazid b. Abi Habib, … from the Prophet ﷺ". "" for a language isnady cannot read names in, or no links."""
    parts = chain_word_parts(chain, code, people)
    if not parts:
        return ""
    text = ", ".join(p for p in parts if p)
    return text[:1].upper() + text[1:] + "."


def chain_link_names(chain: dict, code: str, people: dict | None = None) -> list[str]:
    """Each link of the chain as a name in the language, without its case: "Hişâm", "Hişâm'ın babası Urve b.
    ez-Zübeyr", "Ebû Hüreyre (r.a.)". people: the identified narrators by id (narrators.describe) — a "his father"
    then says whose father and who he is (Bayram, 2026-10-24: "babasi-kardesi gibi kavramlar bir supheli. Kimin
    babasi, kimin kardesi?"). On road A a Companion carries "(r.a.)" / "(RA)" (Sunni manners)."""
    if code not in CHAIN_LANGUAGES.values() or not chain.get("links"):
        return []
    names_out: list[str] = []
    bases: list[str] = []            # each link as a name, without its case: the owner of the next one's "his father"
    owners: list[str] = []           # whose relative each link is ("" for a link named by his own name)
    people = people or {}
    from isnady.core.normalize import normalize, normalize_with_map

    for index, link in enumerate(chain["links"]):
        person = people.get(link.get("person_id"))
        raw = link["raw_name"]
        folded, where = normalize_with_map(raw)
        honour = _HONOUR_RE.search(folded)
        if honour and honour.start() > 0:
            raw = raw[:where[honour.start()]]           # "… رضي الله عنها" is no part of her name
        words = raw.split()
        if len(words) > 1 and normalize(words[-1]) in ("انها", "انه", "انهما", "انهم"):
            words = words[:-1]                           # "أسماء بنت أبي بكر أنها": the "that she" of the text
        kin = ""
        if len(words) > 1 and normalize(words[0]) in _KIN:
            kin = _KIN[normalize(words[0])][0 if code == "tr" else 1]
            words = words[1:]                            # "أمه أسماء بنت أبي بكر": his mother, Asma' …
        raw = " ".join(words)
        # "حدثنا أبي" in a chain: the father of the narrator before — said as "his father", whose father, who he is
        raw = _KIN_THIRD.get(normalize(raw).strip(" ،,"), raw)
        name, _spelled = name_reading(raw, code)
        plain = name
        if kin and name:
            name = f"{kin} {name}"
        if not name:
            name = short_name(link["raw_name"])
        if code == "tr" and name.startswith("Ebî "):
            name = "Ebû " + name[4:]
        whose = (normalize(short_name(link["raw_name"]).split()[0]) in _WHOSE
                 or normalize(short_name(link["raw_name"])).strip(" ،,") in _KIN_ALONE) if link["raw_name"].strip() else False
        known_any = _known_as(person, code)
        known = known_any if whose else ""
        if whose and index and bases[index - 1]:
            # whose relative: the narrator before ("Hişâm'ın babası" / "Hisham's father"), and who he is when known;
            # "عن أبيه عن جده" is the grandfather of the man before the father (Sâlih b. İbrâhim's, not İbrâhim's)
            def first_word(raw_name: str) -> str:
                return (normalize(short_name(raw_name)).split() or [""])[0]

            owner = owners[index - 1] if (owners[index - 1] and first_word(link["raw_name"]) == "جده"
                                          and first_word(chain["links"][index - 1]["raw_name"]) in ("ابيه", "ابوه")) \
                else bases[index - 1]
            owners.append(owner)
            relation = kin or name
            relation = relation[:1].lower() + relation[1:]
            if code == "tr":
                name = f"{_tr_case(owner, 'gen')} {relation}" + (f" {plain}" if kin else f" {known}" if known else "")
            else:
                relation = re.sub(r"^(his|her) ", "", relation)
                name = f"{owner}'s {relation}" + (f", {plain}" if kin else f", {known}" if known else "")
            bases.append(known or (plain if kin else name))
        else:
            owners.append("")
            # inside the sentence the article and a word of kinship are written small: "ez-Zührî'den", "babasından"
            if re.match(r"(?:A[lnrstdz]|E[lnrstdzş]|Aş)-", name) or normalize(short_name(link["raw_name"])) in _KIN:
                name = name[:1].lower() + name[1:]
            if whose and known:
                name = f"{name} {known}" if code == "tr" else f"{name}, {known}"
            bases.append(known_any or name)
        if chain.get("tradition", "sunni") == "sunni" and _is_companion_link(link, person):
            name += " (r.a.)" if code == "tr" else " (RA)"
        names_out.append(name)
    return names_out


def _is_companion_link(link: dict, person: dict | None) -> bool:
    """A Companion at this link: identified as one (tabaqa 1, or Ibn Hajar's first rank), or, not identified, named
    as the chains name the Companions (core.companions)."""
    if person:
        ranks = [v.get("rank") for v in person.get("verdicts") or [] if v.get("rank_scheme") != "shia"]
        return person.get("tabaqa") == 1 or 1 in ranks
    from isnady.core import companions

    return companions.is_companion_name(short_name(link["raw_name"]))


def chain_word_parts(chain: dict, code: str, people: dict | None = None) -> list[str]:
    """The same, one piece for each link and one for whom it reaches (the end, a raised or a cut chain): what is
    written under each name of the chain on a hadith card ("Abdân bize rivayet etti" · "Ebû Hamza'dan" · …)."""
    names = chain_link_names(chain, code, people)
    if not names:
        return []
    parts = []
    for link, name in zip(chain["links"], names):
        term = link.get("transmission") or "bare"
        template = CHAIN_TEMPLATES.get(term, CHAIN_TEMPLATES["'an"])
        values = {"name": name}
        if code == "tr":
            values.update(name_abl=_tr_case(name, "abl"), name_acc=_tr_case(name, "acc"),
                          name_dat=_tr_case(name, "dat"), name_gen=_tr_case(name, "gen"))
        parts.append(_said(template, code, **values))
    key = chain.get("ends_with") or ("prophet" if chain.get("reaches_prophet") else "")
    if key and not chain.get("raised"):
        from isnady.core import traditions

        if code == "tr":
            whom = _MASUM_TR.get(key, key)
        else:
            whom = "the Prophet ﷺ" if key == "prophet" else (traditions.masum_label(key) or key)
        values = {"name": whom}
        if code == "tr":
            values["name_abl"] = _tr_case(whom, "abl")
        parts.append(_said(CHAIN_END, code, **values))
    elif chain.get("raised"):
        parts.append(_said(CHAIN_RAISED, code))
    elif chain.get("problem"):
        parts.append(_said(CHAIN_CUT, code))
    return parts


def compiler_of(book_key: str) -> dict | None:
    """The compiler of a book, for the head of its chains: {"arabic": "البخاري", "tr": "Buhârî", "en": "al-Bukhari"}."""
    from isnady.core import scholars

    s = next((x for x in scholars.SCHOLARS if book_key in x.get("compiler_of", [])), None)
    if s is None:
        return None
    return {"arabic": s.get("known_ar") or s.get("arabic", ""), "tr": s["tr"].split(" (")[0], "en": s["name"]}


def chain_codes(languages: list[str]) -> list[str]:
    """The languages, of those shown ("Turkish", "English" … in order; [] for every one), the chain can be said in."""
    from isnady.core import language

    names = language.sort(languages or list(CHAIN_LANGUAGES))      # in the order the texts are shown
    return list(dict.fromkeys(CHAIN_LANGUAGES[n] for n in names if n in CHAIN_LANGUAGES))


def hadith_id(conn: sqlite3.Connection, book: str, number: str) -> int | None:
    row = conn.execute(
        "SELECT h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id WHERE c.key = ? AND h.number = ?",
        (book, number.strip()),
    ).fetchone()
    return row[0] if row else None


def number_range(conn: sqlite3.Connection, book: str) -> dict | None:
    """The numbers of a book (CH2): {"first", "last", "count"} in the book's own order (number_sort), or None."""
    row = conn.execute(
        """SELECT COUNT(*), MIN(h.number_sort), MAX(h.number_sort) FROM hadiths h
           JOIN collections c ON c.id = h.collection_id WHERE c.key = ?""", (book,)).fetchone()
    if not row or not row[0]:
        return None
    first = conn.execute("""SELECT h.number FROM hadiths h JOIN collections c ON c.id = h.collection_id
                            WHERE c.key = ? ORDER BY h.number_sort, h.id LIMIT 1""", (book,)).fetchone()[0]
    last = conn.execute("""SELECT h.number FROM hadiths h JOIN collections c ON c.id = h.collection_id
                           WHERE c.key = ? ORDER BY h.number_sort DESC, h.id DESC LIMIT 1""", (book,)).fetchone()[0]
    return {"first": first, "last": last, "count": row[0]}


def _sort_key(number: str) -> float | None:
    """The place of a number written by the user in a book's order: "12a" after 12, "5:1740" as volume and hadith."""
    try:
        return float((number or "").strip())            # 7563, 402.2
    except ValueError:
        pass
    m = re.match(r"\s*(\d+)(?::(\d+))?", number or "")
    if not m:
        return None
    return float(m.group(1)) * 100000 + float(m.group(2)) if m.group(2) else float(m.group(1))


def numbers_starting(conn: sqlite3.Connection, book: str, prefix: str, limit: int = 12) -> list[str]:
    """The book's numbers that begin with what is typed, in the book's order (the completer of the number field)."""
    prefix = (prefix or "").strip()
    if not prefix:
        return []
    return [r[0] for r in conn.execute(
        """SELECT h.number FROM hadiths h JOIN collections c ON c.id = h.collection_id
           WHERE c.key = ? AND h.number LIKE ? ESCAPE '\\' ORDER BY h.number_sort, h.id LIMIT ?""",
        (book, prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%", limit))]


def step_number(conn: sqlite3.Connection, book: str, number: str, delta: int) -> str | None:
    """The number before (delta -1) or after (+1) a number in the book's order; for a number the book does not have,
    the nearest one on that side. The first number when nothing is written yet."""
    rng = number_range(conn, book)
    if rng is None:
        return None
    number = (number or "").strip()
    if not number:
        return rng["first"] if delta > 0 else rng["last"]
    here = conn.execute("""SELECT h.number_sort, h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id
                           WHERE c.key = ? AND h.number = ?""", (book, number)).fetchone()
    if here is None:
        key = _sort_key(number)
        if key is None:
            return rng["first"]
        here = (key, -1 if delta > 0 else 1 << 62)
    if delta > 0:
        row = conn.execute("""SELECT h.number FROM hadiths h JOIN collections c ON c.id = h.collection_id
                              WHERE c.key = ? AND (h.number_sort > ? OR (h.number_sort = ? AND h.id > ?))
                              ORDER BY h.number_sort, h.id LIMIT 1""", (book, here[0], here[0], here[1])).fetchone()
    else:
        row = conn.execute("""SELECT h.number FROM hadiths h JOIN collections c ON c.id = h.collection_id
                              WHERE c.key = ? AND (h.number_sort < ? OR (h.number_sort = ? AND h.id < ?))
                              ORDER BY h.number_sort DESC, h.id DESC LIMIT 1""",
                          (book, here[0], here[0], here[1])).fetchone()
    return row[0] if row else number


def nearest_number(conn: sqlite3.Connection, book: str, number: str) -> str | None:
    """The book's number closest to one it does not have ("7600" → the last, 7563)."""
    key = _sort_key(number)
    if key is None:
        return None
    row = conn.execute("""SELECT h.number FROM hadiths h JOIN collections c ON c.id = h.collection_id
                          WHERE c.key = ? ORDER BY ABS(h.number_sort - ?), h.number_sort LIMIT 1""",
                       (book, key)).fetchone()
    return row[0] if row else None


def position(conn: sqlite3.Connection, book: str, number: str) -> tuple[int, int] | None:
    """(place, count): where a number stands among the book's hadith in its own order — Muslim 93 is the 93rd of
    7,583 — or None for a number the book does not have. For "the hadith X of Y" beside the number field."""
    here = conn.execute("""SELECT h.number_sort, h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id
                           WHERE c.key = ? AND h.number = ?""", (book, (number or "").strip())).fetchone()
    if here is None:
        return None
    before, count = conn.execute(
        """SELECT SUM(CASE WHEN h.number_sort < ? OR (h.number_sort = ? AND h.id < ?) THEN 1 ELSE 0 END), COUNT(*)
           FROM hadiths h JOIN collections c ON c.id = h.collection_id WHERE c.key = ?""",
        (here[0], here[0], here[1], book)).fetchone()
    return (before or 0) + 1, count


def random_number(conn: sqlite3.Connection, book: str, with_chain: bool = True) -> str | None:
    """A number of the book chosen at random — of a hadith whose chain was read, when the book has any (Bayram,
    2026-10-25: "rasgele hadis dediginde bazen hicbirsey cikmiyor": Riyad al-Salihin, Mishkat, the Forty of
    al-Dehlawi and others give many hadith without a chain, and such a pick showed an empty page)."""
    if with_chain:
        row = conn.execute("""SELECT h.number FROM hadiths h JOIN collections c ON c.id = h.collection_id
                              WHERE c.key = ? AND EXISTS (SELECT 1 FROM isnads i JOIN isnad_links l ON l.isnad_id = i.id
                                                          WHERE i.hadith_id = h.id)
                              ORDER BY RANDOM() LIMIT 1""", (book,)).fetchone()
        if row:
            return row[0]
    row = conn.execute("""SELECT h.number FROM hadiths h JOIN collections c ON c.id = h.collection_id
                          WHERE c.key = ? ORDER BY RANDOM() LIMIT 1""", (book,)).fetchone()
    return row[0] if row else None


def describe(conn: sqlite3.Connection, hid: int) -> dict | None:
    """Book, number and neighbours of a hadith, for navigation."""
    row = conn.execute(
        """SELECT h.id, h.number, h.number_sort, h.collection_id, c.key, c.name FROM hadiths h
           JOIN collections c ON c.id = h.collection_id WHERE h.id = ?""", (hid,)
    ).fetchone()
    if row is None:
        return None
    prev = conn.execute(
        """SELECT id FROM hadiths WHERE collection_id = ? AND (number_sort < ? OR (number_sort = ? AND id < ?))
           ORDER BY number_sort DESC, id DESC LIMIT 1""", (row[3], row[2], row[2], row[0])
    ).fetchone()
    nxt = conn.execute(
        """SELECT id FROM hadiths WHERE collection_id = ? AND (number_sort > ? OR (number_sort = ? AND id > ?))
           ORDER BY number_sort, id LIMIT 1""", (row[3], row[2], row[2], row[0])
    ).fetchone()
    from isnady.core import titles

    return {"id": row[0], "number": row[1], "book": row[4], "book_name": titles.book(row[4], row[5]),
            "prev": prev[0] if prev else None, "next": nxt[0] if nxt else None}


def arabic_text(conn: sqlite3.Connection, hid: int) -> str | None:
    row = conn.execute(
        """SELECT t.text FROM texts t JOIN editions e ON e.id = t.edition_id
           WHERE t.hadith_id = ? AND e.language = 'Arabic' ORDER BY e.id LIMIT 1""", (hid,)
    ).fetchone()
    return row[0] if row else None


def split_text(text: str, raw_isnad: str | None) -> tuple[str, str]:
    """(isnad part, matn part) of the Arabic text, using the stored raw chain."""
    if not raw_isnad:
        return "", text
    at = text.find(raw_isnad)
    if at == -1:
        return "", text
    end = at + len(raw_isnad)
    return text[:end], text[end:]


def book_stats(conn: sqlite3.Connection) -> list[dict]:
    """Per book: chains read, split into narrators, reaching the Prophet (on road B: a Ma'sum), and why the rest
    were not split. Counted once per change of the database and kept (core.cache); the books' names follow the
    interface language."""
    from isnady.core import cache, titles

    rows = cache.kept(conn, "book-stats", _book_stats_counted)
    return [{**r, "name": titles.book(r["key"], r["name"])} for r in rows]


def _book_stats_counted(conn: sqlite3.Connection) -> list[dict]:
    from isnady.core import books

    out = []
    for r in conn.execute(
        f"""SELECT c.id, c.key, c.name, COUNT(*) AS chains, SUM(i.problem IS NULL) AS split,
                  SUM(i.problem IS NULL AND i.reaches_prophet = 1) AS marfu, COALESCE(c.tradition, 'sunni')
           FROM isnads i JOIN hadiths h ON h.id = i.hadith_id JOIN collections c ON c.id = h.collection_id
           WHERE i.derived_by IS NOT NULL AND (i.problem IS NULL OR i.ordinal = 1)
           GROUP BY c.id ORDER BY {books.order_sql(conn)}"""
    ):
        problems = conn.execute(
            """SELECT i.problem, COUNT(*) FROM isnads i JOIN hadiths h ON h.id = i.hadith_id
               WHERE h.collection_id = ? AND i.problem IS NOT NULL AND i.ordinal = 1 GROUP BY i.problem ORDER BY 2 DESC""",
            (r[0],)
        ).fetchall()
        links = conn.execute(
            """SELECT COUNT(*) FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id JOIN hadiths h ON h.id = i.hadith_id
               WHERE h.collection_id = ? AND i.problem IS NULL""", (r[0],)
        ).fetchone()[0]
        out.append({"key": r[1], "name": r[2], "chains": r[3], "split": r[4] or 0, "marfu": r[5] or 0,
                    "tradition": r[6],
                    "links": links, "problems": [(p, n) for p, n in problems]})
    return out
