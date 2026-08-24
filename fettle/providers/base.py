"""Provider contract for the ephemeral hypergraph (P46)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

PROVIDER_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class NodeDraft:
    kind: str
    stable_key: str
    attributes: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeDraft:
    edge_type: str
    src_key: str
    dst_key: str
    attributes: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResult:
    provider_id: str
    nodes: tuple[NodeDraft, ...]
    edges: tuple[EdgeDraft, ...]
    complete: bool
    notes: tuple[str, ...] = ()

    @property
    def fact_set_id(self) -> str:
        from fettle.graph_types import canonical_digest

        payload = {
            "schema_version": PROVIDER_SCHEMA_VERSION,
            "provider_id": self.provider_id,
            "complete": self.complete,
            "notes": sorted(self.notes),
            "node_keys": sorted(n.stable_key for n in self.nodes),
            "edges": sorted(
                (e.edge_type, e.src_key, e.dst_key) for e in self.edges
            ),
        }
        return canonical_digest(payload)


Provider = Callable[[str], ProviderResult]
