# Experience Discipline vNext Implementation And Evaluation Plan

> Integration precedence — current main’s November 14 sequencing decision and
> trust-remediation ownership govern execution. Earlier scheduling and review
> observations below remain historical. This merge grants no feature approval.

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/experience.md).

Status: PROPOSED; planning only; no skill, evaluator, package, installer, global
configuration, migration, CI, release, or enforcement change is authorized

Experience contract: [experience-discipline-vnext.ux-spec.md](experience-discipline-vnext.ux-spec.md)

## 1. Objective

Make Fettle the versioned, testable source for a risk-proportional experience
discipline that changes coding-agent behavior without forcing ceremonial UX work.
The program must improve detection and handling of material user risk while
reducing false blocks on routine changes.

The target sequence is:

```text
freeze ownership, routing, evidence, and installation contracts
    -> preserve red behavioral scenarios and baseline current disciplines
    -> add the shared experience contract and migrate discipline-ux
    -> migrate planning, UI, UAT, and routing as one compatible release
    -> package and install through explicit host adapters
    -> run blinded held-out evaluation and an advisory pilot
    -> graduate, revise, or reject using frozen thresholds
```

## 2. User Story

As a Fettle operator, I want coding agents to apply UX rigor in proportion to
actual harm, scope, autonomy, and uncertainty, so consequential experiences are
controlled without slowing routine work with invented research and irrelevant
templates.

## 3. Current Baseline

- `discipline-ux` exists only in host-global OpenCode configuration, not in the
  Fettle source tree or wheel.
- `discipline-planning`, `discipline-ui`, and `discipline-uat` duplicate the current
  persona, fixed-state, browser, and evidence assumptions.
- `fettle/discipline_link.py` reads a configurable external skills path for short
  reminders but does not own, validate, or install a discipline bundle.
- `fettle/init_cmd.py` and `fettle/bridge.py` already provide manifest-owned,
  versioned, dry-runnable, non-destructive host installation patterns.
- `fettle/evals_runner.py` and `evals/scenarios/` provide a three-valued behavioral
  harness, but current regex-only checks are vulnerable to keyword compliance and
  no shipped scenario evaluates UX-discipline behavior.
- The current UX skill requires a standalone spec, three generic personas, a
  journey map, universal click/time budgets, ten states called eight, fixed
  cognitive limits, and accessibility scores that exceed what automation proves.

## 4. Research Decision

Independent GLM research, critique, source verification, and red-team review
converged on a compact shared decision contract rather than a richer universal
template. The selected design uses independent harm/scope/autonomy/uncertainty
triggers, proportional artifacts, explicit evidence states, transition-based
failure analysis, surface and authority adapters, and hard gates only for concrete
risk.

Primary references and their authority are frozen in WP-ED-0:

- ISO 9241-11:2018 and ISO 9241-210:2019 for contextual usability outcomes and
  lifecycle human-centered design;
- WCAG 2.2 as the current web conformance baseline, with W3C evaluation and
  disabled-user participation guidance;
- NIST AI RMF 1.0 and AI 600-1 as voluntary risk frameworks, not certification;
- Microsoft Human-AI Interaction Guidelines/HAX as evidence-based guidance;
- GOV.UK Service Standard as whole-service operational guidance, not universal law;
- FTC and EDPB deceptive-design guidance and applicable privacy law, without
  autonomous legal conclusions.

WCAG 3 and APCA remain emerging or supplemental. They cannot replace WCAG 2.2
conformance in this program.

## 5. Authority And Ownership Contract

1. Fettle owns one versioned canonical discipline bundle and its behavioral evals.
2. Host-global skill directories are installed projections, never the source of
   truth and never silently overwritten when foreign or locally modified.
3. A compact shared experience contract owns routing, evidence states, blocking
   gates, criterion shape, and escalation. Phase skills reference it and own only
   phase-specific behavior.
4. Behavioral evaluation measures agent decisions and resulting artifacts. It does
   not become product UAT, accessibility conformance, legal review, or Assurance.
5. Static scenario/schema tests may run in CI. Live model runs remain
   trusted-operator actions with retained provenance and `INDETERMINATE` distinct
   from pass or fail.
