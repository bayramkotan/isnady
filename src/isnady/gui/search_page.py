"""Search page: hadith text search over every imported edition, and the people of hadith.

The drop-down before the search field chooses what is searched (S3): Hadith (the default), Narrators (both
traditions) or Scholars. All matching logic is in isnady.core (search, narrators.find, scholars.search); this page
only collects the query, calls the core and renders the results as cards.
"""

import html
import sqlite3

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
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
from isnady.core import recent as core_recent
from isnady.core import search as core
from isnady.data import db
from isnady.gui import theme
from isnady.gui.chain_widgets import ChainStrip
from isnady.gui.widgets import BookPicker, FlowLayout, LanguagePicker, TextBlock, expanding_width_policy
from isnady.core import titles
from isnady.core.i18n import N_, n_, tr

PAGE_SIZE = 25
FIRST_BATCH = 4     # cards shown at once; the rest follow in small batches
NEXT_BATCH = 3
MODE_LABELS = (("all", N_("All words")), ("any", N_("Any word")), ("phrase", N_("Exact phrase")),
               ("meaning", N_("By meaning (AI)")))
EXAMPLES = ("النيات", "الصلاة", "niyet", "komşu")
KINDS = (("hadith", N_("Hadith")), ("narrators", N_("Narrators")), ("scholars", N_("Scholars")))
KIND_TEXT = {   # placeholder, start-page title, start-page lead, examples
    "hadith": (N_("Search the hadith: a word or phrase in Arabic, Turkish or English (? an unknown letter, * any letters)"), N_("Search the hadith"), "",
               EXAMPLES),
    "narrators": (N_("Search the narrators by name: Arabic, English or Turkish spelling"), N_("Search the narrators"),
                  N_("Every narrator of both traditions — Ibn Hajar's Taqrib for the Sunni books, al-Najashi's Rijal for "
                     "the Shia books — by any part of his name. Names are matched by their letters, without vowels or "
                     "diacritics, so “Abu Hurayra”, “Ebû Hüreyre” and أبو هريرة all find him. Try one of these:"),
                  ("Abu Hurayra", "الزهري", "Ibn Umar", "Âişe", "Zurara")),
    "scholars": (N_("Search the scholars of hadith: a name or a book"), N_("Search the scholars"),
                 N_("The compilers of the books, the scholars who graded their hadith and the critics of narrators — "
                    "by name in any spelling, or by the title of a work. Try one of these:"),
                 ("Buhârî", "Albani", "ابن حجر", "Riyad al-Salihin")),
}
TRADITIONS = (("", N_("Both traditions")), ("sunni", N_("Sunni")), ("shia", N_("Shia")))


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


def _more_languages(conn, imported: list[str]) -> list[str]:
    """Languages the imported books have in isnady's catalog (isnady-data) that are not imported here."""
    from isnady.core import catalog

    keys = {r[0] for r in conn.execute("SELECT key FROM collections")}
    have = set(imported)
    out: list[str] = []
    try:
        entries = catalog.builtin_entries()
    except Exception:              # no catalog: nothing to offer
        return []
    for e in entries:
        if getattr(e, "book", None) in keys:
            for code in getattr(e, "languages", None) or []:
                name = catalog.language_label(code)
                if name not in have and name not in out:
                    out.append(name)
    return out


