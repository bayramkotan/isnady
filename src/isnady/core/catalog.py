"""Sources isnady knows about, and sources the user adds.

BUILT-IN entries come from the REPOSITORY chosen in Settings → Data sources (core.repositories): by default isnady's
own repository (bayramkotan/isnady-data), which lists every Sunni and Shia collection and rijal work isnady reads;
optionally one of the datasets others publish (fawazahmed0, Open Hadith Data, hadith-json, LK corpus, Hadith-Data-Sets,
Hugging Face meeAtif, Thaqalayn, OpenITI) or a repository the user adds. They are imported with one click (or
`iy catalog import ID`).

USER entries (User Resources) are kept in user_sources.json in the data
folder: a title, a format, a file or URL, a licence and the KIND of
authentication. Credentials are never stored; they are asked for at import.
"""

import json
import re
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field

from isnady.core.imports import ImportRequest, remove_source, run_import, run_many
from isnady.data import db
from isnady.data.fetch import Auth, ResourceError
from isnady.data.paths import data_dir

FAWAZ_INDEX = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions.json"
FAWAZ_SOURCE = "fawazahmed0/hadith-api"
FAWAZ_KEY = "fawazahmed0-hadith-api"

LANGUAGE_NAMES = {"ara": "Arabic", "tur": "Turkish", "eng": "English", "urd": "Urdu", "ind": "Indonesian",
                  "ben": "Bengali", "fra": "French", "rus": "Russian", "tam": "Tamil"}
DEFAULT_LANGUAGES = ["ara", "tur", "eng"]


@dataclass
class Entry:
    id: str
    title: str
    kind: str                       # hadith | rijal
    format_id: str
    location: str
    description: str
    license: str | None
    source_name: str
    source_key: str
    book: str | None = None
    languages: list[str] = field(default_factory=list)       # offered
    builtin: bool = True
    auth_kind: str = "none"
    key_name: str | None = None
    key_in: str = "header"
    # from a repository catalog
    title_ar: str = ""
    tradition: str = "sunni"        # sunni | shia | other
    repo: str = ""                  # the repository it is listed in
    mapping: dict | None = None     # a table's columns (format "table")
    parts: list | None = None       # a book in several files (chapters, volumes)
    fallback: dict | None = None    # {"format", "location"}: the origin, when the repository's copy cannot be read
    origin_name: str = ""
    origin_url: str = ""
    aliases: list[str] = field(default_factory=list)
    hadith: int | None = None       # how many, as the source says (before import)


def entry_from_catalog(raw: dict, repo, base: str) -> Entry:
    """A catalog entry (schema isnady-catalog/1) of a repository, its locations made absolute."""
    from isnady.core.repositories import absolute

    parts = raw.get("parts")
    if parts:
        parts = [dict(p, location=absolute(base, p["location"])) if isinstance(p, dict) else absolute(base, p)
                 for p in parts]
    origin = raw.get("origin") or {}
    return Entry(
        id=raw["id"], title=raw["title"], kind=raw.get("kind", "hadith"), format_id=raw["format"],
        location=absolute(base, raw["location"]), description=raw.get("description", ""),
        license=raw.get("license"), source_name=raw.get("source_name") or origin.get("name") or raw["title"],
        source_key=raw.get("source_key") or raw["id"], book=raw.get("book"), languages=raw.get("languages", []),
        builtin=True, title_ar=raw.get("title_ar", ""), tradition=raw.get("tradition", "sunni"), repo=repo.id,
        mapping=raw.get("mapping"), parts=parts, fallback=raw.get("fallback"), origin_name=origin.get("name", ""),
        origin_url=origin.get("url", ""), aliases=raw.get("aliases", []), hadith=raw.get("hadith"))


def builtin_entries(repo_id: str | None = None) -> list[Entry]:
    """The sources of a repository: the one chosen in Settings → Data sources unless another is named."""
    from isnady.core import repositories

    repo = repositories.find(repo_id) if repo_id else repositories.selected()
    if repo is None:
        raise KeyError(f"No repository '{repo_id}'. See: iy repo list")
    return repositories.entries(repo)


# ------------------------------------------------------------------ user entries
def _user_file():
    return data_dir() / "user_sources.json"


