# Work-Item Lifecycle Integrity Implementation Plan

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/lifecycle.md).

Status: PROPOSED; planning only; no implementation, corpus migration, parser,
CLI, hook, CI, release, or enforcement change is authorized

UX contract: [work-item-lifecycle-integrity.ux-spec.md](work-item-lifecycle-integrity.ux-spec.md)

Research basis: [completion lifecycle hypothesis tree](completion-lifecycle-hypothesis-tree.md)

## 1. Objective

Prevent machine-detectable contradictions between work-item lifecycle, final
closure, criterion-level completion evidence, and structured portfolio projections
from reaching a protected merge or governed release.

This plan closes the defect demonstrated by the historical P46 record, which was
committed with `status: open` and a substantive final Resolution. It extends the
existing work-item and v2 completion contracts rather than creating another
completion authority.

## 2. User Story

As a Fettle maintainer or coding agent, I want contradictory work-item lifecycle
records to fail visibly before protected merge or release, so portfolio status
cannot silently disagree with closure evidence.

## 3. Current Baseline And Incident

- Commit `27b957c` introduced `docs/backlog/p46-ephemeral-hypergraph.md` with
  `status: open` and a final `## Resolution` in the same change.
- `fettle/work_items.py` recognizes `open`, `claimed`, and `done`, but currently
  warns only when `done` lacks a Resolution heading.
- `fettle completion validate` evaluates manifests and links evidence only for v2
  done items; legacy P46 is intentionally outside that evidence requirement.
- `fettle work list` runs repository work-item lint, but existing lint has no
  structured final-closure invariant and is not an explicit required CI command.
- Plans, TODOs, and indexes repeat status manually without generic reconciliation.
- The UAT plan acknowledges logical duplicate records with inconsistent metadata.

The current P46 metadata correction is a candidate migration, not prevention
evidence. The committed historical record must remain available as a regression
fixture independently of the live file.

## 4. Authority And Schema Contract

1. `status` is the sole persistent work-item delivery state.
2. New v2 records use `open` or `done`. Runtime ownership remains solely in
   `claims.json` and never changes delivery state.
3. Legacy `claimed` remains readable during migration but cannot be newly authored
   in v2 after enforcement. WP-WLI-0 must freeze its final migration treatment.
4. `closure: final` is a declarative consistency marker, not evidence and not a
   second completion verdict. `done` requires it and `open` forbids it.
5. For v2 `done` items, `fettle work validate` reuses the existing completion
   evaluator and reports its non-pass result. It does not evaluate criteria or
   derive a competing completion decision. Boundaries still invoke both commands.
6. Legacy v1 items must satisfy basic state/closure consistency, but historical
   manifests are not fabricated.
7. Standalone historical completion manifests remain compatible and do not imply
   work-item state.
8. Final closure means the bounded work item's acceptance contract was delivered;
   it does not imply program authorization, qualification, graduation, promotion,
   Assurance, or completion of wider follow-up work.
9. Reopening changes active state to `open` and removes the active final marker.
   Historical prose and manifests remain records, not current closure.
10. Markdown prose and headings have no lifecycle authority. Validation never
    parses Resolution text or repairs records automatically. The current
    `done`-without-Resolution warning is retired rather than promoted into the new
    lifecycle contract.

The exact field types, permitted identity links, line-location rules, reopen
semantics, and state/closure/manifest matrix are frozen by WP-WLI-0 before code.

## 5. User Flow

```text
edit structured work item
    -> fettle work validate
    -> valid OR exact conflict and manual recovery
    -> fettle completion validate for criterion evidence
    -> local commit feedback
    -> blocking CI required aggregate
    -> release preflight before build
```

`fettle work validate [--json]` is the proposed canonical lifecycle command.
`fettle work list` remains presentation. `fettle completion validate` remains the
criterion-evidence authority.

## 6. Assumptions And Constraints

1. Authorized audit hardening remains P0 and overlaps `tests/**`, CI, release, and
   planning documentation. WLI implementation waits until that work is stabilized
   or the operator separately authorizes a bounded integrated repair.
2. Branch and release protection are external facts. They remain `UNKNOWN` unless
   verified through authenticated host evidence.
3. Corpus counts are frozen at audit time and compared with discovery output; this
   plan does not hardcode the current count.
4. Existing Resolution sections may be placeholders, partial progress, or final
   explanations. Heading presence is not a closure signal.
5. Logical identity is never inferred from similar filenames or IDs. Alias or
   supersession requires the same acceptance boundary, owner, and deliverable plus
   operator-reviewed disposition.
