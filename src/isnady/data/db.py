"""SQLite storage.

Schema version 1 is PROVISIONAL: it holds hadith text, editions and grades
with full provenance. Narrators, isnad links and verdicts arrive with D2.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from isnady.data.paths import db_path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY,
    key         TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    format      TEXT NOT NULL,
    location    TEXT NOT NULL,
    license     TEXT,
    origin      TEXT NOT NULL CHECK (origin IN ('builtin', 'user')),
    auth_type   TEXT NOT NULL DEFAULT 'none',
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collections (
    id   INTEGER PRIMARY KEY,
    key  TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS editions (
    id            INTEGER PRIMARY KEY,
    source_id     INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    collection_id INTEGER NOT NULL REFERENCES collections(id),
    key           TEXT NOT NULL,
    language      TEXT,
    direction     TEXT,
    author        TEXT,
    comments      TEXT,
    location      TEXT NOT NULL,
    hadith_count  INTEGER NOT NULL DEFAULT 0,
    imported_at   TEXT NOT NULL,
    UNIQUE (source_id, key)
);

CREATE TABLE IF NOT EXISTS sections (
    edition_id   INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    number       INTEGER NOT NULL,
    title        TEXT,
    first_number REAL,
    last_number  REAL,
    PRIMARY KEY (edition_id, number)
);

-- number is TEXT because sources use sub-numbers such as "402.2";
-- number_sort keeps numeric ordering.
CREATE TABLE IF NOT EXISTS hadiths (
    id            INTEGER PRIMARY KEY,
    edition_id    INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    number        TEXT NOT NULL,
    number_sort   REAL,
    arabic_number TEXT,
    ref_book      INTEGER,
    ref_hadith    INTEGER,
    text          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_hadiths_edition ON hadiths(edition_id, number_sort);

-- grade is stored exactly as the source gives it; normalisation is D3's job.
CREATE TABLE IF NOT EXISTS grades (
    id        INTEGER PRIMARY KEY,
    hadith_id INTEGER NOT NULL REFERENCES hadiths(id) ON DELETE CASCADE,
    grader    TEXT NOT NULL,
    grade     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_grades_hadith ON grades(hadith_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        conn.close()
        raise RuntimeError(
            f"Database schema {version} is newer than this isnady supports ({SCHEMA_VERSION}). Update isnady."
        )
    conn.executescript(SCHEMA)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    return conn
