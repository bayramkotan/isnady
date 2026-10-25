"""The hadith model (ST7-H): what a scholar's grade follows, measured — an ordinal regression of the grade on the
chain.

For every graded hadith of a book, a scholar's grade (sahih … fabricated, an ORDERED category) is modelled from what
its chains show: the weakest identified narrator of its best chain (as categories, never a number), how many weak or
unknown narrators that chain carries, its length, how many of its names are not identified, how many chains the hadith
has in the book (mutaba'at within the book), its other narrations in other books (takhrij), whether it stops short of
the Prophet (mawquf / maqtu'), and whether its chain has a link implausible in time or generation.

The model is the proportional-odds (cumulative logit) model: P(grade at or above k) rises and falls with one linear
predictor η = x·β, with its own threshold for each step of the grade scale. A positive β pushes towards a WEAKER grade;
exp(β) is the odds ratio — how much a unit of the factor multiplies the odds of a weaker grade. Pure Python: hadith
with identical predictors are grouped, fitted by Fisher scoring (BHHH information), standard errors from its inverse.

What it gives: the odds ratios with 95% intervals and Wald tests; a likelihood-ratio test for every factor (refitting
without it); McFadden's R², accuracy against the base rate, Somers' D, calibration; the probability of every grade for
every hadith; and the SURPRISES — hadith graded far higher than their chain foretells (strengthened by other routes:
shawahid, mutaba'at) or far lower (a hidden defect: 'illa, shudhudh). A model of the scholars' practice, not a verdict.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict

from isnady.core import stats_corpus as sc
from isnady.core.i18n import N_, tr

METHOD = "isnady-models-2"
MIN_CATEGORY = 15             # a grade given fewer times than this joins its weaker neighbour (thresholds need data)
SURPRISE = 0.05               # below this probability a surprise is called strong (shown, counted)

# the factors: (key, label, explanation). A block is one factor; a categorical factor is a block of indicators.
WEAKEST_LEVELS = ["Companion only", "Trustworthy", "Truthful", "Acceptable", "Weak / unknown", "Rejected", "None ranked"]
REFERENCE = "Trustworthy"
BLOCKS = [
    ("weakest", N_("Weakest narrator"), N_("the weakest identified narrator of the hadith's best chain, against a chain whose "
                                    "weakest is trustworthy (thiqa)")),
    ("weak_count", N_("More weak narrators"), N_("each further narrator of rank 7 or weaker (mastur, da'if, majhul …) in that "
                                          "chain beyond the first")),
    ("length", N_("Length"), N_("each further name in the chain")),
    ("unidentified", N_("Names not identified"), N_("each name of the chain not matched to a narrator of the Taqrib")),
    ("routes", N_("Chains in the book"), N_("each further chain the hadith has in the same book (mutaba'at within the book)")),
    ("takhrij", N_("Narrations elsewhere"), N_("each further narration of the hadith found in another book (takhrij)")),
    ("mawquf", N_("Stops short of the Prophet"), N_("the chain ends with a Companion or a Successor (mawquf, maqtu')")),
    ("doubtful", N_("A doubtful link"), N_("the chain has a pair too far apart in time, or out of the order of generations")),
]
SUNNI = sc.Road("sunni")


def blocks_for(road: "sc.Road") -> list[tuple[str, str, str]]:
    """BLOCKS in the words of the road (SH1): road B's critic is al-Najashi, its chains end at a Ma'sum."""
    if not road.shia:
        return BLOCKS
    words = {
        "weakest": (N_("Weakest narrator"), N_("the weakest identified narrator of the hadith's best chain in "
                                               "al-Najashi's categories, against a chain whose weakest is "
                                               "trustworthy (thiqa)")),
        "weak_count": (N_("More weak narrators"), N_("each further narrator al-Najashi calls weak in that chain beyond "
                                                     "the first")),
        "unidentified": (N_("Names not identified"), N_("each name of the chain not matched to a narrator of "
                                                        "al-Najashi")),
        "mawquf": (N_("Stops short of a Ma'sum"), N_("the chain does not reach the Prophet or an Imam (it ends with a "
                                                     "narrator)")),
    }
    return [(k, *words[k]) if k in words else (k, lab, e) for k, lab, e in BLOCKS]


# ------------------------------------------------------------------ small numerics
def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    e = math.exp(z)
    return e / (1 + e)


def _solve(a: list[list[float]], b: list[float]) -> list[float] | None:
    """a x = b by Gauss–Jordan with partial pivoting; None when a is singular."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            return None
        m[col], m[piv] = m[piv], m[col]
        p = m[col][col]
        m[col] = [v / p for v in m[col]]
        for r in range(n):
            if r != col and m[r][col]:
                f = m[r][col]
                m[r] = [v - f * w for v, w in zip(m[r], m[col])]
    return [m[i][n] for i in range(n)]


