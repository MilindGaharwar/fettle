"""AI-1 regression contract for the final Assurance Record authority boundary.

These tests intentionally fail until the corresponding production hardening is
authorized. They exercise the aggregate policy decision, not parallel test-only
validators.
"""

from __future__ import annotations

import hashlib
import json
import subprocess

import pytest

from fettle.assurance import build_assurance_record, evaluate_assurance_policy
from fettle.config import load_config


_KNOWN_GAP = pytest.mark.xfail(
    strict=True, reason="AI-1 captures a confirmed Assurance Integrity gap",
)


def _init_repo(tmp_path, name="repo"):
    root = tmp_path / name
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
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"], check=True,
    )
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return root, head


def _policy_decision(root, dimension, required="PASS"):
    (root / ".fettle.toml").write_text(
        f'[assurance.release.production]\n{dimension} = "{required}"\n',
        encoding="utf-8",
    )
    record = build_assurance_record(str(root))["record"]
    return record, evaluate_assurance_policy(record, str(root), "production")


def _write_verify_evidence(root, *, ok=True):
    from fettle.verify_gate import _write_stamp

    stamp = {
        "ok": ok, "session_id": "verify-1", "head_sha": _git_head(root),
        "exit_code": 0 if ok else 1, "command": "pytest -q",
        "error": "tests failed" if not ok else "", "scope": "full", "impacted": [],
    }
    _write_stamp(str(root), stamp, load_config(str(root)))


def _write_ci_evidence(root, *, overall="success"):
    from fettle.ci_gate import _write_stamp

    stamp = {
        "ok": overall == "success", "sha": _git_head(root), "overall": overall,
        "runs": [{"id": 1, "name": "CI"}],
        "error": "CI failed" if overall == "failure" else "",
    }
    _write_stamp(str(root), stamp, load_config(str(root)))


