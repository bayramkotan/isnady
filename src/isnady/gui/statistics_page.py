"""Statistics (ST7, deep): the imported corpus measured — the narrators, the chains, the grades against the chains,
the books, and the graders of each book.

One section at a time, chosen on the left. Each section is a few FINDINGS: a sentence that says what the numbers
show, the chart that shows it, the figures behind it on hover, and — folded until asked for — how to read it and
how it was measured; every finding can be saved as CSV for a thesis or a paper. The numbers are computed once in the
background and kept (core.stats_corpus, core.stats_graders); ranks and grades are ordered categories throughout:
counted, cross-tabulated and rank-correlated, never averaged (SK).
"""

import csv
import html
import math

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
from isnady.core import stats_models as models
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
    """The two analyses of the corpus sections, in one background run: the descriptive one and the model."""
    return {"corpus": corpus.cached(conn, key, progress, recompute), "models": models.cached(conn, key, progress, recompute)}

SECTIONS = [
    ("overview", "Overview", "the corpus at a glance"),
    ("narrators", "Narrators", "who carries the hadith"),
    ("chains", "Chains", "length, weakest link, time"),
    ("grades", "Grades and chains", "do the chains explain the grades"),
    ("model", "The hadith model", "what a scholar's grade follows"),
    ("books", "Books", "the books compared"),
    ("graders", "Graders", "the scholars who graded"),
]
# Ranks and grades are ordered AND two-sided (accepted ↔ rejected): a diverging scale, blue for the accepted side, red
# for the rejected, the neutral grey in the middle for "acceptable when followed" (maqbul). Lightness grows towards the
# middle on each arm; a legend, the gaps between segments and the hover text carry the identity as well (never colour
# alone). Light and dark steps are chosen each for its own surface.
GROUP_COLORS = {False: ["#1E4A8A", "#3A72B8", "#8DB4DE", "#C9C6C0", "#E4997A", "#B23A33"],
                True: ["#6E9FE0", "#4A7FC4", "#2E5A92", "#55534F", "#B4543F", "#E0705F"]}
GRADE_COLORS = {False: ["#1E4A8A", "#8DB4DE", "#E4997A", "#C8564A", "#8E2A25"],
                True: ["#6E9FE0", "#2E5A92", "#B4543F", "#D86A55", "#F08A75"]}


