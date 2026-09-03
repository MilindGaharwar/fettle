"""Completion evidence contract and enforcement tests."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pytest

from fettle.completion import evaluate_manifests, render_completion, work_item_scope_digest


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


def test_done_work_item_requires_matching_completion_manifest(tmp_path):
    item_dir = tmp_path / "docs" / "backlog"
    item_dir.mkdir(parents=True)
    (item_dir / "feature.md").write_text(
        "---\nfettle-work-item: v2\nid: feature-x\nstatus: done\n---\n"
        "\n# Feature X\n\n## Resolution\nShipped.\n",
        encoding="utf-8",
    )

    result = evaluate_manifests(tmp_path, required_work_items={"feature-x"})

    assert result.exit_code == 2
    assert result.errors == [
        "done work item feature-x has no completion manifest; "
        "add docs/completion/feature-x.json before marking it done"
    ]


def test_explicit_done_work_item_is_known_even_without_manifest(tmp_path):
    item_dir = tmp_path / "docs" / "backlog"
    item_dir.mkdir(parents=True)
    (item_dir / "feature.md").write_text(
        "---\nfettle-work-item: v2\nid: feature-x\nstatus: done\n---\n",
        encoding="utf-8",
    )

    result = evaluate_manifests(tmp_path, milestone="feature-x")

    assert result.exit_code == 2
    assert "has no completion manifest" in result.errors[0]


def test_legacy_done_work_item_does_not_require_historical_backfill(tmp_path):
    item_dir = tmp_path / "docs" / "backlog"
    item_dir.mkdir(parents=True)
    (item_dir / "legacy.md").write_text(
        "---\nfettle-work-item: v1\nid: legacy-x\nstatus: done\n---\n",
        encoding="utf-8",
    )

    result = evaluate_manifests(tmp_path)

    assert result.exit_code == 0
    assert result.errors == []


def test_explicit_milestone_ignores_other_done_work_items(tmp_path):
    root = _copy_fixture(tmp_path, "complete")
    item_dir = root / "docs" / "backlog"
    item_dir.mkdir(parents=True)
    (item_dir / "other.md").write_text(
        "---\nfettle-work-item: v2\nid: other-x\nstatus: done\n---\n",
        encoding="utf-8",
    )

    result = evaluate_manifests(root, milestone="P1")

    assert result.exit_code == 0
    assert [item.milestone for item in result.milestones] == ["P1"]


def test_v2_completion_is_bound_to_declared_work_item_scope(tmp_path):
    item_dir = tmp_path / "docs" / "backlog"
    item_dir.mkdir(parents=True)
    source = tmp_path / "src" / "feature.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\n", encoding="utf-8")
    item_path = item_dir / "feature.md"
    item_path.write_text(
        "---\nfettle-work-item: v2\nid: feature-x\nstatus: done\n"
        "scope:\n  - src/feature.py\n---\n\n## Resolution\nShipped.\n",
        encoding="utf-8",
    )
    item, _findings = __import__("fettle.work_items", fromlist=["parse_work_item"]).parse_work_item(
        item_path.read_text(encoding="utf-8"), "docs/backlog/feature.md"
    )
    evidence_dir = tmp_path / "docs" / "completion" / "evidence"
    evidence_dir.mkdir(parents=True)
    evidence = evidence_dir / "feature.json"
    evidence.write_text('{"result":"pass"}\n', encoding="utf-8")
    digest = __import__("hashlib").sha256(evidence.read_bytes()).hexdigest()
    scope_digest, error = work_item_scope_digest(tmp_path, item)
    assert error == ""
    manifest = {
        "schema_version": 1,
        "milestone": "feature-x",
        "revision": "test",
        "scope_digest_version": 2,
        "scope_digest": scope_digest,
        "status": "complete",
        "uat_decision": "SHIP",
        "criteria": [{
            "id": "success", "kind": "success", "required": True,
            "verdict": "confirmed", "observed": "success",
            "evidence": {
                "path": "docs/completion/evidence/feature.json",
                "sha256": digest, "revision": "test",
            },
            "recovery": "Rerun verification",
        }],
    }
    manifest_path = tmp_path / "docs" / "completion" / "feature-x.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert evaluate_manifests(tmp_path, milestone="feature-x").exit_code == 0
    source.write_text("VALUE = 2\n", encoding="utf-8")
    assert evaluate_manifests(tmp_path, milestone="feature-x").exit_code == 0

    item_path.write_text(
        "---\nfettle-work-item: v2\nid: feature-x\nstatus: done\n"
        "scope:\n  - src/*.py\n---\n\n## Resolution\nShipped.\n",
        encoding="utf-8",
    )
    stale = evaluate_manifests(tmp_path, milestone="feature-x")

    assert stale.exit_code == 2
    assert any("scope_digest does not match" in error for error in stale.errors)


def test_unversioned_completion_remains_frozen_history(tmp_path):
    item_dir = tmp_path / "docs" / "backlog"
    item_dir.mkdir(parents=True)
    source = tmp_path / "feature.py"
    source.write_text("VALUE = 2\n", encoding="utf-8")
    (item_dir / "feature.md").write_text(
        "---\nfettle-work-item: v2\nid: feature-x\nstatus: done\n"
        "scope:\n  - feature.py\n---\n\n## Resolution\nShipped.\n",
        encoding="utf-8",
    )
    fixture = _copy_fixture(tmp_path, "complete")
    completion = tmp_path / "docs" / "completion"
    completion.mkdir(exist_ok=True)
    shutil.copy(fixture / "evidence/success.json", completion / "success.json")
    manifest = json.loads((fixture / "docs/completion/P1.json").read_text())
    manifest["milestone"] = "feature-x"
    manifest["scope_digest"] = "0" * 64
    manifest["criteria"][0]["evidence"]["path"] = "docs/completion/success.json"
    (completion / "feature-x.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = evaluate_manifests(tmp_path, milestone="feature-x")

    assert result.exit_code == 0


def test_v2_completion_requires_scope_digest(tmp_path):
    root = tmp_path / "repo"
    item_dir = root / "docs" / "backlog"
    item_dir.mkdir(parents=True)
    source = root / "feature.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    (item_dir / "feature.md").write_text(
        "---\nfettle-work-item: v2\nid: feature-x\nstatus: done\n"
        "scope:\n  - feature.py\n---\n\n## Resolution\nShipped.\n",
        encoding="utf-8",
    )
    fixture = _copy_fixture(tmp_path, "complete")
    completion = root / "docs" / "completion"
    completion.mkdir(parents=True)
    shutil.copy(fixture / "evidence/success.json", completion / "success.json")
    manifest = json.loads((fixture / "docs/completion/P1.json").read_text())
    manifest["milestone"] = "feature-x"
    manifest.pop("scope_digest", None)
    manifest["criteria"][0]["evidence"]["path"] = "docs/completion/success.json"
    (completion / "feature-x.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = evaluate_manifests(root, milestone="feature-x")

    assert result.exit_code == 2
    assert any("missing scope_digest" in error for error in result.errors)


def test_v2_completion_requires_same_id_manifest_filename(tmp_path):
    item_dir = tmp_path / "docs" / "backlog"
    item_dir.mkdir(parents=True)
    source = tmp_path / "feature.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    item_path = item_dir / "feature.md"
    item_path.write_text(
        "---\nfettle-work-item: v2\nid: feature-x\nstatus: done\n"
        "scope:\n  - feature.py\n---\n\n## Resolution\nShipped.\n",
        encoding="utf-8",
    )
    from fettle.work_items import parse_work_item

    item, _findings = parse_work_item(
        item_path.read_text(encoding="utf-8"), "docs/backlog/feature.md"
    )
    scope_digest, error = work_item_scope_digest(tmp_path, item)
    assert error == ""
    evidence_dir = tmp_path / "docs" / "completion" / "evidence"
    evidence_dir.mkdir(parents=True)
    evidence = evidence_dir / "feature.json"
    evidence.write_text('{"result":"pass"}\n', encoding="utf-8")
    import hashlib

    manifest = {
        "schema_version": 1,
        "milestone": "feature-x",
        "revision": "test",
        "scope_digest_version": 2,
        "scope_digest": scope_digest,
        "status": "complete",
        "uat_decision": "SHIP",
        "criteria": [{
            "id": "success", "kind": "success", "required": True,
            "verdict": "confirmed", "observed": "success",
            "evidence": {
                "path": "docs/completion/evidence/feature.json",
                "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                "revision": "test",
            },
            "recovery": "Rerun verification",
        }],
    }
    (tmp_path / "docs" / "completion" / "wrong-name.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    result = evaluate_manifests(tmp_path, milestone="feature-x")

    assert result.exit_code == 2
    assert any("requires same-ID manifest" in error for error in result.errors)


def test_manifest_milestone_must_match_filename(tmp_path):
    root = _copy_fixture(tmp_path, "complete")
    path = root / "docs" / "completion" / "P1.json"
    manifest = json.loads(path.read_text())
    manifest["milestone"] = "P2"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    result = evaluate_manifests(root)

    assert result.exit_code == 2
    assert any("milestone must match manifest filename P1" in error for error in result.errors)


def test_v2_scope_must_match_at_least_one_non_completion_file(tmp_path):
    item_dir = tmp_path / "docs" / "backlog"
    item_dir.mkdir(parents=True)
    item_path = item_dir / "feature.md"
    item_path.write_text(
        "---\nfettle-work-item: v2\nid: feature-x\nstatus: done\n"
        "scope:\n  - docs/completion/**\n---\n",
        encoding="utf-8",
    )
    item, _findings = __import__("fettle.work_items", fromlist=["parse_work_item"]).parse_work_item(
        item_path.read_text(encoding="utf-8"), "docs/backlog/feature.md"
    )

    digest, error = work_item_scope_digest(tmp_path, item)

    assert digest == ""
    assert "no files outside docs/completion" in error


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


def test_human_render_includes_repository_level_errors(tmp_path):
    root = _copy_fixture(tmp_path, "complete")
    item_dir = root / "docs" / "backlog"
    item_dir.mkdir(parents=True)
    (item_dir / "new.md").write_text(
        "---\nfettle-work-item: v2\nid: broken\nstatus: done\n",
        encoding="utf-8",
    )

    result = evaluate_manifests(root)

    assert "malformed work item frontmatter" in render_completion(result)


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