def _git_head(root):
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def _write_mutation_report(root, *, passed=False, status="completed"):
    from fettle.mutation_test import MUTMUT_VERSION, _canonical_digest

    source = root / "src" / "a.py"
    test = root / "tests" / "test_a.py"
    source.parent.mkdir(exist_ok=True)
    test.parent.mkdir(exist_ok=True)
    source.write_text("def value():\n    return 1\n", encoding="utf-8")
    test.write_text("from src.a import value\n\ndef test_value():\n    assert value() == 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "src/a.py", "tests/test_a.py"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "mutation fixture"], check=True)
    config = load_config(str(root))["mutation"]
    policy = {
        key: config.get(key) for key in (
            "mode", "score_target", "minimum_scored_mutants",
            "max_new_actionable_survivors", "max_untested",
            "max_mutant_timeouts", "max_suspicious_mutants",
        )
    }
    mapping = {"src/a.py": ["tests/test_a.py"]}
    ranges = [{"file": "src/a.py", "start": 1, "end": 2}]
    report = {
        "schema_version": "2", "status": status, "passed": passed,
        "revision": _git_head(root), "selection": "all",
        "engine_version": MUTMUT_VERSION,
        "test_runner": "python -m pytest -x --assert=plain {mapped_tests}",
        "files_tested": ["src/a.py"], "tests_run": ["tests/test_a.py"],
        "line_ranges": ranges,
        "policy_digest": _canonical_digest(policy),
        "source_scope_digest": _canonical_digest({
            "src/a.py": hashlib.sha256(source.read_bytes()).hexdigest(),
        }),
        "test_mapping_digest": _canonical_digest(mapping),
        "line_range_digest": _canonical_digest(ranges),
        "killed": 1, "survived": 1, "timeout": 0, "suspicious": 0,
        "untested": 0, "skipped": 0, "score": 50.0,
        "non_killed": [{
            "fingerprint": "a" * 64, "source_context_digest": "b" * 64,
            "engine_id": "1", "state": "survived", "file": "src/a.py",
            "line": 2, "operator": "Constant", "before": "1", "after": "2",
            "mapped_tests": ["tests/test_a.py"], "rerun_command": "mutmut run 1",
        }],
    }
    (root / "mutation-report.json").write_text(json.dumps(report), encoding="utf-8")


def test_raw_green_verify_without_canonical_sidecar_cannot_authorize(tmp_path):
    root, head = _init_repo(tmp_path)
    (root / ".fettle" / "verify.json").write_text(
        json.dumps({"ok": True, "session_id": "verify-1", "head_sha": head}),
        encoding="utf-8",
    )

    record, decision = _policy_decision(root, "behavior")

    assert record["dimensions"]["behavior"]["status"] == "UNKNOWN"
    assert decision["status"] == "FAIL"


def test_raw_green_ci_without_canonical_sidecar_cannot_authorize(tmp_path):
    root, head = _init_repo(tmp_path)
    (root / ".fettle" / "ci-status.json").write_text(
        json.dumps({"ok": True, "sha": head, "overall": "success"}),
        encoding="utf-8",
    )

    record, decision = _policy_decision(root, "ci")

    assert record["dimensions"]["ci"]["status"] == "UNKNOWN"
    assert decision["status"] == "FAIL"


def test_canonical_verify_violation_remains_failure(tmp_path):
    root, _head = _init_repo(tmp_path)
    (root / ".fettle.toml").write_text(
        '[assurance.release.production]\nbehavior = "PASS"\n', encoding="utf-8",
    )
    _write_verify_evidence(root, ok=False)

    record = build_assurance_record(str(root))["record"]
    decision = evaluate_assurance_policy(record, str(root), "production")

    assert record["dimensions"]["behavior"]["status"] == "FAIL"
    assert decision["status"] == "FAIL"


def test_canonical_verify_for_old_source_cannot_authorize(tmp_path):
    root, _head = _init_repo(tmp_path)
    _write_verify_evidence(root)
    (root / "README.md").write_text("changed\n", encoding="utf-8")

    record, decision = _policy_decision(root, "behavior")

    assert record["dimensions"]["behavior"]["status"] == "UNKNOWN"
    assert "wrong_source" in record["dimensions"]["behavior"]["reason"]
    assert decision["status"] == "FAIL"


def test_canonical_ci_for_old_policy_cannot_authorize(tmp_path):
    root, _head = _init_repo(tmp_path)
    _write_ci_evidence(root)
    (root / ".fettle.toml").write_text(
        '[gates.ci]\nmode = "enforce"\n\n'
        '[assurance.release.production]\nci = "PASS"\n', encoding="utf-8",
    )

    record = build_assurance_record(str(root))["record"]
    decision = evaluate_assurance_policy(record, str(root), "production")

    assert record["dimensions"]["ci"]["status"] == "UNKNOWN"
    assert "wrong_policy" in record["dimensions"]["ci"]["reason"]
    assert decision["status"] == "FAIL"


def test_completed_but_failed_mutation_cannot_authorize(tmp_path):
    root, _head = _init_repo(tmp_path)
    (root / ".fettle.toml").write_text(
        '[mutation]\nmode = "enforce"\nscore_target = 80\nminimum_scored_mutants = 0\n\n'
        '[assurance.release.production]\nbehavior = "PASS"\n', encoding="utf-8",
    )
    _write_verify_evidence(root)
    _write_mutation_report(root, passed=False)

    record = build_assurance_record(str(root))["record"]
    decision = evaluate_assurance_policy(record, str(root), "production")

    assert record["dimensions"]["behavior"]["status"] == "FAIL"
    assert decision["status"] == "FAIL"


def test_mutation_tool_error_cannot_become_behavior_failure_or_pass(tmp_path):
    root, _head = _init_repo(tmp_path)
    _write_verify_evidence(root)
    (root / "mutation-report.json").write_text(
        json.dumps({"schema_version": "2", "status": "tool_error", "passed": False}),
        encoding="utf-8",
    )

    record, decision = _policy_decision(root, "behavior")

    assert record["dimensions"]["behavior"]["status"] == "UNKNOWN"
    assert "mutation" in record["dimensions"]["behavior"]["reason"]
    assert decision["status"] == "FAIL"


def test_parseable_forged_anchor_cannot_authorize(tmp_path):
    root, _head = _init_repo(tmp_path)
    (root / ".fettle" / "governance-ledger.jsonl").write_text(
        "{}\n", encoding="utf-8",
    )
    (root / ".fettle" / "ledger-anchor.json").write_text("{}\n", encoding="utf-8")

    record, decision = _policy_decision(root, "provenance", "COMPLETE")

    assert record["dimensions"]["provenance"]["status"] == "UNKNOWN"
    assert decision["status"] == "FAIL"


def test_unbound_raw_security_review_cannot_authorize(tmp_path):
    root, _head = _init_repo(tmp_path)
    (root / ".fettle" / "security-review.json").write_text(
        json.dumps({
            "findings": [],
            "tools_used": ["ruff", "semgrep"],
            "tools_missing": [],
            "tool_errors": [],
        }),
        encoding="utf-8",
    )

    record, decision = _policy_decision(root, "security")

    assert record["dimensions"]["security"]["status"] == "UNKNOWN"
    assert decision["status"] == "FAIL"


def test_caller_supplied_changed_files_do_not_establish_scope(tmp_path):
    root, _head = _init_repo(tmp_path)
    (root / ".fettle.toml").write_text(
        '[assurance.release.production]\nscope = "PASS"\n', encoding="utf-8",
    )

    record = build_assurance_record(
        str(root), changed_files=["src/not-derived-from-repository.py"],
    )["record"]
    decision = evaluate_assurance_policy(record, str(root), "production")

    scope = record["dimensions"]["scope"]
    assert scope["status"] == "PASS"
    assert scope["evidence"][0]["path"] == "git:changed-files"
    assert record["scope"]["paths"] == [".fettle.toml"]
    assert "src/not-derived-from-repository.py" not in record["scope"]["paths"]
    assert decision["status"] == "PASS"


def test_equivalent_clone_locations_have_portable_record_digest(tmp_path):
    first, _head = _init_repo(tmp_path, "first")
    second = tmp_path / "second"
    subprocess.run(["git", "clone", "-q", str(first), str(second)], check=True)

    first_record = build_assurance_record(str(first))["record"]
    second_record = build_assurance_record(str(second))["record"]

    assert first_record["digest"] == second_record["digest"]


def test_effective_policy_digest_changes_with_org_layer(tmp_path, monkeypatch):
    root, _head = _init_repo(tmp_path)
    config_home = tmp_path / "config"
    org_dir = config_home / "fettle"
    org_dir.mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    (org_dir / "org.toml").write_text(
        '[gates.lint]\nmode = "soft"\n', encoding="utf-8",
    )
    first = build_assurance_record(str(root))["record"]

    (org_dir / "org.toml").write_text(
        '[gates.lint]\nmode = "enforce"\n', encoding="utf-8",
    )
    second = build_assurance_record(str(root))["record"]

    assert first["policy"]["digest"] != second["policy"]["digest"]
    assert first["dimensions"]["policy_integrity"]["evidence"][0]["path"] == "effective-policy"


def test_working_subject_digest_changes_with_source(tmp_path):
    root, _head = _init_repo(tmp_path)
    first = build_assurance_record(str(root))["record"]

    (root / "README.md").write_text("changed\n", encoding="utf-8")
    second = build_assurance_record(str(root))["record"]

    assert first["subject"]["kind"] == "working"
    assert first["subject"]["snapshot_digest"] != second["subject"]["snapshot_digest"]
