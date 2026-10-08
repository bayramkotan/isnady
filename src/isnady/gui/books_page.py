"""Books (BR1): open any imported work and read it in its own order — a hadith collection chapter by chapter,
the Taqrib letter by letter, and later every kind of book (core.works). Each hadith keeps its card (chain,
narrators, other narrations, grades); each narrator's entry opens the narrator."""

import html

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from isnady import config
from isnady.core import search as core
from isnady.core import works as core_works
from isnady.core.names import latin
from isnady.core.normalize import normalize
from isnady.core.scholars import find as find_scholar
from isnady.gui import theme
from isnady.gui.widgets import TextBlock

BATCH = 12           # items drawn at a time, so a long chapter never freezes the window
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
        title = _label("Books", "CardTitle")
        title.setFont(theme.reading_font(18, bold=True))
        lbox.addWidget(title)
        lbox.addWidget(_label("Open a book and read it in its own order, chapter by chapter.", "Caption"))
        self.works = QListWidget()
        self.works.setObjectName("NarratorList")
        self.works.setMaximumHeight(250)
        self.works.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.works.currentItemChanged.connect(lambda item, _p: item and self.open_work(item.data(Qt.ItemDataRole.UserRole)))
        lbox.addWidget(self.works)
        lbox.addWidget(_label("Contents", "FilterLabel"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setObjectName("Contents")
        self.tree.itemClicked.connect(lambda item, _c: item.data(0, Qt.ItemDataRole.UserRole) and
                                      self.open_chapter(item.data(0, Qt.ItemDataRole.UserRole)))
        lbox.addWidget(self.tree, 1)

        # the reading pane
        self.where = _label("", "Lead", rich=True)
        self.prev_button = QPushButton("‹ Previous")
        self.next_button = QPushButton("Next ›")
        for b in (self.prev_button, self.next_button):
            b.setObjectName("Quiet")
        self.prev_button.clicked.connect(lambda: self._step(-1))
        self.next_button.clicked.connect(lambda: self._step(+1))
        self.find = QLineEdit()
        self.find.setPlaceholderText("Find in this chapter")
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
        bar = QHBoxLayout()
        bar.addWidget(self.prev_button)
        bar.addWidget(self.next_button)
        bar.addSpacing(12)
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
        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(self.where)
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
    def refresh(self) -> None:
        conn = self.conn
        if conn is None:
            return
        core_works.ensure_collection_works(conn)
        shelf = core_works.list_works(conn)
        self.works.blockSignals(True)
        self.works.clear()
        for w in shelf:
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
            unit = "hadith" if w["kind"] == "hadith" else "entries"
            facts = [core_works.KIND_LABELS.get(w["kind"], "Book"), f"{w['leaves']:,} {unit}", f"{w['chapters']} chapters"]
            if author:
                facts.insert(0, author.get("tr") or author["name"])
            box.addWidget(_label(" · ".join(facts), "Caption", wrap=False))
            item.setSizeHint(row.sizeHint())
            self.works.addItem(item)
            self.works.setItemWidget(item, row)
        self.works.blockSignals(False)
        if not shelf:
            self._clear()
            self.where.setText("")
            self.body_layout.addWidget(_label("No books yet: import a collection (File → Data Sources).", "Lead"))
            return
        wanted = (self._work or {}).get("key") or config.state_get("reader.last_work") or shelf[0]["key"]
        keys = [w["key"] for w in shelf]
        self.select_work(wanted if wanted in keys else keys[0])

    def select_work(self, key: str) -> None:
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
        remembered = config.state_get(f"reader.position.{key}")
        target = chapter or (remembered if remembered in self._order else (self._order[0] if self._order else None))
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
        langs = [r[0] for r in self.conn.execute(
            """SELECT DISTINCT e.language FROM editions e JOIN collections c ON c.id = e.collection_id
               WHERE c.key = ? ORDER BY (e.language != 'Arabic'), e.language""", (self._work["key"],))]
        from isnady.core import language

        # the book's own choice; without one, the content languages (L1) — and every language when none is among them
        saved = (config.state_get(f"reader.languages.{self._work['key']}")
                 or [lang for lang in langs if language.shows(lang)] or langs)
        for lang in langs:
            box = QCheckBox(lang)
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
                w.setParent(None)
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
                           + (f"&nbsp;&nbsp;<span style='color:{theme.current().muted}'>chapter {position} of "
                              f"{len(self._order)}</span>" if position else ""))
        self.prev_button.setEnabled(position > 1)
        self.next_button.setEnabled(0 < position < len(self._order))
        self._select_in_tree(chapter_id)
        items, total = core_works.leaves(conn, chapter_id)
        wanted = normalize(self.find.text()).split()
        if wanted:
            items = [i for i in items if self._matches(i, wanted)]
        self._items = items
        self._clear()
        note = f"{len(items):,} of {total:,} match “{self.find.text()}”" if wanted else f"{total:,} in this chapter"
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
                earlier = QPushButton(f"Show the {self._shown:,} earlier items in this chapter")
                earlier.setObjectName("Quiet")
                earlier.clicked.connect(lambda: self.open_chapter(chapter_id, keep_find=True))
                self.body_layout.addWidget(earlier, 0, Qt.AlignmentFlag.AlignHCenter)
        self.body_layout.addStretch(1)
        self._more()
        self.scroll.verticalScrollBar().setValue(0)

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
        self._draw(token, self._shown, end)

    def _draw(self, token: int, start: int, end: int) -> None:
        if token != self._token:
            return                                       # another chapter replaced this one
        stretch = self.body_layout.takeAt(self.body_layout.count() - 1)
        stop = min(end, start + BATCH)
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
            self.more.setText(f"Show {min(PAGE, left)} more ({left:,} left in this chapter)")
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
            box.addWidget(_label("Cross-reference", "Caption"))
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
            go = QPushButton("Open narrator")
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

    def show_person(self, person_id: int) -> None:
        """Open the rijal work and chapter of a narrator's entry (from the Narrators or Shia Rijal pages)."""
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
