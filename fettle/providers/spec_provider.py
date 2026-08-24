"""Specification and scenario provider (P46)."""

from __future__ import annotations

from fettle.providers.base import EdgeDraft, NodeDraft, ProviderResult


def spec_provider(root: str) -> ProviderResult:
    """Emit spec and scenario nodes with containment edges."""
    from fettle.spec_model import discover_specs

    nodes: list[NodeDraft] = []
    edges: list[EdgeDraft] = []
    notes: list[str] = []
    for spec, findings in discover_specs(root):
        if spec is None:
            notes.extend(
                f"unparsable spec finding: {f['message']}" for f in findings[:3]
            )
            continue
        if spec.status != "active":
            continue
        nodes.append(NodeDraft(
            "spec", f"spec:{spec.spec_id}",
            {"path": spec.path, "status": spec.status},
        ))
        for scen in spec.scenarios:
            key = f"scenario:{spec.spec_id}/{scen.id}"
            nodes.append(NodeDraft(
                "scenario", key,
                {
                    "title": scen.title,
                    "traces": list(scen.traces),
                    "spec_id": spec.spec_id,
                },
            ))
            edges.append(EdgeDraft("contains", f"spec:{spec.spec_id}", key))
    return ProviderResult("specs", tuple(nodes), tuple(edges), True, tuple(notes))
