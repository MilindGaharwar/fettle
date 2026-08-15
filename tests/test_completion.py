"""Completion evidence contract and enforcement tests."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pytest

from fettle.completion import evaluate_manifests, render_completion


FIXTURES = Path(__file__).parent / "fixtures" / "completion"


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    shutil.copytree(FIXTURES / name, root)
    return root


@pytest.mark.parametrize(
    ("fixture", "exit_code", "valid", "complete"),
    [
        ("complete", 0, True, True),
        ("timeout", 1, True, False),
        ("error-path", 0, True, True),
        ("contradictory", 2, False, False),
        ("malformed", 2, False, False),
        ("duplicate", 2, False, False),
        ("missing", 2, False, False),
        ("stale", 1, True, False),
        ("p63-regression", 2, False, False),
    ],
)
def test_completion_fixture_decisions(tmp_path, fixture, exit_code, valid, complete):
    result = evaluate_manifests(_copy_fixture(tmp_path, fixture))

    assert result.exit_code == exit_code
    assert result.valid is valid
    assert result.complete is complete


def test_timeout_can_confirm_only_error_path(tmp_path):
    result = evaluate_manifests(_copy_fixture(tmp_path, "error-path"))

    criterion = result.milestones[0].criteria[0]
    assert criterion.kind == "error_path"
    assert criterion.verdict == "confirmed"
    assert criterion.observed == "timeout"


def test_one_evidence_reference_cannot_confirm_different_outcomes(tmp_path):
    root = _copy_fixture(tmp_path, "complete")
    manifest_path = root / "docs" / "completion" / "P1.json"
    manifest = json.loads(manifest_path.read_text())
    duplicate = dict(manifest["criteria"][0])
    duplicate.update({"id": "error", "kind": "error_path"})
    manifest["criteria"].append(duplicate)
    manifest_path.write_text(json.dumps(manifest))

    result = evaluate_manifests(root)

    assert result.exit_code == 2
    assert "different expected outcomes" in result.errors[0]


def test_evidence_reference_cannot_confirm_different_outcomes_across_manifests(tmp_path):
    root = _copy_fixture(tmp_path, "complete")
    original = root / "docs" / "completion" / "P1.json"
    manifest = json.loads(original.read_text())
    manifest.update({"milestone": "P2", "status": "in_progress", "uat_decision": "FIX_FIRST"})
    manifest["criteria"][0].update({"id": "timeout-handling", "kind": "error_path"})
    (original.parent / "P2.json").write_text(json.dumps(manifest))

    result = evaluate_manifests(root)

    assert result.exit_code == 2
    assert any("different expected outcomes" in error for error in result.errors)


def test_unknown_milestone_is_usage_error(tmp_path):
    result = evaluate_manifests(_copy_fixture(tmp_path, "complete"), milestone="P404")

    assert result.exit_code == 2
    assert result.errors == ["unknown milestone P404"]


def test_empty_directory_has_no_completion_claims(tmp_path):
    result = evaluate_manifests(tmp_path)

    assert result.exit_code == 0
    assert result.valid is True
    assert result.complete is True
    assert result.milestones == []


def test_human_and_json_render_same_decision(tmp_path):
    result = evaluate_manifests(_copy_fixture(tmp_path, "timeout"))

    human = render_completion(result)
    payload = result.as_dict()

    assert "P2: incomplete" in human
    assert payload["milestones"][0]["status"] == "incomplete"
    assert "Run installed success UAT" in human
    assert payload["milestones"][0]["criteria"][0]["recovery"] == "Run installed success UAT"


def test_completion_cli_json_exit_code(tmp_path, monkeypatch, capsys):
    from fettle.cli import cmd_completion

    root = _copy_fixture(tmp_path, "timeout")
    (root / ".git").mkdir()
    (root / ".fettle.toml").write_text("")
    monkeypatch.chdir(root)

    with pytest.raises(SystemExit) as exc:
        cmd_completion(argparse.Namespace(completion_action="validate", milestone=None, json=True))

    assert exc.value.code == 1
    assert json.loads(capsys.readouterr().out)["complete"] is False
