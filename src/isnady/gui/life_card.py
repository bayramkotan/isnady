"""The card of a life (BIO2): on the Narrators and Hadith Scholars pages.

A written life (core.lives, assets/lives): its kind, the facts at a glance (full name, birth, death, family, …),
the life told in a few paragraphs, the works it is summarised from. Every other narrator: the same card, filled from
what the rijal work and the imported chains say of him.
"""

from __future__ import annotations

import re

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from isnady.core.i18n import tr
from isnady.gui import theme


def _label(text: str, name: str = "", rich: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def _names(text: str) -> list[str]:
    """The names of a "Teachers" or "Students" fact, as written: split at the commas, without "more than a thousand:"
    or the closing "…"."""
    import re

    body = text.split(":", 1)[1] if ":" in text[:40] else text
    parts = [p.strip(" .…") for p in re.split(r"[,،;؛]", body.replace("...", "…"))]
    return [p for p in parts if p and len(p) > 2]


def life_card(life: dict, written: bool, open_book=None, open_name=None) -> QFrame:
    """life: core.lives.view() or core.lives.read(); written: a life written for isnady. open_book(key), when given,
    opens a book of isnady named under "Read more" (al-Shama'il under the Prophet's life ﷺ)."""
    t = theme.current()
    card = QFrame()
    card.setObjectName("Card")
    box = QVBoxLayout(card)
    box.setContentsMargins(20, 14, 20, 16)
    box.setSpacing(10)

    head = QHBoxLayout()
    title = QLabel(tr("Life"))
    title.setObjectName("CardTitle")
    title.setFont(theme.reading_font(14, bold=True))
    head.addWidget(title)
    if written and life.get("title"):
        name = QLabel(life["title"])
        name.setWordWrap(True)
        name.setFont(theme.reading_font(14))
        name.setStyleSheet(f"color: {t.muted};")
        head.addWidget(name)
    if life.get("kind"):
        kind = QLabel(life["kind"])
        kind.setObjectName("TagGold" if life.get("road") == "shia" or written else "TagMuted")
        head.addWidget(kind)
    head.addStretch(1)
    box.addLayout(head)

    if life.get("facts"):
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        keys = life.get("fact_keys") or []
        for row, (label, value) in enumerate(life["facts"]):
            key = QLabel(label)
            key.setStyleSheet(f"color: {t.gold}; font-weight: 600;")
            key.setAlignment(Qt.AlignmentFlag.AlignTop)
            grid.addWidget(key, row, 0, Qt.AlignmentFlag.AlignTop)
            fact = keys[row] if row < len(keys) else ""
            if open_name is not None and fact in ("teachers", "students") and _names(value):
                # each teacher and student opens among the narrators (2026-10-18: "hâlâ tıklanmayan yerler var")
                import html as _html

                linked = value
                for name in sorted(_names(value), key=len, reverse=True):
                    linked = linked.replace(name, f"\x00{name}\x01", 1)
                linked = _html.escape(linked)
                linked = re.sub("\x00(.*?)\x01", lambda m: f"<a href='{_html.escape(m.group(1), quote=True)}' "
                                f"style='color:{t.lapis}; text-decoration:none'>{m.group(1)}</a>", linked)
                text = _label(linked)
                text.setTextFormat(Qt.TextFormat.RichText)
                text.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
                text.setToolTip(tr("Click a name to look for him among the narrators"))
                text.linkActivated.connect(lambda name, go=open_name: go(name))
                grid.addWidget(text, row, 1)
                continue
            text = _label(value)
            grid.addWidget(text, row, 1)
        grid.setColumnStretch(1, 1)
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background: {t.lapis_soft}; border-radius: 8px; }}"
                            f" QLabel {{ background: transparent; }}")
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(14, 10, 14, 10)
        inner.addLayout(grid)
        box.addWidget(frame)

    font = theme.reading_font(12.5)
    for paragraph in life.get("paragraphs", []):
        text = _label(paragraph)
        text.setFont(font)
        text.setStyleSheet(f"color: {t.ink}; line-height: 140%;")
        box.addWidget(text)

    reads = [r for r in life.get("read", []) if r.get("text") and (r.get("url") or (r.get("book") and open_book))]
    if reads:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        more = QLabel(tr("Read more"))
        more.setStyleSheet(f"color: {t.gold}; font-weight: 600;")
        box.addWidget(more)
        for i, r in enumerate(reads):
            # a label with a link, not a button: a long title wraps instead of widening the card
            mark = "📖 " if r.get("book") else "↗ "
            link = QLabel(f"{mark}<a href='{i}' style='color:{t.lapis}; text-decoration:none'>{html.escape(r['text'])}</a>")
            link.setTextFormat(Qt.TextFormat.RichText)
            link.setWordWrap(True)
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            if r.get("url"):
                link.setToolTip(r["url"])

            def follow(_href, r=r):
                if r.get("book") and open_book:
                    open_book(r["book"])
                elif r.get("url"):
                    QDesktopServices.openUrl(QUrl(r["url"]))
            link.linkActivated.connect(follow)
            box.addWidget(link)
    for entry in life.get("entries", []):
        box.addWidget(SourceEntry(entry))
    if life.get("sources"):
        sources = _label("<b>" + html.escape(tr("Sources")) + ":</b> " + " · ".join(html.escape(s) for s in life["sources"]),
                         "Caption", rich=True)
        box.addWidget(sources)
    return card


