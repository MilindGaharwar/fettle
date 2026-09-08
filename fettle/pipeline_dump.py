"""Item 9 — pipeline dump: composed gate/check pipeline with provenance.

Answers "which checks are active, on which host events, with what authority,
and WHERE was that decided" — one row per dispatcher check and wired host. Complements
`fettle config --explain` (per-key values) with the runtime composition
view.
"""

from __future__ import annotations

from pathlib import Path

from fettle.dispatcher_registry import CHECKS
from fettle.host_capabilities import host_capabilities


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
    """One row per check and wired host with selection provenance."""
    from fettle.policy_layers import discover_layers, resolve_config

    layers = discover_layers(Path(root))
    config = resolve_config(layers)
    dispatcher_cfg = config.get("dispatcher", {}) or {}
    checks_cfg = dispatcher_cfg.get("checks", {}) or {}
    disabled_checks = dispatcher_cfg.get("disabled_checks", []) or []
    hosts = host_capabilities()

    rows = []
    for check in sorted(CHECKS, key=lambda c: c.name):
        check_cfg = checks_cfg.get(check.name, {}) or {}
        enabled_path = f"dispatcher.checks.{check.name}.enabled"
        if "enabled" in check_cfg:
            source_key = enabled_path
            source = _source_of(layers, source_key)
        elif check.name in disabled_checks:
            source_key = "dispatcher.disabled_checks"
            source = _source_of(layers, source_key)
        else:
            source_key = "enabled_by_default"
            source = "registry"

        for host, capabilities in sorted(hosts.items()):
            events = sorted(check.events.intersection(capabilities["dispatcher_events"]))
            if not events:
                continue
            rows.append({
                "name": check.name,
                "host": host,
                "events": events,
                "enabled": check.is_enabled(config),
                "mode": "check-defined",
                "authority": {
                    event: capabilities["enforcement"][event] for event in events
                },
                "source": source,
                "source_key": source_key,
            })
    return {
        "status": "completed",
        "root": str(Path(root).resolve()),
        "layers": [{"name": layer.name, "source": layer.source}
                    for layer in layers],
        "rows": rows,
    }
