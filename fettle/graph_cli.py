"""P47 — advisory `fettle graph` CLI: status and impact."""

from __future__ import annotations

import argparse
import json

from fettle.graph_builder import build_ephemeral_graph


def _resolve_seeds(graph, paths: list[str]) -> tuple[set[str], list[str]]:
    keys = graph.stable_keys()
    seeds: set[str] = set()
    unresolved: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        matched_ids = {
            keys[key] for key in keys
            if key.endswith(f":{normalized}")
        }
        matched_ids.update(
            keys[stable_key]
            for stable_key in graph.stable_keys_with_attribute("path", normalized)
        )
        if matched_ids:
            seeds.update(matched_ids)
        else:
            unresolved.append(path)
    return seeds, unresolved


def cmd_status(args: argparse.Namespace) -> int:
    result = build_ephemeral_graph(args.root)
    payload = {
        "status": result["status"],
    }
    if result["status"] != "completed":
        payload["message"] = result["message"]
        print(json.dumps(payload, indent=2) if args.json else result["message"])
        return 2
    generation = result["graph"].generation
    payload.update({
        "digest": generation.digest,
        "nodes": len(generation.node_ids),
        "edges": len(generation.edge_ids),
        "providers": result["providers"],
    })
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        lines = [
            f"graph {generation.digest[:12]} · "
            f"{payload['nodes']} nodes · {payload['edges']} edges",
        ]
        for provider in result["providers"]:
            mark = "ok" if provider["complete"] else "partial"
            lines.append(f"  [{mark}] {provider['id']}")
            lines.extend(f"      note: {note}" for note in provider["notes"][:3])
        print("\n".join(lines))
    return 0


def _impact_payload(graph, paths: list[str]) -> tuple[dict | None, list[str]]:
    seeds, unresolved = _resolve_seeds(graph, paths)
    if not seeds:
        return None, unresolved
    closure_ids = graph.closure(seeds) - seeds
    affected = sorted(
        (
            {"stable_key": node.stable_key, "kind": node.kind}
            for node_id in closure_ids
            if (node := graph.node(node_id))
        ),
        key=lambda item: item["stable_key"],
    )
    keys = graph.stable_keys()
    seed_keys = sorted(k for k, nid in keys.items() if nid in seeds)
    return {
        "status": "completed",
        "advisory": True,
        "seeds": seed_keys,
        "unresolved_paths": unresolved,
        "affected": affected,
        "count": len(affected),
    }, unresolved


def cmd_impact(args: argparse.Namespace) -> int:
    result = build_ephemeral_graph(args.root)
    if result["status"] != "completed":
        message = result["message"]
        print(json.dumps({"status": "tool_error", "message": message}, indent=2)
              if args.json else message)
        return 2

    payload, unresolved = _impact_payload(result["graph"], args.paths)
    if payload is None:
        message = "no graph nodes match: " + ", ".join(unresolved or args.paths)
        print(json.dumps({"status": "unknown", "message": message}, indent=2)
              if args.json else message)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        affected = payload["affected"]
        lines = [f"blast radius ({len(affected)} nodes, advisory superset):"]
        lines.extend(f"  [{a['kind']}] {a['stable_key']}" for a in affected[:40])
        if len(affected) > 40:
            lines.append(f"  … and {len(affected) - 40} more")
        if unresolved:
            lines.append(f"unmatched paths: {', '.join(unresolved)}")
        print("\n".join(lines))
    return 0


def cmd_shadow(args: argparse.Namespace) -> int:
    from fettle.graph_shadow import shadow_semantic

    result = shadow_semantic(args.root)
    print(json.dumps(result, indent=2) if args.json else _render_shadow(result))
    return 0 if result["status"] == "completed" and not result["unexplained_narrower"] else 2


def _render_shadow(result: dict) -> str:
    lines = [
        f"shadow parity ({result['digest'][:12]}): "
        f"{result['matched_count']} matched links",
    ]
    if result["unexplained_narrower"]:
        lines.append(f"UNEXPLAINED NARROWER RESULTS: "
                     f"{len(result['unexplained_narrower'])}")
        lines.extend(f"  - {p}" for p in result["unexplained_narrower"][:10])
    else:
        lines.append("no unexplained narrower results")
    lines.append("documented differences:")
    lines.extend(f"  [{d['label']}] {d['reason']}"
                 for d in result["documented_differences"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Advisory ephemeral graph (P47)")
    subparsers = parser.add_subparsers(dest="graph_action", required=True)

    p_status = subparsers.add_parser("status", help="Digest, counts, provider completeness")
    p_status.add_argument("--root", default=".")
    p_status.add_argument("--json", action="store_true")

    p_impact = subparsers.add_parser("impact", help="Advisory blast-radius closure")
    p_impact.add_argument("--root", default=".")
    p_impact.add_argument("paths", nargs="+", help="Repo-relative paths to seed from")
    p_impact.add_argument("--json", action="store_true")

    p_shadow = subparsers.add_parser(
        "shadow", help="P48: parity report vs the legacy semantic layer")
    p_shadow.add_argument("--root", default=".")
    p_shadow.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    actions = {"status": cmd_status, "impact": cmd_impact,
               "shadow": cmd_shadow}
    return actions[args.graph_action](args)


if __name__ == "__main__":
    raise SystemExit(main())
