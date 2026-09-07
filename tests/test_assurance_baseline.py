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
    review_bundle,
    summarize_store,
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


def _bundle(tmp_path, *, differences=None, identity="b"):
    from fettle.assurance_baseline import (
        _canonical_bytes,
        _capture_digest,
        _digest_bytes,
        _digest_file,
    )

    content = b"value = 2\n"
    capture = {
        "protocol_version": "1",
        "captured_at": "2026-09-07T12:00:00Z",
        "baseline": {
            "commit": "a" * 40, "implementation_digest": "sha256:" + "1" * 64,
        },
        "hardened": {
            "commit": "b" * 40, "implementation_digest": "sha256:" + "2" * 64,
        },
        "candidate": {
            "head": identity * 40,
            "source_snapshot_digest": "sha256:" + identity * 64,
            "policy_digest": "sha256:" + "3" * 64,
            "scope_digest": "sha256:" + "4" * 64,
        },
        "policy": {},
        "changed_files": [{
            "path": "app.py", "status": "modified", "digest": _digest_bytes(content),
        }],
    }
    capture["capture_manifest_digest"] = _capture_digest(capture)
    bundle = tmp_path / capture["capture_manifest_digest"].removeprefix("sha256:")
    bundle.mkdir(parents=True)
    (bundle / "source").mkdir()
    (bundle / "source" / "app.py").write_bytes(content)
    raw_dimensions = {name: {"status": "PASS"} for name in (
            "authorization", "policy_integrity", "scope", "behavior", "security",
            "independence", "provenance", "uat", "ci",
        )}
    prior_raw = {"status": "completed", "record": {"dimensions": raw_dimensions}}
    hardened_raw = json.loads(json.dumps(prior_raw))
    for difference in differences or []:
        if difference["path"].startswith("dimensions."):
            name = difference["path"].split(".", 1)[1]
            hardened_raw["record"]["dimensions"][name]["status"] = difference["hardened"]
        elif difference["path"] in {"policy.status", "completeness"}:
            hardened_raw["record"]["dimensions"]["security"]["status"] = "UNKNOWN"
    prior = normalize_decision(
        prior_raw, capture, capture["baseline"]["commit"],
        capture["baseline"]["implementation_digest"],
    )
    hardened = normalize_decision(
        hardened_raw, capture, capture["hardened"]["commit"],
        capture["hardened"]["implementation_digest"],
    )
    differences = compare_decisions(prior, hardened)
    for name, value in (
        ("capture.json", capture),
        ("changed-files.json", capture["changed_files"]),
        ("prior-v1.raw.json", prior_raw),
        ("prior-v1.decision.json", prior),
        ("hardened.raw.json", hardened_raw),
        ("hardened.decision.json", hardened),
    ):
        (bundle / name).write_bytes(_canonical_bytes(value))
    comparison = {
        "protocol_version": "1",
        "comparator_implementation_digest": "sha256:" + "c" * 64,
        "raw_digests": {
            "prior_v1": _digest_file(bundle / "prior-v1.raw.json"),
            "hardened": _digest_file(bundle / "hardened.raw.json"),
        },
        "differences": differences,
        "accepted": False,
    }
    (bundle / "comparison.json").write_bytes(_canonical_bytes(comparison))
    return bundle


def test_review_accepts_complete_bundle_with_no_differences(tmp_path):
    bundle = _bundle(tmp_path)

    result = review_bundle(
        bundle, change="PR-41", reviewer="Milind",
        reviewer_email="20487933+MilindGaharwar@users.noreply.github.com",
        classifications=[],
    )

    assert result["accepted"] is True
    assert result["change"] == "PR-41"
    assert json.loads((bundle / "review.json").read_text()) == result


def test_review_requires_evidenced_classification_for_each_difference(tmp_path):
    difference = {"path": "dimensions.security", "prior": "PASS", "hardened": "UNKNOWN"}
    bundle = _bundle(tmp_path, differences=[difference])

    with pytest.raises(ValueError, match="classification"):
        review_bundle(
            bundle, change="PR-42", reviewer="Milind", reviewer_email="milind@example.com",
            classifications=[],
        )

    result = review_bundle(
        bundle, change="PR-42", reviewer="Milind", reviewer_email="milind@example.com",
        classifications=[{
            "path": "dimensions.security", "classification": "intentional_hardening",
            "evidence": "commit f911f0e security authority hardening",
        }],
    )
    assert result["accepted"] is True


