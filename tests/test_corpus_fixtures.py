"""Demo corpus contracts — the maintained fixture anchors measured claims."""

from __future__ import annotations

from pathlib import Path

from fettle.graph_builder import build_ephemeral_graph

CORPUS = Path(__file__).resolve().parent.parent / "examples" / "corpus"


def _built():
    result = build_ephemeral_graph(str(CORPUS))
    assert result["status"] == "completed"
    return result


def test_corpus_builds_a_complete_generation():
    result = _built()

    assert all(p["complete"] for p in result["providers"])
    graph = result["graph"]
    assert graph.node_count() >= 6
    assert graph.find_by_stable_key("spec:ledger-core") is not None
    assert graph.find_by_stable_key("scenario:ledger-core/S1") is not None


def test_corpus_digest_is_deterministic():
    first = _built()
    second = _built()

    assert first["graph"].generation.digest == second["graph"].generation.digest


def test_corpus_contains_import_and_verify_edges():
    graph = _built()["graph"]

    edge_types = {
        graph.edge(eid).type for eid in graph.generation.edge_ids
    }
    assert {"imports", "verifies", "contains"} <= edge_types


def test_workspace_routing_sees_python_and_web_workspaces():
    from fettle.workspace import discover_workspaces

    names = {ws.name for ws in discover_workspaces(str(CORPUS))}

    assert any("web" in name.lower() or name == "ledger-web" for name in names), names
