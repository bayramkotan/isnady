"""A work of the OpenITI corpus as a readable book (LIB1): the sira, the tabaqat — anything that is neither a hadith
collection nor a rijal work isnady reads into narrators.

The file is read as the corpus marks it (mARkdown): "### |", "### ||" … are its headings, one level per bar;
"### $ 126 - heading" an entry (a life, numbered as the edition numbers it); "# " a new paragraph, "~~" a line the
corpus wrapped. The book becomes a work of core.works: a heading under which more headings or entries follow is a
chapter; a heading followed only by its text is a section of its chapter, read as it stands; an entry is an entry.
Nothing is summarised or reworded: the text is the author's, its page marks taken out.

When the work is one whose entries the written lives quote (al-Dhahabi's Siyar and Tadhkira, core.source_entries),
its entries are also kept there, so the "In the source" of a life needs no second download.
"""

from __future__ import annotations

import re
import sqlite3

from isnady.data.db import now_iso, tier_for_license
from isnady.data.fetch import ResourceError, read_bytes
from isnady.data.importers.base import ImportReport, Importer, ProgressCallback, SourceInfo, register

_LINE = re.compile(r"^### (\|+|\$+) ?(.*)$")
_NUMBER = re.compile(r"^(\d+)\s*[-–ـ:.]?\s*(.*)$")
_MARKUP = re.compile(r"PageV\d+P\d+|\bms\d+\b|^~~|^#+ ?\|*|^# ", re.M)
LONG = 6000                    # a section longer than this is read in parts, at its paragraphs


def _clean(chunk: str) -> str:
    chunk = re.sub(r"\n~~", " ", chunk)                     # a line the corpus wrapped: the same paragraph
    chunk = re.sub(r"\n# ", "\n", chunk)                   # a new paragraph: a new line
    text = _MARKUP.sub("", chunk)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"\n", "\n\n", text)).strip()


def _heading(text: str) -> str:
    return re.sub(r"\s+", " ", _MARKUP.sub("", text)).strip(" *:.") or ""


def read_items(text: str) -> list[dict]:
    """The work as a flat list: {"type": "head", "level", "title", "text"} and {"type": "entry", "label", "title",
    "text"}, in the order of the book; the text before the first heading (the editor's front matter) as a head of
    level 1 called "Introduction"."""
    body = text.split("#META#Header#End#", 1)[-1]
    items: list[dict] = []
    current: dict | None = None
    buf: list[str] = []

    def close():
        if current is not None:
            current["text"] = _clean("\n".join(buf))
        elif "".join(buf).strip():
            front = _clean("\n".join(buf))
            if front:
                items.insert(0, {"type": "head", "level": 1, "title": "Introduction", "text": front})

    for line in body.split("\n"):
        m = _LINE.match(line)
        if not m:
            buf.append(line)
            continue
        close()
        buf = []
        marks, rest = m.group(1), m.group(2)
        if marks[0] == "|":
            current = {"type": "head", "level": len(marks), "title": _heading(rest) or "—", "text": ""}
        else:
            n = _NUMBER.match(rest.strip())
            label, title = (n.group(1), n.group(2)) if n else (None, rest)
            current = {"type": "entry", "label": label, "title": _heading(title), "text": ""}
        items.append(current)
    close()
    return items


def _parts(text: str) -> list[str]:
    """A long section in parts of about LONG characters, cut between paragraphs."""
    if len(text) <= LONG:
        return [text]
    out, part = [], ""
    for para in text.split("\n\n"):
        if part and len(part) + len(para) > LONG:
            out.append(part)
            part = para
        else:
            part = f"{part}\n\n{para}" if part else para
    return out + ([part] if part else [])


