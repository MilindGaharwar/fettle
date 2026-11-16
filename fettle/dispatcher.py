#!/usr/bin/env python3
"""Fettle Single Dispatcher — v2 Foundation.

One Python process per hook event. Reads stdin once, loads config once,
selects and runs applicable checks, aggregates output.

Optional checks fail open; required checks fail closed when execution is incomplete.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import time
import traceback
import hashlib
from dataclasses import replace
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent  # repo root (clone mode)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fettle.config import load_config  # noqa: E402
from fettle.dispatcher_aggregate import Aggregator  # noqa: E402
from fettle.dispatcher_registry import CHECKS, select_checks  # noqa: E402
from fettle.dispatcher_types import CheckResult, Decision, HookContext  # noqa: E402
from fettle.paths import find_project_root  # noqa: E402
from fettle.trace import build_evidence, log_decision, log_evidenced_decision, read_tail  # noqa: E402


logger = logging.getLogger(__name__)

# Repeated-failure escalation: same check failing this many times within the
# window turns silent fail-open into a visible in-session advisory.
_ESCALATION_THRESHOLD = 3
_ESCALATION_WINDOW_S = 24 * 3600


def _trace_dispatch_failure(status: str, detail: str, session_id: str = "") -> None:
    """Record a dispatcher-level fail-open on the audit trail. Never raises."""
    # Tracing must never break the hook path; log_decision itself warns on
    # stderr if the audit log is unwritable, so suppression here is not silent.
    with contextlib.suppress(Exception):
        log_decision(
            hook="dispatcher",
            status=status,
            findings=[{"detail": detail[:500]}] if detail else [],
            session_id=session_id,
        )


def _repeated_failure_checks(errors: list[dict]) -> list[str]:
    """Names of checks that also failed >= threshold times in the window."""
    if not errors:
        return []
    try:
        now = time.time()
        counts: dict[str, int] = {}
        for entry in read_tail():
            if entry.get("hook") != "dispatcher" or entry.get("status") != "check_error":
                continue
            if now - float(entry.get("ts", 0)) > _ESCALATION_WINDOW_S:
                continue
            for finding in entry.get("findings", []):
                name = finding.get("check", "")
                if name:
                    counts[name] = counts.get(name, 0) + 1
        return [
            err["check"]
            for err in errors
            # The current run's failure is already traced before this check
            # runs, so the tail count includes it.
            if counts.get(err["check"], 0) >= _ESCALATION_THRESHOLD
        ]
    except Exception as exc:  # noqa: BLE001 — escalation is best-effort
        logger.error("fettle: failure-escalation probe failed: %s", exc, exc_info=True)
        return []


DEFAULT_EVENT_BUDGETS_MS = {
    "PreToolUse": 250,
    "PostToolUse": 400,
    "Stop": 600,
}


def _event_budget_ms(config: dict, event: str) -> int:
    dispatcher_cfg = config.get("dispatcher", {})
    by_event = dispatcher_cfg.get("event_budgets_ms", {}).get(event)
    if isinstance(by_event, int) and by_event > 0:
        return by_event
    global_budget = dispatcher_cfg.get("global_budget_ms")
    if isinstance(global_budget, int) and global_budget > 0:
        return global_budget
    return DEFAULT_EVENT_BUDGETS_MS.get(event, 400)


def _empty_output(event_name: str = "") -> str:
    # Codex's Stop output wire has no hookSpecificOutput field and rejects
    # unknown fields — an empty object is the universal no-op (Stage 13).
    if event_name in ("Stop", "SubagentStop") or not event_name:
        return json.dumps({}, separators=(",", ":"))
    return json.dumps(
        {"hookSpecificOutput": {"hookEventName": event_name}}, separators=(",", ":")
    )


def _is_policy_repair(hook_input, root: Path) -> bool:
    if hook_input.hook_event_name != "PreToolUse" or hook_input.tool_name not in {"Write", "Edit"}:
        return False
    if len(hook_input.targets) != 1:
        return False
    target = hook_input.targets[0]
    if not target.is_absolute():
        target = (hook_input.invocation_cwd or root) / target
    return target.resolve(strict=False) == (root / ".fettle.toml").resolve(strict=False)


def _most_severe_target_result(check_name: str, results: list[CheckResult]) -> CheckResult:
    """Collapse one check's target fan-out without hiding later results."""
    precedence = {Decision.ALLOW: 0, Decision.ADVISORY: 1, Decision.BLOCK: 2}
    winner = max(results, key=lambda item: precedence[item.decision], default=CheckResult.allow())
    advisories = [item for item in results if item.decision == Decision.ADVISORY]
    if not advisories:
        return winner

    count = len(advisories)
    noun = "target" if count == 1 else "targets"
    details = "\n".join(
        dict.fromkeys(item.message.strip() for item in advisories if item.message)
    )
    summary = f"{check_name}: {count} {noun} had advisories"
    if details:
        summary += f"\n{details}"
    if winner.decision == Decision.ADVISORY:
        winner.message = summary
    else:
        output = dict(winner.hook_specific_output)
        existing = output.get("additionalContext")
        output["additionalContext"] = f"{summary}\n\n{existing}" if existing else summary
        winner.replace(hook_specific_output=output)
    return winner


