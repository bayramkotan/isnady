"""JSON importer for the fawazahmed0/hadith-api edition format.

Repository: https://github.com/fawazahmed0/hadith-api (Unlicense)

Accepts either
  * one edition file:   {"metadata": {...}, "hadiths": [...]}
  * the editions index: {"bukhari": {"name": ..., "collection": [ {edition}, ... ]}, ...}
    from which the chosen editions are downloaded through their own links.

Each location may be a local file or a URL, with or without authentication.
"""

import json
import re
import sqlite3
from pathlib import PurePosixPath
from urllib.parse import urlparse

from isnady.data.db import now_iso
from isnady.data.fetch import ResourceError, read_bytes, resolve
from isnady.data.importers.base import (
    ImportReport,
    Importer,
    ProgressCallback,
    SourceInfo,
    register,
    slugify,
)

# Language prefixes used in this repository's edition names.
LANGUAGE_CODES = {
    "ara": "Arabic", "ben": "Bengali", "eng": "English", "fra": "French",
    "ind": "Indonesian", "rus": "Russian", "tam": "Tamil", "tur": "Turkish", "urd": "Urdu",
}
RTL_LANGUAGES = {"Arabic", "Urdu"}


def _load_json(data: bytes, location: str):
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResourceError(f"Not valid UTF-8 JSON: {location} ({exc})") from exc


def is_edition(obj) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get("metadata"), dict) and isinstance(obj.get("hadiths"), list)


def is_index(obj) -> bool:
    return (
        isinstance(obj, dict)
        and bool(obj)
        and all(isinstance(v, dict) and isinstance(v.get("collection"), list) for v in obj.values())
    )


