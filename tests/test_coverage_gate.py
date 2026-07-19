"""WP-F — Diff Coverage Gate tests."""

import json
import time
from pathlib import Path
from unittest.mock import patch

from dispatcher_types import Decision, HookContext, HookInput


def _make_ctx(cwd: Path, session_id: str = "test-cov", mode: str = "advisory",
              threshold: int = 80, enabled: bool = True):
    config = {
        "gates": {
            "coverage": {
                "enabled": enabled,
                "threshold": threshold,
                "mode": mode,
                "scope": "changed_lines",
                "max_staleness_seconds": 0,
            },
        },
    }
    hook_input = HookInput(
        hook_event_name="Stop",
        tool_name=None,
        tool_input={},
        cwd=cwd,
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


def _write_coverage_json(cwd: Path, files_data: dict):
    """Write a coverage.json in coverage.py format."""
    data = {"files": files_data}
    (cwd / "coverage.json").write_text(json.dumps(data))


def _write_edits_jsonl(state_dir: Path, session_id: str, files: list[str]):
    """Write edits.jsonl with file entries."""
    sess_dir = state_dir / session_id
    sess_dir.mkdir(parents=True, exist_ok=True)
    with open(sess_dir / "edits.jsonl", "w") as f:
        for fpath in files:
            f.write(json.dumps({"file": fpath}) + "\n")


def test_no_coverage_json_allows(tmp_path):
    """No coverage.json → silent allow."""
    from coverage_gate import run_check

    ctx = _make_ctx(tmp_path)
    with patch("config.state_dir", return_value=tmp_path / "state" / "test-cov"):
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_above_threshold_allows(tmp_path):
    """Coverage above threshold → allow."""
    from coverage_gate import run_check

    src = tmp_path / "app.py"
    src.write_text("line1\nline2\nline3\nline4\nline5\n")

    _write_coverage_json(tmp_path, {
        str(src): {"executed_lines": [1, 2, 3, 4, 5]},
    })

    state_dir = tmp_path / "state"
    _write_edits_jsonl(state_dir, "test-cov", [str(src)])

    # Touch coverage.json to be newer than edits
    (tmp_path / "coverage.json").touch()
    time.sleep(0.01)

    ctx = _make_ctx(tmp_path, threshold=80)
    with (patch("config.state_dir", return_value=state_dir / "test-cov"),
          patch("coverage_gate._get_changed_lines", return_value={1, 2, 3, 4, 5})):
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_below_threshold_advisory(tmp_path):
    """Coverage below threshold in advisory mode → advisory."""
    from coverage_gate import run_check

    src = tmp_path / "app.py"
    src.write_text("a\nb\nc\nd\ne\n")

    # Only 2 of 5 lines covered
    _write_coverage_json(tmp_path, {
        str(src): {"executed_lines": [1, 2]},
    })

    state_dir = tmp_path / "state"
    _write_edits_jsonl(state_dir, "test-cov", [str(src)])
    (tmp_path / "coverage.json").touch()
    time.sleep(0.01)

    ctx = _make_ctx(tmp_path, threshold=80, mode="advisory")
    with (patch("config.state_dir", return_value=state_dir / "test-cov"),
          patch("coverage_gate._get_changed_lines", return_value={1, 2, 3, 4, 5})):
        result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "40%" in result.message


def test_below_threshold_enforce_blocks(tmp_path):
    """Coverage below threshold in enforce mode → block."""
    from coverage_gate import run_check

    src = tmp_path / "app.py"
    src.write_text("a\nb\nc\nd\ne\n")

    _write_coverage_json(tmp_path, {
        str(src): {"executed_lines": [1]},
    })

    state_dir = tmp_path / "state"
    _write_edits_jsonl(state_dir, "test-cov", [str(src)])
    (tmp_path / "coverage.json").touch()
    time.sleep(0.01)

    ctx = _make_ctx(tmp_path, threshold=80, mode="enforce")
    with (patch("config.state_dir", return_value=state_dir / "test-cov"),
          patch("coverage_gate._get_changed_lines", return_value={1, 2, 3, 4, 5})):
        result = run_check(ctx)
    assert result.decision == Decision.BLOCK
    assert "20%" in result.message


def test_stale_coverage_warns(tmp_path):
    """Coverage.json older than edits → staleness advisory."""
    from coverage_gate import run_check

    src = tmp_path / "app.py"
    src.write_text("hello\n")

    _write_coverage_json(tmp_path, {str(src): {"executed_lines": [1]}})

    state_dir = tmp_path / "state"
    _write_edits_jsonl(state_dir, "test-cov", [str(src)])

    # Make edits newer than coverage
    time.sleep(0.05)
    edits_file = state_dir / "test-cov" / "edits.jsonl"
    edits_file.touch()

    ctx = _make_ctx(tmp_path, threshold=80)
    with patch("config.state_dir", return_value=state_dir / "test-cov"):
        result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "stale" in result.message
