"""The interface catalogs (I1).

    python tools/i18n.py extract           every t("…"), n_("…", "…") and N_("…") of the code → src/isnady/assets/i18n/en.json
    python tools/i18n.py check [CODE …]    what each language still lacks, and translations whose {fields} differ
    python tools/i18n.py missing CODE      the English texts CODE lacks, as JSON (to translate)
    python tools/i18n.py merge CODE FILE   add the translations of FILE ({"English": "translation"}) to CODE's catalog
    python tools/i18n.py prune             drop from every catalog the texts the code no longer has
    python tools/i18n.py titles CODE [DB]  the chapter titles of the imported books that CODE's titles table
                                           (assets/i18n/titles/CODE.json) lacks, as JSON (to translate)
    python tools/i18n.py titles-merge CODE FILE   add {"English title": "title"} to that table

The English text is the key (core/i18n.py). A catalog keeps its keys in the order of en.json.
"""

from __future__ import annotations

import ast
import json
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "isnady"
OUT = SRC / "assets" / "i18n"
MARKERS = {"t", "tr", "N_", "n_"}


def _name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _literal(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract() -> list[tuple[str, str]]:
    """(text, where) for every marked text, in the order of the files and lines."""
    found: dict[str, str] = {}
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _name(n.func) in MARKERS]
        for call in sorted(calls, key=lambda c: (c.lineno, c.col_offset)):
            texts = call.args[:2] if _name(call.func) == "n_" else call.args[:1]
            for arg in texts:
                text = _literal(arg)
                if text and text.strip() and text not in found:
                    found[text] = f"{path.relative_to(SRC)}:{call.lineno}"
    return list(found.items())


def fields(text: str) -> set[str]:
    try:
        return {f for _l, f, _s, _c in string.Formatter().parse(text) if f is not None}
    except ValueError:
        return {"<broken>"}


# the cases of a name a language may put on it in place of the name itself (core.isnad.chain_in_words: Turkish
# "{name_abl}" for "from {name}" — Leys'ten, Ebû Hüreyre'den)
CASES = ("abl", "acc", "dat")


def same_fields(source: str, translation: str) -> bool:
    """The translation fills the same {fields} as the English, a field in one of its grammatical cases counting as
    the field: "from {name}" → "{name_abl}"."""
    want, have = fields(source), fields(translation)
    bare = {f.rsplit("_", 1)[0] if f.rsplit("_", 1)[-1] in CASES else f for f in have}
    return want == have or (want == bare and all(f in want or f.rsplit("_", 1)[0] in want for f in have))


def load(code: str) -> dict[str, str]:
    path = OUT / f"{code}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(code: str, data: dict[str, str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    order = list(load("en"))
    keyed = {k: data[k] for k in order if k in data}
    keyed.update({k: v for k, v in data.items() if k not in keyed})
    (OUT / f"{code}.json").write_text(json.dumps(keyed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    if cmd == "extract":
        items = extract()
        (OUT).mkdir(parents=True, exist_ok=True)
        (OUT / "en.json").write_text(json.dumps({k: k for k, _w in items}, ensure_ascii=False, indent=1) + "\n",
                                     encoding="utf-8")
        print(f"{len(items)} texts, {sum(len(k) for k, _w in items):,} characters → {OUT / 'en.json'}")
        return 0
    if cmd == "check":
        sys.path.insert(0, str(ROOT / "src"))
        from isnady.core.i18n import LANGUAGES

        keys = list(load("en"))
        codes = argv[1:] or [c for c in LANGUAGES if c != "en"]
        bad = 0
        for code in codes:
            data = load(code)
            have = [k for k in keys if data.get(k)]
            wrong = [k for k in have if not same_fields(k, data[k])]
            print(f"{code:4} {len(have):5} of {len(keys)}  ({len(have) / max(1, len(keys)):.0%})"
                  + (f"   {len(wrong)} with other {{fields}}" if wrong else ""))
            for k in wrong[:10]:
                print(f"      {k[:70]!r} → {data[k][:70]!r}")
            bad += len(wrong)
        return 1 if bad else 0
    if cmd == "missing":
        data = load(argv[1])
        print(json.dumps({k: "" for k in load("en") if not data.get(k)}, ensure_ascii=False, indent=1))
        return 0
    if cmd == "merge":
        data = load(argv[1])
        new = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        known = set(load("en"))
        unknown = [k for k in new if k not in known]
        data.update({k: v for k, v in new.items() if v and k in known})
        save(argv[1], data)
        print(f"{argv[1]}: {len(new) - len(unknown)} merged" + (f", {len(unknown)} not in the code (left out)"
                                                               if unknown else ""))
        for k in unknown[:10]:
            print("   ", repr(k[:80]))
        return 0
    if cmd == "prune":
        keys = set(load("en"))
        for path in sorted(OUT.glob("*.json")):
            if path.stem == "en":
                continue
            data = load(path.stem)
            kept = {k: v for k, v in data.items() if k in keys}
            if len(kept) != len(data):
                save(path.stem, kept)
                print(f"{path.stem}: {len(data) - len(kept)} dropped")
        return 0
    if cmd in ("titles", "titles-merge"):
        path = OUT / "titles" / f"{argv[1]}.json"
        table = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"chapters": {}, "books": {}}
        if cmd == "titles-merge":
            new = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
            table.setdefault("chapters", {}).update({" ".join(k.split()): v for k, v in new.items() if v})
            path.write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"{argv[1]}: {len(new)} titles merged")
            return 0
        import sqlite3

        sys.path.insert(0, str(ROOT / "src"))
        from isnady.data.paths import db_path

        conn = sqlite3.connect(argv[2] if len(argv) > 2 else str(db_path()))
        have = table.get("chapters", {})
        missing = {}
        for (title,) in conn.execute("""SELECT DISTINCT t.title FROM section_titles t JOIN editions e
                                        ON e.id = t.edition_id WHERE e.language = 'English'"""):
            key = " ".join((title or "").split())
            if key and key not in have:
                missing[key] = ""
        print(json.dumps(missing, ensure_ascii=False, indent=1))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
