"""File → Export… and File → Import… (EX1): anything isnady holds, in the format chosen, with a preview before it
is written. Everything is decided in core.transfer; this only asks what, how and where."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from isnady.core import formats as F
from isnady.core import transfer as T
from isnady.core.i18n import N_, tr

_KIND_TEXT = {"hadith": N_("Hadith (by number)"), "book": N_("A book or a chapter"), "search": N_("Search results"),
              "bookmarks": N_("Bookmarks"), "narrators": N_("Narrators"),
              "network": N_("Isnad network (who narrated from whom)"), "settings": N_("Settings"),
              "profile": N_("Profile"), "backup": N_("Everything of mine (backup)"), "statistics": N_("Statistics")}
_KIND_HELP = {
    "hadith": N_("The hadith named, with their chapter, texts, grades and chains (Arabic as written, then in "
                 "Turkish and English)."),
    "book": N_("A whole book or one chapter. \"isnady book\" keeps it so that it can be imported again as a book."),
    "search": N_("The hadith a search finds (up to 1,000), as on the Search page."),
    "bookmarks": N_("Your bookmarks with their folders and notes. JSON is isnady's own and comes back with the "
                    "folders as they were."),
    "narrators": N_("The narrators of a tradition: their names, tabaqa, death, rank and verdict, and how often they "
                    "are in the chains."),
    "network": N_("Who narrated from whom in the chains, and how often: for Gephi, yEd or a spreadsheet."),
    "settings": N_("The settings you changed."),
    "profile": N_("A profile with its settings, place and bookmarks."),
    "backup": N_("This profile's settings, place and bookmarks and the list of the books imported: what makes your "
                 "isnady yours, in one file."),
    "statistics": N_("The results of the Statistics page — the corpus, the model, the laboratory and the graders — as "
                     "data. Each chart and table on the Statistics page has its own ⤓ too, and its Export button "
                     "writes a section or all of them as PDF, a web page or Excel."),
}


def _label(text: str, name: str = "", wrap: bool = True) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


class _CheckList(QWidget):
    """Several at once, or all of them (Bayram, 2026-10-24: "birden fazla kitap/..... secilebilir olsun. Hepsi de
    olsun"): a list to tick, with All, None and — for books — Sunni and Shia."""

    changed = Signal()

    def __init__(self, items: list[tuple[str, str, str]], checked: list[str], groups: bool = False) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.list = QListWidget()
        self.list.setMaximumHeight(170)
        for key, text, group in items:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setData(Qt.ItemDataRole.UserRole + 1, group)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if key in checked else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        self.list.itemChanged.connect(lambda _i: self._count())
        lay.addWidget(self.list)
        row = QHBoxLayout()
        row.setSpacing(6)
        picks = [(tr("All"), lambda _g: True), (tr("None"), lambda _g: False)]
        if groups:
            picks += [(tr("Sunni"), lambda g: g == "sunni"), (tr("Shia"), lambda g: g == "shia")]
        for text, test in picks:
            b = QPushButton(text)
            b.setObjectName("Quiet")
            b.clicked.connect(lambda _c=False, t=test: self._pick(t))
            row.addWidget(b)
        row.addStretch(1)
        self.count = QLabel("")
        self.count.setObjectName("Caption")
        row.addWidget(self.count)
        lay.addLayout(row)
        self._count()

    def _pick(self, test) -> None:
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setCheckState(Qt.CheckState.Checked if test(item.data(Qt.ItemDataRole.UserRole + 1))
                               else Qt.CheckState.Unchecked)
        self.list.blockSignals(False)
        self._count()

    def _count(self) -> None:
        self.count.setText(tr("{n} of {total} chosen", n=len(self.keys()), total=self.list.count()))
        self.changed.emit()

    def keys(self) -> list[str]:
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.CheckState.Checked]

    def every(self) -> bool:
        return self.list.count() > 0 and len(self.keys()) == self.list.count()


