"""Python import provider (P46) — wraps import_graph as a graph source."""

from __future__ import annotations

from pathlib import Path

from fettle.providers.base import EdgeDraft, NodeDraft, ProviderResult

_COVERAGE_NOTE = (
    "python-only coverage; JS/TS, Go, and Rust import edges are out of "
    "scope for this provider"
)


def python_import_provider(root: str) -> ProviderResult:
    from fettle.import_graph import (
        _collect_py_files,
        _file_to_module,
    )

    py_files = sorted(_collect_py_files(root))
    nodes = [
        NodeDraft(
            "module", f"module:{rel}",
            {"module": _file_to_module(rel, root) or ""},
        )
        for rel in py_files
    ]
    edges, unresolved = _import_edges(root, py_files)
    return ProviderResult(
        "python_imports", tuple(nodes), tuple(edges),
        complete=True,
        notes=(_COVERAGE_NOTE,) + tuple(sorted(unresolved)[:10]),
    )


def _import_edges(root: str, py_files: list[str]) -> tuple[list[EdgeDraft], set[str]]:
    from fettle.import_graph import _parse_imports, _resolve_module

    known = {f for f in py_files}
    edges: list[EdgeDraft] = []
    unresolved: set[str] = set()
    root_path = Path(root)
    for rel in py_files:
        for imp in _parse_imports(str(root_path / rel)):
            target_rel = _resolve_module(imp["module"], root)
            if target_rel in known and target_rel != rel:
                edges.append(EdgeDraft(
                    "imports", f"module:{rel}", f"module:{target_rel}",
                ))
            elif target_rel is None:
                unresolved.add(imp["module"])
    return edges, unresolved
