"""Main window: a lapis sidebar with the sections and a page stack.

Sections without their own page yet show a short description.
"""

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
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

        self.footer = QLabel(f"version {__version__}")
        self.footer.setObjectName("SidebarFooter")
        self.footer.setContentsMargins(26, 0, 26, 0)
        self.footer.setWordWrap(True)
        side.addWidget(self.footer)

        self.pages = QStackedWidget()
        for key, label, text in SECTIONS:
            self.nav.addItem(label)
            self.nav.item(self.nav.count() - 1).setSizeHint(QSize(0, 38))
            if key == "search":
                page = SearchPage(status_message=self._set_footer)
            else:
                page = _placeholder(label, text)
            self.pages.addWidget(page)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
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
        self._action(file_menu, "Open Data Folder", self._open_data_folder,
                     tip="Open the folder that holds the isnady database")
        file_menu.addSeparator()
        self._action(file_menu, "Quit", QApplication.quit, "Ctrl+Q")

        edit_menu = bar.addMenu("&Edit")
        self._action(edit_menu, "Find", self._find, QKeySequence.StandardKey.Find)
        self._action(edit_menu, "Copy", self._copy, QKeySequence.StandardKey.Copy)

        view_menu = bar.addMenu("&View")
        for i, (_key, label, _text) in enumerate(SECTIONS):
            self._action(view_menu, label, lambda _c=False, row=i: self.nav.setCurrentRow(row), f"Ctrl+{i + 1}")
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu("Theme")
        group = QActionGroup(self)
        for mode, label in (("system", "Follow system"), ("light", "Light"), ("dark", "Dark")):
            action = self._action(theme_menu, label, lambda _c=False, m=mode: self._set_theme(m))
            action.setCheckable(True)
            action.setChecked(theme.theme_mode() == mode)
            group.addAction(action)
        text_menu = view_menu.addMenu("Reading Text Size")
        self._action(text_menu, "Larger", lambda: self._change_text_scale(+1), "Ctrl++")
        self._action(text_menu, "Smaller", lambda: self._change_text_scale(-1), "Ctrl+-")
        self._action(text_menu, "Default Size", lambda: self._change_text_scale(0), "Ctrl+0")
        view_menu.addSeparator()
        self._action(view_menu, "Full Screen", self._toggle_full_screen, "F11")

        tools_menu = bar.addMenu("&Tools")
        self._action(tools_menu, "Rebuild Search Index", lambda: search.rebuild_index(),
                     tip="Rebuild the search index from every imported text")

        help_menu = bar.addMenu("&Help")
        self._action(help_menu, "Search Tips", lambda: dialogs.search_tips(self).exec())
        self._action(help_menu, "Keyboard Shortcuts", lambda: dialogs.shortcuts(self).exec())
        help_menu.addSeparator()
        self._action(help_menu, "Licences", lambda: dialogs.licenses(self, search.connection()).exec())
        self._action(help_menu, "isnady on GitHub", lambda: QDesktopServices.openUrl(QUrl(dialogs.REPO_URL)))
        self._action(help_menu, "Report an Issue", lambda: QDesktopServices.openUrl(QUrl(dialogs.ISSUES_URL)))
        help_menu.addSeparator()
        self._action(help_menu, "About isnady", lambda: dialogs.about(self).exec())

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

    def _set_theme(self, mode: str) -> None:
        theme.set_theme_mode(mode)
        theme.apply(QApplication.instance(), mode)
        self.retheme()

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
        """Called when the system switches between light and dark."""
        for i in range(self.pages.count()):
            page = self.pages.widget(i)
            if hasattr(page, "retheme"):
                page.retheme()
