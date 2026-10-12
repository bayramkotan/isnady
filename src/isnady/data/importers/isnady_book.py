"""isnady's own book format (isnady-book/1), the format of the isnady-data repository.

A book is a folder — sunni/bukhari/, shia/kafi/ — with

  book.json   {"schema": "isnady-book/1", "key": "bukhari", "title": "Sahih al-Bukhari", "title_ar": "صحيح البخاري",
               "tradition": "sunni", "compiler": "...", "license": "...", "credit": "...",
               "languages": {"ara": {"file": "ara.json", "name": "Arabic", "direction": "rtl", "author": "..."}, ...},
               "hadiths": [{"n": "1", "sort": 1.0, "s": 1, "refs": {"arabic": "1"},
                            "grades": [["Al-Albani", "Sahih"], ...]}, ...]}
  ara.json    {"language": "ara", "sections": {"1": "Revelation", ...}, "texts": {"1": "...", ...}}
  eng.json …

book.json holds what does not depend on the language (numbers, chapters, references, grades); each language file
holds the texts and chapter titles of one language, so only the languages chosen are downloaded.
"""

import json
import sqlite3

from isnady.data.db import now_iso, tier_for_license
from isnady.data.fetch import ResourceError, read_bytes, resolve
from isnady.data.importers.base import ImportReport, Importer, ProgressCallback, SourceInfo, register

SCHEMA = "isnady-book/1"
# Books imported before isnady-data existed (v0.1.7 and earlier read the same texts straight from their publisher):
# importing the book from isnady-data replaces them, so a hadith is not shown twice in one language.
LEGACY_SOURCES = ("fawazahmed0-hadith-api",)


def _json(location: str, auth) -> dict:
    try:
        return json.loads(read_bytes(location, auth).decode("utf-8-sig"))
    except ValueError as exc:
        raise ResourceError(f"Not valid JSON: {location} ({exc})") from exc


