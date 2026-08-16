"""WP-F — Diff Coverage Gate tests."""

import hashlib
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from fettle.dispatcher_types import Decision, HookContext, HookInput
from fettle.evidence import parse_artifact


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
    from fettle.coverage_gate import run_check

    ctx = _make_ctx(tmp_path)
    with patch("fettle.config.state_dir", return_value=tmp_path / "state" / "test-cov"):
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_above_threshold_allows(tmp_path):
    """Coverage above threshold → allow."""
    from fettle.coverage_gate import run_check

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
    with (patch("fettle.config.state_dir", return_value=state_dir / "test-cov"),
          patch("fettle.coverage_gate._get_changed_lines", return_value={1, 2, 3, 4, 5})):
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_below_threshold_advisory(tmp_path):
    """Coverage below threshold in advisory mode → advisory."""
    from fettle.coverage_gate import run_check

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
    with (patch("fettle.config.state_dir", return_value=state_dir / "test-cov"),
          patch("fettle.coverage_gate._get_changed_lines", return_value={1, 2, 3, 4, 5})):
        result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "40%" in result.message
    assert result.evidence[0].evidence_id.startswith("ev-")


def test_below_threshold_enforce_blocks(tmp_path):
    """Coverage below threshold in enforce mode → block."""
    from fettle.coverage_gate import run_check

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
    with (patch("fettle.config.state_dir", return_value=state_dir / "test-cov"),
          patch("fettle.coverage_gate._get_changed_lines", return_value={1, 2, 3, 4, 5})):
        result = run_check(ctx)
    assert result.decision == Decision.BLOCK
    assert "20%" in result.message


def test_branch_coverage_below_threshold(tmp_path):
    """Branch coverage below threshold → advisory with branch message."""
    from fettle.coverage_gate import run_check

    src = tmp_path / "app.py"
    src.write_text("a\nb\nc\nd\ne\n")

    # 1 executed branch from line 2, 2 missing branches from lines 2 and 3
    cov_data = {
        "files": {
            str(src): {
                "executed_lines": [1, 2, 3, 4, 5],
                "executed_branches": [[2, 4]],
                "missing_branches": [[2, 5], [3, 6]],
            }
        }
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_data))
    time.sleep(0.01)

    state_dir = tmp_path / "state"
    _write_edits_jsonl(state_dir, "test-branch", [str(src)])
    (tmp_path / "coverage.json").touch()
    time.sleep(0.01)

    ctx = _make_ctx(tmp_path, threshold=80, session_id="test-branch")
    # Set branch threshold
    ctx.config["gates"]["coverage"]["minimum_branch_percent"] = 80

    with (patch("fettle.config.state_dir", return_value=state_dir / "test-branch"),
          patch("fettle.coverage_gate._get_changed_lines", return_value={1, 2, 3, 4, 5})):
        result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "Branch coverage" in result.message
    assert "33%" in result.message


def test_branch_data_absent_skips_silently(tmp_path):
    """No branch data in coverage.json → branch check skipped, line check runs."""
    from fettle.coverage_gate import run_check

    src = tmp_path / "app.py"
    src.write_text("a\nb\nc\n")

    cov_data = {"files": {str(src): {"executed_lines": [1, 2, 3]}}}
    (tmp_path / "coverage.json").write_text(json.dumps(cov_data))
    time.sleep(0.01)

    state_dir = tmp_path / "state"
    _write_edits_jsonl(state_dir, "test-nobranch", [str(src)])
    (tmp_path / "coverage.json").touch()
    time.sleep(0.01)

    ctx = _make_ctx(tmp_path, threshold=80, session_id="test-nobranch")
    ctx.config["gates"]["coverage"]["minimum_branch_percent"] = 80

    with (patch("fettle.config.state_dir", return_value=state_dir / "test-nobranch"),
          patch("fettle.coverage_gate._get_changed_lines", return_value={1, 2, 3})):
        result = run_check(ctx)
    # Line coverage is 100%, branch data absent → passes
    assert result.decision == Decision.ALLOW