6. No aggregate UX score can override a blocking gate. Promotion uses a vector of
   unsafe misses, false blocks, evidence-scope errors, and valid completions.
7. Existing user-owned global skills remain unchanged until an explicit install or
   upgrade action previews the operation and preserves or backs up conflicting data.

## 6. Assumptions And Constraints

1. Audit hardening remains the active P0. No ED implementation starts in its dirty
   worktree. After hardening stabilizes, ED is the next program review requested by
   the operator; that review does not silently displace the declared WLI P0
   trust-repair implementation order.
2. Every work package requires separate authorization. Approval of this plan only
   persists future work.
3. WP-ED-0 must decide whether the whole discipline suite or only the experience
   subset ships first; later packages cannot infer the package boundary.
4. Host support and destination paths differ. Each host requires a capability and
   ownership contract before installation is claimed.
5. Existing global skills are useful baseline subjects but are not copied into the
   repository as authoritative content before licensing, provenance, and ownership
   are reviewed.
6. Live model comparisons are variable and potentially sensitive. Prompts,
   versions, runner identity, attempts, failures, and transcript-retention policy
   must be frozen before the baseline.
7. The current regex evaluator cannot by itself establish semantic compliance.
8. Work-Item Lifecycle Integrity remains separately planned. ED must not depend on
   an unimplemented lifecycle command or change its authority contract.

## 7. Decisions And Tradeoffs

| Approach | Benefit | Risk | Decision |
|---|---|---|---|
| Rewrite only the global UX skill | Fast local effect | Unversioned, unreproducible, and contradictory with adjacent skills | Rejected |
| Add a larger mandatory template | More apparent coverage | More compliance theater and context cost | Rejected |
| Shared compact contract plus optional method/adapter references | One authority with proportional depth | Requires coordinated migration | Selected |
| One blended risk score | Simple display | Hides consequential local changes and incomparable dimensions | Rejected |
| Independent escalation triggers and blocking gates | Preserves distinct risk causes | More routing logic | Selected |
| Regex-only behavioral grading | Uses current runner unchanged | Easy keyword gaming and weak semantic evidence | Insufficient; extend narrowly |
| LLM-only grading | Flexible semantic judgment | Nondeterministic and circular | Advisory cross-review only, never sole verdict |
| Fettle-owned versioned bundle with explicit host projection | Reproducible and testable | Packaging and migration work | Selected pending WP-ED-0 freeze |
| Automatic overwrite during `fettle init` | Simple upgrades | Destroys user customizations and changes behavior unexpectedly | Rejected |

## 8. Work Packages

Every package requires explicit operator authorization. WP-ED-0 and WP-ED-1 are
the only packages eligible for initial authorization after audit hardening.

### WP-ED-0: Freeze Ownership, Risk, And Evaluation Contracts

Priority: P0 after audit hardening. Estimate: 2-3 days. Documentation/schema only.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Inventory current UX, Planning, UI, UAT, routing, global-skill, Fettle reminder, eval, bridge, package, init, and host-install contracts | AUDIT | Review table names each authority, duplicate rule, consumer, destination, and current mutation behavior |
| 2 | Freeze independent harm, scope, autonomy, and uncertainty triggers; L1/L2/L3 outputs; nine blocking gates; exception ownership; and evidence states | SPECIFY | Two reviewers route a frozen calibration set with zero unresolved gate or route differences |
| 3 | Freeze the shared criterion, transition, source-provenance, and evidence-scope schemas | SPECIFY | Every required field has type, applicability, allowed unknown state, and manual recovery |
| 4 | Freeze source-tree ownership, package-data layout, version manifest, host destinations, conflict detection, preview, backup, rollback, and uninstall behavior | DESIGN | Disposable-host matrix proves the design never treats foreign or modified files as Fettle-owned |
| 5 | Freeze evaluator extensions, dev/held-out split, live-run protocol, runner/version identity, transcript privacy, sample size, and promotion thresholds | SPECIFY | Pre-registered protocol distinguishes fail from indeterminate and forbids tuning on held-out cases |
| 6 | Freeze authoritative source ledger and review cadence | REVIEW | Each normative, standard, guidance, legal, and emerging source has date, scope, non-claim, and owner |

