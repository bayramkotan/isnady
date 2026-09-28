"""SQLite storage — schema version 2 (D2).

Design rules
  * A HADITH is one report in one collection (collection + number). A TEXT is
    that hadith in one edition (language / print). Grades, isnads and narrator
    links belong to the hadith, never to a text, so they are stored once.
  * A PERSON is one table for narrators and scholars alike; roles are separate
    rows (al-Bukhari is both a scholar and a narrator in chains).
  * Every fact carries its source. Sources record a licence TIER:
      A = may be redistributed (public domain, CC0, CC BY, Unlicense)
      B = may be redistributed under conditions (ODbL, CC BY-SA, NC)
      C = may not be redistributed (unknown licence, no permission, Shamela)
    and an ORIGIN: builtin (shipped data) or user (User Resources).
    The view `publishable_sources` is the ONLY thing a web or GitHub export
    may read from: builtin + tier A/B. User Resources never leave the machine.
  * Nothing here computes. Reliability scores, isnad analysis and grade
    normalisation live in the Qt-free core (isnady.core), so the desktop app
    and isnady.net give identical answers.
  * Plain SQL types only, so the schema can move to a server database later.
"""

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from isnady.data.paths import db_path

SCHEMA_VERSION = 2

SCHEMA = """
-- ------------------------------------------------------------------ sources
CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY,
    key         TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    format      TEXT NOT NULL,
    location    TEXT NOT NULL,
    license     TEXT,
    tier        TEXT NOT NULL DEFAULT 'C' CHECK (tier IN ('A', 'B', 'C')),
    origin      TEXT NOT NULL CHECK (origin IN ('builtin', 'user')),
    auth_type   TEXT NOT NULL DEFAULT 'none',
    imported_at TEXT NOT NULL
);

CREATE VIEW IF NOT EXISTS publishable_sources AS
    SELECT * FROM sources WHERE origin = 'builtin' AND tier IN ('A', 'B');

-- ------------------------------------------------------------------ persons
-- Narrators (ravi) and scholars (muhaddith, grader, compiler) in one table.
CREATE TABLE IF NOT EXISTS persons (
    id              INTEGER PRIMARY KEY,
    key             TEXT NOT NULL UNIQUE,      -- stable id, e.g. from Tahdhib al-Kamal entry
    name_ar         TEXT,                      -- full name as in the rijal work
    name_latin      TEXT,                      -- transliteration shown in the UI
    kunya           TEXT,
    nisba           TEXT,
    laqab           TEXT,
    birth_year_ah   INTEGER,
    death_year_ah   INTEGER,
    death_year_note TEXT,                      -- "c.", "after", disputed dates as given
    generation      TEXT,                      -- sahabi, tabii, tabi al-tabiin, ...
    tabaqa          INTEGER,                   -- Ibn Hajar's tabaqa 1-12 in Taqrib
    tradition       TEXT CHECK (tradition IN ('sunni', 'shia', 'other')),
    source_id       INTEGER REFERENCES sources(id) ON DELETE SET NULL
);

-- Every way a person is named; the base of narrator identification.
CREATE TABLE IF NOT EXISTS person_names (
    id        INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    kind      TEXT NOT NULL,                   -- full, ism, kunya, nisba, laqab, variant, as_in_chain
    language  TEXT NOT NULL DEFAULT 'ar',
    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_person_names_name ON person_names(name);

CREATE TABLE IF NOT EXISTS person_roles (
    person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    role      TEXT NOT NULL,                   -- narrator, scholar, compiler, grader, rijal_critic
    PRIMARY KEY (person_id, role)
);

-- Teacher -> student, as recorded by a source (e.g. Tahdhib al-Kamal lists).
CREATE TABLE IF NOT EXISTS person_links (
    id         INTEGER PRIMARY KEY,
    teacher_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    source_id  INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    note       TEXT,
    UNIQUE (teacher_id, student_id, source_id)
);

-- A critic's verdict on a person (jarh wa ta'dil), exactly as written.
CREATE TABLE IF NOT EXISTS verdicts (
    id          INTEGER PRIMARY KEY,
    person_id   INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    critic_id   INTEGER REFERENCES persons(id) ON DELETE SET NULL,
    critic_name TEXT NOT NULL,
    work        TEXT,                          -- e.g. Taqrib al-Tahdhib
    phrase      TEXT NOT NULL,                 -- the lafz: thiqa, saduq, da'if ...
    rank_scheme TEXT,                          -- e.g. ibn-hajar-taqrib
    rank        INTEGER,                       -- position in that scheme, if the source gives one
    tradition   TEXT CHECK (tradition IN ('sunni', 'shia', 'other')),
    source_id   INTEGER REFERENCES sources(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_verdicts_person ON verdicts(person_id);

-- -------------------------------------------------------------- collections
CREATE TABLE IF NOT EXISTS collections (
    id          INTEGER PRIMARY KEY,
    key         TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    compiler_id INTEGER REFERENCES persons(id) ON DELETE SET NULL,
    tradition   TEXT NOT NULL DEFAULT 'sunni' CHECK (tradition IN ('sunni', 'shia', 'other'))
);

CREATE TABLE IF NOT EXISTS sections (
    id            INTEGER PRIMARY KEY,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    number        INTEGER NOT NULL,
    first_number  REAL,
    last_number   REAL,
    UNIQUE (collection_id, number)
);

-- ------------------------------------------------------------------ hadiths
-- One row per report. number is TEXT because sources use sub-numbers ("402.2").
CREATE TABLE IF NOT EXISTS hadiths (
    id             INTEGER PRIMARY KEY,
    collection_id  INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    number         TEXT NOT NULL,
    number_sort    REAL,
    section_number INTEGER,
    UNIQUE (collection_id, number)
);
CREATE INDEX IF NOT EXISTS ix_hadiths_sort ON hadiths(collection_id, number_sort);

-- Other numbering schemes of the same hadith (Arabic numbering, in-book reference, ...).
CREATE TABLE IF NOT EXISTS hadith_refs (
    hadith_id INTEGER NOT NULL REFERENCES hadiths(id) ON DELETE CASCADE,
    scheme    TEXT NOT NULL,
    value     TEXT NOT NULL,
    PRIMARY KEY (hadith_id, scheme)
);

-- ------------------------------------------------------------ editions/texts
CREATE TABLE IF NOT EXISTS editions (
    id            INTEGER PRIMARY KEY,
    source_id     INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    key           TEXT NOT NULL,
    language      TEXT,
    direction     TEXT,
    author        TEXT,
    comments      TEXT,
    location      TEXT NOT NULL,
    text_count    INTEGER NOT NULL DEFAULT 0,
    imported_at   TEXT NOT NULL,
    UNIQUE (source_id, key)
);

CREATE TABLE IF NOT EXISTS section_titles (
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    PRIMARY KEY (section_id, edition_id)
);

CREATE TABLE IF NOT EXISTS texts (
    id         INTEGER PRIMARY KEY,
    hadith_id  INTEGER NOT NULL REFERENCES hadiths(id) ON DELETE CASCADE,
    edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
    text       TEXT NOT NULL,
    UNIQUE (hadith_id, edition_id)
);
CREATE INDEX IF NOT EXISTS ix_texts_edition ON texts(edition_id);

-- ------------------------------------------------------------------- isnads
-- A hadith can have several chains. position 1 is the link nearest the compiler.
CREATE TABLE IF NOT EXISTS isnads (
    id        INTEGER PRIMARY KEY,
    hadith_id INTEGER NOT NULL REFERENCES hadiths(id) ON DELETE CASCADE,
    ordinal   INTEGER NOT NULL DEFAULT 1,
    raw_text  TEXT,                            -- the chain as written in the source
    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_isnads_hadith ON isnads(hadith_id);

CREATE TABLE IF NOT EXISTS isnad_links (
    isnad_id         INTEGER NOT NULL REFERENCES isnads(id) ON DELETE CASCADE,
    position         INTEGER NOT NULL,
    raw_name         TEXT NOT NULL,            -- name exactly as in the chain
    person_id        INTEGER REFERENCES persons(id) ON DELETE SET NULL,
    match_confidence REAL,                     -- 0..1, how sure the identification is
    transmission     TEXT,                     -- haddathana, akhbarana, 'an, sami'tu ...
    PRIMARY KEY (isnad_id, position)
);
CREATE INDEX IF NOT EXISTS ix_isnad_links_person ON isnad_links(person_id);

-- ------------------------------------------------------------------- grades
-- A grader's verdict on a hadith (or on one of its chains), exactly as written.
CREATE TABLE IF NOT EXISTS grades (
    id          INTEGER PRIMARY KEY,
    hadith_id   INTEGER NOT NULL REFERENCES hadiths(id) ON DELETE CASCADE,
    isnad_id    INTEGER REFERENCES isnads(id) ON DELETE CASCADE,
    grader_id   INTEGER REFERENCES persons(id) ON DELETE SET NULL,
    grader_name TEXT NOT NULL,
    grade       TEXT NOT NULL,
    source_id   INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    UNIQUE (hadith_id, grader_name, grade, source_id)
);
CREATE INDEX IF NOT EXISTS ix_grades_hadith ON grades(hadith_id);
"""

