"""File formats for export (EX1): every writer isnady has, Qt-free and without any package beyond Python's own.

Two shapes of data are written:

  a TABLE     rows of plain values under named columns (bookmarks, narrators, settings, a book flattened):
              json, jsonl, csv, tsv, xlsx, md, html, txt, sqlite
  a DOCUMENT  a title and sections, each with entries of headings and paragraphs (hadith with their chains and
              texts, Arabic right to left): html, md, txt, epub, docx — and pdf, drawn from the html by Qt
              (gui/pdf.py, the one writer that needs it)

XLSX, DOCX and EPUB are written as the zip of XML their standards define (Office Open XML, EPUB 3): small,
valid files that Excel, LibreOffice, Word and any e-book reader open.
"""

from __future__ import annotations

import csv
import html
import io
import json
import re
import sqlite3
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from isnady.core.i18n import N_

TABLE_FORMATS = ("json", "jsonl", "csv", "tsv", "xlsx", "md", "html", "txt", "sqlite", "pdf")
DOCUMENT_FORMATS = ("html", "md", "txt", "epub", "docx", "pdf")
EXTENSIONS = {"json": ".json", "jsonl": ".jsonl", "csv": ".csv", "tsv": ".tsv", "xlsx": ".xlsx", "md": ".md",
              "html": ".html", "txt": ".txt", "sqlite": ".sqlite", "pdf": ".pdf", "epub": ".epub",
              "docx": ".docx", "graphml": ".graphml", "gexf": ".gexf", "isnady-book": ".isnady-book.zip",
              "isnady-profile": ".isnady-profile.zip", "backup": ".isnady-backup.zip"}
LABELS = {"json": N_("JSON"), "jsonl": N_("JSON Lines"), "csv": N_("CSV"), "tsv": N_("TSV"), "xlsx": N_("Excel (XLSX)"),
          "md": N_("Markdown"), "html": N_("HTML"), "txt": N_("Text"), "sqlite": N_("SQLite"), "pdf": N_("PDF"), "epub": N_("EPUB"),
          "docx": N_("Word (DOCX)"), "graphml": N_("GraphML (Gephi, yEd)"), "gexf": N_("GEXF (Gephi)"),
          "isnady-book": N_("isnady book (importable)"), "isnady-profile": N_("isnady profile"),
          "backup": N_("isnady backup")}
_ARABIC = re.compile(r"[\u0600-\u06ff]")


_ARABIC_LETTERS = re.compile(r"[\u0600-\u06ff]")
_OTHER_LETTERS = re.compile(r"[^\W\d_\u0600-\u06ff]")


def rtl(text: str) -> bool:
    """Mostly Arabic script: written right to left. (Counted with two patterns over the first 400 characters: asked
    for every paragraph of every hadith, it was a third of the time of a whole-book EPUB.)"""
    head = text[:400]
    arabic = len(_ARABIC_LETTERS.findall(head))
    return arabic > 0 and arabic > len(_OTHER_LETTERS.findall(head))


# ------------------------------------------------------------------ the two shapes
@dataclass
class Table:
    title: str
    columns: list[str]
    rows: list[dict]
    meta: dict = field(default_factory=dict)       # written into JSON as it is (what, when, by which isnady)


@dataclass
class Entry:
    heading: str
    paragraphs: list[tuple[str, str]] = field(default_factory=list)   # (label, text): a label may be ""
    note: str = ""


@dataclass
class Section:
    heading: str
    entries: list[Entry] = field(default_factory=list)


@dataclass
class Document:
    title: str
    sections: list[Section]
    subtitle: str = ""


