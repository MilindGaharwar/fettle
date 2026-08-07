"""[gates.tla_sync] — TLA+ spec staleness advisory.

Two enforcement points:

1. PostToolUse(Write|Edit): fires once per session when a verified source
   file is edited, reminding the developer to re-run TLC.

2. Stop: checks mtime of each edited verified file against its TLA+ spec.
   If any source file is newer than its spec, emits an advisory that the
   spec may be stale.

The real hard enforcement is CI (.github/workflows/tla-verify.yml) which
runs TLC on protocol file changes.
"""

from __future__ import annotations

import os
from pathlib import Path

from fettle.dispatcher_types import CheckResult, HookContext

# Map: source file (repo-relative) -> TLA+ spec that models it.
VERIFIED_FILES: dict[str, str] = {
    "fettle/policy_capsule.py": "specs/tla/PolicyCapsule.tla",
    "fettle/capsule_guard.py": "specs/tla/PolicyCapsule.tla",
    "fettle/work_items.py": "specs/tla/WorkItemClaims.tla",
    "fettle/topology.py": "specs/tla/WorkItemClaims.tla",
    "fettle/worktrees.py": "specs/tla/WorkItemClaims.tla",
}

_advised_this_session: set[str] = set()
_edited_verified_files: set[str] = set()


def run_check(ctx: HookContext) -> CheckResult:
    """PostToolUse advisory + Stop staleness check."""
    event = ctx.input.hook_event_name

    if event == "PostToolUse":
        return _post_tool_use(ctx)
    if event == "Stop":
        return _stop_check(ctx)
    return CheckResult.allow()


def _post_tool_use(ctx: HookContext) -> CheckResult:
    target = ctx.target_path
    if target is None:
        return CheckResult.allow()

    cwd = str(ctx.cwd)
    try:
        rel = os.path.relpath(str(target), cwd)
    except ValueError:
        return CheckResult.allow()

    rel_normalized = rel.replace("\\", "/")
    spec = VERIFIED_FILES.get(rel_normalized)
    if not spec:
        return CheckResult.allow()

    _edited_verified_files.add(rel_normalized)

    session_key = f"{ctx.session_id or ''}:{spec}"
    if session_key in _advised_this_session:
        return CheckResult.allow()
    _advised_this_session.add(session_key)

    msg = (
        f"TLA+ sync: {rel_normalized} is formally verified by {spec}. "
        f"Run: ./specs/tla/run-all.sh {Path(spec).stem}"
    )
    return CheckResult.advisory(msg)


def _stop_check(ctx: HookContext) -> CheckResult:
    """At session end, check if any edited verified files are newer than their specs."""
    if not _edited_verified_files:
        return CheckResult.allow()

    cwd = ctx.cwd
    stale_specs: list[str] = []

    for src_rel in _edited_verified_files:
        spec_rel = VERIFIED_FILES.get(src_rel)
        if not spec_rel:
            continue
        src_path = cwd / src_rel
        spec_path = cwd / spec_rel
        if not spec_path.is_file():
            stale_specs.append(f"{spec_rel} (missing)")
            continue
        if not src_path.is_file():
            continue
        if src_path.stat().st_mtime > spec_path.stat().st_mtime:
            stale_specs.append(spec_rel)

    if not stale_specs:
        return CheckResult.allow()

    unique = sorted(set(stale_specs))
    msg = (
        f"TLA+ staleness: {len(_edited_verified_files)} verified source file(s) "
        f"edited this session are newer than their spec(s): {', '.join(unique)}. "
        f"Run: ./specs/tla/run-all.sh"
    )
    return CheckResult.advisory(msg)
