#!/usr/bin/env python3
"""Adapt mapped-test representation before invoking the frozen source runner."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from fettle.config import load_config
from fettle.mutation_test import (
    _canonical_digest,
    _mapped_tests,
    run_capacity_validation_unit,
)


def _ordered_membership(recorded: object, actual: object) -> list[str]:
    if (
        not isinstance(recorded, list)
        or not isinstance(actual, list)
        or any(not isinstance(item, str) or not item for item in recorded + actual)
        or len(recorded) != len(set(recorded))
        or len(actual) != len(set(actual))
        or set(recorded) != set(actual)
    ):
        raise ValueError("capacity recovery mapped-test membership differs")
    return actual


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--unit", type=int, required=True)
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--environment-evidence", required=True)
    args = parser.parse_args()

    source = Path(args.source_root).resolve()
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    unit = plan["units"][args.unit]
    cfg = load_config(str(source), strict=True)["mutation"]
    actual = _mapped_tests(str(source), [unit["file"]], cfg.get("test_mappings", {}))[unit["file"]]
    _ordered_membership(unit["mapped_tests"], actual)

    selected = set(unit["fingerprints"])
    matched = 0
    for record in corpus.get("corpus", []):
        if record.get("fingerprint") in selected:
            record["mapped_tests"] = _ordered_membership(record.get("mapped_tests"), actual)
            matched += 1
    if matched != len(selected):
        raise ValueError("capacity recovery unit corpus coverage differs")

    original_plan_digest = plan["digest"]
    corpus_digest = _canonical_digest(corpus)
    plan["preflight_digest"] = corpus_digest
    plan["digest"] = _canonical_digest({key: value for key, value in plan.items() if key != "digest"})
    from fettle.mutation_test import _checkpoint_environment_digest, _runtime_cache_identity
    identity = _runtime_cache_identity(str(source), [unit["file"]], {unit["file"]: actual}, cfg)
    if identity is None:
        raise ValueError("capacity recovery runtime environment identity is unavailable")
    inputs = identity["inputs"]
    envelope = {
        "engine": inputs["engine"],
        "environment": inputs["environment"],
        "dependencies": [
            {"name": dependency["name"], "version": dependency["version"]}
            for dependency in inputs["dependencies"]
        ],
    }
    evidence = {
        "schema_version": "1",
        "kind": "capacity_validation_runtime_environment",
        "captured_before_mutation": True,
        "envelope": envelope,
        "digest": _checkpoint_environment_digest(identity),
    }
    Path(args.environment_evidence).write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    if evidence["digest"] != unit["environment_digest"]:
        raise ValueError("capacity recovery runtime environment differs")
    with tempfile.TemporaryDirectory(prefix="capacity-recovery-") as directory:
        temporary = Path(directory)
        plan_path = temporary / "plan.json"
        corpus_path = temporary / "corpus.json"
        plan_path.write_text(json.dumps(plan, sort_keys=True) + "\n", encoding="utf-8")
        corpus_path.write_text(json.dumps(corpus, sort_keys=True) + "\n", encoding="utf-8")
        result = run_capacity_validation_unit(
            str(source), cfg, plan_path, corpus_path, args.unit, args.timeout,
            Path(args.checkpoint),
        )
    if result.get("plan_digest") != plan["digest"] or result.get("unit") != unit:
        raise ValueError("capacity recovery source result differs from adapted unit")
    result["plan_digest"] = original_plan_digest
    result["digest"] = _canonical_digest({key: value for key, value in result.items() if key != "digest"})
    Path(args.result).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
