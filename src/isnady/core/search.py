"""Hadith text search.

The search index is DERIVED data owned by the core, not part of the database
schema: `text_norm` holds the normalised text of every text row, and, when the
SQLite build supports it, `texts_fts` is an FTS5 trigram index over it
(substring matching, needed for Arabic words with attached prefixes such as
bi-, wa-, al-). Without FTS5 the search falls back to instr() scans.

Deleting texts removes their index rows through a foreign key cascade and
plain-SQL triggers, so any tool may delete data safely. New texts are indexed
by ensure_index(), which importers' callers and the GUI run.

Known limit (first version): whole-word filtering and paging are done in
Python over all candidates. Fine at tens of thousands of texts; revisit for
hundreds of thousands.
"""

import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Callable

from isnady.core.normalize import NORMALIZER_VERSION, normalize, normalize_with_map

MODES = ("all", "any", "phrase")
_MIN_TRIGRAM = 3
_BATCH = 2000


# ------------------------------------------------------------------- index
def _fts_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp._isnady_probe USING fts5(x, tokenize='trigram')")
        conn.execute("DROP TABLE temp._isnady_probe")
        return True
    except sqlite3.OperationalError:
        return False


def has_fts(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'texts_fts'"
    ).fetchone() is not None


def _create_index_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS core_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS text_norm (
            text_id INTEGER PRIMARY KEY REFERENCES texts(id) ON DELETE CASCADE,
            norm    TEXT NOT NULL
        );
        """
    )
    if _fts_available(conn):
        conn.executescript(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS texts_fts USING fts5(
                norm, content='text_norm', content_rowid='text_id', tokenize='trigram'
            );
            CREATE TRIGGER IF NOT EXISTS text_norm_ai AFTER INSERT ON text_norm BEGIN
                INSERT INTO texts_fts(rowid, norm) VALUES (new.text_id, new.norm);
            END;
            CREATE TRIGGER IF NOT EXISTS text_norm_ad AFTER DELETE ON text_norm BEGIN
                INSERT INTO texts_fts(texts_fts, rowid, norm) VALUES ('delete', old.text_id, old.norm);
            END;
            """
        )


