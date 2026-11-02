"""The Sira as a timeline (SIY1): the life of the Prophet ﷺ from the Year of the Elephant to his death, drawn on one
line in its three periods; each event with its date (and where the reports differ), its place, the verses revealed
about it, the chapter of Ibn Hisham's Sira that tells it, and the hadith that name it."""

import html

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from isnady.core import sira as core
from isnady.core import i18n
from isnady.core.i18n import tr
from isnady.gui import theme
from isnady.gui.widgets import FlowLayout

FIRST, LAST = -53, 11            # the Year of the Elephant … his death (years after the Hijra)


def _label(text: str, name: str = "", wrap: bool = True, rich: bool = False) -> QLabel:
    from isnady.gui.widgets import WrapLabel

    label = WrapLabel(text) if wrap else QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if rich:
        label.setTextFormat(Qt.TextFormat.RichText)
    return label


def _period_colors() -> dict[str, QColor]:
    t = theme.current()
    return {"before": QColor(t.muted), "mecca": QColor(t.gold), "medina": QColor(t.lapis)}


class Timeline(QWidget):
    """The whole life on one line: the three periods as bands, every event a dot (a click opens it)."""

    picked = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(118)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self._current: str | None = None
        self._dots: list[tuple[QRectF, dict]] = []

    def sizeHint(self) -> QSize:
        return QSize(900, 118)

    def set_current(self, event_id: str | None) -> None:
        self._current = event_id
        self.update()

    def _x(self, year: float) -> float:
        left, right = 28.0, self.width() - 28.0
        return left + (year - FIRST) / (LAST - FIRST) * (right - left)

    def paintEvent(self, _e) -> None:
        t = theme.current()
        colors = _period_colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        line_y = 62.0
        # the periods: before the mission, Mecca (from the revelation), Medina (from the Hijra)
        for period, a, b in (("before", FIRST, -13), ("mecca", -13, 0), ("medina", 0, LAST)):
            c = QColor(colors[period])
            c.setAlpha(60)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(QRectF(self._x(a), line_y - 5, self._x(b) - self._x(a), 10), 5, 5)
            p.setPen(QColor(t.muted))
            f = QFont(self.font())
            f.setPointSizeF(max(7.5, f.pointSizeF() - 1))
            p.setFont(f)
            p.drawText(QRectF(self._x(a), line_y + 30, self._x(b) - self._x(a), 18), Qt.AlignmentFlag.AlignCenter,
                       core.text(core.PERIODS[period]))
        # the marks under the line
        f = QFont(self.font())
        f.setPointSizeF(max(7, f.pointSizeF() - 1.5))
        p.setFont(f)
        for year, label in ((FIRST, "570"), (-13, "610"), (0, tr("Hijra") + " 622"), (LAST, "632")):
            x = self._x(year)
            p.setPen(QPen(QColor(t.muted), 1))
            p.drawLine(QPointF(x, line_y + 7), QPointF(x, line_y + 13))
            p.drawText(QRectF(x - 60, line_y + 13, 120, 16), Qt.AlignmentFlag.AlignCenter, label)
        # the events: dots above the line, stacked when they fall in the same year
        self._dots = []
        stack: dict[int, int] = {}
        for e in core.EVENTS:
            k = stack.get(e["year"], 0)
            stack[e["year"]] = k + 1
            x, y = self._x(e["year"]), line_y - 14 - k * 11
            big = e["id"] == self._current
            r = 6.5 if big else 4.5
            p.setPen(QPen(QColor(t.ink) if big else QColor(t.surface), 1.5))
            p.setBrush(colors[e["period"]])
            p.drawEllipse(QPointF(x, y), r, r)
            self._dots.append((QRectF(x - 7, y - 7, 14, 14), e))
        cur = core.find(self._current) if self._current else None
        if cur is not None:
            p.setPen(QColor(t.ink))
            f = QFont(self.font())
            f.setBold(True)
            p.setFont(f)
            x = self._x(cur["year"])
            w = 260
            p.drawText(QRectF(min(max(4, x - w / 2), self.width() - w - 4), 0, w, 16),
                       Qt.AlignmentFlag.AlignCenter, core.text(cur["title"]))
        p.end()

    def _at(self, pos) -> dict | None:
        return next((e for r, e in self._dots if r.contains(QPointF(pos))), None)

    def mouseMoveEvent(self, ev) -> None:
        e = self._at(ev.position())
        self.setCursor(Qt.CursorShape.PointingHandCursor if e else Qt.CursorShape.ArrowCursor)
        self.setToolTip(f"{core.text(e['title'])}\n{core.year_label(e)}" if e else "")

    def mousePressEvent(self, ev) -> None:
        e = self._at(ev.position())
        if e:
            self.picked.emit(e["id"])