# ------------------------------------------------------------------ tables
def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " | ".join(_cell(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def write_table(table: Table, fmt: str, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = table.columns
    if fmt == "json":
        body = {"schema": "isnady-export/1", "title": table.title, **table.meta, "columns": cols, "rows": table.rows}
        path.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    elif fmt == "jsonl":
        with path.open("w", encoding="utf-8") as f:
            for row in table.rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    elif fmt in ("csv", "tsv"):
        with path.open("w", encoding="utf-8-sig", newline="") as f:    # with BOM: Excel reads it as UTF-8
            w = csv.writer(f, delimiter="," if fmt == "csv" else "\t")
            w.writerow(cols)
            for row in table.rows:
                w.writerow([_cell(row.get(c)) for c in cols])
    elif fmt == "xlsx":
        _xlsx(table, path)
    elif fmt == "md":
        path.write_text(table_markdown(table), encoding="utf-8")
    elif fmt == "html":
        path.write_text(table_html(table), encoding="utf-8")
    elif fmt == "txt":
        lines = [table.title, ""]
        for row in table.rows:
            lines += [f"{c}: {_cell(row.get(c))}" for c in cols if _cell(row.get(c))] + [""]
        path.write_text("\n".join(lines), encoding="utf-8")
    elif fmt == "sqlite":
        if path.exists():
            path.unlink()
        db = sqlite3.connect(path)
        safe = [re.sub(r"\W+", "_", c) or f"c{i}" for i, c in enumerate(cols)]
        db.execute(f"CREATE TABLE rows ({', '.join(f'{s} TEXT' for s in safe)})")
        db.executemany(f"INSERT INTO rows VALUES ({', '.join('?' * len(cols))})",
                       [[_cell(r.get(c)) for c in cols] for r in table.rows])
        db.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        db.executemany("INSERT INTO meta VALUES (?, ?)", [("title", table.title)] +
                       [(k, _cell(v)) for k, v in table.meta.items()])
        db.commit()
        db.close()
    else:
        raise ValueError(f"A table is not written as {fmt}.")
    return path


def table_markdown(table: Table) -> str:
    def esc(v):
        return _cell(v).replace("|", "\\|").replace("\n", " ")
    out = [f"# {table.title}", "", "| " + " | ".join(table.columns) + " |",
           "|" + "|".join("---" for _ in table.columns) + "|"]
    out += ["| " + " | ".join(esc(r.get(c)) for c in table.columns) + " |" for r in table.rows]
    return "\n".join(out) + "\n"


_CSS = """body{font-family:'Noto Sans','Segoe UI',sans-serif;margin:2em;color:#1d2433;line-height:1.5}
h1{font-size:1.6em;margin-bottom:.2em}h2{font-size:1.25em;margin-top:1.6em;border-bottom:1px solid #ccd}
h3{font-size:1.05em;margin:1.2em 0 .3em}.sub{color:#667}.label{color:#667;font-size:.85em}
.ar{direction:rtl;text-align:right;font-family:'Amiri','Scheherazade New','Noto Naskh Arabic',serif;font-size:1.3em}
.note{color:#667;font-size:.85em}table{border-collapse:collapse;font-size:.9em}
td,th{border:1px solid #ccd;padding:4px 7px;vertical-align:top}th{background:#eef}"""


def table_html(table: Table) -> str:
    head = "".join(f"<th>{html.escape(c)}</th>" for c in table.columns)
    body = []
    for r in table.rows:
        cells = []
        for c in table.columns:
            v = _cell(r.get(c))
            cls = " class='ar'" if v and rtl(v) else ""
            cells.append(f"<td{cls}>{html.escape(v)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(table.title)}</title>"
            f"<style>{_CSS}</style></head><body><h1>{html.escape(table.title)}</h1>"
            f"<table><tr>{head}</tr>{''.join(body)}</table></body></html>")


def _col(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _xml(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return html.escape(text, quote=False)


def _xlsx(table: Table, path: Path) -> None:
    rows = [table.columns] + [[_cell(r.get(c)) for c in table.columns] for r in table.rows]
    sheet = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for i, row in enumerate(rows, 1):
        bold = ' s="1"' if i == 1 else ""
        cells = "".join(f'<c r="{_col(j)}{i}" t="inlineStr"{bold}><is><t xml:space="preserve">'
                        f'{_xml(v[:32000])}</t></is></c>' for j, v in enumerate(row))
        sheet.append(f'<row r="{i}">{cells}</row>')
    sheet.append("</sheetData></worksheet>")
    name = _xml(re.sub(r"[\[\]:*?/\\]", " ", table.title)[:31] or "isnady")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
                   'content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
                   'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName='
                   '"/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.'
                   'main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.'
                   'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" '
                   'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                   'officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/'
                   'spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
                   f'relationships"><sheets><sheet name="{name}" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                   'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship '
                   'Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
                   'Target="styles.xml"/></Relationships>')
        z.writestr("xl/styles.xml",
                   '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/'
                   'spreadsheetml/2006/main"><fonts count="2"><font/><font><b/></font></fonts><fills count="1">'
                   '<fill/></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
                   '<cellXfs count="2"><xf/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>')
        z.writestr("xl/worksheets/sheet1.xml", "".join(sheet))


# ------------------------------------------------------------------ documents
# ------------------------------------------------------------------ documents, written as they come (EX3)
# A document is written section by section: the whole of every book (99,567 hadith in every language — Bayram,
# 2026-10-24: "epub olarak hepsini tum dilleri ile … cok cok uzuyor") is never held in memory at once, and the file
# grows while the hadith are read. write_document is the same writer given every section at once.

def _section_html(section: Section) -> str:
    out = []
    if section.heading:
        out.append(f"<h2>{html.escape(section.heading)}</h2>")
    for e in section.entries:
        out.append(f"<h3>{html.escape(e.heading)}</h3>")
        for label, text in e.paragraphs:
            if not text:
                continue
            cls = "ar" if rtl(text) else ""
            lab = f"<span class='label'>{html.escape(label)}:</span> " if label and not cls else ""
            out.append(f"<p class='{cls}' dir='{'rtl' if cls else 'ltr'}'>{lab}{html.escape(text)}</p>")
        if e.note:
            out.append(f"<p class='note'>{html.escape(e.note)}</p>")
    return "\n".join(out)


def _section_markdown(section: Section) -> str:
    out = [f"## {section.heading}", ""] if section.heading else []
    for e in section.entries:
        out += [f"### {e.heading}", ""]
        for label, text in e.paragraphs:
            if text:
                out += [(f"**{label}:** " if label and not rtl(text) else "") + text, ""]
        if e.note:
            out += [f"_{e.note}_", ""]
    return "\n".join(out)


def _section_text(section: Section) -> str:
    out = [section.heading, "-" * min(len(section.heading), 70), ""] if section.heading else []
    for e in section.entries:
        out.append(e.heading)
        for label, text in e.paragraphs:
            if text:
                out.append((f"{label}: " if label and not rtl(text) else "") + text)
        if e.note:
            out.append(e.note)
        out.append("")
    return "\n".join(out)


def _section_xhtml(section: Section, title: str) -> str:
    parts = [f"<h2>{_xml(section.heading or title)}</h2>"]
    for e in section.entries:
        parts.append(f"<h3>{_xml(e.heading)}</h3>")
        for label, text in e.paragraphs:
            if text:
                if rtl(text):
                    parts.append(f'<p class="ar" dir="rtl">{_xml(text)}</p>')
                else:
                    lead = f'<span class="label">{_xml(label)}:</span> ' if label else ""
                    parts.append(f"<p>{lead}{_xml(text)}</p>")
        if e.note:
            parts.append(f'<p class="note">{_xml(e.note)}</p>')
    return "".join(parts)


def _docx_para(text: str, style: str = "", bold: bool = False) -> str:
    right = rtl(text)
    ppr = (f'<w:pStyle w:val="{style}"/>' if style else "") + ('<w:bidi/><w:jc w:val="right"/>' if right else "")
    rpr = ("<w:b/>" if bold else "") + ('<w:rtl/><w:rFonts w:cs="Amiri"/><w:szCs w:val="32"/>' if right else "")
    return (f'<w:p><w:pPr>{ppr}</w:pPr><w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{_xml(text)}</w:t>'
            '</w:r></w:p>')


def _section_docx(section: Section) -> str:
    body = [_docx_para(section.heading, "Heading1")] if section.heading else []
    for e in section.entries:
        body.append(_docx_para(e.heading, "Heading2"))
        for label, text in e.paragraphs:
            if text:
                body.append(_docx_para(text if rtl(text) or not label else f"{label}: {text}"))
        if e.note:
            body.append(_docx_para(e.note))
    return "".join(body)


class DocumentWriter:
    """with DocumentWriter(fmt, path, title, subtitle) as w: w.section(s) … — html, md, txt, epub and docx, each
    section written as it comes. Leaving the block by an error (or a stop) removes the half-written file."""

    def __init__(self, fmt: str, path: Path, title: str, subtitle: str = "") -> None:
        if fmt not in ("html", "md", "txt", "epub", "docx"):
            raise ValueError(f"A document is not written as {fmt}.")
        self.fmt, self.path, self.title, self.subtitle = fmt, Path(path), title, subtitle
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._chapters: list[tuple[str, str]] = []
        self._zip = None
        self._file = None
        self._body_path = None
        if fmt == "epub":
            self._zip = zipfile.ZipFile(self.path, "w")
            self._zip.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")   # stored, first (EPUB rule)
        elif fmt == "docx":
            # Word keeps the body in one part: written to a file beside the target piece by piece, zipped at the end
            self._body_path = self.path.with_name(self.path.name + ".part")
            self._file = self._body_path.open("w", encoding="utf-8")
            self._file.write(_docx_para(title, "Title") + (_docx_para(subtitle) if subtitle else ""))
        else:
            self._file = self.path.open("w", encoding="utf-8")
            if fmt == "html":
                self._file.write(f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}"
                                 f"</title><style>{_CSS}</style></head><body><h1>{html.escape(title)}</h1>\n"
                                 + (f"<p class='sub'>{html.escape(subtitle)}</p>\n" if subtitle else ""))
            elif fmt == "md":
                self._file.write("\n".join([f"# {title}", ""] + ([f"*{subtitle}*", ""] if subtitle else [])) + "\n")
            else:
                self._file.write("\n".join([title, "=" * min(len(title), 70), ""] + ([subtitle, ""] if subtitle
                                                                                     else [])) + "\n")

    def __enter__(self) -> "DocumentWriter":
        return self

    def __exit__(self, kind, _value, _tb) -> None:
        if kind is None:
            self.close()
        else:
            self.abort()

    def section(self, section: Section) -> None:
        if self.fmt == "html":
            self._file.write(_section_html(section) + "\n")
        elif self.fmt == "md":
            self._file.write(_section_markdown(section) + "\n")
        elif self.fmt == "txt":
            self._file.write(_section_text(section) + "\n")
        elif self.fmt == "docx":
            self._file.write(_section_docx(section))
        else:
            name = f"c{len(self._chapters) + 1:05}.xhtml"
            heading = section.heading or self.title
            self._zip.writestr(f"OEBPS/{name}", _xhtml(heading, _section_xhtml(section, self.title)),
                               zipfile.ZIP_DEFLATED)
            self._chapters.append((name, heading))

    def close(self) -> Path:
        if self.fmt == "epub":
            self._close_epub()
        elif self.fmt == "docx":
            self._file.close()
            _docx_zip(self.path, self._body_path)
            self._body_path.unlink()
        else:
            if self.fmt == "html":
                self._file.write("</body></html>")
            self._file.close()
        return self.path

    def abort(self) -> None:
        for handle in (self._zip, self._file):
            try:
                if handle is not None:
                    handle.close()
            except Exception:
                pass
        for leftover in (self.path, self._body_path):
            try:
                if leftover is not None and leftover.exists():
                    leftover.unlink()
            except OSError:
                pass

    def _close_epub(self) -> None:
        z = self._zip
        if not self._chapters:
            z.writestr("OEBPS/c00001.xhtml", _xhtml(self.title, f"<h2>{_xml(self.title)}</h2>"), zipfile.ZIP_DEFLATED)
            self._chapters.append(("c00001.xhtml", self.title))
        chapters = self._chapters
        book_id = f"urn:uuid:{uuid.uuid4()}"
        nav = "".join(f'<li><a href="{f}">{_xml(t)}</a></li>' for f, t in chapters)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:'
                   'container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/'
                   'oebps-package+xml"/></rootfiles></container>', zipfile.ZIP_DEFLATED)
        manifest = "".join(f'<item id="c{i}" href="{f}" media-type="application/xhtml+xml"/>'
                           for i, (f, _t) in enumerate(chapters, 1))
        spine = "".join(f'<itemref idref="c{i}"/>' for i in range(1, len(chapters) + 1))
        z.writestr("OEBPS/content.opf",
                   '<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
                   f'unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier '
                   f'id="id">{book_id}</dc:identifier><dc:title>{_xml(self.title)}</dc:title><dc:language>ar'
                   f'</dc:language><meta property="dcterms:modified">{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}'
                   '</meta></metadata><manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
                   f'properties="nav"/>{manifest}</manifest><spine>{spine}</spine></package>', zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", _xhtml(self.title, f'<nav epub:type="toc"><h1>{_xml(self.title)}</h1><ol>{nav}'
                                                         '</ol></nav>'), zipfile.ZIP_DEFLATED)
        z.close()


def document_html(doc: Document) -> str:
    """The whole document as one HTML page (the preview, and the PDF Qt draws from it)."""
    out = [f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(doc.title)}</title>"
           f"<style>{_CSS}</style></head><body><h1>{html.escape(doc.title)}</h1>"]
    if doc.subtitle:
        out.append(f"<p class='sub'>{html.escape(doc.subtitle)}</p>")
    out += [_section_html(section) for section in doc.sections]
    out.append("</body></html>")
    return "\n".join(out)


