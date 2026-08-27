"""Fettle Dispatcher — Static check registry.

All checks are registered here. The dispatcher selects applicable checks
based on event, tool, extension, and config.

WP-13 (audit M-03): check modules are imported lazily at first run, not at
registry import — a PreToolUse(Bash) hook no longer pays the import cost of
every gate module it will never select.
"""

from __future__ import annotations

from importlib import import_module

from fettle.dispatcher_types import CheckResult, CheckRunner, CheckSpec, HookContext


def _lazy(module: str, attr: str = "run_check") -> CheckRunner:
    """Import ``module`` on first invocation and delegate to ``attr``.

    import_module hits sys.modules after the first call, so the steady-state
    overhead is one dict lookup. Resolving at call time also means test
    monkeypatching of the underlying module is honored.
    """
    def run(ctx: HookContext) -> CheckResult:
        return getattr(import_module(module), attr)(ctx)
    run.__qualname__ = f"{module}.{attr}"
    return run

CHECKS: tuple[CheckSpec, ...] = (
    # PreToolUse — first, every tool: delegated-policy tamper guard (Stage A)
    CheckSpec(
        name="capsule_guard",
        run=_lazy("fettle.capsule_guard"),
        events=frozenset({"PreToolUse"}),
        tools=None,
        order=1,
        budget_ms=20,
    ),
    # PreToolUse — Write|Edit
    CheckSpec(
        name="config_protect",
        run=_lazy("fettle.config_protect"),
        events=frozenset({"PreToolUse"}),
        tools=frozenset({"Write", "Edit"}),
        order=10,
        budget_ms=50,
    ),
    CheckSpec(
        name="quality_gate",
        run=_lazy("fettle.quality_gate"),
        events=frozenset({"PreToolUse", "PostToolUse", "Stop"}),
        tools=None,
        order=5,
        budget_ms=120,
    ),
    # PreToolUse — Bash
    CheckSpec(
        name="mcp_trust_gate",
        run=_lazy("fettle.mcp_trust_gate"),
        events=frozenset({"PreToolUse"}),
        tools=frozenset({"Bash", "Write", "Edit"}),
        order=8,
        budget_ms=60,
    ),
    CheckSpec(
        name="destructive_guard",
        run=_lazy("fettle.destructive_guard"),
        events=frozenset({"PreToolUse"}),
        tools=frozenset({"Bash"}),
        order=10,
        budget_ms=50,
    ),
    CheckSpec(
        name="agent_spawn_gate",
        run=_lazy("fettle.agent_spawn_gate"),
        events=frozenset({"PreToolUse"}),
        tools=frozenset({"Bash"}),
        order=12,
        budget_ms=30,
    ),
    CheckSpec(
        name="commit_message",
        run=_lazy("fettle.commit_message"),
        events=frozenset({"PreToolUse"}),
        tools=frozenset({"Bash"}),
        order=20,
        budget_ms=50,
    ),
    # PostToolUse — Write|Edit (tool-backed)
    CheckSpec(
        name="adapter_check",
        run=_lazy("fettle.adapter_check"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write", "Edit"}),
        extensions=frozenset({".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"}),
        order=25,
        budget_ms=150,
    ),
    CheckSpec(
        name="lean_sniffers",
        run=_lazy("fettle.lean_sniffers"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write", "Edit"}),
        order=50,
        budget_ms=200,
    ),
    # PostToolUse — Bash (tool-backed)
    CheckSpec(
        name="post_bash_doc_check",
        run=_lazy("fettle.post_bash_doc_check"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Bash"}),
        order=40,
        budget_ms=80,
    ),
    # PostToolUse — TLA+ spec staleness advisory (per-edit)
    CheckSpec(
        name="tla_sync",
        run=_lazy("fettle.tla_sync"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write", "Edit"}),
        order=88,
        budget_ms=10,
    ),
    # Stop — TLA+ spec staleness mtime check
    CheckSpec(
        name="tla_sync_stop",
        run=_lazy("fettle.tla_sync"),
        events=frozenset({"Stop"}),
        tools=None,
        order=57,
        budget_ms=20,
    ),
    # PostToolUse — all tools
    CheckSpec(
        name="loop_detect",
        run=_lazy("fettle.loop_detect"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write", "Edit", "Bash", "Read"}),
        order=90,
        budget_ms=50,
    ),
    CheckSpec(
        name="scope_creep",
        run=_lazy("fettle.scope_creep"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write", "Edit", "Bash"}),
        order=95,
        budget_ms=50,
    ),
    # Stop
    CheckSpec(
        name="stop_quality_gate",
        run=_lazy("fettle.stop_quality_gate"),
        events=frozenset({"Stop"}),
        tools=None,
        order=50,
        budget_ms=300,
    ),
    # PreToolUse — authorship separation (P52, WP-520)
    CheckSpec(
        name="authorship_gate",
        run=_lazy("fettle.authorship_gate"),
        events=frozenset({"PreToolUse"}),
        tools=frozenset({"Write", "Edit"}),
        order=14,
        budget_ms=20,
    ),
    # PreToolUse + PostToolUse — TDD ordering
    CheckSpec(
        name="tdd_gate",
        run=_lazy("fettle.tdd_gate"),
        events=frozenset({"PreToolUse", "PostToolUse"}),
        tools=frozenset({"Write", "Edit"}),
        order=15,
        budget_ms=50,
    ),
    # PostToolUse — spec scenario coverage (Stage 3, S3.3)
    CheckSpec(
        name="bdd_gate",
        run=_lazy("fettle.bdd_gate"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write", "Edit"}),
        order=16,
        budget_ms=200,
    ),
    # PostToolUse — claim-before-work in fettle worktrees (Stage 4, S4.3)
    CheckSpec(
        name="claims_gate",
        run=_lazy("fettle.claims_gate"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write", "Edit"}),
        order=17,
        budget_ms=100,
    ),
    # PostToolUse — complexity (Python only)
    CheckSpec(
        name="complexity_check",
        run=_lazy("fettle.complexity_check"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write", "Edit"}),
        extensions=frozenset({".py"}),
        order=35,
        budget_ms=100,
    ),
    # PreToolUse(Bash) — deploy safety
    CheckSpec(
        name="deploy_gate",
        run=_lazy("fettle.deploy_gate"),
        events=frozenset({"PreToolUse"}),
        tools=frozenset({"Bash"}),
        order=10,
        budget_ms=80,
    ),
    # PreToolUse(Bash) — release/tag validation
    CheckSpec(
        name="release_gate",
        run=_lazy("fettle.release_gate"),
        events=frozenset({"PreToolUse"}),
        tools=frozenset({"Bash"}),
        order=12,
        budget_ms=50,
    ),
    # PreToolUse + PostToolUse(Bash) — artifact verification
    CheckSpec(
        name="artifact_gate",
        run=_lazy("fettle.artifact_gate"),
        events=frozenset({"PreToolUse", "PostToolUse"}),
        tools=frozenset({"Bash"}),
        order=11,
        budget_ms=40,
    ),
    # PostToolUse — architecture boundary rules
    CheckSpec(
        name="boundary_rules",
        run=_lazy("fettle.boundary_rules"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write", "Edit"}),
        extensions=frozenset({".py"}),
        order=65,
        budget_ms=50,
    ),
    # PostToolUse — provenance (new files only)
    CheckSpec(
        name="provenance_gate",
        run=_lazy("fettle.provenance_gate"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write"}),
        order=62,
        budget_ms=30,
    ),
    # Stop — fresh green `fettle verify` stamp required (Stage 7, S7.1)
    CheckSpec(
        name="verify_gate",
        run=_lazy("fettle.verify_gate"),
        events=frozenset({"Stop"}),
        tools=None,
        order=52,
        budget_ms=100,
    ),
    # PostToolUse(Bash) — record `git push` for the CI gate (Stage 8)
    CheckSpec(
        name="ci_push_record",
        run=_lazy("fettle.ci_gate", attr="record_push"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Bash"}),
        order=45,
        budget_ms=100,
    ),
    # Stop — pushed commits demand a fresh green remote CI verdict (Stage 8)
    CheckSpec(
        name="ci_gate",
        run=_lazy("fettle.ci_gate"),
        events=frozenset({"Stop"}),
        tools=None,
        order=53,
        budget_ms=100,
    ),
    # Stop — reject malformed or contradictory milestone completion claims.
    CheckSpec(
        name="completion_gate",
        run=_lazy("fettle.completion_gate"),
        events=frozenset({"Stop"}),
        tools=None,
        order=54,
        budget_ms=100,
    ),
    CheckSpec(
        name="completion_manifest_gate",
        run=_lazy("fettle.completion_gate"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Write", "Edit"}),
        extensions=frozenset({".json", ".md"}),
        order=18,
        budget_ms=100,
    ),
    # Stop — coverage (advisory by default, after blocking checks)
    CheckSpec(
        name="coverage_gate",
        run=_lazy("fettle.coverage_gate"),
        events=frozenset({"Stop"}),
        tools=None,
        order=55,
        budget_ms=100,
    ),
    # Stop — completion report for orchestrators (v1.6 slice C, never blocks)
    CheckSpec(
        name="session_report",
        run=_lazy("fettle.session_report"),
        events=frozenset({"Stop"}),
        tools=None,
        order=58,
        budget_ms=50,
    ),
    # Stop — worklog (advisory by default)
    CheckSpec(
        name="worklog",
        run=_lazy("fettle.worklog"),
        events=frozenset({"Stop"}),
        tools=None,
        order=60,
        budget_ms=50,
    ),
    # Audit (never blocks, runs last)
    CheckSpec(
        name="bash_audit",
        run=_lazy("fettle.bash_audit"),
        events=frozenset({"PostToolUse"}),
        tools=frozenset({"Bash"}),
        order=99,
        budget_ms=30,
    ),
)


def select_checks(ctx: HookContext) -> list[CheckSpec]:
    """Select and order applicable checks for this context."""
    selected = [
        spec for spec in CHECKS
        if spec.matches(ctx) and spec.is_enabled(ctx.config)
    ]
    return sorted(selected, key=lambda s: (s.order, s.name))
