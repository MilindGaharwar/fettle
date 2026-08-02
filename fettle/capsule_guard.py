"""Capsule guard — fail-closed tamper check for delegated policy (Stage A, A3).

First PreToolUse check in the registry. When $FETTLE_POLICY_CAPSULE asserts
a capsule that is missing or tampered, every tool call is blocked (D-A4 —
tampering is the attack regardless of whether the cwd has a .fettle.toml).
A verified capsule whose monotonic merge suppressed weaker local overrides
gets a once-per-session advisory naming them (silent policy correction is
its own failure mode).

Design doc: docs/engagement/12-stage-a-policy-continuity.md §2.4.
"""

from __future__ import annotations

from fettle.dispatcher_types import CheckResult, HookContext


def run_check(ctx: HookContext) -> CheckResult:
    from fettle.policy_capsule import last_ignored, resolve_env_capsule

    doc, err = resolve_env_capsule()
    if err:
        return CheckResult.block(
            f"Delegated policy capsule failed verification: {err}. "
            "This session was spawned under a policy that can no longer be "
            "trusted — re-spawn via `fettle spawn` or unset "
            "FETTLE_POLICY_CAPSULE if this session is genuinely standalone.",
            hook_specific_output={
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"policy capsule tampered or missing: {err}",
            },
        )

    ignored = last_ignored()
    if doc and ignored and not _already_advised(ctx):
        keys = ", ".join(item["key"] for item in ignored[:5])
        more = f" (+{len(ignored) - 5} more)" if len(ignored) > 5 else ""
        return CheckResult.advisory(
            f"Delegated policy capsule overrode {len(ignored)} weaker local "
            f"setting(s): {keys}{more}. Children may only tighten policy."
        )
    return CheckResult.allow()


def _already_advised(ctx: HookContext) -> bool:
    """Once-per-session stamp (ci_bootstrap precedent) — never raises."""
    try:
        from fettle.config import state_dir
        stamp = state_dir(ctx.session_id or "unknown") / "capsule_advised"
        if stamp.exists():
            return True
        stamp.touch()
        return False
    except OSError:
        return True  # cannot stamp → stay quiet rather than spam
