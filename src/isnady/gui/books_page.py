"""Books (BR1): open any imported work and read it in its own order — a hadith collection chapter by chapter,
the Taqrib letter by letter, and later every kind of book (core.works). Each hadith keeps its card (chain,
narrators, other narrations, grades); each narrator's entry opens the narrator."""

import html

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QButtonGroup,
    QInputDialog,
    QMenu,
    QToolButton,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from isnady import config
from isnady.core import search as core
from isnady.core import readmarks
from isnady.core import works as core_works
from isnady.core.names import latin
from isnady.core.normalize import normalize
from isnady.core.scholars import find as find_scholar
from isnady.gui import theme
from isnady.gui.hadith_nav import HadithNavigator
from isnady.gui.widgets import FlowLayout, TextBlock
from isnady.core.i18n import N_, tr

BATCH = 12           # items drawn at a time, so a long chapter never freezes the window
FIRST = 4            # the first few drawn at once, the rest after the window has shown them (2026-10-12)
PAGE = 60            # items per "show more"


def _unhighlight(widget) -> None:
    """Remove the brief highlight — unless the card is gone already (another chapter was opened meanwhile)."""
    try:
        widget.setStyleSheet("")
    except RuntimeError:
        pass


def _label(text: str, name: str = "", wrap: bool = True, rich: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if rich:
        label.setTextFormat(Qt.TextFormat.RichText)
    return label


class BooksPage(QWidget):
    open_chain = Signal(int)
    open_narrator = Signal(int)
    search_in_chapter = Signal(str, int, str)       # book key, chapter id, its title (SRCH-SEC1)
    visited_book = Signal(str)                      # a book picked in the list → back and forward (NAV2b)
    visited_chapter = Signal(int)                   # a chapter picked in the contents → back and forward

    def __init__(self, connection_getter, card_maker, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._conn_of = connection_getter
        self._make_card = card_maker
        self._work: dict | None = None
        self._chapter: int | None = None
        self._order: list[int] = []
        self._shown = 0
        self._token = 0

        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(400)
        lbox = QVBoxLayout(left)
        lbox.setContentsMargins(18, 16, 18, 14)
        lbox.setSpacing(8)
        title = _label(tr("Books"), "CardTitle")
        title.setFont(theme.reading_font(18, bold=True))
        lbox.addWidget(title)
        lbox.addWidget(_label(tr("Open a book and read it in its own order, chapter by chapter."), "Caption"))
        # Sunni and Shia on one shelf, each under its own heading; the switch shows one of them alone (SH1)
        # the Sunni books first, each time isnady opens (NR-DEF1, Bayram 2026-10-20: "ilk açıldığında default Sunni …
        # kitaplar ve alimler içinde"); the reader's choice holds while it runs
        self._shelf_tradition: str | None = "sunni"
        self._shelf_buttons = QButtonGroup(self)
        seg = QHBoxLayout()
        seg.setSpacing(6)
        for key, text in ((None, N_("All")), ("sunni", N_("Sunni")), ("shia", N_("Shia"))):
            b = QPushButton(tr(text))
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setProperty("tradition", key)
            b.setChecked(key == self._shelf_tradition)
            self._shelf_buttons.addButton(b)
            seg.addWidget(b)
        seg.addStretch(1)
        self._shelf_buttons.buttonClicked.connect(lambda b: self.set_shelf(b.property("tradition")))
        lbox.addLayout(seg)
        self.works = QListWidget()
        self.works.setObjectName("NarratorList")
        self.works.setMinimumHeight(250)
        self.works.setMaximumHeight(340)
        self.works.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.works.currentItemChanged.connect(lambda item, _p: item and self._picked_work(item.data(Qt.ItemDataRole.UserRole)))
        # right-click (CTX1): open, where I left it, its markers, search in it, copy its name
        self.works.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.works.customContextMenuRequested.connect(self._work_menu)
        lbox.addWidget(self.works)
        lbox.addWidget(_label(tr("Contents"), "FilterLabel"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setObjectName("Contents")
        self.tree.itemClicked.connect(lambda item, _c: item.data(0, Qt.ItemDataRole.UserRole) and
                                      self._picked_chapter(item.data(0, Qt.ItemDataRole.UserRole)))
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._chapter_menu)
        lbox.addWidget(self.tree, 1)

        # the reading pane
        self.where = _label("", "Lead", rich=True)
        # going through the book (NAV3, Bayram 2026-10-24: "kitaplari rahat dolasmak lazim! Max hadis nerede????
        # max sayfa numarasi?????"): chapter by number, first / previous / next / last, and the hadith by its number
        self.first_chapter = QPushButton("⏮")
        self.prev_button = QPushButton("‹  " + tr("Previous chapter"))
        self.next_button = QPushButton(tr("Next chapter") + "  ›")
        self.last_chapter = QPushButton("⏭")
        self.first_chapter.setToolTip(tr("The first chapter"))
        self.last_chapter.setToolTip(tr("The last chapter"))
        for b in (self.first_chapter, self.prev_button, self.next_button, self.last_chapter):
            b.setObjectName("Quiet")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_button.clicked.connect(lambda: self._step(-1))
        self.next_button.clicked.connect(lambda: self._step(+1))
        self.first_chapter.clicked.connect(lambda: self._order and self.open_chapter(self._order[0]))
        self.last_chapter.clicked.connect(lambda: self._order and self.open_chapter(self._order[-1]))
        self.chapter_spin = QSpinBox()
        self.chapter_spin.setMinimum(1)
        self.chapter_spin.setKeyboardTracking(False)       # goes when Enter is pressed or the arrows are used
        self.chapter_spin.setMinimumWidth(80)
        self.chapter_spin.setToolTip(tr("Type a chapter's place in the book and press Enter"))
        self.chapter_spin.valueChanged.connect(self._chapter_typed)
        self.chapter_count = QLabel("")
        self.chapter_count.setObjectName("FilterLabel")
        self.nav = HadithNavigator(lambda: self.conn, tr("Show"))
        self.nav.activated.connect(self._hadith_typed)
        self.find = QLineEdit()
        self.find.setPlaceholderText(tr("Find in this chapter"))
        self.find.setClearButtonEnabled(True)
        self.find.setMaximumWidth(280)
        self._find_timer = QTimer(self)
        self._find_timer.setSingleShot(True)
        self._find_timer.setInterval(300)
        self._find_timer.timeout.connect(lambda: self._chapter and self.open_chapter(self._chapter, keep_find=True))
        self.find.textChanged.connect(lambda _t: self._find_timer.start())
        self.languages_box = QHBoxLayout()
        self.languages_box.setSpacing(10)
        self._language_checks: dict[str, QCheckBox] = {}
        chapters = QWidget()
        chapter_flow = FlowLayout(chapters, spacing=8)
        chapter_caption = QLabel(tr("Chapter"))
        chapter_caption.setObjectName("FilterLabel")
        for w in (chapter_caption, self.chapter_spin, self.chapter_count, self.first_chapter, self.prev_button,
                  self.next_button, self.last_chapter):
            chapter_flow.addWidget(w)
        bar = QHBoxLayout()
        bar.addLayout(self.languages_box)
        bar.addStretch(1)
        bar.addWidget(self.find)

        self.body = QWidget()
        self.body.setObjectName("Page")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 4, 4, 16)
        self.body_layout.setSpacing(14)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.body)
        # where the reader has come to: the hadith at the top of the page, kept a moment after the scrolling stops
        self._reading_timer = QTimer(self)
        self._reading_timer.setSingleShot(True)
        self._reading_timer.setInterval(700)
        self._reading_timer.timeout.connect(self._remember_reading)
        self.scroll.verticalScrollBar().valueChanged.connect(lambda _v: self._reading_timer.start())
        right = QVBoxLayout()
        right.setSpacing(8)
        where_row = QHBoxLayout()
        where_row.addWidget(self.where, 1)
        self.star_box = QHBoxLayout()           # the ☆ of the chapter shown (BM1)
        where_row.addLayout(self.star_box)
        # the reader's markers (BM3, Bayram: "Kitaplarda nerede kaldım?"): put one here, go to one, or to where each
        # book was left
        self.marks_button = QToolButton()
        self.marks_button.setText("🔖 " + tr("Markers"))
        self.marks_button.setObjectName("Quiet")
        self.marks_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.marks_button.setToolTip(tr("Put a marker where you are reading, go to one of your markers, or to where "
                                        "you left each book"))
        self.marks_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.marks_menu = QMenu(self.marks_button)
        self.marks_menu.aboutToShow.connect(self._fill_marks_menu)
        self.marks_button.setMenu(self.marks_menu)
        where_row.addWidget(self.marks_button)
        # search the words in the chapter being read, and the chapters under it (SRCH-SEC1, Bayram 2026-10-27:
        # "Kitaplarin belli bolumlerinde ara eklenebilir mi?")
        self.search_here = QToolButton()
        self.search_here.setText("🔎 " + tr("Search in this chapter"))
        self.search_here.setObjectName("Quiet")
        self.search_here.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_here.setToolTip(tr("Search only in the chapter you are reading and the chapters under it"))
        self.search_here.clicked.connect(self._search_here)
        where_row.addWidget(self.search_here)
        right.addLayout(where_row)
        right.addWidget(chapters)
        right.addWidget(self.nav)
        right.addLayout(bar)
        right.addWidget(self.scroll, 1)
        self.more = QPushButton()
        self.more.setObjectName("Quiet")
        self.more.clicked.connect(self._more)

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)
        root.addWidget(left)
        root.addLayout(right, 1)

    @property
    def conn(self):
        return self._conn_of()

    # ------------------------------------------------------------------ the shelf
    def refresh(self, keep_open: bool = False) -> None:
        """The shelf drawn again; keep_open: the book and chapter being read stay as they are (only the list)."""
        conn = self.conn
        if conn is None:
            return
        core_works.ensure_collection_works(conn)
        shelf = [w for w in core_works.list_works(conn)
                 if self._shelf_tradition is None or w["tradition"] == self._shelf_tradition]
        self.works.blockSignals(True)
        self.works.clear()
        heading = None
        for w in shelf:
            if w["tradition"] != heading:
                heading = w["tradition"]
                head = QListWidgetItem()
                head.setFlags(Qt.ItemFlag.NoItemFlags)          # a heading, not a book
                text = {"sunni": N_("Sunni books · {count}"), "shia": N_("Shia books · {count}")}.get(
                    heading, N_("Other books · {count}"))
                count = sum(1 for x in shelf if x["tradition"] == heading)
                label = _label(tr(text, count=count), "FilterTitle", wrap=False)
                label.setContentsMargins(10, 10, 10, 2)
                if heading == "shia":
                    label.setStyleSheet(f"color: {theme.current().gold};")
                head.setSizeHint(label.sizeHint())
                self.works.addItem(head)
                self.works.setItemWidget(head, label)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, w["key"])
            row = QWidget()
            box = QVBoxLayout(row)
            box.setContentsMargins(10, 7, 10, 7)
            box.setSpacing(1)
            name = _label(w["title"], "RowTitle", wrap=False)
            name.setFont(theme.reading_font(14, bold=True))
            box.addWidget(name)
            author = find_scholar(w["author"]) if w["author"] else None
            leaves = (tr("{n:,} hadith", n=w["leaves"]) if w["kind"] == "hadith" else tr("{n:,} entries", n=w["leaves"]))
            facts = [tr(core_works.KIND_LABELS.get(w["kind"], "Book")), leaves, tr("{n} chapters", n=w["chapters"])]
            if author:
                facts.insert(0, html.escape(author.get("tr") or author["name"]))
            if w["tradition"] == "shia":
                facts.insert(0, f"<span style='color:{theme.current().gold}'><b>{tr('Shia')}</b></span>")
            box.addWidget(_label(" · ".join(facts), "Caption", wrap=False, rich=True))
            left_at = readmarks.last(w["key"])
            if left_at and (left_at["number"] or left_at["place"]):
                where = (tr("hadith {number}", number=left_at["number"]) if left_at["number"]
                         else tr("chapter {position}", position=left_at["place"]))
                box.addWidget(_label("🔖 " + tr("You left off at {where}", where=where), "Caption", wrap=False))
            item.setSizeHint(row.sizeHint())
            self.works.addItem(item)
            self.works.setItemWidget(item, row)
        self.works.blockSignals(False)
        if not shelf:
            self._clear()
            self.where.setText("")
            self.body_layout.addWidget(_label(tr("No books yet: import a collection (File → Data Sources)."), "Lead"))
            return
        wanted = (self._work or {}).get("key") or config.state_get("reader.last_work") or shelf[0]["key"]
        keys = [w["key"] for w in shelf]
        if keep_open and self._work and self._work.get("key") in keys:
            for i in range(self.works.count()):              # the row of the book being read, marked again
                if self.works.item(i).data(Qt.ItemDataRole.UserRole) == self._work["key"]:
                    self.works.blockSignals(True)
                    self.works.setCurrentRow(i)
                    self.works.blockSignals(False)
            return
        self.select_work(wanted if wanted in keys else keys[0])

    def set_shelf(self, tradition: str | None) -> None:
        """Show every book, or only the Sunni or only the Shia ones."""
        self._shelf_tradition = tradition
        for b in self._shelf_buttons.buttons():
            b.setChecked(b.property("tradition") == tradition)
        self.refresh()

    def select_work(self, key: str) -> None:
        w = next((x for x in core_works.list_works(self.conn) if x["key"] == key), None) if self.conn else None
        if w and self._shelf_tradition and w["tradition"] != self._shelf_tradition:
            self._shelf_tradition = w["tradition"]           # a book of the other tradition was asked for: its shelf
            for b in self._shelf_buttons.buttons():
                b.setChecked(b.property("tradition") == self._shelf_tradition)
            self.refresh()
        for i in range(self.works.count()):
            if self.works.item(i).data(Qt.ItemDataRole.UserRole) == key:
                self.works.blockSignals(True)
                self.works.setCurrentRow(i)
                self.works.blockSignals(False)
        self.open_work(key)

    def open_work(self, key: str, chapter: int | None = None) -> None:
        conn = self.conn
        work = core_works.find_work(conn, key)
        if work is None:
            return
        self._work = work
        config.state_set("reader.last_work", key)
        self._order = core_works.reading_order(conn, work["id"])
        self.chapter_spin.blockSignals(True)
        self.chapter_spin.setMaximum(max(1, len(self._order)))
        self.chapter_spin.blockSignals(False)
        self.chapter_count.setText("/ " + f"{len(self._order):,}")
        self.chapter_count.setToolTip(tr("{n} chapters in this book", n=f"{len(self._order):,}"))
        self.nav.setVisible(work["kind"] == "hadith")
        self.nav.set_book(work["key"] if work["kind"] == "hadith" else None)
        self.tree.clear()

        def add(parent_item, parent_id):
            for c in core_works.containers(conn, work["id"], parent_id):
                label = (f"{c['label']}. " if c["label"] and work["kind"] == "hadith" else "") + (c["title"] or "")
                count = f"   ({c['leaves']})" if c["leaves"] else ""
                item = QTreeWidgetItem([label + count])
                item.setData(0, Qt.ItemDataRole.UserRole, c["id"] if c["leaves"] else None)
                if any("\\u0600" <= ch <= "\\u06ff" for ch in label):
                    item.setFont(0, theme.script_font("arabic", factor=0.62))
                (parent_item.addChild(item) if parent_item else self.tree.addTopLevelItem(item))
                if c["subchapters"]:
                    add(item, c["id"])
        add(None, None)
        self._build_language_checks()
        if chapter:
            self.open_chapter(chapter)
            return
        # where the book was left (BM3): its chapter, scrolled to the hadith the reader had come to
        left_at = readmarks.last(key)
        if left_at:
            at, hid = readmarks.resolve(conn, left_at)
            if at in self._order:
                self.open_chapter(at, focus_hadith=hid)
                return
        remembered = config.state_get(f"reader.position.{key}")
        target = remembered if remembered in self._order else (self._order[0] if self._order else None)
        if target:
            self.open_chapter(target)

    def _build_language_checks(self) -> None:
        while self.languages_box.count():
            w = self.languages_box.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._language_checks = {}
        if not self._work or self._work["kind"] != "hadith":
            return
        from isnady.core import language

        langs = language.sort(r[0] for r in self.conn.execute(
            """SELECT DISTINCT e.language FROM editions e JOIN collections c ON c.id = e.collection_id
               WHERE c.key = ?""", (self._work["key"],)))

        # the book's own choice; without one, the content languages (L1) — and every language when none is among them
        saved = (config.state_get(f"reader.languages.{self._work['key']}")
                 or [lang for lang in langs if language.shows(lang)] or langs)
        for lang in langs:
            box = QCheckBox(tr(lang))
            box.setChecked(lang in saved)
            box.toggled.connect(self._languages_changed)
            self._language_checks[lang] = box
            self.languages_box.addWidget(box)

    def _languages_changed(self) -> None:
        chosen = [l for l, b in self._language_checks.items() if b.isChecked()]
        config.state_set(f"reader.languages.{self._work['key']}", chosen)
        if self._chapter:
            self.open_chapter(self._chapter, keep_find=True)

    # ------------------------------------------------------------------ reading
    def _clear(self) -> None:
        self._token += 1
        self.more.setParent(None)
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                # hidden and deleted when the event loop is free: taking each card out of the page one by one
                # (setParent(None)) cost 80 ms on every new chapter (PERF1)
                w.hide()
                w.deleteLater()

    def open_chapter(self, chapter_id: int, keep_find: bool = False, focus_hadith: int | None = None,
                     focus_person: int | None = None) -> None:
        conn = self.conn
        if conn is None or self._work is None:
            return
        if not keep_find and self.find.text():
            self.find.blockSignals(True)
            self.find.clear()
            self.find.blockSignals(False)
        self._chapter = chapter_id
        config.state_set(f"reader.position.{self._work['key']}", chapter_id)
        crumbs = [self._work["title"]] + [((p["label"] + ". ") if p["label"] and self._work["kind"] == "hadith" else "")
                                          + (p["title"] or "") for p in core_works.path(conn, chapter_id)]
        position = self._order.index(chapter_id) + 1 if chapter_id in self._order else 0
        self.where.setText(" › ".join(f"<b>{html.escape(c)}</b>" if i == len(crumbs) - 1 else html.escape(c)
                                      for i, c in enumerate(crumbs))
                           + (f"&nbsp;&nbsp;<span style='color:{theme.current().muted}'>"
                              + tr("chapter {position} of {count}", position=position, count=len(self._order))
                              + "</span>" if position else ""))
        self.prev_button.setEnabled(position > 1)
        self.first_chapter.setEnabled(position > 1)
        self.next_button.setEnabled(0 < position < len(self._order))
        self.last_chapter.setEnabled(0 < position < len(self._order))
        if position:
            self.chapter_spin.blockSignals(True)
            self.chapter_spin.setValue(position)
            self.chapter_spin.blockSignals(False)
        self._chapter_star(chapter_id)
        self._select_in_tree(chapter_id)
        self._remember_place(chapter_id, focus_hadith)
        items, total = core_works.leaves(conn, chapter_id)
        if self._work["kind"] == "hadith":
            # the number field shows the hadith asked for, or the first of the chapter
            shown = focus_hadith or next((i["hadith_id"] for i in items if i.get("hadith_id")), None)
            row = conn.execute("SELECT number FROM hadiths WHERE id = ?", (shown,)).fetchone() if shown else None
            self.nav.set_number(row[0] if row else "")
        wanted = normalize(self.find.text()).split()
        if wanted:
            items = [i for i in items if self._matches(i, wanted)]
        self._items = items
        self._clear()
        note = (tr("{n:,} of {total:,} match “{words}”", n=len(items), total=total, words=self.find.text()) if wanted
                else tr("{total:,} in this chapter", total=total))
        self.body_layout.addWidget(_label(note, "Caption"))
        self._shown = 0
        self._focus = ("hadith", focus_hadith) if focus_hadith is not None else (("person", focus_person) if focus_person else None)
        if self._focus is not None:
            # start a little before that item, not at the top: a hadith deep in a long chapter (al-Bukhari 7183 is
            # the 293rd of 308) shows at once instead of after drawing every card before it
            field, value = self._focus
            at = next((i for i, it in enumerate(items) if it.get(f"{field}_id") == value), None)
            if at is not None and at > 3:
                self._shown = at - 2
                earlier = QPushButton(tr("Show the {shown:,} earlier items in this chapter", shown=self._shown))
                earlier.setObjectName("Quiet")
                earlier.clicked.connect(lambda: self.open_chapter(chapter_id, keep_find=True))
                self.body_layout.addWidget(earlier, 0, Qt.AlignmentFlag.AlignHCenter)
        self.body_layout.addStretch(1)
        self._more()
        self.scroll.verticalScrollBar().setValue(0)

    # ------------------------------------------------------------------ where the reader is (BM3)
    def _remember_place(self, chapter_id: int, hadith_id: int | None = None) -> None:
        if self._work is None or self.conn is None:
            return
        p = readmarks.place_of(self.conn, self._work["key"], chapter_id, hadith_id)
        readmarks.remember(p["book"], p["chapter"], p["number"], p["title"], p["place"])

    def _top_hadith(self) -> int | None:
        """The hadith whose card is at the top of the reading pane now."""
        top = self.scroll.verticalScrollBar().value()
        for i in range(self.body_layout.count()):
            w = self.body_layout.itemAt(i).widget()
            if w is not None and not w.isHidden() and w.property("hadith_id") and w.y() + w.height() > top + 8:
                return w.property("hadith_id")
        return None

    def _remember_reading(self) -> None:
        if self._chapter and self._work and self._work["kind"] == "hadith":
            hid = self._top_hadith()
            if hid:
                self._remember_place(self._chapter, hid)

    def _fill_marks_menu(self) -> None:
        """Put a marker here; then each marker with Go, Rename and Remove right under it, and each book's last place
        with Go and Forget (BM3b, Bayram 2026-10-27: "ayraci kaldirma bulamadim" — Remove was a submenu at the
        bottom, and the place a book was left could not be forgotten at all)."""
        menu = self.marks_menu
        menu.clear()
        here = menu.addAction(tr("Put a marker here…"))
        here.setEnabled(bool(self._work and self._chapter))
        here.triggered.connect(self._add_mark)
        titles = {w["key"]: w["title"] for w in core_works.list_works(self.conn)} if self.conn else {}
        mine = readmarks.marks()
        if mine:
            menu.addSection(tr("Your markers"))
            for m in mine:
                sub = menu.addMenu(f"🔖 {m['name']}   —   {readmarks.describe(m, titles.get(m['book'], ''))}")
                go = sub.addAction(tr("Go to this marker"))
                go.triggered.connect(lambda _c=False, m=m: self.go_to_mark(m))
                ren = sub.addAction(tr("Rename…"))
                ren.triggered.connect(lambda _c=False, m=m: self._rename_mark(m))
                sub.addSeparator()
                rm = sub.addAction("✕  " + tr("Remove this marker"))
                rm.triggered.connect(lambda _c=False, m=m: self._remove_mark(m))
        left = [p for p in readmarks.recent(10) if p["book"] in titles]
        if left:
            menu.addSection(tr("Where you left each book"))
            for p in left:
                sub = menu.addMenu(readmarks.describe(p, titles.get(p["book"], "")))
                go = sub.addAction(tr("Go there"))
                go.triggered.connect(lambda _c=False, p=p: self.go_to_mark(p))
                sub.addSeparator()
                fg = sub.addAction("✕  " + tr("Forget where I left this book"))
                fg.triggered.connect(lambda _c=False, key=p["book"]: self._forget_place(key))
        if mine or left:
            menu.addSeparator()
        if mine:
            every = menu.addAction("✕  " + tr("Remove all markers…"))
            every.triggered.connect(self._remove_all_marks)
        if left:
            places = menu.addAction("✕  " + tr("Forget where I left every book…"))
            places.triggered.connect(lambda: self._forget_place(None))

    def _picked_work(self, key: str) -> None:
        self.open_work(key)
        self.visited_book.emit(key)

    def _picked_chapter(self, chapter_id: int) -> None:
        self.open_chapter(chapter_id)
        self.visited_chapter.emit(chapter_id)

    # ------------------------------------------------------------------ right-click menus (CTX1)
    def _work_menu(self, pos) -> None:
        from isnady.gui import context_menu as cm

        item = self.works.itemAt(pos)
        key = item.data(Qt.ItemDataRole.UserRole) if item else None
        conn = self.conn
        work = core_works.find_work(conn, key) if key and conn else None
        if work is None:
            return
        left_at = readmarks.last(key)
        marks = [m for m in readmarks.marks() if m["book"] == key]
        hadith = work["kind"] == "hadith"
        root = self._first_chapter_of(work) if hadith else None
        cm.popup(self.works, self.works.viewport().mapToGlobal(pos), [
            (tr("Open"), lambda: self.select_work(key)),
            (tr("Go where I left this book"), (lambda: self.go_to_mark(left_at)) if left_at else None),
            (tr("Markers in this book"), [(f"🔖 {m['name']}", lambda m=m: self.go_to_mark(m)) for m in marks]),
            (tr("From the first chapter"), (lambda: self._open_at(key, root)) if root else None),
            None,
            (tr("Copy the name of the book"), lambda: cm.copy(work["title"])),
            *([("✕  " + tr("Forget where I left this book"), lambda: self._forget_place(key))] if left_at else []),
        ])

    def _first_chapter_of(self, work: dict) -> int | None:
        order = core_works.reading_order(self.conn, work["id"])
        return order[0] if order else None

    def _open_at(self, key: str, chapter: int) -> None:
        if not self._work or self._work["key"] != key:
            self.select_work(key)
        self.open_chapter(chapter)

    def _chapter_menu(self, pos) -> None:
        from isnady.core import bookmarks
        from isnady.gui import context_menu as cm

        item = self.tree.itemAt(pos)
        if item is None or not self._work:
            return
        chapter = item.data(0, Qt.ItemDataRole.UserRole)
        title = item.text(0).rsplit("   (", 1)[0]
        ref = bookmarks.chapter_ref(self.conn, chapter) if chapter else None
        hadith = self._work.get("kind") == "hadith"

        def go(then=None):
            self.open_chapter(chapter)
            if then:
                then()
        cm.popup(self.tree, self.tree.viewport().mapToGlobal(pos), [
            (tr("Open this chapter"), (lambda: go()) if chapter else None),
            *([(tr("Search in this chapter"), (lambda: go(self._search_here)) if chapter else None)] if hadith else []),
            (tr("Put a marker here…"), (lambda: go(self._add_mark)) if chapter else None),
            None,
            cm.bookmark_entry("chapter", ref[0], ref[1], ref[2]) if ref else None,
            (tr("Copy the chapter title"), lambda: cm.copy(title)),
        ])

    def _search_here(self) -> None:
        if not (self._work and self._chapter):
            return
        if self._work.get("kind") not in (None, "hadith"):
            self._say(tr("Only the books of hadith are searched; this is a book of narrators."))
            return
        trail = core_works.path(self.conn, self._chapter)
        title = " › ".join(((n["label"] + ". ") if n["label"] else "") + (n["title"] or "") for n in trail)
        self.search_in_chapter.emit(self._work["key"], self._chapter, title)   # the book shows beside it

    def _remove_mark(self, mark: dict) -> None:
        readmarks.remove(mark["id"])
        self._say(tr("Marker removed: {name}", name=mark["name"]))

    def _remove_all_marks(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        mine = readmarks.marks()
        if QMessageBox.question(self, tr("Remove all markers"),
                                tr("Remove all {n} of your markers? Where you left each book is kept.", n=len(mine))
                                ) != QMessageBox.StandardButton.Yes:
            return
        for m in mine:
            readmarks.remove(m["id"])
        self._say(tr("{n} markers removed", n=len(mine)))

    def _forget_place(self, key: str | None) -> None:
        """Forget where one book (key) or every book (None) was left; its "You left off at" line goes too."""
        from PySide6.QtWidgets import QMessageBox

        if key is None and QMessageBox.question(
                self, tr("Forget where I left every book"),
                tr("Forget where you left every book? Your named markers are kept.")) != QMessageBox.StandardButton.Yes:
            return
        n = readmarks.forget(key)
        self._say(tr("Forgot where you left {n} books", n=n) if key is None else tr("Forgot where you left this book"))
        self.refresh(keep_open=True)

    def _say(self, text: str) -> None:
        """A short word in the window's bottom line (the main window's footer), or nothing."""
        try:
            self.window()._set_footer(text)
        except Exception:
            pass

    def _add_mark(self) -> None:
        if not (self._work and self._chapter):
            return
        hid = self._top_hadith() if self._work["kind"] == "hadith" else None
        p = readmarks.place_of(self.conn, self._work["key"], self._chapter, hid)
        suggested = readmarks.describe(p, self._work["title"])
        name, ok = QInputDialog.getText(self, tr("Put a marker here"), tr("Name of the marker:"), text=suggested)
        if ok:
            readmarks.add(name, p["book"], p["chapter"], p["number"], p["title"], p["place"])

    def _rename_mark(self, mark: dict) -> None:
        name, ok = QInputDialog.getText(self, tr("Rename a marker"), tr("Name of the marker:"), text=mark["name"])
        if ok and name.strip():
            readmarks.rename(mark["id"], name)

    def go_to_mark(self, mark: dict) -> None:
        """Open a kept place: its book, its chapter, the hadith it was at."""
        if self.conn is None:
            return
        chapter, hid = readmarks.resolve(self.conn, mark)
        if chapter is None:
            return
        if self.works.count() == 0:
            self.refresh()
        if not self._work or self._work["key"] != mark["book"]:
            self.select_work(mark["book"])
        self.open_chapter(chapter, focus_hadith=hid)

    def _matches(self, item: dict, wanted: list[str]) -> bool:
        if item["kind"] == "hadith":
            text = " ".join(t for (t,) in self.conn.execute("SELECT text FROM texts WHERE hadith_id = ?", (item["hadith_id"],)))
        else:
            text = item.get("text") or item.get("title") or ""
        folded = normalize(text)
        return all(w in folded for w in wanted)

    def _more(self) -> None:
        self._token += 1
        token = self._token
        end = min(len(self._items), self._shown + PAGE)

        self.more.setParent(None)
        self._draw(token, self._shown, end, FIRST)

    def _draw(self, token: int, start: int, end: int, batch: int = BATCH) -> None:
        if token != self._token:
            return                                       # another chapter replaced this one
        stretch = self.body_layout.takeAt(self.body_layout.count() - 1)
        stop = min(end, start + batch)
        query = core.SearchQuery(text="", languages=[l for l, b in self._language_checks.items() if b.isChecked()])
        for item in self._items[start:stop]:
            self.body_layout.addWidget(self._item_widget(item, query))
        self._shown = stop
        if stop < end:
            if stretch is not None:
                self.body_layout.addItem(stretch)
            QTimer.singleShot(0, lambda: self._draw(token, stop, end))
            return
        if getattr(self, "_focus", None) is not None:
            # twice: cards take their final height (long texts, commentary) only after the layout settles
            QTimer.singleShot(60, lambda: self._scroll_to_focus(keep=True))
            QTimer.singleShot(450, self._scroll_to_focus)
        left = len(self._items) - self._shown
        if left > 0:
            self.more.setText(tr("Show {page} more ({left:,} left in this chapter)", page=min(PAGE, left), left=left))
            self.body_layout.addWidget(self.more, 0, Qt.AlignmentFlag.AlignHCenter)
        self.body_layout.addStretch(1)

    def _item_widget(self, item: dict, query) -> QWidget:
        if item["kind"] == "hadith":
            result = core._load_result(self.conn, item["hadith_id"], [], query)
            return self._make_card(result, in_book=True)
        card = QFrame()
        card.setObjectName("Card")
        if item.get("person_id"):
            card.setProperty("person_id", item["person_id"])
        box = QVBoxLayout(card)
        box.setContentsMargins(20, 12, 20, 12)
        box.setSpacing(4)
        if item["kind"] == "reference":
            note = TextBlock(item["text"] or "", theme.script_font("arabic", factor=0.7), rtl=True)
            box.addWidget(_label(tr("Cross-reference"), "Caption"))
            box.addWidget(note)
            return card
        head = QHBoxLayout()
        head.addWidget(_label(f"#{item['label']}" if item["label"] else "", "CardNumber", wrap=False))
        if item["person_id"]:
            from isnady.core import name_parts

            view = name_parts.present(name_parts.parse((item.get("title") or "").strip()))
            reading = view["full_reading"] or latin((item.get("title") or "").strip(), "en")
            if reading:
                head.addWidget(_label(reading, "RowLatin", wrap=False))
            head.addStretch(1)
            go = QPushButton(tr("Open narrator"))
            go.setObjectName("Link")
            go.setCursor(Qt.CursorShape.PointingHandCursor)
            go.clicked.connect(lambda _c=False, pid=item["person_id"]: self.open_narrator.emit(pid))
            head.addWidget(go)
        else:
            head.addStretch(1)
        box.addLayout(head)
        box.addWidget(TextBlock(item["text"] or item.get("title") or "", theme.script_font("arabic", factor=0.85), rtl=True))
        return card

    def _scroll_to_focus(self, keep: bool = False) -> None:
        focus = self._focus
        if not keep:
            self._focus = None
        if focus is None:
            return
        self.body.layout().activate()
        for i in range(self.body_layout.count()):
            w = self.body_layout.itemAt(i).widget()
            if w is not None and w.property(f"{focus[0]}_id") == focus[1]:
                self.scroll.ensureWidgetVisible(w, 0, 40)
                y = w.mapTo(self.body, w.rect().topLeft()).y()
                self.scroll.verticalScrollBar().setValue(max(0, y - 12))
                # a short highlight so the eye finds it
                if not keep:
                    w.setStyleSheet(f"QFrame#Card {{ border: 2px solid {theme.current().gold}; }}")
                    QTimer.singleShot(2500, lambda w=w: _unhighlight(w))
                break

    def _select_in_tree(self, chapter_id: int) -> None:
        def walk(item):
            if item.data(0, Qt.ItemDataRole.UserRole) == chapter_id:
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                return True
            return any(walk(item.child(i)) for i in range(item.childCount()))
        for i in range(self.tree.topLevelItemCount()):
            if walk(self.tree.topLevelItem(i)):
                break

    def _step(self, delta: int) -> None:
        if self._chapter in self._order:
            i = self._order.index(self._chapter) + delta
            if 0 <= i < len(self._order):
                self.open_chapter(self._order[i])

    def _chapter_typed(self, place: int) -> None:
        if 0 < place <= len(self._order) and self._order[place - 1] != self._chapter:
            self.open_chapter(self._order[place - 1])

    def _hadith_typed(self) -> None:
        """A hadith number typed, or stepped to: its chapter, scrolled to it."""
        from isnady.core import isnad as core_isnad

        if not self._work or self.conn is None:
            return
        number = self.nav.number()
        hid = core_isnad.hadith_id(self.conn, self._work["key"], number)
        if hid is None:
            near = core_isnad.nearest_number(self.conn, self._work["key"], number)
            if not near:
                return
            self.nav.set_number(near)
            hid = core_isnad.hadith_id(self.conn, self._work["key"], near)
        if hid is not None:
            self.show_hadith(hid)

    def show_person(self, person_id: int) -> None:
        """Open the rijal work and chapter of a narrator's entry (from the Narrators page)."""
        conn = self.conn
        if self.works.count() == 0:
            self.refresh()
        chapter = core_works.chapter_of_person(conn, person_id)
        if chapter is None:
            return
        node = core_works.node(conn, chapter)
        work = next((w for w in core_works.list_works(conn) if w["id"] == node["work_id"]), None)
        if work:
            if not self._work or self._work["key"] != work["key"]:
                self.select_work(work["key"])
            self.open_chapter(chapter, focus_person=person_id)

    def _chapter_star(self, chapter_id: int) -> None:
        while self.star_box.count():
            w = self.star_box.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        from isnady.core import bookmarks
        from isnady.gui.bookmarks_page import BookmarkButton

        ref = bookmarks.chapter_ref(self.conn, chapter_id)
        if ref:
            self.star_box.addWidget(BookmarkButton("chapter", *ref))

    def show_chapter(self, chapter_id: int) -> None:
        """Open a chapter by its node (a bookmark)."""
        conn = self.conn
        if self.works.count() == 0:
            self.refresh()
        node = core_works.node(conn, chapter_id)
        if node is None:
            return
        work = next((w for w in core_works.list_works(conn) if w["id"] == node["work_id"]), None)
        if work:
            if not self._work or self._work["key"] != work["key"]:
                self.select_work(work["key"])
            self.open_chapter(chapter_id)

    def show_hadith(self, hadith_id: int) -> None:
        """Open the book and chapter a hadith belongs to (from a search result or a chain)."""
        conn = self.conn
        if self.works.count() == 0:
            self.refresh()                     # first visit through "In its book": fill the shelf first
        chapter = core_works.chapter_of_hadith(conn, hadith_id)
        if chapter is None:
            return
        node = core_works.node(conn, chapter)
        work = next((w for w in core_works.list_works(conn) if w["id"] == node["work_id"]), None)
        if work:
            if not self._work or self._work["key"] != work["key"]:
                self.select_work(work["key"])
            self.open_chapter(chapter, focus_hadith=hadith_id)

    def release(self) -> None:
        """Let go of the open chapter before a new theme; retheme() opens it again (UI5-P)."""
        if self._work:
            self._clear()

    def retheme(self) -> None:
        if self._work:
            self.open_work(self._work["key"], self._chapter)
