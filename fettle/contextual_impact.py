"""Deterministic contextual-impact adaptation and analysis."""

from __future__ import annotations

from dataclasses import dataclass, replace

from fettle.graph_types import canonical_digest
from fettle.hypergraph import EphemeralGraph
from fettle.provider_contract import (
    Completeness,
    ProviderFactSet,
    ProviderRunState,
    TrustClass,
)
from fettle.traversal_rules import TraversalFact


@dataclass(frozen=True, order=True)
class RejectedFact:
    provider_id: str
    reason: str
    detail: str


@dataclass(frozen=True)
class AdaptedGraphFacts:
    facts: tuple[TraversalFact, ...]
    provider_fact_sets: tuple[ProviderFactSet, ...]
    rejections: tuple[RejectedFact, ...]
    state: str


@dataclass(frozen=True)
class ImpactPath:
    seed_id: str
    target_id: str
    steps: tuple[TraversalFact, ...]
    depth: int
    provider_ids: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class ImpactCandidate:
    node_id: str
    stable_key: str
    kind: str
    classification: str
    score: int
    score_components: tuple[tuple[str, int], ...]
    sort_key: tuple[int | str, ...]
    paths: tuple[ImpactPath, ...]
    reasons: tuple[str, ...]
    action: str
    digest: str


@dataclass(frozen=True)
class ContextualImpactResult:
    state: str
    seeds: tuple[str, ...]
    required: tuple[ImpactCandidate, ...]
    contextual: tuple[ImpactCandidate, ...]
    excluded: tuple[ImpactCandidate, ...]
    limitations: tuple[str, ...]
    analysis_digest: str


_DIRECTION_RULES = {
    "imports": ("dst", "src", "consumer"),
    "contains": ("src", "dst", "contained"),
    "governs": ("dst", "src", "governing_spec"),
    "verifies": ("dst", "src", "verifying_test"),
    "implements": ("dst", "src", "implementing_work_item"),
}
_MAX_PATHS_PER_TARGET = 3


def adapt_graph_facts(graph: EphemeralGraph) -> AdaptedGraphFacts:
    """Adapt graph-owned provider facts without inventing missing provenance."""
    fact_sets: list[ProviderFactSet] = []
    rejections: list[RejectedFact] = []
    by_fact_set_id = {}
    rejected_fact_set_ids: set[str] = set()
    fact_set_ids_by_provider: dict[str, set[str]] = {}
    for result in graph.provider_results:
        required = (
            result.provider_id, result.provider_version, result.implementation_digest,
            result.completeness_scope,
        )
        if not all(required) or result.deterministic is None or result.trust_class is None:
            rejections.append(RejectedFact(
                result.provider_id, "missing_provider_metadata",
                "provider identity, implementation, trust, determinism, and scope are required",
            ))
            rejected_fact_set_ids.add(result.fact_set_id)
            continue
        completeness = Completeness.COMPLETE if result.complete else Completeness.PARTIAL
        run_state = ProviderRunState.PASS if result.complete else ProviderRunState.UNKNOWN
        fact_set = ProviderFactSet(
            result.provider_id, result.provider_version, result.implementation_digest,
            graph.generation.traversal_rule_set_digest, graph.generation.source_snapshot_id,
            run_state, completeness, result.completeness_scope, result.deterministic,
            result.trust_class, message="" if result.complete else "provider reported partial results",
        )
        fact_sets.append(fact_set)
        by_fact_set_id[result.fact_set_id] = (result, fact_set)
        fact_set_ids_by_provider.setdefault(result.provider_id, set()).add(result.fact_set_id)

    conflicting_providers = {
        provider_id
        for provider_id, fact_set_ids in fact_set_ids_by_provider.items()
        if len(fact_set_ids) > 1
    }
    for provider_id in sorted(conflicting_providers):
        rejections.append(RejectedFact(
            provider_id, "conflicting_provider_fact_sets",
            f"provider {provider_id} emitted conflicting canonical fact sets",
        ))

    facts: list[TraversalFact] = []
    for edge_id in graph.generation.edge_ids:
        edge = graph.edge(edge_id)
        owner = by_fact_set_id.get(edge.provider_fact_set_id) if edge else None
        if edge and edge.provider_fact_set_id in rejected_fact_set_ids:
            continue
        if edge is None or owner is None:
            rejections.append(RejectedFact("", "unattributed_edge", edge_id))
            continue
        result, fact_set = owner
        if not result.complete or result.provider_id in conflicting_providers:
            continue
        rule = _DIRECTION_RULES.get(edge.type)
        endpoints = {role: node_id for node_id, role, _direction, _ordinal in edge.incidence_signature}
        if rule is None or rule[0] not in endpoints or rule[1] not in endpoints:
            rejections.append(RejectedFact(result.provider_id, "unsupported_relationship", edge.id))
            continue
        facts.append(TraversalFact(
            endpoints[rule[0]], endpoints[rule[1]], edge.id, edge.type, rule[2], "out",
            result.provider_id, fact_set.trust_class,
        ))
    fact_ids_by_provider: dict[str, list[str]] = {}
    for fact in facts:
        fact_ids_by_provider.setdefault(fact.provider_id, []).append(canonical_digest(fact))
    fact_sets = [
        replace(item, fact_ids=tuple(fact_ids_by_provider.get(item.provider_id, ())))
        for item in fact_sets
    ]
    state = "unknown" if rejections or any(not result.complete for result in graph.provider_results) else "complete"
    return AdaptedGraphFacts(
        tuple(sorted(set(facts))), tuple(sorted(fact_sets, key=lambda item: item.id)),
        tuple(sorted(rejections)), state,
    )


