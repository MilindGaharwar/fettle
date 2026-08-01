"""JSON schema contract tests for dispatcher output.

Validates that all dispatcher output conforms to the hook output schema
shared by Claude Code, Codex, and Gemini CLI. Prevents regressions like
the hookEventName bug (commit ea9f2d4) from shipping again.

Stage 13 wire rules (Codex parses output with deny_unknown_fields):
- PreToolUse/PostToolUse: {"hookSpecificOutput": {...}} (+ top-level
  decision/reason on block); permissionDecision on PreToolUse ONLY.
- Stop/SubagentStop: NO hookSpecificOutput — blocks are top-level
  {decision, reason}; advisories ride systemMessage; else {}.

Exit code semantics:
  0 = allow/advisory (tool proceeds)
  2 = block (tool denied)
"""

import json
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
DISPATCHER = os.path.join(SCRIPTS_DIR, "dispatcher.py")

VALID_HOOK_EVENTS = {"PreToolUse", "PostToolUse", "Stop", "SubagentStop"}
VALID_PERMISSION_DECISIONS = {"allow", "deny", "ask", "defer"}

sys.path.insert(0, SCRIPTS_DIR)


def _run_dispatcher(payload: dict) -> tuple[dict, int]:
    """Run dispatcher.py with payload, return (parsed_output, exit_code)."""
    proc = subprocess.run(
        [sys.executable, DISPATCHER],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
        env={**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")},
    )
    output = json.loads(proc.stdout.strip()) if proc.stdout.strip() else {}
    return output, proc.returncode


def _validate_schema(output: dict, expected_event: str, expect_block: bool = False):
    """Validate output against the shared hook output schema."""
    if expected_event in ("Stop", "SubagentStop"):
        _validate_stop_schema(output, expect_block)
        return
    assert "hookSpecificOutput" in output, "Missing hookSpecificOutput key"
    hso = output["hookSpecificOutput"]

    assert "hookEventName" in hso, (
        f"hookSpecificOutput missing required 'hookEventName' field. Got: {hso}"
    )
    assert hso["hookEventName"] in VALID_HOOK_EVENTS, (
        f"hookEventName '{hso['hookEventName']}' not in {VALID_HOOK_EVENTS}"
    )
    assert hso["hookEventName"] == expected_event, (
        f"hookEventName mismatch: expected '{expected_event}', got '{hso['hookEventName']}'"
    )

    if "permissionDecision" in hso:
        assert expected_event == "PreToolUse", (
            f"permissionDecision is only legal on PreToolUse output, not {expected_event}"
        )
        assert hso["permissionDecision"] in VALID_PERMISSION_DECISIONS, (
            f"Invalid permissionDecision: '{hso['permissionDecision']}'"
        )

    if "permissionDecisionReason" in hso:
        assert isinstance(hso["permissionDecisionReason"], str)

    if "additionalContext" in hso:
        assert isinstance(hso["additionalContext"], str)
        assert len(hso["additionalContext"]) > 0, "additionalContext present but empty"

    if "updatedInput" in hso:
        assert isinstance(hso["updatedInput"], dict)

    # No unexpected top-level keys
    allowed_top_keys = {"hookSpecificOutput", "decision", "reason"}
    for key in output:
        assert key in allowed_top_keys, f"Unexpected top-level key: '{key}'"

    # No unexpected hookSpecificOutput keys
    allowed_hso_keys = {
        "hookEventName", "permissionDecision", "permissionDecisionReason",
        "additionalContext", "updatedInput",
    }
    for key in hso:
        assert key in allowed_hso_keys, f"Unexpected hookSpecificOutput key: '{key}'"


def _validate_stop_schema(output: dict, expect_block: bool = False):
    """Stop/SubagentStop output: no hookSpecificOutput (Codex strict parser)."""
    assert "hookSpecificOutput" not in output, (
        f"Stop output must not carry hookSpecificOutput (Codex rejects it). Got: {output}"
    )
    allowed = {"decision", "reason", "systemMessage"}
    for key in output:
        assert key in allowed, f"Unexpected Stop output key: '{key}'"
    if expect_block:
        assert output.get("decision") == "block"
        assert isinstance(output.get("reason"), str) and output["reason"]


class TestPreToolUseSchema:
    def test_allow_bash(self):
        output, rc = _run_dispatcher({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "cwd": "/tmp",
            "session_id": "schema-test-pre-bash",
        })
        assert rc == 0
        _validate_schema(output, "PreToolUse")

    def test_allow_edit(self):
        output, rc = _run_dispatcher({
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": "/tmp/nonexistent.py", "old_string": "x", "new_string": "y"},
            "cwd": "/tmp",
            "session_id": "schema-test-pre-edit",
        })
        assert rc == 0
        _validate_schema(output, "PreToolUse")

    def test_allow_write(self):
        output, rc = _run_dispatcher({
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/new_file.py", "content": "x = 1"},
            "cwd": "/tmp",
            "session_id": "schema-test-pre-write",
        })
        assert rc == 0
        _validate_schema(output, "PreToolUse")

    def test_advisory_destructive_command(self):
        output, rc = _run_dispatcher({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /important/data"},
            "cwd": "/tmp",
            "session_id": "schema-test-destructive",
        })
        assert rc == 0
        _validate_schema(output, "PreToolUse")
        if "additionalContext" in output["hookSpecificOutput"]:
            assert "destructive" in output["hookSpecificOutput"]["additionalContext"].lower() or \
                   "rm" in output["hookSpecificOutput"]["additionalContext"].lower()


class TestPostToolUseSchema:
    def test_allow_edit_py(self):
        output, rc = _run_dispatcher({
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": "/tmp/nonexistent.py"},
            "cwd": "/tmp",
            "session_id": "schema-test-post-edit",
        })
        assert rc == 0
        _validate_schema(output, "PostToolUse")

    def test_allow_bash(self):
        output, rc = _run_dispatcher({
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/ -q"},
            "cwd": "/tmp",
            "session_id": "schema-test-post-bash",
        })
        assert rc == 0
        _validate_schema(output, "PostToolUse")

    def test_allow_read(self):
        output, rc = _run_dispatcher({
            "hook_event_name": "PostToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/anything.txt"},
            "cwd": "/tmp",
            "session_id": "schema-test-post-read",
        })
        assert rc == 0
        _validate_schema(output, "PostToolUse")


