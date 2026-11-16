# Fettle Review Implementation And Evaluation Plan

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/review.md).

Status: PROPOSED; documentation is approved for planning only; no runtime, CLI,
test, fixture, configuration, policy, HTML, or Assurance implementation is
authorized without a separate explicit operator decision

UX contract: [fettle-review.ux-spec.md](fettle-review.ux-spec.md)

UI contract: [fettle-review.ui-spec.md](fettle-review.ui-spec.md)

Research state: [hypothesis-tree-fettle-review.md](hypothesis-tree-fettle-review.md)

## 1. Objective

Determine whether a read-only, change-centered assurance case can let a
non-engineer understand intended behavior, implemented logic, supporting
evidence, material risks, and unknowns without creating a second quality
authority or trusting fluent AI prose.

The product sequence is:

```text
plain-English intent approved by user
    -> exact candidate and changed scope
    -> existing Fettle evidence and policy decision
    -> deterministic claim-to-evidence projection
    -> optional advisory code/logic explanation
    -> terminal, JSON, and local HTML views
    -> human chooses a named recovery action
```

## 2. User Story

As a non-engineer who builds software with coding agents, I want one plain-English
review of a specific change, so I can distinguish verified behavior from failures,
unknowns, and AI interpretation before deciding whether to fix, escalate, or ship.

## 3. Current Baseline

Fettle already provides most evidence inputs. The proposed work is primarily a
consumer and presentation problem:

| Existing capability | Current owner | Proposed use |
|---|---|---|
| Candidate-bound multidimensional decision | `fettle assurance` | Sole overall policy decision; do not recompute it |
| Gate-decision explanation | `fettle explain` | Findings, reasons, evidence, and recovery detail |
| Requirement scenarios and drift | `fettle spec`, `fettle links`, canonical trace | Intent and executed-coverage path |
| Verification, mutation, UAT, CI, security | Existing canonical producers | Dimension evidence after normal validation |
| Change graph and impact | `fettle graph`; advisory status retained | Changed-area and preservation context only |
| Operational summary | `fettle brief`, `fettle report` | Supporting context, not release authority |
| Durable governance history | `fettle ledger` | Tamper-evident decision provenance |
| Completion | `fettle completion` | Criterion status; never inferred from activity |

Known gap: these surfaces are optimized for engineers and automation. A user must
run multiple commands and understand evidence semantics to answer one practical
question: "What is safe, unsafe, or still unknown about this change?"

## 4. Assumptions

1. The initial user is comfortable opening a local HTML file or reading terminal
   output but is not expected to read code.
2. Existing Fettle public functions or their JSON projections remain the source
   of facts; scraping rendered terminal text is not acceptable.
3. The Assurance Record remains the only aggregate policy authority.
4. Generated code explanations are useful but fallible, must cite exact source,
   and remain advisory.
5. A report may explain only the evidence available for one immutable candidate;
   it cannot establish universal correctness or absence of defects.
6. Offline, local, zero-core-runtime-dependency behavior remains the default.
7. No raw prompts, hidden reasoning, secrets, or unrestricted source excerpts are
   required to meet the job.

## 5. Decisions And Tradeoffs

| Approach | Benefit | Cost or risk | Decision |
|---|---|---|---|
| Improve each existing CLI independently | Small changes | User must correlate many commands and identities | Retain as fallback; insufficient primary flow |
| Add one deterministic review model and three renderers | One coherent answer with machine parity | Requires careful ownership and status mapping | Selected for experiment |
| Build a hosted dashboard | Rich navigation and collaboration | Privacy, auth, storage, freshness, and operational burden | Reject |
| Generate self-contained local HTML | Visual and shareable without a service | Accessibility and stale-file handling must be explicit | Selected for prototype |
| Let an LLM decide readiness | Natural language feels accessible | Nondeterministic false assurance | Reject |
| Let an LLM explain code under a deterministic envelope | Useful logic translation with explicit limits | Explanation may be incomplete or wrong | Conditional, advisory-only package |
| Add a single quality score | Easy to scan | Masks critical failures and unknowns | Reject |
| Import agent trajectories | Explains process history | Does not prove product behavior; privacy-heavy | Reject; see deferred trajectory record |

## 6. Authority Contract

- `fettle review` would be an evidence consumer and renderer, not a producer of
  verification facts.
- It must call existing validators and preserve their result states, applicability,
  candidate bindings, and reasons.
