"""P38 contract tests — canonical traceability and drift evidence."""

from __future__ import annotations

from fettle.trace_canonical import (
    bind_results,
    build_trace_index,
    collect_test_markers,
    drift_evidence,
    validate_markers,
)
from fettle.trace_requirements import trace_requirements

SPEC_TEXT = """---
fettle-spec: v1
id: checkout-flow
status: active
scope:
  - "src/checkout/**"
---

## Requirements

- R1. Checkout completes for valid carts.

## Scenarios

### S1. Valid cart checks out (traces R1)
Given a valid cart
When the user checks out
Then the order is placed

### S2. Expired card is rejected
Given an expired card
When the user pays
Then checkout fails
"""

MARKERED_TEST = '''\
def test_checkout_ok():
    # traces: checkout-flow/S1
    assert True
'''

GHOST_TEST = '''\
def test_ghost():
    # traces: ghost-spec/S9
    assert True
'''


def _write_spec(root):
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "checkout.md").write_text(SPEC_TEXT, encoding="utf-8")


def _write_tests(root):
    (root / "tests_t").mkdir(exist_ok=True)
    (root / "tests_t" / "test_checkout.py").write_text(MARKERED_TEST, encoding="utf-8")


def _make_repo(tmp_path):
    _write_spec(tmp_path)
    _write_tests(tmp_path)


def test_index_uses_stable_ids_and_requirement_links(tmp_path):
    _make_repo(tmp_path)

    first = build_trace_index(str(tmp_path))
    second = build_trace_index(str(tmp_path))

    assert list(first) == ["checkout-flow/S1", "checkout-flow/S2"]
    assert first == second
    assert first["checkout-flow/S1"].requirement_ids == ["R1"]
    assert first["checkout-flow/S1"].spec_path == "docs/checkout.md"


def test_markers_resolve_and_unknowns_are_reported(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "tests_t" / "test_ghost.py").write_text(GHOST_TEST, encoding="utf-8")

    markers, _ = collect_test_markers(str(tmp_path))
    unknown = validate_markers(build_trace_index(str(tmp_path)), markers)

    assert markers["checkout-flow/S1"] == ["tests_t/test_checkout.py"]
    assert markers["ghost-spec/S9"] == ["tests_t/test_ghost.py"]
    assert unknown == ["ghost-spec/S9"]


def test_declaration_is_linked_but_only_a_pass_verifies(tmp_path):
    _make_repo(tmp_path)

    index = build_trace_index(str(tmp_path))
    markers, _ = collect_test_markers(str(tmp_path))
    coverage = bind_results(
        index,
        markers,
        {
            "tests_t/test_checkout.py": "passed",
            "tests_t/test_ghost.py": "skipped",
        },
    )

    assert coverage["checkout-flow/S1"]["verified"] == 1
    assert coverage["checkout-flow/S2"] == {"linked": 0, "verified": 0, "executed": 0}


def test_failing_or_skipped_marker_never_verifies(tmp_path):
    _make_repo(tmp_path)

    index = build_trace_index(str(tmp_path))
    markers, _ = collect_test_markers(str(tmp_path))
    coverage = bind_results(
        index, markers, {"tests_t/test_checkout.py": "failed"}
    )

    assert coverage["checkout-flow/S1"]["linked"] == 1
    assert coverage["checkout-flow/S1"]["verified"] == 0


def test_governed_change_without_review_produces_advisory(tmp_path):
    _make_repo(tmp_path)

    report = drift_evidence(
        str(tmp_path),
        changed_paths={"src/checkout/pay.py"},
        results={"tests_t/test_checkout.py": "passed"},
    )

    assert report["governed_without_review"] == ["src/checkout/pay.py"]
    assert report["advisories"][0]["rule"] == "TRACE_DRIFT"
    assert report["uncovered_scenarios"] == ["checkout-flow/S2"]
    assert report["unknown_markers"] == []
    assert report["executed_coverage"]["verified"] == ["checkout-flow/S1"]


def test_spec_change_or_audit_review_clears_drift(tmp_path):
    _make_repo(tmp_path)

    via_spec = drift_evidence(
        str(tmp_path),
        changed_paths={"src/checkout/pay.py", "docs/checkout.md"},
    )
    via_audit = drift_evidence(
        str(tmp_path), changed_paths={"src/checkout/pay.py"}, audit_reviewed=True
    )

    assert via_spec["governed_without_review"] == []
    assert via_audit["governed_without_review"] == []
    assert via_spec["changed_governed_specs"] == ["checkout-flow"]
    assert via_audit["changed_governed_specs"] == []


def test_ghost_marked_test_counts_as_orphan(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "tests_t" / "test_ghost.py").write_text(GHOST_TEST, encoding="utf-8")

    report = drift_evidence(str(tmp_path), changed_paths=set())

    assert report["orphan_tests"] == ["tests_t/test_ghost.py"]
    assert report["unknown_markers"] == ["ghost-spec/S9"]


def test_filename_inference_is_deprecated_but_functional(tmp_path):
    _make_repo(tmp_path)
    legacy = tmp_path / "tests_t" / "test_docs_checkout.py"
    legacy.write_text("def test_any():\n    assert True\n", encoding="utf-8")

    cfg = {"spec_patterns": ["docs/*.md"], "test_roots": ["tests_t"]}
    modern = trace_requirements(str(tmp_path), cfg)
    legacy_cfg = dict(cfg, naming_convention=True)
    deprecated = trace_requirements(str(tmp_path), legacy_cfg)

    assert modern.get("deprecated", False) is False
    assert deprecated["deprecated"] is True
    assert "deprecated" in deprecated["deprecation"]
