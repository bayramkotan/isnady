"""The correlation and test laboratory (ST7-C): every measure against every other, and the tests that say whether a
difference is real.

  * Hadith: the factors of each hadith's best chain (weakest narrator, weak narrators, length, names not identified,
    chains in the book, narrations elsewhere, stopping short of the Prophet, a doubtful link), its place in the book,
    every scholar's grade and how far the scholars disagree — a Spearman matrix with Benjamini–Hochberg q-values,
    and the PARTIAL correlations: what each pair shares when all the others are held equal.
  * Narrators: Ibn Hajar's rank, generation, year of death, how often in the chains, in how many hadith, how many
    teachers and students, PageRank — the same two matrices.
  * Scholars of one book: is one scholar's distribution of grades the same as another's on the same hadith?
    Stuart–Maxwell's test of marginal homogeneity (the paired, ordered version of "do they grade alike overall").
  * The hadith model (core.stats_models): Brant's test of its proportional-odds assumption — does each factor weigh
    the same at every step of the grades (sahih/hasan, hasan/da'if …)?
  * Books: Kruskal–Wallis across the books for the chains' weakest narrator, length and identified share, with
    epsilon² (its effect size); pairwise Mann–Whitney with Cliff's delta, Holm-adjusted.

Two roads (SH1): a Shia book (or "@shia") is measured on its own scale — al-Najashi's four categories for the
narrators, the four Imami grades (sahih, hasan, muwaththaq, da'if) of al-Majlisi and al-Behbudi, chains ending at a
Ma'sum; never on Ibn Hajar's ranks or the Sunni grade groups (core.stats_corpus.Road).

Ranks and grades are ordered categories (SK): every test here is a rank test; nothing is averaged. Qt-free and
numpy-free; computed once and kept (DX1).
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict

from isnady.core import stats_corpus as sc
from isnady.core import stats_models as sm

METHOD = "isnady-lab-3"
ALPHA = 0.05                 # a q or Holm-adjusted p below this is called beyond chance


# ------------------------------------------------------------------ distributions
def _betacf(a: float, b: float, x: float) -> float:
    """The continued fraction of the incomplete beta function (Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = tiny if abs(d) < tiny else d
    d = 1 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """The regularized incomplete beta I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def t_two_sided(t: float, df: float) -> float:
    if df <= 0:
        return 1.0
    return betainc(df / 2, 0.5, df / (df + t * t))


def bh(pvalues: list[float]) -> list[float]:
    """Benjamini–Hochberg q-values: the false-discovery rate when every p up to this one is called significant."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    q = [0.0] * m
    running = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        running = min(running, pvalues[i] * m / (rank + 1))
        q[i] = running
    return q


# ------------------------------------------------------------------ rank statistics
def rankdata(values: list[float]) -> list[float]:
    """Ranks 1..n, ties given their average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 3:
        return None
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else None


def spearman(x: list, y: list) -> dict:
    """Spearman's rho on the cases where both are known, with its two-sided p (t with n − 2 df)."""
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    n = len(pairs)
    if n < 10:
        return {"rho": None, "n": n, "p": None}
    rho = _pearson(rankdata([a for a, _b in pairs]), rankdata([b for _a, b in pairs]))
    if rho is None:
        return {"rho": None, "n": n, "p": None}
    rho = max(-1.0, min(1.0, rho))
    t = rho * math.sqrt((n - 2) / max(1e-12, 1 - rho * rho))
    return {"rho": rho, "n": n, "p": t_two_sided(t, n - 2)}


def correlation_matrix(names: list[str], columns: list[list]) -> dict:
    """Spearman's rho of every pair (pairwise complete), BH q-values over the pairs, and the PARTIAL correlations
    (each pair with all the others held equal) on the cases where every variable is known."""
    k = len(names)
    cells = [[None] * k for _ in range(k)]
    flat = []
    for i in range(k):
        for j in range(i + 1, k):
            s = spearman(columns[i], columns[j])
            cells[i][j] = cells[j][i] = s
            if s["p"] is not None:
                flat.append((i, j, s["p"]))
    for (i, j, _p), q in zip(flat, bh([p for _i, _j, p in flat])):
        cells[i][j]["q"] = cells[j][i]["q"] = q
    # partial: ranks of the complete cases → correlation matrix → its inverse
    complete = [r for r in range(len(columns[0])) if all(col[r] is not None for col in columns)]
    partial = None
    if len(complete) > k + 10:
        ranked = [rankdata([columns[c][r] for r in complete]) for c in range(k)]
        keep = [c for c in range(k) if len(set(ranked[c])) > 1]
        if len(keep) >= 3:
            corr = [[1.0 if a == b else (_pearson(ranked[a], ranked[b]) or 0.0) for b in keep] for a in keep]
            inv = sm._inverse(corr)
            if inv is not None:
                n, m = len(complete), len(keep)
                partial = [[None] * k for _ in range(k)]
                pflat = []
                for a in range(m):
                    for b in range(a + 1, m):
                        denom = math.sqrt(abs(inv[a][a] * inv[b][b]))
                        r = max(-1.0, min(1.0, -inv[a][b] / denom)) if denom else 0.0
                        df = n - 2 - (m - 2)
                        t = r * math.sqrt(df / max(1e-12, 1 - r * r))
                        cell = {"rho": r, "n": n, "p": t_two_sided(t, df)}
                        partial[keep[a]][keep[b]] = partial[keep[b]][keep[a]] = cell
                        pflat.append((keep[a], keep[b], cell["p"]))
                for (i, j, _p), q in zip(pflat, bh([p for _i, _j, p in pflat])):
                    partial[i][j]["q"] = partial[j][i]["q"] = q
    return {"names": names, "cells": cells, "partial": partial, "complete": len(complete)}


def kruskal(groups: list[list[float]]) -> dict | None:
    """Kruskal–Wallis H (ties corrected), its p (χ², g − 1 df) and epsilon² = H / (n − 1)."""
    groups = [g for g in groups if g]
    if len(groups) < 2:
        return None
    allv = [v for g in groups for v in g]
    n = len(allv)
    ranks = rankdata(allv)
    pos, h = 0, 0.0
    for g in groups:
        r = ranks[pos:pos + len(g)]
        pos += len(g)
        h += sum(r) ** 2 / len(g)
    h = 12 / (n * (n + 1)) * h - 3 * (n + 1)
    ties = sum(t ** 3 - t for t in Counter(allv).values())
    corr = 1 - ties / (n ** 3 - n) if n > 1 else 1
    h = h / corr if corr else 0.0
    return {"H": h, "df": len(groups) - 1, "p": sm.chi2_sf(h, len(groups) - 1), "epsilon2": h / (n - 1) if n > 1 else None,
            "n": n}


def mann_whitney(a: list[float], b: list[float]) -> dict | None:
    """Mann–Whitney U (normal approximation, ties corrected) and Cliff's delta = P(a > b) − P(a < b)."""
    n1, n2 = len(a), len(b)
    if n1 < 5 or n2 < 5:
        return None
    ranks = rankdata(list(a) + list(b))
    r1 = sum(ranks[:n1])
    u1 = r1 - n1 * (n1 + 1) / 2
    n = n1 + n2
    ties = sum(t ** 3 - t for t in Counter(list(a) + list(b)).values())
    var = n1 * n2 / 12 * ((n + 1) - ties / (n * (n - 1)))
    z = (u1 - n1 * n2 / 2) / math.sqrt(var) if var > 0 else 0.0
    return {"U": u1, "z": z, "p": 2 * sm.normal_sf(abs(z)), "delta": 2 * u1 / (n1 * n2) - 1, "n1": n1, "n2": n2}


def stuart_maxwell(table: list[list[int]]) -> dict | None:
    """Stuart–Maxwell test of marginal homogeneity of a square table of paired ordered grades: are the two
    scholars' distributions of grades the same? χ² on k − 1 df (categories empty in both are dropped)."""
    k = len(table)
    keep = [i for i in range(k) if sum(table[i]) + sum(table[r][i] for r in range(k)) > 0]
    if len(keep) < 2:
        return None
    t = [[table[i][j] for j in keep] for i in keep]
    m = len(keep)
    rows = [sum(t[i]) for i in range(m)]
    cols = [sum(t[r][i] for r in range(m)) for i in range(m)]
    d = [rows[i] - cols[i] for i in range(m - 1)]
    s = [[0.0] * (m - 1) for _ in range(m - 1)]
    for i in range(m - 1):
        for j in range(m - 1):
            s[i][j] = rows[i] + cols[i] - 2 * t[i][i] if i == j else -(t[i][j] + t[j][i])
    x = sm._solve(s, d)
    if x is None:
        return None
    chi2 = sum(a * b for a, b in zip(d, x))
    return {"chi2": chi2, "df": m - 1, "p": sm.chi2_sf(chi2, m - 1), "n": sum(rows)}


# ------------------------------------------------------------------ Brant's test of the hadith model's shape
def _logit_fit(rows: list[tuple[tuple, int, float]], iterations: int = 50) -> list[float] | None:
    """Binary logistic regression by Newton–Raphson on weighted rows (x with its leading 1, y 0/1, weight)."""
    p = len(rows[0][0])
    beta = [0.0] * p
    for _ in range(iterations):
        grad = [0.0] * p
        info = [[0.0] * p for _ in range(p)]
        for x, y, w in rows:
            z = sum(a * b for a, b in zip(x, beta))
            pi = sm._sigmoid(z)
            for i in range(p):
                grad[i] += w * (y - pi) * x[i]
                wi = w * pi * (1 - pi) * x[i]
                for j in range(i, p):
                    info[i][j] += wi * x[j]
        for i in range(p):
            for j in range(i):
                info[i][j] = info[j][i]
        step = sm._solve(info, grad)
        if step is None:
            return None
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-9:
            break
    if any(abs(b) > 30 for b in beta):           # separation: a factor that fixes the outcome — no finite estimate
        return None
    return beta


def brant(rows: list[tuple[tuple, int]], categories: int, names: list[str]) -> dict | None:
    """Brant's (1990) Wald test of the proportional-odds assumption: one binary logit per threshold (grade weaker
    than j), and are the slopes the same at every threshold? Overall and for each factor."""
    if categories < 3:
        return None
    grouped = Counter(rows)
    data = [((1.0,) + tuple(x), y, w) for (x, y), w in grouped.items()]
    p = len(data[0][0])
    fits, used = [], []
    for j in range(categories - 1):
        # a threshold whose binary logit has no finite estimate (a factor never seen above it: separation) is left
        # out, as R's brant warns of it; the test then compares the thresholds that can be estimated
        beta = _logit_fit([(x, int(y > j), w) for x, y, w in data])
        if beta is not None:
            fits.append(beta)
            used.append(j)
    m = len(fits)
    if m < 2:
        return None
    pis = [[sm._sigmoid(sum(a * b for a, b in zip(x, beta))) for x, _y, _w in data] for beta in fits]

    def xwx(weights: list[float]) -> list[list[float]]:
        out = [[0.0] * p for _ in range(p)]
        for (x, _y, w), v in zip(data, weights):
            for i in range(p):
                for k in range(p):
                    out[i][k] += w * v * x[i] * x[k]
        return out

    inv = []
    for j in range(m):
        a = sm._inverse(xwx([q * (1 - q) for q in pis[j]]))
        if a is None:
            return None
        inv.append(a)

    def mul(a, b):
        return [[sum(a[i][t] * b[t][k] for t in range(len(b))) for k in range(len(b[0]))] for i in range(len(a))]

    # covariance of the stacked slopes (the intercepts left out)
    q = p - 1
    big = [[0.0] * (m * q) for _ in range(m * q)]
    for j in range(m):
        for k in range(j, m):
            if j == k:
                block = inv[j]
            else:
                block = mul(mul(inv[j], xwx([pis[k][r] - pis[j][r] * pis[k][r] for r in range(len(data))])), inv[k])
            for a in range(q):
                for b in range(q):
                    big[j * q + a][k * q + b] = block[a + 1][b + 1]
                    big[k * q + b][j * q + a] = block[a + 1][b + 1]
    stacked = [fits[j][a + 1] for j in range(m) for a in range(q)]

    def wald(cols: list[int]) -> dict | None:
        """Contrasts: the first threshold's slope minus each later one's, for the chosen factors."""
        rows_d = []
        for j in range(1, m):
            for a in cols:
                d = [0.0] * (m * q)
                d[a] = 1.0
                d[j * q + a] = -1.0
                rows_d.append(d)
        dv = [sum(d[i] * stacked[i] for i in range(m * q)) for d in rows_d]
        dvd = [[sum(d1[i] * sum(big[i][k] * d2[k] for k in range(m * q)) for i in range(m * q)) for d2 in rows_d]
               for d1 in rows_d]
        x = sm._solve(dvd, dv)
        if x is None:
            return None
        chi2 = max(0.0, sum(a * b for a, b in zip(dv, x)))
        return {"chi2": chi2, "df": len(rows_d), "p": sm.chi2_sf(chi2, len(rows_d))}

    overall = wald(list(range(q)))
    if overall is None:
        return None
    factors = []
    for a in range(q):
        t = wald([a])
        if t:
            factors.append({"name": names[a], "slopes": [fits[j][a + 1] for j in range(m)], **t})
    for f, adj in zip(factors, sm.holm([f["p"] for f in factors])):
        f["p_holm"] = adj
    return {"overall": overall, "factors": factors, "thresholds": used, "of": categories - 1}


def brant_for(conn: sqlite3.Connection, key: str, grader: str, by_hadith: dict[int, int], feats: dict,
              road: "sc.Road" = sm.SUNNI) -> dict | None:
    """Brant's test on the very model of core.stats_models: the same rows, grades merged the same way, same factors."""
    order = road.grade_order
    rows_raw = [(feats[h], order.index(g)) for h, g in by_hadith.items() if h in feats and g in order]
    if len(rows_raw) < 100:
        return None
    mapping, labels = sm._merge_categories([y for _f, y in rows_raw], road)
    if len(labels) < 3:                      # two grades: one threshold, nothing to compare across thresholds
        return None
    rows = [(f, mapping[y]) for f, y in rows_raw]
    blocks = sm._varying([f for f, _y in rows])
    columns, _cb, make = sm._design([f for f, _y in rows], blocks, road)
    out = brant([(make(f), y) for f, y in rows], len(labels), columns)
    if out:
        out.update(grader=grader, labels=labels, n=len(rows))
    return out


# ------------------------------------------------------------------ the analysis
HADITH_VARS = [
    ("weakest", "Weakest narrator", "the weakest identified narrator of the best chain, as Ibn Hajar's rank group"),
    ("weak_count", "More weak narrators", "weak or unknown narrators beyond the first"),
    ("length", "Length", "names in the chain"),
    ("unidentified", "Names not identified", "names not matched to a narrator"),
    ("routes", "Chains in the book", "the hadith's chains in the same book"),
    ("takhrij", "Narrations elsewhere", "its narrations found in other books"),
    ("mawquf", "Stops short", "the chain ends with a Companion or Successor (1) or reaches the Prophet (0)"),
    ("doubtful", "Doubtful link", "a pair implausible in time or generation (1)"),
    ("position", "Place in the book", "the hadith's place in the book, from first to last"),
]
NARRATOR_VARS = [
    ("rank", "Ibn Hajar's rank", "1 Companion … 12 liar — a higher number is a WEAKER narrator"),
    ("tabaqa", "Generation", "Ibn Hajar's tabaqa, 1 Companions … 12"),
    ("death", "Year of death", "AH"),
    ("links", "Times in the chains", ""),
    ("teachers", "Teachers", "different narrators he narrates from in these chains"),
    ("students", "Students", "different narrators who narrate from him"),
    ("pagerank", "PageRank", "his share of the flow of transmission"),
]


def hadith_vars(road: "sc.Road") -> list[tuple[str, str, str]]:
    """HADITH_VARS in the words of the road (SH1)."""
    if not road.shia:
        return HADITH_VARS
    words = {"weakest": ("Weakest narrator", "the weakest identified narrator of the best chain, in al-Najashi's categories"),
             "weak_count": ("More weak narrators", "narrators al-Najashi calls weak beyond the first"),
             "mawquf": ("Stops short", "the chain does not reach a Ma'sum (1) or reaches the Prophet or an Imam (0)")}
    return [(k, *words[k]) if k in words else (k, lab, e) for k, lab, e in HADITH_VARS]


def narrator_vars(road: "sc.Road") -> list[tuple[str, str, str]]:
    """NARRATOR_VARS in the words of the road: road B has al-Najashi's four categories and no generations (tabaqat)."""
    if not road.shia:
        return NARRATOR_VARS
    return [("rank", "al-Najashi's category", "1 trustworthy, 2 praised, 3 muwaththaq, 4 weak — a higher number is a "
                                              "WEAKER narrator")] + [v for v in NARRATOR_VARS if v[0] not in ("rank", "tabaqa")]


def _hadith_table(conn: sqlite3.Connection, key: str, road: "sc.Road" = sm.SUNNI) -> dict | None:
    """The hadith of one book as columns: the factors, then every scholar's grade and how far they disagree."""
    feats = sm.hadith_features(conn, key, road)
    if len(feats) < 30:
        return None
    data = road.load(conn, key)
    order_g = road.grade_order
    worst = road.grade_labels[-1]
    order = {h: i for i, (h,) in enumerate(conn.execute(
        "SELECT h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id WHERE c.key = ? "
        "ORDER BY h.number_sort, h.id", (key,)))}
    # a grader who gives one grade only (a selection: al-Behbudi) cannot go with anything, nor disagree in degree
    graders = sorted(g for g, d in data.items() if len(d) >= 100 and len(set(d.values())) > 1)
    hadith = sorted(feats)
    total = max(1, len(order) - 1)
    factors = []
    for k, label, explain in hadith_vars(road):
        if k == "weakest":
            col = [road.levels.index(feats[h]["weakest"]) if feats[h]["weakest"] != "None ranked" else None
                   for h in hadith]
        elif k == "position":
            col = [order.get(h, 0) / total for h in hadith]
        else:
            col = [feats[h][k] for h in hadith]
        if len({v for v in col if v is not None}) > 1:        # a factor that never varies says nothing
            factors.append((label, explain, col))
    outcomes = [(f"Grade: {g}", f"{g}'s grade, 0 sahih … {len(order_g) - 1} {worst} (higher = weaker)",
                 [order_g.index(data[g][h]) if h in data[g] else None for h in hadith]) for g in graders]
    if len(graders) >= 2:
        spread = []
        for h in hadith:
            gs = [order_g.index(data[g][h]) for g in graders if h in data[g]]
            spread.append(max(gs) - min(gs) if len(gs) >= 2 else None)
        outcomes.append(("Disagreement", "how many grade steps apart the scholars are on this hadith", spread))
    outcomes = [o for o in outcomes if len({v for v in o[2] if v is not None}) > 1]
    return {"factors": factors, "outcomes": outcomes, "hadith": len(hadith)}


def adjusted(factors: list[tuple], outcome: list) -> list[dict | None]:
    """Each factor against one outcome with every other factor held equal (partial Spearman), BH over the factors."""
    m = correlation_matrix([f[0] for f in factors] + ["outcome"], [f[2] for f in factors] + [outcome])
    if not m["partial"]:
        return [None] * len(factors)
    cells = [m["partial"][i][-1] for i in range(len(factors))]
    known = [i for i, c in enumerate(cells) if c]
    for i, q in zip(known, bh([cells[i]["p"] for i in known])):
        cells[i] = dict(cells[i], q=q)
    return cells


def _narrator_table(conn: sqlite3.Connection, collection: str | None,
                    road: "sc.Road" = sm.SUNNI) -> tuple[list[str], list[list], list[str]]:
    """The narrators of the chains as columns (names, columns, explanations); a column that never varies (road B has
    no generations) is left out."""
    persons = sc._persons(conn, road.tradition)
    chains = sc._chains(conn, [b[0] for b in sc._books(conn, collection)])
    links = Counter()
    teachers, students = defaultdict(set), defaultdict(set)
    edges = Counter()
    for c in chains:
        ls = c["links"]
        for p in ls:
            if p in persons:
                links[p] += 1
        for s, t in zip(ls, ls[1:]):
            if s in persons and t in persons:
                teachers[s].add(t)
                students[t].add(s)
                edges[(s, t)] += 1
    pr = sc.pagerank(edges)
    people = sorted(links)
    values = {"rank": lambda p: persons[p]["rank"], "tabaqa": lambda p: persons[p]["tabaqa"],
              "death": lambda p: persons[p]["death"], "links": lambda p: links[p],
              "teachers": lambda p: len(teachers[p]), "students": lambda p: len(students[p]),
              "pagerank": lambda p: pr.get(p, 0.0)}
    names, cols, explain = [], [], []
    for k, lab, e in narrator_vars(road):
        col = [values[k](p) for p in people]
        if len({v for v in col if v is not None}) > 1 and sum(v is not None for v in col) >= 30:
            names.append(lab)
            cols.append(col)
            explain.append(e)
    return names, cols, explain


def analyse(conn: sqlite3.Connection, collection: str | None = None, progress=None) -> dict:
    say = progress or (lambda _m: None)
    books = sc._books(conn, collection)
    road = sc.road_of(conn, collection)
    order_g = road.grade_order
    out: dict = {"method": METHOD, "collection": collection, "tradition": road.tradition, "critic": road.critic,
                 "grade_labels": road.grade_labels, "hadith": [], "graders": [], "brant": [], "books": None}
    for _id, key, name in books:
        say(f"Correlating the hadith of {name}")
        table = _hadith_table(conn, key, road)
        if table and len(table["factors"]) + len(table["outcomes"]) >= 3:
            fs, os_ = table["factors"], table["outcomes"]
            m = correlation_matrix([x[0] for x in fs + os_], [x[2] for x in fs + os_])
            m.update(book=name, key=key, explain=[x[1] for x in fs + os_], hadith=table["hadith"], factors=len(fs))
            # what each factor says of each grade when the other factors are equal
            m["adjusted"] = [{"outcome": o[0], "cells": adjusted(fs, o[2])} for o in os_]
            m.pop("partial")
            m["partial"] = correlation_matrix([x[0] for x in fs], [x[2] for x in fs])["partial"]
            out["hadith"].append(m)
        # the scholars of the book, pair by pair: Stuart–Maxwell
        data = road.load(conn, key)
        graders = sorted(g for g, d in data.items() if len(d) >= 100 and len(set(d.values())) > 1)
        feats = sm.hadith_features(conn, key, road)
        for g in graders:
            say(f"Testing the shape of the model of {g}")
            b = brant_for(conn, key, g, data[g], feats, road)
            if b:
                out["brant"].append(dict(b, book=name, key=key))
        for i, a in enumerate(graders):
            for b in graders[i + 1:]:
                common = [h for h in data[a] if h in data[b]]
                if len(common) < 30:
                    continue
                table = [[0] * len(order_g) for _ in order_g]
                higher = lower = 0
                for h in common:
                    x, y = order_g.index(data[a][h]), order_g.index(data[b][h])
                    table[x][y] += 1
                    higher += x < y          # a gives the stronger grade (index 0 is sahih)
                    lower += x > y
                test = stuart_maxwell(table)
                if test:
                    out["graders"].append({"book": name, "a": a, "b": b, "n": len(common), "a_stronger": higher,
                                           "a_weaker": lower, "table": table, **test})
    for t, adj in zip(out["graders"], sm.holm([t["p"] for t in out["graders"]])):
        t["p_holm"] = adj
    for t, adj in zip(out["brant"], sm.holm([b["overall"]["p"] for b in out["brant"]])):
        t["overall"]["p_holm"] = adj
    say("Correlating the narrators")
    names, cols, explain = _narrator_table(conn, collection, road)
    if len(cols) >= 2 and len(cols[0]) >= 30:
        m = correlation_matrix(names, cols)
        m.update(explain=explain, people=len(cols[0]))
        out["narrators"] = m
    # the books compared
    if len(books) >= 2:
        say("Comparing the books")
        measures = {"Weakest narrator": [], "Length": [], "Names identified": []}
        persons = sc._persons(conn, road.tradition)
        for bid, _key, name in books:
            weakest, length, ident = [], [], []
            for c in sc._chains(conn, [bid]):
                ls = c["links"]
                if not ls:
                    continue
                length.append(len(ls))
                ids = [p for p in ls if p in persons]
                ident.append(len(ids) / len(ls))
                ranks = [persons[p]["rank"] for p in ids if persons[p]["rank"] in road.group_of]
                if ranks:
                    weakest.append(road.group_of[max(ranks)])
            measures["Weakest narrator"].append((name, weakest))
            measures["Length"].append((name, length))
            measures["Names identified"].append((name, ident))
        comparisons = []
        for label, groups in measures.items():
            kw = kruskal([g for _n, g in groups])
            pairs = []
            for i in range(len(groups)):
                for j in range(i + 1, len(groups)):
                    mw = mann_whitney(groups[i][1], groups[j][1])
                    if mw:
                        pairs.append({"a": groups[i][0], "b": groups[j][0], **mw})
            for p_, adj in zip(pairs, sm.holm([p_["p"] for p_ in pairs])):
                p_["p_holm"] = adj
            comparisons.append({"measure": label, "kruskal": kw, "pairs": pairs,
                                "medians": [[n, sorted(g)[len(g) // 2] if g else None, len(g)] for n, g in groups]})
        out["books"] = comparisons
    return out


def cached(conn: sqlite3.Connection, collection: str | None = None, progress=None, recompute: bool = False) -> dict:
    """The laboratory from data_dir()/derived/ while the data is unchanged; computed and written otherwise (DX1)."""
    from isnady.data.paths import data_dir

    path = data_dir() / "derived" / sc.cache_name("lab", collection)
    stamp = sc.fingerprint(conn, collection) + METHOD
    if not recompute and path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved.get("fingerprint") == stamp:
                saved["from_file"] = str(path)
                return saved
        except (OSError, ValueError):
            pass
    result = analyse(conn, collection, progress)
    result["fingerprint"] = stamp
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    result["from_file"] = None
    return result


# ------------------------------------------------------------------ tables (the CLI, the CSV files and the page)
def pairs_table(m: dict, which: str = "cells") -> list[list]:
    """Every pair of a matrix, strongest first: a, b, rho, n, p, q."""
    rows = []
    grid = m.get(which) or []
    k = len(grid)
    for i in range(k):
        for j in range(i + 1, k):
            c = grid[i][j] if grid else None
            if c and c.get("rho") is not None:
                rows.append([m["names"][i], m["names"][j], c["rho"], c["n"], c["p"], c.get("q")])
    return sorted(rows, key=lambda r: -abs(r[2]))


def adjusted_table(m: dict) -> list[list]:
    """outcome, factor, plain rho, adjusted rho, n, q of the adjusted."""
    rows = []
    for j, a in enumerate(m.get("adjusted", [])):
        col = m["factors"] + j
        for i, c in enumerate(a["cells"]):
            plain = m["cells"][i][col]
            rows.append([a["outcome"], m["names"][i], plain["rho"] if plain else None,
                         c["rho"] if c else None, c["n"] if c else None, c["q"] if c else None])
    return rows


def write_csv(r: dict, folder: str) -> list[str]:
    """Every table of the laboratory as CSV (UTF-8 with BOM). Returns the files written."""
    import csv
    from pathlib import Path

    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    written = []

    def write(name: str, header: list, rows: list) -> None:
        with open(out / f"{name}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        written.append(str(out / f"{name}.csv"))

    from isnady.core import books as core_books

    head = ["a", "b", "spearman_rho", "n", "p", "q_bh"]
    for m in r["hadith"]:
        name = core_books.full_name(m["key"])
        write(f"lab_{name}_hadith", ["book"] + head, [[m["book"]] + row for row in pairs_table(m)])
        write(f"lab_{name}_hadith_partial", ["book"] + head, [[m["book"]] + row for row in pairs_table(m, "partial")])
        write(f"lab_{name}_adjusted", ["outcome", "factor", "rho", "rho_others_equal", "n", "q_bh"], adjusted_table(m))
    if r.get("brant"):
        rows = []
        for b in r["brant"]:
            o = b["overall"]
            rows.append([b["book"], b["grader"], "all factors", o["chi2"], o["df"], o["p"], o["p_holm"], ""])
            for f in b["factors"]:
                rows.append([b["book"], b["grader"], f["name"], f["chi2"], f["df"], f["p"], f["p_holm"],
                             " ".join(f"{x:.4f}" for x in f["slopes"])])
        write("lab_model_brant", ["book", "scholar", "factor", "chi2", "df", "p", "p_holm", "slope_at_each_threshold"], rows)
    if r.get("narrators"):
        write("lab_narrators", head, pairs_table(r["narrators"]))
        write("lab_narrators_partial", head, pairs_table(r["narrators"], "partial"))
    if r["graders"]:
        write("lab_scholars_stuart_maxwell", ["book", "a", "b", "hadith", "a_stronger", "a_weaker", "chi2", "df", "p", "p_holm"],
              [[t["book"], t["a"], t["b"], t["n"], t["a_stronger"], t["a_weaker"], t["chi2"], t["df"], t["p"], t["p_holm"]]
               for t in r["graders"]])
    if r.get("books"):
        rows = []
        for c in r["books"]:
            kw = c["kruskal"] or {}
            rows.append([c["measure"], "all", "", kw.get("H"), kw.get("df"), kw.get("p"), "", kw.get("epsilon2")])
            for p in c["pairs"]:
                rows.append([c["measure"], p["a"], p["b"], p["U"], "", p["p"], p["p_holm"], p["delta"]])
        write("lab_books", ["measure", "a", "b", "H_or_U", "df", "p", "p_holm", "epsilon2_or_cliffs_delta"], rows)
    return written
