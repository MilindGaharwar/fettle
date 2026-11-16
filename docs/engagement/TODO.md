# Engagement To-Do (living)

Status: `[ ]` open · `[~]` in progress · `[x]` done · `[?]` blocked on a decision

## Phase A — Orientation (current)
- [x] A1. Read repository end to end (core spine + delegated sectional reads)
- [x] A2. Write repository orientation summary → 01-orientation.md
- [x] A3. Pillar-by-pillar gap assessment → 02-pillar-gap-assessment.md
- [x] A4. Open questions + proposed sequencing → 03-open-questions-and-sequencing.md (presented)
- [x] A5. Collaborator invite — CLOSED: Milind will add Prerit manually via UI
      (API needs username; email has no public match).

## Phase B — Work-package analysis & design (one doc + work note each)
- [x] B1. WP1 Opus-5 readiness → 06-wp1-frontier-agent-readiness.md (review + backlog)
- [x] B2. WP2 Functional testing architecture → 08-stage3-spec-format-and-wp2.md (implemented, Stage 3)
- [x] B3. WP3 Agentic UAT design (highest priority) → 10-stage5 doc (implemented, Stage 5)
- [x] B4. WP4 Configuration / feature dependency model → 07-wp4-config-dependency-model.md (implemented, Stage 2)
- [x] B5. WP5 Coordination substrate evaluation → 09-stage4 doc (implemented, Stage 4)
- [x] B6. WP6 Wayfinder review → 04-wp6-wayfinder-review.md
- [x] B7. WP7 Git worktrees design → 09-stage4 doc (implemented, Stage 4)
- [x] B8. WP8 Adjacent projects review → 05-wp8-adjacent-projects.md
- [x] B9. WP9 Whole-system consistency pass (S7.2 config debts; S7.3 hygiene)
- [x] B10. Consolidated prioritised roadmap with WP dependencies (docs/ROADMAP.md, 2026-08 section)

## Phase C — Implementation (Stage 0 underway; stages approved 2026-08-01)
- [x] C0. Stage 0 failure-visibility hardening (complete)
  - [x] S0.1 dispatcher trace events + repeated-failure escalation (13 tests)
  - [x] S0.2 doctor/report surfacing + trace-writability probe (10 tests)
  - [x] S0.3 scanner tool-error surfacing (security_review, threat_model,
        pr_review, cargo check) — exit 2 / incomplete banners / trace entries
  - [x] S0.4 health_telemetry write-failure visibility (warn-once stderr)
  - [x] S0.5 fail-closed posture: mcp_trust denies on corrupt allowlist
- [x] C2. Stage 2 — WP4 config dependency model (MODE_ENUMS, RANGES,
      DEPENDENCIES, doctor check, schema regeneration; 17 tests)
- [x] C3. Stage 3 — spec format + WP2 seed
  - [x] S3.1 spec_model parser/lint + `fettle spec lint|list` (26 tests)
  - [x] S3.2 scenario coverage + `fettle spec coverage` evidence (14 tests)
  - [x] S3.3 `[gates.bdd]` scenario-coverage gate (10 tests)
  - [x] S3.4 docs + work note
- [x] C4. Stage 4 — agent infrastructure
  - [x] S4.1 fettle.runners protocol + claude adapter (12 tests)
  - [x] S4.2 worktree spine + .git-file audit (16 tests)
  - [x] S4.3 work items + claims + [gates.claims] (21 tests)
  - [x] S4.4 docs + work note
- [x] C5. Stage 5 — WP3 agentic UAT (highest priority)
  - [x] S5.1 [uat] config + surface detection + capability probe
  - [x] S5.2 session core (worktree isolation, persona prompt, runner)
  - [x] S5.3 reconciler (CONFIRMED/CONTRADICTED/BLOCKED/UNOBSERVED verdicts)
  - [x] S5.4 manual fallback walkthroughs + `fettle uat attest`
  - [x] S5.5 web surface — playwright driving + consent + redaction shipped
        (P74); axe-core deep scan and per-scenario screenshots tracked in P74
        follow-ups (docs/backlog/p74-web-surface-driver.md)
  - [x] S5.6 docs + work note
- [x] C6. Stage 6 — semantic layer thin slice
  - [x] S6.1 link fusion + `fettle links <id>|--orphans`
  - [x] S6.2 graphify consume-optional enrichment + docs
- [x] C7. Stage 7 — WP9 consistency + roadmap
  - [x] S7.1 [gates.verify] + `fettle verify` (closes WP2 execution gap)
  - [x] S7.2 config debts: subagent.mode removed, complexity mode
        unified, docs 'soft' deprecated, stale comments fixed
  - [x] S7.3 hygiene: plan docs → docs/archive/ (frozen-status banner),
        work notes unified under docs/engagement/worknotes/, TODO current
  - [x] S7.4 docs (verify gate) + consolidated roadmap (B10) + work note
- [x] C8. Stage 8 — remote CI verification gate (incident-driven)
  - [x] S8.0 incident root-cause: CI red ×8 since Stage 3 (subprocess CLI
        tests needed editable install) — fixed in ci.yml, verified green
  - [x] S8.1 [gates.ci]: push recorder (PostToolUse) + Stop stamp check
        + `fettle ci status|wait` (gh CLI, REST fallback) (31 tests)
  - [x] S8.2 failure ingest wired: red run → ci_ingest/ci_diagnose →
        reproduction command in the gate message
  - [x] S8.3 docs + work note + dogfood (enforce mode in .fettle.toml)
- [x] C9. Release v1.3.0 “Evidence Loop” — tagged, published to PyPI
      (finefettle 1.3.0); release.yml editable-install fix (0f94948);
      remote CI verified green end to end
- [x] C10. Stage 10 — WP-146 compliance evidence
  - [x] S10.1 fettle/compliance.py: canonical rule→CWE/ASVS/SOC 2 mapping
        (23 bundled rules + ruff S-codes via security_review._CWE_MAP)
  - [x] S10.2 metadata.compliance tags mirrored in all three rule packs,
        YAML↔Python sync pinned by test
  - [x] S10.3 `fettle report --compliance [--json]` evidence table
        (fired/blocked per control from the audit trail; unmapped surfaced)
  - [x] S10.4 tests (test_compliance.py) + docs + work note
- [x] C11. Stage 11 — WP-147 supply-chain posture
  - [x] S11.1 release.yml: Sigstore/SLSA provenance (attest-build-provenance)
        + CycloneDX SBOM from the smoke venv + GitHub release w/ artifacts
  - [x] S11.2 fettle/supply_chain.py: PINNED_TOOLS canonical home +
        RECORD hash verification (stdlib-only, offline)
  - [x] S11.3 `fettle doctor --verify-hashes` (tampering = required
        failure; drift = warn; not-installed = skipped, surfaced)
  - [x] S11.4 tests (test_supply_chain.py) + docs + work note
