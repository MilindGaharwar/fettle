#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 <candidates.json> <download-root> <prepare.json> <output.json> | --self-test" >&2
  exit 2
}

guard() {
  local candidates_path=$1
  local download_root=$2
  local prepare_path=$3
  local output_path=$4

  python3 - "$candidates_path" "$download_root" "$prepare_path" "$output_path" <<'PY'
import json
from pathlib import Path
import sys

candidates_path, download_root, prepare_path, output_path = map(Path, sys.argv[1:])
candidates = json.loads(candidates_path.read_text(encoding="utf-8"))["candidates"]
run_ids = [str(candidate["run_id"]) for candidate in candidates]
identities = list(download_root.rglob("mutation-pr-identity.json"))

if not candidates:
    prepared = json.loads(prepare_path.read_text(encoding="utf-8"))
    result = {
        "status": "completed",
        "passed": True,
        "reused_shards": [],
        "matrix": prepared["matrix"],
    }
    output_path.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    raise SystemExit(0)

if identities:
    raise SystemExit(0)

result = {
    "status": "error",
    "passed": False,
    "message": "Advisory reuse candidates existed but no identity-bound artifacts downloaded",
    "candidate_run_ids": run_ids,
}
output_path.write_text(json.dumps(result, separators=(",", ":")) + "\n")
raise SystemExit(2)
PY
}

self_test() {
  temporary=$(mktemp -d)
  trap 'rm -rf "$temporary"' EXIT
  mkdir -p "$temporary/downloads"
  printf '%s\n' '{"matrix":{"shard":[3,7]}}' > "$temporary/prepare.json"

  printf '%s\n' '{"candidates":[]}' > "$temporary/candidates.json"
  guard "$temporary/candidates.json" "$temporary/downloads" \
    "$temporary/prepare.json" "$temporary/output.json"
  python3 - "$temporary/output.json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
assert value == {"status":"completed","passed":True,"reused_shards":[],"matrix":{"shard":[3,7]}}
PY

  printf '%s\n' '{"candidates":[{"run_id":101,"run_attempt":1}]}' > "$temporary/candidates.json"
  mkdir -p "$temporary/downloads/101"
  printf '%s\n' '{}' > "$temporary/downloads/101/mutation-pr-identity.json"
  rm "$temporary/output.json"
  guard "$temporary/candidates.json" "$temporary/downloads" \
    "$temporary/prepare.json" "$temporary/output.json"
  test ! -e "$temporary/output.json"

  rm "$temporary/downloads/101/mutation-pr-identity.json"
  printf '%s\n' '{"candidates":[{"run_id":101,"run_attempt":1},{"run_id":202,"run_attempt":3}]}' > "$temporary/candidates.json"
  set +e
  guard "$temporary/candidates.json" "$temporary/downloads" \
    "$temporary/prepare.json" "$temporary/output.json"
  local status=$?
  set -e
  test "$status" -eq 2
  python3 - "$temporary/output.json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
assert value["status"] == "error"
assert value["passed"] is False
assert value["candidate_run_ids"] == ["101", "202"]
PY
}

if [[ ${1:-} == --self-test ]]; then
  self_test
  exit 0
fi

[[ $# -eq 4 ]] || usage
guard "$1" "$2" "$3" "$4"
