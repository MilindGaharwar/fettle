"""WP-I — TDD Phase Enforcement tests."""

from pathlib import Path
from unittest.mock import patch

from dispatcher_types import Decision, HookContext, HookInput


def _make_ctx(file_path: str, event: str = "PreToolUse", cwd: str = "/tmp/proj",
              session_id: str = "test-tdd", config_overrides: dict | None = None):
    config = {
        "gates": {
            "tdd": {
                "enabled": True,
                "mode": "advisory",
                "test_patterns": ["tests/test_*.py", "tests/**/test_*.py"],
                "implementation_roots": ["src/"],
                "exempt_paths": ["docs/**", "**/*.md", "**/*.toml"],
                "accept_preexisting_tests": True,
                "path_mappings": {},
            },
        },
    }
    if config_overrides:
        config["gates"]["tdd"].update(config_overrides)

    hook_input = HookInput(
        hook_event_name=event,
        tool_name="Edit",
        tool_input={"file_path": file_path},
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


def test_test_edit_then_impl_allowed(tmp_path):
    """Edit test first, then impl → impl allowed."""
    from tdd_gate import run_check

    cwd = str(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "tests" / "test_parser.py").write_text("def test_x(): pass")
    (tmp_path / "src" / "parser.py").write_text("def parse(): pass")

    with patch("tdd_gate._get_state_path", return_value=tmp_path / "tdd.jsonl"):
        # Record test edit (PostToolUse)
        ctx = _make_ctx("tests/test_parser.py", event="PostToolUse", cwd=cwd, session_id="s1")
        run_check(ctx)

        # Now impl edit (PreToolUse) should be allowed
        ctx = _make_ctx("src/parser.py", event="PreToolUse", cwd=cwd, session_id="s1")
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_impl_without_test_advisory(tmp_path):
    """Edit impl without prior test → advisory."""
    from tdd_gate import run_check

    cwd = str(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "parser.py").write_text("def parse(): pass")

    with patch("tdd_gate._get_state_path", return_value=tmp_path / "tdd.jsonl"):
        ctx = _make_ctx(
            "src/parser.py", event="PreToolUse", cwd=cwd, session_id="s2",
            config_overrides={"accept_preexisting_tests": False},
        )
        result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "TDD" in result.message
    assert "test_parser" in result.message


def test_preexisting_test_satisfies(tmp_path):
    """With accept_preexisting_tests=true, existing test file satisfies."""
    from tdd_gate import run_check

    cwd = str(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "parser.py").write_text("def parse(): pass")
    (tmp_path / "tests" / "test_parser.py").write_text("def test_x(): pass")

    with patch("tdd_gate._get_state_path", return_value=tmp_path / "tdd.jsonl"):
        ctx = _make_ctx("src/parser.py", event="PreToolUse", cwd=cwd, session_id="s3")
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_exempt_paths_bypass(tmp_path):
    """Exempt paths never trigger TDD checks."""
    from tdd_gate import run_check

    with patch("tdd_gate._get_state_path", return_value=tmp_path / "tdd.jsonl"):
        ctx = _make_ctx("docs/readme.md", event="PreToolUse", cwd=str(tmp_path))
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_disabled_gate_allows(tmp_path):
    """When disabled, always allows."""
    from tdd_gate import run_check

    with patch("tdd_gate._get_state_path", return_value=tmp_path / "tdd.jsonl"):
        ctx = _make_ctx(
            "src/parser.py", event="PreToolUse", cwd=str(tmp_path),
            config_overrides={"enabled": False},
        )
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_test_file_always_allowed(tmp_path):
    """Editing a test file is always allowed at PreToolUse."""
    from tdd_gate import run_check

    with patch("tdd_gate._get_state_path", return_value=tmp_path / "tdd.jsonl"):
        ctx = _make_ctx("tests/test_parser.py", event="PreToolUse", cwd=str(tmp_path))
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW
