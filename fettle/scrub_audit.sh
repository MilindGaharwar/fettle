#!/usr/bin/env bash
# Permanent CI guard: no private/internal strings may enter this public repo.
set -uo pipefail
PATTERN='crucible|/data/bridge|cortex|nexus|contextbus|localhost:4000|logact'
# Optional local blocklist (never committed): one extended-regex per line.
EXTRA_FILE="${FETTLE_SCRUB_EXTRA:-$HOME/.config/fettle/scrub-extra}"
if [ -f "$EXTRA_FILE" ]; then
  while IFS= read -r extra; do
    [ -n "$extra" ] && PATTERN="$PATTERN|$extra"
  done < "$EXTRA_FILE"
fi
HITS=$(grep -riE "$PATTERN" . \
  --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.fettle \
  --exclude-dir=.venv --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache \
  --exclude-dir=.state --exclude-dir=build --exclude-dir=dist \
  --exclude-dir=node_modules --exclude-dir=.opencode --exclude-dir=.claude \
  --exclude=.git --exclude=scrub_audit.sh || true)
if [ -n "$HITS" ]; then
  echo "SCRUB AUDIT FAILED — private strings found:" >&2
  echo "$HITS" >&2
  exit 1
fi
echo "scrub audit clean"
