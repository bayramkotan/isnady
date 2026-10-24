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
              "profile": N_("Profile"), "backup": N_("Everything of mine (backup)")}
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
}


def _label(text: str, name: str = "", wrap: bool = True) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


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
        # book
        self.book = QComboBox()
        for w in book_list:
            self.book.addItem(f"{w['title']} ({w['key']})", w["key"])
        if preset.get("book"):
            i = self.book.findData(preset["book"])
            if i >= 0:
                self.book.setCurrentIndex(i)
        self.chapter = QComboBox()
        self.book.currentIndexChanged.connect(self._fill_chapters)
        self._add_scope("book", [(tr("Book"), self.book), (tr("Chapter"), self.chapter)])
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
        # network
        self.net_book = QComboBox()
        self.net_book.addItem(tr("All books"), "")
        for w in book_list:
            if w.get("kind") == "hadith":
                self.net_book.addItem(f"{w['title']} ({w['key']})", w["key"])
        self._add_scope("network", [(tr("Book"), self.net_book)])
        # profile
        from isnady.core import profiles

        self.profile = QComboBox()
        for p in profiles.all_profiles():
            self.profile.addItem(p.get("name") or p["id"], p["id"])
        self._add_scope("profile", [(tr("Profile"), self.profile)])
        for key in ("bookmarks", "settings", "backup"):
            self._add_scope(key, [])
        form.addRow("", self.scope)

        self.languages = QListWidget()
        self.languages.setMaximumHeight(120)
        from isnady.core import language, search

        chosen = language.content_languages()
        for lang in (search.list_languages(conn) if conn is not None else []):
            item = QListWidgetItem(tr(lang))
            item.setData(Qt.ItemDataRole.UserRole, lang)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if not chosen or lang in chosen else Qt.CheckState.Unchecked)
            self.languages.addItem(item)
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
        self.status = _label("", "Caption")
        box.addWidget(self.status)
        row = QHBoxLayout()
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
        self.chapter.addItem(tr("The whole book"), None)
        conn, key = self._conn_of(), self.book.currentData()
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
        return [self.languages.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.languages.count())
                if self.languages.item(i).checkState() == Qt.CheckState.Checked]

    def _arguments(self, preview: bool = False) -> dict:
        kind = self._kind()
        args = {"languages": self._languages() or None, "chains": self.chains.isChecked()}
        if kind == "hadith":
            args["refs"] = self.refs.text().split()
        elif kind == "book":
            args["book"] = self.book.currentData() or ""
            args["chapter"] = self.chapter.currentData()
            if preview and args["chapter"] is None and self.format.currentData() != "isnady-book":
                first = self.chapter.itemData(1) if self.chapter.count() > 1 else None
                args["chapter"] = first                 # a preview of the first chapter, not of the whole book
        elif kind == "search":
            args["query"] = self.query.text().strip()
        elif kind == "narrators":
            args["tradition"] = self.narrator_road.currentData()
            args["query"] = self.narrator_text.text().strip()
        elif kind == "network":
            args["book"] = self.net_book.currentData() or ""
            args["tradition"] = None
        elif kind == "profile":
            args["profile"] = self.profile.currentData()
        return args

    def _suggested(self) -> str:
        kind, fmt = self._kind(), self.format.currentData()
        a = self._arguments()
        if kind == "book":
            from isnady.core import books

            base = books.full_name(a["book"])
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
                                              fmt=F.LABELS.get(fmt))
            self.preview.setPlainText((note + "\n\n" if note else "") + text[:20000]
                                      + ("\n…" if len(text) > 20000 else ""))
            self.status.setText("")
        except T.TransferError as exc:
            self.preview.setPlainText("")
            self.status.setText(str(exc))
        finally:
            QGuiApplication.restoreOverrideCursor()

    def _export(self) -> None:
        fmt, kind = self.format.currentData(), self._kind()
        start = os.path.join(os.path.expanduser("~"), self._suggested())
        ext = T.suffix(fmt).rsplit(".", 1)[-1]
        name, _f = QFileDialog.getSaveFileName(self, tr("Export"), start, f"{tr(F.LABELS.get(fmt, fmt))} (*.{ext})")
        if not name:
            return
        if not name.endswith(T.suffix(fmt)) and not name.endswith(Path(T.suffix(fmt)).suffix):
            name += T.suffix(fmt)
        args = self._arguments()
        if fmt == "pdf":                     # Qt draws a PDF in the window's own thread
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                path = T.export(self._conn_of(), kind, fmt, name, pdf=self._pdf(),
                                progress=lambda m: self.status.setText(m), **args)
                self._done(True, str(path))
            except (T.TransferError, OSError) as exc:
                self._done(False, str(exc))
            finally:
                QGuiApplication.restoreOverrideCursor()
            return
        self.go.setEnabled(False)
        self.status.setText(tr("Exporting…"))
        self._job = _Job(lambda conn, say: T.export(conn, kind, fmt, name, progress=say, **args))
        self._job.progress.connect(self.status.setText)
        self._job.done.connect(self._done)
        self._job.start()

    def _done(self, ok: bool, message: str) -> None:
        self.go.setEnabled(True)
        if not ok:
            self.status.setText(tr("Failed: ") + message)
            return
        self.status.setText(tr("Written: {path}", path=message))
        box = QMessageBox(QMessageBox.Icon.Information, tr("Export"), tr("Written: {path}", path=message), parent=self)
        show = box.addButton(tr("Show in folder"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() is show:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(message).parent)))


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
        self.file.setPlaceholderText(tr("the file to import"))
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
        name, _f = QFileDialog.getOpenFileName(self, tr("Import"), os.path.expanduser("~"),
                                               f"{tr('isnady files')} ({patterns} book.json);;{tr('All files')} (*)")
        if name:
            self.file.setText(name)

    def _detect(self) -> None:
        path = self.file.text().strip()
        if not path:
            self.detected.setText("")
            return
        fmt = T.guess_format(path, self.kind.currentData())
        ok = fmt in T.KINDS[self.kind.currentData()]["import"]
        self.detected.setText((tr("Read as {fmt}.", fmt=tr(F.LABELS.get(fmt, fmt))) if ok
                               else tr("{fmt} is not read for this; choose another file.", fmt=fmt)))
        self.go.setEnabled(ok)

    def _import(self) -> None:
        kind, path = self.kind.currentData(), self.file.text().strip()
        if not path:
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
        self._job = _Job(lambda conn, say: T.import_file(conn, kind, path, progress=say, **options))
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
