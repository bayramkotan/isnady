"""Bookmarks (BM1): anything worth keeping — a hadith, a narrator, a scholar, a term of the glossary, a chapter of a
book — kept in folders of the user's own, with a note. Qt-free; the GUI page, the ☆ buttons and `iy bookmark`
all go through here.

Bayram: "Bookmarks kısmı olacak! Hatta klasör klasör saklayabilecek … 'namaz ile alakalı hadisler' deyip …
istediği klasörün altına sürükleyebilecek, hatta birden fazla klasör altına alabilecek … rename, remove/delete …
Bunların hepsi JSON dosyasında saklanacak ve bookmark export/import ayarları da olacak" (2026-10-04) and
"ister Learn'den, ister âlimlerden, ister râvilerden bookmark yapabilecek" (2026-10-11).

The file is `bookmarks.json` in isnady's data folder — the user's own, never published (rule 17). Every item is
kept by a reference that survives a new import: a hadith by its book and number ("bukhari:1"), a narrator by his
key in the rijal work, a scholar and a term by their ids, a chapter by its book and chapter number.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from isnady.core.i18n import N_

KINDS = {"hadith": N_("Hadith"), "narrator": N_("Narrator"), "scholar": N_("Scholar"), "term": N_("Term"),
         "chapter": N_("Chapter")}
VERSION = 1


def path() -> Path:
    from isnady.data.paths import data_dir

    return data_dir() / "bookmarks.json"


@dataclass
class Folder:
    id: str
    name: str
    parent: str | None = None


@dataclass
class Item:
    id: str
    kind: str                 # one of KINDS
    ref: str                  # "bukhari:1", a narrator's key, a scholar's id, a term's id, "bukhari:3" (chapter)
    title: str                # as shown when it was marked
    subtitle: str = ""
    note: str = ""
    folders: list[str] = field(default_factory=list)
    added: float = 0.0


@dataclass
class Store:
    folders: list[Folder] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)

    # ------------------------------------------------------------------ reading and writing
    @classmethod
    def load(cls, file: Path | None = None) -> "Store":
        file = file or path()
        try:
            data = json.loads(Path(file).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Store":
        folders = [Folder(f["id"], f["name"], f.get("parent")) for f in data.get("folders", []) if f.get("id")]
        known = {f.id for f in folders}
        items = []
        for d in data.get("items", []):
            if d.get("kind") not in KINDS or not d.get("ref"):
                continue
            items.append(Item(d.get("id") or _new_id(), d["kind"], str(d["ref"]), d.get("title") or str(d["ref"]),
                              d.get("subtitle", ""), d.get("note", ""),
                              [f for f in d.get("folders", []) if f in known], float(d.get("added") or 0)))
        return cls(folders, items)

    def to_dict(self) -> dict:
        return {"schema": f"isnady-bookmarks/{VERSION}",
                "folders": [{"id": f.id, "name": f.name, "parent": f.parent} for f in self.folders],
                "items": [{"id": i.id, "kind": i.kind, "ref": i.ref, "title": i.title, "subtitle": i.subtitle,
                           "note": i.note, "folders": i.folders, "added": i.added} for i in self.items]}

    def save(self, file: Path | None = None) -> None:
        file = Path(file or path())
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(file)

    # ------------------------------------------------------------------ items
    def find(self, kind: str, ref: str) -> Item | None:
        return next((i for i in self.items if i.kind == kind and i.ref == str(ref)), None)

    def add(self, kind: str, ref: str, title: str, subtitle: str = "", folder: str | None = None,
            note: str = "") -> Item:
        if kind not in KINDS:
            raise ValueError(f"unknown kind {kind!r}; one of {', '.join(KINDS)}")
        item = self.find(kind, ref)
        if item is None:
            item = Item(_new_id(), kind, str(ref), title, subtitle, note, [], time.time())
            self.items.insert(0, item)
        if folder and folder not in item.folders and self.folder(folder):
            item.folders.append(folder)
        return item

    def remove(self, item_id: str) -> bool:
        before = len(self.items)
        self.items = [i for i in self.items if i.id != item_id]
        return len(self.items) != before

    def item(self, item_id: str) -> Item | None:
        return next((i for i in self.items if i.id == item_id), None)

    def file_in(self, item_id: str, folder_id: str, keep_others: bool = True) -> None:
        """Put an item in a folder (also in its other folders, unless keep_others is False: then moved)."""
        item, folder = self.item(item_id), self.folder(folder_id)
        if not item or not folder:
            return
        if not keep_others:
            item.folders = []
        if folder_id not in item.folders:
            item.folders.append(folder_id)

    def take_out(self, item_id: str, folder_id: str) -> None:
        item = self.item(item_id)
        if item and folder_id in item.folders:
            item.folders.remove(folder_id)

    # ------------------------------------------------------------------ folders
    def folder(self, folder_id: str | None) -> Folder | None:
        return next((f for f in self.folders if f.id == folder_id), None)

    def folder_named(self, name: str) -> Folder | None:
        """A folder by its name or its path ("Prayer/Friday"), case not minded."""
        parts = [p.strip().casefold() for p in name.replace("\\", "/").split("/") if p.strip()]
        parent = None
        found = None
        for p in parts:
            found = next((f for f in self.folders if f.parent == parent and f.name.casefold() == p), None)
            if found is None:
                return None
            parent = found.id
        return found

    def new_folder(self, name: str, parent: str | None = None) -> Folder:
        name = name.strip() or "…"
        same = next((f for f in self.folders if f.parent == parent and f.name == name), None)
        if same:
            return same
        folder = Folder(_new_id(), name, parent if self.folder(parent) else None)
        self.folders.append(folder)
        return folder

    def ensure_path(self, name: str) -> Folder:
        """The folder of a path ("Prayer/Friday"), made where it is missing."""
        parent = None
        folder = None
        for p in [p.strip() for p in name.replace("\\", "/").split("/") if p.strip()]:
            folder = self.new_folder(p, parent)
            parent = folder.id
        if folder is None:
            raise ValueError("a folder needs a name")
        return folder

    def rename_folder(self, folder_id: str, name: str) -> None:
        folder = self.folder(folder_id)
        if folder and name.strip():
            folder.name = name.strip()

    def delete_folder(self, folder_id: str) -> None:
        """A folder and the folders inside it go; their items stay among the bookmarks (outside those folders)."""
        gone = {folder_id} | set(self.descendants(folder_id))
        self.folders = [f for f in self.folders if f.id not in gone]
        for i in self.items:
            i.folders = [f for f in i.folders if f not in gone]

    def move_folder(self, folder_id: str, parent: str | None) -> None:
        folder = self.folder(folder_id)
        if folder and parent != folder_id and parent not in self.descendants(folder_id):
            folder.parent = parent if self.folder(parent) else None

    def children(self, parent: str | None) -> list[Folder]:
        return sorted((f for f in self.folders if f.parent == parent), key=lambda f: f.name.casefold())

    def descendants(self, folder_id: str) -> list[str]:
        out, todo = [], [folder_id]
        while todo:
            current = todo.pop()
            for f in self.folders:
                if f.parent == current:
                    out.append(f.id)
                    todo.append(f.id)
        return out

    def path_of(self, folder_id: str) -> str:
        names, current = [], self.folder(folder_id)
        while current:
            names.insert(0, current.name)
            current = self.folder(current.parent)
        return "/".join(names)

    def in_folder(self, folder_id: str | None, deep: bool = True) -> list[Item]:
        """The items of a folder (and of the folders inside it when deep); None: every item."""
        if folder_id is None:
            return list(self.items)
        wanted = {folder_id} | (set(self.descendants(folder_id)) if deep else set())
        return [i for i in self.items if wanted & set(i.folders)]

    def unfiled(self) -> list[Item]:
        return [i for i in self.items if not i.folders]

    # ------------------------------------------------------------------ exchange
    def merge(self, other: "Store") -> tuple[int, int]:
        """Add another store's folders (by path) and items (by kind and reference); returns (items, folders) added."""
        added_items = added_folders = 0
        mapping = {}
        for f in sorted(other.folders, key=lambda f: other.path_of(f.id).count("/")):
            before = len(self.folders)
            mapping[f.id] = self.ensure_path(other.path_of(f.id)).id
            added_folders += len(self.folders) - before
        for i in other.items:
            existing = self.find(i.kind, i.ref)
            if existing is None:
                existing = Item(_new_id(), i.kind, i.ref, i.title, i.subtitle, i.note, [], i.added or time.time())
                self.items.append(existing)
                added_items += 1
            elif i.note and i.note not in existing.note:
                existing.note = (existing.note + "\n" + i.note).strip()
            for f in i.folders:
                if f in mapping and mapping[f] not in existing.folders:
                    existing.folders.append(mapping[f])
        return added_items, added_folders


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------- references
def hadith_ref(conn, hadith_id: int) -> tuple[str, str, str] | None:
    """(reference, title, subtitle) of a hadith: "bukhari:1", "Sahih al-Bukhari 1", the start of its text."""
    from isnady.core import titles

    row = conn.execute("""SELECT c.key, c.name, h.number FROM hadiths h JOIN collections c ON c.id = h.collection_id
                          WHERE h.id = ?""", (hadith_id,)).fetchone()
    if not row:
        return None
    text = conn.execute("""SELECT t.text FROM texts t JOIN editions e ON e.id = t.edition_id WHERE t.hadith_id = ?
                           ORDER BY CASE e.language WHEN 'Arabic' THEN 1 ELSE 0 END LIMIT 1""", (hadith_id,)).fetchone()
    snippet = " ".join((text[0] if text else "").split())[:140]
    return f"{row[0]}:{row[2]}", f"{titles.book(row[0], row[1])} {row[2]}", snippet


