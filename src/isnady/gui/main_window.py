"""Main window: a lapis sidebar with the sections and a page stack.

Sections without their own page yet show a short description.
"""

from contextlib import contextmanager

from PySide6.QtCore import QEvent, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QMenu,
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
from isnady.core.i18n import N_, tr
from isnady.data.paths import data_dir
from isnady.gui import dialogs, theme
from isnady.gui.isnad_page import IsnadPage
from isnady.gui.search_page import SearchPage

# (key, sidebar label, description shown until the page is built)
# every section of the sidebar; the order shown is config.sidebar_order() (Preferences → Sidebar)
SECTIONS = [
    ("search", N_("Search"), N_("Search hadith text, books and grades.")),
    ("books", N_("Books"), N_("The hadith collections in the database and what each source adds.")),
    ("narrators", N_("Narrators"), N_("Every narrator, Sunni and Shia on one page: biography, teachers and students, "
                                      "generation, narrations and every recorded verdict, each by its own tradition's "
                                      "measure.")),
    ("chains", N_("Isnad Chains"), N_("Chains of transmission drawn link by link, with each narrator's standing "
                                      "and whether each link could have met the next.")),
    ("scholars", N_("Hadith Scholars"), N_("The scholars of hadith: their lives, books, teachers and students, "
                                           "and what their collections contain.")),
    ("genealogy", N_("Genealogies"), N_("The prophets' lineage, Quraysh and the Prophet's family, a narrator's family "
                                       "and his line of learning, drawn as trees.")),
    ("statistics", N_("Statistics"), N_("Narrators, books and grades counted and compared.")),
    ("bookmarks", N_("Bookmarks"), N_("What you marked with ☆, in folders of your own.")),
    ("learn", N_("Learn"), N_("The sciences of hadith: terms, grades, jarh wa ta'dil and the classical works, "
                              "shown on real hadith and real chains.")),
]


def _placeholder(title: str, text: str) -> QWidget:
    page = QWidget()
    page.setObjectName("Page")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(48, 44, 48, 44)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    heading = QLabel(tr(title))
    heading.setObjectName("PageTitle")
    heading.setFont(theme.reading_font(26, bold=True))
    body = QLabel(tr(text))
    body.setObjectName("Lead")
    body.setWordWrap(True)
    body.setMaximumWidth(620)
    note = QLabel(tr("This section is being built."))
    note.setObjectName("Caption")
    layout.addWidget(heading)
    layout.addSpacing(6)
    layout.addWidget(body)
    layout.addSpacing(14)
    layout.addWidget(note)
    return page


class _Nothing:
    """Stands for anything a page that could not be built would have had (signals, methods): does nothing."""

    def __getattr__(self, _name):
        return self

    def __call__(self, *_a, **_k):
        return self

    def __bool__(self) -> bool:
        return False

    def __iter__(self):
        return iter(())


class _BrokenPage(QWidget):
    """A page that could not be built (ROB1): a plain card in its place, the window goes on."""

    def __init__(self, key: str, exc: BaseException, check, sources) -> None:
        super().__init__()
        self.setObjectName("Page")
        from isnady.core import errlog

        errlog.write(f"the page '{key}' could not be built", exc)
        box = QVBoxLayout(self)
        box.setContentsMargins(48, 44, 48, 44)
        box.setAlignment(Qt.AlignmentFlag.AlignTop)
        title = QLabel(tr("This page could not be opened"))
        title.setObjectName("PageTitle")
        title.setFont(theme.reading_font(22, bold=True))
        box.addWidget(title)
        text = QLabel(tr("{error}\n\nThe rest of isnady works. Often the data is incomplete — an import that did not "
                         "finish — or two copies of isnady are installed. The details are written to {log}.",
                         error=f"{type(exc).__name__}: {exc}", log=str(errlog.path())))
        text.setObjectName("Lead")
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(text)
        row = QHBoxLayout()
        for label, slot in ((tr("Check Installation…"), check), (tr("Data Sources…"), sources)):
            b = QPushButton(label)
            b.setObjectName("Quiet")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        box.addSpacing(10)
        box.addLayout(row)

    def __getattr__(self, name):
        return _Nothing()


