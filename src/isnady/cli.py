"""The isnady command line (no Qt needed).

Every name runs it: `isnady ARGS`, `iy ARGS`, `isnady-cli ARGS`.

Examples
  iy search niyet
  iy search النيات --book bukhari
  iy chain bukhari 1
  iy isnads
  iy import taqrib https://raw.githubusercontent.com/OpenITI/0875AH/master/data/0852IbnHajarCasqalani/0852IbnHajarCasqalani.TaqribTahdhib/0852IbnHajarCasqalani.TaqribTahdhib.JK000121-ara1.completed
  iy narrator الزهري
  iy ai build
  iy search --mode meaning "komşu hakları"
  iy tahric bukhari 1
  iy scholar albani
  iy book bukhari 2
  iy shortcut
  iy stats graders --book abudawud
  iy term mursal --lang tr
  iy import fawazahmed0 ./tur-bukhari.json
  iy import fawazahmed0 https://example.org/editions.json --book bukhari --language tur
  iy import fawazahmed0 https://example.org/ed.json --user bayram          (password is asked)
  iy import fawazahmed0 https://example.org/ed.json --token-env MY_TOKEN
  iy config list --prefix text.arabic
  iy config set text.arabic.size 22
  iy config set colors.dark.gilt "#5A4A1E"
  iy config reset text.arabic
  iy catalog list
  iy catalog import fawaz-muslim --language ara --language tur
  iy catalog import taqrib
  iy catalog import --all --language ara --language tur
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
        subprocess.run(argv, check=False)


def cmd_doctor(args) -> int:
    from isnady import doctor

    report = doctor.diagnose(check_pypi=not args.offline)
    print(doctor.as_text(report))
    if not args.fix or not report.fixes:
        return 1 if report.problems else 0
    print()
    _run_plan(report.fixes, args.yes)
    after = doctor.diagnose(check_pypi=False)
    print("\nAfter updating:\n" + doctor.as_text(after))
    return 1 if after.problems else 0


def cmd_update(args) -> int:
    """Update every copy of isnady where it is installed. Nothing is removed or moved."""
    from isnady import doctor

    report = doctor.diagnose(check_pypi=True)
    if not report.fixes:
        print(f"isnady {report.running_version} is up to date"
              + (f" (latest on PyPI: {report.latest})." if report.latest else " (PyPI could not be reached)."))
        return 0
    print("Updating every copy of isnady where it is installed:")
    _run_plan(report.fixes, args.yes)
    after = doctor.diagnose(check_pypi=False)
    print("\n" + doctor.as_text(after))
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


def cmd_catalog(args) -> int:
    from isnady.core import catalog

    if args.action == "list":
        conn = _connect()
        for kind, title in (("builtin", "Built-in sources"), ("user", "Your sources (User Resources)")):
            entries = [e for e in catalog.all_entries() if (e.builtin if kind == "builtin" else not e.builtin)]
            print(f"\n{title}")
            if not entries:
                print("  none yet — add one: iy catalog add TITLE FORMAT FILE-OR-URL")
            for e in entries:
                st = catalog.status(conn, e)
                state = ("imported" + (f" ({', '.join(catalog.language_label(l) if len(l) == 3 else l for l in st['languages'])})"
                                       if st["languages"] else "") + f", {st['count']:,}"
                         if st["imported"] else "not imported")
                print(f"  {e.id:16} {e.title:42} {state}")
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
    entry = catalog.find(args.id or "")
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
    short = {g: next((s["name"] for s in SCHOLARS if g in s.get("grader_names", [])), g) for g in r["graders"]}
    print(f"{key}: {len(r['graders'])} graders" + (f"  (from {r['from_file']})" if r.get("from_file") else "  (computed and saved)"))
    if len(r["graders"]) < 2:
        print("  one grader: no agreement or model")
        return 0
    a = r["alpha"]
    print(f"Krippendorff's alpha (ordinal) {a['value']:.3f}  95% {a['ci'][0]:.3f}–{a['ci'][1]:.3f}  over {a['units']:,} hadith")
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
        print(f"  {short[g]:40} {s['value']:+.3f}  [{s['ci'][0]:+.3f}, {s['ci'][1]:+.3f}]")
    c = r["certainty"]
    print(f"The model is sure (≥95%) of {c['high']:,} of {c['total']:,} hadith, unsure (<60%) of {c['low']:,}; "
          f"{r['disputed_total']:,} disputed")
    for d in r["disputed"][: args.limit]:
        grades = ", ".join(f"{short[g]}: {sg.LABELS[v]}" for g, v in d["grades"].items())
        print(f"  #{d.get('number')}: model {sg.LABELS[d['consensus']]} ({100 * d['certainty']:.0f}%) — {grades}")
    return 0


def cmd_stats_corpus(args) -> int:
    """iy stats narrators|chains|grades|books — the corpus statistics of the Statistics page (ST7), as text;
    --csv DIR writes every table behind them."""
    from isnady.core import stats_corpus as sc

    conn = _connect()
    r = sc.cached(conn, args.book, lambda m: print(f"  … {m}", file=sys.stderr), args.recompute)
    if r.get("empty"):
        print("Nothing to measure: import a hadith collection first.")
        return 0
    groups = [g for g, _d in r["groups"]]
    pct = lambda x, n: f"{100 * x / n:.1f}%" if n else "—"  # noqa: E731
    o = r["overview"]
    print(f"{args.book or 'All books'}: {o['hadith']:,} hadith, {o['chains']:,} chains, {o['identified']:,} of "
          f"{o['links']:,} names identified ({pct(o['identified'], o['links'])}), {o['narrators']:,} narrators"
          + (f"  (from {r['from_file']})" if r.get("from_file") else "  (computed and saved)"))
    topic = args.topic
    if topic in ("narrators", None):
        n = r["narrators"]
        print("\nReliability (Ibn Hajar's ranks in six groups)")
        for label, row in (("all narrators of the Taqrib", n["rank_all"]), ("narrators in these chains", n["rank_people"]),
                           ("every name in these chains", n["rank_links"])):
            total = sum(row)
            print(f"  {label:30} " + " · ".join(f"{g} {pct(v, total)}" for g, v in zip(groups, row)))
        c = n["concentration"]
        if c.get("gini") is not None:
            print(f"\nConcentration: busiest 1% carry {100 * c['top1']:.1f}%, busiest 10% {100 * c['top10']:.1f}%; "
                  f"{c['half_by']:,} of {c['people']:,} narrators carry half; Gini {c['gini']:.3f}")
        print("\nThe pillars (times in the chains · hadith · rank)")
        for p in n["pillars"][:args.limit]:
            print(f"  {p['links']:6,} {p['hadith']:6,}  rank {p['rank'] or '—':>2}  {p['name']}")
    if topic in ("chains", None):
        ch = r["chains"]
        print("\nChain length (names: chains): " + ", ".join(f"{k}: {v:,}" for k, v in ch["lengths"]))
        total = sum(ch["weakest"])
        print("Weakest link: " + " · ".join(f"{g} {pct(v, total)}" for g, v in zip(groups, ch["weakest"])))
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
    if topic in ("books", None):
        print("\nBooks: chains · median length · identified · reach the Prophet · narrators")
        for b in r["books"]["rows"]:
            print(f"  {b['name'][:32]:32} {b['chains']:7,}  {b['median_length'] or '—':>3}  {100 * b['identified']:5.1f}%  "
                  f"{100 * b['reaching']:5.1f}%  {b['narrators']:6,}")
    if args.csv:
        _write_corpus_csv(r, args.csv)
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


def cmd_stats(args) -> int:
    if getattr(args, "topic", None) == "graders":
        return cmd_stats_graders(args)
    if getattr(args, "topic", None) in ("corpus", "narrators", "chains", "grades", "books"):
        if args.topic == "corpus":
            args.topic = None
        return cmd_stats_corpus(args)
    conn = _connect()
    books = conn.execute(
        """SELECT c.id, c.name,
                  (SELECT COUNT(*) FROM hadiths h WHERE h.collection_id = c.id) AS hadiths,
                  (SELECT COUNT(DISTINCT g.hadith_id) FROM grades g JOIN hadiths h ON h.id = g.hadith_id
                   WHERE h.collection_id = c.id) AS graded,
                  (SELECT COUNT(*) FROM grades g JOIN hadiths h ON h.id = g.hadith_id
                   WHERE h.collection_id = c.id) AS grades
           FROM collections c ORDER BY c.name"""
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
    conn.close()
    shown = rows[args.offset:args.offset + args.limit]
    more = f" (the closest {len(rows)} are ranked)" if total > len(rows) else ""
    print(f"{total} narrator{'s' if total != 1 else ''} found{more}")
    for r in shown:
        view = r["view"]
        known = view["reading"] or view["full_reading"]
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
        if r["tradition"] != "shia":
            facts.append(f"{r['in_chains']} in chains")
        print("  " + " · ".join(facts))
    return 0


def cmd_search(args) -> int:
    conn = _connect()
    if args.kind != "hadith":
        return _search_people(conn, args)
    if args.mode == "meaning":
        return _search_meaning(conn, args)
    core_search.ensure_index(conn, progress=lambda m: print(m, file=sys.stderr))
    q = core_search.SearchQuery(
        text=" ".join(args.words), mode=args.mode, whole_words=args.whole_words,
        collections=args.book or [], languages=args.language or [], limit=args.limit, offset=args.offset,
    )
    page = core_search.search(conn, q)
    conn.close()
    print(f"{page.total} hadith found in {page.elapsed_ms} ms"
          f"{'' if page.used_index else ' (no FTS5 index available; slower scan)'}")
    for r in page.results:
        print(f"\n{r.collection_name} #{r.number}")
        if r.grades:
            print("  grades: " + "; ".join(f"{g}: {v}" for g, v in r.grades))
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
                                languages=args.language or [], limit=args.limit, offset=args.offset)
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


def cmd_term(args) -> int:
    from isnady.core import learn

    lang = args.lang
    if args.search or not args.name:
        found = learn.search(args.search or "", lang)
        for t in found:
            print(f"  {t['id']:16} {learn.name(t, lang):30} {t['ar']:18} {t['short'][lang][:70]}")
        print(f"{len(found)} term(s)")
        return 0
    found = learn.get(args.name) or next(iter(learn.search(args.name, lang)), None)
    if not found:
        print(f"No term '{args.name}'. Try: iy term --search {args.name}", file=sys.stderr)
        return 1
    t = found
    print(f"{learn.name(t, lang)}  {t['ar']}   [{learn.categories()[t['cat']][lang]}]")
    print(f"  {t['short'][lang]}")
    if t["long"][lang]:
        print(f"  {t['long'][lang]}")
    if t["related"]:
        print("  related: " + ", ".join(learn.name(learn.get(r), lang) for r in t["related"]))
    if t["source"]:
        print(f"  source: {t['source']}")
    return 0


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


def cmd_book(args) -> int:
    from isnady.core import works

    conn = _connect()
    works.ensure_collection_works(conn)
    if not args.key:
        for w in works.list_works(conn):
            print(f"  {w['key']:12} {w['title']:32} {w['kind']:8} {w['leaves']:6,} items, {w['chapters']} chapters")
        conn.close()
        return 0
    work = works.find_work(conn, args.key)
    if work is None:
        print(f"No book '{args.key}'. See: iy book", file=sys.stderr)
        conn.close()
        return 1
    order = works.reading_order(conn, work["id"])
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
    items, total = works.leaves(conn, cid, 0, args.limit)
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
    if total > len(items):
        print(f"\n… {total - len(items)} more (--limit)")
    conn.close()
    return 0


def cmd_scholar(args) -> int:
    from isnady.core import scholars as S

    conn = _connect()
    people = S.present(conn)
    if not args.name:
        for s in people:
            print(f"  {s['id']:13} {s['name']:38} {', '.join(s['roles'])}")
        conn.close()
        return 0
    want = " ".join(args.name).lower()
    s = next((p for p in people if want in (p["id"] + " " + p["name"] + " " + p["full"]).lower()), None)
    if s is None:
        print("No such scholar in the imported data. See: iy scholar", file=sys.stderr)
        conn.close()
        return 1
    print(f"{s['full']}  ({s['arabic']})  {s['dates']}\n  roles: {', '.join(s['roles'])}; works: {'; '.join(s['works'])}")
    for st in S.compiler_stats(conn, s):
        print(f"\n  {st['book']}: {st['hadith']:,} hadith, {st['chains']:,} chains, {st['identified']:,} of {st['links']:,} narrators identified")
        print("  teachers: " + "; ".join(f"{t['name']} ({t['count']})" for t in st["teachers"][:6]))
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
        print(f"\n  verdicts on narrators: {cr['verdicts']:,} — " + ", ".join(f"{r}:{n}" for r, _l, n in cr["ranks"]))
    conn.close()
    return 0


def cmd_tahric(args) -> int:
    from isnady.core import takhrij

    conn = _connect()
    hid = core_isnad.hadith_id(conn, args.book, args.number)
    if hid is None:
        print(f"No hadith {args.number} in '{args.book}'. See: iy stats", file=sys.stderr)
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
        print(f"  {b['name']}: {b['chains']} chains, {b['split']} split into narrators "
              f"({100 * b['split'] / b['chains']:.1f}%), {b['marfu']} reach the Prophet, {b['links']} links")
        for problem, count in b["problems"]:
            print(f"    {count:6}  not split: {problem}")
    if core_narrators_loaded(conn):
        core_narrators.link_narrators(conn, progress=print)
        for book, total, found in conn.execute(
            """SELECT c.name, COUNT(*), SUM(l.person_id IS NOT NULL) FROM isnad_links l
               JOIN isnads i ON i.id = l.isnad_id JOIN hadiths h ON h.id = i.hadith_id
               JOIN collections c ON c.id = h.collection_id WHERE i.problem IS NULL GROUP BY c.id ORDER BY c.name"""):
            print(f"  {book}: {found} of {total} narrators in chains identified ({100 * found / total:.1f}%)")
    conn.close()
    return 0


def cmd_chain(args) -> int:
    conn = _connect()
    core_isnad.ensure_isnads(conn)
    row = conn.execute(
        """SELECT h.id, c.name FROM hadiths h JOIN collections c ON c.id = h.collection_id
           WHERE c.key = ? AND h.number = ?""", (args.book, args.number)
    ).fetchone()
    if row is None:
        print(f"No hadith {args.number} in '{args.book}'. See: iy stats", file=sys.stderr)
        conn.close()
        return 1
    core_narrators.link_narrators(conn)
    chains = core_isnad.chain(conn, row["id"])
    print(f"{row['name']} {args.number}")
    if not chains:
        print("  no chain stored (no Arabic text for this hadith)")
    for ch in chains:
        if ch["problem"]:
            print(f"  not split: {ch['problem']}")
        for link in ch["links"]:
            arabic, meaning, _why = core_isnad.term_label(link["transmission"])
            print(f"  {link['position']:>2}. {arabic} ({meaning})  {link['raw_name']}")
            if link["person_id"]:
                who = core_narrators.describe(conn, link["person_id"])
                v = who["verdicts"][0] if who["verdicts"] else None
                facts = [f"tabaqa {who['tabaqa']}" if who["tabaqa"] else "",
                         f"d. {who['death_year_ah']} AH" if who["death_year_ah"] else "",
                         f"Ibn Hajar: {v['phrase']}" + (f" (rank {v['rank']})" if v and v["rank"] else "") if v else ""]
                print(f"      = {who['display_name']}")
                print(f"        {'; '.join(f for f in facts if f)}")
            elif link.get("candidates") is not None and core_narrators_loaded(conn):
                n = link["candidates"]
                print(f"      = not identified ({n} possible narrator{'s' if n != 1 else ''})" if n else
                      "      = not identified (no narrator of that name found)")
        if ch["links"]:
            print("      -> the Prophet" if ch["reaches_prophet"] else "      (chain stops here)")
        if args.raw and ch["raw"]:
            print(f"  raw: {ch['raw']}")
    conn.close()
    return 0


def core_narrators_loaded(conn) -> bool:
    return conn.execute("SELECT 1 FROM persons LIMIT 1").fetchone() is not None


def cmd_narrator(args) -> int:
    conn = _connect()
    found = core_narrators.search_persons(conn, " ".join(args.words), limit=args.limit)
    if not found:
        print("No narrator found. Import a rijal work first, for example: iy import taqrib <file-or-url>")
        conn.close()
        return 1
    for pid, _name in found:
        who = core_narrators.describe(conn, pid)
        print(f"\n{who['display_name']}")
        if who["other_names"]:
            print(f"  also: {', '.join(who['other_names'][:6])}")
        if who["tabaqa"]:
            print(f"  tabaqa {who['tabaqa']}: {who['tabaqa_label']}")
        if who["death_year_ah"] or who["death_year_note"]:
            print(f"  death: {who['death_year_ah'] or '?'} AH" + (f"  ({who['death_year_note']})" if who["death_year_note"] else ""))
        for v in who["verdicts"]:
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
    sub.add_parser("formats", help="list supported data formats").set_defaults(func=cmd_formats)
    cat = sub.add_parser("catalog", help="built-in sources and your own: list, import, remove, add, delete")
    cat.add_argument("action", choices=["list", "import", "remove", "add", "delete"])
    cat.add_argument("id", nargs="?", help="source id (see list); for add: a title")
    cat.add_argument("format", nargs="?", help="add: data format, see 'iy formats'")
    cat.add_argument("location", nargs="?", help="add: file path or URL")
    cat.add_argument("--language", action="append", help="import: language code or name (repeatable; default ara, tur, eng)")
    cat.add_argument("--all", action="store_true", help="import: every built-in source (hadith books, then the Taqrib)")
    cat.add_argument("--license", help="add: licence of the data")
    cat.add_argument("--book", help="add: book key for index files (e.g. bukhari)")
    cat.add_argument("--auth", choices=["none", "basic", "bearer", "apikey"], default="none",
                     help="add: kind of authentication; credentials are asked at import and never stored")
    cat.add_argument("--api-key-header", help="add: header name for an API key")
    cat.add_argument("--api-key-param", help="add: query parameter name for an API key")
    cat.set_defaults(func=cmd_catalog)

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
    se.add_argument("words", nargs="+", help="words to search; Arabic diacritics and letter forms are ignored")
    se.add_argument("--in", dest="kind", choices=["hadith", "narrators", "scholars"], default="hadith",
                    help="what to search: hadith text (default), narrators of both traditions by name, or scholars")
    se.add_argument("--tradition", choices=["sunni", "shia"],
                    help="with --in narrators: only the Sunni (Taqrib) or the Shia (al-Najashi) narrators")
    se.add_argument("--mode", choices=["all", "any", "phrase", "meaning"], default="all",
                    help="meaning: by meaning and across languages (needs: pip install \"isnady[ai]\" and iy ai build)")
    se.add_argument("--whole-words", action="store_true", help="match whole words only")
    se.add_argument("--book", action="append", help="collection key, e.g. bukhari (repeatable)")
    se.add_argument("--language", action="append", help="language name, e.g. Turkish (repeatable)")
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
    tm.add_argument("--lang", choices=["en", "tr"], default="en")
    tm.set_defaults(func=cmd_term)
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
    bk.set_defaults(func=cmd_book)
    sc = sub.add_parser("scholar", help="the hadith scholars in the data: compilers, graders, critics, with measured statistics")
    sc.add_argument("name", nargs="*", help="part of a name, e.g. albani, bukhari; none = the list")
    sc.set_defaults(func=cmd_scholar)
    tk = sub.add_parser("tahric", help="other narrations of a hadith in the imported books (takhrij)")
    tk.add_argument("book")
    tk.add_argument("number")
    tk.set_defaults(func=cmd_tahric)
    nr = sub.add_parser("narrator", help="look up a narrator: verdict, rank, tabaqa, death, books")
    nr.add_argument("words", nargs="+", help="part of the name, e.g. الزهري, 'سفيان بن عيينة', 'ابو هريرة'")
    nr.add_argument("--limit", type=int, default=5)
    nr.set_defaults(func=cmd_narrator)
    ch = sub.add_parser("chain", help="show the chain of one hadith")
    ch.add_argument("book", help="collection key, e.g. bukhari")
    ch.add_argument("number", help="hadith number, e.g. 1")
    ch.add_argument("--raw", action="store_true", help="also print the chain as written")
    ch.set_defaults(func=cmd_chain)

    sub.add_parser("sources", help="list imported sources").set_defaults(func=cmd_sources)
    st = sub.add_parser("stats", help="count what the database holds; corpus, narrators, chains, grades, books, graders "
                                      "for the statistics in depth")
    st.add_argument("topic", nargs="?", choices=["corpus", "narrators", "chains", "grades", "books", "graders"],
                    help="corpus: everything below; narrators: reliability, concentration, pillars; chains: length, "
                         "weakest link, time gaps; grades: weakest narrator and length against the grade; books: the "
                         "books compared; graders: agreement, model, strictness, disputed hadith")
    st.add_argument("--csv", metavar="DIR", help="also write every table behind the statistics as CSV files into DIR")
    st.add_argument("--book", help="collection key, e.g. abudawud (default: the book with most graders)")
    st.add_argument("--recompute", action="store_true", help="compute again instead of reading the saved results")
    st.add_argument("--limit", type=int, default=10, help="disputed hadith to list")
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
    try:
        return args.func(args)
    except BrokenPipeError:
        # the output was cut short by the reader ("iy search … | head"): not an error
        import os

        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
