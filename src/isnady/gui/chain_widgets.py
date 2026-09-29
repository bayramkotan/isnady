"""Widgets that draw a chain of transmission.

ChainStrip   compact, right-to-left row of names for result cards
ChainNode    one narrator in the vertical timeline of the Isnad Chains page

All data comes from isnady.core.isnad; nothing here decides anything.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from isnady.core import isnad as core_isnad
from isnady.gui import theme
from isnady.gui.widgets import FlowLayout, expanding_width_policy

PROPHET = "النبي ﷺ"


def _chip(text: str, name: str, tip: str = "") -> QLabel:
    chip = QLabel(text)
    chip.setObjectName(name)
    chip.setFont(theme.reading_font(12.5, scaled=True))
    if tip:
        chip.setToolTip(tip)
    return chip


def _arrow(tip: str = "") -> QLabel:
    arrow = _chip("←", "ChainArrow", tip)
    arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return arrow


class ChainStrip(QWidget):
    """Narrator names in reading order (right to left), ending at the Prophet when the chain does."""

    def __init__(self, chain: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        flow = FlowLayout(self, spacing=4, rtl=True)
        for i, link in enumerate(chain["links"]):
            arabic, meaning, _why = core_isnad.term_label(link["transmission"])
            if i:
                flow.addWidget(_arrow(f"{arabic}: {meaning}"))
            flow.addWidget(_chip(core_isnad.short_name(link["raw_name"]), "ChainChip",
                                 f"{link['raw_name']}\n{arabic}: {meaning}"))
        if chain["reaches_prophet"]:
            flow.addWidget(_arrow())
            flow.addWidget(_chip(PROPHET, "ChainChipProphet", "The chain reaches the Prophet (marfu')"))
        self.setSizePolicy(expanding_width_policy())

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self.layout().heightForWidth(width)


class _Gutter(QWidget):
    """Timeline gutter: a line through the column and a dot for this node."""

    def __init__(self, first: bool, last: bool, prophet: bool) -> None:
        super().__init__()
        self._first, self._last, self._prophet = first, last, prophet
        self.setFixedWidth(34)

    def paintEvent(self, _event) -> None:  # noqa: N802
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = self.width() / 2
        dot_y = 26.0
        p.setPen(QPen(QColor(t.border), 2))
        if not self._first:
            p.drawLine(QPointF(x, 0), QPointF(x, dot_y))
        if not self._last:
            p.drawLine(QPointF(x, dot_y), QPointF(x, self.height()))
        radius = 8.0 if self._prophet else 6.0
        p.setPen(QPen(QColor(t.gold if self._prophet else t.lapis), 2))
        p.setBrush(QColor(t.gold if self._prophet else t.surface))
        p.drawEllipse(QRectF(x - radius, dot_y - radius, radius * 2, radius * 2))
        p.end()


class ChainNode(QWidget):
    """One step of the vertical chain: the term that links it to the previous step, then the name."""

    def __init__(self, title: str, subtitle: str = "", term: str | None = None, *, first: bool = False,
                 last: bool = False, prophet: bool = False, full_name: str = "", latin: bool = False) -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(_Gutter(first, last, prophet))

        card = QFrame()
        card.setObjectName("NodeProphet" if prophet else "Node")
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 7, 16, 8)
        box.setSpacing(2)
        if term:
            arabic, meaning, why = core_isnad.term_label(term)
            term_label = QLabel(f"<span style='font-family:\"{theme.READING_FAMILY}\"'>{arabic}</span>"
                                f"&nbsp;&nbsp;{meaning}")
            term_label.setObjectName("NodeTerm")
            term_label.setTextFormat(Qt.TextFormat.RichText)
            term_label.setToolTip(f"{arabic}: {meaning}\n{why}")
            box.addWidget(term_label)
        name = QLabel(title)
        name.setObjectName("NodeName")
        name.setFont(theme.reading_font(17 if latin else 18, bold=prophet or latin, scaled=True))
        side = Qt.AlignmentFlag.AlignLeft if latin else Qt.AlignmentFlag.AlignRight
        name.setAlignment(side | Qt.AlignmentFlag.AlignAbsolute | Qt.AlignmentFlag.AlignVCenter)
        name.setWordWrap(True)
        name.setSizePolicy(expanding_width_policy())
        name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if full_name and full_name != title:
            name.setToolTip(full_name)
        box.addWidget(name)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("Caption")
            sub.setWordWrap(True)
            box.addWidget(sub)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        holder = QWidget()
        holder_box = QVBoxLayout(holder)
        holder_box.setContentsMargins(0, 0, 4, 8)      # the gap to the next node, inside the row
        holder_box.addWidget(card)
        row.addWidget(holder, 1)
