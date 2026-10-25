"""Statistics out of isnady (EX4): each finding on its own — its chart as an image (PNG, SVG) or a PDF, its figures
as CSV, Excel or JSON — or a whole section, or every section: one PDF, one HTML page (charts and tables), one Excel
workbook with a sheet for each table, the tables as CSV files in a folder, or the computed results as JSON.

Bayram (2026-10-25): "Herseyi disari aktarabilmemiz lazim! Istatistik kismindaki detaylari veya grafikleri ayri ayri
ya da tam disari aktarabilmemiz lazim!!!"

Every card of the Statistics page gets a small ⤓ in its top right corner (added when the card appears, without
touching how the page builds it); the page's own "Export ▾" does a section or all of them.
"""

from __future__ import annotations

import base64
import csv
import html
import json
import os
import time
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QEvent, QIODevice, QMarginsF, QObject, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtWidgets import QFileDialog, QFrame, QMenu, QMessageBox, QToolButton, QWidget

from isnady import __version__
from isnady.core import formats as F
from isnady.core.i18n import tr

ARMED = "_isnady_export_button"


# ------------------------------------------------------------------ the cards of a section
def cards(page: QWidget) -> list[QFrame]:
    """The findings of a section in reading order: each Card that is not inside another Card."""
    found = []
    for frame in page.findChildren(QFrame):
        if frame.objectName() != "Card" or not frame.isVisibleTo(page):
            continue
        parent, inside = frame.parentWidget(), False
        while parent is not None and parent is not page:
            if isinstance(parent, QFrame) and parent.objectName() == "Card":
                inside = True
                break
            parent = parent.parentWidget()
        if not inside:
            found.append(frame)
    return sorted(found, key=lambda f: f.mapTo(page, QPoint(0, 0)).y())


def card_name(card: QFrame) -> str:
    name = getattr(card, "_isnady_name", "")
    if name:
        return name
    from PySide6.QtWidgets import QLabel

    for label in card.findChildren(QLabel):
        text = label.text().strip()
        if text and "<" not in text[:1]:
            return text[:80]
    return "isnady"


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")[:60] or "isnady"


def _hidden_buttons(widget: QWidget):
    """Hide the ⤓ buttons while a picture is taken."""
    buttons = [b for b in widget.findChildren(QToolButton) if getattr(b, ARMED, False)]
    for b in buttons:
        b.hide()
    return buttons


def image(widget: QWidget, scale: float = 2.0) -> QImage:
    """The widget as a picture, sharper than the screen (scale 2)."""
    hidden = _hidden_buttons(widget)
    try:
        size = widget.size()
        img = QImage(QSize(int(size.width() * scale), int(size.height() * scale)), QImage.Format.Format_ARGB32)
        img.setDevicePixelRatio(scale)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        widget.render(painter, QPoint(0, 0))
        painter.end()
        return img
    finally:
        for b in hidden:
            b.show()


def save_png(widget: QWidget, path: str) -> str:
    image(widget).save(path, "PNG")
    return path


def save_svg(widget: QWidget, path: str, title: str = "") -> str:
    from PySide6.QtSvg import QSvgGenerator

    hidden = _hidden_buttons(widget)
    try:
        gen = QSvgGenerator()
        gen.setFileName(path)
        gen.setSize(widget.size())
        gen.setViewBox(QRect(QPoint(0, 0), widget.size()))
        gen.setTitle(title or "isnady")
        gen.setDescription(f"isnady {__version__}")
        painter = QPainter(gen)
        widget.render(painter, QPoint(0, 0))
        painter.end()
    finally:
        for b in hidden:
            b.show()
    return path


