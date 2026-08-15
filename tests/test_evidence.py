"""P67 canonical evidence kernel contracts."""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import unicodedata
from collections import OrderedDict
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from fettle.evidence import (
    EvidenceArtifact,
    EvidenceReference,
    EvidenceValidationContext,
    ResultState,
    Validity,
    canonical_json,
    parse_artifact,
    validate_artifact,
)


FIXTURES = Path(__file__).parent / "fixtures" / "evidence"
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64


def _artifact(**changes: object) -> EvidenceArtifact:
    values = {
        "kind": "fettle.verify",
        "producer": {
            "id": "fettle.verify",
            "version": "1.10.0",
            "implementation_digest": SHA_D,
        },
        "result_state": "pass",
        "completeness": "complete",
        "trust_class": "authoritative",
        "source": {"snapshot_digest": SHA_A, "revision": "1" * 40},
        "policy_digest": SHA_B,
        "scope_digest": SHA_C,
        "observation_id": "verify-run-1",
        "observed_at": "2026-08-15T10:00:00Z",
        "payload": {"command": ["python", "-m", "pytest"], "exit_code": 0},
    }
    values.update(changes)
    return EvidenceArtifact.create(**values)


def _context(**changes: object) -> EvidenceValidationContext:
    values = {
        "kind": "fettle.verify",
        "source_snapshot_digest": SHA_A,
        "source_revision": "1" * 40,
        "policy_digest": SHA_B,
        "scope_digest": SHA_C,
        "producer_id": "fettle.verify",
        "producer_versions": frozenset({"1.10.0"}),
        "producer_implementation_digest": SHA_D,
        "require_complete": True,
        "allowed_trust_classes": frozenset({"authoritative"}),
        "recovery_action": "fettle verify",
    }
    values.update(changes)
    return EvidenceValidationContext(**values)


def test_artifact_is_immutable_and_has_separate_content_and_occurrence_identity():
    first = _artifact()
    second = _artifact(
        observation_id="verify-run-2",
        observed_at="2026-08-15T10:01:00Z",
    )

    assert first.artifact_digest == second.artifact_digest
    assert first.observation_id != second.observation_id
    with pytest.raises(FrozenInstanceError):
        first.kind = "other"  # type: ignore[misc]


def test_canonical_identity_is_deterministic_in_another_process():
    artifact = _artifact()
    script = (
        "import json,sys; from fettle.evidence import parse_artifact; "
        "print(parse_artifact(sys.stdin.buffer.read()).artifact_digest)"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        input=artifact.to_bytes(),
        capture_output=True,
        check=True,
    )

    assert completed.stdout.decode().strip() == artifact.artifact_digest


def test_reference_is_sorted_in_parent_projection_and_binds_requested_context():
    later = EvidenceReference(
        artifact_digest="sha256:" + "f" * 64,
        kind="fettle.verify",
        expected={"producer_id": "fettle.verify"},
    )
    earlier = EvidenceReference(
        artifact_digest="sha256:" + "e" * 64,
        kind="fettle.verify",
        expected={"source_snapshot_digest": SHA_A},
    )

    artifact = _artifact(parents=(later, earlier))

    assert artifact.to_dict()["parents"] == [earlier.to_dict(), later.to_dict()]
    assert validate_artifact(artifact, _context()).validity == Validity.VALID


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"source": {"snapshot_digest": "sha256:" + "0" * 64}}, Validity.WRONG_SOURCE),
        ({"policy_digest": "sha256:" + "0" * 64}, Validity.WRONG_POLICY),
        ({"scope_digest": "sha256:" + "0" * 64}, Validity.WRONG_SCOPE),
        ({"completeness": "partial"}, Validity.INCOMPLETE),
    ],
)
def test_consequential_binding_failures_are_typed_non_pass(change, expected):
    artifact = _artifact(**change)

    result = validate_artifact(artifact, _context())

    assert result.validity == expected
    assert result.result_state == ResultState.UNKNOWN
    assert result.recovery_action == "fettle verify"


def test_unknown_producer_version_and_implementation_substitution_fail_closed():
    version = _artifact(producer={
        "id": "fettle.verify", "version": "999.0.0", "implementation_digest": SHA_D,
    })
    implementation = _artifact(producer={
        "id": "fettle.verify", "version": "1.10.0",
        "implementation_digest": "sha256:" + "0" * 64,
    })

    assert validate_artifact(version, _context()).validity == Validity.UNSUPPORTED
    assert validate_artifact(implementation, _context()).validity == Validity.WRONG_PRODUCER


def test_non_pass_artifact_never_maps_to_pass():
    artifact = _artifact(result_state="tool_error", completeness="unknown")

    result = validate_artifact(artifact, _context(require_complete=False))

    assert result.validity == Validity.VALID
    assert result.result_state == ResultState.TOOL_ERROR


def test_missing_and_explicit_invalidation_have_safe_recovery_only():
    missing = validate_artifact(None, _context())
    stale = validate_artifact(_artifact(), _context(invalidated=True))

    assert (missing.validity, missing.result_state) == (
        Validity.MISSING, ResultState.UNKNOWN,
    )
    assert (stale.validity, stale.result_state) == (
        Validity.STALE, ResultState.UNKNOWN,
    )
    assert missing.recovery_action == stale.recovery_action == "fettle verify"


