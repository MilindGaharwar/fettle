# Application Audit Follow-Up Plan

Date: 2026-09-18
Status: Implementation authorized 2026-09-18; hardening in progress, acceptance pending.
Owner: Milind (approval); implementing engineer (delivery); independent automated
reviewer in an isolated session (acceptance review).

Related artifacts: [UX acceptance contract](audit-hardening.ux-spec.md),
[worklog](audit-hardening-worklog.md), [program index](plan-index.md),
[extension ownership](behavior-map.md), and [existing roadmap](ROADMAP.md).

## Objective And User Flow

As a repository owner, I want a green Fettle result to mean that all required
checks actually ran against the intended scope, so I can trust local decisions,
installed commands, concurrent evidence, and CI outcomes.

Flow: install -> diagnose -> select scope -> run checks -> inspect result and
evidence -> follow recovery action -> rerun -> verify independently.

This plan addresses six reproduced audit findings before expanding features.
An audit observation is not a completed fix. Green lint alone is not acceptance.

## Assumptions, Boundaries, And Decisions

- Reproduce each finding against the current checkout before changing behavior.
- Prefer small repairs in existing owners over a scanner, dispatcher, or CLI rewrite.
- Preserve public commands and valid-result compatibility. Tighten invalid-input
  handling deliberately, with documented exit semantics and regression tests.
- Dispatcher advisory-first behavior remains for optional checks. Authorization
  covers required-check execution integrity. Config/registry failures and compound
  gate semantics are now regression-covered locally; independent acceptance remains.
- Ledger repair must cover competing processes, rotation, and anchoring, not just
  threads. Do not silently rewrite or repair existing suspect evidence.
- The wheel finding was verified on the existing local v1.13.1 artifact, not a
  freshly built or downloaded public wheel. WP-AH05 must close that evidence gap.
- No new dependency, telemetry collection, persistent database, browser UI,
  enforcement promotion, release, commit, or push is authorized by this plan.
  Operator subsequently authorized commit/push on 2026-09-19 after verification;
  release and feature/research admission constraints remain unchanged.
- Existing roadmap programs retain ownership. Later packages extend or feed those
  programs rather than duplicating their schemas, trackers, or experiments.
- On 2026-10-05 the owner replaced AH07's previously required human-independent
  review with independent automated acceptance because no human reviewer is
  available. This satisfies AH07's reviewer-type decision when 07.4 is executed;
  it does not create human acceptance or human-usability evidence. No such human
  validation was performed. Platform, host, artifact, remote-CI, and completion
  criteria remain unchanged. Real-participant parity belongs to later WP-AH13/P77,
  not Milestone A. Public-PyPI canary verification belongs to WP-AH15 and the release
  contract, not AH05 or Milestone A.
- Before a multi-file implementation slice, run `kgraph impact <owner> --json`;
  if unavailable, record a references/call-site impact review, not a claimed pass.
- Resolve existing work and dirty changes before edits. Claim the actual work item
  through `fettle work` once Git is functional; do not invent a successful claim.

Approaches considered: patch only the six examples (fast but leaves sibling paths
untested); repair owning contracts plus final-boundary tests (recommended); rewrite
the trust kernel (too broad and risky for these findings).

## Priority And Detailed To-Do List

P0 = false success or evidence integrity; P1 = installed correctness and acceptance;
P2 = measured engineering/product improvement; P3 = separately approved expansion.
Dependencies are acceptance dependencies, not permission to run parallel agents.
Estimates are focused engineering days including review, not calendar promises.

