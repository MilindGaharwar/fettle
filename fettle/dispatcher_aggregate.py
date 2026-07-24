"""Fettle Dispatcher — Output aggregation.

Combines multiple CheckResults into a single hook output JSON + exit code.
Rules: first block wins, advisories concatenate, checks stop after block.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fettle.dispatcher_types import CheckResult, Decision


@dataclass
class CheckTiming:
    name: str
    elapsed_ms: int
    decision: str


@dataclass
class Aggregator:
    total_budget_ms: int
    hook_event_name: str = ""
    max_advisories_per_turn: int = 3
    max_advisory_bytes: int = 2048
    advisories: list[str] = field(default_factory=list)
    first_block: CheckResult | None = None
    first_block_name: str | None = None
    timings: list[CheckTiming] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    budget_exhausted_before: str | None = None
    _advisories_suppressed: int = 0

    @property
    def has_block(self) -> bool:
        return self.first_block is not None

    def add_result(self, check_name: str, result: CheckResult, elapsed_ms: int) -> None:
        self.timings.append(CheckTiming(name=check_name, elapsed_ms=elapsed_ms, decision=result.decision.value))

        if result.decision == Decision.BLOCK:
            if self.first_block is None:
                self.first_block = result
                self.first_block_name = check_name
            return

        context = result.hook_specific_output.get("additionalContext")
        if isinstance(context, str) and context.strip():
            if len(self.advisories) < self.max_advisories_per_turn:
                self.advisories.append(context.strip())
            else:
                self._advisories_suppressed += 1
        elif result.message and result.decision == Decision.ADVISORY:
            if len(self.advisories) < self.max_advisories_per_turn:
                self.advisories.append(result.message.strip())
            else:
                self._advisories_suppressed += 1

    def record_check_error(self, check_name: str, error: str) -> None:
        self.errors.append({"check": check_name, "error": error})
        self.timings.append(CheckTiming(name=check_name, elapsed_ms=0, decision="error_fail_open"))

    def record_budget_exhausted(self, next_check_name: str) -> None:
        self.budget_exhausted_before = next_check_name

    def finish(self) -> tuple[dict[str, Any], int]:
        hso: dict[str, Any] = {}
        if self.hook_event_name:
            hso["hookEventName"] = self.hook_event_name

        # Build advisory context with byte cap
        parts: list[str] = []
        total_bytes = 0
        for adv in self.advisories:
            adv_bytes = len(adv.encode("utf-8"))
            if total_bytes + adv_bytes > self.max_advisory_bytes:
                self._advisories_suppressed += 1
                continue
            parts.append(adv)
            total_bytes += adv_bytes

        if self._advisories_suppressed > 0:
            parts.append(f"... and {self._advisories_suppressed} more advisory(s) suppressed this turn")

        advisory_context = "\n\n".join(parts).strip()

        if self.first_block is not None:
            hso.update(self.first_block.hook_specific_output)
            if "hookEventName" not in hso and self.hook_event_name:
                hso["hookEventName"] = self.hook_event_name
            if advisory_context:
                existing = hso.get("additionalContext", "")
                if existing:
                    hso["additionalContext"] = advisory_context + "\n\n" + existing
                else:
                    hso["additionalContext"] = advisory_context
            if "permissionDecision" not in hso:
                hso["permissionDecision"] = "deny"
            if "permissionDecisionReason" not in hso and self.first_block.message:
                hso["permissionDecisionReason"] = self.first_block.message
            return {"hookSpecificOutput": hso}, 2

        if advisory_context:
            hso["additionalContext"] = advisory_context
        return {"hookSpecificOutput": hso}, 0
