"""Tests for scripts/ratchet.py — ratchet workflow (WP-119)."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.ratchet import (
    aggregate_evidence,
    demote_rule,
    load_ratchet,
    promote_rule,
    ratchet_status,
    save_ratchet,
)


# --- Fixtures ---


def _write_trace(state_dir, entries):
    """Write trace entries to trace.jsonl under the given state dir."""
    trace_dir = state_dir / "fettle"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = trace_dir / "trace.jsonl"
    with open(trace_path, "a") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _write_fp_stamps(state_dir, stamps):
    """Write FP stamps to false-positives.jsonl under the given state dir."""
    fp_dir = state_dir / "fettle"
    fp_dir.mkdir(parents=True, exist_ok=True)
    fp_path = fp_dir / "false-positives.jsonl"
    with open(fp_path, "a") as f:
        for stamp in stamps:
            f.write(json.dumps(stamp) + "\n")


# --- load_ratchet ---


def test_load_ratchet_missing_file(tmp_path):
    """Returns empty schema when ratchet.json doesn't exist."""
    data = load_ratchet(tmp_path)
    assert data == {"schema_version": "1", "rules": {}}


def test_load_ratchet_empty_dir(tmp_path):
    """Returns empty schema when .fettle dir exists but no ratchet.json."""
    (tmp_path / ".fettle").mkdir()
    data = load_ratchet(tmp_path)
    assert data == {"schema_version": "1", "rules": {}}


def test_load_ratchet_valid_data(tmp_path):
    """Loads valid ratchet data from disk."""
    fettle_dir = tmp_path / ".fettle"
    fettle_dir.mkdir()
    ratchet_data = {
        "schema_version": "1",
        "rules": {
            "F401": {
                "mode": "enforce",
                "promoted_at": "2026-07-01T10:00:00",
                "demoted_at": None,
                "evidence": {"total_fires": 10, "true_positives": 9, "false_positives": 1},
            }
        },
    }
    (fettle_dir / "ratchet.json").write_text(json.dumps(ratchet_data))
    data = load_ratchet(tmp_path)
    assert data["rules"]["F401"]["mode"] == "enforce"


def test_load_ratchet_corrupt_json(tmp_path):
    """Returns empty schema when JSON is malformed."""
    fettle_dir = tmp_path / ".fettle"
    fettle_dir.mkdir()
    (fettle_dir / "ratchet.json").write_text("{not valid json")
    data = load_ratchet(tmp_path)
    assert data == {"schema_version": "1", "rules": {}}


# --- save_ratchet ---


def test_save_ratchet_creates_dir(tmp_path):
    """Creates .fettle dir if missing."""
    data = {"schema_version": "1", "rules": {"X": {"mode": "advisory"}}}
    save_ratchet(tmp_path, data)
    ratchet_path = tmp_path / ".fettle" / "ratchet.json"
    assert ratchet_path.exists()
    loaded = json.loads(ratchet_path.read_text())
    assert loaded["rules"]["X"]["mode"] == "advisory"


def test_save_ratchet_atomic(tmp_path):
    """File is written atomically (no partial writes visible)."""
    data = {"schema_version": "1", "rules": {"R1": {"mode": "enforce"}}}
    save_ratchet(tmp_path, data)
    # Verify no tmp files left behind
    fettle_dir = tmp_path / ".fettle"
    files = list(fettle_dir.iterdir())
    assert len(files) == 1
    assert files[0].name == "ratchet.json"


# --- aggregate_evidence ---


def test_aggregate_evidence_empty(tmp_path, monkeypatch):
    """No trace, no FP -> empty evidence."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    evidence = aggregate_evidence(tmp_path)
    assert evidence == {}


def test_aggregate_evidence_from_trace(tmp_path, monkeypatch):
    """Counts fires from relevant trace entries."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    entries = [
        {
            "timestamp": "2026-07-10T10:00:00",
            "hook": "post_edit",
            "status": "violation",
            "findings": [{"code": "F401", "message": "unused import"}],
        },
        {
            "timestamp": "2026-07-10T10:01:00",
            "hook": "quality_gate",
            "status": "advisory",
            "findings": [
                {"code": "F401", "message": "unused import"},
                {"code": "E501", "message": "line too long"},
            ],
        },
        # This entry should be ignored (wrong hook)
        {
            "timestamp": "2026-07-10T10:02:00",
            "hook": "fp_stamp",
            "status": "stamped",
            "findings": [{"code": "F401", "message": "stamped"}],
        },
        # This entry should be ignored (wrong status)
        {
            "timestamp": "2026-07-10T10:03:00",
            "hook": "post_edit",
            "status": "pass",
            "findings": [{"code": "F401", "message": "clean"}],
        },
    ]
    _write_trace(tmp_path, entries)

    evidence = aggregate_evidence(tmp_path)
    assert "F401" in evidence
    assert evidence["F401"].total_fires == 2
    assert evidence["F401"].true_positives == 2
    assert evidence["F401"].false_positives == 0
    assert evidence["F401"].last_fire == "2026-07-10T10:01:00"
    assert "E501" in evidence
    assert evidence["E501"].total_fires == 1