| Done | Package | Priority | Outcome | Depends on | Estimate | State |
|---|---|---|---|---|---|---|
| [ ] | WP-AH00 | P0 | Restore trustworthy verification environment | Working CLT Git found | 0.5-1 | Local environment restored |
| [ ] | WP-AH01 | P0 | Scanner failures cannot produce clean standalone results | AH00 for full acceptance | 1-2 | Implemented; local tests and live recovery pass |
| [ ] | WP-AH02 | P0 | Action validates scope and scanner evidence | AH01 | 0.5-1 | Implemented; 21 focused tests pass |
| [ ] | WP-AH03 | P0 | Required enforcement survives budget/error paths | AH00; policy review | 2-3 | Registry/config and compound gaps repaired locally; acceptance open |
| [ ] | WP-AH04 | P0 | Concurrent ledger operations preserve valid history | AH00 | 2-3 | POSIX concurrency/interruption verified; Windows gate added, run pending |
| [ ] | WP-AH05 | P1 | Wheel includes graph providers and usable commands | AH00 | 1-2 | September 19 wheel/sdist isolated smoke passed; remote acceptance open |
| [ ] | WP-AH06 | P1 | UAT inputs preserve their declared classes | AH00 for integration | 0.5-1 | Implemented; 23 focused tests pass |
| [ ] | WP-AH07 | P1 | Independent hardening acceptance evidence | AH01-AH06 | 1-2 | Independent automated review is required; supported-platform, available-host, remote-CI, and inspectable evidence remain blockers until confirmed |
| [ ] | WP-AH08 | P2 | Ratcheted critical-module type and branch checks | AH07 | 2-4 | Narrow type gate added; branch baseline measured |
| [ ] | WP-AH09 | P2 | Measured hook and ledger performance | AH07 | 2-3 | Exploratory local baseline; frozen benchmark pending |
| [ ] | WP-AH10 | P2 | One justified CLI or mutation responsibility extraction | AH08-AH09 | 3-5 | Measurement-gated |
| [ ] | WP-AH11 | P2 | Clear command discovery and recovery summary | AH07; UX approval | 2-4 | Existing help inspected; journey approval pending |
| [ ] | WP-AH12 | P3 | Read-only evidence viewer and PR summary | AH11; demand evidence | 1-2 discovery only | CLI-first proposal; demand/prototype approval pending |
| [ ] | WP-AH13 | P3 | Broader polyglot and human-validated UAT parity | AH06-AH07; existing owners | 2-3 discovery only | Prerequisites inventoried; real human sessions missing |
| [ ] | WP-AH14 | P3 | New contextual-impact research proposal | Prior experiment review | 1-2 design only | Admission proposal recorded; no experiment authorized |
| [ ] | WP-AH15 | P3 | Live-host, dependency, and public-artifact audit coverage | AH05-AH07; operator access | 1-2 baseline only | Runtime advisory scan clean; external evidence open |

Suggested sequence: AH00 -> AH01 -> AH02 -> AH03 -> AH04 -> AH05 -> AH06 -> AH07.
AH05/AH06 can move earlier while another package awaits review. Do not begin P2/P3
merely because a P0 package is blocked. Initial hardening budget: approximately
9-16 days; P2: 9-16 additional days. P3 delivery estimates require approved designs.

## Work Packages

Every row starts unchecked. Update a row only after its named evidence is retained.
All implementation packages follow AUDIT -> SPECIFY -> REVIEW -> IMPLEMENT -> VERIFY:
recheck owner/call sites, freeze the acceptance case, review blast radius, reproduce
with a failing test, patch narrowly, then run focused and independent verification.

### WP-AH00: Verification Environment And Baseline

Owner: operator for system approval; engineer for isolated project checks.
Scope: local environment and baseline evidence; no application behavior changes.
Acceptance: supported Python and Git can run repository fixtures, build tools exist
in an isolated environment, and baseline failures are classified before repair.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 00.1 | Operator reviews and accepts Xcode license or supplies a working Git installation | REVIEW | `git --version` and disposable `git init` succeed; agent never accepts legal terms |
| [ ] 00.2 | Select supported Python 3.11-3.13; record interpreter and dependency versions; provision build tools only in isolated environment | VERIFY | `python --version`, `python -m pip check`, `python -m build --version` |
| [ ] 00.3 | Record worktree state, baseline tests, scan results, and claimable work item | INSPECT | `git status --short`, `fettle work list`, focused tests and Fettle results retained |
| [ ] 00.4 | Confirm certificate access without disabling TLS verification | VERIFY | `fettle check --all --root fettle --json` has no tool errors |

### WP-AH01: Standalone Scanner Failure Integrity

