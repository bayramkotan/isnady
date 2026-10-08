"""Hadith Scholars: the compilers, graders and critics present in the imported data, with what the data
measures of their work (isnady.core.scholars)."""

import html

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from isnady.core import scholars as core_scholars
from isnady.core.rijal import short_name
from isnady.gui import theme
from isnady.gui.name_card import NameCard

ROLE_TEXT = {"compiler": "compiler of a collection", "grader": "grades hadith", "critic": "judges narrators"}
HIGH_AGREEMENT = 0.95       # above this between two independent graders, the source data is suspected


def _label(text: str, name: str = "", wrap: bool = True, rich: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if rich:
        label.setTextFormat(Qt.TextFormat.RichText)
    return label


class Bar(QWidget):
    """One horizontal bar: label, a filled share, the number."""

    def __init__(self, label: str, value: int, maximum: int, color: str, suffix: str = "") -> None:
        super().__init__()
        self._label, self._value, self._max, self._color, self._suffix = label, value, max(1, maximum), color, suffix
        self.setMinimumHeight(26)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event) -> None:  # noqa: N802
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        label_w, num_w = 170, 90
        bar_w = max(10, self.width() - label_w - num_w)
        p.setPen(QColor(t.ink))
        if any("\u0600" <= ch <= "\u06ff" for ch in self._label):
            # an Arabic name: the reading font, right-aligned against the bar
            p.setFont(theme.script_font("arabic", factor=0.62))
            p.drawText(QRectF(0, 0, label_w - 10, self.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, self._label)
            p.setFont(self.font())
        else:
            p.drawText(QRectF(0, 0, label_w - 8, self.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       self._label)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.lapis_soft))
        p.drawRoundedRect(QRectF(label_w, 6, bar_w, self.height() - 12), 4, 4)
        p.setBrush(QColor(self._color))
        p.drawRoundedRect(QRectF(label_w, 6, bar_w * self._value / self._max, self.height() - 12), 4, 4)
        p.setPen(QColor(t.muted))
        p.drawText(QRectF(label_w + bar_w + 8, 0, num_w - 8, self.height()), Qt.AlignmentFlag.AlignVCenter,
                   f"{self._value:,}{self._suffix}")
        p.end()


GROUP_COLORS = {"sahih": 2, "hasan": 4, "da'if": 8, "very weak": 10, "fabricated": 12}   # rank colours reused


