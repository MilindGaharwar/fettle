"""Living specification model (Stage 3, Pillar 1).

Parses structured spec files: markdown with YAML-style frontmatter marked
by the ``fettle-spec`` key. Detection is by frontmatter content, never by
filename. Grammar (deliberately small — everything else is free prose):

- frontmatter: ``fettle-spec``, ``id``, ``status``, ``scope`` (glob list)
- ``## Requirements`` — list items ``R<n>. <text>``
- ``## Scenarios`` — headings ``### S<n>. <title> (traces R<n>[, R<m>])``
  each followed by Given/When/Then bullets

Stable IDs: ``<spec-id>/R<n>`` and ``<spec-id>/S<n>`` — the ontology seed
for the semantic layer (Stage 6). Frontmatter is parsed with a minimal
reader (no PyYAML dependency), consistent with the rest of the tree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

VALID_STATUSES = frozenset({"draft", "active", "superseded"})

_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_REQ_RE = re.compile(r"^[-*]\s+(R\d+)\.\s+(.+)$")
_SCENARIO_RE = re.compile(r"^###\s+(S\d+)\.\s+(.+?)(?:\s*\(traces\s+([^)]+)\))?\s*$")
_GWT_RE = re.compile(r"^[-*]\s+(Given|When|Then)\b", re.IGNORECASE)
_TRACE_MARKER_RE = re.compile(r"(?:#|//)\s*traces?:\s*(.+?)\s*$")

#: Test files eligible for trace markers (Python and JS/TS conventions).
_TEST_NAME_RE = re.compile(
    r"(^test_.+\.py$)|(_test\.py$)|(\.(test|spec)\.(js|jsx|ts|tsx|mjs|cjs)$)"
)

_SKIP_DIRS = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
})


@dataclass
class Scenario:
    id: str  # e.g. "S1"
    title: str
    line: int
    traces: list[str] = field(default_factory=list)  # e.g. ["R1"]
    steps: list[str] = field(default_factory=list)  # lowercased keywords seen


@dataclass
class Spec:
    path: str  # repo-relative
    spec_id: str
    status: str
    scope: list[str] = field(default_factory=list)
    requirements: dict[str, str] = field(default_factory=dict)  # "R1" -> text
    scenarios: list[Scenario] = field(default_factory=list)


def _finding(path: str, line: int, severity: str, message: str, fix: str) -> dict:
    return {
        "file": path,
        "line": line,
        "rule": "SPEC_LINT",
        "severity": severity,
        "tool": "spec_model",
        "message": message,
        "fix": fix,
    }


def _parse_frontmatter(lines: list[str]) -> tuple[dict, int]:
    """Parse minimal YAML frontmatter. Returns (data, body_start_line_index).

    Supports ``key: value`` scalars and ``key:`` followed by ``- item``
    lists. Returns ({}, 0) when no frontmatter block is present.
    """
    if not lines or lines[0].strip() != "---":
        return {}, 0
    data: dict = {}
    current_list: list[str] | None = None
    for i, raw in enumerate(lines[1:], start=1):
        line = raw.rstrip()
        if line.strip() == "---":
            return data, i + 1
        stripped = line.strip()
        if current_list is not None and stripped.startswith("- "):
            current_list.append(stripped[2:].strip().strip("'\""))
            continue
        current_list = None
        if ":" in stripped and not stripped.startswith("#"):
            key, _, value = stripped.partition(":")
            key, value = key.strip(), value.split("#")[0].strip().strip("'\"")
            if value:
                data[key] = value
            else:
                current_list = []
                data[key] = current_list
    return {}, 0  # unterminated frontmatter — treat as no frontmatter


def is_spec_text(text: str) -> bool:
    """Cheap detection: frontmatter block containing a fettle-spec key."""
    data, end = _parse_frontmatter(text.splitlines()[:50])
    return end > 0 and "fettle-spec" in data


def parse_spec(text: str, path: str = "<spec>") -> tuple[Spec | None, list[dict]]:
    """Parse spec text. Returns (spec-or-None, findings).

    Returns (None, [error]) only when the file is not a spec at all or the
    frontmatter is unusable; grammar problems inside a valid spec return
    the spec plus findings.
    """
    lines = text.splitlines()
    meta, body_start = _parse_frontmatter(lines)
    if body_start == 0 or "fettle-spec" not in meta:
        return None, [_finding(path, 1, "ERROR",
                                "Not a fettle spec: missing frontmatter with a 'fettle-spec' key.",
                                "Add '---\\nfettle-spec: v1\\nid: <kebab-id>\\n---' at the top.")]
    findings: list[dict] = []

    spec_id = str(meta.get("id", ""))
    if not _ID_RE.match(spec_id):
        findings.append(_finding(path, 1, "ERROR",
                                 f"Spec id {spec_id!r} is missing or not kebab-case.",
                                 "Set frontmatter 'id:' to a unique kebab-case identifier."))
    status = str(meta.get("status", "draft"))
    if status not in VALID_STATUSES:
        findings.append(_finding(path, 1, "ERROR",
                                 f"Spec status {status!r} is not one of {sorted(VALID_STATUSES)}.",
                                 "Set frontmatter 'status:' to draft, active, or superseded."))
    scope = meta.get("scope", [])
    if isinstance(scope, str):
        scope = [scope]

    spec = Spec(path=path, spec_id=spec_id, status=status, scope=list(scope))

    section = ""
    current: Scenario | None = None
    for lineno, raw in enumerate(lines[body_start:], start=body_start + 1):
        line = raw.rstrip()
        heading = re.match(r"^##\s+(\w[\w ]*)$", line)
        if heading:
            section = heading.group(1).strip().lower()
            current = None
            continue
        if section == "requirements":
            m = _REQ_RE.match(line.strip())
            if m:
                rid, text_part = m.group(1), m.group(2).strip()
                if rid in spec.requirements:
                    findings.append(_finding(path, lineno, "ERROR",
                                             f"Duplicate requirement id {rid}.",
                                             "Renumber so each R<n> appears once."))
                spec.requirements[rid] = text_part
        elif section == "scenarios":
            m = _SCENARIO_RE.match(line)
            if m:
                sid, title, traces_raw = m.group(1), m.group(2).strip(), m.group(3)
                if any(s.id == sid for s in spec.scenarios):
                    findings.append(_finding(path, lineno, "ERROR",
                                             f"Duplicate scenario id {sid}.",
                                             "Renumber so each S<n> appears once."))
                traces = [t.strip() for t in traces_raw.split(",")] if traces_raw else []
                current = Scenario(id=sid, title=title, line=lineno, traces=traces)
                spec.scenarios.append(current)
                continue
            g = _GWT_RE.match(line.strip())
            if g and current is not None:
                current.steps.append(g.group(1).lower())

    # Cross-checks
    for scen in spec.scenarios:
        for keyword in ("given", "when", "then"):
            if keyword not in scen.steps:
                findings.append(_finding(path, scen.line, "ERROR",
                                         f"Scenario {scen.id} has no '{keyword.capitalize()}' step.",
                                         f"Add a '- {keyword.capitalize()} …' bullet under {scen.id}."))
        for rid in scen.traces:
            if rid not in spec.requirements:
                findings.append(_finding(path, scen.line, "ERROR",
                                         f"Scenario {scen.id} traces {rid}, which does not exist.",
                                         f"Add '{rid}.' under ## Requirements or fix the traces list."))
    traced_reqs = {rid for s in spec.scenarios for rid in s.traces}
    for rid in spec.requirements:
        if rid not in traced_reqs:
            findings.append(_finding(path, 1, "WARNING",
                                     f"Requirement {rid} has no scenario tracing it.",
                                     f"Add a scenario with '(traces {rid})' or remove {rid}."))
    if not spec.requirements:
        findings.append(_finding(path, 1, "WARNING",
                                 "Spec has no requirements — the spec is inert.",
                                 "Add 'R1. …' list items under a '## Requirements' heading."))
    return spec, findings


def discover_specs(root: str) -> list[tuple[Spec | None, list[dict]]]:
    """Find and parse every spec file under root. Sorted by path."""
    root_path = Path(root)
    results: list[tuple[Spec | None, list[dict]]] = []
    for md in sorted(root_path.rglob("*.md")):
        if any(part in _SKIP_DIRS for part in md.parts):
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not is_spec_text(text):
            continue
        rel = str(md.relative_to(root_path))
        results.append(parse_spec(text, rel))
    return results


def lint_specs(root: str) -> list[dict]:
    """Lint all specs under root, including repo-level duplicate-id check."""
    findings: list[dict] = []
    seen_ids: dict[str, str] = {}
    for spec, spec_findings in discover_specs(root):
        findings.extend(spec_findings)
        if spec is None or not spec.spec_id:
            continue
        if spec.spec_id in seen_ids:
            findings.append(_finding(spec.path, 1, "ERROR",
                                     f"Spec id '{spec.spec_id}' already used by {seen_ids[spec.spec_id]}.",
                                     "Give each spec a unique 'id:' in frontmatter."))
        else:
            seen_ids[spec.spec_id] = spec.path
        for pattern in spec.scope:
            if not list(Path(root).glob(pattern)):
                findings.append(_finding(spec.path, 1, "WARNING",
                                         f"Scope glob '{pattern}' matches nothing — binding is inert.",
                                         "Fix the glob or remove it from 'scope:'."))
    return findings


def extract_trace_markers(text: str) -> list[str]:
    """All ``# traces:`` / ``// traces:`` marker values in a file (comma-split)."""
    markers: list[str] = []
    for line in text.splitlines():
        m = _TRACE_MARKER_RE.search(line)
        if m:
            markers.extend(p.strip() for p in m.group(1).split(",") if p.strip())
    return markers


