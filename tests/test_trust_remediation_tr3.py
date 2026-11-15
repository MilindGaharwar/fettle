from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

from fettle.dispatcher_types import Decision
from fettle.evidence import ResultState
from fettle.verify_gate import STAMP_RELPATH, run_check, run_verify
from tests.test_verify_gate import _cfg, _gate_ctx, _git_repo, _write_edits


def _project(tmp_path: Path, command: str) -> Path:
    repo = _git_repo(tmp_path)
    (repo / ".fettle.toml").write_text(f'[profile]\ntest_command = "{command}"\n')
    return repo


def test_successful_custom_command_without_counts_is_unknown(tmp_path):
    repo = _project(tmp_path, f"{sys.executable} -c pass")

    stamp = run_verify(str(repo), _cfg(scope="full"))

    assert stamp["ok"] is False
    assert stamp["result_state"] == ResultState.UNKNOWN
    assert stamp["tests"] is None
    assert "no test count is available" in stamp["error"]


def test_pytest_all_skipped_is_red_with_counts(tmp_path):
    repo = _git_repo(tmp_path)
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_skip.py").write_text(
        "import pytest\n\n@pytest.mark.skip(reason='fixture')\ndef test_skipped(): pass\n"
    )
    (repo / ".fettle.toml").write_text(
        f'[profile]\ntest_command = "{sys.executable} -m pytest tests"\n'
    )

    stamp = run_verify(str(repo), _cfg(scope="full"))

    assert stamp["ok"] is False
    assert stamp["result_state"] == ResultState.VIOLATION
    assert stamp["tests"]["collected"] == 1
    assert stamp["tests"]["executed"] == 0
    assert stamp["tests"]["skipped"] == 1
    assert "no tests executed" in stamp["error"]


def test_stop_uses_canonical_result_not_edited_stamp_ok(tmp_path):
    repo = _project(tmp_path, f"{sys.executable} -c 'raise SystemExit(1)'")
    source = repo / "app.py"
    source.write_text("value = 1\n")
    state = repo / "state" / "sess-g"
    _write_edits(state, [str(source)])
    config = _cfg(mode="enforce", scope="full")
    with patch("fettle.config.state_dir", return_value=state):
        run_verify(str(repo), config, session_id="sess-g")
    stamp_path = repo / STAMP_RELPATH
    stamp = json.loads(stamp_path.read_text())
    stamp["ok"] = True
    stamp_path.write_text(json.dumps(stamp))

    with patch("fettle.config.state_dir", return_value=state):
        result = run_check(_gate_ctx(repo, config))

    assert result.decision == Decision.BLOCK
    assert "last verification evidence is violation" in result.message


def test_pytest_evidence_binds_counts_and_argv(tmp_path):
    repo = _git_repo(tmp_path)
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_pass.py").write_text("def test_pass(): pass\n")
    (repo / ".fettle.toml").write_text(
        f'[profile]\ntest_command = "{sys.executable} -m pytest tests"\n'
    )

    stamp = run_verify(str(repo), _cfg(scope="full"))
    artifact = json.loads((repo / ".fettle" / "verify-evidence.json").read_text())

    assert stamp["ok"] is True
    assert artifact["payload"]["tests"]["executed"] == 1
    assert artifact["payload"]["argv"][:3] == [Path(sys.executable).name, "-m", "pytest"]
    assert artifact["payload"]["argv"][-1] == "--junitxml=.fettle/verify-junit.xml"
