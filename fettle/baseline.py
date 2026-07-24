#!/usr/bin/env python3
"""Fettle baseline — snapshot existing violations for incremental enforcement.

Allows gradual adoption: only NEW violations are reported, existing ones
are grandfathered until explicitly fixed.

Usage:
    python3 baseline.py create [--root PATH]
    python3 baseline.py update [--root PATH]
    python3 baseline.py check [--root PATH]  # returns only new violations
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.paths import find_repo_root


BASELINE_FILENAME = ".fettle-baseline.json"


def _get_baseline_path(repo_root: Path) -> Path:
    return repo_root / BASELINE_FILENAME


def _fingerprint(finding: dict) -> str:
    """Create a stable fingerprint for a finding (for dedup across runs)."""
    return f"{finding.get('tool', '')}:{finding.get('file', '')}:{finding.get('line', '')}:{finding.get('code', '')}"


def load_baseline(repo_root: Path) -> dict | None:
    """Load existing baseline, or None if not found."""
    path = _get_baseline_path(repo_root)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def create_baseline(findings: list[dict], repo_root: Path) -> dict:
    """Create a new baseline from current findings."""
    baseline = {
        "version": 1,
        "created": datetime.now().isoformat(),
        "fettle_version": "0.3.0",
        "findings_count": len(findings),
        "fingerprints": [_fingerprint(f) for f in findings],
        "findings": findings,
    }
    path = _get_baseline_path(repo_root)
    path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    return baseline


def filter_new_violations(findings: list[dict], baseline: dict) -> list[dict]:
    """Return only findings NOT in the baseline (new violations)."""
    if not baseline:
        return findings
    baseline_fps = set(baseline.get("fingerprints", []))
    return [f for f in findings if _fingerprint(f) not in baseline_fps]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fettle baseline management")
    parser.add_argument("action", choices=["create", "update", "check", "info"])
    parser.add_argument("--root", help="Repository root (auto-detected if not specified)")
    args = parser.parse_args()

    repo_root = Path(args.root) if args.root else find_repo_root()
    if not repo_root:
        print("Error: not inside a repository.", file=sys.stderr)
        sys.exit(1)

    if args.action == "info":
        baseline = load_baseline(repo_root)
        if baseline:
            print(f"Baseline: {_get_baseline_path(repo_root)}")
            print(f"  Created: {baseline.get('created', '?')}")
            print(f"  Findings: {baseline.get('findings_count', 0)}")
        else:
            print("No baseline found. Run `fettle baseline create` first.")

    elif args.action in ("create", "update"):
        from fettle.config import load_config
        config = load_config(str(repo_root))

        # Run scan to get current findings
        try:
            from fettle.quality_scan import scan_project
            results = scan_project(str(repo_root), config, json_output=True)
            findings = results.get("findings", [])
        except (ImportError, TypeError):
            findings = []

        baseline = create_baseline(findings, repo_root)
        action = "Created" if args.action == "create" else "Updated"
        print(f"✓ {action} baseline: {baseline['findings_count']} finding(s)")
        print(f"  Path: {_get_baseline_path(repo_root)}")

    elif args.action == "check":
        baseline = load_baseline(repo_root)
        if not baseline:
            print("No baseline found. All findings will be reported.")
            sys.exit(0)
        print(f"Baseline loaded: {baseline.get('findings_count', 0)} grandfathered finding(s)")


if __name__ == "__main__":
    main()
