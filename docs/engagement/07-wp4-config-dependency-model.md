# WP4 — Configuration / Feature Dependency Model (design)

Stage 2. Non-negotiable served: **no invalid config states** — a config that
validates must behave as written; one that would misbehave must fail visibly.

## Evidence: three classes of invalid-but-accepted states

Today `validate_config` (fettle/config_schema.py) checks unknown keys, type
compatibility, and membership of `mode` values in a **global union**
(`_MODE_VALUES` = advisory/soft/enforce/silent/strict/none/marker/manifest/
commit/off). Audit of every mode consumer found:

### C1 — Per-gate invalid modes pass validation

Each gate honors a small subset, but any union member validates:

| Gate | Modes the code honors | Silently accepted today |
|---|---|---|
| lint, docs | advisory / soft / enforce | `lint.mode="manifest"` |
| ci_bootstrap, tdd | advisory / strict | `tdd.mode="enforce"` (acts as advisory!) |
| lean_review | silent / advisory | `lean_review.mode="strict"` |
| provenance | none / marker / manifest / commit | `provenance.mode="enforce"` |
| destructive, config_protect, commit_message, coverage, deploy_safety, release, artifact_integrity, worklog, subagent | advisory / enforce | `coverage.mode="strict"` (acts as advisory) |

The worst shape: `tdd.mode = "enforce"` *feels* stricter but the gate only
checks `mode == "strict"`, so the user believes they hardened TDD while it
stayed advisory. That is exactly an "invalid config state".

### C2 — Cross-field dependencies unchecked

- `extends.url` set without a valid 64-hex `extends.sha256`: caught only at
  policy-load time (policy_remote raises), not by `fettle config --validate`.
- `architecture_boundaries.enabled = true` with empty `rules`: gate is inert;
  user believes boundaries are enforced.
- `lean_review.tier2.enabled = true` with empty `model`/`ollama_url`:
  tier2 can never run.
- `ui_colors.enabled = true` with empty `allowed_hex`: flags **every**
  hardcoded color (quality_gate falls through to the empty module-level
  `ALLOWED_HEX`) — coherent as a policy but usually a forgotten palette.

### C3 — Numeric ranges unchecked

`coverage.threshold = 150`, `plan.threshold = 0`, negative cooldowns, and
similar all validate and then misbehave arithmetically.

## Design

One new declarative layer in fettle/config_schema.py — three tables, all
keyed by dotted path, all consumed by both `validate_config` and
`generate_json_schema` so validation, published schema, and docs cannot
drift (same derivation discipline as WP-142):

```python
MODE_ENUMS: dict[str, frozenset[str]]   # "gates.tdd.mode" -> {"advisory","strict"}
RANGES: dict[str, tuple[num|None, num|None]]  # "gates.coverage.threshold" -> (0, 100)
DEPENDENCIES: tuple[Dependency, ...]    # cross-field rules
```

`Dependency` = (when_path, when_predicate, message, severity), where
severity is `error` (config would misbehave) or `warning` (feature is inert
or an unusual-but-coherent policy). Initial rule set = the C2 list above:
extends pin → error; boundaries/tier2 inert → warning; ui_colors empty
palette → warning.

Validation behavior:
- mode not in that gate's enum → **error** naming the allowed set
  (upgraded from today's warning-against-union).
- out-of-range numeric → **error** with the permitted range.
- dependency rules → error/warning per table.

Schema behavior: per-path `enum` on every mode field (replacing the global
union), `minimum`/`maximum` on ranged fields, dependency rules described in
field `description`s (JSON Schema `if/then` is deliberately avoided — the
generator stays trivially auditable). docs/fettle.schema.json regenerated;
the existing consistency test pins it.

Anti-drift guarantees (tests):
1. Every `gates.*.mode` path in DEFAULTS has a MODE_ENUMS entry, and its
   default value is a member.
2. Every RANGES/DEPENDENCIES path exists in DEFAULTS.
3. Behavior pins for the two asymmetric gates (tdd strict, provenance modes)
   asserting the honored-mode set matches the table.

## Explicitly out of scope (recorded, not lost)

- **Docs-gate mode semantics**: today any non-advisory mode blocks, so
  `soft` blocks — arguably misnamed. Normalizing is a behavior change, not
  validation; deferred to WP9 consistency pass.
- **`gates.subagent`**: defined in DEFAULTS, consumed by no code in the
  tree (hook-side vestige). Flagged for WP9 — remove or wire, don't validate
  around it. Tentatively assigned advisory/enforce in MODE_ENUMS.
- **complexity's `enforce: bool`**: a second on/off vocabulary alongside
  `mode`; unifying it is a breaking config change — WP9 candidate with a
  deprecation path.

## Increments

- S2.1 this design doc.
- S2.2 MODE_ENUMS + RANGES + per-gate validation + schema regeneration + tests.
- S2.3 DEPENDENCIES rules + tests.
- S2.4 CONFIG.md + CHANGELOG + doctor surfacing (`fettle doctor` runs
  validate_config against the project's .fettle.toml).
