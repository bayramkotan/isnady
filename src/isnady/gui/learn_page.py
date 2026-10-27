"""Learn (G7, UI8): the terms of hadith and its sciences, in colour.

Bayram (2026-10-11): "Learn kısmı çok okunaksız → VenvStudio'daki gibi olamaz mı? Biraz daha düzgün, okunaklı ve
renkli??" — each of the ten categories has its own colour and sign, used everywhere the term appears: the
category chips at the top of the list (a click shows that category alone), the dot before each term, the band at
the top of the term's card, the box of its short definition, the chips of its related terms. The card reads from
top to bottom: the term large with its Arabic, its names in the other languages, "In short", "In detail", the
source, the related terms, the ☆ (BM1). The terms are in English, Türkçe and العربية (the interface language when
the glossary has it)."""

import html

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
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
from isnady.core import learn_history
from isnady.core.i18n import tr
from isnady.gui import theme
from isnady.gui.widgets import FlowLayout

# category → (colour, sign): the same in every theme, strong enough on light and on dark backgrounds
CATEGORY_STYLE = {
    "grades": ("#2E7D5B", "✔"), "chain_kinds": ("#1D63A8", "⛓"), "chain": ("#6A4C93", "⟷"),
    "transmission": ("#0F7C8C", "🗣"), "critics": ("#A23B54", "⚖"), "generations": ("#8A5A1E", "⌛"),
    "names": ("#B5651D", "✎"), "shia": ("#7A6A12", "☀"), "books": ("#4E6A86", "📚"), "measures": ("#C0392B", "📊"),
    "history": ("#8B4A2B", "📜"),
}
ARTICLE = "article:"               # the tree's id of an article of History and method (LRN-H1)


class _Count(QThread):
    """One block of live numbers counted in a thread of its own (the first count reads every Arabic text, seconds;
    after that it is kept with the other figures, core.cache)."""

    done = Signal(str, str, list)            # block, language, rows

    def __init__(self, kind: str, lang: str) -> None:
        super().__init__()
        self.kind, self.lang = kind, lang

    def run(self) -> None:
        from isnady.data import db

        conn = None
        try:
            conn = db.connect()
            rows = learn_history.block(conn, self.kind, self.lang)
        except Exception:              # never a crash of the page: the block says there is nothing to show
            rows = []
        finally:
            if conn is not None:
                conn.close()
        self.done.emit(self.kind, self.lang, [list(r) for r in rows])


