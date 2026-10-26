"""Narrators: every narrator of the imported rijal works, Sunni and Shia on one page (SH1), searchable and
filterable, with what the rijal work says of him and what the imported chains show — whom he narrates from, who
narrates from him, and the hadith whose chains include him.

The two traditions meet here but are not mixed: a Shia narrator carries a gold "Shia" tag and is judged in the
Imami terms of his own critics (core.shia_rijal), a Sunni narrator on Ibn Hajar's twelve ranks; each is found in
the chains of his own tradition's books (road A / road B, core.traditions)."""

import html

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QButtonGroup,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from isnady.core import i18n
from isnady.core import narrators as core_narrators
from isnady.core.i18n import N_, n_, tr
from isnady.core import shia_rijal, traditions
from isnady.core.names import latin
from isnady.core.rijal import BOOK_MARKS, RANK_LABELS, TABAQA_LABELS, display_name, short_name
from isnady.gui import theme
from isnady.gui.name_card import SPELLED, NameCard
from isnady.gui.widgets import FlowLayout

LIST_LIMIT = 200
ROWS_FIRST = 30        # rows built at once; the rest in batches right after (2026-10-12)
ROWS_BATCH = 40
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
    open_genealogy = Signal(int, str)   # person id, "family" | "learning" → Genealogies (GEN1)
    open_narrator = Signal(int)     # a teacher or student → shown here through the window, so Back returns (NAV2)
    open_book = Signal(str)         # a book his hadith are in (Ibn Hajar's mark) → Books
    find_name = Signal(str)         # a teacher or student named in his life → looked for among the narrators

    def __init__(self, connection_getter, parent=None, tradition: str | None = None) -> None:
        """tradition: the narrators shown first — "sunni", "shia", or None for both. The reader switches between
        them at the top of the list; each narrator is shown by his own tradition's measure."""
        super().__init__(parent)
        self.setObjectName("Page")
        self._conn_of = connection_getter
        self._current: int | None = None
        self.tradition = tradition

        # ---------------------------------------------------------------- left: search and list
        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(420)
        lbox = QVBoxLayout(left)
        lbox.setContentsMargins(18, 16, 18, 14)
        lbox.setSpacing(8)
        title = _label(tr("Narrators"), "CardTitle")
        title.setFont(theme.reading_font(18, bold=True))
        self.overview = _label("", "Caption", rich=True)
        # Sunni / Shia / both: one page, the two roads side by side
        self._segments = QButtonGroup(self)
        self._segments.setExclusive(True)
        seg_row = QHBoxLayout()
        seg_row.setSpacing(6)
        for key, text, tip in ((None, N_("All"), N_("Sunni and Shia narrators together, each by his own tradition's "
                                                    "measure")),
                               ("sunni", N_("Sunni"), N_("Narrators of the Sunni rijal works (Ibn Hajar's Taqrib): twelve "
                                                         "ranks")),
                               ("shia", N_("Shia"), N_("Narrators of the Shia rijal works (al-Najashi …): the Imami "
                                                       "terms"))):
            text, tip = tr(text), tr(tip)
            b = QPushButton(text)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(tip)
            b.setProperty("tradition", key)
            b.setChecked(key == tradition)
            self._segments.addButton(b)
            seg_row.addWidget(b)
        seg_row.addStretch(1)
        self._segments.buttonClicked.connect(lambda b: self.set_tradition(b.property("tradition")))
        self.query = QLineEdit()
        self.query.setPlaceholderText(tr("Name, kunya or nisba — Arabic or Latin letters"))
        self.query.setClearButtonEnabled(True)
        # FS1: the famous Companions in their groups — the four Caliphs, the Ten, the Mothers of the Believers …
        self._famous_mode = False
        self.famous_button = QPushButton()
        self.famous_button.setObjectName("Link")
        self.famous_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.famous_button.clicked.connect(self._toggle_famous)
        self._famous_text()
        self.tabaqa = QComboBox()
        self.tabaqa.addItem(tr("All generations"), None)
        for t, text in TABAQA_LABELS.items():
            self.tabaqa.addItem(tr("Tabaqa {tabaqa}: {meaning}", tabaqa=t, meaning=tr(text).split(" (")[0]), t)
        self.rank = QComboBox()
        self._fill_ranks()
        self.book = QComboBox()
        self.book.addItem(tr("All books"), None)
        for key, name in (("bukhari", "al-Bukhari"), ("muslim", "Muslim"), ("abudawud", "Abu Dawud"),
                          ("tirmidhi", "al-Tirmidhi"), ("nasai", "al-Nasa'i"), ("ibnmajah", "Ibn Maja")):
            self.book.addItem(tr("Narrates in {name}", name=name), key)
        for combo in (self.tabaqa, self.rank, self.book):
            combo.setObjectName("FilterCombo")
            combo.setCursor(Qt.CursorShape.PointingHandCursor)
            combo.currentIndexChanged.connect(self._filters_changed)
        self.clear_filters = QPushButton(tr("Clear filters"))
        self.clear_filters.setObjectName("Link")
        self.clear_filters.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_filters.clicked.connect(self._clear_filters)
        self.clear_filters.hide()
        self.list = QListWidget()
        self.list.setObjectName("NarratorList")
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(lambda item, _p: item and self.show_person(item.data(Qt.ItemDataRole.UserRole)))
        # the next narrators when the list is scrolled to its end (NR-B1)
        self.list.verticalScrollBar().valueChanged.connect(self._near_end)
        self.count = _label("", "Caption")
        lbox.addWidget(title)
        lbox.addLayout(seg_row)
        lbox.addWidget(self.overview)
        lbox.addWidget(self.query)
        famous_row = QHBoxLayout()
        famous_row.addWidget(self.famous_button)
        famous_row.addStretch(1)
        lbox.addLayout(famous_row)
        # each filter under its own title, so it is clear what it narrows (UI6)
        self._filter_boxes = {}
        self._filter_titles = {}
        titles = (("tabaqa", tr("Generation (tabaqa)"), self.tabaqa),
                  ("rank", tr("Rank (Ibn Hajar)"), self.rank),
                  ("book", tr("Book"), self.book))
        for key, title, combo in titles:
            holder = QWidget()
            hb = QVBoxLayout(holder)
            hb.setContentsMargins(0, 2, 0, 0)
            hb.setSpacing(3)
            self._filter_titles[key] = _label(title, "FilterTitle", wrap=False)
            hb.addWidget(self._filter_titles[key])
            hb.addWidget(combo)
            self._filter_boxes[key] = holder
            lbox.addWidget(holder)
        self._show_filters()
        clear_row = QHBoxLayout()
        clear_row.addStretch(1)
        clear_row.addWidget(self.clear_filters)
        lbox.addLayout(clear_row)
        lbox.addWidget(self.list, 1)
        lbox.addWidget(self.count)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._populate)
        self.query.textChanged.connect(self._typed)

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
        self.detail_scroll = scroll
        self.left = left
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)
        root.addWidget(left)
        root.addWidget(scroll, 1)

    # ------------------------------------------------------------------ the famous ones (FS1)
    def _famous_text(self) -> None:
        if self._famous_mode:
            self.famous_button.setText("← " + tr("All narrators"))
        elif self.tradition == "shia":
            self.famous_button.setText("★ " + tr("Famous narrators"))
        else:
            self.famous_button.setText("★ " + tr("Famous Companions"))
        self.famous_button.setToolTip(tr("The four Caliphs, the ten promised Paradise, the Mothers of the Believers, "
                                         "the Prophet's household, those who narrated most …")
                                      if self.tradition != "shia" else tr("Ashab al-Ijma'"))

    def _typed(self, _text: str) -> None:
        if self._famous_mode:
            self._famous_mode = False
            self._famous_text()
        self._debounce.start()

    def _toggle_famous(self) -> None:
        self._famous_mode = not self._famous_mode
        self._famous_text()
        if self._famous_mode:
            self._show_famous()
        else:
            self._populate()

    def _show_famous(self) -> None:
        """The famous ones of the tradition shown, group by group, each name as people know it."""
        conn = self.conn
        if conn is None:
            return
        from isnady.core import famous

        self._famous_titles = famous.titles(conn, i18n.language())
        self._row_token = getattr(self, "_row_token", 0) + 1
        self._rows_left, self._shown_ids = [], set()
        self._list_read = self._list_total = 0
        self.list.blockSignals(True)
        self.list.clear()
        first = None
        shown = 0
        for group in famous.groups(self.tradition):
            ids = famous.ids(conn, [p[0] for p in group["people"]])
            if not ids:
                continue
            rows, _n = core_narrators.browse(conn, limit=len(ids), tradition=group["tradition"], only=ids)
            place = {pid: i for i, pid in enumerate(ids)}
            rows.sort(key=lambda r: place.get(r["id"], len(ids)))
            head = QListWidgetItem(tr(group["title"]))
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            font = self.list.font()
            font.setBold(True)
            head.setFont(font)
            head.setForeground(QColor(theme.current().gold))
            self.list.addItem(head)
            for r in rows:
                self._add_row(r)
                shown += 1
                first = first or r["id"]
        self.list.blockSignals(False)
        self.count.setText(n_("{n:,} famous one", "{n:,} famous ones", shown))
        if first and self._current is None:
            self.show_person(first)

    # ------------------------------------------------------------------ data
    def _filters_changed(self, *_args) -> None:
        """A chosen filter is coloured, so it is plain at a glance which ones are on; then the list refreshes."""
        active = False
        for combo in (self.tabaqa, self.rank, self.book):
            on = combo.currentIndex() > 0
            active = active or (on and combo.isVisibleTo(self))
            if combo.property("active") != on:
                combo.setProperty("active", on)
                combo.style().unpolish(combo)
                combo.style().polish(combo)
        self.clear_filters.setVisible(active)
        self._populate()

    def _clear_filters(self) -> None:
        for combo in (self.tabaqa, self.rank, self.book):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self._filters_changed()

    def _fill_ranks(self) -> None:
        """The rank filter speaks the chosen tradition's language; for both together there is no one scale."""
        self.rank.blockSignals(True)
        self.rank.clear()
        if self.tradition == "shia":
            self.rank.addItem(tr("All assessments"), None)
            for r, (_ar, en, _why) in shia_rijal.RANKS.items():
                en = tr(en)
                self.rank.addItem(en[0].upper() + en[1:], r)
            self.rank.addItem(tr("No judgment in the work"), -1)
        else:
            self.rank.addItem(tr("All ranks"), None)
            for r, (_ar, en) in RANK_LABELS.items():
                self.rank.addItem(tr("Rank {rank}: {meaning}", rank=r, meaning=tr(en).split(" (")[0]), r)
        self.rank.blockSignals(False)

    def _show_filters(self) -> None:
        # Ibn Hajar's tabaqa and book marks are the Sunni works' measure; the two scales are never one filter
        sunni = self.tradition == "sunni"
        self._filter_boxes["tabaqa"].setVisible(sunni)
        self._filter_boxes["book"].setVisible(sunni)
        self._filter_boxes["rank"].setVisible(self.tradition is not None)
        self._filter_titles["rank"].setText(tr("Assessment (Imami terms)") if self.tradition == "shia" else tr("Rank (Ibn Hajar)"))

    def set_tradition(self, tradition: str | None) -> None:
        """Show the Sunni narrators, the Shia ones, or both (None)."""
        if tradition == self.tradition:
            return
        self.tradition = tradition
        for b in self._segments.buttons():
            b.setChecked(b.property("tradition") == tradition)
        for combo in (self.tabaqa, self.book):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self._fill_ranks()
        self._show_filters()
        self._current = None
        self._famous_mode = False
        self._famous_text()
        self.refresh()
        self._filters_changed()

    @property
    def conn(self):
        return self._conn_of()

    def refresh(self) -> None:
        conn = self.conn
        if conn is None:
            return
        lines, persons = [], 0
        for road in ((self.tradition,) if self.tradition else traditions.TRADITIONS):
            ov = core_narrators.overview(conn, road)
            persons += ov["persons"]
            if not ov["persons"]:
                continue
            share = f"{100 * ov['identified'] / ov['links']:.1f}%" if ov["links"] else "—"
            tag = ("<span style='color:%s'><b>%s</b></span>" % (theme.current().gold, tr("Shia")) if road == "shia"
                   else f"<b>{tr('Sunni')}</b>")
            if road == "shia":
                chains = (tr("{identified:,} of {links:,} names in the Shia chains identified ({share})",
                             identified=ov["identified"], links=ov["links"], share=share) if ov["links"]
                          else tr("no Shia chains imported yet"))
            else:
                chains = (tr("{identified:,} of {links:,} names in the Sunni chains identified ({share})",
                             identified=ov["identified"], links=ov["links"], share=share) if ov["links"]
                          else tr("no Sunni chains imported yet"))
            lines.append(f"{tag}: " + tr("{persons:,} narrators from {works}; {chains}.", persons=ov["persons"],
                                         works=html.escape(", ".join(ov["works"])), chains=chains))
        self.left.setEnabled(True)
        if not persons:
            self.overview.setText("")
            self.list.clear()
            self.count.setText("")
            self._show_empty()
            return
        self.overview.setText("<br>".join(lines))
        shown = self._current
        if self._famous_mode:
            self._show_famous()
        else:
            self._populate()
        if shown:                       # the one shown before; the list's first is drawn by _populate only when none
            self.show_person(shown)

    def _populate(self) -> None:
        conn = self.conn
        if conn is None:
            return
        if self._famous_mode:
            self._show_famous()
            return
        from isnady.core import famous

        self._famous_titles = famous.titles(conn, i18n.language())
        self._shown_ids = set()
        self._list_args = (self.query.text(), self.tabaqa.currentData(), self.rank.currentData(),
                           self.book.currentData(), self.tradition)
        rows, total = core_narrators.browse(conn, self.query.text(), self.tabaqa.currentData(),
                                            self.rank.currentData(), self.book.currentData(), limit=LIST_LIMIT,
                                            tradition=self.tradition)
        # a famous Companion named any way people write him ("Ebubekir", "Omer ibn Hattap", "Hz. Ali") first (FS1)
        first = famous.ids(conn, famous.named(self.query.text(), self.tradition)) if self.query.text().strip() else []
        if first:
            ahead, _n = core_narrators.browse(conn, "", self.tabaqa.currentData(), self.rank.currentData(),
                                              self.book.currentData(), limit=len(first), tradition=self.tradition,
                                              only=first)
            place = {pid: i for i, pid in enumerate(first)}
            ahead.sort(key=lambda r: place.get(r["id"], len(first)))
            known = {r["id"] for r in ahead}
            total += len([pid for pid in known if pid not in {r["id"] for r in rows}])
            rows = ahead + [r for r in rows if r["id"] not in known]
        self._list_read, self._list_total = len(rows), total
        self.list.blockSignals(True)
        self.list.clear()
        self.list.blockSignals(False)
        # the first rows at once, the rest a batch at a time after the window has drawn them (2026-10-12: the page
        # opened only when all 200 rows were built)
        self._row_token = getattr(self, "_row_token", 0) + 1
        self._rows_left = list(rows)
        self._add_rows(self._row_token, ROWS_FIRST)
        self._show_count()
        if self._current is None and rows:
            self.show_person(rows[0]["id"])

    def _show_count(self) -> None:
        total, read = self._list_total, self._list_read
        more = " — " + tr("{shown:,} listed; scroll down for the next", shown=read) if total > read else ""
        self.count.setText(n_("{n:,} narrator", "{n:,} narrators", total) + more)

    def _near_end(self, value: int) -> None:
        """NR-B1 (Bayram, 2026-10-13: "daha var diyor ama bir sonraki sayfaya geç yok! Sadece çok azını
        gösteriyor"): the list stopped at its first LIST_LIMIT; now the next ones are read at its end."""
        bar = self.list.verticalScrollBar()
        if (self.conn is None or getattr(self, "_rows_left", None) or value < bar.maximum() - bar.pageStep() // 2
                or getattr(self, "_list_read", 0) >= getattr(self, "_list_total", 0)):
            return
        text, tabaqa, rank, book, tradition = self._list_args
        rows, _total = core_narrators.browse(self.conn, text, tabaqa, rank, book, limit=LIST_LIMIT,
                                             tradition=tradition, offset=self._list_read)
        if not rows:
            self._list_total = self._list_read
        self._list_read += len(rows)
        self._rows_left = list(rows)
        self._add_rows(self._row_token, ROWS_FIRST)
        self._show_count()

    def _add_rows(self, token: int, count: int = 0) -> None:
        """Build the next rows of the list (all that are left when count is 0)."""
        if token != getattr(self, "_row_token", 0):
            return                                   # another list replaced this one
        left = self._rows_left
        take, self._rows_left = (left[:count], left[count:]) if count else (left, [])
        self.list.blockSignals(True)
        shown = getattr(self, "_shown_ids", set())
        for r in take:
            if r["id"] in shown:
                continue                             # a famous one put first, met again on a later page
            self._add_row(r)
        self.list.blockSignals(False)
        if self._rows_left:
            QTimer.singleShot(0, lambda: self._add_rows(token, ROWS_BATCH))

    def _flush_rows(self) -> None:
        if getattr(self, "_rows_left", None):
            self._add_rows(self._row_token, 0)

    def _add_row(self, r: dict) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, r["id"])
        item.setToolTip(r["name"])
        widget = QWidget()
        box = QVBoxLayout(widget)
        box.setContentsMargins(8, 6, 8, 6)
        box.setSpacing(1)
        view = r["view"]
        getattr(self, "_shown_ids", set()).add(r["id"])
        top = QHBoxLayout()
        top.setSpacing(10)
        fm_ui = QFontMetrics(self.list.font())
        famous_title = getattr(self, "_famous_titles", {}).get(r["id"])
        # a famous one by the name people know him by — Abu Bakr's entry begins with 'Abd Allah b. 'Uthman (FS1)
        known = famous_title or view["reading"] or view["full_reading"]
        if known:
            title = _label(fm_ui.elidedText(known, Qt.TextElideMode.ElideRight, 190), "RowTitle", wrap=False)
            tip = (tr("{full_reading}\nknown by {how}", full_reading=view['full_reading'], how=tr(view['how']))
                   if view["how"] else view["full_reading"])
            title.setToolTip(tip + ("\n" + tr(SPELLED) if view.get("spelled") else ""))
            top.addWidget(title, 1)
        arabic_known = _arabic("", 0.7, bold=not known)
        arabic_known.setWordWrap(False)
        fm_ar = QFontMetrics(theme.script_font("arabic", factor=0.7))
        arabic_known.setText(fm_ar.elidedText(view["arabic"] or r["name"], Qt.TextElideMode.ElideRight,
                                              ROW_TEXT_WIDTH - (200 if known else 0)))
        top.addWidget(arabic_known, 0 if known else 1)
        box.addLayout(top)
        if famous_title and (view["reading"] or view["full_reading"]):
            box.addWidget(_label(fm_ui.elidedText(view["full_reading"] or view["reading"], Qt.TextElideMode.ElideRight,
                                                  ROW_TEXT_WIDTH), "Caption", wrap=False))
        elif known and view["full_reading"] and view["full_reading"] != known:
            box.addWidget(_label(fm_ui.elidedText(view["full_reading"], Qt.TextElideMode.ElideRight, ROW_TEXT_WIDTH),
                                 "Caption", wrap=False))
        shia = r.get("tradition") == "shia"
        dot = theme.rank_color(SHIA_COLOR.get(r["rank"]) if shia else r["rank"])
        facts = []
        if shia:
            facts.append(f"<span style='color:{theme.current().gold}'><b>{tr('Shia')}</b></span>")
            if r["rank"]:
                facts.append(f"<span style='color:{dot}'>●</span> "
                             + tr(shia_rijal.RANKS[r["rank"]][1]).split(" (")[0])
            else:
                facts.append(tr("no judgment"))
            if r.get("madhhab"):
                facts.append(tr(shia_rijal.MADHHAB_LABELS.get(r["madhhab"], r["madhhab"])))
        elif r["rank"]:
            facts.append(f"<span style='color:{dot}'>●</span> " + tr("rank {rank}", rank=r["rank"]))
        if r["tabaqa"]:
            facts.append(tr("tabaqa {tabaqa}", tabaqa=r["tabaqa"]))
        if r["death"]:
            facts.append(tr("d. {year}", year=r["death"]))
        facts.append(tr("{n:,} in chains", n=r["in_chains"]))
        caption = _label(" · ".join(facts), "Caption", wrap=False, rich=True)
        box.addWidget(caption)
        item.setSizeHint(widget.sizeHint())
        self.list.addItem(item)
        self.list.setItemWidget(item, widget)

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
        hero = _label(tr("No narrators yet"), "Hero")
        hero.setFont(theme.reading_font(24, bold=True))
        box.addWidget(hero)
        if self.tradition != "shia":
            box.addWidget(_label(tr("Sunni narrators come from Ibn Hajar's Taqrib al-Tahdhib — 8,824 narrators with his verdict on "
                                   "each; every name in the chains of the Sunni books is matched to its narrator."),
                                 "Lead"))
        if self.tradition != "sunni":
            box.addWidget(_label(tr("Shia narrators come from al-Najashi's Rijal — 1,266 authors and narrators with his judgment on "
                                   "each, read in the Imami terms (reliability and creed); the chains of the Shia books are matched "
                                   "to them."), "Lead"))
        row = QHBoxLayout()
        go = QPushButton(tr("Open Data Sources"))
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
        shia = (who.get("tradition") or "sunni") == "shia"

        # the name: known-as, full name, the parts (NM1)
        from isnady.core import bookmarks
        from isnady.gui.bookmarks_page import BookmarkButton

        ref = bookmarks.narrator_ref(conn, person_id)
        self.detail_box.addWidget(NameCard(who["name_view"], star=BookmarkButton("narrator", *ref) if ref else None))
        trees = QHBoxLayout()
        trees.addWidget(_label("🌳 " + tr("Genealogies:"), "Caption", wrap=False))
        for text, which, tip in ((tr("his family"), "family", tr("His forefathers and descendants among the narrators, "
                                                                 "read from their names")),
                                 (tr("his line of learning"), "learning", tr("His teachers above him and his students "
                                                                             "below him, from the imported chains"))):
            link = _link(text, lambda _c=False, w=which: self.open_genealogy.emit(person_id, w), tip)
            trees.addWidget(link)
        from isnady.core import genealogy as core_genealogy
        from isnady.core import lives as core_lives

        own = core_lives.of_person(conn, person_id)
        if own and own["id"] in core_genealogy.LIFE_NODES:
            tree_key = core_genealogy.LIFE_NODES[own["id"]][0]
            # his box in a written tree (GEN1-L): Abu Bakr in the tree of Quraysh, beside the Prophet's line ﷺ
            trees.addWidget(_link(tr("his place in the tree of Quraysh"),
                                  lambda _c=False, k=tree_key: self.open_genealogy.emit(person_id, k),
                                  tr("The family of Quraysh as the genealogists give it, with him in it")))
        trees.addStretch(1)
        self.detail_box.addLayout(trees)

        # his life (BIO2): written for isnady, or read from the rijal work and the chains
        from isnady.core import lives
        from isnady.gui.life_card import life_card

        info, written = lives.life(conn, person_id)
        if info is not None and (written or info["paragraphs"]):
            self.detail_box.addWidget(life_card(info, written, open_name=self.find_name.emit))

        # verdicts, tabaqa, death
        card, box = self._card(tr("What the critics say"))
        tag_row = QHBoxLayout()
        tag = QLabel(tr("Shia narrator") if shia else tr("Sunni narrator"))
        tag.setObjectName("TagGold" if shia else "TagMuted")
        tag.setToolTip((tr("A narrator of the Shia rijal works, judged in the Imami terms of his own critics and identified "
                          "in the chains of the Shia books")) if shia else
                       (tr("A narrator of the Sunni rijal works, ranked on Ibn Hajar's scale and identified in the chains of "
                          "the Sunni books")))
        tag_row.addWidget(tag)
        tag_row.addWidget(_label(tr("from {source}", source=html.escape(who.get("source") or "")), "Caption", wrap=False,
                                 rich=True))
        tag_row.addStretch(1)
        box.addLayout(tag_row)
        if who["name_ar"].strip() != who["display_name"].strip() or shia:
            # the entry as the critic wrote it: folded away, one click to read
            entry = _arabic(who["name_ar"], 0.62, muted=True)
            entry.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            entry.hide()
            toggle = QPushButton(tr("Show the entry as the critic wrote it"))
            toggle.setObjectName("Link")
            toggle.setCursor(Qt.CursorShape.PointingHandCursor)

            def _flip(_c=False, e=entry, b=toggle):
                e.setVisible(not e.isVisible())
                b.setText(tr("Hide the entry") if e.isVisible() else tr("Show the entry as the critic wrote it"))
            toggle.clicked.connect(_flip)
            row = QHBoxLayout()
            row.addWidget(toggle)
            row.addStretch(1)
            box.addLayout(row)
            box.addWidget(entry)
        for v in who["verdicts"]:
            if v["rank_scheme"] == "shia":
                dot = theme.rank_color(SHIA_COLOR.get(v["rank"]))
                rank = (f"&nbsp;&nbsp;<span style='color:{dot}'>●</span> {html.escape(v['rank_label'])}" if v["rank"]
                        else "&nbsp;&nbsp;<i>" + tr("no judgment in these words") + "</i>")
                if v.get("madhhab_label"):
                    rank += "&nbsp;·&nbsp;" + tr("creed: {creed}", creed=html.escape(v["madhhab_label"]))
            else:
                dot = theme.rank_color(v["rank"])
                rank = (f"&nbsp;&nbsp;<span style='color:{dot}'>●</span> "
                        "<span style='text-decoration: underline dotted'>" + tr("rank {rank} of 12", rank=v["rank"])
                        + "</span>: "
                        f"{html.escape(v['rank_label'])}") if v["rank"] else ""
            arabic = theme.script_font("arabic", factor=0.75)
            line = _label(f"<b>{html.escape(tr(v['critic_name']))}</b>, <i>{html.escape(v['work'])}</i>:&nbsp; "
                          f"<span style='font-family:\"{arabic.family()}\"; font-size:{arabic.pointSizeF():.1f}pt'>"
                          f"{html.escape(v['phrase'])}</span>{i18n.mark()}{rank}", "NodeVerdict", rich=True)
            from isnady.core import learn

            if v["rank_scheme"] == "shia":
                term = {1: "thiqa", 2: "mamduh", 3: "muwaththaq", 4: "daif_narrator"}.get(v["rank"])
                line.setToolTip(learn.short(term) + ("\n\n" + learn.short("imami") if v.get("madhhab") else "") if term else "")
            elif v["rank"]:
                line.setToolTip(learn.short("rank"))
            box.addWidget(line)
        if not who["verdicts"]:
            box.addWidget(_label(tr("No verdict recorded."), "Caption"))
        facts = []
        if who["tabaqa"]:
            facts.append("<b>" + tr("Tabaqa {tabaqa}", tabaqa=who["tabaqa"]) + f"</b>: {html.escape(who['tabaqa_label'])}")
        if who["death_year_ah"]:
            facts.append(tr("<b>Died</b> {year} AH", year=who["death_year_ah"]))
        elif who["death_year_note"]:
            facts.append(tr("<b>Death</b>: {note}", note=html.escape(who["death_year_note"])))
        if facts:
            box.addWidget(_label(" &nbsp;·&nbsp; ".join(facts), "Lead", rich=True))
        if shia:
            explain = _label(tr("<b>How the Imami critics judge</b> — on two axes: <b>reliability</b> (thiqa; praised — jalil, "
                               "wajh, 'ayn, la ba's bihi; weak) and <b>creed</b> (Imami, or Waqifi, Fathi, Zaydi, 'ammi …). "
                               "Together they give the classical four: an Imami <b>thiqa</b>, a <b>praised</b> narrator (mamduh), "
                               "a thiqa of another school (<b>muwaththaq</b>), a <b>weak</b> one. Read from the critic's own "
                               "words at the head of the entry; a creed he does not state is left unknown. Not Ibn Hajar's scale: "
                               "each tradition is shown by its own measure."), "Caption", rich=True)
        else:
            explain = None
        if explain is None:
            explain = _label(tr("<b>Rank</b> — Ibn Hajar sorts narrators into twelve degrees, from the Companions (1) down to the "
                               "accused liar (12); 2–3 are trustworthy, 4 truthful, 5–6 acceptable, 7–12 weak to rejected. "
                               "<b>Tabaqa</b> — the generation: 1 Companions, 2–5 Successors, 6–9 their followers, 10–12 the "
                               "compilers' teachers."), "Caption", rich=True)
        box.addWidget(explain)
        go_book = QPushButton(tr("Open his entry in the book"))
        go_book.setObjectName("Quiet")
        go_book.clicked.connect(lambda: self.open_in_book.emit(person_id))
        book_row = QHBoxLayout()
        book_row.addWidget(go_book)
        book_row.addStretch(1)
        box.addLayout(book_row)
        if who["marks"]:
            marks = QWidget()
            flow = FlowLayout(marks, spacing=6)
            from isnady.core.rijal import COLLECTION_MARKS

            have = {r[0] for r in conn.execute("SELECT key FROM collections")}
            for mark, meaning in who["marks"]:
                chip = QLabel(f"{mark}  {meaning}")
                chip.setObjectName("ChainChip")
                tip = tr("Ibn Hajar's mark {mark}: {meaning}", mark=mark, meaning=meaning)
                # a mark of one book opens that book (2026-10-18: every name and book on the page opens)
                books = [k for k, marks in COLLECTION_MARKS.items() if mark in marks and mark not in ("ع", "4")]
                if len(books) == 1 and books[0] in have:
                    chip.setCursor(Qt.CursorShape.PointingHandCursor)
                    tip += "\n\n" + tr("Click to open this book.")
                    chip.mouseReleaseEvent = (lambda e, k=books[0]: e.button() == Qt.MouseButton.LeftButton
                                              and self.open_book.emit(k))
                chip.setToolTip(tip)
                flow.addWidget(chip)
            box.addWidget(_label(tr("Where his hadith appear (Ibn Hajar's marks)"), "Caption"))
            box.addWidget(marks)

        # teachers and students as the chains of his own tradition's books show them
        rel = core_narrators.relations(conn, person_id)
        card, box = self._card(tr("Teachers and students in the imported chains"))
        box.addWidget(_label((tr("Counted from the chains of the Shia books imported here (al-Kafi …), where both narrators are "
                                "identified.") if shia else
                              tr("Counted from the chains imported here, where both narrators are identified. The full lists of "
                                "al-Mizzi's Tahdhib al-Kamal are a later step.")), "Caption"))
        cols = QHBoxLayout()
        for heading, items in ((tr("Narrates from"), rel["teachers"]), (tr("Narrated to"), rel["students"])):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(_label(heading, "FilterLabel"))
            for r in items:
                # read in the interface language (L1); the Arabic (ism and the first of the lineage) when unread
                reading, _unused = core_narrators.reading(conn, r["id"], r["name"])
                short = reading or short_name(r["name"], 5)
                link = _link(f"{short}  ({r['count']})", lambda _c=False, pid=r["id"]: self.open_narrator.emit(pid),
                             f"{r['name']}\n" + tr("Open this narrator"))
                col.addWidget(link)
            if not items:
                col.addWidget(_label("—", "Caption"))
            col.addStretch(1)
            cols.addLayout(col, 1)
        box.addLayout(cols)
        if rel["compilers"]:
            parts = " · ".join(f"{html.escape(c['book'])} ({c['count']:,})" for c in rel["compilers"])
            box.addWidget(_label(tr("<b>Compilers who narrate from him directly:</b> {parts}", parts=parts), "Lead", rich=True))

        # the hadith
        hadith, total = core_narrators.hadiths_of(conn, person_id)
        card, box = self._card(tr("In the chains of {total:,} hadith", total=total))
        if hadith:
            # one table of equal columns, so the links stand in straight columns; the book named once per run
            wrap = QWidget()
            grid = QGridLayout(wrap)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(2)
            columns = 6
            cell = 0
            last_book = None
            for h in hadith:
                if h["book"] != last_book:
                    if cell % columns:
                        cell += columns - cell % columns            # a new book starts a new row
                    head = _label(html.escape(h["book"]), "FilterLabel", wrap=False, rich=True)
                    grid.addWidget(head, cell // columns, 0, 1, columns)
                    cell += columns
                    last_book = h["book"]
                link = _link(tr("hadith {number}", number=h["number"]),
                             lambda _c=False, hid=h["hadith_id"]: self.open_chain.emit(hid),
                             f"{h['book']} {h['number']}\n" + tr("Open this chain"))
                grid.addWidget(link, cell // columns, cell % columns, Qt.AlignmentFlag.AlignLeft)
                cell += 1
            for c in range(columns):
                grid.setColumnStretch(c, 1)
            box.addWidget(wrap)
            if total > len(hadith):
                box.addWidget(_label(tr("… and {value:,} more.", value=total - len(hadith)), "Caption"))
        else:
            box.addWidget(_label(tr("Not identified in any imported chain yet."), "Caption"))
        self.detail_box.addStretch(1)
        _ = t

    def select(self, person_id: int) -> None:
        """Show a narrator, from this page or from another (the chain page)."""
        conn = self.conn
        row = conn.execute("SELECT COALESCE(tradition, 'sunni') FROM persons WHERE id = ?", (person_id,)).fetchone() \
            if conn is not None else None
        if row and self.tradition and row[0] != self.tradition:
            self.set_tradition(row[0])              # a Shia narrator opened while Sunni ones are shown, or the reverse
        if any(r["id"] == person_id for r in getattr(self, "_rows_left", [])[:ROWS_BATCH * 2]):
            self._flush_rows()                       # he is just about to be listed: list him now to mark him
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == person_id:
                self.list.blockSignals(True)
                self.list.setCurrentRow(i)
                self.list.blockSignals(False)
                break
        self.show_person(person_id)

    def retheme(self) -> None:
        self.refresh()

    def release(self) -> None:
        """Let go of the list and the detail before a new theme; retheme() builds them again (UI5-P)."""
        self.list.clear()
        self._clear()
