"""Deterministic ephemeral hypergraph assembler (P46).

Providers emit node/edge drafts; the assembler resolves references after
ALL providers finish, canonicalizes through P44's content-addressed types,
publishes one frozen generation atomically, and exposes bidirectional
incidence indexes. Integer handles exist only inside this module and never
enter canonical output.
"""

from __future__ import annotations

from dataclasses import dataclass

from fettle.graph_types import (
    GraphGeneration,
    Hyperedge,
    Incidence,
    Node,
    canonical_digest,
)
from fettle.providers.base import ProviderResult


@dataclass(frozen=True)
class AssemblyError:
    message: str


class EphemeralGraph:
    """One complete, immutable generation plus traversal indexes."""

    def __init__(
        self,
        generation: GraphGeneration,
        nodes: dict[str, Node],
        edges: dict[str, Hyperedge],
        incidences: list[Incidence],
        results: tuple[ProviderResult, ...],
    ):
        self._generation = generation
        # Keyed by canonical node id; stable-key access goes through
        # find_by_stable_key / stable_keys().
        self._nodes = {node.id: node for node in nodes.values()}
        self._edges = dict(edges)
        self._node_to_edges: dict[str, list[tuple[str, str]]] = {}
        self._edge_endpoints: dict[str, list[tuple[str, str, str]]] = {}
        for inc in incidences:
            self._node_to_edges.setdefault(
                inc.node_id, []
            ).append((inc.edge_id, inc.direction))
            self._edge_endpoints.setdefault(
                inc.edge_id, []
            ).append((inc.node_id, inc.role, inc.direction))

    @property
    def generation(self) -> GraphGeneration:
        return self._generation

    def node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def edge(self, edge_id: str) -> Hyperedge | None:
        return self._edges.get(edge_id)

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return len(self._edges)

    def edges_of(self, node_id: str, direction: str | None = None) -> list[str]:
        pairs = self._node_to_edges.get(node_id, [])
        if direction is None:
            return [edge_id for edge_id, _direction in pairs]
        return [edge_id for edge_id, dirn in pairs if dirn == direction]

    def endpoints(self, edge_id: str) -> list[tuple[str, str]]:
        return [
            (node_id, direction)
            for node_id, _role, direction in self._edge_endpoints.get(edge_id, [])
        ]

    def find_by_stable_key(self, stable_key: str) -> Node | None:
        for node in self._nodes.values():
            if node.stable_key == stable_key:
                return node
        return None

    def stable_keys(self) -> dict[str, str]:
        """stable_key -> node_id map for seed resolution."""
        return {node.stable_key: node.id for node in self._nodes.values()}

    def stable_keys_with_attribute(self, name: str, value: str) -> list[str]:
        """Stable keys whose attributes carry ``name == value`` (exact match)."""
        import json as _json

        matches = []
        for node in self._nodes.values():
            try:
                attrs = _json.loads(node.attributes_json)
            except ValueError:
                continue
            if attrs.get(name) == value:
                matches.append(node.stable_key)
        return matches

    def closure(self, seed_node_ids: set[str]) -> set[str]:
        """Undirected blast-radius closure over incidences (advisory)."""
        seen: set[str] = set(seed_node_ids)
        frontier = list(seed_node_ids)
        while frontier:
            node_id = frontier.pop()
            for edge_id, _direction in self._node_to_edges.get(node_id, []):
                for neighbor_id, _role, _direction in self._edge_endpoints.get(
                    edge_id, []
                ):
                    if neighbor_id not in seen:
                        seen.add(neighbor_id)
                        frontier.append(neighbor_id)
        return seen


def assemble(
    root: str,
    results: tuple[ProviderResult, ...],
    source_snapshot_digest: str,
    traversal_rules: dict,
) -> EphemeralGraph | AssemblyError:
    """Two-phase assembly. Never returns a partial graph."""
    collected = _collect_drafts(results)
    if isinstance(collected, AssemblyError):
        return collected
    key_to_node = {
        key: Node.create(kind, key, attributes)
        for key, (kind, attributes) in sorted(collected[0].items())
    }
    missing = _missing_endpoints(collected[1], key_to_node)
    if missing:
        return AssemblyError(
            "edge endpoints without nodes: " + ", ".join(missing[:10])
        )
    built = _build_edges(collected[1], key_to_node, results)
    if isinstance(built, AssemblyError):
        return built
    edges, incidence_list = built
    generation = GraphGeneration.create(
        source_snapshot_id=source_snapshot_digest,
        traversal_rule_set_digest=canonical_digest(traversal_rules),
        node_ids=tuple(node.id for node in key_to_node.values()),
        edge_ids=tuple(edges.keys()),
        incidence_ids=tuple(
            f"{inc.edge_id}/{inc.node_id}/{inc.role}" for inc in incidence_list
        ),
        provider_fact_set_ids=tuple(r.fact_set_id for r in results),
    )
    return EphemeralGraph(generation, key_to_node, edges, incidence_list, results)


def _missing_endpoints(
    edge_drafts: list[tuple[str, str, str, dict]],
    key_to_node: dict[str, Node],
) -> list[str]:
    return sorted({
        endpoint
        for _t, src, dst, _a in edge_drafts
        for endpoint in (src, dst)
        if endpoint not in key_to_node
    })


def _collect_drafts(
    results: tuple[ProviderResult, ...],
) -> tuple[dict[str, tuple[str, dict]], list[tuple[str, str, str, dict]]] | AssemblyError:
    node_drafts: dict[str, tuple[str, dict]] = {}
    edge_drafts: list[tuple[str, str, str, dict]] = []
    for result in results:
        for draft in result.nodes:
            existing = node_drafts.get(draft.stable_key)
            if existing is not None:
                if existing[0] != draft.kind:
                    return AssemblyError(
                        f"provider {result.provider_id} redefines "
                        f"{draft.stable_key!r} with a different kind"
                    )
                continue
            node_drafts[draft.stable_key] = (draft.kind, draft.attributes)
        edge_drafts.extend(
            (d.edge_type, d.src_key, d.dst_key, d.attributes) for d in result.edges
        )
    return node_drafts, edge_drafts


def _build_edges(
    edge_drafts: list[tuple[str, str, str, dict]],
    key_to_node: dict[str, Node],
    results: tuple[ProviderResult, ...],
) -> tuple[dict[str, Hyperedge], list[Incidence]] | AssemblyError:
    edges: dict[str, Hyperedge] = {}
    incidence_list: list[Incidence] = []
    for edge_type, src, dst, attributes in sorted(edge_drafts):
        edge = Hyperedge.create(
            edge_type,
            ((key_to_node[src].id, "src", "out", 0),
             (key_to_node[dst].id, "dst", "in", 0)),
            provider_fact_set_id=_fact_set_for(results, edge_type),
            attributes=attributes,
        )
        if edge.id in edges:
            continue
        edges[edge.id] = edge
        for role, node_id, direction in (
            ("src", key_to_node[src].id, "out"),
            ("dst", key_to_node[dst].id, "in"),
        ):
            incidence_list.append(Incidence(edge.id, node_id, role, direction))
    return edges, incidence_list


def _fact_set_for(results: tuple[ProviderResult, ...], edge_type: str) -> str:
    owner = next((r for r in results if any(
        e.edge_type == edge_type for e in r.edges
    )), None)
    return owner.fact_set_id if owner else "unattributed"
