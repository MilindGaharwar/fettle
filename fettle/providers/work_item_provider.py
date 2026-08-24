"""Work-item provider: work items and their declared spec links (P46)."""

from __future__ import annotations

from fettle.providers.base import EdgeDraft, NodeDraft, ProviderResult
from fettle.spec_model import discover_specs
from fettle.work_items import discover_work_items


def work_item_provider(root: str) -> ProviderResult:
    nodes: list[NodeDraft] = []
    edges: list[EdgeDraft] = []
    notes: list[str] = []
    known_specs = {
        spec.spec_id
        for spec, _f in discover_specs(root)
        if spec is not None and spec.status == "active"
    }
    for item, findings in discover_work_items(root):
        if item is None:
            notes.extend(f"invalid work item finding: {f['message']}" for f in findings[:3])
            continue
        nodes.append(NodeDraft(
            "work_item", f"work_item:{item.item_id}",
            {"path": item.path, "status": item.status},
        ))
        if item.spec in known_specs:
            edges.append(EdgeDraft(
                "implements", f"work_item:{item.item_id}", f"spec:{item.spec}",
            ))
        elif item.spec:
            notes.append(
                f"item {item.item_id} references unknown spec {item.spec!r}"
            )
    return ProviderResult("work_items", tuple(nodes), tuple(edges), True, tuple(notes))
