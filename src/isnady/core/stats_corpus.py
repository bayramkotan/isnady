"""Statistics of the whole corpus (ST7, deep): the narrators, the chains, the grades and the books, measured.

Qt-free and numpy-free, like all of isnady.core; computed once and kept in data_dir()/derived/ while the data is
unchanged (DX1). Every measure here keeps to the rules of the project:

  * Ranks and grades are ORDERED CATEGORIES (SK). They are counted, cross-tabulated and rank-correlated — Kendall's
    tau-b and Goodman–Kruskal's gamma — never turned into numbers and averaged.
  * Ibn Hajar's twelve ranks are drawn in six groups so a chart stays readable; the twelve are kept in the data.
  * Two roads (SH1): "all books" are the Sunni books, measured on Ibn Hajar's ranks; the Shia books ("@shia", or
    one Shia book) are measured apart, on their narrators' Imami categories (al-Najashi), their chains ending at a
    Ma'sum. The two are never measured together nor on each other's scale.
  * Intervals are percentile bootstraps over hadith (BOOT samples, a fixed seed: the same data gives the same numbers).

The chain's first link (position 1) is the compiler's own teacher; each link narrates FROM the next one, and the
last is usually the Companion. A pair (p, p+1) is therefore (student, teacher).
"""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from collections import Counter, defaultdict

from isnady.core import stats_graders
from isnady.core.grades import GROUP_LABELS, IMAMI_LABELS, group, isnad_only
from isnady.core.i18n import N_, tr

METHOD = "isnady-corpus-3"
SHIA_SCOPE = "@shia"           # every active Shia book (road B)
ALL_SCOPE = "@all"             # every active book: the two roads shown one after the other, each measured apart (BK1)
BOOT = 200
SEED = 1405

# Ibn Hajar's twelve ranks in six ordered groups (1 strongest … 6 weakest) — for drawing; the ranks stay in the data
RANK_GROUPS = [
    (N_("Companion"), N_("Companions (rank 1): their uprightness is not examined"), (1,)),
    (N_("Trustworthy"), N_("thiqa and above (ranks 2–3)"), (2, 3)),
    (N_("Truthful"), N_("saduq, with or without lapses (ranks 4–5)"), (4, 5)),
    (N_("Acceptable"), N_("maqbul — acceptable when followed, weak otherwise (rank 6)"), (6,)),
    (N_("Weak / unknown"), N_("mastur, da'if, majhul (ranks 7–9)"), (7, 8, 9)),
    (N_("Rejected"), N_("abandoned, accused of lying, liar (ranks 10–12)"), (10, 11, 12)),
]
GROUP_OF_RANK = {r: i for i, (_n, _d, ranks) in enumerate(RANK_GROUPS) for r in ranks}
# road B: the Imami categories of the critic's own words (core.shia_rijal), strongest first
RANK_GROUPS_SHIA = [
    (N_("Trustworthy"), N_("thiqa — an Imami the critic calls trustworthy"), (1,)),
    (N_("Praised"), N_("mamduh — praised (jalil, wajh, 'ayn …) without the word thiqa"), (2,)),
    (N_("Muwaththaq"), N_("a thiqa of another school (Waqifi, Fathi, 'ammi …)"), (3,)),
    (N_("Weak"), N_("da'if — weak, confused, accused, extremist"), (4,)),
]
GROUP_OF_RANK_SHIA = {r: i for i, (_n, _d, ranks) in enumerate(RANK_GROUPS_SHIA) for r in ranks}


def tradition_of_scope(conn: sqlite3.Connection, collection: str | None) -> str:
    """"sunni" for all books (the Sunni road) or a Sunni book; "shia" for "@shia" or a Shia book."""
    if collection == SHIA_SCOPE:
        return "shia"
    if not collection:
        return "sunni"
    row = conn.execute("SELECT tradition FROM collections WHERE key = ?", (collection,)).fetchone()
    return "shia" if row and row[0] == "shia" else "sunni"
GRADE_ORDER = [4, 3, 2, 1, 0]          # sahih … fabricated, strongest first (as the ranks)
IMAMI_ORDER = [4, 3, 2, 1]             # sahih, hasan, muwaththaq, da'if — the Imami categories, strongest first


