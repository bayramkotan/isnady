"""The statistics in plain words (ST-EXP1, 2026-10-25).

Bayram: "Bu cok karisik! … Istatistiksel degerler en ince detayina kadar gosterilsin ama bunu istatistik bilmeyenlerde
anlayacak sekilde gosterilsin!" Every measure the Statistics page (and `iy stats`) shows has here:

- what it measures, in everyday words;
- how to read its value (what is small, what is large);
- what it means for the science of hadith;
- an example.

and a few functions that turn one value into a plain sentence ("τ 0.42: a clear but moderate relation"), so every
finding can say beside its figures what they mean. Qt-free: the page, the CLI and the exports use the same words.
"""

from __future__ import annotations

from isnady.core.i18n import N_, tr

# key -> (name, what it measures, how to read it, what it means for hadith science, an example)
TERMS: dict[str, tuple[str, str, str, str, str]] = {
    "share": (
        N_("Share (percentage)"),
        N_("How many out of every hundred."),
        N_("50% is half, 10% one in ten."),
        N_("Every share on this page is counted from the imported books, never guessed."),
        N_("“78% of the chains reach the Prophet ﷺ”: of every 100 chains read, 78 end with him."),
    ),
    "median": (
        N_("Median"),
        N_("The middle value: half of the cases are below it, half above."),
        N_("Unlike an average it is not pulled by a few very large or very small cases."),
        N_("The usual length of a chain: how many narrators usually stand between the compiler and the Prophet ﷺ."),
        N_("A median length of 5: half of the chains have 5 narrators or fewer, half 5 or more."),
    ),
    "gini": (
        N_("Gini coefficient"),
        N_("How unevenly something is shared out: here, how unevenly the transmission is spread over the narrators."),
        N_("0: every narrator carries the same share. 1: one man carries everything. Above 0.6 the load rests on a "
           "few."),
        N_("A high value is the classical madar: a few great narrators (al-Zuhri, Qatada, al-A'mash …) through whom "
           "most hadith pass. It is a fact of transmission, not a defect."),
        N_("Gini 0.75: a small group of narrators carries most of the hadith."),
    ),
    "lorenz": (
        N_("Lorenz curve"),
        N_("A picture of the same unevenness: the narrators sorted from the least to the most used, and how much of "
           "the transmission they carry together."),
        N_("The straight diagonal would be everyone carrying the same; the further the curve sags below it, the more "
           "the load rests on a few."),
        N_("Where the curve rises steeply at the end, those last few narrators are the pivots (madar) of the corpus."),
        N_("If the curve is at 20% when 80% of the narrators are counted, the busiest 20% carry 80% of the "
           "transmission."),
    ),
    "pagerank": (
        N_("PageRank (network weight)"),
        N_("How central a narrator is in the web of who narrates from whom — not only how often he appears, but how "
           "many chains lead through him."),
        N_("Shown in thousandths (‰) of the whole flow: the larger, the more central."),
        N_("It finds the narrators the transmission flows through, like the critics' talk of the 'pivot' (madar) of a "
           "hadith."),
        N_("A narrator with 12‰ carries about one hundredth of the whole flow of transmission."),
    ),
    "weakest": (
        N_("The weakest link"),
        N_("For each chain, the lowest-ranked of its identified narrators."),
        N_("A chain is graded by its weakest narrator: one weak man weakens the whole chain."),
        N_("This is the rule of the critics: “the chain follows the weakest of its men” (al-isnad yatba' "
           "akhass rijalih)."),
        N_("A chain of four trustworthy narrators and one weak one has a weak weakest link."),
    ),
    "time_gap": (
        N_("Years between teacher and student"),
        N_("For two neighbours in a chain, the year the student died minus the year the teacher died."),
        N_("Students usually die 20–60 years after their teachers. Over 110 years, or a student dying long "
           "before his teacher, is hard to believe."),
        N_("This is the critics' check of meeting (liqa') and contemporaneity (mu'asara): a pair that cannot have "
           "met points to a wrongly identified name, or a break in the chain (inqita')."),
        N_("A teacher who died in 110 AH and a student in 250 AH are 140 years apart: one of the two names is "
           "probably someone else."),
    ),
    "tabaqa_order": (
        N_("Generations in order"),
        N_("Whether the student belongs to the same or a later generation (tabaqa) than his teacher."),
        N_("Close to 100% is expected; the pairs out of order are listed."),
        N_("A student of an earlier generation than his teacher cannot be: a sign of a wrong identification."),
        N_("A Follower (tabaqa 3) narrating from a man of tabaqa 6 is out of order."),
    ),
    "kendall": (
        N_("Kendall's τb (rank correlation)"),
        N_("How far two orderings agree: here, whether the weaker a chain's narrator, the weaker the grade."),
        N_("0: no relation. Up to 0.1 hardly any, 0.1–0.3 weak, 0.3–0.5 moderate, above 0.5 strong. A "
           "minus sign: they go in opposite directions."),
        N_("A clear positive value shows the scholars' grades follow the narrators; that it is not near 1 shows what "
           "else they weighed: other routes (mutaba'at, shawahid), hidden defects ('ilal), the text."),
        N_("τb 0.35: a moderate relation — weaker narrators usually go with weaker grades, but not always."),
    ),
    "gamma": (
        N_("Goodman–Kruskal γ"),
        N_("The same question as τb, counting only the cases that are not tied."),
        N_("From −1 to +1; it is always larger than τb, because ties are left out."),
        N_("A second look at whether grades follow narrators."),
        N_("γ 0.55 beside τb 0.35 is the same relation, measured on the untied pairs."),
    ),
    "interval": (
        N_("95% interval"),
        N_("The range the true value very probably lies in, given how many cases there are."),
        N_("A narrow interval is a sure figure; a wide one, an uncertain one. If the whole interval is above zero "
           "(or below it), the relation is not chance."),
        N_("It tells how much weight a finding can bear — like the critics' care to say how sure a judgement is."),
        N_("τb 0.30 [0.25–0.35]: the true value is very probably between 0.25 and 0.35 — surely above zero."),
    ),
    "bootstrap": (
        N_("Bootstrap"),
        N_("A way to find the 95% interval: the hadith are drawn again at random many times and the measure "
           "recomputed each time."),
        N_("How much the result moves from draw to draw is how uncertain it is."),
        N_("It needs no assumption about how grades are spread."),
        N_("2,000 bootstrap samples: the measure computed 2,000 times on reshuffled hadith."),
    ),
    "spearman": (
        N_("Spearman's ρ (rank correlation)"),
        N_("Whether two measures rise and fall together, by their order only."),
        N_("+1: they rise together perfectly. −1: one falls as the other rises. 0: no relation. Up to 0.1 "
           "hardly any, 0.1–0.3 weak, 0.3–0.5 moderate, above 0.5 strong."),
        N_("Ranks and grades are ordered, never averaged; ρ respects that."),
        N_("ρ −0.40 between rank and how often a narrator appears: the most used narrators are the "
           "stronger ones."),
    ),
    "partial": (
        N_("Partial correlation (“the others held equal”)"),
        N_("The relation between two measures that is left when every other measure is held the same."),
        N_("Read like ρ; it removes what the two share only through a third."),
        N_("A long chain is not blamed for what its weak narrator does: each factor is credited only with its own "
           "part."),
        N_("Length and grade: ρ 0.20 alone, 0.05 with the weakest narrator held equal — length mattered "
           "mostly because long chains have more chances of a weak man."),
    ),
    "pvalue": (
        N_("p-value and q-value"),
        N_("How likely a result this large would be if there were no relation at all. q is the same, corrected for "
           "having looked at many results at once."),
        N_("Below 0.05: a relation beyond chance. Above it: it could be chance. It says nothing of how large the "
           "relation is."),
        N_("With hundreds of pairs some look related by chance; q keeps those out."),
        N_("q < 0.001: practically impossible by chance."),
    ),
    "odds": (
        N_("Odds ratio"),
        N_("How many times a factor multiplies the chance of a weaker grade."),
        N_("1: no effect. 2: twice the odds. 0.5: half. The interval beside it shows how sure it is."),
        N_("It measures how heavily a scholar's grade leans on a narrator of a given rank."),
        N_("Odds ratio 4.2 for a weak weakest narrator: such a chain has 4.2 times the odds of a weaker grade than one "
           "whose weakest narrator is trustworthy."),
    ),
    "ordinal": (
        N_("Ordinal regression (the hadith model)"),
        N_("A model that foretells a scholar's grade from the chain: its weakest narrator, its length, its other "
           "routes — all at once."),
        N_("Each factor gets an odds ratio; together they show what the grade follows and how much is left "
           "unexplained."),
        N_("What it cannot foretell is where the scholar weighed more than one chain: other routes, hidden defects, "
           "the text."),
        N_("The model foretells “sahih” for a chain of trustworthy men; a scholar who grades it da'if saw "
           "something the chain does not show."),
    ),
    "lr": (
        N_("Likelihood-ratio χ²"),
        N_("How much worse the model foretells the grades when one factor is taken out of it."),
        N_("The larger, the more that factor matters. p (Holm) below 0.05: it matters beyond chance."),
        N_("It ranks the parts of a chain by how much the grades depend on them."),
        N_("χ² 300 for the weakest narrator, 4 for length: the narrator decides far more than the length."),
    ),
    "r2": (
        N_("McFadden's R²"),
        N_("How much of the grades the model explains, beside a model that knows only how often each grade is "
           "given."),
        N_("For human judgement 0.1–0.2 is usual, 0.2–0.4 very good. It is not a percentage."),
        N_("A modest value is the finding itself: a scholar grades on all routes and the text, not on one chain."),
        N_("R² 0.18: the chain explains a real but partial share of the grade."),
    ),
    "somers": (
        N_("Somers' D"),
        N_("How well the model puts the hadith in the right order, from strong to weak."),
        N_("0: no better than chance. 1: perfect order. Above 0.4 is good."),
        N_("It asks whether the stronger chains get the stronger grades, even when the exact grade is missed."),
        N_("D 0.55: the model's order of the hadith mostly matches the scholar's."),
    ),
    "calibration": (
        N_("Calibration"),
        N_("Whether the model's probabilities can be taken at their word."),
        N_("Points on the diagonal: when the model says 70%, about 70 of 100 such hadith got that grade."),
        N_("It keeps the model honest: a model that is sure must be right as often as it says."),
        N_("A point at 0.8 across and 0.78 up is well calibrated."),
    ),
    "surprise": (
        N_("Surprises (graded otherwise than the chain foretells)"),
        N_("The hadith whose grade is far from what their chain alone would lead one to expect."),
        N_("The lower the model's probability for the grade given, the larger the surprise."),
        N_("Graded higher: usually strengthened by other routes (hasan or sahih li-ghayrihi). Graded lower: a hidden "
           "defect ('illa), an irregular text (shudhudh), a break the names do not show."),
        N_("A chain of trustworthy men graded da'if — worth reading: what did the scholar see?"),
    ),
    "stuart": (
        N_("Stuart–Maxwell test"),
        N_("Whether one scholar gives stronger or weaker grades overall than another, on the same hadith."),
        N_("p below 0.05 (“no”): one is milder or stricter beyond chance. The counts show who and how "
           "often."),
        N_("It measures the classical labels: the lenient (mutasahil) and the strict (mutashaddid)."),
        N_("On the same 3,000 hadith, scholar A grades higher than B 400 times and lower 90 times: A is milder."),
    ),
    "brant": (
        N_("Brant's test"),
        N_("Whether a factor weighs the same at every step of the grades (sahih→hasan as hasan→da'if)."),
        N_("“Yes, within chance”: the model's single weight is fair. “No”: the factor decides "
           "one step more than another."),
        N_("A weak narrator may decide between hasan and da'if more than between sahih and hasan."),
        N_("Odds ratio 1.5 at the first step, 4.0 at the second: the factor matters mostly for the lower grades."),
    ),
    "kruskal": (
        N_("Kruskal–Wallis test and ε²"),
        N_("Whether the chains of several books differ in a measure (length, weakest narrator …). ε² is how "
           "large the difference is."),
        N_("p below 0.05: the books differ beyond chance. ε²: 0.01 small, 0.06 medium, 0.14 large."),
        N_("It compares the books on the same footing, without averaging ranks."),
        N_("ε² 0.08: a medium difference between the books."),
    ),
    "cliff": (
        N_("Mann–Whitney test and Cliff's δ"),
        N_("Two books compared: how often a chain of the first is above one of the second, minus how often it is "
           "below."),
        N_("From −1 to +1. 0: no difference. Beyond ±0.15 small, ±0.33 medium, ±0.47 large."),
        N_("Which book's chains are longer, or rest on weaker narrators, and by how much."),
        N_("δ +0.30: a chain of the first book is longer than one of the second in 30% more of the pairs."),
    ),
    "jaccard": (
        N_("Shared narrators (Jaccard)"),
        N_("Of the narrators found in either of two books, the share found in both."),
        N_("0%: no narrator in common. 100%: the very same narrators."),
        N_("Books of one school and one period share most; it shows the common routes of transmission."),
        N_("40%: four in ten of the narrators of the two books appear in both."),
    ),
    "alpha": (
        N_("Krippendorff's α"),
        N_("How far all the graders of a book agree, beyond what chance would give, counting a near miss (hasan "
           "against sahih) as less than a far one (sahih against fabricated)."),
        N_("1: complete agreement. 0: no better than chance. Above 0.8 strong, 0.67–0.8 allows tentative "
           "conclusions, below 0.67 weak."),
        N_("It measures how much the scholars' judgement is shared — and where ijtihad differs."),
        N_("α 0.72: the scholars mostly agree, with real differences of judgement."),
    ),
    "kappa": (
        N_("Weighted kappa (κw)"),
        N_("The agreement of two graders beyond chance, a near miss counting less than a far one."),
        N_("1: perfect. 0: chance. Above 0.8 almost perfect, 0.6–0.8 substantial, 0.4–0.6 moderate, below "
           "0.4 weak."),
        N_("Two scholars may agree 70% of the time only because most hadith are sahih; kappa removes that."),
        N_("κw 0.65: substantial agreement between the two."),
    ),
    "dawid": (
        N_("Dawid–Skene model (the “true grade”)"),
        N_("A model that learns at once how each grader grades and what grade the graders' grades together most "
           "probably mean."),
        N_("For each hadith a grade and a certainty; for each grader a table of what he says for each true grade."),
        N_("It does not replace the scholars: the “true grade” is only what their grades imply together."),
        N_("Certainty 95%: the graders' grades point clearly to one grade."),
    ),
    "strictness": (
        N_("Strictness"),
        N_("The chance a grader gives a hadith a lower grade than the others' grades imply, minus the chance he "
           "gives a higher one."),
        N_("Below zero: stricter (mutashaddid). Above zero: more lenient (mutasahil). Measured, not assumed."),
        N_("It puts a number on the classical labels of the critics."),
        N_("−0.08: the grader grades about 8 in 100 hadith lower than the others would."),
    ),
}