def test_aggregate_evidence_with_fp_stamps(tmp_path, monkeypatch):
    """FP stamps reduce true positives."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    entries = [
        {
            "timestamp": "2026-07-10T10:00:00",
            "hook": "post_edit",
            "status": "violation",
            "findings": [{"code": "BLE001", "message": "blind except"}],
        },
        {
            "timestamp": "2026-07-10T10:01:00",
            "hook": "quality_gate",
            "status": "violation",
            "findings": [{"code": "BLE001", "message": "blind except"}],
        },
        {
            "timestamp": "2026-07-10T10:02:00",
            "hook": "post_edit",
            "status": "violation",
            "findings": [{"code": "BLE001", "message": "blind except"}],
        },
    ]
    _write_trace(tmp_path, entries)

    fp_stamps = [
        {"timestamp": "2026-07-11T09:00:00", "rule": "BLE001", "file": "x.py", "line": 10, "reason": "intentional"},
    ]
    _write_fp_stamps(tmp_path, fp_stamps)

    evidence = aggregate_evidence(tmp_path)
    assert evidence["BLE001"].total_fires == 3
    assert evidence["BLE001"].false_positives == 1
    assert evidence["BLE001"].true_positives == 2
    assert evidence["BLE001"].last_fp_stamp == "2026-07-11T09:00:00"


def test_aggregate_evidence_fp_rate(tmp_path, monkeypatch):
    """FP rate is computed correctly."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    entries = [
        {
            "timestamp": f"2026-07-10T10:0{i}:00",
            "hook": "post_edit",
            "status": "violation",
            "findings": [{"code": "SEC001", "message": "issue"}],
        }
        for i in range(5)
    ]
    _write_trace(tmp_path, entries)

    fp_stamps = [
        {"timestamp": "2026-07-11T09:00:00", "rule": "SEC001", "file": f"f{i}.py", "line": 1, "reason": "fp"}
        for i in range(2)
    ]
    _write_fp_stamps(tmp_path, fp_stamps)

    evidence = aggregate_evidence(tmp_path)
    assert evidence["SEC001"].total_fires == 5
    assert evidence["SEC001"].false_positives == 2
    assert evidence["SEC001"].fp_rate == pytest.approx(0.4)


# --- promote_rule ---


def test_promote_rule_sufficient_evidence(tmp_path, monkeypatch):
    """Promotes when fires >= min and FP rate <= max."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    # Write 6 fires, 0 FP
    entries = [
        {
            "timestamp": f"2026-07-10T10:0{i}:00",
            "hook": "post_edit",
            "status": "violation",
            "findings": [{"code": "F401", "message": "unused"}],
        }
        for i in range(6)
    ]
    _write_trace(tmp_path, entries)

    result = promote_rule(tmp_path, "F401")
    assert "Promoted" in result
    assert "enforce" in result

    # Verify persisted
    data = load_ratchet(tmp_path)
    assert data["rules"]["F401"]["mode"] == "enforce"
    assert data["rules"]["F401"]["promoted_at"] is not None


def test_promote_rule_too_few_fires(tmp_path, monkeypatch):
    """Refuses when fires < min_fires."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    entries = [
        {
            "timestamp": "2026-07-10T10:00:00",
            "hook": "post_edit",
            "status": "violation",
            "findings": [{"code": "F401", "message": "unused"}],
        }
    ]
    _write_trace(tmp_path, entries)

    result = promote_rule(tmp_path, "F401", min_fires=5)
    assert "Refused" in result
    assert "1 fires" in result


def test_promote_rule_high_fp_rate(tmp_path, monkeypatch):
    """Refuses when FP rate exceeds max_fp_rate."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    # 5 fires
    entries = [
        {
            "timestamp": f"2026-07-10T10:0{i}:00",
            "hook": "post_edit",
            "status": "violation",
            "findings": [{"code": "NOISY001", "message": "noisy"}],
        }
        for i in range(5)
    ]
    _write_trace(tmp_path, entries)

    # 3 FP stamps -> 60% FP rate
    fp_stamps = [
        {"timestamp": "2026-07-11T09:00:00", "rule": "NOISY001", "file": f"f{i}.py", "line": 1, "reason": "fp"}
        for i in range(3)
    ]
    _write_fp_stamps(tmp_path, fp_stamps)

    result = promote_rule(tmp_path, "NOISY001", max_fp_rate=0.2)
    assert "Refused" in result
    assert "FP rate" in result


def test_promote_rule_no_evidence(tmp_path, monkeypatch):
    """Refuses when no evidence exists for the rule."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    result = promote_rule(tmp_path, "UNKNOWN_RULE")
    assert "Refused" in result
    assert "no evidence" in result


