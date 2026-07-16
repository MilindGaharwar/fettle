#!/usr/bin/env bash
# Fettle pre-commit entry: validate project-local semgrep rule packs.
# An invalid pack silently disables ALL its rules (v0.4.1 incident class).
# Uses the offline-safe validator: semgrep >= 1.168 --validate fetches a
# registry pack and hard-fails behind TLS-intercepting proxies.
set -euo pipefail
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${FETTLE_PYTHON:-python3}"
if ! command -v semgrep >/dev/null 2>&1; then
  echo "fettle: semgrep not on PATH — rule validation skipped (advisory)" >&2
  exit 0
fi
status=0
for dir in .fettle/rules .lint/semgrep; do
  [ -d "$dir" ] || continue
  for f in "$dir"/*.yml "$dir"/*.yaml; do
    [ -f "$f" ] || continue
    if ! FETTLE_PACK="$f" "$PYTHON" - <<PYEOF
import os, sys
sys.path.insert(0, os.path.join("$HOOK_DIR", "scripts"))
from semgrep_util import validate_rule_pack
ok, err = validate_rule_pack(os.environ["FETTLE_PACK"])
if not ok:
    print(err, file=sys.stderr)
sys.exit(0 if ok else 1)
PYEOF
    then
      echo "fettle: INVALID rule pack: $f — all its rules are silently disabled" >&2
      status=1
    fi
  done
done
exit "$status"
