"""Tests for scripts/report.py"""

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.report import compute_effectiveness, compute_override_inventory, identify_candidates


def test_compute_effectiveness_no_data(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    result = compute_effectiveness(days=30)
    assert "error" in result


def test_compute_effectiveness_with_data(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    from fettle.trace import log_decision
    log_decision(hook="PostToolUse", status="pass", tool="ruff", file="app.py")
    log_decision(hook="PostToolUse", status="violation", tool="ruff", file="bad.py",
                 findings=[{"code": "F401", "message": "unused", "file": "bad.py"}])
    log_decision(hook="PostToolUse", status="tool_error", tool="semgrep")

    result = compute_effectiveness(days=30)
    assert result["total_decisions"] == 3
    assert result["pass_rate_pct"] > 0
    assert result["violation_rate_pct"] > 0
    assert result["tool_error_rate_pct"] > 0


def test_identify_candidates(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    result = identify_candidates(days=30)
    assert "retire_candidates" in result
    assert "recalibrate_candidates" in result
    assert "active_rules" in result


def test_effectiveness_includes_recent_evidence_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    from fettle.trace import build_evidence, log_decision
    evidence = build_evidence("command", exit_code=1, duration_ms=20)
    log_decision(hook="verify", status="tool_error", evidence=[evidence])

    result = compute_effectiveness(days=30)
    assert result["evidence_ids"] == [evidence["evidence_id"]]


def test_effectiveness_counts_overrides_separately_from_pass(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    from fettle.trace import log_decision
    log_decision(hook="quality", status="pass")
    log_decision(hook="quality", status="overridden", overrides=[{
        "override_id": "ov-123", "actor": "maintainer", "reason": "accepted risk",
        "expiry": "2026-09-01T00:00:00Z", "check_id": "quality", "scope": "src/app.py",
    }])

    result = compute_effectiveness(days=30)

    assert result["pass_rate_pct"] == 50.0
    assert result["overridden_count"] == 1
    assert result["recent_overrides"][0]["override_id"] == "ov-123"


def test_override_inventory_exposes_active_expired_and_invalid(tmp_path):
    ledger = tmp_path / ".fettle" / "overrides.json"
    ledger.parent.mkdir()
    ledger.write_text('{"schema_version":"1","overrides":[{"actor":"anonymous"}]}')

    result = compute_override_inventory(tmp_path)

    assert result["invalid_count"] == 1
    assert result["active_count"] == 0