- Presentation aliases never alter underlying states. The JSON result retains the
  canonical value beside any user-language label.
- The overall disposition comes from the selected existing Assurance policy. If
  no valid Assurance decision exists, the review is `UNKNOWN`, not independently
  ready.
- `ADVISORY INTERPRETATION` content cannot satisfy completion criteria, resolve a
  contradiction, establish coverage, or alter exit status.
- Generated HTML is a disposable projection. Its existence, filename, or age is
  not evidence.

## 7. Review Contract

The eventual immutable in-memory review result should contain:

- schema version and renderer version;
- exact source candidate and changed scope;
- selected policy and unmodified Assurance disposition;
- ordered reasons, unknowns, and recovery actions;
- every required review dimension and its canonical status;
- claim nodes and typed links to scenarios, code locations, tests, observations,
  and decisions;
- evidence references and validation summaries, never unbounded raw payloads;
- explicitly separate observed, derived, and advisory statements;
- generation occurrence and stale-applicability result.

The contract must define deterministic ordering and size bounds before code. It
must also distinguish `not applicable with reason` from absent evidence.

## 8. Work Packages

Each package after WP-FR-0 requires separate operator authorization. Authorization
of one package does not authorize later packages.

### WP-FR-0: Freeze Research And Product Contracts

Files: this plan, linked UX/UI specifications, hypothesis tree,
`docs/plan-index.md`, `docs/ROADMAP.md`, and the planning-status corrections made
with this review.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Inventory existing public facts, owners, status vocabularies, and candidate bindings | AUDIT | Review `behavior-map.md`, Assurance, explain, brief, report, spec, graph, UAT, mutation, completion, and ledger contracts |
| 2 | Freeze the user journey, dimensions, statement classes, and no-score rule | SPECIFY | Two reviewers classify every UX scenario without implementation assumptions |
| 3 | Record the visual hierarchy, accessibility contract, and local-only boundary | SPECIFY | UI checklist covers mobile, keyboard, screen reader, print, stale, loading, empty, and error states |
| 4 | Reconcile roadmap dependencies and preserve explicit implementation authorization | REVIEW | Documentation grep finds no known P41, P49, or CS-6 contradiction in active planning records |
| 5 | Validate all planning artifacts without runtime edits | VERIFY | Run plan validator, doc claims, link checks, completion validation, and changed-file Fettle scan |

Exit: planning is complete and the operator chooses whether WP-FR-1 may run. No
prototype, fixture corpus, or Fettle behavior exists yet.

Estimate: 1 day. Status: documentation work in progress; implementation blocked.

### WP-FR-1: Baseline Comprehension Study

Possible files after authorization: `docs/engagement/fettle-review-baseline.md`,
sanitized evaluation cases under `evals/`, and evaluation-only scripts if needed.
No production code.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Freeze five or more eligible changes and seeded truth labels | SPECIFY | Independent engineer and evidence reviewer agree on candidate, blockers, unknowns, and expected next action |
| 2 | Define participant script and scoring before sessions | REVIEW | Rubric measures classification, false-ready decisions, time, comprehension, and recovery success |
| 3 | Measure current CLI workflow without coaching | LIVE | At least ten blinded sessions retain timings and answers without storing secrets or code content |
| 4 | Decide whether presentation is the limiting factor | VERIFY | Proceed only if evidence exists but target users fail to integrate it reliably |

Exit: a retained baseline demonstrates a product need. If existing CLI output
already meets thresholds, stop and improve documentation rather than build.

Estimate: 2-4 days plus participant scheduling.

### WP-FR-2: Freeze The Deterministic Review Schema And Fixtures

Possible files after authorization: `docs/fettle-review-contract.md` and
`tests/fixtures/review/`; no production code.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add a failing schema test for the smallest valid candidate-bound review | TDD | Run the future focused contract test and retain the intended missing-schema failure |
| 2 | Freeze fields, enums, ordering, bounds, applicability, and statement classes | INTEGRATION | Map every field to one existing owner or mark it advisory; no duplicated authority remains |
| 3 | Add hostile fixtures for stale, malformed, missing, contradictory, mixed-candidate, unsupported, and not-applicable-without-reason inputs | REGRESSION | Named false-ready fixture remains non-ready and exposes its exact contradiction |
| 4 | Walk all fixtures through the paper/fixture renderer with target users | LIVE | Run the authorized `uv run python evals/fettle_review_study.py --corpus tests/fixtures/review --mode paper`; every participant classifies every fixture without reading code and the report records zero false-ready decisions |

