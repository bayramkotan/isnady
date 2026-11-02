"""Written sources (SHF1): Hammam's sahifa as it stands in the Musnad with its parallels, the writings that live in
later books, and writing in the chains — the Sunni road and the Shia road each on its own (SH1)."""

import html

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from isnady.core import sahifa as core
from isnady.core.i18n import N_, tr
from isnady.gui import theme

PAGE = 20                      # hadith cards drawn at a time

LAYERS = {1: N_("Came down whole"), 2: N_("Lives in later books"), 3: N_("Writing in the chains")}


def _label(text: str, name: str = "", wrap: bool = True, rich: bool = False) -> QLabel:
    from isnady.gui.widgets import WrapLabel

    label = WrapLabel(text) if wrap else QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if rich:
        label.setTextFormat(Qt.TextFormat.RichText)
    return label


class _Count(QObject):
    """The count (core.sahifa.counted, some seconds on a full database) in the background, with its own connection:
    the window is never held while it runs (Bayram, 2026-11-02: "Yazılı Kaynaklara geçtiğimizde yavaşlama oluyor,
    biraz takılıyor"). A daemon thread, not a QThread: closing isnady while it counts neither waits nor aborts."""
    done = Signal()

    def start(self) -> None:
        import threading

        threading.Thread(target=self._run, name="sahifa-count", daemon=True).start()

    def _run(self) -> None:
        from isnady.data import db

        conn = db.connect()
        try:
            core.counted(conn)
        except Exception:  # noqa: BLE001 — the page says nothing was found rather than freezing
            pass
        finally:
            conn.close()
            self.done.emit()                      # queued to the window's thread


