"""`fettle brief` — one poll for orchestrators (v1.6 slice C).

Everything an orchestrating agent needs to supervise a session or a
multi-agent topology, in one machine-readable call instead of five file
parses: active plan, claims, topology workers, cached CI verdict, open
rule proposals, recent friction, latest completion reports.

Read-only. Offline: the CI verdict comes from the cached stamp
(.fettle/ci-status.json), never the network.
"""

from __future__ import annotations

import json
from pathlib import Path


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def compute_brief(root: Path, days: int = 7) -> dict:
    from fettle.report import compute_effectiveness
    from fettle.rules_cmd import list_rules
    from fettle.session_plan import active_plan
    from fettle.session_report import load_reports
    from fettle.topology_apply import load_manifest, topology_status
    from fettle.work_items import load_claims

    root = Path(root)

    plan = active_plan(root, max_age_hours=24.0)

    try:
        claims = load_claims(str(root))
    except (OSError, json.JSONDecodeError):
        claims = {}

    topology = None
    if load_manifest(str(root)):
        status = topology_status(str(root))
        if "error" not in status:
            topology = {
                "topology": status["topology"],
                "workers": [{
                    "item": w["item"],
                    "claimed": w["claimed"],
                    "decisions": w["decisions"],
                    "blocks": w["blocks"],
                    "stop_loss_breached": w["stop_loss_breached"],
                    "last_activity": w["last_activity"],
                } for w in status["workers"]],
            }

    ci = _read_json(root / ".fettle" / "ci-status.json")
    verify = _read_json(root / ".fettle" / "verify.json")

    rules = list_rules(root)
    proposals = [r["id"] for r in rules if r.get("stage") == "proposed"]

    friction = compute_effectiveness(days)
    top = friction.get("top_violations", []) if isinstance(friction, dict) else []
    top_friction = [{"code": code, "count": count} for code, count in top[:3] if count]

    return {
        "repo": root.name,
        "plan": ({"title": plan["title"], "done": plan["done"],
                  "total": plan["total"]} if plan else None),
        "claims": {item: c.get("session_id", "") for item, c in claims.items()},
        "topology": topology,
        "ci": ({"ok": bool(ci.get("ok")), "sha": ci.get("sha", ""),
                "overall": ci.get("overall", "")} if ci else None),
        "verify": ({"ok": bool(verify.get("ok"))} if verify else None),
        "open_proposals": proposals,
        "top_friction": top_friction,
        "completion_reports": [{
            "session_id": r.get("session_id", ""),
            "ts": r.get("ts", ""),
            "files_edited_count": r.get("files_edited_count", 0),
            "claims_held": r.get("claims_held", []),
            "plan": r.get("plan"),
        } for r in load_reports(str(root))[:5]],
    }


def render_brief(data: dict) -> str:
    lines = [f"── fettle brief: {data['repo']} ──", ""]
    plan = data["plan"]
    lines.append(f"  plan      {plan['title']} ({plan['done']}/{plan['total']} done)"
                 if plan else "  plan      none active")
    if data["claims"]:
        held = ", ".join(f"{i} ({s or 'unknown'})" for i, s in data["claims"].items())
        lines.append(f"  claims    {held}")
    else:
        lines.append("  claims    none")
    topo = data["topology"]
    if topo:
        lines.append(f"  topology  {topo['topology']}")
        for w in topo["workers"]:
            flag = "  STOP-LOSS" if w["stop_loss_breached"] else ""
            lines.append(f"            {w['item']:<24} blocks {w['blocks']:>2}"
                         f"/{w['decisions']:<4}{flag}")
    ci = data["ci"]
    lines.append(f"  ci        {ci['overall'] or ('green' if ci['ok'] else 'red')} "
                 f"@ {ci['sha'][:12]}" if ci else "  ci        no cached verdict")
    verify = data["verify"]
    lines.append(f"  verify    {'green' if verify['ok'] else 'red'}"
                 if verify else "  verify    no stamp")
    lines.append(f"  proposals {len(data['open_proposals'])} awaiting review"
                 + (f": {', '.join(data['open_proposals'][:3])}"
                    if data["open_proposals"] else ""))
    if data["top_friction"]:
        f = ", ".join(f"{x['code']} ({x['count']})" for x in data["top_friction"])
        lines.append(f"  friction  {f}")
    if data["completion_reports"]:
        lines.append(f"  reports   {len(data['completion_reports'])} recent "
                     "completion report(s) in .fettle/reports/")
    return "\n".join(lines)
