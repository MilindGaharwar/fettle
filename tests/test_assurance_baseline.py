from __future__ import annotations

import json
import subprocess

import pytest

from fettle.assurance_baseline import (
    BASELINE_COMMIT,
    _copy_state,
    capture_candidate,
    compare_decisions,
    evaluate_frozen_policy,
    normalize_decision,
    portable_value,
    verify_capture,
)


def _repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    (root / ".gitignore").write_text(".fettle/\n", encoding="utf-8")
    (root / "app.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "seed"], check=True)
    (root / ".fettle.toml").write_text(
        '[assurance.release.production]\nsecurity = "PASS"\nprovenance = "PARTIAL|COMPLETE"\n',
        encoding="utf-8",
    )
    (root / "app.py").write_text("value = 2\n", encoding="utf-8")
    return root


def test_frozen_policy_is_sorted_and_maps_provenance():
    dimensions = {
        "security": {"status": "PASS"},
        "provenance": {"status": "UNKNOWN"},
    }

    result = evaluate_frozen_policy(
        dimensions, {"security": "PASS", "provenance": "PARTIAL|COMPLETE"},
    )

    assert result["status"] == "PASS"
    assert [item["dimension"] for item in result["criteria"]] == ["provenance", "security"]
    assert result["criteria"][0]["actual"] == "PARTIAL"


@pytest.mark.parametrize(
    ("policy", "dimensions"),
    [
        ({"confidence": "PASS"}, {}),
        ({"security": "GREEN"}, {"security": {"status": "PASS"}}),
        ({"security": "PASS"}, {"security": {"status": "GREEN"}}),
    ],
)
def test_frozen_policy_rejects_unsupported_dimensions_and_statuses(policy, dimensions):
    assert evaluate_frozen_policy(dimensions, policy)["status"] == "CONFIG_ERROR"


def test_normalization_is_stable_and_ignores_volatile_fields():
    capture = {
        "candidate": {
            "head": "a" * 40,
            "source_snapshot_digest": "sha256:" + "b" * 64,
            "policy_digest": "sha256:" + "c" * 64,
            "scope_digest": "sha256:" + "d" * 64,
        },
        "changed_files": [{"path": "app.py", "status": "modified", "digest": "sha256:x"}],
        "policy": {"security": "PASS"},
    }
    raw = {
        "status": "completed",
        "record": {
            "generated_at": 1,
            "digest": "first",
            "dimensions": {"security": {"status": "PASS", "reason": "volatile prose"}},
            "completeness": "PARTIAL",
        },
    }

    first = normalize_decision(raw, capture, BASELINE_COMMIT, "sha256:" + "e" * 64)
    raw["record"]["generated_at"] = 2
    raw["record"]["digest"] = "second"
    second = normalize_decision(raw, capture, BASELINE_COMMIT, "sha256:" + "e" * 64)

    assert first == second
    assert first["policy"]["status"] == "PASS"
    assert first["dimensions"]["authorization"] == "UNKNOWN"


def test_portable_value_removes_candidate_absolute_paths(tmp_path):
    root = tmp_path / "candidate"
    raw = {"root": str(root), "path": str(root / ".fettle" / "verify.json")}

    assert portable_value(raw, root) == {
        "root": ".", "path": ".fettle/verify.json",
    }


def test_state_copy_minimizes_trace_and_restores_runtime_paths(tmp_path, monkeypatch):
    root = tmp_path / "candidate"
    root.mkdir()
    state_home = tmp_path / "source-state"
    (state_home / "fettle").mkdir(parents=True)
    relevant = {
        "hook": "authorship_gate", "status": "pass",
        "file": str(root / "app.py"), "session_id": "implementer",
    }
    unrelated = {
        "hook": "authorship_gate", "status": "pass",
        "file": str(tmp_path / "other" / "app.py"), "session_id": "other",
    }
    (state_home / "fettle" / "trace.jsonl").write_text(
        "\n".join(json.dumps(row) for row in (relevant, unrelated)) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))
    bundle = tmp_path / "bundle"
    runtime = tmp_path / "runtime"

    _copy_state(root, bundle, runtime)

    retained = json.loads((bundle / "state" / "fettle" / "trace.jsonl").read_text())
    restored = json.loads((runtime / "fettle" / "trace.jsonl").read_text())
    assert retained["file"] == "app.py"
    assert str(root) not in json.dumps(retained)
    assert restored["file"] == str(root / "app.py")


def test_comparison_reports_semantic_field_changes_only():
    dimensions = {
        name: "UNKNOWN" for name in (
            "authorization", "policy_integrity", "scope", "behavior", "security",
            "independence", "provenance", "uat", "ci",
        )
    }
    prior = {
        "policy": {"status": "PASS"}, "dimensions": {**dimensions, "security": "PASS"},
        "completeness": "PARTIAL",
    }
    hardened = {
        "policy": {"status": "FAIL"}, "dimensions": {**dimensions, "security": "FAIL"},
        "completeness": "PARTIAL",
    }

    differences = compare_decisions(prior, hardened)

    assert {item["path"] for item in differences} == {
        "dimensions.security", "policy.status",
    }


def test_capture_is_portable_and_detects_tampering(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    state_home = tmp_path / "state-home"
    (state_home / "fettle").mkdir(parents=True)
    (state_home / "fettle" / "trace.jsonl").write_text('{"hook":"test"}\n', encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))
    monkeypatch.setattr(
        "fettle.assurance_baseline._implementation",
        lambda _root, revision=None: (revision or "f" * 40, "sha256:" + "a" * 64),
    )

    capture = capture_candidate(root)

    encoded = json.dumps(capture, sort_keys=True)
    assert str(root) not in encoded
    assert capture["changed_files"] == [
        {"path": ".fettle.toml", "status": "untracked", "digest": capture["changed_files"][0]["digest"]},
        {"path": "app.py", "status": "modified", "digest": capture["changed_files"][1]["digest"]},
    ]
    assert verify_capture(root, capture) == []

    (root / "app.py").write_text("value = 3\n", encoding="utf-8")
    assert "changed files differ from capture" in verify_capture(root, capture)


def test_capture_identity_ignores_capture_time(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    monkeypatch.setattr(
        "fettle.assurance_baseline._implementation",
        lambda _root, revision=None: (revision or "f" * 40, "sha256:" + "a" * 64),
    )

    first = capture_candidate(root)
    second = capture_candidate(root)

    assert first["capture_manifest_digest"] == second["capture_manifest_digest"]


def test_capture_rejects_empty_scope(tmp_path):
    root = _repo(tmp_path)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "clean"], check=True)

    with pytest.raises(ValueError, match="no changed files"):
        capture_candidate(root)
