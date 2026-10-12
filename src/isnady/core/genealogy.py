"""Genealogies (GEN1): the family trees isnady draws — Qt-free; the Genealogies page and `iy tree` use it.

Bayram (2026-10-11): "Hani râvilerin, âlimlerin şecereleri? Peygamberlerin soy ağacı?"

Four trees:
1. **The prophets** — from Adam to Muhammad ﷺ, as the classical historians give it (Ibn Hisham, Ibn Sa'd,
   al-Tabari, Ibn Kathir); a link whose generations are not known is a *gap*, a report the sources differ on is
   *disputed*, each with a note (`assets/genealogy/trees.json`, written for isnady).
2. **Quraysh** — the Prophet's family ﷺ, the four caliphs' lineages joining his, the Umayyads, the Imams of the
   Shia (each tradition's figures shown as they are; nothing is weighed).
3. **A narrator's family** — read from the narrators' own names: "X b. Y b. Z" is the son of "Y b. Z" when exactly
   one narrator of the same tradition has that name and his generation is not later. A tree found this way is a
   reading of the names, said so on the page, not a genealogist's verdict.
4. **A narrator's line of learning** (al-silsila al-'ilmiyya) — his teachers above him and his students below,
   counted from the imported chains (the same relation as the Narrators page).
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

from isnady.core import i18n
from isnady.core.normalize import normalize


@dataclass
class Node:
    id: str
    names: dict                     # en, tr, ar
    kind: str = "person"            # prophet, caliph, imam, person, narrator
    parent: str | None = None
    gap: bool = False               # generations between it and its parent not known (drawn dashed)
    disputed: dict | None = None    # a note: the reports differ
    note: dict | None = None
    person_id: int | None = None    # a narrator in the database
    count: int | None = None        # how often (teacher / student links)
    children: list[str] = field(default_factory=list)

    def name(self, lang: str | None = None) -> str:
        code = lang or i18n.language()
        if code == "tr":
            return self.names.get("tr") or self.names.get("en") or ""
        if code in ("ar", "fa", "prs", "ps", "ur", "ug"):
            return self.names.get("ar") or self.names.get("en") or ""
        return self.names.get("en") or self.names.get("tr") or ""

    def text(self, which: str, lang: str | None = None) -> str:
        d = getattr(self, which) or {}
        code = lang or i18n.language()
        return d.get(code) or d.get("en") or ""


@dataclass
class Tree:
    key: str
    title: str
    root: str
    nodes: dict[str, Node]
    up: str | None = None           # for a line of learning: the root of the teachers' side (drawn above)

    def walk(self, start: str | None = None, depth: int = 0):
        """(node, depth) in order, the root first."""
        node = self.nodes[start or self.root]
        yield node, depth
        for c in node.children:
            yield from self.walk(c, depth + 1)


# ---------------------------------------------------------------------- the written trees
@lru_cache(maxsize=1)
def _data() -> dict:
    path = resources.files("isnady.assets").joinpath("genealogy", "trees.json")
    return json.loads(path.read_text(encoding="utf-8"))


WRITTEN = ("prophets", "quraysh")


def written(key: str, lang: str | None = None) -> Tree:
    d = _data()["trees"][key]
    code = lang or i18n.language()
    nodes = {}
    for x in d["nodes"]:
        nodes[x["id"]] = Node(x["id"], {"en": x["en"], "tr": x["tr"], "ar": x["ar"]}, x.get("kind", "person"),
                              x.get("parent"), bool(x.get("gap")), x.get("disputed"), x.get("note"))
    for n in nodes.values():
        if n.parent:
            nodes[n.parent].children.append(n.id)
    title = d["title"].get(code) or d["title"]["en"]
    return Tree(key, title, d["root"], nodes)


def sources() -> str:
    return _data()["_about"]


def path_to(tree: Tree, node_id: str) -> list[Node]:
    """The line from the root down to a node."""
    out, current = [], tree.nodes.get(node_id)
    while current:
        out.insert(0, current)
        current = tree.nodes.get(current.parent) if current.parent else None
    return out


def find(tree: Tree, text: str) -> list[Node]:
    words = normalize(text).casefold().split()
    out = []
    for n in tree.nodes.values():
        hay = normalize(" ".join(n.names.values())).casefold()
        if words and all(w in hay for w in words):
            out.append(n)
    return out


# ---------------------------------------------------------------------- narrators' families, from their names
_NAME_HEAD = ("عبد", "عبيد", "أبو", "أبي", "أبا", "أم")


def _segments(name: str) -> list[str]:
    """The names of a nasab: "يحيى بن سعيد بن قيس الأنصاري" → ["يحيى", "سعيد", "قيس"] (normalised; nisbas dropped)."""
    from isnady.core.rijal import display_name

    parts = re.split(r"\s+(?:بن|ابن|بنت)\s+", display_name(name).strip())
    out = []
    for p in parts:
        words = [w for w in p.split() if w]
        if not words:
            break
        take = 2 if len(words) > 1 and (words[0] in _NAME_HEAD or words[1] == "الله") else 1
        out.append(normalize(" ".join(words[:take])))
    return out


def _family_edges(conn: sqlite3.Connection) -> tuple[dict, dict]:
    """(father of, sons of): read from every narrator's name once per change of the database and kept
    (core.cache: in memory and cache/family-edges.json)."""
    from isnady.core import cache

    return cache.kept(conn, "family-edges", _family_edges_counted)


def _family_edges_counted(conn: sqlite3.Connection) -> tuple[dict, dict]:
    people = conn.execute("SELECT id, name_ar, COALESCE(tradition, 'sunni'), tabaqa FROM persons").fetchall()
    segs = {pid: _segments(name or "") for pid, name, _t, _tb in people}
    info = {pid: (trad, tab) for pid, _n, trad, tab in people}
    index: dict = {}
    for pid, s in segs.items():
        for k in (2, 3):
            if len(s) >= k:
                index.setdefault((info[pid][0], tuple(s[:k])), []).append(pid)
    father: dict[int, int] = {}
    for pid, s in segs.items():
        if len(s) < 3:                                  # "X b. Y" alone names too many fathers
            continue
        want = tuple(s[1:4]) if len(s) >= 4 else tuple(s[1:3])
        found = [c for c in index.get((info[pid][0], want), []) if c != pid]
        ts = info[pid][1]
        # a father of a later generation than his son is not him; of two of the same name, the one who can be
        found = [c for c in found if not (info[c][1] and ts and info[c][1] > ts)]
        if len(found) > 1 and ts:
            earlier = [c for c in found if info[c][1] and info[c][1] < ts]
            found = earlier if len(earlier) == 1 else found
        if len(found) != 1:
            continue
        f = found[0]
        father[pid] = f
    sons: dict[int, list[int]] = {}
    for s, f in father.items():
        sons.setdefault(f, []).append(s)
    return father, sons


def family(conn: sqlite3.Connection, person_id: int) -> Tree | None:
    """A narrator's family as his and his kin's names give it: his forefathers (as far as they are narrators)
    and every descendant of the eldest of them. None when the names show no kin."""
    father, sons = _family_edges(conn)
    top = person_id
    seen = {top}
    while top in father and father[top] not in seen:
        top = father[top]
        seen.add(top)
    if top == person_id and person_id not in sons:
        return None
    nodes: dict[str, Node] = {}

    def add(pid: int, parent: str | None):
        node = _person_node(conn, pid, parent)
        nodes[node.id] = node
        if parent:
            nodes[parent].children.append(node.id)
        for s in sorted(sons.get(pid, [])):
            if f"p{s}" not in nodes:
                add(s, node.id)
    add(top, None)
    return Tree("family", i18n.t("Family"), f"p{top}", nodes)


def family_count(conn: sqlite3.Connection) -> int:
    father, _sons = _family_edges(conn)
    return len(father)


def _person_node(conn: sqlite3.Connection, pid: int, parent: str | None, count: int | None = None) -> Node:
    from isnady.core import narrators

    row = conn.execute("SELECT name_ar FROM persons WHERE id = ?", (pid,)).fetchone()
    reading, arabic = narrators.reading(conn, pid, row[0] if row else "")
    return Node(f"p{pid}", {"en": reading or arabic, "tr": reading or arabic, "ar": arabic}, "narrator", parent,
                person_id=pid, count=count)


# ---------------------------------------------------------------------- a narrator's line of learning
def learning(conn: sqlite3.Connection, person_id: int, depth: int = 2, width: int = 4) -> Tree:
    """His teachers (and theirs) above him, his students (and theirs) below — the most frequent `width` at each
    step, from the imported chains. Two trees joined at him: `up` is the teachers' side."""
    from isnady.core import narrators

    nodes: dict[str, Node] = {}
    root = _person_node(conn, person_id, None)
    nodes[root.id] = root
    used = {person_id}

    def grow(pid: int, node_id: str, side: str, level: int, prefix: str):
        if level >= depth:
            return
        rel = narrators.relations(conn, pid, limit=width * 3)[side]
        for r in [r for r in rel if r["id"] not in used][:width]:
            used.add(r["id"])
            child = _person_node(conn, r["id"], node_id, r["count"])
            child.id = f"{prefix}{r['id']}"
            nodes[child.id] = child
            nodes[node_id].children.append(child.id)
            grow(r["id"], child.id, side, level + 1, prefix)

    # the teachers hang from a copy of the root, so the two sides can be laid out apart and joined at him
    up = Node("up", root.names, "narrator", None, person_id=person_id)
    nodes["up"] = up
    grow(person_id, "up", "teachers", 0, "t")
    grow(person_id, root.id, "students", 0, "s")
    return Tree("learning", i18n.t("Line of learning"), root.id, nodes, up="up")


# ---------------------------------------------------------------------- text (the command line)
def as_text(tree: Tree, lang: str = "en") -> str:
    lines = [tree.title]
    if tree.up:
        lines.append("  " + i18n.t("teachers (above):"))
        for n, d in list(tree.walk(tree.up))[1:]:
            lines.append("    " + "  " * (d - 1) + "↑ " + _line(n, lang))
        lines.append("  " + i18n.t("students (below):"))
    for n, d in tree.walk():
        lines.append("  " + "  " * d + ("└ " if d else "") + _line(n, lang))
    return "\n".join(lines)


def _line(n: Node, lang: str) -> str:
    text = n.name(lang)
    if n.names.get("ar") and lang != "ar" and n.names["ar"] != text:
        text += f"  {n.names['ar']}"
    if n.count:
        text += f"  ({n.count})"
    if n.gap:
        text += "   [" + i18n.t("generations between not known") + "]"
    if n.disputed:
        text += "   [" + i18n.t("disputed") + "]"
    return text