class _Job(QThread):
    """A long export or import beside the window, with a connection of its own."""
    progress = Signal(str)
    done = Signal(bool, str)

    def __init__(self, work) -> None:
        super().__init__()
        self._work = work

    def run(self) -> None:
        from isnady.data import db

        conn = db.connect()
        try:
            result = self._work(conn, self.progress.emit)
            self.done.emit(True, str(result))
        except (T.TransferError, OSError, ValueError, KeyError) as exc:
            self.done.emit(False, str(exc))
        except Exception as exc:          # anything else: said, never a crash of the window
            self.done.emit(False, f"{type(exc).__name__}: {exc}")
        finally:
            conn.close()


class ExportDialog(QDialog):
    def __init__(self, connection_getter, parent=None, kind: str = "hadith", preset: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Export"))
        self.resize(820, 680)
        self._conn_of = connection_getter
        self._job = None
        preset = preset or {}
        box = QVBoxLayout(self)
        box.setSpacing(10)
        box.addWidget(_label(tr("Export"), "CardTitle", False))

        form = QFormLayout()
        self.kind = QComboBox()
        for key in T.KINDS:
            self.kind.addItem(tr(_KIND_TEXT[key]), key)
        form.addRow(tr("What"), self.kind)
        self.help = _label("", "Caption")
        form.addRow("", self.help)

        self.scope = QStackedWidget()
        self._scopes: dict[str, QWidget] = {}
        conn = self._conn_of()
        from isnady.core import works

        book_list = works.list_works(conn) if conn is not None else []
        # hadith
        self.refs = QLineEdit(preset.get("refs", ""))
        self.refs.setPlaceholderText("bukhari:1  bukhari:5-10  muslim:8")
        self._add_scope("hadith", [(tr("Hadith"), self.refs)])
        # book: one, several or all; a chapter when one book is chosen
        hadith_books = [w for w in book_list if w.get("kind") == "hadith"]
        first = preset.get("book") or (hadith_books[0]["key"] if hadith_books else "")
        self.books = _CheckList([(w["key"], f"{w['title']} ({w['key']})", w["tradition"]) for w in hadith_books],
                                [first], groups=True)
        self.books.changed.connect(self._fill_chapters)
        self.chapter = QComboBox()
        self.separate = QCheckBox(tr("Each book in its own file (in a folder)"))
        self.separate.toggled.connect(self._preview_clear)
        self._add_scope("book", [(tr("Books"), self.books), (tr("Chapter"), self.chapter), ("", self.separate)])
        # search
        self.query = QLineEdit(preset.get("query", ""))
        self.query.setPlaceholderText(tr("the words to search for, as on the Search page"))
        self._add_scope("search", [(tr("Search"), self.query)])
        # narrators
        self.narrator_road = QComboBox()
        for key, text in (("sunni", N_("Sunni")), ("shia", N_("Shia")), (None, N_("All"))):
            self.narrator_road.addItem(tr(text), key)
        self.narrator_text = QLineEdit()
        self.narrator_text.setPlaceholderText(tr("a name to narrow the list (empty: all of them)"))
        self._add_scope("narrators", [(tr("Tradition"), self.narrator_road), (tr("Name"), self.narrator_text)])
        # network: the chains of the books chosen, together
        self.net_books = _CheckList([(w["key"], f"{w['title']} ({w['key']})", w["tradition"]) for w in hadith_books],
                                    [w["key"] for w in hadith_books], groups=True)
        self._add_scope("network", [(tr("Books"), self.net_books)])
        # profile: one, several or all, each in its own file
        from isnady.core import profiles

        every_profile = profiles.all_profiles()
        self.profiles = _CheckList([(p["id"], p.get("name") or tr("Default"), "") for p in every_profile],
                                   [profiles.active()])
        self._add_scope("profile", [(tr("Profiles"), self.profiles)])
        # statistics: of a road or of one book
        self.stats_scope = QComboBox()
        self.stats_scope.addItem(tr("All Sunni books"), ("", "sunni"))
        self.stats_scope.addItem(tr("All Shia books"), ("", "shia"))
        for w in hadith_books:
            self.stats_scope.addItem(f"{w['title']} ({w['key']})", (w["key"], w["tradition"]))
        self._add_scope("statistics", [(tr("Books"), self.stats_scope)])
        for key in ("bookmarks", "settings", "backup"):
            self._add_scope(key, [])
        form.addRow("", self.scope)

        from isnady.core import language, search

        # every language with one click (Bayram, 2026-10-25: "tum diller sec diye birsey de yok!")
        chosen = language.content_languages()
        have = search.list_languages(conn) if conn is not None else []
        self.languages = _CheckList([(lang, tr(lang), "") for lang in have],
                                    [lang for lang in have if not chosen or lang in chosen])
        self.languages.list.setMaximumHeight(110)
        self.languages_label = QLabel(tr("Languages"))
        form.addRow(self.languages_label, self.languages)
        self.chains = QCheckBox(tr("With the chains (Arabic, Turkish, English)"))
        self.chains.setChecked(True)
        form.addRow("", self.chains)
        self.format = QComboBox()
        self.format.currentIndexChanged.connect(self._preview_clear)
        form.addRow(tr("Format"), self.format)
        box.addLayout(form)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText(tr("Preview: what the file will hold"))
        box.addWidget(self.preview, 1)
        self.progress = QProgressBar()
        self.progress.setFormat("%p%")
        self.progress.hide()
        box.addWidget(self.progress)
        self.status = _label("", "Caption")
        box.addWidget(self.status)
        row = QHBoxLayout()
        self.stop = QPushButton(tr("Stop"))
        self.stop.setObjectName("Quiet")
        self.stop.clicked.connect(self._stop_job)
        self.stop.hide()
        look = QPushButton(tr("Preview"))
        look.setObjectName("Quiet")
        look.clicked.connect(self._preview)
        self.go = QPushButton(tr("Export…"))
        self.go.setObjectName("Primary")
        self.go.clicked.connect(self._export)
        close = QPushButton(tr("Close"))
        close.setObjectName("Quiet")
        close.clicked.connect(self.reject)
        row.addWidget(look)
        row.addStretch(1)
        row.addWidget(self.stop)
        row.addWidget(close)
        row.addWidget(self.go)
        box.addLayout(row)

        self.kind.currentIndexChanged.connect(self._kind_changed)
        i = self.kind.findData(kind)
        self.kind.setCurrentIndex(max(0, i))
        self._fill_chapters()
        self._kind_changed()

    def _add_scope(self, key: str, rows: list) -> None:
        page = QWidget()
        lay = QFormLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        for text, widget in rows:
            lay.addRow(text, widget)
        self._scopes[key] = page
        self.scope.addWidget(page)

    def _fill_chapters(self) -> None:
        self.chapter.clear()
        keys = self.books.keys()
        several = len(keys) > 1
        self.chapter.setEnabled(len(keys) == 1)               # a chapter of one book only
        self.separate.setVisible(several)
        self.chapter.addItem(tr("The whole book") if not several else tr("Every chapter of every book chosen"), None)
        self._preview_clear()
        conn, key = self._conn_of(), (keys[0] if len(keys) == 1 else "")
        if conn is None or not key:
            return
        rows = conn.execute(
            """SELECT s.number, (SELECT st.title FROM section_titles st WHERE st.section_id = s.id LIMIT 1)
               FROM sections s JOIN collections c ON c.id = s.collection_id WHERE c.key = ? ORDER BY s.number""",
            (key,)).fetchall()
        for number, title in rows:
            self.chapter.addItem(f"{number}. {title or ''}".strip(), number)

    def _kind(self) -> str:
        return self.kind.currentData()

    def _kind_changed(self) -> None:
        kind = self._kind()
        self.help.setText(tr(_KIND_HELP[kind]))
        self.scope.setCurrentWidget(self._scopes[kind])
        document = kind in T.DOCUMENT_KINDS
        for w in (self.languages, self.languages_label, self.chains):
            w.setVisible(document)
        self.format.blockSignals(True)
        self.format.clear()
        for fmt in T.KINDS[kind]["export"]:
            self.format.addItem(tr(F.LABELS.get(fmt, fmt)), fmt)
        self.format.blockSignals(False)
        self._preview_clear()

    def _preview_clear(self) -> None:
        self.preview.clear()
        self.status.setText("")

    def _languages(self) -> list[str]:
        return self.languages.keys()

    def _arguments(self, preview: bool = False) -> dict:
        kind = self._kind()
        args = {"languages": self._languages() or None, "chains": self.chains.isChecked()}
        if kind == "hadith":
            args["refs"] = self.refs.text().split()
        elif kind == "book":
            keys = self.books.keys()
            if len(keys) == 1 or (preview and keys):
                args["book"] = keys[0]                  # the preview shows the first book chosen
                args["chapter"] = self.chapter.currentData() if len(keys) == 1 else None
                if preview and args["chapter"] is None and self.format.currentData() != "isnady-book":
                    rows = self._conn_of().execute(
                        """SELECT MIN(s.number) FROM sections s JOIN collections c ON c.id = s.collection_id
                           WHERE c.key = ?""", (keys[0],)).fetchone()
                    args["chapter"] = rows[0] if rows else None    # its first chapter, not the whole book
            else:
                args["books"] = ["all"] if self.books.every() else keys
                args["separate"] = self.separate.isChecked()
        elif kind == "search":
            args["query"] = self.query.text().strip()
        elif kind == "narrators":
            args["tradition"] = self.narrator_road.currentData()
            args["query"] = self.narrator_text.text().strip()
        elif kind == "network":
            args["books"] = None if self.net_books.every() else self.net_books.keys()
            args["tradition"] = None
        elif kind == "statistics":
            key, road = self.stats_scope.currentData()
            args["book"], args["tradition"] = key, road
        elif kind == "profile":
            args["profiles"] = self.profiles.keys()
            if preview:
                args["profiles"] = args["profiles"][:1]
        return args

    def _suggested(self) -> str:
        kind, fmt = self._kind(), self.format.currentData()
        a = self._arguments()
        if kind == "book" and a.get("books"):
            base = "isnady_books" if a["books"] == ["all"] else "isnady_" + "_".join(a["books"][:4])
        elif kind == "book":
            from isnady.core import books

            base = books.full_name(a.get("book") or "")
            base += f"_chapter_{a['chapter']}" if a.get("chapter") is not None else ""
        elif kind == "hadith":
            base = "isnady_" + "_".join(a["refs"])[:60].replace(":", "-")
        elif kind == "search":
            base = "isnady_search_" + a["query"][:40]
        else:
            base = f"isnady_{kind}"
        base = "".join(c if c.isalnum() or c in "-_." else "_" for c in base).strip("_") or "isnady"
        return base + T.suffix(fmt)

    def _pdf(self):
        from isnady.gui.pdf import html_to_pdf

        return html_to_pdf

    def _preview(self) -> None:
        fmt, kind = self.format.currentData(), self._kind()
        shown = {"xlsx": "md", "sqlite": "md", "docx": "txt", "epub": "txt", "pdf": "txt", "isnady-book": "json",
                 "isnady-profile": "json", "backup": "json", "gexf": "gexf"}.get(fmt, fmt)
        if shown not in T.KINDS[kind]["export"]:
            shown = next((f for f in ("md", "json", "txt", "csv") if f in T.KINDS[kind]["export"]), fmt)
        tmp = Path(tempfile.mkdtemp(prefix="isnady-preview-")) / ("preview" + T.suffix(shown))
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            args = self._arguments(preview=True)
            if kind == "hadith" and len(args.get("refs") or []) > 5:
                args["refs"] = args["refs"][:5]
            path = T.export(self._conn_of(), kind, shown, tmp, pdf=self._pdf(), **args)
            text = path.read_text(encoding="utf-8-sig", errors="replace") if path.is_file() else ""
            note = "" if shown == fmt else tr("(shown as {shown}; the file will be {fmt})", shown=tr(F.LABELS.get(shown, shown)),
                                              fmt=tr(F.LABELS.get(fmt, fmt)))
            self.preview.setPlainText((note + "\n\n" if note else "") + text[:20000]
                                      + ("\n…" if len(text) > 20000 else ""))
            self.status.setText("")
        except T.TransferError as exc:
            self.preview.setPlainText("")
            self.status.setText(str(exc))
        finally:
            QGuiApplication.restoreOverrideCursor()

    def _many_files(self, args: dict) -> bool:
        """Several things, each into its own file: a folder is asked for, not a file."""
        fmt = self.format.currentData()
        return bool(args.get("books") and (args.get("separate") or fmt == "isnady-book")) or \
            len(args.get("profiles") or []) > 1

    def _export(self) -> None:
        fmt, kind = self.format.currentData(), self._kind()
        args = self._arguments()
        if kind == "book" and not args.get("book") and not args.get("books"):
            self.status.setText(tr("Choose at least one book."))
            return
        if kind == "profile" and not args.get("profiles"):
            self.status.setText(tr("Choose at least one profile."))
            return
        if kind in T.DOCUMENT_KINDS and fmt != "isnady-book" and self.languages.list.count() and not self._languages():
            self.status.setText(tr("Choose at least one language."))
            return
        if self._many_files(args):
            folder = QFileDialog.getExistingDirectory(self, tr("Export: the folder for the files"),
                                                      os.path.expanduser("~"))
            if not folder:
                return
            name = os.path.join(folder, self._suggested().rsplit(".", 1)[0].split(".isnady-book")[0])
        else:
            start = os.path.join(os.path.expanduser("~"), self._suggested())
            ext = T.suffix(fmt).rsplit(".", 1)[-1]
            name, _f = QFileDialog.getSaveFileName(self, tr("Export"), start,
                                                   f"{tr(F.LABELS.get(fmt, fmt))} (*.{ext})")
            if not name:
                return
            if not name.endswith(T.suffix(fmt)) and not name.endswith(Path(T.suffix(fmt)).suffix):
                name += T.suffix(fmt)
        # every export in a thread of its own, with a progress bar and Stop, here and in the window's bottom bar
        # (EX3, Bayram 2026-10-24: "en azindan ayri bir threat olabilir, bunun disinda progress bar da olabilir"):
        # this dialog can be closed while it runs, and the window stays usable
        pdf = self._pdf() if fmt == "pdf" else None
        title = tr("Export") + f" · {Path(name).name}"

        def work(conn, say, tick):
            return T.export(conn, kind, fmt, name, pdf=pdf, progress=say, tick=tick, **args)

        jobs = getattr(self.parent(), "jobs", None)
        if jobs is not None:
            job = jobs.start(work, title)
        else:                                            # no window (a test): a job of the dialog's own
            from isnady.gui.jobs import Job

            job = Job(work, title)
            job.start()
        self._job = job
        job.progress.connect(self._said)
        job.ticked.connect(self._ticked)
        job.done.connect(self._done)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.stop.show()
        self.stop.setEnabled(True)
        self.go.setEnabled(False)
        self.status.setText(tr("Exporting… This window can be closed: the export goes on, its progress is shown at "
                               "the bottom of the main window."))

    def _said(self, message: str) -> None:
        self._last_said = message
        if self.progress.maximum() == 0:
            self.status.setText(message)

    def _ticked(self, done: int, total: int) -> None:
        from isnady.gui.jobs import describe

        if total <= 0 or self._job is None:
            return
        if self.progress.maximum() != total:
            self.progress.setRange(0, total)
        self.progress.setValue(done)
        _p, text = describe(self._job, done, total)
        book = (getattr(self, "_last_said", "") or "").split(" · ")[0]
        self.status.setText((book + " · " if book else "") + text)

    def _stop_job(self) -> None:
        if self._job is not None:
            self._job.stop()
            self.stop.setEnabled(False)
            self.status.setText(tr("Stopping…"))

    def _done(self, ok: bool, message: str) -> None:
        self.go.setEnabled(True)
        self.progress.hide()
        self.stop.hide()
        cancelled = bool(self._job is not None and getattr(self._job, "cancelled", False))
        self._job = None
        if not ok:
            self.status.setText(tr("Stopped; the unfinished file was removed.") if cancelled
                                else tr("Failed: ") + message)
            return
        self.status.setText(tr("Written: {path}", path=message))
        if not self.isVisible():
            return                                     # closed meanwhile: the bottom bar says it
        box = QMessageBox(QMessageBox.Icon.Information, tr("Export"), tr("Written: {path}", path=message), parent=self)
        show = box.addButton(tr("Show in folder"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() is show:
            where = Path(message)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(where if where.is_dir() else where.parent)))


class ImportDialog(QDialog):
    data_imported = Signal()          # a book came in: the window refreshes its pages
    settings_imported = Signal()      # settings or a backup came in: the window redraws

    def __init__(self, connection_getter, parent=None, kind: str = "bookmarks") -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Import"))
        self.resize(720, 520)
        self._conn_of = connection_getter
        self._job = None
        box = QVBoxLayout(self)
        box.setSpacing(10)
        box.addWidget(_label(tr("Import"), "CardTitle", False))
        form = QFormLayout()
        self.kind = QComboBox()
        for key, spec in T.KINDS.items():
            if spec["import"]:
                self.kind.addItem(tr(_KIND_TEXT[key]), key)
        form.addRow(tr("What"), self.kind)
        self.help = _label("", "Caption")
        form.addRow("", self.help)
        file_row = QHBoxLayout()
        self.file = QLineEdit()
        self.file.setPlaceholderText(tr("the file to import; several: Choose… and pick them all"))
        browse = QPushButton(tr("Choose…"))
        browse.setObjectName("Quiet")
        browse.clicked.connect(self._browse)
        file_row.addWidget(self.file, 1)
        file_row.addWidget(browse)
        form.addRow(tr("File"), file_row)
        self.detected = _label("", "Caption")
        form.addRow("", self.detected)
        self.replace = QCheckBox(tr("Replace what is there (otherwise added to it)"))
        form.addRow("", self.replace)
        self.folder = QLineEdit()
        self.folder.setPlaceholderText(tr("optional: a folder to put them in, e.g. Imported"))
        self.folder_label = QLabel(tr("Folder"))
        form.addRow(self.folder_label, self.folder)
        self.name = QLineEdit()
        self.name.setPlaceholderText(tr("optional: the new profile's name"))
        self.name_label = QLabel(tr("Name"))
        form.addRow(self.name_label, self.name)
        box.addLayout(form)
        self.status = _label("", "Caption")
        box.addWidget(self.status)
        box.addStretch(1)
        row = QHBoxLayout()
        close = QPushButton(tr("Close"))
        close.setObjectName("Quiet")
        close.clicked.connect(self.reject)
        self.go = QPushButton(tr("Import"))
        self.go.setObjectName("Primary")
        self.go.clicked.connect(self._import)
        row.addStretch(1)
        row.addWidget(close)
        row.addWidget(self.go)
        box.addLayout(row)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.file.textChanged.connect(self._detect)
        self.kind.setCurrentIndex(max(0, self.kind.findData(kind)))
        self._kind_changed()

    def _kind_changed(self) -> None:
        kind = self.kind.currentData()
        formats = ", ".join(F.LABELS.get(f, f) for f in T.KINDS[kind]["import"])
        extra = {"book": tr("A book comes in as a source of your own: an isnady book (.isnady-book.zip, its folder or "
                            "book.json) or an export of isnady's as JSON, JSON Lines, CSV or TSV."),
                 "bookmarks": tr("Added to your bookmarks; the ones you have stay."),
                 "settings": tr("The settings in the file are set; the others stay unless Replace is ticked."),
                 "profile": tr("Comes in as a new profile; yours stays as it is."),
                 "backup": tr("Your settings, place and bookmarks are replaced by the backup's.")}[kind]
        self.help.setText(tr("From: {formats}.", formats=formats) + " " + extra)
        self.replace.setVisible(kind in ("bookmarks", "settings"))
        for w in (self.folder, self.folder_label):
            w.setVisible(kind == "bookmarks")
        for w in (self.name, self.name_label):
            w.setVisible(kind == "profile")
        self._detect()

    def _browse(self) -> None:
        kind = self.kind.currentData()
        patterns = " ".join(f"*{T.suffix(f)}" for f in T.KINDS[kind]["import"])
        # several files at once (Bayram, 2026-10-24: "birden fazla … secilebilir olsun. Hepsi de olsun")
        names, _f = QFileDialog.getOpenFileNames(self, tr("Import"), os.path.expanduser("~"),
                                                 f"{tr('isnady files')} ({patterns} book.json);;{tr('All files')} (*)")
        if names:
            self.file.setText(" ; ".join(names))

    def _paths(self) -> list[str]:
        return [p.strip() for p in self.file.text().split(";") if p.strip()]

    def _detect(self) -> None:
        paths = self._paths()
        if not paths:
            self.detected.setText("")
            return
        kind = self.kind.currentData()
        formats = [T.guess_format(p, kind) for p in paths]
        wrong = [f"{Path(p).name} ({f})" for p, f in zip(paths, formats) if f not in T.KINDS[kind]["import"]]
        if wrong:
            self.detected.setText(tr("Not read for this: {files}; choose other files.", files=", ".join(wrong)))
        elif len(paths) == 1:
            self.detected.setText(tr("Read as {fmt}.", fmt=tr(F.LABELS.get(formats[0], formats[0]))))
        else:
            self.detected.setText(tr("{n} files, read as {formats}.", n=len(paths),
                                     formats=", ".join(dict.fromkeys(tr(F.LABELS.get(f, f)) for f in formats))))
        self.go.setEnabled(not wrong)

    def _import(self) -> None:
        kind, paths = self.kind.currentData(), self._paths()
        if not paths:
            return
        if kind == "backup" and QMessageBox.question(
                self, tr("Import"), tr("Your settings, place and bookmarks will be replaced by the backup's. Go on?")) \
                != QMessageBox.StandardButton.Yes:
            return
        options = {"replace": self.replace.isChecked() and kind in ("bookmarks", "settings"),
                   "folder": self.folder.text().strip() if kind == "bookmarks" else "",
                   "name": self.name.text().strip() if kind == "profile" else ""}
        self.go.setEnabled(False)
        self.status.setText(tr("Importing…"))
        self._kind_running = kind
        def work(conn, say):
            said = []
            for n, path in enumerate(paths, 1):
                prefix = f"{n}/{len(paths)} · {Path(path).name}: " if len(paths) > 1 else ""
                try:
                    said.append(prefix + T.import_file(conn, kind, path, progress=lambda m: say(prefix + m), **options))
                except T.TransferError as exc:
                    if len(paths) == 1:
                        raise
                    said.append(prefix + tr("Failed: ") + str(exc))
            return "\n".join(said)

        self._job = _Job(work)
        self._job.progress.connect(self.status.setText)
        self._job.done.connect(self._done)
        self._job.start()

    def _done(self, ok: bool, message: str) -> None:
        self.go.setEnabled(True)
        self.status.setText(message if ok else tr("Failed: ") + message)
        if not ok:
            return
        if self._kind_running == "book":
            self.data_imported.emit()
        elif self._kind_running in ("settings", "backup"):
            self.settings_imported.emit()
        QMessageBox.information(self, tr("Import"), message)