Owner: `fettle/quality_scan.py`; consumers include `.github/workflows/ci.yml`.
Reuse `tests/test_quality_scan.py` and CLI tests. Risk: baseline/output compatibility.
Acceptance: required scanner failure is nonzero and structured, even with no findings;
valid clean and violation results preserve their documented behavior.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 01.1 | Pin missing, crashed, timed-out, empty, and malformed analyzer outcomes at `main()` | TDD | Focused tests fail on current false-success path before repair |
| [ ] 01.2 | Route standalone output through the structured owning result contract; preserve baseline behavior | FIX | No findings-only wrapper controls the final success decision |
| [ ] 01.3 | Compare standalone entry, public CLI, and CI self-scan semantics | INTEGRATION | `python -m pytest tests/test_quality_scan.py tests/test_cli.py -q` |
| [ ] 01.4 | Preserve clean scan, ordinary findings, and baseline filtering while both analyzers fail | REGRESSION | Named missing-both-analyzers case cannot return exit 0 |
| [ ] 01.5 | Use disposable missing-tool and valid-tool environments | LIVE | Run `python -m fettle.quality_scan --root <fixture> --json`; failure is nonzero, valid clean is zero |

### WP-AH02: GitHub Action Scope And Result Validation

Owner: `fettle/action_entrypoint.py`; action and reusable workflow consumers.
Reuse `tests/test_action_entrypoint.py`. Risk: malformed legacy reports now fail.
Acceptance: zero scans, malformed results, or status/exit contradictions cannot pass;
advisory mode softens valid findings only, never infrastructure failures.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 02.1 | Pin whitespace paths, empty objects, invalid finding types, contradictory status/exit, and multi-root partial failure | TDD | Parameterized tests fail for each reproduced gap |
| [ ] 02.2 | Validate nonempty scope and the existing scanner result shape without inventing another schema | FIX | Valid output accepted; invalid evidence returns tool/config error |
| [ ] 02.3 | Exercise annotation/SARIF outputs and final enforcement in both workflow consumers | INTEGRATION | `python -m pytest tests/test_action_entrypoint.py -q` plus workflow contract checks |
| [ ] 02.4 | Keep quoted paths with spaces, uppercase ERROR findings, and advisory findings working | REGRESSION | Named zero-scan-success and tool-error-exit-1 cases remain non-pass |
| [ ] 02.5 | Invoke the entrypoint with empty scope and disposable clean/error fixtures | LIVE | Run `python -m fettle.action_entrypoint`; inspect exit, findings count, and output files |

### WP-AH03: Mandatory Dispatcher Enforcement

Owner: `fettle/dispatcher.py`, registry/types, and existing dispatcher tests.
Risk: blocking semantics and hook latency across supported hosts. Approval required:
which checks are mandatory, retry messaging, and fail-closed error behavior.
Acceptance: a selected required check that does not execute cannot yield allow;
optional advisory checks remain bounded without blanket fail-closed conversion.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 03.1 | Pin elapsed-budget, check exception, registry failure, and invalid-config decisions under enforce/advisory modes | TDD | Fake-clock tests distinguish required non-pass from optional omission |
| [ ] 03.2 | Implement approved mandatory-check policy at the dispatcher owner | FIX | No real destructive command executes in any fixture |
| [ ] 03.3 | Exercise normalized events and host output contracts | INTEGRATION | `python -m pytest tests/test_dispatcher.py tests/test_dispatcher_registry.py tests/test_dispatcher_aggregate.py tests/test_agents.py -q` |
| [ ] 03.4 | Preserve secret protection and advisory availability; slow first check must not bypass destructive enforcement | REGRESSION | Named secret-overrun-then-destructive case returns deny/non-pass |
| [ ] 03.5 | Feed safe synthetic hook payloads through the real dispatcher process | LIVE | Run `python -m fettle.dispatcher` with fixture stdin; verify block, recovery action, and trace |

### WP-AH04: Concurrent Evidence Ledger Integrity

Owner: `fettle/evidence_ledger.py`; callers in trace and assurance.
Reuse ledger/assurance tests and existing locking conventions after platform review.
Risk: deadlocks, anchor snapshots, crash durability, performance, Windows parity.
Acceptance: competing processes cannot reuse sequence numbers or break hash links;
append/rotation/anchor interactions retain verifiable history or explicit non-pass.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 04.1 | Reproduce duplicate sequence with synchronized independent writers and append/rotate/anchor races | TDD | Deterministic failing race fixture, not timing-only stress |
| [ ] 04.2 | Serialize critical operations with bounded lock failure handling and no silent evidence repair | FIX | Lock scope covers read through durable publication; platform behavior documented |
| [ ] 04.3 | Verify caller behavior, anchor consistency, process interruption, and lock cleanup | INTEGRATION | `python -m pytest tests/test_evidence_ledger.py tests/test_assurance_adversary.py -q` |
| [ ] 04.4 | Preserve detection of tampering, truncation, and legitimate rotation | REGRESSION | Named simultaneous-genesis-appends case yields unique ordered sequences and valid chain |
| [ ] 04.5 | Run concurrent append workload in a disposable repository, then inspect provenance | LIVE | Run `fettle ledger --help` and its verification subcommand; valid chain or explicit error, never false pass |

