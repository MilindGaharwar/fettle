#!/usr/bin/env bash
# Fettle pre-commit entry: validate project-local semgrep rule packs.
# An invalid pack silently disables ALL its rules (v0.4.1 incident class).
set -euo pipefail
if ! command -v semgrep >/dev/null 2>&1; then
  echo "fettle: semgrep not on PATH — rule validation skipped (advisory)" >&2
  exit 0
fi
status=0
for dir in .fettle/rules .lint/semgrep; do
  [ -d "$dir" ] || continue
  for f in "$dir"/*.yml "$dir"/*.yaml; do
    [ -f "$f" ] || continue
    if ! semgrep scan --config "$f" --validate --metrics=off >/dev/null 2>&1; then
      echo "fettle: INVALID rule pack: $f — all its rules are silently disabled" >&2
      semgrep scan --config "$f" --validate --metrics=off 2>&1 | tail -5 >&2 || true
      status=1
    fi
  done
done
exit "$status"
