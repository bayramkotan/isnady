"""A hadith chosen from a book's contents, without knowing its number (CH2b): the chapters on the left, the hadith of
the chapter on the right with the start of their text and how far their chain was read; a double click (or Show
chain) gives the hadith."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from isnady.core import language as core_language
from isnady.core import works as core_works
from isnady.core.i18n import tr
from isnady.gui import theme


class ChapterPicker(QDialog):
    def __init__(self, conn, book: str, parent=None, chapter: int | None = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self.hadith_id: int | None = None
        work = core_works.find_work(conn, book)
        self.setWindowTitle(tr("Choose from the contents") + (f" — {work['title']}" if work else ""))
        self.resize(1000, 640)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setObjectName("Contents")
        self.tree.currentItemChanged.connect(lambda item, _p: item and self._fill(item.data(0, Qt.ItemDataRole.UserRole)))
        self.find = QLineEdit()
        self.find.setPlaceholderText(tr("Look for a word in this chapter"))
        self.find.setClearButtonEnabled(True)
        self.find.textChanged.connect(self._filter)
        self.list = QListWidget()
        self.list.setObjectName("NarratorList")
        self.list.setWordWrap(True)
        self.list.itemDoubleClicked.connect(lambda _i: self._accept())
        self.where = QLabel("")
        self.where.setObjectName("Caption")
        self.where.setWordWrap(True)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(self.where)
        right.addWidget(self.find)
        right.addWidget(self.list, 1)
        holder = QWidget()
        holder.setLayout(right)
        split = QSplitter()
        split.addWidget(self.tree)
        split.addWidget(holder)
        split.setSizes([380, 620])

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        show = buttons.addButton(tr("Show chain"), QDialogButtonBox.ButtonRole.AcceptRole)
        show.setObjectName("Primary")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        box = QVBoxLayout(self)
        box.setContentsMargins(18, 16, 18, 14)
        box.addWidget(QLabel(tr("Choose a chapter, then a hadith of it: the start of its text and how many narrators "
                                "its chain was read into are shown beside its number.")))
        box.addWidget(split, 1)
        box.addWidget(buttons)
        if work:
            self._build(work, chapter)

    def _build(self, work: dict, chapter: int | None) -> None:
        first = None
        chosen = None

        def add(parent_item, parent_id):
            nonlocal first, chosen
            for c in core_works.containers(self._conn, work["id"], parent_id):
                label = (f"{c['label']}. " if c["label"] else "") + (c["title"] or "")
                item = QTreeWidgetItem([label + (f"   ({c['leaves']})" if c["leaves"] else "")])
                item.setData(0, Qt.ItemDataRole.UserRole, c["id"] if c["leaves"] else None)
                if any("؀" <= ch <= "ۿ" for ch in label):
                    item.setFont(0, theme.script_font("arabic", factor=0.62))
                (parent_item.addChild(item) if parent_item else self.tree.addTopLevelItem(item))
                if c["leaves"] and first is None:
                    first = item
                if chapter and c["id"] == chapter:
                    chosen = item
                if c["subchapters"]:
                    add(item, c["id"])
        add(None, None)
        target = chosen or first
        if target is not None:
            self.tree.setCurrentItem(target)
            self.tree.scrollToItem(target)

    def _fill(self, chapter_id: int | None) -> None:
        self.list.clear()
        if not chapter_id:
            self.where.setText(tr("This heading holds chapters only: choose one of them."))
            return
        trail = core_works.path(self._conn, chapter_id)
        self.where.setText(" › ".join(((n["label"] + ". ") if n["label"] else "") + (n["title"] or "") for n in trail))
        from isnady.core import i18n

        # the start of each text in the first language chosen for the texts after Arabic, else the interface's
        wanted = [x for x in core_language.content_languages() if x != "Arabic"]
        lang = wanted[0] if wanted else {"tr": "Turkish", "en": "English"}.get(i18n.language())
        for h in core_works.chapter_hadith(self._conn, chapter_id, lang):
            read = (tr("{n} narrators", n=h["links"]) if h["links"] else tr("chain not read"))
            item = QListWidgetItem(f"{h['number']}   ·   {read}\n{h['words']}")
            item.setData(Qt.ItemDataRole.UserRole, h["hadith_id"])
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        self._filter(self.find.text())

    def _filter(self, text: str) -> None:
        from isnady.core.narrators import fold_latin
        from isnady.core.normalize import normalize

        words = [w for w in text.split() if w]
        for i in range(self.list.count()):
            item = self.list.item(i)
            hay = item.text()
            ok = all((normalize(w) in normalize(hay)) if any("؀" <= ch <= "ۿ" for ch in w)
                     else (fold_latin(w) in fold_latin(hay)) for w in words)
            item.setHidden(not ok)

    def _accept(self) -> None:
        item = self.list.currentItem()
        if item is None or item.isHidden():
            return
        self.hadith_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
