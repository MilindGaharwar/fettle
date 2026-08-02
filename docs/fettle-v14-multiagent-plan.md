# Fettle v1.4 — Multi-Agent Integrity Plan

**Theme: policy continuity, topology intelligence, and governed self-evolution.**

Status: PLANNED · Author: engagement session 2026-08-02 · WP range: WP-156..WP-163

---

## 0. Problem statement

Fettle enforces quality per-agent and per-checkpoint. It does not yet enforce
quality **across delegation**. When an executor agent spawns another agent —
a Claude Task subagent, a `codex exec` worker, a `gemini --yolo` helper — the
policy constraints imposed on the parent are **not reliably passed to the
child**. This is the confused-deputy problem for agent swarms, and the OWASP
Agentic Security Initiative catalogues its failure modes directly (privilege
compromise, orchestration exploitation, agent communication poisoning —
*Agentic AI Threats and Mitigations*, OWASP ASI, Feb 2025).

### Audited gaps in Fettle today (verified against code, 2026-08-02)

| # | Gap | Evidence |
|---|-----|----------|
| G1 | **Bash-spawned nested agents are ungoverned.** `bash_audit.py` has zero patterns for `claude -p`, `codex exec`, `gemini`, `opencode run`. A parent agent can launch a child with `--dangerously-skip-permissions` / `--yolo` / `--full-auto` and the child edits with no hooks, no gates, nothing until commit time. | grep of `fettle/bash_audit.py` — no agent-CLI patterns |
| G2 | **Subagent injection is advisory prose, not policy.** WP-104's `SubagentStart` hook injects a discipline ladder (≤500 tokens, fails open, Claude-only). It transfers *culture*, not *constraints*. | `tests/test_subagent_inject.py`, `config.py` `"subagent": {"enabled": True, "injection_file": ""}` |
| G3 | **Session state is isolated but lineage is invisible.** Per-session state dirs prevent corruption, but nothing records that session B was spawned by session A. Trace records have no `parent_session_id`; delegation chains cannot be audited or reported. | `trace.py` record schema |
| G4 | **cwd escape.** A child spawned outside the repo (temp dir, sibling clone) never discovers `.fettle.toml`. Policy is repo-anchored; delegation is not. | `paths.find_repo_root` walk-up semantics |
| G5 | **Worktrees are opt-in; claims gate exempts the main worktree.** Concurrent agents editing main tree collide invisibly; rollback of one agent's work requires surgical git archaeology. | `claims_gate.py` lines 24-26: `is_linked_worktree` false → `allow()` |
| G6 | **No topology guidance.** Fettle has runners, worktrees, work items, claims — every primitive for a supervised swarm — but no component that recommends, materializes, or monitors an actual topology. | absence |

