"""tools/measure_speed.py — isnady'nin bu bilgisayarda nerede yavaşladığını ölçer ve isnady_olcum.txt dosyasına yazar.

Kullanım:  python tools/measure_speed.py <isnady kaynak klasörü>     (ör. ~/Github/isnady  ya da  C:\\Github\\isnady)
isnady'nin kendisi KAPALIYKEN çalıştırın. Pencere açılmaz (ekransız çalışır); verilerinizi değiştirmez, yalnız
isnady'nin önbellek dosyalarını (cache/*.json) yazabilir.
"""

import cProfile
import io
import os
import platform
import pstats
import sys
import time
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else ".").expanduser().resolve() / "src"
# which isnady the usual "iy" starts (before the source folder is put first): a copy installed from PyPI does not
# have what was pushed to the source folder
import shutil  # noqa: E402
import subprocess  # noqa: E402

installed = subprocess.run([sys.executable, "-c", "import isnady, sys; print(isnady.__version__, isnady.__file__)"],
                           capture_output=True, text=True, cwd=str(Path.home())).stdout.strip() or "(none)"
iy = shutil.which("iy") or "(not on PATH)"
sys.path.insert(0, str(src))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
out = Path.home() / "isnady_olcum.txt"
lines: list[str] = []


def say(text: str = "") -> None:
    print(text)
    lines.append(text)


T0 = time.perf_counter()
from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
import isnady  # noqa: E402
from isnady.data.paths import data_dir, db_path  # noqa: E402

say(f"measured: isnady {isnady.__version__} from {Path(isnady.__file__).parent}")
say(f"the usual one (this Python): {installed}")
say(f"iy command: {iy}")
say(f"{platform.platform()} · Python {platform.python_version()} · {platform.processor()}")
say(f"data folder: {data_dir()}")
db = Path(db_path())
say(f"database: {db.stat().st_size / 1e6:,.0f} MB" if db.exists() else "database: none")
cache_dir = data_dir() / "cache"
say(f"cache: {len(list(cache_dir.glob('*.json'))) if cache_dir.exists() else 0} files")

from isnady.gui import theme  # noqa: E402

theme.load_fonts()
theme.apply(app, "light")
from isnady.gui.main_window import MainWindow  # noqa: E402

times: list[tuple[str, float]] = []


def settle(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def timed(label: str, action) -> None:
    t = time.perf_counter()
    try:
        action()
        app.processEvents()
        times.append((label, time.perf_counter() - t))
    except Exception as exc:  # a failing step is reported, the rest still measured
        times.append((f"{label}  [HATA: {exc}]", time.perf_counter() - t))


profile = cProfile.Profile()
profile.enable()
w = None


def make():
    global w
    w = MainWindow()
    w.resize(1400, 900)
    w.show()


timed("pencere", make)
settle(3000)                 # the user looks at the window a moment (pages are prepared meanwhile)
conn = w.search_page.connection()
if conn is not None:
    from isnady.core import cache

    t = time.perf_counter()
    cache._full_stamp(conn)
    times.append(("veritabanı damgası", time.perf_counter() - t))
    for table in ("hadiths", "texts", "isnads", "isnad_links", "grades", "persons", "work_nodes"):
        try:
            say(f"  {table}: {conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:,}")
        except Exception:
            pass
    keys = [k for k in w._order if k != "statistics"]
    for k in keys:
        timed(f"sayfa: {k}", lambda k=k: w.nav.setCurrentRow(w._row(k)))
    for k in keys:
        timed(f"sayfa tekrar: {k}", lambda k=k: w.nav.setCurrentRow(w._row(k)))

    def search(text):
        w.nav.setCurrentRow(w._row("search"))
        w.search_page.query_edit.setText(text)
        w.search_page.run_search()

    timed("arama: النيات", lambda: search("النيات"))
    timed("arama: niyet", lambda: search("niyet"))
    timed("arama tekrar: niyet", lambda: search("niyet"))
    row = conn.execute("SELECT h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id "
                       "WHERE c.key = 'bukhari' AND h.number = '1'").fetchone()
    person = conn.execute("SELECT id FROM persons WHERE name_ar LIKE 'عبد الله بن عمر بن الخطاب%'").fetchone()
    if row:
        timed("isnad: Buhârî 1", lambda: w._open_chain(row[0]))
        timed("kitapta aç: Buhârî 1", lambda: w._open_in_book(row[0]))
    if person:
        timed("râvi: İbn Ömer", lambda: w._open_narrator(person[0]))
        timed("şecere: aile", lambda: w._open_genealogy(person[0], "family"))
    timed("âlim: Elbânî", lambda: w._open_scholar("albani"))
    w.nav.setCurrentRow(w._row("books"))
    for key in ("ahmad", "muslim", "kafi"):
        timed(f"kitap seç: {key}", lambda key=key: w.books_page.select_work(key))
    if getattr(w.books_page, "_order", None) and len(w.books_page._order) > 2:
        timed("sonraki bölüm", lambda: w.books_page.open_chapter(w.books_page._order[2]))
    timed("sayfa: statistics", lambda: w.nav.setCurrentRow(w._row("statistics")))
profile.disable()

say("")
say("SÜRELER (saniye)")
for label, seconds in times:
    say(f"  {seconds:7.2f}  {label}")
say(f"  {time.perf_counter() - T0:7.2f}  TOPLAM")
for title, key, pattern, n in (("EN ÇOK SÜRE ALANLAR (isnady, toplam)", "cumulative", r"isnady", 45),
                                ("EN ÇOK SÜRE ALANLAR (her şey, kendi süresi)", "tottime", "", 30)):
    s = io.StringIO()
    stats = pstats.Stats(profile, stream=s).sort_stats(key)
    stats.print_stats(pattern, n) if pattern else stats.print_stats(n)
    say("")
    say(title)
    say(s.getvalue())
out.write_text("\n".join(lines), encoding="utf-8")
print(f"\nYazıldı: {out}")
os._exit(0)