def analyze_contextual_impact(
    graph: EphemeralGraph,
    seed_node_ids: tuple[str, ...],
    *,
    max_depth: int = 5,
    fanout_cap: int = 100,
    result_cap: int = 500,
) -> ContextualImpactResult:
    """Classify and rank bounded directional impact without changing legacy closure."""
    if min(max_depth, fanout_cap, result_cap) <= 0:
        raise ValueError("contextual impact bounds must be positive")
    seeds = tuple(sorted(set(seed_node_ids)))
    adapted = adapt_graph_facts(graph)
    adjacency: dict[str, list[TraversalFact]] = {}
    for fact in adapted.facts:
        adjacency.setdefault(fact.source_id, []).append(fact)

    paths: dict[str, list[tuple[TraversalFact, ...]]] = {}
    visited = set(seeds)
    frontier = [(seed, ()) for seed in seeds]
    limitations = [rejection.detail for rejection in adapted.rejections]
    limit_reached = False
    for _depth in range(max_depth):
        next_frontier: list[tuple[str, tuple[TraversalFact, ...]]] = []
        for source_id, path in sorted(frontier, key=lambda item: item[0]):
            outgoing = adjacency.get(source_id, [])
            if len(outgoing) > fanout_cap:
                outgoing = outgoing[:fanout_cap]
                limitations.append(f"fan-out cap exceeded at {source_id}")
                limit_reached = True
            for fact in outgoing:
                candidate_path = path + (fact,)
                path_node_ids = {step.source_id for step in path}
                path_node_ids.update(step.target_id for step in path)
                if fact.target_id in set(seeds) | path_node_ids:
                    continue
                if fact.target_id in visited:
                    target_paths = paths.setdefault(fact.target_id, [])
                    if len(target_paths) < _MAX_PATHS_PER_TARGET:
                        target_paths.append(candidate_path)
                    continue
                if len(paths) >= result_cap:
                    limitations.append("result cap reached")
                    limit_reached = True
                    break
                paths.setdefault(fact.target_id, []).append(candidate_path)
                visited.add(fact.target_id)
                next_frontier.append((fact.target_id, candidate_path))
            if limit_reached and limitations[-1] == "result cap reached":
                break
        frontier = next_frontier
        if not frontier or (limit_reached and limitations[-1] == "result cap reached"):
            break
    if frontier and "result cap reached" not in limitations:
        limitations.append("maximum depth reached")
        limit_reached = True

    required: list[ImpactCandidate] = []
    contextual: list[ImpactCandidate] = []
    for node_id, candidate_paths in sorted(paths.items()):
        shortest_depth = min(len(path) for path in candidate_paths)
        classification = "required" if shortest_depth == 1 else "contextual"
        candidate = _candidate(graph, node_id, classification, candidate_paths)
        (required if classification == "required" else contextual).append(candidate)

    reached = set(paths)
    legacy = graph.closure(set(seeds)) - set(seeds)
    excluded = [] if limit_reached or adapted.state == "unknown" else [
        _candidate(graph, node_id, "excluded", (), reasons=("direction_or_rule",))
        for node_id in sorted(legacy - reached)
    ]
    required.sort(key=lambda item: item.sort_key)
    contextual.sort(key=lambda item: item.sort_key)
    excluded.sort(key=lambda item: item.sort_key)
    if adapted.state == "unknown":
        state = "unknown"
    elif limit_reached:
        state = "limit_reached"
    else:
        state = "complete"
    payload = {
        "state": state,
        "graph_digest": graph.generation.digest,
        "seeds": seeds,
        "required": required,
        "contextual": contextual,
        "excluded": excluded,
        "limitations": sorted(set(limitations)),
    }
    return ContextualImpactResult(
        state, seeds, tuple(required), tuple(contextual), tuple(excluded),
        tuple(sorted(set(limitations))), canonical_digest(payload),
    )