class Road:
    """Everything that differs between the two roads (SH1), in one place, so every measure is written once and run
    on each road with its own scale: the critic and his categories, the grades and their order, where a chain ends.
    Road A (Sunni): Ibn Hajar's twelve ranks in six groups; the five Sunni grade groups; the chain ends at the Prophet.
    Road B (Shia): al-Najashi's four Imami categories; the four Imami grades of al-Majlisi and al-Behbudi; the chain
    ends at a Ma'sum. A level of one road is never laid on the other."""

    def __init__(self, tradition: str) -> None:
        self.tradition = tradition
        self.shia = tradition == "shia"
        self.rank_groups = RANK_GROUPS_SHIA if self.shia else RANK_GROUPS
        self.group_of = GROUP_OF_RANK_SHIA if self.shia else GROUP_OF_RANK
        self.weak_from = 4 if self.shia else 7            # al-Najashi's "weak"; Ibn Hajar's rank 7 (mastur) and below
        self.grade_order = IMAMI_ORDER if self.shia else GRADE_ORDER
        self.grade_names = IMAMI_LABELS if self.shia else GROUP_LABELS
        self.grade_labels = [self.grade_names[g] for g in self.grade_order]
        # the weakest narrator of a chain, as a level: the rank groups by name ("Companion only": every ranked
        # narrator a Companion, whose uprightness is not examined), and "None ranked"
        self.levels = [(N_("Companion only") if not self.shia and i == 0 else n) for i, (n, _d, _r) in
                       enumerate(self.rank_groups)] + [N_("None ranked")]
        self.reference = "Trustworthy"
        self.critic = "al-Najashi" if self.shia else "Ibn Hajar"
        self.rank_name = "al-Najashi's category" if self.shia else "Ibn Hajar's rank"
        self.rijal = "al-Najashi's Rijal" if self.shia else "the Taqrib"
        self.end = "a Ma'sum" if self.shia else "the Prophet"
        self.weak_words = "weak (da'if)" if self.shia else "of rank 7 or weaker (mastur, da'if, majhul …)"

    def load(self, conn: sqlite3.Connection, key: str, chain_only_out: dict | None = None) -> dict[str, dict[int, int]]:
        """grader -> {hadith id: grade} on this road's own scale (core.stats_graders)."""
        if self.shia:
            return stats_graders.load_imami(conn, key)
        return stats_graders.load(conn, key, chain_only_out)


def road_of(conn: sqlite3.Connection, collection: str | None) -> Road:
    return Road(tradition_of_scope(conn, collection))
GAP_BINS = list(range(-60, 161, 10))   # years between a student's death and his teacher's


# ------------------------------------------------------------------ small statistics
def kendall_from_table(table: list[list[int]]) -> tuple[float | None, float | None]:
    """Kendall's tau-b and Goodman–Kruskal's gamma of an ordered r × c table (both orders ascending).
    O(r²c²) on the cells, not on the cases: fine for 6 × 5 tables of any size."""
    rows, cols = len(table), len(table[0]) if table else 0
    n = sum(map(sum, table))
    if n < 2:
        return None, None
    concordant = discordant = 0
    for i in range(rows):
        for j in range(cols):
            nij = table[i][j]
            if not nij:
                continue
            for k in range(i + 1, rows):
                for m in range(cols):
                    if m > j:
                        concordant += nij * table[k][m]
                    elif m < j:
                        discordant += nij * table[k][m]
    pairs = n * (n - 1) / 2
    tie_rows = sum(s * (s - 1) / 2 for s in (sum(r) for r in table))
    tie_cols = sum(s * (s - 1) / 2 for s in (sum(table[i][j] for i in range(rows)) for j in range(cols)))
    denom = ((pairs - tie_rows) * (pairs - tie_cols)) ** 0.5
    tau = (concordant - discordant) / denom if denom else None
    gamma = (concordant - discordant) / (concordant + discordant) if concordant + discordant else None
    return tau, gamma


def _table(pairs: list[tuple[int, int]], rows: int, cols: int) -> list[list[int]]:
    t = [[0] * cols for _ in range(rows)]
    for a, b in pairs:
        t[a][b] += 1
    return t


