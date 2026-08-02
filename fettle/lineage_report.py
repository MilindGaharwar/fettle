"""``fettle report --lineage`` — delegation-chain forest from the trace (WP-158, A6).

Groups trace entries by session, builds the parent→child forest from
``parent_session_id``, and renders a tree with per-node activity counts and
capsule digests. Sessions with edit activity but no capsule, in a repo whose
``[gates.agent_spawn].mode`` is ``enforce``, are flagged ``UNGOVERNED`` —
that flag is the auditor-facing answer to "which policy governed this edit?".
"""

from __future__ import annotations

import time
from collections import Counter

_EDIT_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})


def compute_lineage(days: int = 30) -> dict:
    """Build the session forest from recent trace entries."""
    from fettle.trace import get_recent_decisions

    entries = get_recent_decisions(limit=10000)
    cutoff = time.time() - days * 86400
    recent = [e for e in entries if e.get("ts", 0) > cutoff]
    if not recent:
        return {"error": f"No trace data in the last {days} days."}

    sessions: dict[str, dict] = {}
    for entry in recent:
        sid = entry.get("session_id") or "(unknown)"
        node = sessions.setdefault(sid, {
            "session_id": sid,
            "parent_session_id": "",
            "capsule_digest": "",
            "repos": Counter(),
            "counts": Counter(),
            "first_ts": entry.get("ts", 0),
            "last_ts": entry.get("ts", 0),
        })
        if entry.get("parent_session_id"):
            node["parent_session_id"] = entry["parent_session_id"]
        if entry.get("capsule_digest"):
            node["capsule_digest"] = entry["capsule_digest"]
        if entry.get("repo"):
            node["repos"][entry["repo"]] += 1
        status = entry.get("status", "")
        if status in ("blocked", "block"):
            node["counts"]["blocks"] += 1
        elif status == "violation":
            node["counts"]["advisories"] += 1
        if entry.get("tool") in _EDIT_TOOLS:
            node["counts"]["edits"] += 1
        node["counts"]["decisions"] += 1
        node["first_ts"] = min(node["first_ts"], entry.get("ts", 0))
        node["last_ts"] = max(node["last_ts"], entry.get("ts", 0))
        # `spawn` entries name children in findings — keep the digest linkage.
        if entry.get("hook") == "spawn":
            node["counts"]["spawns"] += 1

    enforce = _agent_spawn_enforced()
    for node in sessions.values():
        node["repo"] = node["repos"].most_common(1)[0][0] if node["repos"] else ""
        del node["repos"]
        node["counts"] = dict(node["counts"])
        node["ungoverned"] = bool(
            enforce and node["counts"].get("edits", 0) > 0
            and not node["capsule_digest"]
        )

    roots = sorted(
        (sid for sid, n in sessions.items()
         if not n["parent_session_id"] or n["parent_session_id"] not in sessions),
        key=lambda sid: sessions[sid]["first_ts"],
    )
    children: dict[str, list[str]] = {}
    for sid, node in sessions.items():
        parent = node["parent_session_id"]
        if parent and parent in sessions:
            children.setdefault(parent, []).append(sid)
    for kids in children.values():
        kids.sort(key=lambda sid: sessions[sid]["first_ts"])

    return {
        "period_days": days,
        "total_sessions": len(sessions),
        "agent_spawn_enforced": enforce,
        "sessions": sessions,
        "roots": roots,
        "children": children,
    }


def _agent_spawn_enforced() -> bool:
    """Whether the current repo enforces governed spawns — never raises."""
    try:
        from fettle.config import load_config
        gate = load_config(".").get("gates", {}).get("agent_spawn", {})
        return bool(gate.get("enabled", True)) and gate.get("mode") == "enforce"
    except Exception:  # noqa: BLE001 — reporting must not crash on bad config
        return False


def render_lineage_tree(data: dict) -> str:
    """Human-readable forest."""
    if "error" in data:
        return data["error"]
    lines = [
        f"── Fettle Lineage ({data['period_days']}d, "
        f"{data['total_sessions']} session(s)) ──",
        "",
    ]

    def _render(sid: str, prefix: str, is_last: bool, is_root: bool = False) -> None:
        node = data["sessions"][sid]
        counts = node["counts"]
        connector = "" if is_root else ("└─ " if is_last else "├─ ")
        capsule = f"capsule {node['capsule_digest']}" if node["capsule_digest"] else "no capsule"
        flag = "  ⚠ UNGOVERNED" if node["ungoverned"] else ""
        repo = f" [{node['repo']}]" if node["repo"] else ""
        lines.append(
            f"{prefix}{connector}{sid}{repo} — {capsule} · "
            f"edits {counts.get('edits', 0)} · blocks {counts.get('blocks', 0)} · "
            f"advisories {counts.get('advisories', 0)}{flag}"
        )
        kids = data["children"].get(sid, [])
        child_prefix = prefix + ("" if is_root else ("   " if is_last else "│  "))
        for i, kid in enumerate(kids):
            _render(kid, child_prefix, i == len(kids) - 1)

    for i, root in enumerate(data["roots"]):
        _render(root, "", i == len(data["roots"]) - 1, is_root=True)
    return "\n".join(lines)
