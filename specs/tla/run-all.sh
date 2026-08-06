#!/usr/bin/env bash
# Run all TLA+ specs through the TLC model checker.
# Requires: Java 11+, tla2tools.jar (auto-downloaded if missing).
#
# Usage:
#   ./specs/tla/run-all.sh          # run all specs
#   ./specs/tla/run-all.sh PolicyCapsule  # run one spec

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TLA2TOOLS="${TLA2TOOLS:-$SCRIPT_DIR/tla2tools.jar}"
TLA2TOOLS_URL="https://github.com/tlaplus/tlaplus/releases/download/v1.8.0/tla2tools.jar"

# Auto-download tla2tools.jar if not present
if [[ ! -f "$TLA2TOOLS" ]]; then
    echo "Downloading tla2tools.jar..."
    curl -fsSL -o "$TLA2TOOLS" "$TLA2TOOLS_URL"
    echo "Downloaded to $TLA2TOOLS"
fi

# Verify Java
if ! command -v java &>/dev/null; then
    echo "ERROR: Java 11+ required but not found. Install via: brew install openjdk" >&2
    exit 1
fi

# Specs to check (all .cfg files, or filtered by argument)
SPECS=()
if [[ $# -gt 0 ]]; then
    for name in "$@"; do
        cfg="$SCRIPT_DIR/${name}.cfg"
        if [[ ! -f "$cfg" ]]; then
            echo "ERROR: $cfg not found" >&2
            exit 1
        fi
        SPECS+=("$name")
    done
else
    for cfg in "$SCRIPT_DIR"/*.cfg; do
        SPECS+=("$(basename "${cfg%.cfg}")")
    done
fi

PASS=0
FAIL=0
TOTAL=${#SPECS[@]}

echo "=== TLA+ Model Checking: $TOTAL spec(s) ==="
echo ""

for spec in "${SPECS[@]}"; do
    tla_file="$SCRIPT_DIR/${spec}.tla"
    cfg_file="$SCRIPT_DIR/${spec}.cfg"

    echo "--- $spec ---"
    echo "  Spec: $tla_file"
    echo "  Config: $cfg_file"

    start_time=$(date +%s)

    if java -XX:+UseParallelGC \
         -cp "$TLA2TOOLS" tlc2.TLC \
         -config "$cfg_file" \
         -workers auto \
         -deadlock \
         "$tla_file" 2>&1 | tee "/tmp/tlc_${spec}.log" | tail -20; then

        elapsed=$(($(date +%s) - start_time))
        echo "  PASS (${elapsed}s)"
        echo ""
        PASS=$((PASS + 1))
    else
        elapsed=$(($(date +%s) - start_time))
        echo "  FAIL (${elapsed}s) — see /tmp/tlc_${spec}.log"
        echo ""
        FAIL=$((FAIL + 1))
    fi
done

echo "=== Results: $PASS passed, $FAIL failed, $TOTAL total ==="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
