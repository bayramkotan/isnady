"""The card of a life (BIO2): on the Narrators and Hadith Scholars pages.

A written life (core.lives, assets/lives): its kind, the facts at a glance (full name, birth, death, family, …),
the life told in a few paragraphs, the works it is summarised from. Every other narrator: the same card, filled from
what the rijal work and the imported chains say of him.
"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from isnady.core.i18n import tr
from isnady.gui import theme


def _label(text: str, name: str = "", rich: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def life_card(life: dict, written: bool) -> QFrame:
    """life: core.lives.view() or core.lives.read(); written: a life written for isnady."""
    t = theme.current()
    card = QFrame()
    card.setObjectName("Card")
    box = QVBoxLayout(card)
    box.setContentsMargins(20, 14, 20, 16)
    box.setSpacing(10)

    head = QHBoxLayout()
    title = QLabel(tr("Life"))
    title.setObjectName("CardTitle")
    title.setFont(theme.reading_font(14, bold=True))
    head.addWidget(title)
    if written and life.get("title"):
        name = QLabel(life["title"])
        name.setFont(theme.reading_font(14))
        name.setStyleSheet(f"color: {t.muted};")
        head.addWidget(name)
    if life.get("kind"):
        kind = QLabel(life["kind"])
        kind.setObjectName("TagGold" if life.get("road") == "shia" or written else "TagMuted")
        head.addWidget(kind)
    head.addStretch(1)
    box.addLayout(head)

    if life.get("facts"):
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        for row, (label, value) in enumerate(life["facts"]):
            key = QLabel(label)
            key.setStyleSheet(f"color: {t.gold}; font-weight: 600;")
            key.setAlignment(Qt.AlignmentFlag.AlignTop)
            grid.addWidget(key, row, 0, Qt.AlignmentFlag.AlignTop)
            text = _label(value)
            grid.addWidget(text, row, 1)
        grid.setColumnStretch(1, 1)
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background: {t.lapis_soft}; border-radius: 8px; }}"
                            f" QLabel {{ background: transparent; }}")
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(14, 10, 14, 10)
        inner.addLayout(grid)
        box.addWidget(frame)

    font = theme.reading_font(12.5)
    for paragraph in life.get("paragraphs", []):
        text = _label(paragraph)
        text.setFont(font)
        text.setStyleSheet(f"color: {t.ink}; line-height: 140%;")
        box.addWidget(text)

    if life.get("sources"):
        sources = _label("<b>" + html.escape(tr("Sources")) + ":</b> " + " · ".join(html.escape(s) for s in life["sources"]),
                         "Caption", rich=True)
        box.addWidget(sources)
    return card
