"""Tests for scripts/trace.py — decision logging."""

import json
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.overrides import OverrideRecord
from fettle.trace import build_evidence, log_decision, get_recent_decisions, rotate_trace


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


def test_log_decision_rotates_when_over_threshold(tmp_path, monkeypatch):
    """WP-6: production writes trigger rotation — no unbounded growth."""
    import fettle.trace as trace_mod
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(trace_mod, "_ROTATE_BYTES", 2048)
    trace_path = tmp_path / "fettle" / "trace.jsonl"
    trace_path.parent.mkdir(parents=True)
    with open(trace_path, "w") as f:
        for i in range(6000):
            f.write(json.dumps({"schema": 2, "status": f"s{i}"}) + "\n")
    log_decision(hook="test", status="newest")
    lines = trace_path.read_text().strip().splitlines()
    assert len(lines) == 5000  # rotated down from 6001
    assert json.loads(lines[-1])["status"] == "newest"


def test_get_recent_decisions_is_bounded_tail_read(tmp_path, monkeypatch):
    """WP-6: reading recents must not scan the whole file."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    trace_path = tmp_path / "fettle" / "trace.jsonl"
    trace_path.parent.mkdir(parents=True)
    with open(trace_path, "w") as f:
        for i in range(5000):
            f.write(json.dumps({"schema": 2, "status": f"s{i}"}) + "\n")
    entries = get_recent_decisions(limit=3)
    assert [e["status"] for e in entries] == ["s4997", "s4998", "s4999"]


def test_lineage_fields_empty_when_solo(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.delenv("FETTLE_PARENT_SESSION", raising=False)
    monkeypatch.delenv("FETTLE_POLICY_CAPSULE", raising=False)
    log_decision(hook="t", status="pass")
    entry = get_recent_decisions(limit=1)[0]
    assert entry["parent_session_id"] == ""
    assert entry["capsule_digest"] == ""


def test_lineage_fields_from_spawn_env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("FETTLE_PARENT_SESSION", "parent-1")
    monkeypatch.setenv("FETTLE_POLICY_CAPSULE", "/x/capsules/abcd1234abcd1234.json")
    log_decision(hook="t", status="pass", session_id="child-1")
    entry = get_recent_decisions(limit=1)[0]
    assert entry["parent_session_id"] == "parent-1"
    assert entry["capsule_digest"] == "abcd1234abcd1234"


def test_structured_evidence_is_bounded_and_redacted(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    evidence = build_evidence(
        "command",
        command=["tool", "--token=secret-value", "x" * 5000],
        exit_code=1,
        output="password=hunter2\n" + "failure\n" * 1000,
    )
    log_decision(
        hook="verify", status="tool_error", evidence=[evidence],
        findings=[{"message": "token=secret-value", "raw_tool_output": "source" * 1000}],
    )

    entry = get_recent_decisions(limit=1)[0]
    serialized = json.dumps(entry)
    assert evidence["evidence_id"].startswith("ev-")
    assert "hunter2" not in serialized
    assert "secret-value" not in serialized
    assert len(serialized) < 12000
    assert entry["evidence"][0]["kind"] == "command"


def test_evidence_reference_keeps_existing_id(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    log_decision(
        hook="dispatcher", status="violation",
        evidence=[{"evidence_id": "ev-existing123", "kind": "command"}],
    )

    entry = get_recent_decisions(limit=1)[0]
    assert entry["evidence"] == [{"evidence_id": "ev-existing123", "kind": "command"}]


def test_override_is_recorded_distinctly_and_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    record = OverrideRecord.create(
        actor="maintainer", reason="accepted risk", timestamp="2026-08-07T10:00:00Z",
        expiry="2026-08-08T10:00:00Z", check_id="gate", scope="src/app.py",
        revision="a" * 40, policy_digest="b" * 64, evidence_id="ev-prior", surface="ci",
    )

    log_decision(hook="gate", status="overridden", overrides=[record.to_dict()])

    entry = get_recent_decisions(limit=1)[0]
    assert entry["status"] == "overridden"
    assert entry["overrides"][0]["override_id"] == record.override_id
    assert entry["overrides"][0]["reason"] == "accepted risk"
