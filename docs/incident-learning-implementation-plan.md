# Incident Learning And Improvement Roster Implementation Plan

> Integration precedence — current main’s November 14 sequencing decision and
> trust-remediation ownership govern execution. Earlier scheduling and review
> observations below remain historical. This merge grants no feature approval.

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/incident.md).

Status: PROPOSED IMPLEMENTATION; documentation and high-priority scheduling
authorized on 2026-10-12. No runtime implementation, evidence ingestion, model
call, remote job, commit, push, release, or policy promotion is authorized here.

Priority: P0 learning infrastructure, coordinated with lifecycle trust repair.

UX and BDD: [incident-learning.ux-spec.md](incident-learning.ux-spec.md).
CLI presentation: [incident-learning.ui-spec.md](incident-learning.ui-spec.md).
Scheduling: [engagement/TODO.md](engagement/TODO.md).
Lifecycle authority: [work-item-lifecycle-integrity-plan.md](work-item-lifecycle-integrity-plan.md).

Experience standard: planned [Experience Discipline vNext](experience-discipline-vnext.ux-spec.md).
P0-IL follows its independent harm/scope/autonomy/uncertainty routing, scoped claim
states, derived transitions, nine blocking gates and criterion-level handoff.
This is alignment with the requested future standard, not installation or approval
of the whole discipline program. Rebind to the accepted version at IL-1; do not
make a global skill rollout a prerequisite for preserving incidents.

## 1. User Outcome

As an operator reviewing an AI-agent failure, I want to retain its evidence,
understand what is known about its cause, and connect it to a reviewed improvement
and verification result, so the product learns without repeating expensive
mistakes or claiming prevention it has not demonstrated.

The first useful deliverable is a manually curated, evidence-linked roster using
existing work items. Automation follows demonstrated friction in that flow.
Recording an incident, confirming a cause, delivering a fix, and observing reduced
recurrence are different claims. The roster must keep them distinct.

## 2. Authorization And Sequence

1. This approval covers this planning package and its P0 TODO entry only.
2. Request bounded authorization for WP-IL-0 first: preserve operator-approved
   local incident evidence and create ordinary work-item records. It may run
   alongside hardening only if the operator explicitly approves the source scope
   and non-overlapping documentation workspace. Do not mutate the candidate.
3. Otherwise begin WP-IL-0 at the first post-hardening checkpoint, before optional
   product expansion. Do not wait for logging automation to preserve evidence.
4. Freeze WP-IL-1 with WP-WLI-0/WLI-1. Do not create a second work-item lifecycle
   schema. Runtime packages require hardening acceptance and the approved WLI
   parser/evaluator boundary; closure qualification requires WLI-4 enforcement.
5. WP-IL-2 through WP-IL-4 form one small vertical implementation, delivered in
   ordered, tested slices. Approve that bounded phase, not every routine command.
6. WP-IL-5 is a local advisory pilot; live providers, new hosts, remote downloads,
   mutation campaigns, or independent effectiveness experiments need separate
   scope, spending, and privacy approval.
7. WP-IL-6 requires an explicit delivery/rollout decision. No active global skill,
   rule, policy, or hook changes follow automatically from a lesson.

P0 reflects the value of shortening learning time, not permission to restart
hardening or make this feature a new AH01-AH07 acceptance requirement. Shared
capture/triage contracts cover code and non-code tasks; domain validators remain
specialized. M-NC1 remains the first new domain workflow. The roster is supporting
infrastructure, not authorization for broader research or a second product pilot.

## 3. Local Evidence And Rebinding

Source inspection used local HEAD
`4522a564791bce326ca4f340f7007f09e988b8e1` with pre-existing dirty changes.
It is not a claim about the hardening agent's delivered candidate.

| Existing owner | Observed capability | Limitation relevant to this plan |
|---|---|---|
| [trace.py](../fettle/trace.py) | Bounded decision findings, evidence references, session lineage; JSONL rotation | Instrumented paths only; write/rotation loss possible; not an incident archive |
| [evidence.py](../fettle/evidence.py), [evidence_ledger.py](../fettle/evidence_ledger.py) | Artifact validation and selected governance records | A digest or ledger entry alone does not prove an artifact is available, applicable, or true |
| [evolution.py](../fettle/evolution.py) | Repeated trace findings and ingested CI classes | Repeated messages do not prove a shared cause; scope and time-window semantics need validation |
| [learn.py](../fettle/learn.py) | Quarantined rule proposals and sample evidence | Rule-centric; proposal generation may call a model; not a general postmortem lifecycle |
| [work_items.py](../fettle/work_items.py) | Versioned Markdown items with runtime claims separate | Incident fields are not yet a supported structured contract; WLI changes are pending |
| [report.py](../fettle/report.py) | Read-side summaries from retained traces | A zero count cannot establish zero failures outside observed coverage |

