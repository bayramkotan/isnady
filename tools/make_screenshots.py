"""Regenerate the README screenshots in assets/screenshots/.

Needs an imported database with Sahih al-Bukhari and Sunan Abi Dawud (Arabic and
Turkish). Run from the repository root:

    python tools/make_screenshots.py

On a machine without a display, set QT_QPA_PLATFORM=offscreen first.
"""

from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QEventLoop
app = QApplication([])
from isnady.gui import theme
theme.load_fonts(); theme.apply(app, "light")
from isnady.gui.main_window import MainWindow
D = str(Path(__file__).resolve().parent.parent / "assets" / "screenshots") + "/"
def settle(ms=900):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()
w = MainWindow(); w.resize(1400, 900); w.show(); settle()
w.grab().save(D + "start.png")
p = w.search_page
p.search_for("النيات"); settle(); w.grab().save(D + "search-arabic.png")
p.search_for("niyet"); p.book_combo.setCurrentIndex(p.book_combo.findData("abudawud")); settle(); w.grab().save(D + "search-grades.png")
p.book_combo.setCurrentIndex(0); settle(300)
w.nav.setCurrentRow(2); w.isnad_page._current = None; w.isnad_page.refresh(); settle(); w.grab().save(D + "chains-overview.png")
hid = w.isnad_page.conn.execute("select h.id from hadiths h join collections c on c.id=h.collection_id where c.key='bukhari' and h.number='1'").fetchone()[0]
w.isnad_page.show_hadith(hid); settle(); w.grab().save(D + "chain.png")
w.isnad_page.body.grab().save(D + "chain-full.png")
w._set_theme("dark")
hid = w.isnad_page.conn.execute("select h.id from hadiths h join collections c on c.id=h.collection_id where c.key='abudawud' and h.number='1500'").fetchone()[0]
w.isnad_page.show_hadith(hid); settle(); w.grab().save(D + "chain-dark.png")
w.nav.setCurrentRow(0); p.search_for("namaz"); settle(); w.grab().save(D + "search-dark.png")
w._set_theme("light")
w.nav.setCurrentRow(w._narrators_row); w.narrators_page.query.setText("Ibn Umar"); settle(1200)
w.narrators_page.list.setCurrentRow(0); settle(); w.grab().save(D + "narrators.png")
w.nav.setCurrentRow([k for k, *_ in __import__("isnady.gui.main_window", fromlist=["SECTIONS"]).SECTIONS].index("scholars"))
w.scholars_page.select("albani"); settle(); w.grab().save(D + "scholars.png")
w.nav.setCurrentRow(w._books_row); settle(1500)
w.books_page.select_work("bukhari"); settle(); w.books_page.open_chapter(w.books_page._order[1]); settle(1500)
w.grab().save(D + "books.png")
w.books_page.select_work("taqrib"); settle(1500); w.grab().save(D + "books-taqrib.png")
w.nav.setCurrentRow(w._shia_row); w.shia_page.query.setText("بابويه"); settle(1200)
w.shia_page.list.setCurrentRow(0); settle(); w.grab().save(D + "shia-rijal.png")
w.nav.setCurrentRow(w._statistics_row); settle(1500)
for _ in range(240):
    if w.statistics_page._thread is not None and not w.statistics_page._thread.isRunning():
        break
    settle(500)
settle(1500); w.grab().save(D + "statistics.png")
from isnady.gui.main_window import SECTIONS as _SECTIONS
w.nav.setCurrentRow([k for k, *_ in _SECTIONS].index("learn")); w.learn_page._set_lang("en"); w.learn_page.show_term("mursal")
settle(); w.grab().save(D + "learn.png")
from isnady.gui.preferences import PreferencesDialog
d = PreferencesDialog(w); d.resize(900, 660); d.show(); settle(); d.grab().save(D + "preferences.png"); d.close()
theme.set_theme_mode("system")
