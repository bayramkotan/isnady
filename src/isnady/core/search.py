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
from isnady.core.i18n import tr

MODES = ("all", "any", "phrase")
_MIN_TRIGRAM = 3
_BATCH = 2000
_BULK = 5000            # this many texts or more to index: their search index built without the trigger


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
        CREATE TABLE IF NOT EXISTS words (word TEXT PRIMARY KEY, n INTEGER NOT NULL) WITHOUT ROWID;
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
        DROP TABLE IF EXISTS words;
        """
    )


def ensure_index(conn: sqlite3.Connection, progress: Callable[[str], None] | None = None) -> int:
    """Index every text that is not indexed yet. Returns how many were added."""
    say = progress or (lambda _m: None)
    _create_index_tables(conn)
    row = conn.execute("SELECT value FROM core_meta WHERE key = 'normalizer_version'").fetchone()
    if row is not None and row[0] != str(NORMALIZER_VERSION):
        say(tr("Normalisation rules changed; rebuilding the search index"))
        _drop_index(conn)
        _create_index_tables(conn)
    conn.execute(
        "INSERT OR REPLACE INTO core_meta (key, value) VALUES ('normalizer_version', ?)", (str(NORMALIZER_VERSION),)
    )
    missing = conn.execute(
        "SELECT COUNT(*) FROM texts t LEFT JOIN text_norm n ON n.text_id = t.id WHERE n.text_id IS NULL"
    ).fetchone()[0]
    if not missing:
        if conn.execute("SELECT 1 FROM words LIMIT 1").fetchone() is None and \
                conn.execute("SELECT 1 FROM text_norm LIMIT 1").fetchone() is not None:
            say(tr("Listing the words of the texts (once)"))
            _add_words(conn, None, rebuild=True)       # a database indexed before the word list existed
        conn.commit()
        return 0
    say(tr("Indexing {missing} texts for search", missing=missing))
    # the texts to index, found once (each batch used to look for them again from the first text: slower and
    # slower as the index grew); many at once: their search index built in one statement, not row by row by the
    # trigger (the full isnady-data: 89 s → about 35 s, the same index)
    ids = [r[0] for r in conn.execute(
        "SELECT t.id FROM texts t LEFT JOIN text_norm n ON n.text_id = t.id WHERE n.text_id IS NULL ORDER BY t.id")]
    bulk = len(ids) >= _BULK and has_fts(conn)
    # an empty index (a first import): FTS5 builds it from the table in one pass, faster still than in chunks
    fresh = bulk and conn.execute("SELECT 1 FROM text_norm LIMIT 1").fetchone() is None
    if bulk:
        conn.execute("DROP TRIGGER IF EXISTS text_norm_ai")
    added = 0
    try:
        for start in range(0, len(ids), _BATCH):
            chunk = ids[start:start + _BATCH]
            rows = conn.execute(f"SELECT id, text FROM texts WHERE id IN ({','.join('?' * len(chunk))})",
                                chunk).fetchall()
            conn.executemany("INSERT INTO text_norm (text_id, norm) VALUES (?, ?)",
                             [(r[0], normalize(r[1])) for r in rows])
            if bulk and not fresh:
                conn.execute(f"INSERT INTO texts_fts (rowid, norm) SELECT text_id, norm FROM text_norm "
                             f"WHERE text_id IN ({','.join('?' * len(chunk))})", chunk)
            conn.commit()
            added += len(rows)
        if fresh:
            conn.execute("INSERT INTO texts_fts (texts_fts) VALUES ('rebuild')")
            conn.commit()
        # every word again on a first import, or when the word list is still empty (a database from before it)
        _add_words(conn, ids, rebuild=fresh or conn.execute("SELECT 1 FROM words LIMIT 1").fetchone() is None)
    finally:
        if bulk:
            _create_index_tables(conn)               # the trigger again, for the texts added one by one later
            conn.commit()
    return added


_WORD_RE = re.compile(r"\w+")


def _add_words(conn: sqlite3.Connection, text_ids: list[int] | None, rebuild: bool = False) -> None:
    """The words of the texts with how often each is (spellings, S4b): all of them, or those of new texts added."""
    from collections import Counter

    counts: Counter = Counter()
    if rebuild or text_ids is None:
        conn.execute("DELETE FROM words")
        for (norm,) in conn.execute("SELECT norm FROM text_norm"):
            counts.update(_WORD_RE.findall(norm))
    else:
        for start in range(0, len(text_ids), _BATCH):
            chunk = text_ids[start:start + _BATCH]
            for (norm,) in conn.execute(f"SELECT norm FROM text_norm WHERE text_id IN ({','.join('?' * len(chunk))})",
                                        chunk):
                counts.update(_WORD_RE.findall(norm))
    conn.executemany("INSERT INTO words (word, n) VALUES (?, ?) ON CONFLICT(word) DO UPDATE SET n = n + excluded.n",
                     counts.items())
    conn.commit()


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
    spellings: dict = field(default_factory=dict)   # a word as typed → the spellings found for it (?, *, near)


# punctuation that clings to a word in a pasted passage ("قَالَ:", "«لَا", "أَوْ؟"): not part of what is looked for
# (2026-10-14: a passage of Musnad Ahmad 12338 pasted with «» and ":" found nothing). "?" and "؟" inside a word and
# "*" anywhere are wildcards: one unknown letter, any letters ("ي?من", "مسل*")
_PUNCT_RE = re.compile(r"[«»“”„\"‘’:;؛،,.!()\[\]{}<>…–—\-/\\|~﴿﴾]+")
_QUESTION_END_RE = re.compile(r"(?<=\w)[?؟]+(?=\s|$)")
WILDCARDS = "?؟*"


def _terms(query: SearchQuery) -> list[str]:
    text = _QUESTION_END_RE.sub(" ", normalize(query.text))      # a question mark ending a word is punctuation
    norm = " ".join(_PUNCT_RE.sub(" ", text).split())
    norm = " ".join(w for w in norm.split() if w.strip(WILDCARDS))  # a lone "?" or "*" is no word
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


# ------------------------------------------------------------------ spellings: wildcards and near ones (S4b)
# Bayram (2026-10-14): "Aramanın çok çok iyi olmasını istiyorum. Bir (ya da fazla) hareke veya bir (ya da fazla)
# bilinmeyen harf varsa da bulmasını istiyorum." Harakat never mattered (normalize). A word with an unknown letter is
# written with "?" (one letter) or "*" (any letters); a word not found as typed is looked for in its spellings one
# letter away (a letter more, less or different) — every word of the query may have its own. The words come from
# the words of the texts (table `words`, filled with the search index).
NEAR_MAX = 30                  # spellings tried for one word, the most frequent first
NEAR_MIN_LENGTH = 3            # shorter words have too many neighbours to mean anything


def _vocabulary(conn: sqlite3.Connection) -> tuple[str, dict]:
    """Every word of the texts, one per line (for one regular expression over them all), and how often each is."""
    from isnady.core import cache

    def load():
        counts = dict(conn.execute("SELECT word, n FROM words"))
        return "\n".join(counts), counts
    return cache.memo(conn, "vocabulary", "all", load)


def _in_vocabulary(conn: sqlite3.Connection, pattern: str, limit: int = NEAR_MAX) -> list[str]:
    lines, counts = _vocabulary(conn)
    found = re.findall(r"^(?:" + pattern + r")$", lines, re.M)
    return sorted(set(found), key=lambda w: -counts.get(w, 0))[:limit]


def spellings_text(spellings: dict, most: int = 4) -> str:
    """"يمن → يومن; مسل* → مسلم, مسلمه …": what a search found its words as (for the result line)."""
    return "; ".join(f"{w} → " + ", ".join(alts[:most]) + (" …" if len(alts) > most else "")
                     for w, alts in spellings.items())


def _wildcard_pattern(word: str) -> str:
    return "".join("." if ch in "?؟" else ".*" if ch == "*" else re.escape(ch) for ch in word)


def _near_pattern(word: str) -> str:
    """Every spelling one letter away: a letter changed, left out, or added."""
    pats = set()
    for i in range(len(word)):
        pats.add(re.escape(word[:i]) + "." + re.escape(word[i + 1:]))
        pats.add(re.escape(word[:i]) + re.escape(word[i + 1:]))
    for i in range(len(word) + 1):
        pats.add(re.escape(word[:i]) + "." + re.escape(word[i:]))
    return "|".join(sorted(pats))


def _spell(conn: sqlite3.Connection, terms: list[str], mode: str, near: str = "") -> tuple[list[str], dict]:
    """The terms with each word that has a wildcard replaced by its spellings, joined by "|"; with near="unknown"
    also each word found in no text, with near="all" every word long enough, by the word and its spellings one
    letter away. Returns (terms, {word: spellings})."""
    spellings: dict = {}
    _lines, counts = _vocabulary(conn)

    def word(w: str) -> str:
        if any(ch in w for ch in WILDCARDS):
            alts = _in_vocabulary(conn, _wildcard_pattern(w))
        elif near and len(w) >= NEAR_MIN_LENGTH and (near == "all" or w not in counts):
            alts = [a for a in _in_vocabulary(conn, _near_pattern(w)) if a != w and len(a) >= _MIN_TRIGRAM]
            alts = [w] + alts
        else:
            return w
        if not alts:
            alts = [w.strip(WILDCARDS) or w]          # nothing like it: the word as typed (found nowhere)
        if alts != [w]:
            spellings[w] = [a for a in alts if a != w]
        return "|".join(alts)

    if mode == "phrase":
        return [" ".join(word(w) for w in terms[0].split())], spellings
    return [word(t) for t in terms], spellings


def _fts_literal(term: str) -> str:
    return '"' + term.replace('"', "") + '"'


def _word_re(term: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)")


def _alt_re(word: str) -> str:
    alts = word.split("|")
    return re.escape(alts[0]) if len(alts) == 1 else "(?:" + "|".join(re.escape(a) for a in alts) + ")"


def _phrase_re(phrase: str, whole_words: bool) -> re.Pattern:
    """The words of a phrase in order, whatever punctuation or spaces stand between them in the text
    ("قال لا يومن" finds "قال: «لا يومن" and "قال، لا يومن"); a word may be several spellings ("a|b")."""
    body = r"[^\w]+".join(_alt_re(w) for w in phrase.split())
    return re.compile(r"(?<!\w)" + body + r"(?!\w)" if whole_words else body)


def _spans(norm: str, terms: list[str], whole_words: bool, mode: str = "all") -> list[tuple[int, int]]:
    spans = []
    if mode == "phrase":
        for term in terms:
            spans.extend(m.span() for m in _phrase_re(term, whole_words).finditer(norm))
        terms = []
    for term in [a for t in terms for a in t.split("|")]:
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
    if mode == "phrase":
        return all(_phrase_re(t, whole_words).search(norm) for t in terms)
    if whole_words:
        found = [any(_word_re(a).search(norm) for a in t.split("|")) for t in terms]
    else:
        found = [any(a in norm for a in t.split("|")) for t in terms]
    return any(found) if mode == "any" else all(found)


def search(conn: sqlite3.Connection, query: SearchQuery) -> SearchPage:
    """The hits of a query; the same query asked again (another page of results, back to it, the same words) is
    not searched again while the database is unchanged (core.cache)."""
    from isnady.core import cache, i18n

    key = (query.text, query.mode, query.whole_words, tuple(query.collections), tuple(query.languages),
           query.limit, query.offset, i18n.language())
    return cache.memo(conn, "search", key, lambda: _search_counted(conn, query))


def _search_counted(conn: sqlite3.Connection, query: SearchQuery) -> SearchPage:
    started = time.perf_counter()
    if query.mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    terms = _terms(query)
    use_index = has_fts(conn)
    if not terms:
        return SearchPage(query, terms, 0, [], use_index, 0)
    typed = list(terms)
    terms, spellings = _spell(conn, typed, query.mode, near=False)
    page = _search_terms(conn, query, terms, use_index, started, spellings)
    for near in ("unknown", "all"):
        if page.total:
            break
        # nothing as typed: the words found in no text (then every word) also in their spellings one letter away
        near_terms, near_spellings = _spell(conn, typed, query.mode, near)
        if near_terms != terms:
            terms = near_terms
            page = _search_terms(conn, query, terms, use_index, started, near_spellings)
    return page


def _search_terms(conn: sqlite3.Connection, query: SearchQuery, terms: list[str], use_index: bool, started: float,
                  spellings: dict) -> SearchPage:

    # 1. candidate texts: index for terms long enough, instr() otherwise; a phrase: texts with all its words (the
    #    punctuation between them may differ), checked in order below
    joiner = " OR " if query.mode == "any" else " AND "
    groups = list(dict.fromkeys(terms[0].split())) if query.mode == "phrase" else terms
    conditions, params = [], []
    for group in groups:                         # a word, or its spellings "a|b|c": any of them
        alts = group.split("|")
        long_ = [a for a in alts if use_index and len(a) >= _MIN_TRIGRAM]
        short = [a for a in alts if a not in long_]
        parts = []
        if long_:
            parts.append("n.text_id IN (SELECT rowid FROM texts_fts WHERE texts_fts MATCH ?)")
            params.append(" OR ".join(_fts_literal(a) for a in long_))
        for a in short:
            parts.append("instr(n.norm, ?) > 0")
            params.append(a)
        conditions.append("(" + " OR ".join(parts) + ")")
    where = [f"({joiner.join(conditions)})"]
    from isnady.core import books as core_books

    keys = query.collections or core_books.active_keys(conn)       # "all books" = every ACTIVE book
    if keys is not None:
        where.append(f"c.key IN ({','.join('?' * len(keys)) or 'NULL'})")
        params.extend(keys)
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
            ORDER BY {core_books.order_sql(conn)}, h.number_sort, h.number""",
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
    if spellings:
        # tell only the spellings the shown hadith really have
        seen = {w for r in results for t in r.texts if t.matched for w in _WORD_RE.findall(normalize(t.text))}
        spellings = {w: [a for a in alts if a in seen] for w, alts in spellings.items()}
        spellings = {w: alts for w, alts in spellings.items() if alts}
    elapsed = int((time.perf_counter() - started) * 1000)
    return SearchPage(query, terms, total, results, use_index, elapsed, spellings if total else {})