def _inverse(a: list[list[float]]) -> list[list[float]] | None:
    n = len(a)
    cols = []
    for j in range(n):
        e = [0.0] * n
        e[j] = 1.0
        x = _solve(a, e)
        if x is None:
            return None
        cols.append(x)
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def normal_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2))


def chi2_sf(x: float, df: int) -> float:
    """P(χ² > x) for df degrees of freedom: the regularized upper incomplete gamma Q(df/2, x/2)."""
    if x <= 0:
        return 1.0
    a, x = df / 2, x / 2
    if x < a + 1:                                   # the series for P, then Q = 1 − P
        term = total = 1 / a
        n = a
        for _ in range(500):
            n += 1
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-12:
                break
        return max(0.0, 1 - total * math.exp(-x + a * math.log(x) - math.lgamma(a)))
    b = x + 1 - a                                   # the continued fraction for Q (Lentz)
    c, d = 1 / 1e-300, 1 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return min(1.0, math.exp(-x + a * math.log(x) - math.lgamma(a)) * h)


def holm(pvalues: list[float]) -> list[float]:
    """Holm's step-down adjustment: several factors are tested at once."""
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    out, running = [0.0] * len(pvalues), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[i]))
        out[i] = running
    return out


# ------------------------------------------------------------------ the ordinal model
def fit_ordinal(groups: list[tuple[tuple, int, int]], categories: int, iterations: int = 100) -> dict | None:
    """The proportional-odds model by Fisher scoring. groups = [(x, y, weight)], y in 0..categories−1 (0 the
    strongest grade). Parameters: categories−1 thresholds, then one β per column of x. Returns the estimates, their
    covariance, the log-likelihood and convergence; None when the information matrix is singular."""
    p = len(groups[0][0]) if groups else 0
    k = categories - 1
    total = sum(w for _x, _y, w in groups)
    counts = Counter()
    for _x, y, w in groups:
        counts[y] += w
    cum, alphas = 0, []
    for j in range(k):                               # start at the marginal cumulative logits
        cum += counts[j]
        q = min(max(cum / total, 1e-4), 1 - 1e-4)
        alphas.append(math.log(q / (1 - q)))
    params = alphas + [0.0] * p

    def loglik_and_scores(theta):
        a, beta = theta[:k], theta[k:]
        ll, scores = 0.0, []
        for x, y, w in groups:
            eta = sum(b * v for b, v in zip(beta, x))
            upper = _sigmoid(a[y] - eta) if y < k else 1.0
            lower = _sigmoid(a[y - 1] - eta) if y > 0 else 0.0
            prob = max(upper - lower, 1e-300)
            ll += w * math.log(prob)
            fu = upper * (1 - upper) if y < k else 0.0
            fl = lower * (1 - lower) if y > 0 else 0.0
            g = [0.0] * (k + p)
            if y < k:
                g[y] += fu / prob
            if y > 0:
                g[y - 1] -= fl / prob
            d_eta = (fl - fu) / prob
            for j, v in enumerate(x):
                g[k + j] = d_eta * v
            scores.append((g, w))
        return ll, scores

    ll, scores = loglik_and_scores(params)
    converged = False
    for _ in range(iterations):
        n = k + p
        info = [[0.0] * n for _ in range(n)]
        grad = [0.0] * n
        for g, w in scores:
            for i in range(n):
                if g[i]:
                    grad[i] += w * g[i]
                    gi = w * g[i]
                    row = info[i]
                    for j in range(n):
                        row[j] += gi * g[j]
        step = _solve(info, grad)
        if step is None:
            return None
        scale = 1.0
        while scale > 1e-4:
            trial = [v + scale * s for v, s in zip(params, step)]
            if all(trial[j] < trial[j + 1] for j in range(k - 1)):
                new_ll, new_scores = loglik_and_scores(trial)
                if new_ll >= ll - 1e-9:
                    break
            scale /= 2
        else:
            break
        improvement = new_ll - ll
        params, ll, scores = trial, new_ll, new_scores
        if abs(improvement) < 1e-7:
            converged = True
            break
    # standard errors from the OBSERVED information: the Hessian of the log-likelihood at the estimate, by central
    # differences of the analytic score (checked against statsmodels' OrderedModel: the same estimates and errors)
    n = k + p

    def total_score(theta):
        _ll, sc_ = loglik_and_scores(theta)
        out = [0.0] * n
        for g, w in sc_:
            for i in range(n):
                out[i] += w * g[i]
        return out

    info = [[0.0] * n for _ in range(n)]
    for i in range(n):
        h = 1e-5 * max(1.0, abs(params[i]))
        up, down = params[:], params[:]
        up[i] += h
        down[i] -= h
        su, sd = total_score(up), total_score(down)
        for j in range(n):
            info[i][j] = -(su[j] - sd[j]) / (2 * h)
    info = [[(info[i][j] + info[j][i]) / 2 for j in range(n)] for i in range(n)]
    cov = _inverse(info)
    if cov is None:
        return None
    return {"params": params, "cov": cov, "loglik": ll, "converged": converged, "k": k, "p": p, "n": total}


