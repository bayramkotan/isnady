"""Works: every book isnady can open and read (BR1), of any kind and any depth.

A work is a tree (`work_nodes`): containers (volume, kitab, bab, section) and leaves — a hadith (linked to
`hadiths`), a narrator's entry (text, linked to `persons`), a cross-reference, a paragraph. Hadith collections
are built here from their imported hadith and chapters, again whenever those change (`stamp`); other works
(the Taqrib, later commentaries, fiqh manuals, all of a scholar's works) write their own tree when imported.
The reader, the CLI and isnady's own exchange format all speak this one shape.
"""

import sqlite3

CONTAINERS = ("volume", "kitab", "bab", "section")
LEAVES = ("hadith", "entry", "reference", "paragraph")
KIND_LABELS = {"hadith": "Hadith collection", "rijal": "Narrators (rijal)", "fiqh": "Fiqh", "commentary": "Commentary",
               "other": "Book"}


def _author_of(collection_key: str) -> str | None:
    from isnady.core.scholars import SCHOLARS

    return next((s["id"] for s in SCHOLARS if collection_key in s.get("compiler_of", [])), None)


def ensure_collection_works(conn: sqlite3.Connection) -> int:
    """Build (or rebuild, when the hadith or chapters changed) the tree of every imported hadith collection:
    kitab → hadith, from `sections` and `hadiths.section_number`. Returns how many were rebuilt."""
    rebuilt = 0
    for cid, key, name in conn.execute("SELECT id, key, name FROM collections").fetchall():
        n, top = conn.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM hadiths WHERE collection_id = ?", (cid,)).fetchone()
        chapters = conn.execute("SELECT COUNT(*) FROM sections WHERE collection_id = ?", (cid,)).fetchone()[0]
        stamp = f"collection|{n}|{top}|{chapters}"
        row = conn.execute("SELECT id, stamp FROM works WHERE key = ?", (key,)).fetchone()
        if row and row[1] == stamp:
            continue
        with conn:
            if row:
                conn.execute("DELETE FROM works WHERE id = ?", (row[0],))
            wid = conn.execute("INSERT INTO works (key, kind, title, author, collection_id, stamp) VALUES (?, 'hadith', ?, ?, ?, ?)",
                               (key, name, _author_of(key), cid, stamp)).lastrowid
            titles = {}
            for number, title in conn.execute(
                    """SELECT s.number, t.title FROM sections s LEFT JOIN section_titles t ON t.section_id = s.id
                       WHERE s.collection_id = ? ORDER BY s.number, t.edition_id""", (cid,)):
                if title and title.strip() and number not in titles:
                    titles[number] = title.strip()
            node_of = {}
            # chapter 0 without a title is how the source marks "no chapter": not a first chapter, but the last
            numbers = sorted({r[0] for r in conn.execute(
                "SELECT DISTINCT section_number FROM hadiths WHERE collection_id = ?", (cid,))
                if r[0] is not None and not (r[0] == 0 and not titles.get(0))})
            for ordinal, number in enumerate(numbers):
                node_of[number] = conn.execute(
                    "INSERT INTO work_nodes (work_id, parent_id, ordinal, kind, label, title) VALUES (?, NULL, ?, 'kitab', ?, ?)",
                    (wid, ordinal, str(number), titles.get(number) or f"Chapter {number}")).lastrowid
            other = None
            counters: dict = {}
            rows = []
            for hid, num, section in conn.execute(
                    "SELECT id, number, section_number FROM hadiths WHERE collection_id = ? ORDER BY number_sort", (cid,)).fetchall():
                parent = node_of.get(section)
                if parent is None:
                    if other is None:
                        other = conn.execute("INSERT INTO work_nodes (work_id, parent_id, ordinal, kind, title) VALUES "
                                             "(?, NULL, ?, 'kitab', 'Without a chapter in the source')",
                                             (wid, len(numbers))).lastrowid
                    parent = other
                counters[parent] = counters.get(parent, 0) + 1
                rows.append((wid, parent, counters[parent], num, hid))
            conn.executemany("INSERT INTO work_nodes (work_id, parent_id, ordinal, kind, label, hadith_id) "
                             "VALUES (?, ?, ?, 'hadith', ?, ?)", rows)
        rebuilt += 1
    return rebuilt


