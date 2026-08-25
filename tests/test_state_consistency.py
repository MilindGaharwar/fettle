"""P53/SC1 contract tests — frozen state-consistency schema + fixtures."""

from __future__ import annotations

from fettle.state_consistency import (
    TEMPLATE_V1,
    lint_contract_text,
    parse_contract,
)

VALID = """\
fettle-consistency: v1
id: customer-name-propagates
title: Customer name propagates to checkout
scope:
  - "app/customer/**"
  - "app/checkout/**"
fact: customer.display_name
owner: customer-service
consistency:
  model: immediate
  deadline_ms: 30000
  poll_interval_ms: 1000
mutation:
  adapter: rename_customer
  retry_safe: false
canonical_read:
  adapter: read_customer
observers:
  - id: checkout
    surface: api
    adapter: read_checkout_customer
comparator:
  kind: normalized
cleanup:
  adapter: delete_test_customer
redaction:
  retain_values: false
"""


def test_valid_contract_parses_with_identity():
    contract, findings = parse_contract(VALID)

    assert contract is not None, [f.message for f in findings]
    assert findings == []
    assert contract.id == "customer-name-propagates"
    assert contract.model == "immediate"
    assert len(contract.observers) == 1
    assert len(contract.digest) == 64


def test_identity_is_canonical_across_formatting():
    reformatted = VALID.replace("deadline_ms: 30000", "deadline_ms:   30000")

    first, _ = parse_contract(VALID)
    second, _ = parse_contract(reformatted)

    assert first.digest == second.digest


def test_comparator_change_alters_identity():
    mutated = VALID.replace("kind: normalized", "kind: exact")

    base, _ = parse_contract(VALID)
    changed, _ = parse_contract(mutated)

    assert base.digest != changed.digest


def test_unknown_top_level_key_rejected():
    mutated = VALID + "\nsecret_sauce: yes\n"

    findings = lint_contract_text(mutated)

    assert any("unknown top-level key" in f["message"] for f in findings)


def test_missing_fact_and_bad_model_produce_errors():
    broken = "fettle-consistency: v1\nid: bad\nowner: x\nconsistency:\n  model: magic\n"

    findings = lint_contract_text(broken)

    messages = " | ".join(f["message"] for f in findings)
    assert "missing required key 'fact'" in messages
    assert "consistency.model" in messages


def test_template_parses_after_placeholder_fill():
    filled = (TEMPLATE_V1
              .replace("<kebab-case-contract-id>", "demo-contract")
              .replace("<human title>", "Demo")
              .replace("<governed/path/**>", "src/**")
              .replace("<dotted.fact.path>", "a.b")
              .replace("<owning-service>", "svc")
              .replace("<adapter-name>", "adapter_x")
              .replace("<view-name>", "view"))
    # template has no trailing --- separator; add one like a real document
    filled = filled.rstrip("-").rstrip() + "\n"

    contract, findings = parse_contract(filled)

    assert contract is not None, [f.message for f in findings]
    assert findings == []


def test_lint_shape_matches_house_findings():
    findings = lint_contract_text("not: a contract")

    assert findings
    assert all(set(f) >= {"severity", "message", "fix"} for f in findings)
