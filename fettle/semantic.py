"""Semantic layer — link fusion + query surface (Stage 6, S6.1).

The repository is the database: specs, trace markers, work items, UAT
reports, and attestations already live in git with stable IDs. This
module fuses them into one deterministic link graph, recomputed on
demand (never persisted, so never stale), and answers two questions:

- ``fettle links <id>`` — everything attached to a known ID.
- ``fettle links --orphans`` — where the evidence chain is broken.

Node kinds: spec, requirement, scenario, test, work-item, verdict,
attestation. Edges: scenario-traces->requirement, test-covers->scenario,
work-item-implements->spec, verdict-observes->scenario,
attestation-observes->scenario.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Graph:
    nodes: dict[str, dict] = field(default_factory=dict)  # id -> {kind, ...}
    edges: list[dict] = field(default_factory=list)  # {src, label, dst}

    def add_node(self, node_id: str, kind: str, **attrs) -> None:
        self.nodes.setdefault(node_id, {"kind": kind, **attrs})

    def add_edge(self, src: str, label: str, dst: str) -> None:
        self.edges.append({"src": src, "label": label, "dst": dst})

    def neighbors(self, node_id: str) -> list[dict]:
        out = []
        for e in self.edges:
            if e["src"] == node_id:
                out.append({"direction": "out", "label": e["label"],
                            "id": e["dst"], **self.nodes.get(e["dst"], {})})
            elif e["dst"] == node_id:
                out.append({"direction": "in", "label": e["label"],
                            "id": e["src"], **self.nodes.get(e["src"], {})})
        return out


def _uat_evidence(root: str, config: dict) -> tuple[list[dict], list[dict]]:
    """(verdicts, attestations) from session worktrees + repo attest file."""
    from fettle.uat.manual import load_attestations
    from fettle.worktrees import worktrees_root

    verdicts: list[dict] = []
    wt_root = worktrees_root(root, config)
    if wt_root.is_dir():
        for report in sorted(wt_root.glob("*/.fettle/uat-report.json")):
            try:
                data = json.loads(report.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for v in data.get("verdicts", []):
                verdicts.append({**v, "session_id": data.get("session_id", "")})
    return verdicts, load_attestations(root)


def _graphify_files(root: str) -> list[str]:
    """Code file paths from graphify-out/graph.json, when present.

    Consume-optional (design doc 11 §3): fettle never requires or shells
    out to graphify; an absent or unreadable graph degrades to no
    enrichment. Node shape is probed defensively — any of file/path/
    file_path attributes counts.
    """
    graph_path = Path(root) / "graphify-out" / "graph.json"
    try:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    nodes = data.get("nodes", data if isinstance(data, list) else [])
    files: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        for key in ("file", "path", "file_path"):
            value = node.get(key)
            if isinstance(value, str) and value:
                files.add(value.lstrip("./"))
                break
    return sorted(files)


def build_graph(root: str, config: dict | None = None) -> Graph:
    """Fuse all repo artifacts into one link graph. Deterministic."""
    from fettle.spec_model import discover_specs, scenario_coverage
    from fettle.work_items import discover_work_items

    config = config or {}
    g = Graph()

    specs = [s for s, _ in discover_specs(root) if s is not None and s.spec_id]
    graphify_files = _graphify_files(root)
    for spec in specs:
        g.add_node(spec.spec_id, "spec", path=spec.path, status=spec.status)
        if spec.scope and graphify_files:
            import fnmatch
            touched = sorted({f for f in graphify_files
                              if any(fnmatch.fnmatch(f, pat) for pat in spec.scope)})
            for code_file in touched:
                g.add_node(code_file, "code", source="graphify")
                g.add_edge(spec.spec_id, "scopes", code_file)
        for rid, text in spec.requirements.items():
            g.add_node(f"{spec.spec_id}/{rid}", "requirement", text=text)
        for scen in spec.scenarios:
            sid = f"{spec.spec_id}/{scen.id}"
            g.add_node(sid, "scenario", title=scen.title)
            g.add_edge(spec.spec_id, "contains", sid)
            for rid in scen.traces:
                g.add_edge(sid, "traces", f"{spec.spec_id}/{rid}")

    coverage = scenario_coverage(root)
    for spec_row in coverage.get("specs", []):
        for scen in spec_row["scenarios"]:
            sid = f"{spec_row['id']}/{scen['id']}"
            for test in scen["covered_by"]:
                g.add_node(test, "test")
                g.add_edge(test, "covers", sid)

    for item, _ in discover_work_items(root):
        if item is None or not item.item_id:
            continue
        g.add_node(item.item_id, "work-item", status=item.status, path=item.path)
        if item.spec:
            g.add_edge(item.item_id, "implements", item.spec)

    verdicts, attestations = _uat_evidence(root, config)
    for i, v in enumerate(verdicts):
        vid = f"verdict:{v.get('session_id', '?')}:{v['scenario_id']}:{i}"
        g.add_node(vid, "verdict", verdict=v["verdict"],
                   session_id=v.get("session_id", ""))
        g.add_edge(vid, "observes", v["scenario_id"])
    for i, a in enumerate(attestations):
        aid = f"attestation:{a.get('operator', '?')}:{a['scenario_id']}:{i}"
        g.add_node(aid, "attestation", outcome=a.get("outcome", ""),
                   operator=a.get("operator", ""))
        g.add_edge(aid, "observes", a["scenario_id"])
    return g


def links_for(g: Graph, node_id: str) -> dict | None:
    """Neighborhood of a known ID; None when unknown."""
    if node_id not in g.nodes:
        return None
    return {"id": node_id, **g.nodes[node_id], "links": g.neighbors(node_id)}


def closest_ids(g: Graph, node_id: str, limit: int = 5) -> list[str]:
    """Cheap suggestions for an unknown ID (substring, then prefix word)."""
    needle = node_id.lower()
    hits = [n for n in sorted(g.nodes) if needle in n.lower()]
    if not hits:
        head = needle.split("/")[0]
        hits = [n for n in sorted(g.nodes) if n.lower().startswith(head)]
    return hits[:limit]


def find_orphans(g: Graph) -> list[dict]:
    """Broken evidence chains. Report, not gate.

    - requirement with no scenario tracing it
    - scenario with no covering test AND no UAT evidence
    - work item implementing an unknown spec
    """
    orphans: list[dict] = []
    traced: set[str] = set()
    covered: set[str] = set()
    observed: set[str] = set()
    for e in g.edges:
        if e["label"] == "traces":
            traced.add(e["dst"])
        elif e["label"] == "covers":
            covered.add(e["dst"])
        elif e["label"] == "observes":
            observed.add(e["dst"])
    for node_id, node in sorted(g.nodes.items()):
        kind = node["kind"]
        if kind == "requirement" and node_id not in traced:
            orphans.append({"id": node_id, "kind": kind,
                            "problem": "no scenario traces this requirement",
                            "fix": f"add a scenario with '(traces {node_id.rsplit('/', 1)[-1]})'"})
        elif kind == "scenario" and node_id not in covered and node_id not in observed:
            orphans.append({"id": node_id, "kind": kind,
                            "problem": "no test, verdict, or attestation touches this scenario",
                            "fix": f"add a test with '# traces: {node_id}' or run fettle uat"})
        elif kind == "work-item":
            for e in g.edges:
                if e["src"] == node_id and e["label"] == "implements" \
                        and e["dst"] not in g.nodes:
                    orphans.append({"id": node_id, "kind": kind,
                                    "problem": f"implements unknown spec '{e['dst']}'",
                                    "fix": "fix the 'spec:' frontmatter or add the spec"})
    return orphans


def format_links(info: dict) -> str:
    attrs = {k: v for k, v in info.items() if k not in ("id", "kind", "links")}
    attr_str = " ".join(f"{k}={v}" for k, v in attrs.items())
    lines = [f"{info['id']}  [{info['kind']}]" + (f"  {attr_str}" if attr_str else "")]
    if not info["links"]:
        lines.append("  (no links)")
    for link in info["links"]:
        arrow = f"\u2500{link['label']}\u2192" if link["direction"] == "out" \
            else f"\u2190{link['label']}\u2500"
        extra = link.get("title") or link.get("verdict") or link.get("outcome") \
            or link.get("status") or ""
        lines.append(f"  {arrow} {link['id']}  [{link['kind']}]"
                     + (f"  {extra}" if extra else ""))
    return "\n".join(lines)


def format_orphans(orphans: list[dict]) -> str:
    if not orphans:
        return "\u2713 No orphans — every requirement, scenario, and work item is linked."
    lines = [f"{len(orphans)} orphan(s) — broken evidence chains:"]
    for o in orphans:
        lines.append(f"  \u2717 {o['id']}  [{o['kind']}] — {o['problem']}")
        lines.append(f"      fix: {o['fix']}")
    return "\n".join(lines)
