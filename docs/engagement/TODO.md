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
  - [x] S5.5 web surface (playwright extra) + consent + redaction
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

## Standing rules
- No Claude/model-name attribution anywhere in Fettle docs or repo.
- Every increment: tests + work note + independently reviewable.
- Fettle self-check before declaring any coding work complete.
