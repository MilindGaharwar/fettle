#!/usr/bin/env python3
"""Exercise the PR mutation path on a bounded two-shard repository fixture."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


SCENARIOS = (
    "broken-aggregator-flag",
    "missing-runtime-dependency",
    "mismatched-manifest-digest",
)


def _run(
    argv: list[str], *, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True)


def _record(
    path: Path, scenario: str, result: subprocess.CompletedProcess[str]
) -> None:
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        report = None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "scenario": scenario,
                "exit_code": result.returncode,
                "passed": result.returncode == 0,
                "report": report,
                "stderr": result.stderr[-4000:],
            },
            indent=2,
        )
        + "\n"
    )


def _check(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode:
        raise RuntimeError(f"{label} failed: {result.stderr or result.stdout}")


def _fixture(root: Path) -> str:
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src/__init__.py").write_text("")
    (root / "src/a.py").write_text("def value():\n    return 1\n")
    (root / "src/b.py").write_text("def value():\n    return 2\n")
    (root / "tests/test_a.py").write_text(
        "from src.a import value\n\ndef test_value():\n    assert value() == 1\n"
    )
    (root / "tests/test_b.py").write_text(
        "from src.b import value\n\ndef test_value():\n    assert value() == 2\n"
    )
    (root / ".fettle.toml").write_text(
        "[mutation]\n"
        "enabled = true\n"
        "mode = 'advisory'\n"
        "paths = ['src/a.py', 'src/b.py']\n"
        "exclude = []\n"
        "full_shards = 2\n"
        "default_chunk_lines = 60\n"
        "score_target = 0\n"
        "[mutation.test_mappings]\n"
        "'src/a.py' = ['tests/test_a.py']\n"
        "'src/b.py' = ['tests/test_b.py']\n"
    )
    _check(_run(["git", "init", "-q"], cwd=root, env=os.environ.copy()), "git init")
    _check(
        _run(
            ["git", "config", "user.email", "fixture@example.invalid"],
            cwd=root,
            env=os.environ.copy(),
        ),
        "git config",
    )
    _check(
        _run(
            ["git", "config", "user.name", "Fixture"], cwd=root, env=os.environ.copy()
        ),
        "git config",
    )
    _check(
        _run(
            ["git", "commit", "--allow-empty", "-qm", "base"],
            cwd=root,
            env=os.environ.copy(),
        ),
        "base commit",
    )
    base = _run(
        ["git", "rev-parse", "HEAD"], cwd=root, env=os.environ.copy()
    ).stdout.strip()
    _check(_run(["git", "add", "."], cwd=root, env=os.environ.copy()), "git add")
    _check(
        _run(["git", "commit", "-qm", "fixture"], cwd=root, env=os.environ.copy()),
        "fixture commit",
    )
    return base


def _command(python: str) -> list[str]:
    return [python, "-m", "fettle.mutation_test", "--root", "."]


def _prepare_and_shard(
    root: Path,
    output: Path,
    command: list[str],
    env: dict[str, str],
    base: str,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    prepared = _run(
        [
            *command,
            "--base",
            base,
            "--prepare-changed-manifests",
            "manifests",
            "--json",
        ],
        cwd=root,
        env=env,
    )
    _check(prepared, "prepare")
    (output / "prepare.json").write_text(prepared.stdout)
    for index in range(2):
        result = _run(
            [
                *command,
                "--manifest",
                f"manifests/partition-{index}.json",
                "--manifest-scope",
                "manifests",
                "--shard-index",
                str(index),
                "--shard-count",
                "2",
                "--timeout",
                "120",
                "--json",
            ],
            cwd=root,
            env=env,
        )
        _check(result, f"shard {index}")
        destination = root / f"reports/{index}"
        destination.mkdir(parents=True)
        (destination / "mutation-report.json").write_text(result.stdout)
        retained = output / f"reports/{index}"
        retained.mkdir(parents=True)
        (retained / "mutation-report.json").write_text(result.stdout)
    shutil.copytree(root / "manifests", output / "manifests")


def _aggregate(
    root: Path,
    command: list[str],
    env: dict[str, str],
    base: str,
    reports: str = "reports",
    *,
    broken_flag: bool = False,
) -> subprocess.CompletedProcess[str]:
    flag = "--aggregate-advisory-broken" if broken_flag else "--aggregate-advisory"
    return _run(
        [
            *command,
            "--aggregate",
            reports,
            flag,
            "--aggregate-scope",
            "manifests",
            "--base",
            base,
            "--shard-count",
            "2",
            "--json",
        ],
        cwd=root,
        env=env,
    )


def _missing_dependency(
    root: Path,
    command: list[str],
    env: dict[str, str],
    output: Path,
) -> subprocess.CompletedProcess[str]:
    isolated = root / "isolated"
    isolated.mkdir()
    python = isolated / "python"
    python.symlink_to(Path(command[0]).resolve())
    missing_env = {**env, "HOME": str(isolated), "PATH": "/usr/bin:/bin"}
    result = _run(
        [
            *_command(str(python)),
            "--manifest",
            "manifests/partition-0.json",
            "--manifest-scope",
            "manifests",
            "--shard-index",
            "0",
            "--shard-count",
            "2",
            "--timeout",
            "120",
            "--json",
        ],
        cwd=root,
        env=missing_env,
    )
    _record(
        output / "missing-runtime-dependency/result.json",
        "missing-runtime-dependency",
        result,
    )
    return result


def run(output: Path, scenario: str | None) -> int:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fettle-admission-") as temporary:
        root = Path(temporary) / "repo"
        root.mkdir()
        base = _fixture(root)
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
        command = _command(sys.executable)
        positive = output / "positive"
        _prepare_and_shard(root, positive, command, env, base)

        if scenario == "missing-runtime-dependency":
            return _missing_dependency(root, command, env, output).returncode

        broken = _aggregate(root, command, env, base, broken_flag=True)
        _record(
            output / "broken-aggregator-flag/result.json",
            "broken-aggregator-flag",
            broken,
        )
        if scenario == "broken-aggregator-flag":
            return broken.returncode

        removed_root = root / "removed-report"
        shutil.copytree(root / "reports", removed_root)
        (removed_root / "1/mutation-report.json").unlink()
        removed = _aggregate(root, command, env, base, reports="removed-report")
        _record(output / "removed-report/result.json", "removed-report", removed)

        mismatched_root = root / "mismatched-reports"
        shutil.copytree(root / "reports", mismatched_root)
        report_path = mismatched_root / "0/mutation-report.json"
        report = json.loads(report_path.read_text())
        report["manifest_digest"] = "0" * 64
        report_path.write_text(json.dumps(report))
        mismatched = _aggregate(root, command, env, base, reports="mismatched-reports")
        _record(
            output / "mismatched-manifest-digest/result.json",
            "mismatched-manifest-digest",
            mismatched,
        )
        if scenario == "mismatched-manifest-digest":
            return mismatched.returncode

        missing = _missing_dependency(root, command, env, output)
        if any(
            result.returncode == 0 for result in (broken, removed, mismatched, missing)
        ):
            raise RuntimeError("a negative admission fixture unexpectedly passed")

        success = _aggregate(root, command, env, base)
        _check(success, "aggregate")
        aggregate = json.loads(success.stdout)
        if (
            aggregate.get("passed") is not True
            or aggregate.get("qualification_eligible") is not False
        ):
            raise RuntimeError(
                "positive advisory aggregate did not satisfy its contract"
            )
        aggregate_path = positive / "mutation-report.json"
        aggregate_path.write_text(success.stdout)
        summary = positive / "summary.md"
        published = _run(
            [
                *command,
                "--github-summary",
                str(aggregate_path),
                "--artifact-name",
                "mutation-admission-fixture",
                "--artifact-url",
                "https://example.invalid/artifacts/fixture",
            ],
            cwd=root,
            env={**env, "GITHUB_STEP_SUMMARY": str(summary)},
        )
        _check(published, "publication")
        if "mutation-admission-fixture" not in summary.read_text():
            raise RuntimeError("publication summary omitted the fixture artifact")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario", choices=SCENARIOS)
    args = parser.parse_args()
    try:
        return run(args.output, args.scenario)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"mutation admission fixture failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
