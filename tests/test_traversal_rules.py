import json
from pathlib import Path

import pytest

from fettle.overrides import OverrideRecord

from fettle.graph_types import Node
from fettle.provider_contract import Completeness, ProviderFactSet, ProviderRunState, TrustClass
from fettle.traversal_rules import (
    Obligation,
    ObligationDecision,
    ObligationResolution,
    ObligationTemplate,
    RuleSurface,
    TraversalFact,
    TraversalRule,
    TraversalState,
    traverse,
)


def _provider(state=ProviderRunState.PASS, completeness=Completeness.COMPLETE, message="", **overrides):
    values = {
        "provider_id": "imports", "provider_version": "1", "implementation_digest": "impl",
        "config_digest": "config", "input_digest": "input", "run_state": state,
        "completeness": completeness, "completeness_scope": ("python",), "deterministic": True,
        "trust_class": TrustClass.DERIVED, "message": message,
    }
    values.update(overrides)
    return ProviderFactSet(
        **values,
    )


def _rule(**overrides):
    values = {
        "rule_id": "python-impact",
        "version": 1,
        "permitted_edge_types": ("imports",),
        "permitted_roles": ("consumer",),
        "permitted_directions": ("out",),
        "accepted_trust_classes": (TrustClass.DERIVED,),
        "required_provider_ids": ("imports",),
        "trigger_node_kinds": ("file",),
        "change_classes": ("modified", "deleted"),
        "impact_classifications": ("transitive",),
        "obligation_templates": (ObligationTemplate("tests", "run affected tests"),),
        "surfaces": (RuleSurface.ADVISORY,),
        "recovery_command": "fettle impact --full",
        "max_depth": 5,
        "fanout_cap": 5,
        "result_cap": 10,
    }
    values.update(overrides)
    return TraversalRule(**values)


def _fact(source, target, edge):
    return TraversalFact(source, target, edge, "imports", "consumer", "out", "imports", TrustClass.DERIVED)


def test_cycles_terminate_deterministically_regardless_of_insertion_order():
    facts = (_fact("a", "b", "e1"), _fact("b", "a", "e2"))
    first = traverse(("a",), facts, (_provider(),), _rule())
    second = traverse(("a",), tuple(reversed(facts)), (_provider(),), _rule())
    assert first == second
    assert first.state == TraversalState.COMPLETE
    assert first.affected_node_ids == ("b",)
    assert first.provider_completeness == (("imports", "pass", "complete"),)
    assert len(first.obligation_ids) == 1


def test_missing_or_partial_required_provider_returns_unknown():
    missing = traverse(("a",), (), (), _rule())
    partial = traverse(
        ("a",), (),
        (_provider(ProviderRunState.UNKNOWN, Completeness.PARTIAL, "unsupported syntax"),),
        _rule(),
    )
    assert missing.state == TraversalState.UNKNOWN
    assert partial.state == TraversalState.UNKNOWN


def test_fanout_and_result_limits_are_explicit_non_complete_states():
    facts = tuple(_fact("a", target, f"e{target}") for target in ("b", "c", "d"))
    closure = traverse(("a",), facts, (_provider(),), _rule(fanout_cap=2, result_cap=1))
    assert closure.state == TraversalState.LIMIT_REACHED
    assert closure.reason
    assert len(closure.affected_node_ids) == 1


def test_conflicting_provider_fact_sets_return_unknown():
    conflict = ProviderFactSet(
        "imports", "2", "other-impl", "config", "input", ProviderRunState.PASS,
        Completeness.COMPLETE, ("python",), True, TrustClass.DERIVED,
    )
    closure = traverse(("a",), (), (_provider(), conflict), _rule())
    assert closure.state == TraversalState.UNKNOWN
    assert "conflicting provider fact sets" in closure.reason

    duplicate = traverse(("a",), (), (_provider(), _provider()), _rule())
    assert duplicate.state == TraversalState.COMPLETE


