"""``fettle topology apply`` / ``status`` / controls (WP-160/161, B3–B4).

``apply`` materializes an advised (or explicitly chosen) topology:
provisions per-item worktrees + claims, and writes a ``topology.json``
manifest to the shared git common dir (coordination substrate — visible
from every worktree, never committed). Runner launches stay explicit:
apply prints ready-to-run ``fettle spawn`` commands, or executes them
sequentially with ``--run`` (no daemon — v1.4 non-goal).

``status`` joins the manifest with live claims and the audit trail;
stop-loss breaches (max blocks per session) are flagged, and ``revoke``
releases an item's claim.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def _manifest_path(root: str) -> Path | None:
    from fettle.worktrees import git_common_dir
    common = git_common_dir(root)
    if not common:
        return None
    d = common / "fettle"
    d.mkdir(parents=True, exist_ok=True)
    return d / "topology.json"


def load_manifest(root: str) -> dict | None:
    path = _manifest_path(root)
    if not path or not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def apply_topology(root: str, runner_name: str = "claude",
                   days: int = 30) -> dict:
    """Provision the advised topology. Returns the manifest (with any errors).

    Non-solo topologies get: worktree + claim per item, manifest written,
    spawn commands listed. Solo (including conflict-refusals) provisions
    nothing — the advice explains why.
    """
    from fettle.topology import advise
    from fettle.work_items import claim_item
    from fettle.worktrees import create_worktree, worktrees_root
    from fettle.config import load_config

    advice = advise(root, days=days)
    manifest: dict = {
        "topology": advice["topology"],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "runner": runner_name,
        "items": [],
        "rationale": advice["rationale"],
        "errors": [],
    }
    if advice["topology"] == "solo":
        manifest["errors"] = [c["reason"] for c in advice.get("conflicts", [])]
        return manifest

    config = load_config(root)
    session_id = f"topology-{int(time.time())}"
    for item_id in advice["items"]:
        wt_path = worktrees_root(root, config) / item_id
        if not wt_path.is_dir():
            created, err = create_worktree(root, item_id, config)
            if err:
                manifest["errors"].append(f"{item_id}: worktree failed: {err}")
                continue
            wt_path = created
        claim_err = claim_item(root, item_id, session_id, str(wt_path))
        if claim_err:
            manifest["errors"].append(f"{item_id}: claim failed: {claim_err}")
            continue
        manifest["items"].append({
            "item": item_id,
            "worktree": str(wt_path),
            "session_id": session_id,
            "spawn": f"fettle spawn {runner_name} "
                     f"--task 'implement {item_id}' --worktree {item_id}",
        })

    if manifest["items"] and not config.get("worktrees", {}).get("require", False):
        manifest["rationale"].append(
            "recommended: set [worktrees].require = true so main-worktree "
            "edits are gated while this topology is live")

    path = _manifest_path(root)
    if path:
        path.write_text(json.dumps(manifest, indent=2) + "\n")
        manifest["manifest_path"] = str(path)
    else:
        manifest["errors"].append("not a git repo — manifest not written")
    return manifest


# ── B4: status + controls ───────────────────────────────────────────────────

DEFAULT_MAX_BLOCKS = 10   # stop-loss: blocks per session before flagging


def topology_status(root: str, max_blocks: int = DEFAULT_MAX_BLOCKS) -> dict:
    """Join manifest × live claims × trace into a per-worker table."""
    from fettle.trace import get_recent_decisions
    from fettle.work_items import load_claims

    manifest = load_manifest(root)
    if not manifest:
        return {"error": "no topology manifest — run `fettle topology apply` first"}

    claims = load_claims(root)
    entries = get_recent_decisions(limit=10000)
    by_session: dict[str, dict] = {}
    for e in entries:
        sid = e.get("session_id", "")
        if not sid:
            continue
        s = by_session.setdefault(sid, {"blocks": 0, "decisions": 0, "last_ts": 0.0})
        s["decisions"] += 1
        if e.get("status") in ("blocked", "block"):
            s["blocks"] += 1
        s["last_ts"] = max(s["last_ts"], e.get("ts", 0.0))

    workers = []
    for entry in manifest["items"]:
        item = entry["item"]
        claim = claims.get(item, {})
        sid = claim.get("session_id", entry.get("session_id", ""))
        activity = by_session.get(sid, {"blocks": 0, "decisions": 0, "last_ts": 0.0})
        workers.append({
            "item": item,
            "worktree": entry["worktree"],
            "claimed": bool(claim),
            "session_id": sid,
            "decisions": activity["decisions"],
            "blocks": activity["blocks"],
            "last_activity": (time.strftime("%Y-%m-%dT%H:%M:%S",
                                            time.localtime(activity["last_ts"]))
                              if activity["last_ts"] else ""),
            "stop_loss_breached": activity["blocks"] >= max_blocks,
        })
    return {
        "topology": manifest["topology"],
        "created_at": manifest["created_at"],
        "max_blocks": max_blocks,
        "workers": workers,
    }


def revoke_item(root: str, item_id: str) -> str:
    """Release an item's claim and drop it from the manifest. '' on success."""
    from fettle.work_items import release_item

    err = release_item(root, item_id)
    if err and "not claimed" not in err:
        return err
    manifest = load_manifest(root)
    if manifest:
        before = len(manifest["items"])
        manifest["items"] = [e for e in manifest["items"] if e["item"] != item_id]
        if len(manifest["items"]) != before:
            path = _manifest_path(root)
            if path:
                path.write_text(json.dumps(manifest, indent=2) + "\n")
            return ""
    return err or ""