class IsnadyBookImporter(Importer):
    format_id = "isnady"
    title = "isnady book (isnady-data)"
    description = "A book of the isnady-data repository: book.json with one file per language"

    def run(self, conn: sqlite3.Connection, source: SourceInfo, options: dict,
            progress: ProgressCallback | None = None) -> ImportReport:
        say = progress or (lambda _m: None)
        say(f"Reading {source.location}")
        book = _json(source.location, source.auth)
        if book.get("schema") != SCHEMA:
            raise ResourceError(f"{source.location} is not an isnady book (schema {SCHEMA}).")
        key = book["key"]
        offered = book.get("languages", {})
        wanted = [c for c in (options.get("languages") or []) if c in offered] or list(offered)[:1]
        source_key = f"isnady-{key}"
        report = ImportReport(source_key=source_key)
        tier = source.tier or tier_for_license(book.get("license") or source.license)
        conn.execute(
            """INSERT INTO sources (key, name, format, location, license, tier, origin, auth_type, imported_at)
               VALUES (?, ?, 'isnady', ?, ?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET name = excluded.name, location = excluded.location,
                   license = excluded.license, tier = excluded.tier, origin = excluded.origin""",
            (source_key, f"isnady-data: {book['title']}", source.location, book.get("license"), tier, source.origin,
             source.auth.describe(), now_iso()))
        source_id = conn.execute("SELECT id FROM sources WHERE key = ?", (source_key,)).fetchone()[0]

        texts_by_lang = {}
        for code in wanted:
            where = resolve(source.location, offered[code]["file"])
            say(f"Downloading {book['title']} ({offered[code].get('name', code)})")
            texts_by_lang[code] = _json(where, source.auth)

        with conn:
            conn.execute("""INSERT INTO collections (key, name, tradition) VALUES (?, ?, ?)
                            ON CONFLICT(key) DO UPDATE SET name = excluded.name, tradition = excluded.tradition""",
                         (key, book["title"], book.get("tradition", "sunni")))
            cid = conn.execute("SELECT id FROM collections WHERE key = ?", (key,)).fetchone()[0]
            for legacy in LEGACY_SOURCES:
                old = conn.execute("SELECT id FROM sources WHERE key = ?", (legacy,)).fetchone()
                if old is None:
                    continue
                gone = conn.execute("DELETE FROM editions WHERE source_id = ? AND collection_id = ?",
                                    (old[0], cid)).rowcount
                conn.execute("DELETE FROM grades WHERE source_id = ? AND hadith_id IN "
                             "(SELECT id FROM hadiths WHERE collection_id = ?)", (old[0], cid))
                if gone:
                    say(f"{book['title']}: the copy imported before isnady-data is replaced")
                if not conn.execute("SELECT 1 FROM editions WHERE source_id = ?", (old[0],)).fetchone():
                    conn.execute("DELETE FROM sources WHERE id = ?", (old[0],))
            ids: dict[str, int] = {}
            new_hadiths = new_grades = 0
            for h in book.get("hadiths", []):
                cur = conn.execute("""INSERT INTO hadiths (collection_id, number, number_sort, section_number)
                                      VALUES (?, ?, ?, ?) ON CONFLICT(collection_id, number) DO NOTHING""",
                                   (cid, h["n"], h.get("sort"), h.get("s")))
                new_hadiths += cur.rowcount
                hid = conn.execute("SELECT id FROM hadiths WHERE collection_id = ? AND number = ?",
                                   (cid, h["n"])).fetchone()[0]
                ids[h["n"]] = hid
                for scheme, value in (h.get("refs") or {}).items():
                    conn.execute("INSERT OR IGNORE INTO hadith_refs VALUES (?, ?, ?)", (hid, scheme, str(value)))
                for grader, grade in h.get("grades") or []:
                    cur = conn.execute("""INSERT OR IGNORE INTO grades (hadith_id, grader_name, grade, source_id)
                                          VALUES (?, ?, ?, ?)""", (hid, grader, grade, source_id))
                    new_grades += cur.rowcount
            sections = sorted({h.get("s") for h in book.get("hadiths", []) if h.get("s") is not None})
            for s in sections:
                conn.execute("INSERT INTO sections (collection_id, number) VALUES (?, ?) "
                             "ON CONFLICT(collection_id, number) DO NOTHING", (cid, s))
            for code, data in texts_by_lang.items():
                meta = offered[code]
                ekey = f"isnady:{key}:{code}"
                conn.execute("DELETE FROM editions WHERE source_id = ? AND key = ?", (source_id, ekey))
                eid = conn.execute(
                    """INSERT INTO editions (source_id, collection_id, key, language, direction, author, comments,
                                             location, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (source_id, cid, ekey, meta.get("name", code), meta.get("direction", "ltr"), meta.get("author"),
                     book.get("credit"), resolve(source.location, meta["file"]), now_iso())).lastrowid
                for number, title in (data.get("sections") or {}).items():
                    try:
                        number = int(number)
                    except (TypeError, ValueError):
                        continue             # a section without a number in the source ("None" in al-Shama'il)
                    row = conn.execute("SELECT id FROM sections WHERE collection_id = ? AND number = ?",
                                       (cid, number)).fetchone()
                    if row and title:
                        conn.execute("INSERT OR REPLACE INTO section_titles VALUES (?, ?, ?)", (row[0], eid, title))
                count = 0
                for number, text in (data.get("texts") or {}).items():
                    hid = ids.get(number)
                    if hid is not None and text:
                        conn.execute("INSERT OR REPLACE INTO texts (hadith_id, edition_id, text) VALUES (?, ?, ?)",
                                     (hid, eid, text))
                        count += 1
                conn.execute("UPDATE editions SET text_count = ? WHERE id = ?", (count, eid))
                report.editions.append(f"{key} ({meta.get('name', code)})")
                report.texts += count
            conn.execute("UPDATE sources SET imported_at = ? WHERE id = ?", (now_iso(), source_id))
        report.new_hadiths, report.grades = new_hadiths, new_grades
        say(f"{book['title']}: {len(ids):,} hadith, {report.texts:,} texts, {new_grades:,} grades")
        return report


register(IsnadyBookImporter())
