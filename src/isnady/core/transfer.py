"""Export and import, of everything, each in the formats that fit it (EX1). Qt-free: File → Export… / Import… and
`iy export` / `iy import-data` come here.

Bayram (2026-10-24): "herseyin ayri ayri farkli formatlarda export/import edilebilirligini istiyorum. Ister
bookmarklar ister profiller, ister kitaplar! Bunun cok gelismis bir sekilde yap" — and before, "Lokalde belki json
belki pdf tutmak isteyecegim".

  what        export as                                                     import from
  hadith      json jsonl csv tsv xlsx md html txt epub docx pdf sqlite       —
  book        isnady-book (importable) json jsonl csv tsv xlsx md html txt   isnady-book (zip / folder / book.json),
              epub docx pdf sqlite                                           json, jsonl, csv, tsv of an export
  search      as hadith                                                      —
  bookmarks   json jsonl csv tsv xlsx md html txt pdf                        json (isnady's own or an export),
                                                                             jsonl, csv, tsv
  narrators   json jsonl csv tsv xlsx md html txt pdf sqlite                 —
  network     graphml gexf csv json (who taught whom, how often)             —
  settings    json csv tsv md                                                json, csv, tsv
  profile     isnady-profile (zip) json                                      isnady-profile, json
  backup      backup (zip: settings, place, bookmarks, the list of books)    backup

A hadith export keeps, for each hadith, its book and number, its chapter, its texts in the languages chosen, its
grades and its chains — the Arabic as written and the chain said in Turkish and English. An isnady-book is the
format of isnady-data itself, so a book exported so is imported again as a book (a source of your own).
"""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import time
import zipfile
from pathlib import Path
from typing import Callable

from isnady import __version__
from isnady.core import formats as F

Progress = Callable[[str], None]

KINDS: dict[str, dict] = {
    "hadith": {"label": "Hadith", "export": ["json", "jsonl", "csv", "tsv", "xlsx", "md", "html", "txt", "epub",
                                             "docx", "pdf", "sqlite"], "import": []},
    "book": {"label": "Book or chapter", "export": ["isnady-book", "json", "jsonl", "csv", "tsv", "xlsx", "md",
                                                    "html", "txt", "epub", "docx", "pdf", "sqlite"],
             "import": ["isnady-book", "json", "jsonl", "csv", "tsv"]},
    "search": {"label": "Search results", "export": ["json", "jsonl", "csv", "tsv", "xlsx", "md", "html", "txt",
                                                     "epub", "docx", "pdf", "sqlite"], "import": []},
    "bookmarks": {"label": "Bookmarks", "export": ["json", "jsonl", "csv", "tsv", "xlsx", "md", "html", "txt", "pdf"],
                  "import": ["json", "jsonl", "csv", "tsv"]},
    "narrators": {"label": "Narrators", "export": ["json", "jsonl", "csv", "tsv", "xlsx", "md", "html", "txt", "pdf",
                                                   "sqlite"], "import": []},
    "network": {"label": "Isnad network", "export": ["graphml", "gexf", "csv", "json"], "import": []},
    "settings": {"label": "Settings", "export": ["json", "csv", "tsv", "md"], "import": ["json", "csv", "tsv"]},
    "profile": {"label": "Profile", "export": ["isnady-profile", "json"], "import": ["isnady-profile", "json"]},
    "backup": {"label": "Everything of mine (backup)", "export": ["backup"], "import": ["backup"]},
}
DOCUMENT_KINDS = ("hadith", "book", "search")


class TransferError(Exception):
    pass


def _meta(kind: str, **more) -> dict:
    return {"kind": kind, "exported": time.strftime("%Y-%m-%dT%H:%M:%S"), "isnady": __version__, **more}


def suffix(fmt: str) -> str:
    return F.EXTENSIONS.get(fmt, "." + fmt)


def guess_format(path: str | Path, kind: str = "") -> str:
    """The format of a file to import, from its name (and, for a .json, its contents)."""
    name = str(path).lower()
    for fmt in ("isnady-book", "isnady-profile", "backup"):
        if name.endswith(F.EXTENSIONS[fmt]):
            return fmt
    p = Path(path)
    if p.is_dir() or name.endswith("book.json"):
        return "isnady-book"
    if name.endswith(".zip"):
        try:
            with zipfile.ZipFile(p) as z:
                names = z.namelist()
        except (OSError, zipfile.BadZipFile):
            return "zip"
        if "profile.json" in names:
            return "isnady-profile"
        if "backup.json" in names:
            return "backup"
        if any(n.endswith("book.json") for n in names):
            return "isnady-book"
        return "zip"
    return p.suffix.lstrip(".") or kind


# ================================================================== what is exported
def _languages_of(conn: sqlite3.Connection, hadith_ids: list[int], wanted: list[str] | None) -> list[str]:
    from isnady.core import search

    have = search.list_languages(conn)
    order = ["Arabic"] + [lang for lang in have if lang != "Arabic"]
    chosen = [lang for lang in order if lang in have and (not wanted or lang in wanted)]
    return chosen


