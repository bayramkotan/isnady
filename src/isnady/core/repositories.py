"""Data repositories: where isnady finds its sources.

A REPOSITORY is a catalog (catalog.json, schema isnady-catalog/1) listing hadith collections and rijal works —
where each file is, its format, its licence, its tradition. isnady's own repository, bayramkotan/isnady-data, is the
DEFAULT: it lists every source isnady can read, Sunni and Shia. The datasets others publish on GitHub and Hugging Face
(fawazahmed0, Open Hadith Data, hadith-json, LK corpus, Hadith-Data-Sets, meeAtif, Thaqalayn, OpenITI) are OPTIONAL
repositories whose catalogs ship with isnady (they have none of their own). The user can add any repository that
has a catalog — a GitHub or Hugging Face repository, a URL, or a folder — choose it, and import from it.

The default repository is read from the network and kept in data_dir()/repos/ (refreshed after a day or on
request); without the network, or before the repository is published, the copy shipped with isnady is used.
Built with tools/build_data_repo.py.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from isnady.data.fetch import ResourceError, is_url, read_bytes, resolve
from isnady.data.paths import data_dir

SCHEMA = "isnady-catalog/1"
DEFAULT_ID = "isnady"
REFRESH_SECONDS = 24 * 3600
CATALOG_TIMEOUT = 10            # seconds: a catalog is small; an unreachable server must not hold the window
ORDER = ["isnady", "fawazahmed0", "thaqalayn", "open-hadith-data", "hadith-json", "lk-hadith-corpus",
         "huggingface-meeatif", "hadith-data-sets", "openiti"]


@dataclass
class Repository:
    id: str
    name: str
    url: str | None             # where its catalog.json is read from (None: only the copy shipped with isnady)
    homepage: str | None
    description: str
    builtin: bool
    default: bool = False


# ------------------------------------------------------------------ the shipped catalogs
def _bundled() -> dict[str, dict]:
    out = {}
    folder = resources.files("isnady.data") / "repos"
    for item in folder.iterdir():
        if item.name.endswith(".json"):
            cat = json.loads(item.read_text(encoding="utf-8"))
            out[cat["id"]] = cat
    return out


_BUNDLED: dict[str, dict] | None = None


def bundled() -> dict[str, dict]:
    global _BUNDLED
    if _BUNDLED is None:
        _BUNDLED = _bundled()
    return _BUNDLED


def _repo_of(cat: dict, builtin: bool, url: str | None = None) -> Repository:
    return Repository(id=cat["id"], name=cat.get("name") or cat["id"], url=url or cat.get("url"),
                      homepage=cat.get("homepage"), description=cat.get("description", ""), builtin=builtin,
                      default=cat["id"] == DEFAULT_ID)


def builtin_repositories() -> list[Repository]:
    cats = bundled()
    ids = sorted(cats, key=lambda i: (ORDER.index(i) if i in ORDER else len(ORDER), i))
    return [_repo_of(cats[i], True) for i in ids]


# ------------------------------------------------------------------ the user's repositories
def _user_file() -> Path:
    return data_dir() / "user_repositories.json"


def user_repositories() -> list[Repository]:
    try:
        rows = json.loads(_user_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [Repository(**{**r, "builtin": False, "default": False}) for r in rows if isinstance(r, dict) and r.get("id")]


def _save_user(repos: list[Repository]) -> None:
    path = _user_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"id": r.id, "name": r.name, "url": r.url, "homepage": r.homepage, "description": r.description}
            for r in repos]
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def all_repositories() -> list[Repository]:
    return builtin_repositories() + user_repositories()


def find(repo_id: str) -> Repository | None:
    return next((r for r in all_repositories() if r.id == repo_id), None)


def selected() -> Repository:
    """The repository chosen in Settings → Data sources (the default one unless the user chose another)."""
    from isnady import config

    chosen = find(config.get("sources.repository") or DEFAULT_ID)
    return chosen or find(DEFAULT_ID) or builtin_repositories()[0]


def select(repo_id: str) -> Repository:
    from isnady import config

    repo = find(repo_id)
    if repo is None:
        raise KeyError(f"No repository '{repo_id}'. See: iy repo list")
    config.set("sources.repository", "" if repo.id == DEFAULT_ID else repo.id)
    return repo


def candidates(text: str) -> list[str]:
    """Where a repository's catalog may be, from what the user typed: a GitHub or Hugging Face repository, a
    catalog URL, or a folder or file on this computer."""
    text = text.strip().rstrip("/")
    m = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)(?:/(?:tree|blob)/([^/]+)(/.*)?)?$", text)
    if m:
        owner, repo, branch, sub = m.group(1), m.group(2).removesuffix(".git"), m.group(3) or "HEAD", m.group(4) or ""
        base = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}{sub}"
        if base.endswith(".json"):
            return [base]
        return [f"{base}/catalog.json", f"{base}/isnady.json"]
    m = re.match(r"https?://huggingface\.co/datasets/([^/]+)/([^/#?]+)(?:/(?:tree|blob|resolve)/([^/]+)(/.*)?)?$", text)
    if m:
        branch = m.group(3) or "main"
        base = f"https://huggingface.co/datasets/{m.group(1)}/{m.group(2)}/resolve/{branch}{m.group(4) or ''}"
        return [base] if base.endswith(".json") else [f"{base}/catalog.json", f"{base}/isnady.json"]
    if is_url(text):
        return [text] if text.endswith(".json") else [f"{text}/catalog.json", text]
    path = Path(text).expanduser()
    if path.is_dir():
        return [str(path / "catalog.json"), str(path / "isnady.json")]
    return [str(path)]


def _read_catalog(location: str) -> dict:
    try:
        cat = json.loads(read_bytes(location, timeout=CATALOG_TIMEOUT).decode("utf-8-sig"))
    except ValueError as exc:
        raise ResourceError(f"{location} is not a JSON catalog ({exc})") from exc
    if not isinstance(cat, dict) or not isinstance(cat.get("entries"), list):
        raise ResourceError(f"{location} is not an isnady catalog (it needs \"entries\": [...]). "
                            "See tools/build_data_repo.py in isnady for the format.")
    return cat


def _known_external(text: str) -> dict | None:
    """One of the datasets whose catalog ships with isnady, typed by its address: use that catalog."""
    norm = text.lower().rstrip("/").removesuffix(".git")
    for cat in bundled().values():
        home = (cat.get("homepage") or "").lower().rstrip("/")
        if home and norm.startswith(home):
            return cat
    return None


def add_repository(text: str, name: str | None = None) -> Repository:
    """Add a repository by its address. Its catalog is read now, to check it; then it can be chosen."""
    known = _known_external(text)
    if known is not None:
        raise ValueError(f"{known['name']} is already in the list (repository '{known['id']}'). "
                         f"Choose it: iy repo use {known['id']}")
    errors = []
    for location in candidates(text):
        try:
            cat = _read_catalog(location)
        except ResourceError as exc:
            errors.append(str(exc))
            continue
        base = re.sub(r"[^a-z0-9]+", "-", (name or cat.get("name") or cat.get("id") or "repository").lower()).strip("-")
        rid, n = base or "repository", 1
        while find(rid) is not None:
            n += 1
            rid = f"{base}-{n}"
        repo = Repository(id=rid, name=name or cat.get("name") or rid, url=location,
                          homepage=cat.get("homepage") or (text if is_url(text) else None),
                          description=cat.get("description", ""), builtin=False)
        repos = user_repositories()
        repos.append(repo)
        _save_user(repos)
        _cache_path(rid).parent.mkdir(parents=True, exist_ok=True)
        _cache_path(rid).write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
        return repo
    raise ResourceError("No isnady catalog found there. A repository needs a catalog.json listing its sources "
                        "(see tools/build_data_repo.py). Tried:\n  " + "\n  ".join(errors))


def remove_repository(repo_id: str) -> bool:
    repos = user_repositories()
    kept = [r for r in repos if r.id != repo_id]
    if len(kept) == len(repos):
        return False
    _save_user(kept)
    try:
        _cache_path(repo_id).unlink()
    except OSError:
        pass
    from isnady import config

    if config.get("sources.repository") == repo_id:
        config.set("sources.repository", "")
    return True


# ------------------------------------------------------------------ reading a catalog
def _cache_path(repo_id: str) -> Path:
    return data_dir() / "repos" / f"{repo_id}.json"


_LAST: dict[str, tuple[dict, str]] = {}


def catalog(repo: Repository, refresh: bool = False) -> tuple[dict, str]:
    """(catalog, where it came from: "network" | "saved" | "shipped"). Never raises for a built-in repository."""
    if not refresh and repo.id in _LAST:
        return _LAST[repo.id]
    cache = _cache_path(repo.id)
    fresh = cache.exists() and time.time() - cache.stat().st_mtime < REFRESH_SECONDS
    result = None
    if repo.url and (refresh or not fresh):
        try:
            cat = _read_catalog(repo.url)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
            result = (cat, "network")
        except (ResourceError, OSError):
            result = None
    if result is None and cache.exists():
        try:
            result = (json.loads(cache.read_text(encoding="utf-8")), "saved")
        except (OSError, ValueError):
            result = None
    if result is None:
        if repo.id in bundled():
            result = (bundled()[repo.id], "shipped")
        else:
            raise ResourceError(f"The catalog of {repo.name} cannot be read ({repo.url}).")
    _LAST[repo.id] = result
    return result


def base_of(repo: Repository) -> str:
    """What locations in the catalog are relative to: the catalog's own address."""
    if repo.url:
        return repo.url
    return ""


def entries(repo: Repository, refresh: bool = False) -> list:
    """The repository's sources as catalog entries, locations made absolute."""
    from isnady.core.catalog import entry_from_catalog

    cat, _where = catalog(repo, refresh)
    base = base_of(repo)
    out = []
    for raw in cat.get("entries", []):
        try:
            out.append(entry_from_catalog(raw, repo, base))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def absolute(base: str, location: str) -> str:
    return resolve(base, location) if base and not is_url(location) and not Path(location).is_absolute() else location
