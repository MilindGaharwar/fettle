"""WP-R — PR Review Orchestration.

Aggregates existing Fettle checks into a PR-ready markdown report.
Does NOT re-implement review logic — orchestrates quality_scan,
coverage, complexity, and git diff into a structured checklist.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
_ENV = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")}


def _git_diff_stat(root: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", root, "diff", "--stat", "HEAD~1"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _git_diff_files(root: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "-C", root, "diff", "--name-only", "HEAD~1"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip().splitlines() if result.returncode == 0 else []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _run_quality_scan(root: str) -> dict:
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "quality_scan.py"), "--root", root, "--json"],
            capture_output=True, text=True, timeout=120, env=_ENV,
        )
        if result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return {"findings": [], "summary": {}}


def _get_coverage(root: str) -> str:
    cov_path = Path(root) / "coverage.json"
    if not cov_path.is_file():
        return "No coverage.json found"
    try:
        data = json.loads(cov_path.read_text())
        totals = data.get("totals", {})
        pct = totals.get("percent_covered", 0)
        return str(round(pct, 1)) + "% overall"
    except (json.JSONDecodeError, OSError):
        return "coverage.json unreadable"


def _detect_breaking_changes(root: str, files: list[str]) -> list[str]:
    """Detect potential breaking changes from diff."""
    breaking: list[str] = []
    for f in files:
        if not f.endswith(".py"):
            continue
        if "__init__.py" in f:
            try:
                result = subprocess.run(
                    ["git", "-C", root, "diff", "HEAD~1", "--", f],
                    capture_output=True, text=True, timeout=5,
                )
                for line in result.stdout.splitlines():
                    if (line.startswith("-") and not line.startswith("---")
                            and ("import" in line or "def " in line or "class " in line)):
                        breaking.append(f + ": removed export: " + line[1:].strip())
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
    return breaking[:10]


def generate_pr_review(root: str) -> str:
    """Generate a PR review report from existing Fettle checks."""
    files = _git_diff_files(root)
    if not files:
        return "# PR Review\n\nNo changes detected (no diff from HEAD~1)."

    diff_stat = _git_diff_stat(root)
    quality = _run_quality_scan(root)
    coverage = _get_coverage(root)
    breaking = _detect_breaking_changes(root, files)
    summary = quality.get("summary", {})

    lines = [
        "# PR Review",
        "",
        "## Changes",
        "```",
        diff_stat or "(no diff stat available)",
        "```",
        "",
        "## Quality Scan",
        "- Errors: " + str(summary.get("errors", 0)),
        "- Warnings: " + str(summary.get("warnings", 0)),
        "- Info: " + str(summary.get("info", 0)),
        "",
        "## Coverage",
        "- " + coverage,
        "",
    ]

    if breaking:
        lines.append("## Breaking Changes")
        for b in breaking:
            lines.append("- " + b)
        lines.append("")

    lines.extend([
        "## Checklist",
        "- [ ] Quality scan: 0 errors",
        "- [ ] Tests pass",
        "- [ ] No breaking changes (or documented)",
        "- [ ] Commit messages explain WHY",
        "- [ ] Manual verification done",
        "",
    ])

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fettle PR review")
    parser.add_argument("--root", default=".", help="Project root")
    args = parser.parse_args()
    print(generate_pr_review(args.root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
