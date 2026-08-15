"""Strict, local evaluation of milestone completion evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

KINDS = {"success", "error_path"}
VERDICTS = {
    "confirmed", "timeout", "blocked", "unobserved", "indeterminate",
    "skipped", "missing", "failed",
}
STATUSES = {"in_progress", "complete"}
UAT_DECISIONS = {"FIX_FIRST", "SHIP", "REJECT"}


@dataclass
class CriterionResult:
    id: str
    kind: str
    required: bool
    verdict: str
    observed: str
    evidence: str
    recovery: str
    passed: bool
    reason: str = ""


@dataclass
class MilestoneResult:
    milestone: str
    claimed_status: str
    uat_decision: str
    status: str
    valid: bool
    complete: bool
    criteria: list[CriterionResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class CompletionResult:
    valid: bool
    complete: bool
    exit_code: int
    milestones: list[MilestoneResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _string(data: dict[str, Any], key: str, source: Path, errors: list[str]) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{source}: {key} must be a non-empty string")
        return ""
    return value


def _evidence_path(root: Path, value: str) -> Path | None:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _evaluate_manifest(
    root: Path, path: Path, data: Any, evidence_kinds: dict[str, str],
) -> MilestoneResult:
    errors: list[str] = []
    if not isinstance(data, dict):
        return MilestoneResult("?", "", "", "invalid", False, False,
                               errors=[f"{path}: manifest must be an object"])
    milestone = _string(data, "milestone", path, errors)
    revision = _string(data, "revision", path, errors)
    status = _string(data, "status", path, errors)
    uat_decision = _string(data, "uat_decision", path, errors)
    if data.get("schema_version") != 1:
        errors.append(f"{path}: unsupported schema_version")
    if status and status not in STATUSES:
        errors.append(f"{path}: unsupported status {status}")
    if uat_decision and uat_decision not in UAT_DECISIONS:
        errors.append(f"{path}: unsupported uat_decision {uat_decision}")
    raw_criteria = data.get("criteria")
    if not isinstance(raw_criteria, list):
        errors.append(f"{path}: criteria must be a list")
        raw_criteria = []

    criteria: list[CriterionResult] = []
    criterion_ids: set[str] = set()
    for index, raw in enumerate(raw_criteria):
        label = f"{path}: criteria[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{label} must be an object")
            continue
        criterion_id = _string(raw, "id", path, errors)
        kind = _string(raw, "kind", path, errors)
        verdict = _string(raw, "verdict", path, errors)
        observed = _string(raw, "observed", path, errors)
        recovery = _string(raw, "recovery", path, errors)
        required = raw.get("required")
        if not isinstance(required, bool):
            errors.append(f"{label}.required must be a boolean")
            required = True
        if criterion_id in criterion_ids:
            errors.append(f"{path}: duplicate criterion {criterion_id}")
        criterion_ids.add(criterion_id)
        if kind and kind not in KINDS:
            errors.append(f"{label}: unsupported kind {kind}")
        if verdict and verdict not in VERDICTS:
            errors.append(f"{label}: unsupported verdict {verdict}")

        evidence = raw.get("evidence")
        evidence_ref = ""
        stale = False
        if not isinstance(evidence, dict):
            errors.append(f"{label}: missing evidence")
        else:
            evidence_ref = _string(evidence, "path", path, errors)
            digest = _string(evidence, "sha256", path, errors)
            evidence_revision = _string(evidence, "revision", path, errors)
            target = _evidence_path(root, evidence_ref) if evidence_ref else None
            if target is None:
                errors.append(f"{label}: unsafe evidence path {evidence_ref!r}")
            elif not target.is_file():
                errors.append(f"{label}: evidence does not exist: {evidence_ref}")
            elif len(digest) != 64 or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                errors.append(f"{label}: evidence digest mismatch: {evidence_ref}")
            stale = bool(revision and evidence_revision and revision != evidence_revision)
            previous_kind = evidence_kinds.setdefault(evidence_ref, kind)
            if evidence_ref and previous_kind != kind:
                errors.append(
                    f"{path}: evidence {evidence_ref} cannot satisfy different expected outcomes"
                )
        passed = verdict == "confirmed" and not stale
        reason = ""
        if stale:
            reason = f"evidence revision does not match {revision}"
        elif verdict != "confirmed":
            reason = f"observed verdict is {verdict}"
        criteria.append(CriterionResult(
            criterion_id, kind, required, verdict, observed, evidence_ref,
            recovery, passed, reason,
        ))

    derived_complete = bool(criteria) and all(c.passed for c in criteria if c.required)
    contradiction = (status == "complete" or uat_decision == "SHIP") and not derived_complete
    if contradiction:
        errors.append(f"{path}: complete/SHIP claim contradicts required evidence")
    valid = not errors
    return MilestoneResult(
        milestone=milestone or "?",
        claimed_status=status,
        uat_decision=uat_decision,
        status="complete" if derived_complete and valid else "incomplete" if valid else "invalid",
        valid=valid,
        complete=derived_complete and valid,
        criteria=criteria,
        errors=errors,
    )


def evaluate_manifests(root: Path, milestone: str | None = None) -> CompletionResult:
    """Evaluate manifests under ``docs/completion`` with fail-closed evidence checks."""
    root = Path(root).resolve()
    manifest_dir = root / "docs" / "completion"
    paths = sorted(manifest_dir.glob("*.json")) if manifest_dir.is_dir() else []
    results: list[MilestoneResult] = []
    parse_errors: list[str] = []
    seen: set[str] = set()
    evidence_kinds: dict[str, str] = {}
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            parse_errors.append(f"{path}: malformed manifest: {exc}")
            continue
        result = _evaluate_manifest(root, path, data, evidence_kinds)
        if result.milestone in seen:
            result.errors.append(f"duplicate milestone {result.milestone}")
            result.valid = False
            result.complete = False
            result.status = "invalid"
        seen.add(result.milestone)
        results.append(result)
    if milestone is not None:
        results = [result for result in results if result.milestone == milestone]
        if not results and not parse_errors:
            parse_errors.append(f"unknown milestone {milestone}")
    errors = parse_errors + [error for result in results for error in result.errors]
    valid = not errors
    complete = valid and all(result.complete for result in results)
    exit_code = 2 if not valid else 0 if complete else 1
    return CompletionResult(valid, complete, exit_code, results, errors)


def render_completion(result: CompletionResult) -> str:
    """Render the same derived decisions exposed by ``as_dict``."""
    if not result.milestones and not result.errors:
        return "Completion: no manifests\n"
    lines: list[str] = []
    for milestone in result.milestones:
        lines.append(f"{milestone.milestone}: {milestone.status}")
        for criterion in milestone.criteria:
            if criterion.required and not criterion.passed:
                lines.append(f"  {criterion.id}: {criterion.reason}")
                lines.append(f"  Next: {criterion.recovery}")
        lines.extend(f"  Error: {error}" for error in milestone.errors)
    lines.extend(f"Error: {error}" for error in result.errors if not result.milestones)
    return "\n".join(lines) + "\n"
