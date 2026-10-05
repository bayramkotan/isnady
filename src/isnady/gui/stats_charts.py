"""Charts drawn for isnady in its own colours and type (ST7): a heat map and an interval (forest) plot."""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from isnady.gui import theme


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


class HeatMap(QWidget):
    """A square table of cells coloured by value. cells[r][c] = (value or None, [text lines]); diverging=True colours
    below zero gold and above zero lapis (for signed measures), otherwise light → lapis."""

    def __init__(self, rows: list[str], cols: list[str], cells: list[list[tuple]], low: float = 0.0, high: float = 1.0,
                 diverging: bool = False, cell: QSize = QSize(132, 58), label_w: int = 150, parent=None) -> None:
        super().__init__(parent)
        self.rows, self.cols, self.cells = rows, cols, cells
        self.low, self.high, self.diverging = low, high, diverging
        self.cell = cell
        self.label_w = label_w
        self.head_h = 44
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMinimumSize(self.sizeHint())

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.label_w + self.cell.width() * len(self.cols) + 4, self.head_h + self.cell.height() * len(self.rows) + 4)

    def _colour(self, v: float) -> QColor:
        t = theme.current()
        base = QColor(t.surface)
        if self.diverging:
            span = max(abs(self.low), abs(self.high)) or 1
            x = v / span
            return _mix(base, QColor(t.lapis), x) if x >= 0 else _mix(base, QColor(t.gold), -x)
        return _mix(base, QColor(t.lapis), (v - self.low) / ((self.high - self.low) or 1))

    def paintEvent(self, _e) -> None:  # noqa: N802
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        small = QFont(self.font())
        small.setPointSizeF(self.font().pointSizeF() * 0.86)
        bold = QFont(self.font())
        bold.setBold(True)
        p.setPen(QColor(t.muted))
        p.setFont(small)
        for c, name in enumerate(self.cols):
            r = QRectF(self.label_w + c * self.cell.width(), 0, self.cell.width(), self.head_h - 4)
            p.drawText(r, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom | Qt.TextFlag.TextWordWrap, name)
        for rr, name in enumerate(self.rows):
            y = self.head_h + rr * self.cell.height()
            p.setPen(QColor(t.ink))
            p.setFont(bold)
            p.drawText(QRectF(0, y, self.label_w - 10, self.cell.height()),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap, name)
            for c in range(len(self.cols)):
                value, lines = self.cells[rr][c]
                box = QRectF(self.label_w + c * self.cell.width() + 2, y + 2, self.cell.width() - 4, self.cell.height() - 4)
                if value is None:
                    p.setPen(QPen(QColor(t.border), 1))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(box, 6, 6)
                    if lines:                          # a note in an empty cell ("too few")
                        p.setPen(QColor(t.muted))
                        p.setFont(small)
                        p.drawText(box, Qt.AlignmentFlag.AlignCenter, lines[0])
                    continue
                fill = self._colour(value)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(fill)
                p.drawRoundedRect(box, 6, 6)
                dark = fill.lightnessF() < 0.55
                p.setPen(QColor("#FFFFFF") if dark else QColor(t.ink))
                p.setFont(bold)
                p.drawText(box.adjusted(0, 4, 0, -box.height() / 2), Qt.AlignmentFlag.AlignCenter, lines[0] if lines else "")
                if len(lines) > 1:
                    p.setFont(small)
                    p.drawText(box.adjusted(0, box.height() / 2 - 2, 0, -2), Qt.AlignmentFlag.AlignCenter, lines[1])
        p.end()


class IntervalPlot(QWidget):
    """One row per item: a dot at the value and a line over its 95% interval, around a zero line.
    rows = [(label, value, (low, high))]; left/right = what each side of zero means."""

    def __init__(self, rows: list[tuple[str, float, tuple[float, float]]], left: str, right: str, parent=None) -> None:
        super().__init__(parent)
        self.rows, self.left, self.right = rows, left, right
        span = max([abs(v) for _l, v, _c in rows] + [abs(x) for _l, _v, c in rows for x in c] + [0.05])
        self.span = span * 1.15
        self.label_w, self.row_h, self.top, self.bottom = 290, 40, 8, 40
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(self.top + self.row_h * len(rows) + self.bottom)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(640, self.minimumHeight())

    def paintEvent(self, _e) -> None:  # noqa: N802
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x0, x1 = self.label_w, self.width() - 70
        def X(v):
            return x0 + (v + self.span) / (2 * self.span) * (x1 - x0)
        h = self.top + self.row_h * len(self.rows)
        p.setPen(QPen(QColor(t.border), 1, Qt.PenStyle.DashLine))
        p.drawLine(int(X(0)), self.top, int(X(0)), h)
        small = QFont(self.font())
        small.setPointSizeF(self.font().pointSizeF() * 0.86)
        for i, (label, v, (lo, hi)) in enumerate(self.rows):
            y = self.top + i * self.row_h + self.row_h / 2
            p.setPen(QColor(t.ink))
            p.setFont(self.font())
            p.drawText(QRectF(0, y - self.row_h / 2, x0 - 12, self.row_h),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap, label)
            colour = QColor(t.gold) if v < 0 else QColor(t.lapis)
            p.setPen(QPen(colour, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(int(X(lo)), int(y), int(X(hi)), int(y))
            p.setBrush(colour)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(X(v) - 6, y - 6, 12, 12))
            p.setPen(QColor(t.muted))
            p.setFont(small)
            p.drawText(QRectF(x1 + 6, y - self.row_h / 2, 70, self.row_h), Qt.AlignmentFlag.AlignVCenter, f"{v:+.3f}")
        p.setPen(QColor(t.muted))
        p.setFont(small)
        p.drawText(QRectF(x0, h + 6, X(0) - x0 - 8, 30), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, "◀ " + self.left)
        p.drawText(QRectF(X(0) + 8, h + 6, x1 - X(0), 30), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.right + " ▶")
        p.end()