def save_pdf(widgets: list[QWidget], path: str, title: str = "", headings: list[str] | None = None) -> str:
    """Widgets one after another on A4 pages, each scaled to the page's width; a new page when one does not fit."""
    writer = QPdfWriter(path)
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
                                     QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter))
    writer.setResolution(150)
    writer.setTitle(title or "isnady")
    writer.setCreator(f"isnady {__version__}")
    page = writer.pageLayout().paintRectPixels(writer.resolution())
    painter = QPainter(writer)
    y = 0
    gap = 24
    for i, widget in enumerate(widgets):
        if headings and i < len(headings) and headings[i]:
            font = painter.font()
            font.setPointSize(13)
            font.setBold(True)
            painter.setFont(font)
            if y and y + 60 > page.height():
                writer.newPage()
                y = 0
            painter.drawText(QRect(0, y, page.width(), 50), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             headings[i])
            y += 60
        img = image(widget, 2.0)
        w = page.width()
        h = int(img.height() / img.width() * w) if img.width() else 0
        if h > page.height():                       # taller than a page: shrunk to fit one
            w = int(w * page.height() / h)
            h = page.height()
        if y and y + h > page.height():
            writer.newPage()
            y = 0
        painter.drawImage(QRect(0, y, w, h), img)
        y += h + gap
    painter.end()
    return path


def _png_data(widget: QWidget) -> str:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image(widget, 1.5).save(buf, "PNG")
    return base64.b64encode(bytes(data)).decode("ascii")


def save_html(sections: list[tuple[str, list[QFrame]]], path: str, title: str) -> str:
    """One page: each section's heading, each finding as a picture with its table under it."""
    out = [f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>"
           "body{font-family:'Noto Sans','Segoe UI',sans-serif;margin:2em auto;max-width:1100px;color:#1d2433}"
           "h1{font-size:1.6em}h2{font-size:1.3em;margin-top:2em;border-bottom:1px solid #ccd}"
           "img{max-width:100%;border:1px solid #e3e6ee;border-radius:10px;margin:.6em 0}"
           "table{border-collapse:collapse;font-size:.85em;margin:.4em 0 1.6em}td,th{border:1px solid #d6dae3;"
           "padding:3px 8px}th{background:#f1f3f8}details{margin-bottom:1.4em}</style></head><body>",
           f"<h1>{html.escape(title)}</h1><p>isnady {__version__} · {time.strftime('%Y-%m-%d %H:%M')}</p>"]
    for heading, items in sections:
        out.append(f"<h2>{html.escape(heading)}</h2>")
        for card in items:
            out.append(f"<img alt='{html.escape(card_name(card))}' src='data:image/png;base64,{_png_data(card)}'>")
            table = getattr(card, "_isnady_table", None)
            if table:
                header, rows = table
                out.append(f"<details><summary>{html.escape(tr('The figures'))} — {html.escape(card_name(card))}"
                           "</summary><table><tr>" + "".join(f"<th>{html.escape(str(h))}</th>" for h in header) + "</tr>")
                for row in rows:
                    out.append("<tr>" + "".join(f"<td>{html.escape(F._cell(v))}</td>" for v in row) + "</tr>")
                out.append("</table></details>")
    out.append("</body></html>")
    Path(path).write_text("\n".join(out), encoding="utf-8")
    return path


def save_table(card: QFrame, fmt: str, path: str) -> str:
    header, rows = card._isnady_table
    name = card_name(card)
    if fmt == "csv":
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        return path
    table = F.Table(name, [str(h) for h in header], [dict(zip([str(h) for h in header], r)) for r in rows],
                    {"isnady": __version__, "kind": "statistics"})
    return str(F.write_table(table, fmt, Path(path)))


def save_workbook(tables: list[tuple[str, list, list]], path: str) -> str:
    sheets = [F.Table(name, [str(h) for h in header], [dict(zip([str(h) for h in header], r)) for r in rows])
              for name, header, rows in tables]
    return str(F.write_workbook(sheets, Path(path)))