# ── v1.6 slice C: outcome report — did the advice hold? ─────────────────────


def _rel_files(files: list[str], root: str) -> set[str]:
    import os
    rroot = os.path.abspath(root)
    out: set[str] = set()
    for f in files:
        if os.path.isabs(f):
            af = os.path.abspath(f)
            if af.startswith(rroot + os.sep):
                out.add(os.path.relpath(af, rroot))
            else:
                out.add(f)
        else:
            out.add(f)
    return out


def topology_report(root: str) -> dict:
    """Predicted-vs-actual join over the live/last topology (read-only).

    D-C2: facts, not verdicts — predicted footprints (recomputed), actual
    edited files (from completion reports), pairwise actual overlaps,
    per-worker friction, verify/CI stamp state. Interpretation stays
    human (or `fettle insights`).
    """
    from fettle.session_report import load_reports
    from fettle.topology import predict_footprint
    from fettle.work_items import discover_work_items

    manifest = load_manifest(root)
    if not manifest:
        return {"error": "no topology manifest — run `fettle topology apply` first"}
    status = topology_status(root)

    scopes: dict[str, list[str]] = {}
    for item, _path in discover_work_items(root):
        if item:
            scopes[item.item_id] = item.scope
    reports = {r.get("session_id", ""): r for r in load_reports(root)}

    rows: list[dict] = []
    actual_by_item: dict[str, set[str]] = {}
    for w in status.get("workers", []):
        iid = w["item"]
        fp = predict_footprint(root, iid, scopes.get(iid, []))
        rep = reports.get(w["session_id"])
        actual = _rel_files(rep.get("files_edited", []), root) if rep else set()
        actual_by_item[iid] = actual
        predicted = sorted(fp.expanded) if not fp.unknown else []
        outside = sorted(actual - set(predicted)) if predicted else []
        verify = (rep or {}).get("verify") or {}
        ci = (rep or {}).get("ci") or {}
        rows.append({
            "item": iid,
            "session_id": w["session_id"],
            "report_present": rep is not None,
            "predicted_files": len(predicted),
            "predicted_unknown": fp.unknown,
            "actual_files": len(actual),
            "outside_prediction": outside[:10],
            "decisions": w["decisions"],
            "blocks": w["blocks"],
            "stop_loss_breached": w["stop_loss_breached"],
            "verify_ok": bool(verify.get("ok")),
            "ci_ok": bool(ci.get("ok")),
            "plan": (rep or {}).get("plan"),
        })

    overlaps: list[dict] = []
    items = sorted(actual_by_item)
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            shared = sorted(actual_by_item[a] & actual_by_item[b])
            if shared:
                overlaps.append({"a": a, "b": b, "files": shared[:10],
                                 "count": len(shared)})

    return {
        "topology": manifest["topology"],
        "created_at": manifest["created_at"],
        "workers": rows,
        "actual_overlaps": overlaps,
        "prediction_held": not overlaps,
    }


