"""P80 contract tests — the canonical Assurance Record."""

from __future__ import annotations

import json
import subprocess

from fettle.assurance import (
    build_assurance_record,
    evaluate_assurance_policy,
    write_evidence,
)
from fettle.config import load_config


def _init_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)])
    for flag in (("config", "user.email", "test@fettle.invalid"), ("config", "user.name", "t")):
        subprocess.run(["git", "-C", str(root), *flag], capture_output=True)
    (root / ".fettle").mkdir(exist_ok=True)
    return root


def _commit_head(root):
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "seed"],
                   capture_output=True)
    done = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    return done.stdout.strip()


def _write_verify_result(root, *, ok, error=""):
    from fettle.verify_gate import _write_stamp

    stamp = {
        "ok": ok, "session_id": "s-1", "head_sha": _commit_head(root),
        "exit_code": 0 if ok else 1, "command": "pytest -q", "error": error,
        "scope": "full", "impacted": [],
    }
    _write_stamp(str(root), stamp, load_config(str(root)))


def _write_ci_result(root, *, overall):
    from fettle.ci_gate import _write_stamp

    stamp = {
        "ok": overall == "success", "sha": _commit_head(root),
        "overall": overall, "runs": [{"id": 1, "name": "CI"}],
        "error": "CI failed" if overall == "failure" else "",
    }
    _write_stamp(str(root), stamp, load_config(str(root)))


def test_empty_repo_produces_partial_record_with_reasons(tmp_path):
    root = _init_repo(tmp_path)

    result = build_assurance_record(str(root))

    record = result["record"]
    assert result["status"] == "completed"
    assert record["completeness"] == "PARTIAL"
    assert record["dimensions"]["behavior"]["status"] == "UNKNOWN"
    assert "no verify stamp" in record["dimensions"]["behavior"]["reason"]
    assert len(record["digest"]) == 64


def test_digest_is_canonical_and_stable(tmp_path):
    root = _init_repo(tmp_path)
    _ = build_assurance_record(str(root))
    (root / ".fettle" / "verify.json").write_text(
        json.dumps({"exit_code": 0, "command": "pytest"}), encoding="utf-8")

    first = build_assurance_record(str(root))
    second = build_assurance_record(str(root))

    # generated_at excluded from digest; same inputs → same digest
    assert first["record"]["digest"] == second["record"]["digest"]
    assert first["record"]["completeness"] == "PARTIAL"


def test_bound_green_verify_stamp_promotes_behavior_dimension(tmp_path):
    root = _init_repo(tmp_path)
    _write_verify_result(root, ok=True)

    record = build_assurance_record(str(root))["record"]

    behavior = record["dimensions"]["behavior"]
    assert behavior["status"] == "PASS"
    assert behavior["evidence"][0]["path"] == ".fettle/verify.json"


def test_red_verify_stamp_fails_behavior_dimension(tmp_path):
    root = _init_repo(tmp_path)
    _write_verify_result(root, ok=False, error="2 failed")

    record = build_assurance_record(str(root))["record"]

    behavior = record["dimensions"]["behavior"]
    assert behavior["status"] == "FAIL"
    assert "violation" in behavior["reason"]


def test_handwritten_minimal_stamp_never_passes_behavior(tmp_path):
    root = _init_repo(tmp_path)
    _commit_head(root)
    (root / ".fettle" / "verify.json").write_text(
        json.dumps({"ok": True}), encoding="utf-8")

    record = build_assurance_record(str(root))["record"]

    behavior = record["dimensions"]["behavior"]
    assert behavior["status"] == "UNKNOWN"
    assert "canonical verification evidence" in behavior["reason"]


def test_stale_revision_stamp_never_passes_behavior(tmp_path):
    root = _init_repo(tmp_path)
    _commit_head(root)
    (root / ".fettle" / "verify.json").write_text(
        json.dumps({"ok": True, "session_id": "s-1", "head_sha": "0" * 40}),
        encoding="utf-8")

    record = build_assurance_record(str(root))["record"]

    behavior = record["dimensions"]["behavior"]
    assert behavior["status"] == "UNKNOWN"
    assert "canonical verification evidence" in behavior["reason"]