6. No permanent baseline, allowlist, or suppression may hide a lifecycle conflict.

## 7. Decisions And Tradeoffs

| Approach | Benefit | Risk | Decision |
|---|---|---|---|
| Treat `## Resolution` as closure | Minimal implementation | Existing placeholders and partial-delivery records become false positives | Rejected |
| Structured final marker plus existing completion evaluator | Deterministic lifecycle without duplicating evidence authority | Requires corpus migration and consumer review | Selected |
| Derive all state from completion manifests | One apparent authority | Breaks open planning, legacy records, and standalone manifests | Rejected |
| Full transactional lifecycle service | Controlled transitions | Excessive migration and operational complexity | Deferred pending evidence |
| Parse arbitrary plan prose | Broad apparent coverage | Fragile semantics and false assurance | Rejected |
| Generate or validate structured projections | Reduces status drift while preserving typed program decisions | Requires explicit IDs and bounded coverage | P1, separately authorized |

## 8. Work Packages

Every package requires explicit authorization. Planning approval does not authorize
implementation, migration, hooks, workflow changes, or enforcement.

### WP-WLI-0: Freeze Lifecycle And UX Contract

Priority: P0. Estimate: 1-2 days. Planning/schema only.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Inventory every work item by version, status, closure kind, logical milestone, and runtime claim | AUDIT | A machine-readable or stable table has the same IDs and count as `uv run fettle work list --json` at audit time |
| 2 | Decide legacy `claimed` migration and freeze the state, closure, manifest, and reopen truth table | SPECIFY | Two reviewers apply the exact rules independently and record zero unresolved item/rule differences |
| 3 | Freeze the closure field schema and line-precise human/JSON finding contract | SPECIFY | Every supported combination maps to one validity, exit, and manual recovery result |
| 4 | Trace all consumers, freeze the lifecycle-to-completion delegation boundary, and decide invalid-record behavior for each | REVIEW | Impact table covers work list/validate, the existing `evaluate_manifests` result and error model, completion/gate, provider, semantic, graph shadow, topology/apply, and focused tests; no second evidence evaluator is introduced |
| 5 | Record current command limitations without promoting them to assurance | LIVE | Run `uv run fettle work list --json` and `uv run fettle completion validate`; retained baseline names the absent invariant |

Exit: schema, corpus, consumer policy, UX/BDD contract, and reviewer decisions are
accepted. No production behavior changes.

### WP-WLI-1: Preserve Red Corpus And Expected Migration

Priority: P0. Estimate: 1 day. Fixtures and expected outcomes only.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Preserve the committed historical P46 contradiction as an immutable fixture | SPECIFY | Fixture retains `open` plus final delivered closure independently of the live P46 correction |
| 2 | Specify the full state, closure, version, manifest, reopen, duplicate, alias, and supersession matrix | SPECIFY | Every fixture has an expected rule, severity, exit, and manual recovery |
| 3 | Inventory live-corpus findings and proposed dispositions without editing live records | AUDIT | One row exists per discovered item and logical identity; no naming-similarity inference occurs |
| 4 | Adjudicate possible aliases by acceptance boundary, owner, and deliverable | REVIEW | Operator decisions leave zero unresolved identity questions before migration |
| 5 | Preserve expected pre-fix outcomes | VERIFY | Reviewers confirm P46 is non-pass while P77 partial progress and placeholder headings do not imply closure |

Exit: red fixtures and a migration ledger are frozen; the live corpus is unchanged.

### WP-WLI-2: Implement Strict Repository Lifecycle Validation

Priority: P0. Estimate: 2-4 days. Separate implementation authorization required.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing parameterized tests for the full truth table and historical P46 fixture | TDD | `uv run pytest tests/test_work_items.py -q` fails only on missing lifecycle behavior before production edits |
| 2 | Parse structured closure and identity fields, retire the existing Resolution-heading warning, reject duplicate front-matter keys, and emit blocking line-precise errors | CODE | Unit tests prove Resolution headings and prose have no lifecycle effect and no automatic repair or warning-only contradiction remains |
| 3 | Add `fettle work validate [--json]` and preserve list compatibility | INTEGRATION | Disposable clean and contradictory repositories return documented human/JSON fields and exit codes |
| 4 | Reuse the completion evaluator for v2 done items and propagate invalid records through frozen consumers | INTEGRATION | Focused completion, gate, provider, semantic, graph, and topology tests prove no parser error becomes complete or usable authority |
| 5 | Preserve P46, persistent-claimed/runtime split, malformed closure, manifest, alias-cycle, and missing-target failures while P77-style progress stays open | REGRESSION | Named fixture assertions pin every result without a baseline or suppression |
| 6 | Exercise the validator against red and clean repositories | LIVE | Run `uv run fettle work validate --json`; the P46 fixture exits nonzero with exact recovery and the clean fixture exits zero |

