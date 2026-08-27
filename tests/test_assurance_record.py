"""P80 contract tests — the canonical Assurance Record."""

from __future__ import annotations

import json
import subprocess

from fettle.assurance import build_assurance_record, evaluate_assurance_policy


def _init_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)])
    for flag in (("config", "user.email", "t@t"), ("config", "user.name", "t")):
        subprocess.run(["git", "-C", str(root), *flag], capture_output=True)
    (root / ".fettle").mkdir(exist_ok=True)
    return root


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


def test_verify_stamp_promotes_behavior_dimension(tmp_path):
    root = _init_repo(tmp_path)
    (root / ".fettle" / "verify.json").write_text(
        json.dumps({"exit_code": 0, "command": "pytest -q"}),
        encoding="utf-8")

    record = build_assurance_record(str(root))["record"]

    behavior = record["dimensions"]["behavior"]
    assert behavior["status"] == "PASS"
    assert behavior["evidence"][0]["path"] == ".fettle/verify.json"


def test_failed_mutation_report_fails_behavior_dimension(tmp_path):
    root = _init_repo(tmp_path)
    (root / "mutation-report.json").write_text(
        json.dumps({"status": "tool_error", "message": "mutmut crashed"}),
        encoding="utf-8")

    record = build_assurance_record(str(root))["record"]

    behavior = record["dimensions"]["behavior"]
    assert behavior["status"] == "FAIL"
    assert "tool_error" in behavior["reason"]


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


def test_anchor_makes_provenance_pass(tmp_path):
    root = _init_repo(tmp_path)
    _ = build_assurance_record(str(root))
    append = root / ".fettle" / "governance-ledger.jsonl"
    append.parent.mkdir(parents=True, exist_ok=True)
    append.write_text(json.dumps({
        "schema_version": 1, "seq": 1, "ts": 1.0, "kind": "genesis",
        "payload": {}, "prev": "0" * 64, "hash": "a" * 64,
    }) + "\n", encoding="utf-8")
    (root / ".fettle" / "ledger-anchor.json").write_text(json.dumps({
        "schema_version": 1, "commit": "a" * 40, "records": 1,
        "terminal_hash": "a" * 64,
    }), encoding="utf-8")

    record = build_assurance_record(str(root))["record"]

    assert record["dimensions"]["provenance"]["status"] == "PASS"


def test_scope_dimension_from_changed_files(tmp_path):
    root = _init_repo(tmp_path)

    record = build_assurance_record(
        str(root), changed_files=["src/a.py", "tests/test_a.py"]
    )["record"]

    assert record["dimensions"]["scope"]["status"] == "PASS"


def test_complete_clean_security_review_passes(tmp_path):
    root = _init_repo(tmp_path)
    (root / ".fettle" / "security-review.json").write_text(json.dumps({
        "findings": [],
        "tools_used": ["ruff", "semgrep"],
        "tools_missing": [],
        "tool_errors": [],
    }), encoding="utf-8")

    security = build_assurance_record(str(root))["record"]["dimensions"]["security"]

    assert security["status"] == "PASS"
    assert security["evidence"][0]["path"] == ".fettle/security-review.json"


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


def test_security_findings_fail_even_when_review_is_partial(tmp_path):
    root = _init_repo(tmp_path)
    (root / ".fettle" / "security-review.json").write_text(json.dumps({
        "findings": [{"code": "S608"}],
        "tools_used": ["ruff"],
        "tools_missing": ["semgrep"],
        "tool_errors": [],
    }), encoding="utf-8")

    security = build_assurance_record(str(root))["record"]["dimensions"]["security"]

    assert security["status"] == "FAIL"
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
    root = _init_repo(tmp_path)
    ledger = root / ".fettle" / "governance-ledger.jsonl"
    ledger.write_text("{}\n", encoding="utf-8")
    (root / ".fettle" / "ledger-anchor.json").write_text("{}", encoding="utf-8")
    (root / ".fettle.toml").write_text(
        '[assurance.release.production]\nprovenance = "COMPLETE"\n',
        encoding="utf-8",
    )
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
