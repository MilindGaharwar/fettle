#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 <candidates.json> <download-root> <prepare.json> <output.json> [--authorization-label <label> --authorized-by <login>] | --self-test" >&2
  exit 2
}

guard() {
  local candidates_path=$1
  local download_root=$2
  local prepare_path=$3
  local output_path=$4
  local authorization_label=${5:-}
  local authorized_by=${6:-}

  python3 - "$candidates_path" "$download_root" "$prepare_path" "$output_path" \
    "$authorization_label" "$authorized_by" <<'PY'
import json
from pathlib import Path
import sys

candidates_path, download_root, prepare_path, output_path = map(Path, sys.argv[1:5])
authorization_label, authorized_by = sys.argv[5:7]
candidates = json.loads(candidates_path.read_text(encoding="utf-8"))["candidates"]
run_ids = [str(candidate["run_id"]) for candidate in candidates]
identities = list(download_root.rglob("mutation-pr-identity.json"))

if identities:
    raise SystemExit(0)

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

authorized = (
    authorization_label == "mutation-full-matrix-authorized"
    and bool(authorized_by)
)
if authorized:
    prepared = json.loads(prepare_path.read_text(encoding="utf-8"))
    result = {
        "status": "completed",
        "passed": True,
        "reused_shards": [],
        "matrix": prepared["matrix"],
        "override": {
            "reason": "candidates_expired",
            "candidate_run_ids": run_ids,
            "authorized_by": authorized_by,
            "label": authorization_label,
        },
    }
    output_path.write_text(json.dumps(result, separators=(",", ":")) + "\n")
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

  # A downloaded identity always wins and leaves selection to digest-bound reuse.
  printf '%s\n' '{"candidates":[{"run_id":101,"run_attempt":1}]}' > "$temporary/candidates.json"
  mkdir -p "$temporary/downloads/101"
  printf '%s\n' '{}' > "$temporary/downloads/101/mutation-pr-identity.json"
  rm "$temporary/output.json"
  guard "$temporary/candidates.json" "$temporary/downloads" \
    "$temporary/prepare.json" "$temporary/output.json"
  test ! -e "$temporary/output.json"

  # Rule 13 remains fail-closed without authorization.
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

  # Exact label-event authorization permits the prepared full matrix.
  guard "$temporary/candidates.json" "$temporary/downloads" \
    "$temporary/prepare.json" "$temporary/output.json" \
    "mutation-full-matrix-authorized" "maintainer"
  python3 - "$temporary/output.json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
assert value == {
    "status":"completed", "passed":True, "reused_shards":[],
    "matrix":{"shard":[3,7]},
    "override": {
        "reason":"candidates_expired", "candidate_run_ids":["101","202"],
        "authorized_by":"maintainer", "label":"mutation-full-matrix-authorized",
    },
}
PY

  # Even valid authorization cannot bypass an available identity artifact.
  mkdir -p "$temporary/downloads/101"
  printf '%s\n' '{}' > "$temporary/downloads/101/mutation-pr-identity.json"
  rm "$temporary/output.json"
  guard "$temporary/candidates.json" "$temporary/downloads" \
    "$temporary/prepare.json" "$temporary/output.json" \
    "mutation-full-matrix-authorized" "maintainer"
  test ! -e "$temporary/output.json"

  # Half-formed authorization is equivalent to no authorization.
  rm "$temporary/downloads/101/mutation-pr-identity.json"
  set +e
  guard "$temporary/candidates.json" "$temporary/downloads" \
    "$temporary/prepare.json" "$temporary/output.json" \
    "mutation-full-matrix-authorized" ""
  status=$?
  set -e
  test "$status" -eq 2
  python3 - "$temporary/output.json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
assert value["status"] == "error"
assert value["passed"] is False
assert value["candidate_run_ids"] == ["101", "202"]
assert "override" not in value
PY
}

if [[ ${1:-} == --self-test ]]; then
  self_test
  exit 0
fi

[[ $# -eq 4 || $# -eq 8 ]] || usage
if [[ $# -eq 8 ]]; then
  [[ $5 == --authorization-label && $7 == --authorized-by ]] || usage
  guard "$1" "$2" "$3" "$4" "$6" "$8"
else
  guard "$1" "$2" "$3" "$4"
fi