def test_review_rejects_tampered_raw_output(tmp_path):
    bundle = _bundle(tmp_path)
    (bundle / "hardened.raw.json").write_text('{"tampered":true}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="digest"):
        review_bundle(
            bundle, change="PR-43", reviewer="Milind", reviewer_email="milind@example.com",
            classifications=[],
        )


def test_review_rejects_tampered_normalized_decision(tmp_path):
    bundle = _bundle(tmp_path)
    decision = json.loads((bundle / "hardened.decision.json").read_text())
    decision["dimensions"]["security"] = "UNKNOWN"
    (bundle / "hardened.decision.json").write_text(json.dumps(decision), encoding="utf-8")

    with pytest.raises(ValueError, match="semantic decision digest"):
        review_bundle(
            bundle, change="PR-43", reviewer="Milind", reviewer_email="milind@example.com",
            classifications=[],
        )


def test_review_rejects_retained_source_path_outside_bundle(tmp_path):
    from fettle.assurance_baseline import _canonical_bytes, _capture_digest

    bundle = _bundle(tmp_path)
    capture = json.loads((bundle / "capture.json").read_text())
    capture["changed_files"][0]["path"] = "../escape.py"
    capture["capture_manifest_digest"] = _capture_digest(capture)
    replacement = bundle.with_name(capture["capture_manifest_digest"].removeprefix("sha256:"))
    bundle.rename(replacement)
    (replacement / "capture.json").write_bytes(_canonical_bytes(capture))
    (replacement / "changed-files.json").write_bytes(
        _canonical_bytes(capture["changed_files"])
    )

    with pytest.raises(ValueError, match="escapes bundle"):
        review_bundle(
            replacement, change="PR-43", reviewer="Milind",
            reviewer_email="milind@example.com", classifications=[],
        )


def test_review_rejects_self_consistent_decision_not_derived_from_raw(tmp_path):
    from fettle.assurance_baseline import _canonical_bytes, _json_digest

    bundle = _bundle(tmp_path)
    decision = json.loads((bundle / "hardened.decision.json").read_text())
    decision["dimensions"]["security"] = "UNKNOWN"
    decision["semantic_input_digest"] = _json_digest({
        key: value for key, value in decision.items() if key != "semantic_input_digest"
    })
    (bundle / "hardened.decision.json").write_bytes(_canonical_bytes(decision))

    with pytest.raises(ValueError, match="retained raw output"):
        review_bundle(
            bundle, change="PR-43", reviewer="Milind", reviewer_email="milind@example.com",
            classifications=[],
        )


def test_summary_counts_only_accepted_reviews_and_writes_register(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    accepted = _bundle(store)
    review_bundle(
        accepted, change="PR-44", reviewer="Milind", reviewer_email="milind@example.com",
        classifications=[],
    )
    rejected = _bundle(store, identity="c", differences=[{
        "path": "dimensions.security", "prior": "PASS", "hardened": "UNKNOWN",
    }])
    review_bundle(
        rejected, change="PR-45", reviewer="Milind", reviewer_email="milind@example.com",
        classifications=[{
            "path": "dimensions.security", "classification": "unresolved",
            "evidence": "requires investigation",
        }],
    )
    register = tmp_path / "register.md"

    summary = summarize_store(store, register)

    assert summary["accepted"] == 1
    assert summary["reviewed"] == 2
    assert summary["remaining"] == 19
    assert "Status: collecting; 1 of 20" in register.read_text()
    assert "PR-44" in register.read_text()
    assert "PR-45" in register.read_text()


def test_summary_does_not_count_duplicate_source_snapshot(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    first = _bundle(store, identity="d")
    review_bundle(
        first, change="PR-46", reviewer="Milind", reviewer_email="milind@example.com",
        classifications=[],
    )
    second = _bundle(store, identity="e")
    capture_path = second / "capture.json"
    capture = json.loads(capture_path.read_text())
    capture["candidate"]["source_snapshot_digest"] = "sha256:" + "d" * 64
    from fettle.assurance_baseline import _canonical_bytes, _capture_digest
    capture["capture_manifest_digest"] = _capture_digest(capture)
    replacement = second.with_name(capture["capture_manifest_digest"].removeprefix("sha256:"))
    second.rename(replacement)
    capture_path = replacement / "capture.json"
    capture_path.write_bytes(_canonical_bytes(capture))
    # Rebuild decisions because the subject identity is part of normalization.
    prior_raw = json.loads((replacement / "prior-v1.raw.json").read_text())
    hardened_raw = json.loads((replacement / "hardened.raw.json").read_text())
    for name, raw, evaluator in (
        ("prior-v1", prior_raw, capture["baseline"]),
        ("hardened", hardened_raw, capture["hardened"]),
    ):
        decision = normalize_decision(
            raw, capture, evaluator["commit"], evaluator["implementation_digest"],
        )
        (replacement / f"{name}.decision.json").write_bytes(_canonical_bytes(decision))
    comparison = json.loads((replacement / "comparison.json").read_text())
    comparison["differences"] = []
    (replacement / "comparison.json").write_bytes(_canonical_bytes(comparison))
    review_bundle(
        replacement, change="PR-47", reviewer="Milind", reviewer_email="milind@example.com",
        classifications=[],
    )

    summary = summarize_store(store)

    assert summary["reviewed"] == 2
    assert summary["accepted"] == 1
    assert {row["qualification"] for row in summary["rows"]} == {
        "accepted", "duplicate_subject",
    }
