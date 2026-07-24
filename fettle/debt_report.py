"""WP-X1 — Technical Debt Dashboard.

Extends /fettle:report with debt quantification: TODO count,
suppression debt, complexity trend, lean markers, and A-E rating.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


_TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
_NOQA_RE = re.compile(r"#\s*noqa\b|//\s*eslint-disable|/\*\s*@ts-ignore")
_FETTLE_IGNORE_RE = re.compile(r"fettle:ignore")

_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".gif", ".pdf", ".zip", ".gz", ".woff", ".pyc", ".so",
    ".exe", ".bin", ".ico", ".woff2", ".ttf", ".eot", ".bz2", ".xz",
}


def _scan_markers(root: str) -> dict:
    """Count TODO/FIXME and suppression markers across source files."""
    todo_count = 0
    suppression_count = 0
    files_scanned = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (
            "__pycache__", ".venv", "venv", "node_modules", ".git", "dist", "build",
        )]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in _BINARY_EXTENSIONS:
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    content = f.read(262144)
            except OSError:
                continue
            files_scanned += 1
            todo_count += len(_TODO_RE.findall(content))
            suppression_count += len(_NOQA_RE.findall(content))
            suppression_count += len(_FETTLE_IGNORE_RE.findall(content))

    return {
        "todo_count": todo_count,
        "suppression_count": suppression_count,
        "files_scanned": files_scanned,
    }


def _complexity_trend(root: str) -> str:
    """Check complexity trend from ratchet data."""
    ratchet_path = Path(root) / ".fettle" / "ratchet.json"
    if not ratchet_path.is_file():
        return "unknown"
    try:
        data = json.loads(ratchet_path.read_text())
        history = data.get("history", [])
        if len(history) < 2:
            return "unknown"
        recent = [h.get("avg_complexity", 0) for h in history[-5:]]
        if all(recent[i] <= recent[i + 1] for i in range(len(recent) - 1)):
            return "rising"
        if all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1)):
            return "falling"
        return "stable"
    except (json.JSONDecodeError, OSError, KeyError):
        return "unknown"


def _lean_markers(root: str) -> list[dict]:
    """Find lean:upgrade-when markers that may be actionable."""
    markers: list[dict] = []
    marker_re = re.compile(r"fettle:lean:\s*(.+)")
    try:
        result = subprocess.run(
            ["grep", "-rn", "fettle:lean:", root,
             "--include=*.py", "--include=*.ts", "--include=*.js"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines()[:20]:
            m = marker_re.search(line)
            if m:
                markers.append({"location": line.split(":")[0], "content": m.group(1)[:100]})
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return markers


def _compute_rating(todo_count: int, suppression_count: int, files_scanned: int) -> str:
    """SQALE-inspired A-E rating based on debt density."""
    if files_scanned == 0:
        return "A"
    debt_items = todo_count + suppression_count
    density = debt_items / files_scanned
    if density <= 0.02:
        return "A"
    if density <= 0.05:
        return "B"
    if density <= 0.10:
        return "C"
    if density <= 0.20:
        return "D"
    return "E"


def generate_debt_report(root: str) -> dict:
    """Generate full debt report."""
    markers_data = _scan_markers(root)
    trend = _complexity_trend(root)
    lean = _lean_markers(root)
    rating = _compute_rating(
        markers_data["todo_count"],
        markers_data["suppression_count"],
        markers_data["files_scanned"],
    )

    return {
        "todo_count": markers_data["todo_count"],
        "suppression_count": markers_data["suppression_count"],
        "files_scanned": markers_data["files_scanned"],
        "complexity_trend": trend,
        "lean_markers": lean,
        "rating": rating,
    }


def format_debt_report(report: dict) -> str:
    """Format as human-readable output."""
    lines = [
        "## Technical Debt Report",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        "| Rating | **" + report["rating"] + "** |",
        "| TODO/FIXME/HACK | " + str(report["todo_count"]) + " |",
        "| Suppressions (noqa/ignore) | " + str(report["suppression_count"]) + " |",
        "| Files scanned | " + str(report["files_scanned"]) + " |",
        "| Complexity trend | " + report["complexity_trend"] + " |",
        "| Lean markers | " + str(len(report["lean_markers"])) + " |",
        "",
    ]

    if report["lean_markers"]:
        lines.append("### Intentional Debt (fettle:lean markers)")
        for m in report["lean_markers"][:10]:
            lines.append("- " + m["content"])
        lines.append("")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fettle debt report")
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    report = generate_debt_report(args.root)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_debt_report(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
