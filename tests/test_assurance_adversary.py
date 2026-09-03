"""P83 named adversary suite for assurance-control benchmark scoring."""

from __future__ import annotations

import json
import subprocess

import pytest

from fettle.capsule_guard import run_check as check_capsule
from fettle.assurance import build_assurance_record, evaluate_assurance_policy
from fettle.dispatcher_types import Decision, HookContext, HookInput
from fettle.evidence import (
    EvidenceArtifact,
    EvidenceValidationContext,
    ResultState,
    Validity,
    validate_artifact,
)
from fettle.evidence_ledger import append_record, verify_chain
from fettle.policy_capsule import merge_for_child
from fettle.post_bash_doc_check import run_check as check_docs
from fettle.uat.artifacts import load_scenario_artifacts, write_scenario_artifacts
from fettle.uat.reconcile import reconcile

SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64


def _hook_context(tmp_path, *, command="", config=None):
    return HookContext(
        input=HookInput(
            hook_event_name="PostToolUse" if command else "PreToolUse",
            tool_name="Bash" if command else "Write",
            tool_input={"command": command} if command else {"file_path": "src/app.py"},
            cwd=tmp_path,
            session_id="adversary-session",
            raw={},
        ),
        config=config or {"gates": {}},
        plugin_root=tmp_path,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=9999.0,
    )


def _evidence():
    return EvidenceArtifact.create(
        kind="fettle.verify",
        producer={"id": "fettle.verify", "version": "1.0",
                  "implementation_digest": SHA_D},
        result_state="pass",
        completeness="complete",
        trust_class="authoritative",
        source={"snapshot_digest": SHA_A, "revision": "1" * 40},
        policy_digest=SHA_B,
        scope_digest=SHA_C,
        observation_id="p83-run",
        observed_at="2026-08-27T10:00:00Z",
        payload={"exit_code": 0},
    )


def _evidence_context(**changes):
    values = {
        "kind": "fettle.verify",
        "source_snapshot_digest": SHA_A,
        "source_revision": "1" * 40,
        "policy_digest": SHA_B,
        "scope_digest": SHA_C,
        "producer_id": "fettle.verify",
        "producer_versions": frozenset({"1.0"}),
        "producer_implementation_digest": SHA_D,
        "recovery_action": "fettle verify",
    }
    values.update(changes)
    return EvidenceValidationContext(**values)


def _init_assurance_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@fettle.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "t"], check=True,
    )
    (root / ".fettle").mkdir()
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "seed"], check=True,
    )
    return root


def _release_decision(root, dimension, required="PASS"):
    (root / ".fettle.toml").write_text(
        f'[assurance.release.production]\n{dimension} = "{required}"\n',
        encoding="utf-8",
    )
    record = build_assurance_record(str(root))["record"]
    return record["dimensions"][dimension], evaluate_assurance_policy(
        record, str(root), "production",
    )


def test_p83_ledger_edit_is_detected(tmp_path):
    append_record(str(tmp_path), "gate_decision", decision="block")
    ledger = tmp_path / ".fettle" / "governance-ledger.jsonl"
    record = json.loads(ledger.read_text(encoding="utf-8"))
    record["payload"]["decision"] = "allow"
    ledger.write_text(json.dumps(record) + "\n", encoding="utf-8")

    assert verify_chain(str(tmp_path))["status"] == "tampered"


def test_p83_transcript_drift_is_not_confirmed(tmp_path):
    scenarios = [{"id": "demo/S1", "steps": ["Then exit code is zero"]}]
    transcript = "SCENARIO: demo/S1\nOBSERVED: command exited 0\nOUTCOME: matches\n"
    artifacts = write_scenario_artifacts(str(tmp_path), transcript, scenarios, "cli")
    tampered = transcript.replace("command exited 0", "everything worked")

    verdict = reconcile(
        scenarios, tampered, artifacts=load_scenario_artifacts(artifacts),
        require_artifacts=True,
    )[0]

    assert verdict.verdict == "INDETERMINATE"