def test_stale_coverage_warns(tmp_path):
    """Coverage.json older than edits → staleness advisory."""
    from fettle.coverage_gate import run_check

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
    with patch("fettle.config.state_dir", return_value=state_dir / "test-cov"):
        result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "stale" in result.message


def test_passing_coverage_writes_complete_portable_canonical_sidecar(tmp_path):
    from fettle.coverage_gate import EVIDENCE_RELPATH, RECOVERY_COMMAND, run_check

    src = tmp_path / "app.py"
    src.write_text("a\nb\n")
    _write_coverage_json(tmp_path, {str(src): {"executed_lines": [1, 2]}})
    state_dir = tmp_path / "state"
    _write_edits_jsonl(state_dir, "test-cov", [str(src)])
    (tmp_path / "coverage.json").touch()
    ctx = _make_ctx(tmp_path)

    with (patch("fettle.config.state_dir", return_value=state_dir / "test-cov"),
          patch("fettle.coverage_gate._get_changed_lines", return_value={1, 2})):
        result = run_check(ctx)

    artifact_bytes = (tmp_path / EVIDENCE_RELPATH).read_bytes()
    artifact = parse_artifact(artifact_bytes)
    report_digest = "sha256:" + hashlib.sha256(
        (tmp_path / "coverage.json").read_bytes()
    ).hexdigest()
    assert result.decision == Decision.ALLOW
    assert artifact.kind == "fettle.coverage"
    assert artifact.result_state == "pass"
    assert artifact.completeness == "complete"
    assert artifact.payload["coverage_report"] == {
        "digest": report_digest,
        "path": "coverage.json",
    }
    assert artifact.payload["edited_line_scope"] == (
        {"lines": (1, 2), "path": "app.py"},
    )
    assert artifact.payload["recovery_command"] == RECOVERY_COMMAND
    assert str(tmp_path).encode() not in artifact_bytes


def test_violation_retains_legacy_reference_and_adds_bound_canonical_reference(tmp_path):
    from fettle.coverage_gate import EVIDENCE_RELPATH, run_check

    src = tmp_path / "app.py"
    src.write_text("a\nb\n")
    _write_coverage_json(tmp_path, {str(src): {"executed_lines": [1]}})
    state_dir = tmp_path / "state"
    _write_edits_jsonl(state_dir, "test-cov", [str(src)])
    (tmp_path / "coverage.json").touch()
    ctx = _make_ctx(tmp_path, threshold=80)

    with (patch("fettle.config.state_dir", return_value=state_dir / "test-cov"),
          patch("fettle.coverage_gate._get_changed_lines", return_value={1, 2})):
        result = run_check(ctx)

    artifact = parse_artifact((tmp_path / EVIDENCE_RELPATH).read_bytes())
    assert result.decision == Decision.ADVISORY
    assert result.message == "Diff coverage below threshold:\napp.py: 50% (1/2 lines)"
    assert result.evidence[0].evidence_id.startswith("ev-")
    assert result.evidence[0].kind == "coverage"
    assert result.evidence[1].artifact_digest == artifact.artifact_digest
    assert result.evidence[1].expected == {
        "source_snapshot_digest": artifact.source["snapshot_digest"],
        "policy_digest": artifact.policy_digest,
        "scope_digest": artifact.scope_digest,
        "producer_id": "fettle.coverage",
    }
    assert artifact.result_state == "violation"


