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
        p.setPen(QPen(QColor(t.muted), 1))                 # the zero line: a solid hairline
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


# ---------------------------------------------------------------------------------------------- ST7, deep (2026-10-08)
# The charts of the corpus statistics. Marks are thin (bars at most 22 px, rounded at the data end), separated by a
# 2 px gap in the surface colour; grids and axes are hairlines one step off the surface; text wears the text tokens,
# never the series colour; every mark answers the mouse with its numbers.

from PySide6.QtCore import QPointF, Signal  # noqa: E402
from PySide6.QtGui import QPainterPath  # noqa: E402
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolTip, QVBoxLayout  # noqa: E402


def _fmt(n: float) -> str:
    return f"{n:,.0f}" if abs(n) >= 1 or n == 0 else f"{n:.2f}"


def _rounded_bar(p: QPainter, rect: QRectF, radius: float = 4.0, round_left: bool = False, round_right: bool = True) -> None:
    """A bar rounded only at its data end (square at the baseline)."""
    r = min(radius, rect.height() / 2, rect.width() / 2)
    path = QPainterPath()
    path.addRoundedRect(rect, r, r)
    if not round_left:
        path.addRect(QRectF(rect.left(), rect.top(), min(r, rect.width()), rect.height()))
    if not round_right:
        path.addRect(QRectF(rect.right() - min(r, rect.width()), rect.top(), min(r, rect.width()), rect.height()))
    p.drawPath(path.simplified())


class StatTiles(QWidget):
    """A row of figures: a label, the figure, a line saying what it means (no chart where the story is a number)."""

    def __init__(self, items: list[tuple[str, str, str]], parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        t = theme.current()
        for label, value, note in items:
            tile = QFrame()
            tile.setObjectName("Tile")
            box = QVBoxLayout(tile)
            box.setContentsMargins(16, 12, 16, 12)
            box.setSpacing(2)
            top = QLabel(label)
            top.setStyleSheet(f"color: {t.muted}; font-size: 9pt; background: transparent;")
            fig = QLabel(value)
            fig.setStyleSheet(f"color: {t.ink}; font-size: 20pt; font-weight: 600; background: transparent;")
            sub = QLabel(note)
            sub.setWordWrap(True)
            sub.setStyleSheet(f"color: {t.muted}; font-size: 8.5pt; background: transparent;")
            for w in (top, fig, sub):
                box.addWidget(w)
            box.addStretch(1)                          # the figures line up at the top of every tile
            row.addWidget(tile, 1)


class StackedBars(QWidget):
    """Rows of 100% bars split into ordered categories (rank groups, grades), a legend under them. Each segment
    tells its count and share on hover. rows: [(label, [count per category])]; categories: [(name, colour)]."""

    def __init__(self, rows: list[tuple[str, list[int]]], categories: list[tuple[str, str]], label_w: int = 190,
                 parent=None) -> None:
        super().__init__(parent)
        self.rows, self.categories, self.label_w = rows, categories, label_w
        self.bar_h, self.row_h, self.legend_h = 22, 40, 30
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(self.sizeHint().height())

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(560, self.row_h * len(self.rows) + self.legend_h + 6)

    def _segments(self):
        width = max(40, self.width() - self.label_w - 60)
        for r, (label, counts) in enumerate(self.rows):
            total = sum(counts) or 1
            x = float(self.label_w)
            y = r * self.row_h + (self.row_h - self.bar_h) / 2
            for c, n in enumerate(counts):
                w = width * n / total
                yield r, c, QRectF(x, y, w, self.bar_h), n, total
                x += w

    def paintEvent(self, _e) -> None:  # noqa: N802
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        segs = list(self._segments())
        for r, (label, counts) in enumerate(self.rows):
            p.setPen(QColor(t.ink))
            p.drawText(QRectF(0, r * self.row_h, self.label_w - 12, self.row_h),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight | Qt.TextFlag.TextWordWrap, label)
            p.setPen(QColor(t.muted))
            total = sum(counts)
            p.drawText(QRectF(self.width() - 56, r * self.row_h, 56, self.row_h),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, _fmt(total))
        p.setPen(Qt.PenStyle.NoPen)
        last_of_row = {}
        for r, c, rect, n, _tot in segs:
            if n:
                last_of_row[r] = c
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)          # crisp edges: no seams in the gaps
        for r, c, rect, n, _tot in segs:
            if not n:
                continue
            last = c == last_of_row.get(r)
            colour = QColor(self.categories[c][1])
            # a 2 px surface gap after every segment but the last, which ends rounded instead
            inner = QRectF(rect.left(), rect.top(), max(1.0, rect.width() - (0 if last else 2)), rect.height())
            if last and inner.width() > 6:
                p.fillRect(QRectF(inner.left(), inner.top(), inner.width() - 4, inner.height()), colour)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.setBrush(colour)
                p.drawRoundedRect(QRectF(inner.right() - 8, inner.top(), 8, inner.height()), 4, 4)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            else:
                p.fillRect(inner, colour)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # the legend
        x, y = float(self.label_w), self.row_h * len(self.rows) + 8
        fm = p.fontMetrics()
        for name, colour in self.categories:
            p.setBrush(QColor(colour))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x, y + 4, 10, 10), 2, 2)
            p.setPen(QColor(t.muted))
            p.drawText(QPointF(x + 15, y + 13), name)
            x += 15 + fm.horizontalAdvance(name) + 18
        p.end()

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        for r, c, rect, n, total in self._segments():
            if n and rect.contains(e.position()):
                QToolTip.showText(e.globalPosition().toPoint(),
                                  f"{self.rows[r][0]}\n{self.categories[c][0]}: {n:,} ({100 * n / total:.1f}%)", self)
                return
        QToolTip.hideText()


