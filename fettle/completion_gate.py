"""Hook enforcement for authoritative milestone completion manifests."""

from __future__ import annotations

from pathlib import Path

from fettle.completion import evaluate_manifests, render_completion
from fettle.dispatcher_types import CheckResult


def run_check(ctx):
    cfg = ctx.config.get("gates", {}).get("completion", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()
    if ctx.event == "PostToolUse":
        target = ctx.target_path
        if target is None:
            return CheckResult.allow()
        try:
            relative = target.resolve().relative_to(ctx.cwd.resolve())
        except ValueError:
            return CheckResult.allow()
        if relative.parent != Path("docs/completion"):
            return CheckResult.allow()
    result = evaluate_manifests(ctx.cwd)
    # Honest work in progress is allowed; malformed or contradictory claims are not.
    if result.valid:
        return CheckResult.allow()
    message = "Completion gate:\n" + render_completion(result).rstrip()
    if cfg.get("mode", "advisory") == "enforce":
        return CheckResult.block(message, action="Run: fettle completion validate")
    return CheckResult.advisory(message, action="Run: fettle completion validate")
