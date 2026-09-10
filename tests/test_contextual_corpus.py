from fettle.contextual_corpus import (
    _analysis_path,
    _assign_splits,
    _review_packets,
    _subsystem_group,
    apply_owner_decisions,
    combine_collections,
    freeze_reviewed_corpus,
)
import pytest


def _case(case_id, group):
    return {
        "id": case_id,
        "group": group,
        "revision": case_id,
        "subject": "change",
        "changed_paths": [f"fettle/{case_id}.py"],
        "required_universe_digest": "digest",
        "required_universe_count": 2,
        "required_candidate_universe": ["module:required.py", "module:possible.py"],
        "actual_required": ["module:required.py"],
        "candidates": [
            {"stable_key": f"module:{index}.py", "score": index, "depth": 2}
            for index in range(12)
        ],
    }


def test_assign_splits_keeps_groups_isolated_and_balanced():
    cases = [
        _case("a1", "fettle/a"), _case("a2", "fettle/a"),
        _case("b1", "fettle/b"), _case("b2", "fettle/b"),
        _case("c1", "fettle/c"), _case("c2", "fettle/c"),
        _case("d1", "fettle/d"), _case("d2", "fettle/d"),
    ]

    selected = _assign_splits(cases, target_per_split=4)

    assert sum(case["split"] == "development" for case in selected) == 4
    assert sum(case["split"] == "held_out" for case in selected) == 4
    assert all(len({case["split"] for case in selected if case["group"] == group}) == 1
               for group in {case["group"] for case in selected})


def test_review_packets_hide_rank_and_randomize_candidate_order():
    case = {**_case("a1", "fettle/a"), "split": "held_out"}

    packets = _review_packets([case])

    first = packets["glm-reviewer"]["cases"][0]["contextual_candidates"]
    second = packets["ai-reviewer"]["cases"][0]["contextual_candidates"]
    assert [item["stable_key"] for item in first] != [item["stable_key"] for item in second]
    assert all(set(item) == {"stable_key", "relevance", "rationale"} for item in first + second)
    assert "split" not in packets["glm-reviewer"]["cases"][0]
    required = packets["glm-reviewer"]["cases"][0]["required_candidates"]
    assert {item["stable_key"] for item in required} == {
        "module:required.py", "module:possible.py",
    }
    assert packets["glm-reviewer"]["cases"][0]["required_universe_count"] == 2
    assert packets["ai-reviewer"]["independence"] == "fresh-context-blinded"


def test_subsystem_group_is_stable_for_related_modules():
    assert _subsystem_group(["fettle/assurance_record.py"]) == "fettle/assurance"
    assert _subsystem_group(["fettle/assurance.py"]) == "fettle/assurance"
    prefixes = ("src/alpha_os/", "web/src/")
    assert _subsystem_group(["src/alpha_os/agent/core.py"], prefixes) == "src/alpha_os/agent"
    assert _subsystem_group(["web/src/App.tsx"], prefixes) == "web/src/App"


def test_analysis_path_is_relative_to_nested_graph_root():
    assert _analysis_path("backend/core/agent.py", "backend") == "core/agent.py"
    assert _analysis_path("fettle/graph.py", ".") == "fettle/graph.py"


def test_combine_collections_preserves_exact_split_counts_and_isolation():
    first = {"repository": "first", "cases": [
        {**_case("a1", "first/a"), "split": "development"},
        {**_case("b1", "first/b"), "split": "held_out"},
    ]}
    second = {"repository": "second", "cases": [
        {**_case("c1", "second/c"), "split": "development"},
        {**_case("d1", "second/d"), "split": "held_out"},
    ]}

    draft, packets = combine_collections([first, second], target_per_split=2)

    assert draft["repositories"] == ["first", "second"]
    assert sum(case["split"] == "development" for case in draft["cases"]) == 2
    assert sum(case["split"] == "held_out" for case in draft["cases"]) == 2
    assert len(packets["glm-reviewer"]["cases"]) == 4
    assert len(packets["ai-reviewer"]["cases"]) == 4
    assert draft["review_protocol"]["reviewer_roles"] == {
        "ai-reviewer": "ai", "glm-reviewer": "ai",
    }


