"""Bookmarks (BM1): the ☆ button every page carries, and the page that keeps what was marked — in folders of the
user's own (nested, an item in as many folders as wanted, dragged onto a folder), with notes, opened with a
click, exported and imported as a file. The store is core.bookmarks (bookmarks.json in the data folder)."""

from __future__ import annotations

import html

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from isnady.core import bookmarks as core
from isnady.core.i18n import N_, tr
from isnady.gui import theme

MIME = "application/x-isnady-bookmarks"
ALL, UNFILED = "__all__", "__unfiled__"
# a colour per kind, the same in every theme (drawn on the theme's own pill background)
KIND_COLOURS = {"hadith": "#2E7D5B", "narrator": "#1D63A8", "scholar": "#8A5A1E", "term": "#7B3FA0", "chapter": "#A23B54",
                "tree": "#5B7A1E"}
KIND_ICONS = {"hadith": "❝", "narrator": "👤", "scholar": "🎓", "term": "📖", "chapter": "📚", "tree": "🌳"}
# what the ☆ of each kind adds, said on the star itself (BM2: "neyi eklediği yazsın")
KIND_ADD = {"hadith": N_("Add this hadith to your bookmarks"), "narrator": N_("Add this narrator to your bookmarks"),
            "scholar": N_("Add this scholar to your bookmarks"), "term": N_("Add this term to your bookmarks"),
            "chapter": N_("Add this chapter to your bookmarks"),
            "tree": N_("Add this place in the genealogy to your bookmarks")}


class _Hub(QObject):
    changed = Signal()          # any bookmark added, removed or filed: every ☆ and the page follow


HUB = _Hub()


def store() -> core.Store:
    return core.Store.load()


def save(s: core.Store) -> None:
    s.save()
    HUB.changed.emit()


class BookmarkButton(QToolButton):
    """☆ / ★: marks or unmarks one thing. The reference and the title are given by the page that shows it."""

    def __init__(self, kind: str, ref: str, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.kind, self.ref, self.title, self.subtitle = kind, str(ref), title, subtitle
        self.setObjectName("Star")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.clicked.connect(self._toggle)
        HUB.changed.connect(self._update)
        self._update()

    def _update(self) -> None:
        try:
            marked = store().find(self.kind, self.ref) is not None
        except RuntimeError:            # the button was deleted with its page
            return
        t = theme.current()
        self.setText("★" if marked else "☆")
        self.setStyleSheet(f"QToolButton#Star {{ color: {t.gold if marked else t.muted}; font-size: 20px; border: none;"
                           f" padding: 0 4px; background: transparent; }}")
        what = f"{tr(core.KINDS.get(self.kind, ''))}: {self.title}"
        self.setToolTip(tr("In your bookmarks — click to take it out") + f"\n{what}" if marked else
                        tr(KIND_ADD.get(self.kind, "Add to your bookmarks")) + f"\n{what}\n"
                        + tr("Bookmarks in the sidebar keeps them, in folders of your own."))

    def _toggle(self) -> None:
        s = store()
        item = s.find(self.kind, self.ref)
        if item:
            s.remove(item.id)
        else:
            s.add(self.kind, self.ref, self.title, self.subtitle)
        save(s)


class _ItemList(QListWidget):
    """The bookmarks shown; dragged onto a folder of the tree to file them there."""

    def mimeData(self, items):  # noqa: N802
        data = QMimeData()
        data.setData(MIME, ",".join(i.data(Qt.ItemDataRole.UserRole) for i in items).encode())
        return data

    def mimeTypes(self):  # noqa: N802
        return [MIME]

    def startDrag(self, actions):  # noqa: N802
        items = self.selectedItems()
        if not items:
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData(items))
        drag.exec(Qt.DropAction.CopyAction)


