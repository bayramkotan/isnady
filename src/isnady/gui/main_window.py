"""Main window: a lapis sidebar with the sections and a page stack.

Sections without their own page yet show a short description.
"""

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QPushButton,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from isnady import __version__
from isnady.data.paths import data_dir
from isnady.gui import dialogs, theme
from isnady.gui.isnad_page import IsnadPage
from isnady.gui.search_page import SearchPage

# (key, sidebar label, description shown until the page is built)
SECTIONS = [
    ("search", "Search", "Search hadith text, books and grades."),
    ("narrators", "Narrators", "Every narrator: biography, teachers and students, generation, narrations "
                               "and every recorded verdict on them."),
    ("chains", "Isnad Chains", "Chains of transmission drawn link by link, with each narrator's standing "
                               "and whether each link could have met the next."),
    ("scholars", "Hadith Scholars", "The scholars of hadith: their lives, books, teachers and students, "
                                     "and what their collections contain."),
    ("books", "Books", "The hadith collections in the database and what each source adds."),
    ("shia_rijal", "Shia Rijal", "Narrator verdicts from the Shia rijal works, per narrator, beside the "
                                 "Sunni view."),
    ("statistics", "Statistics", "Narrators, books and grades counted and compared."),
    ("learn", "Learn", "The sciences of hadith: terms, grades, jarh wa ta'dil and the classical works, "
                       "shown on real hadith and real chains."),
]


