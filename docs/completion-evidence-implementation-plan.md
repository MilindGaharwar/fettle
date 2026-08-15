# Completion Evidence Implementation Plan

Status: complete

UX contract: [completion-evidence.ux-spec.md](completion-evidence.ux-spec.md)

## Objective

Correct P63's false completion record, obtain genuine installed-CLI success
evidence, and make contradictory completion claims mechanically impossible in
normal Fettle completion and release paths.

## Assumptions And Boundaries

- `c2be709` is retained; corrections use a new commit.
- Existing unrelated `fettle/bdd_gate.py` changes and its backup are excluded.
- Markdown is explanatory, not an authority source.
- Full mutation runs remain held-out verification and are not used to debug the
  preflight timeout.
- Missing or malformed consequential evidence remains non-pass.

## Work Packages

### WP1: Correct P63

- [x] Mark P63 and UAT in progress; reopen copied-command and installed-success
  criteria while preserving valid implementation/error-path evidence.
- [x] Reproduce the clean-sample timeout from retained inputs and identify its
  exact stage.
- [x] Add a deterministic minimal preflight-success fixture.
- [x] Fix the root cause without broadening scope or reinterpreting timeout.
- [x] Run an installed wheel in a fresh environment and require exit 0,
  `completed`, `passed`, generated > 0, generated = canonicalized, zero rejected,
  and zero collisions.
- [x] Update P63 UAT and status only after successful evidence exists.

### WP2: Structured Completion Contract

- [x] Add a strict versioned completion-manifest parser and derived evaluator.
- [x] Add permanent complete, timeout, error-path, contradictory, malformed,
  duplicate, missing, and stale fixtures.
- [x] Add `fettle completion validate` with matching human/JSON decisions and
  exit 0/1/2 semantics.
- [x] Extend UAT reports with derived completion fields without breaking legacy
  report reads.

### WP3: Enforcement

- [x] Add a completion gate using the shared validator.
- [x] Register the gate for Stop and changed-file validation within its budget.
- [x] Require completion validation in CI.
- [x] Extend release/tag validation to reject invalid complete claims.
- [x] Enable dogfood enforcement for this repository.

### WP4: Durable Learning

- [x] Add the P63 incident as a named behavioral regression.
- [x] Update repository agent instructions and persistent knowledge guidance.
- [x] Update `discipline-uat` and add a behavioral eval proving implementation
  complete + timed-out success UAT means milestone incomplete.

### WP5: Verification And Shipping

- [x] Run focused completion, UAT, mutation, CLI, registry, and release tests.
- [x] Run the full repository suite; classify unrelated failures explicitly.
- [x] Run installed CLI UAT for complete, incomplete, malformed, and P63 flows.
- [x] Run Ruff, config validation, `git diff --check`, kgraph impact, and
  `fettle check --changed`.
- [x] Keep the final change set limited to intended files; do not push.

## Completion Contract

This plan is complete only when every checkbox is checked and its required
success scenarios have passing evidence. A timeout can prove timeout handling;
it cannot close a success criterion.