def hadith_records(conn: sqlite3.Connection, hadith_ids: list[int], languages: list[str] | None = None,
                   chains: bool = True, progress: Progress | None = None) -> list[dict]:
    """Each hadith as a record: book, number, chapter, texts by language, grades, chains (Arabic, Turkish, English)."""
    from isnady.core import isnad

    say = progress or (lambda _m: None)
    langs = _languages_of(conn, hadith_ids, languages)
    out = []
    for i, hid in enumerate(hadith_ids):
        if i and i % 500 == 0:
            say(f"{i:,} / {len(hadith_ids):,}")
        head = conn.execute("""SELECT h.number, h.section_number, c.key, c.name, COALESCE(c.tradition, 'sunni')
                               FROM hadiths h JOIN collections c ON c.id = h.collection_id WHERE h.id = ?""",
                            (hid,)).fetchone()
        if head is None:
            continue
        number, section, key, name, road = head
        texts: dict[str, str] = {}
        chapter: dict[str, str] = {}
        for lang, text, eid in conn.execute(
                """SELECT e.language, t.text, e.id FROM texts t JOIN editions e ON e.id = t.edition_id
                   WHERE t.hadith_id = ? ORDER BY e.id""", (hid,)):
            if lang in langs and lang not in texts:
                texts[lang] = text
                if section is not None:
                    row = conn.execute("""SELECT st.title FROM section_titles st JOIN sections s ON s.id = st.section_id
                                          JOIN hadiths h ON h.collection_id = s.collection_id
                                          WHERE h.id = ? AND s.number = ? AND st.edition_id = ?""",
                                       (hid, section, eid)).fetchone()
                    if row:
                        chapter[lang] = row[0]
        grades = [[g, v] for g, v in conn.execute(
            "SELECT grader_name, grade FROM grades WHERE hadith_id = ? ORDER BY id", (hid,))]
        record = {"book": key, "book_title": name, "tradition": road, "number": number, "chapter_number": section,
                  "chapter": {lang: chapter[lang] for lang in langs if lang in chapter},
                  "texts": {lang: texts[lang] for lang in langs if lang in texts}, "grades": grades}
        if chains:
            record["chains"] = []
            for ch in isnad.chain(conn, hid):
                if not ch["links"] and not ch["raw"]:
                    continue
                record["chains"].append({
                    "arabic": ch["raw"] or "",
                    "turkish": isnad.chain_in_words(ch, "tr"), "english": isnad.chain_in_words(ch, "en"),
                    "narrators": [{"name": link["raw_name"], "term": link["transmission"],
                                   "identified": bool(link.get("person_id"))} for link in ch["links"]],
                    "reaches": isnad.end_label(ch) if (ch["reaches_prophet"] or ch.get("ends_with")) else ""})
        out.append(record)
    return out


def book_ids(conn: sqlite3.Connection, book: str, chapter: int | None = None) -> list[int]:
    from isnady.core import books

    key = books.resolve(book)
    sql = """SELECT h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id WHERE c.key = ?"""
    args: list = [key]
    if chapter is not None:
        sql += " AND h.section_number = ?"
        args.append(chapter)
    ids = [r[0] for r in conn.execute(sql + " ORDER BY h.number_sort, h.id", args)]
    if not ids:
        raise TransferError(f"No hadith in '{book}'" + (f", chapter {chapter}" if chapter is not None else "") + ".")
    return ids


def book_keys(conn: sqlite3.Connection, names: list[str]) -> list[str]:
    """Books named for an export, several at once (Bayram, 2026-10-24: "birden fazla kitap … secilebilir olsun.
    Hepsi de olsun"): keys or full names, or "all", "sunni", "shia" for every book (of that tradition) switched on."""
    from isnady.core import books

    every = books.all_books(conn)
    out: list[str] = []
    for name in names:
        name = (name or "").strip()
        if name in ("all", "sunni", "shia"):
            out += [b["key"] for b in every if name == "all" or (b.get("tradition") or "sunni") == name]
        elif name:
            out.append(books.resolve(name))
    return list(dict.fromkeys(out))


def ref_ids(conn: sqlite3.Connection, refs: list[str]) -> list[int]:
    """"bukhari:1", "bukhari:1-10", "muslim:8 muslim:9" → hadith ids, in the order asked."""
    from isnady.core import books

    out: list[int] = []
    for ref in " ".join(refs).replace(",", " ").split():
        book, _sep, nums = ref.partition(":")
        if not nums:
            raise TransferError(f"'{ref}': write it as book:number, e.g. bukhari:1 or bukhari:1-10.")
        key = books.resolve(book)
        if "-" in nums:
            a, b = nums.split("-", 1)
            try:
                lo, hi = float(a), float(b)
            except ValueError:
                raise TransferError(f"'{ref}': a range is two numbers, e.g. bukhari:1-10.") from None
            out += [r[0] for r in conn.execute(
                """SELECT h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id
                   WHERE c.key = ? AND h.number_sort BETWEEN ? AND ? ORDER BY h.number_sort, h.id""", (key, lo, hi))]
        else:
            row = conn.execute("""SELECT h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id
                                  WHERE c.key = ? AND h.number = ?""", (key, nums)).fetchone()
            if row is None:
                raise TransferError(f"No hadith {ref}.")
            out.append(row[0])
    if not out:
        raise TransferError("No hadith named.")
    return list(dict.fromkeys(out))


