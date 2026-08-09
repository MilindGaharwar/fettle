"""P66 portable evidence contract and adversarial fixture freeze."""

import hashlib
import json
import unicodedata
from pathlib import Path


ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "evidence"


def _content_digest(artifact: dict) -> str:
    content = {
        key: value for key, value in artifact.items()
        if key not in {"artifact_digest", "observation_id", "observed_at"}
    }
    canonical = json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    canonical = unicodedata.normalize("NFC", canonical)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def test_p66_contract_freezes_required_sections_and_runtime_boundary():
    contract = (ROOT / "docs" / "evidence-artifact-contract.md").read_text()

    for section in (
        "## Representation Inventory",
        "## EvidenceArtifact Schema V1",
        "## EvidenceReference V2",
        "## Canonical Encoding And Bounds",
        "## Validity And Consequential Mapping",
        "## Compatibility Matrix",
        "## Threat Model",
    ):
        assert section in contract
    assert "does not change any current writer" in contract
    assert "No validity failure maps to pass" in contract


def test_p66_examples_have_frozen_artifact_and_reference_fields():
    artifact = json.loads((FIXTURES / "valid-artifact-v1.json").read_text())
    reference = json.loads((FIXTURES / "valid-reference-v2.json").read_text())

    assert set(artifact) == {
        "schema_version", "artifact_digest", "kind", "producer", "result_state",
        "completeness", "trust_class", "source", "policy_digest", "scope_digest",
        "observation_id", "observed_at", "payload",
    }
    assert set(reference) == {"artifact_digest", "kind", "schema_version", "expected"}
    assert set(reference["expected"]) == {
        "source_snapshot_digest", "policy_digest", "scope_digest", "producer_id",
    }
    assert artifact["artifact_digest"] == reference["artifact_digest"]
    assert artifact["artifact_digest"] == _content_digest(artifact)

    with_parent = dict(artifact, parents=[reference])
    assert _content_digest(with_parent) != artifact["artifact_digest"]


def test_p66_adversarial_manifest_covers_every_frozen_threat_case():
    manifest = json.loads((FIXTURES / "adversarial-v1.json").read_text())
    cases = manifest["cases"]

    assert manifest["schema_version"] == "1"
    assert manifest["contract"] == "docs/evidence-artifact-contract.md"
    assert manifest["base_fixture"] == "valid-artifact-v1.json"
    assert manifest["execution_mode"] == "isolated_with_base_registered"
    assert manifest["expected_context"] == "base_artifact_bindings"
    assert {case["id"] for case in cases} == {
        "digest-collision-injection", "content-tampering", "duplicate-observation-id",
        "replay-another-revision", "policy-mismatch", "scope-mismatch",
        "partial-evidence", "unknown-producer-version", "producer-implementation-mismatch",
        "unknown-top-level-field", "oversized-payload", "absolute-path-leakage",
        "unicode-key-ambiguity", "embedded-secret", "byte-order-mark",
        "noncanonical-key-order", "floating-point-number", "oversized-string",
        "excessive-nesting", "excessive-object-keys", "excessive-array-items",
    }
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(case["operation"]["op"] in {
        "add", "add_nfc_duplicate_keys", "collide", "duplicate_observation",
        "generate_array", "generate_nesting", "generate_object", "generate_string",
        "prefix_bytes", "replace", "reverse_top_level_keys",
    } for case in cases)
    assert all(case["expected_result_state"] == "unknown" for case in cases)
    assert all(case["expected_validity"] != "valid" for case in cases)
