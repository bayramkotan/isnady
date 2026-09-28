"""Search page: hadith text search over every imported edition.

All matching logic is in isnady.core.search; this page only collects the
query, calls the core and renders the results as cards.
"""

import html
import sqlite3

from PySide6.QtCore import Qt
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

from isnady.core import search as core
from isnady.data import db
from isnady.gui import theme
from isnady.gui.widgets import FlowLayout, expanding_width_policy

PAGE_SIZE = 25
COLUMN_MAX = 1000   # reading column; keeps translation lines readable on wide windows
MODE_LABELS = (("all", "All words"), ("any", "Any word"), ("phrase", "Exact phrase"))
EXAMPLES = ("النيات", "الصلاة", "niyet", "komşu")
ARABIC_PT = 20
TRANSLATION_PT = 12.5


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
    def __init__(self, result: core.SearchResult) -> None:
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
        head.addStretch(1)
        box.addLayout(head)

        if result.grades:
            pills = FlowLayout(spacing=6)
            for grader, grade in result.grades:
                pill = _label(f"{html.escape(grader)}: <b>{html.escape(grade)}</b>", "Pill")
                pill.setTextFormat(Qt.TextFormat.RichText)
                pill.setToolTip(f"{grader} graded this hadith: {grade}")
                pills.addWidget(pill)
            box.addLayout(pills)
            box.addSpacing(4)

        for text in result.texts:
            body = _highlight(text.text, text.spans, t.gilt)
            if text.direction == "rtl":
                label = _label(f"<div dir='rtl' align='right' style='line-height:125%'>{body}</div>",
                               "ArabicText", wrap=True, selectable=True)
                label.setTextFormat(Qt.TextFormat.RichText)
                label.setFont(theme.reading_font(ARABIC_PT, scaled=True))
                label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute
                                   | Qt.AlignmentFlag.AlignTop)
                box.addWidget(label)
            else:
                frame = QFrame()
                frame.setObjectName("Translation")
                inner = QVBoxLayout(frame)
                inner.setContentsMargins(16, 2, 0, 2)
                label = _label(f"<div style='line-height:115%'>{body}</div>", "TranslationText",
                               wrap=True, selectable=True)
                label.setTextFormat(Qt.TextFormat.RichText)
                label.setFont(theme.reading_font(TRANSLATION_PT, scaled=True))
                inner.addWidget(label)
                box.addWidget(frame)
            caption = _label(f"{text.language}, {text.edition_key}", "Caption")
            if text.direction == "rtl":
                caption.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
            box.addWidget(caption)


class SearchPage(QWidget):
    def __init__(self, status_message=None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._status = status_message or (lambda _m: None)
        self._conn: sqlite3.Connection | None = None
        self._data_version = None
        self._notice = ""
        self._page: core.SearchPage | None = None
        self._results: list[core.SearchResult] = []

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
        top.addWidget(self.query_edit, 1)
        top.addWidget(self.search_button)
        filters = QHBoxLayout()
        filters.setSpacing(8)
        for text, widget in (("Match", self.mode_combo), (None, self.whole_words),
                             ("Book", self.book_combo), ("Language", self.language_combo)):
            if text:
                filters.addSpacing(10)
                filters.addWidget(_label(text, "FilterLabel"))
            filters.addWidget(widget)
        filters.addStretch(1)
        filters.addWidget(self.summary)

        column = QWidget()
        column.setMaximumWidth(COLUMN_MAX)
        inner = QVBoxLayout(column)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(12)
        inner.addLayout(top)
        inner.addLayout(filters)
        inner.addWidget(self.scroll, 1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(36, 28, 28, 12)
        layout.addWidget(column, 1, Qt.AlignmentFlag.AlignHCenter)

        self._open_database()

    # ------------------------------------------------------------ database
    def _open_database(self) -> None:
        try:
            self._conn = db.connect(reset_old=True)
        except db.SchemaReset as exc:
            self._notice = str(exc)
            self._conn = db.connect()
        except Exception as exc:  # shown to the user rather than crashing the window
            self._conn = None
            self.summary.setText(f"Could not open the database: {exc}")
            self.setEnabled(False)
            return
        self._sync_with_database(force=True)

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
        finally:
            QGuiApplication.restoreOverrideCursor()
        self._data_version = self._conn.execute("PRAGMA data_version").fetchone()[0]
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

    def _rerun_if_searched(self, *_args) -> None:
        if self._page is not None and self.query_edit.text().strip():
            self.run_search()

    def search_for(self, text: str) -> None:
        self.query_edit.setText(text)
        self.run_search()

    def run_search(self) -> None:
        if self._conn is None:
            return
        self._sync_with_database()
        if not self.query_edit.text().strip():
            self._page = None
            self._show_start()
            return
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._page = core.search(self._conn, self._query(0))
            self._results = list(self._page.results)
            self._render()
        finally:
            QGuiApplication.restoreOverrideCursor()

    def load_more(self) -> None:
        if not self._page:
            return
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            page = core.search(self._conn, self._query(len(self._results)))
            self._page = page
            self._results.extend(page.results)
            self._append_cards(page.results)
            self._update_summary()
        finally:
            QGuiApplication.restoreOverrideCursor()

    # -------------------------------------------------------------- render
    def _clear_body(self) -> None:
        """Remove every card; the "more" button is kept and re-added, never deleted."""
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
        title = _label("Search the hadith", "Hero")
        title.setFont(theme.reading_font(30, bold=True))
        box.addWidget(arabic)
        box.addWidget(title)

        if self._notice:
            box.addWidget(_label(html.escape(self._notice), "Lead", wrap=True))
        if hadith == 0:
            lead = _label(
                "The database is empty. Import a source from a terminal, for example:<br>"
                "<code>isnady-cli import fawazahmed0 https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/"
                "editions.json --book bukhari --language tur --language ara --license Unlicense</code><br>"
                "Importing from inside the app arrives with User Resources.",
                "Lead", wrap=True, selectable=True)
            lead.setTextFormat(Qt.TextFormat.RichText)
            box.addWidget(lead)
        else:
            lead = _label(
                "Arabic diacritics and letter forms are ignored, so الاعمال finds الأَعْمَالُ. "
                "Turkish and other Latin-script text ignores case and accents. Try one of these:",
                "Lead", wrap=True)
            lead.setMaximumWidth(640)
            box.addWidget(lead)
            examples = QHBoxLayout()
            examples.setSpacing(8)
            for word in EXAMPLES:
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
        # remove the trailing "more" button and stretch, add cards, put them back
        self.more_button.setParent(None)
        last = self.body_layout.count() - 1
        if last >= 0 and self.body_layout.itemAt(last).spacerItem() is not None:
            self.body_layout.takeAt(last)
        for result in results:
            self.body_layout.addWidget(ResultCard(result))
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
        self.summary.setText(f"{page.total:,} hadith, {page.elapsed_ms} ms{note}")

    def retheme(self) -> None:
        """Redraw the results with the current theme and text size."""
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

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt name)
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        super().closeEvent(event)
