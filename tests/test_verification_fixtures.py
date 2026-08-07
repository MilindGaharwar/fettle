"""P35 seeded-defect fixture manifest contracts."""

import json

import pytest

from fettle.verification_fixtures import (
    BUILTIN_RUNNERS,
    FixtureOutcome,
    evaluate_manifest,
    load_manifests,
    validate_manifest,
)


def _manifest(**changes):
    value = {
        "schema_version": "1",
        "check_id": "quality.scan",
        "owner": "quality-team",
        "runner": "quality-scan",
        "clean_fixture": "clean",
        "defect_fixture": "known-bad",
        "prior_suite_expected": "pass",
        "expected_state": "violation",
        "expected_finding_code": "F401",
        "max_runtime_ms": 1000,
        "rerun_command": "fettle verification check quality.scan",
    }
    value.update(changes)
    return value


def test_manifest_requires_complete_bounded_contract(tmp_path):
    fixture_root = tmp_path / "case"
    (fixture_root / "clean").mkdir(parents=True)
    (fixture_root / "known-bad").mkdir()

    manifest = validate_manifest(_manifest(), fixture_root)

    assert manifest.check_id == "quality.scan"
    assert manifest.max_runtime_ms == 1000


@pytest.mark.parametrize(
    "field,value",
    [
        ("check_id", ""),
        ("owner", ""),
        ("runner", ""),
        ("prior_suite_expected", "violation"),
        ("expected_state", "pass"),
        ("expected_finding_code", ""),
        ("max_runtime_ms", 0),
        ("rerun_command", ""),
        ("clean_fixture", "../escape"),
    ],
)
def test_manifest_rejects_missing_invalid_and_unsafe_fields(tmp_path, field, value):
    with pytest.raises(ValueError):
        validate_manifest(_manifest(**{field: value}), tmp_path)


def test_manifest_requires_both_fixture_directories(tmp_path):
    (tmp_path / "clean").mkdir()
    with pytest.raises(ValueError, match="defect fixture"):
        validate_manifest(_manifest(), tmp_path)


def test_manifest_discovery_surfaces_malformed_files(tmp_path):
    valid = tmp_path / "valid"
    (valid / "clean").mkdir(parents=True)
    (valid / "known-bad").mkdir()
    (valid / "manifest.json").write_text(json.dumps(_manifest()))
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "manifest.json").write_text("not json")

    result = load_manifests(tmp_path)

    assert [item.check_id for item in result.manifests] == ["quality.scan"]
    assert len(result.errors) == 1


def test_promoted_checks_require_unique_manifests(tmp_path):
    result = load_manifests(tmp_path, promoted_check_ids={"quality.scan"})
    assert result.errors == ("promoted check 'quality.scan' has no seeded-defect manifest",)


def test_conformance_requires_prior_miss_clean_pass_and_defect_finding(tmp_path):
    (tmp_path / "clean").mkdir()
    (tmp_path / "known-bad").mkdir()
    manifest = validate_manifest(_manifest(), tmp_path)

    outcomes = {
        "prior": FixtureOutcome("pass"),
        "clean": FixtureOutcome("pass"),
        "defect": FixtureOutcome("violation", ("F401",)),
    }
    result = evaluate_manifest(manifest, lambda _manifest, phase, _path: outcomes[phase])

    assert result.status == "pass"
    assert result.errors == ()


@pytest.mark.parametrize(
    "phase,outcome,expected",
    [
        ("prior", FixtureOutcome("violation", ("F401",)), "preceding assurance layer"),
        ("clean", FixtureOutcome("violation", ("F401",)), "clean fixture"),
        ("defect", FixtureOutcome("pass"), "known-bad fixture"),
        ("defect", FixtureOutcome("violation", ("OTHER",)), "expected finding"),
        ("defect", FixtureOutcome("tool_error"), "tool_error"),
    ],
)
def test_conformance_fails_closed_for_wrong_or_indeterminate_outcomes(
    tmp_path, phase, outcome, expected,
):
    (tmp_path / "clean").mkdir()
    (tmp_path / "known-bad").mkdir()
    manifest = validate_manifest(_manifest(), tmp_path)
    outcomes = {
        "prior": FixtureOutcome("pass"),
        "clean": FixtureOutcome("pass"),
        "defect": FixtureOutcome("violation", ("F401",)),
    }
    outcomes[phase] = outcome

    result = evaluate_manifest(manifest, lambda _manifest, current, _path: outcomes[current])

    assert result.status == "violation"
    assert expected in result.errors[0]


def test_conformance_rejects_unregistered_runner_and_runtime_overrun(tmp_path):
    (tmp_path / "clean").mkdir()
    (tmp_path / "known-bad").mkdir()
    manifest = validate_manifest(_manifest(max_runtime_ms=1), tmp_path)

    missing = evaluate_manifest(manifest, {})
    slow = evaluate_manifest(
        manifest,
        {"quality-scan": lambda _manifest, _phase, _path: FixtureOutcome("pass", duration_ms=2)},
    )

    assert missing.status == "tool_error"
    assert "not registered" in missing.errors[0]
    assert slow.status == "violation"
    assert "runtime" in slow.errors[0]


def test_committed_promoted_ci_fixture_proves_seeded_defect():
    root = __import__("pathlib").Path(__file__).parent / "fixtures" / "verification"
    result = load_manifests(root, promoted_check_ids={"ci.verdict"})

    assert result.errors == ()
    assert len(result.manifests) == 1
    assert evaluate_manifest(result.manifests[0], BUILTIN_RUNNERS).status == "pass"