Before implementation, re-read these owners and their tests at the accepted base,
record the actual version/environment, and revise file ownership if it changed.
Hardening-agent reports are leads until their artifacts are independently read and
bound. Do not label reported observations as locally reproduced.

## 4. Design Decisions

| Approach | Benefit | Cost or risk | Decision |
|---|---|---|---|
| Keep only rotating traces | No new flow | Loses context and durable links; poor triage | Insufficient |
| Existing work items plus retained evidence and derived reports | Fits current authority; manual value first | Requires an explicit metadata and retention contract | Selected |
| New incident service, database, scheduler, or dashboard | Centralized automation | Duplicate lifecycle/evidence ownership and operational burden | Out of scope |
| Automatically promote learned fixes | Low review effort | Wrong diagnoses and poisoned evidence can alter policy | Rejected |

Local hypothesis: existing work items and canonical evidence references can
represent a useful roster without a new ledger. Cheap disconfirming check:
manually represent and walk through the seed incidents in WP-IL-0, including an
unavailable artifact and one incident with multiple proposed improvements. If
identities, permissions, or closure become ambiguous, revise WP-IL-1 before code.

## 5. Record And Authority Contract To Freeze

The following are required concepts, not permission to add arbitrary frontmatter
keys now. WP-IL-1 chooses exact types and versioning with WLI.

| Concept | Required information and behavior |
|---|---|
| Occurrence | Stable identity for one event; source producer, repository/workspace binding, task class, host, candidate/environment, run/attempt/session when available, observed and expected outcome, event and ingestion times with unknowns explicit |
| Incident | Stable work-item identity, one or more explicit occurrence links, impact, containment, current diagnosis and confidence, contradictory evidence and superseded diagnoses retained |
| Improvement | Existing work-item identity; explicit incident links, bounded proposed change, owner, priority rationale, approval scope, acceptance criteria and verification references |
| Evidence | Canonical references where supported; retained bytes or explicitly unavailable location, digest, producer/source binding, access/retention decision, redaction version, inspection result |
| Verification | Named pre-fix reproducer, candidate-bound post-fix result, relevant adverse cases, applicable domain validator; no generated summary substitutes for underlying evidence |
| Closure | Existing WLI/completion semantics only; a closed investigation need not mean a fix exists; a completed improvement is not proof of universal prevention |

Use ordinary work-item IDs for incidents and improvements; do not maintain an
independent mutable status database. Occurrence identity and recurrence grouping
are separate: reimporting the same source event adds nothing, but a new attempt
is preserved even with identical text. Similarity suggests a link; a reviewer
confirms cause, merge, split, or supersession. One incident may justify several
improvements; one improvement may address several incidents without duplicate
closure credit. New recurrences retain history and prompt review; they do not
silently rewrite a past completion decision.

Unknown repository identity must not silently join another project's cluster.
Unknown timestamps must not enter a claimed time window. Old records remain
readable as explicitly incomplete; no fabricated migration evidence.

## 6. Capture, Privacy And Failure Boundaries

- Inventory supported producers before claiming automatic capture. Initial scope
  is existing local trace and approved retained CI evidence, plus explicit manual
  non-code records. A crash outside instrumentation remains unknown, not healthy.
- Record capture coverage separately from incident counts: source, enabled state,
  observed interval, read/write errors, truncation, and retention limitations.
- Preserve selected incident evidence outside the rotating diagnostic trace using
  the existing artifact storage/reference mechanism. No unbounded full-transcript
  capture. Freeze byte/count caps, retention duration, access ownership, and an
  explicit archive/export decision in WP-IL-1 before adding storage behavior.
- Redact before persistence and before optional model input; digest the retained
  representation and record the transformation. Never imply redacted bytes hash
  to the original. Retain only necessary context; unknown secret safety blocks
  export/model submission pending review.
