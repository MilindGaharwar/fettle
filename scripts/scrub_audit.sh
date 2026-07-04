#!/usr/bin/env bash
# Permanent CI guard: no private/corporate strings may enter this public repo.
set -uo pipefail
PATTERN='crucible|mb.?its|/data/bridge|cortex|nexus|contextbus|mb-marketplace|localhost:4000|MMILIND|logact'
HITS=$(grep -riE "$PATTERN" . \
  --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.fettle \
  --exclude=scrub_audit.sh || true)
if [ -n "$HITS" ]; then
  echo "SCRUB AUDIT FAILED — private strings found:" >&2
  echo "$HITS" >&2
  exit 1
fi
echo "scrub audit clean"
