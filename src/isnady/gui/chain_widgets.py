"""Widgets that draw a chain of transmission.

ChainStrip   compact, right-to-left row of names for result cards
ChainNode    one narrator in the vertical timeline of the Isnad Chains page

All data comes from isnady.core.isnad; nothing here decides anything.
"""

import html

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from isnady.core import i18n
from isnady.core import isnad as core_isnad
from isnady.core.i18n import tr
from isnady.gui import theme
from isnady.gui.widgets import FlowLayout, expanding_width_policy

PROPHET = "النبي ﷺ"


def end_chip(chain: dict) -> str:
    """The short Arabic name of whom a chain reaches: the Prophet ﷺ, or on road B one of the Imams."""
    from isnady.core import traditions

    key = chain.get("ends_with") or "prophet"
    if key == "prophet":
        return PROPHET
    m = traditions.MASUM.get(key)
    return m.name_ar if m else "الإمام عليه السلام"


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


SHIA_COLOR = {1: 2, 2: 4, 3: 5, 4: 9}   # the Shia categories drawn in the rank colours of like standing


def _critic(v: dict) -> str:
    """The critic by the name isnady gives him (NM2): "Ibn Hajar", "al-Najashi" …"""
    if v.get("rank_scheme") == "shia":
        return tr(v.get("critic_name") or "al-Najashi")
    return tr("Ibn Hajar") if "حجر" in (v.get("critic_name") or "") or not v.get("critic_name") else v["critic_name"]


def person_summary(person: dict | None) -> str:
    """One line about an identified narrator: his critic's verdict (Ibn Hajar's rank, or the Imami terms of a
    Shia critic), tabaqa and death."""
    if not person:
        return ""
    parts = []
    v = person["verdicts"][0] if person.get("verdicts") else None
    if v:
        if v.get("rank_scheme") == "shia":
            parts.append(f"{_critic(v)}: {v['phrase'][:80]}" + (f" ({v['rank_label']})" if v["rank"] else ""))
        else:
            parts.append(f"{tr('Ibn Hajar')}: {v['phrase']}"
                         + (" (" + tr("rank {rank} of 12", rank=v["rank"]) + ")" if v["rank"] else ""))
    if person.get("tabaqa"):
        parts.append(tr("tabaqa {tabaqa}", tabaqa=person["tabaqa"]))
    if person.get("death_year_ah"):
        parts.append(tr("d. {year} AH", year=person["death_year_ah"]))
    return " · ".join(parts)


def stop_note(chain: dict) -> str:
    """Why a chain drawn as far as it was read stops there (a tooltip, never a box)."""
    return tr("The chain is read as far as here; the rest is in the text. ({reason})", reason=tr(chain["problem"]))


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
                why = core_isnad.link_note(link["raw_name"]) or (tr("not identified yet") if n is None else
                       tr("not identified: {n} narrators could have this name", n=n) if n else
                       tr("not identified: no narrator of this name in the rijal work"))
                flow.addWidget(_chip(core_isnad.short_name(link["raw_name"]), "ChainChipUnknown",
                                     f"{link['raw_name']}\n{why}\n{arabic}: {meaning}"))
        if chain.get("problem") and not (chain["reaches_prophet"] or chain.get("ends_with")):
            # read as far as here: the rest of the chain runs on in the text (shown below the chain)
            flow.addWidget(_arrow())
            flow.addWidget(_chip("…", "ChainChipUnknown", stop_note(chain)))
        if chain["reaches_prophet"] or chain.get("ends_with"):
            flow.addWidget(_arrow())
            flow.addWidget(_chip(end_chip(chain), "ChainChipProphet",
                                 tr("The chain reaches {whom}", whom=core_isnad.end_label(chain))))
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


def identified_how(confidence: float | None) -> str:
    """How a narrator of a chain was identified, from the matcher's confidence (core.narrators)."""
    if confidence is None:
        return ""
    if confidence >= 1.0:
        return tr("Identified by his name as the rijal work gives it.")
    if confidence >= 0.8:
        return tr("Identified by his name and the chain around him (his patron, the bare name's teacher or student).")
    if confidence >= 0.6:
        return tr("Identified by the narrators around him: this teacher and student are seen with him in the chains "
                  "that name him in full.")
    return tr("Taken as the famous narrator of this name: nothing else decided between those who bear it.")


