"""P46 contract tests — deterministic ephemeral graph assembly."""

from __future__ import annotations

import time


from fettle.graph_builder import build_ephemeral_graph
from fettle.hypergraph import assemble
from fettle.providers.base import EdgeDraft, NodeDraft, ProviderResult
from fettle.source_snapshot import committed_snapshot

SPEC = """---
fettle-spec: v1
id: demo-flow
status: active
scope:
  - "src/**"
---

## Requirements

- R1. Demo behaves.

## Scenarios

### S1. Demo works (traces R1)
Given the demo
When it runs
Then it passes
"""


def _make_repo(tmp_path):
    import subprocess

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "demo.md").write_text(SPEC, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "demo.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests_t").mkdir()
    (tmp_path / "tests_t" / "test_demo.py").write_text(
        "def test_demo():\n    # traces: demo-flow/S1\n    assert True\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(tmp_path)])
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "t@t"],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "t"],
        capture_output=True,
    )
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-qm", "init"], capture_output=True
    )
    return str(tmp_path)


def test_identical_inputs_produce_identical_digest(tmp_path):
    root = _make_repo(tmp_path)

    first = build_ephemeral_graph(root)
    second = build_ephemeral_graph(root)

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert (
        first["graph"].generation.digest == second["graph"].generation.digest
    )


def test_generation_binds_snapshot_and_providers(tmp_path):
    root = _make_repo(tmp_path)
    snap = committed_snapshot(root)

    result = build_ephemeral_graph(root)

    generation = result["graph"].generation
    assert generation.source_snapshot_id == snap["snapshot"]["digest"]
    assert len(generation.provider_fact_set_ids) >= 5


def test_provider_output_changes_the_digest(tmp_path):
    root = _make_repo(tmp_path)
    before = build_ephemeral_graph(root)

    (tmp_path / "tests_t" / "test_more.py").write_text(
        "def test_more():\n    # traces: demo-flow/S1\n    assert True\n",
        encoding="utf-8",
    )
    after = build_ephemeral_graph(root)

    assert (
        before["graph"].generation.digest != after["graph"].generation.digest
    )


def test_dangling_edge_reference_is_rejected_not_silently_dropped():
    bad = ProviderResult(
        "broken",
        (NodeDraft("spec", "spec:x", {}),),
        (EdgeDraft("contains", "spec:x", "scenario:missing", {}),),
        complete=True,
    )

    result = assemble("root", (bad,), "snap", {"rules": True})

    assert hasattr(result, "message") and "scenario:missing" in result.message


def test_conflicting_node_kinds_are_rejected():
    first = ProviderResult("a", (NodeDraft("spec", "k1", {}),), (), complete=True)
    second = ProviderResult("b", (NodeDraft("module", "k1", {}),), (), complete=True)

    result = assemble("root", (first, second), "snap", {"rules": True})

    assert hasattr(result, "message") and "different kind" in result.message


def test_build_budget_on_self_repo_is_bounded():
    start = time.monotonic()
    result = build_ephemeral_graph(".")
    elapsed = time.monotonic() - start

    assert result["status"] == "completed"
    assert elapsed < 60, f"full build took {elapsed:.1f}s"
    assert result["graph"].node_count() > 10