def _candidate(
    graph: EphemeralGraph,
    node_id: str,
    classification: str,
    raw_paths: tuple[tuple[TraversalFact, ...], ...] | list[tuple[TraversalFact, ...]],
    *,
    reasons: tuple[str, ...] = (),
) -> ImpactCandidate:
    node = graph.node(node_id)
    stable_key = node.stable_key if node else node_id
    kind = node.kind if node else "unknown"
    impact_paths = tuple(sorted(
        (_impact_path(path) for path in raw_paths), key=lambda path: (path.depth, path.digest),
    ))
    depth = impact_paths[0].depth if impact_paths else 0
    trust = max(
        (_trust_score(step.trust_class) for path in impact_paths for step in path.steps),
        default=0,
    )
    components = (
        ("required", 1000 if classification == "required" else 0),
        ("proximity", max(0, 100 - depth * 10) if depth else 0),
        ("trust", trust),
        ("provider_completeness", 100 if impact_paths else 0),
        ("corroboration", len({path.digest for path in impact_paths})),
    )
    score = sum(value for _name, value in components)
    sort_key: tuple[int | str, ...] = (-score, depth, stable_key)
    action = "verify required impact" if classification == "required" else (
        "review contextual impact" if classification == "contextual" else "no action"
    )
    payload = {
        "node_id": node_id, "stable_key": stable_key, "kind": kind,
        "classification": classification, "score_components": components,
        "paths": impact_paths, "reasons": reasons, "action": action,
    }
    return ImpactCandidate(
        node_id, stable_key, kind, classification, score, components, sort_key,
        impact_paths, reasons, action, canonical_digest(payload),
    )


def _impact_path(steps: tuple[TraversalFact, ...]) -> ImpactPath:
    seed_id = steps[0].source_id
    target_id = steps[-1].target_id
    providers = tuple(sorted({step.provider_id for step in steps}))
    payload = {"seed_id": seed_id, "target_id": target_id, "steps": steps}
    return ImpactPath(
        seed_id, target_id, steps, len(steps), providers, canonical_digest(payload),
    )


def _trust_score(trust: TrustClass) -> int:
    return {
        TrustClass.AUTHORITATIVE: 40,
        TrustClass.DERIVED: 30,
        TrustClass.HEURISTIC: 20,
        TrustClass.EXTERNAL: 10,
    }[trust]
