"""Tests for WP-121 — loaded-rules health telemetry.

Covers:
- Recording load events to the global trace
- Detecting zero-rule packs (ERROR)
- Detecting packs that dropped to zero (ERROR)
- Detecting expected-but-missing packs (WARNING)
- Doctor check discovering packs from rules/
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle import health_telemetry
# ──────────────────────────────────────────────────────────────────────
# Recording load events
# ──────────────────────────────────────────────────────────────────────


def test_record_creates_trace_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    health_telemetry.record_loaded_rules(
        pack_name="llm-antipatterns",
        rules_loaded=12,
        rules_skipped=2,
        config_source="rules/llm-antipatterns.yml",
    )
    trace_path = tmp_path / "fettle" / "trace.jsonl"
    assert trace_path.exists()
    entry = json.loads(trace_path.read_text().strip())
    assert entry["hook"] == "health_telemetry"
    assert entry["event"] == "rules_loaded"
    assert entry["pack"] == "llm-antipatterns"
    assert entry["rules_loaded"] == 12
    assert entry["rules_skipped"] == 2
    assert entry["config_source"] == "rules/llm-antipatterns.yml"
    assert "timestamp" in entry
    assert "ts" in entry


def test_record_uses_session_id_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("FETTLE_SESSION_ID", "sess-abc123")
    health_telemetry.record_loaded_rules("test-pack", 5, 0, "rules/test.yml")
    trace_path = tmp_path / "fettle" / "trace.jsonl"
    entry = json.loads(trace_path.read_text().strip())
    assert entry["session_id"] == "sess-abc123"


def test_record_multiple_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    for i in range(3):
        health_telemetry.record_loaded_rules(f"pack-{i}", i * 5, i, f"rules/pack-{i}.yml")
    trace_path = tmp_path / "fettle" / "trace.jsonl"
    lines = trace_path.read_text().strip().splitlines()
    assert len(lines) == 3


# ──────────────────────────────────────────────────────────────────────
# Detecting zero-rule packs
# ──────────────────────────────────────────────────────────────────────


def test_zero_rules_in_latest_run_is_error(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    # Record a pack with zero rules loaded
    health_telemetry.record_loaded_rules("llm-antipatterns", 0, 5, "rules/llm-antipatterns.yml")

    issues = health_telemetry.check_health(["llm-antipatterns"])
    assert len(issues) == 1
    assert issues[0]["level"] == "error"
    assert issues[0]["pack"] == "llm-antipatterns"
    assert "0 rules" in issues[0]["message"]


def test_nonzero_rules_is_healthy(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    health_telemetry.record_loaded_rules("llm-antipatterns", 12, 0, "rules/llm-antipatterns.yml")

    issues = health_telemetry.check_health(["llm-antipatterns"])
    assert issues == []


# ──────────────────────────────────────────────────────────────────────
# Detecting dropped packs (zero after previously non-zero)
# ──────────────────────────────────────────────────────────────────────


def test_drop_to_zero_is_error(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    # First run: healthy
    health_telemetry.record_loaded_rules("ts-antipatterns", 8, 1, "rules/ts-antipatterns.yml")
    # Second run: dropped to zero
    health_telemetry.record_loaded_rules("ts-antipatterns", 0, 0, "rules/ts-antipatterns.yml")

    issues = health_telemetry.check_health(["ts-antipatterns"])
    assert len(issues) == 1
    assert issues[0]["level"] == "error"
    assert issues[0]["pack"] == "ts-antipatterns"


# ──────────────────────────────────────────────────────────────────────
# Detecting expected-but-missing packs
# ──────────────────────────────────────────────────────────────────────


def test_never_seen_pack_is_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    # Create trace dir but no entries for the expected pack
    (tmp_path / "fettle").mkdir(parents=True, exist_ok=True)
    (tmp_path / "fettle" / "trace.jsonl").write_text("")

    issues = health_telemetry.check_health(["go-antipatterns"])
    assert len(issues) == 1
    assert issues[0]["level"] == "warning"
    assert issues[0]["pack"] == "go-antipatterns"
    assert "never seen" in issues[0]["message"]


def test_mixed_packs_health(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    # One healthy, one zero, one missing
    health_telemetry.record_loaded_rules("llm-antipatterns", 12, 0, "rules/llm-antipatterns.yml")
    health_telemetry.record_loaded_rules("ts-antipatterns", 0, 8, "rules/ts-antipatterns.yml")

    issues = health_telemetry.check_health(["llm-antipatterns", "ts-antipatterns", "go-antipatterns"])
    levels = {i["pack"]: i["level"] for i in issues}
    assert "llm-antipatterns" not in levels  # healthy
    assert levels["ts-antipatterns"] == "error"
    assert levels["go-antipatterns"] == "warning"


# ──────────────────────────────────────────────────────────────────────
# get_pack_history
# ──────────────────────────────────────────────────────────────────────


def test_get_pack_history_returns_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    for i in range(5):
        health_telemetry.record_loaded_rules("llm-antipatterns", 10 + i, 0, "rules/llm-antipatterns.yml")
    # Also record a different pack (should not appear)
    health_telemetry.record_loaded_rules("ts-antipatterns", 7, 1, "rules/ts-antipatterns.yml")

    history = health_telemetry.get_pack_history("llm-antipatterns")
    assert len(history) == 5
    assert all(h["pack"] == "llm-antipatterns" for h in history)
    assert history[-1]["rules_loaded"] == 14


def test_get_pack_history_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    for i in range(10):
        health_telemetry.record_loaded_rules("go-antipatterns", i, 0, "rules/go-antipatterns.yml")

    history = health_telemetry.get_pack_history("go-antipatterns", limit=3)
    assert len(history) == 3
    # Should be the last 3
    assert history[0]["rules_loaded"] == 7


def test_get_pack_history_empty_for_unknown(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    (tmp_path / "fettle").mkdir(parents=True, exist_ok=True)
    (tmp_path / "fettle" / "trace.jsonl").write_text("")

    history = health_telemetry.get_pack_history("nonexistent-pack")
    assert history == []


# ──────────────────────────────────────────────────────────────────────
# Doctor integration
# ──────────────────────────────────────────────────────────────────────


def test_doctor_discovers_packs_from_rules_dir(monkeypatch):
    """doctor_check should discover packs from rules/*.yml in plugin root."""
    # The real rules/ dir should have at least the known packs
    packs = health_telemetry._discover_expected_packs()
    assert "llm-antipatterns" in packs
    assert "ts-antipatterns" in packs
    assert "go-antipatterns" in packs


def test_doctor_check_passes_when_all_healthy(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    # Record healthy entries for all packs
    for pack in health_telemetry._discover_expected_packs():
        health_telemetry.record_loaded_rules(pack, 10, 0, f"rules/{pack}.yml")

    passed, messages = health_telemetry.doctor_check()
    assert passed is True
    assert any("healthy" in m for m in messages)


def test_doctor_check_fails_on_zero_rules(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    # One pack healthy, one zero
    packs = health_telemetry._discover_expected_packs()
    for pack in packs:
        count = 0 if pack == "llm-antipatterns" else 10
        health_telemetry.record_loaded_rules(pack, count, 0, f"rules/{pack}.yml")

    passed, messages = health_telemetry.doctor_check()
    assert passed is False
    assert any("ERROR" in m and "llm-antipatterns" in m for m in messages)


def test_doctor_check_warns_on_no_trace_data(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    # Empty trace — all packs will be "never seen"
    (tmp_path / "fettle").mkdir(parents=True, exist_ok=True)
    (tmp_path / "fettle" / "trace.jsonl").write_text("")

    passed, messages = health_telemetry.doctor_check()
    # Warnings only (no errors), so still passes
    assert passed is True
    assert any("WARN" in m for m in messages)


def test_doctor_check_no_rules_dir(tmp_path, monkeypatch):
    """If no rule packs exist, doctor check passes with info message."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(health_telemetry, "RULES_DIR", tmp_path / "nonexistent")

    passed, messages = health_telemetry.doctor_check()
    assert passed is True
    assert any("nothing to check" in m for m in messages)