### WP-AH05: Complete Installed Wheel And Command Smoke Tests

Owner: `pyproject.toml`, `setup.py`, installed-artifact tests and CI/release workflows.
Risk: package resources, editable-install leakage, optional external prerequisites.
Acceptance: newly built wheel and sdist include providers; graph commands import
and run outside checkout; no source-tree imports rescue missing distribution files.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 05.1 | Add package inventory and isolated graph-provider import assertions | TDD | Current explicit package omission produces a failing artifact test |
| [ ] 05.2 | Correct package discovery/list conservatively; preserve bundled resources | FIX | Fresh wheel includes `fettle/providers` without unrelated packaging churn |
| [ ] 05.3 | Install wheel and sdist into fresh environments outside checkout; update every affected workflow | INTEGRATION | `python -m build`; artifact canary tests and resource assertions |
| [ ] 05.4 | Exclude editable hooks, PYTHONPATH, and working-directory leakage | REGRESSION | Named graph-provider-wheel-omission cannot be masked by editable install |
| [ ] 05.5 | Exercise demo, help, graph, and non-mutating command-family probes | LIVE | Run installed `fettle demo` and `fettle graph status --json` in disposable repo; capture origins and exits |

### WP-AH06: Class-Valid UAT Inputs

Owner: `fettle/uat/session.py`; `tests/test_uat_session.py`.
Risk: deterministic fixture identities and downstream session expectations.
Acceptance: zero remains numeric zero; valid email/phone formats remain valid;
uniqueness does not mutate the semantic class; invalid-format cases are explicit.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 06.1 | Assert class membership, deterministic values, and meaningful boundary cases | TDD | Tests reject bracket-suffixed numeric and email inputs |
| [ ] 06.2 | Use class-specific generation or metadata-only identifiers | FIX | No universal suffix appended to every value |
| [ ] 06.3 | Check prompt and retained profile compatibility without inventing benchmark parity | INTEGRATION | `python -m pytest tests/test_uat_session.py -q` |
| [ ] 06.4 | Retain Unicode, whitespace, punctuation, and explicit malformed-input classes | REGRESSION | Named suffixed-zero-not-zero and suffixed-email-invalid cases stay fixed |
| [ ] 06.5 | Generate a profile and feed values into a deterministic validation fixture | LIVE | Run `python -c 'from fettle.uat.session import generate_profile; print(generate_profile("audit"))'`; verify formats and zero |

### WP-AH07: Independent Hardening Acceptance

Owner: implementing engineer plus independent automated reviewer operating read-only
in a separate session and isolated review environment; no automatic release. Before
2026-10-05 this package required an independent human reviewer. The owner explicitly
replaced only that requirement because no human reviewer is available. No human
acceptance or human-usability validation was performed or inferred.
Acceptance: every AH01-AH06 criterion has current evidence; blocked/skipped checks
remain non-pass. No remote verification or installed-host claim is inferred. AH07
does not require a separate human-acceptance sign-off or real-participant parity
study after the owner-authorized reviewer replacement. Those observations must still
not be fabricated or attributed to automation.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 07.1 | Replay all six audit cases against final candidate and record source/policy identity | VERIFY | Named regressions and safe end-to-end fixtures pass |
| [ ] 07.2 | Run full suite, Ruff, Fettle, applicable rule packs, and completion validation | VERIFY | `python -m pytest tests -q`, `ruff check fettle tests`, `fettle check --all`, `fettle completion validate` |
| [ ] 07.3 | Perform supported-platform wheel/host smoke checks and failure-path UAT | REVIEW | Unsupported or inaccessible host remains unverified, not pass |
| [ ] 07.4 | Independently inspect the candidate diff, artifacts, migration notes, operator recovery, and evidence completeness; execute relevant checks without repairing the candidate | REVIEW | Independent automated reviewer records criterion-by-criterion verdicts, evidence references, findings, and limitations; user separately authorizes commit/push/release, and unavailable evidence remains non-pass |

