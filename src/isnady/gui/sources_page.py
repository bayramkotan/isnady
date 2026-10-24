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
from isnady.core.i18n import N_, tr


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
                message = tr("Imported {n} of {total} sources of the repository", n=len(imported),
                             total=len(imported) + len(failed))
                if narrators.get("links"):
                    message += "; " + tr("{identified:,} of {links:,} narrators in chains identified ({share:.1f}%)",
                                         identified=narrators["identified"], links=narrators["links"],
                                         share=100 * narrators["identified"] / narrators["links"])
                if failed:
                    message += ". " + tr("Failed:") + " " + "; ".join(f"{label} ({why})" for label, why in failed)
                self.done.emit(not failed, message + ".")
                return
            if self.action == "add_languages":            # LANG2: one language for every book
                imported, failed, _n = catalog.add_languages(conn, self.languages, self.progress.emit)
                message = tr("{names} added to {n} book(s)", names=", ".join(
                    tr(catalog.language_label(c)) for c in self.languages), n=len(imported))
                if failed:
                    message += ". " + tr("Failed:") + " " + "; ".join(f"{label} ({why})" for label, why in failed)
                self.done.emit(not failed, message + ".")
                return
            if self.action == "remove_languages":
                n = catalog.remove_languages(conn, self.languages)
                self.done.emit(True, tr("{names} removed from every book ({n} edition(s)).", names=", ".join(
                    tr(catalog.language_label(c)) for c in self.languages), n=n))
                return
            if self.action == "remove":
                catalog.remove_entry(conn, self.entry)
                self.done.emit(True, tr("Removed {title}.", title=self.entry.title))
                return
            report, narrators = catalog.import_entry(conn, self.entry, self.languages, self.auth, self.progress.emit)
            message = (tr("Imported {title}: {n:,} narrators", title=self.entry.title, n=report.texts)
                       if self.entry.kind == "rijal" else
                       tr("Imported {title}: {n:,} texts", title=self.entry.title, n=report.texts))
            if narrators.get("links"):
                message += "; " + tr("{identified:,} of {links:,} narrators in chains identified ({share:.1f}%)",
                                     identified=narrators["identified"], links=narrators["links"],
                                     share=100 * narrators["identified"] / narrators["links"])
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
        self.setWindowTitle(tr("Add a source"))
        self.resize(620, 300)
        self.title = QLineEdit()
        self.format = QComboBox()
        for imp in list_importers():
            self.format.addItem(imp.title, imp.format_id)
        self.location = QLineEdit()
        self.location.setPlaceholderText(tr("https://… or a file on this computer"))
        browse = QPushButton(tr("Browse…"))
        browse.setObjectName("Quiet")
        browse.clicked.connect(self._browse)
        where = QHBoxLayout()
        where.addWidget(self.location, 1)
        where.addWidget(browse)
        self.book = QLineEdit()
        self.book.setPlaceholderText(tr("optional, for index files: bukhari, muslim …"))
        self.license = QLineEdit()
        self.license.setPlaceholderText(tr("e.g. CC-BY-4.0; empty = not redistributed (tier C)"))
        self.auth = QComboBox()
        for kind, label in (("none", tr("None")), ("basic", tr("Username and password")), ("bearer", tr("Bearer token")),
                            ("apikey", tr("API key"))):
            self.auth.addItem(label, kind)
        self.key_name = QLineEdit()
        self.key_name.setPlaceholderText(tr("header name for an API key, e.g. X-API-Key"))
        form = QFormLayout()
        form.addRow(tr("Title"), self.title)
        form.addRow(tr("Format"), self.format)
        form.addRow(tr("File or URL"), where)
        form.addRow(tr("Book"), self.book)
        form.addRow(tr("Licence"), self.license)
        form.addRow(tr("Authentication"), self.auth)
        form.addRow(tr("API key header"), self.key_name)
        note = QLabel(tr("Passwords, tokens and keys are asked for when you import and are never stored."))
        note.setObjectName("Caption")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("Choose a source file"))
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
            intro = QLabel(tr("isnady reads its sources from a REPOSITORY: its own by default, which lists every Sunni and Shia "
                             "collection and rijal work it can read. Choose another, or add your own, and import with one "
                             "click. Your own files (User Resources) stay on this computer. The same from the command line: iy "
                             "repo, iy catalog."))
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
                self.status.setText(tr("The repository cannot be read: {exc}", exc=exc))
            if entries:
                self.box.addWidget(self._languages_card(conn))
            head = QHBoxLayout()
            title = QLabel(tr("Sources of {name}", name=repositories.selected().name))
            title.setObjectName("CardTitle")
            title.setFont(theme.reading_font(15, bold=True))
            head.addWidget(title)
            head.addStretch(1)
            all_button = QPushButton(tr("Import all"))
            all_button.setObjectName("Primary")
            all_button.setToolTip(tr("Every source of this repository, each in the languages ticked on its card; the search index, "
                                    "chains and narrators are brought up to date once, at the end"))
            all_button.clicked.connect(self._import_all)
            all_button.setProperty("allowed", bool(entries))
            self._buttons.append(all_button)
            head.addWidget(all_button)
            self.box.addLayout(head)
            groups = [(tr("Sunni hadith collections"), [e for e in entries if e.kind == "hadith" and e.tradition != "shia"]),
                      (tr("Shia hadith collections"), [e for e in entries if e.kind == "hadith" and e.tradition == "shia"]),
                      (tr("Narrators (rijal)"), [e for e in entries if e.kind == "rijal"])]
            for heading, group in groups:
                if not group:
                    continue
                sub = QLabel(f"{heading}  ·  {len(group)}")
                sub.setObjectName("FilterTitle")
                self.box.addWidget(sub)
                for entry in group:
                    self.box.addWidget(self._card(conn, entry))

            title = QLabel(tr("Your sources"))
            title.setObjectName("CardTitle")
            title.setFont(theme.reading_font(15, bold=True))
            self.box.addWidget(title)
            mine = catalog.user_entries()
            for entry in mine:
                self.box.addWidget(self._card(conn, entry))
            if not mine:
                none = QLabel(tr("None yet: a file or a URL of your own, in any format isnady reads."))
                none.setObjectName("Caption")
                self.box.addWidget(none)
            add = QPushButton(tr("Add a source…"))
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

    def _languages_card(self, conn) -> QFrame:
        """One language for every book at once (LANG2): added to or taken out of all the imported books that offer
        it; a book's own languages can still be chosen on its card."""
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 12, 18, 12)
        box.setSpacing(6)
        title = QLabel(tr("Languages for every book"))
        title.setObjectName("CardTitle")
        title.setFont(theme.reading_font(13.5, bold=True))
        box.addWidget(title)
        lead = QLabel(tr("Add a language to every imported book that has it, or take it out of all of them, in one step. "
                         "Arabic stays: the chains are read from it. Each book's card below can still differ."))
        lead.setObjectName("Caption")
        lead.setWordWrap(True)
        box.addWidget(lead)
        try:
            rows = catalog.language_overview(conn)
        except Exception:
            rows = []
        from PySide6.QtWidgets import QGridLayout

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)
        for r, row in enumerate(rows):
            name = QLabel(tr(row["label"]))
            name.setFont(theme.reading_font(12, bold=True))
            grid.addWidget(name, r, 0)
            count = QLabel(tr("in {have} of the {offered} books that have it", have=row["imported"], offered=row["offered"]))
            count.setObjectName("Caption")
            grid.addWidget(count, r, 1)
            add = QPushButton(tr("Add to every book"))
            add.setObjectName("Quiet")
            add.setCursor(Qt.CursorShape.PointingHandCursor)
            add.setProperty("allowed", row["imported"] < row["offered"])
            add.clicked.connect(lambda _c=False, c=row["code"]: self._every_book("add_languages", c))
            grid.addWidget(add, r, 2)
            self._buttons.append(add)
            rem = QPushButton(tr("Remove from every book"))
            rem.setObjectName("Quiet")
            rem.setCursor(Qt.CursorShape.PointingHandCursor)
            rem.setProperty("allowed", row["code"] != "ara" and row["imported"] > 0)
            if row["code"] == "ara":
                rem.setToolTip(tr("Arabic stays: the chains and the narrators are read from it."))
            rem.clicked.connect(lambda _c=False, c=row["code"]: self._every_book("remove_languages", c))
            grid.addWidget(rem, r, 3)
            self._buttons.append(rem)
        grid.setColumnStretch(4, 1)
        box.addLayout(grid)
        return card

    def _every_book(self, action: str, code: str) -> None:
        label = tr(catalog.language_label(code))
        if action == "remove_languages":
            answer = QMessageBox.question(self, tr("Remove a language"),
                                          tr("Take {language} out of every book?", language=label))
            if answer != QMessageBox.StandardButton.Yes:
                return
            self._start(Worker(action, None, [code]), tr("Removing {language} from every book…", language=label))
        else:
            self._start(Worker(action, None, [code]), tr("Adding {language} to every book that has it…", language=label))

    def _repo_card(self) -> QFrame:
        """The repository: chosen from the list (the default first), with where its catalog came from."""
        repo = repositories.selected()
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 12, 18, 12)
        box.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel(tr("Repository"))
        title.setObjectName("CardTitle")
        title.setFont(theme.reading_font(13.5, bold=True))
        head.addWidget(title)
        self.repo_combo = QComboBox()
        self.repo_combo.setObjectName("FilterCombo")
        self.repo_combo.setMinimumWidth(360)
        for r in repositories.all_repositories():
            label = r.name + ("" if r.builtin else "  " + tr("(added by you)"))
            self.repo_combo.addItem(label, r.id)
        self.repo_combo.setCurrentIndex(max(0, self.repo_combo.findData(repo.id)))
        self.repo_combo.currentIndexChanged.connect(self._choose_repo)
        head.addWidget(self.repo_combo, 1)
        box.addLayout(head)
        desc = QLabel(tr(repo.description))
        desc.setObjectName("Lead")
        desc.setWordWrap(True)
        box.addWidget(desc)
        try:
            _cat, where = repositories.catalog(repo)
            where = "shipped-own" if where == "shipped" and not repo.url else where
            how = tr({"network": N_("Catalog read from the repository just now."),
                      "shipped-own": N_("This dataset publishes no catalog of its own; isnady ships one for it."),
                      "saved": N_("Catalog read from the repository in the last day (Refresh reads it again)."),
                      "shipped": N_("The repository cannot be reached now, so the catalog shipped with isnady is used; "
                                    "each source is read from the repository, or from its origin when the repository "
                                    "has no copy.")}[where])
        except Exception as exc:
            how = tr("The catalog cannot be read: {exc}", exc=exc)
        links = [f"<a href='{repo.homepage}'>{repo.homepage}</a>"] if repo.homepage else []
        note = QLabel(" · ".join(links + [how]))
        note.setObjectName("Caption")
        note.setWordWrap(True)
        note.setTextFormat(Qt.TextFormat.RichText)
        note.setOpenExternalLinks(True)
        box.addWidget(note)
        # the buttons wrap onto a second line when the window is narrow, rather than pushing a horizontal scrollbar
        bar = QWidget()
        row = FlowLayout(bar, spacing=8)
        for label, slot, ok in ((tr("Refresh"), self._refresh_repo, True),
                                (tr("A folder on this computer…"), self._add_folder_repo, True),
                                (tr("Add a repository…"), self._add_repo, True),
                                (tr("Remove from list"), self._remove_repo, not repo.builtin),
                                (tr("Use the default"), lambda: self._use_repo(repositories.DEFAULT_ID),
                                 not repo.default)):
            b = QPushButton(label)
            b.setObjectName("Quiet")
            b.clicked.connect(slot)
            b.setProperty("allowed", ok)
            row.addWidget(b)
            self._buttons.append(b)
        box.addWidget(bar)
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
        name.setWordWrap(True)                           # a long title wraps rather than widening the whole page
        head.addWidget(name, 3)
        if entry.title_ar:
            ar = QLabel(entry.title_ar)
            ar.setStyleSheet(f"color: {theme.script_color('arabic')}; "
                             f"{theme.font_css(theme.script_font('arabic', factor=0.85))}")
            ar.setWordWrap(True)
            head.addWidget(ar, 2)
        state = QLabel(self._state_text(entry, st))
        state.setObjectName("Caption")
        state.setWordWrap(True)
        state.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        head.addWidget(state, 2)
        box.addLayout(head)
        if entry.builtin:
            tag_bar = QWidget()
            tags = FlowLayout(tag_bar, spacing=8)        # wraps on a narrow window instead of widening the page
            ours = entry.repo == repositories.DEFAULT_ID
            items = [(tr("Shia") if entry.tradition == "shia" else tr("Sunni"),
                      "TagGold" if entry.tradition == "shia" else "Tag",
                      tr("The tradition of the collection: Shia books are kept apart from Sunni ones, and their grades "
                         "and narrators are read in their own terms.")),
                     (entry.license or tr("licence not stated"), "TagMuted",
                      tr("May be shared further (tier A/B)") if db.tier_for_license(entry.license) in "AB"
                      else tr("No licence allowing it to be shared further: for this computer (tier C)"))]
            if not ours and entry.origin_url:
                items.append((tr("read from its publisher"), "TagMuted",
                              f"{entry.origin_name}\n{entry.origin_url}" if entry.origin_url else ""))
            for text, name_, tip in items:
                tag = QLabel(text)
                tag.setObjectName(name_)
                tag.setToolTip(tip)
                tags.addWidget(tag)
            if entry.hadith:
                count = QLabel(tr("{n:,} hadith", n=entry.hadith))
                count.setObjectName("Caption")
                tags.addWidget(count)
            if entry.origin_url:
                link = QLabel(f"<a href='{entry.origin_url}'>{entry.origin_name or entry.origin_url}</a>")
                link.setObjectName("Caption")
                link.setTextFormat(Qt.TextFormat.RichText)
                link.setOpenExternalLinks(True)
                tags.addWidget(link)
            box.addWidget(tag_bar)
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
                check = QCheckBox(tr(catalog.language_label(code)))
                check.setChecked(catalog.language_label(code) in chosen)
                check.setProperty("code", code)
                flow.addWidget(check)
                checks.append(check)
            box.addWidget(langs)
            self._lang_checks[entry.id] = checks

        row = QHBoxLayout()
        row.addStretch(1)
        imp = QPushButton(tr("Update") if st["imported"] else tr("Import"))
        imp.setObjectName("Primary" if not st["imported"] else "Quiet")
        imp.clicked.connect(lambda _c=False, e=entry, cs=checks: self._import(e, cs))
        row.addWidget(imp)
        self._buttons.append(imp)
        if st["imported"]:
            rem = QPushButton(tr("Remove data"))
            rem.setObjectName("Quiet")
            rem.clicked.connect(lambda _c=False, e=entry: self._remove(e))
            row.addWidget(rem)
            self._buttons.append(rem)
        if not entry.builtin:
            forget = QPushButton(tr("Delete from list"))
            forget.setObjectName("Quiet")
            forget.clicked.connect(lambda _c=False, e=entry: self._delete(e))
            row.addWidget(forget)
            self._buttons.append(forget)
        box.addLayout(row)
        return card

    @staticmethod
    def _state_text(entry, st) -> str:
        if not st["imported"]:
            return tr("Not imported")
        what = (tr("Imported: {n:,} narrators", n=st["count"]) if entry.kind == "rijal" else
                tr("Imported: {n:,} hadith", n=st["count"]) if entry.book else tr("Imported: {n:,} texts", n=st["count"]))
        langs = f" · {', '.join(st['languages'])}" if st["languages"] else ""
        when = f" · {st['when'][:10]}" if st.get("when") else ""
        tier = " · " + tr("tier {tier}", tier=st["tier"]) if st.get("tier") else ""
        return what + langs + when + tier

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
        self.status.setText(("" if ok else tr("Failed: ")) + message)
        if ok:
            self.data_imported.emit()

    def _ask_auth(self, entry: catalog.Entry) -> Auth | None:
        if entry.auth_kind == "none":
            return Auth()
        if entry.auth_kind == "basic":
            user, ok = QInputDialog.getText(self, entry.title, tr("Username:"))
            if not ok:
                return None
            password, ok = QInputDialog.getText(self, entry.title, tr("Password:"), QLineEdit.EchoMode.Password)
            return Auth(kind="basic", username=user, password=password) if ok else None
        secret, ok = QInputDialog.getText(self, entry.title, tr("Token:") if entry.auth_kind == "bearer" else tr("API key:"),
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
        title = QLabel(tr("Data folder"))
        title.setObjectName("CardTitle")
        title.setFont(theme.reading_font(13.5, bold=True))
        how = {"default": tr("the default for this system"), "chosen": tr("chosen by you"),
               "environment": tr("set by the ISNADY_DATA_DIR environment variable")}[paths.data_dir_source()]
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
        note = QLabel(tr("The database, your settings and your own sources live here. A new folder is used from the next "
                        "start of isnady. A ready database (isnady.db, or the isnady-db zip of isnady-data) can be taken "
                        "from a file on this computer instead of importing book by book."))
        note.setObjectName("Caption")
        note.setWordWrap(True)
        box.addWidget(note)
        bar = QWidget()
        row = FlowLayout(bar, spacing=8)
        for key, label, slot in (("open", tr("Open"), self._open_folder), ("change", tr("Change…"), self._change_folder),
                                 ("default", tr("Use default"), self._default_folder),
                                 ("ready", tr("Use a ready database…"), self._use_ready_database)):
            b = QPushButton(label)
            b.setObjectName("Quiet")
            b.clicked.connect(slot)
            if key in ("change", "default") and paths.data_dir_source() == "environment":
                b.setEnabled(False)
            if key == "default" and paths.data_dir_source() == "default":
                b.setEnabled(False)
            row.addWidget(b)
            if key != "open":
                self._buttons.append(b)
        box.addWidget(bar)
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
            QMessageBox.warning(self, tr("Data folder"), str(exc))
            return
        answer = QMessageBox.question(
            self, tr("Data folder"),
            (tr("isnady will use\n{new}\nfrom its next start; your data was copied there and the old folder is "
                "kept.", new=new) if mode == "copy" else tr("isnady will use\n{new}\nfrom its next start.", new=new))
            + "\n\n" + tr("Quit isnady now?"))
        self.refresh()
        if answer == QMessageBox.StandardButton.Yes:
            from PySide6.QtWidgets import QApplication

            QApplication.quit()

    def _change_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("Choose a folder for isnady's data"))
        if not folder:
            return
        box = QMessageBox(self)
        box.setWindowTitle(tr("Data folder"))
        box.setText(tr("Use {folder} for isnady's data?", folder=folder))
        copy = box.addButton(tr("Copy my data there"), QMessageBox.ButtonRole.AcceptRole)
        as_is = box.addButton(tr("Use the folder as it is"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() is copy:
            self._relocate(folder, "copy")
        elif box.clickedButton() is as_is:
            self._relocate(folder, "as-is")

    def _default_folder(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(tr("Data folder"))
        box.setText(tr("Go back to the default folder for this system?"))
        copy = box.addButton(tr("Copy my data there"), QMessageBox.ButtonRole.AcceptRole)
        as_is = box.addButton(tr("Use it as it is"), QMessageBox.ButtonRole.ActionRole)
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
            QMessageBox.warning(self, tr("Repository"), str(exc.args[0]))
        self.refresh()

    def _refresh_repo(self) -> None:
        repo = repositories.selected()
        try:
            _cat, where = repositories.catalog(repo, refresh=True)
            self.refresh()
            self.status.setText(tr("Catalog read again.") if where == "network" else
                                tr("The repository cannot be reached; the saved or shipped catalog is used."))
        except Exception as exc:
            self.status.setText(tr("Failed: {exc}", exc=exc))

    def _add_repo(self) -> None:
        text, ok = QInputDialog.getText(
            self, tr("Add a repository"),
            tr("The address of a repository with an isnady catalog (catalog.json):\n  a GitHub repository   "
              "https://github.com/owner/name\n  a Hugging Face dataset   "
              "https://huggingface.co/datasets/owner/name\n  a catalog URL, or a folder on this computer"))
        if not ok or not text.strip():
            return
        try:
            repo = repositories.add_repository(text.strip())
        except (ResourceError, ValueError) as exc:
            QMessageBox.warning(self, tr("Add a repository"), str(exc.args[0] if exc.args else exc))
            return
        repositories.select(repo.id)
        self.refresh()
        self.status.setText(tr("Added {name}; it is the repository now.", name=repo.name))

    def _add_folder_repo(self) -> None:
        """A repository on this computer: a copy of isnady-data (git clone, a USB stick, a shared folder) or any
        folder with a catalog.json — read without the network."""
        folder = QFileDialog.getExistingDirectory(self, tr("A folder with a catalog.json (e.g. your copy of isnady-data)"))
        if not folder:
            return
        try:
            repo = repositories.add_repository(folder)
        except (ResourceError, ValueError) as exc:
            QMessageBox.warning(self, tr("A folder on this computer"), str(exc.args[0] if exc.args else exc))
            return
        repositories.select(repo.id)
        self.refresh()
        self.status.setText(tr("Added {name} ({folder}); it is the repository now, read from this computer.", name=repo.name, folder=folder))

    def _use_ready_database(self) -> None:
        from isnady.data import ready

        path, _f = QFileDialog.getOpenFileName(self, tr("A ready isnady database"),
                                               "", tr("isnady database") + " (isnady-db-*.zip isnady*.db *.zip *.db)")
        if not path:
            return
        try:
            info = ready.stage(path)
        except ready.ReadyError as exc:
            QMessageBox.warning(self, tr("Ready database"), str(exc))
            return
        answer = QMessageBox.question(
            self, tr("Ready database"),
            tr("{books} books, {hadith:,} hadith. It takes the place of your database at the next start of "
              "isnady; your database is kept beside it as isnady.<date>.bak.db.\n\nQuit isnady now?", books=info['books'], hadith=info['hadith']))
        self.status.setText(tr("A ready database is waiting; it is used from the next start."))
        if answer == QMessageBox.StandardButton.Yes:
            from PySide6.QtWidgets import QApplication

            QApplication.quit()

    def _remove_repo(self) -> None:
        repo = repositories.selected()
        answer = QMessageBox.question(self, tr("Repository"), tr("Remove {name} from the list? What you imported from it stays until you remove it.", name=repo.name))
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
        answer = QMessageBox.question(self, tr("Import all"), tr("Import all {n} sources of {name}? Large books are downloaded; this can take a while.", n=n, name=repositories.selected().name))
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start(Worker("import_all", None, languages), tr("Importing every source of the repository…"))

    def _import(self, entry: catalog.Entry, checks: list) -> None:
        languages = [c.property("code") for c in checks if c.isChecked()] or None
        if checks and not languages:
            self.status.setText(tr("Choose at least one language."))
            return
        auth = self._ask_auth(entry)
        if auth is None:
            return
        self._start(Worker("import", entry, languages, auth), tr("Importing {title}…", title=entry.title))

    def _remove(self, entry: catalog.Entry) -> None:
        answer = QMessageBox.question(self, tr("Remove data"), tr("Remove everything imported from {title}?", title=entry.title))
        if answer == QMessageBox.StandardButton.Yes:
            self._start(Worker("remove", entry), tr("Removing {title}…", title=entry.title))

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
            QMessageBox.warning(self, tr("Add a source"), str(exc.args[0] if exc.args else exc))
            return
        self.refresh()

    def busy(self) -> bool:
        return self._worker is not None