Exit: two independent reviewers produce the same expected review result for every
fixture. No runtime parser or renderer is authorized by schema approval.

Estimate: 2-3 days.

### WP-FR-3: Build The Read-Only Review Composer And Terminal/JSON Views

Possible files after authorization: future `fettle/review.py`, `fettle/cli.py`,
`docs/behavior-map.md`, `tests/test_review.py`, and focused CLI tests.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing tests for canonical status preservation and candidate identity | TDD | Focused tests fail before implementation for valid, missing, stale, and contradictory cases |
| 2 | Compose one immutable bounded result from existing validated public data | CODE | Unit tests prove no renderer, AI text, or optional input can alter Assurance or dimension states |
| 3 | Wire human and JSON output from the same result | INTEGRATION | CLI parity tests compare dispositions, reasons, unknowns, evidence IDs, and action ordering |
| 4 | Preserve the prior false-ready incident class when one passing source conflicts with required evidence | REGRESSION | Contradictory fixture is `UNKNOWN` or `FAILED`, never averaged or omitted |
| 5 | Run the source-tree and rebuilt-wheel command on clean and incomplete sample repositories | LIVE | `fettle review` remains read-only and outputs the same candidate-bound decision in both installations |

Exit: terminal and JSON answer the primary question using existing evidence only.
No HTML or model integration is included.

Estimate: 4-7 days.

### WP-FR-4: Add The Accessible Local HTML Projection

Possible files after authorization: renderer module or templates selected after
impact analysis, package-data declarations, and focused accessibility fixtures.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing golden/semantic tests for summary, dimensions, claim paths, and stale state | TDD | Focused renderer tests fail before HTML implementation |
| 2 | Render self-contained semantic HTML from the same review result | CODE | No network asset, script requirement, raw evidence payload, or independent status calculation exists |
| 3 | Add CLI generation and atomic stale-output handling | INTEGRATION | Failed generation cannot leave an older report represented as current |
| 4 | Preserve the stale-ready and color-only failure scenarios | REGRESSION | Stale candidate displays `STALE`; grayscale and text extraction retain every status and action |
| 5 | Exercise all UX states, including missing-data `UNKNOWN`, at 320px, 768px, 1440px, 200% zoom, keyboard-only, screen reader, print, and axe | LIVE | Run the authorized `uv run pytest tests/test_review_html.py -m live -q`; output is green, the missing-data fixture is visibly `UNKNOWN`, axe has zero serious/critical findings, and no task requires a mouse, color, network, or source-code reading |

Exit: HTML, terminal, and JSON have exact decision parity and the user can reach
evidence for any conclusion within three interactions.

Estimate: 4-7 days.

### WP-FR-5: Evaluate Optional Advisory Logic Explanation

Possible files after authorization depend on the selected existing model adapter.
This package must not be combined with WP-FR-3 or WP-FR-4.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing tests that advisory prose cannot alter facts, statuses, actions, or exit code | TDD | Focused authority-boundary tests fail before integration |
| 2 | Add one bounded optional explanation input/output contract with source citations | CODE | Missing model, malformed output, unsupported language, and uncited claims remain absent or explicitly unknown |
| 3 | Render advisory prose and deterministic evidence in separate typed sections | INTEGRATION | Human/JSON/HTML parity retains `ADVISORY INTERPRETATION` and exact source references |
| 4 | Preserve the plausible-but-wrong explanation incident class | REGRESSION | Seeded wrong branch explanation is rejected or visibly unsupported and cannot change readiness |
| 5 | Compare blinded comprehension with and without explanations | LIVE | Run the authorized `uv run python evals/fettle_review_study.py --compare explanations`; retain only when its report shows improved comprehension, zero increase in false-ready decisions, and zero material privacy leakage |

Exit: choose `omit`, `revise`, or `retain optional`. No model becomes required for
the deterministic review.

Estimate: 3-6 days plus evaluation.

### WP-FR-6: Held-Out User Evaluation And Product Decision