def test_stale_coverage_writes_recoverable_non_pass_evidence(tmp_path):
    from fettle.coverage_gate import EVIDENCE_RELPATH, RECOVERY_COMMAND, run_check

    src = tmp_path / "app.py"
    src.write_text("a\n")
    _write_coverage_json(tmp_path, {str(src): {"executed_lines": [1]}})
    state_dir = tmp_path / "state"
    _write_edits_jsonl(state_dir, "test-cov", [str(src)])
    coverage_path = tmp_path / "coverage.json"
    edits_path = state_dir / "test-cov" / "edits.jsonl"
    old = time.time() - 60
    os.utime(coverage_path, (old, old))
    os.utime(edits_path, None)

    with (patch("fettle.config.state_dir", return_value=state_dir / "test-cov"),
          patch("fettle.coverage_gate._get_changed_lines", return_value={1})):
        result = run_check(_make_ctx(tmp_path))

    artifact = parse_artifact((tmp_path / EVIDENCE_RELPATH).read_bytes())
    assert result.decision == Decision.ADVISORY
    assert result.message == "Coverage data is stale — re-run tests to enable the coverage gate"
    assert artifact.result_state == "unknown"
    assert artifact.payload["stale"] is True
    assert artifact.payload["recovery_command"] == RECOVERY_COMMAND


def test_canonical_evidence_false_rolls_back_without_changing_result(tmp_path):
    from fettle.coverage_gate import EVIDENCE_RELPATH, run_check

    src = tmp_path / "app.py"
    src.write_text("a\nb\n")
    _write_coverage_json(tmp_path, {str(src): {"executed_lines": [1]}})
    state_dir = tmp_path / "state"
    _write_edits_jsonl(state_dir, "test-cov", [str(src)])
    (tmp_path / "coverage.json").touch()
    ctx = _make_ctx(tmp_path)
    ctx.config["gates"]["coverage"]["canonical_evidence"] = False

    with (patch("fettle.config.state_dir", return_value=state_dir / "test-cov"),
          patch("fettle.coverage_gate._get_changed_lines", return_value={1, 2})):
        result = run_check(ctx)

    assert result.decision == Decision.ADVISORY
    assert result.message == "Diff coverage below threshold:\napp.py: 50% (1/2 lines)"
    assert len(result.evidence) == 1
    assert result.evidence[0].evidence_id.startswith("ev-")
    assert not (tmp_path / EVIDENCE_RELPATH).exists()


def test_canonical_coverage_sidecar_detects_tampering(tmp_path):
    from fettle.coverage_gate import EVIDENCE_RELPATH, run_check

    src = tmp_path / "app.py"
    src.write_text("a\n")
    _write_coverage_json(tmp_path, {str(src): {"executed_lines": [1]}})
    state_dir = tmp_path / "state"
    _write_edits_jsonl(state_dir, "test-cov", [str(src)])
    (tmp_path / "coverage.json").touch()
    with (patch("fettle.config.state_dir", return_value=state_dir / "test-cov"),
          patch("fettle.coverage_gate._get_changed_lines", return_value={1})):
        run_check(_make_ctx(tmp_path))
    sidecar = tmp_path / EVIDENCE_RELPATH
    artifact = json.loads(sidecar.read_text())
    artifact["payload"]["stale"] = True
    sidecar.write_text(json.dumps(artifact, sort_keys=True, separators=(",", ":")))

    with pytest.raises(ValueError, match="digest does not match"):
        parse_artifact(sidecar.read_bytes())


def test_canonical_coverage_write_failure_is_logged_without_changing_result(tmp_path, caplog):
    from fettle.coverage_gate import run_check

    src = tmp_path / "app.py"
    src.write_text("a\n")
    _write_coverage_json(tmp_path, {str(src): {"executed_lines": [1]}})
    state_dir = tmp_path / "state"
    _write_edits_jsonl(state_dir, "test-cov", [str(src)])
    (tmp_path / "coverage.json").touch()

    with (patch("fettle.config.state_dir", return_value=state_dir / "test-cov"),
          patch("fettle.coverage_gate._get_changed_lines", return_value={1}),
          patch("fettle.coverage_gate._write_bytes_atomic", side_effect=OSError("full"))):
        result = run_check(_make_ctx(tmp_path))

    assert result.decision == Decision.ALLOW
    assert "canonical coverage evidence unavailable" in caplog.text