def list_works(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT w.id, w.key, w.kind, w.title, w.title_ar, w.author,
                  (SELECT COUNT(*) FROM work_nodes n WHERE n.work_id = w.id AND n.kind IN ('hadith', 'entry', 'paragraph')),
                  (SELECT COUNT(*) FROM work_nodes n WHERE n.work_id = w.id AND n.parent_id IS NULL)
           FROM works w ORDER BY (w.kind != 'hadith'), w.title""").fetchall()
    return [{"id": r[0], "key": r[1], "kind": r[2], "title": r[3], "title_ar": r[4], "author": r[5],
             "leaves": r[6], "chapters": r[7]} for r in rows]


def find_work(conn: sqlite3.Connection, key: str) -> dict | None:
    return next((w for w in list_works(conn) if w["key"] == key), None)


def containers(conn: sqlite3.Connection, work_id: int, parent_id: int | None = None) -> list[dict]:
    """The chapters (non-leaf nodes) under a parent, with how many leaves each holds directly."""
    rows = conn.execute(
        f"""SELECT n.id, n.kind, n.label, n.title,
                   (SELECT COUNT(*) FROM work_nodes c WHERE c.parent_id = n.id AND c.kind IN ({','.join('?' * len(LEAVES))})),
                   (SELECT COUNT(*) FROM work_nodes c WHERE c.parent_id = n.id AND c.kind IN ({','.join('?' * len(CONTAINERS))}))
            FROM work_nodes n WHERE n.work_id = ? AND n.parent_id {'IS NULL' if parent_id is None else '= ?'}
              AND n.kind IN ({','.join('?' * len(CONTAINERS))}) ORDER BY n.ordinal""",
        (*LEAVES, *CONTAINERS, work_id, *(() if parent_id is None else (parent_id,)), *CONTAINERS)).fetchall()
    return [{"id": r[0], "kind": r[1], "label": r[2], "title": r[3], "leaves": r[4], "subchapters": r[5]} for r in rows]


def node(conn: sqlite3.Connection, node_id: int) -> dict | None:
    r = conn.execute("SELECT id, work_id, parent_id, ordinal, kind, label, title FROM work_nodes WHERE id = ?", (node_id,)).fetchone()
    return None if r is None else {"id": r[0], "work_id": r[1], "parent_id": r[2], "ordinal": r[3], "kind": r[4],
                                   "label": r[5], "title": r[6]}


def path(conn: sqlite3.Connection, node_id: int) -> list[dict]:
    out, current = [], node(conn, node_id)
    while current:
        out.insert(0, current)
        current = node(conn, current["parent_id"]) if current["parent_id"] else None
    return out


def leaves(conn: sqlite3.Connection, node_id: int, offset: int = 0, limit: int = 1000) -> tuple[list[dict], int]:
    """The readable items directly under a chapter, in order: (items, total)."""
    total = conn.execute(f"SELECT COUNT(*) FROM work_nodes WHERE parent_id = ? AND kind IN ({','.join('?' * len(LEAVES))})",
                         (node_id, *LEAVES)).fetchone()[0]
    rows = conn.execute(
        f"""SELECT id, kind, label, title, hadith_id, person_id, text FROM work_nodes
            WHERE parent_id = ? AND kind IN ({','.join('?' * len(LEAVES))}) ORDER BY ordinal LIMIT ? OFFSET ?""",
        (node_id, *LEAVES, limit, offset)).fetchall()
    return [{"id": r[0], "kind": r[1], "label": r[2], "title": r[3], "hadith_id": r[4], "person_id": r[5], "text": r[6]}
            for r in rows], total


def reading_order(conn: sqlite3.Connection, work_id: int) -> list[int]:
    """Every chapter that holds readable items, in reading order (for previous / next)."""
    out = []

    def walk(parent):
        for c in containers(conn, work_id, parent):
            if c["leaves"]:
                out.append(c["id"])
            if c["subchapters"]:
                walk(c["id"])
    walk(None)
    return out


def chapter_of_hadith(conn: sqlite3.Connection, hadith_id: int) -> int | None:
    r = conn.execute("SELECT parent_id FROM work_nodes WHERE hadith_id = ? LIMIT 1", (hadith_id,)).fetchone()
    return r[0] if r else None


def chapter_of_person(conn: sqlite3.Connection, person_id: int) -> int | None:
    r = conn.execute("SELECT parent_id FROM work_nodes WHERE person_id = ? AND kind = 'entry' LIMIT 1", (person_id,)).fetchone()
    return r[0] if r else None