def search_ids(conn: sqlite3.Connection, text: str, limit: int = 1000, books: list[str] | None = None,
               languages: list[str] | None = None) -> list[int]:
    from isnady.core import search

    page = search.search(conn, search.SearchQuery(text=text, collections=books or [], languages=languages or [],
                                                  limit=limit))
    if not page.results:
        raise TransferError(f"Nothing found for '{text}'.")
    return [r.hadith_id for r in page.results]


def hadith_table(records: list[dict], title: str, meta: dict) -> F.Table:
    langs = list(dict.fromkeys(lang for r in records for lang in r["texts"]))
    with_chains = any("chains" in r for r in records)
    cols = ["book", "book_title", "tradition", "number", "chapter_number", "chapter"] + \
        [f"text_{lang}" for lang in langs] + ["grades"]
    if with_chains:
        cols += ["chain_arabic", "chain_turkish", "chain_english", "reaches"]
    rows = []
    for r in records:
        row = {"book": r["book"], "book_title": r["book_title"], "tradition": r["tradition"], "number": r["number"],
               "chapter_number": r["chapter_number"],
               "chapter": next(iter(r["chapter"].values()), ""),
               "grades": "; ".join(f"{g}: {v}" for g, v in r["grades"])}
        for lang in langs:
            row[f"text_{lang}"] = r["texts"].get(lang, "")
        if with_chains:
            chains = r.get("chains") or []
            row["chain_arabic"] = " ‖ ".join(c["arabic"] for c in chains)
            row["chain_turkish"] = " ‖ ".join(c["turkish"] for c in chains)
            row["chain_english"] = " ‖ ".join(c["english"] for c in chains)
            row["reaches"] = " ‖ ".join(c["reaches"] for c in chains if c["reaches"])
        rows.append(row)
    return F.Table(title, cols, rows, meta)


def hadith_document(records: list[dict], title: str, subtitle: str = "") -> F.Document:
    from isnady.core.i18n import tr

    sections: list[F.Section] = []
    current_key = None
    for r in records:
        key = (r["book"], r["chapter_number"])
        if key != current_key:
            heading = r["book_title"] + (f" — {next(iter(r['chapter'].values()))}" if r["chapter"] else "")
            sections.append(F.Section(heading))
            current_key = key
        paragraphs: list[tuple[str, str]] = []
        for c in r.get("chains") or []:
            paragraphs.append((tr("Chain"), c["arabic"]))
            paragraphs.append((tr("Turkish"), c["turkish"]))
            paragraphs.append((tr("English"), c["english"]))
        for lang, text in r["texts"].items():
            paragraphs.append((tr(lang), text))
        note = "; ".join(f"{g}: {v}" for g, v in r["grades"])
        sections[-1].entries.append(F.Entry(f"{r['book_title']} {r['number']}", paragraphs, note))
    return F.Document(title, sections, subtitle)


def bookmark_table(store=None) -> F.Table:
    from isnady.core import bookmarks

    store = store or bookmarks.Store.load()
    rows = []
    for item in store.items:
        rows.append({"id": item.id, "kind": item.kind, "ref": item.ref, "title": item.title,
                     "subtitle": item.subtitle, "note": item.note,
                     "folders": [store.path_of(f) for f in item.folders],
                     "added": time.strftime("%Y-%m-%d %H:%M", time.localtime(item.added)) if item.added else ""})
    return F.Table("isnady bookmarks", ["kind", "ref", "title", "subtitle", "note", "folders", "added", "id"], rows,
                   _meta("bookmarks"))


def narrator_table(conn: sqlite3.Connection, text: str = "", tradition: str | None = "sunni",
                   progress: Progress | None = None) -> F.Table:
    from isnady.core import narrators

    rows, _total = narrators.browse(conn, text, limit=100000, tradition=tradition)
    out = []
    for r in rows:
        view = r.get("view") or {}
        out.append({"id": r["id"], "tradition": r.get("tradition"), "name_ar": r["name"],
                    "known_as": view.get("arabic") or "", "reading": view.get("reading") or "",
                    "full_reading": view.get("full_reading") or "", "tabaqa": r.get("tabaqa"),
                    "death_ah": r.get("death"), "rank": r.get("rank"), "verdict": r.get("verdict"),
                    "in_chains": r.get("in_chains"), "source": r.get("source")})
    cols = ["id", "tradition", "known_as", "reading", "full_reading", "name_ar", "tabaqa", "death_ah", "rank",
            "verdict", "in_chains", "source"]
    return F.Table("isnady narrators" + (f": {text}" if text else ""), cols, out,
                   _meta("narrators", tradition=tradition or "all", query=text))


