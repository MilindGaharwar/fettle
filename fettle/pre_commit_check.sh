#!/usr/bin/env bash
# Fettle pre-commit entry: run quality checks on changed files.
# Runs from the pre-commit-cloned Fettle checkout; the consumer repo is $PWD.
set -euo pipefail
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${FETTLE_PYTHON:-python3}"
exec "$PYTHON" "$HOOK_DIR/scripts/cli.py" check --changed
