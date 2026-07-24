"""Tests for scripts/report.py"""

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.report import compute_effectiveness, identify_candidates


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
