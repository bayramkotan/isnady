#!/usr/bin/env bash
# isnady installer and updater for Linux and macOS
#
#   curl -fsSL https://raw.githubusercontent.com/bayramkotan/isnady/main/install.sh | bash
#   sudo bash install.sh        install or update for every user of this computer
#   ./install.sh                inside a clone of the repository: editable install of that clone
#
# isnady may be installed anywhere: for all users, for one user, in any virtual environment, with pipx,
# or editable from a clone. Nothing is removed or moved: every copy found is UPDATED WHERE IT IS (with
# sudo when needed). When there is no copy yet, it is installed the way this script is run.
set -eu

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*" >&2; }
ask()  {   # works under "curl | bash" too: the answer is read from the terminal
    local a=n
    if [ -r /dev/tty ]; then printf '%s [y/N] ' "$1" > /dev/tty; read -r a < /dev/tty || a=n; fi
    case "$a" in y|Y|yes|e|E|evet) return 0 ;; *) return 1 ;; esac
}

PY="${PYTHON:-}"
if [ -z "$PY" ]; then
    for c in python3 python; do if command -v "$c" > /dev/null 2>&1; then PY="$(command -v "$c")"; break; fi; done
fi
[ -n "$PY" ] || { warn "Python 3.10 or newer was not found. Install it with your package manager first."; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
    || { warn "isnady needs Python 3.10 or newer; $PY is $("$PY" -V 2>&1)."; exit 1; }

BREAK=""
if "$PY" -c 'import os, sys, sysconfig; sys.exit(0 if os.path.exists(os.path.join(sysconfig.get_path("stdlib"), "EXTERNALLY-MANAGED")) else 1)'; then
    BREAK="--break-system-packages"        # PEP 668: the distribution manages its Python
fi
IN_VENV="$("$PY" -c 'import sys; print(1 if sys.prefix != sys.base_prefix else 0)')"
CLONE=""
if [ "${ISNADY_INSTALL:-}" != "pypi" ] && [ -f pyproject.toml ] && grep -q '^name = "isnady"' pyproject.toml; then
    CLONE="$(pwd)"
fi
say "Python: $PY ($("$PY" -V 2>&1))${CLONE:+; clone: $CLONE}"

# ---------------------------------------------------------------- every copy this Python can see
COPIES="$("$PY" - << 'PYEOF'
import json, site, sys
from importlib import metadata
from pathlib import Path
from urllib.parse import unquote, urlparse
user = Path(site.getusersitepackages())
dirs = []
for p in sys.path + list(getattr(site, "getsitepackages", lambda: [])()) + [str(user)]:
    if p and Path(p).is_dir() and Path(p) not in dirs:
        dirs.append(Path(p))
seen = set()
for d in dirs:
    for dist in metadata.distributions(path=[str(d)]):
        if (dist.metadata["Name"] or "").lower() != "isnady" or (str(d), dist.version) in seen:
            continue
        seen.add((str(d), dist.version))
        where = str(d)
        try:
            info = json.loads(dist.read_text("direct_url.json") or "{}")
        except ValueError:
            info = {}
        if info.get("dir_info", {}).get("editable"):
            kind, where = "editable", unquote(urlparse(info["url"]).path)
        elif "pipx" in str(d):
            kind = "pipx"
        elif str(d).startswith(str(user)):
            kind = "user"
        elif sys.prefix != sys.base_prefix and str(d).startswith(sys.prefix):
            kind = "venv"
        else:
            kind = "system"
        print(f"{kind}|{where}|{dist.version}")
PYEOF
)"

update_copy() {   # kind where version
    case "$1" in
        user)     say "Updating the copy for this user ($2, $3)"
                  "$PY" -m pip install -q --user -U isnady $BREAK ;;
        venv)     say "Updating the copy in this virtual environment ($2, $3)"
                  "$PY" -m pip install -q -U isnady ;;
        pipx)     say "Updating the pipx copy ($3)"; pipx upgrade isnady || true ;;
        editable) if [ -n "$CLONE" ] && [ "$2" = "$CLONE" ]; then
                      : # this clone is (re)installed below
                  else
                      say "Refreshing the editable install of $2 ($3); update that clone with git pull"
                      ( cd "$2" && "$PY" -m pip install -q $([ "$IN_VENV" = 0 ] && echo --user) -e . $BREAK ) || true
                  fi ;;
        system)   if [ -w "$2" ]; then
                      say "Updating the copy for all users ($2, $3)"
                      "$PY" -s -m pip install -q -U isnady $BREAK
                  else
                      warn "isnady $3 is installed for all users in $2."
                      if ask "Update it there with sudo?"; then
                          sudo "$PY" -s -m pip install -q -U isnady $BREAK || warn "That update failed."
                      else
                          warn "Not updated; it stays at $3."
                      fi
                  fi ;;
    esac
}

if [ -n "$COPIES" ]; then
    printf '%s\n' "$COPIES" | while IFS='|' read -r kind where version; do
        update_copy "$kind" "$where" "$version" < /dev/null
    done
fi
if [ -n "$CLONE" ]; then
    say "Installing the clone in $CLONE (editable: every git pull is live)"
    "$PY" -m pip install -q $([ "$IN_VENV" = 0 ] && echo --user) -e "$CLONE" $BREAK
elif [ -z "$COPIES" ]; then
    # nothing yet: install the way this script is run
    if [ "$IN_VENV" = 1 ]; then
        say "Installing into this virtual environment"; "$PY" -m pip install -q -U isnady
    elif [ "$(id -u)" = 0 ]; then
        say "Installing for all users"; "$PY" -m pip install -q -U isnady $BREAK
    elif command -v pipx > /dev/null 2>&1; then
        say "Installing with pipx"; pipx install isnady
    else
        say "Installing for this user"; "$PY" -m pip install -q --user -U isnady $BREAK
    fi
fi

# ---------------------------------------------------------------- commands on PATH, then a check
USER_BIN="$("$PY" -m site --user-base)/bin"
if [ "$IN_VENV" = 0 ] && [ "$(id -u)" != 0 ] && [ -x "$USER_BIN/iy" ]; then
    case ":$PATH:" in
        *":$USER_BIN:"*) ;;
        *)  warn "$USER_BIN is not in PATH, so the isnady commands would not be found."
            RC="$HOME/.bashrc"; [ "${SHELL##*/}" = zsh ] && RC="$HOME/.zshrc"
            if ask "Add it to $RC?"; then
                printf '\n# isnady\nexport PATH="%s:$PATH"\n' "$USER_BIN" >> "$RC"; say "Added. Open a new terminal, or run: source $RC"
            fi
            export PATH="$USER_BIN:$PATH" ;;
    esac
fi
hash -r 2>/dev/null || true
say "Checking"
if command -v iy > /dev/null 2>&1; then
    iy -V
    if iy -h 2>/dev/null | grep -q doctor; then iy doctor --offline || true; fi
fi
say "Done. Start isnady with: iy   (or isnady-gui)"
