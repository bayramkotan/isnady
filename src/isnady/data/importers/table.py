"""One importer for hadith published as a TABLE: CSV files, or JSON lists of records.

Most open hadith datasets are a table — one row per hadith, a column for the Arabic, one for a translation,
perhaps a grade, a chapter, a link — and differ only in what the columns are called. Instead of an importer per
dataset, a repository catalog says which column is which (the MAPPING), and this importer reads them all:

    {"type": "csv" | "json",                 default: from the file name
     "records": "hadiths",                   JSON: dotted path to the list of records (default: the root)
     "header": true,                         CSV: the first row names the columns (false: use "#0", "#1" …)
     "number": "Hadith_number",              the hadith's number; "@row" = its place in the file (from 1)
     "section": "Chapter_Number",            optional: the chapter (book) number
     "section_titles": [{"field": "Chapter_Arabic", "language": "Arabic"}, …],
     "texts":  [{"field": "Arabic_Hadith", "language": "Arabic"},
                {"field": "english.text", "language": "English", "lead": "english.narrator"}],
     "grades": [{"field": "majlisiGrading", "grader": "al-Majlisi", "pattern": ":\\s*(.+?)\\s*(?:\\n|$)",
                 "skip": ["لم يخرجه"]}],
     "url": "URL",                           optional: the hadith's page at its source
     "number_pattern": ":(\\w+)$"}           optional: the number is the first group of this pattern in the field

A text spec may carry "name" (e.g. "sharh"): two editions in one language (the hadith and its commentary).

A field is a column name, "#N" (the N-th column) or a dotted path into a JSON record ("english.text").

The LOCATION is one file or several (a book split into chapters or volumes). A part may be
{"location": …, "volume": 2}: the volume becomes part of the number ("2:15"), so volumes that each count from 1
stay apart in one book. The book's key, title and tradition come from the catalog entry (options).
"""

import csv
import io
import json
import re
import sqlite3

from isnady.data.db import now_iso, tier_for_license
from isnady.data.fetch import ResourceError, read_bytes
from isnady.data.importers.base import ImportReport, Importer, ProgressCallback, SourceInfo, register, slugify

RTL = {"Arabic", "Urdu", "Persian"}
csv.field_size_limit(1 << 30)


def _get(record, field: str):
    """A column by name, by position ("#N"), or a dotted path into nested JSON."""
    if not field:
        return None
    if isinstance(record, (list, tuple)):
        if field.startswith("#"):
            i = int(field[1:])
            return record[i] if i < len(record) else None
        return None
    if field in record:
        return record[field]
    value = record
    for part in field.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def _clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).replace("‏", "").replace("‎", "")
    return re.sub(r"[ \t]+", " ", text).strip()


def _number(value) -> tuple[str, float | None]:
    text = _clean(value)
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".")[0]
    try:
        return text, float(text)
    except ValueError:
        m = re.match(r"(\d+(?:\.\d+)?)", text)
        return text, (float(m.group(1)) if m else None)


def _records(data: bytes, location: str, mapping: dict) -> list:
    kind = mapping.get("type") or ("json" if location.lower().split("?")[0].endswith(".json") else "csv")
    text = data.decode("utf-8-sig", errors="replace")
    if kind == "json":
        try:
            root = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ResourceError(f"Not valid JSON: {location} ({exc})") from exc
        if mapping.get("records"):
            root = _get(root, mapping["records"])
        if isinstance(root, dict):                      # {"1": {...}, "2": {...}}
            root = list(root.values())
        if not isinstance(root, list):
            raise ResourceError(f"{location}: no list of hadith found (records: {mapping.get('records')!r})")
        return root
    rows = list(csv.reader(io.StringIO(text)))
    rows = rows[int(mapping.get("skip_rows", 0)):]
    if mapping.get("header", True):
        if not rows:
            return []
        head = [h.strip() for h in rows[0]]
        return [dict(zip(head, r)) for r in rows[1:] if any(c.strip() for c in r)]
    return [r for r in rows if any(c.strip() for c in r)]


