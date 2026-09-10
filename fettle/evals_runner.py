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
import random
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


def evaluate_contextual_rankings(cases: list[dict], *, held_out: bool) -> dict:
    """Compute aggregate precision@10 for one frozen corpus split."""
    selected = [case for case in cases if case.get("held_out") is held_out]
    relevant = 0
    returned = 0
    for case in selected:
        ranked = case.get("ranked_contextual", [])[:10]
        labels = set(case.get("contextual_relevance", []))
        relevant += sum(item in labels for item in ranked)
        returned += len(ranked)
    precision = round(relevant * 10_000 / returned) if returned else 0
    return {
        "split": "held_out" if held_out else "development",
        "case_count": len(selected),
        "relevant_in_top_10": relevant,
        "returned_in_top_10": returned,
        "precision_at_10_basis_points": precision,
    }


def validate_contextual_corpus(corpus: dict) -> list[str]:
    """Validate the frozen v2 ranking corpus without requiring collected cases."""
    if corpus.get("schema_version") != 2:
        raise ValueError("contextual corpus schema_version must be 2")
    review = corpus.get("review")
    cases = corpus.get("cases")
    if not isinstance(review, dict) or not isinstance(cases, list):
        raise ValueError("contextual corpus requires review metadata and cases")
    reviewers = review.get("reviewers", [])
    if len(reviewers) < 2 or review.get("labeling") != "blind-randomized":
        raise ValueError("contextual corpus requires two reviewers and blind-randomized labeling")
    roles = review.get("reviewer_roles")
    model_classes = review.get("reviewer_model_classes")
    if (
        not isinstance(roles, dict)
        or set(roles) != set(reviewers)
        or set(roles.values()) != {"ai"}
        or not isinstance(model_classes, dict)
        or set(model_classes) != set(reviewers)
        or len(set(model_classes.values())) != len(reviewers)
        or review.get("ai_independence") != "fresh-context-blinded"
        or review.get("disagreement_resolution")
        != "owner-reconciles-after-both-ai-reviews"
    ):
        raise ValueError(
            "contextual corpus requires two distinct fresh-context blinded AI reviewers "
            "and owner reconciliation"
        )
    limits = {
        "minimum_ranking_cases_per_split": 1,
        "minimum_candidates_per_case": 10,
        "minimum_relevant_per_case": 1,
        "minimum_irrelevant_per_case": 1,
    }
    for name, floor in limits.items():
        if not isinstance(review.get(name), int) or review[name] < floor:
            raise ValueError(f"{name} must be an integer of at least {floor}")

    seen_ids: set[str] = set()
    groups: dict[str, str] = {}
    for case in cases:
        case_id = case.get("id")
        split = case.get("split")
        group = case.get("group")
        if not case_id or case_id in seen_ids:
            raise ValueError("contextual case ids must be unique and non-empty")
        seen_ids.add(case_id)
        if split not in {"development", "held_out"} or not group:
            raise ValueError(f"{case_id}: split and group are required")
        identity_fields = (
            "repository_digest", "revision", "graph_digest", "provider_digest", "oracle_digest",
        )
        if not all(case.get(name) for name in identity_fields):
            raise ValueError(f"{case_id}: immutable identity fields are required")
        if group in groups and groups[group] != split:
            raise ValueError(f"split leakage: group {group} appears in both splits")
        groups[group] = split
        if not case.get("ranking_eligible", False):
            continue
        candidates = case.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError(f"{case_id}: candidates must be a list")
        if len(candidates) < review["minimum_candidates_per_case"]:
            raise ValueError(
                f"{case_id}: requires at least {review['minimum_candidates_per_case']} candidates"
            )
        keys: set[str] = set()
        counts = {"relevant": 0, "irrelevant": 0}
        for candidate in candidates:
            key = candidate.get("stable_key")
            relevance = candidate.get("relevance")
            if not key or key in keys:
                raise ValueError(f"{case_id}: candidate stable keys must be unique and non-empty")
            keys.add(key)
            if relevance not in counts:
                raise ValueError(f"{case_id}: candidate relevance must be relevant or irrelevant")
            counts[relevance] += 1
            if not candidate.get("rationale"):
                raise ValueError(f"{case_id}: every candidate requires a rationale")
            reviews = candidate.get("reviews")
            if not isinstance(reviews, list) or {
                item.get("reviewer") for item in reviews if isinstance(item, dict)
            } != set(reviewers):
                raise ValueError(f"{case_id}: every candidate requires one blind review per declared reviewer")
            if any(
                item.get("relevance") not in counts or not item.get("rationale")
                for item in reviews
            ):
                raise ValueError(f"{case_id}: blind reviews require relevance and rationale")
            score = candidate.get("score")
            depth = candidate.get("depth")
            if (
                not isinstance(score, int) or isinstance(score, bool) or score < 0
                or not isinstance(depth, int) or isinstance(depth, bool) or depth < 0
            ):
                raise ValueError(f"{case_id}: score and depth must be non-negative integers")
        for relevance in ("relevant", "irrelevant"):
            minimum = review[f"minimum_{relevance}_per_case"]
            if counts[relevance] < minimum:
                raise ValueError(f"{case_id}: requires at least {minimum} {relevance} candidates")
        required = case.get("required_targets")
        actual = case.get("actual_required")
        if not isinstance(required, list) or not isinstance(actual, list):
            raise ValueError(f"{case_id}: required target and actual-required lists are required")
    return []