- Treat logs, document text, prompts, and model diagnoses as untrusted data. They
  cannot execute commands, alter approval, supply policy, or follow remote links.
- Default roster inspection and deterministic drafting are offline, read-only or
  explicitly local-write operations. Model assistance is optional, separately
  authorized, visibly attributed, and never required for a useful proposal.
- Reject path escape, symlink escape, malformed records, oversized input, foreign
  artifacts, conflicting duplicate identities and hidden prompt instructions.
- Do not implement a transaction service. Use existing locks/atomic-write helpers
  where applicable, preserve partial failure visibly, and test retries for no
  false success or duplicate occurrence. Logging failure must not recursively log
  forever or silently replace the original failure.
- Missing, malformed, stale, skipped, blocked, contradictory, or indeterminate
  verification remains non-pass. A warning count is not completion evidence.

## 7. File Ownership And Blast Radius

| File | Planned responsibility and bounded risk |
|---|---|
| [work_items.py](../fettle/work_items.py) | Parse validated incident/improvement links; preserve legacy reading and WLI delivery/claim split |
| [evolution.py](../fettle/evolution.py) | Deterministic occurrence/group candidates with explicit scope; preserve existing rule-signature compatibility |
| [learn.py](../fettle/learn.py) | Draft a generic improvement work item from retained evidence; keep existing rule proposals and explicit promotion intact |
| [report.py](../fettle/report.py) | Derive a read-only roster with evidence gaps, approvals, and completion results; never mutate or evaluate a second verdict |
| [cli.py](../fettle/cli.py) | Route proposed options through existing work/learn/report families; unambiguous no-write versus write/model behavior |
| [trace.py](../fettle/trace.py) | Only contract-required source/correlation or failure-visibility gaps demonstrated by IL-0/1 |
| [evidence.py](../fettle/evidence.py), [evidence_ledger.py](../fettle/evidence_ledger.py) | Reuse first; edit only for a reviewed missing contract capability, not to duplicate storage |
| [behavior-map.md](behavior-map.md), [CONFIG.md](CONFIG.md), [CAPABILITIES.md](CAPABILITIES.md) | Describe actual delivered ownership, permissions, retention and supported capture, only when implemented |
| [tests/test_work_items.py](../tests/test_work_items.py), [tests/test_evolution.py](../tests/test_evolution.py), [tests/test_learn_proposals.py](../tests/test_learn_proposals.py) | Identity, linkage, legacy compatibility, approval and deterministic proposal tests |
| [tests/test_trace.py](../tests/test_trace.py), [tests/test_trace_canonical.py](../tests/test_trace_canonical.py), [tests/test_evidence_contract.py](../tests/test_evidence_contract.py), [tests/test_evidence_ledger.py](../tests/test_evidence_ledger.py) | Capture limits, canonical references, retention and partial-write failures for touched owners |
| [tests/test_report.py](../tests/test_report.py), [tests/test_cli.py](../tests/test_cli.py) | Actual producer output through parser, report, command routing and completion consumer |

No new shared runtime module is pre-approved. Re-run `kgraph impact` against each
runtime file at the accepted base; a stale index is not proof of no impact.
Inspect current completion consumers before agreeing any schema migration.

### Impact Freshness Preflight

Before a decision that relies on graph impact, run
`kgraph status --repo <checkout> --json` and inspect `index_fresh`, not just the
exit code. Record the checkout, HEAD, working-tree identity, indexed timestamp and
tool version with the decision. File changes can invalidate a previously fresh
result even when HEAD stays the same.

If stale, and local indexing is within the approved scope/budget, run
`kgraph index --repo <checkout> --no-embed`, then repeat status and
`kgraph impact --repo <checkout> <changed-files> --json`. Require fresh status in
the impact result too. Do not default to force rebuild, embeddings or a watcher.
Pause concurrent edits during the check or recheck after changes; freshness is
decision-bound, not a permanent property of a session.

If refresh is unavailable, fails, or still reports stale, preserve UNKNOWN impact
coverage. For bounded documentation changes, inspect actual references directly
and disclose the graph limitation. For consequential runtime changes, provide
equivalent source/call-site and test evidence for review, or stop the affected
decision. A fresh graph still does not prove complete dynamic behavior or coverage
of unsupported file types. No scheduler, new repository gate or tool repair is
authorized by this preflight. Record repeated actionable misses as IL-0 incident
candidates only when evidence supports a workflow or tool defect.