class _FolderTree(QTreeWidget):
    dropped = Signal(list, str)          # item ids, folder id

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

    def dragEnterEvent(self, e):  # noqa: N802
        e.acceptProposedAction() if e.mimeData().hasFormat(MIME) else e.ignore()

    def dragMoveEvent(self, e):  # noqa: N802
        target = self.itemAt(e.position().toPoint())
        ok = e.mimeData().hasFormat(MIME) and target is not None and \
            target.data(0, Qt.ItemDataRole.UserRole) not in (ALL, UNFILED)
        e.acceptProposedAction() if ok else e.ignore()

    def dropEvent(self, e):  # noqa: N802
        target = self.itemAt(e.position().toPoint())
        if target is None or not e.mimeData().hasFormat(MIME):
            return
        folder = target.data(0, Qt.ItemDataRole.UserRole)
        if folder in (ALL, UNFILED):
            return
        ids = bytes(e.mimeData().data(MIME)).decode().split(",")
        self.dropped.emit([i for i in ids if i], folder)
        e.acceptProposedAction()


def _label(text: str, name: str = "", wrap: bool = True, rich: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    if rich:
        label.setTextFormat(Qt.TextFormat.RichText)
    return label


class BookmarksPage(QWidget):
    open_hadith = Signal(int)
    open_narrator = Signal(int)
    open_scholar = Signal(str)
    open_term = Signal(str)
    open_chapter = Signal(int)
    open_tree = Signal(str, object)      # which tree, the box's id or the narrator's id (BM2)

    def __init__(self, connection, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._connection = connection           # a callable that gives the database connection (or None)
        self.folder = ALL
        left = QFrame()
        left.setObjectName("Card")
        left.setFixedWidth(330)
        lbox = QVBoxLayout(left)
        lbox.setContentsMargins(18, 16, 18, 14)
        lbox.setSpacing(8)
        title = _label(tr("Bookmarks"), "CardTitle")
        title.setFont(theme.reading_font(18, bold=True))
        lbox.addWidget(title)
        lbox.addWidget(_label(tr("Hadith, narrators, scholars, terms and chapters you marked with ☆ — in folders of your "
                                 "own. Drag a bookmark onto a folder to file it there; one bookmark can be in many "
                                 "folders."), "Caption"))
        buttons = QHBoxLayout()
        new = QPushButton(tr("New folder"))
        new.clicked.connect(lambda: self._new_folder(None))
        more = QPushButton(tr("Export / import"))
        menu = QMenu(more)
        menu.addAction(tr("Export bookmarks…"), self._export)
        menu.addAction(tr("Import bookmarks…"), self._import)
        more.setMenu(menu)
        for b in (new, more):
            b.setObjectName("Quiet")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            buttons.addWidget(b)
        buttons.addStretch(1)
        lbox.addLayout(buttons)
        self.tree = _FolderTree()
        self.tree.setHeaderHidden(True)
        self.tree.setObjectName("Contents")
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._folder_menu)
        self.tree.itemClicked.connect(lambda it, _c: self._show_folder(it.data(0, Qt.ItemDataRole.UserRole)))
        self.tree.dropped.connect(self._file)
        lbox.addWidget(self.tree, 1)

        right = QWidget()
        rbox = QVBoxLayout(right)
        rbox.setContentsMargins(0, 0, 0, 0)
        rbox.setSpacing(10)
        bar = QHBoxLayout()
        self.heading = _label("", "PageTitle", wrap=False)
        self.heading.setFont(theme.reading_font(20, bold=True))
        bar.addWidget(self.heading)
        bar.addStretch(1)
        self.kind = QComboBox()
        self.kind.setObjectName("FilterCombo")
        self.kind.addItem(tr("Every kind"), None)
        for key, label in core.KINDS.items():
            self.kind.addItem(f"{KIND_ICONS[key]}  {tr(label)}", key)
        self.kind.currentIndexChanged.connect(lambda _i: self._fill())
        self.find = QLineEdit()
        self.find.setPlaceholderText(tr("Find in the bookmarks"))
        self.find.setClearButtonEnabled(True)
        self.find.textChanged.connect(lambda _t: self._fill())
        self.find.setFixedWidth(240)
        bar.addWidget(self.kind)
        bar.addWidget(self.find)
        rbox.addLayout(bar)
        self.list = _ItemList()
        self.list.setObjectName("BookmarkList")
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setDragEnabled(True)
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.list.setSpacing(4)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.itemDoubleClicked.connect(lambda it: self._open(it.data(Qt.ItemDataRole.UserRole)))
        rbox.addWidget(self.list, 1)
        self.empty = _label("", "Lead")
        rbox.addWidget(self.empty)

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)
        root.addWidget(left)
        root.addWidget(right, 1)
        HUB.changed.connect(self.refresh)
        self.refresh()

    # ------------------------------------------------------------------ drawing
    def refresh(self) -> None:
        s = store()
        if self.folder not in (ALL, UNFILED) and not s.folder(self.folder):
            self.folder = ALL
        self.tree.clear()
        top = QTreeWidgetItem([f"★  {tr('All bookmarks')}  ({len(s.items)})"])
        top.setData(0, Qt.ItemDataRole.UserRole, ALL)
        loose = QTreeWidgetItem([f"☆  {tr('Not in a folder')}  ({len(s.unfiled())})"])
        loose.setData(0, Qt.ItemDataRole.UserRole, UNFILED)
        self.tree.addTopLevelItem(top)
        self.tree.addTopLevelItem(loose)

        def add(parent_item, parent_id):
            for f in s.children(parent_id):
                node = QTreeWidgetItem([f"📁  {f.name}  ({len(s.in_folder(f.id))})"])
                node.setData(0, Qt.ItemDataRole.UserRole, f.id)
                node.setToolTip(0, tr("Drop bookmarks here to file them in {folder}. Right click: new folder inside, "
                                      "rename, delete.", folder=s.path_of(f.id)))
                if parent_item is None:
                    self.tree.addTopLevelItem(node)
                else:
                    parent_item.addChild(node)
                add(node, f.id)
                node.setExpanded(True)
        add(None, None)
        for i in range(self.tree.topLevelItemCount()):
            self._select_in_tree(self.tree.topLevelItem(i))
        self._fill()

    def _select_in_tree(self, item: QTreeWidgetItem) -> None:
        if item.data(0, Qt.ItemDataRole.UserRole) == self.folder:
            self.tree.setCurrentItem(item)
        for j in range(item.childCount()):
            self._select_in_tree(item.child(j))

    def _show_folder(self, folder: str) -> None:
        self.folder = folder
        self._fill()

    def _fill(self) -> None:
        s = store()
        if self.folder == ALL:
            items, heading = s.items, tr("All bookmarks")
        elif self.folder == UNFILED:
            items, heading = s.unfiled(), tr("Not in a folder")
        else:
            items, heading = s.in_folder(self.folder), s.path_of(self.folder)
        self.heading.setText(heading)
        kind = self.kind.currentData()
        words = self.find.text().casefold().split()
        shown = [i for i in items if (not kind or i.kind == kind)
                 and all(w in f"{i.title} {i.subtitle} {i.note}".casefold() for w in words)]
        self.list.clear()
        for item in shown:
            row = QListWidgetItem()
            row.setData(Qt.ItemDataRole.UserRole, item.id)
            widget = self._row(s, item)
            row.setSizeHint(widget.sizeHint() + QSize(0, 4))
            self.list.addItem(row)
            self.list.setItemWidget(row, widget)
        self.empty.setText("" if shown else (
            tr("Nothing here yet. Mark anything with ☆ — a hadith card, a narrator, a scholar, a term in Learn, a chapter "
               "in Books — and it is kept here.") if not s.items else tr("No bookmark here matches.")))
        self.empty.setVisible(not shown)

    def _row(self, s: core.Store, item: core.Item) -> QWidget:
        t = theme.current()
        colour = KIND_COLOURS[item.kind]
        frame = QFrame()
        frame.setObjectName("Card")
        frame.setStyleSheet(f"QFrame#Card {{ border-left: 5px solid {colour}; }}")
        box = QVBoxLayout(frame)
        box.setContentsMargins(16, 10, 12, 10)
        box.setSpacing(4)
        top = QHBoxLayout()
        pill = QLabel(f"{KIND_ICONS[item.kind]} {tr(core.KINDS[item.kind])}")
        pill.setStyleSheet(f"color: {colour}; background: {t.pill}; border-radius: 9px; padding: 1px 8px; font-weight: 600;")
        top.addWidget(pill)
        name = _label(html.escape(item.title), "RowTitle", wrap=False, rich=True)
        name.setFont(theme.reading_font(14, bold=True))
        top.addWidget(name, 1)
        for text, tip, slot in ((tr("Open"), tr("Open it where it belongs"), lambda: self._open(item.id)),
                                (tr("Folders"), tr("Put it in folders, or take it out of them"), None),
                                (tr("Note"), tr("Write a note of your own"), lambda: self._note(item.id)),
                                (tr("Remove"), tr("Take it out of the bookmarks"), lambda: self._remove(item.id))):
            b = QPushButton(text)
            b.setObjectName("Link")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(tip)
            if slot is None:
                b.setMenu(self._folders_menu(b, s, item))
            else:
                b.clicked.connect(slot)
            top.addWidget(b)
        box.addLayout(top)
        conn = self._connection() if callable(self._connection) else self._connection
        more = core.detail(conn, item)
        if more:
            box.addWidget(_label(html.escape(more), "Caption", rich=True))
        if item.subtitle:
            arabic = any("؀" <= ch <= "ۿ" for ch in item.subtitle[:40])
            sub = _label(html.escape(item.subtitle), "Caption", rich=True)
            if arabic:
                sub.setFont(theme.script_font("arabic", factor=0.62))
                sub.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
            box.addWidget(sub)
        chips = [f"📁 {html.escape(s.path_of(f))}" for f in item.folders if s.folder(f)]
        if chips:
            box.addWidget(_label(" &nbsp; ".join(f"<span style='color:{t.lapis}'>{c}</span>" for c in chips),
                                 "Caption", rich=True))
        if item.note:
            note = _label(f"✎ {html.escape(item.note)}", "Lead", rich=True)
            note.setStyleSheet(f"color: {t.ink}; background: {t.gilt}; border-radius: 6px; padding: 4px 8px;")
            box.addWidget(note)
        return frame

    def _folders_menu(self, parent, s: core.Store, item: core.Item) -> QMenu:
        menu = QMenu(parent)
        if not s.folders:
            menu.addAction(tr("No folder yet: make one with New folder")).setEnabled(False)

        def add(parent_id, depth):
            for f in s.children(parent_id):
                act = menu.addAction(("    " * depth) + f.name)
                act.setCheckable(True)
                act.setChecked(f.id in item.folders)
                act.toggled.connect(lambda on, fid=f.id: self._toggle_folder(item.id, fid, on))
                add(f.id, depth + 1)
        add(None, 0)
        menu.addSeparator()
        menu.addAction(tr("New folder with it…"), lambda: self._new_folder(None, item.id))
        return menu

    # ------------------------------------------------------------------ actions
    def _toggle_folder(self, item_id: str, folder_id: str, on: bool) -> None:
        s = store()
        s.file_in(item_id, folder_id) if on else s.take_out(item_id, folder_id)
        save(s)

    def _file(self, ids: list, folder: str) -> None:
        s = store()
        for i in ids:
            s.file_in(i, folder)
        save(s)

    def _note(self, item_id: str) -> None:
        s = store()
        item = s.item(item_id)
        if not item:
            return
        text, ok = QInputDialog.getMultiLineText(self, tr("Note"), item.title, item.note)
        if ok:
            item.note = text.strip()
            save(s)

    def _remove(self, item_id: str) -> None:
        s = store()
        s.remove(item_id)
        save(s)

    def _new_folder(self, parent: str | None, with_item: str | None = None) -> None:
        name, ok = QInputDialog.getText(self, tr("New folder"), tr("Name of the folder (Prayer, or Prayer/Friday for one "
                                                                    "inside another):"))
        if not ok or not name.strip():
            return
        s = store()
        if parent:
            folder = s.new_folder(name, parent)
        else:
            folder = s.ensure_path(name)
        if with_item:
            s.file_in(with_item, folder.id)
        save(s)

    def _folder_menu(self, pos) -> None:
        node = self.tree.itemAt(pos)
        folder = node.data(0, Qt.ItemDataRole.UserRole) if node else None
        menu = QMenu(self)
        if folder in (None, ALL, UNFILED):
            menu.addAction(tr("New folder"), lambda: self._new_folder(None))
        else:
            menu.addAction(tr("New folder inside"), lambda: self._new_folder(folder))
            menu.addAction(tr("Rename"), lambda: self._rename(folder))
            move = menu.addMenu(tr("Move into"))
            s = store()
            move.addAction(tr("(the top)"), lambda: self._move(folder, None))
            for f in s.folders:
                if f.id != folder and f.id not in s.descendants(folder):
                    move.addAction(s.path_of(f.id), lambda fid=f.id: self._move(folder, fid))
            menu.addSeparator()
            menu.addAction(tr("Delete the folder"), lambda: self._delete(folder))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _rename(self, folder: str) -> None:
        s = store()
        f = s.folder(folder)
        name, ok = QInputDialog.getText(self, tr("Rename"), tr("New name:"), text=f.name if f else "")
        if ok and name.strip():
            s.rename_folder(folder, name)
            save(s)

    def _move(self, folder: str, parent: str | None) -> None:
        s = store()
        s.move_folder(folder, parent)
        save(s)

    def _delete(self, folder: str) -> None:
        s = store()
        if QMessageBox.question(self, tr("Delete the folder"), tr(
                "Delete the folder {folder} and the folders inside it? The bookmarks in them stay among your bookmarks.",
                folder=s.path_of(folder))) != QMessageBox.StandardButton.Yes:
            return
        s.delete_folder(folder)
        save(s)

    def _export(self) -> None:
        """File → Export… with the bookmarks chosen (EX1): JSON, CSV, Excel, Markdown, HTML, PDF …"""
        window = self.window()
        if hasattr(window, "export_dialog"):
            window.export_dialog("bookmarks")

    def _import(self) -> None:
        window = self.window()
        if hasattr(window, "import_dialog"):
            window.import_dialog("bookmarks")
        self.refresh()

    def _open(self, item_id: str) -> None:
        item = store().item(item_id)
        if not item:
            return
        conn = self._connection() if callable(self._connection) else self._connection
        if item.kind == "scholar":
            self.open_scholar.emit(item.ref)
            return
        if item.kind == "term":
            self.open_term.emit(item.ref)
            return
        if conn is None:
            return
        if item.kind == "tree":
            where = core.resolve_tree(conn, item.ref)
            if where is None:
                QMessageBox.information(self, tr("Bookmarks"), tr("{title} is not in the database now (was its book "
                                                                  "removed?). The bookmark stays.", title=item.title))
                return
            self.open_tree.emit(*where)
            return
        target = {"hadith": core.resolve_hadith, "narrator": core.resolve_narrator,
                  "chapter": core.resolve_chapter}[item.kind](conn, item.ref)
        if target is None:
            QMessageBox.information(self, tr("Bookmarks"), tr("{title} is not in the database now (was its book removed?). "
                                                              "The bookmark stays.", title=item.title))
            return
        {"hadith": self.open_hadith, "narrator": self.open_narrator, "chapter": self.open_chapter}[item.kind].emit(target)

    def retheme(self) -> None:
        self.refresh()


_KIND_WORDS = (N_("Hadith"), N_("Narrator"), N_("Scholar"), N_("Term"), N_("Chapter"))
