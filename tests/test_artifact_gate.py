"""WP-O — Artifact Verification Gate tests."""

from pathlib import Path
from unittest.mock import patch

from dispatcher_types import Decision, HookContext, HookInput


def _make_ctx(command: str, event: str = "PreToolUse", session_id: str = "test-artifact",
              enabled: bool = True, mode: str = "advisory"):
    config = {
        "gates": {"artifact_integrity": {"enabled": enabled, "mode": mode}},
    }
    hook_input = HookInput(
        hook_event_name=event,
        tool_name="Bash",
        tool_input={"command": command},
        cwd=Path("/tmp"),
        session_id=session_id,
        raw={"tool_response": {"exit_code": 0}},
    )
    return HookContext(
        input=hook_input,
        config=config,
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=999999.0,
    )


def test_disabled_allows(tmp_path):
    from artifact_gate import run_check
    ctx = _make_ctx("docker push myimg:v1", enabled=False)
    with patch("artifact_gate._evidence_path", return_value=tmp_path / "ev.jsonl"):
        assert run_check(ctx).decision == Decision.ALLOW


def test_non_publish_command_allows(tmp_path):
    from artifact_gate import run_check
    ctx = _make_ctx("ls -la")
    with patch("artifact_gate._evidence_path", return_value=tmp_path / "ev.jsonl"):
        assert run_check(ctx).decision == Decision.ALLOW


def test_publish_without_evidence_advisory(tmp_path):
    from artifact_gate import run_check
    ctx = _make_ctx("docker push ghcr.io/org/app:v1", session_id="no-ev")
    with patch("artifact_gate._evidence_path", return_value=tmp_path / "ev.jsonl"):
        result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "verification evidence" in result.message


def test_publish_with_evidence_allows(tmp_path):
    from artifact_gate import run_check

    ev_path = tmp_path / "ev.jsonl"
    with patch("artifact_gate._evidence_path", return_value=ev_path):
        # Record verification evidence
        ctx_verify = _make_ctx("cosign sign ghcr.io/org/app:v1", event="PostToolUse", session_id="with-ev")
        run_check(ctx_verify)

        # Now publish should pass
        ctx_push = _make_ctx("docker push ghcr.io/org/app:v1", event="PreToolUse", session_id="with-ev")
        result = run_check(ctx_push)
    assert result.decision == Decision.ALLOW


def test_failed_verification_not_valid_evidence(tmp_path):
    from artifact_gate import run_check

    ev_path = tmp_path / "ev.jsonl"
    with patch("artifact_gate._evidence_path", return_value=ev_path):
        # Record FAILED verification (exit_code=1)
        ctx_verify = _make_ctx("cosign sign ghcr.io/org/app:v1", event="PostToolUse", session_id="fail-ev")
        ctx_verify.input = HookInput(
            hook_event_name="PostToolUse", tool_name="Bash",
            tool_input={"command": "cosign sign ghcr.io/org/app:v1"},
            cwd=Path("/tmp"), session_id="fail-ev",
            raw={"tool_response": {"exit_code": 1}},
        )
        run_check(ctx_verify)

        # Publish should still advisory (failed verification doesn't count)
        ctx_push = _make_ctx("docker push ghcr.io/org/app:v1", event="PreToolUse", session_id="fail-ev")
        result = run_check(ctx_push)
    assert result.decision == Decision.ADVISORY


def test_rebuild_invalidates_evidence(tmp_path):
    from artifact_gate import run_check

    ev_path = tmp_path / "ev.jsonl"
    with patch("artifact_gate._evidence_path", return_value=ev_path):
        # Verify
        ctx_v = _make_ctx("cosign sign ghcr.io/org/app:v1", event="PostToolUse", session_id="rebuild")
        run_check(ctx_v)

        # Rebuild (invalidates)
        ctx_b = _make_ctx("docker build -t ghcr.io/org/app:v1 .", event="PostToolUse", session_id="rebuild")
        run_check(ctx_b)

        # Publish now should advisory (evidence invalidated)
        ctx_p = _make_ctx("docker push ghcr.io/org/app:v1", event="PreToolUse", session_id="rebuild")
        result = run_check(ctx_p)
    assert result.decision == Decision.ADVISORY


def test_enforce_mode_blocks(tmp_path):
    from artifact_gate import run_check
    ctx = _make_ctx("docker push ghcr.io/org/app:v1", session_id="enforce", mode="enforce")
    with patch("artifact_gate._evidence_path", return_value=tmp_path / "ev.jsonl"):
        result = run_check(ctx)
    assert result.decision == Decision.BLOCK