class ResultCard(QFrame):
    def __init__(self, result: core.SearchResult, chain: dict | None = None, open_chain=None,
                 people: dict | None = None, score: float | None = None, related: list | None = None,
                 open_book=None, folded: list | None = None, chains: list | None = None,
                 on_person=None, on_name=None, on_end=None) -> None:
        super().__init__()
        self.setObjectName("Card")
        t = theme.current()
        box = QVBoxLayout(self)
        box.setContentsMargins(26, 20, 26, 20)
        box.setSpacing(10)

        head = QHBoxLayout()
        title = _label(titles.book(result.collection_key, result.collection_name), "CardTitle")
        title.setFont(theme.reading_font(15, bold=True, scaled=True))
        number = _label(tr("hadith {number}", number=result.number), "CardNumber")
        head.addWidget(title)
        head.addSpacing(8)
        head.addWidget(number, 0, Qt.AlignmentFlag.AlignBaseline)
        if score is not None:
            meaning = _label(f"meaning {score:.2f}", "CardNumber")
            meaning.setToolTip(tr("How close this hadith is in meaning to the search, from 0 to 1: shared words and shared concepts "
                                 "learnt from the Arabic texts and their translations.\nA measure of closeness, not of authenticity."))
            head.addSpacing(10)
            head.addWidget(meaning, 0, Qt.AlignmentFlag.AlignBaseline)
        head.addStretch(1)
        from isnady.gui.bookmarks_page import BookmarkButton

        first = next((x.text for x in result.texts if x.language != "Arabic"), result.texts[0].text if result.texts else "")
        head.addWidget(BookmarkButton("hadith", f"{result.collection_key}:{result.number}",
                                      f"{titles.book(result.collection_key, result.collection_name)} {result.number}",
                                      " ".join((first or "").split())[:160]))
        head.addSpacing(6)
        if open_book is not None:
            book = QPushButton(tr("In its book"))
            book.setObjectName("Link")
            book.setCursor(Qt.CursorShape.PointingHandCursor)
            book.setToolTip(tr("Read this hadith where it stands in its book, among the hadith of its chapter"))
            book.clicked.connect(lambda: open_book(result.hadith_id))
            head.addWidget(book)
            head.addSpacing(14)
        if open_chain is not None:
            view = QPushButton(tr("View chain"))
            view.setObjectName("Link")
            view.setCursor(Qt.CursorShape.PointingHandCursor)
            view.setToolTip(tr("Open this hadith's chain of transmission"))
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
            also = _label(tr("Also narrated in:") + " " + "&nbsp;&nbsp;|&nbsp;&nbsp;".join(parts), "Caption", wrap=True)
            also.setTextFormat(Qt.TextFormat.RichText)
            also.setToolTip(tr("Other narrations of this hadith found by comparing the texts (takhrij).\nUpright numbers: the "
                              "same text. Italic: probably the same report (the texts overlap and the same Companion narrates "
                              "both).\nClick a number to open it."))
            if open_chain is not None:
                also.linkActivated.connect(lambda hid: open_chain(int(hid)))
            box.addWidget(also)
        drawn = [c for c in (chains or ([chain] if chain else [])) if c["links"]]
        if drawn:
            if len(drawn) > 1:
                # a tahwil: the compiler joined roads in one hadith — each drawn (2026-10-13)
                box.addWidget(_label(n_("{n} chain", "{n} chains of this hadith", len(drawn)), "ChainCount"))
            for i, c in enumerate(drawn, 1):
                if len(drawn) > 1:
                    box.addWidget(_label(tr("Chain {i}", i=i), "Caption"))
                box.addWidget(ChainStrip(c, people, on_person=on_person, on_name=on_name, on_end=on_end))
            box.addSpacing(6)

        if result.grades:
            pills = FlowLayout(spacing=6)
            for grader, grade in result.grades:
                pill = _label(f"{html.escape(grader)}: <b>{html.escape(grade)}</b>", "Pill")
                pill.setTextFormat(Qt.TextFormat.RichText)
                from isnady.core import learn
                from isnady.core.grades import group as grade_group

                meaning = learn.for_group(grade_group(grade))
                pill.setToolTip(tr("{grader} graded this hadith: {grade}", grader=grader, grade=grade) + (f"\n\n{meaning}" if meaning else ""))
                pills.addWidget(pill)
            box.addLayout(pills)
            box.addSpacing(4)

        for text in result.texts:
            self._add_text(box, text, t)
        if folded:
            # the languages not chosen in Settings → Books and languages: behind an arrow, opened on a click
            names = ", ".join(dict.fromkeys(x.language for x in folded))
            more = QPushButton(tr("▸  Other languages: {names}", names=names))
            more.setObjectName("Link")
            more.setCursor(Qt.CursorShape.PointingHandCursor)
            more.setToolTip(tr("Languages you chose not to show (Settings → Books and languages). Click to show them here."))
            holder = QWidget()
            inner = QVBoxLayout(holder)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.setSpacing(10)
            holder.hide()
            built = []

            def flip(_c=False, h=holder, b=more, lay=inner) -> None:
                if not built:
                    for x in folded:
                        self._add_text(lay, x, theme.current())
                    built.append(True)
                h.setVisible(not h.isVisible())
                b.setText(("▾  " if h.isVisible() else "▸  ") + b.text()[3:])
            more.clicked.connect(flip)
            row = QHBoxLayout()
            row.addWidget(more)
            row.addStretch(1)
            box.addLayout(row)
            box.addWidget(holder)

    @staticmethod
    def _add_text(box: QVBoxLayout, text, t) -> None:
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
        caption = _label(f"{tr(text.language)}, {text.edition_key}", "Caption")
        if text.direction == "rtl":
            caption.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
        box.addWidget(caption)


