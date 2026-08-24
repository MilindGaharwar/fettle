"""Graph builder facade (P46): wire default providers and build one generation."""

from __future__ import annotations

from fettle.hypergraph import AssemblyError, assemble
from fettle.providers import default_providers
from fettle.source_snapshot import committed_snapshot

DEFAULT_TRAVERSAL_RULES = {
    "edge_types": ["contains", "verifies", "implements", "imports"],
    "completeness": "required",
    "external_providers": "disabled",
}


def build_ephemeral_graph(root: str, snapshot: dict | None = None) -> dict:
    """Build one complete ephemeral generation; fail-visible envelope."""
    snap = snapshot or committed_snapshot(root)
    if snap.get("status") != "completed":
        return {"status": "tool_error", "message": snap.get("message", "")}
    results = tuple(provider(root) for provider in default_providers())
    graph = assemble(
        root, results,
        source_snapshot_digest=snap["snapshot"]["digest"],
        traversal_rules=DEFAULT_TRAVERSAL_RULES,
    )
    if isinstance(graph, AssemblyError):
        return {"status": "unknown", "message": graph.message}
    return {
        "status": "completed",
        "graph": graph,
        "providers": [
            {"id": r.provider_id, "complete": r.complete, "notes": list(r.notes)}
            for r in results
        ],
    }