### WP-AH08: Critical Type And Branch Ratchets

Scope: CI typecheck/coverage plus evidence, policy, and dispatcher owners.
Estimate: 2-4 days after baseline. No unrelated whole-repo type cleanup.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 08.1 | Establish real type and subprocess-coverage baselines before choosing ratchets | INSPECT | Retained reports; unknown/degraded tooling is not zero defects |
| [ ] 08.2 | Pin newly introduced type-error and coverage-regression rejection | TDD | Deliberate fixture defect fails the gate |
| [ ] 08.3 | Remove unconditional masking only for approved baseline-controlled scope | FIX | Existing debt explicit; new critical errors block |
| [ ] 08.4 | Verify local, PR, and release workflow consistency | INTEGRATION | CI fixture checks plus critical-module suite |
| [ ] 08.5 | Preserve visibility of missing checker and subprocess branches | REGRESSION | Missing mypy or unknown coverage cannot produce a passing report |
| [ ] 08.6 | Run actual type and branch measurement commands in candidate environment | LIVE | `mypy fettle --ignore-missing-imports` and `pytest --cov=fettle --cov-branch`; retain baseline and ratchet decision |

### WP-AH09: Hook And Ledger Performance Baseline

Scope: existing benchmarks and reporting; no automatic telemetry enablement.
Estimate: 2-3 days. Acceptance: reproducible p50/p95/p99, required-check omissions,
and ledger growth curves; no performance win by omitting required checks.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 09.1 | Freeze representative events, fixture sizes, cold/warm conditions, and machine metadata | INSPECT | Versioned benchmark inputs and measurement protocol |
| [ ] 09.2 | Assert latency counters retain failed/omitted required checks | TDD | Missing/degraded observations stay distinct from fast successful runs |
| [ ] 09.3 | Extend existing measurement owner only where baseline data is missing | BUILD | No extra collection by default or new production database |
| [ ] 09.4 | Measure dispatcher and ledger together under concurrent fixture load | INTEGRATION | Same completed-work counts across comparisons |
| [ ] 09.5 | Inject slow analyzer and growing ledger, preserving honest failure accounting | REGRESSION | Slow/unknown result cannot improve reported success rate |
| [ ] 09.6 | Run the frozen benchmark and inspect tail latency plus decision outcomes | LIVE | Run `fettle bench --help`, then documented benchmark command; retain environment and counts |

### WP-AH10: Measured Responsibility Extraction

Scope: choose one cohesive CLI or mutation responsibility after impact review.
Estimate: 3-5 days for one extraction, not a rewrite of both large modules.
Acceptance: measurable complexity/duplication reduction with unchanged public behavior.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 10.1 | Identify actual change friction and freeze public command/output contracts | INSPECT | Before metrics and bounded ownership diagram |
| [ ] 10.2 | Add characterization cases for selected responsibility | TDD | Output, exit, state, and import contracts pinned |
| [ ] 10.3 | Extract one owner and preserve public wrappers | REFACTOR | No opportunistic adjacent cleanup |
| [ ] 10.4 | Run consumer and installed-package checks | INTEGRATION | Selected command tests plus wheel smoke tests |
| [ ] 10.5 | Preserve CLI aliases and mutation fingerprint/cache compatibility where touched | REGRESSION | Named public-entrypoint and stale-cache regressions remain passing |
| [ ] 10.6 | Exercise chosen command with valid and failing fixtures | LIVE | Run `fettle <selected-command> --help` and approved fixture commands; compare outcomes |

### WP-AH11: Discovery And Recovery Design

Scope: existing doctor, pipeline, brief, help and result rendering. Prefer improving
existing entry points before adding a new command. Estimate: 2-4 days after approval.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 11.1 | Validate setup/check/verify/recover journeys with users; extend the UX contract before code | REVIEW | Approved task budgets, 8 states plus offline/stale, and BDD cases |
| [ ] 11.2 | Pin consistent human/JSON recovery and unavailable-capability states | TDD | Degraded/unknown never displayed as green |
| [ ] 11.3 | Group command discovery and surface the next valid recovery action | BUILD | Reuse existing summary surfaces and authoritative data |
| [ ] 11.4 | Exercise novice and automation flows across related commands | INTEGRATION | Command contract tests and noninteractive behavior |
| [ ] 11.5 | Preserve scripts, non-color output, and explicit stale/unknown evidence | REGRESSION | Named missing-host-and-stale-evidence scenario remains actionable |
| [ ] 11.6 | Time fresh-repository recovery using documented commands | LIVE | Run `fettle doctor`, `fettle pipeline`, and `fettle --help`; operator identifies failure and next step within approved budget |

