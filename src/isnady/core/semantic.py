"""Meaning search (YZ1a): cross-lingual latent semantic analysis, learnt from isnady's own data.

Every hadith is held in Arabic AND in its translations, side by side: a parallel corpus. Latent
semantic analysis (a truncated singular value decomposition of the TF-IDF matrix) over documents that
join all the languages of one hadith learns concepts shared by the languages, so a Turkish or English
query finds an Arabic hadith that shares none of its words, and a query finds hadith on the same topic
without the exact words. Nothing is downloaded and no outside model or licence is involved; the model
is learnt on this computer from the sources imported here, and rebuilt when they change.

Requires numpy and scipy:  pip install "isnady[ai]"
A pretrained neural model (YZ1b) will be a second engine behind the same functions.
"""

import json
import math
import re
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from isnady.core.normalize import normalize
from isnady.core.search import SearchQuery, SearchResult, _load_result
from isnady.data.paths import data_dir

METHOD_ID = "isnady-lsa-2"
DEFAULT_DIMS = 200
MIN_DF = 3                  # a word must appear in at least this many hadith
MAX_DF_SHARE = 0.4          # words in more than this share of hadith carry no meaning of their own
LATIN_STEM = 5              # Turkish and other Latin-script words cut to their first five letters ("F5")
LEXICAL_WEIGHT = 0.5        # final score = weight × word match + (1 − weight) × concept match
_ARABIC = re.compile(r"[\u0600-\u06FF]")
_PREFIXES = ("وبال", "فبال", "وال", "فال", "بال", "كال", "لل", "ال")


class NotAvailable(Exception):
    """numpy/scipy missing, or the index not built; the message tells the user what to do."""


def requirements_message() -> str | None:
    try:
        import numpy  # noqa: F401
        import scipy.sparse  # noqa: F401
        import scipy.sparse.linalg  # noqa: F401
    except ImportError:
        return 'Meaning search needs numpy and scipy: pip install "isnady[ai]"'
    return None


def _model_dir():
    d = data_dir() / "ai"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tokens(text: str) -> list[str]:
    """Words after isnady's normalization; Arabic words lose the article and joined particles
    (و ف ب ك ل + ال), so بالنيات, والنية and النيات meet at نيات / نيه."""
    out = []
    for w in normalize(text).split():
        if _ARABIC.search(w):
            for p in _PREFIXES:
                if w.startswith(p) and len(w) - len(p) >= 3:
                    w = w[len(p):]
                    break
            else:
                if w[:1] in ("و", "ف") and len(w) > 4:
                    w = w[1:]
        elif len(w) > LATIN_STEM:
            # Turkish is agglutinative ("öğrenmenin", "öğrendi", "öğrenmek"); keeping the first five letters
            # is a measured, simple stand-in for a stemmer in Turkish retrieval (Can et al., 2008, "F5")
            w = w[:LATIN_STEM]
        if len(w) >= 2 and not w.isdigit():
            out.append(w)
    return out


def _stamp(conn: sqlite3.Connection) -> str:
    n, m = conn.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM texts").fetchone()
    return f"{METHOD_ID}|{n}|{m}"


def status(conn: sqlite3.Connection) -> dict:
    meta_file = _model_dir() / "lsa.json"
    if not meta_file.exists():
        return {"built": False}
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except ValueError:
        return {"built": False}
    meta["built"] = True
    meta["stale"] = meta.get("stamp") != _stamp(conn)
    return meta


