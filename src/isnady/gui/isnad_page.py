"""Isnad Chains page: one hadith's chain drawn as a timeline, the Arabic text
with the chain and the text (matn) told apart, and per-book statistics.

Every fact shown comes from isnady.core.isnad.
"""

import html
import sqlite3

from PySide6.QtCore import Signal, Qt
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
from isnady.core import narrators as core_narrators
from isnady.core.i18n import n_, tr
from isnady.gui import theme
from isnady.core import traditions
from isnady.gui.chain_widgets import ChainNode, end_chip
from isnady.gui.widgets import TextBlock, expanding_width_policy



def _label(text: str = "", name: str = "", wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if wrap:
        label.setSizePolicy(expanding_width_policy())
    return label


class IsnadPage(QWidget):
    open_narrator = Signal(int)      # person id → Narrators page

    def __init__(self, connection_getter, parent=None) -> None:
        super().__init__(parent)
        self._tradition = "sunni"
        self.setObjectName("Page")
        self._conn_of = connection_getter          # the Search page owns the connection
        self._current: dict | None = None

        self.book_combo = QComboBox()
        self.book_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.number_edit = QLineEdit()
        self.number_edit.setObjectName("NumberField")
        self.number_edit.setPlaceholderText(tr("Hadith number"))
        self.number_edit.setFixedWidth(150)
        self.number_edit.returnPressed.connect(self._go)
        go = QPushButton(tr("Show chain"))
        go.setObjectName("Primary")
        go.setCursor(Qt.CursorShape.PointingHandCursor)
        go.clicked.connect(self._go)
        self.prev_button = QPushButton(tr("‹  Previous"))
        self.next_button = QPushButton(tr("Next  ›"))
        for b in (self.prev_button, self.next_button):
            b.setObjectName("Quiet")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_button.clicked.connect(lambda: self._step("prev"))
        self.next_button.clicked.connect(lambda: self._step("next"))

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(_label(tr("Book"), "FilterLabel"))
        top.addWidget(self.book_combo)
        top.addSpacing(8)
        top.addWidget(_label(tr("Number"), "FilterLabel"))
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
        # the column follows the window (Bayram, 2026-10-04: like the Narrators page), with margins only
        inner = QVBoxLayout(column)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(14)
        inner.addLayout(top)
        inner.addWidget(scroll, 1)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(36, 28, 28, 12)
        layout.addWidget(column, 1)          # no alignment: an aligned widget keeps its own width and does not follow the window

    # ------------------------------------------------------------- helpers
    @property
    def conn(self) -> sqlite3.Connection | None:
        return self._conn_of()

    def refresh(self) -> None:
        """Fill the book list and show either the current hadith or the overview."""
        if self.conn is None:
            return
        from isnady.gui.widgets import fill_book_combo

        fill_book_combo(self.book_combo, self.conn)
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
            # say how this book numbers its hadith: al-Kafi and 'Uyun count volume:hadith ("5:1740"), not "1740"
            sample = [r[0] for r in self.conn.execute(
                "SELECT h.number FROM hadiths h JOIN collections c ON c.id = h.collection_id WHERE c.key = ? "
                "ORDER BY h.number_sort LIMIT 3", (book,))]
            hint = (" " + tr("Its numbers are written like {sample} …", sample=", ".join(html.escape(x) for x in sample))
                    + (" — " + tr("volume:hadith.") if any(":" in x for x in sample) else "")) if sample else ""
            msg = _label(tr("There is no hadith {number} in this book.{hint}", number=html.escape(number), hint=hint), "Lead", wrap=True)
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
        title = _label(tr("Chains of transmission"), "Hero")
        title.setFont(theme.reading_font(28, bold=True))
        lead = _label(
            tr("Every chain below was read from the Arabic text: who narrated to whom, with which words, and whom "
              "it reaches. Each book is read along the road of its own tradition: a Sunni book's chain ends at "
              "the Prophet ﷺ and its narrators are identified in Ibn Hajar's Taqrib; a Shia book's chain is read "
              "the Shia way, ends at a Ma'sum and its narrators are identified in al-Najashi. Names are shown "
              "exactly as written. Where the wording could not be read with confidence, the chain is kept whole "
              "and not split, so nothing is guessed. Choose a book and a number, or open a chain from a search "
              "result."),
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
        shia = b.get("tradition") == "shia"
        top = QHBoxLayout()
        name = _label(b["name"], "CardTitle")
        name.setFont(theme.reading_font(16, bold=True))
        top.addWidget(name)
        if shia:
            tag = QLabel(tr("Shia"))
            tag.setObjectName("TagGold")
            top.addSpacing(8)
            top.addWidget(tag, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch(1)
        box.addLayout(top)
        numbers = QHBoxLayout()
        numbers.setSpacing(28)
        split_pct = 100 * b["split"] / b["chains"] if b["chains"] else 0
        marfu_pct = 100 * b["marfu"] / b["split"] if b["split"] else 0
        avg = b["links"] / b["split"] if b["split"] else 0
        cells = [(f"{b['chains']:,}", tr("chains read")), (f"{split_pct:.1f}%", tr("split into narrators")),
                 (f"{marfu_pct:.1f}%", tr("of those reach a Ma'sum") if shia else tr("of those reach the Prophet")),
                 (f"{avg:.1f}", tr("narrators per chain"))]
        known = self.conn.execute(
            """SELECT COUNT(*), SUM(l.person_id IS NOT NULL), SUM(l.candidates IS NOT NULL) FROM isnad_links l
               JOIN isnads i ON i.id = l.isnad_id JOIN hadiths h ON h.id = i.hadith_id
               JOIN collections c ON c.id = h.collection_id WHERE c.key = ? AND i.problem IS NULL""", (b["key"],)
        ).fetchone()
        if known and known[2]:
            cells.append((f"{100 * (known[1] or 0) / known[0]:.1f}%",
                          tr("identified in al-Najashi") if shia else tr("identified in the Taqrib")))
        for value, caption in cells:
            cell = QVBoxLayout()
            cell.setSpacing(0)
            v = _label(value, "StatValue")
            cell.addWidget(v)
            cell.addWidget(_label(caption, "Caption"))
            numbers.addLayout(cell)
        numbers.addStretch(1)
        box.addLayout(numbers)
        if b["problems"]:
            lines = "<br>".join(f"{n:,} &nbsp;{html.escape(tr(p))}" for p, n in b["problems"])
            kept = _label(tr("<span style='font-weight:600'>Kept whole, not split:</span><br>{lines}", lines=lines), "Caption", wrap=True)
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
        number = _label(tr("hadith {number}", number=info["number"]), "CardNumber")
        head.addWidget(title)
        head.addSpacing(10)
        head.addWidget(number, 0, Qt.AlignmentFlag.AlignBaseline)
        self._tradition = traditions.of_collection(self.conn, info["book"])
        if self._tradition == "shia":
            tag = QLabel(tr("Shia — read the Shia way"))
            tag.setObjectName("TagGold")
            tag.setToolTip(tr("Road B: the teacher named without a term, al-Kulayni's groups, the chain ending at a Ma'sum; the "
                             "narrators identified only in the Shia rijal works and judged in the Imami terms."))
            head.addSpacing(10)
            head.addWidget(tag, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addStretch(1)
        self.body_layout.addLayout(head)

        verdict = self._verdict(chain)
        self.body_layout.addWidget(verdict)
        self.body_layout.addSpacing(16)

        if chain and chain["links"]:
            self.body_layout.addWidget(ChainNode(info["book_name"], tr("The compiler's book, where the chain begins"),
                                                 first=True, latin=True))
            links = chain["links"]
            for i, link in enumerate(links):
                person = core_narrators.describe(self.conn, link["person_id"]) if link.get("person_id") else None
                nxt = links[i + 1]["raw_name"] if i + 1 < len(links) else ""
                self.body_layout.addWidget(ChainNode(core_isnad.short_name(link["raw_name"]), "",
                                                     link["transmission"], full_name=link["raw_name"],
                                                     person=person, candidates=link.get("candidates"),
                                                     on_person=self.open_narrator.emit,
                                                     note=core_isnad.link_note(link["raw_name"], nxt)))
            if chain["reaches_prophet"] or chain.get("ends_with"):
                key = chain.get("ends_with") or "prophet"
                subtitle = tr("The Messenger of God") if key == "prophet" else core_isnad.end_label(chain)
                self.body_layout.addWidget(ChainNode(end_chip(chain), subtitle, None, last=True, prophet=True))
            elif chain.get("raised"):
                # "رفعه": the narrator raises it to the Ma'sum without the links between — a gap, shown as one
                self.body_layout.addWidget(ChainNode("رفعه", tr("Raised (marfu'): the rest of the chain is left out — "
                                                        "whom it reaches is not named"), None, last=True))
        self.body_layout.addSpacing(18)

        text = core_isnad.arabic_text(self.conn, hid)
        if text:
            self.body_layout.addWidget(self._text_card(text, chain))
        self.body_layout.addStretch(1)
        self.scroll.verticalScrollBar().setValue(0)

    def _verdict(self, chain: dict | None) -> QLabel:
        if chain is None:
            text = tr("No Arabic text for this hadith, so no chain was read.")
        elif chain["problem"]:
            text = tr("This chain was kept whole and not split: {reason}. The full wording is shown below.",
                      reason=tr(chain["problem"]))
        elif self._tradition == "shia" and chain["links"]:
            # road B: the chain is read in the Shia way and ends at one of the Fourteen Ma'sumun
            n = len(chain["links"])
            known = sum(1 for link in chain["links"] if link.get("person_id"))
            end = core_isnad.end_label(chain)
            if end:
                text = n_("Read as a Shia chain: {n} link between the compiler and {end}.",
                          "Read as a Shia chain: {n} links between the compiler and {end}.", n, end=end)
            elif chain.get("raised"):
                text = n_("Read as a Shia chain: {n} link, then raised (رفعه) without the rest of its links — a gap "
                          "(marfu' in the Imami usage): whom it reaches is not named.",
                          "Read as a Shia chain: {n} links, then raised (رفعه) without the rest of its links — a gap "
                          "(marfu' in the Imami usage): whom it reaches is not named.", n)
            else:
                text = n_("Read as a Shia chain: {n} link; it stops before a Ma'sum is named (maqtu', or the last "
                          "link could not be read with confidence).",
                          "Read as a Shia chain: {n} links; it stops before a Ma'sum is named (maqtu', or the last "
                          "link could not be read with confidence).", n)
            if any(link.get("candidates") is not None for link in chain["links"]):
                text += " " + tr("{known} of them identified in the Shia rijal works (al-Najashi …).", known=known)
            from isnady.core.normalize import normalize

            if "جميعا" in normalize(chain.get("raw") or ""):
                text += " " + tr("A second road joins it (\"jami'an\"); the first road is drawn.")
        elif chain["reaches_prophet"]:
            n = len(chain["links"])
            known = sum(1 for link in chain["links"] if link.get("person_id"))
            text = n_("{n} narrator between the compiler and the Prophet, as read from the text.",
                      "{n} narrators between the compiler and the Prophet, as read from the text.", n)
            if any(link.get("candidates") is not None for link in chain["links"]):
                text += " " + tr("{known} of them identified in Ibn Hajar's Taqrib al-Tahdhib.", known=known)
        else:
            text = tr("The chain as read stops before the Prophet: the report may be from a Companion or a later "
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
        caption = _label(tr("The chain in lighter ink, the text of the hadith (matn) in full ink") if split_known
                         else tr("The full wording as written; the chain was not separated from the text"),
                         "Caption", wrap=True)
        body = TextBlock(
            f"<div dir='rtl' align='right' style='line-height:{theme.script_line_height('arabic')}%'>"
            f"<span style='color:{t.muted}'>{html.escape(isnad_part)}</span>"
            f"<span style='color:{theme.script_color('arabic')}'>{html.escape(matn)}</span></div>",
            theme.script_font("arabic"), rtl=True)
        box.addWidget(caption)
        box.addWidget(body)
        return card

    def retheme(self) -> None:
        if self._current:
            self.show_hadith(self._current["id"])
        else:
            self._show_overview()