def test_malformed_mutation_cannot_mask_red_verify(tmp_path):
    root = _init_repo(tmp_path)
    (root / "mutation-report.json").write_text(
        json.dumps({"status": "completed"}), encoding="utf-8")
    _write_verify_result(root, ok=False, error="1 failed")

    record = build_assurance_record(str(root))["record"]

    behavior = record["dimensions"]["behavior"]
    assert behavior["status"] == "FAIL"
    assert "verification reported a violation" in behavior["reason"]


def test_mutation_tool_error_is_unknown_behavior_dimension(tmp_path):
    root = _init_repo(tmp_path)
    (root / "mutation-report.json").write_text(
        json.dumps({"status": "tool_error", "message": "mutmut crashed"}),
        encoding="utf-8")

    record = build_assurance_record(str(root))["record"]

    behavior = record["dimensions"]["behavior"]
    assert behavior["status"] == "UNKNOWN"
    assert "incomplete" in behavior["reason"]


def test_stages_report_presence(tmp_path):
    root = _init_repo(tmp_path)
    _ = build_assurance_record(str(root))
    (root / ".fettle" / "trace.jsonl").write_text(
        json.dumps({"hook": "PreToolUse"}) + "\n", encoding="utf-8")

    result = build_assurance_record(str(root))

    stages = {s["stage"]: s for s in result["record"]["stages"]}
    assert stages["agent_actions"]["present"] is True
    assert stages["mutation"]["present"] is False
    assert stages["mutation"]["digest"] is None


def _write_authorship_trace(state_root, root, entries):
    trace = state_root / "fettle" / "trace.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text("".join(json.dumps({
        "schema": 2, "hook": "authorship_gate", "status": "pass",
        "file": str(root / path), "session_id": session, "role": role,
        "parent_session_id": parent, "capsule_digest": "a" * 16,
    }) + "\n" for path, session, role, parent in entries), encoding="utf-8")


def test_independence_is_high_with_separate_authors_verifier_and_claim(tmp_path, monkeypatch):
    root = _init_repo(tmp_path)
    state = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    _write_authorship_trace(state, root, [
        ("src/app.py", "impl-1", "implementer", "reviewer-1"),
        ("tests/test_app.py", "test-1", "tester", "reviewer-1"),
    ])
    (root / ".fettle" / "verify.json").write_text(
        json.dumps({"ok": True, "session_id": "reviewer-1"}), encoding="utf-8")
    common = root / ".git" / "fettle"
    common.mkdir(parents=True)
    (common / "claims.json").write_text(json.dumps({
        "item": {"session_id": "reviewer-1", "worktree": str(root), "claimed_at": 1},
    }), encoding="utf-8")

    record = build_assurance_record(str(root))["record"]

    independence = record["dimensions"]["independence"]
    assert independence["status"] == "PASS"
    assert independence["grade"] == "HIGH"


def test_independence_is_medium_with_separate_authors_only(tmp_path, monkeypatch):
    root = _init_repo(tmp_path)
    state = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    _write_authorship_trace(state, root, [
        ("src/app.py", "impl-1", "implementer", "parent-1"),
        ("tests/test_app.py", "test-1", "tester", "parent-1"),
    ])

    independence = build_assurance_record(str(root))["record"]["dimensions"]["independence"]

    assert independence["status"] == "PASS"
    assert independence["grade"] == "MEDIUM"
    assert "independent verification" in independence["reason"]


def test_independence_is_low_when_one_session_authors_code_and_tests(tmp_path, monkeypatch):
    root = _init_repo(tmp_path)
    state = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    _write_authorship_trace(state, root, [
        ("src/app.py", "same-1", "implementer", "parent-1"),
        ("tests/test_app.py", "same-1", "tester", "parent-1"),
    ])

    independence = build_assurance_record(str(root))["record"]["dimensions"]["independence"]

    assert independence["status"] == "FAIL"
    assert independence["grade"] == "LOW"