- [x] C12. Stage 12 — WP-148 opt-in telemetry (privacy-first)
  - [x] S12.1 fettle/telemetry.py: payload schema fettle-telemetry/1
        (anonymous counters only, key set pinned by test)
  - [x] S12.2 org-only opt-in: enabled honored solely from the digest-pinned
        [extends] policy; repo-level enable ignored + surfaced; default OFF
  - [x] S12.3 `fettle telemetry status|show|send` + [telemetry] in schema
        + docs/CONFIG.md section
  - [x] S12.4 tests (test_telemetry.py, incl. live-HTTP send) + work note
- [x] C13. Stage 13 — full hook parity: codex / gemini / opencode
  - [x] S13.1 inbound translators fettle/agents/{codex,gemini}.py +
        four-agent conformance fixtures (opencode already shipped, WP-140)
  - [x] S13.2 event-correct output wire: permissionDecision PreToolUse-only,
        Stop/SubagentStop without hookSpecificOutput (Codex strict parser),
        top-level decision/reason on every block; opencode plugin updated
  - [x] S13.3 fettle init: ~/.codex/hooks.json + ~/.gemini/settings.json
        registration (idempotent merges; gemini timeouts in ms;
        codex features.hooks surfaced as action)
  - [x] S13.4 outbound runners codex/gemini/opencode (shared subprocess
        core, fail-visible), registry + doctor/UAT probes, FETTLE_EVAL_RUNNER
  - [x] S13.5 tests + docs + work note (capability matrix)

## Phase D — Post-v1.8 trust evolution

### Post-hardening strategic sequence (2026-10-11)

North star: reduce workslop across AI work. Fettle makes readiness claims
accountable to evidence. Code is the first domain, not the boundary, and remains
the first proof: preserve the coding investment, accepted evidence, and required
regression gates as generalization proceeds. This is a direction, not a claim of
measured effectiveness across domains.

Generalize the assurance contract, not the domain validators: authorized scope,
acceptance criteria, provenance, evidence, uncertainty, and acceptance authority.
Reuse existing Assurance and portable evidence contracts; create no second
quality authority. Domain-specific checks must earn their own evidence.

Only this planning update is authorized. All new discovery, research, skill or
discipline revision, implementation, evaluation, and spending wait until required
audit-hardening acceptance is evidenced and confirmed by the operator. A finished
mutation run or green ordinary CI alone does not complete hardening. AH07 remains
unaccepted. Existing package gates remain binding; M-NC1 uses the bounded approval
below, not permission inferred from its backlog position.

1. [ ] **Repair lifecycle trust before expanding scope.** Review and authorize
      WP-WLI-0/WLI-1 first, then separately gate WLI-2 through WLI-4. Preserve the
      historical contradiction corpus, prove invalid completion claims fail, and
      enforce validation in CI/release preflight. Exit: exact-candidate evidence
      supports lifecycle decisions; missing or contradictory evidence cannot pass.
2. [ ] **Carry skills and disciplines forward with evidence.** At the
      post-hardening DS/ED checkpoint, retain accepted coding rules and lessons,
      separate shared QA principles from task-specific checks, and resolve any
      demonstrated WLI-critical conflict before WLI-2. Scope the first revision to
      what M-NC1 needs; whole-suite research or rollout is not a default dependency.
      Exit: named gaps, retained coding controls, and an approved revision/evaluation
      route. A planning review does not authorize active global skill replacement.
3. [ ] **Run one bounded non-code milestone, M-NC1.** After P0 trust repair,
      discover and freeze a source-table-to-XLSX workflow, then build the minimum
      advisory verification and recipient receipt using existing CLI/hook paths.
      Stage skill/discipline candidates with the pilot, retaining code as the first
      proof and regression control. Exit: frozen scope, authority, budget, UX/UAT,
      supported formulas, validators, and independent evaluation protocol.
4. [ ] **Measure, then decide.** Compare baseline, self-check instruction, and
      Fettle advisory verification on independently graded held-out tasks. Count
      all assigned tasks, false-ready outcomes, abstention, and total human effort.
      Exit: retained evidence supports continue, revise, or stop within declared
      thresholds. Null results can complete the experiment, not justify promotion.
5. [ ] **Expand only where results justify it.** Revisit broader Review, Add-in,
      portable handoffs, adoption/recovery work, and discipline rollout against
      demonstrated gaps and their own approval gates. Retain their existing
      integrity, benefit, cost, and false-ready criteria. Research briefs, extra
      hosts, MCP, and a physical core/pack split remain deferred. Never relax
      required policy, evidence, or safety gates to improve cost.

### Sequencing decision (2026-11-14)

Recorded by the owner on 2026-11-14, after the full audit of `main` at
`1ffff5c`. This block governs wherever an item below says to wait for
audit-hardening acceptance, AH07, or the D4 run sequence: audit hardening was
accepted on 2026-10-26 (P0-1), and D4 closes with the D4 close-out pull
request on the evidence already retained. The items below are otherwise kept
as written; each still needs its own authorisation before it starts.

Order of work:

1. **D4 close-out.**
2. **Trust remediation TR-0 to TR-4** (Phase E): the P0 defects on the shipped
   hook path, the control plane, verification and first run.
3. **Trust remediation TR-5, the trust root.** The work-item lifecycle
   integrity packages (P0-2 to P0-7) are delivered inside TR-5 and do not run
   as a separate program: WP-WLI-0 and WP-WLI-1 supply the frozen schema and
   the red corpus, and WP-WLI-2 to WP-WLI-4 are implemented with TR-5's
   completion-validation changes, using the lifecycle plan as their
   specification.
4. **Disciplines** (P0-2a, P1-DS, P3-ED). Direction decided 2026-11-14; the
   inventory is in
   [discipline-inventory-2026-11-14.md](../discipline-inventory-2026-11-14.md).
   - After TR-3 merges: a narrow update in the disciplines repository, about
     seven changes, each with a replay case from the November sessions.
   - After TR-4 merges: bring the trimmed set into Fettle as an opt-in pack,
     installed by `fettle init` on request and never by default, with a test
     that every command and gate a skill names exists. This is WP-ED-4 without
     the pilot.
   - The sealed evaluation, held-out sets and advisory pilot of the DS and ED
     plans are deferred. They run only if the narrow update proves
     insufficient.
