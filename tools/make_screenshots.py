"""Regenerate the README screenshots in assets/screenshots/.

Needs a database imported from isnady-data with, at least, Sahih al-Bukhari, Sunan Abi Dawud (Arabic, Turkish,
English), al-Kafi of al-Kulayni, Ibn Hajar's Taqrib and al-Najashi's Rijal. Run from the repository root:

    python tools/make_screenshots.py

On a machine without a display, set QT_QPA_PLATFORM=offscreen first.
"""

from pathlib import Path

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QTabWidget

app = QApplication([])
from isnady.gui import theme  # noqa: E402

theme.load_fonts()
theme.apply(app, "light")
from isnady.core import language, repositories  # noqa: E402
from isnady.gui.main_window import SECTIONS, MainWindow  # noqa: E402
from isnady.gui.preferences import PreferencesDialog  # noqa: E402

D = str(Path(__file__).resolve().parent.parent / "assets" / "screenshots") + "/"
ROW = {k: i for i, (k, *_r) in enumerate(SECTIONS)}
language.set_content_languages([])
repositories.select(repositories.DEFAULT_ID)


def settle(ms=900):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def wait_statistics(page):
    for _ in range(600):
        if page._thread is not None and not page._thread.isRunning():
            break
        settle(500)
    settle(1500)


def prefs(tab: str, name: str, size=(1000, 760), scroll_to: int = 0):
    d = PreferencesDialog(w)
    d.resize(*size)
    tabs = d.findChild(QTabWidget)
    tabs.setCurrentIndex([tabs.tabText(i) for i in range(tabs.count())].index(tab))
    d.show()
    settle(1200)
    d.grab().save(D + name)
    d.close()


w = MainWindow()
w.resize(1400, 900)
w.show()
settle()
w.grab().save(D + "start.png")
p = w.search_page
p.book_combo._chosen = {"bukhari"}
p.book_combo._label()
p.search_for("النيات")
settle()
w.grab().save(D + "search-arabic.png")
p.book_combo._chosen = {"abudawud"}
p.book_combo._label()
p.search_for("niyet")
settle()
w.grab().save(D + "search-grades.png")
p.book_combo._chosen = None
p.book_combo._label()
p.book_combo._open()
settle(600)
popup = [x for x in app.topLevelWidgets() if isinstance(x, QFrame) and x.isVisible()
         and x.windowFlags() & Qt.WindowType.Popup][0]
popup.grab().save(D + "book-picker.png")
popup.close()
language.set_content_languages(["Arabic"])
p.book_combo._chosen = {"riyad", "nawawi"}
p.book_combo._label()
p.search_for("الصلاة")
settle(1500)
for b in p.body.findChildren(QPushButton):
    if b.text().startswith("▸"):
        b.click()
        settle(400)
        p.scroll.ensureWidgetVisible(b, 0, 260)
        break
settle(600)
w.grab().save(D + "search-folded.png")
language.set_content_languages([])
p.book_combo._chosen = None
p.book_combo._label()

w.nav.setCurrentRow(ROW["chains"])
w.isnad_page._current = None
w.isnad_page.refresh()
settle()
w.grab().save(D + "chains-overview.png")
hid = w.isnad_page.conn.execute("select h.id from hadiths h join collections c on c.id=h.collection_id "
                                "where c.key='bukhari' and h.number='1'").fetchone()[0]
w.isnad_page.show_hadith(hid)
settle()
w.grab().save(D + "chain.png")
w.isnad_page.body.grab().save(D + "chain-full.png")
w._set_theme("dark")
hid = w.isnad_page.conn.execute("select h.id from hadiths h join collections c on c.id=h.collection_id "
                                "where c.key='abudawud' and h.number='1500'").fetchone()[0]
w.isnad_page.show_hadith(hid)
settle()
w.grab().save(D + "chain-dark.png")
w.nav.setCurrentRow(ROW["search"])
p.search_for("namaz")
settle()
w.grab().save(D + "search-dark.png")
w._set_theme("light")

