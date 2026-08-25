# Improvement Plan — Audit Recommendations (Ordered)

Status: active · Source: full project audit 2026-08-23, revised after GLM
review · Supersedes: none · Review trigger: on completion of all items

Order below is by value-per-effort with dependencies resolved. Each item
lists its verdict from the GLM review and its persistence location
(plan section here + claimable work item where applicable).

| # | Item | Effort | GLM verdict |
|---|---|---|---|
| 1 | Docs-claims gate: executable predicates validating doc/TODO claims against code reality; first case = S5.5-web discrepancy | 1–2 d | KEEP, strengthened (double-confirmed drift) |
| 2 | Graduation-debt triage: plan §17 amendment + dispositions for P43, P52, P34 | 0.5 d | KEEP |
| 3 | Advertise + extend `fettle init --profile` presets (exists; undocumented) | 0.5 d | MODIFY (already ships) |
| 4 | Grow examples/assurance-loop into the demo corpus (polyglot fixtures; feeds budgets, P77 seeds, screenshots) | ongoing | MODIFY (grow, don't create) |
| 5 | Split fettle-evolution-implementation-plan per program; thin index + core-vs-cockpit docs entry page | 2–3 d | KEEP, verified 2,476 lines |
| 6 | P47 advisory `fettle graph impact/status` CLI (deps met: P46 closed this week) | 3–5 d | KEEP pending deps (met) |
| 7 | P77 seeded-defect benchmark remains gated before further UAT advertising | per UAT plan | KEEP |
| 8 | Positioning/motion (trust-first one-liner everywhere; loop capture as GIF) | operator-assisted | KEEP |

## Non-goals

- No new preset machinery beyond extending `--profile` (GLM: already exists).
- No enforcement mode for the docs-claims gate until predicates mature.
- GIF capture requires an operator terminal session; Fettle side prepares
  scripted replay commands only.

## Hazard note (item 4)

Never run lint autofixes over `examples/` — violating fixtures are
intentional (e.g., assurance-loop `broken.py`). The guard is
`tests/test_assurance_loop_example.py`, which caught exactly this on
2026-08-23 after a bulk `ruff --fix`.

## Status

- [x] 1 Docs-claims gate (first predicates: S5.5/web, replay-gate↔README)
- [x] 2 Graduation triage recorded in evolution plan §17
- [x] 3 Profiles advertised in README quick start
- [x] 4 Corpus growth seeded (Python + web + Go workspaces, spec-linked)
- [~] 5 Evolution plan split — delivered as plan-index navigation layer;
      physical extraction deferred to avoid link rot
- [x] 6 P47 CLI shipped
- [~] 8 Positioning pass — PyPI/docs/About copy updated trust-first;
      loop motion capture remains an operator task

## Wave 3 — dsh-informed adoptions (2026-08-25 review of DeepSeek Harness)

Source: independent review of DeepSeek Harness (everything-is-a-plugin agent
harness). Patterns adopted, not the Cordis framework — stdlib-only core is a
constraint and a strength.

| # | Item | Work item | Effort |
|---|---|---|---|
| 9 | Pipeline dump: composed gate/hook pipeline with per-row source provenance | `pipeline-dump-command` | 1–2 d |
| 10 | Canonical producer→consumer event map + drift predicate | `event-map-doc` | 1 d |
| 11 | House invariant: verdict-visible means evidenced | `verdict-evidenced-invariant` | 1–2 d |
| 12 | "Where new behavior goes" decision table + drift predicate | `behavior-decision-table` | 0.5–1 d |

Deferred from the same review: capability-seam graph doc (lands with SC
adapters), BENCHMARK.md placeholder (owned by P77), i18n docs (demand-gated),
knip/jscpd analogs (deptry covers dead-code; copy-paste detector proposed as
a future rule).

- [ ] 9 Pipeline dump
- [ ] 10 Event map
- [ ] 11 Verdict-evidenced invariant
- [ ] 12 Behavior decision table