def _iter_test_files(root: Path) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in _SKIP_DIRS for part in p.parts):
            continue
        if _TEST_NAME_RE.search(p.name):
            out.append(p)
    return out


def scenario_coverage(root: str) -> dict:
    """Scenario→test coverage evidence artifact.

    Reports passes (which test covers which scenario), not only gaps —
    a gate consumer must be able to show evidence of success. Only
    scenario-granular markers (``<spec-id>/S<n>``) count as coverage;
    whole-spec markers (``<spec-id>``) are reported separately as coarse
    traces. Unknown marker targets are surfaced, never dropped.
    """
    root_path = Path(root)
    specs = [s for s, _ in discover_specs(root) if s is not None and s.spec_id]
    by_id = {s.spec_id: s for s in specs}
    if not by_id:  # no specs: markers are meaningless, don't scan tests
        return {"specs": [], "unknown_traces": [],
                "totals": {"scenarios": 0, "covered": 0, "coverage_percent": 100.0}}

    scenario_tests: dict[str, list[str]] = {}  # "<spec-id>/S<n>" -> test paths
    spec_tests: dict[str, list[str]] = {}  # "<spec-id>" -> test paths
    unknown: list[dict] = []
    for test in _iter_test_files(root_path):
        rel = str(test.relative_to(root_path))
        try:
            text = test.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for marker in extract_trace_markers(text):
            spec_part, _, scen_part = marker.partition("/")
            spec = by_id.get(spec_part)
            if spec is None:
                if _ID_RE.match(spec_part):  # ignore non-spec-shaped markers (e.g. WP ids)
                    unknown.append({"test": rel, "marker": marker,
                                    "reason": f"no spec with id '{spec_part}'"})
                continue
            if not scen_part:
                spec_tests.setdefault(spec_part, []).append(rel)
            elif any(s.id == scen_part for s in spec.scenarios):
                scenario_tests.setdefault(marker, []).append(rel)
            else:
                unknown.append({"test": rel, "marker": marker,
                                "reason": f"spec '{spec_part}' has no scenario {scen_part}"})

    report_specs: list[dict] = []
    total = covered = 0
    for spec in specs:
        rows = []
        for scen in spec.scenarios:
            tests = scenario_tests.get(f"{spec.spec_id}/{scen.id}", [])
            rows.append({"id": scen.id, "title": scen.title,
                         "covered": bool(tests), "covered_by": tests})
            total += 1
            covered += bool(tests)
        report_specs.append({
            "id": spec.spec_id, "path": spec.path, "status": spec.status,
            "scenarios": rows,
            "spec_level_traces": spec_tests.get(spec.spec_id, []),
            "covered": sum(1 for r in rows if r["covered"]),
            "total": len(rows),
        })
    return {
        "specs": report_specs,
        "unknown_traces": unknown,
        "totals": {
            "scenarios": total,
            "covered": covered,
            "coverage_percent": round(100 * covered / total, 1) if total else 100.0,
        },
    }
