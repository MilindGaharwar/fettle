#!/usr/bin/env bash
# Fettle launcher — resolves a Python >= 3.11 interpreter portably and runs
# the given script from this directory, forwarding stdin and arguments.
#
# Resolution order:
#   1. $FETTLE_PYTHON (explicit override)
#   2. python3 on PATH, if >= 3.11
#   3. python3.13 / 3.12 / 3.11 / 3.10 on PATH
#   4. `uv python find` (if uv is installed)
#   5. newest uv-managed cpython under ~/.local/share/uv/python
#
# A missing/too-old interpreter is a loud, readable error — never a silent pass.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$1"
shift || true

_ok() {  # is $1 a python >= 3.11?
    [ -n "$1" ] && [ -x "$1" ] && "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null
}

PYTHON="${FETTLE_PYTHON:-}"

if ! _ok "$PYTHON"; then
    PYTHON="$(command -v python3 || true)"
fi

if ! _ok "$PYTHON"; then
    for v in 3.13 3.12 3.11; do
        PYTHON="$(command -v "python$v" || true)"
        _ok "$PYTHON" && break
    done
fi

if ! _ok "$PYTHON" && command -v uv >/dev/null 2>&1; then
    PYTHON="$(uv python find 2>/dev/null || true)"
fi

if ! _ok "$PYTHON"; then
    PYTHON="$(ls -d "$HOME"/.local/share/uv/python/cpython-3.1[1-9]*/bin/python3 2>/dev/null | sort -V | tail -1 || true)"
fi

if ! _ok "$PYTHON"; then
    echo "fettle: no Python >= 3.11 found (tried FETTLE_PYTHON, python3, python3.11-3.13, uv). Set FETTLE_PYTHON." >&2
    exit 0  # hooks must not hard-fail the session over environment issues
fi

# --- Tool bootstrap: ensure ruff and semgrep are available ---
_ensure_tool() {
    local tool="$1"
    [ -x "$HOME/.local/bin/$tool" ] && return 0
    command -v "$tool" >/dev/null 2>&1 && return 0
    # Install via uv tool (preferred) or pipx
    if command -v uv >/dev/null 2>&1; then
        uv tool install "$tool" >/dev/null 2>&1 && return 0
    elif command -v pipx >/dev/null 2>&1; then
        pipx install "$tool" >/dev/null 2>&1 && return 0
    fi
    echo "fettle: could not auto-install $tool (no uv or pipx)" >&2
}
_ensure_tool ruff
_ensure_tool semgrep

exec "$PYTHON" "$SCRIPT_DIR/$TARGET" "$@"
