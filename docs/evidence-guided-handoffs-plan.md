# Evidence-Guided Handoff Pilot Plan

Status: proposed research program; planning artifacts complete; implementation,
pilot execution, roadmap promotion, and enforcement are not authorized

UX and UAT contract:
[evidence-guided-handoffs.ux-spec.md](evidence-guided-handoffs.ux-spec.md)

Research state:
[hypothesis-tree-evidence-guided-handoffs.md](hypothesis-tree-evidence-guided-handoffs.md)

Research basis: *Harness-of-Harness: Multi-Day Autonomous Software Development
with Continual Improvement*, arXiv:2609.01481v1, especially Sections 3.3-3.4,
4.3, 5.2, and Appendices A.1-A.2 and B.6.

## Objective

Determine whether thin, harness-neutral validation of candidate-bound handoffs
and preservation obligations improves Fettle-governed agent work enough to
justify a product capability. Fettle must not schedule planner, developer, or QA
roles, prescribe model reasoning, or become the owner of an autonomous loop.

## User Story And Flow

As a maintainer delegating a change across agent roles, I want each handoff to
state the exact candidate, bounded objective, behavior to preserve, and evidence
needed for acceptance, so the next role can continue from verified state without
trusting prose completion claims.

```text
existing host creates plan -> Fettle validates planning handoff
    -> existing host implements -> candidate identity freezes
    -> existing QA/CI workflow produces candidate-bound evidence
    -> Fettle validates acceptance and preservation obligations
    -> existing host or human chooses the next action
```

## Assumptions

1. Assurance Integrity CS-6 remains the only authorized feature program until it
   graduates; this pilot cannot begin before 20 accepted real assessments and
   explicit operator approval.
2. The canonical evidence kernel remains the sole content and occurrence identity
   vocabulary; the pilot may reference it but cannot define a competing envelope.
3. Existing agent hosts own invocation, context construction, retries, and model
   selection. Fettle validates materialized inputs and outcomes only.
4. Existing role enforcement proves application-level file authority, not an OS
   sandbox or perfect read-only containment.
5. The paper supplies a credible directional hypothesis, not local product proof:
   each task-condition had one valid generation, model inference was unseeded,
   the ablation used one benchmark and harness-model pair, and the 70-loop result
   was one game case study.
6. Cost per verified software change, regression escape rate, and completion
   quality matter more than token count alone.

## Evidence From The Paper

- At three passes on GameCraft-Bench, full HoH scored 71.52 versus 58.24 for
  Vanilla Continuation, using 8.41M versus 6.33M mean tokens per task.
- HoH at two passes scored 64.84 with 5.67M tokens, above three-pass Vanilla
  Continuation at 58.24 with 6.33M tokens.
- Removing plan updates reduced the full score by 8.13 points; withholding QA
  evidence from replanning reduced it by 6.28; rebuilding instead of warm-starting
  reduced it by 7.85 and increased tokens from 8.41M to 11.12M.
- In the 70-loop case, 17 issues reopened after earlier closure. Preservation is
  therefore a tracked obligation, not an assumption that progress is monotonic.

These findings motivate the pilot. They do not establish that Fettle should own
the paper's orchestration architecture.

## Alternatives And Decision

| Approach | Benefit | Cost or risk | Decision |
|---|---|---|---|
| Build a fixed planner-developer-QA runtime | Closest reproduction of HoH | Violates Fettle's product boundary, duplicates host capabilities, creates scheduler and retry ownership | Reject |
| Add prompt templates or guidance only | Minimal implementation | Advisory prose cannot prove candidate identity, role authority, or evidence applicability | Retain as optional host guidance, not the experiment |
| Validate materialized handoffs and candidate-bound obligations | Reuses existing evidence, role, plan, completion, and assurance contracts while remaining host-neutral | Requires a carefully bounded schema and matched pilot | Adopt for the proposed pilot |
| Add a persistent project-memory database | Fast historical retrieval | Introduces staleness, migration, and bootstrap authority risks without measured need | Reject; repository artifacts and progressive disclosure first |

## Proposed Contract Boundary

One handoff is a small, canonical document with:

- schema version and handoff kind (`plan`, `candidate`, or `verification`);
- producer role and occurrence identity;
- input candidate source, policy, and scope bindings;
- one bounded objective and excluded unrelated work;
- acceptance criteria with stable IDs and observable outcomes;
- preservation obligations referencing previously accepted evidence;
- unresolved gaps and parent evidence references;
- output candidate binding for candidate and verification handoffs.