def _drop_index(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TRIGGER IF EXISTS text_norm_ai;
        DROP TRIGGER IF EXISTS text_norm_ad;
        DROP TABLE IF EXISTS texts_fts;
        DROP TABLE IF EXISTS text_norm;
        """
    )


def ensure_index(conn: sqlite3.Connection, progress: Callable[[str], None] | None = None) -> int:
    """Index every text that is not indexed yet. Returns how many were added."""
    say = progress or (lambda _m: None)
    _create_index_tables(conn)
    row = conn.execute("SELECT value FROM core_meta WHERE key = 'normalizer_version'").fetchone()
    if row is not None and row[0] != str(NORMALIZER_VERSION):
        say("Normalisation rules changed; rebuilding the search index")
        _drop_index(conn)
        _create_index_tables(conn)
    conn.execute(
        "INSERT OR REPLACE INTO core_meta (key, value) VALUES ('normalizer_version', ?)", (str(NORMALIZER_VERSION),)
    )
    missing = conn.execute(
        "SELECT COUNT(*) FROM texts t LEFT JOIN text_norm n ON n.text_id = t.id WHERE n.text_id IS NULL"
    ).fetchone()[0]
    if not missing:
        conn.commit()
        return 0
    say(f"Indexing {missing} texts for search")
    added = 0
    while True:
        rows = conn.execute(
            "SELECT t.id, t.text FROM texts t LEFT JOIN text_norm n ON n.text_id = t.id "
            "WHERE n.text_id IS NULL LIMIT ?", (_BATCH,)
        ).fetchall()
        if not rows:
            break
        conn.executemany("INSERT INTO text_norm (text_id, norm) VALUES (?, ?)",
                         [(r[0], normalize(r[1])) for r in rows])
        conn.commit()
        added += len(rows)
    return added


def rebuild_index(conn: sqlite3.Connection, progress: Callable[[str], None] | None = None) -> int:
    """Throw the search index away and build it again from the texts."""
    _drop_index(conn)
    conn.commit()
    return ensure_index(conn, progress)


# ------------------------------------------------------------------ search
@dataclass
class SearchQuery:
    text: str
    mode: str = "all"                     # all | any | phrase
    whole_words: bool = False
    collections: list[str] = field(default_factory=list)   # collection keys; empty = all
    languages: list[str] = field(default_factory=list)     # language names; empty = all
    limit: int = 25
    offset: int = 0


@dataclass
class TextHit:
    edition_key: str
    language: str
    direction: str
    text: str
    spans: list[tuple[int, int]]          # highlight ranges in `text`
    matched: bool


@dataclass
class SearchResult:
    hadith_id: int
    collection_key: str
    collection_name: str
    number: str
    texts: list[TextHit]
    grades: list[tuple[str, str]]         # (grader, grade) exactly as in the source


@dataclass
class SearchPage:
    query: SearchQuery
    terms: list[str]
    total: int
    results: list[SearchResult]
    used_index: bool
    elapsed_ms: int


def _terms(query: SearchQuery) -> list[str]:
    norm = " ".join(normalize(query.text).split())
    if not norm:
        return []
    if query.mode == "phrase":
        return [norm]
    seen, terms = set(), []
    for t in norm.split(" "):
        if t not in seen:
            seen.add(t)
            terms.append(t)
    return terms


def _fts_literal(term: str) -> str:
    return '"' + term.replace('"', "") + '"'


def _word_re(term: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)")


def _spans(norm: str, terms: list[str], whole_words: bool) -> list[tuple[int, int]]:
    spans = []
    for term in terms:
        if whole_words:
            spans.extend(m.span() for m in _word_re(term).finditer(norm))
        else:
            start = norm.find(term)
            while start != -1:
                spans.append((start, start + len(term)))
                start = norm.find(term, start + 1)
    spans.sort()
    merged: list[tuple[int, int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
        else:
            merged.append((s, e))
    return merged


def _to_original(spans: list[tuple[int, int]], index_map: list[int], original_len: int) -> list[tuple[int, int]]:
    out = []
    for s, e in spans:
        start = index_map[s]
        end = index_map[e] if e < len(index_map) else original_len   # keeps trailing diacritics
        out.append((start, end))
    return out


def _text_matches(norm: str, terms: list[str], mode: str, whole_words: bool) -> bool:
    if whole_words:
        found = [bool(_word_re(t).search(norm)) for t in terms]
    else:
        found = [t in norm for t in terms]
    return any(found) if mode == "any" else all(found)


def search(conn: sqlite3.Connection, query: SearchQuery) -> SearchPage:
    started = time.perf_counter()
    if query.mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    terms = _terms(query)
    use_index = has_fts(conn)
    if not terms:
        return SearchPage(query, terms, 0, [], use_index, 0)

    # 1. candidate texts: index for terms long enough, instr() otherwise
    joiner = " OR " if query.mode == "any" else " AND "
    fts_terms = [t for t in terms if use_index and len(t) >= _MIN_TRIGRAM]
    scan_terms = [t for t in terms if t not in fts_terms]
    conditions, params = [], []
    if fts_terms:
        conditions.append("n.text_id IN (SELECT rowid FROM texts_fts WHERE texts_fts MATCH ?)")
        params.append(joiner.join(_fts_literal(t) for t in fts_terms))
    for t in scan_terms:
        conditions.append("instr(n.norm, ?) > 0")
        params.append(t)
    where = [f"({joiner.join(conditions)})"]
    if query.collections:
        where.append(f"c.key IN ({','.join('?' * len(query.collections))})")
        params.extend(query.collections)
    if query.languages:
        where.append(f"e.language IN ({','.join('?' * len(query.languages))})")
        params.extend(query.languages)

    rows = conn.execute(
        f"""SELECT t.hadith_id, n.norm
            FROM text_norm n
            JOIN texts t ON t.id = n.text_id
            JOIN editions e ON e.id = t.edition_id
            JOIN hadiths h ON h.id = t.hadith_id
            JOIN collections c ON c.id = h.collection_id
            WHERE {' AND '.join(where)}
            ORDER BY c.name, h.number_sort, h.number""",
        params,
    ).fetchall()

    # 2. exact check (whole words, all/any within one text), keep hadith order
    hadith_ids: list[int] = []
    seen = set()
    for hadith_id, norm in rows:
        if hadith_id in seen:
            continue
        if _text_matches(norm, terms, query.mode, query.whole_words):
            seen.add(hadith_id)
            hadith_ids.append(hadith_id)

    total = len(hadith_ids)
    page_ids = hadith_ids[query.offset: query.offset + query.limit]
    results = [_load_result(conn, hid, terms, query) for hid in page_ids]
    elapsed = int((time.perf_counter() - started) * 1000)
    return SearchPage(query, terms, total, results, use_index, elapsed)


def _load_result(conn: sqlite3.Connection, hadith_id: int, terms: list[str], query: SearchQuery) -> SearchResult:
    head = conn.execute(
        """SELECT h.number, c.key, c.name FROM hadiths h JOIN collections c ON c.id = h.collection_id
           WHERE h.id = ?""", (hadith_id,)
    ).fetchone()
    lang_filter, params = "", [hadith_id]
    if query.languages:
        lang_filter = f" AND e.language IN ({','.join('?' * len(query.languages))})"
        params.extend(query.languages)
    texts = []
    for r in conn.execute(
        f"""SELECT e.key, e.language, e.direction, t.text FROM texts t JOIN editions e ON e.id = t.edition_id
            WHERE t.hadith_id = ?{lang_filter}
            ORDER BY CASE e.language WHEN 'Arabic' THEN 0 ELSE 1 END, e.language, e.key""",
        params,
    ):
        norm, index_map = normalize_with_map(r[3])
        spans = _spans(norm, terms, query.whole_words)
        texts.append(TextHit(r[0], r[1] or "", r[2] or "ltr", r[3],
                             _to_original(spans, index_map, len(r[3])), bool(spans)))
    grades = [(g[0], g[1]) for g in conn.execute(
        "SELECT grader_name, grade FROM grades WHERE hadith_id = ? ORDER BY grader_name", (hadith_id,)
    )]
    return SearchResult(hadith_id, head[1], head[2], head[0], texts, grades)


# ----------------------------------------------------------------- filters
def list_collections(conn: sqlite3.Connection) -> list[tuple[str, str, int]]:
    """(key, name, hadith count) of every collection that has texts."""
    return [tuple(r) for r in conn.execute(
        """SELECT c.key, c.name, COUNT(DISTINCT h.id) FROM collections c
           JOIN hadiths h ON h.collection_id = c.id JOIN texts t ON t.hadith_id = h.id
           GROUP BY c.id ORDER BY c.name"""
    )]


def list_languages(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT language FROM editions WHERE language IS NOT NULL AND text_count > 0 ORDER BY language"
    )]
