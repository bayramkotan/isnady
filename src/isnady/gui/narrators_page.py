"""Narrators: every narrator of the imported rijal works, searchable and filterable, with what the rijal
work says of him and what the imported chains show — whom he narrates from, who narrates from him, and the
hadith whose chains include him."""

import html

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from isnady.core import narrators as core_narrators
from isnady.core import shia_rijal
from isnady.core.names import latin
from isnady.core.rijal import BOOK_MARKS, RANK_LABELS, TABAQA_LABELS, display_name, short_name
from isnady.gui import theme
from isnady.gui.widgets import FlowLayout

LIST_LIMIT = 200
SHIA_COLOR = {1: 2, 2: 4, 3: 5, 4: 9}   # the Shia categories drawn in the rank colours of like standing
ROW_TEXT_WIDTH = 340        # the list is 420 wide; rows keep inside it


def _label(text: str, name: str = "", wrap: bool = True, rich: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if rich:
        label.setTextFormat(Qt.TextFormat.RichText)
    return label


def _arabic(text: str, factor: float, bold: bool = False, muted: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
    color = theme.current().muted if muted else theme.script_color("arabic")
    label.setStyleSheet(f"color: {color}; {theme.font_css(theme.script_font('arabic', bold=bold, factor=factor))}")
    return label


def _link(text: str, slot, tip: str = "") -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("Link")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if tip:
        button.setToolTip(tip)
    button.clicked.connect(slot)
    return button


class NarratorsPage(QWidget):
    open_chain = Signal(int)        # hadith id → Isnad Chains page
    open_sources = Signal()         # no rijal work yet → Data Sources
    open_in_book = Signal(int)      # person id → the rijal work, at his entry (Books)

    def __init__(self, connection_getter, parent=None, tradition: str = "sunni") -> None:
        """tradition: "sunni" (the Narrators section, Ibn Hajar's scale) or "shia" (the Shia Rijal section, read on
        the Imami scale — core.shia_rijal). The same page, each tradition by its own measure."""
        super().__init__(parent)
        self.setObjectName("Page")
        self._conn_of = connection_getter
        self._current: int | None = None
        self.tradition = tradition
        shia = tradition == "shia"

        # ---------------------------------------------------------------- left: search and list
        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(420)
        lbox = QVBoxLayout(left)
        lbox.setContentsMargins(18, 16, 18, 14)
        lbox.setSpacing(8)
        title = _label("Shia Rijal" if shia else "Narrators", "CardTitle")
        title.setFont(theme.reading_font(18, bold=True))
        self.overview = _label("", "Caption")
        self.query = QLineEdit()
        self.query.setPlaceholderText("Name, kunya or nisba — Arabic or Latin letters")
        self.query.setClearButtonEnabled(True)
        self.tabaqa = QComboBox()
        self.tabaqa.addItem("Every tabaqa", None)
        for t, text in TABAQA_LABELS.items():
            self.tabaqa.addItem(f"Tabaqa {t}: {text.split(' (')[0]}", t)
        self.rank = QComboBox()
        if shia:
            self.rank.addItem("Every assessment", None)
            for r, (_ar, en, _why) in shia_rijal.RANKS.items():
                self.rank.addItem(en[0].upper() + en[1:], r)
            self.rank.addItem("No judgment in the work", -1)
        else:
            self.rank.addItem("Every rank", None)
            for r, (_ar, en) in RANK_LABELS.items():
                self.rank.addItem(f"Rank {r}: {en.split(' (')[0]}", r)
        self.book = QComboBox()
        self.book.addItem("Every book", None)
        for key, name in (("bukhari", "al-Bukhari"), ("muslim", "Muslim"), ("abudawud", "Abu Dawud"),
                          ("tirmidhi", "al-Tirmidhi"), ("nasai", "al-Nasa'i"), ("ibnmajah", "Ibn Maja")):
            self.book.addItem(f"Narrates in {name}", key)
        for combo in (self.tabaqa, self.rank, self.book):
            combo.currentIndexChanged.connect(self._populate)
        self.list = QListWidget()
        self.list.setObjectName("NarratorList")
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(lambda item, _p: item and self.show_person(item.data(Qt.ItemDataRole.UserRole)))
        self.count = _label("", "Caption")
        lbox.addWidget(title)
        lbox.addWidget(self.overview)
        lbox.addWidget(self.query)
        lbox.addWidget(self.tabaqa)
        lbox.addWidget(self.rank)
        lbox.addWidget(self.book)
        if shia:                       # Ibn Hajar's tabaqa and book marks are not the Shia works' measure
            self.tabaqa.hide()
            self.book.hide()
        lbox.addWidget(self.list, 1)
        lbox.addWidget(self.count)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._populate)
        self.query.textChanged.connect(lambda _t: self._debounce.start())

        # ---------------------------------------------------------------- right: the narrator
        self.detail = QWidget()
        self.detail.setObjectName("Page")
        self.detail_box = QVBoxLayout(self.detail)
        self.detail_box.setContentsMargins(8, 4, 8, 16)
        self.detail_box.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.detail)
        self.left = left
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)
        root.addWidget(left)
        root.addWidget(scroll, 1)

    # ------------------------------------------------------------------ data
    @property
    def conn(self):
        return self._conn_of()

    def refresh(self) -> None:
        conn = self.conn
        if conn is None:
            return
        ov = core_narrators.overview(conn, self.tradition)
        self.left.setEnabled(ov["persons"] > 0)
        if not ov["persons"]:
            self.overview.setText("")
            self.list.clear()
            self.count.setText("")
            self._show_empty()
            return
        share = f"{100 * ov['identified'] / ov['links']:.1f}%" if ov["links"] else "—"
        if self.tradition == "shia":
            self.overview.setText(f"{ov['persons']:,} narrators from {', '.join(ov['works'])}, each read on the Imami scale: "
                                  "reliability and creed. Shia chains are not imported yet.")
        else:
            self.overview.setText(f"{ov['persons']:,} narrators from {', '.join(ov['works'])}. "
                                  f"{ov['identified']:,} of {ov['links']:,} names in the chains identified ({share}).")
        self._populate()
        if self._current:
            self.show_person(self._current)

    def _populate(self) -> None:
        conn = self.conn
        if conn is None:
            return
        rows, total = core_narrators.browse(conn, self.query.text(), self.tabaqa.currentData(),
                                            self.rank.currentData(), self.book.currentData(), limit=LIST_LIMIT,
                                            tradition=self.tradition)
        self.list.blockSignals(True)
        self.list.clear()
        for r in rows:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, r["id"])
            item.setToolTip(r["name"])
            widget = QWidget()
            box = QVBoxLayout(widget)
            box.setContentsMargins(8, 6, 8, 6)
            box.setSpacing(1)
            name = _arabic("", 0.72)
            name.setWordWrap(False)
            # one line that fits the row: the start of the name is kept, the end is cut with "…"
            # (a long name used to widen the list and push short right-aligned names out of sight)
            fm = QFontMetrics(theme.script_font("arabic", factor=0.72))
            name.setText(fm.elidedText(r["name"], Qt.TextElideMode.ElideRight, ROW_TEXT_WIDTH))
            name.setMaximumWidth(ROW_TEXT_WIDTH + 8)
            dot = theme.rank_color(SHIA_COLOR.get(r["rank"]) if self.tradition == "shia" else r["rank"])
            facts = []
            if self.tradition == "shia":
                if r["rank"]:
                    facts.append(f"<span style='color:{dot}'>●</span> {shia_rijal.RANKS[r['rank']][1].split(' (')[0]}")
                else:
                    facts.append("no judgment")
                if r.get("madhhab"):
                    facts.append(shia_rijal.MADHHAB_LABELS.get(r["madhhab"], r["madhhab"]))
            elif r["rank"]:
                facts.append(f"<span style='color:{dot}'>●</span> rank {r['rank']}")
            if r["tabaqa"]:
                facts.append(f"tabaqa {r['tabaqa']}")
            if r["death"]:
                facts.append(f"d. {r['death']}")
            if self.tradition != "shia":
                facts.append(f"{r['in_chains']:,} in chains")
            caption = _label(" · ".join(facts), "Caption", wrap=False, rich=True)
            box.addWidget(name)
            reading = latin(r["name"], "tr")
            if reading:
                roman = _label(QFontMetrics(self.list.font()).elidedText(reading, Qt.TextElideMode.ElideRight, ROW_TEXT_WIDTH),
                               "RowLatin", wrap=False)
                roman.setToolTip(f"Türkçe: {reading}\nEnglish: {latin(r['name'], 'en')}")
                box.addWidget(roman)
            box.addWidget(caption)
            item.setSizeHint(widget.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, widget)
        self.list.blockSignals(False)
        more = f" — the first {LIST_LIMIT}; narrow the search to see others" if total > LIST_LIMIT else ""
        self.count.setText(f"{total:,} narrator{'s' if total != 1 else ''}{more}")
        if self._current is None and rows:
            self.show_person(rows[0]["id"])

    # ------------------------------------------------------------------ the right side
    def _clear(self) -> None:
        while self.detail_box.count():
            item = self.detail_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            elif item.layout() is not None:
                lay = item.layout()
                while lay.count():
                    sub = lay.takeAt(0)
                    if sub.widget() is not None:
                        sub.widget().setParent(None)
                        sub.widget().deleteLater()

    def _card(self, title: str = "") -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(20, 14, 20, 14)
        box.setSpacing(8)
        if title:
            head = _label(title, "CardTitle")
            head.setFont(theme.reading_font(14, bold=True))
            box.addWidget(head)
        self.detail_box.addWidget(card)
        return card, box

    def _show_empty(self) -> None:
        self._clear()
        card, box = self._card()
        hero = _label("No narrators yet", "Hero")
        hero.setFont(theme.reading_font(24, bold=True))
        box.addWidget(hero)
        if self.tradition == "shia":
            box.addWidget(_label("The Shia rijal works are imported from Data Sources: al-Najashi's Rijal — 1,266 authors and "
                                 "narrators with his judgment on each, read on the Imami scale (reliability and creed).",
                                 "Lead"))
        else:
            box.addWidget(_label("Narrators come from a rijal work. Import Ibn Hajar's Taqrib al-Tahdhib — 8,824 narrators "
                                 "with his verdict on each — and every name in the chains is matched to its narrator.",
                                 "Lead"))
        row = QHBoxLayout()
        go = QPushButton("Open Data Sources")
        go.setObjectName("Primary")
        go.clicked.connect(self.open_sources.emit)
        row.addWidget(go)
        row.addStretch(1)
        box.addLayout(row)
        self.detail_box.addStretch(1)

    def show_person(self, person_id: int | None) -> None:
        conn = self.conn
        if conn is None or not person_id:
            return
        who = core_narrators.describe(conn, person_id)
        if who is None:
            return
        self._current = person_id
        self._clear()
        t = theme.current()

        # name, other names
        card, box = self._card()
        box.addWidget(_arabic(who["display_name"], 1.15, bold=True))
        if who.get("latin_tr"):
            readings = _label(f"<b>Türkçe:</b> {html.escape(who['latin_tr'])} &nbsp;&nbsp;·&nbsp;&nbsp; "
                              f"<b>English:</b> {html.escape(who['latin_en'] or '')}", "Lead", rich=True)
            readings.setToolTip("Read from a hand-written list of name words (Turkish as in the TDV İslâm "
                                "Ansiklopedisi, English in plain academic spelling). Only the part of the name whose "
                                "words are all known is given.")
            box.addWidget(readings)
        else:
            box.addWidget(_label("No Latin reading yet: a word of this name is not in isnady's name list.", "Caption"))
        if who["other_names"]:
            box.addWidget(_arabic("، ".join(who["other_names"][:10]), 0.62, muted=True))
        if who["name_ar"].strip() != who["display_name"].strip():
            # the entry as Ibn Hajar wrote it, with his notes on how to read the name
            full = _arabic(who["name_ar"], 0.6, muted=True)
            full.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            full.setToolTip("The entry as written in the rijal work, with its notes on how to read the name")
            box.addWidget(full)

        # verdicts, tabaqa, death
        card, box = self._card("What the critics say")
        for v in who["verdicts"]:
            if v["rank_scheme"] == "shia":
                dot = theme.rank_color(SHIA_COLOR.get(v["rank"]))
                rank = (f"&nbsp;&nbsp;<span style='color:{dot}'>●</span> {html.escape(v['rank_label'])}" if v["rank"]
                        else "&nbsp;&nbsp;<i>no judgment in these words</i>")
                if v.get("madhhab_label"):
                    rank += f"&nbsp;·&nbsp;creed: {html.escape(v['madhhab_label'])}"
            else:
                dot = theme.rank_color(v["rank"])
                rank = (f"&nbsp;&nbsp;<span style='color:{dot}'>●</span> rank {v['rank']} of 12: "
                        f"{html.escape(v['rank_label'])}") if v["rank"] else ""
            arabic = theme.script_font("arabic", factor=0.75)
            line = _label(f"<b>{html.escape(v['critic_name'])}</b>, <i>{html.escape(v['work'])}</i>:&nbsp; "
                          f"<span style='font-family:\"{arabic.family()}\"; font-size:{arabic.pointSizeF():.1f}pt'>"
                          f"{html.escape(v['phrase'])}</span>{rank}", "NodeVerdict", rich=True)
            box.addWidget(line)
        if not who["verdicts"]:
            box.addWidget(_label("No verdict recorded.", "Caption"))
        facts = []
        if who["tabaqa"]:
            facts.append(f"<b>Tabaqa {who['tabaqa']}</b>: {html.escape(who['tabaqa_label'])}")
        if who["death_year_ah"]:
            facts.append(f"<b>Died</b> {who['death_year_ah']} AH")
        elif who["death_year_note"]:
            facts.append(f"<b>Death</b>: {html.escape(who['death_year_note'])}")
        if facts:
            box.addWidget(_label(" &nbsp;·&nbsp; ".join(facts), "Lead", rich=True))
        if self.tradition == "shia":
            explain = _label("<b>How the Imami critics judge</b> — on two axes: <b>reliability</b> (thiqa; praised — jalil, "
                             "wajh, 'ayn, la ba's bihi; weak) and <b>creed</b> (Imami, or Waqifi, Fathi, Zaydi, 'ammi …). "
                             "Together they give the classical four: an Imami <b>thiqa</b>, a <b>praised</b> narrator (mamduh), "
                             "a thiqa of another school (<b>muwaththaq</b>), a <b>weak</b> one. Read from the critic's own "
                             "words at the head of the entry; a creed he does not state is left unknown. Not Ibn Hajar's "
                             "scale: each tradition is shown by its own measure.", "Caption", rich=True)
        else:
            explain = None
        if explain is None:
            explain = _label("<b>Rank</b> — Ibn Hajar sorts narrators into twelve degrees, from the Companions (1) down to "
                         "the accused liar (12); 2–3 are trustworthy, 4 truthful, 5–6 acceptable, 7–12 weak to rejected. "
                         "<b>Tabaqa</b> — the generation: 1 Companions, 2–5 Successors, 6–9 their followers, 10–12 "
                         "the compilers' teachers.", "Caption", rich=True)
        box.addWidget(explain)
        go_book = QPushButton("Open his entry in the book")
        go_book.setObjectName("Quiet")
        go_book.clicked.connect(lambda: self.open_in_book.emit(person_id))
        book_row = QHBoxLayout()
        book_row.addWidget(go_book)
        book_row.addStretch(1)
        box.addLayout(book_row)
        if who["marks"]:
            marks = QWidget()
            flow = FlowLayout(marks, spacing=6)
            for mark, meaning in who["marks"]:
                chip = QLabel(f"{mark}  {meaning}")
                chip.setObjectName("ChainChip")
                chip.setToolTip(f"Ibn Hajar's mark {mark}: {meaning}")
                flow.addWidget(chip)
            box.addWidget(_label("Where his hadith appear (Ibn Hajar's marks)", "Caption"))
            box.addWidget(marks)

        if self.tradition == "shia":
            card, box = self._card("Chains")
            box.addWidget(_label("The Shia hadith collections (al-Kafi, Man la yahduruhu al-faqih, Tahdhib al-ahkam, "
                                 "al-Istibsar) and their chains are not imported yet; when they are, this narrator's teachers, "
                                 "students and hadith will show here.", "Caption"))
            self.detail_box.addStretch(1)
            return
        # teachers and students as the chains show them
        rel = core_narrators.relations(conn, person_id)
        card, box = self._card("Teachers and students in the imported chains")
        box.addWidget(_label("Counted from the chains imported here, where both narrators are identified. "
                             "The full lists of al-Mizzi's Tahdhib al-Kamal are a later step.", "Caption"))
        cols = QHBoxLayout()
        for heading, items in (("Narrates from", rel["teachers"]), ("Narrated to", rel["students"])):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(_label(heading, "FilterLabel"))
            for r in items:
                short = short_name(r["name"], 5)                    # the ism and the first of the lineage
                link = _link(f"{short}  ({r['count']})", lambda _c=False, pid=r["id"]: self.select(pid),
                             f"{r['name']}\nOpen this narrator")
                col.addWidget(link)
            if not items:
                col.addWidget(_label("—", "Caption"))
            col.addStretch(1)
            cols.addLayout(col, 1)
        box.addLayout(cols)
        if rel["compilers"]:
            parts = " · ".join(f"{html.escape(c['book'])} ({c['count']:,})" for c in rel["compilers"])
            box.addWidget(_label(f"<b>Compilers who narrate from him directly:</b> {parts}", "Lead", rich=True))

        # the hadith
        hadith, total = core_narrators.hadiths_of(conn, person_id)
        card, box = self._card(f"In the chains of {total:,} hadith")
        if hadith:
            wrap = QWidget()
            flow = FlowLayout(wrap, spacing=6)
            for h in hadith:
                flow.addWidget(_link(f"{h['book']} {h['number']}", lambda _c=False, hid=h["hadith_id"]: self.open_chain.emit(hid),
                                     "Open this chain"))
            box.addWidget(wrap)
            if total > len(hadith):
                box.addWidget(_label(f"… and {total - len(hadith):,} more.", "Caption"))
        else:
            box.addWidget(_label("Not identified in any imported chain yet.", "Caption"))
        self.detail_box.addStretch(1)
        _ = t

    def select(self, person_id: int) -> None:
        """Show a narrator, from this page or from another (the chain page)."""
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == person_id:
                self.list.blockSignals(True)
                self.list.setCurrentRow(i)
                self.list.blockSignals(False)
                break
        self.show_person(person_id)

    def retheme(self) -> None:
        self.refresh()
