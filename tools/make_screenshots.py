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
from isnady.gui.preferences import PreferencesDialog
d = PreferencesDialog(w); d.resize(900, 660); d.show(); settle(); d.grab().save(D + "preferences.png"); d.close()
theme.set_theme_mode("system")