def test_independence_unknown_without_roles_or_lineage(tmp_path):
    root = _init_repo(tmp_path)

    record = build_assurance_record(str(root))["record"]

    independence = record["dimensions"]["independence"]
    assert independence["status"] == "UNKNOWN"
    assert independence["grade"] == "UNKNOWN"
    assert "role-bound authorship" in independence["reason"]


def test_current_commit_anchor_makes_provenance_pass(tmp_path):
    from fettle.evidence_ledger import anchor, append_record

    root = _init_repo(tmp_path)
    _commit_head(root)
    append_record(str(root), "gate_decision", decision="allow")
    anchor(str(root))

    record = build_assurance_record(str(root))["record"]

    assert record["dimensions"]["provenance"]["status"] == "PASS"


def test_anchor_for_other_commit_cannot_pass_provenance(tmp_path):
    from fettle.evidence_ledger import anchor, append_record

    root = _init_repo(tmp_path)
    _commit_head(root)
    append_record(str(root), "gate_decision", decision="allow")
    anchor(str(root), commit="0" * 40)

    provenance = build_assurance_record(str(root))["record"]["dimensions"]["provenance"]

    assert provenance["status"] == "UNKNOWN"
    assert "different commit" in provenance["reason"]


def test_post_anchor_ledger_growth_cannot_pass_provenance(tmp_path):
    from fettle.evidence_ledger import anchor, append_record

    root = _init_repo(tmp_path)
    _commit_head(root)
    append_record(str(root), "gate_decision", decision="allow")
    anchor(str(root))
    append_record(str(root), "gate_decision", decision="block")

    provenance = build_assurance_record(str(root))["record"]["dimensions"]["provenance"]

    assert provenance["status"] == "UNKNOWN"
    assert "post-anchor" in provenance["reason"]


def test_scope_dimension_from_changed_files(tmp_path):
    root = _init_repo(tmp_path)

    record = build_assurance_record(
        str(root), changed_files=["src/a.py", "tests/test_a.py"]
    )["record"]

    assert record["dimensions"]["scope"]["status"] == "PASS"


def test_complete_clean_raw_security_review_remains_unknown(tmp_path):
    root = _init_repo(tmp_path)
    (root / ".fettle" / "security-review.json").write_text(json.dumps({
        "findings": [],
        "tools_used": ["ruff", "semgrep"],
        "tools_missing": [],
        "tool_errors": [],
    }), encoding="utf-8")

    security = build_assurance_record(str(root))["record"]["dimensions"]["security"]

    assert security["status"] == "UNKNOWN"
    assert security["evidence"][0]["path"] == ".fettle/security-review.json"
    assert "not canonical" in security["reason"]


def test_partial_security_review_remains_unknown(tmp_path):
    root = _init_repo(tmp_path)
    (root / ".fettle" / "security-review.json").write_text(json.dumps({
        "findings": [],
        "tools_used": ["ruff"],
        "tools_missing": ["semgrep"],
        "tool_errors": [],
    }), encoding="utf-8")

    security = build_assurance_record(str(root))["record"]["dimensions"]["security"]

    assert security["status"] == "UNKNOWN"
    assert "incomplete" in security["reason"]


def test_raw_security_findings_are_diagnostic_only(tmp_path):
    root = _init_repo(tmp_path)
    (root / ".fettle" / "security-review.json").write_text(json.dumps({
        "findings": [{"code": "S608"}],
        "tools_used": ["ruff"],
        "tools_missing": ["semgrep"],
        "tool_errors": [],
    }), encoding="utf-8")

    security = build_assurance_record(str(root))["record"]["dimensions"]["security"]

    assert security["status"] == "UNKNOWN"
    assert "1 security finding" in security["reason"]


def test_policy_accepts_alternative_status_without_changing_vector(tmp_path):
    root = _init_repo(tmp_path)
    (root / ".fettle.toml").write_text(
        '[assurance.release.production]\nindependence = "PASS|UNKNOWN"\n',
        encoding="utf-8",
    )
    record = build_assurance_record(str(root))["record"]

    decision = evaluate_assurance_policy(record, str(root), "production")

    assert record["dimensions"]["independence"]["status"] == "UNKNOWN"
    assert decision["status"] == "PASS"
    assert decision["criteria"][0]["actual"] == "UNKNOWN"
    assert decision["criteria"][0]["expected"] == ["PASS", "UNKNOWN"]