def user_entries() -> list[Entry]:
    try:
        rows = json.loads(_user_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for r in rows if isinstance(rows, list) else []:
        try:
            out.append(Entry(**{**r, "builtin": False}))
        except TypeError:
            continue
    return out


def _save_user(entries: list[Entry]) -> None:
    rows = [{k: v for k, v in asdict(e).items() if k != "builtin"} for e in entries]
    path = _user_file()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def add_user_entry(title: str, format_id: str, location: str, license: str | None = None,
                   auth_kind: str = "none", key_name: str | None = None, key_in: str = "header",
                   book: str | None = None) -> Entry:
    from isnady.data.importers.base import get_importer, slugify

    get_importer(format_id)                      # raises KeyError for an unknown format
    if not title.strip() or not location.strip():
        raise ValueError("A user source needs a title and a file or URL.")
    if auth_kind not in ("none", "basic", "bearer", "apikey"):
        raise ValueError("Authentication must be none, basic, bearer or apikey.")
    entry = Entry(id=f"user-{uuid.uuid4().hex[:8]}", title=title.strip(), kind="hadith", format_id=format_id,
                  location=location.strip(), description="Added by you.", license=(license or None),
                  source_name=title.strip(), source_key=slugify(title.strip()), book=book, builtin=False,
                  auth_kind=auth_kind, key_name=key_name, key_in=key_in)
    entries = user_entries()
    entries.append(entry)
    _save_user(entries)
    return entry


def delete_user_entry(entry_id: str) -> bool:
    entries = user_entries()
    kept = [e for e in entries if e.id != entry_id]
    _save_user(kept)
    return len(kept) != len(entries)


def all_entries() -> list[Entry]:
    return builtin_entries() + user_entries()


def find(entry_id: str) -> Entry | None:
    """A source by its id: in the chosen repository first, then in every other; "repo/id" names the repository."""
    from isnady.core import repositories

    entry_id = (entry_id or "").strip()
    if "/" in entry_id:
        rid, _, eid = entry_id.partition("/")
        return next((e for e in builtin_entries(rid) if eid in (e.id, *e.aliases)), None) if repositories.find(rid) \
            else None
    order = [repositories.selected()] + [r for r in repositories.all_repositories()
                                         if r.id != repositories.selected().id]
    for repo in order:
        try:
            found = next((e for e in repositories.entries(repo) if entry_id in (e.id, *e.aliases)), None)
        except ResourceError:
            continue
        if found:
            return found
    return next((e for e in user_entries() if e.id == entry_id), None)


# ------------------------------------------------------------------ status and actions
def status(conn: sqlite3.Connection, entry: Entry) -> dict:
    """What of this entry is in the database now."""
    src = conn.execute("SELECT id, imported_at, tier FROM sources WHERE key = ?", (entry.source_key,)).fetchone()
    if src is None:
        return {"imported": False, "languages": [], "when": None, "count": 0}
    if entry.book:
        langs = [r[0] for r in conn.execute(
            """SELECT DISTINCT e.language FROM editions e JOIN collections c ON c.id = e.collection_id
               WHERE e.source_id = ? AND c.key = ? ORDER BY e.language""", (src["id"], entry.book))]
        count = conn.execute(
            "SELECT COUNT(*) FROM hadiths h JOIN collections c ON c.id = h.collection_id WHERE c.key = ?",
            (entry.book,)).fetchone()[0]
        return {"imported": bool(langs), "languages": langs, "when": src["imported_at"], "count": count,
                "tier": src["tier"]}
    if entry.kind == "rijal":
        count = conn.execute("SELECT COUNT(*) FROM persons WHERE source_id = ?", (src["id"],)).fetchone()[0]
    else:
        count = conn.execute("SELECT COALESCE(SUM(text_count), 0) FROM editions WHERE source_id = ?",
                             (src["id"],)).fetchone()[0]
    return {"imported": True, "languages": [], "when": src["imported_at"], "count": count, "tier": src["tier"]}


def request_for(entry: Entry, languages: list[str] | None = None, auth: Auth | None = None,
                use_fallback: bool = False) -> ImportRequest:
    options: dict = {}
    format_id, location = entry.format_id, entry.location
    if use_fallback and entry.fallback:
        format_id, location = entry.fallback.get("format", format_id), entry.fallback["location"]
    if format_id == "table":
        options = {"mapping": entry.mapping or {}, "book": entry.book or entry.id, "title": entry.title,
                   "tradition": entry.tradition, "source_key": entry.source_key}
        if entry.parts and not use_fallback:
            options["parts"] = entry.parts
    elif entry.book and entry.builtin and entry.languages:
        chosen = [c for c in (languages or DEFAULT_LANGUAGES) if c in entry.languages] or ["ara"]
        options = {"books": [entry.book], "languages": chosen}
    elif entry.book:
        options = {"books": [entry.book], "languages": list(languages or [])}
    return ImportRequest(format_id=format_id, location=location, name=entry.source_name,
                         license=entry.license, origin="builtin" if entry.builtin else "user",
                         auth=auth or Auth(), options=options)


def _set_tradition(conn: sqlite3.Connection, entry: Entry) -> None:
    """The collection's tradition and name as the catalog gives them (Shia books apart from Sunni ones)."""
    if entry.kind == "hadith" and entry.book and entry.builtin:
        with conn:
            conn.execute("UPDATE collections SET tradition = ? WHERE key = ?", (entry.tradition, entry.book))


def import_all(conn: sqlite3.Connection, languages: dict[str, list[str]] | list[str] | None = None, progress=None):
    """Every built-in source: hadith collections first, then the rijal works that identify their narrators.

    languages: one list for every book, or {entry id: [codes]}; missing = the defaults.
    """
    entries = sorted(builtin_entries(), key=lambda e: e.kind != "hadith")
    requests = []
    for e in entries:
        langs = languages.get(e.id) if isinstance(languages, dict) else languages
        requests.append((e.title, request_for(e, langs)))
    imported, failed, narrators = run_many(conn, requests, progress)
    # a repository's own copy not reachable (not published yet, offline mirror): the origin, once more
    by_title = {e.title: e for e in entries}
    retry = [(label, request_for(by_title[label], languages.get(by_title[label].id) if isinstance(languages, dict)
                                 else languages, use_fallback=True))
             for label, _why in failed if by_title.get(label) and by_title[label].fallback]
    if retry:
        again, _still, narrators = run_many(conn, retry, progress)
        done = {label for label, _r in again}
        imported += again
        failed = [f for f in failed if f[0] not in done]
    for e in entries:
        _set_tradition(conn, e)
    return imported, failed, narrators


def import_entry(conn: sqlite3.Connection, entry: Entry, languages: list[str] | None = None,
                 auth: Auth | None = None, progress=None):
    # a user's own file: its language comes from the file itself, never from our defaults (request_for)
    try:
        result = run_import(conn, request_for(entry, languages, auth), progress)
    except ResourceError as exc:
        if not entry.fallback:
            raise
        if progress:
            progress(f"The repository's copy could not be read ({exc}); reading the original")
        result = run_import(conn, request_for(entry, languages, auth, use_fallback=True), progress)
    _set_tradition(conn, entry)
    return result


def remove_entry(conn: sqlite3.Connection, entry: Entry) -> bool:
    """Remove what this entry imported (for one book of a shared source: that book only)."""
    src = conn.execute("SELECT id FROM sources WHERE key = ?", (entry.source_key,)).fetchone()
    if src is None:
        return False
    if entry.book:
        with conn:
            removed = conn.execute(
                """DELETE FROM editions WHERE source_id = ? AND collection_id IN
                   (SELECT id FROM collections WHERE key = ?)""", (src["id"], entry.book)).rowcount
            conn.execute("DELETE FROM grades WHERE source_id = ? AND hadith_id IN (SELECT h.id FROM hadiths h "
                         "JOIN collections c ON c.id = h.collection_id WHERE c.key = ?)", (src["id"], entry.book))
            conn.execute("DELETE FROM isnads WHERE source_id = ? AND hadith_id IN (SELECT h.id FROM hadiths h "
                         "JOIN collections c ON c.id = h.collection_id WHERE c.key = ?)", (src["id"], entry.book))
            if not conn.execute("SELECT 1 FROM editions WHERE source_id = ?", (src["id"],)).fetchone():
                conn.execute("DELETE FROM sources WHERE id = ?", (src["id"],))
        db.cleanup(conn)
        return bool(removed)
    return remove_source(conn, entry.source_key)


def language_label(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


def code_for(language_name_or_code: str) -> str:
    v = language_name_or_code.strip().lower()
    return next((c for c, n in LANGUAGE_NAMES.items() if n.lower() == v), v if re.fullmatch(r"[a-z]{3}", v) else v)
