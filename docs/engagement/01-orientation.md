# Deliverable 1 — Repository Orientation Summary

Date: 2026-08-01 · Basis: full read of core spine + three sectional deep-reads
(gates inventory, docs corpus, test strategy). State: v1.2.0 shipped, v1.3.0 in
progress (WP-144/145 shipped; WP-146/147/148/154 open), main == origin/main @ 28b5443.

## 1. What Fettle is today

Fettle is a **reactive quality harness for AI-generated code**. It hooks the
tool calls of a host coding agent (Claude Code, OpenCode) and runs
latency-budgeted static analysis and process gates *inside the agent session*,
where findings can still be fixed with full context. It is **not** an agent
orchestrator: it can deny, advise, and inject context, but it cannot spawn,
supervise, or delegate to agents. The single agent-spawn primitive in the whole
codebase is `_claude_runner` in [fettle/evals_runner.py](../../fettle/evals_runner.py)
(live behavioral evals via `claude -p`).

## 2. Architecture

```
host agent (Claude Code / OpenCode)
   │  hook events (PreToolUse / PostToolUse / Stop / SubagentStart)
   ▼
fettle.agents (normalize)  ──►  dispatcher.py (one process/event, budgeted:
   │                             250/400/600 ms, fail-open)
   ▼
dispatcher_registry.select_checks ──► ~30 gate modules ──► dispatcher_aggregate
   │                                                        (first-block-wins,
   ▼                                                         advisory byte caps)
trace.py (audit JSONL v2)  ◄──  evidence loop: ratchet / bench / suppressions
                                 / baseline / report
```

- **Config**: `config.DEFAULTS` → `.fettle.toml` → env; org policy via
  digest-pinned `[extends]` ([fettle/policy_remote.py](../../fettle/policy_remote.py),
  merge in [fettle/policy_layers.py](../../fettle/policy_layers.py)). JSON schema
  generated from DEFAULTS with an anti-drift test
  ([fettle/config_schema.py](../../fettle/config_schema.py)).
- **Enforcement surfaces** (one policy, five chokepoints): agent hooks, CLI
  (`fettle check`, exit contract 0/1/2), pre-commit, CI (GitHub Action + GitLab
  template + SARIF/JUnit), LSP ([fettle/lsp_server.py](../../fettle/lsp_server.py), prototype).
- **Intelligence loop**: `fettle learn` (incident → LLM-drafted semgrep rule +
  fixtures + human approval), `fettle ratchet` (evidence-based advisory↔enforce
  promotion), `fettle bench` (findings-per-KLOC noise budgets),
  `fettle report` (effectiveness metrics, org rollup).

## 3. Module boundaries

| Layer | Modules | Assessment |
|---|---|---|
| Event ingestion | `agents/` (normalize only), `hooks/hooks.json`, `subagent_inject.js` | Clean boundary (WP-140); parsing lives only in `agents/` |
| Dispatch | `dispatcher*.py` | Solid; but error/timing telemetry collected and then **discarded** (see §6) |
| Gates (~30) | `post_edit`, `stop_quality_gate`, `tdd_gate`, `coverage_gate`, `complexity_check`, `lean_sniffers`, `destructive_guard`, `mcp_trust_gate`, … | Lint path is the flagship and solid; command-surface gates vary (see §6) |
| Evidence | `trace`, `ratchet`, `suppressions_v3`, `baseline`, `bench`, `health_telemetry`, `report` | Solid; this is a proto “Dev-Intelligence” layer in JSONL form |
| Spec/process | `plan_validator`, `spec_audit`, `ux_spec_gate`, `trace_requirements`, `worklog` | All existence/mtime/heading heuristics — no content semantics |
| Distribution | `init_cmd`, `doctor`, `install`, `policy_remote`, CI templates | Solid; installed-wheel path under-tested |

## 4. Agent & workflow abstractions (what exists)

