#!/usr/bin/env python3
"""Behavioral eval harness for Fettle gates — WP-133 (shape stolen from
superpowers-evals/quorum, radically slimmed).

Tests whether Fettle's hooks and gate messages actually change agent
behavior — not whether rules match code (that is tests/test_rule_integrity.py)
but whether an agent, when nudged, produces compliant output.

Safety model (same line quorum draws):
  - STATIC side (CI-safe): scenario schema validation, check evaluation,
    verdict composition. Runs in pytest with a fake runner. Never launches
    an agent CLI, never needs API keys.
  - LIVE side (trusted-operator only, never public CI): `--live` launches
    `claude -p` in a scratch workdir with Fettle hooks active and grades
    the transcript + resulting files.

Verdicts are three-valued (exit codes): pass=0, fail=1, indeterminate=2.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

logger = logging.getLogger("fettle.evals")

CHECK_TYPES = frozenset({
    "file_matches",        # regex found in workdir file
    "file_not_matches",    # regex absent from workdir file
    "transcript_matches",
    "transcript_not_matches",
})


class Verdict(Enum):
    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


EXIT_CODES = {Verdict.PASS: 0, Verdict.FAIL: 1, Verdict.INDETERMINATE: 2}


@dataclass(frozen=True)
class Check:
    type: str
    regex: str
    path: str | None = None


@dataclass(frozen=True)
class Scenario:
    id: str
    prompt: str
    checks: tuple[Check, ...]
    setup_files: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CheckRecord:
    check: Check
    passed: bool
    detail: str


@dataclass(frozen=True)
class RunResult:
    verdict: Verdict
    checks: tuple[CheckRecord, ...]
    transcript: str


def discover_scenarios(root: str | Path) -> list[Path]:
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(d for d in root.iterdir() if (d / "scenario.yaml").is_file())


def load_scenario(scenario_dir: str | Path) -> Scenario:
    path = Path(scenario_dir) / "scenario.yaml"
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: scenario must be a mapping")
    prompt = data.get("prompt")
    if not prompt or not isinstance(prompt, str):
        raise ValueError(f"{path}: 'prompt' is required")
    raw_checks = data.get("checks") or []
    if not raw_checks:
        raise ValueError(f"{path}: at least one check is required")
    checks = []
    for c in raw_checks:
        ctype = c.get("type", "")
        if ctype not in CHECK_TYPES:
            raise ValueError(f"{path}: unknown check type '{ctype}' (allowed: {sorted(CHECK_TYPES)})")
        if not c.get("regex"):
            raise ValueError(f"{path}: check '{ctype}' needs a 'regex'")
        if ctype.startswith("file_") and not c.get("path"):
            raise ValueError(f"{path}: check '{ctype}' needs a 'path'")
        checks.append(Check(type=ctype, regex=c["regex"], path=c.get("path")))
    setup_files = data.get("setup_files") or {}
    return Scenario(
        id=str(data.get("id", Path(scenario_dir).name)),
        prompt=prompt,
        checks=tuple(checks),
        setup_files={str(k): str(v) for k, v in setup_files.items()},
    )


def _evaluate(check: Check, transcript: str, workdir: Path) -> CheckRecord:
    if check.type.startswith("file_"):
        target = workdir / (check.path or "")
        content = target.read_text() if target.is_file() else ""
        found = re.search(check.regex, content) is not None
        wanted = check.type == "file_matches"
        detail = f"{check.path}: /{check.regex}/ {'found' if found else 'absent'}"
    else:
        found = re.search(check.regex, transcript) is not None
        wanted = check.type == "transcript_matches"
        detail = f"transcript: /{check.regex}/ {'found' if found else 'absent'}"
    return CheckRecord(check=check, passed=found == wanted, detail=detail)


def _claude_runner(prompt: str, cwd: Path) -> str:
    """LIVE runner — launches `claude -p`. Trusted-operator use only.

    Runs with --dangerously-skip-permissions (the quorum approach): in
    non-interactive print mode, permission prompts cannot be answered and
    stall the run to timeout. Timeout via $FETTLE_EVAL_TIMEOUT_S (default 600).
    """
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("claude CLI not on PATH — live evals unavailable")
    timeout_s = int(os.environ.get("FETTLE_EVAL_TIMEOUT_S", "600"))
    proc = subprocess.run(
        [claude, "-p", "--dangerously-skip-permissions", prompt],
        capture_output=True, text=True,
        timeout=timeout_s, cwd=str(cwd),
    )
    return proc.stdout


def run_scenario(scenario: Scenario, runner=None, workdir: str | Path | None = None) -> RunResult:
    runner = runner or _claude_runner
    workdir = Path(workdir) if workdir else Path.cwd() / "evals-run"
    workdir.mkdir(parents=True, exist_ok=True)
    for rel, content in scenario.setup_files.items():
        target = workdir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    try:
        transcript = runner(scenario.prompt, workdir)
    except Exception as e:  # noqa: BLE001 — runner failure is indeterminate (broken experiment), not fail
        logger.warning("eval runner failed for %s: %s", scenario.id, e)
        return RunResult(Verdict.INDETERMINATE, (), f"runner error: {e}")
    has_transcript_checks = any(c.type.startswith("transcript_") for c in scenario.checks)
    if not transcript.strip() and has_transcript_checks:
        return RunResult(Verdict.INDETERMINATE, (), transcript)
    records = tuple(_evaluate(c, transcript, workdir) for c in scenario.checks)
    verdict = Verdict.PASS if all(r.passed for r in records) else Verdict.FAIL
    return RunResult(verdict, records, transcript)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fettle behavioral evals")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_validate = sub.add_parser("validate", help="statically validate all scenarios (CI-safe)")
    p_validate.add_argument("--root", default=str(Path(__file__).resolve().parent.parent / "evals" / "scenarios"))
    p_run = sub.add_parser("run", help="run one scenario LIVE (launches claude -p; trusted use only)")
    p_run.add_argument("scenario_dir")
    p_run.add_argument("--workdir", default=None)
    args = parser.parse_args()

    if args.cmd == "validate":
        dirs = discover_scenarios(args.root)
        if not dirs:
            print(f"no scenarios under {args.root}", file=sys.stderr)
            sys.exit(2)
        for d in dirs:
            load_scenario(d)
            print(f"✓ {d.name}")
        sys.exit(0)

    scenario = load_scenario(args.scenario_dir)
    result = run_scenario(scenario, workdir=args.workdir)
    for r in result.checks:
        print(f"  [{'PASS' if r.passed else 'FAIL'}] {r.detail}")
    print(f"verdict: {result.verdict.value}")
    sys.exit(EXIT_CODES[result.verdict])


if __name__ == "__main__":
    main()