Possible files after authorization: retained protocol/results under
`docs/engagement/` and planning status updates. Production changes are limited to
fixes required by an already authorized preceding package.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add automated contract coverage for all accepted result and renderer behavior | TDD | Focused tests cover every status, statement class, dimension, and stale transition |
| 2 | Verify installed behavior against independently frozen candidate fixtures | INTEGRATION | Source-tree and wheel outputs match and existing Assurance outputs remain unchanged |
| 3 | Re-run every named false-ready, stale, contradiction, and advisory-authority case | REGRESSION | Zero false-ready results and no previously fixed incident recurs |
| 4 | Run at least ten blinded target-user sessions on held-out changes including a missing-data case | LIVE | Run the authorized `uv run python evals/fettle_review_study.py --split held-out`; report at least 90% correct classification, zero false-ready decisions, median under five minutes, at least 90% successful first-action identification, and `UNKNOWN` for missing data |

Exit: operator chooses `remove`, `revise`, `retain experimental`, or propose a
separately authorized product release. Passing tests alone do not graduate it.

Estimate: 3-5 days plus participant scheduling.

## 9. Test And Evidence Matrix

| Concern | Required evidence |
|---|---|
| Authority preservation | Existing Assurance result and exit behavior unchanged with review absent, present, malformed, or model-disabled |
| Candidate identity | Source drift makes prior review stale; mixed-candidate evidence remains non-pass |
| Completeness | Every required dimension is present as verified, failed, unknown, or justified not applicable |
| Contradiction | Conflicting applicable evidence is visible and never averaged |
| Explanation safety | Advisory text cannot satisfy claims or modify deterministic fields |
| Privacy | No prompts, hidden reasoning, secrets, absolute paths, or unbounded source enter output |
| Accessibility | Keyboard, screen reader, contrast, zoom, responsive, print, and axe evidence |
| Installation | Source tree and rebuilt wheel produce equivalent results |
| Human comprehension | Blinded classification, false-ready, timing, and recovery metrics |

## 10. Blast Radius

- `fettle/assurance.py`: consume its public result; do not fork policy evaluation.
- `fettle/evidence.py`: use canonical validation; do not change frozen identity or
  trust semantics for presentation convenience.
- `fettle/explain.py`, `fettle/report.py`, and `fettle/brief.py`: reuse concepts or
  shared structured inputs only after impact review; preserve existing output.
- Specification and traceability modules: expose declared and executed links
  without converting declaration into verification.
- Graph output: advisory context only until each consumer's graduation contract
  says otherwise.
- `fettle/cli.py` and `docs/behavior-map.md`: touched only after WP-FR-3 approval.
- Packaging: local HTML templates/assets must work from a rebuilt wheel and cannot
  fetch third-party content.
- Security/privacy: generated reports may be shared, so minimize repository and
  source detail and never embed secrets or raw model interaction content.

Before any runtime package, refresh `kgraph index`, run `kgraph impact` on every
proposed production file, and review the owning public contracts.

## 11. Success And Stop Conditions

Success requires all of the following:

- zero false-ready decisions in contract, adversarial, and held-out user tests;
- at least 90% correct target-user classification;
- median identification of disposition, top risk, and first action under five
  minutes;
- exact terminal/JSON/HTML decision parity;
- every conclusion has provenance and every advisory statement is distinguishable;
- no new authority, scanner, database, hosted service, or mandatory model;
- existing Fettle behavior remains unchanged when review is not invoked.

Stop or narrow the program if existing CLI improvements meet the target, the
report cannot avoid duplicating Assurance logic, source minimization makes the
logic explanation useless, accessibility cannot be met without a larger runtime,
or any presentation variant causes a false-ready decision.

## 12. Authorization And Rollback

- This document authorizes planning records only.
- WP-FR-1 and every later package require explicit operator authorization.
- No runtime code, tests, fixtures, CLI, configuration, generated UI, policy,
  Assurance, completion, hook, or gate changes are authorized now.
- Every implementation package must remain independently revertible.
- Removing review output must not remove or mutate source evidence.
- Any future enforcement proposal requires a separate plan and measured graduation;
  this plan permits explanation and evaluation only.

Planning gate status:

- Phase -1 hypothesis tree: complete.
- Phase 0 UX and BDD contract: complete.
- Phase 0.5 UI contract: complete.
- Phase 1 assumptions, tradeoffs, blast radius, work packages, estimates, and
  success/stop conditions: complete.
- Phase 3.5 UAT scenarios: specified before code in the UX contract and WP-FR-6.
- Feature manifest: recorded in `docs/plan-index.md` as proposed and unauthorized.