def _grade(value: str, rule: dict) -> str:
    text = _clean(value)
    if not text:
        return ""
    if rule.get("pattern"):
        m = re.search(rule["pattern"], text, re.S)
        text = (m.group(1) if m else "").strip()
    if any(s in text for s in rule.get("skip", [])):
        return ""
    return text


class TableImporter(Importer):
    format_id = "table"
    title = "Table — CSV or JSON records (column mapping)"
    description = "Any CSV file or JSON list of hadith; the catalog entry says which column is which"

    def run(self, conn: sqlite3.Connection, source: SourceInfo, options: dict,
            progress: ProgressCallback | None = None) -> ImportReport:
        say = progress or (lambda _m: None)
        mapping = options.get("mapping") or {}
        if not mapping.get("texts"):
            raise ResourceError("This source has no column mapping (which column holds the text).")
        book = options.get("book") or slugify(source.name or source.location)
        title = options.get("title") or source.name or book
        tradition = options.get("tradition") or "sunni"
        parts = options.get("parts") or [source.location]
        source_key = options.get("source_key") or slugify(source.name or source.location)
        report = ImportReport(source_key=source_key)

        tier = source.tier or tier_for_license(source.license)
        conn.execute(
            """INSERT INTO sources (key, name, format, location, license, tier, origin, auth_type, imported_at)
               VALUES (?, ?, 'table', ?, ?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET name = excluded.name, location = excluded.location,
                   license = COALESCE(excluded.license, sources.license), tier = excluded.tier,
                   origin = excluded.origin, auth_type = excluded.auth_type""",
            (source_key, source.name or source_key, source.location, source.license, tier, source.origin,
             source.auth.describe(), now_iso()))
        source_id = conn.execute("SELECT id FROM sources WHERE key = ?", (source_key,)).fetchone()[0]

        rows: list[tuple[dict, int | None, int]] = []
        for n, part in enumerate(parts, 1):
            where = part["location"] if isinstance(part, dict) else part
            volume = part.get("volume") if isinstance(part, dict) else None
            say(f"Reading {where}" + (f" ({n} of {len(parts)})" if len(parts) > 1 else ""))
            recs = _records(read_bytes(where, source.auth), where, mapping)
            rows += [(r, volume, i) for i, r in enumerate(recs, 1)]
        if not rows:
            raise ResourceError(f"No hadith found in {source.location}.")

        with conn:
            conn.execute("""INSERT INTO collections (key, name, tradition) VALUES (?, ?, ?)
                            ON CONFLICT(key) DO UPDATE SET tradition = excluded.tradition""", (book, title, tradition))
            collection_id = conn.execute("SELECT id FROM collections WHERE key = ?", (book,)).fetchone()[0]
            editions: dict[str, int] = {}
            for spec in mapping["texts"]:
                lang = spec.get("language", "Arabic")
                name = spec.get("name") or lang
                key = f"{source_key}:{book}:{name.lower()}"
                conn.execute("DELETE FROM editions WHERE source_id = ? AND key = ?", (source_id, key))
                editions[name] = conn.execute(
                    """INSERT INTO editions (source_id, collection_id, key, language, direction, author, comments,
                                             location, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (source_id, collection_id, key, lang, "rtl" if lang in RTL else "ltr", spec.get("author"),
                     spec.get("comments"), source.location, now_iso())).lastrowid
            counts = dict.fromkeys(editions, 0)
            new_hadiths = new_grades = 0
            seen: dict[str, int] = {}
            for record, volume, row_no in rows:
                field = mapping.get("number", "@row")
                raw = row_no if field == "@row" else _get(record, field)
                if mapping.get("number_pattern") and raw is not None:
                    m = re.search(mapping["number_pattern"], _clean(raw))
                    raw = m.group(1) if m else None
                number, sort = _number(raw if raw is not None else row_no)
                if not number:
                    continue
                if volume is not None:
                    number, sort = f"{volume}:{number}", (volume * 100000 + (sort or 0))
                if number in seen:                     # a repeated number: keep both, the second as "n.2"
                    seen[number] += 1
                    number = f"{number}.{seen[number]}"
                else:
                    seen[number] = 1
                section = None
                if mapping.get("section"):
                    s, _sort = _number(_get(record, mapping["section"]))
                    section = int(_sort) if _sort is not None else None
                    if volume is not None and section is not None:
                        section = volume * 1000 + section
                cur = conn.execute("""INSERT INTO hadiths (collection_id, number, number_sort, section_number)
                                      VALUES (?, ?, ?, ?) ON CONFLICT(collection_id, number) DO NOTHING""",
                                   (collection_id, number, sort, section))
                new_hadiths += cur.rowcount
                hid = conn.execute("SELECT id FROM hadiths WHERE collection_id = ? AND number = ?",
                                   (collection_id, number)).fetchone()[0]
                if section is not None:
                    conn.execute("""INSERT INTO sections (collection_id, number) VALUES (?, ?)
                                    ON CONFLICT(collection_id, number) DO NOTHING""", (collection_id, section))
                    for spec in mapping.get("section_titles", []):
                        t = _clean(_get(record, spec["field"]))
                        target = next((s.get("name") or s.get("language", "Arabic") for s in mapping["texts"]
                                       if s.get("language", "Arabic") == spec.get("language", "Arabic")), None)
                        if t and target in editions:
                            sid = conn.execute("SELECT id FROM sections WHERE collection_id = ? AND number = ?",
                                               (collection_id, section)).fetchone()[0]
                            conn.execute("INSERT OR IGNORE INTO section_titles VALUES (?, ?, ?)",
                                         (sid, editions[target], t))
                if mapping.get("url"):
                    url = _clean(_get(record, mapping["url"]))
                    if url:
                        conn.execute("INSERT OR IGNORE INTO hadith_refs VALUES (?, 'url', ?)", (hid, url))
                for spec in mapping["texts"]:
                    text = _clean(_get(record, spec["field"]))
                    lead = _clean(_get(record, spec["lead"])) if spec.get("lead") else ""
                    if lead and not text.startswith(lead):
                        text = f"{lead} {text}".strip()
                    if text:
                        name = spec.get("name") or spec.get("language", "Arabic")
                        conn.execute("INSERT OR REPLACE INTO texts (hadith_id, edition_id, text) VALUES (?, ?, ?)",
                                     (hid, editions[name], text))
                        counts[name] += 1
                for rule in mapping.get("grades", []):
                    g = _grade(_get(record, rule["field"]), rule)
                    if g:
                        cur = conn.execute("""INSERT OR IGNORE INTO grades (hadith_id, grader_name, grade, source_id)
                                              VALUES (?, ?, ?, ?)""", (hid, rule.get("grader", "Unknown"), g, source_id))
                        new_grades += cur.rowcount
            for lang, edition_id in editions.items():
                conn.execute("UPDATE editions SET text_count = ? WHERE id = ?", (counts[lang], edition_id))
                if counts[lang]:
                    report.editions.append(f"{book} ({lang})")
                else:
                    conn.execute("DELETE FROM editions WHERE id = ?", (edition_id,))
            conn.execute("UPDATE sources SET imported_at = ? WHERE id = ?", (now_iso(), source_id))
        report.texts = sum(counts.values())
        report.new_hadiths = new_hadiths
        report.grades = new_grades
        say(f"{title}: {len(seen):,} hadith, " + ", ".join(f"{c:,} {lang}" for lang, c in counts.items() if c)
            + (f", {new_grades:,} grades" if new_grades else ""))
        return report


register(TableImporter())