class SiraPage(QWidget):
    open_chapter = Signal(int)               # Ibn Hisham's chapter → Books
    open_verse = Signal(int, int)            # a verse → the Qur'an
    search = Signal(str)                     # the hadith that name the event → Search
    visited = Signal(str)                    # an event picked → back and forward (NAV2b)

    def __init__(self, connection_getter, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._conn_of = connection_getter
        self._current: str | None = None

        head = QFrame()
        head.setObjectName("Card")
        hbox = QVBoxLayout(head)
        hbox.setContentsMargins(20, 14, 20, 10)
        hbox.setSpacing(4)
        title = _label(tr("Sira — the life of the Prophet ﷺ"), "CardTitle", wrap=False)
        title.setFont(theme.reading_font(18, bold=True))
        hbox.addWidget(title)
        hbox.addWidget(_label(tr("From the Year of the Elephant to his death, as Ibn Ishaq tells it in Ibn Hisham's "
                                 "edition; where others give another date, it is said beside it. Click an event on "
                                 "the line or in the list."), "Caption"))
        self.timeline = Timeline()
        self.timeline.picked.connect(self._picked)
        hbox.addWidget(self.timeline)

        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(340)
        lbox = QVBoxLayout(left)
        lbox.setContentsMargins(14, 12, 14, 12)
        self.list = QListWidget()
        self.list.setObjectName("NarratorList")
        self.list.setWordWrap(True)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(
            lambda item, _p: item and item.data(Qt.ItemDataRole.UserRole) and
            self._picked(item.data(Qt.ItemDataRole.UserRole)))
        lbox.addWidget(self.list)

        self.detail = QWidget()
        self.detail.setObjectName("Page")
        self.box = QVBoxLayout(self.detail)
        self.box.setContentsMargins(4, 0, 8, 16)
        self.box.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.detail)
        self.scroll = scroll

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(left)
        body.addWidget(scroll, 1)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        root.addWidget(head)
        root.addLayout(body, 1)

    @property
    def conn(self):
        return self._conn_of()

    def refresh(self) -> None:
        from PySide6.QtGui import QPalette

        pal = self.list.palette()
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.current().ink))
        self.list.setPalette(pal)
        colors = _period_colors()
        self.list.blockSignals(True)
        self.list.clear()
        current = None
        for period in core.PERIODS:
            head = QListWidgetItem(core.text(core.PERIODS[period]))
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            f = head.font()
            f.setBold(True)
            head.setFont(f)
            head.setForeground(colors[period])
            self.list.addItem(head)
            for e in core.events(period):
                item = QListWidgetItem(f"{core.text(e['title'])}\n{core.year_label(e)}")
                item.setData(Qt.ItemDataRole.UserRole, e["id"])
                item.setSizeHint(QSize(0, 48))
                self.list.addItem(item)
                if e["id"] == self._current:
                    current = item
        self.list.blockSignals(False)
        target = current.data(Qt.ItemDataRole.UserRole) if current else core.EVENTS[0]["id"]
        self.show_event(target)

    def _picked(self, event_id: str) -> None:
        self.show_event(event_id)
        self.visited.emit(event_id)

    def select(self, event_id: str) -> None:
        if not self.list.count():
            self.refresh()
        self.show_event(event_id)

    def _clear(self) -> None:
        while self.box.count():
            item = self.box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def show_event(self, event_id: str) -> None:
        from isnady.core import quran

        e = core.find(event_id)
        if e is None:
            return
        self._current = event_id
        self.timeline.set_current(event_id)
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == event_id:
                self.list.blockSignals(True)
                self.list.setCurrentRow(i)
                self.list.blockSignals(False)
                self.list.scrollToItem(self.list.item(i))
        self._clear()
        t = theme.current()
        color = _period_colors()[e["period"]].name()
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(22, 16, 22, 16)
        box.setSpacing(8)
        top = QHBoxLayout()
        title = _label(core.text(e["title"]), "CardTitle")
        title.setFont(theme.reading_font(22, bold=True))
        top.addWidget(title, 1)
        ar = QLabel(e["title"].get("ar", ""))
        ar.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                         f"{theme.font_css(theme.script_font('arabic', factor=0.85))}")
        top.addWidget(ar)
        box.addLayout(top)
        chips = QWidget()
        flow = FlowLayout(chips, spacing=8)
        for text, name in ((core.text(core.PERIODS[e["period"]]), "Tag"),
                           ("📅 " + core.year_label(e), "TagMuted"),
                           ("🕰 " + core.text(e["when"]), "TagMuted"),
                           ("📍 " + core.text(e["place"]), "TagMuted"),
                           ("👤 " + tr("his age: {n}", n=core.age(e)), "TagMuted")):
            chip = QLabel(text)
            chip.setObjectName(name)
            flow.addWidget(chip)
        box.addWidget(chips)
        stripe = QFrame()
        stripe.setFixedHeight(3)
        stripe.setStyleSheet(f"background: {color}; border-radius: 1px;")
        box.addWidget(stripe)
        box.addWidget(_label(core.text(e["text"]), "Lead"))
        if e.get("differ"):
            note = _label("⚖ " + core.text(e["differ"]), "Caption")
            note.setStyleSheet(f"border-left: 3px solid {t.gold}; padding-left: 8px;")
            box.addWidget(note)
        self.box.addWidget(card)

        # the verses revealed about it
        if e["quran"]:
            card = QFrame()
            card.setObjectName("Card")
            vbox = QVBoxLayout(card)
            vbox.setContentsMargins(22, 12, 22, 12)
            vbox.addWidget(_label("📖 " + tr("The verses revealed about it"), "CardTitle"))
            row = QWidget()
            rflow = FlowLayout(row, spacing=8)
            for s, a, b in e["quran"]:
                go = QPushButton(quran.label(s, a, b, i18n.language()))
                go.setObjectName("Quiet")
                go.setCursor(Qt.CursorShape.PointingHandCursor)
                go.clicked.connect(lambda _c=False, s=s, a=a: self.open_verse.emit(s, a))
                rflow.addWidget(go)
            vbox.addWidget(row)
            self.box.addWidget(card)

        # Ibn Hisham, and the hadith
        card = QFrame()
        card.setObjectName("Card")
        sbox = QVBoxLayout(card)
        sbox.setContentsMargins(22, 12, 22, 12)
        sbox.setSpacing(6)
        sbox.addWidget(_label("📚 " + tr("In the sources"), "CardTitle"))
        conn = self.conn
        chapter = core.sira_chapter(conn, e) if conn is not None else None
        if chapter:
            go = QPushButton("🕌 " + tr("Read it in Ibn Hisham's Sira") + f" — {e['sira']}")
            go.setObjectName("Link")
            go.setCursor(Qt.CursorShape.PointingHandCursor)
            go.clicked.connect(lambda _c=False, c=chapter: self.open_chapter.emit(c))
            sbox.addWidget(go, 0, Qt.AlignmentFlag.AlignLeft)
        elif e.get("sira"):
            sbox.addWidget(_label(tr("Ibn Hisham's Sira tells it in “{chapter}” — import the Sira in File → Data "
                                     "Sources to read it here.", chapter=e["sira"]), "Caption"))
        if e.get("phrase") and conn is not None:
            n = core.hadith_counts(conn).get(e["id"], 0)
            go = QPushButton("📜 " + tr("The hadith that say “{phrase}”: about {n:,} in the Sunni books",
                                       phrase=e["phrase"], n=n))
            go.setObjectName("Link")
            go.setCursor(Qt.CursorShape.PointingHandCursor)
            go.setEnabled(n > 0)
            go.clicked.connect(lambda _c=False, p=e["phrase"]: self.search.emit(p))
            sbox.addWidget(go, 0, Qt.AlignmentFlag.AlignLeft)
        self.box.addWidget(card)

        # the previous and the next event
        bar = QWidget()
        nav = QHBoxLayout(bar)
        nav.setContentsMargins(0, 0, 0, 0)
        ids = [x["id"] for x in core.EVENTS]
        k = ids.index(event_id)
        for step, text in ((-1, "‹  " + tr("Previous event")), (1, tr("Next event") + "  ›")):
            b = QPushButton(text)
            b.setObjectName("Quiet")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setEnabled(0 <= k + step < len(ids))
            if 0 <= k + step < len(ids):
                b.clicked.connect(lambda _c=False, i=ids[k + step]: self._picked(i))
            nav.addWidget(b)
            if step < 0:
                nav.addStretch(1)
        self.box.addWidget(bar)
        self.box.addStretch(1)
        self.scroll.verticalScrollBar().setValue(0)

    def retheme(self) -> None:
        self.refresh()

    def release(self) -> None:
        self._clear()
