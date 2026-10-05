"""Learn (G7): the terms of hadith and its sciences — search, categories, and a card for each term with its
Arabic, its reading, a short and a long definition, related terms (one click away) and its classical source.
English or Türkçe, remembered (the first step of the interface language, I1)."""

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from isnady import config
from isnady.core import learn
from isnady.gui import theme
from isnady.gui.widgets import FlowLayout


def _label(text: str, name: str = "", rich: bool = False, wrap: bool = True) -> QLabel:
    l = QLabel(text)
    if name:
        l.setObjectName(name)
    l.setWordWrap(wrap)
    if rich:
        l.setTextFormat(Qt.TextFormat.RichText)
    l.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return l


class LearnPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self.lang = config.state_get("learn.language") or "en"
        self._current = None

        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(380)
        lbox = QVBoxLayout(left)
        lbox.setContentsMargins(18, 16, 18, 14)
        lbox.setSpacing(8)
        title = _label("Learn", "CardTitle")
        title.setFont(theme.reading_font(18, bold=True))
        lbox.addWidget(title)
        lbox.addWidget(_label(f"The terms of hadith and its sciences — {len(learn.terms())} terms, each with its "
                              "Arabic, its meaning and its classical source.", "Caption"))
        langs = QHBoxLayout()
        self._lang_group = QButtonGroup(self)
        for code, label in learn.LANGUAGES.items():
            b = QPushButton(label)
            b.setCheckable(True)
            b.setObjectName("Segment")
            b.setChecked(code == self.lang)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, c=code: self._set_lang(c))
            self._lang_group.addButton(b)
            langs.addWidget(b)
        langs.addStretch(1)
        lbox.addLayout(langs)
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search: sahih, mursal, tadlis, künye …")
        self.query.setClearButtonEnabled(True)
        self.query.textChanged.connect(lambda _t: self._populate())
        lbox.addWidget(self.query)
        self.tree = QTreeWidget()
        self.tree.setObjectName("Contents")
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(lambda item, _c: item.data(0, Qt.ItemDataRole.UserRole) and
                                      self.show_term(item.data(0, Qt.ItemDataRole.UserRole)))
        lbox.addWidget(self.tree, 1)

        self.body = QWidget()
        self.body.setObjectName("Page")
        self.box = QVBoxLayout(self.body)
        self.box.setContentsMargins(0, 0, 8, 16)
        self.box.setSpacing(14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.body)

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)
        root.addWidget(left)
        root.addWidget(scroll, 1)
        self._populate()
        self.show_term("sahih")

    def _set_lang(self, code: str) -> None:
        self.lang = code
        for b, c in zip(self._lang_group.buttons(), learn.LANGUAGES):
            b.setChecked(c == code)            # in step also when the language is set from code or a saved state
        config.state_set("learn.language", code)
        self._populate()
        if self._current:
            self.show_term(self._current)

    def _populate(self) -> None:
        found = {t["id"] for t in learn.search(self.query.text(), self.lang)}
        self.tree.clear()
        cats = learn.categories()
        for key, names in cats.items():
            members = [t for t in learn.terms() if t["cat"] == key and t["id"] in found]
            if not members:
                continue
            head = QTreeWidgetItem([names[self.lang]])
            font = head.font(0)
            font.setBold(True)
            head.setFont(0, font)
            self.tree.addTopLevelItem(head)
            for t in members:
                item = QTreeWidgetItem([f"{learn.name(t, self.lang)}   {t['ar']}"])
                item.setData(0, Qt.ItemDataRole.UserRole, t["id"])
                item.setToolTip(0, t["short"][self.lang])
                head.addChild(item)
            head.setExpanded(True)

    def show_term(self, term_id: str) -> None:
        t = learn.get(term_id)
        if not t:
            return
        self._current = term_id
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        th = theme.current()
        card = QFrame()
        card.setObjectName("Card")
        cb = QVBoxLayout(card)
        cb.setContentsMargins(28, 22, 28, 22)
        cb.setSpacing(10)
        top = QHBoxLayout()
        head = QLabel(learn.name(t, self.lang))
        head.setFont(theme.reading_font(28, bold=True))
        head.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        top.addWidget(head, 1)
        if t["ar"]:
            ar = QLabel(t["ar"])
            ar.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                             f"{theme.font_css(theme.script_font('arabic', bold=True, factor=1.3))}")
            ar.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            top.addWidget(ar)
        cb.addLayout(top)
        other = "tr" if self.lang == "en" else "en"
        cat = learn.categories()[t["cat"]][self.lang]
        cb.addWidget(_label(f"<span style='color:{th.gold}'>●</span> {html.escape(cat)} &nbsp;·&nbsp; "
                            f"{learn.LANGUAGES[other]}: <i>{html.escape(learn.name(t, other))}</i>", "Caption", rich=True))
        short = _label(t["short"][self.lang], "Lead")
        short.setFont(theme.reading_font(15, bold=True))
        cb.addWidget(short)
        if t["long"][self.lang]:
            long = _label(t["long"][self.lang], "Lead")
            long.setFont(theme.reading_font(14))
            cb.addWidget(long)
        if t["source"]:
            word = "Kaynak" if self.lang == "tr" else "Source"
            cb.addWidget(_label(f"<b>{word}</b>: {html.escape(t['source'])}", "Caption", rich=True))
        self.box.addWidget(card)
        if t["related"]:
            rel = QFrame()
            rel.setObjectName("Card")
            rb = QVBoxLayout(rel)
            rb.setContentsMargins(24, 14, 24, 16)
            rb.addWidget(_label("Related terms" if self.lang == "en" else "İlgili terimler", "FilterTitle"))
            flow_holder = QWidget()
            flow = FlowLayout(flow_holder)
            for rid in t["related"]:
                r = learn.get(rid)
                chip = QPushButton(f"{learn.name(r, self.lang)}  {r['ar']}")
                chip.setObjectName("Chip")
                chip.setCursor(Qt.CursorShape.PointingHandCursor)
                chip.setToolTip(r["short"][self.lang])
                chip.clicked.connect(lambda _c=False, x=rid: self.show_term(x))
                flow.addWidget(chip)
            rb.addWidget(flow_holder)
            self.box.addWidget(rel)
        self.box.addStretch(1)
        # keep the tree in step
        for i in range(self.tree.topLevelItemCount()):
            head_item = self.tree.topLevelItem(i)
            for j in range(head_item.childCount()):
                if head_item.child(j).data(0, Qt.ItemDataRole.UserRole) == term_id:
                    self.tree.setCurrentItem(head_item.child(j))

    def retheme(self) -> None:
        if self._current:
            self.show_term(self._current)
