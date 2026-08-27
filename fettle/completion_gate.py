"""Hook enforcement for authoritative milestone completion manifests."""

from __future__ import annotations

from pathlib import Path

from fettle.changeset import ChangeStatus, get_changed_files
from fettle.completion import evaluate_manifests, render_completion
from fettle.dispatcher_types import CheckResult
from fettle.work_items import _looks_like_work_item, parse_work_item


def run_check(ctx):
    cfg = ctx.config.get("gates", {}).get("completion", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()
    required_work_items: set[str] | None = None
    if ctx.event == "PostToolUse":
        target = ctx.target_path
        if target is None:
            return CheckResult.allow()
        try:
            relative = target.resolve().relative_to(ctx.cwd.resolve())
        except ValueError:
            return CheckResult.allow()
        if relative.parent == Path("docs/completion"):
            pass
        elif relative.suffix == ".md" and target.is_file():
            try:
                text = target.read_text(encoding="utf-8")
                item, findings = parse_work_item(text, str(relative))
            except (OSError, UnicodeError) as exc:
                message = f"Completion gate: cannot read work item {relative}: {exc}"
                return CheckResult.block(message, action="Fix the work-item file")
            if item is None and (_looks_like_work_item(text) or findings):
                message = f"Completion gate: malformed work item {relative}"
                return CheckResult.block(message, action="Fix the work-item frontmatter")
            if item is None:
                return CheckResult.allow()
            if not item.requires_completion:
                changed = get_changed_files(str(ctx.cwd))
                is_new = any(
                    changed_item.path.replace("\\", "/") == relative.as_posix()
                    and changed_item.status in {ChangeStatus.ADDED, ChangeStatus.UNTRACKED}
                    for changed_item in changed
                )
                if is_new:
                    message = (
                        f"Completion gate: work item {item.item_id} uses legacy format; "
                        "set fettle-work-item: v2"
                    )
                    return CheckResult.block(message, action="Migrate the work item to v2")
                return CheckResult.allow()
            if item.status != "done":
                return CheckResult.allow()
            required_work_items = {item.item_id}
        else:
            return CheckResult.allow()
    result = evaluate_manifests(ctx.cwd, required_work_items=required_work_items)
    # Honest work in progress is allowed; malformed or contradictory claims are not.
    if result.valid:
        return CheckResult.allow()
    message = "Completion gate:\n" + render_completion(result).rstrip()
    if cfg.get("mode", "advisory") == "enforce":
        return CheckResult.block(message, action="Run: fettle completion validate")
    return CheckResult.advisory(message, action="Run: fettle completion validate")
