"""WP-N — Provenance Policy Gate tests."""

import json
from pathlib import Path
from unittest.mock import patch

from dispatcher_types import Decision, HookContext, HookInput


def _make_ctx(file_path: str, cwd: str, mode: str = "marker",
              marker_text: str = "AI-generated", enabled: bool = True):
    config = {
        "gates": {
            "provenance": {
                "enabled": enabled,
                "mode": mode,
                "marker_text": marker_text,
                "exempt_paths": ["**/*.json", "**/*.lock", "**/migrations/**"],
            },
        },
    }
    hook_input = HookInput(
        hook_event_name="PostToolUse",
        tool_name="Write",
        tool_input={"file_path": file_path},
        cwd=Path(cwd),
        session_id="test-provenance",
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
    from provenance_gate import run_check
    src = tmp_path / "new.py"
    src.write_text("x = 1\n")
    ctx = _make_ctx(str(src), str(tmp_path), enabled=False)
    assert run_check(ctx).decision == Decision.ALLOW


def test_mode_none_allows(tmp_path):
    from provenance_gate import run_check
    src = tmp_path / "new.py"
    src.write_text("x = 1\n")
    ctx = _make_ctx(str(src), str(tmp_path), mode="none")
    assert run_check(ctx).decision == Decision.ALLOW


def test_marker_mode_new_file_without_marker_advisory(tmp_path):
    from provenance_gate import run_check
    src = tmp_path / "new_module.py"
    src.write_text("def hello(): pass\n")
    ctx = _make_ctx(str(src), str(tmp_path), mode="marker", marker_text="AI-generated")
    with patch("provenance_gate._is_new_file", return_value=True):
        result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "marker" in result.message.lower()


def test_marker_mode_new_file_with_marker_allows(tmp_path):
    from provenance_gate import run_check
    src = tmp_path / "new_module.py"
    src.write_text("# AI-generated\ndef hello(): pass\n")
    ctx = _make_ctx(str(src), str(tmp_path), mode="marker", marker_text="AI-generated")
    with patch("provenance_gate._is_new_file", return_value=True):
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_marker_mode_existing_file_allows(tmp_path):
    from provenance_gate import run_check
    src = tmp_path / "existing.py"
    src.write_text("x = 1\n")
    ctx = _make_ctx(str(src), str(tmp_path), mode="marker", marker_text="AI-generated")
    with patch("provenance_gate._is_new_file", return_value=False):
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_manifest_mode_records_silently(tmp_path):
    from provenance_gate import run_check
    src = tmp_path / "new_file.py"
    src.write_text("x = 1\n")
    ctx = _make_ctx(str(src), str(tmp_path), mode="manifest")
    with patch("provenance_gate._is_new_file", return_value=True):
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW
    manifest = tmp_path / ".fettle" / "provenance.jsonl"
    assert manifest.is_file()
    entry = json.loads(manifest.read_text().strip())
    assert entry["file"] == "new_file.py"


def test_exempt_json_file_not_checked(tmp_path):
    from provenance_gate import run_check
    src = tmp_path / "data.json"
    src.write_text("{}\n")
    ctx = _make_ctx(str(src), str(tmp_path), mode="marker", marker_text="AI-generated")
    with patch("provenance_gate._is_new_file", return_value=True):
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_binary_file_exempt(tmp_path):
    from provenance_gate import run_check
    src = tmp_path / "image.png"
    src.write_bytes(b"\x89PNG\r\n")
    ctx = _make_ctx(str(src), str(tmp_path), mode="marker", marker_text="AI-generated")
    with patch("provenance_gate._is_new_file", return_value=True):
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW
