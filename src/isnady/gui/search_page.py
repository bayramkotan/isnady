"""Search page: hadith text search over every imported edition, and the people of hadith.

The drop-down before the search field chooses what is searched (S3): Hadith (the default), Narrators (both
traditions) or Scholars. All matching logic is in isnady.core (search, narrators.find, scholars.search); this page
only collects the query, calls the core and renders the results as cards.
"""

import html
import sqlite3

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from isnady import config
from isnady.core import isnad as core_isnad
from isnady.core import narrators as core_narrators
from isnady.core import search as core
from isnady.data import db
from isnady.gui import theme
from isnady.gui.chain_widgets import ChainStrip
from isnady.gui.widgets import FlowLayout, TextBlock, expanding_width_policy

PAGE_SIZE = 25
FIRST_BATCH = 4     # cards shown at once; the rest follow in small batches
NEXT_BATCH = 3
MODE_LABELS = (("all", "All words"), ("any", "Any word"), ("phrase", "Exact phrase"), ("meaning", "By meaning (AI)"))
EXAMPLES = ("النيات", "الصلاة", "niyet", "komşu")
KINDS = (("hadith", "Hadith"), ("narrators", "Narrators"), ("scholars", "Scholars"))
KIND_TEXT = {   # placeholder, start-page title, start-page lead, examples
    "hadith": ("Search the hadith: a word or phrase in Arabic, Turkish or English", "Search the hadith", "", EXAMPLES),
    "narrators": ("Search the narrators by name: Arabic, English or Turkish spelling", "Search the narrators",
                  "Every narrator of both traditions — Ibn Hajar's Taqrib for the Sunni books, al-Najashi's Rijal for "
                  "the Shia books — by any part of his name. Names are matched by their letters, without vowels or "
                  "diacritics, so “Abu Hurayra”, “Ebû Hüreyre” and أبو هريرة all find him. Try one of these:",
                  ("Abu Hurayra", "الزهري", "Ibn Umar", "Âişe", "Zurara")),
    "scholars": ("Search the scholars of hadith: a name or a book", "Search the scholars",
                 "The compilers of the books, the scholars who graded their hadith and the critics of narrators — "
                 "by name in any spelling, or by the title of a work. Try one of these:",
                 ("Buhârî", "Albani", "ابن حجر", "Riyad al-Salihin")),
}
TRADITIONS = (("", "Both traditions"), ("sunni", "Sunni"), ("shia", "Shia"))


def _highlight(text: str, spans: list[tuple[int, int]], gilt: str) -> str:
    out, last = [], 0
    for a, b in spans:
        out.append(html.escape(text[last:a]))
        out.append(f"<span style='background-color:{gilt}'>{html.escape(text[a:b])}</span>")
        last = b
    out.append(html.escape(text[last:]))
    return "".join(out)


