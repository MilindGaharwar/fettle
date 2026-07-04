#!/bin/bash
export PATH="$HOME/Library/Python/3.9/bin:$HOME/.local/bin:$PATH"
PYTHON="$HOME/.local/share/uv/python/cpython-3.14.5-macos-aarch64-none/bin/python3"
if [ ! -f "$PYTHON" ]; then
    PYTHON="python3"
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$PYTHON" "$SCRIPT_DIR/quality_scan.py" "$@"
