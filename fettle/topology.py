"""Topology intelligence — footprint prediction + disjointness (WP-159, B1).

The core question before parallelizing work items across agents: will their
edits collide? A work item's *predicted footprint* is its declared ``scope``
globs expanded against the repo, widened one hop along the import graph
(files that import a seed file are plausible edit sites — signature changes
ripple to callers). Two items whose footprints intersect must NOT run in
parallel — this closes the cross-agent semantic-conflict gap named in the
v1.3 retrospective *before* the merge, not at it.

Items with no declared scope have an unknowable footprint and are treated
as conflicting with everything (conservative by design — declare scope to
unlock parallelism).

TLA+ formal spec: specs/tla/WorkItemClaims.tla
Verified invariants: S3 UnknownScopeConservative, S4 ClaimBeforeWork.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field


@dataclass
class Footprint:
    item_id: str
    seeds: set[str] = field(default_factory=set)      # repo-relative, from scope globs
    expanded: set[str] = field(default_factory=set)   # seeds + 1-hop import dependents
    unknown: bool = False                             # no scope declared


@dataclass
class Conflict:
    item_a: str
    item_b: str
    overlap: list[str]   # repo-relative paths (empty when unknown-footprint)
    reason: str


def _repo_files(root: str) -> list[str]:
    """All tracked-ish files, repo-relative — skips dot dirs and caches."""
    skip = {"__pycache__", "node_modules", ".venv", "venv"}
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(".") and d not in skip]
        for fname in filenames:
            out.append(os.path.relpath(os.path.join(dirpath, fname), root))
    return out


def _match_scope(files: list[str], patterns: list[str]) -> set[str]:
    matched: set[str] = set()
    for pattern in patterns:
        for path in files:
            if fnmatch.fnmatch(path, pattern):
                matched.add(path)
            elif pattern.endswith("/**") and (
                    path == pattern[:-3] or path.startswith(pattern[:-3] + "/")):
                matched.add(path)
            elif pattern.startswith("**/") and fnmatch.fnmatch(path, pattern[3:]):
                matched.add(path)
    return matched


def predict_footprint(root: str, item_id: str, scope: list[str]) -> Footprint:
    """Expand an item's scope globs, then widen one hop along the import graph."""
    if not scope:
        return Footprint(item_id=item_id, unknown=True)

    from fettle.import_graph import dependents_of

    seeds = _match_scope(_repo_files(root), scope)
    expanded = set(seeds)
    for rel in seeds:
        if not rel.endswith(".py"):
            continue
        for dep in dependents_of(os.path.join(root, rel), root):
            expanded.add(os.path.relpath(dep, root))
    return Footprint(item_id=item_id, seeds=seeds, expanded=expanded)


def find_conflicts(footprints: list[Footprint]) -> list[Conflict]:
    """Pairwise disjointness check. Any conflict → those items must not parallelize."""
    conflicts: list[Conflict] = []
    for i, a in enumerate(footprints):
        for b in footprints[i + 1:]:
            if a.unknown or b.unknown:
                culprit = a.item_id if a.unknown else b.item_id
                conflicts.append(Conflict(
                    a.item_id, b.item_id, [],
                    f"'{culprit}' declares no scope — footprint unknowable; "
                    f"add 'scope:' globs to its work item to unlock parallelism",
                ))
                continue
            overlap = sorted(a.expanded & b.expanded)
            if overlap:
                shown = ", ".join(overlap[:5])
                more = f" (+{len(overlap) - 5} more)" if len(overlap) > 5 else ""
                conflicts.append(Conflict(
                    a.item_id, b.item_id, overlap,
                    f"predicted footprints overlap on {shown}{more} "
                    f"(scope + 1-hop import dependents)",
                ))
    return conflicts


# ── WP-159 B2: topology advice ──────────────────────────────────────────────
#
# Deterministic, explainable catalogue (no LLM):
#   solo                      — 0–1 items, low risk
#   writer-reviewer           — 1 item, elevated risk (trace block rate)
#   pipeline                  — 1 spec-linked item (plan → implement → UAT)
#   parallel-workers          — ≥2 items with pairwise-disjoint footprints

_RISK_MIN_DECISIONS = 20     # below this the trace says nothing
_RISK_BLOCK_RATE = 0.10      # ≥10% blocked/violation decisions = elevated


