"""WP-B — Normalized Advisory Contract tests.

Tests Advisory dataclass, AdvisoryDeduplicator persistence, format_advisories
size cap, and Aggregator max_per_turn enforcement.
"""

import json
import time

from advisory import Advisory, AdvisoryDeduplicator, Severity, format_advisories
from dispatcher_aggregate import Aggregator
from dispatcher_types import CheckResult


def _make_advisory(rule_id: str = "TEST001", summary: str = "Test finding") -> Advisory:
    return Advisory(
        rule_id=rule_id,
        category="test",
        severity=Severity.WARNING,
        confidence=0.9,
        summary=summary,
        recommended_action="Fix it",
        provenance="test@0.1",
    )


def test_advisory_auto_generates_dedupe_key():
    a = _make_advisory()
    assert a.dedupe_key
    assert len(a.dedupe_key) == 16


def test_advisory_same_inputs_same_dedupe_key():
    a1 = _make_advisory(rule_id="X", summary="hello")
    a2 = _make_advisory(rule_id="X", summary="hello")
    assert a1.dedupe_key == a2.dedupe_key


def test_advisory_different_inputs_different_key():
    a1 = _make_advisory(rule_id="X", summary="hello")
    a2 = _make_advisory(rule_id="Y", summary="world")
    assert a1.dedupe_key != a2.dedupe_key


class TestDeduplicator:
    def test_first_emit_allowed(self, tmp_path):
        dedup = AdvisoryDeduplicator(tmp_path, "sess1", cooldown_s=300)
        a = _make_advisory()
        assert dedup.should_emit(a) is True

    def test_within_cooldown_suppressed(self, tmp_path):
        dedup = AdvisoryDeduplicator(tmp_path, "sess1", cooldown_s=300)
        a = _make_advisory()
        dedup.record(a)
        assert dedup.should_emit(a) is False

    def test_after_cooldown_emitted(self, tmp_path):
        dedup = AdvisoryDeduplicator(tmp_path, "sess1", cooldown_s=0.01)
        a = _make_advisory()
        dedup.record(a)
        time.sleep(0.02)
        assert dedup.should_emit(a) is True

    def test_persistence_across_instances(self, tmp_path):
        a = _make_advisory()
        d1 = AdvisoryDeduplicator(tmp_path, "sess1", cooldown_s=300)
        d1.record(a)

        d2 = AdvisoryDeduplicator(tmp_path, "sess1", cooldown_s=300)
        assert d2.should_emit(a) is False

    def test_corrupt_state_fails_open(self, tmp_path):
        state_dir = tmp_path / "sess1"
        state_dir.mkdir()
        (state_dir / "advisory_state.json").write_text("NOT JSON{{{")

        dedup = AdvisoryDeduplicator(tmp_path, "sess1", cooldown_s=300)
        a = _make_advisory()
        assert dedup.should_emit(a) is True

    def test_prune_removes_expired_entries(self, tmp_path):
        dedup = AdvisoryDeduplicator(tmp_path, "sess1", cooldown_s=0.01, window_s=0.02)
        a = _make_advisory()
        dedup.record(a)
        time.sleep(0.03)
        dedup.record(_make_advisory(rule_id="OTHER"))
        state = json.loads((tmp_path / "sess1" / "advisory_state.json").read_text())
        assert a.dedupe_key not in state


class TestFormatAdvisories:
    def test_basic_rendering(self):
        advisories = [_make_advisory(summary="Something wrong")]
        result = format_advisories(advisories)
        assert "TEST001" in result
        assert "Something wrong" in result
        assert "Fix it" in result

    def test_respects_byte_cap(self):
        advisories = [_make_advisory(summary=f"Finding {i}" * 20) for i in range(10)]
        result = format_advisories(advisories, max_total_bytes=200)
        assert "suppressed by size cap" in result
        assert len(result.encode("utf-8")) < 400

    def test_includes_discipline_id(self):
        a = Advisory(
            rule_id="LEAN",
            category="lean",
            severity=Severity.INFO,
            confidence=0.8,
            summary="Over-engineered",
            recommended_action="Simplify",
            discipline_id="discipline-coding",
        )
        result = format_advisories([a])
        assert "discipline-coding" in result


class TestAggregatorCap:
    def test_max_per_turn_caps_advisories(self):
        agg = Aggregator(
            total_budget_ms=400,
            hook_event_name="PostToolUse",
            max_advisories_per_turn=2,
        )
        for i in range(5):
            agg.add_result(
                f"check_{i}",
                CheckResult.advisory(f"Advisory {i}", hook_specific_output={
                    "additionalContext": f"Advisory {i}",
                }),
                10,
            )
        assert len(agg.advisories) == 2
        assert agg._advisories_suppressed == 3

    def test_suppression_summary_in_output(self):
        agg = Aggregator(
            total_budget_ms=400,
            hook_event_name="PostToolUse",
            max_advisories_per_turn=1,
        )
        for i in range(3):
            agg.add_result(
                f"check_{i}",
                CheckResult.advisory(f"Advisory {i}", hook_specific_output={
                    "additionalContext": f"Advisory {i}",
                }),
                10,
            )
        output, code = agg.finish()
        context = output["hookSpecificOutput"].get("additionalContext", "")
        assert "2 more advisory" in context
        assert code == 0

    def test_byte_cap_in_finish(self):
        agg = Aggregator(
            total_budget_ms=400,
            hook_event_name="PostToolUse",
            max_advisories_per_turn=100,
            max_advisory_bytes=50,
        )
        agg.add_result(
            "big_check",
            CheckResult.advisory("x" * 100, hook_specific_output={
                "additionalContext": "x" * 100,
            }),
            10,
        )
        agg.add_result(
            "small_check",
            CheckResult.advisory("y" * 10, hook_specific_output={
                "additionalContext": "y" * 10,
            }),
            10,
        )
        output, _ = agg.finish()
        context = output["hookSpecificOutput"].get("additionalContext", "")
        assert "suppressed" in context