def predict(params: list[float], k: int, x: tuple) -> list[float]:
    a, beta = params[:k], params[k:]
    eta = sum(b * v for b, v in zip(beta, x))
    cum = [_sigmoid(a[j] - eta) for j in range(k)] + [1.0]
    return [cum[0]] + [cum[j] - cum[j - 1] for j in range(1, k + 1)]


# ------------------------------------------------------------------ the data
def hadith_features(conn: sqlite3.Connection, collection: str, road: "sc.Road | None" = None) -> dict[int, dict]:
    """For every hadith of a book with at least one chain split into names: its factors (see BLOCKS), on the
    book's own road (SH1)."""
    road = road or sc.road_of(conn, collection)
    persons = sc._persons(conn, road.tradition)
    book = conn.execute("SELECT id FROM collections WHERE key = ?", (collection,)).fetchone()
    if not book:
        return {}
    chains = sc._chains(conn, [book[0]])
    by_hadith: dict[int, list] = defaultdict(list)
    for c in chains:
        if c["links"]:
            by_hadith[c["hadith"]].append(c)
    try:
        takhrij = dict(conn.execute("SELECT hadith_a, COUNT(*) FROM hadith_relations GROUP BY hadith_a").fetchall())
    except sqlite3.Error:
        takhrij = {}
    out = {}
    for h, cs in by_hadith.items():
        described = []
        for c in cs:
            links = c["links"]
            ranks = [persons[p]["rank"] for p in links if p in persons and persons[p]["rank"] in road.group_of]
            ids = [p for p in links if p in persons]
            if ranks:
                weakest = road.levels[road.group_of[max(ranks)]]
            else:
                weakest = "None ranked"
            doubtful = False
            for s, t in zip(links, links[1:]):
                if s in persons and t in persons:
                    ds, dt = persons[s]["death"], persons[t]["death"]
                    if ds and dt and (ds - dt > 110 or ds - dt < -60):
                        doubtful = True
                    ts, tt = persons[s]["tabaqa"], persons[t]["tabaqa"]
                    if ts and tt and ts < tt:
                        doubtful = True
            described.append({
                # the weak narrators BEYOND the first: the first is already the weakest link
                "weakest": weakest, "weak_count": max(0, sum(1 for r in ranks if r >= road.weak_from) - 1), "length": len(links),
                "unidentified": len(links) - len(ids), "mawquf": 0 if c["reaches"] else 1, "doubtful": int(doubtful),
                "order": (road.levels.index(weakest) if weakest != "None ranked" else 9, len(links) - len(ids)),
            })
        best = min(described, key=lambda d: d["order"])       # the strongest weakest link, then the most identified
        best = dict(best)
        best.pop("order")
        best["routes"] = len(cs)
        best["takhrij"] = takhrij.get(h, 0)
        out[h] = best
    return out


