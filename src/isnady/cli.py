"""The isnady command line (no Qt needed).

Every name runs it: `isnady ARGS`, `iy ARGS`, `isnady-cli ARGS`.

Examples
  iy search niyet
  iy search النيات --book bukhari
  iy chain bukhari 1
  iy isnads
  iy import taqrib https://raw.githubusercontent.com/OpenITI/0875AH/master/data/0852IbnHajarCasqalani/0852IbnHajarCasqalani.TaqribTahdhib/0852IbnHajarCasqalani.TaqribTahdhib.JK000121-ara1.completed
  iy narrator الزهري
  iy narrator --famous
  iy ai build
  iy search --mode meaning "komşu hakları"
  iy tahric bukhari 1
  iy scholar albani
  iy book bukhari 2
  iy shortcut
  iy stats graders --book abudawud
  iy stats lab --csv ./lab
  iy term mursal --lang tr
  iy import fawazahmed0 ./tur-bukhari.json
  iy import fawazahmed0 https://example.org/editions.json --book bukhari --language tur
  iy import fawazahmed0 https://example.org/ed.json --user bayram          (password is asked)
  iy import fawazahmed0 https://example.org/ed.json --token-env MY_TOKEN
  iy config list --prefix text.arabic
  iy config set text.arabic.size 22
  iy config set colors.dark.gilt "#5A4A1E"
  iy config reset text.arabic
  iy profile list
  iy profile new Ayşe --copy default
  iy profile use Ayşe
  iy profile export Ayşe ~/Desktop
  iy profile import ~/Desktop/Ayşe.isnady-profile.zip
  iy catalog list
  iy catalog import fawaz-muslim --language ara --language tur
  iy catalog import taqrib
  iy catalog import --all --language ara --language tur
  iy repo list
  iy repo use thaqalayn
  iy repo add https://github.com/owner/name
  iy repo add ~/Github/isnady-data              (a copy on this computer, read without the network)
  iy database use ~/Downloads/isnady-db-2026-10-10.zip
  iy datadir
  iy doctor
  iy update
  iy datadir /data/isnady
  iy sources
  iy stats
  iy remove <source-key>
  iy -V
"""

import argparse
import subprocess
import os.path
import getpass
import os
import sys
import time

from isnady import APP_NAME, __version__
from isnady.core import isnad as core_isnad
from isnady.core import narrators as core_narrators
from isnady.core import search as core_search
from isnady.data import db
from isnady.data.fetch import Auth, ResourceError
from isnady.data.importers import SourceInfo, get_importer, list_importers
from isnady.data.paths import db_path


def _connect():
    try:
        return db.connect(reset_old=True)
    except db.SchemaReset as exc:
        print(f"Note: {exc}", file=sys.stderr)
        return db.connect()


def _secret_from_env(name: str | None) -> str | None:
    if not name:
        return None
    value = os.environ.get(name)
    if value is None:
        raise SystemExit(f"Environment variable {name} is not set.")
    return value


def _auth_from_args(args) -> Auth:
    token = args.token or _secret_from_env(args.token_env)
    api_key = args.api_key or _secret_from_env(args.api_key_env)
    chosen = [bool(args.user), bool(token), bool(api_key)]
    if sum(chosen) > 1:
        raise SystemExit("Use only one of: --user, --token/--token-env, --api-key/--api-key-env.")
    if args.user:
        password = _secret_from_env(args.password_env) if args.password_env else getpass.getpass(f"Password for {args.user}: ")
        return Auth(kind="basic", username=args.user, password=password)
    if token:
        return Auth(kind="bearer", token=token)
    if api_key:
        if args.api_key_param:
            return Auth(kind="apikey", token=api_key, key_name=args.api_key_param, key_in="query")
        return Auth(kind="apikey", token=api_key, key_name=args.api_key_header or "X-API-Key", key_in="header")
    return Auth()


def cmd_profile(args) -> int:
    """iy profile list|new|use|rename|delete|export|import — several people on one isnady (PRF1)."""
    from isnady.core import profiles as P

    def which(text):
        pid = P.find(text) if text else None
        if text and not pid:
            raise P.ProfileError(f"No profile {text}. See: iy profile list")
        return pid

    try:
        if args.action == "list":
            for p in P.all_profiles():
                name = p["name"] or "Default"
                print(f"{'*' if p['active'] else ' '} {name:24} {p['id']:20} {P.folder(p['id'])}")
            print("\n* the profile in use. Its settings, place and bookmarks are its own; the books are shared.")
        elif args.action == "new":
            pid = P.create(args.name or "", which(args.copy) if args.copy else None)
            print(f"Made the profile {args.name} ({pid}). Use it: iy profile use \"{args.name}\"")
        elif args.action == "use":
            P.switch(which(args.name or "") or P.DEFAULT)
            print(f"In use: {P.name_of(P.active()) or 'Default'}")
        elif args.action == "rename":
            if not args.value:
                raise P.ProfileError("Give the new name: iy profile rename OLD NEW")
            P.rename(which(args.name or "") or P.DEFAULT, args.value)
            print(f"Renamed to {args.value}")
        elif args.action == "delete":
            P.delete(which(args.name or "") or "")
            print(f"Deleted {args.name}")
        elif args.action == "export":
            pid = which(args.name) if args.name else P.active()
            written = P.export(pid, args.value or ".")
            print(f"Written: {written}")
        elif args.action == "import":
            if not args.name:
                raise P.ProfileError("Give the file: iy profile import FILE.isnady-profile.zip")
            pid = P.import_file(args.name, args.value)
            print(f"Imported as {P.name_of(pid)} ({pid}). Use it: iy profile use \"{P.name_of(pid)}\"")
    except P.ProfileError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


def cmd_config(args) -> int:
    from isnady import config

    try:
        if args.action == "list":
            for key, value, default in config.all_values():
                if args.prefix and not key.startswith(args.prefix):
                    continue
                mark = "" if value == default else "   (changed)"
                shown = value if value != "" else "(default)"
                print(f"{key:32} {shown}{mark}")
            print(f"\nSaved in {config.settings_path()}")
        elif args.action == "get":
            if not args.key:
                raise config.ConfigError("Give the setting: iy config get text.arabic.size")
            config.validate(args.key, "")
            print(config.get(args.key))
        elif args.action == "set":
            if not args.key or args.value is None:
                raise config.ConfigError("Give the setting and the value: iy config set text.arabic.size 22")
            config.set(args.key, args.value)
            print(f"{args.key} = {config.get(args.key)}")
        elif args.action == "reset":
            removed = config.reset(args.key or "")
            print(f"Reset {removed} setting{'s' if removed != 1 else ''} to the default"
                  + (f" under {args.key}" if args.key else ""))
    except config.ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


def cmd_datadir(args) -> int:
    from isnady.data import paths

    if not args.path and not args.default:
        print(f"{paths.data_dir()}  ({paths.data_dir_source()})")
        print(f"default: {paths.default_data_dir()}")
        return 0
    try:
        target = paths.relocate(None if args.default else args.path, "as-is" if args.as_is else "copy")
    except paths.RelocateError as exc:
        print(exc, file=sys.stderr)
        return 2
    how = "used as it is" if args.as_is else "your data was copied there; the old folder is kept"
    print(f"isnady now uses {target} ({how}).")
    return 0


def _run_plan(plan: list[list[str]], yes: bool) -> None:
    for argv in plan:
        shown = " ".join(argv)
        if argv[0] in ("sudo", "powershell") and not yes:
            how = "a Windows prompt will ask for administrator rights" if argv[0] == "powershell" else "sudo"
            answer = input(f"Update a copy that needs administrator rights ({how})?\n  {shown}\n[y/N] ").strip().lower()
            if answer not in ("y", "yes", "e", "evet"):
                print("  skipped")
                continue
        print(f"$ {shown}")
        # a Windows administrator step runs as a command that prints pip's output here and returns its exit code
        code = subprocess.run(getattr(argv, "run", argv), check=False).returncode
        if code != 0:
            print(f"  ended with code {code}")


def cmd_doctor(args) -> int:
    from isnady import doctor

    report = doctor.diagnose(check_pypi=not args.offline)
    print(doctor.as_text(report))
    if not args.fix or not report.fixes:
        return 1 if report.problems else 0
    print()
    _run_plan(report.fixes, args.yes)
    after = doctor.diagnose(check_pypi=not args.offline)
    print("\nAfter updating:\n" + doctor.as_text(after))
    note = doctor.lag_note(after)
    if note:
        print("\n" + note)
    return 1 if after.problems else 0


def cmd_update(args) -> int:
    """Update every copy of isnady where it is installed. Nothing is removed or moved, except an old version's record
    pip left beside a newer one (doctor.Leftover)."""
    from isnady import doctor
    from isnady.core import updates

    if args.check or args.npm or updates.npm_installed():      # UPD4: PyPI and npm, whichever are installed
        found = updates.check()
        p, n = found["pypi"], found["npm"]
        print(f"PyPI: isnady {p['installed']}"
              + (f" → {p['latest']} available" if p["behind"] else
                 (" (up to date)" if p["latest"] else " (PyPI could not be reached)")))
        if n["installed"]:
            print(f"npm:  isnady {n['installed']}"
                  + (f" → {n['latest']} available" if n["behind"] else
                     (" (up to date)" if n["latest"] else " (npm's registry could not be reached)")))
        else:
            print("npm:  isnady is not installed with npm (npm install -g isnady)")
        for version, text in found["news"]:
            print(f"\nWhat is new in {version}:\n{text}")
        if args.check:
            return 0
        if n["behind"] and (args.npm or not args.pypi):
            print("\nUpdating isnady from npm:")
            _run_plan([updates.npm_update_argv()], args.yes)
        if args.npm and not args.pypi:
            return 0
    report = doctor.diagnose(check_pypi=True)
    if not report.fixes:
        print(f"isnady {report.running_version} is up to date"
              + (f" (latest on PyPI: {report.latest})." if report.latest else " (PyPI could not be reached)."))
        return 0
    print("Updating every copy of isnady where it is installed:")
    _run_plan(report.fixes, args.yes)
    after = doctor.diagnose(check_pypi=True)       # against PyPI again: "no problems" must mean up to date
    print("\n" + doctor.as_text(after))
    note = doctor.lag_note(after)
    if note:
        print("\n" + note)
    print("\nIf the shell still starts an old copy, open a new terminal (or run: hash -r).")
    return 1 if after.problems else 0


def cmd_version(_args) -> int:
    print(f"{APP_NAME} {__version__}")
    return 0


def cmd_formats(_args) -> int:
    for imp in list_importers():
        print(f"{imp.format_id:14} {imp.title}\n{'':14} {imp.description}")
    return 0


def cmd_import(args) -> int:
    from isnady.core.imports import ImportRequest, run_import

    try:
        get_importer(args.format)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 2
    request = ImportRequest(
        format_id=args.format, location=args.location, name=args.name, license=args.license, tier=args.tier,
        origin="builtin" if args.builtin else "user", auth=_auth_from_args(args),
        options={"editions": args.edition, "books": args.book, "languages": args.language, "all": args.all,
                 "edition_key": args.edition_key, "include_plain": args.include_plain},
    )
    conn = _connect()
    try:
        report, narrators = run_import(conn, request, progress=lambda m: print(f"  {m}"))
    except ResourceError as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    _print_report(report, narrators)
    return 0


def _print_report(report, narrators) -> None:
    print(f"Done: source '{report.source_key}' — {len(report.editions)} edition(s), "
          f"{report.texts} texts, {report.new_hadiths} new hadith, {report.grades} new grades")
    if report.skipped_editions:
        print(f"  skipped diacritics-free copies (use --include-plain to keep): {', '.join(report.skipped_editions)}")
    for warning in report.warnings:
        print(f"  warning: {warning}")
    if narrators.get("links"):
        print(f"  narrators identified: {narrators['identified']} of {narrators['links']} links "
              f"({100 * narrators['identified'] / narrators['links']:.1f}%)")


def cmd_database(args) -> int:
    """iy database use FILE: a ready database (isnady.db or the isnady-db zip of isnady-data) from this computer."""
    from isnady.data import ready
    from isnady.data.paths import db_path

    if args.action == "use":
        if not args.file:
            print("Give the file: iy database use ~/Downloads/isnady-db-2026-10-10.zip", file=sys.stderr)
            return 2
        try:
            info = ready.stage(args.file)
        except ready.ReadyError as exc:
            print(exc, file=sys.stderr)
            return 1
        try:
            backup = ready.apply_pending()    # the command line holds no connection open: in place now
        except OSError:
            print(f"Ready: {info['books']} books, {info['hadith']:,} hadith. isnady is open and holds the database; "
                  "it is used from the next start.")
            return 0
        print(f"Using the ready database: {info['books']} books, {info['hadith']:,} hadith (schema {info['schema']})"
              + (f"; your previous database is kept as {backup}" if backup else "") + ".")
        print("If the isnady window is open, close and start it again.")
        return 0
    print(f"database: {db_path()}" + ("  (a ready database is waiting for the next start)" if ready.pending() else ""))
    return 0


def cmd_repo(args) -> int:
    from isnady.core import repositories as R

    if args.action == "list":
        chosen = R.selected().id
        for r in R.all_repositories():
            mark = "*" if r.id == chosen else " "
            kind = "default" if r.default else ("added by you" if not r.builtin else "optional")
            print(f" {mark} {r.id:22} {r.name:46} {kind}")
        print("\n* the repository in use. Choose: iy repo use ID · its sources: iy catalog list")
        return 0
    if args.action == "add":
        if not args.target:
            print("Give the repository: iy repo add https://github.com/owner/name", file=sys.stderr)
            return 2
        try:
            repo = R.add_repository(args.target, args.name)
        except (ResourceError, ValueError) as exc:
            print(exc.args[0] if exc.args else exc, file=sys.stderr)
            return 1
        print(f"Added {repo.id}: {repo.name}. Use it: iy repo use {repo.id}")
        return 0
    repo = R.find(args.target) if args.target else R.selected()
    if repo is None:
        print(f"No repository '{args.target}'. See: iy repo list", file=sys.stderr)
        return 1
    if args.action == "use":
        R.select(repo.id)
        print(f"Using {repo.name}. Its sources: iy catalog list")
        return 0
    if args.action == "remove":
        if repo.builtin:
            print(f"{repo.name} ships with isnady and stays in the list.", file=sys.stderr)
            return 1
        R.remove_repository(repo.id)
        print(f"Removed {repo.name} from the list (what you imported from it stays).")
        return 0
    try:
        cat, where = R.catalog(repo, refresh=args.refresh)
    except ResourceError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"{repo.name} ({repo.id})\n  {repo.description}")
    if repo.homepage:
        print(f"  {repo.homepage}")
    print(f"  catalog: {repo.url} — read from " + {"network": "the repository now", "saved": "the copy saved in the "
                                                    "last day", "shipped": "the copy shipped with isnady (not reachable)"}[where]
          if repo.url else "  catalog: shipped with isnady (this dataset publishes none of its own)")
    for e in cat["entries"]:
        print(f"  {e['id']:20} {e.get('tradition', ''):6} {e['title']}")
    return 0


