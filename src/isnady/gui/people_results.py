"""Search → Narrators and Search → Scholars: one card per person found.

Each card is the person in brief — the name he is known by (reading and Arabic), his full name, his standing in
words with the Arabic term in the tooltip, his generation (tabaqa) and how often he is in the imported chains —
and the whole card opens him on his own page (Narrators, Shia Rijal or Hadith Scholars)."""

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from isnady.core import shia_rijal
from isnady.core.rijal import RANK_LABELS, TABAQA_LABELS
from isnady.core.scholars import ROLE_HELP
from isnady.gui import theme

CLOSE_TIP = ("Found by a close spelling, not by the letters typed: a letter typed twice or missing, or one that "
             "Turkish and English write differently (h and kh, z and dh).")
SHIA_COLOR = {1: 2, 2: 4, 3: 5, 4: 9}    # as on the Narrators page: Shia categories in the colours of like standing
TRADITION = {"sunni": ("Sunni", "A narrator of the Sunni books, as Ibn Hajar's Taqrib al-Tahdhib records him."),
             "shia": ("Shia", "A narrator of the Shia books, as al-Najashi's Rijal records him. His judgment is "
                              "given in its own terms, not mapped to Ibn Hajar's ranks.")}


def _label(text: str, name: str = "", rich: bool = False, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
    label.setWordWrap(wrap)
    return label


def _arabic(text: str, factor: float, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignAbsolute)
    label.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                        f"{theme.font_css(theme.script_font('arabic', bold=bold, factor=factor))}")
    return label


class _ClickCard(QFrame):
    """A card that opens something when clicked anywhere (text stays readable, not selectable)."""

    def __init__(self, on_click, tip: str) -> None:
        super().__init__()
        self.setObjectName("PersonCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tip)
        self._on_click = on_click

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt name)
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self._on_click()
        super().mouseReleaseEvent(event)


def _head(box: QVBoxLayout, reading: str, arabic: str, sub: str) -> None:
    """[reading                Arabic]  then the full name, muted, when it says more."""
    t = theme.current()
    top = QHBoxLayout()
    top.setSpacing(16)
    if reading:
        title = _label(reading)
        title.setFont(theme.reading_font(16, bold=True, scaled=True))
        title.setStyleSheet(f"color: {t.ink};")
        top.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)
    top.addWidget(_arabic(arabic, 1.05, bold=True), 0 if reading else 1, Qt.AlignmentFlag.AlignVCenter)
    box.addLayout(top)
    if sub:
        line = _label(sub, "Lead", wrap=True)
        line.setStyleSheet(f"color: {t.muted};")
        box.addWidget(line)


def _facts(box: QVBoxLayout, tags: list[tuple[str, str]], parts: list[tuple[str, str]], action: str) -> None:
    """One line: tags (tradition, roles), then facts, each with its explanation on hover; the page it opens."""
    t = theme.current()
    row = QHBoxLayout()
    row.setSpacing(14)
    for text, tip in tags:
        tag = _label(text, "Tag")
        tag.setToolTip(tip)
        row.addWidget(tag)
    for text, tip in parts:
        fact = _label(text, "Caption", rich=True)
        fact.setStyleSheet(f"color: {t.muted}; font-size: 9pt;")
        if tip:
            fact.setToolTip(tip)
        row.addWidget(fact)
    row.addStretch(1)
    go = _label(f"{action} →")
    go.setStyleSheet(f"color: {t.lapis}; font-weight: 600;")
    row.addWidget(go)
    box.addLayout(row)


