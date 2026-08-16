"""P35 canonical recorded-override contracts."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from fettle.evidence import EvidenceArtifact
from fettle.overrides import (
    OverrideContext,
    OverrideRecord,
    load_override_ledger,
    save_override_ledger,
    select_override,
    summarize_ledger,
)


_SOURCE = "sha256:" + "c" * 64
_POLICY = "sha256:" + "b" * 64
_SCOPE = "sha256:" + "d" * 64
_IMPLEMENTATION = "sha256:" + "e" * 64


def _artifact(**changes):
    values = {
        "kind": "fettle.mutation.report",
        "producer": {"id": "fettle.mutation", "version": "1.0", "implementation_digest": _IMPLEMENTATION},
        "result_state": "violation", "completeness": "complete", "trust_class": "authoritative",
        "source": {"snapshot_digest": _SOURCE, "revision": "a" * 40},
        "policy_digest": _POLICY, "scope_digest": _SCOPE,
        "observation_id": "mutation-1", "observed_at": "2026-08-01T00:00:00Z",
        "payload": {"report": "mutation-report.json"},
    }
    values.update(changes)
    return EvidenceArtifact.create(**values)


def _record(**changes):
    now = datetime.now(UTC).replace(microsecond=0)
    values = {
        "actor": "maintainer@example.com",
        "reason": "accepted risk with remediation issue FET-123",
        "timestamp": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "expiry": (now + timedelta(days=7)).isoformat().replace("+00:00", "Z"),
        "check_id": "mutation.score",
        "scope": "fettle/mutation_test.py",
        "revision": "a" * 40,
        "policy_digest": _POLICY,
        "evidence_id": _artifact().artifact_digest,
        "surface": "ci",
        "source_snapshot_digest": _SOURCE,
        "expected_artifact_kind": "fettle.mutation.report",
    }
    values.update(changes)
    return OverrideRecord.create(**values)


def _context(**changes):
    values = {
        "check_id": "mutation.score",
        "scope": "fettle/mutation_test.py",
        "revision": "a" * 40,
        "policy_digest": _POLICY,
        "evidence_id": _artifact().artifact_digest,
        "surface": "ci",
        "source_snapshot_digest": _SOURCE,
        "expected_artifact_kind": "fettle.mutation.report",
        "scope_digest": _SCOPE,
        "producer_id": "fettle.mutation",
        "producer_versions": frozenset({"1.0"}),
        "producer_implementation_digest": _IMPLEMENTATION,
    }
    values.update(changes)
    return OverrideContext(**values)


def test_record_has_content_derived_identity_and_round_trips():
    record = _record(reason="accepted unicode risk: cafe")

    restored = OverrideRecord.from_dict(record.to_dict())

    assert restored == record
    assert record.override_id.startswith("ov-")


@pytest.mark.parametrize(
    "field,value",
    [
        ("actor", ""),
        ("reason", "  "),
        ("expiry", ""),
        ("check_id", ""),
        ("scope", "../outside.py"),
        ("revision", ""),
        ("policy_digest", ""),
        ("evidence_id", ""),
        ("surface", ""),
        ("source_snapshot_digest", ""),
        ("expected_artifact_kind", ""),
    ],
)
def test_record_rejects_missing_or_unsafe_fields(field, value):
    with pytest.raises(ValueError):
        _record(**{field: value})


def test_record_rejects_naive_or_non_increasing_timestamps():
    with pytest.raises(ValueError, match="timezone"):
        _record(timestamp="2026-08-07T10:00:00")
    with pytest.raises(ValueError, match="after timestamp"):
        _record(timestamp="2026-08-07T10:00:00Z", expiry="2026-08-07T10:00:00Z")


def test_record_rejects_tampered_identity():
    data = _record().to_dict()
    data["reason"] = "different"

    with pytest.raises(ValueError, match="override_id"):
        OverrideRecord.from_dict(data)


def test_select_override_requires_exact_context_and_returns_expired_separately():
    active = _record()
    artifact = _artifact()
    assert select_override([active], _context(), artifact=artifact).status == "overridden"
    assert select_override([active], _context(revision="c" * 40), artifact=artifact).status == "wrong_revision"

    expired = _record(
        timestamp="2026-01-01T00:00:00Z",
        expiry="2026-01-02T00:00:00Z",
    )
    result = select_override(
        [expired], _context(), now=datetime(2026, 1, 3, tzinfo=UTC), artifact=_artifact(),
    )
    assert result.status == "expired"
    assert result.record == expired


def test_select_override_rejects_record_before_its_timestamp():
    future = _record(
        timestamp="2027-01-01T00:00:00Z",
        expiry="2027-01-02T00:00:00Z",
    )

    result = select_override(
        [future], _context(), now=datetime(2026, 12, 31, tzinfo=UTC),
        artifact=_artifact(),
    )

    assert result.status == "not_yet_active"
    assert result.record == future


@pytest.mark.parametrize(
    "artifact,status",
    [
        (None, "evidence_missing"),
        (b"not-json", "evidence_malformed"),
        (_artifact(kind="wrong.kind"), "evidence_wrong_kind"),
        (_artifact(source={"snapshot_digest": "sha256:" + "f" * 64, "revision": "a" * 40}), "evidence_wrong_source"),
        (_artifact(policy_digest="sha256:" + "f" * 64), "evidence_wrong_policy"),
        (_artifact(scope_digest="sha256:" + "f" * 64), "evidence_wrong_scope"),
    ],
)
def test_v2_selection_rejects_missing_malformed_or_wrong_bound_evidence(artifact, status):
    assert select_override([_record()], _context(), artifact=artifact).status == status


def test_v2_selection_rejects_tampered_content_and_digest_identity():
    artifact = _artifact()
    tampered = artifact.to_dict()
    tampered["payload"] = {"report": "other.json"}
    assert select_override([_record()], _context(), artifact=tampered).status == "evidence_tampered"


def test_v1_is_readable_but_requires_explicit_legacy_rollback():
    legacy = {
        "schema_version": "1", "override_id": "", "actor": "maintainer@example.com",
        "reason": "rollback", "timestamp": "2026-08-01T00:00:00Z",
        "expiry": "2026-09-01T00:00:00Z", "check_id": "mutation.score",
        "scope": "fettle/mutation_test.py", "revision": "a" * 40,
        "policy_digest": "b" * 64, "evidence_id": "legacy-evidence", "surface": "ci",
    }
    from fettle.overrides import _identity
    legacy["override_id"] = _identity({key: value for key, value in legacy.items() if key != "override_id"})
    record = OverrideRecord.from_dict(legacy)

    assert record.schema_version == "1"
    assert select_override([record], _context(), artifact=_artifact()).status == "not_found"
    rollback = OverrideContext(
        check_id=record.check_id, scope=record.scope, revision=record.revision,
        policy_digest=record.policy_digest, evidence_id=record.evidence_id,
        surface=record.surface, legacy_rollback=True,
    )
    assert select_override([record], rollback, now=datetime(2026, 8, 8, tzinfo=UTC)).status == "overridden"


def test_ledger_reports_invalid_records_instead_of_dropping_them(tmp_path):
    path = tmp_path / ".fettle" / "overrides.json"
    path.parent.mkdir()
    path.write_text(json.dumps({
        "schema_version": "1",
        "overrides": [_record().to_dict(), {"actor": "anonymous"}],
    }))

    ledger = load_override_ledger(tmp_path)

    assert len(ledger.records) == 1
    assert len(ledger.invalid) == 1
    assert "record 1" in ledger.invalid[0]


def test_ledger_rejects_malformed_top_level_and_duplicate_ids(tmp_path):
    path = tmp_path / ".fettle" / "overrides.json"
    path.parent.mkdir()
    path.write_text("not json")
    assert load_override_ledger(tmp_path).invalid

    record = _record()
    path.write_text(json.dumps({"schema_version": "1", "overrides": [record.to_dict()] * 2}))
    assert "duplicate" in load_override_ledger(tmp_path).invalid[0]


def test_save_ledger_is_atomic_and_loadable(tmp_path):
    record = _record()

    save_override_ledger(tmp_path, [record])

    assert load_override_ledger(tmp_path).records == (record,)
    assert list((tmp_path / ".fettle").glob("*.tmp")) == []


def test_summary_distinguishes_active_pending_expired_and_invalid(tmp_path):
    active = _record()
    pending = _record(
        timestamp="2027-01-01T00:00:00Z", expiry="2027-01-02T00:00:00Z",
        check_id="future.check",
    )
    expired = _record(
        timestamp="2026-01-01T00:00:00Z", expiry="2026-01-02T00:00:00Z",
        check_id="old.check",
    )
    path = tmp_path / ".fettle" / "overrides.json"
    path.parent.mkdir()
    path.write_text(json.dumps({
        "schema_version": "1",
        "overrides": [
            active.to_dict(), pending.to_dict(), expired.to_dict(), {"actor": "anonymous"},
        ],
    }))

    summary = summarize_ledger(load_override_ledger(tmp_path))

    assert summary["active_count"] == 1
    assert summary["pending_count"] == 1
    assert summary["expired_count"] == 1
    assert summary["invalid_count"] == 1
    assert summary["pending"][0]["check_id"] == "future.check"
    assert summary["expired"][0]["check_id"] == "old.check"