Exit: one repository-wide lifecycle validator rejects machine-detectable
contradictions, delegates v2 evidence decisions, and never auto-fixes.

### WP-WLI-3: Reconcile The Live Corpus Without Fabricating Evidence

Priority: P0. Estimate: 1-2 days. Starts only after WP-WLI-2 proves the red corpus
fails.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Apply the frozen migration ledger to structured work-item metadata | MIGRATE | Every edit traces to an accepted disposition; prose changes only where the ledger separately records an editorial correction |
| 2 | Add canonical milestone, alias, or supersession fields only where identity was adjudicated | MIGRATE | One active authority exists per logical milestone; all targets exist and no cycles remain |
| 3 | Update only structured plan, TODO, and index references needed to preserve current typed semantics | MIGRATE | Delivery, authorization, qualification, graduation, and promotion remain distinct; unrelated status does not change |
| 4 | Independently review migration against the pre-fix inventory | REVIEW | Review records zero omissions, suppressions, fabricated evidence, or unresolved discrepancies |
| 5 | Validate the complete migrated repository | VERIFY | `uv run fettle work validate --json` and `uv run fettle completion validate` both pass without a baseline or allowlist |

Exit: the live corpus is green under the already-implemented validator.

### WP-WLI-4: Require Lifecycle Validation At Repository Boundaries

Priority: P0. Estimate: 1-2 days. Separate boundary authorization required.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing command and workflow tests proving lifecycle validation is independently invoked | TDD | Focused tests fail while lifecycle validation is absent from blocking CI and release preflight |
| 2 | Add a convenience pre-commit hook, dedicated blocking CI lifecycle job, `CI required` dependency, and release-preflight commands | CODE | Workflow tests pin exact commands, dependencies, and ordering before build |
| 3 | Exercise clean and contradictory disposable repositories and workflow contracts | INTEGRATION | Human/JSON exits agree; required aggregate depends on lifecycle; tests do not claim to emulate GitHub protection |
| 4 | Preserve the direct-edit P46 bypass while unrelated tests pass | REGRESSION | Lifecycle command and each repository boundary remain non-pass on the seeded contradiction |
| 5 | Run local boundary commands and verify external protection only when authorized | LIVE | Run `pre-commit run fettle-work-lifecycle --all-files`, `uv run fettle work validate --json`, `uv run fettle completion validate`, and focused workflow tests; freeze the authenticated host endpoint and required-check evidence fields before any `gh api` query, or report branch/release protection `UNKNOWN` |

Exit: local feedback and repository workflow enforcement exist. Protected-merge
or release guarantees are stated only to the extent supported by external evidence.

### WP-WLI-5: Validate Structured Portfolio Projections

Priority: P1. Estimate: 2-4 days. Separate authorization required after lifecycle
enforcement is stable.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing fixtures for structured plan, TODO, and index references with delivery conflicts | TDD | Focused tests fail before projection validation exists |
| 2 | Generate simple delivery tables or validate structured ID references only | CODE | Arbitrary prose remains outside machine authority and coverage is explicit |
| 3 | Preserve separately typed delivery, authorization, evidence qualification, graduation, and promotion | INTEGRATION | P48 advisory/non-promoted and P77 open/partial states retain their distinct meanings |
| 4 | Reproduce P46 as open in the item and complete in a structured projection | REGRESSION | Conflict is non-pass and names both source locations |
| 5 | Run the authorized projection validator over the complete repository | LIVE | Command reports zero structured conflicts and an explicit projection coverage inventory |

Exit: machine-governed portfolio projections cannot silently conflict with the
canonical delivery state; no claim is made about arbitrary prose.

### WP-WLI-6: Measure And Decide Transition Commands

Priority: P2. Estimate: 30-day observation plus 1 decision day. Conditional only.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Observe lifecycle defects, direct-edit attempts, false positives, bypasses, and recovery time for 30 days | MEASURE | Retained report separates local detection, CI rejection, merge bypass, and post-merge detection |
| 2 | Run scheduled full-repository lifecycle and completion scans | LIVE | Run `uv run fettle work validate --json` and `uv run fettle completion validate`; report exact counts and preserve unknown hosting evidence as `UNKNOWN` |
| 3 | Decide `NO_GO` or separately plan transition commands only if measured recurrence or concurrency cost justifies them | REVIEW | Decision record names threshold, evidence, alternatives, and authorization boundary |
| 4 | Confirm direct edits remain repository-boundary checked regardless of the command decision | VERIFY | The seeded direct-edit regression remains required and non-pass |

