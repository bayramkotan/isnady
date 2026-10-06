"""ST7 — the graders of a book, measured in depth (Statistics → Graders).

Grades are ORDINAL categories (sahih > hasan > da'if > very weak > fabricated): never fixed numbers, never averaged
(the SK rule). What is measured here:
  • agreement of every pair of graders: share of identical grades, Cohen's kappa, and the ordinal (quadratic
    weighted) kappa that counts a near miss as less of a disagreement than a far one — each with a 95% interval;
  • Krippendorff's alpha (ordinal) for all graders of the book together, with its interval;
  • a Dawid–Skene model: the TRUE grade of each hadith is unknown; each grader is described by how often he gives
    each grade to a hadith whose true grade is k (his confusion matrix); EM estimates those matrices, how common
    each true grade is, and for every hadith the probability of each grade;
  • strictness from the model, by order only: P(he grades BELOW the true grade) − P(he grades ABOVE it) — the
    classical mutashaddid (negative) and mutasahil (positive), measured; pairwise: P(A lower than B) − P(A higher);
  • the disputed hadith: where the graders are furthest apart and the model is least sure.
Intervals: percentile bootstrap over hadith (fixed seed). Pure Python, no numpy. The result is written to
data_dir()/derived/ with the fingerprint of its inputs and read back while the grades do not change (DX1)."""

import json
import math
import random
import sqlite3
from collections import Counter, defaultdict

from isnady.core.grades import GROUP_LABELS, group, isnad_only

METHOD = "isnady-graders-3"
HIGH_AGREEMENT = 0.95                   # as core.scholars: above this, two graders are not two independent views
K = 5                                   # grade groups 0..4 (fabricated … sahih), used only as ORDER
LABELS = [GROUP_LABELS[k] for k in range(K)]
BOOT = 300
SEED = 1405


# ------------------------------------------------------------------ data
def load(conn: sqlite3.Connection, collection: str, chain_only_out: dict | None = None) -> dict[str, dict[int, int]]:
    """grader -> {hadith id: grade group} for one book (the first grade a grader gives a hadith).

    A grade of the CHAIN only ("Isnaad Sahih": the chain is sound, the text not judged) answers another question
    than a grade of the hadith: compared with "Munkar" it is not a disagreement. Such grades are left out of
    every comparison and counted per grader in chain_only_out. (2026-10-06: 25.8% of Zubair 'Ali Za'i's grades of
    Sunan Abi Dawud are chain-only, against 4.5% of al-Albani's.)"""
    out: dict[str, dict[int, int]] = defaultdict(dict)
    seen: set = set()
    for name, hid, grade in conn.execute(
            """SELECT g.grader_name, g.hadith_id, g.grade FROM grades g JOIN hadiths h ON h.id = g.hadith_id
               JOIN collections c ON c.id = h.collection_id WHERE c.key = ? ORDER BY g.id""", (collection,)):
        if (name, hid) in seen:
            continue
        seen.add((name, hid))
        if isnad_only(grade):
            if chain_only_out is not None:
                chain_only_out[name] = chain_only_out.get(name, 0) + 1
            continue
        k = group(grade)
        if k is not None:
            out[name][hid] = k
    return dict(out)


def books_with_grades(conn: sqlite3.Connection) -> list[tuple[str, str, int]]:
    """(key, name, graders) for every book with grades, most graders first."""
    rows = conn.execute(
        """SELECT c.key, c.name, COUNT(DISTINCT g.grader_name) FROM grades g JOIN hadiths h ON h.id = g.hadith_id
           JOIN collections c ON c.id = h.collection_id GROUP BY c.key ORDER BY 3 DESC, c.name""").fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def fingerprint(conn: sqlite3.Connection, collection: str) -> str:
    n, top = conn.execute("""SELECT COUNT(*), COALESCE(MAX(g.id), 0) FROM grades g JOIN hadiths h ON h.id = g.hadith_id
                             JOIN collections c ON c.id = h.collection_id WHERE c.key = ?""", (collection,)).fetchone()
    return f"{METHOD}|{collection}|{n}|{top}|{BOOT}"