class ChainNode(QWidget):
    """One step of the vertical chain: the term that links it to the previous step, then the name."""

    def __init__(self, title: str, subtitle: str = "", term: str | None = None, *, first: bool = False,
                 last: bool = False, prophet: bool = False, full_name: str = "", latin: bool = False,
                 person: dict | None = None, candidates: int | None = None, on_person=None, note: str = "",
                 confidence: float | None = None) -> None:
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
        reading = None
        if not latin and not prophet and not i18n.rtl():
            # the name in Latin letters beside the Arabic, as it is written in the chain (Bayram, 2026-10-11:
            # the space on the left stood empty)
            text, spelled = core_isnad.name_reading(full_name or title, i18n.language())
            if text:
                reading = QLabel(html.escape(text) + (" <span style='color:%s'>≈</span>" % theme.current().muted
                                                      if spelled else ""))
                reading.setObjectName("NodeReading")
                reading.setTextFormat(Qt.TextFormat.RichText)
                reading.setFont(theme.reading_font(16, bold=True, scaled=True))
                reading.setWordWrap(True)
                reading.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute
                                     | Qt.AlignmentFlag.AlignVCenter)
                reading.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                reading.setToolTip(tr("The name as it is written in the chain, in Latin letters.")
                                   + ("\n" + tr("≈ a word not in isnady's list of names was spelled letter by "
                                                 "letter: its short vowels are a guess.") if spelled else ""))
        if reading is not None:
            line = QHBoxLayout()
            line.setSpacing(16)
            line.addWidget(reading, 1)
            line.addWidget(name, 1)
            box.addLayout(line)
        else:
            box.addWidget(name)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("Caption")
            sub.setWordWrap(True)
            box.addWidget(sub)
        if person:
            who = QLabel(_shorten(person["display_name"], 90))
            if on_person is not None:
                who.setCursor(Qt.CursorShape.PointingHandCursor)
                who.mousePressEvent = lambda _e, pid=person["id"]: on_person(pid)
            who.setObjectName("NodeFacts")
            who.setWordWrap(True)
            who.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
            how = identified_how(confidence)
            who.setToolTip(person["name_ar"] + (("\n" + "، ".join(person["other_names"][:8])) if person.get("other_names") else "")
                           + (f"\n\n{how}" if how else "")
                           + (tr("\n\nClick to open this narrator.") if on_person is not None else ""))
            who.setStyleSheet(f"color: {theme.current().muted}; "
                              f"{theme.font_css(theme.script_font('arabic', factor=0.62))}")
            box.addWidget(who)
            from isnady.core.names import latin

            view = person.get("name_view") or {}
            reading = view.get("reading") or latin(person["display_name"], "en")
            if reading:
                roman = QLabel(f"<b>{reading}</b>" + (f" &nbsp;·&nbsp; {view['full_reading']}"
                                                      if view.get("full_reading") and view["full_reading"] != reading else ""))
                roman.setObjectName("NodeFacts")
                roman.setTextFormat(Qt.TextFormat.RichText)
                roman.setToolTip(tr("known by {how}", how=view['how']) if view.get("how") else "")
                box.addWidget(roman)
            v = person["verdicts"][0] if person.get("verdicts") else None
            if v:
                shia = v.get("rank_scheme") == "shia"
                if shia:                    # the Imami terms, never Ibn Hajar's twelve ranks (SK)
                    dot = theme.rank_color(SHIA_COLOR.get(v["rank"]))
                    rank_text = (f"&nbsp;&nbsp;<span style='color:{dot}'>●</span> {html.escape(v['rank_label'])}"
                                 if v["rank"] else "&nbsp;&nbsp;<i>" + tr("no judgment in these words") + "</i>")
                    if v.get("madhhab_label"):
                        rank_text += f" · {html.escape(v['madhhab_label'])}"
                else:
                    dot = theme.rank_color(v["rank"])
                    rank_text = (f"&nbsp;&nbsp;<span style='color:{dot}'>●</span> "
                                 + tr("rank {rank} of 12", rank=v["rank"]) + f": {html.escape(v['rank_label'])}"
                                 ) if v["rank"] else ""
                arabic = theme.script_font("arabic", factor=0.68)
                verdict = QLabel(f"{html.escape(_critic(v))}: <span style='font-family:\"{arabic.family()}\"; "
                                 f"font-size:{arabic.pointSizeF():.1f}pt'>{html.escape(_shorten(v['phrase'], 70))}</span>"
                                 f"{i18n.mark()}{rank_text}")
                verdict.setObjectName("NodeVerdict")
                verdict.setTextFormat(Qt.TextFormat.RichText)
                verdict.setWordWrap(True)
                verdict.setToolTip(f"{v['critic_name']}, {v['work']}:\n{v['phrase']}")
                box.addWidget(verdict)
            facts = []
            if person.get("tabaqa"):
                facts.append(tr("tabaqa {tabaqa}", tabaqa=person["tabaqa"]) + f": {person['tabaqa_label']}")
            if person.get("death_year_ah"):
                facts.append(tr("died {year} AH", year=person["death_year_ah"]))
            elif person.get("death_year_note"):
                facts.append(person["death_year_note"])
            if facts:
                line = QLabel(" · ".join(facts))
                line.setObjectName("NodeFacts")
                line.setWordWrap(True)
                box.addWidget(line)
        elif note and not prophet:
            unknown = QLabel(note)
            unknown.setObjectName("NodeUnknown")
            unknown.setWordWrap(True)
            box.addWidget(unknown)
        elif candidates is not None and not prophet and not latin:
            text = (tr("Not identified yet: {n} narrators in the rijal work could have this name", n=candidates)
                    if candidates else tr("Not identified: no narrator of this name in the rijal work"))
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
