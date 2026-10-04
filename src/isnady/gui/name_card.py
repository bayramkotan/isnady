"""The name card (NM1): a person shown by the name he is known by, with every part of his name laid out — one
clean design for narrators (both traditions) and scholars. Built from core.name_parts.present()."""

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from isnady.core.name_parts import PART_LABELS
from isnady.gui import theme

EXPLAIN = ("An Arabic name is made of parts: the <b>name</b> (ism), the <b>lineage</b> (nasab — b. means son of), "
           "the <b>kunya</b> (Abu … , father of …), a <b>by-name</b> (laqab) and <b>nisbas</b> telling where a man "
           "was from, his tribe or his trade. A narrator is usually known by one of them — marked ★.")


def _arabic(text: str, factor: float, bold: bool = False, color: str | None = None) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignAbsolute)
    label.setStyleSheet(f"color: {color or theme.script_color('arabic')}; "
                        f"{theme.font_css(theme.script_font('arabic', bold=bold, factor=factor))}")
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


class NameCard(QFrame):
    """[known-as: Arabic | reading]  [full name · known by …]  [ the parts, one per row ]  [what the parts mean]"""

    def __init__(self, view: dict, extra: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        t = theme.current()
        box = QVBoxLayout(self)
        box.setContentsMargins(24, 18, 24, 16)
        box.setSpacing(4)

        # the name he is known by: reading on the left, Arabic on the right
        top = QHBoxLayout()
        reading = QLabel(view["reading"] or view["full_reading"] or "")      # plain text: no HTML escaping
        reading.setTextFormat(Qt.TextFormat.PlainText)
        reading.setFont(theme.reading_font(26, bold=True))
        reading.setStyleSheet(f"color: {t.ink};")
        reading.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        top.addWidget(reading, 1, Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(_arabic(view["arabic"], 1.25, bold=True), 0, Qt.AlignmentFlag.AlignVCenter)
        box.addLayout(top)

        sub = []
        if view["full_reading"] and view["full_reading"] != view["reading"]:
            sub.append(html.escape(view["full_reading"]))
        if view["how"]:
            sub.append(f"<span style='color:{t.gold}'>★</span> known by {html.escape(view['how'])}")
        if extra:
            sub.append(extra)
        if sub:
            line = QLabel(" &nbsp;·&nbsp; ".join(sub))
            line.setObjectName("Lead")
            line.setTextFormat(Qt.TextFormat.RichText)
            line.setWordWrap(True)
            box.addWidget(line)

        if view["rows"]:
            rule = QFrame()
            rule.setFixedHeight(1)
            rule.setStyleSheet(f"background: {t.border};")
            box.addSpacing(8)
            box.addWidget(rule)
            box.addSpacing(6)
            grid = QGridLayout()
            grid.setHorizontalSpacing(18)
            grid.setVerticalSpacing(7)
            grid.setColumnStretch(1, 1)
            for row, (key, values, star) in enumerate(view["rows"]):
                title, term, arabic_term, meaning = PART_LABELS[key]
                head = QLabel(f"<span style='color:{t.gold}'>{'★' if star else '&nbsp;&nbsp;'}</span> <b>{title}</b>"
                              + (f"<br><span style='color:{t.muted}; font-size:small'>{term} · {arabic_term}</span>"
                                 if term else ""))
                head.setTextFormat(Qt.TextFormat.RichText)
                head.setToolTip(meaning)
                head.setMinimumWidth(130)
                readings = QLabel(" &nbsp;·&nbsp; ".join(html.escape(r) if r else "<span style='color:gray'>—</span>"
                                                         for _a, r in values))
                readings.setTextFormat(Qt.TextFormat.RichText)
                readings.setWordWrap(True)
                readings.setStyleSheet(f"color: {t.ink};" + ("font-weight: 600;" if star else ""))
                readings.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                grid.addWidget(head, row, 0, Qt.AlignmentFlag.AlignTop)
                grid.addWidget(readings, row, 1, Qt.AlignmentFlag.AlignVCenter)
                grid.addWidget(_arabic("  ·  ".join(a for a, _r in values), 0.72), row, 2, Qt.AlignmentFlag.AlignVCenter)
            box.addLayout(grid)
            note = QLabel(EXPLAIN)
            note.setObjectName("Caption")
            note.setTextFormat(Qt.TextFormat.RichText)
            note.setWordWrap(True)
            box.addSpacing(6)
            box.addWidget(note)