The artifact contains no prompts, chain-of-thought, copied source bodies, generic
confidence score, model-selected authority, or agent scheduling instruction.

## Experimental Design

### Primary Hypothesis

For repository changes that require at least two independent agent roles, adding
validated handoffs and preservation obligations will reduce regression escapes
or increase independently verified completion without unacceptable operational
cost compared with the same supported host workflow under current Fettle policy.

### Unit And Sample

- Unit: one real, reviewable change completed in a dedicated worktree.
- Eligibility: a bounded requirement, at least one observable acceptance
  criterion, at least one preservation obligation, and two-role execution.
- Exclusions: synthetic fixtures, repeated unchanged runs, documentation-only
  edits, infrastructure/provider failures, and changes lacking reconstructable
  source or evidence.
- Minimum pilot: 20 accepted matched pairs across at least two supported hosts and
  two task classes. The treatment and control ordering is alternated according to
  a committed schedule; pairs use equivalent starting revisions and requirements.
- Human reviewers remain blinded to condition labels while scoring completion and
  regression outcomes where repository evidence permits.

The minimum is an operational admission gate, not a statistical power claim. The
final report must include uncertainty intervals and may conclude that more data
is required.

### Measures

Primary:

- regression escape rate: required preserved behaviors failing independent
  verification without being identified before completion;
- verified completion rate: all required acceptance and preservation criteria
  supported by valid candidate-bound evidence.

Secondary:

- false acceptance count and mixed-candidate evidence count;
- agent invocations, elapsed time, provider-reported tokens, and estimated cost;
- operator interventions and time to repair an invalid handoff;
- invalid, stale, malformed, and indeterminate handoff rates;
- cost per verified change.

### Provisional Admission Thresholds

The pilot may be recommended for a broader advisory trial only if:

1. treatment has zero candidate-binding false accepts;
2. treatment has no higher observed regression escape rate than control;
3. treatment improves verified completion by at least 10 percentage points or
   reduces regression escapes by at least 25% relative, with the direction also
   supported by a paired uncertainty analysis;
4. median wall-clock overhead is at most 20% and p95 handoff validation itself is
   at most one second, excluding existing evidence producers;
5. median provider-token overhead is at most 25%;
6. at least 90% of invalid handoffs provide a recovery action that succeeds on
   the next attempt; and
7. no existing Fettle authority decision changes when the pilot is disabled.

Failure of any integrity threshold rejects enforcement. Missing statistical or
cost evidence yields `INCONCLUSIVE`, not adoption.

## Work Packages

All packages below require separate authorization after CS-6. Completing this
plan does not authorize any package.

### WP-EH-0: Freeze Contract And Corpus

Files: this plan, `docs/evidence-guided-handoffs.ux-spec.md`,
`docs/hypothesis-tree-evidence-guided-handoffs.md`, future
`docs/evidence-guided-handoff-contract.md`, and future
`tests/fixtures/handoffs/`.

- Freeze canonical fields, size limits, unknown-field behavior, compatibility,
  and validity outcomes.
- Write adversarial fixtures for stale candidate, wrong policy/scope, duplicate
  criterion IDs, contradictory preservation outcomes, path escape, secret
  leakage, oversized payload, and mixed candidate evidence.
- Freeze the matched-pair schedule, eligibility rubric, scoring rubric, and
  treatment/control isolation before collecting outcomes.

Verification: contract review, fixture parser checks, `fettle completion
validate`, and confirmation that no runtime behavior changed.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add the canonical field and validity matrix to `docs/evidence-guided-handoff-contract.md` | SPECIFY | Review every field against `docs/evidence-artifact-contract.md`; no second evidence identity exists |
| 2 | Add one JSON file per hostile case under `tests/fixtures/handoffs/` | REVIEW | List fixtures and match each to the threat list in this package |
| 3 | Add the frozen pair schedule and scoring rubric to `docs/engagement/evidence-guided-handoff-protocol.md` | SPECIFY | Two reviewers can assign eligibility and outcomes without condition-specific judgment |
| 4 | Validate all planning documents without runtime edits | VERIFY | Run `uv run python -m fettle.plan_validator docs/evidence-guided-handoffs-plan.md` and `uv run fettle completion validate` |

Estimate: 2-3 days.

### WP-EH-1: Implement Read-Only Validation

Files: future `fettle/handoff.py`, `fettle/cli.py`, `fettle/evidence.py`,
`tests/test_handoff.py`, and `tests/test_cli.py`.

