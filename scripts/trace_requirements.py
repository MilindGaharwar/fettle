"""WP-X5 — Requirements Traceability Command.

Links spec files to test files via naming convention and explicit markers.
Reports: uncovered specs, orphan tests, coverage percentage.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


_TRACE_MARKER_RE = re.compile(r"#\s*traces?:\s*(.+)")


def _find_specs(root: str, patterns: list[str]) -> list[str]:
    """Find spec files matching configured glob patterns."""
    root_path = Path(root)
    specs: list[str] = []
    for pattern in patterns:
        specs.extend(str(p.relative_to(root_path)) for p in root_path.glob(pattern))
    return sorted(set(specs))


def _find_tests(root: str, test_roots: list[str]) -> list[str]:
    """Find all test files under configured test roots."""
    tests: list[str] = []
    root_path = Path(root)
    for test_root in test_roots:
        test_dir = root_path / test_root
        if not test_dir.is_dir():
            continue
        for fpath in test_dir.rglob("test_*.py"):
            tests.append(str(fpath.relative_to(root_path)))
        for fpath in test_dir.rglob("*_test.py"):
            tests.append(str(fpath.relative_to(root_path)))
    return sorted(set(tests))


def _extract_markers(test_file: str, root: str) -> list[str]:
    """Extract explicit trace markers from a test file."""
    fpath = os.path.join(root, test_file)
    traced: list[str] = []
    try:
        with open(fpath, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = _TRACE_MARKER_RE.search(line)
                if m:
                    traced.append(m.group(1).strip())
    except OSError:
        pass
    return traced


def _spec_to_key(spec_path: str) -> str:
    """Derive a matching key from a spec path."""
    basename = os.path.splitext(os.path.basename(spec_path))[0]
    key = re.sub(r"[-_.]?(spec|requirements|ux-spec|strategy)[-_.]?", "", basename)
    key = re.sub(r"[-_]", "", key).lower()
    return key


def _test_to_key(test_path: str) -> str:
    """Derive a matching key from a test path."""
    basename = os.path.basename(test_path)
    key = re.sub(r"^test_|_test$", "", os.path.splitext(basename)[0])
    key = re.sub(r"[-_]", "", key).lower()
    return key


def trace_requirements(root: str, cfg: dict) -> dict:
    """Run traceability analysis. Returns structured report."""
    spec_patterns = cfg.get("spec_patterns", ["docs/**/*spec*.md", "docs/**/*requirements*.md"])
    test_roots = cfg.get("test_roots", ["tests/"])
    use_naming = cfg.get("naming_convention", True)

    specs = _find_specs(root, spec_patterns)
    tests = _find_tests(root, test_roots)

    if not specs:
        return {
            "status": "no_specs",
            "message": "No specification files found at configured patterns",
            "specs": [], "traced": [], "uncovered": [], "orphan_tests": [],
        }

    if not tests:
        return {
            "status": "no_tests",
            "message": "No test directory found",
            "specs": specs, "traced": [], "uncovered": specs, "orphan_tests": [],
        }

    # Build marker-based links
    marker_links: dict[str, list[str]] = {}
    for test in tests:
        markers = _extract_markers(test, root)
        for marker in markers:
            marker_links.setdefault(marker, []).append(test)

    # Match specs to tests
    traced: list[dict] = []
    uncovered: list[str] = []
    matched_tests: set[str] = set()

    for spec in specs:
        linked_tests: list[str] = []

        # Check explicit markers
        if spec in marker_links:
            linked_tests.extend(marker_links[spec])

        # Check naming convention
        if use_naming:
            spec_key = _spec_to_key(spec)
            if spec_key:
                for test in tests:
                    test_key = _test_to_key(test)
                    if spec_key == test_key or spec_key in test_key or test_key in spec_key:
                        linked_tests.append(test)

        linked_tests = list(set(linked_tests))
        if linked_tests:
            traced.append({"spec": spec, "tests": linked_tests})
            matched_tests.update(linked_tests)
        else:
            uncovered.append(spec)

    orphan_tests = [t for t in tests if t not in matched_tests]

    total = len(specs)
    covered = len(traced)
    coverage_pct = (covered / total * 100) if total else 0

    return {
        "status": "completed",
        "specs_total": total,
        "specs_covered": covered,
        "coverage_percent": round(coverage_pct, 1),
        "traced": traced,
        "uncovered": uncovered,
        "orphan_tests": orphan_tests[:20],
    }


def format_report(report: dict) -> str:
    """Format traceability report."""
    lines = ["# Requirements Traceability Report", ""]

    if report["status"] in ("no_specs", "no_tests"):
        return lines[0] + "\n\n" + report["message"]

    lines.append("**Coverage:** " + str(report["coverage_percent"]) + "% ("
                 + str(report["specs_covered"]) + "/" + str(report["specs_total"]) + " specs traced)")
    lines.append("")

    if report["uncovered"]:
        lines.append("## Uncovered Specs (no matching tests)")
        for s in report["uncovered"]:
            lines.append("- " + s)
        lines.append("")

    if report["traced"]:
        lines.append("## Traced Specs")
        for item in report["traced"][:20]:
            lines.append("- " + item["spec"] + " → " + ", ".join(item["tests"][:3]))
        lines.append("")

    if report["orphan_tests"]:
        lines.append("## Orphan Tests (no matching spec)")
        for t in report["orphan_tests"][:10]:
            lines.append("- " + t)
        lines.append("")

    return "\n".join(lines)


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Fettle requirements traceability")
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--spec-patterns", default="docs/**/*spec*.md,docs/**/*plan*.md")
    parser.add_argument("--test-root", default="tests/")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cfg = {
        "spec_patterns": args.spec_patterns.split(","),
        "test_roots": [args.test_root],
        "naming_convention": True,
    }

    report = trace_requirements(args.root, cfg)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