def save_csv_folder(tables: list[tuple[str, list, list]], folder: str) -> str:
    os.makedirs(folder, exist_ok=True)
    used: set[str] = set()
    for name, header, rows in tables:
        base = _safe(name)
        n, stem = 1, base
        while stem in used:
            n += 1
            stem = f"{base}-{n}"
        used.add(stem)
        with open(os.path.join(folder, stem + ".csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
    return folder


def save_json(result, path: str) -> str:
    def plain(x):
        if isinstance(x, dict):
            return {str(k): plain(v) for k, v in x.items()}
        if isinstance(x, (list, tuple, set)):
            return [plain(v) for v in x]
        if isinstance(x, float) and (x != x or x in (float("inf"), float("-inf"))):
            return None
        return x if isinstance(x, (str, int, float, bool)) or x is None else str(x)
    Path(path).write_text(json.dumps({"schema": "isnady-statistics/1", "isnady": __version__,
                                      "exported": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": plain(result)},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    return path


# ------------------------------------------------------------------ the ⤓ on each card
class Armer(QObject):
    """Watches the section pages: each new card gets its ⤓, kept in its top right corner when it is resized."""

    def __init__(self, owner: QWidget, pages: list[QWidget]) -> None:
        super().__init__(owner)
        self._owner = owner
        self._pages = pages
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self.arm_all)
        for page in pages:
            page.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt's name)
        kind = event.type()
        if kind in (QEvent.Type.LayoutRequest, QEvent.Type.ChildAdded, QEvent.Type.Show):
            self._timer.start()
        elif kind == QEvent.Type.Resize and isinstance(obj, QFrame) and getattr(obj, ARMED, None):
            self._place(obj)
        return False

    def arm_all(self) -> None:
        for page in self._pages:
            for card in cards(page):
                if getattr(card, ARMED, None) is None:
                    self._arm(card)
                else:
                    self._place(card)

    def _place(self, card: QFrame) -> None:
        button = getattr(card, ARMED)
        try:
            button.move(card.width() - button.width() - 10, 8)
            button.raise_()
        except RuntimeError:
            pass

    def _arm(self, card: QFrame) -> None:
        button = QToolButton(card)
        setattr(button, ARMED, True)
        button.setText("⤓")
        button.setToolTip(tr("Export this finding: its chart as a picture or PDF, its figures as a table"))
        button.setAutoRaise(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setFixedSize(30, 26)
        menu = QMenu(button)
        menu.aboutToShow.connect(lambda c=card, m=menu: self._fill(c, m))
        button.setMenu(menu)
        setattr(card, ARMED, button)
        card.installEventFilter(self)
        button.show()
        self._place(card)

    def _fill(self, card: QFrame, menu: QMenu) -> None:
        menu.clear()
        name = card_name(card)
        menu.addAction(tr("Picture (PNG)…"), lambda: self._ask(card, name, "png"))
        menu.addAction(tr("Vector picture (SVG)…"), lambda: self._ask(card, name, "svg"))
        menu.addAction(tr("PDF…"), lambda: self._ask(card, name, "pdf"))
        menu.addAction(tr("Copy as a picture"), lambda: QGuiApplication.clipboard().setImage(image(card)))
        if getattr(card, "_isnady_table", None):
            menu.addSeparator()
            for fmt, label in (("csv", tr("Figures (CSV)…")), ("xlsx", tr("Figures (Excel)…")),
                               ("json", tr("Figures (JSON)…")), ("md", tr("Figures (Markdown)…"))):
                menu.addAction(label, lambda f=fmt: self._ask(card, name, f))

    def _ask(self, card: QFrame, name: str, fmt: str) -> None:
        ext = {"png": "png", "svg": "svg", "pdf": "pdf", "csv": "csv", "xlsx": "xlsx", "json": "json", "md": "md"}[fmt]
        start = os.path.join(os.path.expanduser("~"), f"isnady-{_safe(name)}.{ext}")
        path, _f = QFileDialog.getSaveFileName(self._owner, tr("Export"), start, f"{ext.upper()} (*.{ext})")
        if not path:
            return
        try:
            if fmt == "png":
                save_png(card, path)
            elif fmt == "svg":
                save_svg(card, path, name)
            elif fmt == "pdf":
                save_pdf([card], path, name)
            else:
                save_table(card, fmt, path)
        except Exception as exc:                     # said, never a crash
            QMessageBox.warning(self._owner, tr("Export"), f"{type(exc).__name__}: {exc}")
            return
        from isnady.core import log

        log.get("export").info("✔ statistics: %s → %s", name, path)