def association(pairs: list[tuple[int, int]], rows: int, cols: int, rng: random.Random) -> dict:
    """tau-b and gamma of (row, column) pairs with 95% percentile-bootstrap intervals, and the table itself."""
    table = _table(pairs, rows, cols)
    tau, gamma = kendall_from_table(table)
    taus, gammas = [], []
    if len(pairs) >= 30:
        for _ in range(BOOT):
            sample = rng.choices(pairs, k=len(pairs))
            t, g = kendall_from_table(_table(sample, rows, cols))
            if t is not None:
                taus.append(t)
            if g is not None:
                gammas.append(g)

    def ci(values: list[float]) -> list[float] | None:
        if len(values) < 20:
            return None
        values.sort()
        return [values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]]

    return {"n": len(pairs), "table": table, "tau": tau, "tau_ci": ci(taus), "gamma": gamma, "gamma_ci": ci(gammas)}


def lorenz(counts: list[int], points: int = 40) -> dict:
    """The Lorenz curve of a share (narrators → the links they carry), the Gini coefficient, and the top shares."""
    values = sorted(counts)
    n, total = len(values), sum(values)
    if not n or not total:
        return {"curve": [], "gini": None}
    cum, running = [], 0
    for v in values:
        running += v
        cum.append(running)
    curve = [[0.0, 0.0]]
    for k in range(1, points + 1):
        i = max(0, round(k * n / points) - 1)
        curve.append([(i + 1) / n, cum[i] / total])
    gini = 1 - 2 * sum(c / total for c in cum) / n + 1 / n
    desc = values[::-1]

    def top(share: float) -> float:
        k = max(1, round(share * n))
        return sum(desc[:k]) / total

    half, acc = 0, 0
    for v in desc:
        acc += v
        half += 1
        if acc >= total / 2:
            break
    return {"curve": curve, "gini": gini, "top1": top(0.01), "top10": top(0.10), "half_by": half, "people": n}


def pagerank(edges: Counter, damping: float = 0.85, iterations: int = 60) -> dict[int, float]:
    """PageRank on the transmission graph, student → teacher weighted by how often: a narrator ranks high when
    much of the corpus flows THROUGH him towards the Prophet."""
    out_weight: dict[int, float] = defaultdict(float)
    incoming: dict[int, list[tuple[int, int]]] = defaultdict(list)
    nodes = set()
    for (s, t), w in edges.items():
        out_weight[s] += w
        incoming[t].append((s, w))
        nodes.update((s, t))
    if not nodes:
        return {}
    n = len(nodes)
    rank = {v: 1 / n for v in nodes}
    for _ in range(iterations):
        sink = sum(rank[v] for v in nodes if not out_weight[v])
        new = {}
        for v in nodes:
            flow = sum(rank[s] * w / out_weight[s] for s, w in incoming[v])
            new[v] = (1 - damping) / n + damping * (flow + sink / n)
        rank = new
    return rank


# ------------------------------------------------------------------ loading
def _books(conn: sqlite3.Connection, collection: str | None) -> list[tuple[int, str, str]]:
    """(id, key, name) of the books measured: one; every ACTIVE Sunni book (None, road A); or every active Shia
    book ("@shia", road B) — in reading order (core.books)."""
    from isnady.core import books as core_books

    ids = dict(conn.execute("SELECT key, id FROM collections").fetchall())
    if collection and collection != SHIA_SCOPE:
        row = conn.execute("SELECT id, key, name FROM collections WHERE key = ?", (collection,)).fetchone()
        from isnady.core import titles

        return [(row[0], row[1], titles.book(row[1], row[2], "en"))] if row else []
    want = "shia" if collection == SHIA_SCOPE else "sunni"
    from isnady.core import titles

    # the English title: saved results are the same whatever the interface language; the screen translates them
    return [(ids[b["key"]], b["key"], titles.book(b["key"], b["source_name"], "en")) for b in core_books.all_books(conn)
            if (b["tradition"] == "shia") == (want == "shia")]


def fingerprint(conn: sqlite3.Connection, collection: str | None) -> str:
    one = lambda sql: tuple(conn.execute(sql).fetchone())  # noqa: E731
    from isnady.core import books as core_books

    parts = [METHOD, collection or "*", sorted(core_books.disabled()) if not collection else [], one("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM hadiths"),
             one("SELECT COUNT(*), SUM(person_id IS NOT NULL), SUM(COALESCE(person_id, 0)) FROM isnad_links"),
             one("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM verdicts"),
             one("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM grades"),
             # the years of death too: the time gaps of the chains are counted from them (read again in v0.3.0)
             one("SELECT COUNT(*), COALESCE(MAX(id), 0), COALESCE(SUM(death_year_ah), 0) FROM persons")]
    return json.dumps(parts, default=str)