### WP-AH12: Evidence Viewer And PR Summary Discovery

Scope: read-only presentation of existing evidence; no new authority or schema.
Budget: 1-2 discovery days only. Implementation requires separate sizing and approval.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 12.1 | Confirm demand and compare richer CLI/PR output with a browser viewer | REVIEW | Choose smallest surface that improves evidence inspection |
| [ ] 12.2 | Define subject/policy binding, stale/unknown rendering, secret redaction, and safe external links | SPECIFY | UX/UI/accessibility specs and BDD before any frontend code |
| [ ] 12.3 | Specify read-only boundaries, trusted rendering, and retention/privacy limits | REVIEW | Threat model; no untrusted HTML execution or authority inferred from appearance |
| [ ] 12.4 | Present prototype evaluation and independently sized implementation packages | VERIFY | User approval and feature-manifest admission before implementation |

### WP-AH13: Polyglot And Human UAT Parity Discovery

Scope: existing adapters and UAT strengthening program; no duplicate parity claim.
Budget: 2-3 discovery days; human sessions and implementation separately estimated.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 13.1 | Inventory Python/JS/TS/Go/Rust behavior and native prerequisites | INSPECT | Capability matrix distinguishes implemented, tested, installed, and unavailable |
| [ ] 13.2 | Freeze mixed-language failure fixtures and human/agent UAT comparison protocol | SPECIFY | Seed identities, valid inputs, discovery metric, and threshold agreed in advance |
| [ ] 13.3 | Coordinate human sessions with existing P77 owner | REVIEW | Consent and real observations; missing sessions remain unknown |
| [ ] 13.4 | Propose one bounded adapter/parity package from measured gaps | VERIFY | No enforcement promotion without retained evidence and explicit approval |

### WP-AH14: Contextual Impact Research Admission

Scope: existing contextual-impact program; advisory only. Budget: 1-2 design days.
Do not run a new experiment or reuse the held-out corpus for optimization here.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 14.1 | Revisit prior 78.05% required recall and inconclusive paired gain | INSPECT | Failure constraints carried into the existing hypothesis tree |
| [ ] 14.2 | Propose a materially different falsifiable hypothesis and freeze new corpus/budgets | SPECIFY | Required recall, cost, precision, and stopping criteria agreed before execution |
| [ ] 14.3 | Seek separate experiment approval and preserve advisory-only authority | REVIEW | No rollout or promotion inferred from a plan or promising sample |

### WP-AH15: Remaining Audit Coverage

Scope: live hosts, public distribution, dependency advisories, and remote CI.
Budget: 1-2 baseline days excluding access waits and remediation.

| # | Task | Method | Verify by |
|---|---|---|---|
| [ ] 15.1 | Inventory required host versions, credentials, allowed fixtures, and remote access | INSPECT | Operator authorization; no secrets routed through agent conversation |
| [ ] 15.2 | Check current dependency advisories against exact installed versions/SBOM | VERIFY | Timestamped advisory-source results; network failure is unknown, not clean |
| [ ] 15.3 | Run host-specific harmless allow/deny/recovery probes independently | VERIFY | Installation and registration are not substituted for live enforcement evidence |
| [ ] 15.4 | Verify downloaded public wheel identity and exact-candidate remote CI when authorized | VERIFY | No tag or publish; `gh run watch --exit-status <run-id>` only for the relevant run |

## Design And Feature Admission Gate

### Current Admission Decisions (2026-09-18)

These are proposals and explicit non-pass conditions, not completed packages.
The worklog retains executable results and environment limits.

- AH08: blocking mypy 2.3.0 now covers seven repaired critical modules in CI and
  release. Whole-repository typing remains informative. Combined coverage is
  75.46%, branch coverage 68.34%; no new floor is selected from one macOS run.
  Subprocess instrumentation and a seeded regression-rejection check remain open.