def cmd_catalog(args) -> int:
    from isnady.core import catalog
    from isnady.core import repositories as R

    if args.action == "languages":                  # LANG2: one language for every book
        conn = _connect()
        try:
            what = (args.id or "").lower()
            codes = [catalog.code_for(x) for x in ([args.format, args.location] if args.format else []) + (args.language or [])
                     if x]
            if what in ("", "list"):
                for row in catalog.language_overview(conn):
                    print(f"  {row['code']}  {row['label']:12} imported in {row['imported']:>2} of the {row['offered']} "
                          f"books that offer it")
                print("Add one to every book: iy catalog languages add tr en   ·   remove: iy catalog languages remove ur")
                return 0
            if not codes:
                print("Name the languages: iy catalog languages add tr en", file=sys.stderr)
                return 2
            if what == "add":
                imported, failed, _n = catalog.add_languages(conn, codes, progress=lambda m: print(f"  {m}"))
                print(f"Added to {len(imported)} book(s)" + (f"; failed: {'; '.join(f'{a} ({b})' for a, b in failed)}"
                                                              if failed else "."))
                return 1 if failed else 0
            if what == "remove":
                if "ara" in codes:
                    print("Arabic stays: the chains and the narrators are read from it.", file=sys.stderr)
                n = catalog.remove_languages(conn, codes)
                print(f"Removed {n} edition(s).")
                return 0
            print("iy catalog languages [list | add CODES | remove CODES]", file=sys.stderr)
            return 2
        finally:
            conn.close()
    if args.action == "list":
        conn = _connect()
        repo = R.find(args.repo) if args.repo else R.selected()
        if repo is None:
            print(f"No repository '{args.repo}'. See: iy repo list", file=sys.stderr)
            return 1
        for kind, title in (("builtin", f"Sources of {repo.name}"), ("user", "Your sources (User Resources)")):
            entries = catalog.builtin_entries(repo.id) if kind == "builtin" else catalog.user_entries()
            print(f"\n{title}")
            if not entries:
                print("  none yet — add one: iy catalog add TITLE FORMAT FILE-OR-URL")
            for e in entries:
                st = catalog.status(conn, e)
                state = ("imported" + (f" ({', '.join(catalog.language_label(l) if len(l) == 3 else l for l in st['languages'])})"
                                       if st["languages"] else "") + f", {st['count']:,}"
                         if st["imported"] else "not imported")
                print(f"  {e.id:18} {e.tradition if e.builtin else '':6} {e.title:46} {state}")
        conn.close()
        return 0
    if args.action == "add":
        if not args.id or not args.format or not args.location:
            print("Give a title, a format and a file or URL: iy catalog add \"My Bukhari\" fawazahmed0 ./bukhari.json",
                  file=sys.stderr)
            return 2
        try:
            entry = catalog.add_user_entry(args.id, args.format, args.location, args.license,
                                           args.auth, args.api_key_header or args.api_key_param,
                                           "query" if args.api_key_param else "header", args.book)
        except (KeyError, ValueError) as exc:
            print(exc.args[0] if exc.args else exc, file=sys.stderr)
            return 2
        print(f"Added {entry.id}: {entry.title}. Import it with: iy catalog import {entry.id}")
        return 0
    if args.action == "delete":
        ok = catalog.delete_user_entry(args.id or "")
        print("Deleted." if ok else f"No user source '{args.id}'. See: iy catalog list")
        return 0 if ok else 1
    if args.action == "import" and args.all:
        conn = _connect()
        try:
            languages = [catalog.code_for(l) for l in args.language] if args.language else None
            imported, failed, narrators = catalog.import_all(conn, languages, progress=lambda m: print(f"  {m}"))
        finally:
            conn.close()
        print(f"Done: {len(imported)} source(s) imported" + (f", {len(failed)} failed" if failed else ""))
        for label, message in failed:
            print(f"  failed: {label}: {message}")
        if narrators.get("links"):
            print(f"  narrators identified: {narrators['identified']} of {narrators['links']} links "
                  f"({100 * narrators['identified'] / narrators['links']:.1f}%)")
        return 0 if not failed else 1
    entry = catalog.find(f"{args.repo}/{args.id}" if args.repo and args.id else (args.id or ""))
    if entry is None:
        print(f"No source '{args.id}'. See: iy catalog list", file=sys.stderr)
        return 1
    conn = _connect()
    try:
        if args.action == "remove":
            ok = catalog.remove_entry(conn, entry)
            print(f"Removed what {entry.id} imported." if ok else f"{entry.id} was not imported.")
            return 0 if ok else 1
        auth = Auth()
        if entry.auth_kind == "basic":
            user = input(f"Username for {entry.title}: ")
            auth = Auth(kind="basic", username=user, password=getpass.getpass("Password: "))
        elif entry.auth_kind in ("bearer", "apikey"):
            secret = getpass.getpass("Token: " if entry.auth_kind == "bearer" else "API key: ")
            auth = Auth(kind=entry.auth_kind, token=secret, key_name=entry.key_name, key_in=entry.key_in)
        languages = [catalog.code_for(l) for l in args.language] if args.language else None
        report, narrators = catalog.import_entry(conn, entry, languages, auth, progress=lambda m: print(f"  {m}"))
    except ResourceError as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    _print_report(report, narrators)
    return 0


def cmd_sources(_args) -> int:
    conn = _connect()
    rows = conn.execute(
        """SELECT s.key, s.name, s.format, s.origin, s.tier, s.auth_type, s.license, s.location, s.imported_at,
                  COUNT(e.id) AS editions, COALESCE(SUM(e.text_count), 0) AS texts
           FROM sources s LEFT JOIN editions e ON e.source_id = s.id
           GROUP BY s.id ORDER BY s.origin, s.key"""
    ).fetchall()
    conn.close()
    if not rows:
        print("No sources yet. Add one with: iy import <format> <file-or-url>")
        return 0
    for r in rows:
        label = "User Resource" if r["origin"] == "user" else "Built-in"
        print(f"[{label}] {r['key']}  —  {r['name']}")
        tier_note = {"A": "redistributable", "B": "redistributable with conditions", "C": "not redistributable"}[r["tier"]]
        print(f"    format {r['format']}, auth {r['auth_type']}, license {r['license'] or 'not stated'}, "
              f"tier {r['tier']} ({tier_note})")
        print(f"    {r['editions']} edition(s), {r['texts']} texts, imported {r['imported_at']}")
        print(f"    last imported from {r['location']}")
    return 0


def cmd_stats_graders(args) -> int:
    from isnady.core import stats_graders as sg
    from isnady.core.scholars import SCHOLARS

    conn = _connect()
    books = sg.books_with_grades(conn)
    if not books:
        print("No grades imported.")
        return 0
    key = args.book or books[0][0]
    r = sg.cached(conn, key, lambda m: print(f"  … {m}", file=sys.stderr), args.recompute)
    everyone = set(r["graders"]) | {x["grader"] for x in r.get("selections", [])} | set(r.get("too_few") or {})
    for x in r.get("selections", []):
        everyone |= set(x["others"])
    short = {g: next((s.get("short") or s["name"] for s in SCHOLARS if g in s.get("grader_names", [])), g) for g in everyone}
    labels = r.get("labels") or sg.LABELS
    order = list(reversed(r.get("categories") or range(sg.K)))
    print(f"{key}: {len(r['graders'])} graders measured" + (f"  (from {r['from_file']})" if r.get("from_file") else "  (computed and saved)"))
    if r.get("tradition") == "shia":
        print("  road B: the four Imami categories (sahih, hasan, muwaththaq, da'if), never the Sunni grade groups")
    for g, n in (r.get("too_few") or {}).items():
        print(f"  {short[g]}: {n} grade(s) of this book — named, not measured")
    for x in r.get("selections", []):
        grade = labels[x["grade"]]
        print(f"  {short[x['grader']]}: a selection — all {x['count']:,} hadith he names are {grade}")
        for o, y in x["others"].items():
            dist = " · ".join(f"{labels[k]} {y['distribution'][k]:,}" for k in order)
            same = y["distribution"][x["grade"]] / y["common"] if y["common"] else 0
            print(f"    {short[o]} on those {y['common']:,}: {dist}  ({100 * same:.1f}% {grade})")
    if len(r["graders"]) < 2:
        print("  fewer than two graders who give more than one grade: no agreement or model")
        return 0
    from isnady.core import stats_words as sw

    a = r["alpha"]
    print(f"Krippendorff's alpha (ordinal) {a['value']:.3f}  95% {a['ci'][0]:.3f}–{a['ci'][1]:.3f}  over {a['units']:,} hadith")
    print(f"  → in plain words: {sw.alpha(a['value'])}  (iy stats --explain alpha)")
    for ov in r.get("one_voice", []):
        print(f"  ! {short[ov['kept']]} and {short[ov['left_out']]} agree {100 * ov['agree']:.1f}%: one voice in the model")
    print("Pairs: same grade · Cohen's kappa · ordinal kappa (95% intervals)")
    for k, p in r["pairs"].items():
        ga, gb = k.split("|")
        ci = p["ci"]
        print(f"  {short[ga]} – {short[gb]} (n {p['common']:,}): {100 * p['agree']:.1f}% [{100 * ci['agree'][0]:.1f}–{100 * ci['agree'][1]:.1f}]"
              f" · κ {p['kappa']:.2f} [{ci['kappa'][0]:.2f}–{ci['kappa'][1]:.2f}] · κw {p['wkappa']:.2f} [{ci['wkappa'][0]:.2f}–{ci['wkappa'][1]:.2f}]")
    print("Strictness from the model: P(below the true grade) − P(above it); negative = stricter")
    for g, s in sorted(r["model"]["strictness"].items(), key=lambda kv: kv[1]["value"]):
        print(f"  {short[g]:40} {s['value']:+.3f}  [{s['ci'][0]:+.3f}, {s['ci'][1]:+.3f}]  "
              + ("stricter (mutashaddid)" if s["ci"][1] < 0 else "more lenient (mutasahil)" if s["ci"][0] > 0
                 else "neither, within chance"))
    c = r["certainty"]
    print(f"The model is sure (≥95%) of {c['high']:,} of {c['total']:,} hadith, unsure (<60%) of {c['low']:,}; "
          f"{r['disputed_total']:,} disputed")
    for d in r["disputed"][: args.limit]:
        grades = ", ".join(f"{short[g]}: {labels[d['grades'][g]] if d['grades'].get(g) is not None else 'not graded'}"
                           for g in r["graders"])
        print(f"  #{d.get('number')}: model {labels[d['consensus']]} ({100 * d['certainty']:.0f}%) — {grades}")
    return 0


def cmd_stats_corpus(args) -> int:
    """iy stats narrators|chains|grades|books — the corpus statistics of the Statistics page (ST7), as text;
    --csv DIR writes every table behind them. --book @all: the Sunni road, then the Shia road (BK1), each apart."""
    from isnady.core import stats_corpus as sc

    if args.book == sc.ALL_SCOPE:
        import copy

        code = 0
        for i, road in enumerate((None, sc.SHIA_SCOPE)):
            if i:
                print("\n" + "=" * 72 + "\nThe Shia road, measured apart on its own scale (never together with the Sunni books)\n")
            one = copy.copy(args)
            one.book = road
            if args.csv:
                one.csv = os.path.join(args.csv, "sunni" if road is None else "shia")
            code = cmd_stats_corpus(one) or code
        return code
    from isnady.core import stats_words as sw

    conn = _connect()
    r = sc.cached(conn, args.book, lambda m: print(f"  … {m}", file=sys.stderr), args.recompute)
    if r.get("empty"):
        print("Nothing to measure: import a hadith collection first.")
        return 0
    groups = [g for g, _d in r["groups"]]
    pct = lambda x, n: f"{100 * x / n:.1f}%" if n else "—"  # noqa: E731
    o = r["overview"]
    shia = r.get("tradition") == "shia"               # road B: al-Najashi's Imami categories, chains to a Ma'sum
    scope = {None: "All Sunni books", sc.SHIA_SCOPE: "All Shia books"}.get(args.book, args.book)
    print(f"{scope}: {o['hadith']:,} hadith, {o['chains']:,} chains, {o['identified']:,} of "
          f"{o['links']:,} names identified ({pct(o['identified'], o['links'])}), {o['narrators']:,} narrators"
          + (f"  (from {r['from_file']})" if r.get("from_file") else "  (computed and saved)"))
    topic = args.topic
    if topic in ("narrators", None):
        n = r["narrators"]
        print("\nReliability (" + ("al-Najashi's words in the four Imami categories" if shia
                                   else "Ibn Hajar's ranks in six groups") + ")")
        for label, row in (("all narrators of al-Najashi" if shia else "all narrators of the Taqrib", n["rank_all"]), ("narrators in these chains", n["rank_people"]),
                           ("every name in these chains", n["rank_links"])):
            total = sum(row)
            print(f"  {label:30} " + " · ".join(f"{g} {pct(v, total)}" for g, v in zip(groups, row)))
        c = n["concentration"]
        if c.get("gini") is not None:
            print(f"\nConcentration: busiest 1% carry {100 * c['top1']:.1f}%, busiest 10% {100 * c['top10']:.1f}%; "
                  f"{c['half_by']:,} of {c['people']:,} narrators carry half; Gini {c['gini']:.3f}")
            print(f"  → in plain words: {sw.gini(c['gini'])} — the pivots (madar) of the corpus  (iy stats --explain gini)")
        print("\nThe pillars (times in the chains · hadith · rank)")
        for p in n["pillars"][:args.limit]:
            print(f"  {p['links']:6,} {p['hadith']:6,}  rank {p['rank'] or '—':>2}  {p['name']}")
    if topic in ("chains", None):
        ch = r["chains"]
        print("\nChain length (names: chains): " + ", ".join(f"{k}: {v:,}" for k, v in ch["lengths"]))
        total = sum(ch["weakest"])
        print("Weakest link: " + " · ".join(f"{g} {pct(v, total)}" for g, v in zip(groups, ch["weakest"])))
        if ch["order_ok"] + ch["order_bad"]:
            print(f"Generations in order: {ch['order_ok']:,} pairs right, {ch['order_bad']:,} the student earlier than his teacher")
        print("Pairs too far apart in time (student's death − teacher's), most frequent:")
        for s in ch["gap_suspects"][:args.limit]:
            print(f"  {s['gap']:+5d} years ×{s['times']:<4} {s['student']['name']}  ←  {s['teacher']['name']}")
    if topic in ("grades", None):
        print("\nWeakest narrator against the grade (Kendall's tau-b, 95% interval, gamma); then chain length")
        for g in r["grades"]:
            w, ln = g.get("weakest"), g.get("length")
            if not w or w["tau"] is None:
                continue
            ci = f"[{w['tau_ci'][0]:.3f}, {w['tau_ci'][1]:.3f}]" if w["tau_ci"] else ""
            lt = f"{ln['tau']:.3f}" if ln and ln["tau"] is not None else "—"
            print(f"  {g['grader'][:34]:34} {g['book'][:22]:22} n {w['n']:5,}  tau-b {w['tau']:.3f} {ci}  "
                  f"gamma {w['gamma']:.3f}  · length tau-b {lt}")
            print(f"    → in plain words: {sw.strength(w['tau'])}, "
                  f"{sw.sure(*(w['tau_ci'] or (None, None))) or 'no interval'}  (iy stats --explain kendall)")
    if topic in ("books", None):
        print("\nBooks: chains · median length · identified · " + ("reach a Ma'sum" if shia else "reach the Prophet")
              + " · narrators")
        for b in r["books"]["rows"]:
            print(f"  {b['name'][:32]:32} {b['chains']:7,}  {b['median_length'] or '—':>3}  {100 * b['identified']:5.1f}%  "
                  f"{100 * b['reaching']:5.1f}%  {b['narrators']:6,}")
    if args.csv:
        _write_corpus_csv(r, args.csv)
    return 0


