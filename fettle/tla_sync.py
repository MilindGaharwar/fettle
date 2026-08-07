"""[gates.tla_sync] — TLA+ spec staleness advisory.

Fires on PostToolUse(Write|Edit) when the edited file is covered by a TLA+
formal spec. Emits a one-per-session advisory reminding the developer to
re-verify the spec after protocol changes.

This is a lightweight sync mechanism — the real enforcement is CI
(.github/workflows/tla-verify.yml) which runs TLC on protocol file changes.
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


def run_check(ctx: HookContext) -> CheckResult:
    """PostToolUse: advisory when a TLA+-verified file is edited."""
    if ctx.input.hook_event_name != "PostToolUse":
        return CheckResult.allow()

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

    session_key = f"{ctx.session_id or ''}:{spec}"
    if session_key in _advised_this_session:
        return CheckResult.allow()
    _advised_this_session.add(session_key)

    msg = (
        f"TLA+ sync: {rel_normalized} is formally verified by {spec}. "
        f"Run: ./specs/tla/run-all.sh {Path(spec).stem}"
    )
    return CheckResult.advisory(msg)
