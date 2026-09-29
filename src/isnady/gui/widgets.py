"""Small reusable widgets."""

from PySide6.QtCore import QPoint, QRect, QSize, Qt
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
        return QSize(80, self.heightForWidth(self.width() if self.width() > 50 else 600))

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter

        if self._doc.textWidth() != self.width():
            self._doc.setTextWidth(self.width())
        painter = QPainter(self)
        self._doc.drawContents(painter)
        painter.end()
