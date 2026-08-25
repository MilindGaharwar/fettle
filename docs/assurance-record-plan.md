# Assurance Record Program (P80–P83)

Status: PROPOSED → P80 authorized to start · Source: strategic review
(2026-08-25, GPT cross-examined against codebase) · Related:
docs/plan-index.md, docs/mutation-ratchet-decision.md,
docs/uat-strength-plan.md

## The product thesis

One conceptual primitive: the **Assurance Record** — a canonical,
digest-bound, machine-readable answer to:

> "Can we prove that this agent-generated change was authorized, correctly
> executed, sufficiently verified, and safe to release?"

Everything Fettle already ships (gates, mutation, UAT, ledger, graph, CI
binding, specs) is an *input*. The record is the *output*. Release
policies are machine-checkable rules over the record's assurance vector.

## Why the assurance chain is digest references, not a persistent graph

The lifecycle chain (requirement → plan → agent → delegation → tool calls
→ files → commit → tests → mutation → CI → release) is stored today as a
chain of canonical artifacts, each already digest-bound:

requirement (spec, git) → plan (work item, git) → actions (trace,
append-only) → files (P45 snapshot manifest) → commit (git) → tests
(trace markers) → mutation (report artifact) → CI (remote verdict) →
release (tag + provenance).

The Assurance Record stores an ordered list of stage references
{stage, artifact_path, digest, freshness, completeness} — the linearized
chain. Graph views are projections of the references. A persistent graph
store would reintroduce the staleness/tamper class the evidence contract
excludes (P66), and P51's measured-admission gate remains the decision
path if aggregation performance ever demands persistence.

## Milestones

### P80 — Assurance Record v1 (aggregation)

`fettle/assurance.py`: canonical record joining existing artifacts —
verify stamp, mutation report, UAT report, governance ledger (+anchor),
spec coverage summary, CI stamp (when present), policy digest, source
snapshot digest, spawn lineage.

Record shape (v1):

    schema_version, subject {commit, worktree}, generated_at
    stages: [{stage, path, digest, present}]     # ordered chain refs
    dimensions: {authorization, policy_integrity, scope, behavior,
                 security, independence, provenance, uat, ci}
        each: {status: PASS|FAIL|UNKNOWN|NOT_APPLICABLE,
               evidence: [{path, digest}]}
    completeness: COMPLETE | PARTIAL
    digest

CLI: `fettle assurance [--root .] [--json]`.

Independence v1 (presence-based): roles declared (authorship gate
config), spawn lineage present (FETTLE_PARENT_SESSION), tests-vs-code
authorship separation observable → status PASS (separated) / UNKNOWN
(insufficient data). Grading arrives in P82.

Acceptance: golden end-to-end test on the assurance-loop fixture produces
a complete record; missing artifact → dimension UNKNOWN with reason;
digest is canonical and stable.

### P81 — Assurance vector + sufficiency policy

Formal vector over the record's dimensions; release policies as
machine-checkable rules:

    [assurance.release.production]
    authorization = "PASS"
    policy_integrity = "PASS"
    security = "PASS"
    behavior = "PASS"
    independence = "PASS|UNKNOWN"   # policy decides
    provenance = "COMPLETE"

Wire into the completion-gate pattern (criterion-typed, evidence-checked).
Render the "Why should I trust this change?" explanation (CLI; every
assertion carries its evidence reference).

### P82 — Independence computation

Join authorship of code vs tests vs verifying identity from P52 roles +
spawn lineage chains + work-item claims. independence ∈ {LOW, MEDIUM,
HIGH, UNKNOWN} with defined criteria; feeds the vector dimension.

### P83 — Assurance Adversary v1

Codify existing tamper coverage (ledger tampering, transcript drift,
docs-claims, capsule tamper) into a named adversary suite; add stale-
evidence injection, scope-manipulation attempt, policy-downgrade attempt.
Each adversary is a test proving detection. Feeds P77 benchmark scoring.

## Integration with existing programs

- P77 benchmark scores the record (false passes, evidence completeness).
- P48 consumer graduation feeds the behavior dimension (graph parity).
- P49 uses the ledger as substrate (evaluation memo: recommended).
- Completion gate consumes the vector for SHIP/FIX_FIRST/REJECT.
- Enforced mutation gate is the behavior dimension's generator.

## Non-goals

- Persistent graph store (P51 gate decides if ever needed).
- Numeric assurance score (vector + policy, per doctrine).
- New agent framework, LLM, observability platform, rule-count chase.