def _design(feats: list[dict], blocks: list[str], road: "sc.Road" = SUNNI) -> tuple[list[str], list[str], callable]:
    """The columns of x for the chosen blocks: indicators for the weakest narrator (against Trustworthy, levels
    with fewer than 10 hadith folded into their neighbour), numbers capped where long tails would dominate."""
    columns, column_block = [], []
    levels = []
    if "weakest" in blocks:
        seen = Counter(f["weakest"] for f in feats)
        levels = [lv for lv in road.levels if lv != road.reference and seen[lv] >= 10]
        columns += [f"Weakest: {lv}" for lv in levels]
        column_block += ["weakest"] * len(levels)
    caps = {"weak_count": 3, "length": 9, "unidentified": 6, "routes": 5, "takhrij": 5, "mawquf": 1, "doubtful": 1}
    numeric = [b for b in blocks if b != "weakest"]
    for b in numeric:
        columns.append(dict((k, lab) for k, lab, _e in blocks_for(road))[b])
        column_block.append(b)

    def row(f: dict) -> tuple:
        values = [1.0 if f["weakest"] == lv else 0.0 for lv in levels]
        values += [float(min(f[b], caps[b])) for b in numeric]
        return tuple(values)
    return columns, column_block, row


def _varying(feats: list[dict]) -> list[str]:
    """The blocks the data lets the model estimate: a factor that never varies tells nothing."""
    keep = []
    for key, _l, _e in BLOCKS:
        values = {f[key] for f in feats}
        if len(values) > 1:
            keep.append(key)
    return keep


def _merge_categories(ys: list[int], road: "sc.Road" = SUNNI) -> tuple[dict[int, int], list[str]]:
    """Grades given fewer than MIN_CATEGORY times join their weaker neighbour (or stronger, at the end)."""
    order = list(range(len(road.grade_order)))       # 0 sahih … 4 fabricated (road B: 0 sahih … 3 da'if)
    counts = Counter(ys)
    groups = [[c] for c in order if counts[c]]
    changed = True
    while changed and len(groups) > 2:
        changed = False
        for i, g in enumerate(groups):
            if sum(counts[c] for c in g) < MIN_CATEGORY:
                j = i + 1 if i + 1 < len(groups) else i - 1
                groups[min(i, j)] = sorted(groups[i] + groups[j])
                del groups[max(i, j)]
                changed = True
                break
    mapping = {c: gi for gi, g in enumerate(groups) for c in g}
    labels = [" or ".join(road.grade_names[road.grade_order[c]] for c in g) for g in groups]
    return mapping, labels


def _fit_blocks(rows: list[tuple[dict, int]], blocks: list[str], categories: int, road: "sc.Road" = SUNNI):
    columns, column_block, make = _design([f for f, _y in rows], blocks, road)
    grouped = Counter((make(f), y) for f, y in rows)
    groups = [(x, y, w) for (x, y), w in grouped.items()]
    fit = fit_ordinal(groups, categories)
    return fit, columns, column_block, make


