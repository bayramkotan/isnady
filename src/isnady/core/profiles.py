"""Profiles (PRF1, 2026-10-18): several people can use one isnady, each with their own choices.

A profile holds what is a person's own — the settings (settings.json: theme, fonts, interface and content
languages, the books switched off), where the reader was (state.json) and the bookmarks (bookmarks.json). The
database, the sources, the saved statistics and the caches are shared: the books are the same for everyone.

The first profile, "default", is the data folder itself — the files isnady always kept there — so nothing moves
for anyone who never makes a second one. Every other profile is a folder `profiles/<id>/` in the data folder.
`profiles.json` in the data folder lists them and names the active one; the ISNADY_PROFILE environment variable
chooses one for a single run (the command line, tests).

A profile is exported as one file (`<name>.isnady-profile.zip`: the three files and a small manifest) and imported
on another computer — or on the same one, as a new profile.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
import zipfile
from pathlib import Path

from isnady.data.paths import data_dir

LIST_FILE = "profiles.json"
FOLDER = "profiles"
DEFAULT = "default"
FILES = ("settings.json", "state.json", "bookmarks.json")      # what a profile holds
EXTENSION = ".isnady-profile.zip"
FORMAT = "isnady-profile/1"


class ProfileError(ValueError):
    """A profile that cannot be made, found or read; the message is meant for the user."""


def _list_path() -> Path:
    return data_dir() / LIST_FILE


_seen: dict = {}       # the list as last read, by the file's stamp: the settings ask for the profile very often


def _read() -> dict:
    path = _list_path()
    try:
        st = path.stat()
        stamp = (str(path), st.st_mtime_ns, st.st_size)
    except OSError:
        stamp = (str(path), None, None)
    hit = _seen.get("list")
    if hit and hit[0] == stamp:
        return json.loads(json.dumps(hit[1]))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    items = [p for p in data.get("profiles", []) if isinstance(p, dict) and p.get("id")]
    if not any(p["id"] == DEFAULT for p in items):
        items.insert(0, {"id": DEFAULT, "name": ""})
    out = {"active": data.get("active") or DEFAULT, "profiles": items}
    _seen["list"] = (stamp, out)
    return json.loads(json.dumps(out))


def _write(data: dict) -> None:
    path = _list_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)
    _seen.clear()


def all_profiles() -> list[dict]:
    """[{"id", "name", "active"}], the first profile first. The first profile's name is "" until it is given one
    (the screen calls it "Default")."""
    data = _read()
    now = active()
    return [{"id": p["id"], "name": p.get("name") or "", "active": p["id"] == now} for p in data["profiles"]]


def active() -> str:
    wanted = os.environ.get("ISNADY_PROFILE")
    data = _read()
    ids = [p["id"] for p in data["profiles"]]
    if wanted:
        return find(wanted, data) or DEFAULT
    return data["active"] if data["active"] in ids else DEFAULT


def folder(profile_id: str | None = None) -> Path:
    """The folder of a profile's files: the data folder for the first profile, profiles/<id>/ for the others."""
    pid = profile_id or active()
    if pid == DEFAULT:
        return data_dir()
    path = data_dir() / FOLDER / pid
    path.mkdir(parents=True, exist_ok=True)
    return path


def name_of(profile_id: str) -> str:
    for p in _read()["profiles"]:
        if p["id"] == profile_id:
            return p.get("name") or ""
    return ""


def find(text: str, data: dict | None = None) -> str | None:
    """A profile by its id or its name (case does not matter)."""
    data = data or _read()
    want = (text or "").strip().casefold()
    for p in data["profiles"]:
        if p["id"].casefold() == want or (p.get("name") or "").casefold() == want:
            return p["id"]
    if want in ("default", "varsayılan", "الافتراضي"):
        return DEFAULT
    return None


def _new_id(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.casefold().translate(str.maketrans("çğıöşüâîû", "cgiosuaiu"))).strip("-")
    base = base[:32] or "profile"
    pid, n = base, 2
    while pid in taken or pid == DEFAULT:
        pid, n = f"{base}-{n}", n + 1
    return pid


