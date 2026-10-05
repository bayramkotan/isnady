"""Statistics (ST7): deep measures, tab by tab. First tab: the GRADERS of a book — agreement with intervals,
the Dawid–Skene model of the true grade, each grader's confusion matrix and strictness, the disputed hadith.
Every section says what it measures and how to read it; numbers are computed once and kept (core.stats_graders)."""

import html

from PySide6.QtCore import QObject, QSize, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from isnady.core import stats_graders as core
from isnady.core.scholars import SCHOLARS
from isnady.gui import theme
from isnady.gui.stats_charts import HeatMap, IntervalPlot

PLANNED = {
    "Narrators": "Each narrator's reliability as a latent score with its interval (Ibn Hajar's rank as the prior, updated "
                 "by the chains he appears in; hierarchical Bayes shrinks the rarely seen), rank × tabaqa × book, network "
                 "measures (how central a narrator is), the most disputed narrators.",
    "Books": "Per book: the distribution of hadith scores with intervals, sahih / hasan / da'if shares by grader, "
             "unbroken chains, the narrators' average reliability, high and low chains — books compared with tests.",
    "Hadith": "Each hadith on its own: probabilities of each grade, a score with its interval, number of routes, "
              "the support of mutaba'at and shawahid (takhrij), the weakest link of its chains, model against scholars.",
    "Chains": "The weakest link, continuity, length, and how chains differ by book and generation.",
    "Correlations": "Measures against each other: narrator rank and hadith grade, chain length and grade, routes and "
                    "grade, grader strictness by book — rank correlations (Spearman, Kendall), partial correlations, plots.",
    "Models": "The models behind the scores: how well they are calibrated, where model and scholars differ, and the "
              "assumptions you can change.",
}


def _label(text: str, name: str = "", rich: bool = False) -> QLabel:
    l = QLabel(text)
    if name:
        l.setObjectName(name)
    l.setWordWrap(True)
    if rich:
        l.setTextFormat(Qt.TextFormat.RichText)
    return l


def _short(grader: str) -> str:
    for s in SCHOLARS:
        if grader in s.get("grader_names", []):
            return s["name"]
    return grader


class _Worker(QObject):
    progress = Signal(str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, collection: str, recompute: bool) -> None:
        super().__init__()
        self.collection, self.recompute = collection, recompute

    def run(self) -> None:
        from isnady.data import db

        try:
            conn = db.connect()                       # its own connection: SQLite connections stay in their thread
            self.done.emit(core.cached(conn, self.collection, self.progress.emit, self.recompute))
            conn.close()
        except Exception as exc:                      # shown on the page, never a silent failure
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class StatisticsPage(QWidget):
    open_hadith = Signal(int)

    def __init__(self, connection_getter, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._conn_of = connection_getter
        self._thread = None
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 18)
        root.setSpacing(10)
        title = _label("Statistics", "CardTitle")
        title.setFont(theme.reading_font(22, bold=True))
        root.addWidget(title)
        root.addWidget(_label("Deep measures of the imported data, each with what it means and how sure it is. Grades are "
                              "ordered categories — never numbers, never averaged.", "Lead"))
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        root.addWidget(self.tabs, 1)
        # Graders
        graders = QWidget()
        gl = QVBoxLayout(graders)
        gl.setContentsMargins(0, 10, 0, 0)
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
        self.tabs.addTab(graders, "Graders")
        for name, text in PLANNED.items():
            page = QWidget()
            pl = QVBoxLayout(page)
            pl.setContentsMargins(0, 18, 0, 0)
            card = self._card(f"{name} — coming next")
            card.layout().addWidget(_label(text, "Lead"))
            pl.addWidget(card)
            pl.addStretch(1)
            self.tabs.addTab(page, name)
        self._loaded = False

    @property
    def conn(self):
        return self._conn_of()

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
        lab = _label("<b>How to read it</b> — " + text, "Caption", rich=True)
        return lab

    # ------------------------------------------------------------------ data
    def refresh(self) -> None:
        conn = self.conn
        if conn is None:
            return
        books = core.books_with_grades(conn)
        self.book.blockSignals(True)
        self.book.clear()
        for key, name, n in books:
            self.book.addItem(f"{name} — {n} grader{'s' if n != 1 else ''}", key)
        self.book.blockSignals(False)
        if books:
            self.compute(False)
        else:
            self._clear()
            self.box.addWidget(_label("No grades yet: import a collection with graded hadith (Data Sources).", "Lead"))

    def compute(self, recompute: bool) -> None:
        key = self.book.currentData()
        if not key or (self._thread is not None and self._thread.isRunning()):
            return
        self.status.setText("Reading the saved results…" if not recompute else "Computing…")
        self.recompute.setEnabled(False)
        self._thread = QThread(self)
        self._worker = _Worker(key, recompute)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(lambda m: self.status.setText(m + "…"))
        self._worker.done.connect(self._show)
        self._worker.failed.connect(lambda m: self.status.setText("Could not compute: " + m))
        for sig in (self._worker.done, self._worker.failed):
            sig.connect(self._thread.quit)
        self._thread.finished.connect(lambda: self.recompute.setEnabled(True))
        self._thread.start()

    def _clear(self) -> None:
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    # ------------------------------------------------------------------ the page
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
