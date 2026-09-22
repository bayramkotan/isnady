"""Main window: a sidebar of sections and a page stack.

Each section is a placeholder until its own delivery builds it.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from isnady import APP_NAME, __version__

# (key, sidebar label, one-line description shown on the placeholder page)
SECTIONS = [
    ("search", "Search", "Search hadith text, books and grades (mutawatir, sahih, hasan, da'if, mawdu' ...)."),
    ("narrators", "Narrators", "Every narrator: biography, teachers, students, number of narrations, verdicts."),
    ("chains", "Isnad Chains", "Chains of transmission drawn link by link, with each narrator's standing."),
    ("books", "Books", "Hadith collections processed into the database and their coverage."),
    ("shia_rijal", "Shia Rijal", "Narrator verdicts from Shia rijal scholars, per person, beside the Sunni view."),
    ("statistics", "Statistics", "Counts, distributions and rankings across narrators, books and grades."),
    ("learn", "Learn", "Hadith sciences: terminology, grading, jarh wa ta'dil, the classical works."),
]


def _placeholder(title: str, text: str) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    heading = QLabel(title)
    font = heading.font()
    font.setPointSize(font.pointSize() + 6)
    font.setBold(True)
    heading.setFont(font)
    body = QLabel(text)
    body.setWordWrap(True)
    note = QLabel("Not built yet.")
    note.setEnabled(False)
    layout.addWidget(heading)
    layout.addWidget(body)
    layout.addSpacing(12)
    layout.addWidget(note)
    return page


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1100, 720)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(190)
        self.pages = QStackedWidget()

        for key, label, text in SECTIONS:
            self.sidebar.addItem(label)
            page = _placeholder(label, text)
            page.setObjectName(f"page_{key}")
            self.pages.addWidget(page)

        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        central = QWidget()
        row = QHBoxLayout(central)
        row.addWidget(self.sidebar)
        row.addWidget(self.pages, 1)
        self.setCentralWidget(central)

        self.statusBar().showMessage(f"{APP_NAME} {__version__} — no data loaded yet")