def cmd_stats_model(args) -> int:
    """iy stats model — the hadith model (ST7-H): what each scholar's grade follows, the factors that matter, the fit,
    and the hadith graded higher or lower than their chain foretells."""
    from isnady.core import stats_models as sm

    conn = _connect()
    r = sm.cached(conn, args.book, lambda m: print(f"  … {m}", file=sys.stderr), args.recompute)
    if not r["models"]:
        print("No model: it needs a graded book whose chains are split into names (at least 100 graded hadith).")
        return 0
    for m in r["models"]:
        if args.grader and args.grader.lower() not in m["grader"].lower():
            continue
        print(f"\n{m['grader']} — {m['book_name']}: {m['n']:,} hadith, grades {' < '.join(reversed(m['labels']))}")
        print(f"  fit: McFadden R² {m['mcfadden']:.3f} · right {100 * m['accuracy']:.1f}% (always "
              f"“{m.get('base_label', m['labels'][0])}”: {100 * m['base_rate']:.1f}%) "
              f"· Somers' D {m['somers_d']:.3f} · LR χ² {m['lr_all']['chi2']:.1f} on {m['lr_all']['df']} df")
        from isnady.core import stats_words as sw

        print(f"  → in plain words: the chain explains {sw.r2(m['mcfadden'])} of the grades and gives "
              f"{sw.somers(m['somers_d'])} of the hadith; the rest is what the scholar weighed beyond one chain "
              f"(iy stats --explain r2)")
        print("  odds ratio of a WEAKER grade (95% interval), p")
        for c in m["coefficients"]:
            print(f"    {c['name']:34} {c['or']:7.2f} [{c['or_ci'][0]:.2f}–{c['or_ci'][1]:.2f}]  p {c['p']:.2g}")
        print("  factors (likelihood-ratio test, Holm-adjusted p)")
        for t in sorted(m["tests"], key=lambda t: -t["chi2"]):
            print(f"    {t['label']:34} χ² {t['chi2']:7.1f}  df {t['df']}  p {t['p_holm']:.2g}")
        for side, word in (("graded_higher", "higher"), ("graded_lower", "lower")):
            print(f"  graded {word} than the chain foretells: {m[side + '_total']:,}; the least expected:")
            for d in m[side][:args.limit]:
                print(f"    hadith {d['number']:>6}  {d['grade']:>24}  model: {d['likely']:<24} p {d['p']:.3f}  "
                      f"weakest {d['factors']['weakest']}")
    if r.get("shared"):
        print(f"\nSurprises two scholars or more share: {len(r['shared'])}")
        for s in r["shared"][:args.limit]:
            print(f"  {'▲' if s['side'] == 'graded_higher' else '▼'} {s['book']} {s['number']}: "
                  + "; ".join(f"{g}: {gr}" for g, gr, _l, _p in s["graders"]))
    return 0


def _p(p: float | None) -> str:
    return "" if p is None else ("< 0.001" if p < 0.001 else f"{p:.3f}")


def cmd_stats_lab(args) -> int:
    """iy stats lab — the correlation and test laboratory (ST7-C): Spearman matrices with Benjamini–Hochberg q,
    each factor against each grade with the others held equal, the scholars' grade distributions compared pair by
    pair (Stuart–Maxwell), the narrators' measures, and the books compared (Kruskal–Wallis, Mann–Whitney)."""
    import math

    from isnady.core import stats_lab as sl

    conn = _connect()
    r = sl.cached(conn, args.book, lambda m: print(f"  … {m}", file=sys.stderr), args.recompute)
    for m in r["hadith"]:
        print(f"\n{m['book']} — {m['hadith']:,} hadith with a chain split into names (Spearman's rho, BH q)")
        print("  the strongest relations:")
        for a, b, rho, n, _p0, q in sl.pairs_table(m)[:args.limit]:
            print(f"    {a:30} {b:34} {rho:+.2f}  n {n:>5,}  q {_p(q)}")
        print("  each factor against each grade, the other factors held equal (partial rho):")
        for outcome, factor, plain, adj, n, q in sl.adjusted_table(m):
            if adj is not None and q is not None and q < sl.ALPHA:
                print(f"    {outcome:42} {factor:24} {plain:+.2f} → {adj:+.2f}  q {_p(q)}")
    if r["graders"]:
        print("\nDo two scholars grade alike overall? (Stuart–Maxwell, same hadith, Holm-adjusted)")
        for t in r["graders"]:
            print(f"  {t['a']} / {t['b']}: {t['n']:,} hadith; the first grades higher on {t['a_stronger']:,}, lower "
                  f"on {t['a_weaker']:,}; χ² {t['chi2']:.1f} on {t['df']} df, p {_p(t['p_holm'])}")
    if r.get("brant"):
        print("\nDoes the hadith model's shape hold? (Brant: the same weight at every step of the grades)")
        for b in r["brant"]:
            o = b["overall"]
            print(f"  {b['grader']} — {b['book']}: χ² {o['chi2']:.1f} on {o['df']} df, p {_p(o['p_holm'])}"
                  + ("" if len(b["thresholds"]) == b["of"] else f" ({len(b['thresholds'])} of {b['of']} steps estimable)"))
            for f in b["factors"]:
                if f["p_holm"] < sl.ALPHA:
                    print(f"    {f['name']:34} odds ratio at each step "
                          + " → ".join(f"{math.exp(x):.2f}" for x in f["slopes"]) + f"  p {_p(f['p_holm'])}")
    if r.get("narrators"):
        n = r["narrators"]
        print(f"\nNarrators — {n['people']:,} in the chains")
        for a, b, rho, k, _p0, q in sl.pairs_table(n)[:args.limit]:
            print(f"    {a:22} {b:22} {rho:+.2f}  n {k:>5,}  q {_p(q)}")
    if r.get("books"):
        print("\nThe books compared (Kruskal–Wallis; pairs: Mann–Whitney, Cliff's delta, Holm)")
        for c in r["books"]:
            kw = c["kruskal"]
            if kw:
                print(f"  {c['measure']}: H {kw['H']:.1f} on {kw['df']} df, p {_p(kw['p'])}, ε² {kw['epsilon2']:.3f}")
            for p in c["pairs"]:
                print(f"    {p['a']} / {p['b']}: delta {p['delta']:+.2f}, p {_p(p['p_holm'])}")
    if args.csv:
        files = sl.write_csv(r, args.csv)
        print(f"\n{len(files)} CSV tables written to {args.csv}")
    return 0