def create(name: str, copy_from: str | None = None) -> str:
    """A new profile; its settings copied from another one (copy_from) or isnady's defaults. Returns its id."""
    name = (name or "").strip()
    if not name:
        raise ProfileError("A profile needs a name.")
    data = _read()
    if find(name, data):
        raise ProfileError(f"There is already a profile named {name}.")
    pid = _new_id(name, {p["id"] for p in data["profiles"]})
    data["profiles"].append({"id": pid, "name": name})
    _write(data)
    target = folder(pid)
    if copy_from:
        source = folder(copy_from)
        for f in FILES:
            if (source / f).exists():
                shutil.copy2(source / f, target / f)
    return pid


def switch(profile_id: str) -> None:
    """Make a profile the active one (from the next reading of the settings; the window is built again)."""
    data = _read()
    if profile_id not in [p["id"] for p in data["profiles"]]:
        raise ProfileError(f"No profile {profile_id}.")
    data["active"] = profile_id
    _write(data)
    _forget_settings()


def rename(profile_id: str, name: str) -> None:
    name = (name or "").strip()
    if not name:
        raise ProfileError("A profile needs a name.")
    data = _read()
    other = find(name, data)
    if other and other != profile_id:
        raise ProfileError(f"There is already a profile named {name}.")
    for p in data["profiles"]:
        if p["id"] == profile_id:
            p["name"] = name
            _write(data)
            return
    raise ProfileError(f"No profile {profile_id}.")


def delete(profile_id: str) -> None:
    """Remove a profile and its files. The first profile (the data folder itself) and the one in use cannot be."""
    if profile_id == DEFAULT:
        raise ProfileError("The first profile cannot be deleted: its files are isnady's own data folder.")
    if profile_id == active():
        raise ProfileError("The profile in use cannot be deleted: switch to another one first.")
    data = _read()
    left = [p for p in data["profiles"] if p["id"] != profile_id]
    if len(left) == len(data["profiles"]):
        raise ProfileError(f"No profile {profile_id}.")
    data["profiles"] = left
    _write(data)
    shutil.rmtree(data_dir() / FOLDER / profile_id, ignore_errors=True)


def export(profile_id: str, target: str | Path) -> Path:
    """One file with the profile's settings, place and bookmarks. Returns the file written."""
    target = Path(target).expanduser()
    if target.is_dir():
        label = name_of(profile_id) or ("default" if profile_id == DEFAULT else profile_id)
        target = target / (re.sub(r"[^\w.-]+", "_", label) + EXTENSION)
    source = folder(profile_id)
    manifest = {"format": FORMAT, "name": name_of(profile_id) or "", "id": profile_id,
                "exported": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": []}
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            if (source / f).exists():
                z.write(source / f, f)
                manifest["files"].append(f)
        z.writestr("profile.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    return target


def import_file(path: str | Path, name: str | None = None) -> str:
    """A profile file made by export(), as a new profile (named as in the file, or name). Returns its id."""
    path = Path(path).expanduser()
    try:
        with zipfile.ZipFile(path) as z:
            manifest = json.loads(z.read("profile.json").decode("utf-8"))
            if manifest.get("format") != FORMAT:
                raise ProfileError(f"{path.name} is not an isnady profile.")
            contents = {f: z.read(f) for f in FILES if f in z.namelist()}
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        if isinstance(exc, ProfileError):
            raise
        raise ProfileError(f"{path.name} is not an isnady profile ({exc}).") from None
    for f, raw in contents.items():
        try:
            json.loads(raw.decode("utf-8"))                     # only JSON files of isnady are taken
        except ValueError:
            raise ProfileError(f"{path.name}: {f} is damaged.") from None
    wanted = (name or manifest.get("name") or path.name.split(".")[0] or "Imported").strip()
    data = _read()
    final, n = wanted, 2
    while find(final, data):
        final, n = f"{wanted} ({n})", n + 1
    pid = create(final)
    target = folder(pid)
    for f, raw in contents.items():
        (target / f).write_bytes(raw)
    return pid


def _forget_settings() -> None:
    """The settings and the remembered state are read again from the new profile's folder."""
    try:
        from isnady import config

        config.forget()
    except (ImportError, AttributeError):
        pass
