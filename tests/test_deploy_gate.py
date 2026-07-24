"""WP-X2 — Deployment Safety Gate tests."""

from pathlib import Path
from unittest.mock import patch

from dispatcher_types import Decision, HookContext, HookInput


def _make_ctx(command: str, cwd: str, session_id: str = "test-deploy",
              enabled: bool = True, mode: str = "advisory"):
    config = {
        "gates": {
            "deploy_safety": {
                "enabled": enabled,
                "mode": mode,
                "require_tests": True,
                "require_changelog": False,
                "require_health_endpoint": True,
                "check_debug_flags": True,
            },
        },
    }
    hook_input = HookInput(
        hook_event_name="PreToolUse",
        tool_name="Bash",
        tool_input={"command": command},
        cwd=Path(cwd),
        session_id=session_id,
        raw={},
    )
    return HookContext(
        input=hook_input,
        config=config,
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=999999.0,
    )


def test_disabled_allows(tmp_path):
    from deploy_gate import run_check
    ctx = _make_ctx("kubectl apply -f deploy.yaml", str(tmp_path), enabled=False)
    assert run_check(ctx).decision == Decision.ALLOW


def test_non_deploy_allows(tmp_path):
    from deploy_gate import run_check
    ctx = _make_ctx("npm install", str(tmp_path))
    assert run_check(ctx).decision == Decision.ALLOW


def test_deploy_without_tests_advisory(tmp_path):
    from deploy_gate import run_check
    (tmp_path / "app.py").write_text('@app.get("/health")\ndef health(): pass\n')
    ctx = _make_ctx("kubectl apply -f deploy.yaml", str(tmp_path))
    with patch("deploy_gate._check_tests_ran", return_value=False):
        result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "No tests ran" in result.message


def test_deploy_with_all_preconditions_allows(tmp_path):
    from deploy_gate import run_check
    (tmp_path / "app.py").write_text('@app.get("/health")\ndef health(): pass\n')
    ctx = _make_ctx("fly deploy", str(tmp_path))
    with (patch("deploy_gate._check_tests_ran", return_value=True),
          patch("deploy_gate._check_debug_flags", return_value=[])):
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_deploy_with_debug_flags_advisory(tmp_path):
    from deploy_gate import run_check
    (tmp_path / "app.py").write_text('DEBUG = True\n@app.get("/health")\ndef h(): pass\n')
    ctx = _make_ctx("terraform apply", str(tmp_path))
    with patch("deploy_gate._check_tests_ran", return_value=True):
        result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "Debug flags" in result.message


def test_deploy_no_health_endpoint_advisory(tmp_path):
    from deploy_gate import run_check
    (tmp_path / "app.py").write_text("def main(): pass\n")
    ctx = _make_ctx("cdk deploy", str(tmp_path))
    with patch("deploy_gate._check_tests_ran", return_value=True):
        result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "health endpoint" in result.message.lower()


def test_enforce_mode_blocks(tmp_path):
    from deploy_gate import run_check
    (tmp_path / "app.py").write_text("x = 1\n")
    ctx = _make_ctx("kubectl apply -f x.yaml", str(tmp_path), mode="enforce")
    with patch("deploy_gate._check_tests_ran", return_value=False):
        result = run_check(ctx)
    assert result.decision == Decision.BLOCK
