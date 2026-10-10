"""Settings → Data sources: choose a repository, import its sources with one click, and add your own.

The REPOSITORY is chosen at the top (core.repositories): isnady's own (bayramkotan/isnady-data) by default, which lists
every Sunni and Shia source; the datasets others publish as options; and any repository the user adds. Its sources
are listed below it, Sunni hadith, Shia hadith and rijal apart.

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

from isnady.core import catalog, repositories
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
                message = f"Imported {len(imported)} of {len(imported) + len(failed)} sources of the repository"
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
    def _clear(self, layout=None) -> None:
        """Everything on the page goes, rows of buttons and titles (inside layouts) included."""
        layout = layout or self.box
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None and w not in (self.status, self.bar):
                w.setParent(None)
                w.deleteLater()
            elif item.layout() is not None:
                self._clear(item.layout())
                item.layout().deleteLater()

    def refresh(self) -> None:
        self._clear()
        self._buttons = []
        self._lang_checks = {}
        conn = db.connect()
        try:
            intro = QLabel("isnady reads its sources from a REPOSITORY: its own by default, which lists every Sunni "
                           "and Shia collection and rijal work it can read. Choose another, or add your own, and "
                           "import with one click. Your own files (User Resources) stay on this computer. The same "
                           "from the command line: iy repo, iy catalog.")
            intro.setObjectName("Lead")
            intro.setWordWrap(True)
            self.box.addWidget(intro)
            self.box.addWidget(self._repo_card())
            self.box.addWidget(self.bar)
            self.box.addWidget(self.status)
            try:
                entries = catalog.builtin_entries()
            except Exception as exc:          # a broken user repository must not empty the page
                entries = []
                self.status.setText(f"The repository cannot be read: {exc}")
            head = QHBoxLayout()
            title = QLabel(f"Sources of {repositories.selected().name}")
            title.setObjectName("CardTitle")
            title.setFont(theme.reading_font(15, bold=True))
            head.addWidget(title)
            head.addStretch(1)
            all_button = QPushButton("Import all")
            all_button.setObjectName("Primary")
            all_button.setToolTip("Every source of this repository, each in the languages ticked on its card; the "
                                  "search index, chains and narrators are brought up to date once, at the end")
            all_button.clicked.connect(self._import_all)
            all_button.setProperty("allowed", bool(entries))
            self._buttons.append(all_button)
            head.addWidget(all_button)
            self.box.addLayout(head)
            groups = [("Sunni hadith collections", [e for e in entries if e.kind == "hadith" and e.tradition != "shia"]),
                      ("Shia hadith collections", [e for e in entries if e.kind == "hadith" and e.tradition == "shia"]),
                      ("Narrators (rijal)", [e for e in entries if e.kind == "rijal"])]
            for heading, group in groups:
                if not group:
                    continue
                sub = QLabel(f"{heading}  ·  {len(group)}")
                sub.setObjectName("FilterTitle")
                self.box.addWidget(sub)
                for entry in group:
                    self.box.addWidget(self._card(conn, entry))

            title = QLabel("Your sources")
            title.setObjectName("CardTitle")
            title.setFont(theme.reading_font(15, bold=True))
            self.box.addWidget(title)
            mine = catalog.user_entries()
            for entry in mine:
                self.box.addWidget(self._card(conn, entry))
            if not mine:
                none = QLabel("None yet: a file or a URL of your own, in any format isnady reads.")
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
            self.box.addWidget(self._folder_card())
            self.box.addStretch(1)
        finally:
            conn.close()
        self._set_busy(self._worker is not None)

    def _repo_card(self) -> QFrame:
        """The repository: chosen from the list (the default first), with where its catalog came from."""
        repo = repositories.selected()
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 12, 18, 12)
        box.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel("Repository")
        title.setObjectName("CardTitle")
        title.setFont(theme.reading_font(13.5, bold=True))
        head.addWidget(title)
        self.repo_combo = QComboBox()
        self.repo_combo.setObjectName("FilterCombo")
        self.repo_combo.setMinimumWidth(360)
        for r in repositories.all_repositories():
            label = r.name + ("" if r.builtin else "  (added by you)")
            self.repo_combo.addItem(label, r.id)
        self.repo_combo.setCurrentIndex(max(0, self.repo_combo.findData(repo.id)))
        self.repo_combo.currentIndexChanged.connect(self._choose_repo)
        head.addWidget(self.repo_combo, 1)
        box.addLayout(head)
        desc = QLabel(repo.description)
        desc.setObjectName("Lead")
        desc.setWordWrap(True)
        box.addWidget(desc)
        try:
            _cat, where = repositories.catalog(repo)
            where = "shipped-own" if where == "shipped" and not repo.url else where
            how = {"network": "Catalog read from the repository just now.",
                   "shipped-own": "This dataset publishes no catalog of its own; isnady ships one for it.",
                   "saved": "Catalog read from the repository in the last day (Refresh reads it again).",
                   "shipped": ("The repository cannot be reached now, so the catalog shipped with isnady is used; "
                               "each source is read from the repository, or from its origin when the repository "
                               "has no copy.")}[where]
        except Exception as exc:
            how = f"The catalog cannot be read: {exc}"
        links = [f"<a href='{repo.homepage}'>{repo.homepage}</a>"] if repo.homepage else []
        note = QLabel(" · ".join(links + [how]))
        note.setObjectName("Caption")
        note.setWordWrap(True)
        note.setTextFormat(Qt.TextFormat.RichText)
        note.setOpenExternalLinks(True)
        box.addWidget(note)
        row = QHBoxLayout()
        row.addStretch(1)
        for label, slot, ok in (("Refresh", self._refresh_repo, True),
                                ("A folder on this computer…", self._add_folder_repo, True),
                                ("Add a repository…", self._add_repo, True),
                                ("Remove from list", self._remove_repo, not repo.builtin),
                                ("Use the default", lambda: self._use_repo(repositories.DEFAULT_ID), not repo.default)):
            b = QPushButton(label)
            b.setObjectName("Quiet")
            b.clicked.connect(slot)
            b.setProperty("allowed", ok)
            row.addWidget(b)
            self._buttons.append(b)
        box.addLayout(row)
        return card

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
        head.addWidget(name)
        if entry.title_ar:
            ar = QLabel(entry.title_ar)
            ar.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                             f"{theme.font_css(theme.script_font('arabic', factor=0.85))}")
            head.addWidget(ar)
        head.addStretch(1)
        state = QLabel(self._state_text(entry, st))
        state.setObjectName("Caption")
        head.addWidget(state)
        box.addLayout(head)
        if entry.builtin:
            tags = QHBoxLayout()
            tags.setSpacing(8)
            ours = entry.repo == repositories.DEFAULT_ID
            items = [("Shia" if entry.tradition == "shia" else "Sunni", "TagGold" if entry.tradition == "shia" else "Tag",
                      "The tradition of the collection: Shia books are kept apart from Sunni ones, and their grades "
                      "and narrators are read in their own terms."),
                     (entry.license or "licence not stated", "TagMuted",
                      "May be shared further (tier A/B)" if db.tier_for_license(entry.license) in "AB"
                      else "No licence allowing it to be shared further: for this computer (tier C)")]
            if not ours and entry.origin_url:
                items.append(("read from its publisher", "TagMuted",
                              f"{entry.origin_name}\n{entry.origin_url}" if entry.origin_url else ""))
            for text, name_, tip in items:
                tag = QLabel(text)
                tag.setObjectName(name_)
                tag.setToolTip(tip)
                tags.addWidget(tag)
            if entry.hadith:
                count = QLabel(f"{entry.hadith:,} hadith")
                count.setObjectName("Caption")
                tags.addWidget(count)
            tags.addStretch(1)
            if entry.origin_url:
                link = QLabel(f"<a href='{entry.origin_url}'>{entry.origin_name or entry.origin_url}</a>")
                link.setObjectName("Caption")
                link.setTextFormat(Qt.TextFormat.RichText)
                link.setOpenExternalLinks(True)
                tags.addWidget(link)
            box.addLayout(tags)
        desc = QLabel(entry.description + (f"  ·  {entry.location}" if not entry.builtin else ""))
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        box.addWidget(desc)

        checks = []
        if entry.builtin and entry.book and entry.languages:
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
            b.setEnabled(not busy and b.property("allowed") is not False)
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
                      "next start of isnady. A ready database (isnady.db, or the isnady-db zip of isnady-data) can be "
                      "taken from a file on this computer instead of importing book by book.")
        note.setObjectName("Caption")
        note.setWordWrap(True)
        box.addWidget(note)
        row = QHBoxLayout()
        row.addStretch(1)
        for label, slot in (("Open", self._open_folder), ("Change…", self._change_folder),
                            ("Use default", self._default_folder), ("Use a ready database…", self._use_ready_database)):
            b = QPushButton(label)
            b.setObjectName("Quiet")
            b.clicked.connect(slot)
            if label in ("Change…", "Use default") and paths.data_dir_source() == "environment":
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

    def _choose_repo(self, _i: int) -> None:
        self._use_repo(self.repo_combo.currentData())

    def _use_repo(self, repo_id: str) -> None:
        try:
            repositories.select(repo_id)
        except KeyError as exc:
            QMessageBox.warning(self, "Repository", str(exc.args[0]))
        self.refresh()

    def _refresh_repo(self) -> None:
        repo = repositories.selected()
        try:
            _cat, where = repositories.catalog(repo, refresh=True)
            self.refresh()
            self.status.setText("Catalog read again." if where == "network" else
                                "The repository cannot be reached; the saved or shipped catalog is used.")
        except Exception as exc:
            self.status.setText(f"Failed: {exc}")

    def _add_repo(self) -> None:
        text, ok = QInputDialog.getText(
            self, "Add a repository",
            "The address of a repository with an isnady catalog (catalog.json):\n"
            "  a GitHub repository   https://github.com/owner/name\n"
            "  a Hugging Face dataset   https://huggingface.co/datasets/owner/name\n"
            "  a catalog URL, or a folder on this computer")
        if not ok or not text.strip():
            return
        try:
            repo = repositories.add_repository(text.strip())
        except (ResourceError, ValueError) as exc:
            QMessageBox.warning(self, "Add a repository", str(exc.args[0] if exc.args else exc))
            return
        repositories.select(repo.id)
        self.refresh()
        self.status.setText(f"Added {repo.name}; it is the repository now.")

    def _add_folder_repo(self) -> None:
        """A repository on this computer: a copy of isnady-data (git clone, a USB stick, a shared folder) or any
        folder with a catalog.json — read without the network."""
        folder = QFileDialog.getExistingDirectory(self, "A folder with a catalog.json (e.g. your copy of isnady-data)")
        if not folder:
            return
        try:
            repo = repositories.add_repository(folder)
        except (ResourceError, ValueError) as exc:
            QMessageBox.warning(self, "A folder on this computer", str(exc.args[0] if exc.args else exc))
            return
        repositories.select(repo.id)
        self.refresh()
        self.status.setText(f"Added {repo.name} ({folder}); it is the repository now, read from this computer.")

    def _use_ready_database(self) -> None:
        from isnady.data import ready

        path, _f = QFileDialog.getOpenFileName(self, "A ready isnady database",
                                               "", "isnady database (isnady-db-*.zip isnady*.db *.zip *.db)")
        if not path:
            return
        try:
            info = ready.stage(path)
        except ready.ReadyError as exc:
            QMessageBox.warning(self, "Ready database", str(exc))
            return
        answer = QMessageBox.question(
            self, "Ready database",
            f"{info['books']} books, {info['hadith']:,} hadith. It takes the place of your database at the next "
            "start of isnady; your database is kept beside it as isnady.<date>.bak.db.\n\nQuit isnady now?")
        self.status.setText("A ready database is waiting; it is used from the next start.")
        if answer == QMessageBox.StandardButton.Yes:
            from PySide6.QtWidgets import QApplication

            QApplication.quit()

    def _remove_repo(self) -> None:
        repo = repositories.selected()
        answer = QMessageBox.question(self, "Repository", f"Remove {repo.name} from the list? What you imported from "
                                                          "it stays until you remove it.")
        if answer == QMessageBox.StandardButton.Yes:
            repositories.remove_repository(repo.id)
            self.refresh()

    def _import_all(self) -> None:
        languages = {}
        for entry_id, checks in getattr(self, "_lang_checks", {}).items():
            chosen = [c.property("code") for c in checks if c.isChecked()]
            if chosen:
                languages[entry_id] = chosen
        n = len(catalog.builtin_entries())
        answer = QMessageBox.question(self, "Import all", f"Import all {n} sources of {repositories.selected().name}? "
                                      "Large books are downloaded; this can take a while.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start(Worker("import_all", None, languages), "Importing every source of the repository…")

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
