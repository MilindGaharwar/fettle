"""P46 provider contract tests — parity and documented differences."""

from __future__ import annotations

from fettle.providers import default_providers
from fettle.providers.python_import_provider import python_import_provider
from fettle.providers.spec_provider import spec_provider
from fettle.providers.trace_marker_provider import trace_marker_provider
from fettle.providers.workspace_provider import workspace_provider
from fettle.providers.work_item_provider import work_item_provider

SPEC = """---
fettle-spec: v1
id: alpha
status: active
scope:
  - "src/**"
---

## Requirements

- R1. Alpha works.

## Scenarios

### S1. Alpha runs (traces R1)
Given alpha
When run
Then passes
"""


def _make_repo(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "alpha.md").write_text(SPEC, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "alpha.py").write_text(
        "from src.beta import helper\n\nvalue = helper()\n", encoding="utf-8"
    )
    (tmp_path / "src" / "beta.py").write_text(
        "def helper():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "tests_t").mkdir()
    (tmp_path / "tests_t" / "test_alpha.py").write_text(
        "def test_a():\n    # traces: alpha/S1\n    assert True\n", encoding="utf-8"
    )
    return str(tmp_path)


def test_spec_provider_emits_scenarios_with_containment(tmp_path):
    root = _make_repo(tmp_path)

    result = spec_provider(root)

    keys = {n.stable_key for n in result.nodes}
    assert "spec:alpha" in keys
    assert "scenario:alpha/S1" in keys
    assert any(e.src_key == "spec:alpha" for e in result.edges)
    assert result.complete


def test_trace_marker_provider_links_tests_to_known_scenarios(tmp_path):
    root = _make_repo(tmp_path)

    result = trace_marker_provider(root)

    kinds = {(n.kind) for n in result.nodes}
    assert "test" in kinds
    verify = [e for e in result.edges if e.edge_type == "verifies"]
    assert len(verify) == 1
    assert verify[0].dst_key == "scenario:alpha/S1"


def test_work_item_provider_flags_unknown_spec_references(tmp_path):
    root = _make_repo(tmp_path)
    (root_path := __import__("pathlib").Path(root) / "docs" / "item.md")
    root_path.write_text(
        "---\nfettle-work-item: true\nid: item-a\nstatus: open\n"
        "spec: nonexistent\n---\n\nbody\n",
        encoding="utf-8",
    )

    result = work_item_provider(root)

    assert any(n.stable_key == "work_item:item-a" for n in result.nodes)
    assert not result.edges
    assert any("nonexistent" in note for note in result.notes)


def test_python_import_provider_resolves_local_edges(tmp_path):
    root = _make_repo(tmp_path)

    result = python_import_provider(root)

    imports = [e for e in result.edges if e.edge_type == "imports"]
    assert imports, "expected at least one local import edge"
    assert all(e.dst_key != e.src_key for e in imports)
    assert any("python-only" in n for n in result.notes)


def test_workspace_provider_emits_detected_workspaces(tmp_path):
    root = _make_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )

    result = workspace_provider(root)

    assert any(n.kind == "workspace" for n in result.nodes)
    assert result.complete


def test_default_provider_registry_is_complete():
    ids = [p.__name__ for p in default_providers()]

    assert set(ids) == {
        "spec_provider",
        "trace_marker_provider",
        "work_item_provider",
        "workspace_provider",
        "python_import_provider",
    }