def test_apply_owner_decisions_requires_exact_unresolved_coverage():
    reconciliation = {
        "schema_version": 1,
        "status": "awaiting_owner_reconciliation",
        "owner": None,
        "summary": {},
        "cases": [{
            "id": "case",
            "required_disagreements": [{
                "stable_key": "module:required.py",
                "owner_decision": None,
                "owner_rationale": None,
            }],
            "contextual_disagreements": [],
        }],
    }

    with pytest.raises(ValueError, match="exactly cover"):
        apply_owner_decisions(reconciliation, [], owner="owner")

    resolved = apply_owner_decisions(reconciliation, [{
        "case_id": "case",
        "kind": "required",
        "stable_key": "module:required.py",
        "decision": True,
        "rationale": "Directly consumes the changed contract.",
    }], owner="owner")

    assert resolved["status"] == "reconciled"
    assert resolved["summary"]["resolved"] == 1
    assert resolved["summary"]["remaining"] == 0
    assert resolved["cases"][0]["required_disagreements"][0]["owner_decision"] is True


def test_freeze_reviewed_corpus_uses_agreement_and_owner_reconciliation():
    case = {**_case("a1", "fettle/a"), "split": "held_out"}
    case["repository_digest"] = "repository"
    case["graph_digest"] = "graph"
    case["provider_digest"] = "provider"
    packets = _review_packets([case])
    for packet in packets.values():
        packet["reviewer_model_class"] = packet["reviewer"]
        reviewed = packet["cases"][0]
        for item in reviewed["required_candidates"]:
            item["required"] = item["stable_key"] == "module:required.py"
            item["rationale"] = "Required review rationale."
        for item in reviewed["contextual_candidates"]:
            item["relevance"] = "relevant"
            item["rationale"] = "Contextual review rationale."
    disputed = packets["glm-reviewer"]["cases"][0]["contextual_candidates"][0]
    disputed["relevance"] = "irrelevant"
    reconciliation = {
        "status": "reconciled",
        "cases": [{
            "id": "a1",
            "required_disagreements": [],
            "contextual_disagreements": [{
                "stable_key": disputed["stable_key"],
                "owner_decision": "irrelevant",
                "owner_rationale": "The apparent connection is only transitive.",
            }],
        }],
    }

    frozen = freeze_reviewed_corpus(case_draft={
        "schema_version": 2,
        "review_protocol": _review_packets([case])["ai-reviewer"] | {
            "reviewers": ["ai-reviewer", "glm-reviewer"],
            "reviewer_roles": {"ai-reviewer": "ai", "glm-reviewer": "ai"},
            "reviewer_model_classes": {"ai-reviewer": "general", "glm-reviewer": "glm"},
            "labeling": "blind-randomized",
            "ai_independence": "fresh-context-blinded",
            "disagreement_resolution": "owner-reconciles-after-both-ai-reviews",
        },
        "target_per_split": 1,
        "cases": [case],
    }, review_packets=list(packets.values()), reconciliation=reconciliation)

    frozen_case = frozen["cases"][0]
    labels = {item["stable_key"]: item for item in frozen_case["candidates"]}
    assert frozen["status"] == "frozen"
    assert frozen_case["ranking_eligible"] is False
    assert frozen_case["required_targets"] == ["module:required.py"]
    assert labels[disputed["stable_key"]]["relevance"] == "irrelevant"
    assert labels[disputed["stable_key"]]["rationale"] == (
        "The apparent connection is only transitive."
    )
    assert len(labels[disputed["stable_key"]]["reviews"]) == 2
    assert frozen_case["oracle_digest"]


def test_freeze_reviewed_corpus_rejects_extraneous_reconciliation():
    case = {**_case("a1", "fettle/a"), "split": "held_out"}
    case.update(repository_digest="repository", graph_digest="graph", provider_digest="provider")
    packets = _review_packets([case])
    for packet in packets.values():
        for item in packet["cases"][0]["required_candidates"]:
            item.update(required=False, rationale="Agreed required rationale.")
        for item in packet["cases"][0]["contextual_candidates"]:
            item.update(relevance="irrelevant", rationale="Agreed contextual rationale.")
    reconciliation = {
        "status": "reconciled",
        "cases": [{
            "id": "a1",
            "required_disagreements": [{
                "stable_key": "module:required.py",
                "owner_decision": True,
                "owner_rationale": "This was not actually disputed.",
            }],
            "contextual_disagreements": [],
        }],
    }
    draft = {
        "schema_version": 2,
        "review_protocol": {
            "reviewer_roles": {"ai-reviewer": "ai", "glm-reviewer": "ai"},
            "reviewer_model_classes": {"ai-reviewer": "general", "glm-reviewer": "glm"},
            "labeling": "blind-randomized",
            "ai_independence": "fresh-context-blinded",
            "disagreement_resolution": "owner-reconciles-after-both-ai-reviews",
        },
        "target_per_split": 1,
        "cases": [case],
    }

    with pytest.raises(ValueError, match="exactly match"):
        freeze_reviewed_corpus(
            case_draft=draft,
            review_packets=list(packets.values()),
            reconciliation=reconciliation,
        )