def model_grader(conn: sqlite3.Connection, collection: str, grader: str, by_hadith: dict[int, int],
                 features: dict[int, dict], numbers: dict[int, str], road: "sc.Road" = SUNNI) -> dict | None:
    """The model of one scholar's grades of one book, on the book's road."""
    rows_raw = [(features[h], road.grade_order.index(g), h) for h, g in by_hadith.items()
                if h in features and g in road.grade_order]
    if len(rows_raw) < 100:
        return None
    mapping, labels = _merge_categories([y for _f, y, _h in rows_raw], road)
    if len(labels) < 2:
        return None
    rows = [(f, mapping[y]) for f, y, _h in rows_raw]
    blocks = _varying([f for f, _y in rows])
    fit, columns, column_block, make = _fit_blocks(rows, blocks, len(labels), road)
    if fit is None:
        return None
    k = fit["k"]
    null = fit_ordinal([((), y, w) for y, w in Counter(y for _f, y in rows).items()], len(labels))
    ll0 = null["loglik"] if null else None
    coefs = []
    for j, (name, block) in enumerate(zip(columns, column_block)):
        b = fit["params"][k + j]
        se = math.sqrt(max(fit["cov"][k + j][k + j], 0.0))
        z = b / se if se else 0.0
        coefs.append({"name": name, "block": block, "beta": b, "se": se, "or": math.exp(b),
                      "or_ci": [math.exp(b - 1.96 * se), math.exp(b + 1.96 * se)], "p": 2 * normal_sf(abs(z))})
    tests = []
    for block in blocks:
        reduced = [b for b in blocks if b != block]
        if reduced:
            fit_r, cols_r, _cb, _m = _fit_blocks(rows, reduced, len(labels), road)
            ll_r = fit_r["loglik"] if fit_r else None
        else:
            ll_r = ll0
        if ll_r is None:
            continue
        stat = max(0.0, 2 * (fit["loglik"] - ll_r))
        df = sum(1 for cb in column_block if cb == block)
        tests.append({"block": block, "label": dict((k2, lab) for k2, lab, _e in blocks_for(road))[block], "chi2": stat,
                      "df": df, "p": chi2_sf(stat, df)})
    for t, adj in zip(tests, holm([t["p"] for t in tests])):
        t["p_holm"] = adj
    # predictions: accuracy, Somers' D, calibration, the surprises
    commonest, count = Counter(y for _f, y in rows).most_common(1)[0]
    hits, base = 0, count / len(rows)
    table = [[0] * len(labels) for _ in range(20)]
    calibration = defaultdict(lambda: [0.0, 0, 0])
    above, below = [], []
    for f, y, h in rows_raw:
        yy = mapping[y]
        probs = predict(fit["params"], k, make(f))
        if max(range(len(probs)), key=probs.__getitem__) == yy:
            hits += 1
        expected = sum(i * q for i, q in enumerate(probs)) / max(1, len(probs) - 1)
        table[min(19, int(expected * 20))][yy] += 1
        bin_ = min(9, int(probs[0] * 10))
        cal = calibration[bin_]
        cal[0] += probs[0]
        cal[1] += 1
        cal[2] += yy == 0
        likely = max(range(len(probs)), key=probs.__getitem__)
        item = {"hadith_id": h, "number": numbers.get(h, str(h)), "grade": labels[yy], "likely": labels[likely],
                "probs": [round(q, 4) for q in probs], "factors": f}
        # graded STRONGER than the model's most likely grade: how unlikely this grade or a stronger one was
        if yy < likely:
            above.append(dict(item, p=sum(probs[:yy + 1])))
        elif yy > likely:
            below.append(dict(item, p=sum(probs[yy:])))
    tau, gamma = sc.kendall_from_table(table)
    above.sort(key=lambda d: d["p"])
    below.sort(key=lambda d: d["p"])
    return {
        "grader": grader, "book": collection, "n": len(rows), "labels": labels, "blocks": blocks,
        "coefficients": coefs, "thresholds": fit["params"][:k], "converged": fit["converged"],
        "loglik": fit["loglik"], "loglik0": ll0, "mcfadden": (1 - fit["loglik"] / ll0) if ll0 else None,
        "aic": 2 * (k + fit["p"]) - 2 * fit["loglik"], "accuracy": hits / len(rows), "base_rate": base,
        "base_label": labels[commonest],
        "somers_d": somers_d(table), "tau_b": tau, "gamma": gamma,
        "lr_all": {"chi2": 2 * (fit["loglik"] - ll0) if ll0 else None, "df": fit["p"],
                   "p": chi2_sf(2 * (fit["loglik"] - ll0), fit["p"]) if ll0 else None},
        "tests": tests,
        "calibration": [[round(c[0] / c[1], 4), round(c[2] / c[1], 4), c[1]] for _b, c in sorted(calibration.items())
                        if c[1]],
        "graded_higher": above[:60], "graded_higher_total": len(above),
        "graded_higher_strong": sum(1 for d in above if d["p"] <= SURPRISE),
        "graded_lower": below[:60], "graded_lower_total": len(below),
        "graded_lower_strong": sum(1 for d in below if d["p"] <= SURPRISE),
    }