def _write_corpus_csv(r: dict, folder: str) -> None:
    """Every table behind the statistics, one CSV each (UTF-8 with BOM: spreadsheets read the Arabic right)."""
    import csv
    from pathlib import Path

    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    groups = [g for g, _d in r["groups"]]

    def write(name: str, header: list, rows: list) -> None:
        with open(out / f"{name}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    n, ch = r["narrators"], r["chains"]
    write("reliability", ["series"] + groups, [["taqrib"] + n["rank_all"], ["narrators in chains"] + n["rank_people"],
                                               ["names in chains"] + n["rank_links"]])
    write("pillars", ["id", "name", "rank", "tabaqa", "death", "times", "hadith"],
          [[p["id"], p["name"], p["rank"], p["tabaqa"], p["death"], p["links"], p["hadith"]] for p in n["pillars"]])
    write("lorenz", ["share of narrators", "share of names"], n["concentration"].get("curve", []))
    write("tabaqa", ["tabaqa"] + groups, [[i + 1] + row for i, row in enumerate(n["tabaqa_groups"])])
    write("chain_length", ["names", "chains"], ch["lengths"])
    write("weakest_link", ["series"] + groups, [["chains"] + ch["weakest"], ["fully identified"] + ch["weakest_full"]])
    write("time_gaps", ["years (bin)", "pairs"], ch["gaps"])
    write("time_suspects", ["student", "teacher", "years", "times"],
          [[s["student"]["name"], s["teacher"]["name"], s["gap"], s["times"]] for s in ch["gap_suspects"]])
    rows = []
    for g in r["grades"]:
        for kind in ("weakest", "length"):
            a = g.get(kind)
            if a and a["tau"] is not None:
                rows.append([g["grader"], g["book"], kind, a["n"], a["tau"], *(a["tau_ci"] or ["", ""]), a["gamma"]])
    write("grades_association", ["grader", "book", "against", "n", "tau_b", "low", "high", "gamma"], rows)
    write("books", ["book", "chains", "median length", "identified", "reach the Prophet", "narrators"] + groups,
          [[b["name"], b["chains"], b["median_length"], b["identified"], b["reaching"], b["narrators"]] + b["groups"]
           for b in r["books"]["rows"]])
    print(f"\nCSV tables written to {out}")


def _explain_terms(which: str) -> int:
    """iy stats --explain [TERM]: every measure in plain words (ST-EXP1)."""
    from isnady.core import stats_words as sw

    chosen = sw.all_terms() if which in ("", "all") else [t for t in [sw.find(which)] if t]
    if not chosen:
        print(f"No measure '{which}'. Known: " + ", ".join(t["name"] for t in sw.all_terms()), file=sys.stderr)
        return 1
    for t in chosen:
        print(f"\n{t['name']}\n  What it measures: {t['what']}\n  How to read it:   {t['read']}"
              f"\n  Hadith science:   {t['hadith']}\n  Example:          {t['example']}")
    return 0


def cmd_stats(args) -> int:
    if getattr(args, "explain", None) is not None:
        return _explain_terms(args.explain)
    if getattr(args, "topic", None) == "graders":
        return cmd_stats_graders(args)
    if getattr(args, "topic", None) == "model":
        return cmd_stats_model(args)
    if getattr(args, "topic", None) == "lab":
        return cmd_stats_lab(args)
    if getattr(args, "topic", None) in ("corpus", "narrators", "chains", "grades", "books"):
        if args.topic == "corpus":
            args.topic = None
        return cmd_stats_corpus(args)
    conn = _connect()
    from isnady.core import books as core_books

    books = conn.execute(
        f"""SELECT c.id, c.name,
                  (SELECT COUNT(*) FROM hadiths h WHERE h.collection_id = c.id) AS hadiths,
                  (SELECT COUNT(DISTINCT g.hadith_id) FROM grades g JOIN hadiths h ON h.id = g.hadith_id
                   WHERE h.collection_id = c.id) AS graded,
                  (SELECT COUNT(*) FROM grades g JOIN hadiths h ON h.id = g.hadith_id
                   WHERE h.collection_id = c.id) AS grades
           FROM collections c ORDER BY {core_books.order_sql(conn)}"""
    ).fetchall()
    print(f"Database: {db_path()}")
    for b in books:
        print(f"  {b['name']}: {b['hadiths']} hadith, {b['graded']} graded ({b['grades']} grades)")
        for e in conn.execute(
            "SELECT key, language, text_count FROM editions WHERE collection_id = ? ORDER BY language, key", (b["id"],)
        ):
            print(f"      {e['key']:22} {e['language']:11} {e['text_count']:>6} texts")
    totals = conn.execute(
        "SELECT (SELECT COUNT(*) FROM hadiths), (SELECT COUNT(*) FROM texts), (SELECT COUNT(*) FROM grades),"
        " (SELECT COUNT(*) FROM persons), (SELECT COUNT(*) FROM isnads)"
    ).fetchone()
    conn.close()
    print(f"Total: {totals[0]} hadith, {totals[1]} texts, {totals[2]} grades, "
          f"{totals[3]} persons, {totals[4]} isnads")
    return 0


def _search_people(conn, args) -> int:
    """iy search --in narrators|scholars: the same people search as the Search page (S3)."""
    text = " ".join(args.words)
    if args.kind == "scholars":
        from isnady.core import scholars

        found = scholars.search(conn, text)
        conn.close()
        print(f"{len(found)} scholar{'s' if len(found) != 1 else ''} found")
        for s in found[args.offset:args.offset + args.limit]:
            roles = ", ".join(s["roles"]) or "nothing of his imported yet"
            print(f"\n{s['name']}  {s.get('known_ar') or s['arabic']}  ({s['id']})"
                  + ("  ≈ close spelling" if s.get("close") else ""))
            print(f"  {s['tr']} · {s['dates']}" if s["dates"] else f"  {s['tr']}")
            print(f"  roles here: {roles}")
            print(f"  works: {', '.join(s['works'])}")
        return 0
    from isnady.core import shia_rijal
    from isnady.core.rijal import RANK_LABELS

    rows, total = core_narrators.find(conn, text, args.tradition)
    if args.offset + args.limit > len(rows) and total > len(rows):
        # the matches after the ranked ones, as far as --offset/--limit reach (NR-B1)
        have = {r["id"] for r in rows}
        wanted = args.offset + args.limit - len(rows)
        rows += [r for r in core_narrators.find_more(conn, text, args.tradition, core_narrators.SEARCH_RERANK,
                                                     wanted) if r["id"] not in have]
    conn.close()
    shown = rows[args.offset:args.offset + args.limit]
    more = (f" (the closest {core_narrators.SEARCH_RERANK} are ranked first; --offset and --limit reach the others)"
            if total > core_narrators.SEARCH_RERANK else "")
    print(f"{total} narrator{'s' if total != 1 else ''} found{more}")
    for r in shown:
        view = r["view"]
        known = r.get("famous") or view["reading"] or view["full_reading"]
        print(f"\n{known + '  ' if known else ''}{view['arabic'] or r['name']}  (id {r['id']}, {r['tradition']})"
              + ("  ≈ same consonants, other vowels" if r.get("weak") else "  ≈ close spelling" if r.get("close")
                 else "  ≈ same consonants, reading unknown" if r.get("unread") else ""))
        if view["full_reading"] and view["full_reading"] != known:
            print(f"  {view['full_reading']}")
        facts = []
        if r["tradition"] == "shia":
            facts.append(shia_rijal.RANKS[r["rank"]][1] if r["rank"] else "no judgment")
            if r.get("madhhab"):
                facts.append(shia_rijal.MADHHAB_LABELS.get(r["madhhab"], r["madhhab"]))
        elif r["rank"]:
            facts.append(f"rank {r['rank']}: {RANK_LABELS[r['rank']][1]}")
        if r["tabaqa"]:
            facts.append(f"tabaqa {r['tabaqa']}")
        if r["death"]:
            facts.append(f"d. {r['death']} AH")
        facts.append(f"{r['in_chains']} in chains")
        print("  " + " · ".join(facts))
    return 0


def cmd_search(args) -> int:
    from isnady.core import recent

    if args.clear_recent:
        print(f"Forgot {recent.clear()} recent searches.")
        return 0
    if args.recent or not args.words:
        rows = recent.items()
        if not rows:
            print("No recent searches." if args.recent else "Give the words to search: iy search niyet")
            return 0 if args.recent else 2
        for i, r in enumerate(rows, 1):
            print(f"{i:>3}. {r['text']}" + ("" if r["kind"] == "hadith" else f"   (in {r['kind']})"))
        return 0
    recent.add(" ".join(args.words), args.kind)
    conn = _connect()
    if args.kind != "hadith":
        return _search_people(conn, args)
    if args.mode == "meaning":
        return _search_meaning(conn, args)
    core_search.ensure_index(conn, progress=lambda m: print(m, file=sys.stderr))
    q = core_search.SearchQuery(
        text=" ".join(args.words), mode=args.mode, whole_words=args.whole_words,
        collections=args.book or [], languages=args.language or [], limit=args.limit, offset=args.offset,
        grades=args.grade or [], every_grader=args.every_grader, sahihayn=not args.no_sahihayn,
    )
    page = core_search.search(conn, q)
    conn.close()
    print(f"{page.total} hadith found in {page.elapsed_ms} ms"
          f"{'' if page.used_index else ' (no FTS5 index available; slower scan)'}")
    if q.grades:
        from isnady.core import grades as core_grades

        print(f"grades: {core_grades.describe_choice(q.grades, q.every_grader)} — "
              f"{page.before_grades} found by the words in all")
    if page.spellings:
        print(f"near spellings: {core_search.spellings_text(page.spellings)}")
    for r in page.results:
        print(f"\n{r.collection_name} #{r.number}")
        if r.grades:
            print("  grades: " + "; ".join(f"{g}: {v}" for g, v in r.grades))
        elif q.grades and q.sahihayn and r.collection_key in ("bukhari", "muslim"):
            print("  sahih: in the Sahihayn — by the compiler's condition and the community's acceptance, "
                  "not a grader's grade")
        for t in r.texts:
            if not t.matched and not args.all_texts:
                continue
            marked, last = [], 0
            for a, b in t.spans:
                marked.append(t.text[last:a] + "[" + t.text[a:b] + "]")
                last = b
            marked.append(t.text[last:])
            body = "".join(marked)
            if len(body) > args.width:
                body = body[: args.width] + " ..."
            print(f"  [{t.language}] {body}")
    return 0


def _search_meaning(conn, args) -> int:
    from isnady.core import semantic

    q = core_search.SearchQuery(text=" ".join(args.words), collections=args.book or [],
                                languages=args.language or [], limit=args.limit, offset=args.offset,
                                grades=args.grade or [], every_grader=args.every_grader,
                                sahihayn=not args.no_sahihayn)
    try:
        st = semantic.status(conn)
        page = semantic.search(conn, q)
    except semantic.NotAvailable as exc:
        print(exc, file=sys.stderr)
        conn.close()
        return 2
    conn.close()
    stale = "  (the meaning index is older than the data: iy ai build)" if st.get("stale") else ""
    print(f"{page.total} hadith by meaning in {page.elapsed_ms} ms{stale}")
    if page.unknown_words:
        print(f"  no imported text uses: {', '.join(page.unknown_words)}")
    for r, score in zip(page.results, page.scores):
        print(f"\n{r.collection_name} #{r.number}   meaning {score:.2f}")
        for t in r.texts:
            body = " ".join(t.text.split())
            print(f"  [{t.language}] {body[: args.width] + (' ...' if len(body) > args.width else '')}")
    return 0


def cmd_ai(args) -> int:
    from isnady.core import semantic

    conn = _connect()
    try:
        if args.action == "build":
            from isnady.core import takhrij

            meta = semantic.build(conn, dims=args.dims, progress=lambda m: print(f"  {m}"))
            print(f"Meaning index in {meta['seconds']} s: {meta['documents']:,} hadith, {meta['terms']:,} words, "
                  f"{meta['dims']} concepts.")
            found = takhrij.build(conn, progress=lambda m: print(f"  {m}"))
            print(f"Takhrij in {found['seconds']} s: {found['same']:,} pairs of the same hadith, "
                  f"{found['same_report']:,} probably the same report.")
        else:
            missing = semantic.requirements_message()
            st = semantic.status(conn)
            if missing:
                print(missing)
            elif not st.get("built"):
                print("Meaning index: not built yet. Build it with: iy ai build")
            else:
                from isnady.core import takhrij

                print(f"Meaning index: {st['documents']:,} hadith, {st['terms']:,} words, {st['dims']} concepts, "
                      f"built {st['built_at']} ({st['method']})" + ("; OLDER than the data: iy ai build" if st["stale"] else ""))
                tk = takhrij.status(conn)
                print(f"Takhrij: {tk['same']:,} pairs of the same hadith, {tk['same_report']:,} probably the same report")
    except semantic.NotAvailable as exc:
        print(exc, file=sys.stderr)
        return 2
    finally:
        conn.close()
    return 0


def cmd_life(args) -> int:
    """The life of a Companion, a narrator or a scholar (BIO2): written for isnady, or read from the data."""
    import textwrap

    from isnady.core import i18n, language, lives

    i18n.set_language(args.lang or language.ui_language())
    text = " ".join(args.name)
    found = [(lives.view(w), True) for w in lives.find(None, text)]
    conn = None
    if not found:
        conn = _connect()
        rows, _total = core_narrators.find(conn, text, args.tradition)
        for r in rows[:args.limit]:
            info, written = lives.life(conn, r["id"])
            if info is not None:
                found.append((info, written))
    if conn is not None:
        conn.close()
    if not found:
        print(f"No one named '{text}' found.", file=sys.stderr)
        return 1
    width = 100
    for info, written in found[:args.limit]:
        print(f"\n{info['title']}  —  {info['kind']}" + ("" if written else "  (from the data)"))
        for label, value in info["facts"]:
            print(textwrap.fill(value, width, initial_indent=f"  {label}: ", subsequent_indent="    "))
        for paragraph in info["paragraphs"]:
            print()
            print(textwrap.fill(paragraph, width, initial_indent="  ", subsequent_indent="  "))
        if info["sources"]:
            print()
            print(textwrap.fill("; ".join(info["sources"]), width, initial_indent="  " + i18n.t("Sources") + ": ",
                                subsequent_indent="    "))
        for r in info.get("read", []):
            print(f"  → {r['text']}" + (f": {r['url']}" if r.get("url") else f" (iy book {r['book']})"))
        for e in info.get("entries", []):
            print(f"\n  {i18n.t('In the source')}: {e['title']}, {e['where']}")
            if args.source:
                from isnady.core import source_entries

                if not source_entries.available(e["work"]):
                    print(f"  … {i18n.t('Downloading')} (≈{source_entries.WORKS[e['work']]['size_mb']} MB, once)",
                          file=sys.stderr)
                    source_entries.fetch(e["work"], lambda m: print(f"  … {m}", file=sys.stderr))
                found = source_entries.entry(e["work"], e["volume"], e["number"])
                if found:
                    print(f"  {found['heading']}\n")
                    print(found["text"])
            else:
                print("  (iy life ... --source prints it in the author's own words)")
    return 0


def cmd_tree(args) -> int:
    """The genealogies (GEN1): the prophets, Quraysh, a narrator's family, a narrator's line of learning."""
    from isnady.core import genealogy

    if args.which in genealogy.WRITTEN:
        tree = genealogy.written(args.which, "en")
        if args.name:
            hits = genealogy.find(tree, args.name)
            if not hits:
                print(f"No one named '{args.name}' in this tree.", file=sys.stderr)
                return 1
            for n in hits[:5]:
                line = genealogy.path_to(tree, n.id)
                print(" → ".join(x.name("en") for x in line))
                for which in ("note", "disputed"):
                    if getattr(n, which):
                        print(f"  {which}: {n.text(which, 'en')}")
            if args.hadith:
                n = hits[0]
                if n.id == "muhammad":
                    print("\nHis life ﷺ: iy life muhammad")
                    return 0
                conn = _connect()
                found = genealogy.prophet_hadith(conn, n.id, limit=args.width * 10)
                conn.close()
                print(f"\nHadith that speak of {n.name('en')}: {found['total']:,}"
                      + ("" if found["total"] else " (none names him in words that can only mean him)"))
                for road in ("sunni", "shia"):
                    items = found["by_road"][road]
                    if items:
                        print(f"  {road.capitalize()} books ({found['counts'][road]:,}): "
                              + ", ".join(f"{i['book']} {i['number']}" for i in items))
            return 0
        print(genealogy.as_text(tree, "en"))
        return 0
    if not args.name:
        print("Give a narrator's name: iy tree family \"Ibn Umar\"", file=sys.stderr)
        return 2
    from isnady.core import narrators

    conn = _connect()
    try:
        rows, _total = narrators.find(conn, args.name)
        if not rows:
            print(f"No narrator found for '{args.name}'.", file=sys.stderr)
            return 1
        pid = rows[0]["id"]
        if args.which == "family":
            tree = genealogy.family(conn, pid)
            if tree is None:
                print("No kin among the narrators: no narrator's name makes him a father or a son.")
                return 0
        else:
            tree = genealogy.learning(conn, pid, depth=args.depth, width=args.width)
        print(genealogy.as_text(tree, "en"))
        if args.which == "family":
            print("\n(read from the narrators' names: \"X b. Y b. Z\" is the son of \"Y b. Z\" when exactly one narrator "
                  "of that name and of an earlier or the same generation is found)")
    finally:
        conn.close()
    return 0


def cmd_cache(args) -> int:
    """The cache (core.cache): what is kept so pages open without reading the whole database again."""
    from isnady.core import cache

    if args.action == "clear":
        n = cache.clear()
        print(f"Deleted {n} kept file(s); everything is counted again when next asked for.")
        return 0
    files, size = cache.info()
    print(f"Cache folder: {cache.folder()}")
    print(f"{files} file(s), {size / 1024:,.0f} KB — counted once per change of the database, read from here after.")
    return 0


def cmd_bookmark(args) -> int:
    """Bookmarks (BM1): list, add, remove, folders, export, import — the same file as the Bookmarks page."""
    from isnady.core import bookmarks

    store = bookmarks.Store.load()
    if args.action == "list":
        folder = store.folder_named(args.folder) if args.folder else None
        if args.folder and folder is None:
            print(f"No folder '{args.folder}'.", file=sys.stderr)
            return 1
        items = store.in_folder(folder.id) if folder else store.items
        if args.kind:
            items = [i for i in items if i.kind == args.kind]
        try:
            conn = _connect() if any(i.kind == "narrator" for i in items) else None
        except SystemExit:
            conn = None
        for i in items:
            where = ", ".join(store.path_of(f) for f in i.folders)
            more = bookmarks.detail(conn, i)
            print(f"  {i.id}  [{bookmarks.KINDS[i.kind]}] {i.title}" + (f"  · {more}" if more else "")
                  + (f"   — {where}" if where else "") + (f"\n      ✎ {i.note}" if i.note else ""))
        print(f"{len(items)} bookmark(s)")
        return 0
    if args.action == "folders":
        def show(parent, depth):
            for f in store.children(parent):
                print("  " + "  " * depth + f"📁 {f.name}  ({len(store.in_folder(f.id))})")
                show(f.id, depth + 1)
        show(None, 0)
        return 0
    if args.action == "add":
        if not args.kind or not args.ref:
            print("iy bookmark add KIND REF — kinds: hadith (bukhari:1), narrator (his key), scholar, term, chapter, "
                  "tree (prophets:musa, quraysh:ali, family:<narrator's key>, learning:<narrator's key>)",
                  file=sys.stderr)
            return 2
        title, subtitle, ref = args.title or args.ref, "", args.ref
        if args.kind in ("hadith", "narrator", "chapter"):
            conn = _connect()
            try:
                resolve = {"hadith": bookmarks.resolve_hadith, "narrator": bookmarks.resolve_narrator,
                           "chapter": bookmarks.resolve_chapter}[args.kind]
                target = resolve(conn, args.ref)
                if target is None:
                    print(f"No {args.kind} '{args.ref}' in the database.", file=sys.stderr)
                    return 1
                make = {"hadith": bookmarks.hadith_ref, "narrator": bookmarks.narrator_ref,
                        "chapter": bookmarks.chapter_ref}[args.kind]
                ref, title, subtitle = make(conn, target)
            finally:
                conn.close()
        if args.kind == "tree":
            conn = _connect()
            try:
                where = bookmarks.resolve_tree(conn, args.ref)
                if where is None:
                    print(f"No place '{args.ref}' in the genealogies (e.g. prophets:musa, family:taqrib:6340).",
                          file=sys.stderr)
                    return 1
                which, target = where
                made = bookmarks.tree_ref(conn, which, node_id=target if isinstance(target, str) else None,
                                          person_id=target if isinstance(target, int) else None)
                ref, title, subtitle = made
            finally:
                conn.close()
        folder = store.ensure_path(args.folder).id if args.folder else None
        item = store.add(args.kind, ref, args.title or title, subtitle, folder, args.note or "")
        store.save()
        print(f"Bookmarked: {item.title}  ({item.id})")
        return 0
    if args.action == "remove":
        ok = store.remove(args.kind or "")
        store.save()
        print("Removed." if ok else "No bookmark with that id (iy bookmark list shows the ids).")
        return 0 if ok else 1
    if args.action == "export":
        store.save(args.kind or "isnady_bookmarks.json")
        print(f"Written: {args.kind or 'isnady_bookmarks.json'}")
        return 0
    if args.action == "import":
        other = bookmarks.Store.load(args.kind)
        items, folders = store.merge(other)
        store.save()
        print(f"{items} bookmark(s) and {folders} folder(s) added.")
        return 0
    return 2


def cmd_term(args) -> int:
    from isnady.core import learn

    lang = args.lang
    if args.search or not args.name:
        found = learn.search(args.search or "", lang)
        for t in found:
            print(f"  {t['id']:16} {learn.name(t, lang):30} {t['ar']:18} {learn.text(t, 'short', lang)[:70]}")
        print(f"{len(found)} term(s)")
        return 0
    found = learn.get(args.name) or next(iter(learn.search(args.name, lang)), None)
    if not found:
        print(f"No term '{args.name}'. Try: iy term --search {args.name}", file=sys.stderr)
        return 1
    t = found
    arabic = f"  {t['ar']}" if t["ar"] and lang != "ar" else ""
    print(f"{learn.name(t, lang)}{arabic}   [{learn.category(t['cat'], lang)}]")
    print(f"  {learn.text(t, 'short', lang)}")
    if learn.text(t, "long", lang):
        print(f"  {learn.text(t, 'long', lang)}")
    if t["related"]:
        print("  related: " + ", ".join(learn.name(learn.get(r), lang) for r in t["related"]))
    if t["source"]:
        print(f"  source: {t['source']}")
    return 0


def cmd_learn(args) -> int:
    """Learn → History and method (LRN-H1): the articles, with their live numbers counted from this database."""
    import textwrap

    from isnady.core import learn_history as H

    lang = args.lang or _ui_lang()
    if not args.article:
        for a in H.articles():
            print(f"  {a['id']:10} {H.say(a['title'], lang)}")
        print("Read one: iy learn tadwin   (writing, method, numbers; --lang tr|en|ar)")
        return 0
    a = H.get(args.article) or next(iter(H.search(args.article, lang)), None)
    if a is None:
        print(f"No article '{args.article}'. Try: iy learn", file=sys.stderr)
        return 1
    conn = None
    width = args.width

    def para(text: str, indent: str = "") -> None:
        print(textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent))

    print(H.say(a["title"], lang).upper())
    print()
    para(H.say(a.get("lead"), lang))
    for sec in a["sections"]:
        print()
        print("## " + H.say(sec.get("heading"), lang))
        for p in H.say(sec.get("text"), lang) or []:
            print()
            para(p, "  ")
        if sec.get("block"):
            if conn is None and sec["block"] != "timeline":
                conn = _connect()
            rows = H.block(conn, sec["block"], lang)
            if rows:
                print()
                wide = max(len(r[0]) for r in rows)
                for label, value, note in rows:
                    line = f"    {label:<{wide}}  {value}" if value else f"  [{label}]"
                    print(line + (f"   ({note})" if note and value else ""))
    if a.get("sources"):
        print()
        para(H.label("sources", lang) + ": " + H.say(a["sources"], lang))
    if conn is not None:
        conn.close()
    return 0