class ScholarsPage(QWidget):
    open_chain = Signal(int)
    open_narrator = Signal(int)

    def __init__(self, connection_getter, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._conn_of = connection_getter
        self._current: str | None = None

        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(400)
        lbox = QVBoxLayout(left)
        lbox.setContentsMargins(18, 16, 18, 14)
        lbox.setSpacing(8)
        title = _label("Hadith Scholars", "CardTitle")
        title.setFont(theme.reading_font(18, bold=True))
        self.note = _label("The scholars whose work is in the imported data, and what the data measures of it.", "Caption")
        self.list = QListWidget()
        self.list.setObjectName("NarratorList")
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(lambda item, _p: item and item.data(Qt.ItemDataRole.UserRole)
                                             and self.show_scholar(item.data(Qt.ItemDataRole.UserRole)))
        lbox.addWidget(title)
        lbox.addWidget(self.note)
        lbox.addWidget(self.list, 1)

        self.detail = QWidget()
        self.detail.setObjectName("Page")
        self.box = QVBoxLayout(self.detail)
        self.box.setContentsMargins(8, 4, 8, 16)
        self.box.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.detail)
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)
        root.addWidget(left)
        root.addWidget(scroll, 1)

    @property
    def conn(self):
        return self._conn_of()

    def refresh(self) -> None:
        conn = self.conn
        if conn is None:
            return
        people = core_scholars.present(conn)
        self.list.blockSignals(True)
        self.list.clear()
        for role in ("compiler", "grader", "critic"):
            group = [s for s in people if role in s["roles"]]
            if not group:
                continue
            title, _text = core_scholars.ROLE_HELP[role]
            head = QListWidgetItem()
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            head_label = _label(title, "FilterLabel", wrap=False)
            head_label.setContentsMargins(4, 12, 4, 2)
            head.setSizeHint(head_label.sizeHint())
            self.list.addItem(head)
            self.list.setItemWidget(head, head_label)
            for s in group:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, s["id"])
                item.setToolTip(f"{s['full']} — {s['arabic']}")
                row = QWidget()
                rbox = QVBoxLayout(row)
                rbox.setContentsMargins(10, 8, 10, 8)
                rbox.setSpacing(1)
                name = _label(s["name"], "RowTitle", wrap=False)
                name.setFont(theme.reading_font(15, bold=True))
                rbox.addWidget(name)
                rbox.addWidget(_label(s.get("tr", ""), "RowLatin", wrap=False))
                arabic = QLabel(s["arabic"])         # its own line: beside a long Turkish name it was clipped
                arabic.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
                arabic.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                                     f"{theme.font_css(theme.script_font('arabic', factor=0.6))}")
                rbox.addWidget(arabic)
                if s["dates"]:
                    rbox.addWidget(_label(s["dates"], "Caption", wrap=False))
                item.setSizeHint(row.sizeHint())
                self.list.addItem(item)
                self.list.setItemWidget(item, row)
        self.list.blockSignals(False)
        if not people:
            self._clear()
            card, box = self._card()
            box.addWidget(_label("No scholars yet: import a collection (File → Data Sources).", "Lead"))
            self.box.addStretch(1)
            return
        target = self._current if self._current and core_scholars.find(self._current) else people[0]["id"]
        self.select(target)

    def select(self, scholar_id: str) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == scholar_id:
                self.list.blockSignals(True)
                self.list.setCurrentRow(i)
                self.list.blockSignals(False)
        self.show_scholar(scholar_id)

    # ------------------------------------------------------------------ the right side
    def _clear(self) -> None:
        while self.box.count():
            item = self.box.takeAt(0)
            w = item.widget()                  # ask once: after setParent(None) the item no longer has it
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _card(self, title: str = "") -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(20, 14, 20, 14)
        box.setSpacing(6)
        if title:
            head = _label(title, "CardTitle")
            head.setFont(theme.reading_font(14, bold=True))
            box.addWidget(head)
        self.box.addWidget(card)
        return card, box

    def _people_list(self, box, heading: str, rows: list[dict]) -> None:
        if not rows:
            return
        box.addWidget(_label(heading, "FilterLabel"))
        top = max(r["count"] for r in rows)
        for r in rows:
            bar = Bar(short_name(r["name"]), r["count"], top, theme.current().lapis)
            bar.setToolTip(f"{r['name']}\nClick to open this narrator")
            bar.setCursor(Qt.CursorShape.PointingHandCursor)
            bar.mousePressEvent = lambda _e, pid=r["id"]: self.open_narrator.emit(pid)
            box.addWidget(bar)

    def show_scholar(self, scholar_id: str) -> None:
        conn = self.conn
        scholar = core_scholars.find(scholar_id)
        if conn is None or scholar is None:
            return
        self._current = scholar_id
        roles = next((s["roles"] for s in core_scholars.present(conn) if s["id"] == scholar_id), [])
        self._clear()
        t = theme.current()

        # the name (NM1), as for every narrator: known-as, full name, the parts
        self.box.addWidget(NameCard(core_scholars.name_view(scholar)))
        card, box = self._card()
        facts = [scholar["dates"]] if scholar["dates"] else []
        facts.append(", ".join(ROLE_TEXT[r] for r in roles))
        box.addWidget(_label(" · ".join(f for f in facts if f), "Lead"))
        if scholar["works"]:
            box.addWidget(_label("Works: " + "; ".join(scholar["works"]), "Caption"))
        pid = core_scholars.as_narrator(conn, scholar)
        if pid:
            row = QHBoxLayout()
            go = QPushButton("Open him as a narrator")
            go.setObjectName("Quiet")
            go.clicked.connect(lambda: self.open_narrator.emit(pid))
            row.addWidget(go)
            row.addStretch(1)
            box.addLayout(row)
        box.addWidget(_label("His life in full is planned (TODO H4); what follows is measured from the data imported here.",
                             "Caption"))
        for role in roles:
            title, text = core_scholars.ROLE_HELP[role]
            help_box = QFrame()
            help_box.setObjectName("Help")
            hb = QVBoxLayout(help_box)
            hb.setContentsMargins(16, 10, 16, 10)
            hb.setSpacing(3)
            hb.addWidget(_label(f"What is a {title.split(' · ')[0].lower()}?", "RowTitle"))
            hb.addWidget(_label(text, "Lead"))
            self.box.addWidget(help_box)

        for st in core_scholars.compiler_stats(conn, scholar):
            card, box = self._card(f"His collection: {st['book']}")
            pct = lambda a, b: f"{100 * a / b:.1f}%" if b else "—"  # noqa: E731
            box.addWidget(_label(
                f"<b>{st['hadith']:,}</b> hadith · <b>{st['chains']:,}</b> chains read, {pct(st['split'], st['chains'])} split "
                f"into narrators, {pct(st['reach'], st['chains'])} reaching the Prophet · {pct(st['identified'], st['links'])} "
                f"of the narrators identified", "Lead", rich=True))
            self._people_list(box, "His teachers — the first link of his chains", st["teachers"])
            self._people_list(box, "The Companions his chains end with most", st["companions"])

        g = core_scholars.grader_stats(conn, scholar)
        if g:
            card, box = self._card(f"His grades: {g['graded']:,} hadith in {', '.join(g['books'])}")
            top = max(g["distribution"].values() or [1])
            for label, n in g["distribution"].items():
                box.addWidget(Bar(label, n, top, theme.rank_color(GROUP_COLORS[label]),
                                  f"  ({100 * n / max(1, g['graded']):.0f}%)"))
            box.addWidget(_label("Grouped for comparison; the wording is kept. His most frequent wordings: "
                                 + ", ".join(f"{html.escape(w)} ({n:,})" for w, n in g["wordings"]), "Caption", rich=True))
            card, box = self._card("Agreement with the other graders on the same hadith")
            how = QFrame()
            how.setObjectName("Help")
            hw = QVBoxLayout(how)
            hw.setContentsMargins(14, 8, 14, 8)
            hw.setSpacing(4)
            for key in ("agreement", "kappa", "strictness"):
                hw.addWidget(_label(core_scholars.MEASURE_HELP[key], "Caption"))
            box.addWidget(how)
            for other, a in sorted(g["agreement"].items(), key=lambda kv: -kv[1]["agree"]):
                kappa = f"{a['kappa']:.2f}" if a["kappa"] is not None else "—"
                line = (f"<b>{html.escape(other)}</b>: same group on <b>{100 * a['agree']:.1f}%</b> of {a['common']:,} hadith "
                        f"(within one step {100 * a['within_one']:.1f}%) · Cohen's kappa {kappa} · "
                        f"he grades lower on {100 * a['lower']:.1f}%, higher on {100 * a['higher']:.1f}%")
                box.addWidget(_label(line, "Lead", rich=True))
                if a["agree"] >= HIGH_AGREEMENT:
                    warn = _label(f"⚠ {100 * a['agree']:.1f}% agreement is unusually high for two scholars grading on their "
                                  "own. The source may have filled one column from the other; treat this pair as not "
                                  "independent until the source is checked.", "Caption")
                    warn.setStyleSheet(f"color: {t.gold};")
                    box.addWidget(warn)
            if g["strictness"] is not None:
                s = g["strictness"]
                word = "stricter" if s < -0.05 else ("more lenient" if s > 0.05 else "close to the others")
                box.addWidget(_label(
                    f"<b>Strictness {s:+.2f}</b> — {word} than the other graders on the same hadith: his grade lower in "
                    f"{100 * g['lower']:.1f}%, higher in {100 * g['higher']:.1f}% of {g['compared']:,} comparisons. "
                    "The classical mutashaddid / mutasahil, by order only. Statistics → Graders measures it against a "
                    "model of the true grade, with intervals.", "Lead", rich=True))

        cr = core_scholars.critic_stats(conn, scholar)
        if cr:
            card, box = self._card(f"His verdicts on narrators: {cr['verdicts']:,} in {', '.join(cr['works'])}")
            top = max(n for _r, _l, n in cr["ranks"])
            for rank, label, n in cr["ranks"]:
                box.addWidget(Bar(f"{rank}. {label}", n, top, theme.rank_color(rank)))
            if cr["unranked"]:
                box.addWidget(_label(f"{cr['unranked']:,} verdicts do not fit one of his twelve ranks; their words are kept.",
                                     "Caption"))
        self.box.addStretch(1)

    def retheme(self) -> None:
        self.refresh()

    def release(self) -> None:
        """Let go of what is shown before a new theme; retheme() builds it again (UI5-P)."""
        self._clear()
