"""Specification and scenario provider (P46)."""

from __future__ import annotations

import fnmatch
import os

from fettle.providers.base import EdgeDraft, NodeDraft, ProviderResult


def spec_provider(root: str) -> ProviderResult:
    """Emit spec/scenario nodes, containment edges, and scope governance."""
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
    governed = _governed_module_edges(root, discover_specs(root))
    edges.extend(governed)
    return ProviderResult("specs", tuple(nodes), tuple(edges), True, tuple(notes))


def _governed_module_edges(root: str, specs) -> list[EdgeDraft]:
    """Scope-glob governance edges from active specs to Python modules."""
    from fettle.import_graph import _collect_py_files

    edges: list[EdgeDraft] = []
    seen: set[tuple[str, str]] = set()
    for spec, _findings in specs:
        if spec is None or spec.status != "active" or not spec.scope:
            continue
        src_key = f"spec:{spec.spec_id}"
        for py_abs in _collect_py_files(root):
            rel = os.path.relpath(py_abs, root).replace(os.sep, "/")
            if any(fnmatch.fnmatch(rel, pat) for pat in spec.scope):
                pair = (src_key, rel)
                if pair in seen:
                    continue
                seen.add(pair)
                edges.append(EdgeDraft("governs", src_key, f"module:{rel}"))
    return edges
