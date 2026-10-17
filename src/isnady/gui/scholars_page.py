"""Hadith Scholars: the compilers, graders and critics present in the imported data, with what the data
measures of their work (isnady.core.scholars)."""

import html

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
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

from isnady.core import i18n
from isnady.core import narrators as core_narrators
from isnady.core import scholars as core_scholars
from isnady.core.i18n import N_, tr
from isnady.core.rijal import short_name
from isnady.gui import theme
from isnady.gui.name_card import NameCard

ROLE_TEXT = {"compiler": N_("compiler of a collection"), "grader": N_("grades hadith"), "critic": N_("judges narrators")}
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
            shown = p.fontMetrics().elidedText(self._label, Qt.TextElideMode.ElideRight, label_w - 10)
            p.drawText(QRectF(0, 0, label_w - 8, self.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       shown)
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
IMAMI_COLORS = {"sahih": 2, "hasan": 4, "muwaththaq": 5, "da'if": 9}          # the Imami categories (road B)
SHIA_RANK_COLORS = {1: 2, 2: 4, 3: 5, 4: 9}


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
        title = _label(tr("Hadith Scholars"), "CardTitle")
        title.setFont(theme.reading_font(18, bold=True))
        self.note = _label(tr("The scholars whose work is in the imported data, Sunni and Shia, and what the data measures of it "
                             "— each by his own tradition's measure."), "Caption")
        # All / Sunni / Shia (SH1): one page, each tradition apart
        self._tradition: str | None = None
        self._segments = QButtonGroup(self)
        seg = QHBoxLayout()
        seg.setSpacing(6)
        for key, text in ((None, N_("All")), ("sunni", N_("Sunni")), ("shia", N_("Shia"))):
            b = QPushButton(tr(text))
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setProperty("tradition", key)
            b.setChecked(key is None)
            self._segments.addButton(b)
            seg.addWidget(b)
        seg.addStretch(1)
        self._segments.buttonClicked.connect(lambda b: self.set_tradition(b.property("tradition")))
        self.list = QListWidget()
        self.list.setObjectName("NarratorList")
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(lambda item, _p: item and item.data(Qt.ItemDataRole.UserRole)
                                             and self.show_scholar(item.data(Qt.ItemDataRole.UserRole)))
        lbox.addWidget(title)
        lbox.addLayout(seg)
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

    def set_tradition(self, tradition: str | None) -> None:
        """Show every scholar, or only the Sunni or only the Shia ones."""
        self._tradition = tradition
        for b in self._segments.buttons():
            b.setChecked(b.property("tradition") == tradition)
        self.refresh()

    def refresh(self) -> None:
        conn = self.conn
        if conn is None:
            return
        people = [s for s in core_scholars.present(conn)
                  if self._tradition is None or core_scholars.tradition_of(s) == self._tradition]
        self.list.blockSignals(True)
        self.list.clear()
        for role in ("compiler", "grader", "critic"):
            group = [s for s in people if role in s["roles"]]
            if not group:
                continue
            title = tr(core_scholars.ROLE_HELP[role][0])
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
                row.setMaximumWidth(340)            # the list is 364 wide: a long name must not push the rest out of view
                name = _label(s["name"], "RowTitle", wrap=False)
                name.setFont(theme.reading_font(15, bold=True))
                rbox.addWidget(name)
                rbox.addWidget(_label(s.get("tr", ""), "RowLatin", wrap=False))
                arabic = QLabel(s["arabic"])         # its own line: beside a long Turkish name it was clipped
                arabic.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
                arabic.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                                     f"{theme.font_css(theme.script_font('arabic', factor=0.6))}")
                rbox.addWidget(arabic)
                shia = core_scholars.tradition_of(s) == "shia"
                facts = ([f"<span style='color:{theme.current().gold}'><b>{tr('Shia')}</b></span>"] if shia else []) + \
                    ([html.escape(i18n.dates(s["dates"]))] if s["dates"] else [])
                if facts:
                    rbox.addWidget(_label(" · ".join(facts), "Caption", wrap=False, rich=True))
                item.setSizeHint(row.sizeHint())
                self.list.addItem(item)
                self.list.setItemWidget(item, row)
        self.list.blockSignals(False)
        if not people:
            self._clear()
            card, box = self._card()
            box.addWidget(_label(tr("No scholars yet: import a collection (File → Data Sources)."), "Lead"))
            self.box.addStretch(1)
            return
        ids = [p["id"] for p in people]
        target = self._current if self._current in ids else people[0]["id"]
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
        conn = self.conn
        for r in rows:
            # the name read in the interface language (L1); the Arabic where isnady cannot read it yet
            reading, arabic = core_narrators.reading(conn, r["id"], r["name"])
            bar = Bar(reading or short_name(r["name"]), r["count"], top, theme.current().lapis)
            bar.setToolTip(tr("{reading}\n{arabic}\n{name}\nClick to open this narrator", reading=reading, arabic=arabic, name=r['name']) if reading
                           else tr("{name}\nClick to open this narrator", name=r['name']))
            bar.setCursor(Qt.CursorShape.PointingHandCursor)
            bar.mousePressEvent = lambda _e, pid=r["id"]: self.open_narrator.emit(pid)
            box.addWidget(bar)

    def show_scholar(self, scholar_id: str) -> None:
        conn = self.conn
        scholar = core_scholars.find(scholar_id)
        if conn is None or scholar is None:
            return
        if self._tradition and core_scholars.tradition_of(scholar) != self._tradition:
            self.set_tradition(None)                  # a scholar of the other tradition was asked for
        self._current = scholar_id
        roles = next((s["roles"] for s in core_scholars.present(conn) if s["id"] == scholar_id), [])
        self._clear()
        t = theme.current()
        shia = core_scholars.tradition_of(scholar) == "shia"

        # the name (NM1), as for every narrator: known-as, full name, the parts
        from isnady.gui.bookmarks_page import BookmarkButton

        view = core_scholars.name_view(scholar)
        star = BookmarkButton("scholar", scholar["id"], core_scholars.short_name(scholar), scholar.get("arabic", ""))
        self.box.addWidget(NameCard(view, star=star))
        card, box = self._card()
        facts = [i18n.dates(scholar["dates"])] if scholar["dates"] else []
        facts.append(", ".join(tr(ROLE_TEXT[r]) for r in roles))
        trow = QHBoxLayout()
        tag = QLabel(tr("Shia scholar") if shia else tr("Sunni scholar"))
        tag.setObjectName("TagGold" if shia else "TagMuted")
        tag.setToolTip(tr("Measured along the road of his own tradition: his chains end at a Ma'sum, his grades are compared "
                         "only with the Shia graders on the Imami categories, his verdicts are read in the Imami terms.") if shia else tr("Measured along the Sunni road: chains to the Prophet, the Sunni grade groups, Ibn Hajar's twelve "
                                                     "ranks."))
        trow.addWidget(tag)
        trow.addWidget(_label(" · ".join(f for f in facts if f), "Lead"), 1)
        box.addLayout(trow)
        if scholar["works"]:
            box.addWidget(_label(tr("Works: ") + "; ".join(scholar["works"]), "Caption"))
        pid = core_scholars.as_narrator(conn, scholar)
        if pid:
            row = QHBoxLayout()
            go = QPushButton(tr("Open him as a narrator"))
            go.setObjectName("Quiet")
            go.clicked.connect(lambda: self.open_narrator.emit(pid))
            row.addWidget(go)
            row.addStretch(1)
            box.addLayout(row)
        # his life (BIO2): written for isnady; else, when he is a narrator here, as his rijal entry and the chains say
        from isnady.core import lives
        from isnady.gui.life_card import life_card

        written = lives.of_scholar(scholar_id)
        if written is not None:
            self.box.addWidget(life_card(lives.view(written), True))
        elif pid:
            info = lives.read(conn, pid)
            if info is not None and info["paragraphs"]:
                self.box.addWidget(life_card(info, False))
        for role in roles:
            title, text = (tr(x) for x in core_scholars.ROLE_HELP[role])
            help_box = QFrame()
            help_box.setObjectName("Help")
            hb = QVBoxLayout(help_box)
            hb.setContentsMargins(16, 10, 16, 10)
            hb.setSpacing(3)
            hb.addWidget(_label(tr({"compiler": N_("What is a compiler (musannif)?"), "grader": N_("What is a grader?"),
                                    "critic": N_("What is a critic of narrators?")}[role]), "RowTitle"))
            hb.addWidget(_label(text, "Lead"))
            self.box.addWidget(help_box)

        for st in core_scholars.compiler_stats(conn, scholar):
            card, box = self._card(tr("His collection: {book}", book=st['book']))
            pct = lambda a, b: f"{100 * a / b:.1f}%" if b else "—"  # noqa: E731
            values = dict(hadith=st["hadith"], chains=st["chains"], split=pct(st["split"], st["chains"]),
                          reach=pct(st["reach"], st["chains"]), identified=pct(st["identified"], st["links"]))
            box.addWidget(_label(
                tr("<b>{hadith:,}</b> hadith · <b>{chains:,}</b> chains read, {split} split into narrators, {reach} "
                   "reaching a Ma'sum (the Prophet or an Imam) · {identified} of the narrators identified in "
                   "al-Najashi", **values) if st.get("tradition") == "shia" else
                tr("<b>{hadith:,}</b> hadith · <b>{chains:,}</b> chains read, {split} split into narrators, {reach} "
                   "reaching the Prophet · {identified} of the narrators identified in the Taqrib", **values),
                "Lead", rich=True))
            self._people_list(box, tr("His teachers — the first link of his chains"), st["teachers"])
            self._people_list(box, tr("The Companions his chains end with most"), st["companions"])
            if st.get("ends"):
                box.addWidget(_label(tr("Whom his chains reach"), "FilterLabel"))
                top = max(e["count"] for e in st["ends"])
                for e in st["ends"][:10]:
                    box.addWidget(Bar(e["label"], e["count"], top, t.gold))

        g = core_scholars.grader_stats(conn, scholar)
        if g:
            card, box = self._card(tr("His grades: {graded:,} hadith in {books}", graded=g['graded'], books=', '.join(g['books'])))
            imami = g.get("tradition") == "shia"
            colors = IMAMI_COLORS if imami else GROUP_COLORS
            top = max(g["distribution"].values() or [1])
            for label, n in g["distribution"].items():
                box.addWidget(Bar(tr(label), n, top, theme.rank_color(colors.get(label, 8)),
                                  f"  ({100 * n / max(1, g['graded']):.0f}%)"))
            if imami:
                box.addWidget(_label(tr(core_scholars.MEASURE_HELP["imami"]), "Caption"))
            arabic = theme.script_font("arabic", factor=0.7)
            words = ", ".join((f"<span style='font-family:\"{arabic.family()}\"'>{html.escape(w)}</span> ({n:,})"
                               if any("\u0600" <= ch <= "\u06ff" for ch in w) else f"{html.escape(w)} ({n:,})")
                              for w, n in g["wordings"])
            box.addWidget(_label((tr("Grouped in the Imami categories for comparison; the wording is kept. His most "
                                     "frequent wordings: {words}", words=words) if imami else
                                  tr("Grouped for comparison; the wording is kept. His most frequent wordings: {words}",
                                     words=words)), "Caption", rich=True))
            card, box = self._card(tr("Agreement with the other Shia graders on the same hadith") if imami else
                                   tr("Agreement with the other graders on the same hadith"))
            if not g["agreement"]:
                box.addWidget(_label(tr("No other grader of his tradition graded the same hadith in the data imported here."),
                                     "Caption"))
            how = QFrame()
            how.setObjectName("Help")
            hw = QVBoxLayout(how)
            hw.setContentsMargins(14, 8, 14, 8)
            hw.setSpacing(4)
            for key in ("agreement", "kappa", "strictness"):
                hw.addWidget(_label(tr(core_scholars.MEASURE_HELP[key]), "Caption"))
            box.addWidget(how)
            for other, a in sorted(g["agreement"].items(), key=lambda kv: -kv[1]["agree"]):
                kappa = f"{a['kappa']:.2f}" if a["kappa"] is not None else "—"
                line = tr("<b>{other}</b>: same group on <b>{agree:.1f}%</b> of {common:,} hadith (within one step "
                          "{within:.1f}%) · Cohen's kappa {kappa} · he grades lower on {lower:.1f}%, higher on "
                          "{higher:.1f}%", other=html.escape(other), agree=100 * a["agree"], common=a["common"],
                          within=100 * a["within_one"], kappa=kappa, lower=100 * a["lower"], higher=100 * a["higher"])
                box.addWidget(_label(line, "Lead", rich=True))
                if a["agree"] >= HIGH_AGREEMENT:
                    warn = _label(tr("⚠ {value:.1f}% agreement is unusually high for two scholars grading on their own. The source may "
                                    "have filled one column from the other; treat this pair as not independent until the source is "
                                    "checked.", value=100 * a['agree']), "Caption")
                    warn.setStyleSheet(f"color: {t.gold};")
                    box.addWidget(warn)
            if g["strictness"] is not None:
                s = g["strictness"]
                word = tr("stricter") if s < -0.05 else (tr("more lenient") if s > 0.05 else tr("close to the others"))
                box.addWidget(_label(
                    tr("<b>Strictness {s:+.2f}</b> — {word} than the other graders on the same hadith: his grade lower in "
                      "{value:.1f}%, higher in {value2:.1f}% of {compared:,} comparisons. ", s=s, word=word, value=100 * g['lower'], value2=100 * g['higher'], compared=g['compared'])
                    + (tr("By the order of the Imami categories only, among the Shia graders.") if imami else
                       tr("The classical mutashaddid / mutasahil, by order only. Statistics → Graders measures it against a "
                         "model of the true grade, with intervals.")), "Lead", rich=True))

        cr = core_scholars.critic_stats(conn, scholar)
        if cr:
            card, box = self._card(tr("His verdicts on narrators: {verdicts:,} in {works}", verdicts=cr['verdicts'], works=', '.join(cr['works'])))
            top = max([n for _r, _l, n in cr["ranks"]] or [1])
            if cr.get("tradition") == "shia":
                box.addWidget(_label(tr("Reliability, in the Imami terms of his own words (never Ibn Hajar's twelve ranks)"),
                                     "FilterLabel"))
                for rank, label, n in cr["ranks"]:
                    box.addWidget(Bar(tr(label), n, top, theme.rank_color(SHIA_RANK_COLORS.get(rank, 8))))
                if cr.get("creeds"):
                    box.addWidget(_label(tr("Creed, where he states it"), "FilterLabel"))
                    ctop = max(n for _l, n in cr["creeds"])
                    for label, n in cr["creeds"]:
                        box.addWidget(Bar(tr(label), n, ctop, t.gold))
                if cr["unranked"]:
                    box.addWidget(_label(tr("{unranked:,} entries give no judgment in these words (often an author listed for his books); "
                                           "their words are kept.", unranked=cr['unranked']), "Caption"))
            else:
                for rank, label, n in cr["ranks"]:
                    box.addWidget(Bar(f"{rank}. {tr(label)}", n, top, theme.rank_color(rank)))
                if cr["unranked"]:
                    box.addWidget(_label(tr("{unranked:,} verdicts do not fit one of his twelve ranks; their words are kept.", unranked=cr['unranked']), "Caption"))
        self.box.addStretch(1)

    def retheme(self) -> None:
        self.refresh()

    def release(self) -> None:
        """Let go of what is shown before a new theme; retheme() builds it again (UI5-P)."""
        self._clear()