w.nav.setCurrentRow(w._narrators_row)
w.narrators_page.set_tradition(None)
w.narrators_page.query.setText("Ibn Umar")
settle(1200)
w.narrators_page.list.setCurrentRow(0)
settle()
w.grab().save(D + "narrators.png")
w.nav.setCurrentRow(ROW["scholars"])
w.scholars_page.select("albani")
settle()
w.grab().save(D + "scholars.png")
w.nav.setCurrentRow(w._books_row)
settle(1500)
w.books_page.select_work("bukhari")
settle()
w.books_page.open_chapter(w.books_page._order[1])
settle(1500)
w.grab().save(D + "books.png")
w.books_page.select_work("taqrib")
settle(1500)
w.grab().save(D + "books-taqrib.png")
w.nav.setCurrentRow(w._narrators_row)
w.narrators_page.set_tradition("shia")
w.narrators_page.query.setText("زرارة")
settle(1500)
w.narrators_page.list.setCurrentRow(0)
settle()
w.grab().save(D + "narrators-shia.png")
w.narrators_page.set_tradition(None)
w.narrators_page.query.setText("")
w.nav.setCurrentRow(ROW["chains"])
hid = w.isnad_page.conn.execute("select h.id from hadiths h join collections c on c.id=h.collection_id "
                                "where c.key='kafi' and h.number='5:1740'").fetchone()[0]
w.isnad_page.show_hadith(hid)
settle()
w.grab().save(D + "chain-shia.png")

st = w.statistics_page
w.nav.setCurrentRow(w._statistics_row)
settle(1500)
wait_statistics(st)
keys = [st.rail.item(i).data(Qt.ItemDataRole.UserRole) for i in range(st.rail.count())]
st.rail.setCurrentRow(keys.index("narrators"))
settle(800)
w.grab().save(D + "statistics.png")
st.rail.setCurrentRow(keys.index("lab"))
settle(800)
from PySide6.QtWidgets import QComboBox  # noqa: E402

for combo in st.stack.currentWidget().findChildren(QComboBox):
    i = combo.findText("Sunan Abi Dawud")
    if i >= 0:
        combo.setCurrentIndex(i)
        settle(1200)
        break
w.grab().save(D + "statistics-lab.png")
st.rail.setCurrentRow(keys.index("model"))
settle(800)
w.grab().save(D + "statistics-model.png")

w.nav.setCurrentRow(ROW["learn"])
w.learn_page._set_lang("en")
w.learn_page.show_term("mursal")
settle()
w.grab().save(D + "learn.png")

# Genealogies: the prophets around Ibrahim; a narrator's family (Salim b. 'Abdullah b. 'Umar)
genealogy = w.genealogy_page
w.nav.setCurrentRow(ROW["genealogy"])
settle(1500)
genealogy.show_view("prophets")
genealogy.find.setText("Ibrahim")
genealogy._find()
settle(800)
genealogy.view.centre("ibrahim")
settle(400)
w.grab().save(D + "genealogy.png")
conn = w.search_page.connection()
salim = conn.execute("SELECT id FROM persons WHERE name_ar LIKE 'سالم بن عبد الله بن عمر بن الخطاب%'").fetchone()
if salim:
    genealogy.find.clear()
    genealogy.show_view("family", salim[0])
    settle(1200)
    genealogy.view.centre(f"p{salim[0]}")
    settle(400)
    w.grab().save(D + "genealogy-family.png")

# Bookmarks: a few marked things in folders — the user's own bookmarks are put back afterwards
from isnady.core import bookmarks  # noqa: E402
from isnady.gui.bookmarks_page import HUB  # noqa: E402

kept = bookmarks.path().read_bytes() if bookmarks.path().exists() else None
store = bookmarks.Store()
first = conn.execute("""SELECT h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id
                        WHERE c.key = 'bukhari' AND h.number = '1'""").fetchone()
intention = store.ensure_path("Intention/Deeds")
if first:
    store.add("hadith", *bookmarks.hadith_ref(conn, first[0]), folder=intention.id,
              note="Deeds are judged by intentions")
if salim:
    store.add("narrator", *bookmarks.narrator_ref(conn, salim[0]), folder=store.ensure_path("Families of narrators").id)
store.add("scholar", "bukhari", "al-Bukhari", "محمد بن إسماعيل البخاري")
store.add("term", "mursal", "mursal", "مرسل", folder=intention.id)
store.save()
HUB.changed.emit()
w.nav.setCurrentRow(ROW["bookmarks"])
settle(1200)
w.grab().save(D + "bookmarks.png")
if kept is None:
    bookmarks.path().unlink()
else:
    bookmarks.path().write_bytes(kept)
HUB.changed.emit()

prefs("Reading text", "preferences.png", (900, 660))
prefs("Data sources", "data-sources.png", (1100, 900))
prefs("Books and languages", "books-languages.png", (1000, 640))
theme.set_theme_mode("system")