class TestStopSchema:
    def test_stop_empty_session(self):
        output, rc = _run_dispatcher({
            "hook_event_name": "Stop",
            "tool_name": None,
            "tool_input": {},
            "cwd": "/tmp",
            "session_id": "schema-test-stop",
        })
        assert rc == 0
        _validate_schema(output, "Stop")

    def test_stop_with_session_id(self):
        output, rc = _run_dispatcher({
            "hook_event_name": "Stop",
            "tool_name": None,
            "tool_input": {},
            "cwd": "/tmp",
            "session_id": "schema-stop-session-123",
        })
        assert rc == 0
        _validate_schema(output, "Stop")


class TestSubagentStopSchema:
    def test_subagent_stop(self):
        output, rc = _run_dispatcher({
            "hook_event_name": "SubagentStop",
            "tool_name": None,
            "tool_input": {},
            "cwd": "/tmp",
            "session_id": "schema-test-subagent-stop",
        })
        assert rc == 0
        _validate_schema(output, "SubagentStop")


class TestBlockSchema:
    """Test that block outputs also conform to schema."""

    def test_block_output_via_aggregator(self):
        from fettle.dispatcher_aggregate import Aggregator
        from fettle.dispatcher_types import CheckResult

        agg = Aggregator(total_budget_ms=400, hook_event_name="PreToolUse")
        agg.add_result("test_gate", CheckResult.block("Blocked", hook_specific_output={
            "permissionDecision": "deny",
            "permissionDecisionReason": "Test block reason",
        }), 10)
        output, exit_code = agg.finish()

        assert exit_code == 2
        _validate_schema(output, "PreToolUse", expect_block=True)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_block_with_advisory_context(self):
        from fettle.dispatcher_aggregate import Aggregator
        from fettle.dispatcher_types import CheckResult

        agg = Aggregator(total_budget_ms=400, hook_event_name="PreToolUse")
        agg.add_result("advisor", CheckResult.advisory("Warning first", hook_specific_output={
            "additionalContext": "Warning context",
        }), 5)
        agg.add_result("blocker", CheckResult.block("Blocked", hook_specific_output={
            "permissionDecision": "deny",
            "permissionDecisionReason": "Block reason",
        }), 5)
        output, exit_code = agg.finish()

        assert exit_code == 2
        _validate_schema(output, "PreToolUse", expect_block=True)
        assert "Warning context" in output["hookSpecificOutput"]["additionalContext"]

    def test_block_carries_top_level_decision(self):
        """Blocks always carry the universal decision/reason pair."""
        from fettle.dispatcher_aggregate import Aggregator
        from fettle.dispatcher_types import CheckResult

        agg = Aggregator(total_budget_ms=400, hook_event_name="PreToolUse")
        agg.add_result("gate", CheckResult.block("Nope"), 5)
        output, exit_code = agg.finish()
        assert exit_code == 2
        assert output["decision"] == "block"
        assert output["reason"] == "Nope"

    def test_posttooluse_block_has_no_permission_decision(self):
        """permissionDecision is PreToolUse-only — Codex rejects it elsewhere."""
        from fettle.dispatcher_aggregate import Aggregator
        from fettle.dispatcher_types import CheckResult

        agg = Aggregator(total_budget_ms=400, hook_event_name="PostToolUse")
        agg.add_result("gate", CheckResult.block("Bad edit", hook_specific_output={
            "permissionDecision": "deny",
            "permissionDecisionReason": "Bad edit",
        }), 5)
        output, exit_code = agg.finish()
        assert exit_code == 2
        _validate_schema(output, "PostToolUse", expect_block=True)
        assert output["decision"] == "block"
        assert "permissionDecision" not in output["hookSpecificOutput"]

    def test_stop_block_is_top_level_only(self):
        """Codex's Stop output schema has no hookSpecificOutput field at all."""
        from fettle.dispatcher_aggregate import Aggregator
        from fettle.dispatcher_types import CheckResult

        agg = Aggregator(total_budget_ms=400, hook_event_name="Stop")
        agg.add_result("advisor", CheckResult.advisory("heads-up", hook_specific_output={
            "additionalContext": "heads-up",
        }), 5)
        agg.add_result("verify", CheckResult.block("Tests never ran"), 5)
        output, exit_code = agg.finish()
        assert exit_code == 2
        _validate_schema(output, "Stop", expect_block=True)
        assert "Tests never ran" in output["reason"]
        assert "heads-up" in output["reason"]  # advisory folded into reason

    def test_stop_advisory_rides_system_message(self):
        from fettle.dispatcher_aggregate import Aggregator
        from fettle.dispatcher_types import CheckResult

        agg = Aggregator(total_budget_ms=400, hook_event_name="Stop")
        agg.add_result("advisor", CheckResult.advisory("wrap up notes", hook_specific_output={
            "additionalContext": "wrap up notes",
        }), 5)
        output, exit_code = agg.finish()
        assert exit_code == 0
        _validate_schema(output, "Stop")
        assert output == {"systemMessage": "wrap up notes"}

    def test_stop_clean_is_empty_object(self):
        from fettle.dispatcher_aggregate import Aggregator

        agg = Aggregator(total_budget_ms=400, hook_event_name="Stop")
        output, exit_code = agg.finish()
        assert exit_code == 0
        assert output == {}


