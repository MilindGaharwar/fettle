from dataclasses import replace

from fettle.contextual_impact import adapt_graph_facts, analyze_contextual_impact
from fettle.graph_types import canonical_digest
from fettle.hypergraph import assemble
from fettle.provider_contract import TrustClass
from fettle.providers.base import EdgeDraft, NodeDraft, ProviderResult


def _provider(provider_id, edges, *, trust=TrustClass.DERIVED, complete=True):
    nodes = tuple(
        NodeDraft("module", key) for key in sorted({key for edge in edges for key in edge[1:]})
    )
    return ProviderResult(
        provider_id,
        nodes,
        tuple(EdgeDraft(*edge) for edge in edges),
        complete,
        provider_version="1",
        implementation_digest=canonical_digest({"provider": provider_id, "version": 1}),
        deterministic=True,
        trust_class=trust,
        completeness_scope=("repository",),
    )


def _graph(results):
    return assemble(".", results, "snapshot", {"version": 1})


def test_adapter_preserves_duplicate_provider_ownership_regardless_of_order():
    first = _provider("imports-a", [("imports", "module:a", "module:b")])
    second = _provider("imports-b", [("imports", "module:a", "module:b")])

    left = adapt_graph_facts(_graph((first, second)))
    right = adapt_graph_facts(_graph((second, first)))

    assert left == right
    assert {fact.provider_id for fact in left.facts} == {"imports-a", "imports-b"}
    assert len(left.provider_fact_sets) == 2
    assert all(item.fact_ids for item in left.provider_fact_sets)
    assert not left.rejections


def test_adapter_does_not_fabricate_missing_provider_metadata():
    provider = _provider("imports", [("imports", "module:a", "module:b")])
    provider = replace(provider, implementation_digest="")

    adapted = adapt_graph_facts(_graph((provider,)))

    assert not adapted.facts
    assert not adapted.provider_fact_sets
    assert adapted.state == "unknown"
    assert adapted.rejections[0].reason == "missing_provider_metadata"


def test_adapter_marks_incomplete_provider_unknown_without_emitting_facts():
    provider = _provider(
        "imports", [("imports", "module:a", "module:b")], complete=False
    )

    adapted = adapt_graph_facts(_graph((provider,)))

    assert not adapted.facts
    assert adapted.state == "unknown"
    assert adapted.provider_fact_sets[0].completeness.value == "partial"


def test_adapter_marks_conflicting_fact_sets_for_same_provider_unknown():
    first = _provider("imports", [("imports", "module:a", "module:b")])
    second = _provider("imports", [("imports", "module:a", "module:c")])

    adapted = adapt_graph_facts(_graph((first, second)))

    assert adapted.state == "unknown"
    assert any(item.reason == "conflicting_provider_fact_sets" for item in adapted.rejections)


def test_adapter_emits_directional_consumer_impact_fact():
    provider = _provider("imports", [("imports", "module:consumer", "module:base")])
    graph = _graph((provider,))

    adapted = adapt_graph_facts(graph)

    assert [
        (fact.source_id, fact.target_id, fact.role, fact.direction)
        for fact in adapted.facts
    ] == [
        (
            graph.find_by_stable_key("module:base").id,
            graph.find_by_stable_key("module:consumer").id,
            "consumer",
            "out",
        )
    ]


def test_analysis_classifies_direct_required_and_transitive_contextual():
    provider = _provider("imports", [
        ("imports", "module:middle", "module:base"),
        ("imports", "module:api", "module:middle"),
    ])
    graph = _graph((provider,))
    seed = graph.find_by_stable_key("module:base").id

    result = analyze_contextual_impact(graph, (seed,))

    assert [item.stable_key for item in result.required] == ["module:middle"]
    assert [item.stable_key for item in result.contextual] == ["module:api"]
    assert result.required[0].paths[0].depth == 1
    assert result.contextual[0].paths[0].depth == 2
    assert result.state == "complete"


def test_analysis_keeps_direction_rejections_inspectable():
    provider = _provider("imports", [("imports", "module:consumer", "module:base")])
    graph = _graph((provider,))
    seed = graph.find_by_stable_key("module:consumer").id

    result = analyze_contextual_impact(graph, (seed,))

    assert not result.required
    assert not result.contextual
    assert [(item.stable_key, item.reasons) for item in result.excluded] == [
        ("module:base", ("direction_or_rule",))
    ]


def test_analysis_is_deterministic_and_score_is_explained():
    provider = _provider("imports", [
        ("imports", "module:z", "module:base"),
        ("imports", "module:a", "module:base"),
    ])
    graph = _graph((provider,))
    seed = graph.find_by_stable_key("module:base").id

    first = analyze_contextual_impact(graph, (seed,))
    second = analyze_contextual_impact(graph, (seed,))

    assert first == second
    assert [item.stable_key for item in first.required] == ["module:a", "module:z"]
    for item in first.required:
        assert item.score == sum(value for _name, value in item.score_components)
        assert item.sort_key[-1] == item.stable_key
    assert first.analysis_digest


def test_analysis_retains_independent_corroborating_paths():
    first = _provider("imports-a", [("imports", "module:consumer", "module:base")])
    second = _provider("imports-b", [("imports", "module:consumer", "module:base")])
    graph = _graph((first, second))
    seed = graph.find_by_stable_key("module:base").id

    result = analyze_contextual_impact(graph, (seed,))

    candidate = result.required[0]
    assert len(candidate.paths) == 2
    assert {path.provider_ids for path in candidate.paths} == {
        ("imports-a",), ("imports-b",),
    }
    assert dict(candidate.score_components)["corroboration"] == 2


def test_analysis_bounds_corroborating_paths_per_target():
    providers = tuple(
        _provider(f"imports-{index}", [("imports", "module:consumer", "module:base")])
        for index in range(5)
    )
    graph = _graph(providers)
    seed = graph.find_by_stable_key("module:base").id

    result = analyze_contextual_impact(graph, (seed,))

    assert len(result.required[0].paths) == 3
    assert dict(result.required[0].score_components)["corroboration"] == 3


def test_analysis_reports_limits_without_excluding_omitted_candidates():
    provider = _provider("imports", [
        ("imports", "module:b", "module:a"),
        ("imports", "module:c", "module:b"),
        ("imports", "module:d", "module:c"),
    ])
    graph = _graph((provider,))
    seed = graph.find_by_stable_key("module:a").id

    result = analyze_contextual_impact(graph, (seed,), max_depth=1)

    assert result.state == "limit_reached"
    assert [item.stable_key for item in result.required] == ["module:b"]
    assert all(item.stable_key not in {"module:c", "module:d"} for item in result.excluded)
    assert result.limitations


def test_analysis_result_cap_never_returns_n_plus_one_candidates():
    provider = _provider("imports", [
        ("imports", "module:b", "module:a"),
        ("imports", "module:c", "module:a"),
    ])
    graph = _graph((provider,))
    seed = graph.find_by_stable_key("module:a").id

    result = analyze_contextual_impact(graph, (seed,), result_cap=1)

    assert result.state == "limit_reached"
    assert len(result.required) + len(result.contextual) == 1
    assert result.limitations == ("result cap reached",)


def test_analysis_cycle_does_not_return_the_seed_as_impacted():
    provider = _provider("imports", [
        ("imports", "module:b", "module:a"),
        ("imports", "module:a", "module:b"),
    ])
    graph = _graph((provider,))
    seed = graph.find_by_stable_key("module:a").id

    result = analyze_contextual_impact(graph, (seed,))

    assert [item.stable_key for item in result.required] == ["module:b"]
    assert all(item.node_id != seed for item in result.required + result.contextual)