5. **Trust remediation TR-6 to TR-9.**
6. **M-NC1** (P1-NC1), the first non-code milestone, after TR-5 merges.
7. **P0-XE, P0-IL, P2-FM and P3** remain proposed. None starts before TR-5
   merges. The P0-XE mechanisms are reviewed together with the mutation
   decisions D1 to D5 in TR-8.

### Current priority order

Worklog (2026-10-16): approved documentation-only extension of P2-FM using
*Formal Methods: An Appetizer*. Retained capsule conformance as the first slice;
added separately gated completion-obligation, conservative evidence-aggregation,
and authority-flow packages in the existing plan and checklist below. Current
completion validation still reports AH07 blocked. Preserve P0-IL, WLI, DS/ED,
M-NC1's first-expansion position, all parked models and existing acceptance gates.
No Fettle code, test, model, configuration, CI or active skill change is authorized
by this planning update; no new runtime claim is complete.

Worklog (2026-10-12): approved planning for incident learning as P0-IL. Added a
seven-package plan with file ownership, evidence/privacy contracts, manual-first
delivery, focused verification, CLI UX/BDD and measured pilot criteria. Preserve
hardening and lifecycle gates; planning does not authorize execution or declare
any incident, improvement or milestone complete.

- [x] P0-1. Audit hardening accepted and merged through tree-equivalent squashes:
      PR #46 source `9791109` → `2605978`, then PR #47 source `a572f80` →
      `023f9b3`. Exact-tip main CI passed after each merge. Full mutation
      qualification remains `CLOSED_NON_PASS` and is not implied by this closure.
- [x] P0-ERA. Immediately after the hardening merge and before any D4 run:
      expensive-run admission (docs/backlog/expensive-run-admission.md). Gate job
      the shard fan-out `needs:`, running the real prepare→shard→aggregate path
      on a two-shard fixture plus the full suite in the runner environment;
      digest-bound reuse of unchanged shard reports on the advisory path; per-shard
      projection from the observed runner ledger only. Recorded 2026-10-25 after
      three commit-bound ~12 h runs were lost to offline-reproducible defects.
      No scope, pass-semantics, or qualification change.
- [ ] P0-TR. Trust remediation, from the 2026-11-13 full audit
      (docs/trust-remediation-implementation-plan.md). Authorized by the owner
      on 2026-11-14: local implementation may begin before D4 closes; nothing
      from this program merges before the D4 close-out does.
      Packages run in the order listed under Phase E. Owner decisions recorded
      2026-11-13: hardening first; README claims are made true, not reduced;
      the trust root is provider-neutral; the implementing agent opens each
      pull request and the independent reviewer verifies and merges it.
- [ ] P0-XE. After D4 run 3 is terminal and validated, before any D4 baseline
      or ratchet proposal: execution-evidence hardening from the D4 lessons
      ([detailed plan](../d4-lessons-implementation-plan.md),
      [backlog item](../backlog/d4-lessons-execution-evidence.md)). Seven
      container- or timing-specific defects reached the CI gate on first
      execution between 2026-11-03 and 2026-11-07; one cost 256 failed jobs.
      In order: XE-2 classify `tool_error` shards by cause; XE-6 watch-file
      scope-widening notice; XE-3 timing-sensitive-test pack; XE-5 container-job
      pack; XE-4 retained-output rule; XE-1 never-executed-workflow Stop
      advisory; XE-7 playbook pattern. Advisory only; no new required gate, no
      pass-semantics, waiver, D4-criteria, or Docker-dependency change. XE-2 may
      be prepared on a branch during the freeze; nothing merges while `main` is
      frozen for the D4 sequence. Planning recorded 2026-11-07; implementation
      is not authorized by this entry.
- [?] P0-IL. High priority: establish an evidence-linked incident learning and
      improvement roster so repeated mistakes become reviewed, verifiable product
      improvements. [Detailed implementation plan](../incident-learning-implementation-plan.md),
      [UX/BDD contract](../incident-learning.ux-spec.md), and
      [CLI presentation](../incident-learning.ui-spec.md). Planning and this P0
      scheduling entry are approved (2026-10-12); implementation is not.
      First authorize WP-IL-0 to preserve approved incident evidence and create a
      manual roster using existing work items. Concurrent documentation-only
      preservation requires explicit source-access and non-overlap approval;
      otherwise start at the first post-hardening checkpoint, before optional
      expansion. Freeze WP-IL-1 with WLI-0/WLI-1. Runtime IL-2 through IL-4 wait
      for hardening acceptance and the approved WLI parser/evaluator boundary;
      closure qualification requires WLI-4. Then separately gate the local pilot
      and rollout (IL-5/IL-6). Keep code and non-code incidents in scope without
      imposing coding validators on other tasks. Measure time to triage and to
      a verified regression, human effort, recurrence and false grouping, not
      proposal count alone. No second ledger/completion authority, automatic
      policy or skill promotion, remote run, model call or new spending follows
      from this entry. It adds no AH01-AH07 criterion and does not change M-NC1's
      position as the first new domain workflow.
      Apply the planned [Experience Discipline vNext UX contract](../experience-discipline-vnext.ux-spec.md):
      justified L3 routing, actual actors, derived transitions/recovery, scoped
      claim states, shared blocking gates and IL-UX-01 through IL-UX-12 owner/evidence
      traceability. Do not require generic personas, a fixed state count or arbitrary
      time budgets. Freeze against the accepted contract at IL-1 without requiring
      global skill installation. Before relying on graph impact, verify index
      freshness; use the plan's authorized no-embedding refresh and recheck path,
      or document equivalent source inspection and unresolved coverage. A stale
      result never means no impact. This follow-up changes planning only.
- [?] P0-2. Review and approve the Work-Item Lifecycle Integrity planning package;
      if approved, authorize only WP-WLI-0/WLI-1 first.
- [?] P0-2a. At the next post-hardening decision checkpoint, review the
      [Discipline Suite Review Plan](../discipline-suite-review-plan.md) with
      Experience Discipline vNext, after current hardening is complete. Broaden
      the coding-centric plan using B0-B5 below before authorizing WP-DS-0/ED-0:
      Fettle's intended scope is QA for AI-agent activities across task types,
      not just software development. WLI-0/WLI-1 keep trust-repair priority.
      Code remains the first proof: preserve accepted coding disciplines and
      verification controls. Stage cross-task revisions with M-NC1 and later
      workflows; do not require broad suite replacement for the bounded pilot.
      This entry records deferred work only; it authorizes no research execution,
      active skill, live eval, package, installer, host, CI, release, mutation run,
      or spending change. Await the operator's hardening-agent report.