def document_markdown(doc: Document) -> str:
    out = [f"# {doc.title}", ""] + ([f"*{doc.subtitle}*", ""] if doc.subtitle else [])
    return "\n".join(out + [_section_markdown(section) for section in doc.sections])


def document_text(doc: Document) -> str:
    out = [doc.title, "=" * min(len(doc.title), 70), ""] + ([doc.subtitle, ""] if doc.subtitle else [])
    return "\n".join(out + [_section_text(section) for section in doc.sections])


def write_document(doc: Document, fmt: str, path: Path) -> Path:
    with DocumentWriter(fmt, path, doc.title, doc.subtitle) as w:
        for section in doc.sections:
            w.section(section)
    return Path(path)


def _xhtml(title: str, body: str) -> str:
    return ('<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops"><head><meta charset="utf-8"/>'
            f'<title>{_xml(title)}</title><style>{_CSS}</style></head><body>{body}</body></html>')


def _docx_zip(path: Path, body_path: Path) -> None:
    """The Word file around a body written beforehand (DocumentWriter)."""
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.'
              'openxmlformats.org/wordprocessingml/2006/main">'
              '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:sz '
              'w:val="22"/></w:rPr></w:style>'
              '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="40"/>'
              '</w:rPr></w:style>'
              '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:outlineLvl '
              'w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>'
              '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:pPr><w:outlineLvl '
              'w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style></w:styles>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
                   'content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
                   'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName='
                   '"/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.'
                   'document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.'
                   'openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                   'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/_rels/document.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                   'officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        with z.open("word/document.xml", "w") as out, Path(body_path).open("rb") as body:
            out.write(('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.'
                       'openxmlformats.org/wordprocessingml/2006/main"><w:body>').encode("utf-8"))
            while True:
                chunk = body.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
            out.write(('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" '
                       'w:bottom="1134" w:left="1134"/></w:sectPr></w:body></w:document>').encode("utf-8"))
        z.writestr("word/styles.xml", styles)


