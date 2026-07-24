"""Tests for the semantic specification audit gate."""

import subprocess

from fettle.config import DEFAULTS
from fettle.spec_audit import REQUIRED_SECTIONS, scan_spec_audit


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _project(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PRODUCT-STRATEGY.md").write_text("# Strategy\n")
    _git(tmp_path, "add", "docs/PRODUCT-STRATEGY.md")
    _git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base")


def _config(enabled=True):
    config = {**DEFAULTS, "gates": {**DEFAULTS["gates"]}}
    config["gates"]["spec_audit"] = {
        "enabled": enabled,
        "audit_path": "docs/SPEC-AUDIT.md",
        "spec_patterns": ["docs/*strategy*.md", "docs/**/*strategy*.md"],
    }
    return config


def _change_spec(tmp_path):
    (tmp_path / "docs" / "PRODUCT-STRATEGY.md").write_text("# Revised strategy\n")


def _write_audit(tmp_path, sections=REQUIRED_SECTIONS):
    content = "# Audit\n\n" + "\n".join(f"## {section}\nChecked.\n" for section in sections)
    (tmp_path / "docs" / "SPEC-AUDIT.md").write_text(content)


def test_disabled_gate_skips_changed_spec(tmp_path):
    _project(tmp_path)
    _change_spec(tmp_path)
    assert scan_spec_audit(str(tmp_path), _config(enabled=False)) == []


def test_explicit_empty_change_set_does_not_scan_worktree(tmp_path):
    _project(tmp_path)
    _change_spec(tmp_path)
    assert scan_spec_audit(str(tmp_path), _config(), changed_paths=set()) == []


def test_missing_audit_blocks_changed_spec(tmp_path):
    _project(tmp_path)
    _change_spec(tmp_path)
    findings = scan_spec_audit(str(tmp_path), _config())
    assert findings[0]["rule"] == "SPEC_AUDIT"
    assert "without a current" in findings[0]["message"]


def test_unchanged_audit_is_stale(tmp_path):
    _project(tmp_path)
    _write_audit(tmp_path)
    _git(tmp_path, "add", "docs/SPEC-AUDIT.md")
    _git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "audit")
    _change_spec(tmp_path)
    assert "without a current" in scan_spec_audit(str(tmp_path), _config())[0]["message"]


def test_incomplete_audit_lists_missing_sections(tmp_path):
    _project(tmp_path)
    _change_spec(tmp_path)
    _write_audit(tmp_path, REQUIRED_SECTIONS[:-1])
    finding = scan_spec_audit(str(tmp_path), _config())[0]
    assert "Residual Risks" in finding["message"]


def test_complete_changed_audit_passes(tmp_path):
    _project(tmp_path)
    _change_spec(tmp_path)
    _write_audit(tmp_path)
    assert scan_spec_audit(str(tmp_path), _config()) == []
