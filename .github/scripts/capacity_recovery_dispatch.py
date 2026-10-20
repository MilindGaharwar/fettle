#!/usr/bin/env python3
"""Validate and dispatch one retained capacity-recovery payload unchanged."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import yaml

from fettle.staged_preflight import capacity_recovery_authorization_contract

REQUIRED_INPUTS = {
    "mode": "capacity-validation",
    "capacity_stage": "recover",
    "capacity_authorization_id": "AH-CORPUS-RECOVERY-20261020-A",
    "capacity_experiment_id": "capval-corpus-recovery-20261020-a",
    "capacity_preparation_run_id": "39263581356",
    "capacity_recovery_retry_run_id": "39391306615",
    "candidate_sha": "65e63d953b45d3672c24df74d0a1364b83a0157b",
}


def validate_payload(path: Path, workflow_path: Path) -> tuple[dict, bytes]:
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError("dispatch payload or workflow is unavailable or malformed") from exc
    if not isinstance(envelope, dict) or set(envelope) != {
        "controller_sha", "inputs", "ref", "workflow",
    }:
        raise ValueError("dispatch envelope keys differ")
    if envelope["workflow"] != "mutation.yml" or envelope["ref"] not in {
        "audit/hardening-integration-20261005",
        "repair/calibration-monitor-observation-20261016",
    }:
        raise ValueError("dispatch workflow or ref differs")
    controller_sha = envelope["controller_sha"]
    if not isinstance(controller_sha, str) or len(controller_sha) != 40:
        raise ValueError("dispatch controller identity differs")
    inputs = envelope["inputs"]
    if not isinstance(inputs, dict) or set(inputs) != set(REQUIRED_INPUTS):
        raise ValueError("dispatch input names differ")
    expected = dict(REQUIRED_INPUTS)
    retry_id = inputs.get("capacity_recovery_retry_run_id")
    if not isinstance(retry_id, str) or (retry_id and not retry_id.isdecimal()):
        raise ValueError("conditional retry predecessor differs")
    expected["capacity_recovery_retry_run_id"] = retry_id
    if inputs != expected or any(not isinstance(value, str) for value in inputs.values()):
        raise ValueError("dispatch input values or types differ")
    declared = workflow.get(True, {}).get("workflow_dispatch", {}).get("inputs", {})
    if not isinstance(declared, dict) or not set(inputs).issubset(declared):
        raise ValueError("dispatch inputs are absent from the exact workflow")
    capacity_recovery_authorization_contract(
        inputs["capacity_authorization_id"], inputs["candidate_sha"],
        inputs["capacity_experiment_id"],
    )
    return envelope, (json.dumps(inputs, sort_keys=True, separators=(",", ":")) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--workflow-file", type=Path, required=True)
    parser.add_argument("--expected-controller-sha", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        envelope, inputs = validate_payload(args.payload, args.workflow_file)
        if envelope["controller_sha"] != args.expected_controller_sha:
            raise ValueError("dispatch controller does not match the delivered ref")
        if args.validate_only:
            return 0
        result = subprocess.run(
            ["gh", "workflow", "run", envelope["workflow"],
             "--repo", "MilindGaharwar/fettle", "--ref", envelope["ref"], "--json"],
            input=inputs, check=False,
        )
    except ValueError as exc:
        parser.exit(2, f"capacity recovery dispatch rejected: {exc}\n")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