def test_promote_rule_already_enforced(tmp_path, monkeypatch):
    """Reports that rule is already enforced."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    # Write enough fires
    entries = [
        {
            "timestamp": f"2026-07-10T10:0{i}:00",
            "hook": "post_edit",
            "status": "violation",
            "findings": [{"code": "F401", "message": "unused"}],
        }
        for i in range(6)
    ]
    _write_trace(tmp_path, entries)

    # Promote first
    promote_rule(tmp_path, "F401")
    # Try to promote again
    result = promote_rule(tmp_path, "F401")
    assert "already in enforce mode" in result


# --- demote_rule ---


def test_demote_rule_with_reason(tmp_path, monkeypatch):
    """Demotes an enforced rule when reason is given."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    # Set up as enforced first
    entries = [
        {
            "timestamp": f"2026-07-10T10:0{i}:00",
            "hook": "post_edit",
            "status": "violation",
            "findings": [{"code": "F401", "message": "unused"}],
        }
        for i in range(6)
    ]
    _write_trace(tmp_path, entries)
    promote_rule(tmp_path, "F401")

    result = demote_rule(tmp_path, "F401", "Too many false positives in new codebase")
    assert "Demoted" in result
    assert "advisory" in result

    data = load_ratchet(tmp_path)
    assert data["rules"]["F401"]["mode"] == "advisory"
    assert data["rules"]["F401"]["demoted_at"] is not None
    assert data["rules"]["F401"]["demotion_reason"] == "Too many false positives in new codebase"


def test_demote_rule_no_reason(tmp_path, monkeypatch):
    """Refuses demotion without a reason."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    result = demote_rule(tmp_path, "F401", "")
    assert "Refused" in result
    assert "reason" in result


def test_demote_rule_already_advisory(tmp_path, monkeypatch):
    """Reports that rule is already in advisory mode."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    # Pre-populate ratchet with advisory rule
    data = {
        "schema_version": "1",
        "rules": {"F401": {"mode": "advisory", "promoted_at": None, "demoted_at": None, "evidence": {}}},
    }
    save_ratchet(tmp_path, data)

    result = demote_rule(tmp_path, "F401", "want to demote")
    assert "already in advisory mode" in result


# --- ratchet_status ---


def test_ratchet_status_empty(tmp_path, monkeypatch):
    """Returns empty list when no rules tracked."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    rows = ratchet_status(tmp_path)
    assert rows == []


def test_ratchet_status_format(tmp_path, monkeypatch):
    """Returns properly formatted status rows."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    # Write trace data
    entries = [
        {
            "timestamp": f"2026-07-10T10:0{i}:00",
            "hook": "post_edit",
            "status": "violation",
            "findings": [
                {"code": "F401", "message": "unused"},
                {"code": "E501", "message": "too long"},
            ],
        }
        for i in range(6)
    ]
    _write_trace(tmp_path, entries)

    # One FP stamp for F401
    _write_fp_stamps(tmp_path, [
        {"timestamp": "2026-07-11T09:00:00", "rule": "F401", "file": "x.py", "line": 1, "reason": "ok"},
    ])

    rows = ratchet_status(tmp_path)
    assert len(rows) == 2

    # Find F401 row
    f401_row = next(r for r in rows if r["rule"] == "F401")
    assert f401_row["mode"] == "advisory"
    assert f401_row["total_fires"] == 6
    assert f401_row["false_positives"] == 1
    assert f401_row["true_positives"] == 5
    assert f401_row["fp_rate"] == pytest.approx(1 / 6)
    assert f401_row["eligible_promote"] is True  # 6 fires, FP rate ~17% < 20%
    assert f401_row["eligible_demote"] is False

    # E501 row
    e501_row = next(r for r in rows if r["rule"] == "E501")
    assert e501_row["total_fires"] == 6
    assert e501_row["eligible_promote"] is True


def test_ratchet_status_includes_ratchet_file_rules(tmp_path, monkeypatch):
    """Status includes rules from ratchet.json even without fresh trace evidence."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    data = {
        "schema_version": "1",
        "rules": {
            "OLD_RULE": {
                "mode": "enforce",
                "promoted_at": "2026-01-01T00:00:00",
                "demoted_at": None,
                "evidence": {"total_fires": 20, "true_positives": 18, "false_positives": 2},
            }
        },
    }
    save_ratchet(tmp_path, data)

    rows = ratchet_status(tmp_path)
    assert len(rows) == 1
    assert rows[0]["rule"] == "OLD_RULE"
    assert rows[0]["mode"] == "enforce"
    assert rows[0]["eligible_demote"] is True