- Parse and validate one handoff without executing agents or evidence producers.
- Reuse canonical source, policy, scope, producer, and occurrence validation.
- Emit one result object for human and JSON rendering with exit 0 for valid, 1
  for stale/non-authoritative, and 2 for malformed or unsafe input.
- Keep the command opt-in and advisory; no existing gate consumes it.

Verification: contract, adversarial, cross-process determinism, installed-wheel,
and human/JSON parity tests.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add a failing minimal valid-handoff parser test to `tests/test_handoff.py` | TDD | Run `uv run pytest tests/test_handoff.py -q`; retain the intended pre-implementation failure |
| 2 | Add immutable handoff parsing and validation to `fettle/handoff.py` | CODE | Rerun the focused parser test to green |
| 3 | Wire `handoff validate` in `fettle/cli.py` using the same result for human and JSON output | INTEGRATION | Run focused handoff and `tests/test_cli.py` cases |
| 4 | Add the named stale-candidate and path-escape cases from the frozen corpus | REGRESSION | Run `uv run pytest tests/test_handoff.py -q`; both incidents remain non-pass with no command execution |
| 5 | Validate a handoff through a rebuilt installed wheel in a temporary repository | LIVE | Run the documented `fettle handoff validate <path>` command and observe matching source-tree and wheel decisions |

Estimate: 3-5 days.

### WP-EH-2: Bind Preservation Outcomes

Files: future `fettle/handoff.py`, `fettle/completion.py`, producer adapters only
where an existing public validator is reusable, and focused tests.

- Resolve acceptance and preservation IDs only through valid canonical evidence.
- Represent `VERIFIED`, `FAILED`, `REGRESSED`, and `UNVERIFIED` independently
  from plan prose.
- Reject observations collected across different candidate identities.
- Keep completion and Assurance authority unchanged during the pilot.

Verification: regression reopening, missing evidence, conflicting occurrence,
candidate drift, and disabled-pilot compatibility tests.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing obligation-state tests to `tests/test_handoff.py` | TDD | Run the focused tests and retain failures for `REGRESSED` and `UNVERIFIED` |
| 2 | Resolve obligation evidence through public validators in `fettle/handoff.py` | CODE | Focused tests prove no raw report or prose claim establishes an outcome |
| 3 | Add advisory handoff inspection to `fettle/completion.py` without changing completion authority | INTEGRATION | Run `tests/test_handoff.py` and `tests/test_completion.py` together |
| 4 | Add the named mixed-candidate regression where two valid observations refer to different snapshots | REGRESSION | Focused test rejects the combined acceptance and identifies both candidate bindings |
| 5 | Run a temporary-repository candidate-drift flow from valid to stale | LIVE | Execute capture, edit one source file, rerun validation, and observe `STALE` without an accepted completion change |

Estimate: 3-5 days.

### WP-EH-3: Add Progressive Disclosure And Host Guidance

Files: future host-neutral Markdown guidance, supported host bridge resources,
`fettle/cli.py`, and parity tests.

- Provide concise indexes of current objective, gaps, and preservation obligations
  with detailed evidence loaded on demand.
- Offer role-specific guidance without granting tools or scheduling roles.
- Verify all supported host renderings preserve the same public contract and do
  not weaken inherited policy.

Verification: bridge parity, bounded-output, secret-redaction, and first-time CLI
UAT. No host guidance may be required for handoff validation correctness.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing bounded-index and redaction tests to the relevant host bridge test files | TDD | Run only the bridge tests and retain the intended failures |
| 2 | Add host-neutral guidance as one package resource and reference it from each supported bridge | CODE | Package-resource tests prove one source is rendered for every host |
| 3 | Pass validated objective, gap, and preservation summaries through existing bridge adapters | INTEGRATION | Host parity tests compare normalized public content and policy posture |
| 4 | Add the named secret-in-parent-evidence and oversized-index regressions | REGRESSION | Bridge tests reject leakage and truncate only at declared safe boundaries |
| 5 | Initialize a temporary repository for each supported installed host bridge | LIVE | Run documented init and validation commands; observe concise first-time guidance with no scheduling action |

Estimate: 2-4 days.

### WP-EH-4: Run Matched Advisory Pilot

Files: future append-only register under `docs/engagement/`, external retained
bundles, and `docs/uat/evidence-guided-handoffs-pilot.md`.

- Execute the frozen treatment/control schedule on eligible real changes.
- Retain exact starting state, requirement, host/model configuration, role
  lineage, candidate identities, evidence, outcomes, tokens, time, and exclusions.
