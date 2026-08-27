"""P53/SC1 contract tests — frozen state-consistency schema + fixtures."""

from __future__ import annotations

from fettle.state_consistency import (
    TEMPLATE_V1,
    discover_contracts,
    lint_contract_text,
    parse_contract,
    validate_executable_contract,
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


def test_consistency_timing_must_be_bounded_and_poll_within_deadline():
    broken = VALID.replace(
        "deadline_ms: 30000\n  poll_interval_ms: 1000",
        "deadline_ms: 300001\n  poll_interval_ms: 300002",
    )

    contract, findings = parse_contract(broken)

    assert contract is None
    messages = " | ".join(f.message for f in findings)
    assert "deadline_ms" in messages
    assert "poll_interval_ms" in messages


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


EXECUTABLE = VALID + """\
adapters:
  rename_customer:
    kind: command
    argv: ["scripts/customer.py", "rename"]
    cwd: "."
    env: ["FETTLE_SUBJECT_ID"]
    timeout_s: 10
    output: json-v1
  read_customer:
    kind: command
    argv: ["scripts/customer.py", "read"]
    timeout_s: 5
    output: json-v1
  read_checkout_customer:
    kind: command
    argv: ["scripts/checkout.py", "read"]
    timeout_s: 5
    output: json-v1
  delete_test_customer:
    kind: command
    argv: ["scripts/customer.py", "delete"]
    timeout_s: 10
    output: json-v1
"""


def test_executable_contract_retains_phase_and_adapter_manifests():
    contract, findings = parse_contract(EXECUTABLE)

    assert contract is not None, [finding.message for finding in findings]
    assert contract.mutation_adapter == "rename_customer"
    assert contract.canonical_read_adapter == "read_customer"
    assert contract.cleanup_adapter == "delete_test_customer"
    assert contract.observers[0]["adapter"] == "read_checkout_customer"
    assert contract.adapters["rename_customer"].argv == (
        "scripts/customer.py", "rename",
    )
    assert validate_executable_contract(contract) == []


def test_executable_validation_requires_phases_and_referenced_adapters():
    contract, findings = parse_contract(VALID)

    assert contract is not None, [finding.message for finding in findings]
    messages = " | ".join(
        finding.message for finding in validate_executable_contract(contract)
    )
    assert "mutation adapter" in messages
    assert "canonical-read adapter" in messages
    assert "cleanup adapter" in messages
    assert "read_checkout_customer" in messages


def test_adapter_manifest_rejects_shell_strings_paths_secrets_and_unknown_fields():
    unsafe = EXECUTABLE.replace(
        'argv: ["scripts/customer.py", "rename"]',
        'argv: "python scripts/customer.py rename"',
    ).replace('cwd: "."', 'cwd: "../outside"', 1).replace(
        'env: ["FETTLE_SUBJECT_ID"]', 'env: ["TOKEN=secret"]',
    ).replace("output: json-v1", "output: json-v1\n    surprise: true", 1)

    contract, findings = parse_contract(unsafe)

    assert contract is None
    messages = " | ".join(finding.message for finding in findings)
    assert "argv" in messages
    assert "repository-relative" in messages
    assert "environment variable names" in messages
    assert "unknown key" in messages


def test_adapter_manifest_rejects_unbounded_argv_and_observers():
    too_many_args = ", ".join('"x"' for _ in range(65))
    too_many_observers = ", ".join(
        f"{{id: observer-{index}, surface: api, adapter: read_customer}}"
        for index in range(65)
    )
    unsafe = EXECUTABLE.replace(
        '["scripts/customer.py", "rename"]', f"[{too_many_args}]",
    ).replace(
        "  - id: checkout\n    surface: api\n    adapter: read_checkout_customer",
        f"  [{too_many_observers}]",
    )

    contract, findings = parse_contract(unsafe)

    assert contract is None
    messages = " | ".join(finding.message for finding in findings)
    assert "at most 64 items" in messages
    assert "at most 64 observers" in messages


def test_discovery_is_deterministic_skips_tool_dirs_and_rejects_duplicate_ids(tmp_path):
    (tmp_path / "b.md").write_text(VALID, encoding="utf-8")
    (tmp_path / "a.md").write_text(
        VALID.replace("customer-name-propagates", "account-name-propagates"),
        encoding="utf-8",
    )
    ignored = tmp_path / ".git"
    ignored.mkdir()
    (ignored / "ignored.md").write_text(VALID, encoding="utf-8")

    discovered, findings = discover_contracts(tmp_path)

    assert [item.path.name for item in discovered] == ["a.md", "b.md"]
    assert findings == []

    (tmp_path / "c.md").write_text(VALID, encoding="utf-8")
    _discovered, findings = discover_contracts(tmp_path)
    assert any("duplicate contract id" in finding.message for finding in findings)


def test_discovery_ignores_embedded_contract_examples(tmp_path):
    (tmp_path / "plan.md").write_text(
        "# Plan\n\n```yaml\nfettle-consistency: v1\nid: example\n```\n",
        encoding="utf-8",
    )

    discovered, findings = discover_contracts(tmp_path)

    assert discovered == []
    assert findings == []
