#!/usr/bin/env python3
"""Fail-closed exact-once admission for the bounded corpus recovery route."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

FAILED_RECOVERY_RUN_ID = 39369184372
FAILED_RECOVERY_HEAD_SHA = "276ac10bb7b2ec7b80346e821c2324d12bfab73f"
MISSING_INPUT_RUN_ID = 39378451442
MISSING_INPUT_HEAD_SHA = "8e46125ff7d0e6f7d3a845faed32fb14336a5185"
WORKFLOW_PATH = ".github/workflows/mutation.yml"
ADMITTED_RECOVERY_RUN_ID = 39391306615
ADMITTED_RECOVERY_HEAD_SHA = "ebd1e057ae3497b6ec72ef709a08d0c33d1b2bb8"
ADMITTED_MARKER_ID = 12250220498
ADMITTED_MARKER_DIGEST = "sha256:6a938890d590b7dbb48eb5f91c650e5d347f7e86d27d74ef30052f307ba52280"
ADMITTED_RECOVERY_JOB_ID = 118523223941


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


def _charged_minutes(job: dict) -> int:
    try:
        seconds = (
            datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
            - datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
        ).total_seconds()
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("authorized failed recovery predecessor timing is unavailable") from exc
    if seconds < 0:
        raise ValueError("authorized failed recovery predecessor timing is contradictory")
    return math.ceil(seconds / 60)


def validate_admission(
    *, stage: str, current_run_id: int, controller_sha: str, expected_title: str,
    runs_path: Path, markers_path: Path, predecessor_artifacts_path: Path | None = None,
    predecessor_jobs_path: Path | None = None,
    missing_input_artifacts_path: Path | None = None,
    missing_input_jobs_path: Path | None = None,
    retry_predecessor_run_id: int | None = None,
    retry_predecessor_artifacts_path: Path | None = None,
    retry_predecessor_jobs_path: Path | None = None,
) -> None:
    """Validate one fresh stage against the explicitly authorized closed history."""
    runs = _pages(runs_path, "workflow_runs")
    matching = [run for run in runs if run.get("display_title") == expected_title]
    expected_ids = {current_run_id}
    if stage == "recover":
        expected_ids.update((FAILED_RECOVERY_RUN_ID, MISSING_INPUT_RUN_ID))
        if retry_predecessor_run_id is not None:
            expected_ids.add(retry_predecessor_run_id)
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
        predecessors = [
            (FAILED_RECOVERY_RUN_ID, FAILED_RECOVERY_HEAD_SHA,
             predecessor_artifacts_path, predecessor_jobs_path),
            (MISSING_INPUT_RUN_ID, MISSING_INPUT_HEAD_SHA,
             missing_input_artifacts_path, missing_input_jobs_path),
        ]
        if retry_predecessor_run_id is not None:
            if retry_predecessor_run_id in {FAILED_RECOVERY_RUN_ID, MISSING_INPUT_RUN_ID}:
                raise ValueError("conditional retry predecessor is duplicated")
            predecessors.append((
                retry_predecessor_run_id,
                (ADMITTED_RECOVERY_HEAD_SHA
                 if retry_predecessor_run_id == ADMITTED_RECOVERY_RUN_ID else controller_sha),
                retry_predecessor_artifacts_path, retry_predecessor_jobs_path,
            ))
        for run_id, head_sha, artifacts_path, jobs_path in predecessors:
            predecessor = next(run for run in matching if run.get("id") == run_id)
            if (
                predecessor.get("run_attempt") != 1
                or predecessor.get("head_sha") != head_sha
                or predecessor.get("event") != "workflow_dispatch"
                or predecessor.get("path") != WORKFLOW_PATH
                or predecessor.get("status") != "completed"
                or predecessor.get("conclusion") != "failure"
            ):
                raise ValueError("authorized failed recovery predecessor differs")
            artifacts = _pages(artifacts_path, "artifacts") if artifacts_path is not None else None
            if run_id == ADMITTED_RECOVERY_RUN_ID:
                if len(artifacts or []) != 1 or any(
                    artifacts[0].get(key) != value for key, value in {
                        "id": ADMITTED_MARKER_ID,
                        "name": "capacity-recovery-grant-A-recover",
                        "expired": False,
                        "digest": ADMITTED_MARKER_DIGEST,
                    }.items()
                ):
                    raise ValueError("admitted recovery predecessor marker differs")
                marker_run = artifacts[0].get("workflow_run")
                if (
                    not isinstance(marker_run, dict)
                    or marker_run.get("id") != ADMITTED_RECOVERY_RUN_ID
                    or marker_run.get("head_sha") != ADMITTED_RECOVERY_HEAD_SHA
                ):
                    raise ValueError("admitted recovery predecessor marker lineage differs")
            elif artifacts:
                raise ValueError("authorized failed recovery predecessor published artifacts")
            if jobs_path is None:
                raise ValueError("authorized failed recovery predecessor jobs are missing")
            predecessor_jobs = _pages(jobs_path, "jobs")
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
            if run_id == ADMITTED_RECOVERY_RUN_ID:
                if (
                    recovery_jobs[0].get("id") != ADMITTED_RECOVERY_JOB_ID
                    or recovery_jobs[0].get("started_at") != "2026-10-20T08:08:56Z"
                    or recovery_jobs[0].get("completed_at") != "2026-10-20T08:10:03Z"
                    or _charged_minutes(recovery_jobs[0]) != 2
                ):
                    raise ValueError("admitted recovery predecessor execution differs")
            elif run_id == retry_predecessor_run_id and _charged_minutes(recovery_jobs[0]) > 1:
                raise ValueError("conditional retry predecessor leaves insufficient recovery headroom")

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
    parser.add_argument("--missing-input-artifacts", type=Path)
    parser.add_argument("--missing-input-jobs", type=Path)
    parser.add_argument("--retry-predecessor-run-id", type=int)
    parser.add_argument("--retry-predecessor-artifacts", type=Path)
    parser.add_argument("--retry-predecessor-jobs", type=Path)
    args = parser.parse_args()
    try:
        validate_admission(
            stage=args.stage, current_run_id=args.current_run_id,
            controller_sha=args.controller_sha, expected_title=args.expected_title,
            runs_path=args.runs, markers_path=args.markers,
            predecessor_artifacts_path=args.predecessor_artifacts,
            predecessor_jobs_path=args.predecessor_jobs,
            missing_input_artifacts_path=args.missing_input_artifacts,
            missing_input_jobs_path=args.missing_input_jobs,
            retry_predecessor_run_id=args.retry_predecessor_run_id,
            retry_predecessor_artifacts_path=args.retry_predecessor_artifacts,
            retry_predecessor_jobs_path=args.retry_predecessor_jobs,
        )
    except ValueError as exc:
        parser.exit(2, f"capacity recovery admission rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