_LIVE: set = set()


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
    def __init__(self, parent=None, conn_of=None) -> None:
        super().__init__(parent)
        self._conn_of = conn_of or (lambda: None)
        self._blocks: dict = {}                   # (block, language) → rows, counted once per page
        self._waiting: dict = {}                  # (block, language) → the frames waiting for them
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
        self.history_button = QPushButton()
        self.history_button.setObjectName("Primary")
        self.history_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.history_button.clicked.connect(lambda: self.show_term(ARTICLE + "tadwin"))
        lbox.addWidget(self.history_button)
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
        self._name_history()
        self._chips()
        self._populate()
        self.show_term("sahih")

    def _name_history(self) -> None:
        colour, sign = _style("history")
        self.history_button.setText(f"{sign}  {learn_history.label('category', self.lang)}")

    def _set_lang(self, code: str) -> None:
        self.lang = code
        for b, c in zip(self._lang_group.buttons(), learn.LANGUAGES):
            b.setChecked(c == code)            # in step also when the language is set from code or a saved state
        config.state_set("learn.language", code)
        self._name_history()
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
        for key in ["history"] + list(learn.categories()):
            colour, sign = _style(key)
            chip = QPushButton(f"{sign} {self._category_name(key)}")
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

    def _category_name(self, key: str) -> str:
        return learn_history.label("category", self.lang) if key == "history" else learn.category(key, self.lang)

    def _populate(self) -> None:
        found = {t["id"] for t in learn.search(self.query.text(), self.lang)}
        self.tree.clear()
        cats = learn.categories()
        dark = theme.current().dark
        if self._category in (None, "history"):
            # History and method first: the articles (LRN-H1)
            arts = learn_history.search(self.query.text(), self.lang)
            if arts:
                colour, sign = _style("history")
                head = QTreeWidgetItem([f"{sign}  {self._category_name('history')}   ({len(arts)})"])
                font = head.font(0)
                font.setBold(True)
                head.setFont(0, font)
                head.setForeground(0, QBrush(QColor(colour if not dark else QColor(colour).lighter(150).name())))
                self.tree.addTopLevelItem(head)
                for a in arts:
                    item = QTreeWidgetItem([f"●  {learn_history.say(a['title'], self.lang)}"])
                    item.setData(0, Qt.ItemDataRole.UserRole, ARTICLE + a["id"])
                    item.setToolTip(0, learn_history.say(a.get("lead"), self.lang))
                    head.addChild(item)
                head.setExpanded(True)
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
        if term_id and term_id.startswith(ARTICLE):
            self.show_article(term_id[len(ARTICLE):])
            return
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

    # ------------------------------------------------------------------ an article (LRN-H1)
    def _clear(self) -> None:
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def show_article(self, article_id: str) -> None:
        a = learn_history.get(article_id)
        if not a:
            return
        self._current = ARTICLE + article_id
        self._clear()
        self._waiting = {}
        th = theme.current()
        colour, sign = _style("history")
        bright = colour if not th.dark else QColor(colour).lighter(150).name()
        arabic = self.lang == "ar"
        say = lambda v: learn_history.say(v, self.lang)  # noqa: E731

        card = QFrame()
        card.setObjectName("Card")
        cb = QVBoxLayout(card)
        cb.setContentsMargins(0, 0, 0, 22)
        cb.setSpacing(12)
        band = QLabel(f"  {sign}  {html.escape(self._category_name('history'))}")
        band.setStyleSheet(f"background: {colour}; color: white; font-weight: 600; padding: 7px 14px;"
                           f" border-top-left-radius: 13px; border-top-right-radius: 13px;")
        cb.addWidget(band)
        inner = QVBoxLayout()
        inner.setContentsMargins(28, 4, 28, 0)
        inner.setSpacing(12)
        head = QLabel(say(a["title"]))
        head.setWordWrap(True)
        head.setFont(theme.script_font("arabic", bold=True, factor=1.25) if arabic else theme.reading_font(26, bold=True))
        head.setStyleSheet(f"color: {bright};")
        head.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        inner.addWidget(head)
        texts = [head]
        lead_box = QFrame()
        lead_box.setStyleSheet(f"QFrame {{ background: {_soft(colour, th.dark)}; border-left: 5px solid {colour};"
                               f" border-radius: 8px; }}")
        lb = QVBoxLayout(lead_box)
        lb.setContentsMargins(16, 10, 16, 12)
        lead = _label(say(a.get("lead")), "Lead")
        lead.setFont(theme.script_font("arabic", bold=True, factor=0.9) if arabic else theme.reading_font(16, bold=True))
        lead.setStyleSheet(f"color: {th.ink}; background: transparent; border: none;")
        lb.addWidget(lead)
        texts.append(lead)
        inner.addWidget(lead_box)
        for sec in a["sections"]:
            inner.addSpacing(6)
            inner.addWidget(self._heading(say(sec.get("heading")), bright))
            for para in say(sec.get("text")) or []:
                lab = _label(html.escape(para), "Lead", rich=True)
                lab.setFont(theme.script_font("arabic", factor=0.85) if arabic else theme.reading_font(15))
                lab.setStyleSheet(f"color: {th.ink}; line-height: 150%;")
                inner.addWidget(lab)
                texts.append(lab)
            if sec.get("block"):
                inner.addWidget(self._block_frame(sec["block"], colour))
        if arabic:
            for lab in texts:
                lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
                lab.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        if a.get("sources"):
            src = _label(f"📜 <b>{html.escape(learn_history.label('sources', self.lang))}</b>: "
                         f"{html.escape(say(a['sources']))}", "Caption", rich=True)
            src.setStyleSheet(f"background: {th.pill}; border-radius: 8px; padding: 6px 10px;")
            inner.addWidget(src)
        cb.addLayout(inner)
        self.box.addWidget(card)

        others = [x for x in learn_history.articles() if x["id"] != article_id]
        if others:
            more = QFrame()
            more.setObjectName("Card")
            mb = QVBoxLayout(more)
            mb.setContentsMargins(24, 14, 24, 16)
            mb.addWidget(self._heading(learn_history.label("more", self.lang), th.muted))
            holder = QWidget()
            fl = FlowLayout(holder)
            for x in others:
                b = QPushButton(say(x["title"]))
                b.setObjectName("Chip")
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(lambda _c=False, xid=x["id"]: self.show_article(xid))
                fl.addWidget(b)
            mb.addWidget(holder)
            self.box.addWidget(more)
        self.box.addStretch(1)
        for i in range(self.tree.topLevelItemCount()):
            head_item = self.tree.topLevelItem(i)
            for j in range(head_item.childCount()):
                if head_item.child(j).data(0, Qt.ItemDataRole.UserRole) == self._current:
                    self.tree.setCurrentItem(head_item.child(j))

    def _block_frame(self, kind: str, colour: str) -> QFrame:
        """A box of live numbers: drawn at once when counted before, else "Counting…" and filled when the thread
        has counted them."""
        th = theme.current()
        frame = QFrame()
        frame.setStyleSheet(f"QFrame#Numbers {{ border: 1px solid {_soft(colour, th.dark, 0.45)}; border-radius: 10px;"
                            f" background: {th.surface}; }}")
        frame.setObjectName("Numbers")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 12)
        key = (kind, self.lang)
        if kind == "timeline":
            self._fill(frame, learn_history.block(None, "timeline", self.lang), colour, live=False)
            return frame
        if key in self._blocks:
            self._fill(frame, self._blocks[key], colour)
            return frame
        lay.addWidget(_label("⏳ " + learn_history.label("counting", self.lang), "Caption"))
        self._waiting.setdefault(key, []).append(frame)
        if self._conn_of() is None:
            self._fill(frame, [], colour)
            return frame
        worker = _Count(kind, self.lang)
        worker.done.connect(self._counted)
        _LIVE.add(worker)
        worker.finished.connect(lambda w=worker: (_LIVE.discard(w), w.deleteLater()))
        worker.start()
        return frame

    def _counted(self, kind: str, lang: str, rows: list) -> None:
        self._blocks[(kind, lang)] = rows
        colour, _sign = _style("history")
        for frame in self._waiting.pop((kind, lang), []):
            try:
                self._fill(frame, rows, colour)
            except RuntimeError:          # the article was left before the count ended: its frame is gone
                pass

    def _fill(self, frame: QFrame, rows: list, colour: str, live: bool = True) -> None:
        lay = frame.layout()
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        th = theme.current()
        arabic = self.lang == "ar"
        if not rows:
            lay.addWidget(_label(learn_history.label("no_data", self.lang), "Caption"))
            return
        grid_holder = QWidget()
        grid = QGridLayout(grid_holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(5)
        if arabic:
            grid_holder.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        r = 0
        for label, value, note in rows:
            if not value:                     # a heading row: the tradition
                head = QLabel(label)
                head.setTextFormat(Qt.TextFormat.PlainText)
                head.setStyleSheet(f"color: {colour if not th.dark else QColor(colour).lighter(150).name()};"
                                   f" font-weight: 700; padding-top: 8px;")
                grid.addWidget(head, r, 0, 1, 3)
            elif not live:                    # the timeline: the years, then what happened
                when = _label(f"<b>{html.escape(label)}</b>", rich=True)
                when.setMinimumWidth(150)
                grid.addWidget(when, r, 0, Qt.AlignmentFlag.AlignTop)
                what = _label(html.escape(value), rich=True)
                grid.addWidget(what, r, 1, 1, 2)
            else:
                name = _label(html.escape(label), rich=True)
                name.setMinimumWidth(240)
                val = _label(f"<b>{html.escape(value)}</b>", rich=True)
                if value[:1].isdigit():                 # a number large; a name (a Companion) as the text
                    val.setFont(theme.reading_font(15, bold=True))
                grid.addWidget(name, r, 0)
                grid.addWidget(val, r, 1)
                if note:
                    grid.addWidget(_label(html.escape(note), "Caption", rich=True), r, 2)
            r += 1
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(2, 3)
        lay.addWidget(grid_holder)
        if live:
            lay.addWidget(_label("ⓘ " + learn_history.label("live", self.lang), "Caption"))

    @staticmethod
    def _heading(text: str, colour: str) -> QLabel:
        lab = QLabel(text.upper())
        lab.setStyleSheet(f"color: {colour}; font-weight: 700; letter-spacing: 1px; font-size: 11px;"
                          f" background: transparent; border: none;")
        return lab

    def retheme(self) -> None:
        self._name_history()
        self._chips()
        self._populate()
        if self._current:
            self.show_term(self._current)