def cache_name(prefix: str, collection: str | None) -> str:
    """The file a result is kept in (DX1): one per book, and one per SET of active books for "all books", so
    switching a book off and on again reads the earlier result instead of computing it again."""
    from isnady.core import books as core_books

    off = sorted(core_books.disabled())
    tail = "" if collection not in (None, SHIA_SCOPE) or not off else "-" + hashlib.md5(",".join(off).encode()).hexdigest()[:8]
    scope = {None: "all_sunni_books", SHIA_SCOPE: "all_shia_books"}.get(collection) or core_books.full_name(collection)
    return f"{prefix}-{scope}{tail}.json"


def _persons(conn: sqlite3.Connection, tradition: str = "sunni") -> dict[int, dict]:
    """Every narrator of one tradition: name, tabaqa, year of death and his critic's rank (the first verdict) —
    Ibn Hajar's twelve for the Sunni, al-Najashi's four Imami categories for the Shia."""
    out = {}
    for pid, name, tabaqa, death, rank in conn.execute(
            """SELECT p.id, p.name_ar, p.tabaqa, p.death_year_ah,
                      (SELECT v.rank FROM verdicts v WHERE v.person_id = p.id ORDER BY v.id LIMIT 1)
               FROM persons p WHERE COALESCE(p.tradition, 'sunni') = ?""", (tradition,)):
        out[pid] = {"name": name, "tabaqa": tabaqa, "death": death, "rank": rank}
    return out


def _chains(conn: sqlite3.Connection, book_ids: list[int]) -> list[dict]:
    """Every chain of the books: its hadith, its book, whether it reaches the Prophet, its links in order."""
    marks = ",".join("?" * len(book_ids))
    chains: dict[int, dict] = {}
    for isnad_id, hadith_id, book, reaches, position, person in conn.execute(
            f"""SELECT i.id, i.hadith_id, h.collection_id, i.reaches_prophet, l.position, l.person_id
                FROM isnads i JOIN hadiths h ON h.id = i.hadith_id
                LEFT JOIN isnad_links l ON l.isnad_id = i.id AND i.problem IS NULL
                WHERE h.collection_id IN ({marks}) AND (i.problem IS NULL OR i.ordinal = 1)
                ORDER BY i.id, l.position""", book_ids):
        # a chain not split into narrators (its links as far as read, or borrowed from the hadith before) is drawn on
        # the pages but measured here as before: no links — no chain is counted twice, none half
        c = chains.setdefault(isnad_id, {"hadith": hadith_id, "book": book, "reaches": bool(reaches), "links": []})
        if position is not None:
            c["links"].append(person)
    return list(chains.values())


