"""Settings → Data sources: import the built-in sources with one click, and add your own.

Imports run in a background thread with their own database connection, so the
window stays responsive; the shared pipeline (isnady.core.imports) indexes,
reads chains and identifies narrators afterwards, exactly as `iy catalog import`.
"""

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from isnady.core import catalog
from isnady.data import db
from isnady.data.fetch import Auth, ResourceError
from isnady.data.importers import list_importers
from isnady.gui import theme
from isnady.gui.widgets import FlowLayout


# A QThread must outlive the moment it reports "done": it only stops after run() returns. Dropping the
# last Python reference earlier deletes it while running ("QThread: Destroyed while thread is still
# running" -> abort). Workers stay here until Qt's own finished signal (same lesson as VenvStudio 1.6.61).
_LIVE_WORKERS: set = set()


class Worker(QThread):
    progress = Signal(str)
    done = Signal(bool, str)

    def __init__(self, action: str, entry: catalog.Entry | None, languages=None, auth=None) -> None:
        super().__init__()
        self.action, self.entry, self.languages, self.auth = action, entry, languages, auth

    def run(self) -> None:
        conn = db.connect()
        try:
            if self.action == "import_all":
                imported, failed, narrators = catalog.import_all(conn, self.languages, self.progress.emit)
                message = f"Imported {len(imported)} of {len(imported) + len(failed)} built-in sources"
                if narrators.get("links"):
                    message += (f"; {narrators['identified']:,} of {narrators['links']:,} narrators in chains "
                                f"identified ({100 * narrators['identified'] / narrators['links']:.1f}%)")
                if failed:
                    message += ". Failed: " + "; ".join(f"{label} ({why})" for label, why in failed)
                self.done.emit(not failed, message + ".")
                return
            if self.action == "remove":
                catalog.remove_entry(conn, self.entry)
                self.done.emit(True, f"Removed {self.entry.title}.")
                return
            report, narrators = catalog.import_entry(conn, self.entry, self.languages, self.auth, self.progress.emit)
            message = f"Imported {self.entry.title}: {report.texts:,} " + ("narrators" if self.entry.kind == "rijal" else "texts")
            if narrators.get("links"):
                message += (f"; {narrators['identified']:,} of {narrators['links']:,} narrators in chains identified "
                            f"({100 * narrators['identified'] / narrators['links']:.1f}%)")
            self.done.emit(True, message + ".")
        except (ResourceError, KeyError, ValueError) as exc:
            self.done.emit(False, str(exc.args[0] if exc.args else exc))
        except Exception as exc:  # the dialog must never be left waiting
            self.done.emit(False, f"{type(exc).__name__}: {exc}")
        finally:
            conn.close()


