"""[gates.authorship] — role-based file authority enforcement (P52, WP-520).

Principle: the agent writing tests must never be the same agent writing the
implementation. The implementing agent must never be allowed to change tests.

Roles:
  solo          — unrestricted (default, backwards-compatible)
  implementer   — may edit implementation files only
  tester        — may edit test files only
  reviewer      — read-only (no edits permitted)

The role is carried in the policy capsule (``policy.role``) and subject to
monotonic-stricter merge: a child can only narrow its role, never widen it.

This gate fires on PreToolUse for Write and Edit, classifying the target file
and blocking if the session's role forbids that file category.
"""

from __future__ import annotations

import os
from pathlib import Path

from fettle.dispatcher_types import CheckResult, HookContext
from fettle.paths import classify_file

VALID_ROLES = frozenset({"solo", "implementer", "tester", "reviewer"})

# Strictness ladder: higher = more restricted.
ROLE_RANK: dict[str, int] = {
    "solo": 0,
    "implementer": 1,
    "tester": 1,
    "reviewer": 2,
}


def _resolve_role(config: dict) -> str:
    """Resolve the effective role from config (already capsule-merged)."""
    role = config.get("role", "solo")
    if isinstance(role, str) and role in VALID_ROLES:
        return role
    return "solo"


def run_check(ctx: HookContext) -> CheckResult:
    """PreToolUse gate: block file edits that violate the session's role."""
    cfg = ctx.config.get("gates", {}).get("authorship", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    event = ctx.input.hook_event_name
    if event != "PreToolUse":
        return CheckResult.allow()

    target = ctx.target_path
    if target is None:
        return CheckResult.allow()

    role = _resolve_role(ctx.config)
    if role == "solo":
        return CheckResult.allow()

    cwd = str(ctx.cwd)
    rel_path = os.path.relpath(str(target), cwd) if target.is_absolute() else str(target)
    file_kind = classify_file(rel_path)

    if role == "reviewer":
        msg = (
            f"Authorship gate: role 'reviewer' cannot edit files. "
            f"Attempted: {rel_path}"
        )
        return _decide(cfg, msg, event)

    if role == "implementer" and file_kind == "test":
        msg = (
            f"Authorship gate: role 'implementer' cannot edit test files. "
            f"Attempted: {rel_path}\n"
            f"Tests must be written by a separate 'tester' agent."
        )
        return _decide(cfg, msg, event)

    if role == "tester" and file_kind == "implementation":
        msg = (
            f"Authorship gate: role 'tester' cannot edit implementation files. "
            f"Attempted: {rel_path}\n"
            f"Implementation must be written by a separate 'implementer' agent."
        )
        return _decide(cfg, msg, event)

    return CheckResult.allow()


def _decide(cfg: dict, msg: str, event: str) -> CheckResult:
    hso = {"hookEventName": event, "additionalContext": msg}
    mode = cfg.get("mode", "advisory")
    if mode in ("enforce", "strict"):
        return CheckResult.block(msg, hook_specific_output=hso)
    return CheckResult.advisory(msg, hook_specific_output=hso)
