"""Small reusable widgets."""

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import QLayout, QSizePolicy, QWidget
from isnady.core.i18n import tr


class FlowLayout(QLayout):
    """Lays items out left to right and wraps them onto new lines (Qt's flow layout example)."""

    def __init__(self, parent=None, spacing: int = 6, rtl: bool = False) -> None:
        super().__init__(parent)
        self._items = []
        self._rtl = rtl                      # lay items out from the right edge (Arabic reading order)
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        height = self._do_layout(rect, test_only=False)
        # the widget that holds the flow is made as tall as its lines: a layout that does not ask heightForWidth (a
        # QVBoxLayout in a scroll area) gave it the height of one line and cut the second row of the recent searches
        # in half (Bayram, 2026-10-26, screenshot)
        owner = self.parentWidget()
        if owner is not None and owner.layout() is self and rect.width() > 0:
            margins = self.contentsMargins()
            need = height + margins.top() + margins.bottom()
            if owner.minimumHeight() != need:
                owner.setMinimumHeight(need)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        # the items of each line are centred on the line, so a label sits level with the field and the buttons
        # beside it (NAV3)
        space = self.spacing()
        lines, line, x = [], [], rect.x()
        for item in self._items:
            hint = item.sizeHint()
            if line and x + hint.width() > rect.right() + 1:
                lines.append(line)
                line, x = [], rect.x()
            line.append((item, hint, x))
            x += hint.width() + space
        if line:
            lines.append(line)
        y = rect.y()
        for i, line in enumerate(lines):
            height = max(h.height() for _it, h, _x in line)
            if not test_only:
                for item, hint, left in line:
                    if self._rtl:
                        left = rect.right() - (left - rect.x()) - hint.width() + 1
                    item.setGeometry(QRect(QPoint(left, y + (height - hint.height()) // 2), hint))
            y += height + (space if i < len(lines) - 1 else 0)
        return y - rect.y()


def expanding_width_policy() -> QSizePolicy:
    policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    policy.setHeightForWidth(True)
    return policy


class TextBlock(QWidget):
    """Rich text that is laid out once per width and then reused.

    QLabel re-shapes its text every time a layout asks for its height, and a
    layout asks many times; with long Arabic text in Amiri that made a page of
    results take over a second. This widget keeps one QTextDocument and caches
    the height for each width it has been asked about.

    PERF1 (2026-10-12): a layout asks at many widths before it settles (a card of a chapter of Muslim was laid out
    at 640, 586, 661, 644, 646, 659, 633 and 635 px — 1,245 full layouts of Arabic text for 180 texts, 0.7 s).
    Now the text is laid out once to learn how long it is; for a width it has not been shown at, the height is
    estimated from that (no layout); the real layout is made only at the width the widget actually gets
    (resizeEvent), and when it differs from the estimate the layout is asked again.
    """

    def __init__(self, html: str, font, rtl: bool = False, parent=None) -> None:
        super().__init__(parent)
        from PySide6.QtGui import QTextDocument, QTextOption

        self._doc = QTextDocument(self)
        self._doc.setDefaultFont(font)
        self._doc.setDocumentMargin(0)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WordWrap)
        if rtl:
            option.setTextDirection(Qt.LayoutDirection.RightToLeft)
            option.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
        self._doc.setDefaultTextOption(option)
        self._doc.setHtml(html)
        self._heights: dict[int, int] = {}          # width → real height (laid out at that width)
        self._base: tuple[int, int, int] | None = None   # (width, height, lines) of the first real layout
        self.setSizePolicy(expanding_width_policy())
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        from PySide6.QtGui import QAction

        copy = QAction(tr("Copy text"), self)
        copy.triggered.connect(self.copy)
        self.addAction(copy)

    def plain_text(self) -> str:
        return self._doc.toPlainText()

    def copy(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.plain_text())

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def _real_height(self, width: int) -> int:
        """Lay the text out at this width (the costly part) and keep the height."""
        height = self._heights.get(width)
        if height is None:
            self._doc.setTextWidth(width)
            height = int(self._doc.size().height() + 0.999)
            self._heights[width] = height
            if self._base is None:
                lines = sum(self._doc.documentLayout().blockBoundingRect(b).height() > 0 and b.layout().lineCount()
                            for b in _blocks(self._doc))
                self._base = (width, height, max(1, lines))
        return height

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        width = max(width, 1)
        height = self._heights.get(width)
        if height is not None:
            return height
        if self._base is None:
            # not laid out yet (a card being built, not yet at its place): a guess from the length of the text, so
            # the one real layout is made at the width the text is shown at
            from PySide6.QtGui import QFontMetrics

            fm = QFontMetrics(self._doc.defaultFont())
            chars = max(1, self._doc.characterCount())
            lines = max(1, -(-chars * fm.averageCharWidth() // width))
            return lines * fm.lineSpacing()
        # an estimate: the same text over as many lines as its length needs at this width (no layout)
        w0, h0, n0 = self._base
        if n0 <= 1 and width >= w0:
            return h0
        lines = max(1, -(-n0 * w0 // width))            # ceil(n0 * w0 / width)
        return max(1, round(h0 * lines / n0))

    def sizeHint(self) -> QSize:  # noqa: N802
        width = self.width() if self.width() > 50 else 600
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        # one line only: the real height comes from heightForWidth at the width the layout gives. A minimum
        # measured at the creation width (narrow, or 600) made the results area as tall as every text at that
        # width — thousands of empty pixels below the last card (BUG-S1)
        return QSize(80, self.fontMetrics().height())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        width = event.size().width()
        if width > 1 and (event.oldSize().width() != width or width not in self._heights):
            real = self._real_height(width)
            if real != event.size().height() or event.oldSize().width() != width:
                self.updateGeometry()      # the real height at the width given: let the layout ask again

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter

        if self._doc.textWidth() != self.width():
            self._real_height(self.width())
            self._doc.setTextWidth(self.width())
        painter = QPainter(self)
        self._doc.drawContents(painter)
        painter.end()


def _blocks(doc):
    block = doc.begin()
    while block.isValid():
        yield block
        block = block.next()


# ------------------------------------------------------------------ books: Sunni first, Shia after them (core.books)
def fill_book_combo(combo, conn, all_label: str | None = None) -> None:
    """A book list with the Sunni and Shia collections apart, each under its own heading (the headings cannot be
    chosen). The current choice is kept when it is still there."""
    from PySide6.QtGui import QFont

    from isnady.core import books as core_books

    current = combo.currentData()
    combo.blockSignals(True)
    # a list below the box that scrolls, long enough for a shelf (the Fusion style showed every book at once around
    # the current one, and the first entries — "All Sunni books", "All Shia books" — went off the screen;
    # theme.py: combobox-popup: 0)
    combo.setMaxVisibleItems(20)
    if not combo.property("roomy"):
        from PySide6.QtWidgets import QStyledItemDelegate

        combo.setItemDelegate(QStyledItemDelegate(combo))      # rows as tall as before (theme.py: ::item padding)
        combo.setProperty("roomy", True)
    combo.clear()
    if all_label is not None:
        combo.addItem(all_label, None)
    for _t, label, group in core_books.grouped(conn):
        if combo.count():
            combo.insertSeparator(combo.count())
        combo.addItem(tr("{group} collections", group=tr(label)), "__heading__")
        item = combo.model().item(combo.count() - 1)
        item.setEnabled(False)
        font = QFont(combo.font())
        font.setBold(True)
        item.setFont(font)
        for b in group:
            combo.addItem(f"    {b['name']} ({b['count']:,})", b["key"])
    index = combo.findData(current)
    if index < 0 or combo.itemData(index) == "__heading__":
        index = next((i for i in range(combo.count()) if combo.itemData(i) not in ("__heading__",)
                      and combo.model().item(i) is not None and combo.model().item(i).isEnabled()), 0)
    combo.setCurrentIndex(index)
    combo.blockSignals(False)


class BookPicker(QWidget):
    """Choose the books to search: all of them, all Sunni, all Shia, or any few ticked one by one.

    A button shows the choice ("All books", "Sunni (17)", "3 books"); clicking it opens a list with the Sunni and
    Shia collections apart, each heading ticking its whole group. selected() is None for every book."""

    changed = Signal()

    def __init__(self, parent=None) -> None:
        from PySide6.QtWidgets import QHBoxLayout, QPushButton

        super().__init__(parent)
        self._conn = None
        self._chosen: set[str] | None = None          # None: every book
        self._groups: list = []
        self.button = QPushButton(tr("All books"))
        self.button.setObjectName("BookPicker")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setToolTip(tr("Search all books, or tick the ones to search"))
        self.button.clicked.connect(self._open)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.button)

    def fill(self, conn) -> None:
        from isnady.core import books as core_books

        self._conn = conn
        self._groups = core_books.grouped(conn)
        keys = {b["key"] for _t, _l, g in self._groups for b in g}
        if self._chosen is not None:
            self._chosen &= keys
            if not self._chosen or self._chosen == keys:
                self._chosen = None
        self._label()

    def selected(self) -> list[str] | None:
        return None if self._chosen is None else sorted(self._chosen)

    def reset(self) -> None:
        """Every book again (the Home button of the Search page, NAV1); no changed signal: nothing is searched."""
        self._chosen = None
        self._label()

    def _label(self) -> None:
        if self._chosen is None:
            text = tr("All books")
        else:
            whole = [label for _t, label, g in self._groups if {b["key"] for b in g} == self._chosen]
            if whole:
                text = f"{tr(whole[0])} ({len(self._chosen)})"
            elif len(self._chosen) == 1:
                key = next(iter(self._chosen))
                text = next(b["name"] for _t, _l, g in self._groups for b in g if b["key"] == key)
            else:
                text = tr("{n} books", n=len(self._chosen))
        self.button.setText(text + "   ▾")
        self.button.setProperty("active", self._chosen is not None)      # a narrowed search is marked
        self.button.style().unpolish(self.button)
        self.button.style().polish(self.button)

    def _open(self) -> None:
        from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout

        popup = QFrame(self, Qt.WindowType.Popup)
        popup.setObjectName("Card")
        lay = QVBoxLayout(popup)
        lay.setContentsMargins(10, 10, 10, 10)
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setMinimumSize(420, 460)
        everything = {b["key"] for _t, _l, g in self._groups for b in g}
        chosen = everything if self._chosen is None else self._chosen
        for _t, label, group in self._groups:
            head = QTreeWidgetItem(tree, [tr("{group} collections", group=tr(label))])
            head.setFlags(head.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            font = head.font(0)
            font.setBold(True)
            head.setFont(0, font)
            for b in group:
                item = QTreeWidgetItem(head, [f"{b['name']}  ({b['count']:,})"])
                item.setData(0, Qt.ItemDataRole.UserRole, b["key"])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked if b["key"] in chosen else Qt.CheckState.Unchecked)
            head.setExpanded(True)
        lay.addWidget(tree)
        row = QHBoxLayout()

        def tick(keys: set) -> None:
            for i in range(tree.topLevelItemCount()):
                head = tree.topLevelItem(i)
                for j in range(head.childCount()):
                    c = head.child(j)
                    c.setCheckState(0, Qt.CheckState.Checked if c.data(0, Qt.ItemDataRole.UserRole) in keys
                                    else Qt.CheckState.Unchecked)
        for text, keys in [(tr("All"), everything)] + [(tr(label), {b["key"] for b in g}) for _t, label, g in
                                                         self._groups] + [(tr("None"), set())]:
            b = QPushButton(text)
            b.setObjectName("Quiet")
            b.clicked.connect(lambda _c=False, k=keys: tick(k))
            row.addWidget(b)
        row.addStretch(1)
        done = QPushButton(tr("Search these"))
        done.setObjectName("Primary")
        row.addWidget(done)
        lay.addLayout(row)

        def apply() -> None:
            picked = set()
            for i in range(tree.topLevelItemCount()):
                head = tree.topLevelItem(i)
                for j in range(head.childCount()):
                    c = head.child(j)
                    if c.checkState(0) == Qt.CheckState.Checked:
                        picked.add(c.data(0, Qt.ItemDataRole.UserRole))
            new = None if not picked or picked == everything else picked
            popup.close()
            if new != self._chosen:
                self._chosen = new
                self._label()
                self.changed.emit()
        done.clicked.connect(apply)
        popup.adjustSize()
        popup.move(self.button.mapToGlobal(self.button.rect().bottomLeft()))
        popup.show()


class LanguagePicker(QWidget):
    """Choose the languages to search (LANG3, 2026-10-18): all of them, or any few ticked. The button shows the
    choice ("All languages", "Arabic", "Arabic, Turkish"); the list holds every imported language by its name in the
    interface language, and — when the data repository has more — a line that opens Data Sources (wants_import).
    selected() is [] for every language."""

    changed = Signal()
    wants_import = Signal()

    def __init__(self, parent=None) -> None:
        from PySide6.QtWidgets import QHBoxLayout, QPushButton

        super().__init__(parent)
        self._languages: list[str] = []
        self._more: list[str] = []
        self._chosen: set[str] = set()                   # empty: every language
        self.button = QPushButton(tr("All languages"))
        self.button.setObjectName("BookPicker")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setToolTip(tr("Search every language, or tick the ones to search"))
        self.button.clicked.connect(self._open)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.button)

    def fill(self, languages: list[str], more: list[str] | None = None) -> None:
        self._languages = list(languages)
        self._more = list(more or [])
        self._chosen &= set(self._languages)
        if self._chosen == set(self._languages):
            self._chosen = set()
        self._label()

    def selected(self) -> list[str]:
        return [lang for lang in self._languages if lang in self._chosen]

    def set_selected(self, languages: list[str]) -> None:
        self._chosen = {lang for lang in languages if lang in self._languages}
        if self._chosen == set(self._languages):
            self._chosen = set()
        self._label()

    def _label(self) -> None:
        if not self._chosen:
            text = tr("All languages")
        else:
            names = [tr(lang) for lang in self.selected()]
            text = ", ".join(names) if len(names) <= 2 else tr("{n} languages", n=len(names))
        self.button.setText(text + "   ▾")
        self.button.setProperty("active", bool(self._chosen))
        self.button.style().unpolish(self.button)
        self.button.style().polish(self.button)

    def _open(self) -> None:
        from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QPushButton, QVBoxLayout

        popup = QFrame(self, Qt.WindowType.Popup)
        popup.setObjectName("Card")
        lay = QVBoxLayout(popup)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        everything = QCheckBox(tr("All languages"))
        everything.setChecked(not self._chosen)
        lay.addWidget(everything)
        checks = []
        for lang in self._languages:
            c = QCheckBox(tr(lang))
            c.setProperty("language", lang)
            c.setChecked(not self._chosen or lang in self._chosen)
            lay.addWidget(c)
            checks.append(c)

        def whole(on: bool) -> None:
            for c in checks:
                c.blockSignals(True)
                c.setChecked(on)
                c.blockSignals(False)

        def one(_on: bool) -> None:
            everything.blockSignals(True)
            everything.setChecked(all(c.isChecked() for c in checks))
            everything.blockSignals(False)
        everything.toggled.connect(whole)
        for c in checks:
            c.toggled.connect(one)
        if self._more:
            names = ", ".join(tr(n) for n in self._more[:5]) + (" …" if len(self._more) > 5 else "")
            more = QPushButton(tr("More languages: {names} — import", names=names))
            more.setObjectName("Link")
            more.setCursor(Qt.CursorShape.PointingHandCursor)
            more.setToolTip(tr("These books are in the data repository in more languages: {names}. File → Data Sources "
                               "imports them (tick the languages beside a book); they then appear in this list.",
                               names=", ".join(tr(n) for n in self._more)))
            more.clicked.connect(lambda: (popup.close(), self.wants_import.emit()))
            lay.addWidget(more)
        row = QHBoxLayout()
        row.addStretch(1)
        done = QPushButton(tr("Search these"))
        done.setObjectName("Primary")
        row.addWidget(done)
        lay.addLayout(row)

        def apply() -> None:
            picked = {c.property("language") for c in checks if c.isChecked()}
            new = set() if not picked or picked == set(self._languages) else picked
            popup.close()
            if new != self._chosen:
                self._chosen = new
                self._label()
                self.changed.emit()
        done.clicked.connect(apply)
        popup.adjustSize()
        popup.move(self.button.mapToGlobal(self.button.rect().bottomLeft()))
        popup.show()
