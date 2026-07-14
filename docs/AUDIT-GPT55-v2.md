# Fettle Architectural Audit — GPT 5.5 (2026-07-14)

> Full review of Fettle v0.5.0-phase8 by GPT 5.5 via GenAI Nexus.
> Prompt: "Complete architectural review + v2.0 redesign proposal."

## Executive Summary

Fettle has the right instinct — fast, local, deterministic checks in the AI agent loop — but the implementation is at the danger point where a prototype can become "a pile of clever scripts."

**Main problems (in order):**
1. 16 gates is too many for user-facing UX (implementation taxonomy leaking into product)
2. Script-per-hook architecture multiplies startup cost and inconsistency
3. No policy model — checks don't self-describe, no scheduling, no budget
4. No measurement loop proving gates reduce defects more than they annoy
5. Premature subjective/LLM guardrails before deterministic ones are measured

**Strongest parts:** Safety gates, deterministic tooling, hook timing, AI-actionable feedback.

---

## 1. Gate Assessment

| Gate | GPT Rating | Recommendation |
|------|-----------|---------------|
| `lint` | High | Keep. Core value. |
| `destructive` | Very high | Keep as blocker. |
| `config_protect` | High | Keep. |
| `mcp_trust` | High (if MCP used) | Keep conditional. |
| `commit_message` | Medium-high | Keep. |
| `secret_scan` | Very high | **Promote to first-class gate.** |
| `debug detection` | Medium-high | Keep. |
| `loop_detect` | Medium | Advisory only. |
| `scope_creep` | Medium-low | Advisory, needs measurement. |
| `docs` | Medium-low | Move to Stop summary. |
| `plan` | Low-medium | Kill as gate → optional workflow. |
| `ux_spec` | Low (generic) | Off unless design spec detected. |
| `ui_colors` | Low (generic) | Replace with design-token rule. |
| `cross_file` | Unclear | Rename to dependency-impact. |
| `ci_bootstrap` | Medium | Not a hook gate → setup/doctor. |
| `subagent` | Low as enforcement | Keep as agent coaching, not "gate." |
| `lean_review` | Experimental | Keep gated. Requires corpus. |

### Recommended Taxonomy

| Category | Policy | Examples |
|----------|--------|----------|
| **Safety** | Sync, can block | destructive, config_protect, mcp_trust, secrets |
| **Correctness** | Post-edit advisory, optional strict | ruff, semgrep, tsc, debug detection |
| **Workflow** | Stop/pre-push summary | commit_message, docs, tests, CI parity |
| **Agent Behavior** | Advisory only | loop_detect, scope_creep, subagent injection |
| **Experimental** | Off by default | lean_review LLM, architecture review |

---

## 2. Architecture: What to Fix

### Immediate (v1 hardening)

1. **Single dispatcher** — replace N script invocations with one `fettle hook --event X`
2. **Check registry** — each check declares id, events, budget, requires, severity
3. **Structured finding schema** — all checks emit same format
4. **`fettle doctor`** — visible degraded-mode reporting
5. **Reclassify gates** into 4-5 categories (not 16 individual toggles)
6. **Secret scanning as first-class gate**
7. **Fixture tests for semgrep rules**
8. **Suppression system** — `# fettle:ignore[check_id] reason="" expires=""`

### Medium-term (v1.5)

1. SQLite state store (replace JSONL sprawl)
2. Cache/debounce layer (don't rerun on unchanged files)
3. `fettle config explain`
4. Baseline support (`fettle baseline create`)
5. Latency + finding metrics
6. Golden corpus replay harness
7. Time budgets per execution class

### v2.0 (full redesign)

Event-driven policy engine:
```
Claude hook → hook shim → engine
                            ├── policy engine (decides what runs, can it block?)
                            ├── scheduler (sync-pre / sync-post / async / stop)
                            ├── check registry (typed plugins)
                            ├── project profiler (cached)
                            ├── state store (SQLite)
                            ├── renderer (Claude / CLI / JSON / CI)
                            └── telemetry recorder
```

---

## 3. Configuration UX

### Current (too complex)
```toml
[gates.lint]
enabled = true
mode = "advisory"
[gates.destructive]
enabled = true
mode = "advisory"
# ... 14 more sections
```

### Proposed (simple default)
```toml
mode = "advisory"  # off | minimal | advisory | strict | ci
profile = "auto"   # auto | python | typescript | polyglot
```

Advanced overrides available but not required.

---

## 4. Missing Capabilities

1. **First-class secret scanning** (block on high-confidence secrets)
2. **Dependency/supply-chain checks** (new deps, unpinned, vulnerable)
3. **Generated-file awareness** (skip noise on OpenAPI/protobuf/vendored)
4. **Migration/DB safety** (destructive migrations, missing rollback)
5. **API contract checks** (breaking schema changes)
6. **Impacted-test detection** (map source→test, suggest exact command)
7. **Baseline support** (only surface new issues)
8. **Autofix metadata** (machine-actionable fix commands)
9. **Policy test framework** (positive/negative fixtures per rule)
10. **Privacy model** (what's local-only, what goes to LLM?)

---

## 5. Effectiveness Measurement (most important gap)

### Must answer:
- Did Fettle prevent real defects?
- Did users accept the advice?
- Did it slow them down?
- Which gates are noisy/ignored?
- Which correlate with fewer CI failures?

### Promotion criteria:
- Default-on: p95 < budget, FP rate < 10%, fix rate > 40%
- Blocking: precision > 95%, deterministic, actionable, suppressible

---

## 6. v2.0 Design (if from scratch)

**Keep:** Hook integration, fail-open, advisory-default, profile-driven, tool-wrapping, AI-optimized output, destructive guard, config protect, lean sniffers (silent)

**Kill:** plan gate, ux_spec gate, ui_colors (generic), subagent as "gate", ci_bootstrap as hook gate

**Replace:** Many scripts → one dispatcher. Gate-centric config → mode/category config. JSONL → SQLite. Generic checks → typed self-describing plugins.

**Add:** Policy engine, scheduler, cache, suppressions, baselines, telemetry, secret scanning, dependency checks, impacted-test detection.