def resolve_hadith(conn, ref: str) -> int | None:
    key, _, number = ref.partition(":")
    row = conn.execute("""SELECT h.id FROM hadiths h JOIN collections c ON c.id = h.collection_id
                          WHERE c.key = ? AND h.number = ?""", (key, number)).fetchone()
    return row[0] if row else None


def narrator_ref(conn, person_id: int) -> tuple[str, str, str] | None:
    from isnady.core import narrators

    row = conn.execute("SELECT key, name_ar FROM persons WHERE id = ?", (person_id,)).fetchone()
    if not row:
        return None
    reading, arabic = narrators.reading(conn, person_id, row[1])
    return row[0], reading or arabic, arabic


def resolve_narrator(conn, ref: str) -> int | None:
    row = conn.execute("SELECT id FROM persons WHERE key = ?", (ref,)).fetchone()
    return row[0] if row else None


def chapter_ref(conn, node_id: int) -> tuple[str, str, str] | None:
    from isnady.core import works

    node = works.node(conn, node_id)
    if not node:
        return None
    work = conn.execute("SELECT key, title FROM works WHERE id = ?", (node["work_id"],)).fetchone()
    from isnady.core import titles

    book = titles.book(work[0], work[1])
    label = f"{node['label']}. " if node["label"] else ""
    return f"{work[0]}:{node['label'] or node_id}", f"{book} › {label}{node['title'] or ''}", ""


def resolve_chapter(conn, ref: str) -> int | None:
    key, _, label = ref.partition(":")
    row = conn.execute("""SELECT n.id FROM work_nodes n JOIN works w ON w.id = n.work_id
                          WHERE w.key = ? AND n.label = ? AND n.kind IN ('volume', 'kitab', 'bab', 'section')""",
                       (key, label)).fetchone()
    return row[0] if row else None
