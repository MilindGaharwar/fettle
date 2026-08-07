"""Versioned seeded-defect manifests used to qualify promotable checks."""

from __future__ import annotations

import json
import logging
import posixpath
import time
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable, Mapping
from typing import Any


SCHEMA_VERSION = "1"
logger = logging.getLogger(__name__)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _relative_dir(name: str, value: object, root: Path) -> str:
    value = _text(name, value).replace("\\", "/")
    normalized = posixpath.normpath(value)
    if normalized.startswith("/") or normalized == ".." or normalized.startswith("../"):
        raise ValueError(f"{name} must be fixture-relative")
    path = root / normalized
    if not path.is_dir():
        label = "defect fixture" if name == "defect_fixture" else "clean fixture"
        raise ValueError(f"{label} directory does not exist: {normalized}")
    return normalized


@dataclass(frozen=True)
class VerificationManifest:
    check_id: str
    owner: str
    runner: str
    clean_fixture: str
    defect_fixture: str
    prior_suite_expected: str
    expected_state: str
    expected_finding_code: str
    max_runtime_ms: int
    rerun_command: str
    root: Path
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class ManifestSet:
    manifests: tuple[VerificationManifest, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class FixtureOutcome:
    state: str
    finding_codes: tuple[str, ...] = ()
    duration_ms: float = 0.0


@dataclass(frozen=True)
class ConformanceResult:
    status: str
    errors: tuple[str, ...] = ()


def validate_manifest(value: dict[str, Any], root: Path) -> VerificationManifest:
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("manifest has an unsupported or missing schema_version")
    runtime = value.get("max_runtime_ms")
    if isinstance(runtime, bool) or not isinstance(runtime, int) or runtime <= 0:
        raise ValueError("max_runtime_ms must be a positive integer")
    prior = _text("prior_suite_expected", value.get("prior_suite_expected"))
    if prior != "pass":
        raise ValueError("prior_suite_expected must be 'pass'")
    expected = _text("expected_state", value.get("expected_state"))
    if expected != "violation":
        raise ValueError("expected_state must be 'violation'")
    return VerificationManifest(
        check_id=_text("check_id", value.get("check_id")),
        owner=_text("owner", value.get("owner")),
        runner=_text("runner", value.get("runner")),
        clean_fixture=_relative_dir("clean_fixture", value.get("clean_fixture"), root),
        defect_fixture=_relative_dir("defect_fixture", value.get("defect_fixture"), root),
        prior_suite_expected=prior,
        expected_state=expected,
        expected_finding_code=_text("expected_finding_code", value.get("expected_finding_code")),
        max_runtime_ms=runtime,
        rerun_command=_text("rerun_command", value.get("rerun_command")),
        root=root,
    )


def load_manifests(root: Path, promoted_check_ids: set[str] | None = None) -> ManifestSet:
    manifests: list[VerificationManifest] = []
    errors: list[str] = []
    for path in sorted(root.glob("*/manifest.json")):
        try:
            value = json.loads(path.read_text())
            manifests.append(validate_manifest(value, path.parent))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    by_check: dict[str, int] = {}
    for manifest in manifests:
        by_check[manifest.check_id] = by_check.get(manifest.check_id, 0) + 1
    for check_id, count in sorted(by_check.items()):
        if count > 1:
            errors.append(f"check '{check_id}' has {count} seeded-defect manifests")
    for check_id in sorted(promoted_check_ids or set()):
        if check_id not in by_check:
            errors.append(f"promoted check '{check_id}' has no seeded-defect manifest")
    return ManifestSet(tuple(manifests), tuple(errors))


FixtureRunner = Callable[[VerificationManifest, str, Path], FixtureOutcome]


def evaluate_manifest(
    manifest: VerificationManifest,
    runners: Mapping[str, FixtureRunner] | FixtureRunner,
) -> ConformanceResult:
    if callable(runners):
        runner = runners
    else:
        runner = runners.get(manifest.runner)
        if runner is None:
            return ConformanceResult(
                "tool_error", (f"runner '{manifest.runner}' is not registered",),
            )
    phases = (
        ("prior", manifest.root / manifest.defect_fixture),
        ("clean", manifest.root / manifest.clean_fixture),
        ("defect", manifest.root / manifest.defect_fixture),
    )
    outcomes: dict[str, FixtureOutcome] = {}
    for phase, path in phases:
        try:
            outcome = runner(manifest, phase, path)
        except Exception as exc:  # noqa: BLE001 - runner failure is evidence, not a crash
            logger.error("verification runner failed during %s: %s", phase, exc, exc_info=True)
            return ConformanceResult("tool_error", (f"{phase} runner failed: {exc}",))
        if not isinstance(outcome, FixtureOutcome):
            return ConformanceResult("tool_error", (f"{phase} runner returned malformed output",))
        if outcome.duration_ms > manifest.max_runtime_ms:
            return ConformanceResult(
                "violation",
                (f"{phase} runtime {outcome.duration_ms}ms exceeds {manifest.max_runtime_ms}ms",),
            )
        if outcome.state in {"tool_error", "unknown"}:
            return ConformanceResult("violation", (f"{phase} returned {outcome.state}",))
        outcomes[phase] = outcome

    if outcomes["prior"].state != manifest.prior_suite_expected:
        return ConformanceResult(
            "violation", ("preceding assurance layer did not miss the seeded defect",),
        )
    if outcomes["clean"].state != "pass":
        return ConformanceResult("violation", ("clean fixture did not pass",))
    if outcomes["defect"].state != manifest.expected_state:
        return ConformanceResult("violation", ("known-bad fixture was not detected",))
    if manifest.expected_finding_code not in outcomes["defect"].finding_codes:
        return ConformanceResult(
            "violation",
            (f"expected finding {manifest.expected_finding_code!r} was not emitted",),
        )
    return ConformanceResult("pass")


def _ci_verdict_runner(
    _manifest: VerificationManifest,
    phase: str,
    path: Path,
) -> FixtureOutcome:
    started = time.monotonic()
    try:
        value = json.loads((path / "verdict.json").read_text())
    except (OSError, json.JSONDecodeError):
        return FixtureOutcome("tool_error", duration_ms=(time.monotonic() - started) * 1000)
    required = (value.get("sha"), value.get("status"), value.get("conclusion"))
    duration = (time.monotonic() - started) * 1000
    if not all(isinstance(item, str) and item for item in required):
        return FixtureOutcome("tool_error", duration_ms=duration)
    if phase == "prior":
        return FixtureOutcome("pass", duration_ms=duration)
    if value["status"] != "completed":
        return FixtureOutcome("unknown", duration_ms=duration)
    if value["conclusion"] == "success":
        return FixtureOutcome("pass", duration_ms=duration)
    return FixtureOutcome("violation", ("CI_FAILED",), duration)


BUILTIN_RUNNERS: dict[str, FixtureRunner] = {
    "ci-verdict-json": _ci_verdict_runner,
}