def _label(text: str = "", name: str = "", wrap: bool = False, selectable: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if wrap:
        label.setSizePolicy(expanding_width_policy())
    if selectable:
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


class ResultCard(QFrame):
    def __init__(self, result: core.SearchResult, chain: dict | None = None, open_chain=None,
                 people: dict | None = None, score: float | None = None, related: list | None = None,
                 open_book=None) -> None:
        super().__init__()
        self.setObjectName("Card")
        t = theme.current()
        box = QVBoxLayout(self)
        box.setContentsMargins(26, 20, 26, 20)
        box.setSpacing(10)

        head = QHBoxLayout()
        title = _label(result.collection_name, "CardTitle")
        title.setFont(theme.reading_font(15, bold=True, scaled=True))
        number = _label(f"hadith {result.number}", "CardNumber")
        head.addWidget(title)
        head.addSpacing(8)
        head.addWidget(number, 0, Qt.AlignmentFlag.AlignBaseline)
        if score is not None:
            meaning = _label(f"meaning {score:.2f}", "CardNumber")
            meaning.setToolTip("How close this hadith is in meaning to the search, from 0 to 1: shared words "
                               "and shared concepts learnt from the Arabic texts and their translations.\n"
                               "A measure of closeness, not of authenticity.")
            head.addSpacing(10)
            head.addWidget(meaning, 0, Qt.AlignmentFlag.AlignBaseline)
        head.addStretch(1)
        if open_book is not None:
            book = QPushButton("In its book")
            book.setObjectName("Link")
            book.setCursor(Qt.CursorShape.PointingHandCursor)
            book.setToolTip("Read this hadith where it stands in its book, among the hadith of its chapter")
            book.clicked.connect(lambda: open_book(result.hadith_id))
            head.addWidget(book)
            head.addSpacing(14)
        if open_chain is not None:
            view = QPushButton("View chain")
            view.setObjectName("Link")
            view.setCursor(Qt.CursorShape.PointingHandCursor)
            view.setToolTip("Open this hadith's chain of transmission")
            view.clicked.connect(lambda: open_chain(result.hadith_id))
            head.addWidget(view)
        box.addLayout(head)
        if related:
            # other narrations of the same hadith (YZ2, takhrij); each number opens that hadith's chain
            groups: dict = {}
            for r in related:
                groups.setdefault(r["book_name"], []).append(r)
            t = theme.current()
            parts = []
            for book, items in groups.items():
                links = []
                for r in items:
                    style = "" if r["kind"] == "same" else "font-style:italic;"
                    links.append(f"<a href='{r['hadith_id']}' style='color:{t.lapis};text-decoration:none;{style}'>"
                                 f"{html.escape(r['number'])}</a>")
                parts.append(f"{html.escape(book)} " + " · ".join(links))
            also = _label("Also narrated in: " + "&nbsp;&nbsp;|&nbsp;&nbsp;".join(parts), "Caption", wrap=True)
            also.setTextFormat(Qt.TextFormat.RichText)
            also.setToolTip("Other narrations of this hadith found by comparing the texts (takhrij).\n"
                            "Upright numbers: the same text. Italic: probably the same report "
                            "(the texts overlap and the same Companion narrates both).\nClick a number to open it.")
            if open_chain is not None:
                also.linkActivated.connect(lambda hid: open_chain(int(hid)))
            box.addWidget(also)
        if chain and chain["links"]:
            box.addWidget(ChainStrip(chain, people))
            box.addSpacing(6)
        elif chain and chain["problem"]:
            note = _label("Chain kept whole, not split: " + chain["problem"], "Caption", wrap=True)
            box.addWidget(note)

        if result.grades:
            pills = FlowLayout(spacing=6)
            for grader, grade in result.grades:
                pill = _label(f"{html.escape(grader)}: <b>{html.escape(grade)}</b>", "Pill")
                pill.setTextFormat(Qt.TextFormat.RichText)
                from isnady.core import learn
                from isnady.core.grades import group as grade_group

                meaning = learn.for_group(grade_group(grade))
                pill.setToolTip(f"{grader} graded this hadith: {grade}" + (f"\n\n{meaning}" if meaning else ""))
                pills.addWidget(pill)
            box.addLayout(pills)
            box.addSpacing(4)

        for text in result.texts:
            body = _highlight(text.text, text.spans, t.gilt)
            script = config.script_for_language(text.language, text.direction)
            style = (f"line-height:{theme.script_line_height(script)}%;"
                     f"color:{theme.script_color(script)}")
            if text.direction == "rtl":
                box.addWidget(TextBlock(f"<div dir='rtl' align='right' style='{style}'>{body}</div>",
                                        theme.script_font(script), rtl=True))
            else:
                frame = QFrame()
                frame.setObjectName("Translation")
                inner = QVBoxLayout(frame)
                inner.setContentsMargins(16, 2, 0, 2)
                inner.addWidget(TextBlock(f"<div style='{style}'>{body}</div>", theme.script_font(script)))
                box.addWidget(frame)
            caption = _label(f"{text.language}, {text.edition_key}", "Caption")
            if text.direction == "rtl":
                caption.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
            box.addWidget(caption)


class SearchPage(QWidget):
    open_chain = Signal(int)          # hadith id; the main window shows it on the Isnad Chains page
    open_book = Signal(int)           # hadith id; the main window opens its book at its chapter (Books)
    open_person = Signal(int, str)    # person id, tradition; Narrators or Shia Rijal shows him
    open_scholar = Signal(str)        # scholar id; Hadith Scholars shows him
    data_changed = Signal()

    def __init__(self, status_message=None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._status = status_message or (lambda _m: None)
        self._conn: sqlite3.Connection | None = None
        self._data_version = None
        self._notice = ""
        self._page: core.SearchPage | None = None
        self._results: list[core.SearchResult] = []
        self._found: list[dict] | None = None      # narrators or scholars found (S3); None: a hadith search
        self._people_total = 0
        self._people_shown = 0

        # what is searched (S3): hadith by default, every time isnady starts
        self.kind_combo = QComboBox()
        self.kind_combo.setObjectName("SearchKind")
        self.kind_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        for key, label in KINDS:
            self.kind_combo.addItem(label, key)
        self.kind_combo.setToolTip("What to search: the text of the hadith, the narrators of both traditions "
                                   "by name, or the scholars of hadith")
        self.kind_combo.currentIndexChanged.connect(self._kind_changed)

        # search bar
        self.query_edit = QLineEdit()
        self.query_edit.setObjectName("SearchField")
        self.query_edit.setPlaceholderText("Search the hadith: a word or phrase in Arabic, Turkish or English")
        self.query_edit.setClearButtonEnabled(True)
        self.query_edit.returnPressed.connect(self.run_search)
        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("Primary")
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_button.clicked.connect(self.run_search)

        # filters
        self.mode_combo = QComboBox()
        for key, label in MODE_LABELS:
            self.mode_combo.addItem(label, key)
        self.mode_combo.currentIndexChanged.connect(
            lambda _i: self.whole_words.setEnabled(self.mode_combo.currentData() != "meaning"))
        self.whole_words = QCheckBox("Whole words only")
        self.whole_words.setToolTip(
            "Off: النيات also finds بالنيات, because Arabic words carry attached prefixes.\n"
            "On: only the word standing on its own."
        )
        self.book_combo = QComboBox()
        self.language_combo = QComboBox()
        for combo in (self.mode_combo, self.book_combo, self.language_combo):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
            combo.currentIndexChanged.connect(self._rerun_if_searched)
        self.whole_words.toggled.connect(self._rerun_if_searched)
        self.tradition_combo = QComboBox()
        for key, label in TRADITIONS:
            self.tradition_combo.addItem(label, key)
        self.tradition_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.tradition_combo.setToolTip("Sunni: the narrators of Ibn Hajar's Taqrib. Shia: those of al-Najashi's "
                                        "Rijal.\nThe two are never matched to each other: each keeps its own terms.")
        self.tradition_combo.currentIndexChanged.connect(self._rerun_if_searched)
        self.summary = _label(name="Summary")

        # results
        self.body = QWidget()
        self.body.setObjectName("ResultsBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 4, 8, 24)
        self.body_layout.setSpacing(14)
        self.body_layout.addStretch(1)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("Results")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.body)
        self.more_button = QPushButton()
        self.more_button.setObjectName("Quiet")
        self.more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_button.clicked.connect(self.load_more)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(self.kind_combo)
        top.addWidget(self.query_edit, 1)
        top.addWidget(self.search_button)
        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.hadith_filters = QWidget()            # shown for the hadith; the narrators have their own
        row = QHBoxLayout(self.hadith_filters)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for text, widget in (("Match", self.mode_combo), (None, self.whole_words),
                             ("Book", self.book_combo), ("Language", self.language_combo)):
            if text:
                row.addSpacing(10)
                row.addWidget(_label(text, "FilterLabel"))
            row.addWidget(widget)
        self.people_filters = QWidget()
        row = QHBoxLayout(self.people_filters)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addSpacing(10)
        row.addWidget(_label("Tradition", "FilterLabel"))
        row.addWidget(self.tradition_combo)
        self.people_filters.hide()
        filters.addWidget(self.hadith_filters)
        filters.addWidget(self.people_filters)
        filters.addStretch(1)
        filters.addWidget(self.summary)

        column = QWidget()
        # the column follows the window (Bayram, 2026-10-04: like the Narrators page), with margins only
        inner = QVBoxLayout(column)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(12)
        inner.addLayout(top)
        inner.addLayout(filters)
        inner.addWidget(self.scroll, 1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(36, 28, 28, 12)
        layout.addWidget(column, 1)          # no alignment: an aligned widget keeps its own width and does not follow the window

        self._open_database()

    # ------------------------------------------------------------ database
    def _open_database(self) -> None:
        try:
            self._conn = db.connect(reset_old=True)
        except db.SchemaReset as exc:
            self._notice = str(exc)
            self._conn = db.connect()
        except Exception as exc:  # shown to the user, in full, rather than crashing the window
            self._conn = None
            self._show_error(exc)
            return
        self._sync_with_database(force=True)

    def _show_error(self, exc: Exception) -> None:
        """The database could not be opened: say why and what to do, in the middle of the page."""
        from isnady import __version__
        from isnady.data.paths import db_path

        self.query_edit.setEnabled(False)
        self.search_button.setEnabled(False)
        for widget in (self.kind_combo, self.mode_combo, self.whole_words, self.book_combo, self.language_combo):
            widget.setEnabled(False)
        self._clear_body()
        box_widget = QWidget()
        box = QVBoxLayout(box_widget)
        box.setContentsMargins(8, 40, 8, 8)
        box.setSpacing(10)
        title = _label("The database could not be opened", "Hero", wrap=True)
        title.setFont(theme.reading_font(24, bold=True))
        message = str(exc)
        advice = ""
        if "newer than this isnady supports" in message:
            advice = ("The data was last opened by a newer isnady than the one running now "
                      f"({__version__}). Nothing is lost: update isnady, or if you work from the source folder, "
                      "reinstall it there with <code>pip install -e .</code>")
        detail = _label(
            f"{html.escape(message)}<br><br>{advice}<br><br>Database: <code>{html.escape(str(db_path()))}</code>",
            "Lead", wrap=True, selectable=True)
        detail.setTextFormat(Qt.TextFormat.RichText)
        box.addWidget(title)
        box.addWidget(detail)
        self.body_layout.addWidget(box_widget)
        self.body_layout.addStretch(1)
        self._status("Database not opened")

    def _sync_with_database(self, force: bool = False) -> None:
        """Index new texts and refresh the filters when another program changed the data."""
        if self._conn is None:
            return
        version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        if not force and version == self._data_version:
            return
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            core.ensure_index(self._conn, progress=self._status)
            core_isnad.ensure_isnads(self._conn, progress=self._status)
            core_narrators.link_narrators(self._conn, progress=self._status)
        finally:
            QGuiApplication.restoreOverrideCursor()
        self._data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
        self.__dict__.pop("_person_cache", None)
        self.data_changed.emit()
        self._fill_filters()
        hadith = self._conn.execute("SELECT COUNT(*) FROM hadiths").fetchone()[0]
        books = self._conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0]
        self._status(f"{hadith:,} hadith in {books} book{'s' if books != 1 else ''}")
        if not self._page:
            self._show_start()

    def _fill_filters(self) -> None:
        current_book = self.book_combo.currentData()
        current_lang = self.language_combo.currentData()
        for combo in (self.book_combo, self.language_combo):
            combo.blockSignals(True)
            combo.clear()
        self.book_combo.addItem("All books", None)
        for key, name, count in core.list_collections(self._conn):
            self.book_combo.addItem(f"{name} ({count:,})", key)
        self.language_combo.addItem("All languages", None)
        for language in core.list_languages(self._conn):
            self.language_combo.addItem(language, language)
        for combo, value in ((self.book_combo, current_book), (self.language_combo, current_lang)):
            combo.setCurrentIndex(max(combo.findData(value), 0))
            combo.blockSignals(False)

    # -------------------------------------------------------------- search
    def _query(self, offset: int) -> core.SearchQuery:
        book = self.book_combo.currentData()
        language = self.language_combo.currentData()
        return core.SearchQuery(
            text=self.query_edit.text(), mode=self.mode_combo.currentData(),
            whole_words=self.whole_words.isChecked(),
            collections=[book] if book else [], languages=[language] if language else [],
            limit=PAGE_SIZE, offset=offset,
        )

    def _related(self, hadith_id: int) -> list:
        from isnady.core import takhrij

        try:
            return takhrij.related(self._conn, hadith_id)
        except Exception:      # an older database without the table: no line, never an error
            return []

    def _fetch(self, offset: int):
        """One page of results: word search, or search by meaning (YZ1)."""
        query = self._query(offset)
        if query.mode != "meaning":
            return core.search(self._conn, query)
        from isnady.core import semantic

        try:
            meaning = semantic.search(self._conn, query)
        except semantic.NotAvailable as exc:
            self._page = None
            self._show_meaning_notice(str(exc))
            return None
        for result, score in zip(meaning.results, meaning.scores):
            self._scores[result.hadith_id] = score
        self._meaning_stale = semantic.status(self._conn).get("stale", False)
        return core.SearchPage(query, [], meaning.total, meaning.results, True, meaning.elapsed_ms)

    def _show_meaning_notice(self, message: str) -> None:
        """Meaning search cannot run yet: say why, and offer to build the index when that is the reason."""
        from PySide6.QtWidgets import QPushButton

        self._clear_body()
        box_widget = QWidget()
        box = QVBoxLayout(box_widget)
        box.setContentsMargins(8, 40, 8, 8)
        box.setSpacing(10)
        title = _label("Search by meaning", "Hero", wrap=True)
        title.setFont(theme.reading_font(24, bold=True))
        text = _label(message + "\n\nSearch by meaning finds hadith that say the same thing in other words or in "
                      "another language. It learns from the texts imported here; building it takes a few seconds "
                      "to a minute.", "Lead", wrap=True)
        box.addWidget(title)
        box.addWidget(text)
        if "not built" in message:
            build = QPushButton("Build the meaning index now")
            build.setObjectName("Primary")
            build.clicked.connect(self.build_meaning_index)
            row = QHBoxLayout()
            row.addWidget(build)
            row.addStretch(1)
            box.addLayout(row)
        self.body_layout.addWidget(box_widget)
        self.body_layout.addStretch(1)
        self.summary.setText("")

    def build_meaning_index(self) -> None:
        """Build the meaning index in the background (its own database connection)."""
        from PySide6.QtCore import QThread, Signal

        from isnady.core import semantic

        missing = semantic.requirements_message()
        if missing:
            self._show_meaning_notice(missing)
            return
        if getattr(self, "_meaning_worker", None) is not None:
            return

        class _Build(QThread):
            progress = Signal(str)
            done = Signal(bool, str)

            def run(self) -> None:
                from isnady.data import db as _db

                conn = _db.connect()
                try:
                    from isnady.core import takhrij

                    meta = semantic.build(conn, progress=self.progress.emit)
                    found = takhrij.build(conn, progress=self.progress.emit)
                    self.done.emit(True, f"AI indexes ready: meaning ({meta['documents']:,} hadith, {meta['dims']} "
                                         f"concepts); takhrij ({found['same']:,} + {found['same_report']:,} pairs)")
                except Exception as exc:  # shown to the user, never lost
                    self.done.emit(False, f"Meaning index failed: {exc}")
                finally:
                    conn.close()

        worker = _Build()
        self._meaning_worker = worker                   # kept until Qt reports it finished
        worker.progress.connect(self._status)
        worker.done.connect(self._meaning_built)
        worker.finished.connect(lambda: setattr(self, "_meaning_worker", None))
        self._status("Building the AI indexes (meaning, takhrij)…")
        worker.start()

    def _meaning_built(self, ok: bool, message: str) -> None:
        self._status(message)
        semantic_mode = self.mode_combo.currentData() == "meaning"
        if ok and self.query_edit.text().strip() and (semantic_mode or self._results):
            self.run_search()

    def _rerun_if_searched(self, *_args) -> None:
        if (self._page is not None or self._found is not None) and self.query_edit.text().strip():
            self.run_search()

    def kind(self) -> str:
        return self.kind_combo.currentData()

    def _kind_changed(self, *_args) -> None:
        """Another thing to search: its own filters, its own hint; the words typed are searched again."""
        kind = self.kind()
        self.hadith_filters.setVisible(kind == "hadith")
        self.people_filters.setVisible(kind == "narrators")
        self.query_edit.setPlaceholderText(KIND_TEXT[kind][0])
        self.summary.setText("")
        if self.query_edit.text().strip():
            self.run_search()
        else:
            self._page, self._found = None, None
            self._show_start()
        self.query_edit.setFocus()

    def search_for(self, text: str) -> None:
        self.query_edit.setText(text)
        self.run_search()

    def run_search(self) -> None:
        if self._conn is None:
            return
        self._sync_with_database()
        if not self.query_edit.text().strip():
            self._page, self._found = None, None
            self._show_start()
            return
        if self.kind() != "hadith":
            self._search_people()
            return
        self._found = None
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._scores = {}
            page = self._fetch(0)
            if page is None:
                return
            self._page = page
            self._results = list(self._page.results)
            self._render()
        finally:
            QGuiApplication.restoreOverrideCursor()

    def load_more(self) -> None:
        if self._found is not None:
            self._show_people(more=True)
            return
        if not self._page:
            return
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            page = self._fetch(len(self._results))
            if page is None:
                return
            self._page = page
            self._results.extend(page.results)
            self._append_cards(page.results)
            self._update_summary()
        finally:
            QGuiApplication.restoreOverrideCursor()

    # -------------------------------------------------------------- render
    def _clear_body(self) -> None:
        """Remove every card; the "more" button is kept and re-added, never deleted."""
        self._batch_token = getattr(self, "_batch_token", 0) + 1     # cancels batches still queued
        self._pending = []
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget is None:
                continue
            if widget is self.more_button:
                widget.setParent(None)
                continue
            widget.setParent(None)
            widget.deleteLater()

    def _show_start(self) -> None:
        self._clear_body()
        self.summary.setText("")
        hadith = self._conn.execute("SELECT COUNT(*) FROM hadiths").fetchone()[0] if self._conn else 0

        hero = QWidget()
        box = QVBoxLayout(hero)
        box.setContentsMargins(8, 40, 8, 8)
        box.setSpacing(10)
        arabic = _label("وَمَا يَنْطِقُ عَنِ الْهَوَى", "HeroArabic")
        arabic.setFont(theme.reading_font(26))
        arabic.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute)
        kind = self.kind()
        title = _label(KIND_TEXT[kind][1], "Hero")
        title.setFont(theme.reading_font(30, bold=True))
        box.addWidget(arabic)
        box.addWidget(title)

        if self._notice:
            box.addWidget(_label(html.escape(self._notice), "Lead", wrap=True))
        if hadith == 0 and kind == "hadith":
            lead = _label(
                "The database is empty. Import a source from a terminal, for example:<br>"
                "<code>iy import fawazahmed0 https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/"
                "editions.json --book bukhari --language tur --language ara --license Unlicense</code><br>"
                "Importing from inside the app arrives with User Resources.",
                "Lead", wrap=True, selectable=True)
            lead.setTextFormat(Qt.TextFormat.RichText)
            box.addWidget(lead)
        elif kind == "narrators" and not self._conn.execute("SELECT 1 FROM persons LIMIT 1").fetchone():
            box.addWidget(_label("No narrators yet: import Ibn Hajar's Taqrib or al-Najashi's Rijal "
                                 "(File → Data Sources), or from a terminal: iy catalog import taqrib",
                                 "Lead", wrap=True))
        else:
            lead = _label(KIND_TEXT[kind][2] or (
                "Arabic diacritics and letter forms are ignored, so الاعمال finds الأَعْمَالُ. "
                "Turkish and other Latin-script text ignores case and accents. Try one of these:"),
                "Lead", wrap=True)
            lead.setMaximumWidth(640)
            box.addWidget(lead)
            examples = QHBoxLayout()
            examples.setSpacing(8)
            for word in KIND_TEXT[kind][3]:
                button = QPushButton(word)
                button.setObjectName("Example")
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setFont(theme.reading_font(13))
                button.clicked.connect(lambda _c=False, w=word: self.search_for(w))
                examples.addWidget(button)
            examples.addStretch(1)
            box.addSpacing(4)
            box.addLayout(examples)
        self.body_layout.addWidget(hero)
        self.body_layout.addStretch(1)

    def _render(self) -> None:
        self._clear_body()
        page = self._page
        if page.total == 0:
            empty = QWidget()
            box = QVBoxLayout(empty)
            box.setContentsMargins(8, 40, 8, 8)
            title = _label(f"Nothing found for “{page.query.text.strip()}”", "Hero", wrap=True)
            title.setFont(theme.reading_font(20, bold=True))
            hint = "Try fewer words, “Any word”, or turn off “Whole words only”." if (
                len(page.terms) > 1 or page.query.whole_words) else "Try another spelling, or search in another language."
            box.addWidget(title)
            box.addWidget(_label(hint, "Lead", wrap=True))
            self.body_layout.addWidget(empty)
            self.body_layout.addStretch(1)
            self._update_summary()
            return
        self.body_layout.addStretch(1)
        self._append_cards(page.results)
        self._update_summary()
        self.scroll.verticalScrollBar().setValue(0)

    def _append_cards(self, results: list[core.SearchResult]) -> None:
        """Queue cards; they are added a few at a time so the window never freezes."""
        self.more_button.setParent(None)
        last = self.body_layout.count() - 1
        if last < 0 or self.body_layout.itemAt(last).spacerItem() is None:
            self.body_layout.addStretch(1)
        self._pending = list(results)
        self._batch_token = getattr(self, "_batch_token", 0) + 1
        self._add_batch(self._batch_token, FIRST_BATCH)

    def _add_batch(self, token: int, count: int) -> None:
        """Add a few cards, then let the window breathe before adding more."""
        if token != self._batch_token or self._conn is None:
            return                                   # a newer search replaced this one
        stretch = self.body_layout.takeAt(self.body_layout.count() - 1)   # trailing stretch
        self.more_button.setParent(None)
        for result in self._pending[:count]:
            self.body_layout.addWidget(self.make_card(result, getattr(self, "_scores", {}).get(result.hadith_id)))
        self._pending = self._pending[count:]
        if self._pending:
            if stretch is not None:
                self.body_layout.addItem(stretch)
            QTimer.singleShot(0, lambda: self._add_batch(token, NEXT_BATCH))
            return
        remaining = self._page.total - len(self._results)
        if remaining > 0:
            self.more_button.setText(f"Show {min(PAGE_SIZE, remaining)} more ({remaining:,} left)")
            self.body_layout.addWidget(self.more_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.body_layout.addStretch(1)

    def _update_summary(self) -> None:
        page = self._page
        if page.total == 0:
            self.summary.setText("")
            return
        note = "" if page.used_index else ", index unavailable"
        if page.query.mode == "meaning":
            note = " by meaning" + (" · index older than the data (Tools → Build Meaning Index)"
                                    if getattr(self, "_meaning_stale", False) else "")
        self.summary.setText(f"{page.total:,} hadith, {page.elapsed_ms} ms{note}")

    # -------------------------------------------------------------- people (S3)
    def _search_people(self) -> None:
        """Narrators (both traditions, or one) or scholars whose names fit the words typed."""
        from isnady.core import scholars as core_scholars

        text = self.query_edit.text().strip()
        self._page = None
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            import time

            start = time.perf_counter()
            if self.kind() == "narrators":
                self._found, self._people_total = core_narrators.find(
                    self._conn, text, self.tradition_combo.currentData() or None)
            else:
                self._found = core_scholars.search(self._conn, text)
                self._people_total = len(self._found)
            self._people_ms = int((time.perf_counter() - start) * 1000)
        finally:
            QGuiApplication.restoreOverrideCursor()
        self._show_people()

    def _show_people(self, more: bool = False) -> None:
        from isnady.gui import people_results

        if not more:
            self._clear_body()
            self._people_shown = 0
            self.scroll.verticalScrollBar().setValue(0)
        kind = self.kind()
        if not self._found:
            empty = QWidget()
            box = QVBoxLayout(empty)
            box.setContentsMargins(8, 40, 8, 8)
            title = _label(f"No {kind} found for “{self.query_edit.text().strip()}”", "Hero", wrap=True)
            title.setFont(theme.reading_font(20, bold=True))
            box.addWidget(title)
            box.addWidget(people_results.empty_hint(kind))
            self.body_layout.addWidget(empty)
            self.body_layout.addStretch(1)
            self.summary.setText("")
            return
        self.more_button.setParent(None)
        last = self.body_layout.count() - 1
        if last >= 0 and self.body_layout.itemAt(last).spacerItem() is not None:
            self.body_layout.takeAt(last)
        typed = self.query_edit.text().strip()
        if not more and all(r.get("weak") for r in self._found):
            self.body_layout.addWidget(_label(
                f"No name reads “{typed}”. Arabic is written without its short vowels, so isnady first matches the "
                "consonants — these names have the consonants typed, but their readings sound different.",
                "Lead", wrap=True))
        elif not more and all(r.get("close") for r in self._found):
            self.body_layout.addWidget(_label(
                f"Nothing is written exactly “{typed}”. These are the closest spellings: a letter typed twice or "
                "missing, or written as Turkish and English differ (h and kh, z and dh).", "Lead", wrap=True))
        batch = self._found[self._people_shown:self._people_shown + PAGE_SIZE]
        for index, row in enumerate(batch, start=self._people_shown):
            if row.get("weak") and index > 0 and not self._found[index - 1].get("weak"):
                # the weaker matches, after the others, under their own heading (S4)
                head = _label("Weaker matches", "CardTitle")
                head.setFont(theme.reading_font(15, bold=True))
                why = _label(f"The same consonants as “{typed}”, but the names read differently — Arabic is "
                             "written without its short vowels, so the consonants are matched first.", "Caption",
                             wrap=True)
                self.body_layout.addSpacing(10)
                self.body_layout.addWidget(head)
                self.body_layout.addWidget(why)
            if kind == "narrators":
                card = people_results.person_card(row, self.open_person.emit)
            else:
                card = people_results.scholar_card(row, self.open_scholar.emit)
            self.body_layout.addWidget(card)
        self._people_shown += len(batch)
        remaining = len(self._found) - self._people_shown
        if remaining > 0:
            self.more_button.setText(f"Show {min(PAGE_SIZE, remaining)} more ({remaining:,} left)")
            self.body_layout.addWidget(self.more_button, 0, Qt.AlignmentFlag.AlignHCenter)
        elif self._people_total > len(self._found):
            note = _label(f"The {len(self._found):,} closest of {self._people_total:,} are shown: "
                          "add a word to find the others.", "Caption")
            note.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.body_layout.addWidget(note)
        self.body_layout.addStretch(1)
        noun = {"narrators": ("narrator", "narrators"), "scholars": ("scholar", "scholars")}[kind]
        total = self._people_total
        close = sum(1 for r in self._found if r.get("close"))
        weak = sum(1 for r in self._found if r.get("weak"))
        note = "" if not close else (" — by close spelling" if close == len(self._found)
                                     else f", {close:,} by close spelling")
        if weak:
            note += " — all weaker matches" if weak == len(self._found) else f", {weak:,} weaker"
        self.summary.setText(f"{total:,} {noun[total != 1]}{note}, {self._people_ms} ms")

    def release(self) -> None:
        """Let go of the cards before a new theme; retheme() draws them again (UI5-P). The start page and the
        "nothing found" notice are small and stay."""
        if self._found or (self._page is not None and self._page.total):
            self._clear_body()

    def retheme(self) -> None:
        """Redraw the results with the current theme and text size."""
        if self._found is not None:
            scroll = self.scroll.verticalScrollBar().value()
            shown = self._people_shown
            self._show_people()
            while self._people_shown < shown:
                self._show_people(more=True)
            self.scroll.verticalScrollBar().setValue(scroll)
            return
        if self._page is not None and self._page.total:
            scroll = self.scroll.verticalScrollBar().value()
            self._clear_body()
            self.body_layout.addStretch(1)
            self._append_cards(self._results)
            self.scroll.verticalScrollBar().setValue(scroll)

    def focus_search(self) -> None:
        self.query_edit.setFocus()
        self.query_edit.selectAll()

    def rebuild_index(self) -> int:
        if self._conn is None:
            return 0
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            count = core.rebuild_index(self._conn, progress=self._status)
        finally:
            QGuiApplication.restoreOverrideCursor()
        self._data_version = None
        self._sync_with_database(force=True)
        if self._page is not None and self.query_edit.text().strip():
            self.run_search()
        return count

    def connection(self):
        return self._conn

    def make_card(self, result: core.SearchResult, score: float | None = None, in_book: bool = False) -> "ResultCard":
        """The card of one hadith — its chain, identified narrators, other narrations — as every page shows it.
        in_book: the card is already in its book (the reader), so it has no "In its book" link."""
        if not in_book:
            # the content languages (L1): the texts in the languages chosen, and any text the search matched
            from dataclasses import replace

            from isnady.core import language

            kept = [t for t in result.texts if language.shows(t.language) or t.spans]
            if kept and len(kept) != len(result.texts):
                result = replace(result, texts=kept)
        chains = core_isnad.chain(self._conn, result.hadith_id)
        chain = chains[0] if chains else None
        card = ResultCard(result, chain, self.open_chain.emit, self._people(chain), score, self._related(result.hadith_id),
                          None if in_book else self.open_book.emit)
        card.setProperty("hadith_id", result.hadith_id)
        return card

    def _people(self, chain: dict | None) -> dict:
        """Descriptions of the identified narrators of a chain, cached for the session."""
        cache = self.__dict__.setdefault("_person_cache", {})
        out = {}
        for link in (chain or {}).get("links", []):
            pid = link.get("person_id")
            if pid:
                if pid not in cache:
                    cache[pid] = core_narrators.describe(self._conn, pid)
                out[pid] = cache[pid]
        return out

    def identify_narrators(self) -> dict:
        if self._conn is None:
            return {}
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            stats = core_narrators.link_narrators(self._conn, progress=self._status, rebuild=True)
        finally:
            QGuiApplication.restoreOverrideCursor()
        self.__dict__.pop("_person_cache", None)
        self.data_changed.emit()
        self.retheme()
        return stats

    def rebuild_chains(self) -> dict:
        if self._conn is None:
            return {}
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            stats = core_isnad.ensure_isnads(self._conn, progress=self._status, rebuild=True)
        finally:
            QGuiApplication.restoreOverrideCursor()
        self.data_changed.emit()
        self.retheme()
        return stats

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt name)
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        super().closeEvent(event)
