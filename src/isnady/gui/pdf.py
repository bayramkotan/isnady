"""PDF from HTML (EX1): Qt draws the page, so Arabic is joined and set right to left as on the screen. Used by
File → Export… and by `iy export … --format pdf` (which starts Qt without a window)."""

from __future__ import annotations

from pathlib import Path


def html_to_pdf(html: str, path: str | Path) -> Path:
    import os

    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QGuiApplication, QPageLayout, QPageSize, QPdfWriter, QTextDocument

    if QGuiApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")      # the command line: no window, no screen needed
        html_to_pdf._app = QGuiApplication([])
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(path))
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
                                     QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter))
    writer.setResolution(110)
    writer.setTitle(path.stem)
    writer.setCreator("isnady")
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    doc.setHtml(html)
    layout = writer.pageLayout().paintRectPixels(writer.resolution())
    doc.setPageSize(QSizeF(layout.width(), layout.height()))
    doc.print_(writer)
    return path