## 8. Work Packages

Estimates are active engineering effort, not deadlines or spending authority:
IL-0 0.5-1 day; IL-1 1-2 days; IL-2 1-2 days; IL-3 2-3 days; IL-4 1-2 days;
IL-5 1-2 days plus passive observation; IL-6 0.5-1 day. Re-estimate after IL-1.
These package bounds include review and integration; do not pad execution to fill
them. At execution, turn each row into 2-5 minute edit/assert steps, one field,
branch, fixture, or output assertion at a time. Pair a failing test with its
smallest implementation before moving on; retain red evidence, keep delivered
slices green. No broad full-run debugging loop.

### WP-IL-0: Preserve Incidents And Test The Manual Flow

Documentation/evidence only; separate source-access authorization required.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Rebind the baseline and record authorized sources and impact freshness in this plan's execution worklog | AUDIT | Exact candidate, dirty state, environment, permissions, index_fresh and unavailable sources recorded; stale results do not establish no impact |
| 2 | Inventory capture/read/retention behavior in the six owners in section 3 | AUDIT | One row per supported producer; unsupported and unknown paths explicitly listed |
| 3 | Agree the evidence location and access/retention owner before copying any incident artifacts | SPECIFY | Paths, caps and approval recorded; no automatic remote download or raw transcript commit |
| 4 | Create ordinary Markdown work items under the existing docs/backlog convention, with evidence and proposed improvement sections | SPECIFY | One reviewed record per seed incident; no unsupported frontmatter; exact new paths recorded before creation |
| 5 | Seed from the reported launch-accounting field mismatch, terminal-accounting kind failure, resume/prior-stage lineage conflict, and source-mode restoration failure | AUDIT | Each source is available and bound, or explicitly reported/unverified; no run is relaunched |
| 6 | Walk one incident through two alternative improvements, and one missing-artifact record through triage | REVIEW | Operator can locate evidence, distinguish cause from hypothesis, and identify next approval without implying closure |

Exit: a useful manual roster and a capture-gap inventory, not runtime completion.
Keep incident chronology and negative attempts. Missing historic evidence does
not block recording an honest incomplete incident, but blocks claims requiring it.

### WP-IL-1: Freeze Contracts, Fixtures And Acceptance

Schema/design only; coordinate with WLI-0/WLI-1 before runtime edits.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Freeze section 5 types, stable identity, reference and migration rules with the lifecycle plan | SPECIFY | A truth table distinguishes observation, proposal, approval, delivery, verification and recurrence |
| 2 | Freeze source scoping, time windows, unknown handling and idempotency in this plan | SPECIFY | Same-event reimport, new attempts, same-text foreign projects and conflicting IDs have explicit outcomes |
| 3 | Freeze privacy, storage caps, retention, deletion/tombstone and failure behavior in this plan | SPECIFY | Evidence deletion cannot silently preserve an available/verified claim; no unbounded retention default |
| 4 | Freeze the L3 route, IL-UX-01 through IL-UX-12, claim states, transition/recovery table and CLI contract in the UX/UI documents | SPECIFY | Each criterion has an implementation owner and scoped evidence route; applicable shared gates are resolved, old command defaults retained; no mandatory persona/state/time template |
| 5 | Define fixtures beside tests/test_cli.py and tests/test_learn_proposals.py, reusing existing temporary-repository helpers | SPECIFY | Frozen expected outputs cover code, research provenance and spreadsheet verification failures; non-code examples are labeled synthetic |
| 6 | Review the schema and handoffs with a reviewer independent of the implementation | REVIEW | No unresolved identity, privacy, authority or false-closure finding; operator approves exact contract and scope |

Exit: accepted schema/UX/BDD matrix, owned files, local test budget and immutable
development fixture identities. Live effectiveness claims are not an exit condition.

### WP-IL-2: Bind Occurrences To Retained Evidence

