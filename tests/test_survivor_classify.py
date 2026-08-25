"""Survivor classifier contract tests (mutation ratchet follow-on)."""

from __future__ import annotations


from fettle.survivor_classify import (
    classify_survivors,
    load_waivers,
    summarize_classification,
)

FP_A = "a" * 64
FP_B = "b" * 64


def _waivers_yaml(*entries: str) -> str:
    return (
        "schema_version: v1\nwaivers:\n"
        + "".join(f"  \"{e.split('|')[0]}\":\n"
                  f"    classification: {e.split('|')[1]}\n"
                  f"    reason: {e.split('|')[2]}\n"
                  f"    decided_by: operator\n" for e in entries)
    )


def test_waiver_round_trip_and_classification():
    waivers, findings = load_waivers(_waivers_yaml(
        f"{FP_A}|equivalent|mkdir flag unobservable when parent exists"
    ))

    assert findings == []
    report = {"non_killed": [{"fingerprint": FP_A}]}
    result = classify_survivors(report, waivers)

    assert result["enforce_ready"] is True
    assert result["behavioral_count"] == 0
    assert result["waived_counts"]["equivalent"] == 1


def test_unwaived_survivor_is_behavioral_and_blocks():
    waivers, _ = load_waivers(_waivers_yaml())
    report = {"non_killed": [{"fingerprint": FP_B}]}

    result = classify_survivors(report, waivers)

    assert result["enforce_ready"] is False
    assert result["behavioral"][0]["fingerprint"] == FP_B


def test_invalid_classification_is_a_finding_not_a_crash():
    waivers, findings = load_waivers(_waivers_yaml(f"{FP_A}|magic|because"))

    assert any("invalid classification" in f["message"] for f in findings)
    # not loaded -> treated as behavioral downstream
    result = classify_survivors({"non_killed": [{"fingerprint": FP_A}]}, waivers)
    assert result["behavioral_count"] == 1


def test_missing_reason_rejected():
    waivers, findings = load_waivers(_waivers_yaml(f"{FP_A}|equivalent|"))

    assert any("no reason" in f["message"] for f in findings)


def test_malformed_yaml_returns_single_finding():
    waivers, findings = load_waivers("::: not yaml :::")

    assert waivers == {}
    assert len(findings) == 1 and "invalid YAML" in findings[0]["message"]


def test_implementation_detail_class_tracked_separately():
    waivers, _ = load_waivers(_waivers_yaml(
        f"{FP_A}|implementation_detail|internal preimage key naming",
        f"{FP_B}|equivalent|whitespace only",
    ))
    report = {"non_killed": [{"fingerprint": FP_A}, {"fingerprint": FP_B}]}

    result = classify_survivors(report, waivers)

    assert result["enforce_ready"] is True
    summary = summarize_classification(result)
    assert "MET" in summary and "0 behavioral" in summary
