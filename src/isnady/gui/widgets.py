"""Small reusable widgets."""

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import QLayout, QSizePolicy, QWidget


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
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x, y, line_height = rect.x(), rect.y(), 0
        space = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + space
            if next_x - space > rect.right() and line_height > 0:
                x = rect.x()
                y += line_height + space
                next_x = x + hint.width() + space
                line_height = 0
            if not test_only:
                left = rect.right() - (x - rect.x()) - hint.width() + 1 if self._rtl else x
                item.setGeometry(QRect(QPoint(left, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


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
        self._heights: dict[int, int] = {}
        self.setSizePolicy(expanding_width_policy())
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        from PySide6.QtGui import QAction

        copy = QAction("Copy text", self)
        copy.triggered.connect(self.copy)
        self.addAction(copy)

    def plain_text(self) -> str:
        return self._doc.toPlainText()

    def copy(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.plain_text())

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        width = max(width, 1)
        height = self._heights.get(width)
        if height is None:
            self._doc.setTextWidth(width)
            height = int(self._doc.size().height() + 0.999)
            self._heights[width] = height
        return height

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
        if event.oldSize().width() != event.size().width():
            self.updateGeometry()          # a new width means a new height: let the layout ask again

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter

        if self._doc.textWidth() != self.width():
            self._doc.setTextWidth(self.width())
        painter = QPainter(self)
        self._doc.drawContents(painter)
        painter.end()


# ------------------------------------------------------------------ books: Sunni first, Shia after them (core.books)
def fill_book_combo(combo, conn, all_label: str | None = None) -> None:
    """A book list with the Sunni and Shia collections apart, each under its own heading (the headings cannot be
    chosen). The current choice is kept when it is still there."""
    from PySide6.QtGui import QFont

    from isnady.core import books as core_books

    current = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    if all_label is not None:
        combo.addItem(all_label, None)
    for _t, label, group in core_books.grouped(conn):
        if combo.count():
            combo.insertSeparator(combo.count())
        combo.addItem(f"{label} collections", "__heading__")
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
        self.button = QPushButton("All books")
        self.button.setObjectName("BookPicker")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setToolTip("Search all books, or tick the ones to search")
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

    def _label(self) -> None:
        if self._chosen is None:
            text = "All books"
        else:
            whole = [label for _t, label, g in self._groups if {b["key"] for b in g} == self._chosen]
            if whole:
                text = f"{whole[0]} ({len(self._chosen)})"
            elif len(self._chosen) == 1:
                key = next(iter(self._chosen))
                text = next(b["name"] for _t, _l, g in self._groups for b in g if b["key"] == key)
            else:
                text = f"{len(self._chosen)} books"
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
            head = QTreeWidgetItem(tree, [f"{label} collections"])
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
        for text, keys in [("All", everything)] + [(label, {b["key"] for b in g}) for _t, label, g in self._groups] \
                + [("None", set())]:
            b = QPushButton(text)
            b.setObjectName("Quiet")
            b.clicked.connect(lambda _c=False, k=keys: tick(k))
            row.addWidget(b)
        row.addStretch(1)
        done = QPushButton("Search these")
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