- [ ] P0-3. WP-WLI-0 — freeze lifecycle schema, UX contract, corpus inventory,
      persistent `claimed` disposition, and consumer behavior.
- [ ] P0-4. WP-WLI-1 — preserve the committed P46 contradiction and full red
      matrix before editing the live corpus.
- [?] P0-5. Separately authorize WP-WLI-2 strict validator implementation after
      WP-WLI-0/WLI-1 pass. Review quality-critical discipline findings and explicitly
      decide any demonstrated blocking conflict before authorization; record the
      verification route without waiting for a whole-suite rollout by default.
- [ ] P0-6. WP-WLI-3 — reconcile the live corpus only after the implemented
      validator proves the historical red corpus fails.
- [ ] P0-7. WP-WLI-4 — require lifecycle and completion validation in blocking CI
      and release preflight; verify external protection or report `UNKNOWN`.
- [?] P1-NC1. First expansion priority after P0: the bounded spreadsheet milestone
      below, including discovery, minimum advisory build, independent measurement,
      and a continue/revise/stop decision. No discovery runs alongside hardening.
      WP-WLI-4 and the quality-critical discipline checkpoint precede this work;
      the full WP-WLI-6 observation window is not an automatic prerequisite.
- [?] P1-DS. Alongside M-NC1, revise only demonstrated skill/discipline gaps in
      isolated, versioned candidates under existing DS/ED ownership. Verify coding
      behavior is retained before freezing spreadsheet evaluation. No production
      or global installation or whole-suite rollout is included.
- [?] P1. Consider WP-WLI-5 structured projection validation separately after
      lifecycle enforcement is stable. P57 remains independently gated.
- [ ] P2. Run WP-WLI-6 measurement after enforcement. P34 passively accumulates
      qualifying runs; the three unimplemented P43 models remain parked.
      Keep WLI-6 measurement scoped to lifecycle enforcement: contradictions
      detected or missed, bypasses, recovery effort, and independently adjudicated
      false blocks and their delay. A clean merge alone does not prove a false
      block. Broader qualification-cost measurement belongs to B3/B4; P2-FM
      measures its own conformance claim separately. Observation can continue
      alongside M-NC1; new qualification campaigns need their own scope decision.