class SahifaPage(QWidget):
    open_hadith = Signal(int)                # a hadith → in its book
    open_book = Signal(str)                  # the written source as a book of Books (SHF1b)
    wants_sources = Signal()                 # not imported yet → Data sources
    visited = Signal(str)                    # a source picked → back and forward (NAV2b)

    def __init__(self, connection_getter, card_maker, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._conn_of = connection_getter
        self._make_card = card_maker
        self._road = "sunni"                 # the Sunni road first, as every page (NR-DEF1)
        self._current: str | None = None
        self._ids: list[int] = []
        self._shown = 0
        self._counting: _Count | None = None

        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(340)
        lbox = QVBoxLayout(left)
        lbox.setContentsMargins(18, 16, 18, 14)
        lbox.setSpacing(8)
        title = _label(tr("Written sources"), "CardTitle")
        title.setFont(theme.reading_font(18, bold=True))
        lbox.addWidget(title)
        self._segments = QButtonGroup(self)
        seg = QHBoxLayout()
        seg.setSpacing(6)
        for key, text in (("sunni", N_("Sunni")), ("shia", N_("Shia"))):
            b = QPushButton(tr(text))
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setProperty("road", key)
            b.setChecked(key == self._road)
            self._segments.addButton(b)
            seg.addWidget(b)
        seg.addStretch(1)
        self._segments.buttonClicked.connect(lambda b: self.set_road(b.property("road")))
        lbox.addLayout(seg)
        lbox.addWidget(_label(tr("Most hadith came down by word of mouth; some were written in the first "
                                 "generations. What was written, and where it lives in the books imported here."),
                              "Caption"))
        self.list = QListWidget()
        self.list.setObjectName("NarratorList")
        self.list.setWordWrap(True)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(lambda item, _p: item and self._picked(item.data(Qt.ItemDataRole.UserRole)))
        lbox.addWidget(self.list, 1)

        self.detail = QWidget()
        self.detail.setObjectName("Page")
        self.box = QVBoxLayout(self.detail)
        self.box.setContentsMargins(8, 4, 8, 16)
        self.box.setSpacing(12)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.detail)
        self.more = QPushButton()
        self.more.setObjectName("Quiet")
        self.more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more.clicked.connect(self._draw_more)
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)
        root.addWidget(left)
        root.addWidget(self.scroll, 1)

    @property
    def conn(self):
        return self._conn_of()

    def set_road(self, road: str) -> None:
        self._road = road
        for b in self._segments.buttons():
            b.setChecked(b.property("road") == road)
        if self._current and core.find(self._current)["road"] != road:
            self._current = None
        self.refresh()

    def warm(self) -> None:
        """Count in the background now if the count is not ready (the window calls it a little after it opens, and
        after an import), so the page is ready before it is opened."""
        conn = self.conn
        if conn is None or self._counting is not None or core.is_counted(conn):
            return
        self._counting = _Count(self)
        self._counting.done.connect(self._counted)
        self._counting.start()

    def _counted(self) -> None:
        self._counting = None
        if self.isVisible():
            self.refresh()
        else:
            self._stale = True                     # drawn when it is opened next

    def showEvent(self, event) -> None:  # noqa: N802 (Qt's name)
        super().showEvent(event)
        if getattr(self, "_stale", False):
            self._stale = False
            self.refresh()

    def refresh(self) -> None:
        from PySide6.QtGui import QColor, QPalette

        pal = self.list.palette()
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.current().ink))
        self.list.setPalette(pal)
        conn = self.conn
        if conn is not None and not core.is_counted(conn):
            self._waiting()
            self.warm()
            return
        counts = {r["id"]: r["count"] for r in core.summary(conn)} if conn is not None else {}
        self.list.blockSignals(True)
        self.list.clear()
        current = None
        for s in core.sources(self._road):
            n = counts.get(s["id"], 0)
            item = QListWidgetItem(f"{core.text(s['title'])}\n{tr(LAYERS[s['layer']])} · {tr('{n:,} hadith', n=n)}")
            item.setData(Qt.ItemDataRole.UserRole, s["id"])
            item.setSizeHint(QSize(0, 58))
            self.list.addItem(item)
            if s["id"] == self._current:
                current = item
        current = current or self.list.item(0)
        if current is not None:
            self.list.setCurrentItem(current)
        self.list.blockSignals(False)
        if current is not None:
            self.show_source(current.data(Qt.ItemDataRole.UserRole))

    def _waiting(self) -> None:
        """The list without its numbers and a note while the count runs in the background."""
        self.list.blockSignals(True)
        self.list.clear()
        for s in core.sources(self._road):
            item = QListWidgetItem(f"{core.text(s['title'])}\n{tr(LAYERS[s['layer']])} · …")
            item.setData(Qt.ItemDataRole.UserRole, s["id"])
            item.setSizeHint(QSize(0, 58))
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._clear()
        _card, box = self._card()
        box.addWidget(_label(tr("Counting the written sources in the books imported here…"), "CardTitle"))
        box.addWidget(_label(tr("Once, after the books change; the window can be used meanwhile, and this page fills "
                                "in by itself."), "Caption"))
        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setMaximumHeight(6)
        bar.setTextVisible(False)
        box.addWidget(bar)
        self.box.addStretch(1)

    def _picked(self, source_id: str) -> None:
        self.show_source(source_id)
        self.visited.emit(source_id)

    def select(self, source_id: str) -> None:
        s = core.find(source_id)
        if s is None:
            return
        self._current = source_id
        if s["road"] != self._road:
            self.set_road(s["road"])
            return
        self.refresh()

    def _clear(self) -> None:
        self.more.setParent(None)
        while self.box.count():
            item = self.box.takeAt(0)
            w = item.widget()
            if w is not None and w is not self.more:
                w.setParent(None)
                w.deleteLater()

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(20, 14, 20, 14)
        box.setSpacing(6)
        self.box.addWidget(card)
        return card, box

    def show_source(self, source_id: str) -> None:
        from isnady.core import titles

        s = core.find(source_id)
        conn = self.conn
        if s is None or conn is None:
            return
        self._current = source_id
        if not core.is_counted(conn):              # picked while the count runs: shown when it is ready
            self.warm()
            return
        self._clear()
        t = theme.current()
        shia = s["road"] == "shia"
        _card, box = self._card()
        head = _label(core.text(s["title"]), "CardTitle")
        head.setFont(theme.reading_font(20, bold=True))
        box.addWidget(head)
        tags = QHBoxLayout()
        for text, name in ((tr("Shia road") if shia else tr("Sunni road"), "TagGold" if shia else "TagMuted"),
                           (tr(LAYERS[s["layer"]]), "Tag")):
            tag = QLabel(text)
            tag.setObjectName(name)
            tags.addWidget(tag)
        tags.addStretch(1)
        box.addLayout(tags)
        box.addWidget(_label(core.text(s["lead"]), "Lead"))
        box.addWidget(_label("🔎 " + core.text(s["how"]), "Caption"))
        as_book = conn.execute("SELECT 1 FROM works WHERE key = ?", (s["book"],)).fetchone()
        go = QPushButton("📚 " + (tr("Read it as a book in Books") if as_book else
                                  tr("Import it as a book (Data sources)")))
        go.setObjectName("Quiet")
        go.setCursor(Qt.CursorShape.PointingHandCursor)
        go.clicked.connect((lambda: self.open_book.emit(s["book"])) if as_book else self.wants_sources.emit)
        row = QHBoxLayout()
        row.addWidget(go)
        row.addStretch(1)
        box.addLayout(row)

        self._ids = core.hadith(conn, source_id)
        _card, box = self._card()
        title = _label(tr("In the books imported here: {n:,} hadith", n=len(self._ids)), "CardTitle")
        title.setFont(theme.reading_font(15, bold=True))
        box.addWidget(title)
        books = core.by_book(conn, self._ids)
        if books:
            box.addWidget(_label(" · ".join(f"<b>{html.escape(titles.book(k, name))}</b> {n:,}"
                                            for k, name, n in books), "Lead", rich=True))
        elif source_id == "hammam":
            box.addWidget(_label(tr("Not found: import Musnad Ahmad ibn Hanbal (File → Data Sources) — the sahifa "
                                    "is read from it."), "Caption"))
        else:
            box.addWidget(_label(tr("None in the books imported here."), "Caption"))
        if source_id == "hammam" and self._ids:
            data = core.counted(conn)["hammam"]["parallels"]
            others = [h for v in data.values() for h in v]
            box.addWidget(_label(tr("{with_} of the {n} have a parallel in the other books through Hammam's chain "
                                    "— {count:,} hadith:", with_=len(data), n=len(self._ids), count=len(others))
                                 + " " + " · ".join(f"{html.escape(titles.book(k, name))} {c:,}"
                                                    for k, name, c in core.by_book(conn, others)), "Caption", rich=True))
        self._shown = 0
        self._draw_more()
        self.scroll.verticalScrollBar().setValue(0)

    def _draw_more(self) -> None:
        from isnady.core import search as core_search
        from isnady.core import titles

        conn = self.conn
        self.more.setParent(None)
        stretch = self.box.itemAt(self.box.count() - 1)
        if stretch is not None and stretch.spacerItem() is not None:
            self.box.takeAt(self.box.count() - 1)
        hammam = self._current == "hammam"
        t = theme.current()
        for i, hid in enumerate(self._ids[self._shown:self._shown + PAGE], self._shown + 1):
            if hammam:
                found = core.refs(conn, core.parallels(conn, hid))
                line = tr("Hadith {i} of the sahifa", i=i)
                if found:
                    line += " · " + tr("its parallels:") + " " + " · ".join(
                        f"<a href='{h}' style='color:{t.lapis};text-decoration:none'>"
                        f"{html.escape(titles.book(k, k))} {html.escape(str(n))}</a>" for h, k, n in found)
                else:
                    line += " · " + tr("no parallel through Hammam found in the other books imported here")
                note = _label("📜 " + line, "Caption", rich=True)
                note.linkActivated.connect(lambda h: self.open_hadith.emit(int(h)))
                self.box.addWidget(note)
            try:
                result = core_search._load_result(conn, hid, [], core_search.SearchQuery(text=""))
                self.box.addWidget(self._make_card(result))
            except Exception:                  # one card never stops the page
                continue
        self._shown = min(len(self._ids), self._shown + PAGE)
        left = len(self._ids) - self._shown
        if left > 0:
            self.more.setText(tr("Show {page} more ({left:,} left)", page=min(PAGE, left), left=left))
            self.more.setParent(self.detail)
            self.box.addWidget(self.more, 0, Qt.AlignmentFlag.AlignHCenter)
        self.box.addStretch(1)

    def retheme(self) -> None:
        self.refresh()

    def release(self) -> None:
        self._clear()