def term(key: str) -> dict:
    """One measure, in the interface language."""
    name, what, read, hadith, example = TERMS[key]
    return {"key": key, "name": tr(name), "what": tr(what), "read": tr(read), "hadith": tr(hadith),
            "example": tr(example)}


def all_terms() -> list[dict]:
    return [term(k) for k in TERMS]


def find(text: str) -> dict | None:
    text = (text or "").strip().casefold()
    for k in TERMS:
        t = term(k)
        if text in (k, t["name"].casefold()) or text in t["name"].casefold() or text in TERMS[k][0].casefold():
            return t
    return None


# ---------------------------------------------------------------------- one value, one plain sentence
def strength(v: float | None) -> str:
    """The size of a correlation (τ, ρ, κ …) in words."""
    if v is None:
        return tr("not measurable")
    a = abs(v)
    return (tr("hardly any relation") if a < 0.1 else tr("a weak relation") if a < 0.3
            else tr("a moderate relation") if a < 0.5 else tr("a strong relation"))


def direction(v: float, same: str, opposite: str) -> str:
    return same if v >= 0 else opposite


def sure(lo: float | None, hi: float | None) -> str:
    """Whether a 95% interval rules out "no relation"."""
    if lo is None or hi is None:
        return ""
    if lo > 0 or hi < 0:
        return tr("too clear to be chance")
    return tr("could still be chance")