- [?] P2-FM (deferred). Reconsider the bounded P43 model-to-implementation
      conformance pilot after M-NC1's decision, subject to required hardening
      acceptance and WP-WLI-4. Deferral reflects opportunity cost, not irrelevance:
      Policy Capsule monotonicity matters to code and non-code alike. A demonstrated
      trust-critical gap can justify an explicitly approved earlier reprioritization.
      [Detailed plan](../formal-verification-conformance-plan.md),
      [UX/BDD contract](../formal-verification-conformance.ux-spec.md), and
      [CLI presentation](../formal-verification-conformance.ui-spec.md).
      Start with the existing Policy Capsule monotonic-enforcement invariant;
      freeze its scope, assumptions, implementation mapping, fault corpus, and
      evidence contract before separately authorizing tests or runtime changes.
      Then use the FM-6 decision to consider completion obligations (FM-7/FM-8),
      conservative evidence aggregation (FM-9), authority non-interference (FM-10),
      and per-claim qualification (FM-11), in that order. The
      [package checklist](#formal-assurance-continuation) records all activities;
      the new internal checks do not become prerequisites for P0 or M-NC1.
      Work Item Claims and external-project tooling require later decisions.
      No new model, solver, required gate, mutation campaign, enforcement,
      implementation or P43 graduation is authorized here.
- [?] P3. Fettle Review WP-FR-1, Add-in Assurance, and Evidence-Guided Handoffs
      remain decision-blocked, after M-NC1's decision unless a demonstrated
      dependency is explicitly reprioritized. Reuse their contracts where useful;
      their full programs are not prerequisites for the minimal M-NC1 receipt.
- [?] P3-ED. Coordinate WP-DS-1 through WP-DS-4 with existing Experience Discipline
      packages for broader rollout after scoped M-NC1 evidence and its decision:
      baseline and sealed evaluation first, then the smallest compatible candidate,
      packaging, advisory pilot, and explicit `GO`. Each package remains
      separately authorization-gated; no active global discipline may be replaced
      before its required evidence and installation approval. Use the existing
      evaluator and ownership contracts, not a second discipline framework.
- [ ] P4. Research briefs, documents/slides, browser side effects, remote artifacts,
      MCP/non-code desktop hosts, and in-toto/PROV alignment remain deferred.
      Revisit a physical core/pack split only after a second workflow demonstrates
      shared behavior. New domains require their own authority and skill/discipline
      review, not a copy of spreadsheet or coding checks.
- [ ] P4-VT (deferred). Vacuous-test rule pack and distinguishing-mutant authoring
      convention seeded from OSS Verify's enrollment rules
      (docs/backlog/vacuous-test-rule-pack.md). Python tests first; no enrollment,
      no new gate, no scope or pass-semantics change. Revisit after AH07 closes,
      in recorded order.
- [ ] PARKED. P49-P51 await a viable P48 consumer redesign and separate
      authorization. Standalone ATIF inspection remains `NO_GO`.
- [x] D1. P33 scanner and CI result integrity
- [x] D2. P44 immutable change-integrity contracts and adversarial corpus
- [~] D3. P43 narrow formal verification — Policy Capsule and Work Item Claims
      implemented; Verify Gate, Dispatcher, TDD Gate, property/state-machine
      tests, and refinement maps remain. P2-FM now proposes the bounded
      [conformance continuation](../formal-verification-conformance-plan.md);
      WP-FM-0 review is deferred behind M-NC1's decision. The three new
      models stay parked; pilot acceptance does not complete P43. Proposed
      FM-7 through FM-11 extend internal assurance checks without satisfying
      or changing P43's remaining model/refinement criteria.
- [x] D4. P34 mutation evidence integrity — run 1 passed; run 2 is a formal
      non-pass because its aggregate rejected a rescued shard, a defect fixed by
      the bounded selector. No third run was made. On 2026-11-14 the owner
      amended the criterion from three consecutive passing runs to the two
      executions measured here. Full-corpus qualification remains
      `CLOSED_NON_PASS`; no baseline or ratchet is proposed. Open mutation
      programme questions are deferred to TR-8 of the trust remediation plan.
- [x] D5. P35 seeded-defect and recorded-override contract — promoted
      `ci.verdict` seeded evidence and fail-closed, revision/evidence/policy-bound
      enforcing override path verified
- [~] D6. P45-P51 change-integrity runtime — P45-P47 complete; P48 remains
      advisory after broader promotion failed; P49-P51 require package-specific
      authorization and remaining prerequisites in the evolution plan
- [x] D7. P52 authorship separation — role gate and capsule plumbing shipped;
      retained CI verifies TLA+ role invariants, with adversarial path coverage,
      topology guidance, and an evidenced two-role flow
- [~] D8. P53-P61 state consistency contracts — P53-P56 complete; P57-P61 remain
      package- or evidence-gated; review and authorize P57 before web/UAT adapter,
      stateful sequence, evidence-binding, or enforcement work
- [?] D9. Fettle Review — planning complete for a plain-English, visual,
      evidence-linked assurance case; no baseline study or implementation is
      authorized. Next decision: whether to authorize WP-FR-1.
- [?] D10. Work-item lifecycle integrity — reviewed planning package persisted;
      no implementation or corpus migration authorized. Next decision: approve
      WP-WLI-0/WLI-1 after required audit-hardening acceptance.
- [?] D11. Experience Discipline vNext — reviewed planning package persisted;
      [whole-suite review plan](../discipline-suite-review-plan.md) now adds a
      current-copy inventory, quality-critical lessons, and behavioral scenarios.
      Its research and evaluation scope still require cross-task broadening;
      selected source reads were not a comprehensive best-practice search.
      No implementation or host-global skill change authorized. Next decision:
      review the broadened WP-DS-0/ED-0 scope after audit hardening is complete and
      coordinate with WLI P0 trust repair; live baselines need separate approval.
- [?] D12. M-NC1 first non-code milestone: spreadsheet workflow planned below;
      discovery, implementation, evaluation, and spending remain unauthorized.

### Formal assurance continuation

Priority: P2-FM, after M-NC1's decision and evidenced hardening/WLI-4 prerequisites.
The [implementation plan](../formal-verification-conformance-plan.md) owns scope,
file/test boundaries, estimates, fault corpora and acceptance criteria; the
[UX/BDD](../formal-verification-conformance.ux-spec.md) and
[CLI contract](../formal-verification-conformance.ui-spec.md) own the experience.
All activities below remain unexecuted and separately approval-gated. A NO_GO
pauses dependent packages unless the operator explicitly revises the sequence.
Earlier scheduling needs a demonstrated trust-critical gap and explicit approval.

- [?] WP-FM-0. Reconcile the current model/configuration/Python mapping and freeze
      one capsule mode-monotonicity claim, independent corpus, scope and budgets.
- [ ] WP-FM-1. Specify all nine admitted mode pairs, delegation sequences and
      plumbing exceptions independently; separate model and implementation faults.
- [ ] WP-FM-2. Add finite-domain and state-machine conformance tests invoking real
      operations; retain shrinking/replay and missing-action/non-vacuity checks.
- [ ] WP-FM-3. Produce bounded, portable formal evidence with exact model, source,
      policy, scope, oracle, tool and occurrence bindings; reject partial outcomes.
- [ ] WP-FM-4. Integrate truthful, advisory inspection and CI evidence retention
      through existing surfaces; no verified-source badge or new required gate.
- [?] WP-FM-5. Evaluate independent held-out faults, three clean-profile runs,
      maintenance cost and recipient UAT; decide the capsule claim only.
- [?] WP-FM-6. Review measured value and current priorities; authorize at most the
      next package. Prefer the internal continuation below; Work Item Claims and
      external-project engines remain separately gated alternatives.
- [?] WP-FM-7. Freeze one completion criterion family against accepted WLI and
      domain-evaluator contracts: approved obligation inventory, expected outcomes,
      authority, finite lifecycle, legacy compatibility and independent fixtures.
- [ ] WP-FM-8. Connect that opted-in criterion to existing semantic evidence
      evaluation; test real transitions, omissions, stale/forged results, expected
      rejection versus success, cancellation and recovery. Keep new claims advisory.
- [ ] WP-FM-9. Define an independent conservative evidence interpretation and
      bounded reference relation; verify real aggregation across validity,
      completeness, applicability, authority, unknowns and conflicts. Weakening
      required evidence cannot manufacture eligibility under fixed policy/scope.
- [ ] WP-FM-10. Inventory trusted and untrusted inputs; exercise paired real
      decisions with changed annotations and fixed trusted observations. Test
      check-selection bypasses, self-endorsement and legitimate positive controls.
- [?] WP-FM-11. Qualify each internal claim separately using held-out faults,
      independent runs, cost, compatibility and BDD-FM-8 through BDD-FM-13.
      Decide GO/NO_GO/BLOCKED per claim; any promotion needs its own policy approval.

Planning estimates: existing FM-0 through FM-5, 8-15 engineering days; FM-6,
one review day; proposed FM-7 through FM-11, 12-20 engineering days. These exclude
approval/review queues and observation and authorize no budget or delivery date.
Re-estimate at each contract gate. No full mutation run, solver installation,
live-agent campaign, external effectiveness study or new spending is implied.

Planning verification (2026-10-16): initial coordination item and detailed-plan
edits each passed all six documentation-claim tests. Final linked-document and
quality checks are recorded in the implementation plan worklog. None qualifies
a runtime claim or changes AH07, WLI, Assurance, or P43 acceptance.

### Preserved coding and reliability commitments

This revision changes sequencing, not scope or acceptance criteria. No previously
planned coding or reliability improvement is cancelled or declared complete.
Existing identifiers and detailed plans remain authoritative for their scope;
the displayed priority order is the scheduling overlay, not a renumbering.

| Retained work | Treatment in this revision |
|---|---|
| Audit hardening, exact-candidate qualification, and independent AH07 acceptance | Required first; no acceptance criterion removed or added by this planning update |
| WLI-0 through WLI-4, WLI-5 projection, WLI-6 measurement | Trust repair remains P0; later projection/measurement remain planned, with observation allowed alongside M-NC1 |
| P33 scanner/CI integrity, P34/P62-P65 mutation evidence and ratchet, P35 seeded-defect/override controls | Preserve shipped controls, remaining graduation evidence, required gates, and planned improvements; no optional-depth deferral weakens enforcement |
| P43 models, property/state-machine tests, refinement maps, and P2-FM conformance | All retained; additional work deferred, not cancelled or mislabeled as irrelevant to non-code |
| P44-P51 change integrity, P41 commit-linked evidence, graph/claim integrity, and P52 authorship separation | Preserve shipped evidence and remaining redesign/authorization gates; P49-P51 stay parked, not removed |
| P53-P61 state consistency, P57 web/UAT adapter, P72-P77 UAT reliability and parity | Preserve remaining adapter, stateful, recovery, judgment, and human-evidence requirements; no unsupported promotion |
| P66-P71 evidence convergence, canonical security, runtime secret protection, and required CI/release boundaries | Preserve remaining producer/host-specific verification, evidence gates, compatibility, and unsupported-status reporting |
| Coding skills/disciplines, cheap defect detection, traceability, verification cost, and recovery/adoption work | Retain useful rules and the B0-B5/H1-H7 backlog; evaluate revisions against coding controls before broader rollout |

Code remains the first proof and an ongoing regression control, not a disposable
pilot. A newly demonstrated critical reliability gap takes precedence over
expansion through an explicit scope/priority decision. Generalization does not
require every optional coding-depth item to finish first.

### M-NC1: first non-code milestone (deferred)

Owner: Milind. Question: for a bounded source-table-to-spreadsheet workflow,
does Fettle improve independently verified completion or reduce false-ready
outcomes within an agreed total human-effort and latency budget?

User flow: approved brief and CSV/XLSX source tables lead to one produced or
updated XLSX workbook, criterion-driven checks, a recipient receipt, and remaining
human acceptance. Milind's recurring work supplies development cases, not general
effectiveness evidence.

Scope: declared schemas, required sheets/tables/columns, source-row preservation,
reconciled totals, recalculated derived metrics, formula presence where required,
and assumptions traceable to the brief. Freeze tolerances, supported formulas,
and one pinned calculation engine during discovery. Arithmetic, SUM/SUMIF(S),
COUNTIF(S), AVERAGE variants, simple lookups, ROUND, and IF are candidates, not
promised support. Evaluate LibreOffice headless or a Python engine before selection;
data-validation libraries do not recalculate formulas or establish business truth.

Exclude macros, external connections, remote sheets, chart/visual quality beyond
declared presence checks, and business judgment not derivable from the inputs.
Unsupported checks remain unverified, never passed. Bound input trust and parser/
execution risks before build; exclusions alone do not make untrusted documents
safe. Broader malicious-document research remains deferred.

- [ ] NC1-0. **Discover, maximum two weeks; finish earlier when clear.** After
      P0 acceptance and explicit bounded discovery authorization, select 3-5
      nonconfidential or synthetic development tasks. Identify checks, engine,
      data permissions, validator trust boundary, UX/UAT scenarios, and needed
      skill/discipline revisions while retaining coding controls. Assess external
      tasks, including GDPval or alternatives, and 1-2 outside task/criteria
      reviewers within approved limits. GDPval fit is unverified; acknowledge
      public-task contamination. No discovery begins alongside hardening.
- [?] NC1-A. **Approve one bounded milestone, not each internal package.**
      Discovery needs an explicit time/data/spend ceiling; this TODO funds nothing.
      At discovery exit, approve the remaining build/freeze/measure/decide scope,
      authority, data, capabilities, API/compute budget, reviewer compensation,
      latency/human-effort limits, and exclusions together. These remain pending.
      Reapprove only changes to those boundaries. Existing WLI and DS/ED
      production-installation gates are not waived.
- [ ] NC1-1. **Build only the advisory minimum after approval.** Reuse completion
      and canonical evidence for a Git-optional work-unit contract: identity,
      brief, typed criteria/admissible evidence, inputs, outputs, and policy.
      Bind evidence to instance, criterion, input/output digests, validator version/
      configuration, and environment; hashes establish neither truth nor authority.
      Verify declared final outputs regardless of editor, shell, or script origin;
      route by criteria/capabilities, not extensions. Address the docs-only bypass
      for declared outputs without enforcement. Wrap pinned spreadsheet validators
      and show what reconciled/recalculated, failures with locations, unchecked
      items with reasons, and remaining human review in a minimal receipt.
      Use existing CLI and Claude Code hook paths; no new host, MCP, package split,
      or general plugin authority. Revise needed skills/disciplines only in isolated
      candidates, with development checks and coding regression evidence.
- [ ] NC1-2. **Freeze before held-out measurement.** Development criteria may be
      operator-authored and tuned; external authors/reviewers approve evaluation
      criteria before agent runs. Pin runtime validators independently of producers;
      protect sources, criteria, policy, validator code/config, and evidence from
      producer modification and record attempts as violations. Keep held-out graders
      independent of runtime validators and hidden; requirements remain visible.
      Freeze task provenance, engine/formulas, candidate skill/discipline versions,
      coding controls, protocol, grading, analysis, confidence intervals, and
      thresholds in a dated record. Confirmation requires the criterion's declared
      admissible deterministic evidence or human acceptance. LLM findings remain
      advisory; no weighted voting or promotion of self-assertions. Bind validator
      identity/config digest or human identity to the work unit. Distinguish
      confirmed, failed, unverified, awaiting human acceptance, and accepted;
      receipt wording must not collapse these outcomes into an overall pass.
- [ ] NC1-3. **Measure three arms.** Compare baseline, self-check instruction,
      and Fettle advisory verification plus receipt with the same model/settings,
      tools, and budgets. Grade independently across all assigned tasks. Report
      verified completion, false-ready per task and per claim, abstention,
      independently adjudicated unnecessary findings/blocks, and unverified
      criterion share. Count human criteria/setup, findings, receipt review,
      repairs, rejected attempts, and overrides; count wall time, tokens, and
      compute including failures. Review sample outcomes externally. Retain failed
      and indeterminate attempts; do not tune on held-out results.
- [ ] NC1-4. **Decide continue, revise, or stop from retained evidence.** Lower
      false-ready solely through abstention or increased human effort is not an
      improvement. Zero observed false-ready is not zero-risk proof. Null/negative
      findings can complete the experiment, not justify enforcement or public
      effectiveness claims. Record which coding controls held, which skill/
      discipline revisions helped or failed, and what remains unknown. Only then
      propose broader DS/ED revisions and exact-version opt-in rollout with its
      existing evaluation, approval, loading, conflict, and rollback gates.

The parked sibling effectiveness study remains unchanged and unauthorized for
execution. Research briefs are a later workflow, not a second M-NC1 pilot.
Full Review/handoff programs and physical packaging are not hidden prerequisites.
No existing coding, mutation, CI/release, or authority gate is weakened.

Worklog (2026-10-11, generalization planning): replaced research-brief-first
sequencing with deferred M-NC1, kept hardening/WLI first, and deferred optional
conformance/platform expansion. Explicitly retained all coding and reliability
commitments; added staged skill/discipline revision with coding regression controls.
No discovery, runtime, active skill, benchmark, spending, host, or sibling-project
change started. Verification: six documentation-claim tests pass; 37 local links
and anchors resolve; priority, pending-stage, and retained D/B/H checks pass;
editor and whitespace checks are clean; Fettle reports no issues. The consistency
check preserves H5's existing decision-blocked status. The impact index is stale
and diagnostic only. Hardening acceptance remains unchanged.

Worklog (2026-10-10): added the whole-suite discipline review at P0-2a and an
explicit quality-critical findings decision before WLI-2. Existing ED evaluation
and installation gates remain; WLI does not wait for whole-suite rollout by
default. Planning and read-only inspection are not active-skill update approval.

Worklog (2026-10-11, planning drafted): added the formal-methods conformance plan,
UX/BDD and CLI contracts, and P2-FM priority. WP-FM-0 through WP-FM-5 cover claim
freeze, independent fault corpus, implementation conformance, portable evidence,
advisory integration, and qualification; WP-FM-6 is a separate expansion decision.
The first claim is canonical mode monotonicity, not the full capsule merge API.
Audit hardening, WLI, discipline checkpoints, and P43 completion remain unchanged.
Planning checks: six documentation tests pass, 37 local link targets resolve,
editor/whitespace checks are clean, and Fettle reports no issues. Completion
validation still reports AH07 independent hardening acceptance blocked; P2-FM
execution remains deferred. The impact index is stale and diagnostic only. No
model, runtime, active skill, mutation, enforcement, or research-service change
was made.

### Discipline broadening: deferred priority sequence (2026-10-10)

These instructions supersede the earlier coding-first scope and permission to
proceed with discipline review preparation now. Only this backlog update is
authorized. Keep current hardening and active disciplines unchanged; wait for
the operator's report and confirmation that required hardening criteria are met.
The sequence below refines P0-2a/P1-DS/P3-ED; it does not displace WLI trust repair
or authorize a second framework. Code remains the first proof with accepted
disciplines and required checks retained. Use B0-B3 first for quality-critical
WLI findings and M-NC1's scoped needs; revisit the wider task inventory after the
pilot decision rather than making it a prerequisite. Reconcile the linked plan
before execution. Broader candidates/evaluations and production rollout retain
separate DS/ED approvals; bounded M-NC1 candidates and comparisons must be named
within that milestone's approved scope.

- [ ] B0. After hardening completion, bind the accepted candidate and retained
      evidence to the actual delivered state. Record active discipline versions
      and host-loading evidence where available; missing facts remain unknown.
      Do not infer completion from elapsed time or a green ordinary CI run.
- [ ] B1. Start with primary guidance for the bounded spreadsheet workflow and
      coding controls; defer comprehensive multi-domain research until M-NC1's
      decision. Retain the broader comparative backlog of primary guidance and
      research on skill authoring/discovery, agent evaluation, tool permissions,
      prompt-injection resistance, provenance, and domain-specific verification.
      Include research, writing, documents/presentations, data analysis, planning,
      browser operations, and coding. Retain source dates, applicability, evidence
      limits, and competing recommendations; do not elevate a summary or analogy
      into binding policy. Authenticated research access, disclosure, and spending
      require approval; no research calls are authorized by this entry.
- [ ] B2. Define shared, task-neutral QA principles: intended outcome, acceptance
      criteria, risk-proportional checks, evidence and uncertainty, provenance,
      privacy, authorization, output correctness, independent review, recovery,
      and truthful handoffs. Disciplines govern work; skills provide capabilities
      or workflows. Installation and tool success do not establish compliance.
      Keep coding, mutation, accessibility, and presentation checks as applicable
      specializations, not universal requirements or claims of universal coverage.
- [ ] B3. Revise the existing DS/ED plan from the research and retained hardening
      lessons. Preserve useful existing rules; change demonstrated weaknesses.
      Place revisions at the relevant milestone: shared principles and spreadsheet
      skills before NC1-1, exact versions and coding/non-code controls at NC1-2,
      observed behavior at NC1-3, and broader revision/rollout at NC1-4/B5. Add each
      future domain's checks when that workflow is selected, not all at once.
      Freeze representative coding and non-code cases, expected observable actions
      and outputs, risk strata, baseline, independent review, and approval gates.
      Measure unsafe actions, false completion, unnecessary blocks, output quality,
      and verification cost. Keep missing evidence non-pass and distinguish
      automated evaluation from actual human acceptance. Reuse existing validators
      and evaluators; create no new aggregate acceptance authority.
      Specify risk-proportional, cost-ordered verification: cheap discriminating
      checks, real handoff tests, bounded workflow/platform checks where needed,
      then frozen-candidate qualification. Define time, token, runner-minute,
      and acceptance-delay measures without trading away required checks or
      safety blockers. Track defects first found in qualification, attributable
      candidate restarts, verification effort, and observed unsafe misses and
      adjudicated false blocks. Estimate avoidable cost only with a documented
      cheaper reproducer; separate provider-only, locally detectable, and unknown
      causes rather than claiming speculative savings.
      Include representative research retrieval-to-claim-to-source verification,
      document generation-to-export-to-render-to-content inspection, and browser
      permission-to-action-to-observed-result-to-recovery cases. These illustrate
      task-specific checks, not mandatory machinery for every task.
- [ ] B4. After separate approval, author the smallest compatible candidate in
      isolation. Validate discovery/schema and development cases before a frozen
      held-out comparison and the existing advisory pilot. Retain failed and
      indeterminate attempts; do not tune on held-out outcomes. Keep active global
      skills, hooks, policies, dependencies, and accepted hardening evidence
      untouched. Freeze live-call, privacy, time, and spending limits in advance.
      Evaluate whether agents actually inspect outputs and handoffs, use cheaper
      discriminating checks before expensive runs, and retain all required safety
      and evidence gates. Compare the B3 measures against the frozen baseline;
      test counts, matching terminology, or lower cost alone do not establish
      improvement. Live platform probes require separate bounded authorization
      when consequential assumptions cannot be established offline; their evidence
      is scoped to those assumptions, not interchangeable qualification outcomes.
- [ ] B5. Only after required evidence and explicit `GO`, approve an exact-version,
      opt-in rollout to named hosts with conflict preservation and tested rollback.
      Verify actual loading and outcomes. Assess evidence applicability for any
      changed executable boundary; do not assume global skill activation is inert
      or that every discipline update requires a full mutation campaign.

Worklog (2026-10-10): recorded the operator's cross-task QA direction and deferred
all discipline review/update execution until hardening completion. No broader
research, plan rewrite, active-skill change, or hardening-status update performed.

### Future hardening checkpoints (2026-10-10)

Planning only: these checkpoints authorize no implementation, mutation run,
spending, policy change, or release. Material changes and evidence applicability,
not elapsed calendar time, determine the required verification scope. Existing
governing full-run requirements remain binding unless explicitly changed before
execution; a failed run is not grounds to narrow acceptance retroactively.

- [ ] H1. After current hardening is accepted, preserve its exact candidate,
      runtime, dependency, policy, workflow, and evidence identities as the
      comparison baseline. Historical acceptance does not automatically qualify
      a later candidate.
- [ ] H2. Before WP-WLI-2 implementation, freeze the verification scope: changed
      owners, affected consumers, reusable evidence, invalidated evidence, and
      required fresh checks. WLI-0/WLI-1 require contract and fixture review;
      planning alone does not trigger another full mutation campaign.
      Include a short map of critical producer/consumer handoffs, real artifact
      contracts, platform assumptions, failure/recovery paths, and the cheapest
      discriminating check for each. Before separately authorized expensive
      qualification, record which required paths passed, which assumptions remain
      unverified, and why that run is justified. This is planning/readiness
      evidence, not a substitute for the governing acceptance checks.
- [ ] H3. During WLI-2/WLI-3, run focused unit, adversarial, consumer-integration,
      and applicable mutation checks. Do not defer integration discovery until
      the final enforcement checkpoint.
      In handoff/integration tests, feed actual producer output through the owning
      parser, validator, and consumer; mock external services as appropriate, not
      the internal contract being verified. Retain useful isolated unit tests.
      Use small complete-workflow fixtures and applicable interruption, publication,
      and accounting fault injection. Preserve named incident regressions that
      demonstrably fail before the fix. Check changed packaging/platform boundaries
      in the relevant environment; separately authorize a bounded live probe only
      where consequential assumptions cannot be established offline. Probes do
      not replace qualification or supply interchangeable mutation outcomes.
- [ ] H4. At WP-WLI-4, before enforcement is relied on for merge or release,
      complete targeted lifecycle hardening: full-corpus validation, direct-edit
      bypass cases, completion delegation, installed CLI, required CI dependencies,
      release ordering, and authorized external-protection verification or
      explicit `UNKNOWN`. Preserve compatible checks rather than rerunning them.
- [?] H5. Before rollout of material shared-execution or mutation-isolation
      changes, assess broader qualification against the accepted baseline.
      These changes affect evidence production; qualify the frozen candidate
      under the approved impact-based scope and budget. This is the next likely
      broad checkpoint, not an automatic whole-product campaign. Do not batch
      unrelated changes merely to save a qualification run.
- [ ] H6. Keep Review, handoff, and new-host verification scoped to their existing
      false-ready, accessibility, evidence-parity, provenance, authority, privacy,
      and integration gates. Broaden only for demonstrated impact or a governing
      requirement, not merely because a new surface was added.
- [ ] H7. Use WP-WLI-6's existing 30-day observation to review defects, bypasses,
      and recovery effort. It is a review checkpoint, not an automatic full
      calibration schedule or a new current-hardening completion criterion.

Worklog: added explicit verification timing alongside the existing priority
sequence; no delivery status, acceptance policy, or execution authority changed.

Worklog (2026-10-11): incorporated independently reviewed early-defect-detection
recommendations into H2/H3, B3/B4, and P2 without changing priority order. Kept
planning separate from execution, internal-contract fidelity separate from unit
test isolation, lifecycle measurement separate from broader qualification costs,
and safety gates independent of cost savings. P2-FM remains separately gated.
No new current-hardening acceptance criterion or active-discipline change added.

## Phase E — Trust remediation (2026-11-13 audit)

Plan: docs/trust-remediation-implementation-plan.md. Starts after D4 closes.
Order is priority order; each package is one pull request unless the plan says
otherwise. Finding IDs refer to the plan's register.

- [x] E0. TR-0 Baseline harness and required-check containment — end-to-end
      tests that run the hook command exactly as `fettle init` registers it,
      in both launch modes; host failure-mode table; UX acceptance contract
      (docs/trust-remediation.ux-spec.md); a label event can no longer publish
      a skipped check under the required `mutation evidence` name (M5,
      confirmed on pull request #73). No behaviour change in `fettle/`.
      Harness and host table: local completion evidence recorded 2026-11-14.
      Required-check containment confirmed on pull request #76 under the
      reviewer-amended security criterion on 2026-11-16; review and merge remain
      separate actions.
- [ ] E1. TR-1 Shipped hook path (P0: E1, E21, T1, E3, E4, E5) — dispatcher
      records edits; one entry point per check; project-root policy
      resolution; tool taxonomy with multi-target events; isolated launch.
- [ ] E2. TR-2 Control plane and policy floors (P0: E2) — protect Fettle's own
      config, state and hook wiring; fail-closed checks cannot be disabled from
      the repository layer; organisation, remote and capsule policy become
      floors; remote policy fails closed.
- [ ] E3. TR-3 Truthful verification (P0: V2, V3a) — gates read the validated
      artifact, never the stamp's `ok`; test counts recorded and zero executed
      tests is a non-pass; CI evidence bound to the assessed commit.
- [ ] E4. TR-4 First-run correctness (P0: G3, P2, P3) — secret-guard false
      blocks; `init --dry-run` writes nothing; `explain` no longer crashes;
      the demo runs the real engine. Independent; may be pulled forward.
- [ ] E5. TR-5 Trust root — provider-neutral signed attestations, policy read
      from the base ref, assurance levels A0-A3, signed overrides, completion
      manifests and ledger checkpoints. Four rollout steps.
- [ ] E6. TR-6 Guards — secret boundary model, destructive guard, spawn gate,
      MCP gate, role separation, output guard.
- [ ] E7. TR-7 Coordination — worktree scanning, claim ownership and scope,
      worker attribution, session-bound plans.
- [ ] E8. TR-8 Pipeline and mutation decisions — advisory serialisation guard,
      fingerprint portability, admission accounting; owner decisions D1-D5 on
      the mutation programme. D2 was taken 2026-11-15: PR advisories omit
      `fettle/mutation_test.py` and `fettle/staged_preflight.py`, while deliberate
      full-corpus preparation keeps both. The observed ledger's old shard-index
      contents remain an M7 limitation. Starts after D4 closes.
- [ ] E9. TR-9 Polish — all P3 items and survivor triage in trust-critical
      modules.

## Standing rules
- No Claude/model-name attribution anywhere in Fettle docs or repo.
- Every increment: tests + work note + independently reviewable.
- Fettle self-check before declaring any coding work complete.