def _edition_key_from_location(location: str) -> str:
    name = PurePosixPath(urlparse(location).path).name if "://" in location else PurePosixPath(location.replace("\\", "/")).name
    for suffix in (".min.json", ".json"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _format_number(value) -> tuple[str, float | None]:
    if isinstance(value, bool) or value is None:
        return ("", None)
    if isinstance(value, int):
        return (str(value), float(value))
    if isinstance(value, float):
        text = str(int(value)) if value.is_integer() else repr(value)
        return (text, value)
    text = str(value).strip()
    try:
        return (text, float(text))
    except ValueError:
        return (text, None)


def _matches(value: str, wanted: set[str]) -> bool:
    return not wanted or value.lower() in wanted


class FawazahmedJsonImporter(Importer):
    format_id = "fawazahmed0"
    title = "JSON — fawazahmed0/hadith-api"
    description = "Edition files or the editions index of github.com/fawazahmed0/hadith-api"

    # ---------------------------------------------------------------- public
    def run(self, conn: sqlite3.Connection, source: SourceInfo, options: dict,
            progress: ProgressCallback | None = None) -> ImportReport:
        say = progress or (lambda _msg: None)
        say(f"Reading {source.location}")
        root = _load_json(read_bytes(source.location, source.auth), source.location)

        source_name = source.name or _edition_key_from_location(source.location)
        source_key = slugify(source.name or source.location)
        report = ImportReport(source_key=source_key)
        source_id = self._upsert_source(conn, source_key, source_name, source)

        if is_edition(root):
            key = options.get("edition_key") or _edition_key_from_location(source.location)
            languages = options.get("languages") or []
            books = options.get("books") or []
            language = LANGUAGE_CODES.get(languages[0].lower(), languages[0].title()) if languages else None
            entry = {"name": key, "book": books[0] if books else None, "language": language}
            self._import_edition(conn, source_id, entry, root, source.location, report, say)
        elif is_index(root):
            entries = self._select_from_index(root, options)
            if not entries:
                raise ResourceError(
                    "No editions matched. Choose with --edition, --book or --language, "
                    "or pass --all to import every edition in the index."
                )
            say(f"{len(entries)} edition(s) selected from the index")
            for entry in entries:
                link = entry.get("linkmin") or entry.get("link")
                if not link:
                    report.warnings.append(f"{entry.get('name')}: no link in the index, skipped")
                    continue
                url = resolve(source.location, link)
                say(f"Downloading {entry.get('name')}")
                data = _load_json(read_bytes(url, source.auth), url)
                if not is_edition(data):
                    report.warnings.append(f"{entry.get('name')}: not an edition file, skipped")
                    continue
                self._import_edition(conn, source_id, entry, data, url, report, say)
        else:
            raise ResourceError(
                f"{source.location} is JSON but not in the fawazahmed0 format "
                "(expected 'metadata' + 'hadiths', or an editions index)."
            )

        conn.execute("UPDATE sources SET imported_at = ? WHERE id = ?", (now_iso(), source_id))
        conn.commit()
        return report

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _upsert_source(conn, key, name, source: SourceInfo) -> int:
        conn.execute(
            """INSERT INTO sources (key, name, format, location, license, origin, auth_type, imported_at)
               VALUES (?, ?, 'fawazahmed0', ?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   name = excluded.name, location = excluded.location,
                   license = COALESCE(excluded.license, sources.license),
                   origin = excluded.origin, auth_type = excluded.auth_type""",
            (key, name, source.location, source.license, source.origin, source.auth.describe(), now_iso()),
        )
        return conn.execute("SELECT id FROM sources WHERE key = ?", (key,)).fetchone()[0]

    @staticmethod
    def _select_from_index(root: dict, options: dict) -> list[dict]:
        editions = {e.lower() for e in options.get("editions") or []}
        books = {b.lower() for b in options.get("books") or []}
        languages = set()
        for lang in options.get("languages") or []:
            lang = lang.lower()
            languages.add(LANGUAGE_CODES.get(lang, lang).lower())
        if not (editions or books or languages or options.get("all")):
            return []
        chosen = []
        for book_key, book in root.items():
            for entry in book["collection"]:
                if not isinstance(entry, dict):
                    continue
                if editions and entry.get("name", "").lower() not in editions:
                    continue
                if not _matches(entry.get("book") or book_key, books):
                    continue
                if not _matches(entry.get("language") or "", languages):
                    continue
                chosen.append({**entry, "book": entry.get("book") or book_key, "book_name": book.get("name")})
        return chosen

    def _import_edition(self, conn, source_id, entry, data, location, report: ImportReport, say):
        meta = data["metadata"]
        key = entry.get("name") or _edition_key_from_location(location)
        prefix, _, rest = key.partition("-")
        language = entry.get("language") or LANGUAGE_CODES.get(prefix) or "Unknown"
        book_key = entry.get("book") or re.sub(r"\d+$", "", rest) or key
        book_name = entry.get("book_name") or meta.get("name") or book_key
        direction = entry.get("direction") or ("rtl" if language in RTL_LANGUAGES else "ltr")

        with conn:  # one transaction per edition
            conn.execute(
                "INSERT INTO collections (key, name) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
                (book_key, book_name),
            )
            collection_id = conn.execute("SELECT id FROM collections WHERE key = ?", (book_key,)).fetchone()[0]

            # Re-importing an edition replaces it completely (cascades to sections, hadiths, grades).
            conn.execute("DELETE FROM editions WHERE source_id = ? AND key = ?", (source_id, key))
            edition_id = conn.execute(
                """INSERT INTO editions (source_id, collection_id, key, language, direction, author,
                                         comments, location, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_id, collection_id, key, language, direction, entry.get("author"),
                 entry.get("comments") or None, location, now_iso()),
            ).lastrowid

            titles = meta.get("sections") or {}
            details = meta.get("section_details") or {}
            for number, title in titles.items():
                try:
                    num = int(number)
                except (TypeError, ValueError):
                    continue
                d = details.get(number) or {}
                conn.execute(
                    "INSERT INTO sections (edition_id, number, title, first_number, last_number) VALUES (?, ?, ?, ?, ?)",
                    (edition_id, num, title or None, d.get("hadithnumber_first"), d.get("hadithnumber_last")),
                )

            count = empty = grade_count = 0
            for item in data["hadiths"]:
                if not isinstance(item, dict):
                    continue
                text = (item.get("text") or "").strip()
                if not text:
                    empty += 1
                    continue
                number, number_sort = _format_number(item.get("hadithnumber"))
                arabic_number, _ = _format_number(item.get("arabicnumber"))
                ref = item.get("reference") or {}
                hadith_id = conn.execute(
                    """INSERT INTO hadiths (edition_id, number, number_sort, arabic_number, ref_book, ref_hadith, text)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (edition_id, number, number_sort, arabic_number or None,
                     ref.get("book"), ref.get("hadith"), text),
                ).lastrowid
                count += 1
                for grade in item.get("grades") or []:
                    if isinstance(grade, dict) and grade.get("grade"):
                        conn.execute(
                            "INSERT INTO grades (hadith_id, grader, grade) VALUES (?, ?, ?)",
                            (hadith_id, (grade.get("name") or "Unknown").strip(), grade["grade"].strip()),
                        )
                        grade_count += 1

            conn.execute("UPDATE editions SET hadith_count = ? WHERE id = ?", (count, edition_id))

        report.editions.append(key)
        report.hadiths += count
        report.grades += grade_count
        if empty:
            report.warnings.append(f"{key}: {empty} entr{'y' if empty == 1 else 'ies'} with empty text skipped")
        say(f"{key}: {count} hadith, {grade_count} grades ({language})")


register(FawazahmedJsonImporter())