def _placeholder(title: str, text: str) -> QWidget:
    page = QWidget()
    page.setObjectName("Page")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(48, 44, 48, 44)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    heading = QLabel(title)
    heading.setObjectName("PageTitle")
    heading.setFont(theme.reading_font(26, bold=True))
    body = QLabel(text)
    body.setObjectName("Lead")
    body.setWordWrap(True)
    body.setMaximumWidth(620)
    note = QLabel("This section is being built.")
    note.setObjectName("Caption")
    layout.addWidget(heading)
    layout.addSpacing(6)
    layout.addWidget(body)
    layout.addSpacing(14)
    layout.addWidget(note)
    return page


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("isnady")
        self.resize(1240, 820)
        self.setMinimumSize(900, 600)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(232)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 26, 0, 16)
        side.setSpacing(0)

        wordmark = QLabel("isnady")
        wordmark.setObjectName("Wordmark")
        wordmark.setFont(theme.reading_font(26, bold=True))
        wordmark.setContentsMargins(26, 0, 26, 0)
        arabic = QLabel("إسناد")
        arabic.setObjectName("WordmarkArabic")
        arabic.setFont(theme.reading_font(17))
        arabic.setContentsMargins(26, 0, 26, 0)
        arabic.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute
                            | Qt.AlignmentFlag.AlignVCenter)
        side.addWidget(wordmark)
        side.addWidget(arabic)
        side.addSpacing(26)

        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        self.nav.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        side.addWidget(self.nav, 1)

        # shown only when the check at start finds another copy of isnady (see check_installation_later)
        self.install_notice = QPushButton("⚠  Check installation")
        self.install_notice.setObjectName("SidebarNotice")
        self.install_notice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_notice.clicked.connect(self._check_installation)
        self.install_notice.hide()
        side.addWidget(self.install_notice)
        self.footer = QLabel(f"version {__version__}")
        self.footer.setObjectName("SidebarFooter")
        self.footer.setContentsMargins(26, 0, 26, 0)
        self.footer.setWordWrap(True)
        side.addWidget(self.footer)

        self.pages = QStackedWidget()
        self.search_page = SearchPage(status_message=self._set_footer)
        self.isnad_page = IsnadPage(self.search_page.connection)
        from isnady.gui.narrators_page import NarratorsPage

        self.narrators_page = NarratorsPage(self.search_page.connection)
        self.shia_page = NarratorsPage(self.search_page.connection, tradition="shia")
        from isnady.gui.statistics_page import StatisticsPage

        self.statistics_page = StatisticsPage(self.search_page.connection)
        from isnady.gui.learn_page import LearnPage

        self.learn_page = LearnPage()
        from isnady.gui.books_page import BooksPage
        from isnady.gui.scholars_page import ScholarsPage

        self.books_page = BooksPage(self.search_page.connection, self.search_page.make_card)
        self._books_loaded = False

        self.scholars_page = ScholarsPage(self.search_page.connection)
        for key, label, text in SECTIONS:
            self.nav.addItem(label)
            self.nav.item(self.nav.count() - 1).setSizeHint(QSize(0, 38))
            if key == "search":
                page = self.search_page
            elif key == "chains":
                page = self.isnad_page
            elif key == "narrators":
                page = self.narrators_page
            elif key == "scholars":
                page = self.scholars_page
            elif key == "books":
                page = self.books_page
            elif key == "shia_rijal":
                page = self.shia_page
            elif key == "statistics":
                page = self.statistics_page
            elif key == "learn":
                page = self.learn_page
            else:
                page = _placeholder(label, text)
            self.pages.addWidget(page)
        self._chains_row = [k for k, _l, _t in SECTIONS].index("chains")
        self.search_page.open_chain.connect(self._open_chain)
        self.search_page.data_changed.connect(self.isnad_page.refresh)
        self.search_page.data_changed.connect(self.narrators_page.refresh)
        self.isnad_page.refresh()
        self._narrators_row = [k for k, _l, _t in SECTIONS].index("narrators")
        self.narrators_page.open_chain.connect(self._open_chain)
        self.narrators_page.open_sources.connect(lambda: self._preferences("sources"))
        self.isnad_page.open_narrator.connect(self._open_narrator)
        self.narrators_page.refresh()
        self.scholars_page.open_narrator.connect(self._open_narrator)
        self.scholars_page.open_chain.connect(self._open_chain)
        self.search_page.data_changed.connect(self.scholars_page.refresh)
        self.scholars_page.refresh()
        self._books_row = [k for k, _l, _t in SECTIONS].index("books")
        self.books_page.open_chain.connect(self._open_chain)
        self.books_page.open_narrator.connect(self._open_narrator)
        self.search_page.open_book.connect(self._open_in_book)
        self.search_page.open_person.connect(self._open_person)
        self.search_page.open_scholar.connect(self._open_scholar)
        self.search_page.data_changed.connect(lambda: setattr(self, "_books_loaded", False))
        self.nav.currentRowChanged.connect(self._load_books_when_shown)
        self._shia_row = [k for k, _l, _t in SECTIONS].index("shia_rijal")
        self.shia_page.open_sources.connect(lambda: self._preferences("sources"))
        self.search_page.data_changed.connect(self.shia_page.refresh)
        for page in (self.narrators_page, self.shia_page):
            page.open_in_book.connect(self._open_person_in_book)
        self.shia_page.refresh()
        self._statistics_row = [k for k, _l, _t in SECTIONS].index("statistics")
        self._statistics_loaded = False
        self.statistics_page.open_hadith.connect(self._open_in_book)
        self.search_page.data_changed.connect(lambda: setattr(self, "_statistics_loaded", False))
        self.nav.currentRowChanged.connect(self._load_statistics_when_shown)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.currentRowChanged.connect(self._retheme_when_shown)
        self.nav.setCurrentRow(0)

        central = QWidget()
        row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(sidebar)
        row.addWidget(self.pages, 1)
        self.setCentralWidget(central)
        self.statusBar().hide()
        self._build_menus()

    # --------------------------------------------------------------- menus
    def _action(self, menu, text: str, slot, shortcut=None, tip: str = "") -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if tip:
            action.setStatusTip(tip)
            action.setToolTip(tip)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _build_menus(self) -> None:
        bar = self.menuBar()
        search = self.pages.widget(0)

        file_menu = bar.addMenu("&File")
        self._action(file_menu, "Data Sources…", lambda: self._preferences("sources"), "Ctrl+Shift+I",
                     tip="Import built-in sources with one click, or add your own")
        self._action(file_menu, "Open Data Folder", self._open_data_folder,
                     tip="Open the folder that holds the isnady database")
        file_menu.addSeparator()
        self._action(file_menu, "Quit", QApplication.quit, "Ctrl+Q")

        edit_menu = bar.addMenu("&Edit")
        self._action(edit_menu, "Find", self._find, QKeySequence.StandardKey.Find)
        self._action(edit_menu, "Copy", self._copy, QKeySequence.StandardKey.Copy)
        edit_menu.addSeparator()
        self._action(edit_menu, "Preferences…", lambda: self._preferences(), "Ctrl+,",
                     tip="Fonts, sizes and colours for each script, theme colours, interface font")

        view_menu = bar.addMenu("&View")
        for i, (_key, label, _text) in enumerate(SECTIONS):
            self._action(view_menu, label, lambda _c=False, row=i: self.nav.setCurrentRow(row), f"Ctrl+{i + 1}")
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu("Theme")
        group = QActionGroup(self)
        self._theme_actions = {}
        choices = [("system", "Follow system (Lapis / Lapis Night)")] + [(k, v[0]) for k, v in theme.THEMES.items()]
        for n, (mode, label) in enumerate(choices):
            action = self._action(theme_menu, label, lambda _c=False, m=mode: self._set_theme(m))
            action.setCheckable(True)
            action.setChecked(theme.theme_mode() == mode)
            group.addAction(action)
            self._theme_actions[mode] = action
            if n == 0:
                theme_menu.addSeparator()
        theme_menu.addSeparator()
        self._action(theme_menu, "Choose with previews…", lambda: self._preferences("themes"))
        text_menu = view_menu.addMenu("Reading Text Size")
        self._action(text_menu, "Larger", lambda: self._change_text_scale(+1), "Ctrl++")
        self._action(text_menu, "Smaller", lambda: self._change_text_scale(-1), "Ctrl+-")
        self._action(text_menu, "Default Size", lambda: self._change_text_scale(0), "Ctrl+0")
        view_menu.addSeparator()
        self._action(view_menu, "Full Screen", self._toggle_full_screen, "F11")

        tools_menu = bar.addMenu("&Tools")
        self._action(tools_menu, "Rebuild Search Index", lambda: search.rebuild_index(),
                     tip="Rebuild the search index from every imported text")
        self._action(tools_menu, "Read Chains Again", lambda: search.rebuild_chains(),
                     tip="Read every chain of transmission from the Arabic texts again")
        self._action(tools_menu, "Identify Narrators Again", lambda: search.identify_narrators(),
                     tip="Match every name in the chains against the imported rijal works again")
        tools_menu.addSeparator()
        self._action(tools_menu, "Create Desktop Shortcut…", self._create_shortcut,
                     tip="Put isnady on the desktop and in the applications menu, with its icon")
        tools_menu.addSeparator()
        self._action(tools_menu, "Build AI Indexes (Meaning, Takhrij)", lambda: search.build_meaning_index(),
                     tip="Learn the meaning index (Match → By meaning) and find the narrations of each hadith "
                         "across the books (Also narrated in)")

        help_menu = bar.addMenu("&Help")
        self._action(help_menu, "Search Tips", lambda: dialogs.search_tips(self).exec())
        self._action(help_menu, "Keyboard Shortcuts", lambda: dialogs.shortcuts(self).exec())
        help_menu.addSeparator()
        self._action(help_menu, "Check Installation…", self._check_installation,
                     tip="Every copy of isnady on this computer, and which one really runs")
        self._action(help_menu, "Licences", lambda: dialogs.licenses(self, search.connection()).exec())
        self._action(help_menu, "isnady on GitHub", lambda: QDesktopServices.openUrl(QUrl(dialogs.REPO_URL)))
        self._action(help_menu, "Report an Issue", lambda: QDesktopServices.openUrl(QUrl(dialogs.ISSUES_URL)))
        help_menu.addSeparator()
        self._action(help_menu, "About isnady", lambda: dialogs.about(self).exec())

    def _create_shortcut(self) -> None:
        import html as _html

        from PySide6.QtWidgets import QMessageBox

        from isnady.core import shortcut

        program, args, how = shortcut.launch_command()
        try:
            made = shortcut.create()
        except OSError as exc:
            QMessageBox.warning(self, "Create Desktop Shortcut", f"The shortcut could not be created.\n\n{exc}")
            return
        where = {"desktop": "On the desktop", "menu": "In the applications menu"}
        lines = "".join(f"<li><b>{where.get(w, w)}</b>: <code>{_html.escape(str(p))}</code></li>" for w, p in made)
        command = _html.escape(" ".join([program, *args]))
        box = QMessageBox(self)
        box.setWindowTitle("Create Desktop Shortcut")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(f"<p>isnady now has a shortcut, with its own icon:</p><ul>{lines}</ul>"
                    f"<p>It starts {_html.escape(how)}:<br><code>{command}</code></p>"
                    "<p style='color:gray'>Making it again replaces it, so after moving isnady or changing how it is "
                    "installed, create it once more.</p>")
        box.exec()

    def _load_statistics_when_shown(self, row: int) -> None:
        """Statistics reads (or computes) only when it is opened."""
        if row == self._statistics_row and not self._statistics_loaded:
            self._statistics_loaded = True
            self.statistics_page.refresh()

    def _load_books_when_shown(self, row: int) -> None:
        """The Books section reads its first chapter only when it is opened, not at start."""
        if row == self._books_row and not self._books_loaded:
            self._books_loaded = True
            self.books_page.refresh()

    def _open_person_in_book(self, person_id: int) -> None:
        self._books_loaded = True
        self.nav.setCurrentRow(self._books_row)
        self.books_page.show_person(person_id)

    def _open_in_book(self, hadith_id: int) -> None:
        self._books_loaded = True
        self.nav.setCurrentRow(self._books_row)
        self.books_page.show_hadith(hadith_id)

    def _open_narrator(self, person_id: int) -> None:
        self.nav.setCurrentRow(self._narrators_row)
        self.narrators_page.select(person_id)

    def _open_person(self, person_id: int, tradition: str) -> None:
        """A narrator found by Search: on Narrators, or on Shia Rijal for one of the Shia books."""
        if tradition == "shia":
            self.nav.setCurrentRow(self._shia_row)
            self.shia_page.select(person_id)
        else:
            self._open_narrator(person_id)

    def _open_scholar(self, scholar_id: str) -> None:
        self.nav.setCurrentRow([k for k, _l, _t in SECTIONS].index("scholars"))
        self.scholars_page.select(scholar_id)

    def _open_chain(self, hadith_id: int) -> None:
        self.nav.setCurrentRow(self._chains_row)
        self.isnad_page.show_hadith(hadith_id)

    def _open_data_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))

    def _find(self) -> None:
        self.nav.setCurrentRow(0)
        self.pages.widget(0).focus_search()

    def _copy(self) -> None:
        widget = QApplication.focusWidget()
        if hasattr(widget, "copy"):
            widget.copy()
        elif hasattr(widget, "selectedText") and widget.selectedText():
            QApplication.clipboard().setText(widget.selectedText())

    def check_installation_later(self) -> None:
        """At start, quietly look for other copies of isnady; show the notice only if something is wrong.

        A newer isnady cannot be shadowed while it runs, but it CAN see an older copy that would start
        from another command (an old ~/.local copy after a system-wide upgrade, 2026-09-30).
        """
        from PySide6.QtCore import QThread, Signal

        from isnady import doctor

        class _Quiet(QThread):
            done = Signal(object)

            def run(self) -> None:
                try:
                    self.done.emit(doctor.diagnose(check_pypi=False))
                except Exception:      # a check that fails must never disturb the window
                    pass

        worker = _Quiet()
        self._install_check = worker            # kept until Qt reports it finished
        worker.finished.connect(lambda: setattr(self, "_install_check", None))
        worker.done.connect(self._install_checked)
        worker.start()

    def _install_checked(self, report) -> None:
        if report.problems:
            self.install_notice.setToolTip("\n".join(report.problems) + "\n\nClick for the report; 'iy update' updates "
                                           "every copy where it is installed.")
            self.install_notice.show()

    def _check_installation(self) -> None:
        from isnady.gui.install_dialog import InstallDialog

        InstallDialog(self).exec()

    def _preferences(self, tab: str = "") -> None:
        from isnady.gui.preferences import PreferencesDialog

        dialog = PreferencesDialog(self, start_tab=tab)
        dialog.changed.connect(self._apply_settings)
        dialog.data_imported.connect(self._data_imported)
        dialog.exec()

    def _data_imported(self) -> None:
        """A source was imported or removed from Data sources: bring every page up to date."""
        self.search_page._sync_with_database(force=True)
        self.isnad_page.refresh()
        self.narrators_page.refresh()
        self.scholars_page.refresh()

    def _apply_settings(self) -> None:
        self._restyle(lambda: theme.apply(QApplication.instance()))
        for mode, action in getattr(self, "_theme_actions", {}).items():
            action.setChecked(theme.theme_mode() == mode)

    def _set_theme(self, mode: str) -> None:
        theme.set_theme_mode(mode)
        self._restyle(lambda: theme.apply(QApplication.instance(), mode))

    def _restyle(self, apply) -> None:
        """A new theme, fast (UI5-P). Qt styles EVERY widget of the application again, hidden pages too, and was
        then asked to redraw every page: 5–7 seconds with the narrator lists and a book open. Now every page lets go
        of what it shows first (release) — the page in view too, since it is drawn again anyway — so the new style
        meets only the frame of the window; the page in view is then drawn at once, the others when next opened."""
        from PySide6.QtCore import QCoreApplication, QEvent

        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for i in range(self.pages.count()):
                page = self.pages.widget(i)
                if hasattr(page, "release"):
                    page.release()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)   # gone before the new style
            apply()
            self.retheme()
        finally:
            QGuiApplication.restoreOverrideCursor()

    def _change_text_scale(self, direction: int) -> None:
        if direction == 0:
            theme.set_text_scale(1.0)
        else:
            theme.set_text_scale(theme.text_scale() + direction * theme.TEXT_SCALE_STEP)
        self.retheme()

    def _toggle_full_screen(self) -> None:
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def _set_footer(self, message: str) -> None:
        self.footer.setText(f"{message}\nversion {__version__}")

    def retheme(self) -> None:
        """Called when the theme, the text size or any appearance setting changes: the page in view is redrawn
        now, every other page when it is next opened (_retheme_when_shown)."""
        current = self.pages.currentWidget()
        self._stale = {self.pages.widget(i) for i in range(self.pages.count())
                       if hasattr(self.pages.widget(i), "retheme")} - {current}
        if hasattr(current, "retheme"):
            current.retheme()

    def _retheme_when_shown(self, row: int) -> None:
        page = self.pages.widget(row)
        if page in getattr(self, "_stale", set()):
            self._stale.discard(page)
            page.retheme()
