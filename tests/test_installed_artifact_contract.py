import json
import subprocess
import sys
from datetime import UTC, datetime

import pytest

from fettle.installed_artifact_contract import (
    load_capability_policy,
    validate_release_evidence,
    validate_report,
)


NOW = datetime(2026, 8, 17, tzinfo=UTC)
DIGEST = "a" * 64


def _host(*, live_state="pass", observed_at="2026-08-16T12:00:00Z"):
    return {
        "registration": "pass",
        "transport": "pass",
        "live_evidence": {
            "state": live_state,
            "observed_at": observed_at,
            "host_version": "1.2.3",
            "reference": "docs/uat/installed-bridge-v1.11.1.md",
        },
    }


def _report(stage="candidate"):
    return {
        "schema_version": "1",
        "stage": stage,
        "package": {
            "name": "finefettle",
            "version": "1.11.1",
            "wheel": {
                "filename": "finefettle-1.11.1-py3-none-any.whl",
                "sha256": DIGEST,
                "size": 1234,
            },
        },
        "environment": {
            "python": "3.11.9",
            "os": "linux",
            "architecture": "x86_64",
            "pipx": "1.7.1",
            "checkout_independent": True,
        },
        "bridge": {
            "state": "pass",
            "version": "1.11.1",
            "manifest_sha256": "b" * 64,
        },
        "doctor": "pass",
        "hosts": {
            "claude-code": _host(),
            "codex-cli": _host(),
            "gemini-cli": _host(live_state="blocked", observed_at=None),
            "opencode": _host(),
        },
    }


def test_capability_policy_is_valid_and_matches_known_hosts():
    policy = load_capability_policy()

    assert set(policy.hosts) == {
        "claude-code", "codex-cli", "gemini-cli", "opencode",
    }
    assert policy.hosts["codex-cli"].claim == "supported-installed"
    assert policy.hosts["claude-code"].claim == "supported-installed"


def test_report_derives_pass_from_every_required_criterion():
    report = validate_report(_report())

    assert report.stage == "candidate"
    assert report.complete


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.pop("doctor"), "missing or unknown fields"),
        (lambda value: value.update({"unexpected": True}), "missing or unknown fields"),
        (lambda value: value.update({"schema_version": "999"}), "schema_version"),
        (lambda value: value["package"]["wheel"].update({"sha256": "bad"}), "sha256"),
        (lambda value: value["environment"].update({"checkout_independent": False}), "checkout"),
        (lambda value: value["hosts"].pop("opencode"), "host set"),
        (lambda value: value["hosts"]["opencode"].update({"transport": "blocked"}), "transport"),
    ],
)
def test_report_rejects_missing_malformed_or_non_pass_evidence(mutation, message):
    value = _report()
    mutation(value)

    with pytest.raises(ValueError, match=message):
        validate_report(value)


def test_supported_claim_requires_fresh_live_evidence():
    candidate = _report()
    candidate["hosts"]["codex-cli"]["live_evidence"]["observed_at"] = "2026-01-01T00:00:00Z"

    result = validate_release_evidence(candidate, _report("public"), now=NOW)

    assert not result.ok
    assert "codex-cli: live evidence is stale" in result.errors


def test_supported_and_contract_tested_claims_preserve_their_evidence_boundaries():
    result = validate_release_evidence(_report(), _report("public"), now=NOW)

    assert result.ok
    assert result.claims["claude-code"] == "supported-installed"
    assert result.claims["codex-cli"] == "supported-installed"
    assert result.claims["gemini-cli"] == "contract-tested"


def test_public_report_must_match_candidate_artifact_identity():
    public = _report("public")
    public["package"]["wheel"]["sha256"] = "c" * 64

    result = validate_release_evidence(_report(), public, now=NOW)

    assert not result.ok
    assert "public artifact identity does not match candidate" in result.errors


def test_json_parser_rejects_duplicate_keys():
    value = json.dumps(_report()).replace(
        '"schema_version": "1"',
        '"schema_version": "1", "schema_version": "1"',
        1,
    )

    with pytest.raises(ValueError, match="duplicate JSON key"):
        validate_report(value)


def test_module_cli_validates_reports(tmp_path):
    candidate = tmp_path / "candidate.json"
    public = tmp_path / "public.json"
    candidate.write_text(json.dumps(_report()))
    public.write_text(json.dumps(_report("public")))

    result = subprocess.run(
        [sys.executable, "-m", "fettle.installed_artifact_contract", str(candidate), str(public)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "installed artifact evidence passed"
