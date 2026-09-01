"""``[gates.agent_spawn]`` — governed nested-agent-launch gate (Stage A, A5).

PreToolUse(Bash). Detects raw agent-CLI launches (``claude -p``, ``codex
exec``, ``gemini -p/--yolo``, ``opencode run``) that bypass ``fettle spawn``.

Findings ladder (design doc §3.2):
- ungoverned launch (no FETTLE_POLICY_CAPSULE in the env context) →
  advisory: use ``fettle spawn``.
- launch with a hook-bypass flag (``--dangerously-skip-permissions``,
  ``--yolo``, ``--full-auto``) or a ``FETTLE_GATE_MODE=off`` composition →
  advisory in advisory mode, **block in enforce** (a capsule cannot govern
  a child whose hooks are disabled).

Precision over recall: the agent binary must be at command position
(destructive_guard's segment approach); bash string-literal parsing is not
attempted.
"""

from __future__ import annotations

import os
import re

from fettle.destructive_guard import _is_safe_context, _normalize_command
from fettle.dispatcher_types import CheckResult, HookContext

_LAUNCH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("claude", re.compile(r"claude\s+(?:-p|--print)\b")),
    ("codex", re.compile(r"codex\s+exec\b")),
    ("gemini", re.compile(r"gemini\b.*(?:\s-p\b|--prompt\b|--yolo\b)")),
    ("opencode", re.compile(r"opencode\s+run\b")),
]

_BYPASS_FLAGS = re.compile(r"--dangerously-skip-permissions\b|--yolo\b|--full-auto\b")
_GATE_OFF = re.compile(r"\bFETTLE_GATE_MODE=off\b")
_ENV_PREFIX = re.compile(r"^(?:env\s+)?(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*")


def _detect_launch(segment: str) -> str:
    """Return the runner name when the segment launches an agent CLI."""
    if _is_safe_context(segment):
        return ""
    rest = _ENV_PREFIX.sub("", segment.strip(), count=1)
    tokens = rest.split()
    if not tokens:
        return ""
    binary = tokens[0].rsplit("/", 1)[-1]
    for name, pattern in _LAUNCH_PATTERNS:
        if binary == name and pattern.search(rest):
            return name
    return ""


def run_check(ctx: HookContext) -> CheckResult:
    command = ctx.tool_input.get("command", "")
    if not command:
        return CheckResult.allow()

    gate_cfg = ctx.config.get("gates", {}).get("agent_spawn", {})
    if not gate_cfg.get("enabled", True):
        return CheckResult.allow()
    mode = gate_cfg.get("mode", "advisory")

    for segment in _normalize_command(command):
        runner = _detect_launch(segment)
        if not runner:
            continue

        bypass = bool(_BYPASS_FLAGS.search(segment)) or bool(_GATE_OFF.search(segment))
        governed = bool(os.environ.get("FETTLE_POLICY_CAPSULE")) or \
            "FETTLE_POLICY_CAPSULE=" in segment

        if bypass:
            reason = (
                f"Nested `{runner}` launch disables its own governance "
                f"(bypass flag or FETTLE_GATE_MODE=off) — a policy capsule "
                f"cannot follow it. Use `fettle spawn {runner} --task ...`."
            )
            if mode == "enforce":
                return CheckResult.block(
                    reason,
                    hook_specific_output={
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "additionalContext": reason,
                    },
                )
            return CheckResult.advisory(reason)

        if not governed:
            return CheckResult.advisory(
                f"Ungoverned agent spawn: `{segment.strip()[:80]}`. The child "
                f"inherits no policy — launch it via "
                f"`fettle spawn {runner} --task ...` instead."
            )

    # 2026-08 audit: the kill switch was only screened on agent launches,
    # but it disables every gate for ANY child process tree (git hooks,
    # test runners) — screen it on every command segment.
    for segment in _normalize_command(command):
        if _is_safe_context(segment) or _detect_launch(segment):
            continue
        if _GATE_OFF.search(segment):
            reason = (
                "FETTLE_GATE_MODE=off in a Bash command disables every fettle "
                "gate for that process tree. Remove the kill switch, or change "
                "policy in .fettle.toml where it is reviewable."
            )
            if mode == "enforce":
                return CheckResult.block(
                    reason,
                    hook_specific_output={
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "additionalContext": reason,
                    },
                )
            return CheckResult.advisory(reason)
    return CheckResult.allow()
