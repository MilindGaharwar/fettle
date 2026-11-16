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

### Current priority order

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
      (docs/trust-remediation-implementation-plan.md). Next in line after D4
      closes; nothing in this program starts while D4 runs are in flight.
      Packages run in the order listed under Phase E. Owner decisions recorded
      2026-11-13: hardening first; README claims are made true, not reduced;
      the trust root is provider-neutral; the implementing agent opens each
      pull request and the independent reviewer verifies and merges it.
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
      tests, and refinement maps remain
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
- [?] D6. P45-P51 change-integrity runtime — gated by package-specific
      authorization and prerequisites in the evolution plan
- [x] D7. P52 authorship separation — role gate and capsule plumbing shipped;
      retained CI verifies TLA+ role invariants, with adversarial path coverage,
      topology guidance, and an evidenced two-role flow
- [ ] D8. P53-P61 state consistency contracts — P53-P54 scheduled for the next
      minor and P55-P56 for the following minor; review and authorize P53/SC1
      before any runner, browser adapter, static heuristic, or enforcement work

## Phase E — Trust remediation (2026-11-13 audit)

Plan: docs/trust-remediation-implementation-plan.md. Starts after D4 closes.
Order is priority order; each package is one pull request unless the plan says
otherwise. Finding IDs refer to the plan's register.

- [ ] E0. TR-0 Baseline harness and confirmations — end-to-end tests that run
      the hook command exactly as `fettle init` registers it, in both launch
      modes; host failure-mode table; one-time confirmation of M5. No behaviour
      change.
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
      the mutation programme. Starts after D4 closes.
- [ ] E9. TR-9 Polish — all P3 items and survivor triage in trust-critical
      modules.

## Standing rules
- No Claude/model-name attribution anywhere in Fettle docs or repo.
- Every increment: tests + work note + independently reviewable.
- Fettle self-check before declaring any coding work complete.