def build(conn: sqlite3.Connection, dims: int = DEFAULT_DIMS,
          progress: Callable[[str], None] | None = None) -> dict:
    missing = requirements_message()
    if missing:
        raise NotAvailable(missing)
    import numpy as np
    import scipy.sparse as sp
    from scipy.sparse.linalg import svds

    say = progress or (lambda _m: None)
    started = time.perf_counter()
    say("Reading texts")
    docs: dict[int, list[str]] = {}
    for hadith_id, text in conn.execute("SELECT hadith_id, text FROM texts ORDER BY hadith_id"):
        docs.setdefault(hadith_id, []).extend(tokens(text))
    ids = list(docs)
    n = len(ids)
    if n < 50:
        raise NotAvailable("Import some hadith first: meaning search learns from the imported texts.")

    say(f"Learning the vocabulary of {n:,} hadith")
    df = Counter()
    for toks in docs.values():
        df.update(set(toks))
    vocab = sorted(t for t, c in df.items() if c >= MIN_DF and c <= MAX_DF_SHARE * n)
    index = {t: i for i, t in enumerate(vocab)}
    idf = np.array([math.log((1 + n) / (1 + df[t])) + 1.0 for t in vocab], dtype=np.float32)

    rows, cols, vals = [], [], []
    for r, hid in enumerate(ids):
        for t, c in Counter(docs[hid]).items():
            j = index.get(t)
            if j is not None:
                rows.append(r)
                cols.append(j)
                vals.append((1.0 + math.log(c)) * idf[j])
    x = sp.csr_matrix((np.array(vals, dtype=np.float32), (rows, cols)), shape=(n, len(vocab)))
    norms = np.sqrt(np.asarray(x.multiply(x).sum(axis=1)).ravel())
    norms[norms == 0] = 1.0
    x = sp.diags(1.0 / norms) @ x

    k = max(10, min(dims, min(x.shape) - 1))
    say(f"Finding {k} shared concepts across the languages")
    _u, _s, vt = svds(x.astype(np.float64), k=k, random_state=0)
    vt = vt.astype(np.float32)
    vecs = np.asarray(x @ vt.T, dtype=np.float32)
    lengths = np.linalg.norm(vecs, axis=1)
    lengths[lengths == 0] = 1.0
    vecs = (vecs / lengths[:, None]).astype(np.float16)

    folder = _model_dir()
    np.savez_compressed(folder / "lsa.npz", idf=idf, components=vt.astype(np.float16),
                        doc_ids=np.array(ids, dtype=np.int64), doc_vectors=vecs,
                        x_data=x.data.astype(np.float16), x_indices=x.indices.astype(np.int32),
                        x_indptr=x.indptr.astype(np.int64), x_shape=np.array(x.shape, dtype=np.int64))
    (folder / "lsa.vocab").write_text("\n".join(vocab), encoding="utf-8")
    meta = {"method": METHOD_ID, "dims": k, "documents": n, "terms": len(vocab), "stamp": _stamp(conn),
            "built_at": time.strftime("%Y-%m-%d %H:%M"), "seconds": round(time.perf_counter() - started, 1)}
    (folder / "lsa.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _cache.clear()
    say(f"Meaning index ready: {n:,} hadith, {len(vocab):,} words, {k} concepts")
    return meta


_cache: dict = {}


def _load():
    if "model" in _cache:
        return _cache["model"]
    import numpy as np

    folder = _model_dir()
    if not (folder / "lsa.npz").exists():
        raise NotAvailable("The meaning index is not built yet: iy ai build  (or Tools → Build Meaning Index)")
    data = np.load(folder / "lsa.npz")
    vocab = (folder / "lsa.vocab").read_text(encoding="utf-8").split("\n")
    import scipy.sparse as sp

    model = {"index": {t: i for i, t in enumerate(vocab)}, "idf": data["idf"],
             "components": data["components"].astype(np.float32), "ids": data["doc_ids"],
             "vectors": data["doc_vectors"].astype(np.float32),
             "x": sp.csr_matrix((data["x_data"].astype(np.float32), data["x_indices"], data["x_indptr"]),
                                shape=tuple(data["x_shape"]))}
    _cache["model"] = model
    return model


def _weights(text: str):
    """The text's TF-IDF vector over the learnt vocabulary (unit length), or None if no known word."""
    import numpy as np

    m = _load()
    counts = Counter(t for t in tokens(text) if t in m["index"])
    if not counts:
        return None
    q = np.zeros(len(m["idf"]), dtype=np.float32)
    for t, c in counts.items():
        j = m["index"][t]
        q[j] = (1.0 + math.log(c)) * m["idf"][j]
    return q / (np.linalg.norm(q) or 1.0)


def embed(text: str):
    """A text as a point in the learnt concept space (unit length), or None if no known word."""
    import numpy as np

    q = _weights(text)
    if q is None:
        return None
    v = _load()["components"] @ q
    norm = np.linalg.norm(v)
    return v / norm if norm else None


def scores(text: str, lexical_weight: float = LEXICAL_WEIGHT):
    """Hybrid score for every indexed hadith: shared words (exact quotes, rare terms) and shared
    concepts (other languages, other wording). Returns (hadith ids, scores) or None."""
    q = _weights(text)
    if q is None:
        return None
    m = _load()
    v = m["components"] @ q
    import numpy as np

    v = v / (np.linalg.norm(v) or 1.0)
    concept = m["vectors"] @ v
    lexical = m["x"] @ q
    return m["ids"], lexical_weight * lexical + (1.0 - lexical_weight) * concept


@dataclass
class MeaningPage:
    query: SearchQuery
    total: int
    results: list[SearchResult]
    scores: list[float]
    elapsed_ms: int
    unknown_words: list[str] = field(default_factory=list)


def search(conn: sqlite3.Connection, query: SearchQuery, min_score: float = 0.10) -> MeaningPage:
    """Hadith closest in meaning to the query, best first. Scores are cosine similarities (0–1)."""
    missing = requirements_message()            # before importing numpy: a clear message, not a traceback
    if missing:
        raise NotAvailable(missing)
    import numpy as np

    started = time.perf_counter()
    m = _load()
    known = [t for t in tokens(query.text) if t in m["index"]]  # noqa: F841 (kept for the message below)
    unknown = [t for t in tokens(query.text) if t not in m["index"]]
    scored = scores(query.text)
    if scored is None:
        return MeaningPage(query, 0, [], [], 0, unknown)
    ids, all_scores = scored
    order = np.argsort(-all_scores)
    allowed = None
    if query.collections:
        allowed = {r[0] for r in conn.execute(
            f"SELECT h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id "
            f"WHERE c.key IN ({','.join('?' * len(query.collections))})", query.collections)}
    picked = []
    for i in order:
        if all_scores[i] < min_score:
            break
        hid = int(ids[i])
        if allowed is not None and hid not in allowed:
            continue
        picked.append((hid, float(all_scores[i])))
    page = picked[query.offset: query.offset + query.limit]
    results = [_load_result(conn, hid, [], query) for hid, _s in page]
    return MeaningPage(query, len(picked), results, [s for _h, s in page],
                       int((time.perf_counter() - started) * 1000), unknown if not known else [])
