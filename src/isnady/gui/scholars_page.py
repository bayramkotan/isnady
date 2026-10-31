"""Hadith Scholars: the compilers, graders and critics present in the imported data, with what the data
measures of their work (isnady.core.scholars)."""

import html

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from isnady.core.i18n import N_, n_, tr
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
    open_book = Signal(str)          # his book, as imported (2026-10-18: the books he compiled open)
    find_name = Signal(str)          # a teacher or student named in his life → looked for among the narrators
    visited = Signal(str)            # a scholar or a hafiz picked in the list → the window's back and forward (NAV2b)

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
        # the Sunni scholars first, each time isnady opens (NR-DEF1); the reader's choice holds while it runs
        self._tradition: str | None = "sunni"
        self._segments = QButtonGroup(self)
        seg = QHBoxLayout()
        seg.setSpacing(6)
        # the fourth: the huffaz of al-Dhahabi's Tadhkirat al-Huffaz (HFZ1), generation by generation
        for key, text in ((None, N_("All")), ("sunni", N_("Sunni")), ("shia", N_("Shia")), ("huffaz", N_("Huffaz"))):
            b = QPushButton(tr(text))
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setProperty("tradition", key)
            b.setChecked(key == self._tradition)
            self._segments.addButton(b)
            seg.addWidget(b)
        seg.addStretch(1)
        self._segments.buttonClicked.connect(lambda b: self.set_tradition(b.property("tradition")))
        self.list = QListWidget()
        self.list.setObjectName("NarratorList")
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(lambda item, _p: item and item.data(Qt.ItemDataRole.UserRole)
                                             and self._picked(item.data(Qt.ItemDataRole.UserRole)))
        # right-click (CTX1): open, as a narrator, his books, bookmark, copy his name
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._scholar_menu)
        # the huffaz: a name to look for and a generation, shown only with them
        self._hafiz: int | None = None
        self.hafiz_query = QLineEdit()
        self.hafiz_query.setPlaceholderText(tr("Name — Arabic or Latin letters"))
        self.hafiz_query.setClearButtonEnabled(True)
        self.hafiz_tabaqa = QComboBox()
        self.hafiz_tabaqa.addItem(tr("Every generation"), None)
        for g in range(1, 22):
            self.hafiz_tabaqa.addItem(tr("Generation {n}", n=g), g)
        self._hafiz_timer = QTimer(self)
        self._hafiz_timer.setSingleShot(True)
        self._hafiz_timer.setInterval(220)
        self._hafiz_timer.timeout.connect(self._fill_huffaz)
        self.hafiz_query.textChanged.connect(lambda _t: self._hafiz_timer.start())
        self.hafiz_tabaqa.currentIndexChanged.connect(lambda _i: self._fill_huffaz())
        self.hafiz_filters = QWidget()
        fl = QHBoxLayout(self.hafiz_filters)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(6)
        fl.addWidget(self.hafiz_query, 1)
        fl.addWidget(self.hafiz_tabaqa)
        self.hafiz_filters.hide()
        lbox.addWidget(title)
        lbox.addLayout(seg)
        lbox.addWidget(self.note)
        lbox.addWidget(self.hafiz_filters)
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
        huffaz = self._tradition == "huffaz"
        self.hafiz_filters.setVisible(huffaz)
        self.note.setText(tr("Al-Dhahabi's Tadhkirat al-Huffaz (d. 748 AH): the masters of hadith memorisation and "
                             "criticism, generation by generation, each tied to his narrator entry in the Taqrib where he "
                             "is there.") if huffaz else
                          tr("The scholars whose work is in the imported data, Sunni and Shia, and what the data measures of it "
                             "— each by his own tradition's measure."))
        if huffaz:
            self._fill_huffaz()
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
                # the name in the interface language first (Bayram, 2026-10-18: the English name stood on top in the
                # Turkish interface); under it his fuller name in the same language
                lang = i18n.language()
                name = _label(core_scholars.short_name(s, lang), "RowTitle", wrap=False)
                name.setFont(theme.reading_font(15, bold=True))
                rbox.addWidget(name)
                fuller = (s.get("tr") if lang == "tr" else "" if i18n.rtl() else s.get("full")) or ""
                if fuller and fuller != name.text():
                    rbox.addWidget(_label(fuller, "RowLatin", wrap=False))
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

    def _picked(self, scholar_id: str) -> None:
        self.show_scholar(scholar_id)
        if not scholar_id.startswith("tabaqa:"):
            self.visited.emit(scholar_id)

    def _scholar_menu(self, pos) -> None:
        from isnady.core import huffaz
        from isnady.gui import context_menu as cm

        item = self.list.itemAt(pos)
        sid = item.data(Qt.ItemDataRole.UserRole) if item else None
        conn = self.conn
        if not sid or conn is None or sid.startswith("tabaqa:"):
            return
        at = self.list.viewport().mapToGlobal(pos)
        if sid.startswith("hafiz:"):
            r = next((x for x in huffaz.people(conn) if x["n"] == int(sid[6:])), None)
            if r is None:
                return
            reading = huffaz.reading(r, i18n.language())
            cm.popup(self.list, at, [
                (tr("Open"), lambda: self.list.setCurrentItem(item)),
                (tr("Open him as a narrator"), (lambda: self.open_narrator.emit(r["person"])) if r.get("person") else None),
                None,
                (tr("Copy"), [(tr("His name in Arabic"), lambda: cm.copy(r["head"])),
                              *([(tr("His name as read"), lambda: cm.copy(reading))] if reading else [])]),
            ])
            return
        scholar = core_scholars.find(sid)
        if scholar is None:
            return
        from isnady.core import titles

        have = {k: n for k, n in conn.execute("SELECT key, name FROM collections")}
        books = [(tr("Open {book}", book=titles.book(k, have[k])), lambda k=k: self.open_book.emit(k))
                 for k in scholar.get("compiler_of", []) if k in have]
        pid = core_scholars.as_narrator(conn, scholar)
        name = core_scholars.short_name(scholar, i18n.language())
        cm.popup(self.list, at, [
            (tr("Open"), lambda: self.list.setCurrentItem(item)),
            (tr("Open him as a narrator"), (lambda: self.open_narrator.emit(pid)) if pid else None),
            *books,
            None,
            cm.bookmark_entry("scholar", scholar["id"], core_scholars.short_name(scholar), scholar.get("arabic", "")),
            (tr("Copy"), [(tr("His name as read"), lambda: cm.copy(name)),
                          *([(tr("His name in Arabic"), lambda: cm.copy(scholar["arabic"]))] if scholar.get("arabic") else []),
                          *([(tr("His full name"), lambda: cm.copy(scholar["full"]))] if scholar.get("full") else [])]),
        ])

    def show_scholar(self, scholar_id: str) -> None:
        if scholar_id.startswith("hafiz:"):
            if self._tradition != "huffaz":
                # opened from elsewhere (Back, a bookmark): the huffaz shown first, with him chosen
                self._hafiz = int(scholar_id[6:])
                self.set_tradition("huffaz")
                return
            self.show_hafiz(int(scholar_id[6:]))
            return
        if scholar_id.startswith("tabaqa:"):
            self.show_huffaz_overview(int(scholar_id[7:]))
            return
        conn = self.conn
        scholar = core_scholars.find(scholar_id)
        if conn is None or scholar is None:
            return
        if self._tradition and core_scholars.tradition_of(scholar) != self._tradition:
            self.set_tradition(core_scholars.tradition_of(scholar))   # a scholar of the other tradition: his own
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
        from isnady.core import titles

        have = {r[0]: r[1] for r in conn.execute("SELECT key, name FROM collections")}
        mine = [k for k in scholar.get("compiler_of", []) if k in have]
        pid = core_scholars.as_narrator(conn, scholar)
        if mine or pid:
            row = QHBoxLayout()
            for k in mine:
                b = QPushButton(tr("Open {book}", book=titles.book(k, have[k])))
                b.setObjectName("Quiet")
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(lambda _c=False, key=k: self.open_book.emit(key))
                row.addWidget(b)
            row.addStretch(1)
            box.addLayout(row)
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
            self.box.addWidget(life_card(lives.view(written), True, open_name=self.find_name.emit))
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

    # ------------------------------------------------------------------ the huffaz (HFZ1)
    def _hafiz_reading(self, r: dict) -> str:
        from isnady.core import huffaz

        return huffaz.reading(r, i18n.language())

    def _hafiz_died(self, r: dict) -> str:
        from isnady.core import huffaz

        year, whose = huffaz.death_of(r)
        if not year:
            return ""
        text = tr("d. {year} AH", year=year)
        if whose == "taqrib":
            text += " " + tr("(Taqrib)")
        elif r.get("taqrib_death") and r["taqrib_death"] != year:
            text += " " + tr("(Taqrib: {year})", year=r["taqrib_death"])
        return text

    def _fill_huffaz(self) -> None:
        """The list: each generation's heading, then its huffaz — plain rows, so 1,176 of them come at once."""
        from isnady.core import huffaz

        conn = self.conn
        if self._tradition != "huffaz" or conn is None:
            return
        rows = huffaz.find(conn, self.hafiz_query.text().strip(), self.hafiz_tabaqa.currentData())
        gens = {g["tabaqa"]: g for g in huffaz.generations(conn)}
        self.list.blockSignals(True)
        self.list.clear()
        current = None
        last = None
        head_font = theme.reading_font(12, bold=True)
        arabic_first = i18n.language() == "ar"
        for r in rows:
            if r["tabaqa"] != last:
                last = r["tabaqa"]
                g = gens[last]
                span = tr(" · d. {start}–{end} AH", start=g["from"], end=g["to"]) if g["median"] else ""
                head = QListWidgetItem(tr("Generation {n}", n=last) + f" ({g['count']})" + span)
                head.setData(Qt.ItemDataRole.UserRole, f"tabaqa:{last}")
                head.setFont(head_font)
                head.setForeground(QColor(theme.current().gold))
                self.list.addItem(head)
            reading = self._hafiz_reading(r)
            died = self._hafiz_died(r)
            first = r["name"] if arabic_first or not reading else reading
            # the Arabic last: in the middle of a Latin line the direction turns and the line reads out of order
            second = " · ".join(x for x in (str(r["n"]), died, "" if first == r["name"] else r["name"]) if x)
            item = QListWidgetItem(f"{first}\n{second}")
            item.setData(Qt.ItemDataRole.UserRole, f"hafiz:{r['n']}")
            item.setToolTip(r["head"])
            self.list.addItem(item)
            if r["n"] == self._hafiz:
                current = item
        if current is not None:
            self.list.setCurrentItem(current)
        self.list.blockSignals(False)
        if current is not None:
            self.list.scrollToItem(current)
            self.show_hafiz(self._hafiz)
        else:
            self.show_huffaz_overview(self.hafiz_tabaqa.currentData())

    def show_huffaz_overview(self, tabaqa: int | None = None) -> None:
        """The book at a glance: how many huffaz each generation holds, when they died, how many the Taqrib has too."""
        from isnady.core import huffaz

        conn = self.conn
        if conn is None:
            return
        self._clear()
        t = theme.current()
        gens = huffaz.generations(conn)
        rows = huffaz.people(conn)
        card, box = self._card(tr("Al-Dhahabi, Tadhkirat al-Huffaz"))
        dated = sum(1 for r in rows if huffaz.death_of(r)[0])
        linked = sum(1 for r in rows if r.get("person"))
        box.addWidget(_label(tr("<b>{count:,}</b> huffaz in <b>{generations}</b> generations, from Abu Bakr al-Siddiq to "
                                "al-Dhahabi's own teachers · a year of death for {dated:,} · <b>{linked:,}</b> of them are "
                                "narrators of the Taqrib, and open in the Narrators page.",
                                count=len(rows), generations=len(gens), dated=dated, linked=linked), "Lead", rich=True))
        box.addWidget(_label(tr("A hafiz is not every narrator: al-Dhahabi lists the masters who memorised the hadith in great "
                                "numbers and judged their narrators. The many narrators of the first centuries are in the "
                                "Narrators page (Ibn Hajar's Taqrib)."), "Caption"))
        card, box = self._card(tr("Generation by generation"))
        top = max(g["count"] for g in gens)
        for g in gens:
            label = (tr("Gen. {n} · {start}–{end} AH", n=g["tabaqa"], start=g["from"], end=g["to"]) if g["median"]
                     else tr("Generation {n}", n=g["tabaqa"]))
            bar = Bar(label, g["count"], top, t.gold if g["tabaqa"] == tabaqa else t.lapis)
            stated = tr(" — al-Dhahabi's own count: {n}", n=g["stated"]) if g["stated"] else ""
            bar.setToolTip(tr("{count} huffaz; {linked} in the Taqrib; half of them died between {start} and {end} AH "
                              "(median {median}){stated}", count=g["count"], linked=g["in_taqrib"], start=g["from"] or "—",
                              end=g["to"] or "—", median=g["median"] or "—", stated=stated))
            box.addWidget(bar)
        box.addWidget(_label(tr("The years are the middle half of each generation's deaths; the counts are read from the "
                                "book, and where al-Dhahabi gives a generation's count himself it is in the tooltip."),
                             "Caption"))
        card, box = self._card(tr("When they died, by century of the Hijra"))
        cent = huffaz.by_century(conn)
        top = max(n for _c, n in cent)
        for c, n in cent:
            box.addWidget(Bar(tr("{n}. century AH", n=c), n, top, t.lapis))
        self.box.addStretch(1)

    def show_hafiz(self, n: int) -> None:
        from isnady.core import huffaz
        from isnady.core.rijal import display_name
        from isnady.gui.life_card import SourceEntry

        conn = self.conn
        r = next((x for x in huffaz.people(conn) if x["n"] == n), None)
        if conn is None or r is None:
            return
        self._hafiz = n
        self._clear()
        t = theme.current()
        card, box = self._card()
        reading = self._hafiz_reading(r)
        if reading:
            title = _label(reading, "CardTitle")
            title.setFont(theme.reading_font(18, bold=True))
            box.addWidget(title)
            if r.get("taqrib_name") and i18n.language() != "ar":
                from isnady.core.names import latin

                full = latin(display_name(r["taqrib_name"]), i18n.language())
                if full and full != reading:
                    box.addWidget(_label(full, "RowLatin"))
        arabic = QLabel(r["head"])
        arabic.setWordWrap(True)
        arabic.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
        arabic.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                             f"{theme.font_css(theme.script_font('arabic', factor=0.85))}")
        box.addWidget(arabic)
        g = next(x for x in huffaz.generations(conn) if x["tabaqa"] == r["tabaqa"])
        facts = [tr("Tadhkirat al-Huffaz no. {n}", n=r["n"]),
                 tr("generation {n} of 21", n=r["tabaqa"])]
        died = self._hafiz_died(r)
        if died:
            facts.append(died)
        box.addWidget(_label(" · ".join(facts), "Lead"))
        if huffaz.death_of(r)[1] == "dhahabi":
            box.addWidget(_label(tr("The year of death is al-Dhahabi's, read from his words in the entry."), "Caption"))
        if g["median"]:
            box.addWidget(_label(tr("Half of his generation died between {start} and {end} AH.", start=g["from"], end=g["to"]),
                                 "Caption"))
        if r["rumuz"]:
            signs = " ".join(r["rumuz"])
            box.addWidget(_label(tr("Narrates in: {books}", books="; ".join(tr(x) for x in huffaz.rumuz_text(r["rumuz"])))
                                 + f"   <span style='color:{t.muted}'>[{html.escape(signs)}]</span>", "Lead", rich=True))
            box.addWidget(_label(tr("Al-Mizzi's signs, which al-Dhahabi puts before the name: in whose book of the six "
                                    "his hadith are."), "Caption"))
        if r.get("person"):
            card, box = self._card(tr("In Ibn Hajar's Taqrib"))
            name = QLabel(display_name(r["taqrib_name"]))
            name.setWordWrap(True)
            name.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
            name.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                               f"{theme.font_css(theme.script_font('arabic', factor=0.7))}")
            box.addWidget(name)
            who = core_narrators.describe(conn, r["person"])
            lines = []
            for v in (who or {}).get("verdicts", []):
                if v.get("rank_label"):
                    lines.append(tr("{critic}: rank {rank} of 12, {label}", critic=tr(v["critic_name"]), rank=v["rank"],
                                    label=v["rank_label"]))
            if r.get("in_chains"):
                lines.append(n_("In the books imported here: in {links:,} chain link", "In the books imported here: in "
                                "{links:,} chain links", r["in_chains"], links=r["in_chains"]))
            for line in lines:
                box.addWidget(_label(line, "Lead"))
            box.addWidget(_label(tr("Tied by the name, the father and the grandfather and the two years of death; where "
                                    "these do not agree he is left untied."), "Caption"))
            row = QHBoxLayout()
            go = QPushButton(tr("Open him as a narrator"))
            go.setObjectName("Quiet")
            go.setCursor(Qt.CursorShape.PointingHandCursor)
            go.clicked.connect(lambda _c=False, pid=r["person"]: self.open_narrator.emit(pid))
            row.addWidget(go)
            row.addStretch(1)
            box.addLayout(row)
        card, box = self._card(tr("His entry in the Tadhkira"))
        box.addWidget(SourceEntry(huffaz.source_entry(r, i18n.language())))
        row = QHBoxLayout()
        back = QPushButton(tr("All generations"))
        back.setObjectName("Quiet")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(lambda: self.show_huffaz_overview(r["tabaqa"]))
        row.addWidget(back)
        row.addStretch(1)
        self.box.addLayout(row)
        self.box.addStretch(1)

    def retheme(self) -> None:
        self.refresh()

    def release(self) -> None:
        """Let go of what is shown before a new theme; retheme() builds it again (UI5-P)."""
        self._clear()