# ------------------------------------------------------------------ agreement
def _kappas(pairs: list[tuple[int, int]]) -> tuple[float, float, float]:
    """(share identical, Cohen's kappa, quadratic-weighted kappa) — the weights use the ORDER of the grades only."""
    n = len(pairs)
    obs = [[0] * K for _ in range(K)]
    for a, b in pairs:
        obs[a][b] += 1
    ra = [sum(obs[i]) for i in range(K)]
    rb = [sum(obs[i][j] for i in range(K)) for j in range(K)]
    po = sum(obs[i][i] for i in range(K)) / n
    pe = sum(ra[i] * rb[i] for i in range(K)) / (n * n)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    w = [[((i - j) / (K - 1)) ** 2 for j in range(K)] for i in range(K)]
    do = sum(w[i][j] * obs[i][j] for i in range(K) for j in range(K)) / n
    de = sum(w[i][j] * ra[i] * rb[j] for i in range(K) for j in range(K)) / (n * n)
    wkappa = 1 - do / de if de > 0 else 1.0
    return po, kappa, wkappa


def _order_diff(pairs: list[tuple[int, int]]) -> float:
    """P(A lower than B) − P(A higher than B): order only."""
    return (sum(a < b for a, b in pairs) - sum(a > b for a, b in pairs)) / len(pairs)


def _interval(values: list[float]) -> tuple[float, float]:
    v = sorted(values)
    return v[int(0.025 * (len(v) - 1))], v[int(0.975 * (len(v) - 1))]


def _alpha(units: list[list[int]]) -> float | None:
    """Krippendorff's alpha with the ordinal metric, for units graded by two or more."""
    coinc = [[0.0] * K for _ in range(K)]
    for u in units:
        m = len(u)
        if m < 2:
            continue
        for i, a in enumerate(u):
            for j, b in enumerate(u):
                if i != j:
                    coinc[a][b] += 1 / (m - 1)
    nc = [sum(coinc[c]) for c in range(K)]
    n = sum(nc)
    if n <= 1:
        return None

    def delta(c, k):
        lo, hi = min(c, k), max(c, k)
        return (sum(nc[g] for g in range(lo, hi + 1)) - (nc[c] + nc[k]) / 2) ** 2
    do = sum(coinc[c][k] * delta(c, k) for c in range(K) for k in range(K))
    de = sum(nc[c] * nc[k] * delta(c, k) for c in range(K) for k in range(K)) / (n - 1)
    return 1 - do / de if de > 0 else None


# ------------------------------------------------------------------ Dawid–Skene
def dawid_skene(data: dict[str, dict[int, int]], iterations: int = 200, tol: float = 1e-6) -> dict:
    graders = sorted(data)
    items = sorted({h for d in data.values() for h in d})
    votes = {h: [(j, data[g][h]) for j, g in enumerate(graders) if h in data[g]] for h in items}
    # start: each hadith's grades as they are (majority with ties shared)
    post = {}
    for h, vs in votes.items():
        c = Counter(k for _, k in vs)
        post[h] = [c.get(k, 0) / len(vs) for k in range(K)]
    loglik_prev = None
    for _ in range(iterations):
        prior = [sum(post[h][k] for h in items) / len(items) for k in range(K)]
        theta = []
        for j in range(len(graders)):
            m = [[0.5] * K for _ in range(K)]                 # a light prior: no zero probabilities
            for h, vs in votes.items():
                for jj, l in vs:
                    if jj == j:
                        for k in range(K):
                            m[k][l] += post[h][k]
            theta.append([[x / sum(row) for x in row] for row in m])
        loglik = 0.0
        for h, vs in votes.items():
            w = []
            for k in range(K):
                p = max(prior[k], 1e-12)
                for j, l in vs:
                    p *= theta[j][k][l]
                w.append(p)
            s = sum(w)
            loglik += math.log(s)
            post[h] = [x / s for x in w]
        if loglik_prev is not None and abs(loglik - loglik_prev) < tol * abs(loglik_prev):
            break
        loglik_prev = loglik
    strict = {}
    for j, g in enumerate(graders):
        below = sum(prior[k] * theta[j][k][l] for k in range(K) for l in range(K) if l < k)
        above = sum(prior[k] * theta[j][k][l] for k in range(K) for l in range(K) if l > k)
        strict[g] = above - below                            # negative: stricter (mutashaddid)
    return {"graders": graders, "prior": prior, "theta": {g: theta[j] for j, g in enumerate(graders)},
            "posterior": post, "strictness": strict, "votes": votes, "loglik": loglik}