Runtime slice 1; edit trace/evidence owners only for demonstrated gaps.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add single-boundary failing assertions to tests/test_trace_canonical.py and tests/test_evidence_contract.py | TDD | Foreign, missing, malformed and unavailable references fail for the intended reason |
| 2 | Add only required identity/redaction fields in fettle/trace.py and approved reference changes in fettle/evidence.py | CODE | Each field passes its focused fixture; legacy trace entries remain explicitly readable |
| 3 | Bind selected evidence using existing artifact/ledger operations, extending fettle/evidence_ledger.py only if required | INTEGRATION | Real emitted bytes pass parse_artifact and validate_artifact before a work-item reference is considered applicable |
| 4 | Add rotation, permission-denied, interrupted-write, oversized-input and logging-recursion regressions in tests/test_trace.py and tests/test_evidence_ledger.py | REGRESSION | Named incident_capture_partial_write and incident_evidence_rotated fixtures retain unknown/non-pass rather than reporting success |
| 5 | Run uv run --no-sync pytest tests/test_trace.py tests/test_trace_canonical.py tests/test_evidence_contract.py tests/test_evidence_ledger.py -q | LIVE | Nonempty focused checks pass; real temporary-file state retains the selected artifact after diagnostic rotation and reports missing bytes correctly |

Exit: source-bound evidence is usable or visibly unavailable; no universal capture
claim, new evidence authority, or mandatory remote service.

### WP-IL-3: Produce Reviewable Improvement Work Items

Runtime slice 2; dependent on IL-1/2 and the accepted WLI parser boundary.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add one red metadata/identity fixture at a time in tests/test_work_items.py and tests/test_evolution.py | TDD | Conflicting IDs, foreign scope, unknown dates and new-attempt versus reimport cases fail before the matching edit |
| 2 | Parse approved links in fettle/work_items.py, without adding independent delivery states | CODE | Legacy and WLI fixtures pass; invalid references cannot silently become done |
| 3 | Extend fettle/evolution.py with deterministic, source-scoped incident candidates | CODE | Repeat ingestion is idempotent; distinct occurrences survive; similarity never auto-confirms cause |
| 4 | Extend fettle/learn.py with explicit local work-item drafting and optional separately authorized model assistance | CODE | Draft is proposed, not approved; offline deterministic output works; existing Semgrep promotion behavior remains unchanged |
| 5 | Feed actual emitted occurrence/evidence records through evolution, proposal writer and work-item parser in tests/test_learn_proposals.py | INTEGRATION | Result contains resolvable incident/evidence links and preserves approval and diagnosis uncertainty |
| 6 | Preserve incident_resume_dual_lineage, incident_cross_repo_same_message and incident_untrusted_instruction regressions | REGRESSION | Foreign/enriched lineage, merged repositories and embedded instructions cannot create false cause, approval or closure |
| 7 | Run uv run --no-sync pytest tests/test_work_items.py tests/test_evolution.py tests/test_learn.py tests/test_learn_proposals.py -q | LIVE | Real temporary-repository state shows one draft after duplicate ingestion and two occurrences after a new attempt; no provider or policy write occurs |

Exit: an operator can inspect and edit an evidence-linked proposal; drafting does
not imply approval, diagnosis correctness, or prevention effectiveness.

### WP-IL-4: Expose The Roster And Verify The Complete Local Flow

Runtime slice 3; this is the first automated user-facing vertical completion.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add red human/JSON/exit assertions for the frozen contract in tests/test_report.py and tests/test_cli.py | TDD | Missing, empty, stale, malformed, pending approval and verified states remain distinguishable |
| 2 | Add the derived roster view in fettle/report.py and route approved options in fettle/cli.py | CODE | Inspection performs no writes or model calls; summaries preserve source scope and unknown coverage |
| 3 | Connect work items to the existing completion evaluator through its accepted read-only boundary | INTEGRATION | Actual emitted records reach parser, validator, renderer and evaluator; an unavailable required artifact is non-pass, not closed |
| 4 | Preserve incident_terminal_kind_missing, incident_false_done and incident_timeout_not_success regressions in tests/test_cli.py | REGRESSION | Malformed producer output, prose checkboxes and timeout evidence cannot satisfy a required success criterion |
| 5 | Run uv run --no-sync pytest tests/test_report.py tests/test_cli.py -q -k incident_learning | LIVE | Nonempty CLI subprocess tests prove capture-to-proposal state transition, reinspection persistence, no-read-side writes, and rejected false closure |
| 6 | Document implemented ownership and limitations in docs/behavior-map.md, docs/CONFIG.md and docs/CAPABILITIES.md | VERIFY | Help, examples and public claims match the actual supported command contract; no aspirational automatic-every-error claim |