@pytest.mark.parametrize(
    "payload",
    [
        {"value": 1.5},
        {"value": object()},
        {"token": "token=fixture-secret-value"},
        {"path": "/Users/example/project/secret.py"},
        {"path": "../secret.py"},
        {"value": "x" * 65_537},
    ],
)
def test_unsupported_or_sensitive_payloads_are_rejected(payload):
    with pytest.raises(ValueError):
        _artifact(payload=payload)


def test_parser_rejects_noncanonical_bytes_unknown_fields_and_tampering():
    artifact = _artifact()
    noncanonical = json.dumps(artifact.to_dict(), indent=2).encode()
    unknown = artifact.to_dict() | {"unexpected_authority": True}
    tampered = artifact.to_dict()
    tampered["payload"] = {"command": ["python"], "exit_code": 1}

    with pytest.raises(ValueError, match="canonical"):
        parse_artifact(noncanonical)
    with pytest.raises(ValueError, match="fields"):
        parse_artifact(canonical_json(unknown).encode())
    result = validate_artifact(canonical_json(tampered).encode(), _context())
    assert result.validity == Validity.TAMPERED
    assert result.result_state == ResultState.UNKNOWN


def test_parser_accepts_frozen_p66_fixture_as_structured_input():
    fixture = json.loads((FIXTURES / "valid-artifact-v1.json").read_text())

    artifact = parse_artifact(fixture)

    assert artifact.artifact_digest == fixture["artifact_digest"]
    assert artifact.to_dict() == fixture


def test_duplicate_digest_and_observation_identity_fail_closed():
    base = _artifact()
    collision = replace(base, payload={"exit_code": 1})
    duplicate = _artifact(payload={"exit_code": 1})

    assert validate_artifact(
        collision, _context(), registered_artifacts=(base,),
    ).validity == Validity.DIGEST_COLLISION
    assert validate_artifact(
        duplicate, _context(), registered_artifacts=(base,),
    ).validity == Validity.DUPLICATE_ID


def _pointer_parent(value: dict, pointer: str) -> tuple[object, str]:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]
    parent: object = value
    for part in parts[:-1]:
        parent = parent[int(part)] if isinstance(parent, list) else parent[part]
    return parent, parts[-1]


def _set_pointer(value: dict, pointer: str, replacement: object) -> None:
    parent, key = _pointer_parent(value, pointer)
    if isinstance(parent, list):
        parent[int(key)] = replacement
    else:
        parent[key] = replacement


def _fixture_digest(value: dict) -> str:
    content = {
        key: item for key, item in value.items()
        if key not in {"artifact_digest", "observation_id", "observed_at"}
    }
    text = unicodedata.normalize("NFC", json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ))
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _adversarial_input(base: dict, operation: dict) -> tuple[object, bool]:
    value = json.loads(json.dumps(base))
    op = operation["op"]
    if op in {"replace", "add", "collide", "duplicate_observation"}:
        _set_pointer(value, operation["path"], operation["value"])
        if op == "duplicate_observation":
            value["artifact_digest"] = _fixture_digest(value)
        return value, op in {"collide", "duplicate_observation"}
    if op == "generate_string":
        _set_pointer(value, operation["path"], "x" * operation["byte_count"])
    elif op == "generate_nesting":
        nested: object = 0
        for _ in range(operation["depth"]):
            nested = [nested]
        _set_pointer(value, operation["path"], nested)
    elif op == "generate_object":
        _set_pointer(value, operation["path"], {
            f"key-{index}": index for index in range(operation["key_count"])
        })
    elif op == "generate_array":
        _set_pointer(value, operation["path"], list(range(operation["item_count"])))
    elif op == "prefix_bytes":
        return b"\xef\xbb\xbf" + canonical_json(value).encode(), False
    elif op == "reverse_top_level_keys":
        reversed_value = OrderedDict(reversed(list(value.items())))
        return json.dumps(
            reversed_value, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
        ).encode(), False
    elif op == "add_nfc_duplicate_keys":
        canonical = canonical_json(value)
        target = '"payload":{'
        additions = ",".join(
            json.dumps(key, ensure_ascii=False) + ":" + json.dumps(item)
            for key, item in zip(operation["keys"], operation["values"])
        )
        return canonical.replace(target, target + additions + ",", 1).encode(), False
    else:
        raise AssertionError(f"unsupported fixture operation {op}")
    return value, False


def test_frozen_p66_adversarial_corpus_returns_exact_typed_outcomes():
    manifest = json.loads((FIXTURES / "adversarial-v1.json").read_text())
    base_dict = json.loads((FIXTURES / manifest["base_fixture"]).read_text())
    base = parse_artifact(base_dict)
    context = _context(
        source_revision=base.source.get("revision"),
        producer_versions=frozenset({base.producer["version"]}),
        producer_implementation_digest=base.producer["implementation_digest"],
    )

    outcomes = {}
    for case in manifest["cases"]:
        candidate, register_base = _adversarial_input(base_dict, case["operation"])
        result = validate_artifact(
            candidate,
            context,
            registered_artifacts=(base,) if register_base else (),
        )
        outcomes[case["id"]] = result.validity.value
        assert result.result_state == ResultState.UNKNOWN

    assert outcomes == {
        case["id"]: case["expected_validity"] for case in manifest["cases"]
    }
