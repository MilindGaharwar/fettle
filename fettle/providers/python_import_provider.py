"""Python import provider (P46) — wraps import_graph as a graph source."""

from __future__ import annotations

import os
from pathlib import Path

from fettle.providers.base import EdgeDraft, NodeDraft, ProviderResult

_COVERAGE_NOTE = (
    "python-only coverage; JS/TS, Go, and Rust import edges are out of "
    "scope for this provider"
)


def _relative(path: str, root: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def _import_edges(
    root: str,
    pairs: list[tuple[str, str]],
    known: set[str],
) -> tuple[list[EdgeDraft], set[str]]:
    from fettle.import_graph import _parse_imports, _resolve_module

    root_path = Path(root)
    edges: list[EdgeDraft] = []
    unresolved: set[str] = set()
    for _abs_path, rel in pairs:
        for imp in _parse_imports(str(root_path / rel)):
            target = _resolve_module(imp["module"], root)
            if target is None:
                unresolved.add(imp["module"])
                continue
            target_rel = _relative(target, root)
            if target_rel in known and target_rel != rel:
                edges.append(EdgeDraft("imports", f"module:{rel}", f"module:{target_rel}"))
    return edges, unresolved


def python_import_provider(root: str) -> ProviderResult:
    from fettle.import_graph import _collect_py_files, _file_to_module

    absolute = sorted(_collect_py_files(root))
    relative = [_relative(path, root) for path in absolute]
    nodes = [
        NodeDraft(
            "module", f"module:{rel}",
            {"module": _file_to_module(abs_path, root) or ""},
        )
        for abs_path, rel in zip(absolute, relative)
    ]
    edges, unresolved = _import_edges(root, list(zip(absolute, relative)), set(relative))

    return ProviderResult(
        "python_imports", tuple(nodes), tuple(edges),
        complete=True,
        notes=(_COVERAGE_NOTE,) + tuple(sorted(unresolved)[:10]),
    )