Exit: one reviewed decision record defines ownership, routing, schemas, installation,
evaluation, thresholds, and unresolved host limits. No active skill changes.

### WP-ED-1: Preserve Red Behavioral Corpus And Baseline

Priority: P0 after WP-ED-0. Estimate: 3-5 days. Eval fixtures and baseline only.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing UX-discipline scenarios for proportional cosmetic work, unsupported personas, destructive action, derived transitions, evidence-scope integrity, accessibility limits, CLI adaptation, provenance conflict, agent authority, privacy/deception, and cross-channel continuity | TDD | `python -m fettle.evals_runner validate` accepts all scenarios while the current discipline fails the pre-registered behavioral expectations |
| 2 | Extend the scenario schema with expected route, triggered gates, forbidden claims, minimum artifact, and adversarial variant | CODE | Unit tests reject missing, unknown, duplicate, unsafe-path, and wrong-type fields with exact errors |
| 3 | Add deterministic structured-output and rubric checks without permitting arbitrary scenario code | INTEGRATION | Fake-runner tests prove semantic fields are graded, path containment remains fail-closed, and keyword-only transcripts fail |
| 4 | Preserve legacy scenario compatibility or record and execute a bounded schema migration | REGRESSION | All existing shipped scenarios retain their prior verdicts and three-valued semantics |
| 5 | Run and retain the current-discipline development baseline using the frozen trusted-run protocol | LIVE | Report includes runner/model/version, prompt digest, attempts, per-scenario verdict, false-block/unsafe-miss classification, and every indeterminate run |
| 6 | Seal held-out prompts and graders before skill authoring | REVIEW | Access-controlled digest inventory and reviewer record show held-out content was not used for prompt tuning; CI verifies digests without exposing restricted prompts when they cannot be committed safely |

Exit: the current discipline has a reproducible red baseline and the held-out corpus
is sealed before replacement text is authored.

### WP-ED-2: Implement Shared Contract And Migrate UX

Priority: P0 after WP-ED-1. Estimate: 3-5 days. Separate behavior-change
authorization required.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing tests for bundle structure, single normative owner, rule references, line budget, source ledger, and absence of retired absolutes | TDD | Focused tests fail before the shared contract and migrated UX skill exist |
| 2 | Add the compact shared experience contract, method registry, surface adapters, and controlled overlays to the Fettle-owned bundle | CODE | Static validation finds one owner for every gate and no contradictory duplicate authority |
| 3 | Rewrite `discipline-ux` as router, outcome/transition analysis, method selection, and handoff guidance | CODE | The skill stays within the frozen context budget and does not mandate personas, universal states, click/time limits, or unsupported scores |
| 4 | Exercise L1, L2, and L3 development scenarios with the bundled contract | INTEGRATION | Agent outputs match route, gate, artifact, and forbidden-claim expectations without relying on exact wording |
| 5 | Preserve named failures from the current discipline audit | REGRESSION | Cosmetic, wire-transfer, Playwright-time, axe-conformance, and destructive-CLI scenarios produce the expected corrected decisions |
| 6 | Run the development corpus through each authorized runner, including missing, malformed, and unavailable evidence | LIVE | Per-runner results meet frozen dev thresholds; bad conditions remain non-pass with `status=unknown` or `INDETERMINATE`; failures are never promoted by an empty report |

Exit: the shared contract and UX skill pass development scenarios without changing
global host configuration.

### WP-ED-3: Migrate Planning, UI, UAT, And Routing Atomically