def person_card(row: dict, open_person) -> QFrame:
    """A narrator found by Search, from either tradition (core.narrators.find)."""
    shia = row["tradition"] == "shia"
    page = "Shia Rijal" if shia else "Narrators"
    card = _ClickCard(lambda: open_person(row["id"], row["tradition"]), f"Open {row['name']} on the {page} page")
    box = QVBoxLayout(card)
    box.setContentsMargins(22, 14, 22, 12)
    box.setSpacing(4)
    view = row["view"]
    known = view["reading"] or view["full_reading"]
    full = view["full_reading"] if view["full_reading"] and view["full_reading"] != known else ""
    _head(box, known, view["arabic"] or row["name"], full)

    tag, why = TRADITION[row["tradition"]]
    tags = [(tag, f"{why}\nSource: {row['source']}" if row.get("source") else why)]
    parts = []
    rank = row["rank"]
    if shia:
        if rank:
            ar, en, meaning = shia_rijal.RANKS[rank]
            dot = theme.rank_color(SHIA_COLOR.get(rank))
            parts.append((f"<span style='color:{dot}'>●</span> {html.escape(en.split(' (')[0])}",
                          f"{ar} — {en}\n{meaning}"))
        else:
            parts.append(("no judgment", "al-Najashi names him without judging him."))
        if row.get("madhhab"):
            parts.append((html.escape(shia_rijal.MADHHAB_LABELS.get(row["madhhab"], row["madhhab"])),
                          "His school, as the critic gives it."))
    elif rank:
        ar, en = RANK_LABELS[rank]
        parts.append((f"<span style='color:{theme.rank_color(rank)}'>●</span> {html.escape(en.split(' (')[0])}",
                      f"Ibn Hajar's rank {rank} of 12: {ar} — {en}" + (f"\nHis words: {row['verdict']}"
                                                                         if row.get("verdict") else "")))
    if row["tabaqa"]:
        parts.append((f"tabaqa {row['tabaqa']}",
                      f"Generation (tabaqa) {row['tabaqa']} of 12 in Ibn Hajar's count: "
                      f"{TABAQA_LABELS.get(row['tabaqa'], '')}"))
    if row["death"]:
        parts.append((f"d. {row['death']} AH", "Year of death in the Hijri calendar, as the source gives it."))
    if not shia:
        parts.append((f"{row['in_chains']:,} in chains" if row["in_chains"] else "not in the imported chains",
                      "How often he is identified in the chains of the imported books."))
    if row.get("close"):
        parts.append((f"<span style='color:{theme.current().gold}'>≈ close spelling</span>", CLOSE_TIP))
    _facts(box, tags, parts, f"Open in {page}")
    return card


def scholar_card(scholar: dict, open_scholar) -> QFrame:
    """A scholar found by Search (core.scholars.search): who he is and what of his work is in this database."""
    from isnady.core import scholars as core_scholars

    card = _ClickCard(lambda: open_scholar(scholar["id"]), f"Open {scholar['name']} on the Hadith Scholars page")
    box = QVBoxLayout(card)
    box.setContentsMargins(22, 14, 22, 12)
    box.setSpacing(4)
    view = core_scholars.name_view(scholar)
    sub = " · ".join(x for x in (scholar["full"] if scholar["full"] != scholar["name"] else "", scholar["tr"],
                                 scholar["dates"]) if x)
    _head(box, scholar["name"], scholar.get("known_ar") or view["arabic"], sub)
    works = _label("Works: " + ", ".join(scholar["works"]), "Caption", wrap=True)
    box.addWidget(works)
    tags, parts = [], []
    for role in scholar["roles"]:
        title, meaning = ROLE_HELP[role]
        tags.append((title.split(" (")[0].split(" · ")[0], f"{title}\n{meaning}"))
    if not tags:
        parts.append(("nothing of his is imported yet",
                      "Import his book or his grades (File → Data Sources) to see his work measured."))
    if scholar.get("close"):
        parts.append((f"<span style='color:{theme.current().gold}'>≈ close spelling</span>", CLOSE_TIP))
    _facts(box, tags, parts, "Open in Hadith Scholars")
    return card


def empty_hint(kind: str) -> QWidget:
    """Under "Nothing found": how names are matched, so the reader knows what to try."""
    text = {"narrators": "Names are matched by their letters, without vowels or diacritics: “Abu Hurayra”, "
                         "“Ebû Hüreyre” and أبو هريرة all find him. Try fewer words, or the name he is known by.",
            "scholars": "Try his best-known name (al-Bukhari, Buhârî, البخاري) or the title of one of his works."}
    return _label(text.get(kind, ""), "Lead", wrap=True)