1. **`fettle.agents`** — payload-shape translation, not execution.
2. **`subagent_inject.js`** — injects a lean-coding prompt into host-spawned
   subagents (`[gates.subagent]`). Context injection, not delegation.
3. **`evals_runner.py`** — the only place an agent is launched; scenario YAML +
   three-valued verdicts (pass/fail/indeterminate). Embryonic: 2 scenarios,
   regex checks, single-run, Claude-only.
4. **`cross_review.py` / `learn.py`** — LLM-as-worker (HTTP endpoint / Ollama).

No supervisor, personas, delegation protocol, task queue, or agent lifecycle
management exists anywhere.

## 5. Configuration surface

7 top-level tables, **30 gate sub-tables** in the generated schema. Key facts:
[docs/CONFIG.md](../CONFIG.md) documents only ~7 of 30 gates; **no feature
dependency graph exists** (nothing records that `[gates.coverage]` needs
`coverage.json` from pytest-cov, or that BDD (planned WP-154) needs
`trace_requirements`); validation is per-key type/enum shape only
(`fettle config --validate`), not cross-feature consistency. This is the WP4 target.

## 6. Test strategy

~1150 tests, near 1:1 test-module-per-source-module. Styles: subprocess
contract tests (real dispatcher process, stdin/stdout JSON — the signature
style, ~4.5 min full suite), in-process unit tests, golden/anti-drift tests
(schema, version alignment, rule fixtures). Guard chain: commit = fast
consistency tests; push = full suite. CI: ubuntu+macos matrix, pinned semgrep +
canary leg, dogfood self-scan.

Gaps: no session-level E2E (multi-event sequences), installed-wheel path barely
exercised, evals are a proof of concept, no suite tiers/markers, no perf
regression tests despite hard latency budgets, TS/VS Code surfaces untested.

## 7. Weakest parts of the codebase (ranked)

1. **Silent-failure gaps at the dispatcher level** — check crashes and
   budget-exhaustion skips are recorded in the `Aggregator` but `finish()`
   never emits them; nothing reaches trace.jsonl. Bad stdin/config/registry
   failures fail-open untraced. The product's own north star ("no silent
   failures") holds on the lint path (`gate_error` trace events in
   [fettle/post_edit.py](../../fettle/post_edit.py)) but not here.
2. **Command-surface scanners swallow tool failures** — `security_review`,
   `threat_model`, `pr_review`, `deploy_gate` catch tool-missing/timeout with
   `pass`: a security review can silently report zero findings with no tools run.
3. **Telemetry writers fail silently** — `trace.log_decision` and
   `health_telemetry` swallow `OSError`; loss of the audit log is undetectable
   from the audit log.
4. **`threat_model.py`, `cross_review.py`, `mutation_test.py`** — grep-template
   filler; dead fallback code; brittle stdout scraping, respectively.
5. **`plan_validator.py` domain leak** — one project's vocabulary ("facts",
   "nodes", health dimensions) hardcoded into a general tool.
6. **Docs drift** — WP-133 number collision (eval lab vs CLI repair);
   README says 12 commands, lists 11, repo has 17; CONFIG.md covers 7/30 gates;
   two competing worklog models (daily journal shipped vs per-work-item
   proposed in [docs/continuity-traceability-plan.md](../continuity-traceability-plan.md));
   ~10 dead/stale plan files intermixed with live ones.

## 8. Live vs dead planning documents

**Live**: [ROADMAP.md](../ROADMAP.md), [fettle-enterprise-product-plan.md](../fettle-enterprise-product-plan.md)
(WP-133..155), [continuity-traceability-plan.md](../continuity-traceability-plan.md) (proposed).
**Dead/executed** (stale statuses): PLAN-v050-adaptive, WORKPACKAGES-v050,
SPEC-dispatcher-v2 (superseded layout), v08/v09/v10 plans, swebok-gaps,
expansion-plan, AUDIT-GPT55*, ci-enforcement-plan ("ACTIVE" but shipped).
