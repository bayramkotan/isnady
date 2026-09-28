"""Help dialogs: search tips, keyboard shortcuts, licences, about."""

import html
import platform
import sqlite3
import sys

import PySide6
from PySide6.QtCore import Qt, qVersion
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QScrollArea, QVBoxLayout, QWidget

from isnady import __version__
from isnady.data.paths import data_dir, db_path
from isnady.gui import theme

REPO_URL = "https://github.com/bayramkotan/isnady"
ISSUES_URL = REPO_URL + "/issues"
PYPI_URL = "https://pypi.org/project/isnady/"

SHORTCUTS = (
    ("Ctrl+F", "Find: jump to the search field"),
    ("Enter", "Run the search"),
    ("Ctrl+1 … Ctrl+8", "Switch between sections"),
    ("Ctrl++ / Ctrl+− / Ctrl+0", "Larger, smaller or default reading text"),
    ("F11", "Full screen"),
    ("Ctrl+Q", "Quit"),
)


class InfoDialog(QDialog):
    """A themed, scrollable dialog with a title and rich-text body."""

    def __init__(self, parent: QWidget | None, title: str, body_html: str, width: int = 620) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(width, 520)
        heading = QLabel(title)
        heading.setObjectName("PageTitle")
        heading.setFont(theme.reading_font(20, bold=True))
        body = QLabel(body_html)
        body.setObjectName("Lead")
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        body.setOpenExternalLinks(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        holder = QWidget()
        holder.setObjectName("Page")
        inner = QVBoxLayout(holder)
        inner.setContentsMargins(0, 0, 8, 0)
        inner.addWidget(body)
        inner.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(holder)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).setObjectName("Quiet")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 18)
        layout.setSpacing(12)
        layout.addWidget(heading)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)


def search_tips(parent) -> InfoDialog:
    return InfoDialog(parent, "Search tips", """
<p><b>Arabic is matched without diacritics.</b> الاعمال finds الأَعْمَالُ. Alef forms (أ إ آ ٱ), alef maqsura,
hamza seats and ta marbuta are treated alike, so you can type the way you normally write.</p>
<p><b>Attached prefixes are found.</b> النيات also finds بالنيات, because Arabic joins bi-, wa-, fa- and al- to
the word. Turn on <i>Whole words only</i> to find the word standing on its own.</p>
<p><b>Latin-script text ignores case and accents.</b> NIYET, niyet and nîyet are the same; Muʿādh, Mu'adh and
Muadh are the same.</p>
<p><b>Match.</b> <i>All words</i> needs every word in the same text. <i>Any word</i> needs one of them.
<i>Exact phrase</i> needs the words together, in order.</p>
<p><b>Book and Language</b> narrow the results. The language filter also decides which translations appear under
each hadith.</p>
<p><b>Grades</b> are shown exactly as each scholar gave them, with the scholar's name. isnady does not merge or
rewrite them.</p>""")


def shortcuts(parent) -> InfoDialog:
    rows = "".join(f"<tr><td style='padding:4px 18px 4px 0'><b>{html.escape(k)}</b></td>"
                   f"<td style='padding:4px 0'>{html.escape(v)}</td></tr>" for k, v in SHORTCUTS)
    return InfoDialog(parent, "Keyboard shortcuts", f"<table>{rows}</table>", width=560)


def licenses(parent, conn: sqlite3.Connection | None) -> InfoDialog:
    tier_text = {"A": "may be redistributed", "B": "may be redistributed under its conditions",
                 "C": "may not be redistributed"}
    rows = []
    if conn is not None:
        for r in conn.execute("SELECT name, license, tier, origin, location FROM sources ORDER BY origin, name"):
            origin = "User Resource" if r["origin"] == "user" else "Built-in"
            rows.append(
                f"<p><b>{html.escape(r['name'])}</b> ({origin})<br>"
                f"Licence: {html.escape(r['license'] or 'not stated')}; tier {r['tier']}, {tier_text[r['tier']]}.<br>"
                f"<span style='font-size:9pt'>{html.escape(r['location'])}</span></p>")
    data = "".join(rows) or "<p>No data sources imported yet.</p>"
    return InfoDialog(parent, "Licences", f"""
<p><b>isnady</b> — MIT licence. <a href="{REPO_URL}">{REPO_URL}</a></p>
<p><b>Amiri</b> typeface by Khaled Hosny — SIL Open Font License 1.1.
<a href="https://github.com/aliftype/amiri">github.com/aliftype/amiri</a></p>
<p><b>Qt for Python (PySide6)</b> — LGPL v3.</p>
<h3>Data in this database</h3>
<p>Every hadith, grade and text belongs to the source it came from. Tier C sources and User Resources stay on
this computer and are never published.</p>
{data}""")


def about(parent) -> InfoDialog:
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='trigram')")
        fts = "available"
    except sqlite3.OperationalError:
        fts = "not available (search scans instead)"
    return InfoDialog(parent, "About isnady", f"""
<p><span style='font-size:15pt'>isnady {__version__}</span><br>
Hadith search built around the isnad, the chain of transmission.</p>
<p>By Bayram Kotan. <a href="{REPO_URL}">GitHub</a>, <a href="{PYPI_URL}">PyPI</a>,
<a href="{ISSUES_URL}">report an issue</a>.</p>
<table>
<tr><td style='padding:3px 16px 3px 0'>Python</td><td>{platform.python_version()} ({html.escape(sys.platform)})</td></tr>
<tr><td style='padding:3px 16px 3px 0'>PySide6 / Qt</td><td>{PySide6.__version__} / {qVersion()}</td></tr>
<tr><td style='padding:3px 16px 3px 0'>SQLite</td><td>{sqlite3.sqlite_version}, FTS5 trigram {fts}</td></tr>
<tr><td style='padding:3px 16px 3px 0'>Data folder</td><td>{html.escape(str(data_dir()))}</td></tr>
<tr><td style='padding:3px 16px 3px 0'>Database</td><td>{html.escape(str(db_path()))}</td></tr>
</table>""", width=640)