def _trace_risk(days: int = 30) -> tuple[bool, str]:
    """(elevated, rationale) from the recent audit trail — never raises."""
    try:
        import time
        from fettle.trace import get_recent_decisions
        cutoff = time.time() - days * 86400
        recent = [e for e in get_recent_decisions(limit=10000)
                  if e.get("ts", 0) > cutoff]
        if len(recent) < _RISK_MIN_DECISIONS:
            return False, f"trace too thin to judge risk ({len(recent)} decisions)"
        flagged = sum(1 for e in recent
                      if e.get("status") in ("blocked", "block", "violation"))
        rate = flagged / len(recent)
        if rate >= _RISK_BLOCK_RATE:
            return True, (f"elevated friction: {flagged}/{len(recent)} decisions "
                          f"({rate:.0%}) were blocks/violations in the last {days}d")
        return False, f"low friction: {rate:.0%} blocks/violations in the last {days}d"
    except Exception:  # noqa: BLE001 — advice must not crash on a bad trace
        return False, "trace unreadable — risk unknown"


def advise(root: str, days: int = 30) -> dict:
    """Recommend a topology for the repo's open work items, with rationale."""
    from fettle.work_items import discover_work_items

    items = [item for item, _ in discover_work_items(root)
             if item and item.status == "open"]
    rationale: list[str] = []

    if not items:
        return {"topology": "solo", "items": [], "conflicts": [],
                "rationale": ["no open work items — nothing to delegate"],
                "commands": []}

    if len(items) == 1:
        item = items[0]
        risky, risk_note = _trace_risk(days)
        rationale.append(f"one open work item: {item.item_id}")
        rationale.append(risk_note)
        if item.spec:
            rationale.append(f"item links spec '{item.spec}' — scenario-driven "
                             f"pipeline (plan → implement → fettle uat) fits")
            return {"topology": "pipeline", "items": [item.item_id],
                    "conflicts": [], "rationale": rationale,
                    "commands": [f"fettle spawn claude --task 'implement {item.item_id}' "
                                 f"--worktree {item.item_id}",
                                 "fettle uat run --surface auto"]}
        if risky:
            return {"topology": "writer-reviewer", "items": [item.item_id],
                    "conflicts": [], "rationale": rationale,
                    "commands": [f"fettle spawn claude --task 'implement {item.item_id}' "
                                 f"--worktree {item.item_id}",
                                 f"fettle spawn codex --task 'review the changes for {item.item_id} "
                                 f"with fresh context'"]}
        return {"topology": "solo", "items": [item.item_id], "conflicts": [],
                "rationale": rationale, "commands": []}

    footprints = [predict_footprint(root, i.item_id, i.scope) for i in items]
    conflicts = find_conflicts(footprints)
    item_ids = [i.item_id for i in items]

    if conflicts:
        for c in conflicts:
            rationale.append(f"REFUSING to parallelize {c.item_a} ∥ {c.item_b}: {c.reason}")
        rationale.append("run conflicting items sequentially (solo), or narrow "
                         "their scopes until footprints are disjoint")
        return {"topology": "solo", "items": item_ids,
                "conflicts": [{"a": c.item_a, "b": c.item_b,
                               "overlap": c.overlap, "reason": c.reason}
                              for c in conflicts],
                "rationale": rationale, "commands": []}

    rationale.append(f"{len(items)} open work items with pairwise-disjoint "
                     f"predicted footprints (scope + 1-hop import dependents)")
    commands = [f"fettle spawn claude --task 'implement {iid}' --worktree {iid}"
                for iid in item_ids]
    commands.append("# integrator: merge fettle/<item> branches; fettle ci wait arbitrates")
    return {"topology": "parallel-workers", "items": item_ids, "conflicts": [],
            "rationale": rationale, "commands": commands}


def render_advice(data: dict) -> str:
    lines = [f"── Topology advice: {data['topology']} ──", ""]
    for note in data["rationale"]:
        lines.append(f"  · {note}")
    if data["commands"]:
        lines.append("")
        lines.append("  suggested:")
        for cmd in data["commands"]:
            lines.append(f"    {cmd}")
    return "\n".join(lines)