class SearchPage(QWidget):
    open_chain = Signal(int)          # hadith id; the main window shows it on the Isnad Chains page
    open_book = Signal(int)           # hadith id; the main window opens its book at its chapter (Books)
    open_person = Signal(int, str)    # person id, tradition; Narrators shows him
    open_scholar = Signal(str)        # scholar id; Hadith Scholars shows him
    open_narrator = Signal(int)       # a narrator of a chain on a card (Search, Books) → Narrators
    open_tree = Signal(str, object)   # the Prophet ﷺ or an Imam a chain reaches → his life in the Genealogies
    find_narrator = Signal(str)       # a name of a chain not identified → looked for among the narrators
    data_changed = Signal()
    wants_sources = Signal()          # "more languages": the main window opens File → Data Sources
    retry_requested = Signal()        # "Try again" after a locked database: the window is built again

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
        self._people_read = 0
        self._people_shown = 0

        # what is searched (S3): hadith by default, every time isnady starts
        self.kind_combo = QComboBox()
        self.kind_combo.setObjectName("SearchKind")
        self.kind_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        for key, label in KINDS:
            self.kind_combo.addItem(tr(label), key)
        self.kind_combo.setToolTip(tr("What to search: the text of the hadith, the narrators of both traditions by name, or the scholars "
                                     "of hadith"))
        self.kind_combo.currentIndexChanged.connect(self._kind_changed)

        # search bar; 🏠 brings the page back to how it opens (NAV1)
        self.home_button = QPushButton("⌂")
        self.home_button.setObjectName("Quiet")
        self.home_button.setStyleSheet("font-size: 17pt; padding: 0 10px;")
        self.home_button.setFixedHeight(40)
        self.home_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.home_button.setToolTip(tr("Back to the start: clear the search, the filters and the results (Alt+Home)"))
        self.home_button.clicked.connect(self.go_home)
        QShortcut(QKeySequence("Alt+Home"), self, activated=self.go_home)
        self.query_edit = QLineEdit()
        self.query_edit.setObjectName("SearchField")
        self.query_edit.setPlaceholderText(tr("Search the hadith: a word or phrase in Arabic, Turkish or English (? an unknown letter, * any letters)"))
        self.query_edit.setClearButtonEnabled(True)
        self.query_edit.returnPressed.connect(self.run_search)
        self.search_button = QPushButton(tr("Search"))
        self.search_button.setObjectName("Primary")
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_button.clicked.connect(self.run_search)

        # filters
        self.mode_combo = QComboBox()
        for key, label in MODE_LABELS:
            self.mode_combo.addItem(tr(label), key)
        self.mode_combo.currentIndexChanged.connect(
            lambda _i: self.whole_words.setEnabled(self.mode_combo.currentData() != "meaning"))
        self.whole_words = QCheckBox(tr("Whole words only"))
        self.whole_words.setToolTip(
            tr("Off: النيات also finds بالنيات, because Arabic words carry attached prefixes.\nOn: only the word "
              "standing on its own.")
        )
        self.book_combo = BookPicker()            # all books, all Sunni, all Shia, or any few ticked
        self.book_combo.changed.connect(self._rerun_if_searched)
        self.language_combo = LanguagePicker()     # all languages, or any few ticked (LANG3)
        self.language_combo.changed.connect(self._rerun_if_searched)
        self.language_combo.wants_import.connect(self.wants_sources.emit)
        for combo in (self.mode_combo,):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
            combo.currentIndexChanged.connect(self._rerun_if_searched)
        self.whole_words.toggled.connect(self._rerun_if_searched)
        self.tradition_combo = QComboBox()
        for key, label in TRADITIONS:
            self.tradition_combo.addItem(tr(label), key)
        self.tradition_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.tradition_combo.setToolTip(tr("Sunni: the narrators of Ibn Hajar's Taqrib. Shia: those of al-Najashi's Rijal.\nThe two are never "
                                          "matched to each other: each keeps its own terms."))
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
        top.addWidget(self.home_button)
        top.addWidget(self.kind_combo)
        top.addWidget(self.query_edit, 1)
        top.addWidget(self.search_button)
        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.hadith_filters = QWidget()            # shown for the hadith; the narrators have their own
        row = QHBoxLayout(self.hadith_filters)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for text, widget in ((tr("Match"), self.mode_combo), (None, self.whole_words),
                             (tr("Books"), self.book_combo), (tr("Language"), self.language_combo)):
            if text:
                row.addSpacing(10)
                row.addWidget(_label(text, "FilterLabel"))
            row.addWidget(widget)
        self.people_filters = QWidget()
        row = QHBoxLayout(self.people_filters)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addSpacing(10)
        row.addWidget(_label(tr("Tradition"), "FilterLabel"))
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
        title = _label(tr("The database could not be opened"), "Hero", wrap=True)
        title.setFont(theme.reading_font(24, bold=True))
        message = str(exc)
        advice = ""
        locked = "locked" in message.lower()
        if locked:
            advice = tr("Another isnady is still using the database — most often the window closed during the first "
                        "import, while the import goes on in the background. Wait until it finishes, or end it "
                        "(Windows: Task Manager → isnady or python → End task; Linux and macOS: "
                        "<code>pkill -f isnady</code>), then press Try again. Nothing is lost: a book cut short is "
                        "not kept and can be imported again from Data Sources.")
        elif "newer than this isnady supports" in message:
            advice = tr("The data was last opened by a newer isnady than the one running now ({version}). Nothing is "
                        "lost: update isnady, or if you work from the source folder, reinstall it there with "
                        "<code>pip install -e .</code>", version=__version__)
        detail = _label(
            tr("{message}<br><br>{advice}<br><br>Database: <code>{db_path}</code>", message=html.escape(message), advice=advice, db_path=html.escape(str(db_path()))),
            "Lead", wrap=True, selectable=True)
        detail.setTextFormat(Qt.TextFormat.RichText)
        box.addWidget(title)
        box.addWidget(detail)
        if locked:
            again = QPushButton(tr("Try again"))
            again.setObjectName("Primary")
            again.setCursor(Qt.CursorShape.PointingHandCursor)
            again.clicked.connect(self.retry_requested)
            box.addWidget(again, 0, Qt.AlignmentFlag.AlignLeft)
        self.body_layout.addWidget(box_widget)
        self.body_layout.addStretch(1)
        self._status(tr("Database not opened"))

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
        self._status(n_("{hadith:,} hadith in {n} book", "{hadith:,} hadith in {n} books", books, hadith=hadith))
        if not self._page:
            self._show_start()

    def _fill_filters(self) -> None:
        self.book_combo.fill(self._conn)
        imported = core.list_languages(self._conn)
        # the languages the imported books have in the data repository but not on this computer: the list only
        # holds what was imported, so it says where the others are
        self.language_combo.fill(imported, _more_languages(self._conn, imported))

    # -------------------------------------------------------------- search
    def _query(self, offset: int) -> core.SearchQuery:
        books = self.book_combo.selected()
        return core.SearchQuery(
            text=self.query_edit.text(), mode=self.mode_combo.currentData(),
            whole_words=self.whole_words.isChecked(),
            collections=books or [], languages=self.language_combo.selected(),
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
        title = _label(tr("Search by meaning"), "Hero", wrap=True)
        title.setFont(theme.reading_font(24, bold=True))
        text = _label(message + "\n\n" + tr("Search by meaning finds hadith that say the same thing in other words or in another language. "
                                  "It learns from the texts imported here; building it takes a few seconds to a minute."), "Lead", wrap=True)
        box.addWidget(title)
        box.addWidget(text)
        if "not built" in message:
            build = QPushButton(tr("Build the meaning index now"))
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
                    self.done.emit(True, tr("AI indexes ready: meaning ({documents:,} hadith, {concepts} concepts); "
                                            "takhrij ({same:,} + {report:,} pairs)", documents=meta["documents"],
                                            concepts=meta["dims"], same=found["same"], report=found["same_report"]))
                except Exception as exc:  # shown to the user, never lost
                    self.done.emit(False, tr("Meaning index failed: {error}", error=exc))
                finally:
                    conn.close()

        worker = _Build()
        self._meaning_worker = worker                   # kept until Qt reports it finished
        worker.progress.connect(self._status)
        worker.done.connect(self._meaning_built)
        worker.finished.connect(lambda: setattr(self, "_meaning_worker", None))
        self._status(tr("Building the AI indexes (meaning, takhrij)…"))
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
        self.query_edit.setPlaceholderText(tr(KIND_TEXT[kind][0]))
        self.summary.setText("")
        if self.query_edit.text().strip():
            self.run_search()
        else:
            self._page, self._found = None, None
            self._show_start()
        self.query_edit.setFocus()

    def search_for(self, text: str, kind: str | None = None) -> None:
        if kind and kind != self.kind():
            index = self.kind_combo.findData(kind)
            if index >= 0:
                self.kind_combo.blockSignals(True)
                self.kind_combo.setCurrentIndex(index)
                self.kind_combo.blockSignals(False)
                self.hadith_filters.setVisible(kind == "hadith")
                self.people_filters.setVisible(kind == "narrators")
                self.query_edit.setPlaceholderText(tr(KIND_TEXT[kind][0]))
        self.query_edit.setText(text)
        self.run_search()

    def go_home(self) -> None:
        """The page as it opens (NAV1): no words, every filter at its default, the welcome with the recent searches."""
        for combo in (self.mode_combo, self.tradition_combo):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.whole_words.blockSignals(True)
        self.whole_words.setChecked(False)
        self.whole_words.setEnabled(True)
        self.whole_words.blockSignals(False)
        self.book_combo.reset()
        if self.kind() != "hadith":
            self.kind_combo.blockSignals(True)
            self.kind_combo.setCurrentIndex(0)
            self.kind_combo.blockSignals(False)
            self.hadith_filters.show()
            self.people_filters.hide()
            self.query_edit.setPlaceholderText(tr(KIND_TEXT[self.kind()][0]))
        self.query_edit.clear()
        self._page, self._found = None, None
        self._show_start()
        self.scroll.verticalScrollBar().setValue(0)
        self.query_edit.setFocus()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt name)
        if event.key() == Qt.Key.Key_Escape and self.query_edit.text():
            self.query_edit.clear()          # Esc empties the search box (NAV1)
            self.query_edit.setFocus()
            return
        super().keyPressEvent(event)

    def run_search(self) -> None:
        if self._conn is None:
            return
        self._sync_with_database()
        if not self.query_edit.text().strip():
            self._page, self._found = None, None
            self._show_start()
            return
        core_recent.add(self.query_edit.text(), self.kind())      # S4
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
            if self._people_shown >= len(self._found) and self._people_total > len(self._found):
                self._read_more_people()
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
        title = _label(tr(KIND_TEXT[kind][1]), "Hero")
        title.setFont(theme.reading_font(30, bold=True))
        box.addWidget(arabic)
        box.addWidget(title)

        if self._notice:
            box.addWidget(_label(html.escape(self._notice), "Lead", wrap=True))
        if hadith == 0 and kind == "hadith":
            lead = _label(
                tr("No books yet. Import them in <b>File → Data Sources</b> (Ctrl+Shift+I) — every book of isnady-data "
                  "with one click — or from a terminal: <code>iy catalog import --all</code>"),
                "Lead", wrap=True, selectable=True)
            lead.setTextFormat(Qt.TextFormat.RichText)
            box.addWidget(lead)
        elif kind == "narrators" and not self._conn.execute("SELECT 1 FROM persons LIMIT 1").fetchone():
            box.addWidget(_label(tr("No narrators yet: import Ibn Hajar's Taqrib or al-Najashi's Rijal (File → Data Sources), or from "
                                   "a terminal: iy catalog import taqrib"),
                                 "Lead", wrap=True))
        else:
            lead = _label(tr(KIND_TEXT[kind][2]) if KIND_TEXT[kind][2] else tr(
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
            self._add_recent(box)
        self.body_layout.addWidget(hero)
        self.body_layout.addStretch(1)

    def _add_recent(self, box: QVBoxLayout) -> None:
        """The recent searches under the examples (S4): a click searches again; one link forgets them all."""
        rows = core_recent.items()
        if not rows:
            return
        box.addSpacing(18)
        head = QHBoxLayout()
        head.addWidget(_label(tr("Recent searches"), "FilterTitle"))
        clear = QPushButton(tr("Clear recent searches"))
        clear.setObjectName("Quiet")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(self._clear_recent)
        head.addSpacing(12)
        head.addWidget(clear)
        head.addStretch(1)
        box.addLayout(head)
        holder = QWidget()
        flow = FlowLayout(holder, spacing=6)
        names = dict(KINDS)
        for r in rows:
            label = r["text"] if r["kind"] == "hadith" else f"{r['text']}  · {tr(names.get(r['kind'], r['kind']))}"
            button = QPushButton(label)
            button.setObjectName("Example")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFont(theme.reading_font(12))
            button.clicked.connect(lambda _c=False, t=r["text"], k=r["kind"]: self.search_for(t, k))
            flow.addWidget(button)
        holder.setMaximumWidth(900)
        box.addWidget(holder)

    def _clear_recent(self) -> None:
        core_recent.clear()
        self._show_start()

    def _render(self) -> None:
        self._clear_body()
        page = self._page
        if page.total == 0:
            empty = QWidget()
            box = QVBoxLayout(empty)
            box.setContentsMargins(8, 40, 8, 8)
            title = _label(tr("Nothing found for “{strip}”", strip=page.query.text.strip()), "Hero", wrap=True)
            title.setFont(theme.reading_font(20, bold=True))
            hint = tr("Try fewer words, “Any word”, or turn off “Whole words only”.") if (
                len(page.terms) > 1 or page.query.whole_words) else tr("Try another spelling, or search in another "
                                                                       "language.")
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
            self.more_button.setText(tr("Show {page_size} more ({remaining:,} left)", page_size=min(PAGE_SIZE, remaining), remaining=remaining))
            self.body_layout.addWidget(self.more_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.body_layout.addStretch(1)

    def _update_summary(self) -> None:
        page = self._page
        if page.total == 0:
            self.summary.setText("")
            return
        note = "" if page.used_index else ", " + tr("index unavailable")
        if page.query.mode == "meaning":
            note = " " + tr("by meaning") + (" · " + tr("index older than the data (Tools → Build Meaning Index)")
                                             if getattr(self, "_meaning_stale", False) else "")
        if page.spellings:          # words found in another spelling (? and *, or one letter away)
            note += " · " + tr("near spellings: {spellings}", spellings=core.spellings_text(page.spellings))
        self.summary.setText(tr("{total:,} hadith, {ms} ms", total=page.total, ms=page.elapsed_ms) + note)

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
                self._people_read = core_narrators.SEARCH_RERANK   # the matches find() read; the next from here
            else:
                self._found = core_scholars.search(self._conn, text)
                self._people_total = len(self._found)
            self._people_ms = int((time.perf_counter() - start) * 1000)
        finally:
            QGuiApplication.restoreOverrideCursor()
        self._show_people()

    def _read_more_people(self) -> None:
        """The next narrators found, after the first SEARCH_RERANK (NR-B1)."""
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            have = {r["id"] for r in self._found}
            rows = core_narrators.find_more(self._conn, self.query_edit.text().strip(),
                                            self.tradition_combo.currentData() or None, self._people_read, PAGE_SIZE * 4)
            self._people_read += len(rows)
            new = [r for r in rows if r["id"] not in have]
            self._found.extend(new)
            if not rows:                          # nothing more to read: the total said more than there is
                self._people_total = len(self._found)
        finally:
            QGuiApplication.restoreOverrideCursor()

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
            typed = self.query_edit.text().strip()
            title = _label(tr("No narrators found for “{typed}”", typed=typed) if kind == "narrators" else
                           tr("No scholars found for “{typed}”", typed=typed), "Hero", wrap=True)
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
                tr("No name reads “{typed}”. Arabic is written without its short vowels, so isnady first matches the "
                  "consonants — these names have the consonants typed, but their readings sound different.", typed=typed),
                "Lead", wrap=True))
        elif not more and all(r.get("close") for r in self._found):
            self.body_layout.addWidget(_label(
                tr("Nothing is written exactly “{typed}”. These are the closest spellings: a letter typed twice or "
                  "missing, or written as Turkish and English differ (h and kh, z and dh).", typed=typed), "Lead", wrap=True))
        batch = self._found[self._people_shown:self._people_shown + PAGE_SIZE]
        for index, row in enumerate(batch, start=self._people_shown):
            if row.get("weak") and index > 0 and not self._found[index - 1].get("weak"):
                # the weaker matches, after the others, under their own heading (S4)
                head = _label(tr("Weaker matches"), "CardTitle")
                head.setFont(theme.reading_font(15, bold=True))
                why = _label(tr("The same consonants as “{typed}”, but the names read differently — Arabic is written without its "
                               "short vowels, so the consonants are matched first.", typed=typed), "Caption",
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
        # every match can be reached: after the ones read, the next are read when asked for (NR-B1)
        remaining = max(len(self._found), self._people_total) - self._people_shown
        if remaining > 0:
            self.more_button.setText(tr("Show {page_size} more ({remaining:,} left)", page_size=min(PAGE_SIZE, remaining), remaining=remaining))
            self.body_layout.addWidget(self.more_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.body_layout.addStretch(1)
        total = self._people_total
        close = sum(1 for r in self._found if r.get("close"))
        weak = sum(1 for r in self._found if r.get("weak"))
        note = "" if not close else (" — " + tr("by close spelling") if close == len(self._found)
                                     else ", " + tr("{n:,} by close spelling", n=close))
        if weak:
            note += " — " + tr("all weaker matches") if weak == len(self._found) else ", " + tr("{n:,} weaker", n=weak)
        count = (n_("{n:,} narrator", "{n:,} narrators", total) if kind == "narrators" else
                 n_("{n:,} scholar", "{n:,} scholars", total))
        self.summary.setText(count + note + f", {self._people_ms} ms")

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
        folded = []
        if not in_book:
            # the content languages (L1): the texts in the languages chosen, and any text the search matched; the
            # others folded behind an arrow (or left out, as Settings → Books and languages says)
            from dataclasses import replace

            from isnady.core import language

            kept = [t for t in result.texts if language.shows(t.language) or t.spans]
            if kept and len(kept) != len(result.texts):
                if language.folds():
                    folded = [t for t in result.texts if t not in kept]
                result = replace(result, texts=kept)
        chains = core_isnad.chain(self._conn, result.hadith_id)
        chain = chains[0] if chains else None
        people: dict = {}
        for c in chains:
            people.update(self._people(c))
        card = ResultCard(result, chain, self.open_chain.emit, people, score, self._related(result.hadith_id),
                          None if in_book else self.open_book.emit, folded, chains,
                          on_person=self.open_narrator.emit, on_name=self.find_narrator.emit,
                          on_end=lambda node: self.open_tree.emit("quraysh", node))
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
