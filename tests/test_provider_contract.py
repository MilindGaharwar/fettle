import pytest

from fettle.provider_contract import (
    Completeness,
    ProviderDeclaration,
    ProviderFactSet,
    ProviderLimits,
    ProviderRunState,
    TrustClass,
)


def _fact_set(**overrides):
    values = {
        "provider_id": "python-imports",
        "provider_version": "1.0.0",
        "implementation_digest": "impl",
        "config_digest": "config",
        "input_digest": "input",
        "run_state": ProviderRunState.PASS,
        "completeness": Completeness.COMPLETE,
        "completeness_scope": ("python",),
        "deterministic": True,
        "trust_class": TrustClass.DERIVED,
    }
    values.update(overrides)
    return ProviderFactSet(**values)


def test_provider_fact_identity_is_independent_of_fact_order():
    assert _fact_set(fact_ids=("b", "a")).id == _fact_set(fact_ids=("a", "b")).id


def test_partial_provider_cannot_be_represented_as_success():
    with pytest.raises(ValueError, match="must be complete"):
        _fact_set(completeness=Completeness.PARTIAL)


@pytest.mark.parametrize("state", [ProviderRunState.TOOL_ERROR, ProviderRunState.UNKNOWN])
def test_failed_or_unknown_provider_requires_diagnostic(state):
    with pytest.raises(ValueError, match="require a message"):
        _fact_set(run_state=state, completeness=Completeness.UNKNOWN)


def test_non_applicable_provider_cannot_emit_facts():
    with pytest.raises(ValueError, match="cannot be complete or emit facts"):
        _fact_set(run_state=ProviderRunState.NOT_APPLICABLE, completeness=Completeness.UNKNOWN, fact_ids=("fact",))


def test_provider_fact_set_collapses_equivalent_duplicate_facts():
    assert _fact_set(fact_ids=("fact", "fact")).fact_ids == ("fact",)


def test_provider_declaration_captures_applicability_inputs_outputs_and_bounds():
    limits = ProviderLimits(1000, 100, 1_000_000, 1000, 500, 500, 1000, 4096, 20, 8192)
    declaration = ProviderDeclaration(
        "python-imports", "1.0.0", "impl", "platform", TrustClass.DERIVED, True,
        ("file",), ("python",), ("python",), ("tracked", "config"), ("pyproject.toml",),
        ("PYTHONPATH",), ("node:symbol",), ("edge:imports",), ("incidence:consumer",),
        "path suffix .py", "canonical byte order", "full rebuild", "emit deletion facts", limits,
    )
    assert declaration.environment_allowlist == ("PYTHONPATH",)
    assert len(declaration.digest) == 64


def test_provider_declaration_rejects_missing_applicability_or_output_contracts():
    limits = ProviderLimits(1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
    with pytest.raises(ValueError, match="applicability"):
        ProviderDeclaration(
            "provider", "1", "impl", "owner", TrustClass.DERIVED, True,
            (), (), (), ("tracked",), (), (), ("node:file",), (), (),
            "all", "canonical", "full", "tombstones", limits,
        )


def test_non_success_provider_cannot_claim_complete_or_emit_facts():
    for state in (ProviderRunState.TOOL_ERROR, ProviderRunState.UNKNOWN, ProviderRunState.NOT_APPLICABLE):
        with pytest.raises(ValueError):
            _fact_set(run_state=state, completeness=Completeness.COMPLETE, fact_ids=("fact",), message="failed")
