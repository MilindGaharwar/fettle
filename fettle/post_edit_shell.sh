#!/usr/bin/env bash
set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null || echo "")

if [[ "$FILE_PATH" != *.sh ]]; then
    exit 0
fi

if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# ── Edit tracking for live_test_gate.py ──────────────────────────────
TRACKING_FILE="${FETTLE_EDIT_TRACKING:-/tmp/fettle-edits.jsonl}"
python3 - "$FILE_PATH" "$TRACKING_FILE" <<'PYEOF'
import json, time, sys
entry = {"file": sys.argv[1], "ts": time.time(), "tool": "Edit", "tested": False}
with open(sys.argv[2], "a") as f:
    f.write(json.dumps(entry) + chr(10))
PYEOF

SHELLCHECK_BIN=$(which shellcheck 2>/dev/null || echo "")
if [[ -z "$SHELLCHECK_BIN" ]]; then
    exit 0
fi

SC_OUTPUT=$("$SHELLCHECK_BIN" -f json "$FILE_PATH" 2>/dev/null || true)

RESULT=$(echo "$SC_OUTPUT" | python3 -c "
import sys, json
try:
    findings = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

if not findings:
    sys.exit(0)

lines = []
for f in findings:
    code = f.get('code', 0)
    line = f.get('line', 0)
    level = f.get('level', 'info').upper()
    message = f.get('message', '')
    lines.append(f'[{level}] line {line}: SC{code} - {message}')

summary = '\n'.join(lines[:20])
count = len(findings)
out = {
    'hookSpecificOutput': {
        'hookEventName': 'PostToolUse',
        'additionalContext': f'ShellCheck ({count} finding(s)):\n{summary}'
    }
}
print(json.dumps(out))
" 2>/dev/null)

if [[ -n "$RESULT" ]]; then
    echo "$RESULT"
fi

exit 0
