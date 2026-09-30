"""Widgets that draw a chain of transmission.

ChainStrip   compact, right-to-left row of names for result cards
ChainNode    one narrator in the vertical timeline of the Isnad Chains page

All data comes from isnady.core.isnad; nothing here decides anything.
"""

import html

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
    chip.setFont(theme.script_font("arabic", factor=0.625))
    if tip:
        chip.setToolTip(tip)
    return chip


def _arrow(tip: str = "") -> QLabel:
    arrow = _chip("←", "ChainArrow", tip)
    arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return arrow


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


def person_summary(person: dict | None) -> str:
    """One line about an identified narrator: Ibn Hajar's verdict, rank, tabaqa and death."""
    if not person:
        return ""
    parts = []
    v = person["verdicts"][0] if person.get("verdicts") else None
    if v:
        parts.append(f"Ibn Hajar: {v['phrase']}" + (f" (rank {v['rank']} of 12)" if v["rank"] else ""))
    if person.get("tabaqa"):
        parts.append(f"tabaqa {person['tabaqa']}")
    if person.get("death_year_ah"):
        parts.append(f"d. {person['death_year_ah']} AH")
    return " · ".join(parts)


class ChainStrip(QWidget):
    """Narrator names in reading order (right to left), ending at the Prophet when the chain does.
    Identified narrators are filled chips; names not yet identified have a dashed outline."""

    def __init__(self, chain: dict, people: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        people = people or {}
        flow = FlowLayout(self, spacing=4, rtl=True)
        for i, link in enumerate(chain["links"]):
            arabic, meaning, _why = core_isnad.term_label(link["transmission"])
            if i:
                flow.addWidget(_arrow(f"{arabic}: {meaning}"))
            person = people.get(link.get("person_id"))
            if not person and link.get("candidates") is None:
                # no rijal work imported (or not matched yet): a plain chip, not a "not identified" one
                flow.addWidget(_chip(core_isnad.short_name(link["raw_name"]), "ChainChip",
                                     f"{link['raw_name']}\n{arabic}: {meaning}"))
                continue
            if person:
                tip = f"{person['display_name']}\n{person_summary(person)}\n{arabic}: {meaning}"
                flow.addWidget(_chip(core_isnad.short_name(link["raw_name"]), "ChainChip", tip))
            else:
                n = link.get("candidates")
                why = ("not identified yet" if n is None else
                       f"not identified: {n} narrators could have this name" if n else
                       "not identified: no narrator of this name in the rijal work")
                flow.addWidget(_chip(core_isnad.short_name(link["raw_name"]), "ChainChipUnknown",
                                     f"{link['raw_name']}\n{why}\n{arabic}: {meaning}"))
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
                 last: bool = False, prophet: bool = False, full_name: str = "", latin: bool = False,
                 person: dict | None = None, candidates: int | None = None) -> None:
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
        if latin:
            name.setFont(theme.reading_font(17, bold=True, scaled=True))
        else:
            name.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                               f"{theme.font_css(theme.script_font('arabic', bold=prophet, factor=0.9))}")
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
        if person:
            who = QLabel(_shorten(person["display_name"], 90))
            who.setObjectName("NodeFacts")
            who.setWordWrap(True)
            who.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
            who.setToolTip(person["name_ar"] + (("\n" + "، ".join(person["other_names"][:8])) if person.get("other_names") else ""))
            who.setStyleSheet(f"color: {theme.current().muted}; "
                              f"{theme.font_css(theme.script_font('arabic', factor=0.62))}")
            box.addWidget(who)
            v = person["verdicts"][0] if person.get("verdicts") else None
            if v:
                dot = theme.rank_color(v["rank"])
                rank_text = (f"&nbsp;&nbsp;<span style='color:{dot}'>●</span> rank {v['rank']} of 12: "
                             f"{html.escape(v['rank_label'])}") if v["rank"] else ""
                arabic = theme.script_font("arabic", factor=0.68)
                verdict = QLabel(f"Ibn Hajar: <span style='font-family:\"{arabic.family()}\"; "
                                 f"font-size:{arabic.pointSizeF():.1f}pt'>{html.escape(_shorten(v['phrase'], 70))}</span>"
                                 f"{rank_text}")
                verdict.setObjectName("NodeVerdict")
                verdict.setTextFormat(Qt.TextFormat.RichText)
                verdict.setWordWrap(True)
                verdict.setToolTip(f"{v['critic_name']}, {v['work']}:\n{v['phrase']}")
                box.addWidget(verdict)
            facts = []
            if person.get("tabaqa"):
                facts.append(f"tabaqa {person['tabaqa']}: {person['tabaqa_label']}")
            if person.get("death_year_ah"):
                facts.append(f"died {person['death_year_ah']} AH")
            elif person.get("death_year_note"):
                facts.append(person["death_year_note"])
            if facts:
                line = QLabel(" · ".join(facts))
                line.setObjectName("NodeFacts")
                line.setWordWrap(True)
                box.addWidget(line)
        elif candidates is not None and not prophet and not latin:
            text = (f"Not identified yet: {candidates} narrators in the rijal work could have this name"
                    if candidates else "Not identified: no narrator of this name in the rijal work")
            unknown = QLabel(text)
            unknown.setObjectName("NodeUnknown")
            unknown.setWordWrap(True)
            box.addWidget(unknown)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        holder = QWidget()
        holder_box = QVBoxLayout(holder)
        holder_box.setContentsMargins(0, 0, 4, 8)      # the gap to the next node, inside the row
        holder_box.addWidget(card)
        row.addWidget(holder, 1)