class MainWindow(QMainWindow):
    language_switched = Signal()          # another interface language chosen: main.py builds the window again

    def __init__(self) -> None:
        super().__init__()
        from isnady.core import profiles

        person = profiles.name_of(profiles.active())
        self.setWindowTitle(f"isnady — {person}" if person else "isnady")        # the profile in use (PRF1)
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
        side.addSpacing(14)
        # ◀ ▶ back and forward through what was opened (NAV2), like a browser
        self._history: list[tuple] = []
        self._at = -1
        self._replaying = False
        self._opening = False
        self.back_button = QPushButton("◀")
        self.forward_button = QPushButton("▶")
        history_row = QHBoxLayout()
        history_row.setContentsMargins(22, 0, 22, 0)
        history_row.setSpacing(6)
        for b, step in ((self.back_button, -1), (self.forward_button, +1)):
            b.setObjectName("SidebarLang")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedWidth(44)
            b.clicked.connect(lambda _c=False, d=step: self._go_history(d))
            history_row.addWidget(b)
        history_row.addStretch(1)
        side.addLayout(history_row)
        side.addSpacing(12)

        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        self.nav.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        side.addWidget(self.nav, 1)

        # shown only when the check at start finds another copy of isnady (see check_installation_later)
        self.install_notice = QPushButton("⚠  " + tr("Check installation"))
        self.install_notice.setObjectName("SidebarNotice")
        self.install_notice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_notice.clicked.connect(self._check_installation)
        self.install_notice.hide()
        side.addWidget(self.install_notice)
        # the two languages, always in sight (L1): the interface (how names and terms are read) and the content
        # (the languages the hadith texts are shown in); each opens its choices
        self.ui_lang_button = QPushButton()
        self.content_lang_button = QPushButton()
        languages = QWidget()
        lang_box = QVBoxLayout(languages)
        lang_box.setContentsMargins(18, 0, 18, 6)
        lang_box.setSpacing(6)
        for button in (self.ui_lang_button, self.content_lang_button):
            button.setObjectName("SidebarLang")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            lang_box.addWidget(button)
        side.addWidget(languages)
        self.ui_lang_button.setMenu(QMenu(self.ui_lang_button))
        self.content_lang_button.setMenu(QMenu(self.content_lang_button))
        self.ui_lang_button.menu().aboutToShow.connect(lambda: self._fill_ui_language_menu(self.ui_lang_button.menu()))
        self.content_lang_button.menu().aboutToShow.connect(
            lambda: self._fill_content_language_menu(self.content_lang_button.menu()))
        self.footer = QLabel(tr("version {version}", version=__version__))
        self.footer.setObjectName("SidebarFooter")
        self.footer.setContentsMargins(26, 0, 26, 0)
        self.footer.setWordWrap(True)
        side.addWidget(self.footer)

        self.pages = QStackedWidget()
        self.search_page = SearchPage(status_message=self._set_footer)
        self.isnad_page = self._build('chains', lambda: IsnadPage(self.search_page.connection))
        from isnady.gui.narrators_page import NarratorsPage

        self.narrators_page = self._build('narrators', lambda: NarratorsPage(self.search_page.connection))
        from isnady.gui.statistics_page import StatisticsPage

        self.statistics_page = self._build('statistics', lambda: StatisticsPage(self.search_page.connection))
        from isnady.gui.learn_page import LearnPage

        self.learn_page = self._build('learn', lambda: LearnPage())
        from isnady.gui.books_page import BooksPage
        from isnady.gui.scholars_page import ScholarsPage

        self.books_page = self._build('books', lambda: BooksPage(self.search_page.connection, self.search_page.make_card))
        self._books_loaded = False

        self.scholars_page = self._build('scholars', lambda: ScholarsPage(self.search_page.connection))
        from isnady.gui.bookmarks_page import BookmarksPage
        from isnady.gui.genealogy_page import GenealogyPage

        self.genealogy_page = self._build('genealogy', lambda: GenealogyPage(self.search_page.connection))
        self.bookmarks_page = self._build('bookmarks', lambda: BookmarksPage(self.search_page.connection))
        self._page_of = {"search": self.search_page, "chains": self.isnad_page, "narrators": self.narrators_page,
                         "scholars": self.scholars_page, "books": self.books_page, "statistics": self.statistics_page,
                         "learn": self.learn_page, "genealogy": self.genealogy_page, "bookmarks": self.bookmarks_page}
        self._fill_sidebar()
        self.search_page.open_chain.connect(self._open_chain)
        # pages drawn when first opened, not at start (Bayram 2026-10-12: "çok hızlı"); a change of the data marks
        # them to be drawn again when next opened (the one in view at once)
        self._lazy = {"chains": self.isnad_page.refresh, "narrators": self.narrators_page.refresh,
                      "scholars": self.scholars_page.refresh}
        self._pending = set(self._lazy)
        self.nav.currentRowChanged.connect(self._refresh_pending)
        self.search_page.data_changed.connect(lambda: self._refresh_or_later("chains"))
        self.search_page.data_changed.connect(lambda: self._refresh_or_later("narrators"))
        self.narrators_page.open_chain.connect(self._open_chain)
        self.narrators_page.open_sources.connect(lambda: self._preferences("sources"))
        self.isnad_page.open_narrator.connect(self._open_narrator)
        self.scholars_page.open_narrator.connect(self._open_narrator)
        self.scholars_page.open_chain.connect(self._open_chain)
        self.search_page.data_changed.connect(lambda: self._refresh_or_later("scholars"))
        self.books_page.open_chain.connect(self._open_chain)
        self.books_page.open_narrator.connect(self._open_narrator)
        self.search_page.open_book.connect(self._open_in_book)
        self.search_page.open_person.connect(self._open_person)
        self.search_page.open_scholar.connect(self._open_scholar)
        self.search_page.wants_sources.connect(lambda: self._preferences("sources"))
        self.search_page.retry_requested.connect(self.language_switched)   # main.py builds the window again
        self.search_page.data_changed.connect(lambda: setattr(self, "_books_loaded", False))
        self.nav.currentRowChanged.connect(self._load_books_when_shown)
        self.narrators_page.open_in_book.connect(self._open_person_in_book)
        self._statistics_loaded = False
        self.statistics_page.open_hadith.connect(self._open_in_book)
        self.statistics_page.open_narrator.connect(self._open_narrator)
        self.search_page.data_changed.connect(lambda: setattr(self, "_statistics_loaded", False))
        self.nav.currentRowChanged.connect(self._load_statistics_when_shown)
        # GEN1 and BM1
        self.nav.currentRowChanged.connect(lambda row: row == self._row("genealogy") and self.genealogy_page.ensure())
        self.genealogy_page.open_narrator.connect(self._open_narrator)
        self.genealogy_page.open_hadith.connect(self._open_in_book)
        self.genealogy_page.open_book.connect(self._open_book)
        self.narrators_page.open_genealogy.connect(self._open_genealogy)
        self.bookmarks_page.open_hadith.connect(self._open_in_book)
        self.bookmarks_page.open_narrator.connect(self._open_narrator)
        self.bookmarks_page.open_scholar.connect(self._open_scholar)
        self.bookmarks_page.open_term.connect(self._open_term)
        self.bookmarks_page.open_chapter.connect(self._open_chapter)
        self.bookmarks_page.open_tree.connect(self._open_tree)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.currentRowChanged.connect(self._retheme_when_shown)
        self.nav.currentRowChanged.connect(self._section_shown)
        self.nav.setCurrentRow(0)
        QApplication.instance().installEventFilter(self)       # the mouse's back and forward buttons

        central = QWidget()
        row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(sidebar)
        row.addWidget(self.pages, 1)
        self.setCentralWidget(central)
        self.statusBar().hide()
        self._build_menus()
        self._update_language_buttons()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt's name)
        """Closing while an import runs: say what happens, and on yes really end — an import left running in the
        background kept the database locked for the next start ("database is locked", 2026-10-11)."""
        from PySide6.QtWidgets import QMessageBox

        from isnady.gui import sources_page

        running = [w for w in sources_page._LIVE_WORKERS if w.isRunning()]
        if running:
            answer = QMessageBox.question(
                self, tr("An import is running"),
                tr("Books are being imported. If isnady closes now, the book being imported is not kept (the books "
                   "already imported stay); it can be imported again from File → Data Sources.\n\nClose isnady?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        super().closeEvent(event)

    # --------------------------------------------------------------- the sidebar's order
    def _clear_cache(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        from isnady.core import cache

        files, size = cache.info()
        n = cache.clear()
        QMessageBox.information(self, tr("Clear the Cache"), tr(
            "{n} kept file(s) deleted ({size:,.0f} KB). isnady counts them again when a page next needs them; "
            "this is needed only if something looks out of date.", n=n, size=size / 1024))

    def _refresh_pending(self, row: int) -> None:
        key = self._order[row] if 0 <= row < len(self._order) else None
        if key in self._pending:
            self._pending.discard(key)
            self._lazy[key]()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt's name)
        super().showEvent(event)
        if not getattr(self, "_warming", False):
            self._warming = True
            # the pages left for later are drawn while nobody waits, one at a time, right after the window shows:
            # a fast start AND instant switching (2026-10-12: drawn only on the first click, switching felt slower)
            from PySide6.QtCore import QTimer

            QTimer.singleShot(300, self._warm_next)

    def _warm_next(self) -> None:
        from PySide6.QtCore import QTimer

        current = self._order[self.nav.currentRow()] if self.nav.currentRow() >= 0 else None
        waiting = [k for k in ("chains", "narrators", "scholars") if k in self._pending and k != current]
        if not waiting:
            if not self._books_loaded and current != "books":
                self._books_loaded = True                 # Books, its first chapter ready too
                self.books_page.refresh()
            return
        key = waiting[0]
        self._pending.discard(key)
        self._lazy[key]()
        QTimer.singleShot(60, self._warm_next)

    def _refresh_or_later(self, key: str) -> None:
        if self._order[self.nav.currentRow()] == key if self.nav.currentRow() >= 0 else False:
            self._pending.discard(key)
            self._lazy[key]()
        else:
            self._pending.add(key)

    def _row(self, key: str) -> int:
        return self._order.index(key)

    def _fill_sidebar(self) -> None:
        """The sections in the order chosen (config.sidebar_order), each with its page in the same place."""
        from isnady import config

        labels = {k: l for k, l, _t in SECTIONS}
        self._order = config.sidebar_order()
        self.nav.blockSignals(True)
        self.nav.clear()
        while self.pages.count():
            self.pages.removeWidget(self.pages.widget(0))
        for key in self._order:
            self.nav.addItem(tr(labels[key]))
            self.nav.item(self.nav.count() - 1).setSizeHint(QSize(0, 38))
            self.pages.addWidget(self._page_of[key])
        self.nav.blockSignals(False)

    def apply_sidebar_order(self) -> None:
        """Preferences → Sidebar changed the order: the same page stays in view, the shortcuts follow the order."""
        current = self._order[self.nav.currentRow()] if self.nav.currentRow() >= 0 else "search"
        self._fill_sidebar()
        self.nav.blockSignals(True)
        self.nav.setCurrentRow(self._row(current))
        self.nav.blockSignals(False)
        self.pages.setCurrentIndex(self._row(current))
        self._refresh_pending(self._row(current))
        actions = getattr(self, "_section_actions", {})
        menu = getattr(self, "_view_menu", None)
        if menu is None or not actions:
            return
        anchor = next((a for a in menu.actions() if a not in actions.values()), None)
        for action in actions.values():         # the View menu in the same order, Ctrl+1 … Ctrl+9 with it
            menu.removeAction(action)
        for i, key in enumerate(self._order):
            menu.insertAction(anchor, actions[key])
            actions[key].setShortcut(QKeySequence(f"Ctrl+{i + 1}"))

    # --------------------------------------------------------------- menus
    # ------------------------------------------------------------------ profiles (PRF1)
    def _fill_profile_menu(self, menu) -> None:
        """File → Profiles: the profiles to switch to, and making, renaming, deleting, exporting, importing one."""
        from isnady.core import profiles

        menu.clear()
        group = QActionGroup(menu)
        for p in profiles.all_profiles():
            action = menu.addAction(p["name"] or tr("Default"))
            action.setCheckable(True)
            action.setChecked(p["active"])
            group.addAction(action)
            action.triggered.connect(lambda _c=False, pid=p["id"]: self._use_profile(pid))
        menu.addSeparator()
        menu.addAction(tr("New Profile…"), self._new_profile).setToolTip(
            tr("Another person's own settings, place in the books and bookmarks; the books are shared"))
        menu.addAction(tr("Rename This Profile…"), self._rename_profile)
        menu.addAction(tr("Delete a Profile…"), self._delete_profile)
        menu.addSeparator()
        menu.addAction(tr("Export This Profile…"), self._export_profile).setToolTip(
            tr("One file with this profile's settings, place and bookmarks — for another computer"))
        menu.addAction(tr("Import a Profile…"), self._import_profile)

    def _use_profile(self, pid: str) -> None:
        from isnady.core import profiles

        if pid == profiles.active():
            return
        profiles.switch(pid)
        self.language_switched.emit()        # main.py builds the window again, with this profile's settings

    def _profile_error(self, exc) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(self, tr("Profiles"), str(exc))

    def _new_profile(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        from isnady.core import profiles

        name, ok = QInputDialog.getText(self, tr("New Profile"), tr("Name of the new profile:"))
        if not ok or not name.strip():
            return
        try:
            pid = profiles.create(name)
        except profiles.ProfileError as exc:
            self._profile_error(exc)
            return
        self._use_profile(pid)

    def _rename_profile(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        from isnady.core import profiles

        pid = profiles.active()
        name, ok = QInputDialog.getText(self, tr("Rename This Profile"), tr("New name:"),
                                        text=profiles.name_of(pid) or tr("Default"))
        if not ok or not name.strip():
            return
        try:
            profiles.rename(pid, name)
        except profiles.ProfileError as exc:
            self._profile_error(exc)
            return
        self.setWindowTitle(f"isnady — {name.strip()}")

    def _delete_profile(self) -> None:
        from PySide6.QtWidgets import QInputDialog, QMessageBox

        from isnady.core import profiles

        others = [p for p in profiles.all_profiles() if p["id"] not in (profiles.DEFAULT, profiles.active())]
        if not others:
            QMessageBox.information(self, tr("Profiles"), tr("There is no other profile to delete. The first profile and "
                                                            "the one in use cannot be deleted."))
            return
        names = [p["name"] for p in others]
        name, ok = QInputDialog.getItem(self, tr("Delete a Profile"),
                                        tr("Its settings, place and bookmarks are deleted; the books stay."), names, 0, False)
        if not ok:
            return
        try:
            profiles.delete(others[names.index(name)]["id"])
        except profiles.ProfileError as exc:
            self._profile_error(exc)

    def _export_profile(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        from isnady.core import profiles

        pid = profiles.active()
        suggested = (profiles.name_of(pid) or "default") + profiles.EXTENSION
        path, _f = QFileDialog.getSaveFileName(self, tr("Export This Profile"), suggested,
                                               tr("isnady profile") + f" (*{profiles.EXTENSION})")
        if not path:
            return
        if not path.endswith(profiles.EXTENSION):
            path += profiles.EXTENSION
        try:
            written = profiles.export(pid, path)
        except (OSError, profiles.ProfileError) as exc:
            self._profile_error(exc)
            return
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, tr("Profiles"), tr("Written: {path}", path=str(written)))

    def _import_profile(self) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        from isnady.core import profiles

        path, _f = QFileDialog.getOpenFileName(self, tr("Import a Profile"), "",
                                               tr("isnady profile") + f" (*{profiles.EXTENSION} *.zip)")
        if not path:
            return
        try:
            pid = profiles.import_file(path)
        except profiles.ProfileError as exc:
            self._profile_error(exc)
            return
        answer = QMessageBox.question(self, tr("Profiles"),
                                      tr("Imported as {name}. Use it now?", name=profiles.name_of(pid)))
        if answer == QMessageBox.StandardButton.Yes:
            self._use_profile(pid)

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
        search = self.search_page

        file_menu = bar.addMenu(tr("&File"))
        self._action(file_menu, tr("Data Sources…"), lambda: self._preferences("sources"), "Ctrl+Shift+I",
                     tip=tr("Import built-in sources with one click, or add your own"))
        self._action(file_menu, tr("Open Data Folder"), self._open_data_folder,
                     tip=tr("Open the folder that holds the isnady database"))
        profile_menu = file_menu.addMenu(tr("Profiles"))
        profile_menu.setToolTipsVisible(True)
        profile_menu.aboutToShow.connect(lambda m=profile_menu: self._fill_profile_menu(m))
        file_menu.addSeparator()
        self._action(file_menu, tr("Quit"), QApplication.quit, "Ctrl+Q")

        edit_menu = bar.addMenu(tr("&Edit"))
        self._action(edit_menu, tr("Find"), self._find, QKeySequence.StandardKey.Find)
        self._action(edit_menu, tr("Copy"), self._copy, QKeySequence.StandardKey.Copy)
        edit_menu.addSeparator()
        for text, step, key, standard in ((tr("Back"), -1, "Alt+Left", QKeySequence.StandardKey.Back),
                                          (tr("Forward"), +1, "Alt+Right", QKeySequence.StandardKey.Forward)):
            action = self._action(edit_menu, text, lambda _c=False, d=step: self._go_history(d))
            keys = [QKeySequence(key)]                 # and the platform's own (Cmd+[ on a Mac), once each
            keys += [k for k in QKeySequence.keyBindings(standard) if k.toString() != keys[0].toString()]
            action.setShortcuts(keys)
        edit_menu.addSeparator()
        self._action(edit_menu, tr("Preferences…"), lambda: self._preferences(), "Ctrl+,",
                     tip=tr("Fonts, sizes and colours for each script, theme colours, interface font"))

        view_menu = bar.addMenu(tr("&View"))
        self._section_actions = {}
        self._view_menu = view_menu
        for i, key in enumerate(self._order):
            label = dict((k, l) for k, l, _t in SECTIONS)[key]
            self._section_actions[key] = self._action(view_menu, tr(label),
                                                      lambda _c=False, k=key: self.nav.setCurrentRow(self._row(k)),
                                                      f"Ctrl+{i + 1}")
        view_menu.addSeparator()
        ui_menu = view_menu.addMenu(tr("Interface Language"))
        ui_menu.aboutToShow.connect(lambda: self._fill_ui_language_menu(ui_menu))
        content_menu = view_menu.addMenu(tr("Content Languages"))
        content_menu.aboutToShow.connect(lambda: self._fill_content_language_menu(content_menu))
        theme_menu = view_menu.addMenu(tr("Theme"))
        group = QActionGroup(self)
        self._theme_actions = {}
        choices = ([("system", tr("Follow system (Lapis / Lapis Night)"))]
                   + [(k, tr(v[0])) for k, v in theme.THEMES.items()])
        for n, (mode, label) in enumerate(choices):
            action = self._action(theme_menu, label, lambda _c=False, m=mode: self._set_theme(m))
            action.setCheckable(True)
            action.setChecked(theme.theme_mode() == mode)
            group.addAction(action)
            self._theme_actions[mode] = action
            if n == 0:
                theme_menu.addSeparator()
        theme_menu.addSeparator()
        self._action(theme_menu, tr("Choose with previews…"), lambda: self._preferences("themes"))
        text_menu = view_menu.addMenu(tr("Reading Text Size"))
        self._action(text_menu, tr("Larger"), lambda: self._change_text_scale(+1), "Ctrl++")
        self._action(text_menu, tr("Smaller"), lambda: self._change_text_scale(-1), "Ctrl+-")
        self._action(text_menu, tr("Default Size"), lambda: self._change_text_scale(0), "Ctrl+0")
        view_menu.addSeparator()
        self._action(view_menu, tr("Full Screen"), self._toggle_full_screen, "F11")

        tools_menu = bar.addMenu(tr("&Tools"))
        self._action(tools_menu, tr("Clear the Cache"), self._clear_cache,
                     tip=tr("Delete what isnady keeps so pages open fast; it is counted again when next needed"))
        self._action(tools_menu, tr("Rebuild Search Index"), lambda: search.rebuild_index(),
                     tip=tr("Rebuild the search index from every imported text"))
        self._action(tools_menu, tr("Read Chains Again"), lambda: search.rebuild_chains(),
                     tip=tr("Read every chain of transmission from the Arabic texts again"))
        self._action(tools_menu, tr("Identify Narrators Again"), lambda: search.identify_narrators(),
                     tip=tr("Match every name in the chains against the imported rijal works again"))
        tools_menu.addSeparator()
        self._action(tools_menu, tr("Create Desktop Shortcut…"), self._create_shortcut,
                     tip=tr("Put isnady on the desktop and in the applications menu, with its icon"))
        tools_menu.addSeparator()
        self._action(tools_menu, tr("Build AI Indexes (Meaning, Takhrij)"), lambda: search.build_meaning_index(),
                     tip=tr("Learn the meaning index (Match → By meaning) and find the narrations of each hadith "
                           "across the books (Also narrated in)"))

        help_menu = bar.addMenu(tr("&Help"))
        self._action(help_menu, tr("Search Tips"), lambda: dialogs.search_tips(self).exec())
        self._action(help_menu, tr("Keyboard Shortcuts"), lambda: dialogs.shortcuts(self).exec())
        help_menu.addSeparator()
        self._action(help_menu, tr("Check for Updates…"), self._check_updates,
                     tip=tr("The latest isnady on PyPI and npm, what is new, and the update"))
        self._action(help_menu, tr("Check Installation…"), self._check_installation,
                     tip=tr("Every copy of isnady on this computer, and which one really runs"))
        self._action(help_menu, tr("Licences"), lambda: dialogs.licenses(self, search.connection()).exec())
        self._action(help_menu, tr("isnady on GitHub"), lambda: QDesktopServices.openUrl(QUrl(dialogs.REPO_URL)))
        self._action(help_menu, tr("Report an Issue"), lambda: QDesktopServices.openUrl(QUrl(dialogs.ISSUES_URL)))
        help_menu.addSeparator()
        self._action(help_menu, tr("About isnady"), lambda: dialogs.about(self).exec())

    def _create_shortcut(self) -> None:
        import html as _html

        from PySide6.QtWidgets import QMessageBox

        from isnady.core import shortcut

        program, args, how = shortcut.launch_command()
        try:
            made = shortcut.create()
        except OSError as exc:
            QMessageBox.warning(self, tr("Create Desktop Shortcut"),
                                tr("The shortcut could not be created.") + f"\n\n{exc}")
            return
        where = {"desktop": tr("On the desktop"), "menu": tr("In the applications menu")}
        lines = "".join(f"<li><b>{where.get(w, w)}</b>: <code>{_html.escape(str(p))}</code></li>" for w, p in made)
        command = _html.escape(" ".join([program, *args]))
        box = QMessageBox(self)
        box.setWindowTitle(tr("Create Desktop Shortcut"))
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText("<p>" + tr("isnady now has a shortcut, with its own icon:") + f"</p><ul>{lines}</ul>"
                    "<p>" + tr("It starts {how}:", how=_html.escape(how)) + f"<br><code>{command}</code></p>"
                    "<p style='color:gray'>" + tr("Making it again replaces it, so after moving isnady or changing how "
                                                  "it is installed, create it once more.") + "</p>")
        box.exec()

    def _load_statistics_when_shown(self, row: int) -> None:
        """Statistics reads (or computes) only when it is opened."""
        if row == self._row("statistics") and not self._statistics_loaded:
            self._statistics_loaded = True
            self.statistics_page.refresh()

    def _load_books_when_shown(self, row: int) -> None:
        """The Books section reads its first chapter only when it is opened, not at start."""
        if row == self._row("books") and not self._books_loaded:
            self._books_loaded = True
            self.books_page.refresh()

    def _build(self, key: str, make):
        """A page, or a plain error card in its place when it cannot be built (ROB1: one page never stops isnady)."""
        try:
            return make()
        except Exception as exc:
            return _BrokenPage(key, exc, lambda: self._check_installation(), lambda: self._preferences("sources"))

    def check_interrupted_import(self) -> None:
        """An import cut short the last time (ROB1): said on the Search page, with where to import again."""
        try:
            from isnady.core import imports

            cut = imports.interrupted()
        except Exception:
            cut = None
        if not cut:
            return
        names = ", ".join(cut["titles"][:6]) + (" …" if len(cut["titles"]) > 6 else "")
        self.search_page._notice = tr("An import did not finish ({when}): {names}. The books imported before it are "
                                      "kept; import the rest again in File → Data Sources.",
                                      when=cut["started"].replace("T", " "), names=names)
        if not self.search_page.query_edit.text().strip():
            self.search_page._show_start()

    # --------------------------------------------------------------- back and forward (NAV2)
    _PLACE_SECTION = {"person_in_book": "books", "book": "books", "in_book": "books", "chapter": "books",
                      "narrator": "narrators", "scholar": "scholars", "term": "learn", "chain": "chains",
                      "tree": "genealogy", "genealogy": "genealogy"}

    @contextmanager
    def _place(self, entry: tuple):
        """Open something and leave it in the history; the section switch it makes is not a place of its own."""
        before, self._opening = self._opening, True
        try:
            yield
        finally:
            self._opening = before
        self._record(entry)

    def _section_shown(self, row: int) -> None:
        if not self._opening and 0 <= row < len(self._order):
            self._record(("section", self._order[row]))

    def _record(self, entry: tuple) -> None:
        if self._replaying:
            return
        if 0 <= self._at < len(self._history) and self._history[self._at] == entry:
            return
        del self._history[self._at + 1:]
        self._history.append(entry)
        if len(self._history) > 100:
            del self._history[0]
        self._at = len(self._history) - 1
        self._update_history_buttons()

    def _where(self, entry: tuple) -> str:
        labels = {k: l for k, l, _t in SECTIONS}
        key = entry[1] if entry[0] == "section" else self._PLACE_SECTION.get(entry[0], "search")
        return tr(labels.get(key, key))

    def _update_history_buttons(self) -> None:
        back = self._at > 0
        forward = self._at + 1 < len(self._history)
        self.back_button.setEnabled(back)
        self.forward_button.setEnabled(forward)
        self.back_button.setToolTip(tr("Back to {place} (Alt+Left)", place=self._where(self._history[self._at - 1]))
                                    if back else tr("Back (Alt+Left)"))
        self.forward_button.setToolTip(tr("Forward to {place} (Alt+Right)",
                                          place=self._where(self._history[self._at + 1]))
                                       if forward else tr("Forward (Alt+Right)"))

    def _go_history(self, step: int) -> None:
        target = self._at + step
        if not 0 <= target < len(self._history):
            return
        self._at = target
        entry = self._history[target]
        self._replaying = True
        try:
            if entry[0] == "section":
                if entry[1] in self._order:
                    self.nav.setCurrentRow(self._row(entry[1]))
            else:
                handler = {"person_in_book": self._open_person_in_book, "book": self._open_book,
                           "in_book": self._open_in_book, "narrator": self._open_narrator,
                           "scholar": self._open_scholar, "term": self._open_term, "chapter": self._open_chapter,
                           "chain": self._open_chain, "tree": self._open_tree,
                           "genealogy": self._open_genealogy}[entry[0]]
                handler(*entry[1:])
        except Exception:                 # a place that is gone (a book removed): stay where we are
            pass
        finally:
            self._replaying = False
        self._update_history_buttons()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt name)
        if event.type() == QEvent.Type.MouseButtonPress and self.isActiveWindow():
            if event.button() == Qt.MouseButton.BackButton:
                self._go_history(-1)
                return True
            if event.button() == Qt.MouseButton.ForwardButton:
                self._go_history(+1)
                return True
        return super().eventFilter(obj, event)

    def _open_person_in_book(self, person_id: int) -> None:
        with self._place(('person_in_book', person_id)):
            self._books_loaded = True
            self.nav.setCurrentRow(self._row("books"))
            self.books_page.show_person(person_id)

    def _open_book(self, key: str) -> None:
        with self._place(('book', key)):
            self._books_loaded = True
            self.nav.setCurrentRow(self._row("books"))
            self.books_page.refresh()
            self.books_page.select_work(key)

    def _open_in_book(self, hadith_id: int) -> None:
        with self._place(('in_book', hadith_id)):
            self._books_loaded = True
            self.nav.setCurrentRow(self._row("books"))
            self.books_page.show_hadith(hadith_id)

    def _open_narrator(self, person_id: int) -> None:
        with self._place(('narrator', person_id)):
            self.nav.setCurrentRow(self._row("narrators"))
            self.narrators_page.select(person_id)

    def _open_person(self, person_id: int, tradition: str) -> None:
        """A narrator found by Search, Sunni or Shia: on Narrators, which shows each by his tradition's measure."""
        self._open_narrator(person_id)

    def _open_scholar(self, scholar_id: str) -> None:
        with self._place(('scholar', scholar_id)):
            self.nav.setCurrentRow(self._row("scholars"))
            self.scholars_page.select(scholar_id)

    def _open_tree(self, which: str, target) -> None:
        with self._place(('tree', which, target)):
            self.nav.setCurrentRow(self._row("genealogy"))
            self.genealogy_page.open_place(which, target)

    def _open_genealogy(self, person_id: int, which: str) -> None:
        with self._place(('genealogy', person_id, which)):
            self.nav.setCurrentRow(self._row("genealogy"))
            self.genealogy_page.show_person(person_id, which)

    def _open_term(self, term_id: str) -> None:
        with self._place(('term', term_id)):
            self.nav.setCurrentRow(self._row("learn"))
            self.learn_page.show_term(term_id)

    def _open_chapter(self, chapter_id: int) -> None:
        with self._place(('chapter', chapter_id)):
            self._books_loaded = True
            self.nav.setCurrentRow(self._row("books"))
            self.books_page.show_chapter(chapter_id)

    def _open_chain(self, hadith_id: int) -> None:
        with self._place(('chain', hadith_id)):
            self.nav.setCurrentRow(self._row("chains"))
            self.isnad_page.show_hadith(hadith_id)

    def _open_data_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir())))

    def _find(self) -> None:
        self.nav.setCurrentRow(self._row("search"))
        self.search_page.focus_search()

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
            self.install_notice.setToolTip("\n".join(report.problems) + "\n\n" + tr(
                "Click for the report and the Update button: every copy is updated where it is installed."))
            self.install_notice.show()
        else:
            self.install_notice.hide()

    def _check_updates(self) -> None:
        from isnady.gui.update_dialog import UpdateDialog

        UpdateDialog(self).exec()

    def _check_installation(self) -> None:
        from isnady.gui.install_dialog import InstallDialog

        dialog = InstallDialog(self)
        dialog.exec()
        if dialog.report is not None:              # the warning in the sidebar follows the last report
            self._install_checked(dialog.report)

    def _preferences(self, tab: str = "") -> None:
        from isnady.gui.preferences import PreferencesDialog

        dialog = PreferencesDialog(self, start_tab=tab)
        dialog.changed.connect(self._apply_settings)
        dialog.data_imported.connect(self._data_imported)
        dialog.languages_changed.connect(self._languages_changed)
        dialog.sidebar_changed.connect(self.apply_sidebar_order)
        dialog.exec()

    # --------------------------------------------------------------- the first start (FR1)
    def offer_first_import(self) -> None:
        """An empty database at the start: ask once whether to bring in isnady-data's books, then import them in the
        background — the window stays usable, the progress shows in the bar at the bottom."""
        from PySide6.QtWidgets import QMessageBox

        from isnady import config
        from isnady.core import catalog

        conn = self.search_page.connection()
        try:
            empty = conn is None or conn.execute("SELECT 1 FROM hadiths LIMIT 1").fetchone() is None
        except Exception:
            empty = False
        if not empty or config.state_get("first_import.asked"):
            return
        config.state_set("first_import.asked", True)
        try:
            entries = catalog.builtin_entries()
        except Exception:
            entries = []
        books = sum(1 for e in entries if e.kind == "hadith")
        rijal = sum(1 for e in entries if e.kind == "rijal")
        if not entries:
            return
        langs = ", ".join(tr(catalog.language_label(c)) for c in catalog.DEFAULT_LANGUAGES)
        answer = QMessageBox.question(
            self, tr("Import the books?"),
            tr("isnady has no books yet. Import the {books} hadith books and the {rijal} rijal works of isnady-data now? "
               "Languages: {langs} (others can be added in File → Data Sources).\n\nThe import runs in the background "
               "and the window can be used meanwhile; the progress is shown at the bottom.",
               books=books, rijal=rijal, langs=langs),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
        if answer == QMessageBox.StandardButton.Yes:
            self.import_in_background()

    def import_in_background(self, languages=None) -> None:
        """Every source of the repository, imported by the Data Sources worker; the bottom bar shows where it is."""
        from PySide6.QtWidgets import QLabel as _Label, QProgressBar

        from isnady.gui import sources_page

        if any(w.isRunning() for w in sources_page._LIVE_WORKERS):
            return
        bar = self.statusBar()
        if not hasattr(self, "_import_label"):
            self._import_label = _Label()
            self._import_bar = QProgressBar()
            self._import_bar.setRange(0, 0)
            self._import_bar.setMaximumWidth(220)
            self._import_bar.setMaximumHeight(10)
            self._import_bar.setTextVisible(False)
            bar.addWidget(self._import_label, 1)
            bar.addPermanentWidget(self._import_bar)
        self._import_label.setText(tr("Importing the books of isnady-data…"))
        self._import_bar.show()
        bar.show()
        worker = sources_page.Worker("import_all", None, languages)
        sources_page._LIVE_WORKERS.add(worker)
        worker.finished.connect(lambda w=worker: (sources_page._LIVE_WORKERS.discard(w), w.deleteLater()))
        worker.progress.connect(lambda m: self._import_label.setText(m))
        worker.done.connect(self._background_import_done)
        worker.start()

    def _background_import_done(self, ok: bool, message: str) -> None:
        from PySide6.QtCore import QTimer

        self._import_bar.hide()
        self._import_label.setText(("" if ok else tr("Failed: ")) + message)
        self._data_imported()
        QTimer.singleShot(15000, self.statusBar().hide)

    def _data_imported(self) -> None:
        """A source was imported or removed from Data sources: bring every page up to date."""
        self.search_page._sync_with_database(force=True)
        for key in self._lazy:
            self._refresh_or_later(key)
        self.books_page.refresh()
        self.statistics_page.refresh()

    def _apply_settings(self) -> None:
        self._restyle(lambda: theme.apply(QApplication.instance()))
        for mode, action in getattr(self, "_theme_actions", {}).items():
            action.setChecked(theme.theme_mode() == mode)

    def _set_theme(self, mode: str) -> None:
        theme.set_theme_mode(mode)
        self._restyle(lambda: theme.apply(QApplication.instance(), mode))

    # ------------------------------------------------------------------ languages (L1)
    def _update_language_buttons(self) -> None:
        from isnady.core import language

        ui = language.UI_LANGUAGES[language.ui_language()]
        chosen = language.content_languages()
        content = ", ".join(tr(c) for c in chosen) if chosen else tr("all languages")
        self.ui_lang_button.setText(tr("Interface:") + "  " + ui)
        self.ui_lang_button.setToolTip(tr(
            "The interface language: the menus, pages and explanations, how every Arabic name is read (Musaddad b. "
            "Musarhad / Müsedded b. Müserhed) and the language of the glossary."))
        self.content_lang_button.setText(tr("Content:") + "  " + content)
        self.content_lang_button.setToolTip(tr(
            "The hadith texts are shown in: {languages}.\nA text that matches a search is shown whatever its "
            "language; each book in Books can still choose its own.", languages=content))

    def _fill_ui_language_menu(self, menu) -> None:
        """English and the translated languages first; the languages not translated yet in a submenu of their own.
        UI-B1 (Bayram, 2026-10-17: "Arayüz dilinden English kayboldu!"): one menu of all 58 languages was taller
        than the screen; opened upward from the sidebar it lost its first rows — English first of all — where the
        window system cannot move a menu (Wayland)."""
        from isnady.core import language

        from isnady.core import i18n

        menu.clear()
        group = QActionGroup(menu)
        current = language.ui_language()
        later = None

        def add(target, code, own):
            share = i18n.coverage(code)
            # its own name, its name in the interface language beside it, and how much of the interface is translated
            other = i18n.name_of(code)
            label = (own if other == own else f"{own}  ·  {other}") + ("" if share >= 0.995 else f"  ({share:.0%})")
            action = target.addAction(label)
            action.setCheckable(True)
            action.setChecked(code == current)
            group.addAction(action)
            action.triggered.connect(lambda _c=False, c=code: self._set_ui_language(c))

        for code, (own, _english, _rtl) in i18n.LANGUAGES.items():
            if code == "en" or i18n.coverage(code) > 0:
                add(menu, code, own)
                continue
            if later is None:
                menu.addSeparator()
                later = menu.addMenu(tr("Languages not translated yet"))
            add(later, code, own)
        menu.addSeparator()
        note = menu.addAction(tr("A text not yet translated is shown in English"))
        note.setEnabled(False)

    def _fill_content_language_menu(self, menu) -> None:
        from isnady.core import language
        from isnady.core import search as core_search

        menu.clear()
        conn = self.search_page.connection()
        available = core_search.list_languages(conn) if conn is not None else []
        chosen = language.content_languages()
        every = menu.addAction(tr("All languages"))
        every.setCheckable(True)
        every.setChecked(not chosen)
        every.triggered.connect(lambda: self._set_content_languages([]))
        menu.addSeparator()
        for lang in available:
            action = menu.addAction(tr(lang))
            action.setCheckable(True)
            action.setChecked(lang in chosen)
            action.triggered.connect(lambda checked, l=lang: self._toggle_content_language(l, checked))
        if not available:
            menu.addAction(tr("No texts imported yet")).setEnabled(False)

    def _toggle_content_language(self, lang: str, on: bool) -> None:
        from isnady.core import language
        from isnady.core import search as core_search

        conn = self.search_page.connection()
        available = core_search.list_languages(conn) if conn is not None else []
        chosen = language.content_languages() or list(available)
        chosen = [l for l in available if (l in chosen and l != lang) or (l == lang and on)]
        self._set_content_languages([] if not chosen or set(chosen) == set(available) else chosen)

    def _set_ui_language(self, code: str) -> None:
        from isnady.core import language

        from isnady import config
        from isnady.core import learn

        if code == language.ui_language():
            return
        language.set_ui_language(code)
        if code in learn.LANGUAGES:
            config.state_set("learn.language", code)    # the glossary in the same language, where it has one
        self.language_switched.emit()                    # main.py builds the window again in the new language

    def _set_content_languages(self, languages: list[str]) -> None:
        from isnady.core import language

        language.set_content_languages(languages)
        self._languages_changed()

    def _languages_changed(self) -> None:
        self.search_page.__dict__.pop("_person_cache", None)      # the narrators of the chains, read again
        self._update_language_buttons()
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.retheme()                                        # the page in view now, the others when opened
        finally:
            QGuiApplication.restoreOverrideCursor()

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
        self.footer.setText(message + "\n" + tr("version {version}", version=__version__))

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