def by_q(q: float | None) -> str:
    if q is None:
        return ""
    return tr("too clear to be chance") if q < 0.05 else tr("could still be chance")


def odds(x: float) -> str:
    if x >= 1.05:
        return tr("{x:.1f} times the odds", x=x)
    if x <= 0.95:
        return tr("about {share} of the odds", share=f"{100 * x:.0f}%")
    return tr("no change in the odds")


def gini(g: float) -> str:
    return (tr("evenly shared") if g < 0.3 else tr("somewhat uneven") if g < 0.5
            else tr("uneven: a minority carries most") if g < 0.7 else tr("very uneven: a few carry most of it"))


def alpha(a: float) -> str:
    return (tr("strong agreement") if a >= 0.8 else tr("enough agreement for tentative conclusions") if a >= 0.667
            else tr("weak agreement"))


def kappa(k: float) -> str:
    return (tr("almost perfect agreement") if k >= 0.8 else tr("substantial agreement") if k >= 0.6
            else tr("moderate agreement") if k >= 0.4 else tr("weak agreement"))


def r2(v: float) -> str:
    return (tr("a small part") if v < 0.1 else tr("a usual share for human judgement") if v < 0.2
            else tr("a very good share for human judgement"))


def somers(v: float) -> str:
    return (tr("an order hardly better than chance") if v < 0.2 else tr("a fair order") if v < 0.4
            else tr("a good order") if v < 0.6 else tr("a very good order"))


def eps2(v: float) -> str:
    return (tr("a negligible difference") if v < 0.01 else tr("a small difference") if v < 0.06
            else tr("a medium difference") if v < 0.14 else tr("a large difference"))


def cliff(d: float) -> str:
    a = abs(d)
    return (tr("a negligible difference") if a < 0.15 else tr("a small difference") if a < 0.33
            else tr("a medium difference") if a < 0.47 else tr("a large difference"))
