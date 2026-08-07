"""P34 mutation testing with bounded, fail-visible mutmut evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

MUTMUT_VERSION = "2.5.1"
_STATES = ("killed", "survived", "timeout", "suspicious", "untested", "skipped")
_ENV = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + os.pathsep + os.environ.get("PATH", "")}


def _run(argv: list[str], root: str, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=root, env=_ENV, capture_output=True, text=True, timeout=timeout)


def _bounded(text: str) -> str:
    return text.strip()[-2000:]


def _error(status: str, message: str, **evidence) -> dict:
    return {"status": status, "message": message, "score": None, "passed": False, **evidence}


def _get_changed_py_files(root: str, paths: list[str], base: str) -> dict:
    """Select existing implementation files against an explicit merge base."""
    try:
        merge_base = _run(["git", "merge-base", base, "HEAD"], root, 10)
        if merge_base.returncode or not merge_base.stdout.strip():
            return _error("unknown", "Cannot resolve merge base: " + _bounded(merge_base.stderr))
        sha = merge_base.stdout.strip()
        diff = _run(["git", "diff", "--name-status", "-M", sha, "HEAD", "--"], root, 10)
    except subprocess.TimeoutExpired:
        return _error("unknown", "Git change selection timed out")
    except OSError as exc:
        return _error("tool_error", f"Git change selection failed: {exc}")

    if diff.returncode:
        return _error("unknown", "Cannot select changed files: " + _bounded(diff.stderr))
    selected: set[str] = set()
    deleted: set[str] = set()
    for line in diff.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            return _error("unknown", "Unrecognized git --name-status output")
        status, path = parts[0][:1], parts[-1]
        if not path.endswith(".py") or (paths and not any(path.startswith(item) for item in paths)):
            continue
        if status == "D":
            deleted.add(path)
        elif status in {"A", "M", "R", "C"} and (Path(root) / path).is_file():
            selected.add(path)
    return {"status": "completed", "merge_base": sha, "files": sorted(selected), "deleted": sorted(deleted)}


def _get_all_py_files(root: str, paths: list[str]) -> list[str]:
    root_path = Path(root)
    files: set[str] = set()
    for item in paths:
        target = root_path / item
        if target.is_file() and target.suffix == ".py":
            files.add(target.relative_to(root_path).as_posix())
        elif target.is_dir():
            files.update(path.relative_to(root_path).as_posix() for path in target.rglob("*.py") if path.is_file())
    return sorted(files)


def _has_mutmut() -> bool:
    return shutil.which("mutmut", path=_ENV["PATH"]) is not None


def _parse_result_ids(output: str) -> list[str]:
    output = output.strip()
    if not output:
        return []
    if not re.fullmatch(r"\d+(?: \d+)*", output):
        raise ValueError("unrecognized mutmut result-ids output")
    return output.split()


def _run_mutmut(root: str, files: list[str], timeout: int) -> dict:
    """Run mutmut 2.5.1 and reconstruct each outcome from verified ID output."""
    try:
        version = _run(["mutmut", "version"], root, 30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _error("tool_error", f"Cannot check mutmut version: {exc}")
    match = re.fullmatch(r"\s*mutmut version (\d+\.\d+\.\d+)\s*", version.stdout)
    actual = match.group(1) if match else "unrecognized"
    if version.returncode or actual != MUTMUT_VERSION:
        return _error(
            "tool_error",
            f"Unsupported mutmut version {actual}; install mutmut=={MUTMUT_VERSION}",
            engine_version=actual,
            version_exit_code=version.returncode,
            stderr=_bounded(version.stderr),
        )

    try:
        run = _run(
            ["mutmut", "run", "--paths-to-mutate=" + ",".join(files), "--no-progress", "--simple-output"],
            root,
            timeout,
        )
    except subprocess.TimeoutExpired:
        return _error("tool_error", f"Mutation run timed out after {timeout}s", engine_version=actual)
    except OSError as exc:
        return _error("tool_error", f"Cannot execute mutmut: {exc}", engine_version=actual)

    # mutmut 2.x uses bits 2/4/8 for survivor/timeout/suspicious outcomes.
    if run.returncode < 0 or run.returncode & 1 or run.returncode & ~15:
        return _error(
            "tool_error",
            "mutmut run failed",
            engine_version=actual,
            run_exit_code=run.returncode,
            stderr=_bounded(run.stderr or run.stdout),
        )
    try:
        results = _run(["mutmut", "results"], root, 30)
        if results.returncode:
            return _error(
                "tool_error",
                "mutmut results failed",
                engine_version=actual,
                run_exit_code=run.returncode,
                results_exit_code=results.returncode,
                stderr=_bounded(results.stderr or results.stdout),
            )
        ids: dict[str, list[str]] = {}
        for state in _STATES:
            result_ids = _run(["mutmut", "result-ids", state], root, 30)
            if result_ids.returncode:
                return _error(
                    "tool_error",
                    f"mutmut result-ids {state} failed",
                    engine_version=actual,
                    result_ids_exit_code=result_ids.returncode,
                    stderr=_bounded(result_ids.stderr or result_ids.stdout),
                )
            ids[state] = _parse_result_ids(result_ids.stdout)
    except ValueError as exc:
        return _error("unknown", str(exc), engine_version=actual, run_exit_code=run.returncode)
    except subprocess.TimeoutExpired:
        return _error("tool_error", "mutmut result collection timed out", engine_version=actual)
    except OSError as exc:
        return _error("tool_error", f"Cannot read mutmut results: {exc}", engine_version=actual)

    return {
        "status": "completed",
        "engine_version": actual,
        "run_exit_code": run.returncode,
        "results_exit_code": results.returncode,
        **{state: len(ids[state]) for state in _STATES},
        "survivors": ids["survived"][:20],
        "stderr": _bounded(run.stderr),
    }


def compute_score(killed: int, survived: int, timeout: int, suspicious: int, untested: int) -> float | None:
    total = killed + survived + timeout + suspicious + untested
    return None if total == 0 else killed / total * 100


def _rerun(root: str, paths: list[str], timeout: int, threshold: float, base: str, all_files: bool) -> str:
    argv = [
        sys.executable, "-m", "fettle.mutation_test", "--root", root,
        "--paths", ",".join(paths), "--timeout", str(timeout), "--threshold", str(threshold),
    ]
    argv.extend(["--all"] if all_files else ["--base", base])
    return shlex.join([*argv, "--json"])


def run_mutation_test(root: str, cfg: dict) -> dict:
    paths = cfg.get("paths", ["src/"])
    excluded = cfg.get("exclude", ["tests/", "migrations/"])
    timeout = int(cfg.get("timeout_s", 600))
    threshold = float(cfg.get("threshold", 70))
    base = str(cfg.get("base", "origin/main"))
    all_files = bool(cfg.get("all", False))
    rerun = _rerun(root, paths, timeout, threshold, base, all_files)
    if not _has_mutmut():
        return _error(
            "tool_error",
            f"mutmut not found. Install: python -m pip install mutmut=={MUTMUT_VERSION}",
            rerun_command=rerun,
        )

    selection = (
        {"status": "completed", "merge_base": None, "files": _get_all_py_files(root, paths), "deleted": []}
        if all_files else _get_changed_py_files(root, paths, base)
    )
    if selection["status"] != "completed":
        return {**selection, "files_tested": [], "deleted_files": selection.get("deleted", []), "rerun_command": rerun}
    files = [path for path in selection["files"] if not any(path.startswith(item) for item in excluded)]
    common = {
        "merge_base": selection["merge_base"],
        "selection": "all" if all_files else "changed",
        "files_tested": files,
        "deleted_files": selection["deleted"],
        "rerun_command": rerun,
    }
    if not files:
        return {
            "status": "not_applicable", "message": "No existing implementation files changed",
            "score": None, "passed": True, **common,
        }
    result = _run_mutmut(root, files, timeout)
    if result["status"] != "completed":
        return {**result, **common}
    score = compute_score(*(result[state] for state in _STATES[:5]))
    if score is None:
        evidence = {key: value for key, value in result.items() if key != "status"}
        return _error("unknown", "mutmut reported zero scored mutants", **evidence, **common)
    return {**result, "score": round(score, 1), "threshold": threshold, "passed": score >= threshold, **common}


def format_report(report: dict) -> str:
    lines = ["# Mutation Test Report", "", f"**Status:** {report['status']}"]
    if report.get("message"):
        lines.extend(["", report["message"]])
    if report["status"] == "completed":
        lines.extend([
            f"**Score:** {report['score']}%" + (" PASS" if report["passed"] else " FAIL"),
            f"**Engine:** mutmut {report['engine_version']}",
            *[f"**{state.title()}:** {report[state]}" for state in _STATES],
            f"**Threshold:** {report['threshold']}%",
        ])
        if report["survivors"]:
            lines.extend(["", "## Surviving Mutants", *[f"- {item}" for item in report["survivors"]]])
    if report.get("rerun_command"):
        lines.extend(["", f"**Rerun:** `{report['rerun_command']}`"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fettle mutation testing")
    parser.add_argument("--root", default=".")
    parser.add_argument("--paths", default="src/")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--threshold", type=float, default=70)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run_mutation_test(args.root, {
        "paths": args.paths.split(","), "base": args.base, "all": args.all,
        "timeout_s": args.timeout, "threshold": args.threshold,
    })
    output = json.dumps(report, indent=2) if args.json else format_report(report)
    sys.stdout.write(output + ("" if output.endswith("\n") else "\n"))
    return 2 if report["status"] in {"unknown", "tool_error"} else (0 if report.get("passed", True) else 1)


if __name__ == "__main__":
    sys.exit(main())