def _ui_lang() -> str:
    try:
        from isnady.core import language

        code = language.ui_language()
        return code if code in ("en", "tr", "ar") else "en"
    except Exception:
        return "en"


def cmd_shortcut(args) -> int:
    from isnady.core import shortcut

    program, extra, how = shortcut.launch_command()
    try:
        made = shortcut.create(desktop=not args.no_desktop, menu=not args.no_menu)
    except OSError as exc:
        print(f"The shortcut could not be created: {exc}", file=sys.stderr)
        return 1
    for what, path in made:
        print(f"  {what:8} {path}")
    print(f"It starts {how}: {' '.join([program, *extra])}")
    return 0


def _book_marks(conn, args) -> int | None:
    """The reader's markers (BM3): list them, put one, remove one; None when none of that was asked."""
    from isnady.core import readmarks, works

    titles = {w["key"]: w["title"] for w in works.list_works(conn)}
    if args.marks:
        mine = readmarks.marks()
        print("Your markers:" if mine else "No markers yet (iy book KEY CHAPTER --mark NAME).")
        for m in mine:
            print(f"  {m['name']:30} {readmarks.describe(m, titles.get(m['book'], ''))}")
        left = [p for p in readmarks.recent(20) if p["book"] in titles]
        if left:
            print("\nWhere you left each book (iy book KEY --resume):")
            for p in left:
                print(f"  {p['book']:12} {readmarks.describe(p, titles.get(p['book'], ''))}")
        return 0
    if args.unmark:
        m = readmarks.find(args.unmark)
        if m is None:
            print(f"No marker '{args.unmark}'. See: iy book --marks", file=sys.stderr)
            return 1
        readmarks.remove(m["id"])
        print(f"Removed the marker: {m['name']}")
        return 0
    if args.go:
        m = readmarks.find(args.go)
        if m is None:
            print(f"No marker '{args.go}'. See: iy book --marks", file=sys.stderr)
            return 1
        args.key = m["book"]
        args.resume_mark = m
    return None


def cmd_book(args) -> int:
    from isnady.core import readmarks, works

    conn = _connect()
    works.ensure_collection_works(conn)
    args.resume_mark = None
    done = _book_marks(conn, args)
    if done is not None:
        conn.close()
        return done
    if not args.key:
        # the Sunni books unless the other road, or both, are asked for (NR-DEF1), as the Books page opens
        road = None if args.tradition == "all" else args.tradition
        for w in works.list_works(conn):
            if road and w["tradition"] != road:
                continue
            print(f"  {w['key']:12} {w['title']:32} {w['kind']:8} {w['leaves']:6,} items, {w['chapters']} chapters")
        conn.close()
        return 0
    from isnady.core import books as core_books

    work = works.find_work(conn, core_books.resolve(args.key))
    if work is None:
        print(f"No book '{args.key}'. See: iy book", file=sys.stderr)
        conn.close()
        return 1
    order = works.reading_order(conn, work["id"])
    focus = None
    if args.resume or args.resume_mark:
        # where this book was left, or a marker (BM3): its chapter, from the hadith it was at
        kept = args.resume_mark or readmarks.last(work["key"])
        if kept is None:
            print(f"Nothing kept for {work['title']} yet: read a chapter (iy book {work['key']} N) and it is remembered.")
            conn.close()
            return 0
        at, focus = readmarks.resolve(conn, kept)
        if at in order:
            args.chapter = order.index(at) + 1
            print("Continuing at: " + readmarks.describe(kept, work["title"]))
    if args.chapter is None:
        for i, cid in enumerate(order, 1):
            trail = " › ".join((p["title"] or "") for p in works.path(conn, cid))
            print(f"  {i:4}  {trail}  ({works.leaves(conn, cid, 0, 0)[1]})")
        conn.close()
        return 0
    if not 1 <= args.chapter <= len(order):
        print(f"Chapter {args.chapter} does not exist: 1 to {len(order)}", file=sys.stderr)
        conn.close()
        return 1
    cid = order[args.chapter - 1]
    if focus is not None:
        # start at the hadith kept, not at the top of the chapter
        every, _n = works.leaves(conn, cid, 0, 1_000_000)
        start = next((i for i, it in enumerate(every) if it.get("hadith_id") == focus), 0)
        items, total = every[start:start + args.limit], len(every)
    else:
        items, total = works.leaves(conn, cid, 0, args.limit)
    place = readmarks.place_of(conn, work["key"], cid, focus or next((it["hadith_id"] for it in items
                                                                       if it.get("hadith_id")), None))
    readmarks.remember(place["book"], place["chapter"], place["number"], place["title"], place["place"])
    if args.mark:
        m = readmarks.add(args.mark, place["book"], place["chapter"], place["number"], place["title"], place["place"])
        print(f"Marker put: {m['name']} — {readmarks.describe(m, work['title'])}")
    print(" › ".join([work["title"]] + [(p["title"] or "") for p in works.path(conn, cid)]) + f"   ({total} items)")
    query = core_search.SearchQuery(text="", languages=args.language or [])
    for it in items:
        if it["kind"] == "hadith":
            r = core_search._load_result(conn, it["hadith_id"], [], query)
            print(f"\n#{r.number}")
            for t in r.texts:
                body = " ".join(t.text.split())
                print(f"  [{t.language}] {body[: args.width] + (' ...' if len(body) > args.width else '')}")
        else:
            body = " ".join((it["text"] or it["title"] or "").split())
            print(f"\n{('#' + it['label']) if it['label'] else '→'} {body[: args.width] + (' ...' if len(body) > args.width else '')}")
    if total > len(items) and focus is None:
        print(f"\n… {total - len(items)} more (--limit)")
    conn.close()
    return 0


def cmd_scholar(args) -> int:
    from isnady.core import scholars as S

    conn = _connect()
    people = S.present(conn)
    if not args.name:
        road = None if args.tradition == "all" else args.tradition
        for s in people:
            if road and S.tradition_of(s) != road:
                continue
            print(f"  {s['id']:13} {s['name']:38} {S.tradition_of(s):6} {', '.join(s['roles'])}")
        conn.close()
        return 0
    want = " ".join(args.name).lower()
    s = next((p for p in people if want in (p["id"] + " " + p["name"] + " " + p["full"]).lower()), None)
    if s is None:
        print("No such scholar in the imported data. See: iy scholar", file=sys.stderr)
        conn.close()
        return 1
    print(f"{s['full']}  ({s['arabic']})  {s['dates']}  [{S.tradition_of(s)}]\n  roles: {', '.join(s['roles'])}; "
          f"works: {'; '.join(s['works'])}")
    for st in S.compiler_stats(conn, s):
        print(f"\n  {st['book']}: {st['hadith']:,} hadith, {st['chains']:,} chains, {st['identified']:,} of {st['links']:,} narrators identified")
        print("  teachers: " + "; ".join(f"{t['name']} ({t['count']})" for t in st["teachers"][:6]))
        if st.get("ends"):
            print("  his chains reach: " + "; ".join(f"{e['label']} ({e['count']:,})" for e in st["ends"][:6]))
    g = S.grader_stats(conn, s)
    if g:
        print(f"\n  grades: {g['graded']:,} hadith — " + ", ".join(f"{k} {v:,}" for k, v in g["distribution"].items()))
        for other, a in g["agreement"].items():
            k = f"{a['kappa']:.2f}" if a["kappa"] is not None else "-"
            flag = "   (unusually high: possibly not independent in the source)" if a["agree"] >= 0.95 else ""
            print(f"  vs {other}: agree {100 * a['agree']:.1f}% of {a['common']:,}, kappa {k}, he lower {100 * a['lower']:.1f}% / higher {100 * a['higher']:.1f}%{flag}")
        if g["strictness"] is not None:
            print(f"  strictness {g['strictness']:+.2f} by order: lower {100 * g['lower']:.1f}%, higher {100 * g['higher']:.1f}% "
                  f"of {g['compared']:,} comparisons (negative = stricter)")
    cr = S.critic_stats(conn, s)
    if cr:
        if cr.get("tradition") == "shia":
            print(f"\n  verdicts on narrators: {cr['verdicts']:,} — in the Imami terms: "
                  + ", ".join(f"{label} {n:,}" for _r, label, n in cr["ranks"]) + f", no judgment {cr['unranked']:,}")
            if cr.get("creeds"):
                print("  creed, where stated: " + ", ".join(f"{label} {n:,}" for label, n in cr["creeds"]))
        else:
            print(f"\n  verdicts on narrators: {cr['verdicts']:,} — " + ", ".join(f"{r}:{n}" for r, _l, n in cr["ranks"]))
    conn.close()
    return 0


def cmd_tahric(args) -> int:
    from isnady.core import takhrij

    conn = _connect()
    hid = core_isnad.hadith_id(conn, args.book, args.number)
    if hid is None:
        _no_number(conn, args.book, args.number)
        conn.close()
        return 1
    found = takhrij.related(conn, hid)
    conn.close()
    if not found:
        print("No other narration found (or not built yet: iy ai build).")
        return 0
    print(f"Other narrations of {args.book} {args.number}:")
    for r in found:
        level = "same text" if r["kind"] == "same" else "probably the same report (same Companion)"
        print(f"  {r['book_name']:22} {r['number']:>6}   overlap {r['score']:.2f}   {level}")
    return 0