class SourceEntry(QFrame):
    """The entry of a classical work a written life is summarised from, in its author's words (BIO2b): al-Dhahabi's
    Siyar. Downloaded once on request (core.source_entries); folded to its opening, unfolded on a click."""

    def __init__(self, entry: dict, parent=None) -> None:
        from PySide6.QtWidgets import QPushButton

        super().__init__(parent)
        self._entry = entry
        self._thread = None
        t = theme.current()
        self.setStyleSheet(f"SourceEntry {{ border-left: 3px solid {t.gold}; }}")
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(12, 4, 0, 4)
        self._box.setSpacing(6)
        head = QLabel(f"<b>{html.escape(tr('In the source'))}:</b> {html.escape(entry['title'])}, {html.escape(entry['where'])}")
        head.setTextFormat(Qt.TextFormat.RichText)
        head.setWordWrap(True)
        head.setStyleSheet(f"color: {t.gold};")
        self._box.addWidget(head)
        self._body = QVBoxLayout()
        self._box.addLayout(self._body)
        self._QPushButton = QPushButton
        self._fill()

    def _clear(self) -> None:
        while self._body.count():
            w = self._body.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _fill(self) -> None:
        from isnady.core import source_entries

        self._clear()
        e = self._entry
        found = source_entries.entry(e["work"], e["volume"], e["number"])
        if found is None:
            if source_entries.available(e["work"]):
                self._body.addWidget(_label(tr("This entry is not in the downloaded copy."), "Caption"))
                return
            size = source_entries.WORKS[e["work"]]["size_mb"]
            note = _label(tr("Read his entry in the author's own words (Arabic): the work is downloaded once from the "
                             "OpenITI corpus (about {mb} MB) and kept on this computer.", mb=size), "Caption")
            self._body.addWidget(note)
            get = self._QPushButton(tr("Download {work}", work=e["title"]))
            get.setObjectName("Link")
            get.setCursor(Qt.CursorShape.PointingHandCursor)
            get.clicked.connect(self._download)
            self._body.addWidget(get, 0, Qt.AlignmentFlag.AlignLeft)
            return
        heading = QLabel(found["heading"])
        heading.setFont(theme.script_font("arabic", bold=True, factor=0.8))
        heading.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
        heading.setWordWrap(True)
        self._body.addWidget(heading)
        whole = found["text"]
        short = whole if len(whole) <= 900 else whole[:900].rsplit(" ", 1)[0] + " …"
        text = QLabel(short)
        text.setFont(theme.script_font("arabic", factor=0.7))
        text.setStyleSheet(f"color: {theme.script_color('arabic')};")
        text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
        text.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._body.addWidget(text)
        if short != whole:
            more = self._QPushButton(tr("Show the whole entry ({n:,} words)", n=len(whole.split())))
            more.setObjectName("Link")
            more.setCursor(Qt.CursorShape.PointingHandCursor)

            def toggle(_c=False, label=text, button=more):
                full = label.text() == short
                label.setText(whole if full else short)
                button.setText(tr("Show less") if full else tr("Show the whole entry ({n:,} words)", n=len(whole.split())))
            more.clicked.connect(toggle)
            self._body.addWidget(more, 0, Qt.AlignmentFlag.AlignLeft)

    def _download(self) -> None:
        from PySide6.QtCore import QObject, QThread, Signal

        class Job(QObject):
            done = Signal(str)

            def __init__(self, work):
                super().__init__()
                self.work = work

            def run(self):
                from isnady.core import source_entries

                try:
                    source_entries.fetch(self.work)
                    self.done.emit("")
                except Exception as exc:          # shown under the button, never a silent failure
                    self.done.emit(f"{type(exc).__name__}: {exc}")

        self._clear()
        self._body.addWidget(_label(tr("Downloading… (it is kept on this computer; the other lives will use it too)"),
                                    "Caption"))
        self._thread = QThread(self)
        self._job = Job(self._entry["work"])
        self._job.moveToThread(self._thread)
        self._thread.started.connect(self._job.run)
        self._job.done.connect(self._downloaded)
        self._job.done.connect(self._thread.quit)
        self._thread.start()

    def _downloaded(self, error: str) -> None:
        if error:
            self._clear()
            self._body.addWidget(_label(tr("Could not download: {error}", error=error), "Caption"))
            return
        self._fill()