def evaluate_contextual_corpus(corpus: dict, *, split: str) -> dict:
    """Evaluate paired stable-key and deterministic ranker orderings for one split."""
    validate_contextual_corpus(corpus)
    if split not in {"development", "held_out"}:
        raise ValueError("split must be development or held_out")
    selected = [
        case for case in corpus["cases"]
        if case["split"] == split and case.get("ranking_eligible", False)
    ]
    ranker_hits = baseline_hits = returned = required = required_found = 0
    paired_deltas = []
    for case in selected:
        candidates = case["candidates"]
        baseline = sorted(candidates, key=lambda item: item["stable_key"])[:10]
        ranker = sorted(
            candidates,
            key=lambda item: (-item["score"], item["depth"], item["stable_key"]),
        )[:10]
        baseline_case_hits = sum(item["relevance"] == "relevant" for item in baseline)
        ranker_case_hits = sum(item["relevance"] == "relevant" for item in ranker)
        baseline_hits += baseline_case_hits
        ranker_hits += ranker_case_hits
        returned += len(ranker)
        paired_deltas.append(round((ranker_case_hits - baseline_case_hits) * 10_000 / len(ranker)))
        expected_required = set(case["required_targets"])
        actual_required = set(case["actual_required"])
        required += len(expected_required)
        required_found += len(expected_required & actual_required)
    ranker_precision = round(ranker_hits * 10_000 / returned) if returned else 0
    baseline_precision = round(baseline_hits * 10_000 / returned) if returned else 0
    required_recall = round(required_found * 10_000 / required) if required else None
    minimum = corpus["review"]["minimum_ranking_cases_per_split"]
    blockers = []
    if len(selected) < minimum:
        blockers.append(f"requires at least {minimum} ranking-eligible {split} cases")
    if required_recall is None:
        blockers.append("requires at least one required-impact label")
    elif required_recall < 10_000:
        blockers.append("required-impact recall must be 100%")
    relative_gain = (
        round((ranker_precision - baseline_precision) * 10_000 / baseline_precision)
        if baseline_precision else None
    )
    confidence_interval = _paired_bootstrap_interval(paired_deltas)
    if split != "held_out":
        blockers.append("promotion requires the frozen held_out split")
    elif not blockers and relative_gain is None:
        blockers.append("baseline precision is zero; relative gain is undefined")
    elif not blockers and relative_gain < 1000:
        blockers.append("held-out relative precision gain must be at least 10%")
    elif not blockers and confidence_interval[0] <= 0:
        blockers.append("paired 95% gain interval must be above zero")
    return {
        "split": split,
        "case_count": len(selected),
        "ranker_precision_at_10_basis_points": ranker_precision,
        "baseline_precision_at_10_basis_points": baseline_precision,
        "relative_gain_basis_points": relative_gain,
        "paired_case_deltas_basis_points": paired_deltas,
        "paired_gain_ci95_basis_points": list(confidence_interval),
        "required_recall_basis_points": required_recall,
        "evaluation_ready": len(selected) >= minimum,
        "promotion_ready": not blockers,
        "blocking_reasons": blockers,
    }


def _paired_bootstrap_interval(deltas: list[int]) -> tuple[int, int]:
    if not deltas:
        return (0, 0)
    randomizer = random.Random(0)
    means = sorted(
        round(sum(randomizer.choice(deltas) for _ in deltas) / len(deltas))
        for _ in range(10_000)
    )
    return means[249], means[9749]


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
        from fettle.spawn import governed_run
        timeout_s = int(os.environ.get("FETTLE_EVAL_TIMEOUT_S", "600"))
        result = governed_run(runner, prompt, cwd, timeout_s)
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