def test_policy_uses_documented_provenance_completeness_values(tmp_path):
    from fettle.evidence_ledger import anchor, append_record

    root = _init_repo(tmp_path)
    (root / ".fettle.toml").write_text(
        '[assurance.release.production]\nprovenance = "COMPLETE"\n',
        encoding="utf-8",
    )
    _commit_head(root)
    append_record(str(root), "gate_decision", decision="allow")
    anchor(str(root))
    record = build_assurance_record(str(root))["record"]

    decision = evaluate_assurance_policy(record, str(root), "production")

    assert record["dimensions"]["provenance"]["status"] == "PASS"
    assert decision["status"] == "PASS"
    assert decision["criteria"][0]["actual"] == "COMPLETE"


def test_malformed_security_review_shape_remains_unknown(tmp_path):
    root = _init_repo(tmp_path)
    (root / ".fettle" / "security-review.json").write_text("[]", encoding="utf-8")

    security = build_assurance_record(str(root))["record"]["dimensions"]["security"]

    assert security["status"] == "UNKNOWN"
    assert "malformed" in security["reason"]


def test_policy_fails_closed_on_unknown_dimension(tmp_path):
    root = _init_repo(tmp_path)
    (root / ".fettle.toml").write_text(
        '[assurance.release.production]\nconfidence = "PASS"\n',
        encoding="utf-8",
    )

    decision = evaluate_assurance_policy(
        build_assurance_record(str(root))["record"], str(root), "production",
    )

    assert decision["status"] == "CONFIG_ERROR"
    assert "unknown dimension confidence" in decision["errors"][0]


def test_policy_fails_closed_on_empty_alternative(tmp_path):
    root = _init_repo(tmp_path)
    (root / ".fettle.toml").write_text(
        '[assurance.release.production]\nbehavior = "PASS|"\n',
        encoding="utf-8",
    )

    decision = evaluate_assurance_policy(
        build_assurance_record(str(root))["record"], str(root), "production",
    )

    assert decision["status"] == "CONFIG_ERROR"
    assert "unsupported status" in decision["errors"][0]


def test_policy_fails_closed_on_malformed_toml(tmp_path):
    root = _init_repo(tmp_path)
    (root / ".fettle.toml").write_text(
        '[assurance.release.production\nbehavior = "PASS"\n', encoding="utf-8",
    )

    decision = evaluate_assurance_policy(
        build_assurance_record(str(root))["record"], str(root), "production",
    )

    assert decision["status"] == "CONFIG_ERROR"
    assert "could not parse" in decision["errors"][0]


