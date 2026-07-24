"""Fettle Dispatcher — Core types.

Shared data structures for the single-dispatcher architecture.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Decision(StrEnum):
    ALLOW = "allow"
    ADVISORY = "advisory"
    BLOCK = "block"


@dataclass(frozen=True)
class HookInput:
    hook_event_name: str
    tool_name: str | None
    tool_input: dict[str, Any]
    cwd: Path
    session_id: str | None
    raw: dict[str, Any]


@dataclass
class HookContext:
    input: HookInput
    config: dict[str, Any]
    plugin_root: Path
    hook_start_monotonic: float
    global_deadline_monotonic: float
    check_deadline_monotonic: float = 0.0

    @property
    def event(self) -> str:
        return self.input.hook_event_name

    @property
    def tool_name(self) -> str | None:
        return self.input.tool_name

    @property
    def tool_input(self) -> dict[str, Any]:
        return self.input.tool_input

    @property
    def cwd(self) -> Path:
        return self.input.cwd

    @property
    def session_id(self) -> str | None:
        return self.input.session_id

    @property
    def target_path(self) -> Path | None:
        for key in ("file_path", "path", "notebook_path"):
            value = self.tool_input.get(key)
            if isinstance(value, str) and value:
                p = Path(value)
                return p if p.is_absolute() else self.cwd / p
        return None

    @property
    def target_ext(self) -> str | None:
        p = self.target_path
        return p.suffix.lower() if p else None


@dataclass
class CheckResult:
    decision: Decision = Decision.ALLOW
    message: str | None = None
    hook_specific_output: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(cls) -> CheckResult:
        return cls(decision=Decision.ALLOW)

    @classmethod
    def advisory(cls, message: str, *, hook_specific_output: dict[str, Any] | None = None) -> CheckResult:
        return cls(decision=Decision.ADVISORY, message=message, hook_specific_output=hook_specific_output or {})

    @classmethod
    def block(cls, message: str, *, hook_specific_output: dict[str, Any] | None = None) -> CheckResult:
        return cls(decision=Decision.BLOCK, message=message, hook_specific_output=hook_specific_output or {})


CheckRunner = Callable[[HookContext], CheckResult]


@dataclass(frozen=True)
class CheckSpec:
    name: str
    run: CheckRunner
    events: frozenset[str]
    tools: frozenset[str] | None = None
    extensions: frozenset[str] | None = None
    order: int = 100
    enabled_by_default: bool = True
    budget_ms: int | None = None

    def matches(self, ctx: HookContext) -> bool:
        if ctx.event not in self.events:
            return False
        if self.tools is not None and ctx.tool_name not in self.tools:
            return False
        if self.extensions is not None:
            ext = ctx.target_ext
            if ext not in self.extensions:
                return False
        return True

    def is_enabled(self, config: dict[str, Any]) -> bool:
        checks_cfg = config.get("dispatcher", {}).get("checks", {})
        check_cfg = checks_cfg.get(self.name, {})
        enabled = check_cfg.get("enabled")
        if enabled is not None:
            return bool(enabled)
        disabled_list = config.get("dispatcher", {}).get("disabled_checks", [])
        if self.name in disabled_list:
            return False
        return self.enabled_by_default