def _label(text: str, name: str = "", rich: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
    return label


def _short(grader: str) -> str:
    for s in SCHOLARS:
        if grader in s.get("grader_names", []):
            return s["name"]
    return grader


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
        title = _label("Statistics", "CardTitle")
        title.setFont(theme.reading_font(22, bold=True))
        titles.addWidget(title)
        titles.addWidget(_label("The imported books measured: who carries the hadith, how the chains hold, and whether "
                                "they explain the grades.", "Lead"))
        head.addLayout(titles, 1)
        head.addWidget(_label("Books", "FilterTitle"), 0, Qt.AlignmentFlag.AlignBottom)
        self.scope = QComboBox()
        self.scope.setObjectName("FilterCombo")
        self.scope.setMinimumWidth(220)
        self.scope.currentIndexChanged.connect(lambda _i: self.compute_corpus(False))
        head.addWidget(self.scope, 0, Qt.AlignmentFlag.AlignBottom)
        self.c_recompute = QPushButton("Recompute")
        self.c_recompute.setObjectName("Quiet")
        self.c_recompute.setToolTip("The results are kept in a file and reused while the data is unchanged")
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
            item = QListWidgetItem(f"{name}\n{sub}")
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
            toggle = QPushButton("How to read it ▸")
            toggle.setObjectName("Link")
            toggle.setCursor(Qt.CursorShape.PointingHandCursor)

            def flip(_c=False, m=more, b=toggle):
                m.setVisible(not m.isVisible())
                b.setText("How to read it ▾" if m.isVisible() else "How to read it ▸")
            toggle.clicked.connect(flip)
            foot.addWidget(toggle)
        if table:
            save = QPushButton("Save as CSV…")
            save.setObjectName("Link")
            save.setCursor(Qt.CursorShape.PointingHandCursor)
            save.setToolTip("The figures behind this finding, as a table any spreadsheet or statistics program opens")
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
        path, _f = QFileDialog.getSaveFileName(self, "Save as CSV", f"isnady-{safe}.csv", "CSV (*.csv)")
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
        for r in rows:
            rank = r.get("rank")
            facts = [f"rank {rank}: {RANK_LABELS[rank][1]}" if rank in RANK_LABELS else "no rank in the Taqrib"]
            if r.get("tabaqa"):
                facts.append(f"tabaqa {r['tabaqa']}")
            if r.get("death"):
                facts.append(f"d. {r['death']} AH")
            facts.append(f"{r['links']:,} times in the chains, in {r['hadith']:,} hadith")
            items.append({"id": r["id"], "label": self._name(r["id"], r["name"]), "value": value(r),
                          "dot": GROUP_COLORS[theme.current().dark][corpus.GROUP_OF_RANK[rank]] if rank in corpus.GROUP_OF_RANK
                                 else None,
                          "tip": f"{self._name(r['id'], r['name'])}\n{r['name']}\n" + "\n".join(facts)
                                 + "\n\nClick to open him on the Narrators page"})
        bars = PeopleBars(items, unit)
        bars.clicked.connect(self.open_narrator.emit)
        return bars

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

        current = self.scope.currentData()
        self.scope.blockSignals(True)
        self.scope.clear()
        books = core_search.list_collections(conn)
        self.scope.addItem(f"All books ({len(books)})", None)
        for key, name, count in books:
            self.scope.addItem(f"{name} ({count:,})", key)
        self.scope.setCurrentIndex(max(0, self.scope.findData(current)))
        self.scope.blockSignals(False)
        self._names.clear()
        self.compute_corpus(False)
        self._refresh_graders()

    def compute_corpus(self, recompute: bool) -> None:
        if self.conn is None or (self._thread is not None and self._thread.isRunning()):
            return
        self.c_status.setText("Computing…" if recompute else "Reading the saved results…")
        self.c_recompute.setEnabled(False)
        self._thread = QThread(self)
        self._cworker = _Worker(_corpus_and_models, self.scope.currentData(), recompute)
        self._cworker.moveToThread(self._thread)
        self._thread.started.connect(self._cworker.run)
        self._cworker.progress.connect(lambda m: self.c_status.setText(m + "…"))
        self._cworker.done.connect(self._show_corpus)
        self._cworker.failed.connect(lambda m: self.c_status.setText("Could not compute: " + m))
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
                self._boxes[key].addWidget(_label("Nothing to measure yet: import a hadith collection (File → Data "
                                                  "Sources), and a book of narrators (Ibn Hajar's Taqrib) to identify "
                                                  "them.", "Lead"))
                self._boxes[key].addStretch(1)
            self.c_status.setText("")
            return
        self.c_status.setText(
            ("From the saved results — computed once, reused while the data is unchanged." if r.get("from_file")
             else "Computed and saved.") + f" Intervals: {r['boot']} bootstrap samples of hadith.")
        self._overview(r)
        self._narrators(r)
        self._chains(r)
        self._grades(r)
        self._model_section()
        self._books(r)
        for box in self._boxes.values():
            box.addStretch(1)

    def _group_categories(self, r: dict) -> list[tuple[str, str]]:
        return list(zip([name for name, _d in r["groups"]], GROUP_COLORS[theme.current().dark]))

    def _grade_categories(self, r: dict) -> list[tuple[str, str]]:
        return list(zip(r["grade_labels"], GRADE_COLORS[theme.current().dark]))

    def _overview(self, r: dict) -> None:
        o, n = r["overview"], r["narrators"]
        share_id = o["identified"] / o["links"] if o["links"] else 0
        reach = o["reaching"] / o["chains"] if o["chains"] else 0
        tiles = StatTiles([
            ("Hadith", f"{o['hadith']:,}", f"in {o['books']} book{'s' if o['books'] != 1 else ''}"),
            ("Chains read", f"{o['chains']:,}", f"{_pct(reach)} reach the Prophet ﷺ"),
            ("Names identified", _pct(share_id), f"{o['identified']:,} of {o['links']:,} names in the chains"),
            ("Narrators", f"{o['narrators']:,}", "different people identified in the chains"),
        ])
        self._finding("overview", "The corpus", f"{o['hadith']:,} hadith, {o['chains']:,} chains, "
                      f"{o['narrators']:,} narrators identified.", [tiles],
                      "A chain is <b>read</b> when isnady split its text into names; a name is <b>identified</b> when it "
                      "is matched to one person of Ibn Hajar's Taqrib. Everything below rests on the identified names, "
                      "so their share is the first thing to know: the measures describe the identified part.",
                      (["measure", "value"], [["hadith", o["hadith"]], ["books", o["books"]], ["chains", o["chains"]],
                                              ["chains reaching the Prophet", o["reaching"]], ["names in chains", o["links"]],
                                              ["names identified", o["identified"]], ["narrators", o["narrators"]],
                                              ["chains fully identified", o["full"]]]))
        cats = self._group_categories(r)
        strong = (n["rank_links"][0] + n["rank_links"][1]) / (sum(n["rank_links"]) or 1)
        rows = [("All narrators of the Taqrib", n["rank_all"]), ("The narrators in these chains", n["rank_people"]),
                ("Every name in these chains", n["rank_links"])]
        self._finding("overview", "Reliability", f"{_pct(strong)} of all transmission passes through Companions and "
                      "trustworthy narrators — far more than their share of the Taqrib.",
                      [StackedBars(rows, cats)],
                      "Ibn Hajar's twelve ranks in six groups, from Companions to the rejected. The first bar is everyone "
                      "Ibn Hajar judged; the second, the narrators who appear in these chains; the third counts each "
                      "narrator as often as he appears — what the hadith actually rest on. The ranks are ordered "
                      "categories: counted, never averaged.",
                      (["series"] + [c[0] for c in cats], [[label] + list(v) for label, v in rows]))
        if r["grades"]:
            gcats = self._grade_categories(r)
            grows = [(f"{_short(g['grader'])} — {g['book']}", g["distribution"]) for g in r["grades"]]
            self._finding("overview", "Grades", "How each scholar graded each book.", [StackedBars(grows, gcats, label_w=260)],
                          "Each bar is one scholar's grades of one book, in five ordered groups. Grades of the chain alone "
                          "(\"Isnaad Sahih\") are left out: they judge another thing than a grade of the hadith.",
                          (["grader", "book"] + r["grade_labels"],
                           [[_short(g["grader"]), g["book"]] + g["distribution"] for g in r["grades"]]))

    def _narrators(self, r: dict) -> None:
        n = r["narrators"]
        c = n["concentration"]
        if c.get("gini") is not None:
            tiles = StatTiles([("Busiest 1%", _pct(c["top1"]), "of all identified names"),
                               ("Busiest 10%", _pct(c["top10"]), "of all identified names"),
                               ("Half of all names", f"{c['half_by']:,}", f"narrators, of {c['people']:,}"),
                               ("Gini", f"{c['gini']:.2f}", "0 equal shares, 1 one man carries all")])
            self._finding("narrators", "Concentration", f"The busiest 10% of narrators carry {_pct(c['top10'])} of the "
                          f"transmission; {c['half_by']:,} narrators carry half of it.", [tiles, Lorenz(c["curve"])],
                          "The curve sorts the narrators from the least to the most often seen and adds up their share of "
                          "the identified names. The diagonal would be every narrator carrying the same; the further the "
                          "curve sags below it, the more the corpus rests on a few — the madar (pivot) narrators of the "
                          "classical critics. The Gini coefficient is the area between the two, doubled.",
                          (["share of narrators", "share of names"], c["curve"]))
        self._finding("narrators", "The pillars", "The narrators the most hadith pass through.",
                      [self._people(n["pillars"][:20])],
                      "Counted from the identified names of these chains: how often a narrator appears, and (on hover) in "
                      "how many hadith. The dot is his rank in Ibn Hajar's colours. Click a name to open him.",
                      (["narrator", "arabic", "rank", "tabaqa", "times", "hadith"],
                       [[self._name(p["id"], p["name"]), p["name"], p["rank"], p["tabaqa"], p["links"], p["hadith"]]
                        for p in n["pillars"]]))
        if n["weak_pillars"]:
            self._finding("narrators", "Weak narrators", "The weak or unknown narrators the most hadith pass through — "
                          "where a grade would hang on one man.", [self._people(n["weak_pillars"])],
                          "Narrators of rank 7 or weaker (mastur, da'if, majhul and below), by how often they appear. "
                          "A hadith that passes through one of them is graded on its other routes — or stays weak.",
                          (["narrator", "arabic", "rank", "times", "hadith"],
                           [[self._name(p["id"], p["name"]), p["name"], p["rank"], p["links"], p["hadith"]]
                            for p in n["weak_pillars"]]))
        if n["central"]:
            self._finding("narrators", "The network", "The narrators the transmission flows through, towards the "
                          "Prophet ﷺ.", [self._people(n["central"], value=lambda p: 100 * p["score"], unit=" ‰")],
                          "PageRank on the graph of who narrates from whom (each pair of neighbours in a chain, weighted "
                          "by how often): a narrator ranks high when many chains lead to him and through him, not only "
                          "when he appears often. The figure is his share of the flow in thousandths.",
                          (["narrator", "arabic", "pagerank", "times"],
                           [[self._name(p["id"], p["name"]), p["name"], round(p["score"], 6), p["links"]]
                            for p in n["central"]]))
        cats = self._group_categories(r)
        rows = [(f"{t} · {TABAQA_LABELS.get(t, '').split(' (')[0]}", n["tabaqa_groups"][t - 1]) for t in range(1, 13)
                if sum(n["tabaqa_groups"][t - 1])]
        if rows:
            self._finding("narrators", "Generations", "Reliability generation by generation (tabaqa).",
                          [StackedBars(rows, cats, label_w=250)],
                          "Ibn Hajar's twelve generations, from the Companions (1) to the teachers of the six books' "
                          "compilers (10–12); each bar shows how the narrators of that generation found in these chains "
                          "are ranked.",
                          (["tabaqa"] + [c[0] for c in cats], [[label] + list(v) for label, v in rows]))

    def _chains(self, r: dict) -> None:
        ch = r["chains"]
        lengths = dict((int(k), v) for k, v in ch["lengths"])
        unsplit = lengths.pop(0, 0)
        bins = [(str(k), lengths.get(k, 0)) for k in range(1, max(lengths or {1: 0}) + 1)]
        counts = sorted(k for k, v in lengths.items() for _ in range(v))
        median = counts[len(counts) // 2] if counts else 0
        self._finding("chains", "Length", f"Most chains have {median} narrators between the compiler and the Prophet ﷺ.",
                      [Columns(bins, " chains")],
                      f"The number of names in each chain. A short chain (isnad 'ali) has fewer links between the compiler "
                      f"and the Prophet; a long one (nazil) more. {unsplit:,} chains could not be split into names yet "
                      "and are not counted.",
                      (["names in the chain", "chains"], [[k, v] for k, v in bins] + [["not split", unsplit]]))
        cats = self._group_categories(r)
        good = sum(ch["weakest"][:3]) / (sum(ch["weakest"]) or 1)
        rows = [("Chains with a ranked narrator", ch["weakest"]), ("Chains fully identified", ch["weakest_full"])]
        self._finding("chains", "The weakest link", f"In {_pct(good)} of the chains the weakest narrator is truthful or "
                      "better.", [StackedBars(rows, cats)],
                      "A chain is as strong as its weakest narrator: for each chain, the weakest rank among its "
                      "identified narrators. The first bar counts every chain with at least one ranked narrator — its "
                      "weakest may be among the names not yet identified; the second only the chains whose every name "
                      "is identified.",
                      (["series"] + [c[0] for c in cats], [[label] + list(v) for label, v in rows]))
        gaps = [(f"{k}", v) for k, v in ch["gaps"]]
        marked = {i for i, (k, _v) in enumerate(ch["gaps"]) if k > 100 or k <= -60}
        outside = sum(v for i, (_k, v) in enumerate(ch["gaps"]) if i in marked)
        table = self._suspects_table(ch["gap_suspects"], gap=True)
        self._finding("chains", "Time", f"{outside:,} teacher–student pairs lie too far apart in time — each points to a "
                      "wrongly identified name or a wrong year.", [Columns(gaps, " pairs", marked, label_every=2), table],
                      "For two neighbours in a chain whose years of death are known: the student's year minus the "
                      "teacher's. Most students die 20–60 years after their teachers. More than 110 years, or a student "
                      "dying 60 years or more before his teacher (gold), is hard to believe: the list shows the pairs "
                      "behind them — check them on the Narrators page (double-click).",
                      (["student", "teacher", "years apart", "times"],
                       [[self._name(s["student"]["id"], s["student"]["name"]), self._name(s["teacher"]["id"], s["teacher"]["name"]),
                         s["gap"], s["times"]] for s in ch["gap_suspects"]]))
        total = ch["order_ok"] + ch["order_bad"]
        if total:
            table = self._suspects_table(ch["order_suspects"], gap=False)
            self._finding("chains", "Generations in order", f"{_pct(ch['order_ok'] / total)} of the identified pairs are "
                          "in the right order of generations.", [table],
                          "A student belongs to the same or a later generation (tabaqa) than his teacher. A pair where the "
                          "student is of an EARLIER generation than his teacher is a sign of a wrong identification; the "
                          "list shows those met most often.",
                          (["student", "student tabaqa", "teacher", "teacher tabaqa", "times"],
                           [[self._name(s["student"]["id"], s["student"]["name"]), s["student"]["tabaqa"],
                             self._name(s["teacher"]["id"], s["teacher"]["name"]), s["teacher"]["tabaqa"], s["times"]]
                            for s in ch["order_suspects"]]))

    def _suspects_table(self, suspects: list[dict], gap: bool) -> QTableWidget:
        heads = ["Student", "Teacher", "Years apart" if gap else "Generations", "Times"]
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
        rows = [g for g in r["grades"] if g.get("weakest") and g["weakest"]["tau"] is not None]
        if not rows:
            self._boxes["grades"].addWidget(_label("No grades to compare: import a collection whose hadith are graded.",
                                                   "Lead"))
            return
        plot = [(f"{_short(g['grader'])} — {g['book']}", g["weakest"]["tau"],
                 tuple(g["weakest"]["tau_ci"] or (g["weakest"]["tau"], g["weakest"]["tau"]))) for g in rows]
        lo, hi = min(p[1] for p in plot), max(p[1] for p in plot)
        self._finding("grades", "The weakest link and the grade",
                      f"The weaker a chain's weakest narrator, the lower the grade — for every grader (Kendall's τ<sub>b</sub> "
                      f"{lo:.2f} to {hi:.2f}).",
                      [IntervalPlot(plot, "weaker narrator, higher grade", "weaker narrator, lower grade")],
                      "For each graded hadith: the weakest identified narrator of its best chain against the scholar's "
                      "grade, both as ordered categories. Kendall's τ<sub>b</sub> is a rank correlation that allows "
                      "ties: 0 is no relation, 1 a perfect one. The dot is the value, the line its 95% interval (a "
                      "bootstrap over hadith). A relation well above zero shows the grades follow the narrators — and "
                      "how much they do not shows what else a scholar weighed: other routes (mutaba'at, shawahid), "
                      "hidden defects ('ilal).",
                      (["grader", "book", "hadith", "tau-b", "tau-b low", "tau-b high", "gamma"],
                       [[_short(g["grader"]), g["book"], g["weakest"]["n"], round(g["weakest"]["tau"], 4)]
                        + [round(x, 4) for x in (g["weakest"]["tau_ci"] or [None, None]) if x is not None]
                        + [round(g["weakest"]["gamma"], 4) if g["weakest"]["gamma"] is not None else ""] for g in rows]))
        # the tables behind it, one per grader: row = weakest narrator, column = grade, cell = share of the row
        grid = QGridLayout()
        grid.setHorizontalSpacing(22)
        group_names = [name for name, _d in r["groups"]]
        for i, g in enumerate(rows[:6]):
            table = g["weakest"]["table"]
            cells = []
            for row in table:
                total = sum(row)
                cells.append([(cnt / total if total else None, [f"{100 * cnt / total:.0f}%" if total else "—"])
                              for cnt in row])
            keep = [k for k, row in enumerate(table) if sum(row)]
            grid.addWidget(_label(f"<b>{html.escape(_short(g['grader']))}</b> — {html.escape(g['book'])}", "Lead", rich=True),
                           (i // 2) * 2, i % 2)
            grid.addWidget(HeatMap([group_names[k] for k in keep], r["grade_labels"], [cells[k] for k in keep],
                                   cell=QSize(64, 28), label_w=120), (i // 2) * 2 + 1, i % 2)
        grid.setColumnStretch(2, 1)
        self._finding("grades", "Cross-tables", "How each grade is spread over the weakest narrator.", [grid],
                      "Rows: the weakest narrator of the hadith's best chain; columns: the grade. Each row adds up to "
                      "100%. A sahih grade where the weakest narrator is weak is a hadith strengthened by other routes, "
                      "or a narrator the grader judged otherwise than Ibn Hajar.",
                      (["grader", "book", "weakest narrator"] + r["grade_labels"],
                       [[_short(g["grader"]), g["book"], group_names[k]] + list(g["weakest"]["table"][k])
                        for g in rows for k in range(len(group_names))]))
        lengths = [g for g in rows if g.get("length") and g["length"]["tau"] is not None]
        if lengths:
            plot = [(f"{_short(g['grader'])} — {g['book']}", g["length"]["tau"],
                     tuple(g["length"]["tau_ci"] or (g["length"]["tau"], g["length"]["tau"]))) for g in lengths]
            self._finding("grades", "Length and grade", "Longer chains are graded a little lower — much less than "
                          "weaker narrators are.", [IntervalPlot(plot, "longer, higher grade", "longer, lower grade")],
                          "The same rank correlation between the number of names in the hadith's chain and its grade. Its "
                          "size beside the weakest-link relation shows which of the two the grades follow.",
                          (["grader", "book", "tau-b", "low", "high"],
                           [[_short(g["grader"]), g["book"], round(g["length"]["tau"], 4)]
                            + [round(x, 4) for x in (g["length"]["tau_ci"] or [])] for g in lengths]))

    # ------------------------------------------------------------------ the hadith model (ST7-H)
    def _model_section(self) -> None:
        box = self._boxes["model"]
        ms = (self._models or {}).get("models") or []
        if not ms:
            box.addWidget(_label("No model yet: it needs a book whose hadith are graded and whose chains are split into "
                                 "names (at least a hundred graded hadith).", "Lead"))
            return
        row = QHBoxLayout()
        row.addWidget(_label("Model of", "FilterTitle"))
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
        headline = (f"For {name}, {top['name'].replace('Weakest: ', 'a weakest narrator who is ').lower()} multiplies "
                    f"the odds of a weaker grade by {top['or']:.1f}." if top else
                    f"For {name}, no factor of the chain moves the grade beyond chance.")
        plot = [(c["name"], c["beta"], (c["beta"] - 1.96 * c["se"], c["beta"] + 1.96 * c["se"])) for c in coefs]
        fmt = lambda v, lo, hi: f"OR {math.exp(v):.2f}  [{math.exp(lo):.2f}–{math.exp(hi):.2f}]"  # noqa: E731
        self._model_finding(
            "What the grade follows", headline,
            [IntervalPlot(plot, "a stronger grade", "a weaker grade", fmt=fmt, label_w=250)],
            "An ordinal (proportional-odds) regression of the scholar's grade on the hadith's best chain. Each row is "
            "one factor; the dot is its effect on the log-odds of a WEAKER grade, the line its 95% interval, and the "
            "figure at the right the odds ratio: 2 doubles the odds of a weaker grade, 0.5 halves them, 1 is no effect. "
            "The weakest narrator is compared with a chain whose weakest is trustworthy (thiqa); the other factors are "
            "per unit. All are measured together, so each is its effect with the others held equal.",
            (["factor", "beta", "se", "odds ratio", "low", "high", "p"],
             [[c["name"], round(c["beta"], 5), round(c["se"], 5), round(c["or"], 4), round(c["or_ci"][0], 4),
               round(c["or_ci"][1], 4), c["p"]] for c in coefs]))
        # which factors matter: likelihood-ratio tests
        tests = sorted(m["tests"], key=lambda t: -t["chi2"])
        matter = [t for t in tests if t["p_holm"] < 0.05]
        total = m["lr_all"]["chi2"] or 1
        table = QTableWidget(len(tests), 5)
        table.setHorizontalHeaderLabels(["Factor", "χ²", "df", "p (Holm)", "Share of what the chain explains"])
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for i, t in enumerate(tests):
            for j, v in enumerate([t["label"], f"{t['chi2']:.1f}", str(t["df"]),
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
            "Which factors matter",
            (f"{len(matter)} of {len(tests)} factors matter; {lead['label'].lower()} alone carries "
             f"{_pct(lead['chi2'] / total)} of what the chain explains." if lead else "No factor to test."),
            [table],
            "For each factor the model is fitted again without it; the likelihood-ratio χ² is how much worse it then "
            "fits, with its degrees of freedom. p is adjusted for testing several factors at once (Holm). The last "
            "column is the factor's χ² beside the whole chain's (all factors against none) — overlapping factors can "
            "add up to more than 100%.",
            (["factor", "chi2", "df", "p", "p holm"], [[t["label"], round(t["chi2"], 3), t["df"], t["p"], t["p_holm"]]
                                                       for t in tests]))
        # how much the chain explains
        tiles = StatTiles([
            ("Hadith", f"{m['n']:,}", f"graded by {name}, with a chain"),
            ("Right", _pct(m["accuracy"]), f"against {_pct(m['base_rate'])} by always saying “{m['labels'][0]}”"),
            ("McFadden R²", f"{m['mcfadden']:.3f}" if m["mcfadden"] is not None else "—", "0.2–0.4 is a very good fit"),
            ("Somers' D", f"{m['somers_d']:.2f}" if m["somers_d"] is not None else "—", "ordering: 0 none, 1 perfect"),
        ])
        self._model_finding(
            "How much the chain explains",
            f"The chain explains part of {name}'s grades, not most: the rest is what a scholar weighs beyond one chain.",
            [tiles, Calibration(m["calibration"], f"Calibration: the model's probability of “{m['labels'][0]}” (across) "
                                                  "against the share of hadith that got it (up). Points on the diagonal: "
                                                  "the model's probabilities can be taken at their word.")],
            "McFadden's R² compares the model's likelihood with a model that knows only how often each grade is given; "
            "for a model of human judgement values of 0.1–0.2 are usual and 0.2–0.4 very good. 'Right' counts the "
            "hadith whose most likely grade is the scholar's. Somers' D measures how well the model's expected grade "
            "orders the hadith. That the chain explains only part of the grade is itself the finding: a scholar grades "
            "a hadith on all its routes and on its text, not on one chain.",
            (["predicted (mean)", "observed", "hadith"], m["calibration"]))
        # the surprises
        for side, title, sentence, how in (
            ("graded_higher", "Graded higher than the chain foretells",
             "hadith {name} grades stronger than their chain alone would — candidates for strengthening by other "
             "routes (mutaba'at, shawahid).",
             "Hadith whose grade is STRONGER than the model's most likely grade, the least expected first: the "
             "probability is the model's for this grade or a stronger one. A weak chain graded sahih or hasan is "
             "usually a hadith strengthened by its other routes (hasan li-ghayrihi, sahih li-ghayrihi) — or a "
             "narrator the scholar judges otherwise than Ibn Hajar. Double-click to read it in its book."),
            ("graded_lower", "Graded lower than the chain foretells",
             "hadith {name} grades weaker than their chain alone would — candidates for a hidden defect ('illa) or "
             "an irregular text (shudhudh).",
             "Hadith whose grade is WEAKER than the model's most likely grade, the least expected first. A chain of "
             "trustworthy narrators graded weak points to what the chain does not show: a hidden defect ('illa), a "
             "contradiction of stronger narrators (shudhudh), a break the names do not reveal (irsal khafi, tadlis). "
             "Double-click to read it in its book.")):
            items = m[side]
            if not items:
                continue
            total_side = m[f"{side}_total"]
            self._model_finding(title, f"{total_side:,} " + sentence.format(name=name),
                                [self._surprise_table(items, m["labels"])], how,
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
                        rows.append((f"{c_name.replace('Weakest: ', '')} — {_short(x['grader'])}", c["beta"],
                                     (c["beta"] - 1.96 * c["se"], c["beta"] + 1.96 * c["se"])))
            self._model_finding(
                "The scholars compared", "How strongly each scholar's grade follows the weakest narrator.",
                [IntervalPlot(rows, "a stronger grade", "a weaker grade", fmt=fmt, label_w=300)],
                "The same model fitted to each scholar's grades of this book. Where one scholar's odds ratio for a weak "
                "narrator is larger than another's, he leans more on Ibn Hajar's verdicts on the narrators; a smaller "
                "one shows a scholar who more often finds the hadith strengthened elsewhere — or who judges the "
                "narrator otherwise.",
                (["level", "grader", "beta", "low", "high"],
                 [[r_[0].split(" — ")[0], r_[0].split(" — ")[1], round(r_[1], 5), round(r_[2][0], 5), round(r_[2][1], 5)]
                  for r_ in rows]))

    def _surprise_table(self, items: list[dict], labels: list[str]) -> QTableWidget:
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Hadith", "Grade", "Model's most likely", "Probability", "Weakest narrator",
                                         "Names / not identified"])
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
            probs = " · ".join(f"{lab} {100 * q:.0f}%" for lab, q in zip(labels, d["probs"]))
            for j, v in enumerate([d["grade"], d["likely"], f"{100 * d['p']:.1f}%", f["weakest"],
                                   f"{f['length']} / {f['unidentified']}"], start=1):
                item = QTableWidgetItem(v)
                item.setToolTip(f"The model's grades for this hadith: {probs}")
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
        table.setHorizontalHeaderLabels(["Hadith", "Book", "Scholars and their grades", "Weakest narrator"])
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for s in shared[:30]:
            row = table.rowCount()
            table.insertRow(row)
            first = QTableWidgetItem(f"{s['number']}  {'▲' if s['side'] == 'graded_higher' else '▼'}")
            first.setData(Qt.ItemDataRole.UserRole, s["hadith_id"])
            first.setToolTip("▲ graded higher than the chain foretells · ▼ graded lower")
            table.setItem(row, 0, first)
            table.setItem(row, 1, QTableWidgetItem(s["book"]))
            who = QTableWidgetItem("; ".join(f"{_short(g)}: {grade}" for g, grade, _l, _p in s["graders"]))
            who.setToolTip("\n".join(f"{_short(g)}: {grade} — the model expected {likely} ({100 * p:.1f}% for this or "
                                      "further)" for g, grade, likely, p in s["graders"]))
            table.setItem(row, 2, who)
            table.setItem(row, 3, QTableWidgetItem(s["factors"]["weakest"]))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setFixedHeight(min(30, len(shared)) * 30 + 34)
        table.cellDoubleClicked.connect(lambda rr, _c: self.open_hadith.emit(table.item(rr, 0).data(Qt.ItemDataRole.UserRole)))
        up = sum(1 for s in shared if s["side"] == "graded_higher")
        self._finding("model", "Surprises the scholars share",
                      f"{len(shared)} hadith surprise two scholars or more in the same way — {up} graded higher than "
                      f"their chain, {len(shared) - up} lower.", [table],
                      "One scholar's surprise may be his own judgement or a slip; the same surprise in several scholars' "
                      "grades points to the hadith itself — its other routes, or a defect they all saw. ▲ higher than "
                      "the chain foretells, ▼ lower. Double-click to read it in its book.",
                      (["hadith", "side", "book", "graders", "weakest narrator"],
                       [[s["number"], s["side"], s["book"], "; ".join(f"{g}: {gr}" for g, gr, _l, _p in s["graders"]),
                         s["factors"]["weakest"]] for s in shared]))

    def _books(self, r: dict) -> None:
        b = r["books"]
        rows = b["rows"]
        table = QTableWidget(len(rows), 6)
        table.setHorizontalHeaderLabels(["Book", "Chains", "Median length", "Names identified", "Reach the Prophet",
                                         "Narrators"])
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for i, row in enumerate(rows):
            for j, v in enumerate([row["name"], f"{row['chains']:,}", str(row["median_length"] or "—"),
                                   _pct(row["identified"]), _pct(row["reaching"]), f"{row['narrators']:,}"]):
                table.setItem(i, j, QTableWidgetItem(v))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setFixedHeight(len(rows) * 30 + 34)
        cats = self._group_categories(r)
        self._finding("books", "The books side by side", "Each book's chains and the narrators they rest on.",
                      [table, StackedBars([(row["name"], row["groups"]) for row in rows], cats, label_w=230)],
                      "The table compares the books' chains; the bars, the narrators each book's chains pass through, "
                      "each counted as often as he appears.",
                      (["book", "chains", "median length", "identified", "reach the Prophet", "narrators"]
                       + [c[0] for c in cats],
                       [[row["name"], row["chains"], row["median_length"], round(row["identified"], 4),
                         round(row["reaching"], 4), row["narrators"]] + list(row["groups"]) for row in rows]))
        if len(b["names"]) > 1:
            cells = [[(None, []) if i == j else (v, [f"{100 * v:.0f}%"]) for j, v in enumerate(row)]
                     for i, row in enumerate(b["overlap"])]
            self._finding("books", "Shared narrators", "How many narrators each pair of books shares.",
                          [HeatMap(b["names"], b["names"], cells, cell=QSize(96, 40), label_w=200)],
                          "The Jaccard share: narrators found in both books' chains, out of those found in either. Books "
                          "of one school and one period share most.",
                          ([""] + b["names"], [[name] + [round(v, 4) for v in row] for name, row in zip(b["names"], b["overlap"])]))

    # ------------------------------------------------------------------ the graders section (ST7, first tab)
    def _graders_section(self) -> QWidget:
        graders = QWidget()
        gl = QVBoxLayout(graders)
        gl.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        bar.addWidget(_label("Book", "FilterTitle"))
        self.book = QComboBox()
        self.book.setObjectName("FilterCombo")
        self.book.currentIndexChanged.connect(lambda _i: self.compute(False))
        bar.addWidget(self.book)
        self.recompute = QPushButton("Recompute")
        self.recompute.setObjectName("Quiet")
        self.recompute.setToolTip("The results are kept in a file and reused while the grades are unchanged")
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
        return _label("<b>How to read it</b> — " + text, "Caption", rich=True)

    def _refresh_graders(self) -> None:
        conn = self.conn
        books = core.books_with_grades(conn)
        current = self.book.currentData()
        self.book.blockSignals(True)
        self.book.clear()
        for key, name, n in books:
            self.book.addItem(f"{name} — {n} grader{'s' if n != 1 else ''}", key)
        self.book.setCurrentIndex(max(0, self.book.findData(current)))
        self.book.blockSignals(False)
        if books:
            self.compute(False)
        else:
            self._clear()
            self.box.addWidget(_label("No grades yet: import a collection with graded hadith (Data Sources).", "Lead"))

    def compute(self, recompute: bool) -> None:
        key = self.book.currentData()
        if not key or (self._gthread is not None and self._gthread.isRunning()):
            return
        self.status.setText("Reading the saved results…" if not recompute else "Computing…")
        self.recompute.setEnabled(False)
        self._gthread = QThread(self)
        self._worker = _Worker(core.cached, key, recompute)
        self._worker.moveToThread(self._gthread)
        self._gthread.started.connect(self._worker.run)
        self._worker.progress.connect(lambda m: self.status.setText(m + "…"))
        self._worker.done.connect(self._keep_and_show)
        self._worker.failed.connect(lambda m: self.status.setText("Could not compute: " + m))
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
        self.status.setText((f"From the saved results ({r['from_file']}). " if r.get("from_file") else "Computed and saved. ")
                            + f"Intervals: {r['boot']} bootstrap samples of hadith.")
        if len(graders) < 2:
            card = self._card("One grader only")
            card.layout().addWidget(_label(f"{names[0] if names else 'No one'} graded this book; agreement and the model "
                                           "need two or more. His grades:", "Lead"))
            dist = r["distribution"].get(graders[0], []) if graders else []
            card.layout().addWidget(_label(" · ".join(f"{core.LABELS[k]} {n:,}" for k, n in reversed(list(enumerate(dist)))), "Lead"))
            self.box.addWidget(card)
            self.box.addStretch(1)
            return
        t = theme.current()
        # 1 — the whole picture
        a = r["alpha"]
        c = r["certainty"]
        card = self._card("All graders together")
        card.layout().addWidget(_label(
            f"<b>Krippendorff's alpha {a['value']:.3f}</b> (95% interval {a['ci'][0]:.3f}–{a['ci'][1]:.3f}) over "
            f"{a['units']:,} hadith graded by two or more — {self._alpha_words(a['value'])}.<br>"
            f"The model is sure (≥95%) of the true grade of <b>{c['high']:,}</b> hadith ({100 * c['high'] / c['total']:.1f}%), "
            f"fairly sure of {c['middle']:,}, and unsure (<60%) of <b>{c['low']:,}</b> ({100 * c['low'] / c['total']:.1f}%).",
            "Lead", rich=True))
        left = {g: n for g, n in r.get("chain_only", {}).items() if n}
        if left:
            card.layout().addWidget(_label(
                "Grades of the <b>chain only</b> (\"Isnaad Sahih\": the chain is sound, the text is not judged) answer "
                "another question than a grade of the hadith, so they are left out of every comparison here: "
                + ", ".join(f"{html.escape(_short(g))} {n:,}" for g, n in sorted(left.items(), key=lambda kv: -kv[1])) + ".",
                "Caption", rich=True))
        for ov in r.get("one_voice", []):
            warn = _label(f"⚠ {_short(ov['kept'])} and {_short(ov['left_out'])} agree on {100 * ov['agree']:.1f}% — too often "
                          "for two scholars grading on their own; the source probably filled one column from the other. In "
                          f"the model they are one voice ({_short(ov['kept'])}); {_short(ov['left_out'])} is measured against "
                          "the model's result without moving it.", "Caption")
            warn.setStyleSheet(f"color: {t.gold};")
            card.layout().addWidget(warn)
        card.layout().addWidget(self._how(
            "alpha measures agreement beyond chance for all graders at once, by the order of the grades (a near miss "
            "counts less than a far one): 1 is complete agreement, 0 no better than chance; above 0.8 is strong, "
            "0.67–0.8 allows tentative conclusions, below 0.67 is weak."))
        self.box.addWidget(card)
        # 2 — agreement heat maps
        card = self._card("Agreement between each pair of graders")
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
        card.layout().addWidget(_label("<b>Same grade</b>", "Lead", rich=True))
        card.layout().addWidget(HeatMap(names, names, matrix("agree", lambda v: f"{100 * v:.1f}%",
                                                             lambda a, b: f"{100 * a:.1f}–{100 * b:.1f}"), low=0.5, high=1.0,
                                        label_w=210))
        card.layout().addWidget(_label("<b>Ordinal (weighted) kappa</b>", "Lead", rich=True))
        card.layout().addWidget(HeatMap(names, names, matrix("wkappa", lambda v: f"κw {v:.2f}", lambda a, b: f"{a:.2f}–{b:.2f}"),
                                        low=0.0, high=1.0, label_w=210))
        card.layout().addWidget(self._how(
            "each cell compares the row's grader with the column's on the hadith both graded (n). Left: how often they "
            "give the same grade. Right: Cohen's kappa weighted by order — agreement beyond chance, where calling a "
            "hasan hadith da'if is a smaller disagreement than calling it fabricated. The small figures are 95% intervals."))
        self.box.addWidget(card)
        # 3 — strictness
        card = self._card("Strictness — mutashaddid and mutasahil, measured")
        rows = [(n, r["model"]["strictness"][g]["value"], tuple(r["model"]["strictness"][g]["ci"])) for n, g in zip(names, graders)]
        rows.sort(key=lambda x: x[1])
        card.layout().addWidget(IntervalPlot(rows, "stricter (mutashaddid)", "more lenient (mutasahil)"))
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
        card.layout().addWidget(_label("<b>Pair by pair</b>: P(row grades higher) − P(row grades lower)", "Lead", rich=True))
        card.layout().addWidget(HeatMap(names, names, pair_cells, low=-0.25, high=0.25, diverging=True, label_w=210))
        card.layout().addWidget(self._how(
            "from the model: the chance a grader gives a hadith a LOWER grade than its true grade, minus the chance he "
            "gives it a HIGHER one — by order only. Below zero (gold) he is stricter, above zero (blue) more lenient; the "
            "line is the 95% interval. The 'true grade' is what these graders' grades imply together, so the measure is "
            "relative to them, not absolute. Pair by pair needs no model: who grades the same hadith higher, who lower."))
        self.box.addWidget(card)
        # 4 — confusion matrices
        card = self._card("How each grader grades a hadith of each true grade (the model's confusion matrices)")
        order = list(reversed(range(core.K)))
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        for n, (g, name) in enumerate(zip(graders, names)):
            th = r["model"]["theta"][g]
            # a true grade the model finds (almost) no hadith of has no row to measure: its cells would show only
            # the light prior (20% everywhere) — shown as "too few" instead
            few = {k for k in range(core.K) if r["model"]["prior"][k] * r["certainty"]["total"] < 15}
            cells = [[(None, ["too few"]) if k in few else (th[k][l], [f"{100 * th[k][l]:.0f}%"]) for l in order]
                     for k in order]
            grid.addWidget(_label(f"<b>{html.escape(name)}</b>", "Lead", rich=True), (n // 2) * 2, n % 2)
            grid.addWidget(HeatMap([core.LABELS[k] for k in order], [core.LABELS[k] for k in order], cells,
                                   cell=QSize(62, 28), label_w=86), (n // 2) * 2 + 1, n % 2)
        grid.setColumnStretch(2, 1)
        card.layout().addLayout(grid)
        prior = r["model"]["prior"]
        card.layout().addWidget(_label("How common each true grade is, by the model: " + " · ".join(
            f"{core.LABELS[k]} {100 * prior[k]:.1f}%" for k in order), "Lead"))
        card.layout().addWidget(self._how(
            "rows are the true grade, columns what the grader says. A strong diagonal is a grader who sees the grade the "
            "others see; weight to the right of it (towards weaker grades) is strictness, to the left leniency. This is "
            "the Dawid–Skene model: it learns each grader's matrix and the true grades together."))
        self.box.addWidget(card)
        # 5 — disputed hadith
        card = self._card(f"The disputed hadith — {r['disputed_total']:,} where the graders are two steps apart or the "
                          "model is unsure")
        table = QTableWidget(0, 3 + len(graders))
        table.setHorizontalHeaderLabels(["Hadith", "Model's grade", "Certainty"] + names)
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for d in r["disputed"][:150]:
            row = table.rowCount()
            table.insertRow(row)
            item = QTableWidgetItem(str(d.get("number") or d["hadith_id"]))
            item.setData(Qt.ItemDataRole.UserRole, d["hadith_id"])
            table.setItem(row, 0, item)
            table.setItem(row, 1, QTableWidgetItem(core.LABELS[d["consensus"]]))
            table.setItem(row, 2, QTableWidgetItem(f"{100 * d['certainty']:.0f}%"))
            for j, g in enumerate(graders):
                v = d["grades"].get(g)
                table.setItem(row, 3 + j, QTableWidgetItem(core.LABELS[v] if v is not None else "—"))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setMinimumHeight(360)
        table.cellDoubleClicked.connect(lambda rr, _c: self.open_hadith.emit(table.item(rr, 0).data(Qt.ItemDataRole.UserRole)))
        card.layout().addWidget(table)
        card.layout().addWidget(self._how(
            "the hadith where the scholars are furthest apart come first. Certainty is the model's probability for its "
            "grade. Double-click a row to read the hadith in its book."))
        self.box.addWidget(card)
        self.box.addStretch(1)

    @staticmethod
    def _alpha_words(a: float) -> str:
        return ("strong agreement" if a >= 0.8 else "enough agreement for tentative conclusions" if a >= 0.667
                else "weak agreement")
