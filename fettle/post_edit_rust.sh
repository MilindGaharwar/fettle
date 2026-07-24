#!/usr/bin/env bash
set -uo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null || echo "")

if [[ "$FILE_PATH" != *.rs ]]; then
    exit 0
fi

if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

SEARCH_DIR=$(dirname "$FILE_PATH")
CARGO_TOML=""
while [[ "$SEARCH_DIR" != "/" ]]; do
    if [[ -f "$SEARCH_DIR/Cargo.toml" ]]; then
        CARGO_TOML="$SEARCH_DIR/Cargo.toml"
        break
    fi
    SEARCH_DIR=$(dirname "$SEARCH_DIR")
done

if [[ -z "$CARGO_TOML" ]]; then
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

TOOLCHAIN_BIN="$(dirname "$(command -v cargo 2>/dev/null || echo "${HOME}/.cargo/bin/cargo")")"
if [[ -d "$TOOLCHAIN_BIN" ]]; then
    export PATH="${TOOLCHAIN_BIN}:${PATH}"
    CARGO_BIN="${TOOLCHAIN_BIN}/cargo"
else
    CARGO_BIN=$(which cargo 2>/dev/null || echo "")
fi
if [[ -z "$CARGO_BIN" || ! -x "$CARGO_BIN" ]]; then
    exit 0
fi

CARGO_OUTPUT=$("$CARGO_BIN" check --message-format=json --quiet --manifest-path "$CARGO_TOML" 2>&1 || true)

echo "$CARGO_OUTPUT" | python3 -c "
import sys, json
errors = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    if msg.get('reason') == 'compiler-message':
        m = msg.get('message', {})
        level = m.get('level', '')
        if level == 'error':
            rendered = m.get('rendered', m.get('message', ''))
            errors.append(rendered.strip())
if errors:
    ctx = 'cargo check errors:\n' + '\n'.join(errors[:10])
    out = {
        'decision': 'block',
        'reason': ctx,
        'hookSpecificOutput': {
            'hookEventName': 'PostToolUse',
            'additionalContext': ctx
        }
    }
    print(json.dumps(out))
    sys.exit(2)
"

exit $?
