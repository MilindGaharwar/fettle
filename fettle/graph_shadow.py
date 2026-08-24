"""P48 slice 1 — shadow parity between the ephemeral graph and the shipped
semantic layer. Measures correctness before any authority changes hands."""

from __future__ import annotations

from fettle.graph_builder import build_ephemeral_graph

# Semantic-layer edge labels that have a graph-native counterpart, mapped
# to the graph edge type. Everything else is a documented difference.
COMPARABLE = {"contains": "contains", "covers": "verifies",
              "implements": "implements"}

_DOCUMENTED_DIFFERENCES = {
    "traces": (
        "requirements are scenario attributes in the canonical graph; the "
        "legacy requirement nodes come from the same source data"
    ),
    "scopes": (
        "graphify code-file enrichment is external/advisory and disabled by "
        "default in providers"
    ),
    "observes": (
        "verdict/attestation observation edges are evidence-plane records, "
        "not structural links"
    ),
}


def _semantic_to_pairs(semantic_graph) -> tuple[set, list[tuple[str, str, str]]]:
    """Normalize semantic edges to stable-key pairs.

    Returns (comparable_pairs, documented) where comparable pairs are
    ``(edge_type, src_key, dst_key)`` triples with graph stable keys.
    """
    def key_of(node_id: str, kind_hint: str) -> str:
        if kind_hint == "test":
            return f"test:{node_id}"
        if kind_hint == "work-item":
            return f"work_item:{node_id}"
        if kind_hint == "spec":
            return f"spec:{node_id}"
        return f"scenario:{node_id}"

    src_kinds = {nid: data.get("kind", "")
                 for nid, data in semantic_graph.nodes.items()}
    comparable: set[tuple[str, str, str]] = set()
    documented: list[tuple[str, str, str]] = []
    for edge in semantic_graph.edges:
        label = edge["label"]
        src_kind = src_kinds.get(edge["src"], "")
        dst_kind = src_kinds.get(edge["dst"], "")
        if label == "covers":
            pair = ("verifies", f"test:{edge['src']}",
                    f"scenario:{edge['dst']}")
            comparable.add(pair)
        elif label == "implements":
            comparable.add(("implements", f"work_item:{edge['src']}",
                            f"spec:{edge['dst']}"))
        elif label == "contains":
            comparable.add(("contains", f"spec:{edge['src']}",
                            f"scenario:{edge['dst']}"))
        else:
            documented.append((
                label,
                key_of(edge["src"], src_kind),
                key_of(edge["dst"], dst_kind),
            ))
    return comparable, documented


def _graph_pairs(graph) -> set[tuple[str, str, str]]:
    keys = graph.stable_keys()
    id_to_key = {node_id: key for key, node_id in keys.items()}
    pairs: set[tuple[str, str, str]] = set()
    for edge_id in graph.generation.edge_ids:
        edge = graph.edge(edge_id)
        endpoints = graph.endpoints(edge_id)
        src_id = next(nid for nid, _d in endpoints if _d == "out")
        dst_id = next(nid for nid, _d in endpoints if _d == "in")
        pairs.add((edge.type, id_to_key[src_id], id_to_key[dst_id]))
    return pairs


def _snapshot_envelope(root: str) -> dict:
    """Prefer the committed snapshot; advisory shadow runs may use working."""
    from fettle.source_snapshot import committed_snapshot, working_snapshot

    snap = committed_snapshot(root)
    if snap.get("status") == "completed":
        return snap
    return working_snapshot(root)


def shadow_semantic(root: str) -> dict:
    """Run both engines over one tree and classify every difference."""
    from fettle.semantic import build_graph

    snap = _snapshot_envelope(root)
    if snap.get("status") != "completed":
        return {"status": "tool_error", "message": snap.get("message", "")}
    built = build_ephemeral_graph(root, snapshot=snap)
    if built["status"] != "completed":
        return {"status": "tool_error", "message": built["message"]}
    graph = built["graph"]

    legacy = build_graph(root)
    comparable_legacy, documented_legacy = _semantic_to_pairs(legacy)
    graph_pairs = _graph_pairs(graph)

    matched = sorted(comparable_legacy & graph_pairs)
    legacy_only = sorted(comparable_legacy - graph_pairs)
    graph_only = sorted(graph_pairs - comparable_legacy)

    # Acceptance: no unexplained narrower result — every legacy link the
    # graph lacks must be explained by a documented difference category.
    unexplained_narrower = [p for p in legacy_only]

    return {
        "status": "completed",
        "advisory": True,
        "digest": graph.generation.digest,
        "matched": matched,
        "matched_count": len(matched),
        "unexplained_narrower": unexplained_narrower,
        "graph_only_count": len(graph_only),
        "documented_differences": [
            {"label": label, "reason": _DOCUMENTED_DIFFERENCES[label]}
            for label in sorted({label for label, _s, _d in documented_legacy})
        ],
    }