# Hadith rows are shared by every source that mentions them; once nothing
# refers to a hadith any more, it goes.
CLEANUP_SQL = """
DELETE FROM hadiths WHERE id NOT IN (SELECT hadith_id FROM texts)
                      AND id NOT IN (SELECT hadith_id FROM grades)
                      AND id NOT IN (SELECT hadith_id FROM isnads);
DELETE FROM sections WHERE collection_id NOT IN (SELECT collection_id FROM hadiths)
                       AND id NOT IN (SELECT section_id FROM section_titles);
DELETE FROM collections WHERE id NOT IN (SELECT collection_id FROM hadiths)
                          AND id NOT IN (SELECT collection_id FROM editions);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SchemaReset(Exception):
    """An older pre-release database was set aside; its data must be re-imported."""

    def __init__(self, backup: Path, old_version: int):
        self.backup = backup
        self.old_version = old_version
        super().__init__(
            f"The database used schema {old_version}, which this version replaces. "
            f"It was moved to {backup}. Re-import your sources."
        )


def _set_aside(path: Path, version: int) -> Path:
    backup = path.with_name(f"{path.stem}.v{version}.bak{path.suffix}")
    n = 1
    while backup.exists():
        backup = path.with_name(f"{path.stem}.v{version}.bak{n}{path.suffix}")
        n += 1
    shutil.move(str(path), backup)
    for extra in ("-wal", "-shm"):
        side = path.with_name(path.name + extra)
        if side.exists():
            side.unlink()
    return backup


def connect(path: Path | None = None, *, reset_old: bool = False) -> sqlite3.Connection:
    """Open (and create or upgrade) the database.

    Pre-release schemas (below 2) are not migrated: with reset_old=True the old
    file is moved aside and SchemaReset is raised once, so the caller can tell
    the user; the next call opens a fresh database.
    """
    path = Path(path or db_path())
    if path.exists():
        probe = sqlite3.connect(path)
        version = probe.execute("PRAGMA user_version").fetchone()[0]
        probe.close()
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema {version} is newer than this isnady supports ({SCHEMA_VERSION}). Update isnady."
            )
        if 0 < version < SCHEMA_VERSION:
            if not reset_old:
                raise RuntimeError(f"Database schema {version} is outdated; open it with reset_old=True.")
            raise SchemaReset(_set_aside(path, version), version)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    return conn


def cleanup(conn: sqlite3.Connection) -> None:
    conn.executescript(CLEANUP_SQL)
    conn.commit()


# ------------------------------------------------------------ licence tiers
_TIER_A = {"unlicense", "cc0", "cc0-1.0", "public domain", "public-domain", "pd",
           "cc-by", "cc-by-4.0", "cc by", "cc by 4.0", "mit"}
_TIER_B = {"odbl", "odbl-1.0", "cc-by-sa", "cc-by-sa-4.0", "cc by-sa", "cc-by-nc",
           "cc-by-nc-4.0", "cc-by-nc-sa", "cc-by-nc-sa-4.0", "cc by-nc-sa"}


def tier_for_license(license_name: str | None) -> str:
    """Best guess of the tier from a licence name; unknown means C (not redistributable)."""
    if not license_name:
        return "C"
    name = license_name.strip().lower()
    if name in _TIER_A:
        return "A"
    if name in _TIER_B or "-nc" in name or "-sa" in name:
        return "B"
    return "C"
