"""Trace-marker provider: binds test files to scenarios they verify (P46)."""

from __future__ import annotations

from fettle.provider_contract import TrustClass
from fettle.providers.base import EdgeDraft, NodeDraft, ProviderResult, implementation_digest
from fettle.trace_canonical import build_trace_index, collect_test_markers


def trace_marker_provider(root: str) -> ProviderResult:
    markers, _unknown = collect_test_markers(root)
    index = build_trace_index(root)

    nodes: list[NodeDraft] = []
    edges: list[EdgeDraft] = []
    notes: list[str] = []
    test_keys: set[str] = set()
    for marker in sorted(markers):
        for test_rel in sorted(markers[marker]):
            key = f"test:{test_rel}"
            nodes.append(NodeDraft("test", key, {"path": test_rel}))
            test_keys.add(key)
            if marker in index:
                edges.append(EdgeDraft(
                    "verifies", key, f"scenario:{marker}", {"marker": marker},
                ))
            else:
                notes.append(f"unresolved marker {marker!r} in {test_rel}")
    return ProviderResult(
        "trace_markers", tuple(nodes), tuple(edges),
        complete=True, notes=tuple(sorted(notes)),
        provider_version="1", implementation_digest=implementation_digest(__file__),
        deterministic=True, trust_class=TrustClass.DERIVED,
        completeness_scope=("test_trace_markers",),
    )
