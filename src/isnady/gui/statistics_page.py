"""Statistics (ST7, deep): the imported corpus measured — the narrators, the chains, the grades against the chains,
the books, and the graders of each book.

One section at a time, chosen on the left. Each section is a few FINDINGS: a sentence that says what the numbers
show, the chart that shows it, the figures behind it on hover, and — folded until asked for — how to read it and
how it was measured; every finding can be saved as CSV for a thesis or a paper. The numbers are computed once in the
background and kept (core.stats_corpus, core.stats_models, core.stats_lab, core.stats_graders); ranks and grades are
ordered categories throughout: counted, cross-tabulated and rank-correlated, never averaged (SK).
"""

import csv
import html
import math
from collections import Counter

from PySide6.QtCore import QObject, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from isnady.core import narrators as core_narrators
from isnady.core import stats_corpus as corpus
from isnady.core import stats_graders as core
from isnady.core import stats_lab as lab
from isnady.core import stats_models as models
from isnady.core.i18n import N_, n_, tr
from isnady.core.rijal import RANK_LABELS, TABAQA_LABELS
from isnady.core.scholars import SCHOLARS
from isnady.gui import theme
from isnady.gui.stats_charts import (
    Calibration,
    Columns,
    HeatMap,
    IntervalPlot,
    Lorenz,
    PeopleBars,
    StackedBars,
    StatTiles,
)


def _corpus_and_models(conn, key, progress, recompute) -> dict:
    """The analyses of the corpus sections, in one background run: the descriptive one, the model, the laboratory.
    Each road on its own scale (SH1): road B (the Shia books) on al-Najashi's categories and the four Imami grades of
    al-Majlisi and al-Behbudi — never on Ibn Hajar's ranks or the Sunni grade groups (core.stats_corpus.Road)."""
    return {"corpus": corpus.cached(conn, key, progress, recompute), "models": models.cached(conn, key, progress, recompute),
            "lab": lab.cached(conn, key, progress, recompute), "road": corpus.tradition_of_scope(conn, key)}


SECTIONS = [
    ("overview", N_("Overview"), N_("the corpus at a glance")),
    ("narrators", N_("Narrators"), N_("who carries the hadith")),
    ("chains", N_("Chains"), N_("length, weakest link, time")),
    ("grades", N_("Grades and chains"), N_("do the chains explain the grades")),
    ("model", N_("The hadith model"), N_("what a scholar's grade follows")),
    ("lab", N_("Correlations and tests"), N_("what goes with what, and is it real")),
    ("books", N_("Books"), N_("the books compared")),
    ("graders", N_("Graders"), N_("the scholars who graded")),
]
# Ranks and grades are ordered AND two-sided (accepted ↔ rejected): a diverging scale, blue for the accepted side, red
# for the rejected, the neutral grey in the middle for "acceptable when followed" (maqbul). Lightness grows towards the
# middle on each arm; a legend, the gaps between segments and the hover text carry the identity as well (never colour
# alone). Light and dark steps are chosen each for its own surface.
GROUP_COLORS = {False: ["#1E4A8A", "#3A72B8", "#8DB4DE", "#C9C6C0", "#E4997A", "#B23A33"],
                True: ["#6E9FE0", "#4A7FC4", "#2E5A92", "#55534F", "#B4543F", "#E0705F"]}
# why, on road B, a chain whose weakest is "praised" is so often graded sahih — hadith science, not a quirk of the data
PRAISED_NOTE = N_("In al-Najashi's own words \u201cpraised\u201d takes in some of the greatest narrators — Zurara, Ibn Abi "
                "'Umayr, Ahmad b. Muhammad b. 'Isa — whom he calls jalil or wajh without the word thiqa, and whom al-Tusi "
                "and the later scholars count as thiqa (some among the ashab al-ijma'): a chain whose weakest is "
                "\u201cpraised\u201d is therefore often graded sahih.")
GRADE_COLORS = {False: ["#1E4A8A", "#8DB4DE", "#E4997A", "#C8564A", "#8E2A25"],
                True: ["#6E9FE0", "#2E5A92", "#B4543F", "#D86A55", "#F08A75"]}
# road B's four Imami grades: sahih and hasan on the accepted side, muwaththaq (a thiqa of another school) the neutral
# middle, da'if the rejected side — the same diverging scale, never the Sunni groups' colours by meaning
IMAMI_GRADE_COLORS = {False: ["#1E4A8A", "#8DB4DE", "#C9C6C0", "#C8564A"],
                      True: ["#6E9FE0", "#2E5A92", "#55534F", "#D86A55"]}