class Columns(QWidget):
    """Columns over ordered bins (a histogram): bins = [(label, value)], one hue; marked bins (a set of indexes)
    take the accent colour — the ones the text points to. Hover: the bin's label and value."""

    def __init__(self, bins: list[tuple[str, float]], unit: str = "", marked: set | None = None, height: int = 200,
                 label_every: int = 1, parent=None) -> None:
        super().__init__(parent)
        self.bins, self.unit, self.marked, self.label_every = bins, unit, marked or set(), label_every
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(height)

    def _geometry(self):
        left, bottom, top = 46, 26, 10
        plot_w = max(40, self.width() - left - 8)
        plot_h = self.height() - bottom - top
        peak = max((v for _l, v in self.bins), default=0) or 1
        slot = plot_w / max(1, len(self.bins))
        bar_w = min(22.0, slot - 2)
        return left, bottom, top, plot_h, peak, slot, bar_w

    def paintEvent(self, _e) -> None:  # noqa: N802
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, bottom, top, plot_h, peak, slot, bar_w = self._geometry()
        base_y = top + plot_h
        p.setPen(QPen(QColor(t.border), 1))
        for k in range(0, 5):
            y = base_y - plot_h * k / 4
            p.drawLine(QPointF(left, y), QPointF(self.width() - 8, y))
            p.setPen(QColor(t.muted))
            p.drawText(QRectF(0, y - 8, left - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       _fmt(peak * k / 4))
            p.setPen(QPen(QColor(t.border), 1))
        for i, (label, v) in enumerate(self.bins):
            x = left + i * slot + (slot - bar_w) / 2
            h = plot_h * v / peak
            if h > 0:
                colour = QColor(t.gold if i in self.marked else t.lapis)
                r = min(4.0, bar_w / 2, h / 2)
                # square at the baseline, rounded at the data end: a body and a rounded cap
                p.fillRect(QRectF(x, base_y - h + r, bar_w, h - r), colour)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(colour)
                p.drawRoundedRect(QRectF(x, base_y - h, bar_w, 2 * r), r, r)
            if i % self.label_every == 0:
                p.setPen(QColor(t.muted))
                p.drawText(QRectF(x - slot, base_y + 4, bar_w + 2 * slot, bottom - 4),
                           Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)
        p.end()

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        left, bottom, top, plot_h, peak, slot, bar_w = self._geometry()
        i = int((e.position().x() - left) // slot) if slot else -1
        if 0 <= i < len(self.bins):
            label, v = self.bins[i]
            QToolTip.showText(e.globalPosition().toPoint(), f"{label}: {_fmt(v)}{self.unit}", self)
        else:
            QToolTip.hideText()


class Lorenz(QWidget):
    """The Lorenz curve of a share: the bottom x% of narrators carry y% of the links. The diagonal is equal shares;
    the further the curve sags below it, the more the transmission rests on a few."""

    def __init__(self, curve: list[list[float]], parent=None) -> None:
        super().__init__(parent)
        self.curve = curve
        self.setMouseTracking(True)
        self.setFixedHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _xy(self, x: float, y: float) -> QPointF:
        w, h = max(60, self.width() - 70), self.height() - 34
        return QPointF(46 + x * w, 8 + (1 - y) * h)

    def paintEvent(self, _e) -> None:  # noqa: N802
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(t.border), 1))
        for k in range(5):
            a, b = self._xy(0, k / 4), self._xy(1, k / 4)
            p.drawLine(a, b)
            p.setPen(QColor(t.muted))
            p.drawText(QRectF(0, a.y() - 8, 40, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{25 * k}%")
            q = self._xy(k / 4, 0)
            p.drawText(QRectF(q.x() - 20, q.y() + 4, 40, 16), Qt.AlignmentFlag.AlignHCenter, f"{25 * k}%")
            p.setPen(QPen(QColor(t.border), 1))
        p.setPen(QPen(QColor(t.muted), 1))
        p.drawLine(self._xy(0, 0), self._xy(1, 1))
        if self.curve:
            path = QPainterPath(self._xy(*self.curve[0]))
            for x, y in self.curve[1:]:
                path.lineTo(self._xy(x, y))
            p.setPen(QPen(QColor(t.lapis), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)
        p.end()

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if not self.curve:
            return
        w = max(60, self.width() - 70)
        x = (e.position().x() - 46) / w
        if 0 <= x <= 1:
            point = min(self.curve, key=lambda c: abs(c[0] - x))
            QToolTip.showText(e.globalPosition().toPoint(),
                              f"The {100 * point[0]:.0f}% of narrators who carry least carry {100 * point[1]:.1f}% of the "
                              f"links;\nthe other {100 - 100 * point[0]:.0f}% carry {100 - 100 * point[1]:.1f}%.", self)


class PeopleBars(QWidget):
    """People ranked by a count: the name (in the interface language), a dot in the colour of his rank, a bar, the
    count. A click opens the person. rows: [{"label", "tip", "value", "dot", "id"}]."""

    clicked = Signal(int)

    def __init__(self, rows: list[dict], unit: str = "", label_w: int = 230, parent=None) -> None:
        super().__init__(parent)
        self.rows, self.unit, self.label_w = rows, unit, label_w
        self.row_h = 28
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self.row_h * len(rows) + 4)

    def paintEvent(self, _e) -> None:  # noqa: N802
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        peak = max((r["value"] for r in self.rows), default=0) or 1
        width = max(40, self.width() - self.label_w - 70)
        fm = p.fontMetrics()
        for i, r in enumerate(self.rows):
            y = i * self.row_h
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(r.get("dot") or t.muted))
            p.drawEllipse(QPointF(7, y + self.row_h / 2), 4, 4)
            p.setPen(QColor(t.ink))
            label = fm.elidedText(r["label"], Qt.TextElideMode.ElideRight, self.label_w - 26)
            p.drawText(QRectF(18, y, self.label_w - 22, self.row_h), Qt.AlignmentFlag.AlignVCenter, label)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t.lapis_soft))
            p.drawRoundedRect(QRectF(self.label_w, y + 8, width, self.row_h - 16), 3, 3)
            w = max(4.0, width * r["value"] / peak)
            p.fillRect(QRectF(self.label_w, y + 8, w - 3, self.row_h - 16), QColor(t.lapis))
            p.setBrush(QColor(t.lapis))
            p.drawRoundedRect(QRectF(self.label_w + w - 6, y + 8, 6, self.row_h - 16), 3, 3)
            p.setPen(QColor(t.muted))
            p.drawText(QRectF(self.label_w + width + 8, y, 62, self.row_h), Qt.AlignmentFlag.AlignVCenter,
                       f"{_fmt(r['value'])}{self.unit}")
        p.end()

    def _row_at(self, y: float) -> int:
        i = int(y // self.row_h)
        return i if 0 <= i < len(self.rows) else -1

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        i = self._row_at(e.position().y())
        if i >= 0:
            QToolTip.showText(e.globalPosition().toPoint(), self.rows[i].get("tip") or self.rows[i]["label"], self)

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        i = self._row_at(e.position().y())
        if i >= 0 and self.rows[i].get("id") and e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.rows[i]["id"])
