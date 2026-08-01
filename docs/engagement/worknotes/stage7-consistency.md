# Stage 7 — Functional-test verification + WP9 consistency pass

Slices: S7.1 verify gate (c0dead3) · S7.2 config debts (72f1516) ·
S7.3 hygiene · S7.4 docs + roadmap (this commit).

## What shipped

- **S7.1 — `[gates.verify]` + `fettle verify` (closes WP2's execution gap).**
  Two-world pattern, mirroring coverage_gate: the CLI (minutes-world) runs
  the discovered suite and writes `.fettle/verify.json`; the Stop gate
  (ms-world, 100 ms budget, order 52) only checks stamp freshness against
  `edits.jsonl`. Impacted scoping: edited `foo.py` → `test_foo.py` /
  `foo_test.py` under test roots (pytest only); empty mapping ⇒ full suite.
  Failure history feeds `build_pytest_args(mode="changed")`. 25 tests.
- **S7.2 — config debts retired (WP9).** `gates.subagent.mode` removed;
  `gates.complexity` unified on `mode` (legacy `enforce` bool honored +
  deprecation warning); `gates.docs` default `soft` → `enforce`, `"soft"`
  kept one release as a warned alias; stale "live_test_gate.py" comments
  fixed. 5 new schema/complexity tests.
- **S7.3 — hygiene.** 14 executed/superseded plan docs → `docs/archive/`
  with frozen-status banners (closes open question #11 — flagged to
  operator, git-reversible). Work notes unified under
  `docs/engagement/worknotes/` (stage 5/6 had landed in a root
  `worknotes/` by accident). Engagement TODO brought current.
- **S7.4 — docs + B10.** CHANGELOG entry; README/CONFIG already covered by
  S7.1/S7.2; `docs/ROADMAP.md` gains the consolidated forward roadmap
  (7 prioritized items with dependencies) and archived-link fixes.

## Decisions

- **D-S7.1 — `verify`, not `tests`.** The natural key `[gates.tests]`
  collided with the pre-existing quality_gate bash test-stamping config
  (`browser_test_window_s`). The duplicate dict key shadowed silently;
  the RANGES anti-drift pin caught it (KeyError on the vanished path) —
  exactly what those pins are for. Renamed module/key/CLI verb to
  `verify` end to end.
- **D-S7.2 — record correction on `gates.subagent`.** The WP4 audit doc
  claimed the table was "consumed by no code". Wrong: `hooks/
  subagent_inject.js` consumes `enabled` + `injection_file` (contract
  tests exist). Only `mode` was vestigial; only `mode` was removed.
- **D-S7.3 — deprecations warn, never break.** `"soft"` docs mode and the
  `complexity.enforce` bool behave exactly as before for one release;
  schema validation emits warnings naming the replacement. Unknown keys
  (a removed `subagent.mode` in user configs) already degrade to
  warnings.
- **D-S7.4 — complexity dual-signal.** During the tolerance window either
  `mode = "enforce"` or `enforce = true` blocks (`or`, not precedence
  games) — no behavior cliff for existing configs.
- **D-S7.5 — impacted-scope argv filter is exact-match.** The original
  `endswith(test_roots)` filter would strip the literal `pytest` token
  when a test root is `test`. Filter is exact membership after
  `rstrip("/")`.
- **D-S7.6 — compiled-shim question answered as a trigger, not a plan.**
  Operator asked about a Go/Rust port. Recorded in ROADMAP: no port;
  extract a hot-path shim only if telemetry shows hook-budget violations
  from interpreter startup, after trying lazy imports first.

## Archive list (S7.3)

PLAN-v050-adaptive, WORKPACKAGES-v050, SPEC-dispatcher-v2,
fettle-v08-plan-sol(-v2), fettle-v09-plan, fettle-v10-enterprise-plan,
fettle-v10-plan-compliant, AUDIT-GPT55(-v2), ci-enforcement-plan,
fettle-expansion-plan, fettle-swebok-gaps-plan,
continuity-traceability-plan. Kept live: CONFIG, OPENCODE, ROADMAP,
fettle-enterprise-product-plan (WP-133..153 reference), fettle.schema.json.

## Verification

- `tests/test_verify_gate.py` (25) + schema/complexity additions (5);
  affected suites green per slice; full suite on pre-push.
- Fettle self-check green on all touched files (accepted pre-existing
  fail-visible prints in config.py/post_edit.py — hook protocol, Stage 0).