def main() -> int:
    if os.environ.get("FETTLE_DISABLE_DISPATCHER") == "1":
        print(_empty_output())
        return 0

    try:
        raw_stdin = sys.stdin.read()
        payload = json.loads(raw_stdin or "{}")
        if not isinstance(payload, dict):
            raise TypeError("hook input must be a JSON object")
    except Exception as exc:  # noqa: BLE001 — fail-open by design, but never silently
        logger.error("fettle: stdin parse failed: %s", exc, exc_info=True)
        _trace_dispatch_failure("input_error", f"{type(exc).__name__}: {exc}")
        from fettle.agents import raw_names_pretool_event
        if raw_names_pretool_event(raw_stdin):
            failure = Aggregator(total_budget_ms=0, hook_event_name="PreToolUse")
            failure.add_result(
                "dispatcher",
                CheckResult.block(
                    "Malformed PreToolUse input; policy checks could not run. "
                    "Run `fettle doctor` and retry."
                ),
                0,
            )
            output, exit_code = failure.finish()
            print(json.dumps(output, separators=(",", ":")))
            return exit_code
        print(_empty_output())
        return 0

    # WP-140: agent-specific payload parsing lives ONLY in fettle.agents.
    # The dispatcher consumes the normalized event model exclusively.
    try:
        from fettle.agents import normalize
        hook_input = normalize(payload, fallback_cwd=os.getcwd())
    except Exception as exc:  # noqa: BLE001 — fail-open by design, but never silently
        logger.error("fettle: event normalize failed: %s", exc, exc_info=True)
        _trace_dispatch_failure("input_error", f"normalize: {type(exc).__name__}: {exc}")
        print(_empty_output(str(payload.get("hook_event_name") or "")))
        return 0
    invocation_cwd = hook_input.invocation_cwd or hook_input.cwd
    cwd = find_project_root(invocation_cwd)
    hook_input = replace(hook_input, cwd=cwd, invocation_cwd=invocation_cwd)
    if (
        hook_input.hook_event_name == "PreToolUse"
        and hook_input.targets
        and hook_input.tool_name not in {"Bash", "Write", "Edit", "Read", "Search"}
    ):
        hook_input = replace(hook_input, tool_name="Edit")
    session_id = hook_input.session_id or ""

    try:
        config = load_config(str(cwd), strict=True)
        from fettle.edit_journal import record, record_session_start
        policy_digest = hashlib.sha256(
            json.dumps(config, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        record_session_start(session_id, cwd, policy_digest)
        if hook_input.hook_event_name == "PostToolUse" and hook_input.tool_name in {"Write", "Edit"}:
            for target in hook_input.targets:
                record(session_id, target if target.is_absolute() else invocation_cwd / target, hook_input.tool_name)
        start = time.monotonic()
        budget_ms = _event_budget_ms(config, hook_input.hook_event_name)
        deadline = start + (budget_ms / 1000.0)
        ctx = HookContext(
            input=hook_input,
            config=config,
            plugin_root=_REPO_ROOT,
            hook_start_monotonic=start,
            global_deadline_monotonic=deadline,
        )
        advisory_cfg = config.get("gates", {}).get("advisory", {})
        aggregator = Aggregator(
            total_budget_ms=budget_ms,
            hook_event_name=hook_input.hook_event_name,
            max_advisories_per_turn=int(advisory_cfg.get("max_per_turn", 3)),
            max_advisory_bytes=int(advisory_cfg.get("max_total_bytes", 2048)),
        )
        required_names = {
            spec.name for spec in CHECKS
            if spec.matches(ctx) and spec.is_enabled(config) and spec.requires_execution_for(ctx)
        }
    except Exception as exc:  # noqa: BLE001 — unknown policy cannot authorize checks
        logger.error("fettle: config load failed: %s", exc, exc_info=True)
        _trace_dispatch_failure(
            "config_error", f"{type(exc).__name__}: {exc}", session_id
        )
        failure = Aggregator(total_budget_ms=0, hook_event_name=hook_input.hook_event_name)
        if _is_policy_repair(hook_input, cwd):
            failure.add_result(
                "dispatcher",
                CheckResult.advisory(
                    "Fettle policy is invalid; allowing this policy-file repair only. "
                    "Run `fettle doctor` after the repair."
                ),
                0,
            )
            output, exit_code = failure.finish()
            print(json.dumps(output, separators=(",", ":")))
            return exit_code
        failure.add_result("dispatcher", CheckResult.block(
            "Org policy is declared but not available locally. Run: fettle policy sync"
             if "policy sync" in str(exc)
             else "Policy configuration could not be loaded; required checks are unknown. "
                  "Run `fettle doctor` and retry."
        ), 0)
        output, exit_code = failure.finish()
        print(json.dumps(output, separators=(",", ":")))
        return exit_code

    try:
        checks = select_checks(ctx)
    except Exception as exc:  # noqa: BLE001 — retain required policy when selection fails
        logger.error("fettle: check registry failed: %s", exc, exc_info=True)
        _trace_dispatch_failure(
            "registry_error", f"{type(exc).__name__}: {exc}", session_id
        )
        message = "Check selection failed; checks did not run. Run `fettle doctor` and retry."
        aggregator.add_result(
            "dispatcher",
            CheckResult.block(message) if required_names else CheckResult.tool_error(message, action="fettle doctor"),
            0,
        )
        checks = []

    for index, spec in enumerate(checks):
        if time.monotonic() > deadline:
            required = next((remaining for remaining in checks[index:]
                             if remaining.requires_execution_for(ctx)), None)
            if required:
                aggregator.add_result(
                    required.name,
                    CheckResult.block(
                        f"Required check '{required.name}' could not run before the deadline. "
                        "Run `fettle doctor` and retry."
                    ),
                    0,
                )
            aggregator.record_budget_exhausted(spec.name)
            break

        check_start = time.monotonic()

        # WP-D: Per-check deadline = min(global, start + budget_ms)
        check_deadline = deadline
        if spec.budget_ms:
            check_deadline = min(deadline, check_start + spec.budget_ms / 1000.0)

        ctx.check_deadline_monotonic = check_deadline

        try:
            target_contexts = [ctx]
            if len(hook_input.targets) > 1 and spec.tools is not None:
                target_contexts = [
                    replace(ctx, input=replace(hook_input, targets=(target,)))
                    for target in hook_input.targets
                ]
            target_results = []
            for target_ctx in target_contexts:
                result = spec.run(target_ctx)
                if result is None:
                    result = (
                        CheckResult.unknown("Required check returned no result", action="retry")
                        if spec.requires_execution_for(target_ctx) else CheckResult.allow()
                    )
                target_results.append(result)
            result = _most_severe_target_result(spec.name, target_results)
        except Exception as exc:  # noqa: BLE001 — isolate check failures
            if spec.requires_execution_for(ctx):
                logger.error("fettle: security check %s failed closed", spec.name)
                aggregator.add_result(
                    spec.name,
                    CheckResult.block(
                        f"Required check '{spec.name}' failed closed. "
                        "Run `fettle doctor` and retry."
                    ),
                    int((time.monotonic() - check_start) * 1000),
                )
                break
            logger.error("fettle: check %s failed: %s", spec.name, exc)
            aggregator.record_check_error(spec.name, f"{type(exc).__name__}: {exc}")
            continue

        if spec.requires_execution_for(ctx) and result.result_state.value in {"tool_error", "unknown"}:
            result = CheckResult.block(
                f"Required check '{spec.name}' did not complete. Run `fettle doctor` and retry."
            )
        elapsed_ms = int((time.monotonic() - check_start) * 1000)
        aggregator.add_result(spec.name, result, elapsed_ms)
        if result.findings or result.evidence or spec.name == "authorship_gate":
            with contextlib.suppress(Exception):
                evidence = [item.to_dict() for item in result.evidence]
                if spec.name == "authorship_gate" and result.result_state.value != "pass":
                    if not evidence:
                        evidence = [build_evidence(
                            "authorship_verdict",
                            scope=str(ctx.target_path or ""),
                            exit_code=0 if result.result_state.value == "pass" else 1,
                        )]
                    log_evidenced_decision(
                        str(ctx.cwd), hook=spec.name,
                        status=result.result_state.value,
                        tool=hook_input.tool_name or "",
                        file=str(ctx.target_path or ""), evidence=evidence,
                        session_id=session_id,
                        role=str(ctx.config.get("role", "")),
                    )
                else:
                    log_decision(
                        hook=spec.name,
                        status=result.result_state.value,
                        tool=hook_input.tool_name or "",
                        file=str(ctx.target_path or ""),
                        findings=[finding.to_dict() for finding in result.findings],
                        evidence=evidence,
                        duration_ms=elapsed_ms,
                        session_id=session_id,
                        role=str(ctx.config.get("role", "")),
                        root=str(ctx.cwd),
                    )

        # WP-D: Log overruns for observability — and trace them, so chronic
        # slow checks are visible in `fettle report`, not only in stderr.
        if time.monotonic() > check_deadline:
            logger.warning(
                "fettle: check %s overran budget (%dms budget, %dms actual)",
                spec.name, spec.budget_ms or 0, elapsed_ms,
            )
            with contextlib.suppress(Exception):
                log_decision(
                    "dispatcher", "budget_overrun", tool=hook_input.tool_name or "",
                    findings=[{"code": "CHECK_BUDGET_OVERRUN", "check": spec.name,
                               "budget_ms": spec.budget_ms or 0,
                               "actual_ms": elapsed_ms}],
                    session_id=session_id,
                    root=str(ctx.cwd),
                )

        if aggregator.has_block:
            break

    # Stage-0 failure visibility: a check crash or budget kill is a fail-open
    # that MUST leave a persistent record and, when chronic, become visible
    # in-session. One bounded trace write; escalation reads a bounded tail.
    if aggregator.errors:
        _trace_dispatch_failure_findings(aggregator.errors, session_id)
        for name in _repeated_failure_checks(aggregator.errors):
            aggregator.add_system_advisory(
                f"fettle: check '{name}' has failed repeatedly and is being "
                "skipped (fail-open) — findings may be missed. "
                "Run `fettle doctor` to diagnose."
            )
    if aggregator.budget_exhausted_before:
        # Suppression is not silent: log_decision warns on stderr if unwritable.
        with contextlib.suppress(Exception):
            log_decision(
                hook="dispatcher",
                status="budget_exhausted",
                findings=[{
                    "skipped_from": aggregator.budget_exhausted_before,
                    "budget_ms": budget_ms,
                    "event": hook_input.hook_event_name,
                }],
                session_id=session_id,
            )

    output, exit_code = aggregator.finish()
    print(json.dumps(output, separators=(",", ":")))
    return exit_code


def _trace_dispatch_failure_findings(errors: list[dict], session_id: str) -> None:
    """Persist per-check crash details as one trace entry. Never raises."""
    # Suppression is not silent: log_decision warns on stderr if unwritable.
    with contextlib.suppress(Exception):
        log_decision(
            hook="dispatcher",
            status="check_error",
            findings=[
                {"check": e.get("check", ""), "error": str(e.get("error", ""))[:500]}
                for e in errors
            ],
            session_id=session_id,
        )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 — last-resort fail-open
        traceback.print_exc(file=sys.stderr)
        print(_empty_output())  # nosemgrep: debug-print-statement -- hook stdout protocol
        raise SystemExit(0) from None
