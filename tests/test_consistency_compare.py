"""P56a typed comparison contracts."""

from __future__ import annotations

import pytest

from fettle.consistency_compare import ComparisonError, fingerprint_value


def test_exact_comparison_preserves_json_type_and_value():
    integer = fingerprint_value(1, "exact")
    boolean = fingerprint_value(True, "exact")
    string = fingerprint_value("1", "exact")

    assert integer != boolean
    assert integer != string
    assert boolean != string


def test_normalized_comparison_applies_unicode_nfc_recursively():
    decomposed = {"cafe\u0301": ["A\u030a"]}
    composed = {"caf\u00e9": ["\u00c5"]}

    assert fingerprint_value(decomposed, "normalized") == fingerprint_value(
        composed, "normalized"
    )
    assert fingerprint_value(decomposed, "exact") != fingerprint_value(composed, "exact")


def test_normalized_comparison_does_not_coerce_or_fold_values():
    assert fingerprint_value("  VALUE  ", "normalized") != fingerprint_value(
        "value", "normalized"
    )
    assert fingerprint_value(1, "normalized") != fingerprint_value("1", "normalized")


def test_normalized_object_rejects_colliding_keys():
    with pytest.raises(ComparisonError, match="same NFC form"):
        fingerprint_value({"caf\u00e9": 1, "cafe\u0301": 2}, "normalized")


def test_unknown_comparator_is_rejected():
    with pytest.raises(ComparisonError, match="unsupported comparator"):
        fingerprint_value("value", "subset")
