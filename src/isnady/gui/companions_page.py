"""Companions and the Household (AM1, EB1): the ten promised Paradise, the people of the cloak, the Mothers of the
Believers on the Sunni road; the Fourteen Infallibles on the Shia road — each road on its own (SH1)."""

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from isnady.core import sahaba as core
from isnady.core import i18n
from isnady.core.i18n import N_, tr
from isnady.gui import theme


def _label(text: str, name: str = "", wrap: bool = True, rich: bool = False) -> QLabel:
    from isnady.gui.widgets import WrapLabel

    label = WrapLabel(text) if wrap else QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if rich:
        label.setTextFormat(Qt.TextFormat.RichText)
    return label


class CompanionsPage(QWidget):
    open_narrator = Signal(int)
    open_tree = Signal(str, object)          # "quraysh", his box → Genealogies
    visited = Signal(str)                    # a group picked → the window's back and forward (NAV2b)

    def __init__(self, connection_getter, card_maker, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._conn_of = connection_getter
        self._make_card = card_maker
        self._road = "sunni"                 # the Sunni road first, as every page (NR-DEF1)
        self._current: str | None = None

        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(340)
        lbox = QVBoxLayout(left)
        lbox.setContentsMargins(18, 16, 18, 14)
        lbox.setSpacing(8)
        title = _label(tr("Companions and the Household"), "CardTitle")
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
        self._segments.buttonClicked.connect(lambda b: (self.set_road(b.property("road")),
                                                        self._current and self.visited.emit(self._current)))
        lbox.addLayout(seg)
        lbox.addWidget(_label(tr("Each group as its own road gives it: the hadith that names it, what its scholars read "
                                 "in it, and what the books imported here hold of its members."), "Caption"))
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.detail)
        self.scroll = scroll
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)
        root.addWidget(left)
        root.addWidget(scroll, 1)

    @property
    def conn(self):
        return self._conn_of()

    def set_road(self, road: str) -> None:
        self._road = road
        for b in self._segments.buttons():
            b.setChecked(b.property("road") == road)
        self.refresh()

    def refresh(self) -> None:
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QColor, QPalette

        # plain rows: the chosen one keeps the ink of the theme on its light ground (not white on light blue)
        pal = self.list.palette()
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.current().ink))
        self.list.setPalette(pal)
        self.list.blockSignals(True)
        self.list.clear()
        current = None
        for g in core.groups(self._road):
            item = QListWidgetItem(core.text(g["title"]))
            item.setData(Qt.ItemDataRole.UserRole, g["id"])
            item.setSizeHint(QSize(0, 46))
            self.list.addItem(item)
            if g["id"] == self._current:
                current = item
        current = current or self.list.item(0)
        if current is not None:
            self.list.setCurrentItem(current)
        self.list.blockSignals(False)
        if current is not None:
            self.show_group(current.data(Qt.ItemDataRole.UserRole))

    def _picked(self, group_id: str) -> None:
        self.show_group(group_id)
        self.visited.emit(group_id)

    def select(self, group_id: str) -> None:
        group = core.find(group_id)
        if group is None:
            return
        self._current = group_id
        if group["road"] != self._road:
            self.set_road(group["road"])
            return
        self.refresh()

    def _clear(self) -> None:
        while self.box.count():
            item = self.box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _card(self, title: str = "") -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(20, 14, 20, 14)
        box.setSpacing(6)
        if title:
            head = _label(title, "CardTitle")
            head.setFont(theme.reading_font(15, bold=True))
            box.addWidget(head)
        self.box.addWidget(card)
        return card, box

    def show_group(self, group_id: str) -> None:
        conn = self.conn
        group = core.find(group_id)
        if group is None:
            return
        self._current = group_id
        self._clear()
        t = theme.current()
        shia = group["road"] == "shia"
        card, box = self._card()
        head = _label(core.text(group["title"]), "CardTitle")
        head.setFont(theme.reading_font(20, bold=True))
        box.addWidget(head)
        tag = QLabel(tr("Shia road") if shia else tr("Sunni road"))
        tag.setObjectName("TagGold" if shia else "TagMuted")
        row = QHBoxLayout()
        row.addWidget(tag)
        row.addStretch(1)
        box.addLayout(row)
        box.addWidget(_label(core.text(group["lead"]), "Lead"))

        # the members
        members = core.members(conn, group)
        card, box = self._card(tr("Its members") + f" ({len(members)})")
        if shia and conn is not None:
            shared = core.shared_ends(conn)
            if shared:
                box.addWidget(_label(tr("{n:,} more chains of the Shia books end at an Imam not named, or named by a "
                                        "kunya several of them share (Abu al-Hasan); they are not counted under one.",
                                        n=shared), "Caption"))
        # two to a row (a grid: each card as tall as its own text, never over the next one)
        grid = QGridLayout()
        grid.setSpacing(10)
        for i, m in enumerate(members):
            grid.addWidget(self._member(m, shia), i // 2, i % 2, Qt.AlignmentFlag.AlignTop)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        box.addLayout(grid)

        # the hadith that name the group, as they stand in the books imported here
        found = core.hadith(conn, group) if conn is not None else []
        if group.get("hadith"):
            card, box = self._card(tr("The hadith that name them"))
            if not found:
                box.addWidget(_label(tr("Not in the books imported here: {refs}", refs=", ".join(
                    f"{b} {n}" for b, n in group["hadith"])), "Caption"))
            box.addWidget(_label(tr("As the books imported here give them; each opens in its book and its chain."),
                                 "Caption"))
            from isnady.core import search as core_search

            for _book, _number, hid in found:
                try:
                    result = core_search._load_result(conn, hid, [], core_search.SearchQuery(text=""))
                    self.box.addWidget(self._make_card(result))
                except Exception:                  # one card never stops the page
                    continue
        self.box.addStretch(1)
        self.scroll.verticalScrollBar().setValue(0)

    def _member(self, m: dict, shia: bool) -> QFrame:
        t = theme.current()
        card = QFrame()
        card.setObjectName("PersonCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 12, 16, 12)
        box.setSpacing(3)
        name = _label(m["name"], "RowTitle")
        name.setFont(theme.reading_font(14, bold=True))
        box.addWidget(name)
        if m.get("arabic") and m["arabic"] != m["name"]:
            arabic = QLabel(m["arabic"])
            arabic.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
            arabic.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                                 f"{theme.font_css(theme.script_font('arabic', factor=0.7))}")
            box.addWidget(arabic)
        facts = []
        if m.get("died"):
            facts.append(html.escape(m["died"]))
        if shia:
            facts.append(tr("<b>{n:,}</b> chains end here in the Shia books", n=m.get("ends", 0)) if m.get("ends")
                         else tr("no chain ends here in the books imported here"))
        elif m.get("person") and m.get("links"):
            facts.append(tr("in <b>{links:,}</b> chain links, of <b>{hadith:,}</b> hadith", links=m.get("links", 0),
                            hadith=m.get("hadith", 0)))
        elif m.get("person"):
            facts.append(tr("not identified in the chains imported here"))
        if facts:
            box.addWidget(_label(" · ".join(facts), "Caption", rich=True))
        if m.get("summary"):
            text = m["summary"]
            short = text if len(text) <= 220 else text[:220].rsplit(" ", 1)[0] + " …"
            about = _label(short, "Lead")
            about.setToolTip(text)
            box.addWidget(about)
        row = QHBoxLayout()
        row.setSpacing(6)
        if m.get("person"):
            go = QPushButton(tr("Life and narrations"))
            go.setObjectName("Quiet")
            go.setCursor(Qt.CursorShape.PointingHandCursor)
            go.clicked.connect(lambda _c=False, pid=m["person"]: self.open_narrator.emit(pid))
            row.addWidget(go)
        if m.get("node"):
            tree = QPushButton("🌳 " + tr("In the family tree"))
            tree.setObjectName("Quiet")
            tree.setCursor(Qt.CursorShape.PointingHandCursor)
            tree.clicked.connect(lambda _c=False, n=m["node"]: self.open_tree.emit("quraysh", n))
            row.addWidget(tree)
        row.addStretch(1)
        box.addLayout(row)
        box.addStretch(1)
        return card

    def retheme(self) -> None:
        self.refresh()

    def release(self) -> None:
        self._clear()