class AddSourceDialog(QDialog):
    """A user source: title, format, file or URL, licence, kind of authentication (no secrets)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add a source")
        self.resize(620, 300)
        self.title = QLineEdit()
        self.format = QComboBox()
        for imp in list_importers():
            self.format.addItem(imp.title, imp.format_id)
        self.location = QLineEdit()
        self.location.setPlaceholderText("https://… or a file on this computer")
        browse = QPushButton("Browse…")
        browse.setObjectName("Quiet")
        browse.clicked.connect(self._browse)
        where = QHBoxLayout()
        where.addWidget(self.location, 1)
        where.addWidget(browse)
        self.book = QLineEdit()
        self.book.setPlaceholderText("optional, for index files: bukhari, muslim …")
        self.license = QLineEdit()
        self.license.setPlaceholderText("e.g. CC-BY-4.0; empty = not redistributed (tier C)")
        self.auth = QComboBox()
        for kind, label in (("none", "None"), ("basic", "Username and password"), ("bearer", "Bearer token"),
                            ("apikey", "API key")):
            self.auth.addItem(label, kind)
        self.key_name = QLineEdit()
        self.key_name.setPlaceholderText("header name for an API key, e.g. X-API-Key")
        form = QFormLayout()
        form.addRow("Title", self.title)
        form.addRow("Format", self.format)
        form.addRow("File or URL", where)
        form.addRow("Book", self.book)
        form.addRow("Licence", self.license)
        form.addRow("Authentication", self.auth)
        form.addRow("API key header", self.key_name)
        note = QLabel("Passwords, tokens and keys are asked for when you import and are never stored.")
        note.setObjectName("Caption")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a source file")
        if path:
            self.location.setText(path)

    def values(self) -> dict:
        return {"title": self.title.text(), "format_id": self.format.currentData(), "location": self.location.text(),
                "license": self.license.text().strip() or None, "auth_kind": self.auth.currentData(),
                "key_name": self.key_name.text().strip() or None, "book": self.book.text().strip() or None}


class SourcesPage(QWidget):
    data_imported = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._worker: Worker | None = None
        self._buttons: list[QPushButton] = []
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(6, 12, 12, 12)
        self.box.setSpacing(10)
        self.status = QLabel("")
        self.status.setObjectName("Caption")
        self.status.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setMaximumHeight(6)
        self.bar.setTextVisible(False)
        self.bar.hide()
        self.refresh()

    # ------------------------------------------------------------ building
    def _clear(self) -> None:
        while self.box.count():
            item = self.box.takeAt(0)
            w = item.widget()
            if w is not None and w not in (self.status, self.bar):
                w.setParent(None)
                w.deleteLater()

    def refresh(self) -> None:
        self._clear()
        self._buttons = []
        conn = db.connect()
        try:
            intro = QLabel("Import sources with one click. Built-in sources are defined by isnady; your own "
                           "sources (User Resources) stay on this computer. The same list works from the "
                           "command line: iy catalog list.")
            intro.setObjectName("Lead")
            intro.setWordWrap(True)
            self.box.addWidget(intro)
            self.box.addWidget(self._folder_card())
            self.box.addWidget(self.bar)
            self.box.addWidget(self.status)
            for heading, entries in (("Built-in sources", catalog.builtin_entries()),
                                     ("Your sources", catalog.user_entries())):
                title = QLabel(heading)
                title.setObjectName("CardTitle")
                title.setFont(theme.reading_font(15, bold=True))
                head = QHBoxLayout()
                head.addWidget(title)
                head.addStretch(1)
                if heading == "Built-in sources":
                    all_button = QPushButton("Import all")
                    all_button.setObjectName("Primary")
                    all_button.setToolTip("Every built-in source, each in the languages ticked on its card; the "
                                          "search index, chains and narrators are brought up to date once, at the end")
                    all_button.clicked.connect(self._import_all)
                    self._buttons.append(all_button)
                    head.addWidget(all_button)
                self.box.addLayout(head)
                self._lang_checks = getattr(self, "_lang_checks", {}) if heading != "Built-in sources" else {}
                for entry in entries:
                    self.box.addWidget(self._card(conn, entry))
                if heading == "Your sources":
                    if not entries:
                        none = QLabel("None yet.")
                        none.setObjectName("Caption")
                        self.box.addWidget(none)
                    add = QPushButton("Add a source…")
                    add.setObjectName("Quiet")
                    add.clicked.connect(self._add)
                    self._buttons.append(add)
                    row = QHBoxLayout()
                    row.addWidget(add)
                    row.addStretch(1)
                    self.box.addLayout(row)
            self.box.addStretch(1)
        finally:
            conn.close()
        self._set_busy(self._worker is not None)

    def _card(self, conn, entry: catalog.Entry) -> QFrame:
        st = catalog.status(conn, entry)
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 12, 18, 12)
        box.setSpacing(6)
        head = QHBoxLayout()
        name = QLabel(entry.title)
        name.setObjectName("CardTitle")
        name.setFont(theme.reading_font(13.5, bold=True))
        state = QLabel(self._state_text(entry, st))
        state.setObjectName("Caption")
        head.addWidget(name)
        head.addStretch(1)
        head.addWidget(state)
        box.addLayout(head)
        desc = QLabel(entry.description + (f"  ·  {entry.location}" if not entry.builtin else ""))
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        box.addWidget(desc)

        checks = []
        if entry.builtin and entry.book:
            langs = QWidget()
            flow = FlowLayout(langs, spacing=10)
            chosen = st["languages"] or [catalog.language_label(c) for c in catalog.DEFAULT_LANGUAGES]
            for code in entry.languages:
                check = QCheckBox(catalog.language_label(code))
                check.setChecked(catalog.language_label(code) in chosen)
                check.setProperty("code", code)
                flow.addWidget(check)
                checks.append(check)
            box.addWidget(langs)
            self._lang_checks[entry.id] = checks

        row = QHBoxLayout()
        row.addStretch(1)
        imp = QPushButton("Update" if st["imported"] else "Import")
        imp.setObjectName("Primary" if not st["imported"] else "Quiet")
        imp.clicked.connect(lambda _c=False, e=entry, cs=checks: self._import(e, cs))
        row.addWidget(imp)
        self._buttons.append(imp)
        if st["imported"]:
            rem = QPushButton("Remove data")
            rem.setObjectName("Quiet")
            rem.clicked.connect(lambda _c=False, e=entry: self._remove(e))
            row.addWidget(rem)
            self._buttons.append(rem)
        if not entry.builtin:
            forget = QPushButton("Delete from list")
            forget.setObjectName("Quiet")
            forget.clicked.connect(lambda _c=False, e=entry: self._delete(e))
            row.addWidget(forget)
            self._buttons.append(forget)
        box.addLayout(row)
        return card

    @staticmethod
    def _state_text(entry, st) -> str:
        if not st["imported"]:
            return "Not imported"
        what = "narrators" if entry.kind == "rijal" else ("hadith" if entry.book else "texts")
        langs = f" · {', '.join(st['languages'])}" if st["languages"] else ""
        when = f" · {st['when'][:10]}" if st.get("when") else ""
        tier = f" · tier {st['tier']}" if st.get("tier") else ""
        return f"Imported: {st['count']:,} {what}{langs}{when}{tier}"

    # ------------------------------------------------------------ actions
    def _set_busy(self, busy: bool) -> None:
        for b in self._buttons:
            b.setEnabled(not busy)
        self.bar.setVisible(busy)

    def _start(self, worker: Worker, first_message: str) -> None:
        self._worker = worker
        _LIVE_WORKERS.add(worker)
        worker.finished.connect(lambda w=worker: (_LIVE_WORKERS.discard(w), w.deleteLater()))
        self.status.setText(first_message)
        self._set_busy(True)
        worker.progress.connect(self.status.setText)
        worker.done.connect(self._finished)
        worker.start()

    def _finished(self, ok: bool, message: str) -> None:
        self._worker = None
        self.refresh()
        self.status.setText(("" if ok else "Failed: ") + message)
        if ok:
            self.data_imported.emit()

    def _ask_auth(self, entry: catalog.Entry) -> Auth | None:
        if entry.auth_kind == "none":
            return Auth()
        if entry.auth_kind == "basic":
            user, ok = QInputDialog.getText(self, entry.title, "Username:")
            if not ok:
                return None
            password, ok = QInputDialog.getText(self, entry.title, "Password:", QLineEdit.EchoMode.Password)
            return Auth(kind="basic", username=user, password=password) if ok else None
        secret, ok = QInputDialog.getText(self, entry.title, "Token:" if entry.auth_kind == "bearer" else "API key:",
                                          QLineEdit.EchoMode.Password)
        return Auth(kind=entry.auth_kind, token=secret, key_name=entry.key_name, key_in=entry.key_in) if ok else None

    def _folder_card(self) -> QFrame:
        from isnady.data import paths

        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 12, 18, 12)
        box.setSpacing(6)
        head = QHBoxLayout()
        title = QLabel("Data folder")
        title.setObjectName("CardTitle")
        title.setFont(theme.reading_font(13.5, bold=True))
        how = {"default": "the default for this system", "chosen": "chosen by you",
               "environment": "set by the ISNADY_DATA_DIR environment variable"}[paths.data_dir_source()]
        state = QLabel(how)
        state.setObjectName("Caption")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(state)
        box.addLayout(head)
        where = QLabel(str(paths.data_dir()))
        where.setObjectName("Lead")
        where.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        where.setWordWrap(True)
        box.addWidget(where)
        note = QLabel("The database, your settings and your own sources live here. A new folder is used from the "
                      "next start of isnady.")
        note.setObjectName("Caption")
        note.setWordWrap(True)
        box.addWidget(note)
        row = QHBoxLayout()
        row.addStretch(1)
        for label, slot in (("Open", self._open_folder), ("Change…", self._change_folder),
                            ("Use default", self._default_folder)):
            b = QPushButton(label)
            b.setObjectName("Quiet")
            b.clicked.connect(slot)
            if label != "Open" and paths.data_dir_source() == "environment":
                b.setEnabled(False)
            if label == "Use default" and paths.data_dir_source() == "default":
                b.setEnabled(False)
            row.addWidget(b)
            if label != "Open":
                self._buttons.append(b)
        box.addLayout(row)
        return card

    def _open_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from isnady.data import paths

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.data_dir())))

    def _relocate(self, target, mode: str) -> None:
        from isnady.data import paths

        try:
            new = paths.relocate(target, mode)
        except paths.RelocateError as exc:
            QMessageBox.warning(self, "Data folder", str(exc))
            return
        answer = QMessageBox.question(
            self, "Data folder",
            f"isnady will use\n{new}\nfrom its next start"
            + ("; your data was copied there and the old folder is kept." if mode == "copy" else ".")
            + "\n\nQuit isnady now?")
        self.refresh()
        if answer == QMessageBox.StandardButton.Yes:
            from PySide6.QtWidgets import QApplication

            QApplication.quit()

    def _change_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder for isnady's data")
        if not folder:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Data folder")
        box.setText(f"Use {folder} for isnady's data?")
        copy = box.addButton("Copy my data there", QMessageBox.ButtonRole.AcceptRole)
        as_is = box.addButton("Use the folder as it is", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() is copy:
            self._relocate(folder, "copy")
        elif box.clickedButton() is as_is:
            self._relocate(folder, "as-is")

    def _default_folder(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Data folder")
        box.setText("Go back to the default folder for this system?")
        copy = box.addButton("Copy my data there", QMessageBox.ButtonRole.AcceptRole)
        as_is = box.addButton("Use it as it is", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() is copy:
            self._relocate(None, "copy")
        elif box.clickedButton() is as_is:
            self._relocate(None, "as-is")

    def _import_all(self) -> None:
        languages = {}
        for entry_id, checks in getattr(self, "_lang_checks", {}).items():
            chosen = [c.property("code") for c in checks if c.isChecked()]
            if chosen:
                languages[entry_id] = chosen
        self._start(Worker("import_all", None, languages), "Importing every built-in source…")

    def _import(self, entry: catalog.Entry, checks: list) -> None:
        languages = [c.property("code") for c in checks if c.isChecked()] or None
        if checks and not languages:
            self.status.setText("Choose at least one language.")
            return
        auth = self._ask_auth(entry)
        if auth is None:
            return
        self._start(Worker("import", entry, languages, auth), f"Importing {entry.title}…")

    def _remove(self, entry: catalog.Entry) -> None:
        answer = QMessageBox.question(self, "Remove data", f"Remove everything imported from {entry.title}?")
        if answer == QMessageBox.StandardButton.Yes:
            self._start(Worker("remove", entry), f"Removing {entry.title}…")

    def _delete(self, entry: catalog.Entry) -> None:
        catalog.delete_user_entry(entry.id)
        self.refresh()

    def _add(self) -> None:
        dialog = AddSourceDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            catalog.add_user_entry(**dialog.values())
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, "Add a source", str(exc.args[0] if exc.args else exc))
            return
        self.refresh()

    def busy(self) -> bool:
        return self._worker is not None
