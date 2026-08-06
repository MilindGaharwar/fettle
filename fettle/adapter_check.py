"""Adapter-backed PostToolUse lint dispatch."""

from __future__ import annotations

from fettle.adapters import get_adapter, run_adapter_check
from fettle.dispatcher_types import CheckResult, HookContext
from fettle.finding import ResultState, to_human
from fettle.profile import detect_profile
from fettle.workspace import route_file_to_workspace


_LANGUAGE_ADAPTERS = {
    "javascript": "typescript",
    "typescript": "typescript",
    "python": "python",
    "go": "go",
    "rust": "rust",
}


def run_check(ctx: HookContext) -> CheckResult:
    """Run the owning workspace's language adapter for one edited file."""
    target = ctx.target_path
    lint_cfg = ctx.config.get("gates", {}).get("lint", {})
    if target is None or not target.is_file() or not lint_cfg.get("enabled", True):
        return CheckResult.allow()

    try:
        canonical_target = target.resolve()
        relative_target = canonical_target.relative_to(ctx.cwd.resolve()).as_posix()
    except ValueError:
        return CheckResult.allow()

    profile = detect_profile(str(ctx.cwd), use_cache=False)
    workspace = route_file_to_workspace(relative_target, profile.workspaces)
    if workspace is None:
        return CheckResult.allow()

    adapter_name = _LANGUAGE_ADAPTERS.get(workspace.language)
    registered = get_adapter(adapter_name) if adapter_name else None
    if registered is None:
        return CheckResult.allow()

    workspace_root = ctx.cwd if workspace.path == "." else ctx.cwd / workspace.path
    adapter = type(registered)(cwd=str(workspace_root))
    adapter._config = ctx.config
    run = run_adapter_check(
        adapter, "lint", workspace, [str(canonical_target)], scope="changed",
    )

    if run.result_state == ResultState.PASS:
        return CheckResult.allow()

    if run.result_state == ResultState.TOOL_ERROR:
        message = run.tool_error or "Language lint tool failed"
        return CheckResult.tool_error(
            message,
            action="Install or repair the workspace lint tool, then retry.",
            hook_specific_output=_hook_output(message),
            evidence=run.evidence,
        )

    if run.result_state == ResultState.UNKNOWN:
        message = "Language lint result is unknown"
        return CheckResult.unknown(
            message,
            action="Run the workspace lint command directly and inspect its output.",
            hook_specific_output=_hook_output(message),
            evidence=run.evidence,
        )

    message = to_human(run.findings) or "Language lint violations found"
    kwargs = {
        "hook_specific_output": _hook_output(message),
        "findings": run.findings,
        "evidence": run.evidence,
    }
    mode = str(lint_cfg.get("mode", "advisory"))
    if mode == "enforce" and any(f.blocking for f in run.findings):
        return CheckResult.block(message, **kwargs)
    return CheckResult.advisory(message, **kwargs)


def _hook_output(message: str) -> dict[str, str]:
    return {"hookEventName": "PostToolUse", "additionalContext": message}
