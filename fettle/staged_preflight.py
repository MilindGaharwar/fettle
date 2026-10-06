#!/usr/bin/env python3
"""Validate the fixed, single-run staged preflight without replacing final aggregation."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
from datetime import datetime
from pathlib import Path

FROZEN_CANDIDATE = "0fc41fdfee13e09f4bda3dc5eee177030882aa36"
SHARD_COUNT = 256
ARTIFACT_RETENTION_DAYS = 90
WAVES = {
    "wave-1": [8, 27, 28, 37, 48, 50, 51, 53],
    "wave-2": [0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16,
               17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 29, 30, 31, 32, 33, 34],
}
WAVES["wave-3"] = [
    index for index in range(SHARD_COUNT)
    if index not in set(WAVES["wave-1"] + WAVES["wave-2"])
]
MAX_PARALLEL = {"wave-1": 2, "wave-2": 4, "wave-3": 8}
BUDGET = {
    "operational_ceiling_runner_minutes": 740,
    "wave_allowances": {"wave-1": 20, "wave-2": 75, "wave-3": 500},
    "orchestration_and_aggregation": 45,
    "cancellation_headroom": 100,
    "launch_ceiling": {"wave-2": 20, "wave-3": 95, "aggregate": 595, "complete": 640},
}


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _load_manifests(root: Path, directory: Path) -> list[dict]:
    sys.path.insert(0, str(root))
    from fettle.mutation_test import load_partition_manifest

    paths = sorted(directory.glob("partition-*.json"))
    manifests = [load_partition_manifest(path) for path in paths]
    manifests.sort(key=lambda item: item["shard_index"])
    if len(manifests) != SHARD_COUNT:
        raise ValueError(f"expected {SHARD_COUNT} manifests, found {len(manifests)}")
    if [item["shard_index"] for item in manifests] != list(range(SHARD_COUNT)):
        raise ValueError("manifest indexes are incomplete or duplicated")
    if any(
        item["revision"] != FROZEN_CANDIDATE or item["shard_count"] != SHARD_COUNT
        for item in manifests
    ):
        raise ValueError("manifest candidate or topology differs from the frozen identity")
    return manifests


def build_plan(root: Path, manifests_dir: Path, orchestration_sha: str, identity: dict) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", orchestration_sha):
        raise ValueError("orchestration SHA must be a full lowercase commit")
    manifests = _load_manifests(root, manifests_dir)
    members = [index for wave in WAVES.values() for index in wave]
    if len(members) != SHARD_COUNT or sorted(members) != list(range(SHARD_COUNT)):
        raise ValueError("fixed waves do not cover each shard exactly once")
    allocated = (
        sum(BUDGET["wave_allowances"].values())
        + BUDGET["orchestration_and_aggregation"]
        + BUDGET["cancellation_headroom"]
    )
    if allocated != BUDGET["operational_ceiling_runner_minutes"]:
        raise ValueError("predeclared budget does not reconcile")
    return {
        "schema_version": "1",
        "candidate_sha": FROZEN_CANDIDATE,
        "orchestration_sha": orchestration_sha,
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "dependencies": {
            "requirements_mutation_sha256": _file_digest(root / "requirements-mutation.txt"),
        },
        "policy": {"fettle_toml_sha256": _file_digest(root / ".fettle.toml")},
        "workflow": identity,
        "artifact_retention_days": ARTIFACT_RETENTION_DAYS,
        "shard_count": SHARD_COUNT,
        "manifest_digests": [item["digest"] for item in manifests],
        "manifest_topology_digest": _digest(manifests),
        "waves": {
            name: {"shards": shards, "max_parallel": MAX_PARALLEL[name]}
            for name, shards in WAVES.items()
        },
        "budget": BUDGET,
        "budget_notice": "Operational ceiling, not a guaranteed provider billing cap.",
    }


def validate_wave(
    root: Path,
    plan_path: Path,
    manifests_dir: Path,
    reports_dir: Path,
    wave: str,
    orchestration_sha: str,
    identity: dict,
) -> dict:
    plan = _load_json(plan_path)
    if (
        plan.get("candidate_sha") != FROZEN_CANDIDATE
        or plan.get("orchestration_sha") != orchestration_sha
        or plan.get("workflow") != identity
    ):
        raise ValueError("wave identity differs from the frozen plan")
    manifests = _load_manifests(root, manifests_dir)
    if plan.get("manifest_digests") != [item["digest"] for item in manifests]:
        raise ValueError("wave manifest digests differ from the frozen topology")
    expected = plan.get("waves", {}).get(wave, {}).get("shards")
    if expected != WAVES.get(wave):
        raise ValueError("wave membership differs from the fixed plan")
    report_paths = sorted(reports_dir.rglob("mutation-preflight.json"))
    reports = [_load_json(path) for path in report_paths]
    if len(reports) != len(expected):
        raise ValueError(f"{wave} requires exactly {len(expected)} reports")
    by_index: dict[int, dict] = {}
    for report in reports:
        index = report.get("shard_index")
        if index in by_index or index not in expected:
            raise ValueError(f"{wave} contains a duplicate or substituted shard")
        manifest = manifests[index]
        fingerprints = report.get("fingerprints")
        corpus = report.get("corpus")
        if (
            report.get("status") != "completed"
            or report.get("passed") is not True
            or report.get("engine_version") != "2.5.1"
            or report.get("shard_count") != SHARD_COUNT
            or report.get("manifest_digest") != manifest["digest"]
            or report.get("line_ranges") != manifest["ranges"]
            or report.get("files") != manifest["files"]
            or report.get("generated") != report.get("canonicalized")
            or report.get("collisions") != 0
            or not isinstance(fingerprints, list)
            or not isinstance(corpus, list)
            or len(fingerprints) != report.get("generated")
            or len(corpus) != len(fingerprints)
            or len(fingerprints) != len(set(fingerprints))
            or any(not isinstance(item, dict) for item in corpus)
            or any(not isinstance(item, str) for item in fingerprints)
            or sorted(item.get("fingerprint") for item in corpus) != sorted(fingerprints)
        ):
            raise ValueError(f"shard {index!r} has failed, malformed, or incompatible evidence")
        by_index[index] = report
    if sorted(by_index) != sorted(expected):
        raise ValueError(f"{wave} reports are incomplete")
    return {
        "schema_version": "1",
        "status": "completed",
        "passed": True,
        "wave": wave,
        "candidate_sha": FROZEN_CANDIDATE,
        "orchestration_sha": plan["orchestration_sha"],
        "shards": expected,
        "generated": sum(item["generated"] for item in reports),
        "report_digests": {
            str(index): _digest(by_index[index]) for index in sorted(by_index)
        },
    }


def observed_runner_minutes(jobs_path: Path, now: datetime | None = None) -> float:
    pages = json.loads(jobs_path.read_text(encoding="utf-8"))
    if not isinstance(pages, list):
        pages = [pages]
    if not pages or any(
        not isinstance(page, dict) or not isinstance(page.get("jobs"), list)
        for page in pages
    ):
        raise ValueError("jobs response is missing or malformed")
    jobs = [job for page in pages for job in page["jobs"]]
    if not jobs:
        raise ValueError("jobs response is empty")
    total = 0.0
    current = now
    for job in jobs:
        started = job.get("started_at")
        completed = job.get("completed_at")
        status = job.get("status")
        conclusion = job.get("conclusion")
        if started is None and completed is not None:
            raise ValueError("job timing is partial")
        if started is None:
            if status == "completed" and conclusion == "skipped":
                continue
            raise ValueError("non-skipped job timing is missing")
        start = datetime.fromisoformat(started.replace("Z", "+00:00"))
        if completed is None:
            if current is None:
                current = datetime.now(start.tzinfo)
            end = current
        else:
            end = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        if end < start:
            raise ValueError("job timing is reversed")
        total += (end - start).total_seconds() / 60
    return round(total, 2)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    wave = sub.add_parser("validate-wave")
    budget = sub.add_parser("budget-gate")
    for command in (plan, wave):
        command.add_argument("--root", type=Path, required=True)
        command.add_argument("--manifests", type=Path, required=True)
        command.add_argument("--repository", required=True)
        command.add_argument("--workflow", required=True)
        command.add_argument("--workflow-ref", required=True)
        command.add_argument("--run-id", required=True)
        command.add_argument("--run-attempt", required=True)
    plan.add_argument("--orchestration-sha", required=True)
    plan.add_argument("--output", type=Path, required=True)
    wave.add_argument("--plan", type=Path, required=True)
    wave.add_argument("--reports", type=Path, required=True)
    wave.add_argument("--wave", choices=tuple(WAVES), required=True)
    wave.add_argument("--orchestration-sha", required=True)
    wave.add_argument("--output", type=Path, required=True)
    budget.add_argument("--jobs", type=Path, required=True)
    budget.add_argument(
        "--next-wave",
        choices=("wave-2", "wave-3", "aggregate", "complete"),
        required=True,
    )
    args = parser.parse_args()
    try:
        if args.command == "budget-gate":
            observed = observed_runner_minutes(args.jobs)
            ceiling = BUDGET["launch_ceiling"][args.next_wave]
            result = {
                "observed_runner_minutes": observed,
                "launch_ceiling": ceiling,
                "next_wave": args.next_wave,
                "passed": observed <= ceiling,
            }
            print(json.dumps(result, indent=2))
            return 0 if result["passed"] else 2
        identity = {
            "repository": args.repository,
            "workflow": args.workflow,
            "workflow_ref": args.workflow_ref,
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
        }
        if args.command == "plan":
            result = build_plan(args.root, args.manifests, args.orchestration_sha, identity)
        else:
            result = validate_wave(
                args.root,
                args.plan,
                args.manifests,
                args.reports,
                args.wave,
                args.orchestration_sha,
                identity,
            )
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"staged preflight rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
