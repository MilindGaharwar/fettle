# Stage 3 — Living Spec Format + WP2 Functional-Testing Architecture

Status: design (approved stage; implementation follows in slices)
Inputs: 02-pillar-gap-assessment.md (Pillars 1+3), 06-wp1 backlog #1/#4,
04-wp6 gate invariants, WP-154 (enterprise plan §Phase 2).

## 1. Problem

Fettle today enforces spec *discipline shells* with zero spec *semantics*:

| Existing piece | What it checks | What it cannot do |
| --- | --- | --- |
| `spec_audit.py` | changed spec ⇒ audit file updated, 5 headings present | never reads spec content |
| `ux_spec_gate.py` | *any* `*.ux-spec.md` exists anywhere ⇒ all frontend edits unlocked | no binding spec→files |
| `tdd_gate.py` | test file edited before impl file (ordering proxy, self-documented) | no red/green, no spec linkage |
| `trace_requirements.py` | spec *file* ↔ test *file* via naming/`# traces:` markers | file-granularity only; not wired into `fettle` CLI |
| `plan_validator.py` | plan WPs carry TDD/INTEGRATION/REGRESSION/LIVE rows | validates the plan doc, not the code |

The gap (Pillar 1 + Pillar 3): no spec format an agent can parse, no
requirement-level identity, no gate that consumes spec *content*, no
tests-from-specs contract (WP-154 is planned, unbuilt).

## 2. Design

### 2.1 Spec format — structured markdown, zero new tooling to read it

A **living spec** is a markdown file with YAML frontmatter, detected by
frontmatter key `fettle-spec` (not by filename — filenames stay free):

```markdown
---
fettle-spec: v1
id: checkout-flow            # stable, kebab-case, unique per repo
status: active               # draft | active | superseded
scope:                       # globs of governed implementation paths
  - src/checkout/**
---

# Checkout flow

## Requirements
- R1. Cart total recalculates on quantity change.
- R2. Payment failures show a retryable error state.

## Scenarios
### S1. quantity change updates total (traces R1)
- Given a cart with 2 items
- When the quantity of one item is set to 3
- Then the displayed total equals the recomputed sum

### S2. payment declined (traces R2)
- Given a valid cart at the payment step
- When the provider declines the card
- Then a retryable error is shown and the cart is preserved
```

Grammar (deliberately small):
- **Requirements**: list items matching `R<n>.` under a `## Requirements`
  heading — stable IDs `<spec-id>/R<n>`.
- **Scenarios**: `### S<n>.` headings under `## Scenarios`, each with
  Given/When/Then bullets; `(traces R…)` links scenario→requirement.
- Anything else in the file is free prose — the spec stays a document
  humans read, not a data file.

Test binding reuses the existing `# traces:` marker, extended to scenario
granularity: `# traces: checkout-flow/S1` in a test file/function body.
File-level naming-convention matching stays as the coarse fallback.

### 2.2 New module `fettle/spec_model.py`

Parser + validator, pure and dependency-free (frontmatter parsed with the
same minimal approach as elsewhere in the tree — no PyYAML dependency):
`parse_spec(text) -> Spec | SpecError`, `discover_specs(root) -> list[Spec]`,
`lint_spec(spec) -> list[finding-dict]`. Lint rules: duplicate IDs,
scenario without G/W/T bullets, `traces` pointing at missing requirement,
requirement with zero scenarios (warning), `scope` glob matching nothing
(warning — inert, mirrors WP4 severity doctrine D-S2.4).

### 2.3 CLI surface — `fettle spec`

- `fettle spec lint` — validate all discovered specs (exit 1 on errors).
- `fettle spec list` — table of specs, status, requirement/scenario counts.
- `fettle spec coverage` — scenario→test trace report (upgrades
  `trace_requirements` to scenario granularity and finally wires it into
  the main CLI; JSON with `--json`).

### 2.4 `[gates.bdd]` — the WP-154 gate, advisory-first

Off by default. When enabled (PostToolUse on impl edits + Stop check):
an edited implementation file that matches an **active** spec's `scope`
requires every scenario of that spec to have at least one trace-marked
test; untraced scenarios produce findings. Modes `advisory | enforce`
(registered in WP4's `MODE_ENUMS`), graduation per WP1 backlog #7.
This is *deterministic* — no test execution, no red/green claims —
consistent with tdd_gate's documented philosophy.

### 2.5 Finding ergonomics (WP1 backlog #1 and #4)

- Every bdd/spec finding carries a **`fix` field**: the concrete next
  action ("add `# traces: checkout-flow/S2` to the test covering …").
- `fettle spec coverage --json` emits an **evidence artifact** including
  *passes* (which scenarios are covered by which tests), not only gaps —
  the first gate surface to implement the "evidence on success" principle;
  Stage 5 UAT reuses the shape.

## 3. Out of scope (recorded for later stages)

- Test *generation* from scenarios → Stage 5 (WP3 UAT runner territory).
- Spec freeze/hash lock-in and same-commit co-evolution → Pillar 1 phase 2.
- kgraph/semantic-layer links from spec IDs → Stage 6 (the ID scheme here
  is deliberately the ontology seed: `<spec-id>/R<n>`, `<spec-id>/S<n>`).
- Replacing ux_spec_gate/spec_audit — they stay; bdd gate is additive.

## 4. Implementation slices

| Slice | Content | Tests |
| --- | --- | --- |
| S3.1 | `spec_model.py` parser/lint + `fettle spec lint/list` | parser grammar, lint rules, CLI |
| S3.2 | scenario-granular tracing + `fettle spec coverage` (+ JSON evidence) | marker extraction, coverage report |
| S3.3 | `[gates.bdd]` advisory gate + WP4 registration (MODE_ENUMS, DEFAULTS, schema) | gate behavior, config validation |
| S3.4 | docs (CONFIG.md, README pointer), CHANGELOG, work note | consistency suite |
