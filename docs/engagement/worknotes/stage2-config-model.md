# Work note — Stage 2: WP4 config/feature dependency model

Status: complete (2026-08-01)

## What was done

Design: docs/engagement/07-wp4-config-dependency-model.md (evidence audit of
every `mode` consumer; three classes of invalid-but-accepted states).

Implementation (fettle/config_schema.py — same derived-from-DEFAULTS
discipline as WP-142):

- `MODE_ENUMS` — per-gate mode vocabulary (15 paths, exactly the `.mode`
  paths in DEFAULTS; pinned by test). Out-of-vocabulary mode → **error**
  (was: warning against the 10-value global union). Worst case fixed:
  `tdd.mode="enforce"` validated but behaved as advisory.
- `RANGES` — 24 numeric bounds (coverage 0–100, tier2 confidence 0–1,
  positive thresholds/windows). Out of range → error.
- `DEPENDENCIES` — 5 cross-field rules on the defaults-merged view:
  extends.url→sha256 pin (error); boundaries/tier2/tdd inert (warning);
  ui_colors empty palette (warning). Skipped when structural errors exist.
- Schema generator emits per-gate `enum` + `minimum`/`maximum`;
  docs/fettle.schema.json regenerated (anti-drift test pins it).
- `fettle doctor` gained `check_config_valid` (validates the project's
  .fettle.toml, names the first problem, points at `fettle config
  --validate`).
- CONFIG.md "Validation: no invalid config states" section; CHANGELOG entry.

## Decisions

- **D-S2.1** Mode-enum violations are errors, not warnings: a mode that
  silently acts as a different mode is precisely an invalid config state.
- **D-S2.2** `"off"` is in no gate's enum — the kill switch is
  `enabled=false`; `mode="off"` on the docs gate would *block* (any
  non-advisory mode blocks there).
- **D-S2.3** Dependency rules evaluate the defaults-merged view (static,
  network-free; org policy layers not resolved — noted in docstring).
- **D-S2.4** Severity split: error = would misbehave; warning = inert
  feature or unusual-but-coherent policy (ui_colors empty palette flags
  every color — coherent, so warning).

## Deferred to WP9 (recorded in design doc)

- docs-gate mode semantics (`soft` blocks — any non-advisory blocks).
- `gates.subagent` defined but consumed nowhere — remove or wire.
- complexity's `enforce: bool` second vocabulary → unify with `mode`.

## Rejected alternatives

- JSON Schema `if/then` for dependencies — generator auditability wins;
  rules live in Python with messages, schema documents bounds/enums only.
- Validating at config load time (hook path) — validation stays in
  `fettle config --validate` + doctor; hooks must stay fast and non-fatal.

## Verification

tests/test_config_schema.py: +17 tests (enum coverage/membership pins,
range pins, per-rule dependency cases, schema enum/bounds). Full targeted
run: 80 passed (config, schema, doctor, cli). Full suite + fettle
self-check ran at commit/push via guard chain.
