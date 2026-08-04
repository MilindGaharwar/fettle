"""Tests for fettle.dispatcher_aggregate — output aggregation logic."""

from fettle.dispatcher_aggregate import Aggregator
from fettle.dispatcher_types import CheckResult
from fettle.finding import CheckFinding, EvidenceReference, FindingSeverity


class TestAggregatorAllow:
    def test_no_results_produces_empty_output(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PreToolUse")
        output, code = agg.finish()
        assert code == 0
        assert "hookSpecificOutput" in output
        assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"

    def test_allow_results_pass_through(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PostToolUse")
        agg.add_result("check_a", CheckResult.allow(), 5)
        agg.add_result("check_b", CheckResult.allow(), 3)
        output, code = agg.finish()
        assert code == 0
        assert not agg.has_block


class TestAggregatorBlock:
    def test_first_block_wins(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PreToolUse")
        agg.add_result("a", CheckResult.block("reason A"), 5)
        agg.add_result("b", CheckResult.block("reason B"), 5)
        assert agg.first_block_name == "a"
        output, code = agg.finish()
        assert code == 2
        assert "reason A" in output["reason"]

    def test_block_includes_explain_pointer(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PreToolUse")
        agg.add_result("x", CheckResult.block("some issue"), 5)
        output, _ = agg.finish()
        assert "fettle explain" in output["reason"]

    def test_block_on_pretooluse_has_permission_fields(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PreToolUse")
        agg.add_result("x", CheckResult.block("denied"), 5)
        output, code = agg.finish()
        hso = output["hookSpecificOutput"]
        assert hso["permissionDecision"] == "deny"
        assert "denied" in hso["permissionDecisionReason"]

    def test_block_on_posttooluse_no_permission_fields(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PostToolUse")
        agg.add_result("x", CheckResult.block("denied", hook_specific_output={
            "permissionDecision": "deny",
            "permissionDecisionReason": "r",
        }), 5)
        output, code = agg.finish()
        hso = output["hookSpecificOutput"]
        assert "permissionDecision" not in hso

    def test_block_on_stop_no_hook_specific_output(self):
        agg = Aggregator(total_budget_ms=600, hook_event_name="Stop")
        agg.add_result("x", CheckResult.block("tests failed"), 5)
        output, code = agg.finish()
        assert code == 2
        assert "hookSpecificOutput" not in output
        assert "tests failed" in output["reason"]

    def test_empty_block_message_fallback(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PreToolUse")
        agg.add_result("x", CheckResult.block(""), 5)
        output, _ = agg.finish()
        assert "Blocked by Fettle" in output["reason"]


class TestAggregatorAdvisory:
    def test_advisory_via_additional_context(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PostToolUse")
        agg.add_result("a", CheckResult.advisory("msg", hook_specific_output={
            "additionalContext": "context text",
        }), 5)
        output, code = agg.finish()
        assert code == 0
        assert "context text" in output["hookSpecificOutput"]["additionalContext"]

    def test_advisory_via_message_fallback(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PostToolUse")
        agg.add_result("a", CheckResult.advisory("direct message"), 5)
        output, code = agg.finish()
        assert code == 0
        assert "direct message" in output["hookSpecificOutput"]["additionalContext"]

    def test_advisory_cap_limits(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PostToolUse",
                         max_advisories_per_turn=2)
        agg.add_result("a", CheckResult.advisory("one"), 5)
        agg.add_result("b", CheckResult.advisory("two"), 5)
        agg.add_result("c", CheckResult.advisory("three"), 5)
        output, _ = agg.finish()
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "one" in ctx
        assert "two" in ctx
        assert "suppressed" in ctx

    def test_advisory_byte_cap(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PostToolUse",
                         max_advisory_bytes=50)
        agg.add_result("a", CheckResult.advisory("A" * 40), 5)
        agg.add_result("b", CheckResult.advisory("B" * 40), 5)
        output, _ = agg.finish()
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "suppressed" in ctx

    def test_stop_advisory_uses_system_message(self):
        agg = Aggregator(total_budget_ms=600, hook_event_name="Stop")
        agg.add_result("a", CheckResult.advisory("reminder"), 5)
        output, code = agg.finish()
        assert code == 0
        assert "reminder" in output.get("systemMessage", "")
        assert "hookSpecificOutput" not in output

    def test_structured_transport_does_not_change_host_wire(self):
        finding = CheckFinding(
            checker="ruff",
            severity=FindingSeverity.ERROR,
            file="app.py",
            line=1,
            message="unused import",
        )
        plain = Aggregator(total_budget_ms=400, hook_event_name="PostToolUse")
        plain.add_result("ruff", CheckResult.advisory("fix import"), 5)
        enriched = Aggregator(total_budget_ms=400, hook_event_name="PostToolUse")
        enriched.add_result(
            "ruff",
            CheckResult.advisory(
                "fix import",
                findings=[finding],
                evidence=[EvidenceReference(evidence_id="ev-1", kind="command")],
            ),
            5,
        )
        assert enriched.finish() == plain.finish()


class TestAggregatorErrors:
    def test_check_error_is_fail_open(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PreToolUse")
        agg.record_check_error("broken_check", "NoneType error")
        output, code = agg.finish()
        assert code == 0
        assert len(agg.errors) == 1

    def test_budget_exhausted_recorded(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PreToolUse")
        agg.record_budget_exhausted("slow_check")
        assert agg.budget_exhausted_before == "slow_check"

    def test_system_advisory_respects_cap(self):
        agg = Aggregator(total_budget_ms=400, hook_event_name="PostToolUse",
                         max_advisories_per_turn=1)
        agg.add_result("a", CheckResult.advisory("first"), 5)
        agg.add_system_advisory("system msg")
        output, _ = agg.finish()
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "first" in ctx
        assert "suppressed" in ctx