# ------------------------------------------------------------------ everything for one book
def analyse(conn: sqlite3.Connection, collection: str, progress=None) -> dict:
    say = progress or (lambda _m: None)
    chain_only: dict = {}
    data = load(conn, collection, chain_only)
    graders = sorted(data, key=lambda g: -len(data[g]))
    rng = random.Random(SEED)
    out = {"collection": collection, "graders": graders, "counts": {g: len(data[g]) for g in graders},
           "distribution": {g: [sum(1 for k in data[g].values() if k == c) for c in range(K)] for g in graders},
           "labels": LABELS, "boot": BOOT, "chain_only": {g: chain_only.get(g, 0) for g in graders}}
    if len(graders) < 2:
        return out
    say("Agreement between every pair of graders")
    pairs_out = {}
    for i, a in enumerate(graders):
        for b in graders[i + 1:]:
            common = sorted(data[a].keys() & data[b].keys())
            if len(common) < 20:
                continue
            pairs = [(data[a][h], data[b][h]) for h in common]
            po, kap, wk = _kappas(pairs)
            od = _order_diff(pairs)
            boots = {"agree": [], "kappa": [], "wkappa": [], "order": []}
            for _ in range(BOOT):
                s = [pairs[rng.randrange(len(pairs))] for _ in range(len(pairs))]
                bpo, bk, bwk = _kappas(s)
                boots["agree"].append(bpo); boots["kappa"].append(bk); boots["wkappa"].append(bwk)
                boots["order"].append(_order_diff(s))
            pairs_out[f"{a}|{b}"] = {
                "common": len(common), "agree": po, "kappa": kap, "wkappa": wk, "order": od,
                "within_one": sum(abs(x - y) <= 1 for x, y in pairs) / len(pairs),
                "ci": {k: _interval(v) for k, v in boots.items()},
                "table": [[sum(1 for x, y in pairs if x == r and y == c) for c in range(K)] for r in range(K)]}
    out["pairs"] = pairs_out
    say("Krippendorff's alpha")
    units = [[data[g][h] for g in graders if h in data[g]] for h in sorted({h for d in data.values() for h in d})]
    units = [u for u in units if len(u) >= 2]
    alpha = _alpha(units)
    boots = []
    for _ in range(BOOT // 3):
        boots.append(_alpha([units[rng.randrange(len(units))] for _ in range(len(units))]))
    out["alpha"] = {"value": alpha, "ci": _interval([b for b in boots if b is not None]), "units": len(units)}
    say("Dawid–Skene model (each grader's confusion matrix)")
    # the model assumes graders judge independently. A pair agreeing on HIGH_AGREEMENT or more was probably filled
    # one from the other in the source (al-Albani and Muhyi al-Din: 98.1%): counted as two votes, that one view
    # would decide every hadith. In the model they are ONE voice — the one with more grades; the other is measured
    # against the model's result afterwards, without moving it.
    one_voice = []
    for key, p in out["pairs"].items():
        a, b = key.split("|")
        if p["agree"] >= HIGH_AGREEMENT:
            keep, drop = (a, b) if len(data[a]) >= len(data[b]) else (b, a)
            one_voice.append({"kept": keep, "left_out": drop, "agree": p["agree"]})
    left_out = {o["left_out"] for o in one_voice}
    voices = {g: data[g] for g in graders if g not in left_out}
    out["one_voice"] = one_voice
    ds = dawid_skene(voices)
    for g in left_out:                                     # measured against the model, not part of it
        m = [[0.5] * K for _ in range(K)]
        for h, l in data[g].items():
            if h in ds["posterior"]:
                for k in range(K):
                    m[k][l] += ds["posterior"][h][k]
        theta_g = [[x / sum(row) for x in row] for row in m]
        ds["theta"][g] = theta_g
        below = sum(ds["prior"][k] * theta_g[k][l] for k in range(K) for l in range(K) if l < k)
        above = sum(ds["prior"][k] * theta_g[k][l] for k in range(K) for l in range(K) if l > k)
        ds["strictness"][g] = above - below
    # strictness interval: the model refitted on bootstrap samples of hadith
    items = list(ds["votes"])
    strict_boot = defaultdict(list)
    for b in range(40):
        say(f"Strictness intervals ({b + 1} of 40)")
        sample = [items[rng.randrange(len(items))] for _ in range(len(items))]
        resampled: dict = defaultdict(dict)
        for n, h in enumerate(sample):
            for g in graders:
                if h in data[g]:
                    resampled[g][n] = data[g][h]
        fit = dawid_skene({g: v for g, v in resampled.items() if g not in left_out}, iterations=60, tol=1e-5)
        for g in left_out:
            m = [[0.5] * K for _ in range(K)]
            for n, l in resampled[g].items():
                if n in fit["posterior"]:
                    for k in range(K):
                        m[k][l] += fit["posterior"][n][k]
            th = [[x / sum(row) for x in row] for row in m]
            fit["strictness"][g] = (sum(fit["prior"][k] * th[k][l] for k in range(K) for l in range(K) if l > k)
                                    - sum(fit["prior"][k] * th[k][l] for k in range(K) for l in range(K) if l < k))
        for g, v in fit["strictness"].items():
            strict_boot[g].append(v)
    out["model"] = {"prior": ds["prior"], "theta": ds["theta"], "loglik": ds["loglik"],
                    "strictness": {g: {"value": ds["strictness"][g], "ci": _interval(strict_boot[g])} for g in graders}}
    # consensus: most probable true grade and its probability; the disputed hadith
    consensus = Counter()
    disputed = []
    for h, p in ds["posterior"].items():
        best = max(range(K), key=lambda k: p[k])
        consensus[best] += 1
        given = {g: data[g][h] for g in graders if h in data[g]}
        spread = max(given.values()) - min(given.values()) if len(given) >= 2 else 0
        entropy = -sum(x * math.log(x) for x in p if x > 0) / math.log(K)
        if spread >= 2 or (len(given) >= 2 and p[best] < 0.6):
            disputed.append({"hadith_id": h, "grades": given, "consensus": best, "certainty": p[best],
                             "spread": spread, "entropy": entropy})
    disputed.sort(key=lambda d: (-d["spread"], d["certainty"]))
    numbers = dict(conn.execute("SELECT id, number FROM hadiths WHERE id IN (%s)" % ",".join(
        str(d["hadith_id"]) for d in disputed[:300]) or "0"))
    for d in disputed[:300]:
        d["number"] = numbers.get(d["hadith_id"])
    out["consensus"] = [consensus.get(k, 0) for k in range(K)]
    out["disputed_total"] = len(disputed)
    out["disputed"] = disputed[:300]
    out["certainty"] = {"high": sum(1 for p in ds["posterior"].values() if max(p) >= 0.95),
                        "middle": sum(1 for p in ds["posterior"].values() if 0.6 <= max(p) < 0.95),
                        "low": sum(1 for p in ds["posterior"].values() if max(p) < 0.6),
                        "total": len(ds["posterior"])}
    return out


def cached(conn: sqlite3.Connection, collection: str, progress=None, recompute: bool = False) -> dict:
    """The analysis, from data_dir()/derived/ while the grades are unchanged; computed and written otherwise."""
    from isnady.data.paths import data_dir

    path = data_dir() / "derived" / f"graders-{collection}.json"
    stamp = fingerprint(conn, collection)
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
    # JSON keys are strings: hadith ids in the model's grades
    for d in result.get("disputed", []):
        d["grades"] = dict(d["grades"])
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    result["from_file"] = None
    return result