# ------------------------------------------------------------------ the analysis
def analyse(conn: sqlite3.Connection, collection: str | None = None, progress=None) -> dict:
    say = progress or (lambda _m: None)
    rng = random.Random(SEED)
    books = _books(conn, collection)
    if not books:
        return {"empty": True}
    book_name = {bid: name for bid, _key, name in books}
    road = road_of(conn, collection)
    tradition = road.tradition
    rank_groups = road.rank_groups
    group_of = road.group_of
    ngroups = len(rank_groups)
    say(tr("Reading the narrators"))
    persons = _persons(conn, tradition)
    say(tr("Reading the chains"))
    chains = _chains(conn, [b[0] for b in books])
    hadith_count = conn.execute(
        f"SELECT COUNT(*) FROM hadiths WHERE collection_id IN ({','.join('?' * len(books))})",
        [b[0] for b in books]).fetchone()[0]

    # ---- overview, per book and in all
    per_book: dict[int, dict] = {bid: {"name": book_name[bid], "chains": 0, "links": 0, "identified": 0,
                                       "reaching": 0, "full": 0, "lengths": Counter(), "groups": [0] * ngroups,
                                       "narrators": set()} for bid in book_name}
    link_count: Counter = Counter()
    hadith_of: dict[int, set] = defaultdict(set)
    edges: Counter = Counter()
    weakest_of_hadith: dict[int, int] = {}
    length_of_hadith: dict[int, int] = {}
    gaps: Counter = Counter()
    gap_pairs: Counter = Counter()
    order_ok = order_bad = 0
    order_pairs: Counter = Counter()
    weakest_dist = [0] * ngroups
    weakest_full = [0] * ngroups

    say(tr("Measuring the chains"))
    for c in chains:
        b = per_book[c["book"]]
        links = c["links"]
        b["chains"] += 1
        b["links"] += len(links)
        b["lengths"][len(links)] += 1
        b["reaching"] += c["reaches"]
        ids = [p for p in links if p in persons]
        b["identified"] += len(ids)
        if links and len(ids) == len(links):
            b["full"] += 1
        for p in ids:
            link_count[p] += 1
            hadith_of[p].add(c["hadith"])
            b["narrators"].add(p)
            rank = persons[p]["rank"]
            if rank in group_of:
                b["groups"][group_of[rank]] += 1
        # the weakest identified narrator of the chain (the highest rank number: the weakest)
        ranks = [persons[p]["rank"] for p in ids if persons[p]["rank"] in group_of]
        if ranks:
            weakest = group_of[max(ranks)]
            weakest_dist[weakest] += 1
            if len(ids) == len(links):
                weakest_full[weakest] += 1
            # a hadith with several chains: its best chain (the strongest weakest link)
            h = c["hadith"]
            weakest_of_hadith[h] = min(weakest, weakest_of_hadith.get(h, 99))
        if links and c["hadith"] not in length_of_hadith:
            length_of_hadith[c["hadith"]] = len(links)
        # pairs of neighbours: (student, teacher)
        for student, teacher in zip(links, links[1:]):
            if student in persons and teacher in persons:
                edges[(student, teacher)] += 1
                ds, dt = persons[student]["death"], persons[teacher]["death"]
                if ds and dt:
                    gap = ds - dt
                    gaps[min(max(gap, GAP_BINS[0]), GAP_BINS[-1]) // 10 * 10] += 1
                    if gap > 110 or gap < -60:
                        gap_pairs[(student, teacher, gap)] += 1
                ts, tt = persons[student]["tabaqa"], persons[teacher]["tabaqa"]
                if ts and tt:
                    if ts < tt:                       # the student is of an EARLIER generation than his teacher
                        order_bad += 1
                        order_pairs[(student, teacher)] += 1
                    else:
                        order_ok += 1

    total_links = sum(b["links"] for b in per_book.values())
    total_identified = sum(b["identified"] for b in per_book.values())
    overview = {
        "books": len(books), "hadith": hadith_count, "chains": len(chains), "links": total_links,
        "identified": total_identified, "reaching": sum(b["reaching"] for b in per_book.values()),
        "full": sum(b["full"] for b in per_book.values()),
        "narrators": len(link_count),
    }

    # ---- narrators
    say(tr("Measuring the narrators"))
    rank_all = [0] * ngroups
    for p in persons.values():
        if p["rank"] in group_of:
            rank_all[group_of[p["rank"]]] += 1
    rank_links = [0] * ngroups
    rank_people = [0] * ngroups
    unranked_links = 0
    for p, n in link_count.items():
        rank = persons[p]["rank"]
        if rank in group_of:
            rank_links[group_of[rank]] += n
            rank_people[group_of[rank]] += 1
        else:
            unranked_links += n
    tabaqa_groups = [[0] * ngroups for _ in range(12)]
    for p in link_count:
        t, rank = persons[p]["tabaqa"], persons[p]["rank"]
        if t and 1 <= t <= 12 and rank in group_of:
            tabaqa_groups[t - 1][group_of[rank]] += 1

    def person_row(p: int) -> dict:
        info = persons[p]
        return {"id": p, "name": info["name"], "rank": info["rank"], "tabaqa": info["tabaqa"],
                "death": info["death"], "links": link_count[p], "hadith": len(hadith_of[p])}

    pillars = [person_row(p) for p, _n in link_count.most_common(25)]
    weak_from = road.weak_from
    weak_pillars = [person_row(p) for p, _n in sorted(
        ((p, n) for p, n in link_count.items() if (persons[p]["rank"] or 0) >= weak_from), key=lambda x: -x[1])[:15]]
    concentration = lorenz(list(link_count.values()))
    say(tr("Ranking the narrators in the network"))
    pr = pagerank(edges)
    central = [dict(person_row(p), score=s) for p, s in sorted(pr.items(), key=lambda kv: -kv[1])[:15]]
    teachers_of: Counter = Counter()
    students_of: Counter = Counter()
    for (s, t) in edges:
        teachers_of[s] += 1
        students_of[t] += 1
    most_students = [dict(person_row(p), count=n) for p, n in students_of.most_common(10)]

    # ---- chains
    lengths: Counter = Counter()
    for b in per_book.values():
        lengths.update(b["lengths"])
    suspects = [{"student": person_row(s), "teacher": person_row(t), "gap": g, "times": n}
                for (s, t, g), n in gap_pairs.most_common(15)]
    order_suspects = [{"student": person_row(s), "teacher": person_row(t), "times": n}
                      for (s, t), n in order_pairs.most_common(15)]

    # ---- grades: does the weakest narrator foretell the grade? does the length?
    say(tr("Comparing the grades with the chains"))
    grades_out = []
    order = road.grade_order
    for _bid, key, name in books:
        data = road.load(conn, key)
        for grader, by_hadith in sorted(data.items()):
            # rows: weakest-link group (strong → weak); cols: the grades, strongest first (road A: sahih … fabricated;
            # road B: sahih, hasan, muwaththaq, da'if)
            pairs = [(weakest_of_hadith[h], order.index(g)) for h, g in by_hadith.items()
                     if h in weakest_of_hadith and g in order]
            length_pairs = []
            for h, g in by_hadith.items():
                if h in length_of_hadith and g in order:
                    length_pairs.append((min(length_of_hadith[h], 9) - 1, order.index(g)))
            dist = Counter(by_hadith.values())
            grades_out.append({
                "book": name, "key": key, "grader": grader, "graded": len(by_hadith),
                "distribution": [dist.get(g, 0) for g in order],
                "weakest": association(pairs, ngroups, len(order), rng) if len(pairs) >= 10 else None,
                "length": association(length_pairs, 9, len(order), rng) if len(length_pairs) >= 10 else None,
            })

    # ---- books compared
    book_rows = []
    for bid, b in per_book.items():
        lens = sorted(n for n in b["lengths"].elements() if n)   # the chains split into names (0 = not split)
        book_rows.append({"name": b["name"], "chains": b["chains"], "links": b["links"],
                          "identified": b["identified"] / b["links"] if b["links"] else 0,
                          "reaching": b["reaching"] / b["chains"] if b["chains"] else 0,
                          "median_length": lens[len(lens) // 2] if lens else None,
                          "groups": b["groups"], "narrators": len(b["narrators"])})
    names = [b["name"] for b in per_book.values()]
    sets = [b["narrators"] for b in per_book.values()]
    overlap = [[(len(a & b) / len(a | b) if a | b else 0) for b in sets] for a in sets]

    return {
        "method": METHOD, "collection": collection, "boot": BOOT, "tradition": tradition,
        "groups": [[n, d] for n, d, _r in rank_groups], "grade_labels": road.grade_labels,
        "overview": overview,
        "narrators": {"rank_all": rank_all, "rank_links": rank_links, "rank_people": rank_people,
                      "unranked_links": unranked_links, "tabaqa_groups": tabaqa_groups, "pillars": pillars,
                      "weak_pillars": weak_pillars, "concentration": concentration, "central": central,
                      "most_students": most_students},
        "chains": {"lengths": sorted(lengths.items()), "weakest": weakest_dist, "weakest_full": weakest_full,
                   "gaps": [[k, gaps.get(k, 0)] for k in GAP_BINS], "gap_suspects": suspects,
                   "order_ok": order_ok, "order_bad": order_bad, "order_suspects": order_suspects},
        "grades": grades_out,
        "books": {"rows": book_rows, "names": names, "overlap": overlap},
    }


def cached(conn: sqlite3.Connection, collection: str | None = None, progress=None, recompute: bool = False,
           saved_only: bool = False) -> dict:
    """The analysis from data_dir()/derived/ while the data is unchanged; computed and written otherwise (DX1)."""
    from isnady.data.paths import data_dir

    path = data_dir() / "derived" / cache_name("corpus", collection)
    stamp = fingerprint(conn, collection)
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
    result = analyse(conn, collection, progress)
    result["fingerprint"] = stamp
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    result["from_file"] = None
    return result


__all__ = ["Road", "road_of", "IMAMI_ORDER", "analyse", "cached", "kendall_from_table", "association", "lorenz", "pagerank", "RANK_GROUPS",
           "RANK_GROUPS_SHIA", "SHIA_SCOPE", "ALL_SCOPE", "tradition_of_scope", "isnad_only", "group"]
