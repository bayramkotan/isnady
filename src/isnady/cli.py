"""isnady-cli — command-line access to the data layer (no Qt needed).

Examples
  isnady-cli formats
  isnady-cli import fawazahmed0 ./tur-bukhari.json
  isnady-cli import fawazahmed0 https://example.org/editions.json --book bukhari --language tur
  isnady-cli import fawazahmed0 https://example.org/ed.json --user bayram          (password is asked)
  isnady-cli import fawazahmed0 https://example.org/ed.json --token-env MY_TOKEN
  isnady-cli import fawazahmed0 https://example.org/ed.json --api-key-env KEY --api-key-header X-API-Key
  isnady-cli sources
  isnady-cli stats
  isnady-cli remove <source-key>
"""

import argparse
import getpass
import os
import sys

from isnady import APP_NAME, __version__
from isnady.data import db
from isnady.data.fetch import Auth, ResourceError
from isnady.data.importers import SourceInfo, get_importer, list_importers
from isnady.data.paths import db_path


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


def cmd_formats(_args) -> int:
    for imp in list_importers():
        print(f"{imp.format_id:14} {imp.title}\n{'':14} {imp.description}")
    return 0


def cmd_import(args) -> int:
    try:
        importer = get_importer(args.format)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 2
    source = SourceInfo(
        location=args.location,
        name=args.name,
        license=args.license,
        origin="builtin" if args.builtin else "user",
        auth=_auth_from_args(args),
    )
    options = {
        "editions": args.edition,
        "books": args.book,
        "languages": args.language,
        "all": args.all,
        "edition_key": args.edition_key,
    }
    conn = db.connect()
    try:
        report = importer.run(conn, source, options, progress=lambda m: print(f"  {m}"))
    except ResourceError as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(f"Done: source '{report.source_key}' — {len(report.editions)} edition(s), "
          f"{report.hadiths} hadith, {report.grades} grades")
    for warning in report.warnings:
        print(f"  warning: {warning}")
    return 0


def cmd_sources(_args) -> int:
    conn = db.connect()
    rows = conn.execute(
        """SELECT s.key, s.name, s.format, s.origin, s.auth_type, s.license, s.location, s.imported_at,
                  COUNT(e.id) AS editions, COALESCE(SUM(e.hadith_count), 0) AS hadiths
           FROM sources s LEFT JOIN editions e ON e.source_id = s.id
           GROUP BY s.id ORDER BY s.origin, s.key"""
    ).fetchall()
    conn.close()
    if not rows:
        print("No sources yet. Add one with: isnady-cli import <format> <file-or-url>")
        return 0
    for r in rows:
        label = "User Resource" if r["origin"] == "user" else "Built-in"
        print(f"[{label}] {r['key']}  —  {r['name']}")
        print(f"    format {r['format']}, auth {r['auth_type']}, license {r['license'] or 'not stated'}")
        print(f"    {r['editions']} edition(s), {r['hadiths']} hadith, imported {r['imported_at']}")
        print(f"    last imported from {r['location']}")
    return 0


def cmd_stats(_args) -> int:
    conn = db.connect()
    rows = conn.execute(
        """SELECT c.name AS book, e.key, e.language, e.hadith_count,
                  (SELECT COUNT(*) FROM grades g JOIN hadiths h ON h.id = g.hadith_id
                   WHERE h.edition_id = e.id) AS grades
           FROM editions e JOIN collections c ON c.id = e.collection_id
           ORDER BY c.name, e.language, e.key"""
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM hadiths").fetchone()[0]
    conn.close()
    print(f"Database: {db_path()}")
    for r in rows:
        print(f"  {r['book']:40} {r['key']:22} {r['language']:11} {r['hadith_count']:>6} hadith {r['grades']:>6} grades")
    print(f"Total: {total} hadith in {len(rows)} edition(s)")
    return 0


def cmd_remove(args) -> int:
    conn = db.connect()
    with conn:
        cur = conn.execute("DELETE FROM sources WHERE key = ?", (args.key,))
    conn.execute("DELETE FROM collections WHERE id NOT IN (SELECT collection_id FROM editions)")
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        print(f"No source with key '{args.key}'. See: isnady-cli sources", file=sys.stderr)
        return 1
    print(f"Removed source '{args.key}' and everything imported from it.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="isnady-cli", description=f"{APP_NAME} {__version__} data tools")
    p.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("formats", help="list supported data formats").set_defaults(func=cmd_formats)

    imp = sub.add_parser("import", help="import a file or URL")
    imp.add_argument("format", help="data format, see 'isnady-cli formats'")
    imp.add_argument("location", help="local file path or http(s) URL")
    imp.add_argument("--name", help="display name of the source")
    imp.add_argument("--license", help="license of the data, e.g. Unlicense, CC-BY-4.0")
    imp.add_argument("--builtin", action="store_true", help="mark as built-in data instead of a User Resource")
    sel = imp.add_argument_group("choosing editions from an index")
    sel.add_argument("--edition", action="append", help="edition name, e.g. tur-bukhari (repeatable)")
    sel.add_argument("--book", action="append", help="book key, e.g. bukhari (repeatable)")
    sel.add_argument("--language", action="append", help="language name or code, e.g. Turkish or tur (repeatable)")
    sel.add_argument("--all", action="store_true", help="import every edition in the index")
    sel.add_argument("--edition-key", help="edition name for a single file whose file name is not the edition name")
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

    sub.add_parser("sources", help="list imported sources").set_defaults(func=cmd_sources)
    sub.add_parser("stats", help="count what the database holds").set_defaults(func=cmd_stats)
    rm = sub.add_parser("remove", help="remove a source and everything imported from it")
    rm.add_argument("key", help="source key, see 'isnady-cli sources'")
    rm.set_defaults(func=cmd_remove)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
