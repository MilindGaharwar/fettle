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
- [~] B9. WP9 Whole-system consistency pass (S7.2 config debts done; S7.3 hygiene done)
- [~] B10. Consolidated prioritised roadmap with WP dependencies

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
  - [x] S5.5 web surface (playwright extra) + consent + redaction
  - [x] S5.6 docs + work note
- [x] C6. Stage 6 — semantic layer thin slice
  - [x] S6.1 link fusion + `fettle links <id>|--orphans`
  - [x] S6.2 graphify consume-optional enrichment + docs
- [~] C7. Stage 7 — WP9 consistency + roadmap
  - [x] S7.1 [gates.verify] + `fettle verify` (closes WP2 execution gap)
  - [x] S7.2 config debts: subagent.mode removed, complexity mode
        unified, docs 'soft' deprecated, stale comments fixed
  - [x] S7.3 hygiene: plan docs → docs/archive/ (frozen-status banner),
        work notes unified under docs/engagement/worknotes/, TODO current
  - [ ] S7.4 docs (verify gate) + consolidated roadmap (B10) + work note

## Standing rules
- No Claude/model-name attribution anywhere in Fettle docs or repo.
- Every increment: tests + work note + independently reviewable.
- Fettle self-check before declaring any coding work complete.
