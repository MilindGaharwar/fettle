"""[gates.claims] — claim-before-work gate (Stage 4, S4.3; Wayfinder invariant).

Applies inside a *fettle-managed* linked worktree (branch
``fettle/<item-id>``): an edit there with no claimed work item gets an
advisory naming the fix (``fettle work claim <id>``). Main-worktree edits
are exempt by default (the solo flow stays frictionless) — unless
``[worktrees].require = true`` (WP-162), in which case non-exempt
main-worktree edits are gated too, honoring ``gates.claims.mode``.

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
        return _check_main_worktree(ctx, cfg, cwd)

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


def _check_main_worktree(ctx: HookContext, cfg: dict, cwd: str) -> CheckResult:
    """[worktrees].require (WP-162): gate non-exempt main-worktree edits."""
    wt_cfg = ctx.config.get("worktrees", {})
    if not wt_cfg.get("require", False):
        return CheckResult.allow()  # default: solo flow exempt

    target = ctx.target_path
    if target is None:
        return CheckResult.allow()

    from fettle.boundary_rules import _matches_glob
    from fettle.paths import find_repo_root
    repo_root = find_repo_root(cwd)
    try:
        rel = str(target.resolve().relative_to(repo_root)) if repo_root else str(target)
    except ValueError:
        rel = str(target)
    exempt = wt_cfg.get("exempt_paths", ["docs/**", "**/*.md"])
    # `**/*.md` must also match top-level files (fnmatch needs the slash).
    if any(_matches_glob(rel, p)
           or (p.startswith("**/") and _matches_glob(rel, p[3:]))
           for p in exempt):
        return CheckResult.allow()

    msg = (
        f"Claims gate: [worktrees].require is on — main-worktree edit to "
        f"{rel} requires a work-item worktree: "
        f"fettle worktree create <id> && fettle work claim <id>"
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