def somers_d(table: list[list[int]]) -> float | None:
    """Somers' D of the columns (the grade) on the rows (the model's expected grade): (C − D) / pairs not tied on rows."""
    rows, cols = len(table), len(table[0]) if table else 0
    concordant = discordant = 0
    for i in range(rows):
        for j in range(cols):
            nij = table[i][j]
            if nij:
                for a in range(i + 1, rows):
                    for b in range(cols):
                        if b > j:
                            concordant += nij * table[a][b]
                        elif b < j:
                            discordant += nij * table[a][b]
    n = sum(map(sum, table))
    pairs = n * (n - 1) / 2 - sum(s * (s - 1) / 2 for s in (sum(r) for r in table))
    return (concordant - discordant) / pairs if pairs else None


def analyse(conn: sqlite3.Connection, collection: str | None = None, progress=None) -> dict:
    say = progress or (lambda _m: None)
    books = [(key, name) for _id, key, name in sc._books(conn, collection)]
    road = sc.road_of(conn, collection)
    models = []
    for key, name in books:
        data = road.load(conn, key)
        if not data:
            continue
        say(tr("Reading the chains of {name}", name=name))
        features = hadith_features(conn, key, road)
        numbers = dict(conn.execute("SELECT h.id, h.number FROM hadiths h JOIN collections c ON c.id = h.collection_id "
                                    "WHERE c.key = ?", (key,)).fetchall())
        for grader, by_hadith in sorted(data.items()):
            say(tr("Fitting the model of {grader} — {name}", grader=grader, name=name))
            m = model_grader(conn, key, grader, by_hadith, features, numbers, road)
            if m:
                m["book_name"] = name
                models.append(m)
    # the surprises several scholars share: more telling than one scholar's (his own judgement, a slip, a variant)
    shared = []
    for key, name in books:
        mine = [m for m in models if m["book"] == key]
        if len(mine) < 2:
            continue
        for side in ("graded_higher", "graded_lower"):
            seen: dict = defaultdict(list)
            for m in mine:
                for d in m[side]:
                    seen[d["hadith_id"]].append((m["grader"], d["grade"], d["likely"], d["p"], d["number"], d["factors"]))
            for h, items in seen.items():
                if len(items) >= 2:
                    shared.append({"side": side, "book": name, "hadith_id": h, "number": items[0][4],
                                   "graders": [[g, grade, likely, p] for g, grade, likely, p, _n, _f in items],
                                   "factors": items[0][5]})
    shared.sort(key=lambda s: (-len(s["graders"]), sum(g[3] for g in s["graders"]) / len(s["graders"])))
    return {"method": METHOD, "collection": collection, "surprise": SURPRISE, "tradition": road.tradition,
            "levels": road.levels, "reference": road.reference, "critic": road.critic,
            "blocks": [[k, lab, e] for k, lab, e in blocks_for(road)], "models": models, "shared": shared[:80]}


def cached(conn: sqlite3.Connection, collection: str | None = None, progress=None, recompute: bool = False,
           saved_only: bool = False) -> dict:
    """The models from data_dir()/derived/ while the data is unchanged; fitted and written otherwise (DX1)."""
    from isnady.data.paths import data_dir

    path = data_dir() / "derived" / sc.cache_name("models", collection)
    stamp = sc.fingerprint(conn, collection) + METHOD
    if not recompute and path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved.get("fingerprint") == stamp:
                saved["from_file"] = str(path)
                return saved
        except (OSError, ValueError):
            pass
    if saved_only:
        from isnady.core.stats_jobs import NotSaved

        raise NotSaved(str(path))
    from isnady.core import log

    with log.timed("statistics", f"models computed for {collection or 'all books'}"):
        result = analyse(conn, collection, progress)
    result["fingerprint"] = stamp
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    result["from_file"] = None
    return result