- Classify protocol deviations before unblinding outcomes; never replace a failed
  product result, only invalid infrastructure attempts under frozen rules.
- Generate the report from retained records rather than hand-entered totals.

Verification: 20 accepted matched pairs, reproducible aggregates, discrepancy
ledger, uncertainty analysis, and independent review.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add protocol-conformance tests for one control and one treatment bundle | TDD | Run the future pilot-report tests and retain rejection of incomplete pairs |
| 2 | Implement deterministic aggregation over external bundle references | CODE | Unit tests reproduce counts, paired deltas, exclusions, and uncertainty inputs |
| 3 | Bind register rows to source, requirement, host/model, roles, outcomes, and bundle digest | INTEGRATION | A reconstructed pair produces byte-identical normalized inputs and totals |
| 4 | Add the named condition-leakage and unreconstructable-pair regressions | REGRESSION | The report excludes both rows before outcomes are unblinded |
| 5 | Execute the frozen protocol on 20 accepted real matched pairs | LIVE | Run the documented report command; generated totals reconcile exactly with retained bundles |

Estimate: collection time plus 2-3 days of analysis; calendar duration cannot be
compressed with synthetic repetition.

### WP-EH-5: Decide, Do Not Drift

Files: this plan, `docs/plan-index.md`, `docs/ROADMAP.md`, and an explicit operator
decision record.

- `ADOPT_ADVISORY`: thresholds pass; authorize a separately planned advisory
  integration and compatibility window.
- `ITERATE`: integrity holds but operational or statistical evidence is
  inconclusive; change one falsifiable hypothesis and rerun a new frozen pilot.
- `REJECT`: quality, integrity, or cost thresholds fail; retain findings and do
  not ship the feature.

No result automatically enables enforcement or creates an orchestration runtime.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Generate the threshold decision from the retained WP-EH-4 report | INSPECT | A reviewer independently recomputes every threshold outcome |
| 2 | Record exactly one `ADOPT_ADVISORY`, `ITERATE`, or `REJECT` decision with rationale | REVIEW | Decision cites retained evidence and contains no automatic enforcement change |
| 3 | Update `docs/plan-index.md` and `docs/ROADMAP.md` to the reviewed decision only | VERIFY | Diff matches the signed decision and preserves orchestration non-goals |

Estimate: 1 day.

## Task Decomposition Contract

The package tables are ordered implementation slices, not authorization. When a
package is authorized and claimed, split each row further as needed so one edit
or one verification is performed at a time and the repository returns green
before proceeding. The final task of every runtime package also runs the full
suite, Ruff, config validation, completion validation, changed-file checks,
build, and installed-wheel UAT.

## Blast Radius

- `fettle/evidence.py`: canonical identity and applicability semantics must not
  fork or weaken.
- `fettle/completion.py`: pilot obligations must not silently become completion
  authority.
- `fettle/authorship_gate.py`, `fettle/spawn.py`, and host bridges: role guidance
  must not overstate isolation or weaken policy inheritance.
- `fettle/cli.py`: proposed command must preserve current command and exit-code
  behavior.
- `.fettle/` artifacts: atomic writes, path safety, portability, bounded size,
  and stale-result invalidation are required.
- CI/UAT/mutation/security producers: remain owners of their observations and
  stronger domain contracts.

Before any runtime package, refresh `kgraph index` and run `kgraph impact` on
every named production file. The current documentation-only impact query is
best-effort and stale.

## Security And Privacy

- Treat handoffs and parent references as untrusted input.
- Reject path traversal, symlink escape, duplicate IDs, digest substitution,
  oversized structures, unsupported schemas, and mixed candidate identities.
- Retain no prompts, hidden reasoning, source bodies, secrets, environment
  values, or absolute checkout paths in portable artifacts.
- Never execute commands from a handoff document.
- Validation grants no OS sandbox and no model authority.

## Non-Goals

- Planner, developer, tester, retry, queue, or budget orchestration.
- A fixed three-role topology for every change.
- Autonomous rollback, merge, release, or policy mutation.
- Persistent semantic memory or a hosted control plane.
- Replacing existing plans, work items, completion manifests, CI, UAT, or the
  Assurance Record.
- Claiming local effectiveness from HoH's published benchmark alone.

## Authorization And Stop Conditions

- Stop before WP-EH-0 implementation while CS-6 is incomplete or separate operator
  authorization is absent.
- Stop the pilot on any candidate-binding false accept, evidence leakage,
  authority change while disabled, or inability to reconstruct a matched pair.
- Keep all behavior advisory until WP-EH-5 records an explicit human decision.
