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
        if self.action == "ready_download":               # DB-READY: isnady-data's ready database (self.languages)
            self._ready_download()
            return
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
            if self.action == "update":                   # UPD5: what is new or changed in the repository
                imported, failed, narrators = catalog.update(conn, self.languages, self.progress.emit)
                message = tr("{n} book(s) brought up to date", n=len(imported))
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
                       tr("Downloaded {title}: the Arabic and {n} translation(s)", title=self.entry.title,
                          n=max(0, report.texts - 1)) if self.entry.kind == "quran" else
                       tr("Imported {title}: {n:,} entries and sections — read it in Books", title=self.entry.title,
                          n=report.texts) if self.entry.kind in ("sira", "tabaqat", "sahifa") else
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


    def _ready_download(self) -> None:
        """Download isnady-data's ready database (its database.json given as self.languages) and stage it."""
        from isnady.data import ready

        shown = [-1]

        def step(done: int, total: int) -> None:
            mb = ready.megabytes(done)
            if mb == shown[0]:
                return
            shown[0] = mb
            self.progress.emit(tr("Downloading the ready database… {done:,} of {total:,} MB", done=mb,
                                  total=ready.megabytes(total)) if total else
                               tr("Downloading the ready database… {done:,} MB", done=mb))

        try:
            info = ready.download(self.languages, step)
        except ready.ReadyError as exc:
            self.done.emit(False, str(exc))
            return
        except Exception as exc:  # the window must never be left waiting
            self.done.emit(False, f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(True, tr("The ready database is downloaded: {books} books, {hadith:,} hadith. It takes the place "
                                "of your database at the next start of isnady.", books=info["books"],
                                hadith=info["hadith"]))


def ready_offer_text(info: dict) -> str:
    """What isnady-data's ready database holds, for the dialogs that offer it."""
    from isnady.data import ready

    return tr("{date}: {books} books, {hadith:,} hadith, {narrators:,} narrators — every chain already read and every "
              "narrator already matched. {size:,} MB.", date=info.get("date") or "?", books=info["books"],
              hadith=info["hadith"], narrators=info["narrators"], size=ready.megabytes(info["size"]))


def ask_quit_for_ready(parent) -> None:
    """A ready database is staged: it is used from the next start; offer to quit now."""
    from PySide6.QtWidgets import QApplication

    answer = QMessageBox.question(parent, tr("Ready database"),
                                  tr("The ready database is waiting; it is used from the next start of isnady. Your "
                                     "database is kept beside it as isnady.<date>.bak.db.\n\nQuit isnady now?"))
    if answer == QMessageBox.StandardButton.Yes:
        QApplication.quit()


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


# the kinds of book, as isnady-data's folders are (0.7.3): (kind, sign, name)
KINDS = (("quran", "📖", N_("The Qur'an")), ("hadith", "📚", N_("Hadith collections")),
         ("sahifa", "📜", N_("Written sources")), ("sira", "🕌", N_("Sira")), ("tabaqat", "👥", N_("Tabaqat")),
         ("rijal", "⚖", N_("Rijal")))
ONE = {"quran": N_("Qur'an"), "hadith": N_("Hadith collection"), "sahifa": N_("Written source"), "sira": N_("Sira"),
       "tabaqat": N_("Tabaqat"), "rijal": N_("Rijal")}

# the languages of the Qur'an's translations in isnady-data, marked so that their names are translated
QURAN_LANGUAGES = (N_("Albanian"), N_("Azerbaijani"), N_("Bengali"), N_("Bosnian"), N_("English"), N_("French"),
                   N_("German"), N_("Indonesian"), N_("Kazakh"), N_("Malay"), N_("Persian"), N_("Russian"),
                   N_("Spanish"), N_("Tamil"), N_("Tatar"), N_("Turkish"), N_("Urdu"), N_("Uzbek"))


def _kind_name(kind: str, one: bool = False) -> str:
    return ONE.get(kind, kind) if one else next((k[2] for k in KINDS if k[0] == kind), kind)


def _sign(kind: str) -> str:
    return next((k[1] for k in KINDS if k[0] == kind), "•")


def _road(entry) -> str | None:
    """The road of a book; None for the Qur'an, which is both roads'."""
    if entry.kind == "quran":
        return None
    return "shia" if entry.tradition == "shia" else "sunni"


class SourcesPage(QWidget):
    data_imported = Signal()
    open_book = Signal(str)          # a book's "Open in Books" (the dialog closes, Books opens it)
    export_book = Signal(str)        # a hadith collection's "Export…"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._worker: Worker | None = None
        self._buttons: list[QPushButton] = []
        self._kind = "hadith"                    # the kind shown, as isnady-data's folders (0.7.3)
        self._road = "all"                       # both roads, or one (SH1)
        self._anchors: dict = {}
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
            intro = QLabel(tr("isnady reads every book from a REPOSITORY: its own by default (isnady-data). Its books "
                              "stand in one folder per kind — the Qur'an, hadith, written sources, sira, tabaqat, "
                              "rijal — and in each the Sunni road and the Shia road have their own. This page shows them "
                              "the same way: choose a kind, then a road. Every book has the same buttons and its "
                              "languages. The same from the command line: iy repo, iy catalog."))
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
            self._anchors = {}
            head = QHBoxLayout()
            title = QLabel(tr("Sources of {name}", name=repositories.selected().name))
            title.setObjectName("CardTitle")
            title.setFont(theme.reading_font(15, bold=True))
            head.addWidget(title)
            head.addStretch(1)
            try:
                self._updates = {i["entry"].id: i for i in catalog.updates(conn)} if entries else {}
            except Exception:  # noqa: BLE001 — the page is drawn without it
                self._updates = {}
            n = len(self._updates)
            upd = QPushButton("⟳ " + (tr("Get updates ({n})", n=n) if n else tr("Up to date")))
            upd.setObjectName("Primary" if n else "Quiet")
            upd.setCursor(Qt.CursorShape.PointingHandCursor)
            upd.setToolTip("\n".join(self._why(i) for i in self._updates.values()) if n else
                           tr("Nothing new in the repository: no new book, no changed book, no new language of the "
                              "languages you read"))
            upd.setProperty("allowed", bool(n))
            upd.clicked.connect(self._get_updates)
            self._buttons.append(upd)
            head.addWidget(upd)
            all_button = QPushButton(tr("Import all"))
            all_button.setObjectName("Quiet" if n else "Primary")
            all_button.setToolTip(tr("Every source of this repository, each in the languages ticked on its card; the search index, "
                                    "chains and narrators are brought up to date once, at the end"))
            all_button.clicked.connect(self._import_all)
            all_button.setProperty("allowed", bool(entries))
            self._buttons.append(all_button)
            head.addWidget(all_button)
            self.box.addLayout(head)
            kinds = [k for k in KINDS if any(e.kind == k[0] for e in entries)]
            if kinds and self._kind not in [k[0] for k in kinds]:
                self._kind = kinds[0][0]
            if kinds:
                self.box.addWidget(self._kind_bar(entries, kinds))
            shown = [e for e in entries if e.kind == self._kind]
            roads = [r for r in ("sunni", "shia") if any(_road(e) == r for e in shown)]
            if len(roads) > 1:
                self.box.addWidget(self._road_bar())
            elif self._road not in ("all", *roads):
                self._road = "all"
            # the kind's folder in the repository, and under it one group for each road (SH1); the Qur'an is both roads'
            for road in (roads or [None]):
                group = [e for e in shown if road is None or _road(e) == road]
                if not group or (road is not None and self._road not in ("all", road)):
                    continue
                folder = f"{self._kind}/{road}/" if road else f"{self._kind}/"
                band = QLabel(f"{_sign(self._kind)}  {tr(_kind_name(self._kind))}" +
                              (f" · {tr('Sunni') if road == 'sunni' else tr('Shia')}" if road else "") +
                              f"  ·  {len(group)}")
                band.setObjectName("CardTitle")
                band.setFont(theme.reading_font(16, bold=True))
                if road:
                    band.setStyleSheet(f"color: {theme.current().gold if road == 'shia' else theme.current().lapis};"
                                       "padding-top: 8px;")
                self._anchors[f"{self._kind}-{road}" if road else self._kind] = band
                self.box.addWidget(band)
                where = QLabel(tr("In the repository: {folder}", folder=f"isnady-data/{folder}"))
                where.setObjectName("Caption")
                self.box.addWidget(where)
                for entry in group:
                    self.box.addWidget(self._card(conn, entry))
            if self._kind == "hadith" and shown:
                self.box.addWidget(self._languages_card(conn))

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

    @staticmethod
    def _why(item: dict) -> str:
        from isnady.core import titles as core_titles

        e = item["entry"]
        name = core_titles.book(e.book or e.id, e.title)
        if item["why"] == "new":
            return tr("New in the repository: {title}", title=name)
        if item["why"] == "changed":
            return tr("Changed in the repository: {title}", title=name)
        return tr("{title}: new language(s) {names}", title=name,
                  names=", ".join(tr(catalog.language_label(c)) for c in item.get("new", [])))

    def _get_updates(self) -> None:
        items = list(getattr(self, "_updates", {}).values())
        if not items:
            return
        answer = QMessageBox.question(self, tr("Get updates"), tr("Bring these up to date?") + "\n\n" +
                                      "\n".join("• " + self._why(i) for i in items))
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start(Worker("update", None, items), tr("Bringing {n} book(s) up to date…", n=len(items)))

    def _kind_bar(self, entries, kinds) -> QWidget:
        """One button per kind of book, as the repository's folders are: the Qur'an, hadith, written sources, sira,
        tabaqat, rijal — each with how many books it holds and how many are imported."""
        bar = QWidget()
        flow = FlowLayout(bar, spacing=8)
        for kind, sign, _name in kinds:
            group = [e for e in entries if e.kind == kind]
            b = QPushButton(f"{sign}  {tr(_kind_name(kind))}  ·  {len(group)}")
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setChecked(kind == self._kind)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(tr("In the repository: {folder}", folder=f"isnady-data/{kind}/"))
            b.clicked.connect(lambda _c=False, k=kind: self._set_kind(k))
            flow.addWidget(b)
        return bar

    def _road_bar(self) -> QWidget:
        """Both roads, or one only."""
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        for key, text in (("all", tr("Both roads")), ("sunni", tr("Sunni")), ("shia", tr("Shia"))):
            b = QPushButton(text)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setChecked(self._road == key)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=key: self._set_road(k))
            row.addWidget(b)
        row.addStretch(1)
        return bar

    def _set_kind(self, kind: str) -> None:
        self._kind = kind
        self.refresh()

    def _set_road(self, road: str) -> None:
        self._road = road
        self.refresh()

    def _go_to(self, gid: str) -> None:
        """A kind, or a kind on one road ("sahifa-shia"), shown and in view."""
        from PySide6.QtWidgets import QScrollArea

        kind, _, road = gid.partition("-")
        self._kind, self._road = kind, road or "all"
        self.refresh()
        target = self._anchors.get(gid) or self._anchors.get(kind)
        w = self.parentWidget()
        while w is not None and not isinstance(w, QScrollArea):
            w = w.parentWidget()
        if target is not None and w is not None:
            w.verticalScrollBar().setValue(max(0, target.mapTo(w.widget(), target.rect().topLeft()).y() - 10))

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
        desc = QLabel(tr(repo.description))       # isnady's own one is in the i18n files (REPO_ABOUT)
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
        """One book, the same for every kind: its name, its tags, what it is, its languages, and the same four
        buttons — Import (Update), Remove data, Open in Books, Export (Bayram, 2026-11-02: "Import/export butonları
        hepsi için aynı olmalı! Diller de!")."""
        st = catalog.status(conn, entry)
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 12, 18, 12)
        box.setSpacing(6)
        head = QHBoxLayout()
        from isnady.core import titles as core_titles

        name = QLabel(core_titles.book(entry.book or entry.id, entry.title) if entry.builtin else entry.title)
        name.setToolTip(entry.title)
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
            licence = (entry.license or tr("licence not stated"), "TagMuted",
                       tr("May be shared further (tier A/B)") if db.tier_for_license(entry.license) in "AB"
                       else tr("No licence allowing it to be shared further: for this computer (tier C)"))
            road = _road(entry)
            items = [(tr(_kind_name(entry.kind, one=True)), "Tag", ""),
                     (tr("Both roads") if road is None else tr("Shia") if road == "shia" else tr("Sunni"),
                      "TagGold" if road == "shia" else "TagMuted",
                      tr("The tradition of the book: Shia books are kept apart from Sunni ones, and their "
                         "grades and narrators are read in their own terms.")), licence]
            from isnady.core import i18n as core_i18n

            if entry.compiler and core_i18n.language() == "en":     # in another language it opens the description
                items.append((entry.compiler, "TagMuted", ""))
            if entry.size and entry.size >= 2**19:
                items.append((tr("about {mb} MB", mb=max(1, round(entry.size / 2**20))), "TagMuted",
                              tr("Downloaded once; the Qur'an's translations each when chosen")
                              if entry.kind == "quran" else tr("Downloaded once")))
            pending = getattr(self, "_updates", {}).get(entry.id)
            if pending:
                items.insert(0, ("⟳ " + {"new": tr("New"), "changed": tr("Changed"),
                                         "languages": tr("New language")}[pending["why"]], "TagGold", self._why(pending)))
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
        about = core_titles.about(entry.id, entry.description) if entry.builtin else entry.description
        if entry.kind == "sahifa":                  # its lead in the interface language (SHF1b)
            from isnady.core import sahifa as core_sahifa

            known = next((core_sahifa.find(a) for a in entry.aliases if core_sahifa.find(a)), None)
            if known:
                about = core_sahifa.text(known["lead"])
        desc = QLabel(about + (f"  ·  {entry.location}" if not entry.builtin else ""))
        desc.setObjectName("Caption")
        desc.setWordWrap(True)
        box.addWidget(desc)

        checks = self._language_row(box, entry, st)
        row = QHBoxLayout()
        row.addStretch(1)
        key = self._work_key(conn, entry) if st["imported"] else None
        buttons = [
            (tr("Update") if st["imported"] else tr("Import"), "Quiet" if st["imported"] else "Primary", True, "",
             lambda _c=False, e=entry, cs=checks: self._import(e, cs)),
            (tr("Remove data"), "Quiet", st["imported"], tr("Nothing of it is imported yet"),
             lambda _c=False, e=entry: self._remove(e)),
            ("📚 " + tr("Open in Books"), "Quiet", bool(key), tr("Import it first; then it is read in Books"),
             lambda _c=False, k=key: self.open_book.emit(k)),
            ("⤴ " + tr("Export…"), "Quiet", bool(st["imported"] and entry.kind == "hadith" and entry.book),
             tr("Import it first") if not st["imported"] else
             tr("Export writes hadith collections (EPUB, PDF, CSV …); this kind is read in Books"),
             lambda _c=False, b=entry.book: self.export_book.emit(b or "")),
        ]
        if not entry.builtin:
            buttons.append((tr("Delete from list"), "Quiet", True, "", lambda _c=False, e=entry: self._delete(e)))
        for text, style, ok, why, slot in buttons:
            b = QPushButton(text)
            b.setObjectName(style)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setProperty("allowed", bool(ok))
            if not ok and why:
                b.setToolTip(why)
            b.clicked.connect(slot)
            row.addWidget(b)
            self._buttons.append(b)
        box.addLayout(row)
        return card

    def _language_row(self, box, entry: catalog.Entry, st) -> list:
        """The book's languages, on every card: those a hadith collection offers; the Qur'an's translations by
        language (and its translators); Arabic alone, as it is, for the other kinds."""
        langs = QWidget()
        flow = FlowLayout(langs, spacing=10)
        title = QLabel(tr("Languages:"))
        title.setObjectName("Caption")
        flow.addWidget(title)
        checks = []
        if entry.kind == "quran":
            from isnady.core import quran

            have = {e["language"] for e in quran.editions()} if quran.available() else set()
            fixed = QCheckBox(tr("Arabic"))
            fixed.setChecked(True)
            fixed.setEnabled(False)
            fixed.setToolTip(tr("The Arabic text is always there"))
            flow.addWidget(fixed)
            wanted = set(quran.wanted_languages())
            for lang in entry.languages:
                check = QCheckBox(tr(lang))
                check.setChecked(lang in have or (not have and lang in wanted))
                check.setProperty("code", lang)
                check.setToolTip(tr("Ticked: one translation in this language ({name}); untick to remove its "
                                    "translations. Translators… chooses others.",
                                    name=quran.DEFAULT_OF.get(lang, "")))
                flow.addWidget(check)
                checks.append(check)
            more = QPushButton("➕ " + tr("Translators…"))
            more.setObjectName("Quiet")
            more.setToolTip(tr("Choose the translations to download, of 98 languages; untick one to remove it"))
            more.clicked.connect(self._quran_translations)
            self._buttons.append(more)
            flow.addWidget(more)
        elif entry.book and entry.languages and entry.kind == "hadith":
            chosen = st["languages"] or [catalog.language_label(c) for c in catalog.DEFAULT_LANGUAGES]
            for code in entry.languages:
                check = QCheckBox(tr(catalog.language_label(code)))
                check.setChecked(catalog.language_label(code) in chosen)
                check.setProperty("code", code)
                if code == "ara":
                    check.setToolTip(tr("Arabic stays: the chains and the narrators are read from it."))
                flow.addWidget(check)
                checks.append(check)
            self._lang_checks[entry.id] = checks
        else:
            fixed = QCheckBox(tr("Arabic"))
            fixed.setChecked(True)
            fixed.setEnabled(False)
            fixed.setToolTip(tr("This work is in Arabic only, as its author wrote it"))
            flow.addWidget(fixed)
        box.addWidget(langs)
        return checks

    @staticmethod
    def _work_key(conn, entry: catalog.Entry) -> str | None:
        """The key Books opens this book by, once it is imported."""
        if entry.kind == "quran":
            return "quran"
        names = [n for n in (entry.book, entry.id, *entry.aliases) if n]
        if not names:
            return None
        try:
            row = conn.execute(f"SELECT key FROM works WHERE key IN ({','.join('?' * len(names))}) LIMIT 1",
                               names).fetchone()
            if row is None and entry.kind != "hadith":     # a work named by its source (the rijal: taqrib, najashi)
                row = conn.execute("SELECT w.key FROM works w JOIN sources s ON s.id = w.source_id WHERE s.key = ? "
                                   "LIMIT 1", (entry.source_key,)).fetchone()
        except Exception:  # noqa: BLE001 — a database without works
            row = None
        return row[0] if row else None

    def _import_quran(self, entry: catalog.Entry, checks: list) -> None:
        """The Qur'an's card: a language ticked gets its translation (the one its readers know best), a language
        unticked loses its translations; Update reads again those already here."""
        from isnady.core import quran

        ticked = {c.property("code") for c in checks if c.isChecked()}
        have = [e for e in quran.editions() if e["key"] != quran.ARABIC] if quran.available() else []
        for e in have:
            if e["language"] not in ticked:
                quran.remove(e["key"])
        kept = [e["key"] for e in have if e["language"] in ticked]
        langs = {e["language"] for e in have}
        wanted = kept + [quran.DEFAULT_OF[lang] for lang in sorted(ticked) if lang not in langs and lang in quran.DEFAULT_OF]
        if not wanted and not quran.available():
            wanted = quran.default_editions()
        if not wanted:
            self.refresh()
            return
        self._start(Worker("import", entry, wanted), tr("Downloading the translations…"))

    def _quran_translations(self) -> None:
        """The Qur'an's translations window (gui.quran_view): those ticked are downloaded here, with the page's bar."""
        from isnady.core import quran
        from isnady.gui.quran_view import AddTranslations

        dialog = AddTranslations(self)
        if not dialog.exec():
            return
        for key in dialog.removed:
            quran.remove(key)
        if dialog.chosen:
            entry = next((e for e in catalog.builtin_entries() if e.kind == "quran"), None)
            if entry is not None:
                self._start(Worker("import", entry, dialog.chosen), tr("Downloading the translations…"))
                return
        self.refresh()

    @staticmethod
    def _state_text(entry, st) -> str:
        if entry.kind == "quran":
            return (tr("Downloaded: the Arabic and {n} translation(s)", n=st["count"]) if st["imported"]
                    else tr("Not downloaded"))
        if not st["imported"]:
            return tr("Not imported")
        if entry.kind in ("sira", "tabaqat", "sahifa"):
            when = f" · {st['when'][:10]}" if st.get("when") else ""
            if entry.kind == "sahifa":
                return tr("Imported: {n:,} hadith", n=st["count"]) + when
            return tr("Imported: {n:,} entries and sections", n=st["count"]) + when
        what = (tr("Imported: {n:,} narrators", n=st["count"]) if entry.kind == "rijal" else
                tr("Imported: {n:,} hadith", n=st["count"]) if entry.book else tr("Imported: {n:,} texts", n=st["count"]))
        langs = f" · {', '.join(tr(x) for x in st['languages'])}" if st["languages"] else ""
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
        action = self._worker.action if self._worker is not None else None
        self._worker = None
        self.refresh()
        self.status.setText(("" if ok else tr("Failed: ")) + message)
        if ok and action == "ready_download":
            ask_quit_for_ready(self)
        elif ok:
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
                                 ("download", tr("Download the ready database…"), self._download_ready_database),
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

    def _download_ready_database(self) -> None:
        """DB-READY: isnady-data's own ready database — every book imported, every chain read, every narrator
        matched — downloaded in the background and used from the next start."""
        from isnady.data import ready

        try:
            info = ready.available(timeout=20)
        except ready.ReadyError as exc:
            QMessageBox.warning(self, tr("Ready database"), str(exc))
            return
        if not info["usable"]:
            QMessageBox.warning(self, tr("Ready database"),
                                tr("The ready database of isnady-data is newer (schema {schema}) than this isnady "
                                   "reads. Update isnady first: Help → Check for Updates.", schema=info["schema"]))
            return
        answer = QMessageBox.question(
            self, tr("Ready database"),
            tr("Download the ready database of isnady-data?") + "\n\n" + ready_offer_text(info) + "\n\n"
            + tr("It takes the place of your database at the next start of isnady; your database is kept beside it "
                 "as isnady.<date>.bak.db."))
        if answer == QMessageBox.StandardButton.Yes:
            self._start(Worker("ready_download", None, info), tr("Downloading the ready database…"))

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
        if entry.kind == "quran":                  # its languages ticked on the card (0.7.3)
            self._import_quran(entry, checks)
            return
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