def test_org_layer_supplies_release_policy_without_repo_toml(tmp_path, monkeypatch):
    """Release policies resolve through WP-20 layers, not a raw repo read."""
    org_dir = tmp_path / "xdg" / "fettle"
    org_dir.mkdir(parents=True)
    (org_dir / "org.toml").write_text(
        '[assurance.release.production]\nbehavior = "PASS"\n', encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    root = _init_repo(tmp_path)

    decision = evaluate_assurance_policy(
        build_assurance_record(str(root))["record"], str(root), "production",
    )

    assert decision["status"] in ("PASS", "FAIL")  # resolved, not CONFIG_ERROR
    assert decision["criteria"][0]["dimension"] == "behavior"


# ─── Dimension binding (2026-08 audit: unbound JSON must not PASS) ──────────


def test_ci_dimension_requires_bound_green_status(tmp_path):
    root = _init_repo(tmp_path)
    _write_ci_result(root, overall="success")

    ci = build_assurance_record(str(root))["record"]["dimensions"]["ci"]

    assert ci["status"] == "PASS"
    assert ci["evidence"][0]["path"] == ".fettle/ci-status.json"


def test_ci_dimension_rejects_status_for_other_revision(tmp_path):
    root = _init_repo(tmp_path)
    _write_ci_result(root, overall="success")
    stamp_path = root / ".fettle" / "ci-status.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp["sha"] = "0" * 40
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")

    ci = build_assurance_record(str(root))["record"]["dimensions"]["ci"]

    assert ci["status"] == "UNKNOWN"
    assert "canonical CI evidence" in ci["reason"]


def test_ci_dimension_fails_on_red_status(tmp_path):
    root = _init_repo(tmp_path)
    _write_ci_result(root, overall="failure")

    ci = build_assurance_record(str(root))["record"]["dimensions"]["ci"]

    assert ci["status"] == "FAIL"
    assert "violation" in ci["reason"]


def test_authorization_dimension_verifies_explicit_capsule(tmp_path, monkeypatch):
    from fettle.policy_capsule import canonical_digest
    root = _init_repo(tmp_path)
    policy = {"gates": {"verify": {"enabled": True}}}
    capsule = tmp_path / f"{canonical_digest(policy)[:16]}.json"
    capsule.write_text(json.dumps({
        "fettle_capsule": 1, "digest": canonical_digest(policy),
        "policy": policy, "origin": {}, "lineage": [],
    }), encoding="utf-8")
    monkeypatch.setenv("FETTLE_POLICY_CAPSULE", str(capsule))

    auth = build_assurance_record(str(root))["record"]["dimensions"]["authorization"]

    assert auth["status"] == "PASS"


def test_authorization_dimension_fails_on_explicit_tampered_capsule(tmp_path, monkeypatch):
    root = _init_repo(tmp_path)
    capsule = tmp_path / "ffffffffffffffff.json"
    capsule.write_text(json.dumps({
        "fettle_capsule": 1, "digest": "f" * 64,
        "policy": {"gates": {}}, "origin": {}, "lineage": [],
    }), encoding="utf-8")
    monkeypatch.setenv("FETTLE_POLICY_CAPSULE", str(capsule))

    auth = build_assurance_record(str(root))["record"]["dimensions"]["authorization"]

    assert auth["status"] == "FAIL"
    assert "digest mismatch" in auth["reason"]


def test_incidental_repo_capsule_does_not_make_authorization_applicable(tmp_path):
    root = _init_repo(tmp_path)
    (root / ".fettle" / "capsule.json").write_text("{}", encoding="utf-8")

    auth = build_assurance_record(str(root))["record"]["dimensions"]["authorization"]

    assert auth["status"] == "NOT_APPLICABLE"


def _write_uat_report(root, all_confirmed=True):
    from fettle.uat.reconcile import Verdict, write_report
    verdicts = [
        Verdict("spec/S1", "CONFIRMED" if all_confirmed else "CONTRADICTED",
                observed="ran", note=""),
    ]
    session = {"session_id": "uat-1", "surface": "cli"}
    path, error = write_report(str(root), session, verdicts, candidates=[])
    assert path and not error, error


def test_uat_dimension_passes_with_bound_canonical_sidecar(tmp_path):
    root = _init_repo(tmp_path)
    _write_uat_report(root)

    uat = build_assurance_record(str(root))["record"]["dimensions"]["uat"]

    assert uat["status"] == "PASS"
    assert any(e["path"] == ".fettle/uat-report.evidence.json"
               for e in uat["evidence"])


def test_uat_dimension_rejects_report_without_sidecar(tmp_path):
    root = _init_repo(tmp_path)
    _write_uat_report(root)
    (root / ".fettle" / "uat-report.evidence.json").unlink()

    uat = build_assurance_record(str(root))["record"]["dimensions"]["uat"]

    assert uat["status"] == "UNKNOWN"
    assert "missing" in uat["reason"]


def test_uat_dimension_rejects_edited_report(tmp_path):
    root = _init_repo(tmp_path)
    _write_uat_report(root)
    path = root / ".fettle" / "uat-report.json"
    report = json.loads(path.read_text())
    report["verdicts"].append(
        {"scenario_id": "spec/S2", "verdict": "CONFIRMED", "observed": "", "note": ""})
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    uat = build_assurance_record(str(root))["record"]["dimensions"]["uat"]

    assert uat["status"] == "UNKNOWN"
    assert "tampered" in uat["reason"]


def test_newer_canonical_uat_violation_supersedes_older_pass(tmp_path):
    from fettle.uat.reconcile import Verdict, write_report

    root = _init_repo(tmp_path)
    _write_uat_report(root)
    path, error = write_report(
        str(root), {"session_id": "uat-2", "surface": "cli"},
        [Verdict("spec/S1", "CONTRADICTED", observed="wrong result")], candidates=[],
    )
    assert path and not error, error

    uat = build_assurance_record(str(root))["record"]["dimensions"]["uat"]

    assert uat["status"] == "FAIL"
    assert "0/1 scenarios confirmed" in uat["reason"]


def test_unresolved_uat_evaluator_is_unknown_at_assurance_boundary(tmp_path):
    from fettle.uat.reconcile import Verdict, write_report

    root = _init_repo(tmp_path)
    path, error = write_report(
        str(root), {"session_id": "uat-1", "surface": "cli"},
        [Verdict("spec/S1", "CONFIRMED", observed="ran")], candidates=[],
        judgment={"status": "tool_error", "findings": [], "error": "timeout"},
    )
    assert path and not error, error

    uat = build_assurance_record(str(root))["record"]["dimensions"]["uat"]

    assert uat["status"] == "UNKNOWN"
    assert "canonical UAT result is unknown" in uat["reason"]


def test_persisted_assurance_record_is_canonical_and_portable(tmp_path):
    from fettle.evidence import parse_artifact

    root = _init_repo(tmp_path)
    record = build_assurance_record(str(root))["record"]

    result = write_evidence(str(root), record)
    artifact = parse_artifact((root / ".fettle" / "assurance-record.evidence.json").read_bytes())

    assert result["status"] == "completed"
    assert artifact.kind == "fettle.assurance.record"
    assert artifact.payload["record"]["digest"] == record["digest"]
    assert "root" not in artifact.payload["record"]["subject"]
    assert "generated_at" not in artifact.payload["record"]
    assert str(root) not in artifact.to_bytes().decode()


def test_persisted_record_references_accepted_canonical_evidence(tmp_path):
    from fettle.evidence import parse_artifact

    root = _init_repo(tmp_path)
    _write_verify_result(root, ok=True)
    record = build_assurance_record(str(root))["record"]

    write_evidence(str(root), record)
    artifact = parse_artifact((root / ".fettle" / "assurance-record.evidence.json").read_bytes())
    verify = parse_artifact((root / ".fettle" / "verify-evidence.json").read_bytes())

    assert [(parent.kind, parent.artifact_digest) for parent in artifact.parents] == [
        (verify.kind, verify.artifact_digest),
    ]


def test_failed_persistence_removes_older_assurance_record(tmp_path, monkeypatch):
    import fettle.assurance as assurance

    root = _init_repo(tmp_path)
    output = root / ".fettle" / "assurance-record.evidence.json"
    output.write_text("old passing record", encoding="utf-8")
    record = build_assurance_record(str(root))["record"]
    monkeypatch.setattr(assurance.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("disk full")))

    result = write_evidence(str(root), record)

    assert result["status"] == "tool_error"
    assert not output.exists()
    assert not list(output.parent.glob("*.tmp"))


def test_equivalent_clones_have_same_persisted_artifact_digest(tmp_path):
    from fettle.evidence import parse_artifact

    first = _init_repo(tmp_path)
    _commit_head(first)
    second = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(first), str(second)], check=True)
    (second / ".fettle").mkdir(exist_ok=True)

    first_record = build_assurance_record(str(first))["record"]
    second_record = build_assurance_record(str(second))["record"]
    write_evidence(str(first), first_record)
    write_evidence(str(second), second_record)

    first_artifact = parse_artifact(
        (first / ".fettle" / "assurance-record.evidence.json").read_bytes(),
    )
    second_artifact = parse_artifact(
        (second / ".fettle" / "assurance-record.evidence.json").read_bytes(),
    )
    assert first_artifact.artifact_digest == second_artifact.artifact_digest
