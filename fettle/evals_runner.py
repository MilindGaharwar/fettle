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
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write(
        "fettle evals requires PyYAML; install 'finefettle[evals]'\n"
    )
    sys.exit(2)

logger = logging.getLogger("fettle.evals")

CHECK_TYPES = frozenset({
    "file_matches",        # regex found in workdir file
    "file_not_matches",    # regex absent from workdir file
    "transcript_matches",
    "transcript_not_matches",
})
LANGUAGES = frozenset({"python", "typescript"})


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
    language: str | None = None
    held_out: bool = False


@dataclass(frozen=True)
class CheckRecord:
    check: Check
    passed: bool
    detail: str


@dataclass(frozen=True)
class EvalMetrics:
    repair_success: bool | None
    turns_to_repair: int | None
    repeated_violation: bool
    diagnostic_bytes: int
    indeterminate_reason: str | None = None

    def to_dict(self) -> dict[str, bool | int | str | None]:
        return {
            "repair_success": self.repair_success,
            "turns_to_repair": self.turns_to_repair,
            "repeated_violation": self.repeated_violation,
            "diagnostic_bytes": self.diagnostic_bytes,
            "indeterminate_reason": self.indeterminate_reason,
        }


@dataclass(frozen=True)
class RunResult:
    verdict: Verdict
    checks: tuple[CheckRecord, ...]
    transcript: str
    metrics: EvalMetrics


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
    language = data.get("language")
    if language is not None and language not in LANGUAGES:
        raise ValueError(f"{path}: 'language' must be one of {sorted(LANGUAGES)}")
    held_out = data.get("held_out", False)
    if not isinstance(held_out, bool):
        raise ValueError(f"{path}: 'held_out' must be a boolean")
    return Scenario(
        id=str(data.get("id", Path(scenario_dir).name)),
        prompt=prompt,
        checks=tuple(checks),
        setup_files={str(k): str(v) for k, v in setup_files.items()},
        language=language,
        held_out=held_out,
    )


def _contained(workdir: Path, rel: str) -> Path:
    """Resolve rel against workdir, refusing escapes (L-06).

    Scenario files are data, not trusted code — a scenario must not be able
    to read or write outside its working directory via `../` or absolute
    check/setup paths.
    """
    if Path(rel).is_absolute():
        raise ValueError(f"scenario path must be relative: {rel}")
    target = (workdir / rel).resolve()
    if not target.is_relative_to(workdir.resolve()):
        raise ValueError(f"scenario path escapes the working directory: {rel}")
    return target


def _evaluate(check: Check, transcript: str, workdir: Path) -> CheckRecord:
    if check.type.startswith("file_"):
        try:
            target = _contained(workdir, check.path or "")
        except ValueError as e:
            return CheckRecord(check=check, passed=False, detail=str(e))
        content = target.read_text() if target.is_file() else ""
        found = re.search(check.regex, content) is not None
        wanted = check.type == "file_matches"
        detail = f"{check.path}: /{check.regex}/ {'found' if found else 'absent'}"
    else:
        found = re.search(check.regex, transcript) is not None
        wanted = check.type == "transcript_matches"
        detail = f"transcript: /{check.regex}/ {'found' if found else 'absent'}"
    return CheckRecord(check=check, passed=found == wanted, detail=detail)


def _invoke_runner(runner, prompt: str, cwd: Path) -> tuple[str, int | None]:
    """Bridge: AgentRunner (fettle.runners) or plain callable (test seam).

    An AgentRunner reporting an error raises — run_scenario maps that to
    INDETERMINATE (broken experiment), same path as a crashing callable.
    """
    if hasattr(runner, "run"):
        timeout_s = int(os.environ.get("FETTLE_EVAL_TIMEOUT_S", "600"))
        result = runner.run(prompt, cwd, timeout_s=timeout_s)
        if result.error:
            raise RuntimeError(result.error)
        return result.transcript, getattr(result, "turns", None)
    return runner(prompt, cwd), None


def _metrics(
    verdict: Verdict,
    transcript: str,
    records: tuple[CheckRecord, ...] = (),
    *,
    turns: int | None = None,
    reason: str | None = None,
) -> EvalMetrics:
    return EvalMetrics(
        repair_success=None if verdict == Verdict.INDETERMINATE else verdict == Verdict.PASS,
        turns_to_repair=turns if verdict == Verdict.PASS else None,
        repeated_violation=verdict == Verdict.FAIL and any(not record.passed for record in records),
        diagnostic_bytes=len(transcript.encode("utf-8")),
        indeterminate_reason=reason,
    )


def run_scenario(scenario: Scenario, runner=None, workdir: str | Path | None = None) -> RunResult:
    if runner is None:
        from fettle.runners import get_runner
        runner = get_runner(os.environ.get("FETTLE_EVAL_RUNNER", "claude"))
    workdir = Path(workdir) if workdir else Path.cwd() / "evals-run"
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        setup_targets = {rel: _contained(workdir, rel)
                         for rel in scenario.setup_files}
    except ValueError as e:
        transcript = f"containment error: {e}"
        return RunResult(Verdict.INDETERMINATE, (), transcript, _metrics(
            Verdict.INDETERMINATE, transcript, reason=transcript,
        ))
    for rel, content in scenario.setup_files.items():
        target = setup_targets[rel]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    try:
        transcript, turns = _invoke_runner(runner, scenario.prompt, workdir)
    except Exception as e:  # noqa: BLE001 — runner failure is indeterminate (broken experiment), not fail
        logger.warning("eval runner failed for %s: %s", scenario.id, e)
        transcript = f"runner error: {e}"
        return RunResult(Verdict.INDETERMINATE, (), transcript, _metrics(
            Verdict.INDETERMINATE, transcript, reason=transcript,
        ))
    has_transcript_checks = any(c.type.startswith("transcript_") for c in scenario.checks)
    if not transcript.strip() and has_transcript_checks:
        reason = "runner returned an empty transcript"
        return RunResult(Verdict.INDETERMINATE, (), transcript, _metrics(
            Verdict.INDETERMINATE, transcript, reason=reason,
        ))
    records = tuple(_evaluate(c, transcript, workdir) for c in scenario.checks)
    verdict = Verdict.PASS if all(r.passed for r in records) else Verdict.FAIL
    return RunResult(verdict, records, transcript, _metrics(
        verdict, transcript, records, turns=turns,
    ))


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
            sys.stderr.write(f"no scenarios under {args.root}\n")
            sys.exit(2)
        for d in dirs:
            load_scenario(d)
            sys.stdout.write(f"✓ {d.name}\n")
        sys.exit(0)

    scenario = load_scenario(args.scenario_dir)
    result = run_scenario(scenario, workdir=args.workdir)
    for r in result.checks:
        sys.stdout.write(f"  [{'PASS' if r.passed else 'FAIL'}] {r.detail}\n")
    sys.stdout.write(f"metrics: {json.dumps(result.metrics.to_dict(), sort_keys=True)}\n")
    sys.stdout.write(f"verdict: {result.verdict.value}\n")
    sys.exit(EXIT_CODES[result.verdict])


if __name__ == "__main__":
    main()