def test_p83_capsule_digest_tamper_blocks(tmp_path, monkeypatch):
    capsule = tmp_path / "capsule.json"
    capsule.write_text(json.dumps({
        "fettle_capsule": 1,
        "digest": "0" * 64,
        "policy": {"gates": {}},
        "origin": {},
        "lineage": [],
    }), encoding="utf-8")
    monkeypatch.setenv("FETTLE_POLICY_CAPSULE", str(capsule))

    assert check_capsule(_hook_context(tmp_path)).decision == Decision.BLOCK


def test_p83_documentation_omission_blocks_push(tmp_path, monkeypatch):
    tracking = tmp_path / "edits.jsonl"
    tracking.write_text(json.dumps({
        "file": str(tmp_path / "src" / "app.py"), "ts": 1.0,
    }) + "\n", encoding="utf-8")
    monkeypatch.setenv("FETTLE_EDIT_TRACKING", str(tracking))
    context = _hook_context(
        tmp_path,
        command="git push origin main",
        config={"gates": {"docs": {"enabled": True, "mode": "enforce"}}},
    )

    assert check_docs(context).decision == Decision.BLOCK


def test_p83_stale_evidence_injection_is_non_pass():
    result = validate_artifact(_evidence(), _evidence_context(invalidated=True))

    assert result.validity == Validity.STALE
    assert result.result_state == ResultState.UNKNOWN


def test_p83_wrong_scope_replay_is_non_pass():
    result = validate_artifact(
        _evidence(),
        _evidence_context(scope_digest="sha256:" + "e" * 64),
    )

    assert result.validity == Validity.WRONG_SCOPE
    assert result.result_state == ResultState.UNKNOWN


@pytest.mark.parametrize(
    ("capsule", "local", "path", "expected"),
    [
        (
            {"gates": {"coverage": {"threshold": 90}}},
            {"gates": {"coverage": {"threshold": 60}}},
            ("gates", "coverage", "threshold"), 90,
        ),
        (
            {"gates": {"tdd": {"exempt_paths": ["docs/**"]}}},
            {"gates": {"tdd": {"exempt_paths": ["docs/**", "src/**"]}}},
            ("gates", "tdd", "exempt_paths"), ["docs/**"],
        ),
    ],
)
def test_p83_policy_downgrade_preserves_parent_policy(capsule, local, path, expected):
    effective, ignored = merge_for_child(capsule, local)
    value = effective
    for key in path:
        value = value[key]

    assert value == expected
    assert ignored


@pytest.mark.parametrize(
    ("dimension", "required", "artifact", "expected"),
    [
        (
            "behavior", "PASS", ".fettle/verify.json",
            {"ok": True, "session_id": "forged", "head_sha": "0" * 40},
        ),
        (
            "security", "PASS", ".fettle/security-review.json",
            {"findings": [], "tools_used": ["ruff", "semgrep"],
             "tools_missing": [], "tool_errors": []},
        ),
        ("provenance", "COMPLETE", ".fettle/ledger-anchor.json", {}),
    ],
)
def test_p83_unbound_or_forged_artifact_fails_release_policy(
    tmp_path, dimension, required, artifact, expected,
):
    root = _init_assurance_repo(tmp_path)
    path = root / artifact
    path.write_text(json.dumps(expected), encoding="utf-8")
    if dimension == "provenance":
        (root / ".fettle" / "governance-ledger.jsonl").write_text(
            "{}\n", encoding="utf-8",
        )

    result, decision = _release_decision(root, dimension, required)

    assert result["status"] == "UNKNOWN"
    assert decision["status"] == "FAIL"


def test_p83_tampered_delegation_fails_release_policy(tmp_path, monkeypatch):
    root = _init_assurance_repo(tmp_path)
    capsule = tmp_path / "0000000000000000.json"
    capsule.write_text(json.dumps({
        "fettle_capsule": 1,
        "digest": "0" * 64,
        "policy": {"gates": {}},
        "origin": {},
        "lineage": [],
    }), encoding="utf-8")
    monkeypatch.setenv("FETTLE_POLICY_CAPSULE", str(capsule))

    result, decision = _release_decision(root, "authorization")

    assert result["status"] == "FAIL"
    assert decision["status"] == "FAIL"