- AH09: 30 warm in-process observations per event and 1,000 sequential durable
  appends supply a first baseline, not a production budget. Freeze cold/warm,
  concurrent, slow-check and omitted-check fixtures before performance decisions.
  Existing `bench` measures findings/KLOC; it is not a latency command.
- AH10: no CLI or mutation extraction selected. The measurements show ledger
  growth cost, not evidence that either large module needs the proposed extraction.
  Require change-friction data and a characterized responsibility before coding.
- AH11: existing help lists 41 commands in one flat namespace. Proposed grouping:
  setup (`init`, `doctor`, `demo`); check/recover (`check`, `explain`, `pipeline`);
  verify/evidence (`verify`, `completion`, `ledger`, `assurance`); coordination
  (`plan`, `work`, `brief`, `graph`). Preserve aliases and automation. Test novice
  recovery against the 30-second UX target with actual users before implementation.
- AH12: prefer existing CLI and escaped PR text over a new browser viewer until
  demand is observed. Any prototype must show subject/policy identity, freshness,
  missing evidence and source links; forbid raw HTML, automatic external fetches,
  secrets and a green verdict derived from presentation alone. Retention must
  remain with the canonical producer. No frontend or PR-posting integration added.
- AH13: Python, TypeScript/JavaScript, Go and Rust have repository adapter owners.
  Local Node/npm exist; Go, Cargo/rustc and standalone tsc/eslint were not on PATH.
  Availability is not execution coverage. Existing P77 requires ten real human
  seed sessions, agreed discovery threshold, and zero false verdicts; this work
  does not create those observations or override Assurance Integrity admission.
- AH14: candidate hypothesis for review: fail-visible provider completeness and
  conservative required-impact inclusion could restore required recall without
  using contextual scores to suppress required checks. Compare with the frozen
  conservative baseline on a newly authored, separately held-out corpus, including
  missing-provider, mixed-language and changed-policy cases. Require 100% required
  recall, no false authoritative passes, agreed precision/cost budgets and stopping
  criteria before execution. Corpus, budgets and reviewer are not yet frozen;
  the prior 78.05% result remains disqualifying for promotion. No experiment run.
- AH15: current advisory lookup covered 82 installed wheel packages and 119 audit
  environment packages, with no known vulnerabilities or skips. Claude, Codex,
  OpenCode and gh executables were found; no authenticated host session was launched.
  Gemini/Antigravity were not found. Public wheel identity, host deny/recovery,
  supported-platform runs and exact-candidate remote CI remain unverified.

- Phase 0 UX: immediate repairs covered by the linked acceptance contract.
- Phase 0.5 UI: not applicable to AH00-AH10 (no visual frontend); preserve existing
  CLI style. AH11 needs reviewed output design; AH12 needs a separate UI spec.
- Phase 1 planning: ownership, risk, effort, dependencies, and checks recorded here.
- Phase 3.5 UAT: immediate-repair Given/When/Then cases in the linked UX spec.
- Feature manifest: no root FEATURES.md exists. This plan is the proposed inventory,
  not feature admission: AH11 = discovery/recovery enhancement; AH12 = evidence
  viewer/PR summary; AH13 = parity expansion; AH14 = research; AH15 = audit coverage.
  Add approved new features to the existing CAPABILITIES/ROADMAP owners when admitted;
  do not create a competing product manifest or mark unbuilt features shipped.

## Evidence, Completion, And Release Gates

For each package retain: criterion ID, command, interpreter/platform, candidate
source/policy identity, exit/result, artifact reference, reviewer, and limitations.
Task checkboxes aid navigation only; they never establish completion by themselves.
Use the existing completion mechanism for executable milestones before claiming
them complete; missing, stale, contradictory, skipped, or blocked evidence is non-pass.

At each slice: focused failing test -> smallest repair -> same focused test ->
consumer regressions -> Fettle check. When applicable scan edited files against
`.fettle/rules/` or `.lint/semgrep/` with `semgrep scan --config <pack> --project-root . <files>`.
Validate any edited Semgrep pack with `semgrep scan --config <file> --validate`.
Before acceptance run `fettle completion validate`. Follow the mutation playbook:
fixtures -> preflight -> narrow replay -> held-out full verification only when required.
Never rerun full mutation calibration as an iteration loop.

No implementation package is complete solely from this plan. No release date is promised.
If a push is separately authorized, completion includes green exact-candidate remote CI.