def _load_result(conn: sqlite3.Connection, hadith_id: int, terms: list[str], query: SearchQuery) -> SearchResult:
    """A hadith with its texts (the matched words marked): kept per hadith, words and languages (core.cache) —
    a book read again, a search repeated, draw from memory."""
    from isnady.core import cache

    key = (hadith_id, tuple(terms), tuple(query.languages), query.mode, query.whole_words)
    return cache.memo(conn, "result", key, lambda: _load_result_counted(conn, hadith_id, terms, query))


def _load_result_counted(conn: sqlite3.Connection, hadith_id: int, terms: list[str],
                         query: SearchQuery) -> SearchResult:
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
        if not terms:                     # nothing to mark (a book being read): no need to fold the text
            texts.append(TextHit(r[0], r[1] or "", r[2] or "ltr", r[3], [], False))
            continue
        norm, index_map = normalize_with_map(r[3])
        spans = _spans(norm, terms, query.whole_words, query.mode)
        texts.append(TextHit(r[0], r[1] or "", r[2] or "ltr", r[3],
                             _to_original(spans, index_map, len(r[3])), bool(spans)))
    grades = [(g[0], g[1]) for g in conn.execute(
        "SELECT grader_name, grade FROM grades WHERE hadith_id = ? ORDER BY grader_name", (hadith_id,)
    )]
    return SearchResult(hadith_id, head[1], head[2], head[0], texts, grades)


# ----------------------------------------------------------------- filters
def list_collections(conn: sqlite3.Connection) -> list[tuple[str, str, int]]:
    """(key, name, hadith count) of every ACTIVE collection that has texts, Sunni first, in reading order
    (core.books)."""
    from isnady.core import books as core_books

    return [(b["key"], b["name"], b["count"]) for b in core_books.all_books(conn)]


def list_languages(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT language FROM editions WHERE language IS NOT NULL AND text_count > 0 ORDER BY language"
    )]
