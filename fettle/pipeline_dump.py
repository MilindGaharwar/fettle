"""Item 9 — pipeline dump: composed gate/check pipeline with provenance.

Answers "which checks are active, on which events, with what mode, and
WHERE was that decided" — one row per dispatcher check. Complements
`fettle config --explain` (per-key values) with the runtime composition
view.
"""

from __future__ import annotations

from pathlib import Path

from fettle.dispatcher_registry import CHECKS


def _source_of(layers, key_path: str) -> str:
    """Name of the highest-precedence layer that sets ``key_path``."""
    parts = key_path.split(".")
    found = "defaults"
    for layer in layers:
        node = layer.config
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                node = None
                break
            node = node[part]
        if node is not None:
            found = layer.name
    return found


def dump_pipeline(root: str = ".") -> dict:
    """One row per dispatcher check with effective settings and provenance."""
    from fettle.policy_layers import discover_layers, resolve_config

    layers = discover_layers(Path(root))
    config = resolve_config(layers)
    gates_cfg = config.get("gates", {}) or {}

    rows = []
    for check in sorted(CHECKS, key=lambda c: c.name):
        gate_cfg = gates_cfg.get(check.name, {}) or {}
        enabled = bool(gate_cfg.get("enabled", check.enabled_by_default))
        mode = str(gate_cfg.get("mode", "advisory"))
        source = _source_of(layers, f"gates.{check.name}.enabled")
        rows.append({
            "name": check.name,
            "events": sorted(check.events),
            "enabled": enabled,
            "mode": mode,
            "source": source,
        })
    return {
        "status": "completed",
        "root": str(Path(root).resolve()),
        "layers": [{"name": layer.name, "source": layer.source}
                    for layer in layers],
        "rows": rows,
    }