def _label(text: str, name: str = "", rich: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
    return label


def _short(grader: str) -> str:
    """A grader's short name for headers and charts (the full name is in the tooltips)."""
    for s in SCHOLARS:
        if grader in s.get("grader_names", []):
            return s.get("short") or s["name"]
    return grader


def _full(grader: str) -> str:
    for s in SCHOLARS:
        if grader in s.get("grader_names", []):
            return s.get("full") or s["name"]
    return grader


def _q(q: float | None) -> str:
    return "—" if q is None else ("q < 0.001" if q < 0.001 else f"q {q:.3f}")


def _outcome(name: str) -> str:
    return _short(name[len("Grade: "):]) if name.startswith("Grade: ") else tr(name)


def _factor(name: str) -> str:
    """A factor of the hadith model or the laboratory, as core names it ("Weakest: Praised"), in the interface
    language."""
    if name.startswith("Weakest: "):
        return tr("Weakest: {level}", level=tr(name[len("Weakest: "):]))
    return tr(name)


def _grade(label: str) -> str:
    """A grade, or grades the model merged ("very weak or fabricated"), in the interface language."""
    return " / ".join(tr(part) for part in label.split(" or "))


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


class _Worker(QObject):
    progress = Signal(str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, job, key, recompute: bool) -> None:
        super().__init__()
        self.job, self.key, self.recompute = job, key, recompute

    def run(self) -> None:
        from isnady.data import db

        try:
            conn = db.connect()                       # its own connection: SQLite connections stay in their thread
            self.done.emit(self.job(conn, self.key, self.progress.emit, self.recompute))
            conn.close()
        except Exception as exc:                      # shown on the page, never a silent failure
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class StatisticsPage(QWidget):
    open_hadith = Signal(int)
    open_narrator = Signal(int)

    def __init__(self, connection_getter, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._conn_of = connection_getter
        self._thread = None
        self._gthread = None
        self._result: dict | None = None
        self._names: dict[int, str] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 22, 30, 14)
        root.setSpacing(12)

        # the head: what this is, and the one choice that changes everything below — which books
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = _label(tr("Statistics"), "CardTitle")
        title.setFont(theme.reading_font(22, bold=True))
        titles.addWidget(title)
        titles.addWidget(_label(tr("The imported books measured: who carries the hadith, how the chains hold, and whether they "
                                  "explain the grades."), "Lead"))
        head.addLayout(titles, 1)
        head.addWidget(_label(tr("Books"), "FilterTitle"), 0, Qt.AlignmentFlag.AlignBottom)
        self.scope = QComboBox()
        self.scope.setObjectName("FilterCombo")
        self.scope.setMinimumWidth(220)
        self.scope.currentIndexChanged.connect(self._scope_changed)
        head.addWidget(self.scope, 0, Qt.AlignmentFlag.AlignBottom)
        self.c_recompute = QPushButton(tr("Recompute"))
        self.c_recompute.setObjectName("Quiet")
        self.c_recompute.setToolTip(tr("The results are kept in a file and reused while the data is unchanged"))
        self.c_recompute.clicked.connect(lambda: self.compute_corpus(True))
        head.addWidget(self.c_recompute, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(head)
        self.c_status = _label("", "Caption")
        root.addWidget(self.c_status)

        # the body: the sections on the left, one shown at a time
        body = QHBoxLayout()
        body.setSpacing(18)
        self.rail = QListWidget()
        self.rail.setObjectName("StatsRail")
        self.rail.setFixedWidth(210)
        self.rail.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stack = QStackedWidget()
        self._boxes: dict[str, QVBoxLayout] = {}
        for key, name, sub in SECTIONS:
            item = QListWidgetItem(f"{tr(name)}\n{tr(sub)}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setSizeHint(QSize(200, 52))
            self.rail.addItem(item)
            if key == "graders":
                self.stack.addWidget(self._graders_section())
                continue
            page = QWidget()
            page.setObjectName("Page")
            box = QVBoxLayout(page)
            box.setContentsMargins(0, 0, 10, 20)
            box.setSpacing(16)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
            self._boxes[key] = box
        self.rail.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.rail.setCurrentRow(0)
        body.addWidget(self.rail)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)
        self._loaded = False

    @property
    def conn(self):
        return self._conn_of()

    # ------------------------------------------------------------------ building blocks
    def _finding(self, key: str, kicker: str, headline: str, widgets: list, how: str = "",
                 table: tuple[list, list] | None = None) -> QFrame:
        """A finding: a small kicker, the sentence that says what the numbers show, the chart(s), and a footer with
        "How to read it" (folded) and "Save as CSV…" (the figures behind the chart, for a thesis or a paper)."""
        t = theme.current()
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 18, 24, 14)
        lay.setSpacing(10)
        k = _label(kicker.upper(), "Caption")
        k.setStyleSheet(f"color: {t.muted}; font-size: 8pt; letter-spacing: 1px;")
        lay.addWidget(k)
        h = _label(headline, "", rich=True)
        h.setFont(theme.reading_font(16, bold=True))
        h.setStyleSheet(f"color: {t.ink};")
        lay.addWidget(h)
        for w in widgets:
            if isinstance(w, QWidget):
                lay.addWidget(w)
            else:
                lay.addLayout(w)
        foot = QHBoxLayout()
        foot.setSpacing(14)
        if how:
            more = _label(how, "Caption", rich=True)
            more.setVisible(False)
            toggle = QPushButton(tr("How to read it ▸"))
            toggle.setObjectName("Link")
            toggle.setCursor(Qt.CursorShape.PointingHandCursor)

            def flip(_c=False, m=more, b=toggle):
                m.setVisible(not m.isVisible())
                b.setText(tr("How to read it ▾") if m.isVisible() else tr("How to read it ▸"))
            toggle.clicked.connect(flip)
            foot.addWidget(toggle)
        if table:
            save = QPushButton(tr("Save as CSV…"))
            save.setObjectName("Link")
            save.setCursor(Qt.CursorShape.PointingHandCursor)
            save.setToolTip(tr("The figures behind this finding, as a table any spreadsheet or statistics program opens"))
            save.clicked.connect(lambda _c=False, tb=table, name=kicker: self._save_csv(name, *tb))
            foot.addWidget(save)
        foot.addStretch(1)
        if how or table:
            lay.addLayout(foot)
            if how:
                lay.addWidget(more)
        self._boxes[key].addWidget(card)
        return card

    def _save_csv(self, name: str, header: list, rows: list) -> None:
        safe = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
        path, _f = QFileDialog.getSaveFileName(self, tr("Save as CSV"), f"isnady-{safe}.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:      # with BOM: Excel reads Arabic right
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    def _name(self, pid: int, name_ar: str) -> str:
        """A narrator's name in the interface language (L1), the Arabic where it cannot be read yet."""
        if pid not in self._names:
            reading, arabic = core_narrators.reading(self.conn, pid, name_ar)
            self._names[pid] = reading or arabic
        return self._names[pid]

    def _people(self, rows: list[dict], value=lambda r: r["links"], unit: str = "") -> PeopleBars:
        items = []
        shia = self._shia()
        group_of = corpus.GROUP_OF_RANK_SHIA if shia else corpus.GROUP_OF_RANK
        colors = self._colors()
        for r in rows:
            rank = r.get("rank")
            if shia:
                from isnady.core import shia_rijal

                facts = [tr("al-Najashi: {meaning}", meaning=tr(shia_rijal.RANKS[rank][1])) if rank in shia_rijal.RANKS
                         else tr("no judgment in al-Najashi")]
            else:
                facts = [tr("rank {rank}: {meaning}", rank=rank, meaning=tr(RANK_LABELS[rank][1])) if rank in RANK_LABELS
                         else tr("no rank in the Taqrib")]
            if r.get("tabaqa"):
                facts.append(tr("tabaqa {tabaqa}", tabaqa=r["tabaqa"]))
            if r.get("death"):
                facts.append(tr("d. {year} AH", year=r["death"]))
            facts.append(tr("{links:,} times in the chains, in {hadith:,} hadith", links=r["links"], hadith=r["hadith"]))
            items.append({"id": r["id"], "label": self._name(r["id"], r["name"]), "value": value(r),
                          "dot": colors[group_of[rank]] if rank in group_of else None,
                          "tip": f"{self._name(r['id'], r['name'])}\n{r['name']}\n" + "\n".join(facts)
                                 + "\n\n" + tr("Click to open him on the Narrators page")})
        bars = PeopleBars(items, unit)
        bars.clicked.connect(self.open_narrator.emit)
        return bars

    def _shia(self) -> bool:
        return (getattr(self, "_result", None) or {}).get("corpus", {}).get("tradition") == "shia"

    def _colors(self) -> list[str]:
        """The colours of the rank groups: Ibn Hajar's six, or the four Imami categories (road B)."""
        full = GROUP_COLORS[theme.current().dark]
        return full[1:5] if self._shia() else full

    def _words(self) -> dict:
        """The words of the road being measured: whom the chains reach, whose book identifies the narrators."""
        if self._shia():
            return {"end": tr("a Ma'sum"), "End": tr("a Ma'sum (the Prophet ﷺ or an Imam)"),
                    "rijal": tr("al-Najashi's Rijal"), "critic": tr("al-Najashi"), "reach": tr("Reach a Ma'sum"),
                    "rank": "al-Najashi's category", "rank_shown": tr("al-Najashi's category"),
                    "grades": tr("the four Imami categories (sahih, hasan, muwaththaq, da'if)"),
                    "scale": tr("sahih → da'if"),
                    "otherwise": tr("a narrator the grader judged otherwise than al-Najashi (al-Majlisi also draws on "
                                    "al-Tusi, al-Kashshi and the later critics), or a name matched to the wrong person")}
        return {"end": tr("the Prophet ﷺ"), "End": tr("the Prophet ﷺ"), "rijal": tr("Ibn Hajar's Taqrib"),
                "critic": tr("Ibn Hajar"), "reach": tr("Reach the Prophet"), "rank": "Ibn Hajar's rank",
                "rank_shown": tr("Ibn Hajar's rank"), "grades": tr("five ordered groups"),
                "scale": tr("sahih → fabricated"), "otherwise": tr("a narrator the grader judged otherwise than Ibn Hajar")}

    def _clear_sections(self) -> None:
        for box in self._boxes.values():
            while box.count():
                item = box.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()

    # ------------------------------------------------------------------ data
    def refresh(self) -> None:
        conn = self.conn
        if conn is None:
            return
        from isnady.core import search as core_search

        from isnady.gui.widgets import fill_book_combo

        from isnady.core import books as core_books

        active = core_books.all_books(conn)
        sunni = sum(1 for b in active if b["tradition"] != "shia")
        shia = len(active) - sunni
        current = self.scope.currentData()
        self.scope.blockSignals(True)
        # road A first ("all books" are the Sunni ones), road B beside it: never the two measured together (SH1)
        fill_book_combo(self.scope, conn, tr("All Sunni books ({n})", n=sunni))
        if shia:
            self.scope.insertItem(1, tr("All Shia books ({shia})", shia=shia), corpus.SHIA_SCOPE)
        index = self.scope.findData(current)
        self.scope.setCurrentIndex(index if index >= 0 else 0)
        self.scope.blockSignals(False)
        _ = core_search
        self._names.clear()
        self.compute_corpus(False)
        self._refresh_graders()

    def compute_corpus(self, recompute: bool) -> None:
        if self.conn is None or (self._thread is not None and self._thread.isRunning()):
            return
        self.c_status.setText(tr("Computing…") if recompute else tr("Reading the saved results…"))
        self.c_recompute.setEnabled(False)
        self._thread = QThread(self)
        self._cworker = _Worker(_corpus_and_models, self.scope.currentData(), recompute)
        self._cworker.moveToThread(self._thread)
        self._thread.started.connect(self._cworker.run)
        self._cworker.progress.connect(lambda m: self.c_status.setText(m + "…"))
        self._cworker.done.connect(self._show_corpus)
        self._cworker.failed.connect(lambda m: self.c_status.setText(tr("Could not compute: {error}", error=m)))
        for sig in (self._cworker.done, self._cworker.failed):
            sig.connect(self._thread.quit)
        self._thread.finished.connect(lambda: self.c_recompute.setEnabled(True))
        self._thread.start()

    def retheme(self) -> None:
        self._names.clear()
        if self._result is not None:
            self._show_corpus(self._result)
        if getattr(self, "_gresult", None) is not None:
            self._show(self._gresult)

    def release(self) -> None:
        """Let go of the charts before a new theme; retheme() draws them again (UI5-P)."""
        self._clear_sections()

    # ------------------------------------------------------------------ the corpus sections
    def _show_corpus(self, both: dict) -> None:
        self._result = both
        r, self._models = both["corpus"], both.get("models") or {}
        self._clear_sections()
        if r.get("empty") or not r.get("overview", {}).get("chains"):
            for key in self._boxes:
                self._boxes[key].addWidget(_label(tr("Nothing to measure yet: import a hadith collection (File → Data Sources), and a book of narrators "
                                                    "(Ibn Hajar's Taqrib) to identify them."), "Lead"))
                self._boxes[key].addStretch(1)
            self.c_status.setText("")
            return
        self.c_status.setText(
            (tr("From the saved results — computed once, reused while the data is unchanged.") if r.get("from_file")
             else tr("Computed and saved.")) + " " + tr("Intervals: {boot} bootstrap samples of hadith.", boot=r["boot"]))
        self._overview(r)
        self._narrators(r)
        self._chains(r)
        self._grades(r)
        self._model_section()
        self._lab_section(both.get("lab") or {})
        self._books(r)
        for box in self._boxes.values():
            box.addStretch(1)

    def _group_categories(self, r: dict) -> list[tuple[str, str]]:
        return list(zip([tr(name) for name, _d in r["groups"]], self._colors()))

    def _grade_categories(self, r: dict) -> list[tuple[str, str]]:
        colors = (IMAMI_GRADE_COLORS if r.get("tradition") == "shia" else GRADE_COLORS)[theme.current().dark]
        return list(zip([tr(g) for g in r["grade_labels"]], colors))

    def _overview(self, r: dict) -> None:
        o, n = r["overview"], r["narrators"]
        share_id = o["identified"] / o["links"] if o["links"] else 0
        reach = o["reaching"] / o["chains"] if o["chains"] else 0
        tiles = StatTiles([
            (tr("Hadith"), f"{o['hadith']:,}", n_("in {n} book", "in {n} books", o["books"])),
            (tr("Chains read"), f"{o['chains']:,}", tr("{share} reach {end}", share=_pct(reach), end=self._words()["end"])),
            (tr("Names identified"), _pct(share_id), tr("{identified:,} of {links:,} names in the chains",
                                                         identified=o["identified"], links=o["links"])),
            (tr("Narrators"), f"{o['narrators']:,}", tr("different people identified in the chains")),
        ])
        self._finding("overview", tr("The corpus"), tr("{hadith:,} hadith, {chains:,} chains, {narrators:,} narrators identified.", hadith=o['hadith'], chains=o['chains'], narrators=o['narrators']), [tiles],
                      tr("A chain is <b>read</b> when isnady split its text into names; a name is <b>identified</b> when it "
                        "is matched to one person of {rijal}. Everything below rests on the identified names, so their "
                        "share is the first thing to know: the measures describe the identified part.", rijal=self._words()['rijal']),
                      (["measure", "value"], [["hadith", o["hadith"]], ["books", o["books"]], ["chains", o["chains"]],
                                              ["chains reaching the Prophet", o["reaching"]], ["names in chains", o["links"]],
                                              ["names identified", o["identified"]], ["narrators", o["narrators"]],
                                              ["chains fully identified", o["full"]]]))
        cats = self._group_categories(r)
        strong = (n["rank_links"][0] + n["rank_links"][1]) / (sum(n["rank_links"]) or 1)
        if self._shia():
            rows = [(tr("All narrators of al-Najashi"), n["rank_all"]), (tr("The narrators in these chains"), n["rank_people"]),
                    (tr("Every name in these chains"), n["rank_links"])]
            self._finding("overview", tr("Reliability"), tr("{strong} of the judged transmission passes through narrators al-Najashi calls trustworthy or "
                                                       "praises.", strong=_pct(strong)), [StackedBars(rows, cats)],
                          tr("al-Najashi's words read in the four Imami categories — trustworthy (thiqa), praised (mamduh), a "
                            "thiqa of another school (muwaththaq), weak — never on Ibn Hajar's scale. The first bar is "
                            "everyone he judged; the second, the narrators who appear in these chains; the third counts each "
                            "narrator as often as he appears. Many of his entries give no judgment (an author listed for his "
                            "books): those are left out of the bars. Counted, never averaged."),
                          (["series"] + [c[0] for c in cats], [[label] + list(v) for label, v in rows]))
        else:
            rows = [(tr("All narrators of the Taqrib"), n["rank_all"]), (tr("The narrators in these chains"), n["rank_people"]),
                    (tr("Every name in these chains"), n["rank_links"])]
            self._finding("overview", tr("Reliability"), tr("{strong} of all transmission passes through Companions and trustworthy narrators — far more than "
                                                       "their share of the Taqrib.", strong=_pct(strong)),
                          [StackedBars(rows, cats)],
                          tr("Ibn Hajar's twelve ranks in six groups, from Companions to the rejected. The first bar is "
                            "everyone Ibn Hajar judged; the second, the narrators who appear in these chains; the third counts "
                            "each narrator as often as he appears — what the hadith actually rest on. The ranks are ordered "
                            "categories: counted, never averaged."),
                          (["series"] + [c[0] for c in cats], [[label] + list(v) for label, v in rows]))
        if r["grades"]:
            gcats = self._grade_categories(r)
            grows = [(f"{_short(g['grader'])} — {g['book']}", g["distribution"]) for g in r["grades"]]
            self._finding("overview", tr("Grades"), tr("How each scholar graded each book."), [StackedBars(grows, gcats, label_w=260)],
                          ((tr("Each bar is one scholar's grades of one book, in the four Imami categories — sahih (every "
                              "narrator an Imami thiqa), hasan (a praised Imami), muwaththaq (a thiqa of another school), da'if "
                              "— as al-Majlisi and al-Behbudi wrote them; majhul, mursal and marfu' count among the da'if. "
                              "al-Behbudi's Sahih al-Kafi is his selection: he names only the hadith he holds sahih."))
                           if self._shia() else
                           tr("Each bar is one scholar's grades of one book, in five ordered groups. Grades of the chain alone "
                             "(\"Isnaad Sahih\") are left out: they judge another thing than a grade of the hadith.")),
                          (["grader", "book"] + r["grade_labels"],
                           [[_short(g["grader"]), g["book"]] + g["distribution"] for g in r["grades"]]))

    def _narrators(self, r: dict) -> None:
        n = r["narrators"]
        c = n["concentration"]
        if c.get("gini") is not None:
            tiles = StatTiles([(tr("Busiest 1%"), _pct(c["top1"]), tr("of all identified names")),
                               (tr("Busiest 10%"), _pct(c["top10"]), tr("of all identified names")),
                               (tr("Half of all names"), f"{c['half_by']:,}", tr("narrators, of {people:,}", people=c["people"])),
                               (tr("Gini"), f"{c['gini']:.2f}", tr("0 equal shares, 1 one man carries all"))])
            self._finding("narrators", tr("Concentration"), tr("The busiest 10% of narrators carry {top10} of the transmission; {half_by:,} narrators carry half "
                                                          "of it.", top10=_pct(c['top10']), half_by=c['half_by']), [tiles, Lorenz(c["curve"])],
                          tr("The curve sorts the narrators from the least to the most often seen and adds up their share of "
                            "the identified names. The diagonal would be every narrator carrying the same; the further the "
                            "curve sags below it, the more the corpus rests on a few — the madar (pivot) narrators of the "
                            "classical critics. The Gini coefficient is the area between the two, doubled."),
                          (["share of narrators", "share of names"], c["curve"]))
        self._finding("narrators", tr("The pillars"), tr("The narrators the most hadith pass through."),
                      [self._people(n["pillars"][:20])],
                      tr("Counted from the identified names of these chains: how often a narrator appears, and (on hover) "
                        "in how many hadith. The dot is {critic}'s judgment of him. Click a name to open him.", critic=self._words()['critic']),
                      (["narrator", "arabic", "rank", "tabaqa", "times", "hadith"],
                       [[self._name(p["id"], p["name"]), p["name"], p["rank"], p["tabaqa"], p["links"], p["hadith"]]
                        for p in n["pillars"]]))
        if n["weak_pillars"]:
            self._finding("narrators", tr("Weak narrators"), tr("The weak or unknown narrators the most hadith pass through — where a grade would hang on one man."), [self._people(n["weak_pillars"])],
                          (tr("Narrators al-Najashi calls weak (da'if, confused, accused, extremist), by how often they "
                              "appear. A hadith that passes through one of them is graded on its other routes — or stays "
                              "weak.") if self._shia() else
                           tr("Narrators of rank 7 or weaker (mastur, da'if, majhul and below), by how often they appear. "
                              "A hadith that passes through one of them is graded on its other routes — or stays weak.")),
                          (["narrator", "arabic", "rank", "times", "hadith"],
                           [[self._name(p["id"], p["name"]), p["name"], p["rank"], p["links"], p["hadith"]]
                            for p in n["weak_pillars"]]))
        if n["central"]:
            self._finding("narrators", tr("The network"), tr("The narrators the transmission flows through, towards {end}.", end=self._words()['end']), [self._people(n["central"], value=lambda p: 100 * p["score"], unit=" ‰")],
                          tr("PageRank on the graph of who narrates from whom (each pair of neighbours in a chain, weighted by "
                            "how often): a narrator ranks high when many chains lead to him and through him, not only when he "
                            "appears often. The figure is his share of the flow in thousandths."),
                          (["narrator", "arabic", "pagerank", "times"],
                           [[self._name(p["id"], p["name"]), p["name"], round(p["score"], 6), p["links"]]
                            for p in n["central"]]))
        cats = self._group_categories(r)
        rows = [(f"{t} · {tr(TABAQA_LABELS.get(t, '')).split(' (')[0]}", n["tabaqa_groups"][t - 1]) for t in range(1, 13)
                if sum(n["tabaqa_groups"][t - 1])]
        if rows:
            self._finding("narrators", tr("Generations"), tr("Reliability generation by generation (tabaqa)."),
                          [StackedBars(rows, cats, label_w=250)],
                          tr("Ibn Hajar's twelve generations, from the Companions (1) to the teachers of the six books' "
                            "compilers (10–12); each bar shows how the narrators of that generation found in these chains are "
                            "ranked."),
                          (["tabaqa"] + [c[0] for c in cats], [[label] + list(v) for label, v in rows]))

    def _chains(self, r: dict) -> None:
        ch = r["chains"]
        lengths = dict((int(k), v) for k, v in ch["lengths"])
        unsplit = lengths.pop(0, 0)
        bins = [(str(k), lengths.get(k, 0)) for k in range(1, max(lengths or {1: 0}) + 1)]
        counts = sorted(k for k, v in lengths.items() for _ in range(v))
        median = counts[len(counts) // 2] if counts else 0
        self._finding("chains", tr("Length"), tr("Most chains have {median} narrators between the compiler and {end}.", median=median, end=self._words()['end']),
                      [Columns(bins, " " + tr("chains"))],
                      tr("The number of names in each chain. A short chain (isnad 'ali) has fewer links between the "
                        "compiler and {end}; a long one (nazil) more. {unsplit:,} chains could not be split into names yet "
                        "and are not counted.", end=self._words()['End'], unsplit=unsplit),
                      (["names in the chain", "chains"], [[k, v] for k, v in bins] + [["not split", unsplit]]))
        cats = self._group_categories(r)
        good = sum(ch["weakest"][:2 if self._shia() else 3]) / (sum(ch["weakest"]) or 1)
        rows = [(tr("Chains with a judged narrator"), ch["weakest"]), (tr("Chains fully identified"), ch["weakest_full"])]
        self._finding("chains", tr("The weakest link"),
                      tr("In {good} of the chains the weakest narrator is trustworthy or praised.", good=_pct(good))
                      if self._shia() else
                      tr("In {good} of the chains the weakest narrator is truthful or better.", good=_pct(good)),
                      [StackedBars(rows, cats)],
                      tr("A chain is as strong as its weakest narrator: for each chain, the weakest rank among its "
                        "identified narrators. The first bar counts every chain with at least one ranked narrator — its "
                        "weakest may be among the names not yet identified; the second only the chains whose every name is "
                        "identified."),
                      (["series"] + [c[0] for c in cats], [[label] + list(v) for label, v in rows]))
        if not any(v for _k, v in ch["gaps"]) and not (ch["order_ok"] + ch["order_bad"]):
            return                      # no years of death nor generations to compare (al-Najashi gives few)
        gaps = [(f"{k}", v) for k, v in ch["gaps"]]
        marked = {i for i, (k, _v) in enumerate(ch["gaps"]) if k > 100 or k <= -60}
        outside = sum(v for i, (_k, v) in enumerate(ch["gaps"]) if i in marked)
        table = self._suspects_table(ch["gap_suspects"], gap=True)
        self._finding("chains", tr("Time"), tr("{outside:,} teacher–student pairs lie too far apart in time — each points to a wrongly identified "
                                          "name or a wrong year.", outside=outside), [Columns(gaps, " " + tr("pairs"), marked, label_every=2), table],
                      tr("For two neighbours in a chain whose years of death are known: the student's year minus the "
                        "teacher's. Most students die 20–60 years after their teachers. More than 110 years, or a student "
                        "dying 60 years or more before his teacher (gold), is hard to believe: the list shows the pairs "
                        "behind them — check them on the Narrators page (double-click)."),
                      (["student", "teacher", "years apart", "times"],
                       [[self._name(s["student"]["id"], s["student"]["name"]), self._name(s["teacher"]["id"], s["teacher"]["name"]),
                         s["gap"], s["times"]] for s in ch["gap_suspects"]]))
        total = ch["order_ok"] + ch["order_bad"]
        if total:
            table = self._suspects_table(ch["order_suspects"], gap=False)
            self._finding("chains", tr("Generations in order"), tr("{value} of the identified pairs are in the right order of generations.", value=_pct(ch['order_ok'] / total)), [table],
                          tr("A student belongs to the same or a later generation (tabaqa) than his teacher. A pair where the "
                            "student is of an EARLIER generation than his teacher is a sign of a wrong identification; the "
                            "list shows those met most often."),
                          (["student", "student tabaqa", "teacher", "teacher tabaqa", "times"],
                           [[self._name(s["student"]["id"], s["student"]["name"]), s["student"]["tabaqa"],
                             self._name(s["teacher"]["id"], s["teacher"]["name"]), s["teacher"]["tabaqa"], s["times"]]
                            for s in ch["order_suspects"]]))

    def _suspects_table(self, suspects: list[dict], gap: bool) -> QTableWidget:
        heads = [tr("Student"), tr("Teacher"), tr("Years apart") if gap else tr("Generations"), tr("Times")]
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(heads)
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for s in suspects[:10]:
            row = table.rowCount()
            table.insertRow(row)
            for col, who in ((0, s["student"]), (1, s["teacher"])):
                item = QTableWidgetItem(self._name(who["id"], who["name"]))
                item.setToolTip(who["name"])
                item.setData(Qt.ItemDataRole.UserRole, who["id"])
                table.setItem(row, col, item)
            third = f"{s['gap']:+d}" if gap else f"{s['student']['tabaqa']} → {s['teacher']['tabaqa']}"
            table.setItem(row, 2, QTableWidgetItem(third))
            table.setItem(row, 3, QTableWidgetItem(str(s["times"])))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setFixedHeight(min(10, len(suspects)) * 30 + 34)
        table.cellDoubleClicked.connect(
            lambda rr, cc: self.open_narrator.emit(table.item(rr, cc if cc < 2 else 0).data(Qt.ItemDataRole.UserRole)))
        return table

    def _grades(self, r: dict) -> None:
        words = self._words()
        rows = [g for g in r["grades"] if g.get("weakest") and g["weakest"]["tau"] is not None]
        # a scholar who gives one grade only (al-Behbudi: his book is a selection of what he holds sahih) has nothing
        # to correlate: named, with the reason, instead of silently missing
        one = [g for g in r["grades"] if g not in rows and sum(1 for x in g["distribution"] if x) == 1]
        if one:
            self._boxes["grades"].addWidget(_label(
                "; ".join(tr("{grader} gives one grade only in {book} — {grade} for all {n:,} he names",
                             grader=_short(g["grader"]), book=g["book"], n=g["graded"],
                             grade=tr(r["grade_labels"][next(i for i, x in enumerate(g["distribution"]) if x)]))
                          for g in one)
                + ". " + tr("A single grade cannot go with anything, so he is left out below; how he stands beside the "
                            "other graders is in Graders."), "Caption"))
        if not rows:
            self._boxes["grades"].addWidget(_label(tr("No grades to compare: import a collection whose hadith are graded."),
                                                   "Lead"))
            return
        plot = [(f"{_short(g['grader'])} — {g['book']}", g["weakest"]["tau"],
                 tuple(g["weakest"]["tau_ci"] or (g["weakest"]["tau"], g["weakest"]["tau"]))) for g in rows]
        lo, hi = min(p[1] for p in plot), max(p[1] for p in plot)
        clear = [p for p in plot if p[2][0] > 0]          # the whole interval above zero
        span = f"{lo:.2f}" if len(plot) == 1 else f"{lo:.2f} – {hi:.2f}"
        if len(plot) == 1:
            who = html.escape(_short(rows[0]["grader"]))
            headline = (tr("The weaker a chain's weakest narrator, the lower {who}'s grade (Kendall's τ<sub>b</sub> "
                           "{tau}).", who=who, tau=span) if clear else
                        tr("{who}'s grade does not follow the weakest narrator beyond chance (τ<sub>b</sub> {tau}).",
                           who=who, tau=span))
        elif len(clear) == len(plot):
            headline = tr("The weaker a chain's weakest narrator, the lower the grade — for every grader (Kendall's "
                          "τ<sub>b</sub> {tau}).", tau=span)
        else:
            headline = tr("The weaker a chain's weakest narrator, the lower the grade — for {n} of {total} graders "
                          "beyond chance (τ<sub>b</sub> {tau}).", n=len(clear), total=len(plot), tau=span)
        self._finding("grades", tr("The weakest link and the grade"), headline,
                      [IntervalPlot(plot, tr("weaker narrator, higher grade"), tr("weaker narrator, lower grade"))],
                      tr("For each graded hadith: the weakest identified narrator of its best chain against the scholar's "
                        "grade, both as ordered categories. Kendall's τ<sub>b</sub> is a rank correlation that allows "
                        "ties: 0 is no relation, 1 a perfect one. The dot is the value, the line its 95% interval (a "
                        "bootstrap over hadith). A relation well above zero shows the grades follow the narrators — and "
                        "how much they do not shows what else a scholar weighed: other routes (mutaba'at, shawahid), "
                        "hidden defects ('ilal)."),
                      (["grader", "book", "hadith", "tau-b", "tau-b low", "tau-b high", "gamma"],
                       [[_short(g["grader"]), g["book"], g["weakest"]["n"], round(g["weakest"]["tau"], 4)]
                        + [round(x, 4) for x in (g["weakest"]["tau_ci"] or [None, None]) if x is not None]
                        + [round(g["weakest"]["gamma"], 4) if g["weakest"]["gamma"] is not None else ""] for g in rows]))
        # the tables behind it, one per grader: row = weakest narrator, column = grade, cell = share of the row
        grid = QGridLayout()
        grid.setHorizontalSpacing(22)
        group_names = [tr(name) for name, _d in r["groups"]]
        for i, g in enumerate(rows[:6]):
            table = g["weakest"]["table"]
            cells = []
            for row in table:
                total = sum(row)
                cells.append([(cnt / total if total else None, [f"{100 * cnt / total:.0f}%" if total else "—"])
                              for cnt in row])
            keep = [k for k, row in enumerate(table) if sum(row)]
            # one per row: two side by side were wider than the page and cut everything off on the right
            grid.addWidget(_label(f"<b>{html.escape(_short(g['grader']))}</b> — {html.escape(g['book'])}", "Lead", rich=True),
                           i * 2, 0)
            grid.addWidget(HeatMap([group_names[k] for k in keep], [tr(g) for g in r["grade_labels"]],
                                   [cells[k] for k in keep],
                                   cell=QSize(72, 28), label_w=140), i * 2 + 1, 0)
        grid.setColumnStretch(1, 1)
        self._finding("grades", tr("Cross-tables"), tr("How each grade is spread over the weakest narrator."), [grid],
                      tr("Rows: the weakest narrator of the hadith's best chain; columns: the grade. Each row adds up to "
                        "100%. A sahih grade where the weakest narrator is weak is a hadith strengthened by other routes, "
                        "or {otherwise}.", otherwise=words['otherwise']) + (" " + tr(PRAISED_NOTE) if self._shia() else ""),
                      (["grader", "book", "weakest narrator"] + r["grade_labels"],
                       [[_short(g["grader"]), g["book"], group_names[k]] + list(g["weakest"]["table"][k])
                        for g in rows for k in range(len(group_names))]))
        lengths = [g for g in rows if g.get("length") and g["length"]["tau"] is not None]
        if lengths:
            plot = [(f"{_short(g['grader'])} — {g['book']}", g["length"]["tau"],
                     tuple(g["length"]["tau_ci"] or (g["length"]["tau"], g["length"]["tau"]))) for g in lengths]
            weak_tau = {g["grader"] + g["book"]: g["weakest"]["tau"] for g in rows}
            lower = [p for p, g in zip(plot, lengths) if p[2][0] > 0]
            higher = [p for p, g in zip(plot, lengths) if p[2][1] < 0]
            smaller = all(abs(g["length"]["tau"]) < abs(weak_tau.get(g["grader"] + g["book"], 0)) for g in lengths)
            if not lower and not higher:
                headline = tr("The length of a chain does not go with the grade beyond chance.")
            elif len(lower) == len(plot):
                headline = (tr("Longer chains are graded a little lower — much less than weaker narrators are.")
                            if smaller else tr("Longer chains are graded a little lower."))
            elif len(higher) == len(plot):
                headline = (tr("Longer chains are graded a little higher — a smaller relation than the weakest "
                               "narrator's.") if smaller else tr("Longer chains are graded a little higher."))
            else:
                headline = (tr("Length goes with the grade for {n} of {total} graders, in different directions — always "
                               "less than the weakest narrator.", n=len(lower) + len(higher), total=len(plot)) if smaller
                            else tr("Length goes with the grade for {n} of {total} graders, in different directions.",
                                    n=len(lower) + len(higher), total=len(plot)))
            self._finding("grades", tr("Length and grade"), headline,
                          [IntervalPlot(plot, tr("longer, higher grade"), tr("longer, lower grade"))],
                          tr("The same rank correlation between the number of names in the hadith's chain and its grade. Its "
                            "size beside the weakest-link relation shows which of the two the grades follow."),
                          (["grader", "book", "tau-b", "low", "high"],
                           [[_short(g["grader"]), g["book"], round(g["length"]["tau"], 4)]
                            + [round(x, 4) for x in (g["length"]["tau_ci"] or [])] for g in lengths]))

    # ------------------------------------------------------------------ the hadith model (ST7-H)
    def _model_section(self) -> None:
        box = self._boxes["model"]
        ms = (self._models or {}).get("models") or []
        if not ms:
            box.addWidget(_label(tr("No model yet: it needs a book whose hadith are graded and whose chains are split into names (at "
                                   "least a hundred graded hadith, in two grades or more)."), "Lead"))
            return
        if self._shia():
            box.addWidget(_label(
                tr("Road B: the grade is one of the four Imami categories (sahih, hasan, muwaththaq, da'if), the "
                  "narrators are in al-Najashi's categories, a chain ends at a Ma'sum. al-Behbudi gives one grade "
                  "only (his book is a selection of what he holds sahih), so there is no model of his grades."), "Caption"))
        row = QHBoxLayout()
        row.addWidget(_label(tr("Model of"), "FilterTitle"))
        pick = QComboBox()
        pick.setObjectName("FilterCombo")
        for i, m in enumerate(ms):
            pick.addItem(f"{_short(m['grader'])} — {m['book_name']}", i)
        pick.setCurrentIndex(min(getattr(self, "_model_index", 0), len(ms) - 1))
        row.addWidget(pick)
        row.addStretch(1)
        holder = QWidget()
        holder.setLayout(row)
        box.addWidget(holder)
        self._model_box = QVBoxLayout()
        self._model_box.setSpacing(16)
        wrap = QWidget()
        wrap.setLayout(self._model_box)
        box.addWidget(wrap)

        def show(i: int) -> None:
            self._model_index = i
            while self._model_box.count():
                w = self._model_box.takeAt(0).widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
            self._model_findings(ms[i], ms)
        pick.currentIndexChanged.connect(show)
        show(pick.currentIndex())
        self._shared_surprises()

    def _model_finding(self, *args, **kwargs) -> QFrame:
        """A finding in the model's own box (the box is rebuilt when another scholar's model is chosen)."""
        card = self._finding("model", *args, **kwargs)
        self._boxes["model"].removeWidget(card)
        self._model_box.addWidget(card)
        return card

    def _model_findings(self, m: dict, all_models: list[dict]) -> None:
        name = _short(m["grader"])
        coefs = m["coefficients"]
        sig = [c for c in coefs if c["p"] < 0.05 and c["beta"] > 0]
        top = max(sig, key=lambda c: c["beta"]) if sig else None
        if top and top["name"].startswith("Weakest: "):
            headline = tr("For {name}, a weakest narrator who is {level} multiplies the odds of a weaker grade by "
                          "{odds:.1f}.", name=name, level=tr(top["name"][len("Weakest: "):]).lower(), odds=top["or"])
        elif top:
            headline = tr("For {name}, {factor} multiplies the odds of a weaker grade by {odds:.1f}.", name=name,
                          factor=_factor(top["name"]).lower(), odds=top["or"])
        else:
            headline = tr("For {name}, no factor of the chain moves the grade beyond chance.", name=name)
        plot = [(_factor(c["name"]), c["beta"], (c["beta"] - 1.96 * c["se"], c["beta"] + 1.96 * c["se"])) for c in coefs]
        fmt = lambda v, lo, hi: f"OR {math.exp(v):.2f}  [{math.exp(lo):.2f}–{math.exp(hi):.2f}]"  # noqa: E731
        self._model_finding(
            tr("What the grade follows"), headline,
            [IntervalPlot(plot, tr("a stronger grade"), tr("a weaker grade"), fmt=fmt, label_w=250)],
            tr("An ordinal (proportional-odds) regression of the scholar's grade on the hadith's best chain. Each "
              "row is one factor; the dot is its effect on the log-odds of a WEAKER grade, the line its 95% "
              "interval, and the figure at the right the odds ratio: 2 doubles the odds of a weaker grade, 0.5 "
              "halves them, 1 is no effect. The weakest narrator is compared with a chain whose weakest is "
              "trustworthy (thiqa); the other factors are per unit. All are measured together, so each is its "
              "effect with the others held equal.")
            + (" " + tr(PRAISED_NOTE) if self._shia() else ""),
            (["factor", "beta", "se", "odds ratio", "low", "high", "p"],
             [[c["name"], round(c["beta"], 5), round(c["se"], 5), round(c["or"], 4), round(c["or_ci"][0], 4),
               round(c["or_ci"][1], 4), c["p"]] for c in coefs]))
        # which factors matter: likelihood-ratio tests
        tests = sorted(m["tests"], key=lambda t: -t["chi2"])
        matter = [t for t in tests if t["p_holm"] < 0.05]
        total = m["lr_all"]["chi2"] or 1
        table = QTableWidget(len(tests), 5)
        table.setHorizontalHeaderLabels([tr("Factor"), "χ²", "df", tr("p (Holm)"), tr("Share explained")])
        table.horizontalHeaderItem(4).setToolTip(tr("The factor's χ² beside the whole chain's: its share of what the chain explains"))
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for i, t in enumerate(tests):
            for j, v in enumerate([_factor(t["label"]), f"{t['chi2']:.1f}", str(t["df"]),
                                   "< 0.001" if t["p_holm"] < 0.001 else f"{t['p_holm']:.3f}",
                                   _pct(t["chi2"] / total)]):
                item = QTableWidgetItem(v)
                if t["p_holm"] >= 0.05:
                    item.setForeground(QColor(theme.current().muted))       # no evidence: muted
                table.setItem(i, j, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setFixedHeight(len(tests) * 30 + 34)
        lead = tests[0] if tests else None
        self._model_finding(
            tr("Which factors matter"),
            (tr("{matter} of {tests} factors matter; {factor} alone carries {share} of what the chain explains.",
                matter=len(matter), tests=len(tests), factor=_factor(lead["label"]).lower(),
                share=_pct(lead["chi2"] / total)) if lead else tr("No factor to test.")),
            [table],
            tr("For each factor the model is fitted again without it; the likelihood-ratio χ² is how much worse "
              "it then fits, with its degrees of freedom. p is adjusted for testing several factors at once "
              "(Holm). The last column is the factor's χ² beside the whole chain's (all factors against none) — "
              "overlapping factors can add up to more than 100%."),
            (["factor", "chi2", "df", "p", "p holm"], [[t["label"], round(t["chi2"], 3), t["df"], t["p"], t["p_holm"]]
                                                       for t in tests]))
        # how much the chain explains
        tiles = StatTiles([
            (tr("Hadith"), f"{m['n']:,}", tr("graded by {name}, with a chain", name=name)),
            (tr("Right"), _pct(m["accuracy"]), tr("against {share} by always saying “{grade}”", share=_pct(m["base_rate"]),
                                                  grade=_grade(m.get("base_label") or m["labels"][0]))),
            ("McFadden R²", f"{m['mcfadden']:.3f}" if m["mcfadden"] is not None else "—",
             tr("0.2–0.4 is a very good fit")),
            ("Somers' D", f"{m['somers_d']:.2f}" if m["somers_d"] is not None else "—", tr("ordering: 0 none, 1 perfect")),
        ])
        self._model_finding(
            tr("How much the chain explains"),
            tr("The chain explains part of {name}'s grades, not most: the rest is what a scholar weighs beyond "
              "one chain.", name=name),
            [tiles, Calibration(m["calibration"], tr("Calibration: the model's probability of “{grade}” (across) "
                                                     "against the share of hadith that got it (up). Points on the "
                                                     "diagonal: the model's probabilities can be taken at their word.",
                                                     grade=_grade(m["labels"][0])))],
            tr("McFadden's R² compares the model's likelihood with a model that knows only how often each grade "
              "is given; for a model of human judgement values of 0.1–0.2 are usual and 0.2–0.4 very good. "
              "'Right' counts the hadith whose most likely grade is the scholar's. Somers' D measures how well "
              "the model's expected grade orders the hadith. ")
            + (tr("'Right' near the always-the-same figure does not mean the chain tells nothing — Somers' D and R² "
                 "show how far it orders the grades. On this road the grade is of the chain itself, so what the "
                 "model misses is mostly narrators the scholar judges otherwise than al-Najashi, and names isnady "
                 "did not identify.")
               if self._shia() else
               tr("That the chain explains only part of the grade is itself the finding: a scholar grades a hadith "
                 "on all its routes and on its text, not on one chain.")),
            (["predicted (mean)", "observed", "hadith"], m["calibration"]))
        # the surprises
        if self._shia():
            # road B: the Imami categories are grades of the CHAIN (al-Majlisi grades each chain by its narrators), so a
            # surprise points to a narrator judged otherwise, or to a name read or matched otherwise — not to other routes
            surprises = (
                ("graded_higher", N_("Graded higher than the chain foretells"),
                 N_("{n:,} hadith {name} grades stronger than their chain, as isnady reads it, would foretell."),
                 N_("Hadith whose grade is STRONGER than the model's most likely grade, the least expected first: the "
                 "probability is the model's for this grade or a stronger one. The Imami categories judge the chain by "
                 "its narrators, so the usual reasons are a narrator al-Majlisi holds stronger than al-Najashi's words "
                 "(he also draws on al-Tusi, al-Kashshi and the later critics, and on the shaykhs of ijaza), or a name "
                 "isnady matched to the wrong man of the same name. Double-click to read it in its book.")),
                ("graded_lower", N_("Graded lower than the chain foretells"),
                 N_("{n:,} hadith {name} grades weaker than their chain, as isnady reads it, would foretell."),
                 N_("Hadith whose grade is WEAKER than the model's most likely grade, the least expected first. The usual "
                 "reasons are a narrator al-Majlisi holds weaker or unknown (majhul) where al-Najashi is silent or "
                 "praises, a break in the chain (mursal, marfu') that the split into names does not show, or a wrong "
                 "match. Double-click to read it in its book.")))
        else:
            surprises = (
                ("graded_higher", N_("Graded higher than the chain foretells"),
                 N_("{n:,} hadith {name} grades stronger than their chain alone would — candidates for strengthening "
                    "by other routes (mutaba'at, shawahid)."),
                 N_("Hadith whose grade is STRONGER than the model's most likely grade, the least expected first: the "
                 "probability is the model's for this grade or a stronger one. A weak chain graded sahih or hasan is "
                 "usually a hadith strengthened by its other routes (hasan li-ghayrihi, sahih li-ghayrihi) — or a "
                 "narrator the scholar judges otherwise than Ibn Hajar. Double-click to read it in its book.")),
                ("graded_lower", N_("Graded lower than the chain foretells"),
                 N_("{n:,} hadith {name} grades weaker than their chain alone would — candidates for a hidden defect "
                    "('illa) or an irregular text (shudhudh)."),
                 N_("Hadith whose grade is WEAKER than the model's most likely grade, the least expected first. A chain of "
                 "trustworthy narrators graded weak points to what the chain does not show: a hidden defect ('illa), a "
                 "contradiction of stronger narrators (shudhudh), a break the names do not reveal (irsal khafi, tadlis). "
                 "Double-click to read it in its book.")))
        for side, title, sentence, how in surprises:
            items = m[side]
            if not items:
                continue
            total_side = m[f"{side}_total"]
            strong = m.get(f"{side}_strong", 0)
            sentence = tr(sentence, n=total_side, name=name) + " " + (
                tr("{strong:,} of them clearly (the model gave that grade 5% or less).", strong=strong) if strong
                else tr("None clearly: the model gave each grade more than 5%."))
            self._model_finding(tr(title), sentence, [self._surprise_table(items, m["labels"])], tr(how),
                                (["hadith", "grade", "model's most likely", "probability", "weakest narrator",
                                  "chain length", "chains"],
                                 [[d["number"], d["grade"], d["likely"], round(d["p"], 5), d["factors"]["weakest"],
                                   d["factors"]["length"], d["factors"]["routes"]] for d in items]))
        # the scholars compared, on the weakest narrator
        same_book = [x for x in all_models if x["book"] == m["book"]]
        if len(same_book) > 1:
            rows = []
            for c_name in [c["name"] for c in coefs if c["block"] == "weakest"]:
                for x in same_book:
                    c = next((c for c in x["coefficients"] if c["name"] == c_name), None)
                    if c:
                        rows.append((f"{tr(c_name.replace('Weakest: ', ''))} — {_short(x['grader'])}", c["beta"],
                                     (c["beta"] - 1.96 * c["se"], c["beta"] + 1.96 * c["se"])))
            self._model_finding(
                tr("The scholars compared"), tr("How strongly each scholar's grade follows the weakest narrator."),
                [IntervalPlot(rows, tr("a stronger grade"), tr("a weaker grade"), fmt=fmt, label_w=300)],
                tr("The same model fitted to each scholar's grades of this book. Where one scholar's odds ratio for a "
                  "weak narrator is larger than another's, he leans more on {critic}'s verdicts on the narrators; a "
                  "smaller one shows a scholar who more often finds the hadith strengthened elsewhere — or who "
                  "judges the narrator otherwise.", critic=self._words()['critic']),
                (["level", "grader", "beta", "low", "high"],
                 [[r_[0].split(" — ")[0], r_[0].split(" — ")[1], round(r_[1], 5), round(r_[2][0], 5), round(r_[2][1], 5)]
                  for r_ in rows]))

    def _surprise_table(self, items: list[dict], labels: list[str]) -> QTableWidget:
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels([tr("Hadith"), tr("Grade"), tr("Model's most likely"), tr("Probability"),
                                         tr("Weakest narrator"), tr("Names / not identified")])
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for d in items[:25]:
            row = table.rowCount()
            table.insertRow(row)
            first = QTableWidgetItem(str(d["number"]))
            first.setData(Qt.ItemDataRole.UserRole, d["hadith_id"])
            table.setItem(row, 0, first)
            f = d["factors"]
            probs = " · ".join(f"{_grade(lab)} {100 * q:.0f}%" for lab, q in zip(labels, d["probs"]))
            for j, v in enumerate([_grade(d["grade"]), _grade(d["likely"]), f"{100 * d['p']:.1f}%", tr(f["weakest"]),
                                   f"{f['length']} / {f['unidentified']}"], start=1):
                item = QTableWidgetItem(v)
                item.setToolTip(tr("The model's grades for this hadith: {probs}", probs=probs))
                table.setItem(row, j, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setFixedHeight(min(25, len(items)) * 30 + 34)
        table.cellDoubleClicked.connect(lambda rr, _c: self.open_hadith.emit(table.item(rr, 0).data(Qt.ItemDataRole.UserRole)))
        return table

    def _shared_surprises(self) -> None:
        shared = (self._models or {}).get("shared") or []
        if not shared:
            return
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels([tr("Hadith"), tr("Book"), tr("Scholars and their grades"), tr("Weakest narrator")])
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for s in shared[:30]:
            row = table.rowCount()
            table.insertRow(row)
            first = QTableWidgetItem(f"{s['number']}  {'▲' if s['side'] == 'graded_higher' else '▼'}")
            first.setData(Qt.ItemDataRole.UserRole, s["hadith_id"])
            first.setToolTip(tr("▲ graded higher than the chain foretells · ▼ graded lower"))
            table.setItem(row, 0, first)
            table.setItem(row, 1, QTableWidgetItem(s["book"]))
            who = QTableWidgetItem("; ".join(f"{_short(g)}: {_grade(grade)}" for g, grade, _l, _p in s["graders"]))
            who.setToolTip("\n".join(tr("{grader}: {grade} — the model expected {likely} ({share:.1f}% for this or "
                                         "further)", grader=_short(g), grade=_grade(grade), likely=_grade(likely),
                                         share=100 * p) for g, grade, likely, p in s["graders"]))
            table.setItem(row, 2, who)
            table.setItem(row, 3, QTableWidgetItem(tr(s["factors"]["weakest"])))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setFixedHeight(min(30, len(shared)) * 30 + 34)
        table.cellDoubleClicked.connect(lambda rr, _c: self.open_hadith.emit(table.item(rr, 0).data(Qt.ItemDataRole.UserRole)))
        up = sum(1 for s in shared if s["side"] == "graded_higher")
        self._finding("model", tr("Surprises the scholars share"),
                      tr("{shared} hadith surprise two scholars or more in the same way — {up} graded higher than their "
                        "chain, {value} lower.", shared=len(shared), up=up, value=len(shared) - up), [table],
                      tr("One scholar's surprise may be his own judgement or a slip; the same surprise in several scholars' "
                        "grades points to the hadith itself — its other routes, or a defect they all saw. ▲ higher than "
                        "the chain foretells, ▼ lower. Double-click to read it in its book."),
                      (["hadith", "side", "book", "graders", "weakest narrator"],
                       [[s["number"], s["side"], s["book"], "; ".join(f"{g}: {gr}" for g, gr, _l, _p in s["graders"]),
                         s["factors"]["weakest"]] for s in shared]))

    # ------------------------------------------------------------------ the laboratory (ST7-C)
    def _lab_section(self, r: dict) -> None:
        box = self._boxes["lab"]
        ms = r.get("hadith") or []
        if not ms and not r.get("narrators"):
            box.addWidget(_label(tr("Nothing to correlate yet: it needs a book whose chains are split into names."), "Lead"))
            return
        box.addWidget(_label(
            tr("Every measure against every other, by rank (Spearman's ρ): +1 the two rise together, −1 one falls "
              "as the other rises, 0 no relation. Ranks and grades are ordered, never averaged. With so many "
              "pairs some look related by chance, so each ρ carries a q-value (Benjamini–Hochberg): below 0.05 "
              "it is shown in colour, otherwise only outlined."), "Lead"))
        if len(ms) > 1:
            row = QHBoxLayout()
            row.addWidget(_label(tr("Book"), "FilterTitle"))
            pick = QComboBox()
            pick.setObjectName("FilterCombo")
            for i, m in enumerate(ms):
                pick.addItem(m["book"], i)
            pick.setCurrentIndex(min(getattr(self, "_lab_index", 0), len(ms) - 1))
            row.addWidget(pick)
            row.addStretch(1)
            holder = QWidget()
            holder.setLayout(row)
            box.addWidget(holder)
        self._lab_box = QVBoxLayout()
        self._lab_box.setContentsMargins(0, 0, 0, 0)
        self._lab_box.setSpacing(16)
        wrap = QWidget()
        wrap.setLayout(self._lab_box)
        box.addWidget(wrap)

        def show(i: int) -> None:
            self._lab_index = i
            while self._lab_box.count():
                w = self._lab_box.takeAt(0).widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
            if ms:
                self._lab_book(ms[i], [t for t in r.get("graders", []) if t["book"] == ms[i]["book"]])
                self._lab_brant([b for b in r.get("brant", []) if b["book"] == ms[i]["book"]])
        if len(ms) > 1:
            pick.currentIndexChanged.connect(show)
        show(min(getattr(self, "_lab_index", 0), max(0, len(ms) - 1)))
        if r.get("narrators"):
            self._lab_narrators(r["narrators"])
        if r.get("books"):
            self._lab_books(r["books"])

    def _lab_finding(self, *args, **kwargs) -> QFrame:
        card = self._finding("lab", *args, **kwargs)
        self._boxes["lab"].removeWidget(card)
        self._lab_box.addWidget(card)
        return card

    @staticmethod
    def _rho_cell(c: dict | None, extra: str = "") -> tuple:
        if not c or c.get("rho") is None:
            return (None, ["—"])
        text = f"{c['rho']:+.2f}"
        if c.get("q") is not None and c["q"] < lab.ALPHA:
            return (c["rho"], [text, extra or _q(c["q"])])
        return (None, [text])

    @staticmethod
    def _rho_tip(a: str, b: str, c: dict | None, held: bool = False) -> str:
        if not c or c.get("rho") is None:
            return tr("{a} × {b}: too few cases", a=a, b=b)
        sure = tr("a relation beyond chance") if c.get("q") is not None and c["q"] < lab.ALPHA else tr("could be chance")
        return (f"{a} × {b}" + (" — " + tr("the others held equal") if held else "") + "\n"
                + tr("Spearman's ρ {rho:+.3f} on {n:,} cases", rho=c["rho"], n=c["n"])
                + f"\np {c['p']:.2g} · {_q(c.get('q'))} — {sure}")

    def _matrix(self, m: dict, which: str, names: list[str], cell: QSize, label_w: int) -> HeatMap:
        grid = m[which]
        k = len(names)
        cells = [[(None, []) if i == j else self._rho_cell(grid[i][j]) for j in range(k)] for i in range(k)]
        tips = [["" if i == j else self._rho_tip(names[i], names[j], grid[i][j], which == "partial") for j in range(k)]
                for i in range(k)]
        return HeatMap(names, names, cells, -1, 1, diverging=True, cell=cell, label_w=label_w, tips=tips, head_h=60)

    def _switchable(self, m: dict, names: list[str], cell: QSize, label_w: int) -> QWidget:
        """A matrix with its two readings: each pair alone, and each pair with all the others held equal."""
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(_label(tr("Show"), "FilterTitle"))
        pick = QComboBox()
        pick.setObjectName("FilterCombo")
        pick.addItem(tr("Each pair alone"), "cells")
        if m.get("partial"):
            pick.addItem(tr("The others held equal (partial)"), "partial")
        row.addWidget(pick)
        row.addStretch(1)
        lay.addLayout(row)
        chart = [self._matrix(m, "cells", names, cell, label_w)]
        lay.addWidget(chart[0])

        def flip(_i: int) -> None:
            new = self._matrix(m, pick.currentData(), names, cell, label_w)
            lay.replaceWidget(chart[0], new)
            chart[0].setParent(None)
            chart[0].deleteLater()
            chart[0] = new
        pick.currentIndexChanged.connect(flip)
        return holder

    def _lab_book(self, m: dict, tests: list[dict]) -> None:
        k = m["factors"]
        factors = m["names"][:k]
        shown = [_factor(f) for f in factors]           # the factors in the interface language
        named = dict(zip(factors, shown))
        adjusted = m.get("adjusted") or []
        # 1. each grade against each factor, the others held equal
        if adjusted:
            rows = [_outcome(a["outcome"]) for a in adjusted]
            cells, tips = [], []
            for j, a in enumerate(adjusted):
                line, tip = [], []
                for i, c in enumerate(a["cells"]):
                    plain = m["cells"][i][k + j]
                    line.append(self._rho_cell(c, tr("alone {rho:+.2f}", rho=plain["rho"])
                                               if plain and plain.get("rho") is not None else ""))
                    tip.append(self._rho_tip(rows[j], shown[i], c, True)
                               + ("\n" + tr("Alone (nothing held equal): ρ {rho:+.3f}", rho=plain["rho"])
                                  if plain and plain.get("rho") is not None else ""))
                cells.append(line)
                tips.append(tip)
            best: dict[str, tuple] = {}
            for j, a in enumerate(adjusted):
                if not a["outcome"].startswith("Grade: "):
                    continue
                sure = [(c["rho"], factors[i]) for i, c in enumerate(a["cells"])
                        if c and c["q"] < lab.ALPHA and c["rho"] > 0]
                if sure:
                    best[rows[j]] = max(sure)
            tops = {f for _r, f in best.values()}
            if len(best) > 1 and len(tops) == 1:
                f = tops.pop()
                lo, hi = min(v for v, _f in best.values()), max(v for v, _f in best.values())
                rest = [c["rho"] for a in adjusted if a["outcome"].startswith("Grade: ") for i, c in enumerate(a["cells"])
                        if c and factors[i] != f and c["q"] < lab.ALPHA]
                headline = (tr("With the other factors equal, <i>{factor}</i> still goes with a weaker grade for every "
                               "scholar (ρ {lo:.2f}–{hi:.2f}); no other factor passes {most:.2f}.",
                               factor=html.escape(named[f].lower()), lo=lo, hi=hi, most=max(abs(x) for x in rest))
                            if rest else
                            tr("With the other factors equal, <i>{factor}</i> still goes with a weaker grade for every "
                               "scholar (ρ {lo:.2f}–{hi:.2f}); nothing else holds.",
                               factor=html.escape(named[f].lower()), lo=lo, hi=hi))
            elif best:
                headline = tr("With the other factors equal: {each}.", each="; ".join(
                    tr("for {grader}, <i>{factor}</i> (ρ {rho:.2f})", grader=html.escape(g),
                       factor=html.escape(named[f].lower()), rho=v) for g, (v, f) in best.items()))
            else:
                headline = tr("With the other factors equal, no factor of the chain goes with the grades beyond chance.")
            self._lab_finding(
                tr("What goes with a weaker grade"), headline,
                [HeatMap(rows, shown, cells, -0.5, 0.5, diverging=True, cell=QSize(84, 50), label_w=190, tips=tips,
                         head_h=60)],
                tr("Each row is a scholar's grade of the hadith ({scale}: a higher rank is a weaker grade), the last "
                  "row how far the scholars are apart on it; each column a factor of the hadith's best chain. The "
                  "figure is the PARTIAL Spearman ρ: the relation left when every other factor is held equal, so a "
                  "long chain is not credited with what its weak narrator does. Below it, the plain ρ, nothing held "
                  "equal. Blue: a weaker grade with more of the factor; gold: a stronger one. Outlined: could be "
                  "chance (BH q ≥ 0.05). It is the rank counterpart of the hadith model, and does not assume its "
                  "shape.", scale=self._words()['scale']),
                (["outcome", "factor", "rho alone", "rho others equal", "n", "q"], lab.adjusted_table(m)))
        # 2. the factors among themselves
        fm = {"names": factors, "cells": [row[:k] for row in m["cells"][:k]], "partial": m.get("partial")}
        pairs = lab.pairs_table(fm, "partial") or lab.pairs_table(fm)
        if pairs:
            a, b, rho, _n, _p, _q0 = pairs[0]
            values = dict(a=html.escape(named.get(a, a).lower()), b=html.escape(named.get(b, b).lower()), rho=rho)
            headline = (tr("Of the chain's own factors, <i>{a}</i> and <i>{b}</i> are the most bound together (ρ "
                           "{rho:+.2f}, the others equal).", **values) if fm["partial"] else
                        tr("Of the chain's own factors, <i>{a}</i> and <i>{b}</i> are the most bound together (ρ "
                           "{rho:+.2f}).", **values))
            self._lab_finding(
                tr("The factors with each other"), headline,
                [self._switchable(fm, shown, QSize(84, 46), 190)],
                "<br>".join(f"<b>{html.escape(n)}</b> — {html.escape(tr(e))}" for n, e in zip(shown, m["explain"][:k]))
                + tr("<br><br>Factors that rise together share their credit: the hadith model and the first finding "
                    "hold the others equal for this reason. “The others held equal” shows each pair with the rest "
                    "removed."),
                (["a", "b", "rho alone", "n", "p", "q"], lab.pairs_table(fm)))
        # 3. the scholars against each other
        graders = [n for n in m["names"][k:] if n.startswith("Grade: ")]
        if len(graders) >= 2:
            idx = [m["names"].index(g) for g in graders]
            gm = {"names": [_outcome(g) for g in graders], "cells": [[m["cells"][i][j] for j in idx] for i in idx]}
            widgets = [self._matrix(gm, "cells", gm["names"], QSize(118, 50), 200)]
            if tests:
                table = QTableWidget(0, 5)
                table.setHorizontalHeaderLabels([tr("Scholars"), tr("Same hadith"), tr("First grades higher"), tr("First grades lower"),
                                                 tr("Alike overall?")])
                table.verticalHeader().hide()
                table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
                for t in tests:
                    row = table.rowCount()
                    table.insertRow(row)
                    alike = (tr("no — χ² {chi2:.0f}, {p}", chi2=t["chi2"], p=_q(t["p_holm"]).replace("q", "p"))
                             if t["p_holm"] < lab.ALPHA else tr("cannot tell apart"))
                    for j, v in enumerate([f"{_short(t['a'])} / {_short(t['b'])}", f"{t['n']:,}", f"{t['a_stronger']:,}",
                                           f"{t['a_weaker']:,}", alike]):
                        item = QTableWidgetItem(v)
                        item.setToolTip(tr("Stuart–Maxwell χ² {chi2:.1f} on {df} df; p {p:.2g}, Holm-adjusted {p_holm:.2g}", chi2=t['chi2'], df=t['df'], p=t['p'], p_holm=t['p_holm']))
                        table.setItem(row, j, item)
                table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
                table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
                table.setFixedHeight(len(tests) * 30 + 34)
                widgets.append(table)
                far = max(tests, key=lambda t: abs(t["a_stronger"] - t["a_weaker"]) / t["n"])
                hi, lo = (far["a"], far["b"]) if far["a_stronger"] >= far["a_weaker"] else (far["b"], far["a"])
                more, less = max(far["a_stronger"], far["a_weaker"]), min(far["a_stronger"], far["a_weaker"])
                differ = sum(t["p_holm"] < lab.ALPHA for t in tests)
                values = dict(hi=html.escape(_short(hi)), lo=html.escape(_short(lo)), more=more, less=less)
                headline = (tr("No two scholars grade alike overall: on the same hadith, {hi} grades higher than {lo} "
                               "{more:,} times, lower {less:,}.", **values) if differ == len(tests) else
                            tr("{differ} of {pairs} pairs of scholars do not grade alike overall: on the same hadith, "
                               "{hi} grades higher than {lo} {more:,} times, lower {less:,}.", differ=differ,
                               pairs=len(tests), **values))
            else:
                headline = tr("How closely the scholars' grades follow each other.")
            self._lab_finding(
                tr("Scholar against scholar"), headline, widgets,
                tr("The matrix: Spearman's ρ between two scholars' grades of the same hadith — how far one's order of "
                  "the hadith follows the other's. The table asks another question: even when they rank the hadith "
                  "alike, does one give stronger grades overall? Stuart–Maxwell's test compares the two "
                  "distributions of grades on the same hadith (paired, so the hadith each graded do not differ); "
                  "“no” means one is milder beyond chance (Holm-adjusted over the pairs). The counts are the hadith "
                  "the first scholar grades higher or lower."),
                (["book", "a", "b", "hadith", "a grades higher", "a grades lower", "chi2", "df", "p", "p holm"],
                 [[t["book"], t["a"], t["b"], t["n"], t["a_stronger"], t["a_weaker"], round(t["chi2"], 3), t["df"], t["p"],
                   t["p_holm"]] for t in tests]))

    def _lab_brant(self, tests: list[dict]) -> None:
        """Brant's test of the hadith model: does each factor weigh the same at every step of the grades?"""
        if not tests:
            return
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels([tr("Scholar"), tr("Factor"), tr("Odds ratio at each step"),
                                         tr("Same at every step?")])
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        csv_rows, broken = [], []
        for b in tests:
            steps = [f"{_grade(b['labels'][j])} | {_grade(b['labels'][j + 1])}" for j in b["thresholds"]]
            o = b["overall"]
            shown = [(tr("all factors together"), None, o)] + [(_factor(f["name"]), f["slopes"], f) for f in b["factors"]
                                                               if f["p_holm"] < lab.ALPHA]
            for name, slopes, t in shown:
                row = table.rowCount()
                table.insertRow(row)
                p_ = t.get("p_holm", t["p"])
                same = tr("no — {p}", p=_q(p_).replace("q", "p")) if p_ < lab.ALPHA else tr("yes, within chance")
                for j, v in enumerate([_short(b["grader"]), name,
                                       " → ".join(f"{math.exp(x):.2f}" for x in slopes) if slopes else "",
                                       same]):
                    item = QTableWidgetItem(v)
                    item.setToolTip(tr("Steps: {steps}", steps=" ; ".join(steps))
                                    + f"\nWald χ² {t['chi2']:.1f} · df {t['df']} · p {t['p']:.2g}"
                                    + ("" if len(b["thresholds"]) == b["of"] else "\n" + tr(
                                        "{n} step(s) left out: a factor never seen beyond them",
                                        n=b["of"] - len(b["thresholds"]))))
                    table.setItem(row, j, item)
            broken += [(b["grader"], f["name"]) for f in b["factors"] if f["p_holm"] < lab.ALPHA]
            csv_rows += [[b["book"], b["grader"], f["name"], f["chi2"], f["df"], f["p"], f["p_holm"],
                          " ".join(f"{math.exp(x):.4f}" for x in f["slopes"])] for f in b["factors"]]
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.setFixedHeight(min(14, table.rowCount()) * 30 + 34)
        if broken:
            def say(n: str) -> str:
                return (tr("a weakest narrator who is {level}", level=tr(n[len("Weakest: "):]).lower())
                        if n.startswith("Weakest: ") else tr(n).lower())
            names = sorted({f for _g, f in broken})
            who = sorted({_short(g) for g, _f in broken})
            what = (", ".join(f"<i>{html.escape(say(n))}</i>" for n in names) if len(names) <= 3 else
                    tr("{n} factors (the table)", n=len(names)))
            headline = tr("The hadith model gives each factor one weight for every step of the grades; for {who}, "
                          "{what} weigh differently from step to step.", who=", ".join(html.escape(w) for w in who),
                          what=what)
        else:
            headline = tr("The hadith model's shape holds: each factor weighs the same at every step of the grades.")
        self._lab_finding(
            tr("Does the model's shape hold?"), headline, [table],
            tr("The hadith model (an ordinal, proportional-odds regression) gives each factor ONE weight for "
              "every step of the grades — from sahih to hasan as from hasan to da'if. Brant's test fits each "
              "step on its own and asks whether the weights differ beyond chance (Wald χ², Holm-adjusted over "
              "the factors). Where they do, the odds ratios at each step show how: a factor that weighs more at "
              "the later step decides between hasan and da'if more than between sahih and hasan. The model's "
              "odds ratio is then an average of the steps, still telling the direction. A step a factor never "
              "reaches cannot be estimated and is left out."),
            (["book", "scholar", "factor", "chi2", "df", "p", "p holm", "odds ratio at each step"], csv_rows))

    def _lab_narrators(self, m: dict) -> None:
        names = m["names"]
        shown = [tr(n) for n in names]
        rank = self._words()["rank"]
        cell = (m["cells"][names.index(rank)][names.index("Times in the chains")]
                if rank in names and "Times in the chains" in names else None)
        if cell and cell.get("rho") is not None and cell.get("q", 1) < lab.ALPHA:
            headline = (tr("The narrators the chains use most are the stronger ones (ρ {rho:+.2f} between {rank} and how "
                           "often they appear).", rho=cell["rho"], rank=self._words()["rank_shown"]) if cell["rho"] < 0 else
                        tr("The narrators the chains use most are the weaker ones (ρ {rho:+.2f} between {rank} and how "
                           "often they appear).", rho=cell["rho"], rank=self._words()["rank_shown"]))
        else:
            a, b, rho, *_rest = lab.pairs_table(m)[0]
            headline = tr("Among the narrators, {a} and {b} go together most (ρ {rho:+.2f}).", a=html.escape(tr(a).lower()),
                          b=html.escape(tr(b).lower()), rho=rho)
        self._finding(
            "lab", tr("The narrators' measures"), headline,
            [_label(tr("{people:,} narrators identified in the chains; {complete:,} with every measure known (the partial "
                      "view uses only these).", people=m['people'], complete=m['complete']), "Caption"),
             self._switchable(m, shown, QSize(84, 46), 180)],
            "<br>".join(f"<b>{html.escape(n)}</b>{' — ' + html.escape(tr(e)) if e else ''}" for n, e in zip(shown, m["explain"]))
            + (tr("<br><br>al-Najashi's category runs from trustworthy (1) to weak (4), so a NEGATIVE ρ with it "
                 "means the more of the other, the stronger the narrator. His Rijal gives no generations (tabaqat), "
                 "so there is no generation here.") if self._shia() else
               tr("<br><br>Rank runs from the Companions (1) to the liars (12), so a NEGATIVE ρ with it means the "
                 "more of the other, the stronger the narrator. Generation and year of death move together by their "
                 "nature; held equal, each shows what the other does not.")),
            (["a", "b", "rho alone", "n", "p", "q"], lab.pairs_table(m)))

    def _lab_books(self, comparisons: list[dict]) -> None:
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels([tr("Measure"), tr("Kruskal–Wallis"), tr("Effect (ε²)"), tr("Pairs that differ"),
                                         tr("Furthest apart (Cliff's δ)")])
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        rows = []
        strongest = None
        for c in comparisons:
            kw = c["kruskal"]
            if not kw:
                continue
            far = max(c["pairs"], key=lambda p: abs(p["delta"])) if c["pairs"] else None
            if far and far["p_holm"] < lab.ALPHA and (strongest is None or abs(far["delta"]) > abs(strongest[1]["delta"])):
                strongest = (c["measure"], far)
            differ = sum(p["p_holm"] < lab.ALPHA for p in c["pairs"])
            row = table.rowCount()
            table.insertRow(row)
            for j, v in enumerate([tr(c["measure"]), f"H {kw['H']:.1f}, {_q(kw['p']).replace('q', 'p')}",
                                   f"{kw['epsilon2']:.3f}", tr("{n} of {total}", n=differ, total=len(c["pairs"])),
                                   f"{far['delta']:+.2f}  ({far['a']} / {far['b']})" if far else "—"]):
                table.setItem(row, j, QTableWidgetItem(v))
            for p in c["pairs"]:
                rows.append([c["measure"], p["a"], p["b"], p["U"], p["z"], p["p"], p["p_holm"], p["delta"]])
        if not table.rowCount():
            return
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setFixedHeight(table.rowCount() * 30 + 34)
        if strongest:
            m_, p = strongest
            headline = tr("The books differ most in {measure}: {a} against {b}, Cliff's δ {delta:+.2f}.",
                          measure=html.escape(tr(m_).lower()), a=html.escape(p["a"]), b=html.escape(p["b"]),
                          delta=p["delta"])
        else:
            headline = tr("The books' chains cannot be told apart in {measures}.", measures=", ".join(
                html.escape(tr(c["measure"]).lower()) for c in comparisons if c["kruskal"]))
        self._finding(
            "lab", tr("Are the books different?"), headline, [table],
            tr("Kruskal–Wallis asks whether the books' chains could come from one distribution (ε² is its size: "
              "0.01 small, 0.06 medium, 0.14 large). Mann–Whitney compares each pair, Holm-adjusted; Cliff's δ "
              "is how often a chain of the first book is above one of the second minus how often it is below (−1 "
              "… +1).") + " "
            + (tr("Weakest narrator: al-Najashi's category, higher is weaker.") if self._shia() else
               tr("Weakest narrator: Ibn Hajar's rank group, higher is weaker.")),
            (["measure", "a", "b", "U", "z", "p", "p holm", "cliffs delta"], rows))

    def _books(self, r: dict) -> None:
        b = r["books"]
        rows = b["rows"]
        table = QTableWidget(len(rows), 6)
        table.setHorizontalHeaderLabels([tr("Book"), tr("Chains"), tr("Median length"), tr("Names identified"),
                                         self._words()["reach"], tr("Narrators")])
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for i, row in enumerate(rows):
            for j, v in enumerate([row["name"], f"{row['chains']:,}", str(row["median_length"] or "—"),
                                   _pct(row["identified"]), _pct(row["reaching"]), f"{row['narrators']:,}"]):
                table.setItem(i, j, QTableWidgetItem(v))
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)       # the title takes the room that is left
        table.setFixedHeight(len(rows) * 30 + 34)
        cats = self._group_categories(r)
        self._finding("books", tr("The books side by side"), tr("Each book's chains and the narrators they rest on."),
                      [table, StackedBars([(row["name"], row["groups"]) for row in rows], cats, label_w=230)],
                      tr("The table compares the books' chains; the bars, the narrators each book's chains pass through, "
                        "each counted as often as he appears."),
                      (["book", "chains", "median length", "identified", self._words()["reach"].lower(), "narrators"]
                       + [c[0] for c in cats],
                       [[row["name"], row["chains"], row["median_length"], round(row["identified"], 4),
                         round(row["reaching"], 4), row["narrators"]] + list(row["groups"]) for row in rows]))
        if len(b["names"]) > 1:
            cells = [[(None, []) if i == j else (v, [f"{100 * v:.0f}%"]) for j, v in enumerate(row)]
                     for i, row in enumerate(b["overlap"])]
            self._finding("books", tr("Shared narrators"), tr("How many narrators each pair of books shares."),
                          # the cells shrink with the number of books, so the map fits the page (96 px each was 1,200 px
                          # wide for ten books and cut the whole section off on the right)
                          [HeatMap(b["names"], b["names"], cells, cell=QSize(max(48, min(96, 640 // len(b["names"]))), 40),
                                   label_w=200)],
                          tr("The Jaccard share: narrators found in both books' chains, out of those found in either. Books of "
                            "one school and one period share most."),
                          ([""] + b["names"], [[name] + [round(v, 4) for v in row] for name, row in zip(b["names"], b["overlap"])]))

    # ------------------------------------------------------------------ the graders section (ST7, first tab)
    def _graders_section(self) -> QWidget:
        graders = QWidget()
        gl = QVBoxLayout(graders)
        gl.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        # ONE choice of book for the whole page: this list follows "Books" above and moves it in turn (a book chosen
        # here and another one above showed two different books at once — Bayram, 2026-10-11)
        self.book_title = _label(tr("Book (two or more graders)"), "FilterTitle")
        bar.addWidget(self.book_title)
        self.book = QComboBox()
        self.book.setObjectName("FilterCombo")
        self.book.currentIndexChanged.connect(self._grader_book_changed)
        bar.addWidget(self.book)
        self.recompute = QPushButton(tr("Recompute graders"))
        self.recompute.setObjectName("Quiet")
        self.recompute.setToolTip(tr("The graders' results are kept in a file and reused while the grades are unchanged"))
        self.recompute.clicked.connect(lambda: self.compute(True))
        bar.addWidget(self.recompute)
        self.status = _label("", "Caption")
        bar.addWidget(self.status, 1)
        gl.addLayout(bar)
        self.body = QWidget()
        self.body.setObjectName("Page")
        self.box = QVBoxLayout(self.body)
        self.box.setContentsMargins(0, 6, 8, 16)
        self.box.setSpacing(14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.body)
        gl.addWidget(scroll, 1)
        return graders

    def _card(self, title: str = "") -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(22, 16, 22, 16)
        lay.setSpacing(8)
        if title:
            h = _label(title, "CardTitle")
            h.setFont(theme.reading_font(15, bold=True))
            lay.addWidget(h)
        return card

    def _how(self, text: str) -> QLabel:
        return _label(tr("<b>How to read it</b> — ") + text, "Caption", rich=True)

    def _grader_books(self) -> list[tuple[str, str, int]]:
        """The books with two or more graders, in reading order — each on its own road: a Sunni book on the Sunni
        grade groups, a Shia book on the four Imami categories (SH1)."""
        from isnady.core import books as core_books

        conn = self.conn
        counts = {k: n for k, _name, n in core.books_with_grades(conn)}
        return [(b["key"], b["name"], counts[b["key"]]) for b in core_books.all_books(conn)
                if counts.get(b["key"], 0) >= 2]

    def _refresh_graders(self) -> None:
        books = self._grader_books()
        current = self.book.currentData()
        self.book.blockSignals(True)
        self.book.clear()
        for key, name, n in books:
            self.book.addItem(tr("{name} — {n} graders", name=name, n=n), key)
        self.book.setCurrentIndex(max(0, self.book.findData(current)))
        self.book.blockSignals(False)
        self._follow_scope()

    def _scope_changed(self, _index: int = 0) -> None:
        self.compute_corpus(False)
        self._follow_scope()

    def _follow_scope(self) -> None:
        """Show in Graders the book chosen above; or say why it has none to show."""
        scope = self.scope.currentData()
        books = self._grader_books()
        keys = [k for k, _n, _c in books]
        name = self.scope.currentText().split(" (")[0]
        message = None
        if scope in (None, corpus.SHIA_SCOPE) and books:
            # "all books": the graders are compared book by book — the first such book of this road, or a word
            road = "shia" if scope == corpus.SHIA_SCOPE else "sunni"
            mine = [(k, n) for k, n, _c in books if corpus.tradition_of_scope(self.conn, k) == road]
            if not mine:
                message = tr("No book of this road has two graders to compare. The books that have: {books}.",
                             books=", ".join(n for _k, n, _c in books))
            elif self.book.currentData() not in [k for k, _n in mine]:
                self.book.blockSignals(True)
                self.book.setCurrentIndex(self.book.findData(mine[0][0]))
                self.book.blockSignals(False)
        elif scope and scope not in keys:
            message = tr("{name} has no two graders to compare. The books that have: {books}.", name=name,
                         books=", ".join(n for _k, n, _c in books) or tr("none imported yet"))
        elif not books:
            message = tr("No grades yet: import a collection with graded hadith (Data Sources).")
        self.book.setVisible(message is None)
        self.book_title.setVisible(message is None)
        self.recompute.setVisible(message is None)
        if message:
            self._clear()
            self.status.setText("")
            self.box.addWidget(_label(message, "Lead"))
            self.box.addStretch(1)
            return
        if scope and scope != corpus.SHIA_SCOPE and self.book.currentData() != scope:
            self.book.blockSignals(True)
            self.book.setCurrentIndex(self.book.findData(scope))
            self.book.blockSignals(False)
        self.compute(False)

    def _grader_book_changed(self, _index: int) -> None:
        """A book chosen here is the book of the whole page: "Books" above follows it."""
        key = self.book.currentData()
        if key and self.scope.currentData() != key:
            i = self.scope.findData(key)
            if i >= 0:
                self.scope.setCurrentIndex(i)        # → _scope_changed → corpus of that book, Graders shows it
                return
        self.compute(False)

    def compute(self, recompute: bool) -> None:
        key = self.book.currentData()
        if not key or (self._gthread is not None and self._gthread.isRunning()):
            return
        self.status.setText(tr("Reading the saved results…") if not recompute else tr("Computing…"))
        self.recompute.setEnabled(False)
        self._gthread = QThread(self)
        self._worker = _Worker(core.cached, key, recompute)
        self._worker.moveToThread(self._gthread)
        self._gthread.started.connect(self._worker.run)
        self._worker.progress.connect(lambda m: self.status.setText(m + "…"))
        self._worker.done.connect(self._keep_and_show)
        self._worker.failed.connect(lambda m: self.status.setText(tr("Could not compute: {error}", error=m)))
        for sig in (self._worker.done, self._worker.failed):
            sig.connect(self._gthread.quit)
        self._gthread.finished.connect(lambda: self.recompute.setEnabled(True))
        self._gthread.start()

    def _keep_and_show(self, r: dict) -> None:
        self._gresult = r
        self._show(r)

    def _clear(self) -> None:
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    # ------------------------------------------------------------------ the graders (the first tab of ST7)
    def _show(self, r: dict) -> None:
        self._clear()
        graders = r["graders"]
        names = [_short(g) for g in graders]
        labels = [tr(x) for x in (r.get("labels") or core.LABELS)]
        order = list(reversed(r.get("categories") or range(core.K)))     # strongest first: sahih …
        shia = r.get("tradition") == "shia"
        self.status.setText((tr("From the saved results ({file}).", file=r["from_file"]) if r.get("from_file")
                             else tr("Computed and saved.")) + " "
                            + tr("Intervals: {boot} bootstrap samples of hadith.", boot=r["boot"]))
        if shia:
            self.box.addWidget(_label(
                tr("Road B: the graders of a Shia book compared on the four Imami categories — sahih, hasan, "
                  "muwaththaq, da'if — in their own order, never on the Sunni grade groups."), "Caption"))
        few = r.get("too_few") or {}
        if few:
            self.box.addWidget(_label(tr("Named, not measured — too few grades of this book to compare: {graders}.",
                                         graders=", ".join(f"{_short(g)} ({n})" for g, n in few.items())), "Caption"))
        for sel in r.get("selections", []):
            self._selection_card(sel, labels, order)
        if len(graders) < 2:
            if not r.get("selections"):
                card = self._card(tr("One grader only"))
                card.layout().addWidget(_label(tr("{grader} graded this book; agreement and the model need two or more. "
                                                  "His grades:", grader=names[0] if names else "—"), "Lead"))
                dist = r["distribution"].get(graders[0], []) if graders else []
                card.layout().addWidget(_label(" · ".join(f"{labels[k]} {dist[k]:,}" for k in order if k < len(dist)),
                                               "Lead"))
                self.box.addWidget(card)
            elif graders:
                card = self._card(tr("No second grader to measure against"))
                card.layout().addWidget(_label(
                    tr("Besides the selection above, only {grader} grades this book in more than one grade, so "
                       "agreement beyond chance, strictness and the model of the true grade (which need two graders who "
                       "could each have said otherwise) cannot be measured here. His grades: {grades}.", grader=names[0],
                       grades=" · ".join(f"{labels[k]} {r['distribution'][graders[0]][k]:,}" for k in order)), "Lead"))
                self.box.addWidget(card)
            self.box.addStretch(1)
            return
        t = theme.current()
        # 1 — the whole picture
        a = r["alpha"]
        c = r["certainty"]
        card = self._card(tr("All graders together"))
        card.layout().addWidget(_label(
            tr("<b>Krippendorff's alpha {alpha:.3f}</b> (95% interval {lo:.3f}–{hi:.3f}) over {units:,} "
               "hadith graded by two or more — {words}.<br>The model is sure (≥95%) of the true grade of "
               "<b>{high:,}</b> hadith ({high_share:.1f}%), fairly sure of {middle:,}, and unsure (<60%) of "
               "<b>{low:,}</b> ({low_share:.1f}%).", alpha=a["value"], lo=a["ci"][0], hi=a["ci"][1], units=a["units"],
               words=self._alpha_words(a["value"]), high=c["high"], high_share=100 * c["high"] / c["total"],
               middle=c["middle"], low=c["low"], low_share=100 * c["low"] / c["total"]),
            "Lead", rich=True))
        left = {g: n for g, n in r.get("chain_only", {}).items() if n}
        if left:
            card.layout().addWidget(_label(
                tr("Grades of the <b>chain only</b> (\"Isnaad Sahih\": the chain is sound, the text is not judged) "
                   "answer another question than a grade of the hadith, so they are left out of every comparison "
                   "here: {graders}.", graders=", ".join(f"{html.escape(_short(g))} {n:,}" for g, n in
                                                          sorted(left.items(), key=lambda kv: -kv[1]))),
                "Caption", rich=True))
        for ov in r.get("one_voice", []):
            warn = _label(tr("⚠ {kept} and {left_out} agree on {value:.1f}% — too often for two scholars grading on their own; "
                            "the source probably filled one column from the other. In the model they are one voice ({kept}); "
                            "{left_out} is measured against the model's result without moving it.", kept=_short(ov['kept']), left_out=_short(ov['left_out']), value=100 * ov['agree']), "Caption")
            warn.setStyleSheet(f"color: {t.gold};")
            card.layout().addWidget(warn)
        card.layout().addWidget(self._how(
            tr("alpha measures agreement beyond chance for all graders at once, by the order of the grades (a "
              "near miss counts less than a far one): 1 is complete agreement, 0 no better than chance; above "
              "0.8 is strong, 0.67–0.8 allows tentative conclusions, below 0.67 is weak.")))
        self.box.addWidget(card)
        # 2 — agreement heat maps
        card = self._card(tr("Agreement between each pair of graders"))
        def matrix(field, fmt, ci_fmt):
            cells = []
            for i, ga in enumerate(graders):
                row = []
                for j, gb in enumerate(graders):
                    if i == j:
                        row.append((None, []))
                        continue
                    p = r["pairs"].get(f"{ga}|{gb}") or r["pairs"].get(f"{gb}|{ga}")
                    if not p:
                        row.append((None, []))
                        continue
                    lo, hi = p["ci"][field]
                    row.append((p[field], [fmt(p[field]), ci_fmt(lo, hi) + f" · n {p['common']:,}"]))
                cells.append(row)
            return cells
        # one under the other: side by side they are wider than the page
        card.layout().addWidget(_label(tr("<b>Same grade</b>"), "Lead", rich=True))
        card.layout().addWidget(HeatMap(names, names, matrix("agree", lambda v: f"{100 * v:.1f}%",
                                                             lambda a, b: f"{100 * a:.1f}–{100 * b:.1f}"), low=0.5, high=1.0,
                                        label_w=210))
        card.layout().addWidget(_label(tr("<b>Ordinal (weighted) kappa</b>"), "Lead", rich=True))
        card.layout().addWidget(HeatMap(names, names, matrix("wkappa", lambda v: f"κw {v:.2f}", lambda a, b: f"{a:.2f}–{b:.2f}"),
                                        low=0.0, high=1.0, label_w=210))
        card.layout().addWidget(self._how(
            tr("each cell compares the row's grader with the column's on the hadith both graded (n). Left: how "
              "often they give the same grade. Right: Cohen's kappa weighted by order — agreement beyond chance, "
              "where calling a hasan hadith da'if is a smaller disagreement than calling it fabricated. The "
              "small figures are 95% intervals.")))
        self.box.addWidget(card)
        # 3 — strictness
        card = self._card(tr("Strictness — mutashaddid and mutasahil, measured"))
        rows = [(n, r["model"]["strictness"][g]["value"], tuple(r["model"]["strictness"][g]["ci"])) for n, g in zip(names, graders)]
        rows.sort(key=lambda x: x[1])
        card.layout().addWidget(IntervalPlot(rows, tr("stricter (mutashaddid)"), tr("more lenient (mutasahil)")))
        pair_cells = []
        for i, ga in enumerate(graders):
            row = []
            for j, gb in enumerate(graders):
                p = r["pairs"].get(f"{ga}|{gb}")
                sign = 1
                if p is None:
                    p, sign = r["pairs"].get(f"{gb}|{ga}"), -1
                if i == j or not p:
                    row.append((None, []))
                    continue
                v = -sign * p["order"]                 # positive: the row's grader grades HIGHER than the column's
                lo, hi = sorted((-sign * p["ci"]["order"][0], -sign * p["ci"]["order"][1]))
                row.append((v, [f"{v:+.3f}", f"{lo:+.3f} … {hi:+.3f}"]))
            pair_cells.append(row)
        card.layout().addWidget(_label(tr("<b>Pair by pair</b>: P(row grades higher) − P(row grades lower)"), "Lead", rich=True))
        card.layout().addWidget(HeatMap(names, names, pair_cells, low=-0.25, high=0.25, diverging=True, label_w=210))
        card.layout().addWidget(self._how(
            tr("from the model: the chance a grader gives a hadith a LOWER grade than its true grade, minus the "
              "chance he gives it a HIGHER one — by order only. Below zero (gold) he is stricter, above zero "
              "(blue) more lenient; the line is the 95% interval. The 'true grade' is what these graders' grades "
              "imply together, so the measure is relative to them, not absolute. Pair by pair needs no model: "
              "who grades the same hadith higher, who lower.")))
        self.box.addWidget(card)
        # 4 — confusion matrices
        card = self._card(tr("How each grader grades a hadith of each true grade (the model's confusion matrices)"))
        few_all = {k for k in order if r["model"]["prior"][k] * r["certainty"]["total"] < 15}
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        for n, (g, name) in enumerate(zip(graders, names)):
            th = r["model"]["theta"][g]
            # a true grade the model finds (almost) no hadith of has no row to measure: left out, and named below
            rows_k = [k for k in order if k not in few_all]
            cells = [[(th[k][l], [f"{100 * th[k][l]:.0f}%"]) for l in order] for k in rows_k]
            grid.addWidget(_label(f"<b>{html.escape(name)}</b>", "Lead", rich=True), (n // 2) * 2, n % 2)
            grid.addWidget(HeatMap([labels[k] for k in rows_k], [labels[k] for k in order], cells,
                                   cell=QSize(62, 28), label_w=86), (n // 2) * 2 + 1, n % 2)
        grid.setColumnStretch(2, 1)
        card.layout().addLayout(grid)
        prior = r["model"]["prior"]
        card.layout().addWidget(_label(tr("How common each true grade is, by the model: {shares}.", shares=" · ".join(
            f"{labels[k]} {100 * prior[k]:.1f}%" for k in order))
            + ("" if not few_all else " " + tr("No row for {grades}: too few hadith of that true grade to measure how a "
                                               "grader treats it.", grades=", ".join(labels[k] for k in order
                                                                                    if k in few_all))), "Lead"))
        card.layout().addWidget(self._how(
            tr("rows are the true grade, columns what the grader says. A strong diagonal is a grader who sees the "
              "grade the others see; weight to the right of it (towards weaker grades) is strictness, to the "
              "left leniency. This is the Dawid–Skene model: it learns each grader's matrix and the true grades "
              "together.")))
        self.box.addWidget(card)
        # 5 — disputed hadith
        self._disputed(r, graders, labels)
        self.box.addStretch(1)

    def _selection_card(self, sel: dict, labels: list[str], order: list[int]) -> None:
        """A grader who gives one grade only (a selection, as al-Behbudi's Sahih al-Kafi) beside each other grader."""
        who, grade = _short(sel["grader"]), labels[sel["grade"]]
        card = self._card(tr("{who}'s selection — {count:,} hadith, all {grade}", who=who, count=sel['count'], grade=grade))
        if not sel["others"]:
            card.layout().addWidget(_label(tr("No other grader graded the hadith {who} selected.", who=who), "Lead"))
        for o, x in sel["others"].items():
            dist = x["distribution"]
            same = dist[sel["grade"]] / x["common"] if x["common"] else 0
            card.layout().addWidget(_label(
                tr("Of the <b>{common:,}</b> hadith {who} holds {grade} that {o} grades too, {o} calls <b>{same}</b> "
                  "{grade}.", common=x['common'], who=html.escape(who), grade=html.escape(grade), o=html.escape(_short(o)), same=_pct(same)), "Lead", rich=True))
            rows = [(tr("{other} on {who}'s {grade}", other=_short(o), who=who, grade=grade), [dist[k] for k in order])]
            colors = (IMAMI_GRADE_COLORS if len(order) == 4 else GRADE_COLORS)[theme.current().dark]
            card.layout().addWidget(StackedBars(rows, list(zip([labels[k] for k in order], colors)), label_w=260))
        card.layout().addWidget(self._how(
            tr("{who} names only the hadith he holds {grade}: a selection, not a grading of every hadith, so he "
              "never says anything else and agreement beyond chance (kappa, alpha) or a strictness cannot be "
              "measured for him. What can be measured is how the other graders grade the hadith he selected. The "
              "two need not differ in method only: they may read a narrator differently, or grade different "
              "versions of the chain.", who=who, grade=grade)))
        self.box.addWidget(card)

    def _disputed(self, r: dict, graders: list[str], labels: list[str]) -> None:
        """The hadith the graders are furthest apart on. Every cell says what it is: a grade, or "not graded"."""
        t = theme.current()
        voices = {o["left_out"]: o["kept"] for o in r.get("one_voice", [])}
        card = self._card(tr("The disputed hadith — {disputed_total:,} where the graders are two steps apart or the model is "
                            "unsure", disputed_total=r['disputed_total']))
        table = QTableWidget(0, 4 + len(graders))
        heads = [tr("Hadith"), tr("Model's grade"), tr("Certainty"), tr("Voices weighed")] + [
            _short(g) + (" ≈" if g in voices else "") for g in graders]
        table.setHorizontalHeaderLabels(heads)
        for j, g in enumerate(graders):
            tip = _full(g) + ("\n" + tr("≈ one voice with {other} in the model (they agree too often to count twice): "
                                         "his grade is shown, but does not move the model's grade",
                                         other=_short(voices[g])) if g in voices else "")
            table.horizontalHeaderItem(4 + j).setToolTip(tip)
        table.horizontalHeaderItem(2).setToolTip(tr("The model's probability for its grade"))
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        csv_rows = []
        for d in r["disputed"][:150]:
            row = table.rowCount()
            table.insertRow(row)
            item = QTableWidgetItem(str(d.get("number") or d["hadith_id"]))
            item.setData(Qt.ItemDataRole.UserRole, d["hadith_id"])
            table.setItem(row, 0, item)
            given = {g: d["grades"].get(g) for g in graders}
            voted = [g for g in graders if given[g] is not None and g not in voices]
            # why the model is unsure, in words: the voices it weighs and what they say
            why = ", ".join(f"{_short(g)} {labels[given[g]]}" for g in voted)
            model = QTableWidgetItem(labels[d["consensus"]])
            model.setToolTip(tr("The voices the model weighs on this hadith: {why}.", why=why) + "\n"
                             + (tr("One voice against one: the model sides with the grader it finds closer to the others over the "
                                  "whole book, so its certainty is modest.") if len(voted) == 2 and
                                len({given[g] for g in voted}) == 2 else
                                tr("The model's grade is the grade these voices most probably mean, given how each grades the whole "
                                  "book.")))
            table.setItem(row, 1, model)
            cert = QTableWidgetItem(f"{100 * d['certainty']:.0f}%")
            cert.setToolTip(model.toolTip())
            table.setItem(row, 2, cert)
            tally = Counter(given[g] for g in voted)
            voices_item = QTableWidgetItem(" · ".join(f"{labels[k]} {n}" for k, n in
                                                      sorted(tally.items(), key=lambda kv: -kv[0])))
            voices_item.setToolTip(model.toolTip())
            table.setItem(row, 3, voices_item)
            for j, g in enumerate(graders):
                v = given[g]
                cell = QTableWidgetItem(labels[v] if v is not None else tr("not graded"))
                if v is None:
                    cell.setForeground(QColor(t.muted))
                    cell.setToolTip(tr("{grader} gives no grade of this hadith (or a grade of its chain only)",
                                       grader=_short(g)))
                elif g in voices:
                    cell.setForeground(QColor(t.muted))
                    cell.setToolTip(tr("One voice with {other}: shown, not weighed", other=_short(voices[g])))
                table.setItem(row, 4 + j, cell)
            csv_rows.append([d.get("number") or d["hadith_id"], labels[d["consensus"]], round(d["certainty"], 4)]
                            + [labels[given[g]] if given[g] is not None else "" for g in graders])
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        table.setMinimumHeight(360)
        table.cellDoubleClicked.connect(lambda rr, _c: self.open_hadith.emit(table.item(rr, 0).data(Qt.ItemDataRole.UserRole)))
        card.layout().addWidget(table)
        same = [f"{_short(k)} ≈ {_short(v)}" for k, v in voices.items()]
        card.layout().addWidget(self._how(
            tr("the hadith where the scholars are furthest apart come first. <i>Certainty</i> is the model's "
              "probability for its grade: where only two voices weigh and they disagree, it sits a little above "
              "one half — the model sides with the grader it finds closer to the others over the whole book, "
              "which is why many such rows show the same figure. Near 100% against a dissent means the "
              "dissenting grade is one that grader gives, over the whole book, to hadith the others place "
              "elsewhere — the model holds it to be his own reading, not the grade. <i>Voices weighed</i>: the "
              "grades the model counts. <i>not graded</i>: that scholar gave no grade of the hadith (or graded "
              "its chain only).") + " "
            + (tr("≈ marks a grader who is one voice with another in the model ({same}): his grade is shown, muted, "
                  "but not weighed.", same=", ".join(same)) + " " if same else "")
            + tr("Hover a cell for the details; double-click a row to read the hadith in its book.")))
        self.box.addWidget(card)

    @staticmethod
    def _alpha_words(a: float) -> str:
        return (tr("strong agreement") if a >= 0.8 else tr("enough agreement for tentative conclusions") if a >= 0.667
                else tr("weak agreement"))
