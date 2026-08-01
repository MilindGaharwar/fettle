"""[gates.bdd] — spec scenario coverage gate (Stage 3, S3.3; WP-154 seed).

Deterministic, advisory-first: when an edited implementation file falls
inside an *active* living spec's ``scope`` (see fettle/spec_model.py),
every scenario of that spec must have at least one trace-marked test
(``# traces: <spec-id>/S<n>``). No test execution, no red/green claims —
same philosophy as tdd_gate: this checks the *contract* exists, not that
it passes (the test suite itself proves that).

Off by default. Modes: advisory | enforce (registered in WP4 MODE_ENUMS).
"""

from __future__ import annotations

import os
from fnmatch import fnmatch

from fettle.dispatcher_types import CheckResult, HookContext


def _governing_specs(specs: list, rel_path: str) -> list:
    """Active specs whose scope globs match the edited file."""
    out = []
    for spec in specs:
        if spec.status != "active":
            continue
        if any(fnmatch(rel_path, pattern) for pattern in spec.scope):
            out.append(spec)
    return out


def run_check(ctx: HookContext) -> CheckResult:
    """Dispatcher entry point: PostToolUse on Write/Edit."""
    cfg = ctx.config.get("gates", {}).get("bdd", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    file_path = ctx.tool_input.get("file_path", "")
    if not file_path:
        return CheckResult.allow()
    cwd = str(ctx.cwd)
    rel_path = os.path.relpath(file_path, cwd) if os.path.isabs(file_path) else file_path
    if rel_path.startswith(".."):  # outside the project — not ours to govern
        return CheckResult.allow()

    from fettle.spec_model import discover_specs, scenario_coverage

    specs = [s for s, _ in discover_specs(cwd) if s is not None and s.spec_id]
    governing = _governing_specs(specs, rel_path)
    if not governing:
        return CheckResult.allow()

    coverage = scenario_coverage(cwd)
    by_id = {entry["id"]: entry for entry in coverage["specs"]}

    gaps: list[str] = []
    for spec in governing:
        entry = by_id.get(spec.spec_id)
        if entry is None:
            continue
        for row in entry["scenarios"]:
            if not row["covered"]:
                gaps.append(
                    f"{spec.spec_id}/{row['id']} ({row['title']}) — add a test "
                    f"with '# traces: {spec.spec_id}/{row['id']}'"
                )

    if not gaps:
        return CheckResult.allow()

    spec_names = ", ".join(s.spec_id for s in governing)
    msg = (
        f"BDD gate: {rel_path} is governed by spec(s) {spec_names}; "
        f"{len(gaps)} scenario(s) have no traced test:\n"
        + "\n".join("  - " + g for g in gaps)
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