def cmd_isnads(args) -> int:
    conn = _connect()
    stats = core_isnad.ensure_isnads(conn, progress=print, rebuild=args.rebuild)
    if stats["parsed"] or stats["raw_only"]:
        print(f"Read {stats['parsed'] + stats['raw_only']} chains now.")
    print(f"Parser: {core_isnad.PARSER_ID}")
    for b in core_isnad.book_stats(conn):
        shia = b.get("tradition") == "shia"           # road B: read in the Shia way, ending at a Ma'sum
        end = "a Ma'sum (the Prophet or an Imam)" if shia else "the Prophet"
        print(f"  {b['name']}{' (Shia)' if shia else ''}: {b['chains']} chains, {b['split']} split into narrators "
              f"({100 * b['split'] / b['chains']:.1f}%), {b['marfu']} reach {end}, {b['links']} links")
        for problem, count in b["problems"]:
            print(f"    {count:6}  not split: {problem}")
    if core_narrators_loaded(conn):
        core_narrators.link_narrators(conn, progress=print)
        from isnady.core import books as core_books

        for book, total, found in conn.execute(
            f"""SELECT c.name, COUNT(*), SUM(l.person_id IS NOT NULL) FROM isnad_links l
               JOIN isnads i ON i.id = l.isnad_id JOIN hadiths h ON h.id = i.hadith_id
               JOIN collections c ON c.id = h.collection_id WHERE i.problem IS NULL GROUP BY c.id
               ORDER BY {core_books.order_sql(conn)}"""):
            print(f"  {book}: {found} of {total} narrators in chains identified ({100 * found / total:.1f}%)")
    conn.close()
    return 0


def _no_number(conn, book: str, number: str) -> None:
    """A number the book does not have (CH2): its range and the nearest number."""
    rng = core_isnad.number_range(conn, book)
    near = core_isnad.nearest_number(conn, book, number) if rng else None
    print(f"No hadith {number} in '{book}'."
          + (f" Its numbers run from {rng['first']} to {rng['last']}; the nearest is {near}." if rng else
             " See: iy book"), file=sys.stderr)


def cmd_chain(args) -> int:
    conn = _connect()
    if not args.number:                     # CH2: the book's numbers, to choose from
        rng = core_isnad.number_range(conn, args.book)
        if rng is None:
            print(f"No book '{args.book}'. See: iy book", file=sys.stderr)
            return 1
        print(f"{args.book}: hadith {rng['first']} – {rng['last']} ({rng['count']:,} hadith). "
              f"Example: iy chain {args.book} {core_isnad.random_number(conn, args.book)}")
        return 0
    core_isnad.ensure_isnads(conn)
    row = conn.execute(
        """SELECT h.id, c.name FROM hadiths h JOIN collections c ON c.id = h.collection_id
           WHERE c.key = ? AND h.number = ?""", (args.book, args.number)
    ).fetchone()
    if row is None:
        _no_number(conn, args.book, args.number)
        conn.close()
        return 1
    core_narrators.link_narrators(conn)
    chains = core_isnad.chain(conn, row["id"])
    print(f"{row['name']} {args.number}")
    if not chains:
        print("  no chain stored (no Arabic text for this hadith)")
    for k, ch in enumerate(chains, 1):
        if len(chains) > 1:
            print(f"  Chain {k} of {len(chains)}" + (" (roads joined by tahwil, a second road after a link — \"وعن\" / \"وحدثنا\" — or two narrators at one link)" if k == 1 else ""))
        if ch["problem"] == core_isnad.BORROWED:
            print("  taken from the hadith before it (the book says \"وعنه\" / \"وبهذا الإسناد\"); "
                  "not counted in the statistics")
        elif ch["problem"]:
            print(f"  not split: {ch['problem']}")
        for i, link in enumerate(ch["links"]):
            met = ch.get("meeting")
            if met and link["position"] == met["first_position"]:
                print("      ⤷ tahwil: the roads meet here — " + (
                    f"the text says so (كلهم عن …); attested in {met['attested']} other hadith" if met["said"] else
                    f"not said in the text: the narrator before is found narrating from this one in {met['attested']} "
                    "other hadith, in chains read whole"))
            arabic, meaning, _why = core_isnad.term_label(link["transmission"])
            meaning = meaning if meaning.startswith("(") else f"({meaning})"
            print(f"  {link['position']:>2}. {arabic} {meaning}  {link['raw_name']}")
            nxt = ch["links"][i + 1]["raw_name"] if i + 1 < len(ch["links"]) else ""
            note = core_isnad.link_note(link["raw_name"], nxt)
            if note and not link["person_id"]:
                print(f"      = {note}")
            elif link["person_id"]:
                who = core_narrators.describe(conn, link["person_id"])
                v = who["verdicts"][0] if who["verdicts"] else None
                facts = [f"tabaqa {who['tabaqa']}" if who["tabaqa"] else "",
                         f"d. {who['death_year_ah']} AH" if who["death_year_ah"] else "",
                         f"{v['critic_name']}: {v['phrase'][:160] + (' …' if len(v['phrase']) > 160 else '')}" + (f" ({v['rank_label']})" if v and v["rank"] and v["rank_scheme"] == "shia"
                                                          else f" (rank {v['rank']})" if v and v["rank"] else "") if v else ""]
                conf = link.get("match_confidence")
                how = ("" if conf is None or conf >= 0.8 else
                       "  [by the narrators around him]" if conf >= 0.6 else "  [the famous one of this name]")
                print(f"      = {who['display_name']}{how}")
                print(f"        {'; '.join(f for f in facts if f)}")
            elif link.get("candidates") is not None and core_narrators_loaded(conn):
                n = link["candidates"]
                print(f"      = not identified ({n} possible narrator{'s' if n != 1 else ''})" if n else
                      "      = not identified (no narrator of that name found)")
        if ch["links"]:
            end = core_isnad.end_label(ch)
            print(f"      -> {end}" if end else "      (chain stops here)")
        if args.raw and ch["raw"]:
            print(f"  raw: {ch['raw']}")
        # the chain as the Arabic says it, in the languages asked for (ISN-TR1): --lang tr,en; by default the
        # languages the texts are shown in (iy config view.content_languages), of those isnady reads names in
        from isnady.core import language as content

        codes = ([c.strip() for c in args.lang.split(",") if c.strip()] if args.lang
                 else core_isnad.chain_codes(content.content_languages()))
        people = {link["person_id"]: core_narrators.describe(conn, link["person_id"])
                  for link in ch["links"] if link.get("person_id")}
        for code in codes:
            words = core_isnad.chain_in_words(ch, code, people)
            if words:
                print(f"  [{code}] {words}")
    conn.close()
    return 0


def core_narrators_loaded(conn) -> bool:
    return conn.execute("SELECT 1 FROM persons LIMIT 1").fetchone() is not None


def _famous_list(conn, tradition: str | None) -> int:
    """iy narrator --famous: the famous Companions group by group (FS1), and road B's own famous narrators."""
    from isnady.core import famous

    for group in famous.groups(tradition):
        ids = famous.ids(conn, [p[0] for p in group["people"]])
        if not ids:
            continue
        print(f"\n{group['title']}" + ("  (Shia, al-Najashi)" if group["tradition"] == "shia" else ""))
        rows = dict(((pid, (tab, death, n)) for pid, tab, death, n in conn.execute(
            f"SELECT p.id, p.tabaqa, p.death_year_ah, (SELECT COUNT(*) FROM isnad_links l WHERE l.person_id = p.id) "
            f"FROM persons p WHERE p.id IN ({','.join(str(i) for i in ids)})")))
        by_key = dict(conn.execute(f"SELECT key, id FROM persons WHERE id IN ({','.join(str(i) for i in ids)})")
                      .fetchall())
        for person in group["people"]:
            pid = by_key.get(person[0])
            if pid is None:
                continue
            tab, death, n = rows[pid]
            facts = ([f"tabaqa {tab}"] if tab else []) + ([f"d. {death} AH"] if death else []) + [f"{n} in chains"]
            print(f"  {famous.title(person, 'en'):<46} {person[3]}  (id {pid}) · " + " · ".join(facts))
    conn.close()
    return 0


def cmd_narrator(args) -> int:
    conn = _connect()
    if args.famous:
        # the Companions unless road B, or both, are asked for (NR-DEF1), as the Narrators page opens
        return _famous_list(conn, None if args.tradition == "all" else args.tradition or "sunni")
    if not args.words:
        print("Name a narrator, e.g. iy narrator 'Ebu Bekir', or list the famous ones: iy narrator --famous",
              file=sys.stderr)
        conn.close()
        return 2
    text = " ".join(args.words)
    found = core_narrators.search_persons(conn, text, limit=args.limit)
    # a famous Companion named any way people write him ("Ebubekir", "Omer ibn Hattap", "Hz. Ali") first (FS1)
    from isnady.core import famous

    first = famous.ids(conn, famous.named(text, None if args.tradition == "all" else args.tradition))
    if first:
        found = [(pid, "") for pid in first] + [f for f in found if f[0] not in first]
        found = found[:max(args.limit, len(first))]
    titles = famous.titles(conn, "en")
    if not found:
        print("No narrator found. Import a rijal work first, for example: iy import taqrib <file-or-url>")
        conn.close()
        return 1
    for pid, _name in found:
        who = core_narrators.describe(conn, pid)
        print(f"\n{titles[pid]}  —  {who['display_name']}" if pid in titles else f"\n{who['display_name']}")
        if who["other_names"]:
            print(f"  also: {', '.join(who['other_names'][:6])}")
        if who["tabaqa"]:
            print(f"  tabaqa {who['tabaqa']}: {who['tabaqa_label']}")
        if who["death_year_ah"] or who["death_year_note"]:
            print(f"  death: {who['death_year_ah'] or '?'} AH" + (f"  ({who['death_year_note']})" if who["death_year_note"] else ""))
        for v in who["verdicts"]:
            if v["rank_scheme"] == "shia":         # the Imami terms, not a rank of Ibn Hajar's twelve (SK)
                rank = f"  {v['rank_label']}" + (f", {v['madhhab_label']}" if v.get("madhhab_label") else "") \
                    if v["rank"] else "  no judgment in these words"
            else:
                rank = f"  rank {v['rank']}: {v['rank_label']}" if v["rank"] else ""
            print(f"  {v['critic_name']}, {v['work']}: {v['phrase']}{rank}")
        if who["marks"]:
            print("  books: " + ", ".join(f"{m} {meaning}" for m, meaning in who["marks"]))
        print(f"  identified in {who['in_chains']} chain link{'s' if who['in_chains'] != 1 else ''} of the imported collections")
        if args.limit == 1 or len(found) == 1:
            rel = core_narrators.relations(conn, pid, limit=8)
            if rel["teachers"]:
                print("  narrates from: " + "; ".join(f"{r['name']} ({r['count']})" for r in rel["teachers"]))
            if rel["students"]:
                print("  narrated to:   " + "; ".join(f"{r['name']} ({r['count']})" for r in rel["students"]))
            if rel["compilers"]:
                print("  compilers who narrate from him directly: " + "; ".join(f"{c['book']} ({c['count']})" for c in rel["compilers"]))
            hadith, total = core_narrators.hadiths_of(conn, pid, limit=12)
            if hadith:
                print(f"  in the chains of {total} hadith: " + ", ".join(f"{h['book']} {h['number']}" for h in hadith)
                      + (" …" if total > len(hadith) else ""))
    conn.close()
    return 0


