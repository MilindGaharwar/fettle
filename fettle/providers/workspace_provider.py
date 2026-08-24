"""Workspace routing provider (P46)."""

from __future__ import annotations

from fettle.providers.base import EdgeDraft, NodeDraft, ProviderResult
from fettle.workspace import discover_workspaces


def workspace_provider(root: str) -> ProviderResult:
    nodes: list[NodeDraft] = []
    edges: list[EdgeDraft] = []
    notes: list[str] = []
    workspaces = discover_workspaces(root)
    for ws in workspaces:
        key = f"workspace:{ws.name}"
        nodes.append(NodeDraft(
            "workspace", key,
            {"language": ws.language, "path": ws.path, "marker": ws.marker},
        ))
    if len(workspaces) > 1:
        notes.append("nested workspaces route by most-specific marker")
    return ProviderResult(
        "workspaces", tuple(nodes), tuple(edges), True, tuple(notes),
    )
