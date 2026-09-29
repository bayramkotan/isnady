"""Isnad Chains page: one hadith's chain drawn as a timeline, the Arabic text
with the chain and the text (matn) told apart, and per-book statistics.

Every fact shown comes from isnady.core.isnad.
"""

import html
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from isnady.core import isnad as core_isnad
from isnady.core import search as core_search
from isnady.gui import theme
from isnady.gui.chain_widgets import PROPHET, ChainNode
from isnady.gui.widgets import expanding_width_policy

COLUMN_MAX = 1000


def _label(text: str = "", name: str = "", wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if wrap:
        label.setSizePolicy(expanding_width_policy())
    return label


class IsnadPage(QWidget):
    def __init__(self, connection_getter, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._conn_of = connection_getter          # the Search page owns the connection
        self._current: dict | None = None

        self.book_combo = QComboBox()
        self.book_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.number_edit = QLineEdit()
        self.number_edit.setObjectName("NumberField")
        self.number_edit.setPlaceholderText("Hadith number")
        self.number_edit.setFixedWidth(150)
        self.number_edit.returnPressed.connect(self._go)
        go = QPushButton("Show chain")
        go.setObjectName("Primary")
        go.setCursor(Qt.CursorShape.PointingHandCursor)
        go.clicked.connect(self._go)
        self.prev_button = QPushButton("‹  Previous")
        self.next_button = QPushButton("Next  ›")
        for b in (self.prev_button, self.next_button):
            b.setObjectName("Quiet")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_button.clicked.connect(lambda: self._step("prev"))
        self.next_button.clicked.connect(lambda: self._step("next"))

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(_label("Book", "FilterLabel"))
        top.addWidget(self.book_combo)
        top.addSpacing(8)
        top.addWidget(_label("Number", "FilterLabel"))
        top.addWidget(self.number_edit)
        top.addWidget(go)
        top.addStretch(1)
        top.addWidget(self.prev_button)
        top.addWidget(self.next_button)

        self.body = QWidget()
        self.body.setObjectName("ResultsBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 8, 8, 28)
        self.body_layout.setSpacing(0)
        scroll = QScrollArea()
        scroll.setObjectName("Results")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.body)
        self.scroll = scroll

        column = QWidget()
        column.setMaximumWidth(COLUMN_MAX)
        inner = QVBoxLayout(column)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(14)
        inner.addLayout(top)
        inner.addWidget(scroll, 1)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(36, 28, 28, 12)
        layout.addWidget(column, 1, Qt.AlignmentFlag.AlignHCenter)

    # ------------------------------------------------------------- helpers
    @property
    def conn(self) -> sqlite3.Connection | None:
        return self._conn_of()

    def refresh(self) -> None:
        """Fill the book list and show either the current hadith or the overview."""
        if self.conn is None:
            return
        current = self.book_combo.currentData()
        self.book_combo.blockSignals(True)
        self.book_combo.clear()
        for key, name, count in core_search.list_collections(self.conn):
            self.book_combo.addItem(f"{name} ({count:,})", key)
        self.book_combo.setCurrentIndex(max(self.book_combo.findData(current), 0))
        self.book_combo.blockSignals(False)
        if self._current:
            self.show_hadith(self._current["id"])
        else:
            self._show_overview()

    def _clear(self, layout=None) -> None:
        """Empty the page, including widgets inside nested layouts."""
        layout = layout or self.body_layout
        while layout.count():
            item = layout.takeAt(0)
            widget, child = item.widget(), item.layout()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif child is not None:
                self._clear(child)

    def _go(self) -> None:
        book, number = self.book_combo.currentData(), self.number_edit.text().strip()
        if not book or not number or self.conn is None:
            return
        hid = core_isnad.hadith_id(self.conn, book, number)
        if hid is None:
            self._clear()
            msg = _label(f"There is no hadith {html.escape(number)} in this book.", "Lead", wrap=True)
            self.body_layout.addWidget(msg)
            self.body_layout.addStretch(1)
            return
        self.show_hadith(hid)

    def _step(self, direction: str) -> None:
        if self._current and self._current.get(direction):
            self.show_hadith(self._current[direction])

    # --------------------------------------------------------------- views
    def _show_overview(self) -> None:
        self._clear()
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
        title = _label("Chains of transmission", "Hero")
        title.setFont(theme.reading_font(28, bold=True))
        lead = _label(
            "Every chain below was read from the Arabic text: who narrated to whom, with which words, and whether "
            "the chain reaches the Prophet. Names are shown exactly as written. Where the wording could not be "
            "read with confidence, the chain is kept whole and not split, so nothing is guessed. "
            "Choose a book and a number, or open a chain from a search result.",
            "Lead", wrap=True)
        self.body_layout.addWidget(title)
        self.body_layout.addSpacing(6)
        self.body_layout.addWidget(lead)
        self.body_layout.addSpacing(18)
        if self.conn is not None:
            for b in core_isnad.book_stats(self.conn):
                self.body_layout.addWidget(self._stats_card(b))
                self.body_layout.addSpacing(12)
        self.body_layout.addStretch(1)

    def _stats_card(self, b: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(24, 18, 24, 18)
        box.setSpacing(8)
        name = _label(b["name"], "CardTitle")
        name.setFont(theme.reading_font(16, bold=True))
        box.addWidget(name)
        numbers = QHBoxLayout()
        numbers.setSpacing(28)
        split_pct = 100 * b["split"] / b["chains"] if b["chains"] else 0
        marfu_pct = 100 * b["marfu"] / b["split"] if b["split"] else 0
        avg = b["links"] / b["split"] if b["split"] else 0
        for value, caption in ((f"{b['chains']:,}", "chains read"), (f"{split_pct:.1f}%", "split into narrators"),
                               (f"{marfu_pct:.1f}%", "of those reach the Prophet"), (f"{avg:.1f}", "narrators per chain")):
            cell = QVBoxLayout()
            cell.setSpacing(0)
            v = _label(value, "StatValue")
            cell.addWidget(v)
            cell.addWidget(_label(caption, "Caption"))
            numbers.addLayout(cell)
        numbers.addStretch(1)
        box.addLayout(numbers)
        if b["problems"]:
            lines = "<br>".join(f"{n:,} &nbsp;{html.escape(p)}" for p, n in b["problems"])
            kept = _label(f"<span style='font-weight:600'>Kept whole, not split:</span><br>{lines}", "Caption", wrap=True)
            kept.setTextFormat(Qt.TextFormat.RichText)
            box.addWidget(kept)
        return card

    def show_hadith(self, hid: int) -> None:
        if self.conn is None:
            return
        info = core_isnad.describe(self.conn, hid)
        if info is None:
            self._current = None
            self._show_overview()
            return
        self._current = info
        index = self.book_combo.findData(info["book"])
        if index >= 0:
            self.book_combo.blockSignals(True)
            self.book_combo.setCurrentIndex(index)
            self.book_combo.blockSignals(False)
        self.number_edit.setText(info["number"])
        self.prev_button.setEnabled(info["prev"] is not None)
        self.next_button.setEnabled(info["next"] is not None)

        self._clear()
        chains = core_isnad.chain(self.conn, hid)
        chain = chains[0] if chains else None

        head = QHBoxLayout()
        title = _label(info["book_name"], "Hero")
        title.setFont(theme.reading_font(24, bold=True))
        number = _label(f"hadith {info['number']}", "CardNumber")
        head.addWidget(title)
        head.addSpacing(10)
        head.addWidget(number, 0, Qt.AlignmentFlag.AlignBaseline)
        head.addStretch(1)
        self.body_layout.addLayout(head)

        verdict = self._verdict(chain)
        self.body_layout.addWidget(verdict)
        self.body_layout.addSpacing(16)

        if chain and chain["links"]:
            self.body_layout.addWidget(ChainNode(info["book_name"], "The compiler's book, where the chain begins",
                                                 first=True, latin=True))
            for link in chain["links"]:
                self.body_layout.addWidget(ChainNode(core_isnad.short_name(link["raw_name"]), "",
                                                     link["transmission"], full_name=link["raw_name"]))
            if chain["reaches_prophet"]:
                self.body_layout.addWidget(ChainNode(PROPHET, "The Messenger of God", None, last=True, prophet=True))
        self.body_layout.addSpacing(18)

        text = core_isnad.arabic_text(self.conn, hid)
        if text:
            self.body_layout.addWidget(self._text_card(text, chain))
        self.body_layout.addStretch(1)
        self.scroll.verticalScrollBar().setValue(0)

    def _verdict(self, chain: dict | None) -> QLabel:
        if chain is None:
            text = "No Arabic text for this hadith, so no chain was read."
        elif chain["problem"]:
            text = (f"This chain was kept whole and not split: {chain['problem']}. "
                    "The full wording is shown below.")
        elif chain["reaches_prophet"]:
            n = len(chain["links"])
            text = f"{n} narrator{'s' if n != 1 else ''} between the compiler and the Prophet, as read from the text."
        else:
            text = ("The chain as read stops before the Prophet: the report may be from a Companion or a later "
                    "narrator, or the last link could not be read with confidence.")
        label = _label(text, "Lead", wrap=True)
        return label

    def _text_card(self, text: str, chain: dict | None) -> QFrame:
        t = theme.current()
        split_known = bool(chain and chain["links"] and not chain["problem"])
        isnad_part, matn = core_isnad.split_text(text, chain["raw"] if split_known else None)
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(26, 18, 26, 18)
        box.setSpacing(6)
        caption = _label("The chain in lighter ink, the text of the hadith (matn) in full ink" if split_known
                         else "The full wording as written; the chain was not separated from the text",
                         "Caption", wrap=True)
        body = _label(
            f"<div dir='rtl' align='right' style='line-height:125%'>"
            f"<span style='color:{t.muted}'>{html.escape(isnad_part)}</span>"
            f"<span style='color:{t.ink}'>{html.escape(matn)}</span></div>", "ArabicText", wrap=True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setFont(theme.reading_font(20, scaled=True))
        body.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute | Qt.AlignmentFlag.AlignTop)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(caption)
        box.addWidget(body)
        return card

    def retheme(self) -> None:
        if self._current:
            self.show_hadith(self._current["id"])
        else:
            self._show_overview()