Exit: an explicit no-go or a separately authorized command plan; no lifecycle
service is implied.

## 9. State And Evidence Matrix

WP-WLI-0 must assign exact outcomes for at least:

- v1 and v2 `open` with closure absent, final, blank, malformed, or duplicated;
- legacy `claimed` with and without a live runtime claim;
- v1 and v2 `done` with closure absent or final;
- v2 `done` with complete, incomplete, missing, malformed, stale, wrong-ID, or
  duplicate completion manifests;
- v2 `open` or legacy `claimed` with a same-ID complete manifest;
- standalone historical manifests with no work item;
- reopened items with retained historical prose or manifests;
- final closure of a bounded item whose wider program remains active;
- exact duplicate IDs, malformed duplicates, aliases, supersession chains, missing
  targets, and cycles;
- unknown fields, wrong types, blank values, case variants, and duplicate YAML keys.

## 10. Blast Radius

Primary expected implementation:

- `fettle/work_items.py`
- `fettle/cli.py`
- `tests/test_work_items.py`
- bounded work-item fixtures

Conditional consumers identified by review:

- `fettle/completion.py` and `fettle/completion_gate.py`
- `fettle/providers/work_item_provider.py`
- `fettle/semantic.py`
- `fettle/graph_shadow.py`
- `fettle/topology.py` and `fettle/topology_apply.py`
- focused completion, provider, semantic, graph, and topology tests

Boundary and migration surfaces:

- `.pre-commit-config.yaml`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- workflow contract tests
- adjudicated `docs/backlog/*.md` records
- structured references in `docs/plan-index.md` and `docs/engagement/TODO.md`

No Assurance policy, Fettle Review runtime, hosted service, database, or universal
historical evidence retrofit is in scope.

Before implementation, refresh `kgraph index`, run `kgraph impact` for every
production and workflow owner, and inspect all direct consumers. The planning
impact query was refreshed before this document was persisted.

## 11. Success And Stop Conditions

Success requires:

- historical P46 remains a permanent failing regression fixture;
- the full state/evidence matrix has deterministic outcomes;
- the migrated corpus passes without suppressions;
- existing v2 completion authority and legacy readability remain intact;
- invalid records cannot silently become usable authority in any reviewed consumer;
- blocking CI and release preflight explicitly invoke lifecycle and completion;
- human and JSON findings agree and identify exact conflict locations;
- external merge/release protection claims are evidence-bound.

Stop or narrow if the design requires natural-language interpretation, duplicates
criterion evidence decisions, fabricates legacy evidence, needs a database, or
cannot distinguish bounded delivery from authorization and graduation.

## 12. Prioritized Program Sequence

1. P0: finish or stabilize current authorized audit hardening and mutation
   qualification; do not overlap WLI implementation in its dirty worktree.
2. P0: approve this planning package, then authorize WP-WLI-0 and WP-WLI-1 only
   if desired.
3. P0: separately authorize WP-WLI-2, then execute WP-WLI-3 and WP-WLI-4 in
   order after their prerequisites pass.
4. P1: consider WP-WLI-5 separately after lifecycle enforcement is stable. P57
   remains independently gated and is not automatically scheduled.
5. P2: run WP-WLI-6 measurement. P34 passively accumulates qualifying runs; P43
   remains parked pending demand.
6. P3: Fettle Review WP-FR-1, Add-in Assurance, and Evidence-Guided Handoffs
   remain decision-blocked and cannot displace P0 trust repair.
7. Parked: P49-P51 await a viable P48 consumer redesign and separate authorization;
   standalone ATIF inspection remains `NO_GO`.

## 13. Planning Compliance And Authorization

- Phase 0 UX/JTBD, journeys, states, accessibility, and BDD: complete in the
  linked UX contract.
- Phase 0.5 visual UI: not applicable; proposed behavior is terminal/JSON only.
- Phase 1 assumptions, tradeoffs, blast radius, work packages, estimates, and
  success/stop conditions: complete.
- Phase 3.5 UAT scenarios: specified before code in the UX contract.
- Feature/program index: recorded in `docs/plan-index.md`.
- Every implementation package contains TDD, integration, named regression, and
  exact-command live verification.
- This document authorizes planning records only. Every work package requires an
  explicit operator decision before execution.