def cmd_export(args) -> int:
    """iy export WHAT … --format F --output FILE (EX1): the same as File → Export…."""
    from isnady.core import formats, transfer

    if args.list or not args.what:
        for kind, spec in transfer.KINDS.items():
            print(f"{kind:10} export: {', '.join(spec['export'])}"
                  + (f"\n{'':10} import: {', '.join(spec['import'])}" if spec["import"] else ""))
        return 0
    kind = args.what
    fmt = args.format or transfer.KINDS[kind]["export"][0]
    target = args.output or ("isnady_" + kind + ("_" + "_".join(args.target) if args.target else "")).replace(":", "-") \
        .replace("/", "_") + transfer.suffix(fmt)
    conn = _connect() if kind not in ("settings", "profile") else None
    pdf = None
    if fmt == "pdf":
        from isnady.gui.pdf import html_to_pdf as pdf
    road = None if args.tradition == "all" else args.tradition
    # a bar on the terminal for the long ones (EX3): "  37%  36,912 / 99,567 hadith  1 min 2 s"
    interactive = sys.stderr.isatty()
    started = time.monotonic()

    def bar(done: int, total: int) -> None:
        if total:
            gone = int(time.monotonic() - started)
            print(f"\r  {done * 100 // total:3d}%  {done:,} / {total:,} hadith  {gone // 60} min {gone % 60} s ",
                  end="", file=sys.stderr, flush=True)

    try:
        several = kind in ("book", "network", "profile") and len(args.target) > 1 or \
            (kind in ("book", "network") and args.target[:1] in (["all"], ["sunni"], ["shia"]))
        if several and kind != "network" and (args.separate or fmt == "isnady-book" or kind == "profile") \
                and not args.output:
            target = target.rsplit(".", 1)[0] if "." in target.rsplit("/", 1)[-1] else target   # a folder
        path = transfer.export(conn, kind, fmt, target, book=args.target[0] if kind in ("book", "network", "statistics") and
                               args.target and not several else "",
                               books=args.target if several and kind in ("book", "network") else None,
                               profiles=args.target if kind == "profile" and len(args.target) > 1 else None,
                               separate=args.separate,
                               chapter=args.chapter, refs=args.target if kind == "hadith" else None,
                               query=" ".join(args.target) if kind in ("search", "narrators") else "",
                               languages=args.language, chains=not args.no_chains,
                               tradition=road if kind != "narrators" else (road if args.tradition else "sunni"),
                               profile=args.target[0] if kind == "profile" and args.target else None, pdf=pdf,
                               progress=lambda m: None if interactive else print(f"  {m}", file=sys.stderr),
                               tick=bar if interactive else None)
    except transfer.TransferError as exc:
        print(("\n" if interactive else "") + str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
    finally:
        if conn is not None:
            conn.close()
    if interactive:
        print(file=sys.stderr)
    print(f"Written ({formats.LABELS.get(fmt, fmt)}): {path}")
    return 0


def cmd_import_data(args) -> int:
    """iy import-data WHAT FILE (EX1): a book, bookmarks, settings, a profile or a backup, as File → Import…."""
    from isnady.core import transfer

    conn = _connect() if args.what == "book" else None
    failed = 0
    try:
        for file in args.file:                     # several files at once (2026-10-24)
            try:
                print(transfer.import_file(conn, args.what, file, fmt=args.format or "", replace=args.replace,
                                           folder=args.folder or "", name=args.name or "",
                                           progress=lambda m: print(f"  {m}", file=sys.stderr)))
            except transfer.TransferError as exc:
                print(f"{file}: {exc}", file=sys.stderr)
                failed += 1
    finally:
        if conn is not None:
            conn.close()
    return 1 if failed else 0


def cmd_reset(args) -> int:
    """iy reset settings|books|all (RST1): back to zero, as Settings → Reset does."""
    from isnady.core import reset

    what = {"settings": "every setting and remembered place", "books": "every imported book and source",
            "all": "the books, the settings, the bookmarks and the downloaded data"}[args.what]
    if not args.yes:
        if not sys.stdin.isatty():
            print("Add --yes to delete without being asked.", file=sys.stderr)
            return 2
        answer = input(f"Delete {what}? This cannot be undone. Type yes: ").strip().lower()
        if answer not in ("yes", "evet", "y", "e"):
            print("Nothing deleted.")
            return 1
    if args.what == "settings":
        print(f"{reset.settings()} settings deleted; isnady is as at its first start.")
        return 0
    conn = _connect()
    try:
        if args.what == "books":
            print(f"{reset.books(conn)} sources deleted. Import them again with: iy catalog import --all")
        else:
            out = reset.everything(conn)
            print(f"Everything deleted: {out['books']} sources, the settings"
                  + (", the bookmarks" if out["bookmarks"] else "") + ".")
    finally:
        conn.close()
    return 0


def cmd_remove(args) -> int:
    conn = _connect()
    with conn:
        cur = conn.execute("DELETE FROM sources WHERE key = ?", (args.key,))
    db.cleanup(conn)
    conn.close()
    if cur.rowcount == 0:
        print(f"No source with key '{args.key}'. See: iy sources", file=sys.stderr)
        return 1
    print(f"Removed source '{args.key}' and everything imported from it.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    prog = os.path.splitext(os.path.basename(sys.argv[0]))[0] or "isnady"
    if prog in ("__main__", "main", "cli", "python", "python3"):
        prog = "isnady"
    p = argparse.ArgumentParser(
        prog=prog,
        description=f"{APP_NAME} {__version__}. Run it without arguments to open the window.",
    )
    p.add_argument("-v", "-V", "--version", "--v", "--V", action="version",
                   version=f"{APP_NAME} {__version__}", help="show the version")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="show the version").set_defaults(func=cmd_version)
    up = sub.add_parser("update", help="update every copy of isnady where it is installed (system, user, venv, pipx, clone)")
    up.add_argument("--yes", action="store_true", help="do not ask before using sudo / the administrator prompt")
    up.add_argument("--check", action="store_true", help="only look: the installed and the latest version on PyPI and "
                                                          "npm, and what is new (nothing is changed)")
    up.add_argument("--pypi", action="store_true", help="update the Python package (every copy); the default")
    up.add_argument("--npm", action="store_true", help="update the npm package too (npm install -g isnady@latest); "
                                                        "with --npm alone: only npm")
    up.set_defaults(func=cmd_update)
    doc = sub.add_parser("doctor", help="every isnady installation, which one each command starts, and what is out of date")
    doc.add_argument("--fix", action="store_true", help="update the copies that are behind, where they are")
    doc.add_argument("--yes", action="store_true", help="with --fix: do not ask")
    doc.add_argument("--offline", action="store_true", help="do not ask PyPI for the latest version")
    doc.set_defaults(func=cmd_doctor)
    dd = sub.add_parser("datadir", help="show or change the data folder (database, settings, your sources)")
    dd.add_argument("path", nargs="?", help="new folder; without it the current one is shown")
    dd.add_argument("--as-is", action="store_true", help="use the folder as it is instead of copying your data there")
    dd.add_argument("--default", action="store_true", help="go back to the platform's default folder")
    dd.set_defaults(func=cmd_datadir)
    cfg = sub.add_parser("config", help="appearance and other settings (the same as Edit → Preferences)")
    cfg.add_argument("action", choices=["list", "get", "set", "reset"])
    cfg.add_argument("key", nargs="?", help="e.g. text.arabic.size, colors.dark.gilt, ui.family")
    cfg.add_argument("value", nargs="?", help="value for set; an empty string restores the default")
    cfg.add_argument("--prefix", default="", help="list only keys starting with this, e.g. text.arabic")
    cfg.set_defaults(func=cmd_config)
    prf = sub.add_parser("profile", help="profiles: several people on one isnady, each with their own settings, "
                                         "place and bookmarks (the same as File → Profiles)")
    prf.add_argument("action", choices=["list", "new", "use", "rename", "delete", "export", "import"])
    prf.add_argument("name", nargs="?", help="the profile's name (import: the file)")
    prf.add_argument("value", nargs="?", help="rename: the new name; export: the file or folder to write; "
                                              "import: a name for the new profile")
    prf.add_argument("--copy", metavar="PROFILE", help="new: start from this profile's settings")
    prf.set_defaults(func=cmd_profile)
    sub.add_parser("formats", help="list supported data formats").set_defaults(func=cmd_formats)
    cat = sub.add_parser("catalog", help="built-in sources and your own: list, import, remove, add, delete")
    cat.add_argument("action", choices=["list", "import", "remove", "add", "delete", "languages"],
                     help="languages: one language for every book — iy catalog languages [add|remove] tr en (LANG2)")
    cat.add_argument("id", nargs="?", help="source id (see list); for add: a title")
    cat.add_argument("format", nargs="?", help="add: data format, see 'iy formats'")
    cat.add_argument("location", nargs="?", help="add: file path or URL")
    cat.add_argument("--language", action="append", help="import: language code or name (repeatable; default ara, tur, eng)")
    cat.add_argument("--all", action="store_true", help="import: every source of the repository (hadith books first, "
                                                        "then the rijal works)")
    cat.add_argument("--license", help="add: licence of the data")
    cat.add_argument("--book", help="add: book key for index files (e.g. bukhari)")
    cat.add_argument("--auth", choices=["none", "basic", "bearer", "apikey"], default="none",
                     help="add: kind of authentication; credentials are asked at import and never stored")
    cat.add_argument("--api-key-header", help="add: header name for an API key")
    cat.add_argument("--api-key-param", help="add: query parameter name for an API key")
    cat.add_argument("--repo", help="list / import: the sources of this repository instead of the chosen one")
    cat.set_defaults(func=cmd_catalog)
    dbp = sub.add_parser("database", help="use a ready database from a file on this computer (isnady.db or the "
                                           "isnady-db zip of isnady-data)")
    dbp.add_argument("action", nargs="?", default="show", choices=["show", "use"])
    dbp.add_argument("file", nargs="?", help="use: isnady.db or isnady-db-<date>.zip")
    dbp.set_defaults(func=cmd_database)
    rp = sub.add_parser("repo", help="data repositories: list, use, show, add, remove (isnady's own is the default)")
    rp.add_argument("action", nargs="?", default="list", choices=["list", "use", "show", "add", "remove"])
    rp.add_argument("target", nargs="?", help="use/show/remove: a repository id; add: a GitHub or Hugging Face "
                                              "repository, a catalog URL or a folder")
    rp.add_argument("--name", help="add: the name shown for it")
    rp.add_argument("--refresh", action="store_true", help="show: read the catalog again from the repository")
    rp.set_defaults(func=cmd_repo)

    imp = sub.add_parser("import", help="import a file or URL")
    imp.add_argument("format", help="data format, see 'iy formats'")
    imp.add_argument("location", help="local file path or http(s) URL")
    imp.add_argument("--name", help="display name of the source")
    imp.add_argument("--license", help="license of the data, e.g. Unlicense, CC-BY-4.0")
    imp.add_argument("--builtin", action="store_true", help="mark as built-in data instead of a User Resource")
    imp.add_argument("--tier", choices=["A", "B", "C"],
                     help="licence tier: A redistributable, B with conditions, C not (default: from --license, unknown = C)")
    sel = imp.add_argument_group("choosing editions from an index")
    sel.add_argument("--edition", action="append", help="edition name, e.g. tur-bukhari (repeatable)")
    sel.add_argument("--book", action="append", help="book key, e.g. bukhari (repeatable)")
    sel.add_argument("--language", action="append", help="language name or code, e.g. Turkish or tur (repeatable)")
    sel.add_argument("--all", action="store_true", help="import every edition in the index")
    sel.add_argument("--edition-key", help="edition name for a single file whose file name is not the edition name")
    sel.add_argument("--include-plain", action="store_true",
                     help="also import diacritics-free Arabic copies (skipped by default)")
    auth = imp.add_argument_group("authentication (credentials are never stored)")
    auth.add_argument("--user", help="username for HTTP Basic authentication; the password is asked")
    auth.add_argument("--password-env", help="read the Basic password from this environment variable instead")
    auth.add_argument("--token", help="bearer token (visible in shell history — prefer --token-env)")
    auth.add_argument("--token-env", help="read the bearer token from this environment variable")
    auth.add_argument("--api-key", help="API key (visible in shell history — prefer --api-key-env)")
    auth.add_argument("--api-key-env", help="read the API key from this environment variable")
    auth.add_argument("--api-key-header", help="header name for the API key (default X-API-Key)")
    auth.add_argument("--api-key-param", help="send the API key as this query parameter instead of a header")
    imp.set_defaults(func=cmd_import)

    se = sub.add_parser("search", help="search hadith text, narrators or scholars (same engine as the app)")
    se.add_argument("words", nargs="*", help="words to search; Arabic diacritics and letter forms are ignored")
    se.add_argument("--recent", action="store_true", help="the last 20 searches, the newest first (the same list as the app)")
    se.add_argument("--clear-recent", action="store_true", help="forget the recent searches")
    se.add_argument("--in", dest="kind", choices=["hadith", "narrators", "scholars"], default="hadith",
                    help="what to search: hadith text (default), narrators of both traditions by name, or scholars")
    se.add_argument("--tradition", choices=["sunni", "shia"],
                    help="with --in narrators: only the Sunni (Taqrib) or the Shia (al-Najashi) narrators")
    se.add_argument("--mode", choices=["all", "any", "phrase", "meaning"], default="all",
                    help="meaning: by meaning and across languages (needs: pip install \"isnady[ai]\" and iy ai build)")
    se.add_argument("--whole-words", action="store_true", help="match whole words only")
    se.add_argument("--book", action="append", help="collection key, e.g. bukhari (repeatable)")
    se.add_argument("--language", action="append", help="language name, e.g. Turkish (repeatable)")
    from isnady.core.grades import FILTER_CODES

    se.add_argument("--grade", action="append", choices=FILTER_CODES, metavar="GRADE",
                    help="only hadith of this grade (repeatable: --grade sahih --grade hasan). Sunni books: sahih, "
                         "hasan, daif, very-weak, fabricated, ungraded. Shia books, in their own scale: imami-sahih, "
                         "imami-hasan, muwaththaq, imami-daif, imami-ungraded. A hadith passes when one of its "
                         "graders gave a grade chosen")
    se.add_argument("--every-grader", action="store_true",
                    help="with --grade: only when every grade the hadith was given is among those chosen")
    se.add_argument("--no-sahihayn", action="store_true",
                    help="with --grade sahih: leave out the hadith of al-Bukhari and Muslim, which no grader grades "
                         "(by default they count as sahih: by their compiler's condition and the community's "
                         "acceptance of the two books)")
    se.add_argument("--limit", type=int, default=10)
    se.add_argument("--offset", type=int, default=0)
    se.add_argument("--width", type=int, default=300, help="characters of text to show")
    se.add_argument("--all-texts", action="store_true", help="also show texts that did not match")
    se.set_defaults(func=cmd_search)

    isn = sub.add_parser("isnads", help="read the chains of transmission from the Arabic texts and report")
    isn.add_argument("--rebuild", action="store_true", help="read every chain again")
    isn.set_defaults(func=cmd_isnads)
    ai = sub.add_parser("ai", help="artificial-intelligence features: build or check the meaning index and takhrij")
    ai.add_argument("action", choices=["build", "status"])
    ai.add_argument("--dims", type=int, default=200, help="build: number of concepts (default 200)")
    ai.set_defaults(func=cmd_ai)
    tm = sub.add_parser("term", help="the glossary: a term of hadith and its sciences, or a search")
    tm.add_argument("name", nargs="?", help="e.g. sahih, mursal, tadlis, kunya")
    tm.add_argument("--search", help="words to look for in names and definitions")
    tm.add_argument("--lang", choices=["en", "tr", "ar"], default="en")
    tm.set_defaults(func=cmd_term)
    ln = sub.add_parser("learn", help="history and method of hadith: how they were written down and gathered, the "
                                     "logic of verification, the numbers of the books imported (counted live)")
    ln.add_argument("article", nargs="?", help="tadwin, writing, method or numbers (none: the list)")
    ln.add_argument("--lang", choices=["en", "tr", "ar"], help="the language (default: the interface language)")
    ln.add_argument("--width", type=int, default=100, help="characters per line")
    ln.set_defaults(func=cmd_learn)
    lf = sub.add_parser("life", help="the life of a Companion, a narrator or a scholar, in English, Turkish or Arabic")
    lf.add_argument("name", nargs="+", help="any part of the name, in Arabic or Latin letters")
    lf.add_argument("--lang", choices=["en", "tr", "ar"], help="the language (default: the interface language)")
    lf.add_argument("--tradition", choices=["sunni", "shia"], help="look only among the narrators of one tradition")
    lf.add_argument("--limit", type=int, default=1, help="how many people to show (default 1)")
    lf.add_argument("--source", action="store_true", help="also print his entry in the classical work the life is "
                                                          "summarised from (al-Dhahabi's Siyar; downloaded once)")
    lf.set_defaults(func=cmd_life)
    tr_ = sub.add_parser("tree", help="genealogies: the prophets, Quraysh, a narrator's family, his line of learning")
    tr_.add_argument("which", choices=["prophets", "quraysh", "family", "learning"])
    tr_.add_argument("name", nargs="?", help="a narrator (family, learning) or someone to find in the tree")
    tr_.add_argument("--depth", type=int, default=2, help="learning: steps of teachers and of students (default 2)")
    tr_.add_argument("--width", type=int, default=4, help="learning: how many at each step (default 4)")
    tr_.add_argument("--hadith", action="store_true", help="prophets: the hadith that speak of the prophet found "
                                                           "(e.g. iy tree prophets Musa --hadith)")
    tr_.set_defaults(func=cmd_tree)
    ca = sub.add_parser("cache", help="the cache that keeps the counts of books, narrators, scholars …: info, clear")
    ca.add_argument("action", nargs="?", choices=["info", "clear"], default="info")
    ca.set_defaults(func=cmd_cache)
    bm = sub.add_parser("bookmark", help="bookmarks in folders: list, folders, add, remove, export, import")
    bm.add_argument("action", choices=["list", "folders", "add", "remove", "export", "import"])
    bm.add_argument("kind", nargs="?", help="add: hadith | narrator | scholar | term | chapter | tree; list: only "
                                            "that kind; remove: the id; export/import: the file")
    bm.add_argument("ref", nargs="?", help="add: bukhari:1, a narrator's key, a scholar's or term's id, bukhari:3, prophets:musa")
    bm.add_argument("--folder", help="a folder, Prayer or Prayer/Friday (made if missing)")
    bm.add_argument("--title", help="the title to keep (default: isnady's)")
    bm.add_argument("--note", help="a note of your own")
    bm.set_defaults(func=cmd_bookmark)
    sh = sub.add_parser("shortcut", help="put isnady on the desktop and in the applications menu, with its icon")
    sh.add_argument("--no-desktop", action="store_true", help="only the applications menu")
    sh.add_argument("--no-menu", action="store_true", help="only the desktop")
    sh.set_defaults(func=cmd_shortcut)
    bk = sub.add_parser("book", help="read a book in its own order: the list, a book's chapters, or a chapter")
    bk.add_argument("key", nargs="?", help="e.g. bukhari, abudawud, taqrib; none = the list")
    bk.add_argument("chapter", nargs="?", type=int, help="chapter number in reading order (see: iy book KEY)")
    bk.add_argument("--language", action="append", help="show only this language (repeatable)")
    bk.add_argument("--limit", type=int, default=20)
    bk.add_argument("--width", type=int, default=160)
    bk.add_argument("--tradition", choices=("sunni", "shia", "all"), default="sunni",
                    help="the list: the Sunni books (default), the Shia ones, or all")
    bk.add_argument("--resume", action="store_true", help="go on where you left this book (its chapter and hadith)")
    bk.add_argument("--mark", metavar="NAME", help="put a marker of this name at the chapter shown")
    bk.add_argument("--marks", action="store_true", help="your markers and where you left each book")
    bk.add_argument("--go", metavar="NAME", help="open a marker (by its name or the start of it)")
    bk.add_argument("--unmark", metavar="NAME", help="remove a marker")
    bk.set_defaults(func=cmd_book)
    sc = sub.add_parser("scholar", help="the hadith scholars in the data: compilers, graders, critics, with measured statistics")
    sc.add_argument("name", nargs="*", help="part of a name, e.g. albani, bukhari; none = the list")
    sc.add_argument("--tradition", choices=("sunni", "shia", "all"), default="sunni",
                    help="the list: the Sunni scholars (default), the Shia ones, or all")
    sc.set_defaults(func=cmd_scholar)
    tk = sub.add_parser("tahric", help="other narrations of a hadith in the imported books (takhrij)")
    tk.add_argument("book")
    tk.add_argument("number")
    tk.set_defaults(func=cmd_tahric)
    nr = sub.add_parser("narrator", help="look up a narrator: verdict, rank, tabaqa, death, books")
    nr.add_argument("words", nargs="*", help="part of the name, e.g. الزهري, 'سفيان بن عيينة', 'ابو هريرة', "
                                             "'Ebu Bekir', 'Omer ibn Hattap'")
    nr.add_argument("--limit", type=int, default=5)
    nr.add_argument("--famous", action="store_true",
                    help="list the famous Companions by group: the four Caliphs, the Ten, the Mothers of the "
                         "Believers, the Prophet's household, those who narrated most (and road B's Ashab al-Ijma')")
    nr.add_argument("--tradition", choices=("sunni", "shia", "all"), default=None,
                    help="only this road's famous ones (with --famous: Sunni unless asked) or matches")
    nr.set_defaults(func=cmd_narrator)
    ex = sub.add_parser("export", help="hadith, a book or chapter, search results, bookmarks, narrators, the isnad "
                                       "network, settings, a profile or a backup, in many formats (iy export --list)")
    ex.add_argument("what", nargs="?", choices=("hadith", "book", "search", "bookmarks", "narrators", "network",
                                                "settings", "profile", "backup", "statistics"))
    ex.add_argument("target", nargs="*", help="hadith: bukhari:1 bukhari:5-10; book/network: bukhari, several "
                                              "(bukhari muslim) or all / sunni / shia; search and narrators: the "
                                              "words; profile: its name, or several")
    ex.add_argument("--separate", action="store_true", help="several books: each in its own file, in the folder "
                                                            "--output (isnady books and profiles always are)")
    ex.add_argument("--format", "-f", help="json, jsonl, csv, tsv, xlsx, md, html, txt, epub, docx, pdf, sqlite, "
                                           "isnady-book, graphml, gexf … (iy export --list)")
    ex.add_argument("--output", "-o", help="the file to write (default: a name in this folder)")
    ex.add_argument("--chapter", type=int, help="book: only this chapter (its number)")
    ex.add_argument("--language", action="append", help="hadith/book/search: only these languages (repeatable), "
                                                        "e.g. Arabic, Turkish")
    ex.add_argument("--no-chains", action="store_true", help="hadith/book/search: without the chains")
    ex.add_argument("--tradition", choices=("sunni", "shia", "all"), help="narrators (default sunni) and network")
    ex.add_argument("--list", action="store_true", help="what can be exported and imported, in which formats")
    ex.set_defaults(func=cmd_export)
    im = sub.add_parser("import-data", help="bring back a book, bookmarks, settings, a profile or a backup from a "
                                            "file made by iy export or File → Export…")
    im.add_argument("what", choices=("book", "bookmarks", "settings", "profile", "backup"))
    im.add_argument("file", nargs="+", help="one file or several")
    im.add_argument("--format", help="when the file name does not say it")
    im.add_argument("--replace", action="store_true", help="bookmarks/settings: replace instead of adding")
    im.add_argument("--folder", help="bookmarks: put them in this folder")
    im.add_argument("--name", help="profile: the new profile's name")
    im.set_defaults(func=cmd_import_data)
    lg = sub.add_parser("log", help="isnady's log: the last lines, errors only, a text, follow it, crash reports")
    lg.add_argument("--lines", "-n", type=int, default=60, help="the last N lines (0: all; default 60)")
    lg.add_argument("--level", choices=("info", "warning", "error"), help="only lines of this level and above")
    lg.add_argument("--grep", help="only lines holding this text")
    lg.add_argument("--follow", "-f", action="store_true", help="keep showing new lines (Ctrl+C ends)")
    lg.add_argument("--crash", action="store_true", help="the newest crash report instead")
    lg.add_argument("--files", action="store_true", help="list the log files")
    lg.add_argument("--path", action="store_true", help="print where the log is")
    lg.add_argument("--before", metavar="YYYY-MM-DD", help="remove what was logged before this day")
    lg.add_argument("--clear", action="store_true", help="empty the log and remove the crash reports")
    lg.set_defaults(func=cmd_log)
    rs = sub.add_parser("reset", help="back to zero: delete all settings, all books, or everything")
    rs.add_argument("what", choices=("settings", "books", "all"))
    rs.add_argument("--yes", action="store_true", help="do not ask")
    rs.set_defaults(func=cmd_reset)
    ch = sub.add_parser("chain", help="show the chain of one hadith")
    ch.add_argument("book", help="collection key, e.g. bukhari")
    ch.add_argument("number", nargs="?", help="hadith number, e.g. 1; none = the book's numbers, first to last")
    ch.add_argument("--raw", action="store_true", help="also print the chain as written")
    ch.add_argument("--lang", help="the chain in words in these languages, e.g. tr,en (default: the languages the "
                                   "texts are shown in; Turkish and English so far)")
    ch.set_defaults(func=cmd_chain)

    sub.add_parser("sources", help="list imported sources").set_defaults(func=cmd_sources)
    st = sub.add_parser("stats", help="count what the database holds; corpus, narrators, chains, grades, books, graders "
                                      "for the statistics in depth")
    st.add_argument("topic", nargs="?", choices=["corpus", "narrators", "chains", "grades", "books", "model", "lab", "graders"],
                    help="corpus: everything below; narrators: reliability, concentration, pillars; chains: length, "
                         "weakest link, time gaps; grades: weakest narrator and length against the grade; books: the "
                         "books compared; model: what each scholar's grade follows (ordinal regression) and the hadith "
                         "graded higher or lower than their chain; lab: correlations (Spearman, partial, BH) and tests (Stuart–Maxwell, Kruskal–Wallis, Mann–Whitney); graders: agreement, model, strictness, disputed hadith")
    st.add_argument("--grader", help="with 'model': only the scholars whose name contains this")
    st.add_argument("--csv", metavar="DIR", help="also write every table behind the statistics as CSV files into DIR")
    st.add_argument("--book", help="collection key, e.g. abudawud; @shia for all Shia books; @all for both roads, one "
                                   "after the other (default: all Sunni books; "
                                   "for graders, the book with most graders)")
    st.add_argument("--recompute", action="store_true", help="compute again instead of reading the saved results")
    st.add_argument("--limit", type=int, default=10, help="rows to list (disputed hadith, strongest relations)")
    st.add_argument("--explain", nargs="?", const="all", metavar="TERM",
                    help="every measure in plain words (what it measures, how to read it, what it means for hadith "
                         "science, an example); or one, e.g. gini, kendall, kappa")
    st.set_defaults(func=cmd_stats)
    rm = sub.add_parser("remove", help="remove a source and everything imported from it")
    rm.add_argument("key", help="source key, see 'iy sources'")
    rm.set_defaults(func=cmd_remove)
    return p


def _utf8_output() -> None:
    """Windows prints to a pipe or file in the old code page (cp1252/cp1254), which has no Arabic:
    "iy -h | more" or "iy narrator الزهري > out.txt" crashed. Always write UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if (stream.encoding or "").lower().replace("-", "") != "utf8":
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8_output()
    args = build_parser().parse_args(argv)
    try:                                            # a new version starts clean, keeping the user's own (CFG1)
        from isnady.core import upgrade

        changed = upgrade.check()
        if changed:
            print(upgrade.message(changed), file=sys.stderr)
        from isnady.core import imports as core_imports

        if getattr(args, "func", None) not in (cmd_catalog, cmd_version, cmd_reset):
            # no book yet (FR1): one command brings them all, as one click does in the window
            probe = _connect()
            empty = probe.execute("SELECT 1 FROM hadiths LIMIT 1").fetchone() is None
            probe.close()
            if empty:
                print("isnady has no books yet. Import every hadith book and rijal work of isnady-data with one "
                      "command: iy catalog import --all", file=sys.stderr)
        cut = core_imports.interrupted() if getattr(args, "func", None) is not cmd_catalog else None
        if cut:
            print(f"Note: an import did not finish ({cut['started'].replace('T', ' ')}): {', '.join(cut['titles'][:6])}. "
                  "Import it again: iy catalog import ID (iy catalog list shows what is imported).", file=sys.stderr)
    except Exception:
        pass
    # a book may be named by its full name (musnad_ahmad_ibn_hanbal), its key (ahmad) or an earlier id
    if getattr(args, "book", None) and getattr(args, "func", None) not in (cmd_catalog,):
        from isnady.core import books as core_books

        args.book = [core_books.resolve(b) for b in args.book] if isinstance(args.book, list) \
            else core_books.resolve(args.book)
    # every command in the log too (LOG1): what was asked, how it ended, how long it took — not `iy log` itself
    from isnady.core import log

    logged = getattr(args, "func", None) is not cmd_log
    if logged:
        log.setup("command line")
        log.get("cli").info("▶ iy %s", " ".join(argv if argv is not None else sys.argv[1:]))
    started = time.perf_counter()
    try:
        code = args.func(args)
        if logged:
            log.get("cli").info("%s exit %s in %.1f s", "✔" if not code else "✖", code or 0,
                                time.perf_counter() - started)
        return code
    except BrokenPipeError:
        # the output was cut short by the reader ("iy search … | head"): not an error
        import os

        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0
    except Exception as exc:
        if logged:
            log.get("cli").error("✖ iy %s", getattr(args, "command", ""), exc_info=exc)
        raise


def cmd_log(args) -> int:
    """iy log (LOG1): the log of isnady — the last lines, only errors, a text, follow it, the crash reports, clear."""
    from isnady.core import log

    if args.path:
        print(log.path())
        return 0
    if args.clear:
        print(f"{log.clear()} log file(s) emptied or removed: {log.folder()}")
        return 0
    if args.before:
        print(f"{log.delete_before(args.before)} line(s) before {args.before} removed")
        return 0
    if args.files:
        for f in log.files():
            st = f.stat()
            print(f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))}  {st.st_size / 1024:8.1f} KB  {f}")
        return 0
    target = log.path()
    if args.crash:
        crashes = [f for f in log.files() if f.name.startswith("crash_")]
        if not crashes:
            print("No crash reports.")
            return 0
        target = crashes[0]
    if not target.exists():
        print(f"No log yet: {target}")
        return 0
    print(log.read(target, args.lines, args.level or "", args.grep or ""))
    if args.follow:
        size = target.stat().st_size
        try:
            while True:
                time.sleep(1)
                now = target.stat().st_size
                if now < size:
                    size = 0
                if now > size:
                    with target.open(encoding="utf-8", errors="replace") as f:
                        f.seek(size)
                        sys.stdout.write(f.read())
                        sys.stdout.flush()
                    size = now
        except KeyboardInterrupt:
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
