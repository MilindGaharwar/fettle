"""P38 — Canonical specification traceability and drift evidence.

One canonical query connects specifications, scenarios, tests, governed
code, and executed results using stable spec/scenario IDs — never filename
similarity. Marker grammar: ``<spec-id>/<scenario-id>`` (e.g.
``checkout-flow/S2``), declared in test files as ``# traces: <marker>``.

Drift evidence flags governed code changes whose active governing
specification was neither changed nor explicitly reviewed in an audit
artifact, and reports uncovered scenarios, unknown markers, unlinked
tests, and executed coverage as separate sections (evolution plan P38).
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

from fettle.spec_model import (
    _TEST_NAME_RE,
    _TRACE_MARKER_RE,
    _SKIP_DIRS,
    Spec,
    discover_specs,
)

_VERIFIED_STATUSES = frozenset({"passed"})
_COUNTED_STATUSES = frozenset({"passed", "failed", "skipped"})


@dataclass
class TraceEntry:
    marker: str
    spec_path: str
    scenario_id: str
    requirement_ids: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)


def build_trace_index(root: str) -> dict[str, TraceEntry]:
    """Canonical marker index for every active spec scenario.

    Deterministic: identical specs produce an identically ordered index.
    """
    index: dict[str, TraceEntry] = {}
    for spec, _findings in sorted(discover_specs(root), key=lambda pair: pair[0].path if pair[0] else ""):
        if spec is None or spec.status != "active":
            continue
        for scen in spec.scenarios:
            entry = TraceEntry(
                marker=f"{spec.spec_id}/{scen.id}",
                spec_path=spec.path,
                scenario_id=scen.id,
                requirement_ids=list(scen.traces),
            )
            index[entry.marker] = entry
    return index


def _eligible_test_files(root_path: Path) -> list[str]:
    files: list[str] = []
    for path in sorted(root_path.rglob("*")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and _TEST_NAME_RE.search(path.name):
            files.append(str(path.relative_to(root_path)))
    return files


def collect_test_markers(root: str) -> tuple[dict[str, list[str]], list[str]]:
    """Scan eligible test files for ``# traces:`` markers.

    Returns ({marker: [test paths]}, [unknown markers]) where unknown means
    the marker does not resolve to an active spec scenario in the index.
    """
    root_path = Path(root)
    found: dict[str, list[str]] = {}
    for rel in _eligible_test_files(root_path):
        try:
            text = (root_path / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            match = _TRACE_MARKER_RE.search(line)
            if match:
                found.setdefault(match.group(1).strip(), []).append(rel)
    return found, []


def validate_markers(
    index: dict[str, TraceEntry], markers: dict[str, list[str]]
) -> list[str]:
    """Slice 2: markers must target existing active spec scenarios."""
    return sorted(marker for marker in markers if marker not in index)


def bind_results(
    index: dict[str, TraceEntry],
    test_markers: dict[str, list[str]],
    results: dict[str, str],
) -> dict[str, dict[str, int]]:
    """Slice 3: declaration alone is *linked*, only a passing run verifies.

    ``results`` maps test file → status; anything outside passed/failed/
    skipped is ignored. A skipped or failing test never counts as verified.
    """
    coverage: dict[str, dict[str, int]] = {}
    for marker in index:
        linked = [t for t in test_markers.get(marker, [])]
        statuses = [results.get(t) for t in linked if results.get(t) in _COUNTED_STATUSES]
        coverage[marker] = {
            "linked": len(linked),
            "verified": sum(1 for s in statuses if s == "passed"),
            "executed": sum(1 for s in statuses if s),
        }
    return coverage


def _governed_paths(specs: list[Spec], changed: set[str]) -> dict[str, list[str]]:
    """Map each changed path to the active specs whose scope globs govern it."""
    governed: dict[str, list[str]] = {}
    for path in sorted(changed):
        owners = [
            spec.spec_id
            for spec in specs
            if any(fnmatch.fnmatch(path, pattern) for pattern in spec.scope)
        ]
        if owners:
            governed[path] = owners
    return governed


def _coverage_sections(
    index: dict[str, TraceEntry],
    test_markers: dict[str, list[str]],
    coverage: dict[str, dict[str, int]],
) -> tuple[list[str], list[str], list[str]]:
    verified = sorted(m for m, c in coverage.items() if c["verified"] > 0)
    linked_only = sorted(
        m for m, c in coverage.items() if c["verified"] == 0 and c["linked"] > 0
    )
    linked_tests = {t for marker in index for t in test_markers.get(marker, [])}
    all_marked_tests = {t for tests in test_markers.values() for t in tests}
    orphan_tests = sorted(all_marked_tests - linked_tests)
    return verified, linked_only, orphan_tests


def drift_evidence(
    root: str,
    changed_paths: set[str],
    audit_reviewed: bool = False,
    audit_path: str = "docs/spec-audit.md",
    results: dict[str, str] | None = None,
) -> dict:
    """Slices 4-5: governed-change advisories plus separated report sections."""
    index = build_trace_index(root)
    test_markers, _unknown_from_scan = collect_test_markers(root)
    unknown_markers = validate_markers(index, test_markers)

    active = _active_specs(root)
    governed = _governed_paths(active, changed_paths)
    by_id = {spec.spec_id: spec for spec in active}
    advisories = _drift_advisories(governed=governed, by_id=by_id,
                                   changed=changed_paths,
                                   audit_reviewed=audit_reviewed)

    changed_spec_ids = {spec.spec_id for spec in active if spec.path in changed_paths}
    results = results or {}
    coverage = bind_results(index, test_markers, results)
    verified, linked_only, orphan_tests = _coverage_sections(
        index, test_markers, coverage
    )

    return {
        "status": "completed",
        "markers_total": len(index),
        "uncovered_scenarios": sorted(set(index) - set(test_markers)),
        "unknown_markers": unknown_markers,
        "orphan_tests": orphan_tests,
        "governed_without_review": [a["file"] for a in advisories],
        "advisories": advisories,
        "executed_coverage": {
            "verified": verified,
            "linked_only": linked_only,
            "results_seen": sum(1 for v in results.values() if v in _COUNTED_STATUSES),
        },
        "changed_governed_specs": sorted(changed_spec_ids),
    }


def _active_specs(root: str) -> list[Spec]:
    return [
        spec for spec, _findings in discover_specs(root)
        if spec is not None and spec.status == "active"
    ]


def _drift_advisories(
    governed: dict[str, list[str]],
    by_id: dict[str, Spec],
    changed: set[str],
    audit_reviewed: bool,
) -> list[dict]:
    advisories: list[dict] = []
    for path, owners in sorted(governed.items()):
        spec_changed = any(by_id[o].path in changed for o in owners)
        if spec_changed or audit_reviewed:
            continue
        advisories.append({
            "file": path,
            "line": 1,
            "rule": "TRACE_DRIFT",
            "severity": "WARNING",
            "tool": "trace_canonical",
            "message": (
                f"Governed by {', '.join(owners)} but neither the spec nor "
                f"an audit review covers this change."
            ),
            "fix": f"Revise {owners[0]} scenarios or record a spec audit.",
        })
    return advisories


def format_drift_report(report: dict) -> str:
    lines = ["# Canonical Trace Drift Report", ""]
    lines.append(f"Markers: {report['markers_total']}")
    for title, key in (
        ("Uncovered Scenarios", "uncovered_scenarios"),
        ("Unknown Markers", "unknown_markers"),
        ("Orphan Tests", "orphan_tests"),
        ("Governed Changes Without Review", "governed_without_review"),
        ("Verified Coverage", "executed_coverage"),
    ):
        value = report[key]
        lines.append("")
        if key == "executed_coverage":
            lines.append(f"## {title}")
            lines.append(f"- verified: {len(value['verified'])}")
            lines.append(f"- linked-only: {len(value['linked_only'])}")
            lines.append(f"- executed results seen: {value['results_seen']}")
        else:
            lines.append(f"## {title} ({len(value)})")
            lines.extend(f"- {item}" for item in value[:20])
    return "\n".join(lines) + "\n"
