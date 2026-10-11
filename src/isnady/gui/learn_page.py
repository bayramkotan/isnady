"""Learn (G7, UI8): the terms of hadith and its sciences, in colour.

Bayram (2026-10-11): "Learn kısmı çok okunaksız → VenvStudio'daki gibi olamaz mı? Biraz daha düzgün, okunaklı ve
renkli??" — each of the ten categories has its own colour and sign, used everywhere the term appears: the
category chips at the top of the list (a click shows that category alone), the dot before each term, the band at
the top of the term's card, the box of its short definition, the chips of its related terms. The card reads from
top to bottom: the term large with its Arabic, its names in the other languages, "In short", "In detail", the
source, the related terms, the ☆ (BM1). The terms are in English, Türkçe and العربية (the interface language when
the glossary has it)."""

import html

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
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
from isnady.core import i18n, learn
from isnady.core.i18n import tr
from isnady.gui import theme
from isnady.gui.widgets import FlowLayout

# category → (colour, sign): the same in every theme, strong enough on light and on dark backgrounds
CATEGORY_STYLE = {
    "grades": ("#2E7D5B", "✔"), "chain_kinds": ("#1D63A8", "⛓"), "chain": ("#6A4C93", "⟷"),
    "transmission": ("#0F7C8C", "🗣"), "critics": ("#A23B54", "⚖"), "generations": ("#8A5A1E", "⌛"),
    "names": ("#B5651D", "✎"), "shia": ("#7A6A12", "☀"), "books": ("#4E6A86", "📚"), "measures": ("#C0392B", "📊"),
}


def _style(cat: str) -> tuple[str, str]:
    return CATEGORY_STYLE.get(cat, ("#5B6878", "•"))


def _soft(colour: str, dark: bool, amount: float = 0.13) -> str:
    """A light (or, in a dark theme, deep) tint of a colour, for backgrounds."""
    c = QColor(colour)
    base = QColor("#18202A") if dark else QColor("#FFFFFF")
    a = amount * (1.6 if dark else 1)
    return QColor(int(base.red() + (c.red() - base.red()) * a), int(base.green() + (c.green() - base.green()) * a),
                  int(base.blue() + (c.blue() - base.blue()) * a)).name()


def _label(text: str, name: str = "", rich: bool = False, wrap: bool = True) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    if rich:
        lab.setTextFormat(Qt.TextFormat.RichText)
    lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lab


class LearnPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        # the glossary speaks the interface language when it has it; another one chosen here is kept for the session
        saved = config.state_get("learn.language")
        self.lang = (i18n.language() if i18n.language() in learn.LANGUAGES
                     else saved if saved in learn.LANGUAGES else "en")
        self._current = None
        self._category = None                   # a category chosen with its chip: that one alone

        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(400)
        lbox = QVBoxLayout(left)
        lbox.setContentsMargins(18, 16, 18, 14)
        lbox.setSpacing(8)
        title = _label(tr("Learn"), "CardTitle")
        title.setFont(theme.reading_font(20, bold=True))
        lbox.addWidget(title)
        lbox.addWidget(_label(tr("The terms of hadith and its sciences — {terms} terms, each with its Arabic, its meaning "
                                 "and its classical source.", terms=len(learn.terms())), "Caption"))
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
        self.query.setPlaceholderText(tr("Search: sahih, mursal, tadlis, künye …"))
        self.query.setClearButtonEnabled(True)
        self.query.textChanged.connect(lambda _t: self._populate())
        lbox.addWidget(self.query)
        self.chips_holder = QWidget()
        self.chips = FlowLayout(self.chips_holder, spacing=5)
        lbox.addWidget(self.chips_holder)
        self.tree = QTreeWidget()
        self.tree.setObjectName("Contents")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
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
        self._chips()
        self._populate()
        self.show_term("sahih")

    def _set_lang(self, code: str) -> None:
        self.lang = code
        for b, c in zip(self._lang_group.buttons(), learn.LANGUAGES):
            b.setChecked(c == code)            # in step also when the language is set from code or a saved state
        config.state_set("learn.language", code)
        self._chips()
        self._populate()
        if self._current:
            self.show_term(self._current)

    # ------------------------------------------------------------------ the list
    def _chips(self) -> None:
        while self.chips.count():
            w = self.chips.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        t = theme.current()
        all_chip = QPushButton(tr("All"))
        all_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        selected = self._category is None
        all_chip.setStyleSheet(self._chip_css(t.lapis, selected, t.dark))
        all_chip.clicked.connect(lambda: self._pick_category(None))
        self.chips.addWidget(all_chip)
        for key in learn.categories():
            colour, sign = _style(key)
            chip = QPushButton(f"{sign} {learn.category(key, self.lang)}")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setStyleSheet(self._chip_css(colour, self._category == key, t.dark))
            chip.setToolTip(tr("Show this category alone"))
            chip.clicked.connect(lambda _c=False, k=key: self._pick_category(k))
            self.chips.addWidget(chip)

    @staticmethod
    def _chip_css(colour: str, on: bool, dark: bool) -> str:
        if on:
            return (f"QPushButton {{ background: {colour}; color: white; border: 1px solid {colour}; border-radius: 11px;"
                    f" padding: 3px 10px; font-weight: 600; }}")
        return (f"QPushButton {{ background: {_soft(colour, dark)}; color: {colour if not dark else QColor(colour).lighter(150).name()};"
                f" border: 1px solid {_soft(colour, dark, 0.35)}; border-radius: 11px; padding: 3px 10px; }}"
                f" QPushButton:hover {{ border-color: {colour}; }}")

    def _pick_category(self, key) -> None:
        self._category = None if self._category == key else key
        self._chips()
        self._populate()

    def _populate(self) -> None:
        found = {t["id"] for t in learn.search(self.query.text(), self.lang)}
        self.tree.clear()
        cats = learn.categories()
        dark = theme.current().dark
        for key in cats:
            if self._category and key != self._category:
                continue
            members = [t for t in learn.terms() if t["cat"] == key and t["id"] in found]
            if not members:
                continue
            colour, sign = _style(key)
            head = QTreeWidgetItem([f"{sign}  {learn.category(key, self.lang)}   ({len(members)})"])
            font = head.font(0)
            font.setBold(True)
            head.setFont(0, font)
            head.setForeground(0, QBrush(QColor(colour if not dark else QColor(colour).lighter(150).name())))
            self.tree.addTopLevelItem(head)
            for t in members:
                shown = learn.name(t, self.lang)
                second = t["ar"] if self.lang != "ar" else (t["en"] if t["ar"] else "")
                item = QTreeWidgetItem([f"●  {shown}   {second}" if second and second != shown else f"●  {shown}"])
                item.setData(0, Qt.ItemDataRole.UserRole, t["id"])
                item.setToolTip(0, learn.text(t, "short", self.lang))
                head.addChild(item)
            head.setExpanded(True)

    # ------------------------------------------------------------------ the card
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
        colour, sign = _style(t["cat"])
        bright = colour if not th.dark else QColor(colour).lighter(150).name()
        arabic = self.lang == "ar"

        card = QFrame()
        card.setObjectName("Card")
        cb = QVBoxLayout(card)
        cb.setContentsMargins(0, 0, 0, 22)
        cb.setSpacing(12)
        band = QLabel(f"  {sign}  {html.escape(learn.category(t['cat'], self.lang))}")
        band.setStyleSheet(f"background: {colour}; color: white; font-weight: 600; padding: 7px 14px;"
                           f" border-top-left-radius: 13px; border-top-right-radius: 13px;")
        cb.addWidget(band)
        inner = QVBoxLayout()
        inner.setContentsMargins(28, 4, 28, 0)
        inner.setSpacing(12)
        top = QHBoxLayout()
        head = QLabel(learn.name(t, self.lang))
        head.setFont(theme.script_font("arabic", bold=True, factor=1.4) if arabic else theme.reading_font(30, bold=True))
        head.setStyleSheet(f"color: {bright};")
        head.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        top.addWidget(head, 1)
        if t["ar"] and not arabic:
            ar = QLabel(t["ar"])
            ar.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                             f"{theme.font_css(theme.script_font('arabic', bold=True, factor=1.45))}")
            ar.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            top.addWidget(ar)
        try:
            from isnady.gui.bookmarks_page import BookmarkButton

            top.addWidget(BookmarkButton("term", t["id"], learn.name(t, "en"), t["ar"]), 0, Qt.AlignmentFlag.AlignTop)
        except Exception:          # a bookmark is a convenience: never stop the card
            pass
        inner.addLayout(top)
        others = [f"{learn.LANGUAGES[o]}: <b>{html.escape(learn.name(t, o))}</b>" for o in learn.LANGUAGES
                  if o != self.lang and o != "ar"]
        inner.addWidget(_label(" &nbsp;·&nbsp; ".join(others), "Caption", rich=True))

        short_box = QFrame()
        short_box.setStyleSheet(f"QFrame {{ background: {_soft(colour, th.dark)}; border-left: 5px solid {colour};"
                                f" border-radius: 8px; }}")
        sb = QVBoxLayout(short_box)
        sb.setContentsMargins(16, 10, 16, 12)
        sb.setSpacing(4)
        sb.addWidget(self._heading(tr("In short"), bright))
        short = _label(learn.text(t, "short", self.lang), "Lead")
        short.setFont(theme.script_font("arabic", bold=True, factor=0.9) if arabic else theme.reading_font(16, bold=True))
        short.setStyleSheet(f"color: {th.ink}; background: transparent; border: none;")
        sb.addWidget(short)
        inner.addWidget(short_box)
        labels = [short]
        long_text = learn.text(t, "long", self.lang)
        if long_text:
            inner.addWidget(self._heading(tr("In detail"), bright))
            long = _label(long_text, "Lead")
            long.setFont(theme.script_font("arabic", factor=0.85) if arabic else theme.reading_font(15))
            long.setStyleSheet(f"color: {th.ink}; line-height: 150%;")
            inner.addWidget(long)
            labels.append(long)
        if arabic:                                   # Arabic reads from the right, whatever the interface
            for lab in labels:
                lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
                lab.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        if t["source"]:
            src = _label(f"📜 <b>{tr('Source')}</b>: {html.escape(t['source'])}", "Caption", rich=True)
            src.setStyleSheet(f"background: {th.pill}; border-radius: 8px; padding: 6px 10px;")
            inner.addWidget(src)
        cb.addLayout(inner)
        self.box.addWidget(card)

        if t["related"]:
            rel = QFrame()
            rel.setObjectName("Card")
            rb = QVBoxLayout(rel)
            rb.setContentsMargins(24, 14, 24, 16)
            rb.addWidget(self._heading(tr("Related terms"), th.muted))
            flow_holder = QWidget()
            flow = FlowLayout(flow_holder)
            for rid in t["related"]:
                r = learn.get(rid)
                if not r:
                    continue
                rc, rs = _style(r["cat"])
                shown = learn.name(r, self.lang)
                chip = QPushButton(f"{rs} {shown}  {r['ar']}" if r["ar"] and r["ar"] != shown else f"{rs} {shown}")
                chip.setCursor(Qt.CursorShape.PointingHandCursor)
                chip.setStyleSheet(self._chip_css(rc, False, th.dark))
                chip.setToolTip(f"{learn.category(r['cat'], self.lang)}\n{learn.text(r, 'short', self.lang)}")
                chip.clicked.connect(lambda _c=False, x=rid: self.show_term(x))
                flow.addWidget(chip)
            rb.addWidget(flow_holder)
            self.box.addWidget(rel)

        # the other terms of its category, to read on
        same = [x for x in learn.terms() if x["cat"] == t["cat"] and x["id"] != t["id"]]
        if same:
            more = QFrame()
            more.setObjectName("Card")
            mb = QVBoxLayout(more)
            mb.setContentsMargins(24, 14, 24, 16)
            mb.addWidget(self._heading(tr("More in {category}", category=learn.category(t["cat"], self.lang)), th.muted))
            holder = QWidget()
            fl = FlowLayout(holder)
            for x in same:
                b = QPushButton(learn.name(x, self.lang))
                b.setObjectName("Chip")
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setToolTip(learn.text(x, "short", self.lang))
                b.clicked.connect(lambda _c=False, xid=x["id"]: self.show_term(xid))
                fl.addWidget(b)
            mb.addWidget(holder)
            self.box.addWidget(more)
        self.box.addStretch(1)
        # keep the tree in step
        for i in range(self.tree.topLevelItemCount()):
            head_item = self.tree.topLevelItem(i)
            for j in range(head_item.childCount()):
                if head_item.child(j).data(0, Qt.ItemDataRole.UserRole) == term_id:
                    self.tree.setCurrentItem(head_item.child(j))

    @staticmethod
    def _heading(text: str, colour: str) -> QLabel:
        lab = QLabel(text.upper())
        lab.setStyleSheet(f"color: {colour}; font-weight: 700; letter-spacing: 1px; font-size: 11px;"
                          f" background: transparent; border: none;")
        return lab

    def retheme(self) -> None:
        self._chips()
        self._populate()
        if self._current:
            self.show_term(self._current)
