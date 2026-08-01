"""[gates.claims] — claim-before-work gate (Stage 4, S4.3; Wayfinder invariant).

Applies only inside a *fettle-managed* linked worktree (branch
``fettle/<item-id>``): an edit there with no claimed work item gets an
advisory naming the fix (``fettle work claim <id>``). Main-worktree edits
are always exempt — the solo flow stays frictionless.

Off by default. Modes: advisory | enforce (WP4 MODE_ENUMS).
"""

from __future__ import annotations

from fettle.dispatcher_types import CheckResult, HookContext


def run_check(ctx: HookContext) -> CheckResult:
    """Dispatcher entry point: PostToolUse on Write/Edit."""
    cfg = ctx.config.get("gates", {}).get("claims", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    cwd = str(ctx.cwd)

    from fettle.worktrees import _git, is_linked_worktree
    if not is_linked_worktree(cwd):
        return CheckResult.allow()  # main worktree — solo flow exempt

    branch_out, err = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    if err or not branch_out.strip().startswith("fettle/"):
        return CheckResult.allow()  # not a fettle-managed worktree

    toplevel_out, err = _git(["rev-parse", "--show-toplevel"], cwd)
    if err:
        return CheckResult.allow()
    worktree = toplevel_out.strip()

    from fettle.work_items import claim_for_worktree
    if claim_for_worktree(cwd, worktree):
        return CheckResult.allow()

    item_hint = branch_out.strip().removeprefix("fettle/")
    msg = (
        f"Claims gate: this worktree ({worktree}) has no claimed work item — "
        f"claim one before editing: fettle work claim {item_hint}"
    )
    if cfg.get("mode", "advisory") == "enforce":
        return CheckResult.block(msg, hook_specific_output={
            "hookEventName": ctx.input.hook_event_name,
            "additionalContext": msg,
        })
    return CheckResult.advisory(msg, hook_specific_output={
        "hookEventName": ctx.input.hook_event_name,
        "additionalContext": msg,
    })
