"""Fettle insights — periodic digest from the evidence stores (WP-163, C4).

Cross-session memory the hermes way, kept honest: everything here is
*recomputed* from the trace, CI history, rule dirs, and ratchet evidence.
Nothing is written, nothing is sent, nothing acts (D-C5) — a digest with
side effects would be a daemon in disguise.

Sections: friction gates, emerging failure signatures, the rule pipeline,
and lineage anomalies. Run it weekly (cron recipes in docs/CONFIG.md).
"""

from __future__ import annotations

from pathlib import Path


def compute_insights(root: Path, days: int = 7) -> dict:
    """The four-section digest, all sources recomputed on demand."""
    from fettle.evolution import detect_signatures
    from fettle.lineage_report import compute_lineage
    from fettle.report import compute_effectiveness
    from fettle.rules_cmd import promotion_candidates

    effectiveness = compute_effectiveness(days=days)
    friction = []
    if "error" not in effectiveness:
        by_hook = effectiveness.get("by_hook", {})
        by_status = effectiveness.get("by_status", {})
        friction = sorted(by_hook.items(), key=lambda kv: -kv[1])[:5]
        friction = [{"hook": h, "decisions": n} for h, n in friction]
        friction_meta = {
            "total_decisions": effectiveness.get("total_decisions", 0),
            "blocked": by_status.get("blocked", 0) + by_status.get("block", 0),
            "violations": by_status.get("violation", 0),
        }
    else:
        friction_meta = {"total_decisions": 0, "blocked": 0, "violations": 0}

    signatures = [s.to_dict() for s in detect_signatures(root, days=days)]

    pipeline = promotion_candidates(root)

    lineage = compute_lineage(days=days)
    ungoverned = []
    if "error" not in lineage:
        ungoverned = [
            {"session_id": sid,
             "edits": node["counts"].get("edits", 0),
             "repo": node.get("repo", "")}
            for sid, node in lineage["sessions"].items()
            if node.get("ungoverned")
        ]

    return {
        "period_days": days,
        "friction": {"top_hooks": friction, **friction_meta},
        "signatures": signatures,
        "rule_pipeline": {
            "pending_proposals": len(pipeline["pending"]),
            "promote_candidates": [r["id"] for r in pipeline["promote"]],
            "demote_candidates": [r["id"] for r in pipeline["demote"]],
        },
        "lineage_anomalies": ungoverned,
    }


def render_insights(data: dict) -> str:
    days = data["period_days"]
    lines = [f"── Fettle Insights ({days}d) ──"]

    fr = data["friction"]
    lines.append(f"\nFriction — {fr['total_decisions']} decisions, "
                 f"{fr['blocked']} blocked, {fr['violations']} violations")
    for row in fr["top_hooks"]:
        lines.append(f"  • {row['hook']}: {row['decisions']}")
    if not fr["top_hooks"]:
        lines.append("  (no trace activity in the window)")

    sigs = data["signatures"]
    lines.append(f"\nEmerging failure signatures: {len(sigs)}")
    for s in sigs[:5]:
        draft = " — draftable (fettle learn --from-trace)" if s["draftable"] else ""
        lines.append(f"  • [{s['kind']}] {s['key']} ×{s['count']}{draft}")

    rp = data["rule_pipeline"]
    lines.append(f"\nRule pipeline — {rp['pending_proposals']} pending proposal(s)")
    if rp["promote_candidates"]:
        lines.append(f"  promote candidates: {', '.join(rp['promote_candidates'])}"
                     "  → fettle ratchet promote <id>")
    if rp["demote_candidates"]:
        lines.append(f"  demote candidates: {', '.join(rp['demote_candidates'])}"
                     "  → fettle rules demote <id> --reason ...")

    anomalies = data["lineage_anomalies"]
    lines.append(f"\nLineage anomalies: {len(anomalies)}")
    for a in anomalies[:5]:
        lines.append(f"  ⚠ ungoverned session {a['session_id']} "
                     f"({a['edits']} edit(s), repo {a['repo'] or '?'})")

    return "\n".join(lines)
