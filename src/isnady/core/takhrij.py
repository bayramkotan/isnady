"""Takhrij (YZ2): the narrations of the same hadith, found within and across the imported collections.

Only the TEXT (matn) is compared: the chain is cut off with the isnad parser, otherwise hadith that share
a chain but say different things would look alike. Candidates come from a TF-IDF of the matn words; each
candidate is then checked by CONTAINMENT of word pairs — how much of the shorter text is found in the
longer one — because collections often give a hadith in part (al-Bukhari repeats a long report in pieces
under different chapters). Word pairs made only of the most frequent words ("قال رسول", "صلى الله") are
left out: they made short, unrelated texts look alike.

Two levels, each measured by reading blind samples (Handoff → YZ2):
  same         containment >= 0.5                                   (19 of 20 right before the fix above)
  same_report  containment >= 0.2 and the same identified Companion   (18 of 20 right)
The edition's own "Tekrar" lists for al-Bukhari are too incomplete and partly mis-numbered to be the
measure on their own; they are used as a check.
"""

import math
import sqlite3
import time
from collections import Counter
from typing import Callable

from isnady.core.isnad import split_text
from isnady.core.semantic import NotAvailable, requirements_message, tokens

METHOD_ID = "isnady-takhrij-1"
SAME = 0.5                 # containment for "the same hadith"
SAME_REPORT = 0.2          # containment for "probably the same report" when the Companion is the same
CANDIDATE = 0.25           # TF-IDF cosine for a pair to be checked at all
COMMON_WORDS = 150         # word pairs made only of the most frequent words are not evidence
MIN_PAIRS = 4              # a text needs this many informative word pairs to be compared


def _companions(conn: sqlite3.Connection) -> dict[int, int]:
    """The identified last narrator (normally the Companion) of each hadith's first chain."""
    out = {}
    for hid, pid in conn.execute(
            """SELECT i.hadith_id, l.person_id FROM isnad_links l JOIN isnads i ON i.id = l.isnad_id
               WHERE i.ordinal = 1 AND l.person_id IS NOT NULL
                 AND l.position = (SELECT MAX(position) FROM isnad_links x WHERE x.isnad_id = l.isnad_id)"""):
        out[hid] = pid
    return out


def build(conn: sqlite3.Connection, progress: Callable[[str], None] | None = None) -> dict:
    missing = requirements_message()
    if missing:
        raise NotAvailable(missing)
    import numpy as np
    import scipy.sparse as sp

    say = progress or (lambda _m: None)
    started = time.perf_counter()
    say("Reading the texts of the hadith (the chains are left out)")
    raw = {h: r for h, r in conn.execute("SELECT hadith_id, raw_text FROM isnads WHERE ordinal = 1")}
    matn: dict[int, list[str]] = {}
    for hid, text in conn.execute(
            """SELECT t.hadith_id, t.text FROM texts t JOIN editions e ON e.id = t.edition_id
               WHERE e.language = 'Arabic' ORDER BY t.hadith_id, e.id"""):
        if hid not in matn:
            matn[hid] = tokens(split_text(text, raw.get(hid))[1])
    frequency = Counter()
    for toks in matn.values():
        frequency.update(toks)
    common = {t for t, _c in frequency.most_common(COMMON_WORDS)}
    pairs = {}
    for hid, toks in matn.items():
        sh = {(a, b) for a, b in zip(toks, toks[1:]) if not (a in common and b in common)}
        if len(sh) >= MIN_PAIRS:
            pairs[hid] = sh
    ids = list(pairs)
    n = len(ids)
    if n < 2:
        raise NotAvailable("Import some hadith first.")

    say(f"Finding candidate pairs among {n:,} texts")
    df = Counter()
    for h in ids:
        df.update(set(matn[h]))
    vocab = {t: i for i, t in enumerate(t for t, d in df.items() if 2 <= d <= 0.05 * n)}
    rows, cols, vals = [], [], []
    for r, h in enumerate(ids):
        weights = [(vocab[t], (1 + math.log(c)) * math.log(n / df[t]))
                   for t, c in Counter(matn[h]).items() if t in vocab]
        norm = math.sqrt(sum(w * w for _, w in weights)) or 1.0
        for j, w in weights:
            rows.append(r)
            cols.append(j)
            vals.append(w / norm)
    x = sp.csr_matrix((np.array(vals, dtype=np.float32), (rows, cols)), shape=(n, len(vocab)))
    companion = _companions(conn)
    found = []
    for start in range(0, n, 1000):
        block = (x[start:start + 1000] @ x.T).tocsr()
        for r in range(block.shape[0]):
            i = start + r
            row = block.getrow(r)
            for j, cosine in zip(row.indices, row.data):
                if j <= i or cosine < CANDIDATE:
                    continue
                a, b = ids[i], ids[j]
                pa, pb = pairs[a], pairs[b]
                containment = len(pa & pb) / min(len(pa), len(pb))
                if containment >= SAME:
                    found.append((a, b, "same", containment))
                elif containment >= SAME_REPORT and companion.get(a) and companion.get(a) == companion.get(b):
                    found.append((a, b, "same_report", containment))
        say(f"Compared {min(start + 1000, n):,} of {n:,} texts")
    with conn:
        conn.execute("DELETE FROM hadith_relations WHERE method LIKE 'isnady-takhrij%'")
        conn.executemany("INSERT OR REPLACE INTO hadith_relations (hadith_a, hadith_b, kind, score, method) "
                         "VALUES (?, ?, ?, ?, ?)", [(a, b, k, round(s, 3), METHOD_ID) for a, b, k, s in found])
    kinds = Counter(k for _a, _b, k, _s in found)
    meta = {"method": METHOD_ID, "texts": n, "same": kinds["same"], "same_report": kinds["same_report"],
            "seconds": round(time.perf_counter() - started, 1)}
    say(f"Takhrij ready: {kinds['same']:,} pairs of the same hadith, {kinds['same_report']:,} probably the same report")
    return meta


def related(conn: sqlite3.Connection, hadith_id: int) -> list[dict]:
    """Other narrations of this hadith: book, number, level and overlap, best first."""
    rows = conn.execute(
        """SELECT CASE WHEN r.hadith_a = ? THEN r.hadith_b ELSE r.hadith_a END AS other, r.kind, r.score,
                  c.key, c.name, h.number, h.number_sort
           FROM hadith_relations r
           JOIN hadiths h ON h.id = CASE WHEN r.hadith_a = ? THEN r.hadith_b ELSE r.hadith_a END
           JOIN collections c ON c.id = h.collection_id
           WHERE r.hadith_a = ? OR r.hadith_b = ?
           ORDER BY (r.kind = 'same') DESC, c.key, h.number_sort""",
        (hadith_id, hadith_id, hadith_id, hadith_id)).fetchall()
    return [{"hadith_id": r[0], "kind": r[1], "score": r[2], "book": r[3], "book_name": r[4], "number": r[5]}
            for r in rows]


def status(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT COUNT(*), SUM(kind = 'same'), SUM(kind = 'same_report') FROM hadith_relations "
                       "WHERE method LIKE 'isnady-takhrij%'").fetchone()
    return {"pairs": row[0] or 0, "same": row[1] or 0, "same_report": row[2] or 0}