# ------------------------------------------------------------------ networks
def write_graph(nodes: list[dict], edges: list[dict], fmt: str, path: Path, title: str = "isnady") -> Path:
    """An isnad network: nodes {id, label, tabaqa, tradition}, edges {source, target, weight} (teacher → student)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "graphml":
        out = ['<?xml version="1.0" encoding="UTF-8"?><graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
               '<key id="label" for="node" attr.name="label" attr.type="string"/>',
               '<key id="arabic" for="node" attr.name="arabic" attr.type="string"/>',
               '<key id="tabaqa" for="node" attr.name="tabaqa" attr.type="int"/>',
               '<key id="tradition" for="node" attr.name="tradition" attr.type="string"/>',
               '<key id="weight" for="edge" attr.name="weight" attr.type="int"/>',
               f'<graph id="{_xml(title)}" edgedefault="directed">']
        for n in nodes:
            out.append(f'<node id="n{n["id"]}"><data key="label">{_xml(n.get("label", ""))}</data><data key="arabic">'
                       f'{_xml(n.get("arabic", ""))}</data><data key="tabaqa">{n.get("tabaqa") or 0}</data>'
                       f'<data key="tradition">{_xml(n.get("tradition", ""))}</data></node>')
        for i, e in enumerate(edges):
            out.append(f'<edge id="e{i}" source="n{e["source"]}" target="n{e["target"]}"><data key="weight">'
                       f'{e["weight"]}</data></edge>')
        out.append("</graph></graphml>")
        path.write_text("\n".join(out), encoding="utf-8")
    elif fmt == "gexf":
        out = ['<?xml version="1.0" encoding="UTF-8"?><gexf xmlns="http://gexf.net/1.3" version="1.3">',
               f'<meta><creator>isnady</creator><description>{_xml(title)}</description></meta>',
               '<graph defaultedgetype="directed"><attributes class="node"><attribute id="0" title="arabic" '
               'type="string"/><attribute id="1" title="tabaqa" type="integer"/><attribute id="2" title="tradition" '
               'type="string"/></attributes><nodes>']
        for n in nodes:
            out.append(f'<node id="{n["id"]}" label="{_xml(n.get("label", ""))}"><attvalues><attvalue for="0" '
                       f'value="{_xml(n.get("arabic", ""))}"/><attvalue for="1" value="{n.get("tabaqa") or 0}"/>'
                       f'<attvalue for="2" value="{_xml(n.get("tradition", ""))}"/></attvalues></node>')
        out.append("</nodes><edges>")
        for i, e in enumerate(edges):
            out.append(f'<edge id="{i}" source="{e["source"]}" target="{e["target"]}" weight="{e["weight"]}"/>')
        out.append("</edges></graph></gexf>")
        path.write_text("\n".join(out), encoding="utf-8")
    elif fmt == "json":
        path.write_text(json.dumps({"schema": "isnady-network/1", "title": title, "nodes": nodes, "edges": edges},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    elif fmt == "csv":
        label = {n["id"]: n.get("label", "") for n in nodes}
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["teacher_id", "teacher", "student_id", "student", "chains"])
        for e in edges:
            w.writerow([e["source"], label.get(e["source"], ""), e["target"], label.get(e["target"], ""), e["weight"]])
        path.write_text(buf.getvalue(), encoding="utf-8-sig")
    else:
        raise ValueError(f"A network is not written as {fmt}.")
    return path
