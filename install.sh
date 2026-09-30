#!/usr/bin/env bash
# isnady installer for Linux and macOS
#
#   curl -fsSL https://raw.githubusercontent.com/bayramkotan/isnady/main/install.sh | bash
#   ./install.sh            inside a clone of the repository: editable (developer) install of that clone
#   ISNADY_INSTALL=pypi ./install.sh   the PyPI release even inside a clone
#
# Removes every earlier copy first (an old copy in ~/.local hides a newer one elsewhere), installs one
# copy, makes sure its commands are on PATH, then checks the result with `iy doctor`.
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
    BREAK="--break-system-packages"        # PEP 668: the distribution manages its Python; a user install is still fine
fi
USER_FLAG="--user"
[ -n "${VIRTUAL_ENV:-}" ] && USER_FLAG=""  # inside a virtual environment there is no user folder

MODE=pypi; SRC=""
if [ "${ISNADY_INSTALL:-}" != "pypi" ] && [ -f pyproject.toml ] && grep -q '^name = "isnady"' pyproject.toml; then
    MODE=dev; SRC="$(pwd)"
elif command -v pipx > /dev/null 2>&1; then
    MODE=pipx
fi
say "Python: $PY ($("$PY" -V 2>&1)); mode: $MODE${SRC:+ ($SRC)}"

# ---------------------------------------------------------------- 1. remove earlier copies
say "Looking for earlier installations"
if command -v pipx > /dev/null 2>&1 && pipx list --short 2>/dev/null | grep -q '^isnady '; then
    say "Removing the pipx copy"; pipx uninstall isnady || true
fi
for _ in 1 2 3 4; do
    # which copy would Python import now? (user folder first, like the shell)
    WHERE="$("$PY" -c 'import isnady, os; print(os.path.dirname(os.path.dirname(isnady.__file__)))' 2>/dev/null || true)"
    [ -n "$WHERE" ] || break
    USER_SITE="$("$PY" -c 'import site; print(site.getusersitepackages())')"
    if [ "$WHERE" = "$USER_SITE" ] || [ -w "$WHERE" ]; then
        say "Removing isnady from $WHERE"
        if [ "$WHERE" = "$USER_SITE" ]; then "$PY" -m pip uninstall -y isnady $BREAK > /dev/null || break
        else "$PY" -s -m pip uninstall -y isnady $BREAK > /dev/null || break; fi
    else
        warn "A copy of isnady is installed for the whole system in $WHERE."
        if ask "Remove it with sudo (recommended)?"; then
            sudo "$PY" -s -m pip uninstall -y isnady $BREAK > /dev/null || break
        else
            warn "Kept. It may hide the copy installed now."; break
        fi
    fi
done

# ---------------------------------------------------------------- 2. install one copy
case "$MODE" in
    dev)  say "Installing the clone in $SRC (editable: every git pull is live)"
          "$PY" -m pip install -q $USER_FLAG -e "$SRC" $BREAK ;;
    pipx) say "Installing with pipx"; pipx install --force isnady ;;
    pypi) say "Installing the latest release from PyPI"
          "$PY" -m pip install -q $USER_FLAG -U isnady $BREAK ;;
esac

# ---------------------------------------------------------------- 3. commands on PATH
if [ "$MODE" = pipx ]; then BIN="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$HOME/.local/bin")"
elif [ -n "$USER_FLAG" ]; then BIN="$("$PY" -m site --user-base)/bin"
else BIN="$(dirname "$PY")"; fi
case ":$PATH:" in
    *":$BIN:"*) ;;
    *)  warn "$BIN is not in PATH, so the isnady commands would not be found."
        RC="$HOME/.bashrc"; [ "${SHELL##*/}" = zsh ] && RC="$HOME/.zshrc"
        if ask "Add it to $RC?"; then
            printf '\n# isnady\nexport PATH="%s:$PATH"\n' "$BIN" >> "$RC"; say "Added. Open a new terminal, or run: source $RC"
        fi
        export PATH="$BIN:$PATH" ;;
esac
hash -r 2>/dev/null || true

# ---------------------------------------------------------------- 4. check
say "Checking"
"$BIN/iy" -V
if "$BIN/iy" -h 2>/dev/null | grep -q doctor; then   # iy doctor exists from 0.0.7 on
    "$BIN/iy" doctor --offline || warn "iy doctor reported something above; 'iy doctor --fix' can repair it."
fi
say "Done. Start isnady with: iy   (or isnady-gui)"