Exit: the complete offline flow is proven on real temporary artifacts, not merely
mocked dictionaries. Mock external services, not all internal handoffs. WLI-4
remains required before claiming enforced closure integrity.

### WP-IL-5: Run A Bounded Advisory Pilot And Measure Learning

Local pilot only; fixture success is not proof of live host capture or effectiveness.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Freeze a local pilot manifest in this plan's execution worklog before use | SPECIFY | Named sources, event denominator, participants, candidate, duration/event cap, effort budget and stop conditions approved |
| 2 | Walk the IL-UX criteria with participants selected for actual operator, reviewer and applicable accessibility uncertainties | VERIFY | Record context, assistance, runtime/assistive technology and outcomes by criterion; no invented personas, fixed participant archetypes or automated substitute for human evidence |
| 3 | Compare the manual IL-0 flow with the candidate on the frozen local corpus | VERIFY | All assigned cases counted; separate incident-to-record time, record-to-triage time, triage-to-regression time and human effort |
| 4 | Independently adjudicate duplicate clusters, proposed causes and false closures | REVIEW | Zero unresolved false closures, foreign-scope links, unauthorized actions or secret disclosures; disagreements retained |
| 5 | Record recurrence and costs only within observed source coverage | AUDIT | Denominators, unknowns, misses, false groupings, model cost if authorized, and provider-only failures reported separately |
| 6 | Decide continue, revise or stop without changing the frozen acceptance threshold after observing results | REVIEW | Safety/integrity failures block rollout; null speed benefit permits a completed pilot but not a faster-learning claim |

Exit: retained pilot evidence and a decision. No arbitrary reduction percentage,
universal coverage, or no-recurrence guarantee. A credible benefit assessment
counts operator cleanup and review time, not just automated draft latency.

### WP-IL-6: Deliver, Observe And Feed Existing Improvement Programs

Requires explicit commit/push/rollout approval and passed required criteria.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Reconcile criteria and evidence in the existing completion manifest convention | VERIFY | Each required criterion has candidate-bound evidence; fettle completion validate reports the actual result |
| 2 | Run focused tests, required project suites, Fettle scan and applicable project rule packs | VERIFY | Record commands, versions, counts, exits, skips and unrelated blockers; no hook bypass or policy relaxation |
| 3 | Exercise the packaged CLI in a clean environment and complete the manual UAT report | VERIFY | Installed runtime, persistence, offline and recovery behavior verified; source-only success is not packaging evidence |
| 4 | Obtain delivery and rollout approval, then use normal hooks and verify remote CI when pushing is authorized | REVIEW | Exact delivered identity and green required remote jobs retained; mutation failures require explicit commit permission |
| 5 | Observe existing use without launching new qualification campaigns | AUDIT | Recurrences link to retained incidents; unavailable observations remain unknown; rollback disables new drafting without deleting evidence |
| 6 | Feed accepted lessons into existing WLI, DS/ED and domain work items through reviewed proposals | REVIEW | Every follow-up names its incident and evidence; no automatic global skill edits, rule promotion or widening of acceptance |

Exit: bounded feature acceptance and delivery evidence, not acceptance of every
linked improvement, hardening, broader program, or future domain.

## 9. Verification And Stop Conditions

Order: fixture/schema checks, narrow tests, actual producer-to-consumer flow,
complete local flow, required suite/quality checks, packaged UAT, then approved
remote delivery or separate evaluation. Full mutation runs remain held-out
verification under [mutation-quality-playbook.md](mutation-quality-playbook.md),
never an incident-learning iteration loop.

Stop and ask on a new authority boundary, missing source permission, necessary
schema expansion outside IL-1, unexplained evidence conflict, exceeded budget,
secret exposure, inability to preserve original failure, or need to edit the
active hardening candidate. Record blockers in the roster without calling them
resolved. Routine repairs inside the approved slice use the same focused check.

Before accepting a package, try these false-pass cases: evidence is only a model
summary; the file exists but its source is foreign; diagnosis is asserted without
a reproducer; an investigation closes but its improvement is open; no logs exist
because capture failed; the timeout test passes but success was never observed.
Each must remain accurately labeled rather than become prevention or completion.

## 10. Planning Requirements And Evidence

