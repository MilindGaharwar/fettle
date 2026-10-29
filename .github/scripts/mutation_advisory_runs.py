#!/usr/bin/env python3
"""Fail closed on concurrent PR advisory runs and select reuse candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


def _runs(paths: list[Path]) -> list[dict]:
    runs = []
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        pages = value if isinstance(value, list) else [value]
        for page in pages:
            if not isinstance(page, dict) or not isinstance(page.get("workflow_runs"), list):
                raise ValueError("workflow run response is malformed")
            runs.extend(page["workflow_runs"])
    return runs


def guard(paths: list[Path], current_run_id: str) -> dict:
    if not re.fullmatch(r"[1-9][0-9]*", current_run_id):
        raise ValueError("current workflow run ID is malformed")
    active = sorted({
        str(run.get("id"))
        for run in _runs(paths)
        if str(run.get("id")) != current_run_id
        and run.get("status") in {"queued", "in_progress"}
        and re.fullmatch(r"[1-9][0-9]*", str(run.get("id", "")))
    })
    return {
        "status": "deferred" if active else "completed",
        "passed": not active,
        "reason": "deferred: another advisory matrix is in progress" if active else None,
        "active_run_ids": active,
    }


def candidates(paths: list[Path], current_run_id: str) -> dict:
    selected = []
    for run in _runs(paths):
        run_id = str(run.get("id", ""))
        attempt = run.get("run_attempt")
        started = run.get("run_started_at")
        if (
            run_id == current_run_id
            or run.get("status") != "completed"
            or run.get("conclusion") != "success"
            or not re.fullmatch(r"[1-9][0-9]*", run_id)
            or not isinstance(attempt, int)
            or isinstance(attempt, bool)
            or attempt < 1
            or not isinstance(started, str)
        ):
            continue
        selected.append({
            "run_id": run_id,
            "run_attempt": str(attempt),
            "run_started_at": started,
        })
    selected.sort(key=lambda item: item["run_started_at"], reverse=True)
    return {"schema_version": "1", "candidates": selected}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("guard", "candidates"))
    parser.add_argument("--runs", type=Path, action="append", required=True)
    parser.add_argument("--current-run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = (
            guard(args.runs, args.current_run_id)
            if args.mode == "guard"
            else candidates(args.runs, args.current_run_id)
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result = {"status": "unknown", "passed": False, "reason": str(exc)}
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if args.mode == "guard":
        return 0 if result.get("passed") is True else 2
    return 0 if "candidates" in result else 2


if __name__ == "__main__":
    raise SystemExit(main())
