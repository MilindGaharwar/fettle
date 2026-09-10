"""Redact tool output only on hosts with verified pre-model replacement."""

from __future__ import annotations

import json
from typing import Any

from fettle.dispatcher_types import CheckResult, HookContext
from fettle.runtime_secret_guard import redact_secrets


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    return value


def _contains_secret(value: Any, redacted: Any) -> bool:
    return json.dumps(value, sort_keys=True, default=str) != json.dumps(
        redacted, sort_keys=True, default=str
    )


def run_check(ctx: HookContext) -> CheckResult:
    """Replace or withhold secret-bearing output before model consumption."""
    raw = ctx.input.raw
    if raw.get("fettle_host") == "opencode" or isinstance(raw.get("turn_id"), str):
        return CheckResult.allow()

    response = raw.get("tool_response")
    if response is None:
        return CheckResult.allow()

    is_gemini = raw.get("hook_event_name") == "AfterTool"
    try:
        redacted = _redact(response)
        if not _contains_secret(response, redacted):
            return CheckResult.allow()
        if is_gemini:
            return CheckResult.block(
                "Credential-bearing tool output was withheld by Fettle. "
                "Inspect the source outside the agent session."
            )
        return CheckResult.allow().replace(
            hook_specific_output={"updatedToolOutput": redacted}
        )
    except Exception:  # noqa: BLE001 - supported output boundaries fail closed
        if is_gemini:
            return CheckResult.block(
                "Secret output protection failed closed. Run `fettle doctor` and retry."
            )
        return CheckResult.allow().replace(
            hook_specific_output={"updatedToolOutput": "Tool output withheld: secret protection failed. Run `fettle doctor`."}
        )
