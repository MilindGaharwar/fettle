"""P80 contract tests — the canonical Assurance Record."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fettle.assurance import build_assurance_record


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


def test_independence_passes_with_spawn_lineage(tmp_path, monkeypatch):
    root = _init_repo(tmp_path)
    monkeypatch.setenv("FETTLE_PARENT_SESSION", "parent-abc")

    record = build_assurance_record(str(root))["record"]

    assert record["dimensions"]["independence"]["status"] == "PASS"


def test_independence_unknown_without_roles_or_lineage(tmp_path):
    root = _init_repo(tmp_path)

    record = build_assurance_record(str(root))["record"]

    independence = record["dimensions"]["independence"]
    assert independence["status"] == "UNKNOWN"
    assert "role declaration" in independence["reason"]


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