| Requirement | Contract location | Verification required |
|---|---|---|
| P0 priority without hardening disruption | Section 2 and TODO P0-IL | Cross-document ordering and authority review |
| Useful value before automation | IL-0 | Manual incident-to-improvement walkthrough |
| Cross-task scope, specialized verification | Sections 1/2/5 and UX BDD | Code and synthetic non-code contract fixtures; no unsupported host claim |
| Privacy, evidence availability and failure visibility | Sections 5/6 and IL-2 | Adversarial fixtures plus retention/write-failure checks |
| No duplicate lifecycle authority | Sections 5/7 and IL-1/3/4 | WLI review and real completion-consumer checks |
| Measured learning, not proposal-count theater | IL-5 | Frozen denominators, time/effort, misses, false grouping and independent review |
| Truthful delivery | IL-6 | Criterion evidence, package/UAT checks and explicit approval |
| Planned UX standard alignment | Linked vNext contract and UX IL-UX-01 through IL-UX-12 | Independent L3 triggers, source/claim states, derived recovery, shared gates and owner-to-evidence traceability |
| Freshness before relying on impact | Section 7 preflight and IL-0 | Fresh status and impact on the same checkout state, or explicit reviewed source-inspection fallback |

## 11. Planning Worklog

- 2026-10-12: User approved detailed planning and a high-priority TODO topic.
  Inspected existing trace, learning, reporting, work-item and lifecycle owners.
  Preserved newer M-NC1 scheduling and all unrelated worktree changes.
- Decision: retain existing work items, evidence contracts and completion
  authority. Start with a manual evidence-linked roster; do not build a new
  incident service or automatically alter policy.
- Baseline checks: sandboxed Git failed to resolve the repository; an unsandboxed
  read established the local identity above. Installed kgraph uses positional
  paths, not --file. Its impact result reported a stale index; this is not proof
  of complete impact coverage. No reindex or runtime job was launched.
- Verification: `python3 -B fettle/plan_validator.py
  docs/incident-learning-implementation-plan.md` passed all seven packages.
  A read-only Node check passed 45 local links across four documents, balanced
  fences, ASCII in new files, twelve BDD scenarios and the unique P0 ordering.
  Editor diagnostics were clear. The required external Fettle `check --changed`
  reported no issues; scoped `git diff --check` passed. Neither project rule-pack
  directory exists. Fettle's terse result did not report a scanned-file count;
  document coverage comes from the focused checks, not an inferred code scan.
- Semantic self-review: mapped each requirement in section 10 across plan, UX,
  presentation and TODO; preserved hardening/WLI/M-NC1 ordering, distinguished
  investigation from improvement closure, and kept proposed CLI options visibly
  unimplemented. Missing evidence, a model-only diagnosis and a timeout-only
  result cannot satisfy the intended verification claim. This is not an
  independent implementation review or human UAT result.
- Remaining execution decisions: IL-0 source permissions and artifact access;
  IL-1 exact schema, CLI, retention caps and migration; IL-5 participants and
  measurement budget. No implementation, incident ingestion, model invocation,
  UAT session, effectiveness experiment or milestone acceptance is claimed.
- 2026-10-12 follow-up: compared P0-IL with the planned Experience Discipline
  vNext capabilities. Replaced the old generic persona/state/time template with
  a justified L3 route, actual actors, derived transitions, claim evidence states,
  shared blocking-gate mapping and twelve criterion-to-owner/evidence links.
  No skill was changed or installed. Prior checks above describe the initial
  package. Follow-up checks passed seven work packages, 72 local links, twelve
  unique criterion definitions and scenarios, all four risk triggers, removal of
  the old persona/state/time requirements, and preserved TODO priority. Editor
  diagnostics, required Fettle changed scan and scoped whitespace checks passed;
  project rule-pack directories remain absent. Two preliminary custom checks
  miscounted a criterion reference and overconstrained wording; corrected checks
  passed without changing the intended contract. Semantic self-review confirmed
  no new lifecycle authority, automatic skill rollout or universal UX template.
- Freshness investigation: kgraph status and scoped impact both report
  index_fresh=false, with reason "working tree changed since last index"; indexed
  HEAD matches this checkout's recorded HEAD. This supports an outdated snapshot,
  not corruption, missing code or a specific missed dependency. Exact triggering
  files and why no refresh occurred are not established by those diagnostics.
  Added decision-time freshness verification and a bounded no-embedding refresh
  procedure. No reindex, embedding, watcher or tool-code change was performed.