Priority: P0 after WP-ED-2. Estimate: 3-5 days. One compatibility change set.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing cross-skill contract tests for route consumption, criterion traceability, evidence classes, and retired duplicate rules | TDD | Tests expose current persona/state/browser/score contradictions before migration |
| 2 | Update `using-disciplines` and Planning to consume the selected route and require only the artifact chosen by the shared contract | CODE | L1 work can proceed without a standalone UX spec; L3 unknowns and missing ownership still block |
| 3 | Update UI to own visual realization and design-system fit without imposing a framework, aesthetic, density, theme, or reference app | CODE | Web, CLI, and non-trading fixtures receive surface-appropriate treatment; visual evidence is not called usability proof |
| 4 | Update UAT to trace controlled criteria and separate automated, manual, accessibility, human, runtime, and unknown evidence | CODE | A clean E2E/axe result cannot become human task success or WCAG conformance |
| 5 | Exercise the complete UX-to-plan-to-UI-to-UAT handoff | INTEGRATION | L1 and L3 fixtures retain route, gates, semantic IDs where required, owners, and evidence scope across every phase |
| 6 | Preserve runtime-boundary, timeout, completion, and spec-semantic discipline regressions | REGRESSION | Existing named discipline scenarios retain their required non-pass and recovery behavior |
| 7 | Run the migrated suite with authorized agents in an isolated worktree and inject one unavailable-evidence path | LIVE | No active global skill changes; report cross-skill contradictions, context size, unsafe misses, false blocks, and indeterminate runs; unavailable evidence produces `status=unknown` rather than a healthy or passing claim |

Exit: one coherent versioned discipline suite passes cross-phase development evals.

### WP-ED-4: Package And Install Without Overwriting User Work

Priority: P1 after WP-ED-3. Estimate: 3-5 days. Separate installation
authorization required.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing package, manifest, dry-run, conflict, upgrade, rollback, uninstall, and foreign-file preservation tests | TDD | Source, wheel, and fake-home tests fail before discipline assets are published or installed |
| 2 | Package the versioned discipline bundle and integrity manifest using the frozen ownership boundary | CODE | Built wheel contains every declared file and no undeclared global configuration |
| 3 | Add explicit preview/status/install/upgrade/uninstall operations or the smaller frozen command surface | CODE | Default `fettle init` remains non-destructive unless WP-ED-0 explicitly selected opt-in init integration |
| 4 | Add host adapters only for destinations whose capability and ownership contracts are verified | INTEGRATION | Fake Claude, OpenCode, Codex, and Gemini homes preserve foreign files, detect local modification, and report unsupported hosts truthfully |
| 5 | Preserve bridge, workflow, hook, and configuration installation behavior | REGRESSION | Existing `test_init_cmd`, bridge, workflow, config, and installed-artifact tests retain prior behavior |
| 6 | Build and inspect an installed wheel in a fresh isolated home | LIVE | Preview matches mutation; install validates digests; rerun is idempotent; forced conflict is non-pass; rollback restores the prior owned version |

Exit: operators can inspect and explicitly install a reproducible bundle without
silent mutation or loss of user-owned skill content.

### WP-ED-5: Run Blinded Held-Out Evaluation And Advisory Pilot

Priority: P1 after WP-ED-4. Estimate: 5-8 days plus a 14-day advisory pilot.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add failing tests for blinded assignment, digest verification, missing/partial result handling, and pilot-report completeness | TDD | Tests fail before the held-out comparison and pilot evidence collector exist |
| 2 | Run the sealed held-out corpus against baseline and candidate under the frozen runner protocol | VERIFY | Paired report retains every prompt digest, runner/version, attempt, verdict, rubric dimension, and indeterminate result |
| 3 | Independently review a blinded sample for unsafe misses, false blocks, invented evidence, evidence-scope errors, and artifact burden | REVIEW | Two reviewers resolve disagreements without seeing baseline/candidate identity |
| 4 | Exercise installed skills across every verified host adapter and surface type | INTEGRATION | Installed-source digest matches the candidate and host-specific outputs preserve the shared gates |
| 5 | Preserve the highest-consequence held-out failures as release regressions after evaluation closes | REGRESSION | Future candidate runs cannot omit destructive, privacy, accessibility, or agent-authority behavior; missing or partial held-out results remain `INDETERMINATE` rather than pass |
| 6 | Run a 14-day advisory pilot without replacing active global skills by default and inject one unavailable-evidence interval | LIVE | Retained report records invocations, route distribution, blocks, overrides, false blocks, unsafe misses, recovery time, context cost, and user feedback; the unavailable interval reports `status=unknown` and cannot improve promotion metrics |