def network(conn: sqlite3.Connection, book: str | list[str] | None = None, tradition: str | None = None,
            minimum: int = 1) -> tuple[list[dict], list[dict]]:
    """Who narrated from whom in the chains (of one book, of several, or all): nodes and weighted edges teacher →
    student."""
    where, args = "", []
    keys = book_keys(conn, [book] if isinstance(book, str) else list(book or [])) if book else []
    if keys:
        where = f"AND c.key IN ({','.join('?' * len(keys))})"
        args.extend(keys)
    if tradition:
        where += " AND COALESCE(c.tradition, 'sunni') = ?"
        args.append(tradition)
    pairs = conn.execute(f"""
        SELECT b.person_id AS teacher, a.person_id AS student, COUNT(*) FROM isnad_links a
        JOIN isnad_links b ON b.isnad_id = a.isnad_id AND b.position = a.position + 1
        JOIN isnads i ON i.id = a.isnad_id JOIN hadiths h ON h.id = i.hadith_id JOIN collections c ON c.id = h.collection_id
        WHERE a.person_id IS NOT NULL AND b.person_id IS NOT NULL AND a.person_id != b.person_id {where}
        GROUP BY teacher, student HAVING COUNT(*) >= ?""", (*args, minimum)).fetchall()
    ids = {p for t, s, _n in pairs for p in (t, s)}
    nodes = []
    if ids:
        from isnady.core.rijal import display_name

        for pid, name, tabaqa, road in conn.execute(
                f"SELECT id, name_ar, tabaqa, COALESCE(tradition, 'sunni') FROM persons WHERE id IN "
                f"({','.join(str(i) for i in ids)})"):
            shown = display_name(name or "")
            from isnady.core.isnad import name_reading

            label, _s = name_reading(" ".join(shown.split()[:4]), "en")
            nodes.append({"id": pid, "label": label or shown, "arabic": shown, "tabaqa": tabaqa, "tradition": road})
    edges = [{"source": t, "target": s, "weight": n} for t, s, n in pairs]
    if not edges:
        raise TransferError("No identified teacher and student in these chains.")
    return nodes, edges


def settings_table(profile: str | None = None) -> F.Table:
    from isnady import config

    rows = [{"key": k, "value": v, "default": d, "changed": v != d} for k, v, d in config.all_values()]
    return F.Table("isnady settings", ["key", "value", "default", "changed"], rows, _meta("settings"))


