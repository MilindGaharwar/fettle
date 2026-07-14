"""Fettle Dispatcher — Static check registry.

All checks are registered here. The dispatcher selects applicable checks
based on event, tool, extension, and config.
"""

from __future__ import annotations

from dispatcher_types import CheckSpec, HookContext

# Phase 1 checks (pure logic, no subprocesses)
from destructive_guard import run_check as destructive_guard_run
from config_protect import run_check as config_protect_run
from commit_message import run_check as commit_message_run
from loop_detect import run_check as loop_detect_run
from scope_creep import run_check as scope_creep_run

CHECKS: tuple[CheckSpec, ...] = (
    # PreToolUse — Write|Edit
    CheckSpec(
        name="config_protect",
        run=config_protect_run,
        events=frozenset({"PreToolUse"}),
        tools=frozenset({"Write", "Edit"}),
        order=10,
        budget_ms=50,
    ),
    # PreToolUse — Bash
    CheckSpec(
        name="destructive_guard",
        run=destructive_guard_run,
        events=frozenset({"PreToolUse"}),
        tools=frozenset({"Bash"}),
        order=10,
        budget_ms=50,
    ),
    CheckSpec(
        name="commit_message",
        run=commit_message_run,
        events=frozenset({"PreToolUse"}),
        tools=frozenset({"Bash"}),
        order=20,
        budget_ms=50,
    ),
    # PostToolUse — all tools
    CheckSpec(
        name="loop_detect",
        run=loop_detect_run,
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write", "Edit", "Bash", "Read"}),
        order=90,
        budget_ms=50,
    ),
    CheckSpec(
        name="scope_creep",
        run=scope_creep_run,
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write", "Edit", "Bash"}),
        order=95,
        budget_ms=50,
    ),
)


def select_checks(ctx: HookContext) -> list[CheckSpec]:
    """Select and order applicable checks for this context."""
    selected = [
        spec for spec in CHECKS
        if spec.matches(ctx) and spec.is_enabled(ctx.config)
    ]
    return sorted(selected, key=lambda s: (s.order, s.name))
