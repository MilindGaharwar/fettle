"""Tests for scripts/trace.py — decision logging."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from trace import log_decision, get_recent_decisions, rotate_trace


def test_log_decision_creates_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    log_decision(hook="PostToolUse", status="pass", tool="ruff", file="test.py")
    trace_path = tmp_path / "fettle" / "trace.jsonl"
    assert trace_path.exists()
    entry = json.loads(trace_path.read_text().strip())
    assert entry["hook"] == "PostToolUse"
    assert entry["status"] == "pass"


def test_get_recent_decisions(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    for i in range(5):
        log_decision(hook="PostToolUse", status=f"status_{i}")
    entries = get_recent_decisions(limit=3)
    assert len(entries) == 3
    assert entries[-1]["status"] == "status_4"


def test_rotate_trace(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    for i in range(100):
        log_decision(hook="test", status=f"entry_{i}")
    rotate_trace(max_entries=20)
    entries = get_recent_decisions(limit=100)
    assert len(entries) == 20