# ================================================================== export
def export(conn: sqlite3.Connection | None, kind: str, fmt: str, target: str | Path, *, book: str = "",
           chapter: int | None = None, refs: list[str] | None = None, query: str = "",
           languages: list[str] | None = None, chains: bool = True, tradition: str | None = "sunni",
           profile: str | None = None, pdf=None, progress: Progress | None = None,
           books: list[str] | None = None, profiles: list[str] | None = None, separate: bool = False) -> Path:
    """Write what is asked to target in fmt; returns the file written. pdf: a function (html, path) that draws a PDF
    (gui.pdf.html_to_pdf), given by the window or the command line.

    Several at once: books (keys, full names, "all", "sunni", "shia") for a book or the network, profiles for a
    profile. Several books go into one file, or with separate (and always as isnady books) each into its own file
    in the folder target; several profiles each into its own file in the folder target."""
    say = progress or (lambda _m: None)
    if kind == "book" and books:
        if conn is None:
            raise TransferError("No database.")
        keys = book_keys(conn, books)
        if not keys:
            raise TransferError("No book chosen.")
        if len(keys) == 1:
            book, books = keys[0], None
        elif separate or fmt == "isnady-book":
            return _each(keys, Path(target), fmt, say, lambda key, path: export(
                conn, "book", fmt, path, book=key, languages=languages, chains=chains, pdf=pdf, progress=say))
    if kind == "profile" and profiles and len(profiles) > 1:
        from isnady.core import profiles as core_profiles

        names = {p["id"]: p.get("name") or p["id"] for p in core_profiles.all_profiles()}
        return _each(list(dict.fromkeys(profiles)), Path(target), fmt, say,
                     lambda pid, path: export_profile(fmt, path, pid), names)
    if kind == "profile" and profiles:
        profile = profiles[0]
    if kind not in KINDS:
        raise TransferError(f"Nothing called '{kind}' is exported. One of: {', '.join(KINDS)}.")
    if fmt not in KINDS[kind]["export"]:
        raise TransferError(f"{KINDS[kind]['label']} is exported as {', '.join(KINDS[kind]['export'])}; not {fmt}.")
    target = Path(target).expanduser()
    if fmt == "pdf" and pdf is None:
        raise TransferError("PDF needs isnady's window library (PySide6).")

    if kind in DOCUMENT_KINDS:
        if conn is None:
            raise TransferError("No database.")
        if kind == "book":
            if not book and not books:
                raise TransferError("Which book? e.g. bukhari.")
            if fmt == "isnady-book":
                return export_isnady_book(conn, book, target, languages, say)
            if books:                                   # several books in one file, one after another
                keys = book_keys(conn, books)
                ids = [i for key in keys for i in book_ids(conn, key)]
                title = "isnady: " + ", ".join(
                    conn.execute("SELECT name FROM collections WHERE key = ?", (k,)).fetchone()[0] for k in keys[:6]) \
                    + (f" … ({len(keys)})" if len(keys) > 6 else "")
            else:
                ids = book_ids(conn, book, chapter)
                from isnady.core import books as core_books

                title = conn.execute("SELECT name FROM collections WHERE key = ?",
                                     (core_books.resolve(book),)).fetchone()[0]
                if chapter is not None:
                    title += f" — {chapter}"
        elif kind == "hadith":
            ids = ref_ids(conn, refs or [])
            title = "isnady: " + " ".join(refs or [])
        else:
            ids = search_ids(conn, query, languages=None)
            title = f"isnady: “{query}”"
        say(f"{len(ids):,} hadith")
        records = hadith_records(conn, ids, languages, chains, say)
        meta = _meta(kind, book=book, chapter=chapter, refs=refs or [], query=query, languages=languages or [],
                     **({"books": book_keys(conn, books)} if kind == "book" and books else {}))
        if fmt == "json":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps({"schema": "isnady-export/1", **meta, "title": title, "hadith": records},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
            return target
        if fmt == "jsonl":
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            return target
        if fmt in ("html", "md", "txt", "epub", "docx", "pdf"):
            doc = hadith_document(records, title, f"isnady {__version__} · {time.strftime('%Y-%m-%d')}")
            if fmt == "pdf":
                pdf(F.document_html(doc), target)
                return target
            return F.write_document(doc, fmt, target)
        return F.write_table(hadith_table(records, title, meta), fmt, target)

    if kind == "network":
        chosen = books or ([book] if book else None)
        nodes, edges = network(conn, chosen, tradition)
        return F.write_graph(nodes, edges, fmt, target, f"isnady: {', '.join(chosen) if chosen else 'all books'}")
    if kind == "narrators":
        table = narrator_table(conn, query, tradition, say)
    elif kind == "bookmarks":
        if fmt == "json":
            from isnady.core import bookmarks

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(bookmarks.Store.load().to_dict(), ensure_ascii=False, indent=1),
                              encoding="utf-8")
            return target
        table = bookmark_table()
    elif kind == "settings":
        if fmt == "json":
            from isnady import config

            target.parent.mkdir(parents=True, exist_ok=True)
            changed = {k: v for k, v, d in config.all_values() if v != d}
            target.write_text(json.dumps({"schema": "isnady-settings/1", **_meta("settings"), "settings": changed},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
            return target
        table = settings_table()
    elif kind == "profile":
        return export_profile(fmt, target, profile)
    elif kind == "backup":
        return export_backup(conn, target)
    else:
        raise TransferError(kind)
    if fmt == "pdf":
        pdf(F.table_html(table), target)
        return target
    return F.write_table(table, fmt, target)


def _each(keys: list[str], folder: Path, fmt: str, say: Progress, write, names: dict | None = None) -> Path:
    """One file for each of several things, in a folder; returns the folder."""
    from isnady.core import books as core_books

    if folder.suffix and not folder.is_dir():
        folder = folder.with_suffix("")            # "x.json" given for several: the folder "x"
    folder.mkdir(parents=True, exist_ok=True)
    for n, key in enumerate(keys, 1):
        base = (names or {}).get(key) or core_books.full_name(key)
        base = "".join(c if c.isalnum() or c in "-_. " else "_" for c in base).strip() or key
        say(f"{n}/{len(keys)}: {base}")
        write(key, folder / (base + suffix(fmt)))
    return folder


def export_isnady_book(conn: sqlite3.Connection, book: str, target: Path, languages: list[str] | None,
                       say: Progress) -> Path:
    """The book in isnady-data's own format (isnady-book/1), zipped: imported again as a book."""
    from isnady.core import books, catalog

    key = books.resolve(book)
    row = conn.execute("SELECT id, name, COALESCE(tradition, 'sunni') FROM collections WHERE key = ?",
                       (key,)).fetchone()
    if row is None:
        raise TransferError(f"No book '{book}'.")
    cid, title, road = row
    editions = conn.execute("""SELECT e.id, e.language, e.direction, e.author FROM editions e
                               WHERE e.collection_id = ? AND e.text_count > 0 ORDER BY e.id""", (cid,)).fetchall()
    chosen: dict[str, tuple] = {}
    for eid, lang, direction, author in editions:
        if lang and lang not in chosen and (not languages or lang in languages):
            chosen[lang] = (eid, direction, author)
    if not chosen:
        raise TransferError(f"'{book}' has no texts in the languages chosen.")
    hadiths = []
    for hid, number, sort, section in conn.execute(
            "SELECT id, number, number_sort, section_number FROM hadiths WHERE collection_id = ? "
            "ORDER BY number_sort, id", (cid,)):
        refs = dict(conn.execute("SELECT scheme, value FROM hadith_refs WHERE hadith_id = ?", (hid,)).fetchall())
        grades = [[g, v] for g, v in conn.execute("SELECT grader_name, grade FROM grades WHERE hadith_id = ?", (hid,))]
        hadiths.append({"n": number, "sort": sort, "s": section, "refs": refs, "grades": grades, "_id": hid})
    langs_meta, files = {}, {}
    for lang, (eid, direction, author) in chosen.items():
        code = catalog.code_for(lang)
        say(f"{title}: {lang}")
        texts = {}
        for h in hadiths:
            t = conn.execute("SELECT text FROM texts WHERE hadith_id = ? AND edition_id = ?", (h["_id"], eid)).fetchone()
            if t:
                texts[h["n"]] = t[0]
        sections = {str(n): t for n, t in conn.execute(
            "SELECT s.number, st.title FROM section_titles st JOIN sections s ON s.id = st.section_id "
            "WHERE s.collection_id = ? AND st.edition_id = ?", (cid, eid))}
        files[f"{code}.json"] = {"language": code, "sections": sections, "texts": texts}
        langs_meta[code] = {"file": f"{code}.json", "name": lang, "direction": direction or "ltr",
                            "author": author or ""}
    source = conn.execute("""SELECT s.license FROM sources s JOIN editions e ON e.source_id = s.id
                             WHERE e.collection_id = ? LIMIT 1""", (cid,)).fetchone()
    book_json = {"schema": "isnady-book/1", "key": key, "title": title, "tradition": road,
                 "license": source[0] if source else None, "credit": f"Exported by isnady {__version__}",
                 "languages": langs_meta, "hadiths": [{k: v for k, v in h.items() if k != "_id"} for h in hadiths]}
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{key}/book.json", json.dumps(book_json, ensure_ascii=False))
        for name, data in files.items():
            z.writestr(f"{key}/{name}", json.dumps(data, ensure_ascii=False))
    return target


def export_profile(fmt: str, target: Path, profile: str | None = None) -> Path:
    from isnady.core import profiles

    pid = profiles.find(profile) if profile else profiles.active()
    if pid is None:
        raise TransferError(f"No profile '{profile}'.")
    if fmt == "isnady-profile":
        return profiles.export(pid, target)
    folder = profiles.folder(pid)
    bundle = {"schema": "isnady-profile-json/1", **_meta("profile"), "name": profiles.name_of(pid) or "default"}
    for name in profiles.FILES:
        try:
            bundle[name.split(".")[0]] = json.loads((folder / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            bundle[name.split(".")[0]] = {}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
    return target


def export_backup(conn: sqlite3.Connection | None, target: Path) -> Path:
    """Everything of mine: this profile's settings, place and bookmarks, and the list of the books imported (which
    isnady imports again from where they came)."""
    from isnady.core import profiles

    folder = profiles.folder()
    sources = []
    if conn is not None:
        sources = [{"key": k, "name": n, "format": f, "location": loc, "license": lic, "origin": o}
                   for k, n, f, loc, lic, o in conn.execute(
                       "SELECT key, name, format, location, license, origin FROM sources ORDER BY id")]
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("backup.json", json.dumps({"schema": "isnady-backup/1", **_meta("backup"),
                                              "profile": profiles.name_of(profiles.active()) or "default",
                                              "sources": sources}, ensure_ascii=False, indent=1))
        for name in profiles.FILES:
            if (folder / name).exists():
                z.write(folder / name, name)
    return target


# ================================================================== import
def _rows(path: Path, fmt: str) -> list[dict]:
    """The records of a JSON (an export's "rows"/"hadith" or a plain list), JSON Lines, CSV or TSV file."""
    text = path.read_text(encoding="utf-8-sig")
    if fmt == "jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if fmt == "json":
        data = json.loads(text)
        if isinstance(data, list):
            return data
        for key in ("rows", "hadith", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        raise TransferError(f"{path.name}: no list of records in it.")
    if fmt in ("csv", "tsv"):
        dialect = "excel-tab" if fmt == "tsv" else "excel"
        return list(csv.DictReader(io.StringIO(text), dialect=dialect))
    raise TransferError(f"{path.name}: {fmt} cannot be read.")


def import_file(conn: sqlite3.Connection | None, kind: str, path: str | Path, *, fmt: str = "",
                replace: bool = False, folder: str = "", name: str = "", progress: Progress | None = None) -> str:
    """Bring a file in; returns a sentence saying what came in."""
    say = progress or (lambda _m: None)
    path = Path(path).expanduser()
    if not path.exists():
        raise TransferError(f"No file {path}.")
    fmt = fmt or guess_format(path, kind)
    if kind not in KINDS:
        raise TransferError(f"Nothing called '{kind}' is imported. One of: "
                            f"{', '.join(k for k, v in KINDS.items() if v['import'])}.")
    if fmt not in KINDS[kind]["import"]:
        raise TransferError(f"{KINDS[kind]['label']} is imported from {', '.join(KINDS[kind]['import']) or 'nothing'}; "
                            f"not {fmt}.")
    try:
        if kind == "bookmarks":
            return import_bookmarks(path, fmt, replace, folder)
        if kind == "settings":
            return import_settings(path, fmt, replace)
        if kind == "profile":
            return import_profile(path, fmt, name)
        if kind == "backup":
            return import_backup(path)
        if kind == "book":
            if conn is None:
                raise TransferError("No database.")
            return import_book(conn, path, fmt, say)
    except (ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise TransferError(f"{path.name}: not readable as {fmt} ({exc}).") from None
    raise TransferError(kind)


def import_bookmarks(path: Path, fmt: str, replace: bool = False, folder: str = "") -> str:
    from isnady.core import bookmarks

    store = bookmarks.Store() if replace else bookmarks.Store.load()
    if fmt == "json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict) and str(data.get("schema", "")).startswith("isnady-bookmarks"):
            incoming = bookmarks.Store.from_dict(data)
            if folder:
                top = store.ensure_path(folder)
                for f in incoming.folders:
                    if f.parent is None:
                        f.parent = top.id
                for item in incoming.items:
                    if not item.folders:
                        item.folders = [top.id]
            added, folders = store.merge(incoming)
            store.save()
            return f"{added} bookmarks and {folders} folders added (the ones already there kept)."
    rows = _rows(path, fmt)
    added = 0
    for r in rows:
        kind, ref = str(r.get("kind") or "").strip(), str(r.get("ref") or "").strip()
        if kind not in bookmarks.KINDS or not ref:
            continue
        item = store.find(kind, ref) or store.add(kind, ref, str(r.get("title") or ref), str(r.get("subtitle") or ""))
        if r.get("note"):
            item.note = str(r["note"])
        paths = r.get("folders") or ""
        paths = paths if isinstance(paths, list) else [p.strip() for p in str(paths).split("|") if p.strip()]
        for p in paths + ([folder] if folder else []):
            store.file_in(item.id, store.ensure_path(p).id)
        added += 1
    store.save()
    return f"{added} bookmarks imported."


def import_settings(path: Path, fmt: str, replace: bool = False) -> str:
    from isnady import config

    if fmt == "json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        values = data.get("settings", data) if isinstance(data, dict) else {}
        if "rows" in values:
            values = {r["key"]: r["value"] for r in values["rows"]}
    else:
        # an export lists every setting with its default: only the ones changed are taken
        values = {r["key"]: r.get("value") for r in _rows(path, fmt)
                  if r.get("key") and str(r.get("changed", "True")).lower() in ("true", "1", "yes")}
    if replace:
        config.reset("")
    done, skipped = 0, []
    for key, value in values.items():
        if key in ("schema", "kind", "exported", "isnady", "columns", "title"):
            continue
        try:
            config.set(key, value)
            done += 1
        except Exception:               # an unknown key or a value isnady does not take
            skipped.append(key)
    config.forget()
    return f"{done} settings imported" + (f"; not taken: {', '.join(skipped[:8])}" if skipped else "") + "."


def import_profile(path: Path, fmt: str, name: str = "") -> str:
    from isnady.core import profiles

    if fmt == "isnady-profile":
        pid = profiles.import_file(path, name or None)
        return f"Imported as the profile {profiles.name_of(pid)}."
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data.get("schema") != "isnady-profile-json/1":
        raise TransferError(f"{path.name} is not an isnady profile.")
    wanted = (name or data.get("name") or "Imported").strip()
    final, n = wanted, 2
    while profiles.find(final):
        final, n = f"{wanted} ({n})", n + 1
    pid = profiles.create(final)
    folder = profiles.folder(pid)
    for file in profiles.FILES:
        part = data.get(file.split(".")[0])
        if part:
            (folder / file).write_text(json.dumps(part, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"Imported as the profile {final}."


def import_backup(path: Path) -> str:
    """The backup's settings, place and bookmarks into this profile; says which of its books are not here."""
    from isnady import config
    from isnady.core import profiles

    folder = profiles.folder()
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("backup.json").decode("utf-8"))
        if manifest.get("schema") != "isnady-backup/1":
            raise TransferError(f"{path.name} is not an isnady backup.")
        restored = []
        for name in profiles.FILES:
            if name in z.namelist():
                raw = z.read(name)
                json.loads(raw.decode("utf-8"))
                (folder / name).write_bytes(raw)
                restored.append(name.split(".")[0])
    config.forget()
    books = len(manifest.get("sources", []))
    return (f"Restored: {', '.join(restored) or 'nothing'}. The backup lists {books} sources; import the books again "
            "with File → Data Sources (or iy catalog import --all).")


def _book_from_records(rows: list[dict], path: Path) -> tuple[dict, dict[str, dict]]:
    """An export (json, jsonl, csv, tsv) turned back into an isnady book."""
    from isnady.core import catalog

    if not rows:
        raise TransferError(f"{path.name} has no hadith.")
    first = rows[0]
    key = re.sub(r"\W+", "_", str(first.get("book") or path.stem.split(".")[0]).lower()).strip("_") or "imported"
    title = str(first.get("book_title") or key)
    langs: dict[str, dict] = {}
    hadiths = []
    for r in rows:
        number = str(r.get("number") or "").strip()
        if not number:
            continue
        section = r.get("chapter_number")
        try:
            section = int(section) if section not in (None, "") else None
        except (TypeError, ValueError):
            section = None
        try:
            sort = float(number)
        except ValueError:
            sort = None
        grades = r.get("grades") or []
        if isinstance(grades, str):
            grades = [g.split(":", 1) for g in grades.split(";") if ":" in g]
        hadiths.append({"n": number, "sort": sort, "s": section, "grades": [[g.strip(), v.strip()] for g, v in grades]})
        texts = r.get("texts") if isinstance(r.get("texts"), dict) else {
            k[5:]: v for k, v in r.items() if k.startswith("text_") and v}
        chapters = r.get("chapter") if isinstance(r.get("chapter"), dict) else {}
        for lang, text in texts.items():
            code = catalog.code_for(lang)
            data = langs.setdefault(code, {"name": lang, "texts": {}, "sections": {}})
            data["texts"][number] = text
            if section is not None and chapters.get(lang):
                data["sections"][str(section)] = chapters[lang]
    book = {"schema": "isnady-book/1", "key": key, "title": title,
            "tradition": str(first.get("tradition") or "sunni"), "credit": f"Imported from {path.name}",
            "languages": {code: {"file": f"{code}.json", "name": d["name"],
                                 "direction": "rtl" if F.rtl(next(iter(d["texts"].values()), "")) else "ltr"}
                          for code, d in langs.items()},
            "hadiths": hadiths}
    files = {f"{code}.json": {"language": code, "sections": d["sections"], "texts": d["texts"]}
             for code, d in langs.items()}
    return book, files


def import_book(conn: sqlite3.Connection, path: Path, fmt: str, say: Progress) -> str:
    """A book back into isnady, as a source of your own: an isnady-book (zip, folder or book.json), or an export of
    isnady's in json, jsonl, csv or tsv."""
    from isnady.data.paths import data_dir

    where = data_dir() / "imported-books"
    if fmt == "isnady-book":
        if path.is_dir():
            book_json = path / "book.json"
        elif path.name.endswith("book.json"):
            book_json = path
        else:
            with zipfile.ZipFile(path) as z:
                inside = [n for n in z.namelist() if n.endswith("book.json")]
                if not inside:
                    raise TransferError(f"{path.name} holds no book.json.")
                key = json.loads(z.read(inside[0]).decode("utf-8")).get("key") or path.stem
                target = where / re.sub(r"\W+", "_", key)
                target.mkdir(parents=True, exist_ok=True)
                base = inside[0].rsplit("/", 1)[0] + "/" if "/" in inside[0] else ""
                for n in z.namelist():
                    if n.startswith(base) and not n.endswith("/") and ".." not in n:
                        (target / n[len(base):]).parent.mkdir(parents=True, exist_ok=True)
                        (target / n[len(base):]).write_bytes(z.read(n))
                book_json = target / "book.json"
    else:
        # an export may hold hadith of several books (bukhari:1-3 muslim:10): each goes back to its own book
        groups: dict[str, list[dict]] = {}
        for r in _rows(path, fmt):
            groups.setdefault(str(r.get("book") or ""), []).append(r)
        said = []
        for rows in groups.values():
            book, files = _book_from_records(rows, path)
            target = where / book["key"]
            target.mkdir(parents=True, exist_ok=True)
            (target / "book.json").write_text(json.dumps(book, ensure_ascii=False), encoding="utf-8")
            for name, data in files.items():
                (target / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            said.append(_import_book_json(conn, target / "book.json", say))
        return " ".join(said)
    return _import_book_json(conn, book_json, say)


def _import_book_json(conn: sqlite3.Connection, book_json: Path, say: Progress) -> str:
    from isnady.core import imports

    meta = json.loads(book_json.read_text(encoding="utf-8"))
    request = imports.ImportRequest("isnady", str(book_json), name=meta.get("title"), license=meta.get("license"),
                                    origin="user", options={"languages": list(meta.get("languages", {}))})
    report, _narrators = imports.run_import(conn, request, progress=say)
    return f"{meta.get('title')}: {report.new_hadiths:,} hadith, {report.texts:,} texts imported."