Downstream consequence: a developer using multi-agent workflows either
hand-wires all of this per project (they won't) or ships work produced under
weaker constraints than they configured. **Fettle's promise — one policy,
enforced everywhere — is currently false across the delegation axis.**

---

## 1. Design principles

1. **Policy is monotonic down the delegation tree.** A child may run under
   *stricter* policy than its parent, never weaker. (Mirrors `config_protect`
   semantics: org > repo > session.)
2. **Enforcement over instruction.** Prompt injection (WP-104) stays as
   defense-in-depth, but the load-bearing mechanism must be verifiable
   machinery: env propagation + digest verification + spawn gating.
3. **Blessed path + guarded escape.** `fettle spawn` is the easy, correct way
   to launch a child agent. Raw CLI spawns are detected and blocked/warned by
   gate, not by documentation.
4. **Fail closed on capsule tampering, fail open on absence** (advisory mode
   first, `enforce` once proven — same maturation path every Fettle gate took).
5. **Autonomy never weakens policy.** Self-evolution (Pillar C) may propose;
   only humans promote. No exceptions.

---

## 2. Pillar A — Policy Continuity (WP-156..158) — *ships first, v1.4.0*

### WP-156 — Policy Capsule

A capsule is a content-addressed snapshot of the **effective merged policy**
(org `[extends]` layer + repo `.fettle.toml` + protected-key resolution)
written at session start:

```
$XDG_STATE_HOME/fettle/capsules/<sha256-16>.json
{
  "fettle_capsule": 1,
  "digest": "<sha256 of canonical-JSON policy body>",
  "policy": { ...merged effective config... },
  "origin": {"repo_root": "...", "session_id": "...", "created_at": "..."},
  "lineage": ["<parent capsule digest>", ...]
}
```

- New module `fettle/policy_capsule.py`: `write_capsule()`, `resolve_capsule()`,
  `verify_capsule()` (recompute digest, reject mismatch), and
  `merge_for_child()` — child effective policy = capsule policy overridden
  only by *stricter* values (mode ladder: `silent < advisory < enforce`;
  numeric budgets: min(); booleans: `enabled=true` wins). Weaker child values
  are ignored and surfaced as a finding.
- Propagation: env var `FETTLE_POLICY_CAPSULE=<path>` set by `fettle spawn`
  (WP-157) and exported by the dispatcher into hook-launched tool
  environments where the agent runtime allows it.
- Dispatcher change: config resolution order becomes
  `verified capsule (if env present) → repo .fettle.toml → defaults`. A
  capsule with a bad digest is **rejected loudly** (block on Pre, since
  tampering is the attack).
- Solves G4: capsule carries the policy with the child even when cwd has no
  `.fettle.toml`.
- Stdlib only: `hashlib`, `json`, canonical serialization (sorted keys).

Tests: capsule round-trip; tamper → reject; monotonic merge matrix (each
override direction); cwd-escape scenario (child in tmp dir still enforced);
lineage chain of 3.

### WP-157 — Spawn gate + `fettle spawn`

- **`fettle spawn <runner> [--task ...] [--worktree ITEM]`** — the blessed
  path. Uses the existing runner registry (claude/codex/gemini/opencode),
  writes the capsule, sets `FETTLE_POLICY_CAPSULE`, optionally provisions a
  claimed worktree (Stage 4 primitives), records lineage in the trace.
- **`[gates.agent_spawn]`** (new, `mode = "advisory"` default, `enforce`
  available): extends `bash_audit` with agent-launch detection:
  - patterns: `claude\s+(-p|--print)`, `codex\s+exec`, `gemini\s+.*(--yolo|-p)`,
    `opencode\s+run` (+ conservative word-boundary guards; precision > recall,
    same philosophy as existing bash_audit rules).
  - findings: (a) nested launch without `FETTLE_POLICY_CAPSULE` in the
    command's env → "unpropagated spawn"; (b) permission-bypass flags
    (`--dangerously-skip-permissions`, `--yolo`, `--full-auto`) without a
    capsule → **block in enforce mode**; (c) advisory pointing at
    `fettle spawn` as the fix.
- `fettle doctor` gains a check: for each runner installed on the machine,
  verify Fettle hooks are configured for that runtime (init parity from
  Stage 13) — a spawned codex on a machine where `fettle init codex` never ran
  is a silent hole; make it visible.

Tests: pattern precision fixtures (violating + clean per runner); spawn gate
advisory vs enforce; `fettle spawn` end-to-end with FakeRunner asserting env,
worktree, claim, trace lineage.

### WP-158 — Delegation lineage & audit

- Trace records gain optional `parent_session_id` + `capsule_digest` fields
  (versioned JSONL — additive, no migration).
- `fettle report --lineage`: renders the delegation tree for a time window —
  which sessions spawned which, under which capsule, with per-node
  block/advisory counts. Orphans (sessions without capsules in a repo where
  `[gates.agent_spawn]` is `enforce`) flagged.
- Compliance hook: lineage joins the existing `--compliance` report so an
  auditor can answer "was every edit in this release made under org policy,
  including by sub-agents?" — the question no other tool can answer today.

Sizing: A = ~3 stages, each committable independently (capsule → spawn/gate →
lineage). Ship order fixed: 156 → 157 → 158.

---

## 3. Pillar B — Topology intelligence (WP-159..161) — *v1.4.x*

Fettle should advise on, materialize, and supervise the multi-agent topology
appropriate to the task — using primitives it already owns.

### WP-159 — `fettle topology advise`

Deterministic, explainable heuristics (no LLM required; LLM-optional
narrative later):

Inputs: work items (`fettle work list`), spec scenarios (`specs/`), import
graph coupling (`import_graph.py`), historical trace (block rates, loop
detections), repo size, test-suite latency.

Output: recommended topology + rationale, from a small catalogue:

| Topology | When | Fettle mapping |
|---|---|---|
| **Solo** | single work item, high coupling between touched files | main worktree, full gates |
| **Writer → Reviewer** | risky change, or trace shows elevated block rate | 2 sessions, fresh-context reviewer via `fettle spawn --task review`, cross_review gate |
| **Parallel workers + integrator** | N≥2 work items with disjoint import-graph footprints | N claimed worktrees + spawn per item; integrator session merges, CI gate arbitrates |
| **Pipeline (plan → implement → UAT)** | spec-rich task | plan_validator → worker → existing `fettle uat` |

Disjointness check is the real intelligence: two work items whose predicted
file footprints overlap in the import graph → do NOT parallelize (this is the
cross-agent semantic-conflict gap named in the v1.3 retrospective, addressed
*before* it happens rather than caught at merge).

### WP-160 — `fettle topology apply`

Materializes the advised (or explicitly chosen) topology: creates work items
if missing, provisions worktrees + claims, spawns runners with capsules
(WP-157), writes a `topology.json` manifest to the shared git common dir.

### WP-161 — `fettle topology status` / control

- `status`: live table from claims + per-session trace + `fettle ci` — per
  worker: item, worktree, last activity, blocks fired, loop-detect state,
  budget consumed. Stalled/looping workers highlighted.
- Controls: `fettle topology revoke <item>` (revoke claim, signal runner),
  `reassign <item> <runner>`. Per-worker stop-loss budgets (max blocks, max
  wall-time) — breach → auto-revoke in enforce mode, advisory otherwise.
- Monitoring stays pull-based CLI first (fits stdlib + no daemon); a watch
  mode (`--watch`, poll loop) is acceptable; long-lived supervisor daemon is
  explicitly out of scope for v1.4.

---

## 4. Pillar C — Worktree enforcement & governed self-evolution (WP-162..163)

### WP-162 — `[worktrees].require`

Answering the audit (G5): today worktrees are opt-in and the claims gate
exempts the main worktree. Add:

```toml
[worktrees]
require = false        # true → edits in the MAIN worktree are gated
exempt_paths = ["docs/**", "*.md"]   # solo-friendly carve-outs
```

When `require = true` (recommended default for topology-managed repos, set
automatically by `topology apply`): a Pre edit in the main worktree →
advisory (or block, per `gates.claims.mode`) directing to
`fettle worktree create` + `fettle work claim`. Every unit of work then lives
on branch `fettle/<item-id>` — exploration is cheap, tracking is `fettle
worktree list`, rollback is branch deletion. The main tree becomes
merge-only, which is exactly the property that makes multi-agent work
reviewable.

### WP-163 — Governed self-evolution (hermes-agent learnings)

Hermes-agent (Nous Research) demonstrates a closed learning loop: skills
created from experience, self-improved during use, memory curated across
sessions, scheduled autonomous maintenance. Fettle's analogue must stay
**governed** — the harness that guards quality cannot self-modify unattended.
What we adopt, translated:

| Hermes pattern | Fettle translation | Guardrail |
|---|---|---|
| Autonomous skill creation after complex tasks | **Self-triggered `fettle learn`**: when 30-day trace shows a repeated failure signature (same rule-less block pattern, recurring CI failure class), auto-draft a semgrep rule + fixtures as a *proposal* in `rules/proposed/` | Human approval required to move to `rules/learned/`; proposals never load into gates |
| Skills self-improve during use | **Evidence-based rule ratchet**: learned rules carry precision stats from trace (fired vs overridden/FP-stamped); high-precision advisory rules become promotion candidates (`fettle rules promote --candidates`), noisy rules become demotion candidates | Promotion/demotion = explicit human command; stats are computed, decisions are not |
| Cross-session memory + insights | **`fettle insights`**: weekly digest from trace — top friction gates, emerging failure classes, rule candidates, lineage anomalies | Read-only |
| Cron automations | Documented recipes: nightly `fettle report`, `doctor --verify-hashes` drift check, insights digest → CI cron | Recipes, not a daemon |

This is the honest version of "self-evolving": the *sensing* and *drafting*
loops are autonomous; the *policy mutation* step keeps a human in it, because
principle 5 (autonomy never weakens policy) is only checkable by a person for
newly-created rules.

---

## 5. Sequencing & release mapping

```
v1.4.0  Pillar A (WP-156, 157, 158)     ← security-critical, ships alone
v1.4.1  WP-162 worktree require + WP-159 advise
v1.4.2  WP-160 apply + WP-161 monitor/control
v1.5.0  WP-163 self-evolution loop      ← after A+B produce the trace signal it feeds on
```

Existing v1.4 "Product surface" items (WP-149..153, WP-155) re-slot behind
Pillar A or interleave where independent (Windows/WP-151 and docs/WP-152 are
orthogonal; WP-155 semantic impact gate pairs naturally with WP-159's
disjointness check and should be co-designed).

## 6. Success criteria

1. A `codex exec` worker spawned by a Claude session in a temp dir is provably
   governed by the same org policy — demonstrated by an eval scenario, not a doc.
2. `agent_spawn` enforce mode blocks a `--dangerously-skip-permissions` nested
   launch in fixture tests and in a live smoke.
3. `fettle report --lineage` reconstructs a 3-level delegation tree from a
   real multi-agent run.
4. `topology advise` refuses to parallelize two work items with overlapping
   import-graph footprints, with a stated reason.
5. Zero new runtime dependencies; all gates ship advisory-first with an
   `enforce` mode; published schema + docs regenerated in the same commits.

## 7. Explicit non-goals (v1.4)

- No supervisor daemon / message bus between agents (claims file + trace are
  the coordination substrate; revisit only with evidence they're insufficient).
- No LLM-in-the-loop for topology advice v1 (deterministic + explainable first).
- No autonomous rule promotion, ever, without a human command.
- No attempt to sandbox child agents at the OS level (that's the runtimes' job;
  Fettle governs policy, not syscalls).