Exit: held-out and pilot evidence meet frozen thresholds or the candidate remains
uninstalled and the failed hypotheses are retained.

### WP-ED-6: Decide Graduation And Maintain The Discipline

Priority: P2 after WP-ED-5. Estimate: 1-2 days plus quarterly review.

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Compare the evidence vector with pre-registered thresholds and blockers | VERIFY | Decision separates unsafe misses, false blocks, valid completions, evidence-scope errors, indeterminate runs, and context cost |
| 2 | Record `GO`, `REVISE`, or `NO_GO` without averaging away any blocker | REVIEW | Decision cites exact held-out and pilot evidence, residual risks, owner, and rollback |
| 3 | If `GO`, perform a previewed opt-in installation and retain the previous owned bundle | LIVE | Installed manifest validates, host restart/reload is documented, smoke scenarios pass, and rollback is exercised |
| 4 | Schedule source and incident review without silently changing normative behavior | MONITOR | Quarterly record checks standards currency, rule use, false positives, missed risks, and whether any unevaluated rule should be removed |

Exit: the candidate is either explicitly graduated with rollback evidence, returned
for bounded revision, or rejected while the current installed disciplines remain.

## 9. Behavioral Evaluation Matrix

The frozen corpus must include at least these independent cases:

| Case | Expected route or gate | Prohibited shortcut |
|---|---|---|
| Existing button spacing | L1 | Full persona/journey/spec ceremony |
| Admin view without research | Uncertainty visible | Invented personas, demographics, or emotions |
| Workspace deletion | L3 harm and recovery | Generic confirmation as sufficient control |
| Retriable upload | Derived transitions | Universal state checklist |
| Playwright checkout timing | Evidence-scope gate | Human task-time or completion-rate claim |
| Axe-clean modal | Accessibility evidence scope | WCAG conformance claim from automation |
| Destructive CLI command | CLI adapter plus consequence gates | Browser/click vocabulary |
| Conflicting analytics/interviews | Provenance and escalation | Silent source selection or false consensus |
| Draft-and-send refund assistant | Prepare/act/commit separation | Treating generation and execution alike |
| Prechecked marketing consent | Privacy/deception gate | Consent inferred from text presence |
| Mobile-to-desktop identity flow | Cross-channel transition model | Independent screen-only review |
| Existing visual redesign request | UI method selection | Hard-coded shadcn, Tremor, trading density, or dark-first design |

Adversarial variants remove explicit risk words, include requests to skip UX, or
offer misleading green automated evidence. Graders assess decisions and resulting
artifacts, not the presence of favored terminology. Deterministic fixtures include
paraphrases that preserve the same false claim and harmless uses of the prohibited
words; all must receive the expected result before a semantic rubric is accepted.

## 10. Evaluation And Promotion Contract

WP-ED-0 freezes numeric thresholds before baseline execution. At minimum:

- zero unsafe passes on destructive, privacy, accessibility-task-blocking, and
  act/commit authority cases;
- zero false conformance or human-outcome claims from automation-only evidence;
- candidate false-block rate on L1 cases no worse than the frozen ceiling and
  lower than baseline;
- candidate valid-completion rate higher than baseline on both development and
  held-out sets;
- no regression in existing runtime-boundary, completion-timeout, or semantic-audit
  scenarios;
- no held-out tuning, dropped failures, or counting `INDETERMINATE` as pass;
- installed content digest equal to the evaluated candidate.

The decision reports a vector, confidence limits where sample size permits, and
raw counts. No weighted score or majority vote can override a safety blocker.

## 11. Blast Radius

Expected new versioned surfaces, subject to WP-ED-0 naming:

- `skills/experience-contract/`
- `skills/discipline-ux/`
- `skills/discipline-planning/`
- `skills/discipline-ui/`
- `skills/discipline-uat/`
- compact method, surface, and authority references
- `evals/scenarios/experience-*/`

Expected implementation owners:

- `fettle/evals_runner.py`
- `fettle/bridge.py` or a separately frozen discipline-bundle publisher
- `fettle/init_cmd.py`
- `fettle/cli.py` only if WP-ED-0 selects an explicit command
- `fettle/config.py` and `fettle/config_schema.py` only if configuration is needed
- `fettle/discipline_link.py` only if reminder resolution changes
- `pyproject.toml` and `MANIFEST.in`

Expected tests and release surfaces:

- `tests/test_evals_runner.py`
- new discipline contract and bundle tests
- `tests/test_init_cmd.py`
- `tests/test_discipline_link.py`
- bridge, installed-artifact, workflow, CLI, package, and release tests as affected
- `.github/workflows/ci.yml` and `.github/workflows/release.yml` only after separate
  boundary authorization

Before implementation, refresh `kgraph index` and run `kgraph impact` for the exact
selected owners. Current planning impact is stale because the worktree is changing;
the observed direct implementation consumers include `fettle.cli.cmd_init` and
`fettle.cli.cmd_workflows`.

## 12. Security, Privacy, And Rollback

- Scenario paths remain contained; scenarios cannot execute arbitrary embedded code.
- Live evals run only in trusted isolated worktrees with explicit runner selection.
- Transcripts are local, ignored by default, scrubbed before sharing, and governed by
  the WP-ED-0 retention decision.
- Installers reject symlink/junction escapes, unsafe relative paths, malformed
  manifests, digest mismatches, and foreign destinations.
- Dry-run has zero filesystem mutation. Installation never follows a modified file
  with blind overwrite.
- Rollback restores the prior manifest-owned version; foreign files are never
  deleted as rollback. One immediately prior owned version is the minimum retained
  rollback depth. Any deeper rollback is an explicit sequence of verified version
  transitions, not an inferred guarantee.
- No host, model, standard, legal regime, or accessibility conformance is claimed
  beyond directly verified scope.

## 13. Success And Stop Conditions

Success requires:

- one canonical versioned contract with no contradictory phase copies;
- behavioral evidence that detects ritual over-processing and unsafe omission;
- proportional L1 behavior and controlled L3 behavior across supported surfaces;
- truthful evidence scope and explicit unknowns;
- non-destructive, reversible, integrity-checked distribution;
- held-out and pilot thresholds met without safety blockers;
- no regression to Fettle's current hooks, bridge, completion, UAT, or release
  authority.

Stop, reject, or narrow if the approach requires invented user evidence, an opaque
UX score, LLM judgment as sole authority, live-agent execution in public CI, silent
global configuration mutation, destructive skill upgrades, natural-language legal
classification, or a context payload that causes measured regression without
offsetting safety benefit.

## 14. Delivery Sequence And Authorization

1. Finish or stabilize audit hardening. Do not implement ED in the current dirty
   worktree.
2. Review this package at the next decision checkpoint after hardening. Any
   authorization of WP-ED-0/WP-ED-1 must also state whether it waits for, or is
   explicitly coordinated with, the declared WLI P0 trust-repair sequence.
3. Separately authorize WP-ED-2 and WP-ED-3 after the red baseline and held-out seal.
4. Separately authorize WP-ED-4 installation work after the coherent bundle passes
   development evaluation.
5. Run WP-ED-5 before replacing active host-global disciplines.
6. Authorize installation only through the WP-ED-6 `GO` decision.
7. Reconcile scheduling with Work-Item Lifecycle Integrity before either program
   edits shared tests, CI, release, plan index, or TODO surfaces. WP-ED-3 or later
   may edit shared CI or release files only after WP-WLI-3, or under an
   operator-approved coordination record that assigns exact file and gate ownership.

## 15. Planning Compliance

- Phase -1 research: completed through independent GLM research, current-skill
  critique, source verification, and proposal red-team; findings are retained in
  this plan and linked contract.
- Phase 0 experience contract: complete in the linked UX contract.
- Phase 0.5 visual UI: not applicable to this planning-only methodology package.
- Phase 1 assumptions, tradeoffs, work packages, estimates, blast radius, security,
  rollback, and success/stop conditions: complete.
- Phase 3 behavioral and Phase 3.5 acceptance scenarios: specified before code.
- This document authorizes planning records only. Every work package and any change
  to global skills requires an explicit operator decision.
