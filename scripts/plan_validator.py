#!/usr/bin/env python3
"""
Fettle plan validator — structural quality gate for development plans.

Enforces the 5-phase development pipeline:
  AUDIT → SPECIFY → REVIEW → IMPLEMENT → VERIFY

Every implementation WP must contain all four test method types:
  TDD (unit), INTEGRATION, REGRESSION (named scenario), LIVE (with command).

Usage:
  python3 plan_validator.py <plan_path.md>
  echo $?   # 0 = pass, 1 = fail
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Methods that indicate a WP contains implementation work.
# Any WP with at least one of these triggers the full test-type gate.
IMPLEMENTATION_METHODS: frozenset[str] = frozenset({
    "TDD", "BUILD", "FIX", "REFACTOR", "CODE", "INTEGRATION",
})

# All four test method types required in every implementation WP.
REQUIRED_TEST_METHODS: frozenset[str] = frozenset({
    "TDD", "INTEGRATION", "REGRESSION", "LIVE",
})

# REGRESSION tasks shorter than this (task+verify text) are considered generic.
_REGRESSION_MIN_LEN = 30


def _norm(s: str) -> str:
    """Normalize a method cell value: strip markdown, uppercase, letters+digits only."""
    return re.sub(r"[^A-Z0-9]", "", s.upper().strip())


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    passed: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.passed = False
        self.errors.append(msg)


# ---------------------------------------------------------------------------
# Markdown table parser
# ---------------------------------------------------------------------------

def _parse_table(text: str) -> list[dict[str, str]]:
    """
    Parse the first markdown table found in text.
    Returns list of row dicts keyed by normalised column header (lowercase, stripped).
    Returns [] if no table or no data rows.
    """
    lines = text.splitlines()
    headers: list[str] = []
    rows: list[dict[str, str]] = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]

        if not headers:
            headers = [c.lower() for c in cells]
            in_table = True
            continue

        # Separator row (e.g. |---|---|)
        if all(re.match(r"^[-:]+$", c) for c in cells if c):
            continue

        if len(cells) >= len(headers):
            rows.append(dict(zip(headers, cells)))

    return rows


# ---------------------------------------------------------------------------
# WP section parser
# ---------------------------------------------------------------------------

def _parse_wps(text: str) -> list[tuple[str, str]]:
    """
    Return [(wp_name, wp_body), ...] for every WP-* section in the plan.
    Sections are delimited by the next heading at the same or higher level.
    """
    pattern = re.compile(r"^(#{1,4})\s+(WP-\S.*?)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    wps = []
    for i, m in enumerate(matches):
        wp_name = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        wps.append((wp_name, text[start:end]))
    return wps


# Keywords that signal a WP introduces a queue/pipeline flag.
_QUEUE_FLAG_KEYWORDS: frozenset[str] = frozenset({  # fettle:queue-consumer-verified consumer=N/A
    "processed", "queued", "pending", "status='new'", 'status="new"',
    "processed=0", "processed = 0",
})

# Keywords that a LIVE task must mention to prove state transition was tested.
_STATE_TRANSITION_KEYWORDS: frozenset[str] = frozenset({
    "facts", "nodes", "count", "transition", "processed=1", "processed = 1",
    "queue empty", "state", "> 0", "= 1",
})

# Keywords that signal a WP touches health/monitoring.
_HEALTH_KEYWORDS: frozenset[str] = frozenset({
    "health", "score", "dimension", "monitoring", "status indicator",
    "responsiveness", "accuracy", "behavioral_consistency", "liveness",
})

# Keywords that a REGRESSION or LIVE task must mention for inversion coverage.
_INVERSION_KEYWORDS: frozenset[str] = frozenset({
    "degraded", "unknown", "< 0.5", "inversion", "bad condition",
    "status=unknown", "none", "no data",
})


def _text_contains_any(text: str, keywords: frozenset[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in keywords)


def _check_pipeline_completeness(
    wp_name: str, rows: list[dict[str, str]], result: ValidationResult
) -> None:
    """If any task mentions a queue flag, a LIVE task must assert state transition."""
    all_text = " ".join(
        row.get("task", "") + " " + row.get("verify by", "") + " " + row.get("verify", "")
        for row in rows
    )
    if not _text_contains_any(all_text, _QUEUE_FLAG_KEYWORDS):
        return

    live_rows = [r for r in rows if _norm(r.get("method", "")) == "LIVE"]
    live_text = " ".join(
        r.get("task", "") + " " + r.get("verify by", "") + " " + r.get("verify", "")
        for r in live_rows
    )
    if not _text_contains_any(live_text, _STATE_TRANSITION_KEYWORDS):
        result.fail(
            f"{wp_name}: WP introduces a queue/pipeline flag (processed/queued/pending) "
            "but no LIVE task asserts a state transition. "
            "The LIVE task must verify the downstream side effect occurred "
            "(e.g. 'facts > 0', 'nodes > 0', 'processed=1', 'queue empty'). "
            "Code existence is not sufficient — assert the state transition end-to-end. "
            "Incident: incident INC-2026-0501-B"
            "not that facts were extracted or processed=1 was set."
        )


def _check_health_inversion(
    wp_name: str, rows: list[dict[str, str]], result: ValidationResult
) -> None:
    """If any task mentions health/monitoring, a REGRESSION or LIVE task must cover inversion."""
    all_text = " ".join(
        row.get("task", "") + " " + row.get("verify by", "") + " " + row.get("verify", "")
        for row in rows
    )
    if not _text_contains_any(all_text, _HEALTH_KEYWORDS):
        return

    inversion_rows = [
        r for r in rows
        if _norm(r.get("method", "")) in ("REGRESSION", "LIVE")
    ]
    inversion_text = " ".join(
        r.get("task", "") + " " + r.get("verify by", "") + " " + r.get("verify", "")
        for r in inversion_rows
    )
    if not _text_contains_any(inversion_text, _INVERSION_KEYWORDS):
        result.fail(
            f"{wp_name}: WP touches a health/monitoring component but no REGRESSION or LIVE "
            "task asserts degraded/unknown output under bad conditions. "
            "Add an inversion test: inject the bad condition (bridge down, empty log, "
            "no data) and assert score < 0.5 or status=unknown. "
            "Incident: incident INC-2026-0501-A.0 when bridge "
            "was inactive; no inversion test existed to catch this."
        )


# ---------------------------------------------------------------------------
# Per-WP validation
# ---------------------------------------------------------------------------

def _validate_wp(wp_name: str, wp_body: str, result: ValidationResult) -> None:
    rows = _parse_table(wp_body)

    if not rows:
        # No table at all — check if one was intended
        if re.search(r"\|\s*method\s*\|", wp_body, re.IGNORECASE):
            result.fail(
                f"{wp_name}: Method column found but table has no data rows — "
                "add at least one task row."
            )
        return  # No table means no implementation tasks; skip gate

    # Require Method column
    if "method" not in rows[0]:
        result.fail(
            f"{wp_name}: Task table is missing the required 'Method' column. "
            "Every WP task table must have columns: #, Task, Method, Verify by."
        )
        return

    methods = [_norm(row.get("method", "")) for row in rows]
    method_set = set(methods)

    # Only gate WPs that contain implementation work
    if not (method_set & IMPLEMENTATION_METHODS):
        return  # INSPECT/VERIFY/REVIEW-only WP — no test gate

    # Require all four test method types
    missing = REQUIRED_TEST_METHODS - method_set
    if missing:
        result.fail(
            f"{wp_name}: Implementation WP is missing required test method(s): "
            f"{', '.join(sorted(missing))}. "
            "Every implementation WP must include TDD, INTEGRATION, REGRESSION, and LIVE tasks."
        )

    # Validate REGRESSION rows: must name a specific failure scenario
    for row in rows:
        if _norm(row.get("method", "")) != "REGRESSION":
            continue
        text_blob = (row.get("task", "") + " " + row.get("verify by", "") + " " + row.get("verify", "")).strip()
        if len(text_blob) < _REGRESSION_MIN_LEN:
            result.fail(
                f"{wp_name}: REGRESSION task is too generic: '{text_blob[:60]}'. "
                "Must name the specific failure scenario it prevents — include an incident "
                "date, bug description, or prior council finding."
            )

    # Validate LIVE rows: must specify an actual command
    for row in rows:
        if _norm(row.get("method", "")) != "LIVE":
            continue
        text_blob = (row.get("task", "") + " " + row.get("verify by", "") + " " + row.get("verify", "")).strip()
        has_command = (
            "`" in text_blob
            or "run " in text_blob.lower()
            or "command" in text_blob.lower()
            or "execute" in text_blob.lower()
            or "invoke" in text_blob.lower()
        )
        if not has_command:
            result.fail(
                f"{wp_name}: LIVE task must specify an exact command and observable outcome: "
                f"'{text_blob[:80]}'. "
                "Include the actual command (e.g. `pytest tests/`) and expected output."
            )

    # Semantic checks: pipeline completeness and health inversion
    _check_pipeline_completeness(wp_name, rows, result)
    _check_health_inversion(wp_name, rows, result)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_plan(text: str) -> ValidationResult:
    """Validate a plan's text. Returns ValidationResult with passed/errors."""
    result = ValidationResult()

    wps = _parse_wps(text)
    if not wps:
        result.fail(
            "Plan contains no work packages. "
            "Expected at least one section starting with '### WP-'."
        )
        return result

    for wp_name, wp_body in wps:
        _validate_wp(wp_name, wp_body, result)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: plan_validator.py <plan_path.md>", file=sys.stderr)
        return 1

    plan_path = Path(sys.argv[1])
    if not plan_path.exists():
        print(f"ERROR: Plan file not found: {plan_path}", file=sys.stderr)
        return 1

    text = plan_path.read_text()
    result = validate_plan(text)

    if result.passed:
        wp_count = len(_parse_wps(text))
        print(f"✓ Plan validation passed ({wp_count} work package(s))")
        return 0

    print("✗ Plan validation FAILED\n")
    for error in result.errors:
        print(f"  ERROR: {error}")
    for warning in result.warnings:
        print(f"  WARNING: {warning}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
