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