def write_work(conn: sqlite3.Connection, items: list[dict], source_id: int, key: str, kind: str, title: str,
               title_ar: str | None, stamp: str) -> tuple[int, int, int]:
    """The work's tree in core.works (replacing the earlier one): (work id, chapters, leaves)."""
    conn.execute("DELETE FROM works WHERE key = ?", (key,))
    wid = conn.execute("INSERT INTO works (key, kind, title, title_ar, source_id, stamp) VALUES (?, ?, ?, ?, ?, ?)",
                       (key, kind, title, title_ar, source_id, stamp)).lastrowid
    ordinals: dict = {}
    counts = [0, 0]

    def add(parent, node_kind, label=None, node_title=None, text=None):
        ordinals[parent] = ordinals.get(parent, 0) + 1
        counts[0 if node_kind in ("kitab", "bab", "section") else 1] += 1
        return conn.execute("INSERT INTO work_nodes (work_id, parent_id, ordinal, kind, label, title, text) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (wid, parent, ordinals[parent], node_kind, label, node_title, text)).lastrowid

    def paragraphs(parent, node_title, text):
        for i, part in enumerate(_parts(text)):
            add(parent, "paragraph", None, node_title if i == 0 else None, part)

    stack: list[tuple[int, int]] = []           # (level, node id) of the chapters open
    for i, item in enumerate(items):
        if item["type"] == "entry":
            if not stack:
                stack.append((1, add(None, "kitab", None, "Entries")))
            add(stack[-1][1], "entry", item["label"], item["title"], item["text"])
            continue
        level = item["level"]
        nxt = items[i + 1] if i + 1 < len(items) else None
        chapter = level == 1 or not stack or (nxt is not None and (nxt["type"] == "entry" or nxt["level"] > level))
        while stack and stack[-1][0] >= level:
            stack.pop()
        if chapter:
            node = add(stack[-1][1] if stack else None, "kitab" if not stack else "bab", None, item["title"])
            stack.append((level, node))
            if item["text"]:
                paragraphs(node, None, item["text"])
        else:
            paragraphs(stack[-1][1], item["title"], item["text"])
    return wid, counts[0], counts[1]


class OpenITIWorkImporter(Importer):
    format_id = "openiti-work"
    title = "OpenITI mARkdown — a book to read (sira, tabaqat …)"
    description = "Any work of the OpenITI corpus as a readable book in Books: its headings, entries and text"

    def run(self, conn: sqlite3.Connection, source: SourceInfo, options: dict,
            progress: ProgressCallback | None = None) -> ImportReport:
        from isnady.core.i18n import tr

        say = progress or (lambda _m: None)
        key = options.get("book") or options.get("key")
        if not key:
            raise ValueError("A work needs its key (the catalog's book).")
        say(tr("Reading {title}", title=options.get("title") or key))
        try:
            text = read_bytes(source.location, source.auth, timeout=900).decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ResourceError(f"Not UTF-8 text: {source.location}") from exc
        if "#META#Header#End" not in text and "######OpenITI#" not in text:
            raise ResourceError(f"Not an OpenITI text: {source.location}")
        items = read_items(text)
        if len(items) < 10:
            raise ResourceError(f"Only {len(items)} headings found in {source.location}")
        name = source.name or options.get("title") or key
        tier = source.tier or tier_for_license(source.license)
        report = ImportReport(source_key=key)
        with conn:
            conn.execute(
                """INSERT INTO sources (key, name, format, location, license, tier, origin, auth_type, imported_at)
                   VALUES (?, ?, 'openiti-work', ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET name = excluded.name, location = excluded.location,
                       license = excluded.license, tier = excluded.tier, origin = excluded.origin,
                       auth_type = excluded.auth_type, imported_at = excluded.imported_at""",
                (key, name, source.location, source.license, tier, source.origin, source.auth.describe(), now_iso()))
            source_id = conn.execute("SELECT id FROM sources WHERE key = ?", (key,)).fetchone()[0]
            _wid, chapters, leaves = write_work(conn, items, source_id, key, options.get("kind") or "other",
                                                options.get("title") or name, options.get("title_ar"),
                                                f"{key}|{len(items)}|{len(text)}")
        entries = options.get("entries")
        if entries:
            from isnady.core import source_entries

            if entries in source_entries.WORKS:
                say(tr("Keeping its entries for the written lives"))
                source_entries.store(entries, text, source.location)
        report.editions.append(key)
        report.texts = leaves
        report.warnings.append(f"{chapters:,} chapters, {leaves:,} entries and sections")
        say(report.warnings[-1])
        return report


register(OpenITIWorkImporter())
