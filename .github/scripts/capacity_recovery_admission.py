#!/usr/bin/env python3
"""Fail-closed exact-once admission for the bounded corpus recovery route."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FAILED_RECOVERY_RUN_ID = 39369184372
FAILED_RECOVERY_HEAD_SHA = "276ac10bb7b2ec7b80346e821c2324d12bfab73f"
WORKFLOW_PATH = ".github/workflows/mutation.yml"


def _pages(path: Path, collection: str) -> list[dict]:
    try:
        pages = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{collection} response is unavailable or malformed") from exc
    if not isinstance(pages, list) or not pages:
        raise ValueError(f"{collection} pagination is missing or malformed")
    records: list[dict] = []
    totals = set()
    for page in pages:
        if not isinstance(page, dict) or type(page.get("total_count")) is not int:
            raise ValueError(f"{collection} pagination is malformed")
        values = page.get(collection)
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise ValueError(f"{collection} pagination is malformed")
        totals.add(page["total_count"])
        records.extend(values)
    ids = [item.get("id") for item in records]
    if (
        len(totals) != 1
        or totals.pop() != len(records)
        or any(type(item_id) is not int or item_id < 1 for item_id in ids)
        or len(ids) != len(set(ids))
    ):
        raise ValueError(f"{collection} pagination is incomplete or conflicting")
    return records


def validate_admission(
    *, stage: str, current_run_id: int, controller_sha: str, expected_title: str,
    runs_path: Path, markers_path: Path, predecessor_artifacts_path: Path | None = None,
    predecessor_jobs_path: Path | None = None,
) -> None:
    """Validate the sole fresh stage, with one fixed failed recovery exception."""
    runs = _pages(runs_path, "workflow_runs")
    matching = [run for run in runs if run.get("display_title") == expected_title]
    expected_ids = {current_run_id}
    if stage == "recover":
        expected_ids.add(FAILED_RECOVERY_RUN_ID)
    if {run.get("id") for run in matching} != expected_ids or len(matching) != len(expected_ids):
        raise ValueError("recovery dispatch history is unexpected or conflicting")

    current = next(run for run in matching if run.get("id") == current_run_id)
    if (
        current.get("run_attempt") != 1
        or current.get("head_sha") != controller_sha
        or current.get("event") != "workflow_dispatch"
        or current.get("path") != WORKFLOW_PATH
        or current.get("status") not in {"queued", "in_progress"}
        or current.get("conclusion") is not None
    ):
        raise ValueError("current recovery dispatch identity is stale or conflicting")

    if stage == "recover":
        predecessor = next(run for run in matching if run.get("id") == FAILED_RECOVERY_RUN_ID)
        if (
            predecessor.get("run_attempt") != 1
            or predecessor.get("head_sha") != FAILED_RECOVERY_HEAD_SHA
            or predecessor.get("event") != "workflow_dispatch"
            or predecessor.get("path") != WORKFLOW_PATH
            or predecessor.get("status") != "completed"
            or predecessor.get("conclusion") != "failure"
        ):
            raise ValueError("authorized failed recovery predecessor differs")
        if predecessor_artifacts_path is None or _pages(
            predecessor_artifacts_path, "artifacts",
        ):
            raise ValueError("authorized failed recovery predecessor published artifacts")
        if predecessor_jobs_path is None:
            raise ValueError("authorized failed recovery predecessor jobs are missing")
        predecessor_jobs = _pages(predecessor_jobs_path, "jobs")
        recovery_jobs = [
            job for job in predecessor_jobs
            if job.get("name") == "capacity validation (recover retained corpus)"
        ]
        if (
            len(recovery_jobs) != 1
            or recovery_jobs[0].get("status") != "completed"
            or recovery_jobs[0].get("conclusion") != "failure"
            or any(job.get("status") != "completed" for job in predecessor_jobs)
            or any(
                job.get("conclusion") != "skipped"
                for job in predecessor_jobs if job not in recovery_jobs
            )
        ):
            raise ValueError("authorized failed recovery predecessor jobs differ")

    markers = _pages(markers_path, "artifacts")
    if markers:
        raise ValueError("recovery grant marker already exists")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("recover", "execute", "readback"), required=True)
    parser.add_argument("--current-run-id", type=int, required=True)
    parser.add_argument("--controller-sha", required=True)
    parser.add_argument("--expected-title", required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--markers", type=Path, required=True)
    parser.add_argument("--predecessor-artifacts", type=Path)
    parser.add_argument("--predecessor-jobs", type=Path)
    args = parser.parse_args()
    try:
        validate_admission(
            stage=args.stage, current_run_id=args.current_run_id,
            controller_sha=args.controller_sha, expected_title=args.expected_title,
            runs_path=args.runs, markers_path=args.markers,
            predecessor_artifacts_path=args.predecessor_artifacts,
            predecessor_jobs_path=args.predecessor_jobs,
        )
    except ValueError as exc:
        parser.exit(2, f"capacity recovery admission rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