def render_topology_report(data: dict) -> str:
    if "error" in data:
        return data["error"]
    lines = [f"── Topology outcome: {data['topology']} "
             f"(since {data['created_at']}) ──", ""]
    for w in data["workers"]:
        verdicts = []
        if w["predicted_unknown"]:
            verdicts.append("footprint unknown")
        if w["outside_prediction"]:
            verdicts.append(f"{len(w['outside_prediction'])}+ files outside prediction")
        if w["stop_loss_breached"]:
            verdicts.append("STOP-LOSS")
        plan = w.get("plan")
        plan_s = f" plan {plan['done']}/{plan['total']}" if plan else ""
        lines.append(
            f"  {w['item']:<24} edits {w['actual_files']:>3} "
            f"(predicted {w['predicted_files']:>3})  "
            f"blocks {w['blocks']:>2}/{w['decisions']:<4} "
            f"verify {'✓' if w['verify_ok'] else '·'} "
            f"ci {'✓' if w['ci_ok'] else '·'}"
            f"{plan_s}"
            + (f"  [{', '.join(verdicts)}]" if verdicts else "")
            + ("" if w["report_present"] else "  (no completion report)"))
    lines.append("")
    if data["actual_overlaps"]:
        lines.append("  ✗ prediction did NOT hold — actual overlaps:")
        for o in data["actual_overlaps"]:
            lines.append(f"    {o['a']} ∩ {o['b']}: {o['count']} file(s) — "
                         f"{', '.join(o['files'][:5])}")
    else:
        lines.append("  ✓ disjointness prediction held (no actual overlaps)")
    return "\n".join(lines)


def render_status(data: dict) -> str:
    if "error" in data:
        return data["error"]
    lines = [f"── Topology: {data['topology']} (since {data['created_at']}, "
             f"stop-loss {data['max_blocks']} blocks) ──", ""]
    for w in data["workers"]:
        flags = []
        if not w["claimed"]:
            flags.append("UNCLAIMED")
        if w["stop_loss_breached"]:
            flags.append("⚠ STOP-LOSS")
        flag_s = ("  [" + ", ".join(flags) + "]") if flags else ""
        last = w["last_activity"] or "no activity"
        lines.append(f"  {w['item']}: {w['worktree']} — "
                     f"decisions {w['decisions']} · blocks {w['blocks']} · "
                     f"{last}{flag_s}")
    if not data["workers"]:
        lines.append("  (no active workers)")
    return "\n".join(lines)


def render_apply(manifest: dict) -> str:
    lines = [f"── Topology apply: {manifest['topology']} ──", ""]
    for note in manifest["rationale"]:
        lines.append(f"  · {note}")
    if manifest["items"]:
        lines.append("")
        lines.append("  provisioned:")
        for entry in manifest["items"]:
            lines.append(f"    {entry['item']} → {entry['worktree']}")
        lines.append("")
        lines.append("  launch workers:")
        for entry in manifest["items"]:
            lines.append(f"    {entry['spawn']}")
    for err in manifest["errors"]:
        lines.append(f"  ✗ {err}")
    return "\n".join(lines)
