"""A written source as a book (SHF1b): isnady-data's sahifa/<road>/<book>.json (isnady-sahifa/1) — the hadith of a
sahifa as [book, number] of the books they stand in. Importing it makes a book of Books whose leaves point at those
hadith in the books imported here (core.sahifa.write_work): nothing is copied, so search and the statistics count
each hadith once. A hadith of a book not imported is counted as missing and said."""

from __future__ import annotations

import json
import sqlite3

from isnady.data.db import now_iso, tier_for_license
from isnady.data.fetch import ResourceError, read_bytes
from isnady.data.importers.base import (
    Importer,
    ImportReport,
    ProgressCallback,
    SourceInfo,
    register,
)


class SahifaImporter(Importer):
    format_id = "isnady-sahifa"
    title = "isnady — a written source (sahifa) as a book"
    description = "The hadith of a sahifa, pointed at where they stand in the books imported"

    def run(self, conn: sqlite3.Connection, source: SourceInfo, options: dict,
            progress: ProgressCallback | None = None) -> ImportReport:
        from isnady.core import sahifa
        from isnady.core.i18n import tr

        say = progress or (lambda _m: None)
        try:
            data = json.loads(read_bytes(source.location, source.auth, timeout=300).decode("utf-8-sig"))
        except ValueError as exc:
            raise ResourceError(f"Not a sahifa file: {source.location}") from exc
        if data.get("schema") != sahifa.SCHEMA or not data.get("id"):
            raise ResourceError(f"Not a sahifa file (isnady-sahifa/1): {source.location}")
        key = data["id"]
        title = (data.get("title") or {}).get("en") or key
        say(tr("Reading {title}", title=title))
        report = ImportReport(source_key=key)
        with conn:
            conn.execute(
                """INSERT INTO sources (key, name, format, location, license, tier, origin, auth_type, imported_at)
                   VALUES (?, ?, 'isnady-sahifa', ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET name = excluded.name, location = excluded.location,
                       license = excluded.license, tier = excluded.tier, origin = excluded.origin,
                       auth_type = excluded.auth_type, imported_at = excluded.imported_at""",
                (key, source.name or title, source.location, source.license,
                 source.tier or tier_for_license(source.license), source.origin, source.auth.describe(), now_iso()))
            source_id = conn.execute("SELECT id FROM sources WHERE key = ?", (key,)).fetchone()[0]
            found, missing = sahifa.write_work(conn, data, source_id)
        report.editions.append(key)
        report.texts = found
        if missing:
            report.warnings.append(f"{missing:,} hadith stand in books not imported here")
        say(f"{found:,} hadith" + (f"; {missing:,} in books not imported here" if missing else ""))
        return report


register(SahifaImporter())