class TestEdgeCases:
    def test_empty_payload(self):
        """Empty stdin should produce valid schema (fail-open)."""
        output, rc = _run_dispatcher({})
        assert rc == 0
        hso = output.get("hookSpecificOutput", {})
        # May or may not have hookEventName (no event provided)
        # But must not have invalid keys
        allowed = {"hookEventName", "permissionDecision", "permissionDecisionReason",
                   "additionalContext", "updatedInput"}
        for key in hso:
            assert key in allowed, f"Unexpected key in empty-payload output: {key}"

    def test_unknown_tool(self):
        """Unknown tool should produce valid schema."""
        output, rc = _run_dispatcher({
            "hook_event_name": "PostToolUse",
            "tool_name": "UnknownTool",
            "tool_input": {},
            "cwd": "/tmp",
            "session_id": "schema-test-unknown",
        })
        assert rc == 0
        _validate_schema(output, "PostToolUse")

    def test_disabled_dispatcher(self):
        """FETTLE_DISABLE_DISPATCHER=1 should still produce parseable JSON."""
        proc = subprocess.run(
            [sys.executable, DISPATCHER],
            input="{}",
            capture_output=True,
            text=True,
            timeout=5,
            env={**os.environ, "FETTLE_DISABLE_DISPATCHER": "1"},
        )
        assert proc.returncode == 0
        output = json.loads(proc.stdout.strip())
        assert output == {}  # eventless no-op is the universal empty object

    def test_malformed_json_input(self):
        """Malformed input should produce valid JSON output (fail-open)."""
        proc = subprocess.run(
            [sys.executable, DISPATCHER],
            input="NOT JSON {{{",
            capture_output=True,
            text=True,
            timeout=5,
            env={**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")},
        )
        assert proc.returncode == 0
        output = json.loads(proc.stdout.strip())
        assert output == {}  # eventless no-op is the universal empty object
