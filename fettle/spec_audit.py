"""Require semantic audit evidence when strategy or specification files change."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from fettle.changeset import get_changed_files


REQUIRED_SECTIONS = (
    "Requirements Matrix",
    "Fixture And Live Separation",
    "Adversarial Pass Review",
    "Non-Goals And Failure Paths",
    "Residual Risks",
)


def _matches(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/").lower()
    return any(fnmatch.fnmatch(normalized, pattern.lower()) for pattern in patterns)


def scan_spec_audit(root: str, config: dict, changed_paths: set[str] | None = None) -> list[dict]:
    gate = config["gates"].get("spec_audit", {})
    if not gate.get("enabled", False):
        return []

    changed = (
        changed_paths
        if changed_paths is not None
        else {item.path.replace("\\", "/") for item in get_changed_files(root)}
    )
    audit_path = str(gate.get("audit_path", "docs/spec-audit.md")).replace("\\", "/")
    patterns = gate.get("spec_patterns", [
        "docs/*spec*.md",
        "docs/**/*spec*.md",
        "docs/*strategy*.md",
        "docs/**/*strategy*.md",
        "docs/*architecture*.md",
        "docs/**/*architecture*.md",
        "docs/*plan*.md",
        "docs/**/*plan*.md",
    ])
    scoped = sorted(path for path in changed if path != audit_path and _matches(path, patterns))
    if not scoped:
        return []

    finding = {
        "file": audit_path,
        "line": 1,
        "rule": "SPEC_AUDIT",
        "severity": "ERROR",
        "tool": "spec_audit",
    }
    if audit_path not in changed:
        return [{
            **finding,
            "message": "Specification files changed without a current semantic audit record.",
        }]

    audit_file = Path(root) / audit_path
    try:
        content = audit_file.read_text(encoding="utf-8")
    except OSError:
        return [{**finding, "message": "Semantic audit record is changed but cannot be read."}]

    missing = [section for section in REQUIRED_SECTIONS if f"## {section}" not in content]
    if missing:
        return [{
            **finding,
            "message": f"Semantic audit record is incomplete; missing sections: {', '.join(missing)}.",
        }]
    return []