def test_obligation_identity_is_stable_but_resolution_requires_complete_evidence():
    obligation = Obligation.create("tests", "test:api", "impact-digest", "run contract tests")
    reordered = Obligation.create("tests", "test:api", "impact-digest", "run contract tests")
    assert obligation.id == reordered.id

    verified = ObligationDecision.create(
        obligation.id, ObligationResolution.VERIFIED_UNCHANGED, evidence_id="evidence-1",
    )
    assert verified.id != obligation.id

    with pytest.raises(ValueError, match="requires evidence"):
        ObligationDecision.create(obligation.id, ObligationResolution.VERIFIED_UNCHANGED)
    with pytest.raises(ValueError, match="requires a reason"):
        ObligationDecision.create(obligation.id, ObligationResolution.NOT_APPLICABLE)


def test_override_resolution_is_bound_to_actor_policy_graph_and_expiry():
    with pytest.raises(ValueError, match="override record"):
        ObligationDecision.create(
            "obligation", ObligationResolution.OVERRIDDEN,
        )

    override = OverrideRecord.create(
        actor="maintainer", reason="accepted risk", timestamp="2026-08-01T00:00:00Z",
        expiry="2026-09-01T00:00:00Z", revision="abc123",
        policy_digest="sha256:" + "a" * 64,
        evidence_id="sha256:" + "b" * 64, check_id="change-integrity.obligation",
        scope="obligations/obligation", surface="ci",
        source_snapshot_digest="sha256:" + "c" * 64,
        expected_artifact_kind="fettle.change-integrity",
    )
    decision = ObligationDecision.create(
        "obligation", ObligationResolution.OVERRIDDEN, override=override, graph_digest="graph",
    )
    assert decision.resolution == ObligationResolution.OVERRIDDEN
    assert decision.override_id == override.override_id


def test_traversal_rule_requires_triggers_outputs_surface_and_recovery():
    for field, value in (
        ("trigger_node_kinds", ()), ("change_classes", ()), ("impact_classifications", ()),
        ("surfaces", ()), ("recovery_command", ""),
    ):
        with pytest.raises(ValueError):
            _rule(**{field: value})
    with pytest.raises(ValueError, match="directions"):
        _rule(permitted_directions=("sideways",))
    with pytest.raises(ValueError, match="fact fields"):
        TraversalFact("", "target", "edge", "imports", "consumer", "out", "imports", TrustClass.DERIVED)


def test_fixture_corpus_exercises_each_adversarial_case():
    fixture_dir = Path(__file__).parent / "fixtures" / "change_integrity"
    fixtures = {path.name: json.loads(path.read_text()) for path in fixture_dir.glob("*.json")}
    assert fixtures["duplicate-facts.json"]["expected"] == ["fact-a", "fact-b"]
    assert fixtures["cycle.json"]["expected"] == ["b"]
    assert {case["provider"] for case in fixtures["provider-failures.json"]["cases"]} == {
        "missing", "partial", "conflicting",
    }
    assert fixtures["malformed-attributes.json"]["expected"] == "reject_noncanonical"
    assert fixtures["oversized-output.json"]["expected_state"] == "limit_reached"
    assert {entry["object_type"] for entry in fixtures["source-entry-variants.json"]["entries"]} == {
        "symlink", "gitlink", "tombstone",
    }

    duplicate = fixtures["duplicate-facts.json"]
    assert _provider(fact_ids=tuple(duplicate["facts"])).fact_ids == tuple(duplicate["expected"])

    cycle = fixtures["cycle.json"]
    cycle_facts = tuple(_fact(source, target, f"e{index}") for index, (source, target) in enumerate(cycle["facts"]))
    assert list(traverse(tuple(cycle["changed"]), cycle_facts, (_provider(),), _rule()).affected_node_ids) == cycle["expected"]

    malformed = fixtures["malformed-attributes.json"]
    with pytest.raises(ValueError, match="canonical JSON object"):
        Node("id", "file", "a.py", malformed["attributes_json"], ())
