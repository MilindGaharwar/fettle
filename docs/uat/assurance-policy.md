# UAT Report: Assurance Sufficiency Policy

Date: 2026-08-27

## Scenarios Tested

| Scenario | Persona | Surface | Result |
|---|---|---|---|
| Inspect a partial record | New maintainer | Human CLI | PASS: every dimension includes a status, reason where applicable, and evidence or `none` |
| Evaluate a matching named policy | Release owner | Human CLI | PASS: policy reports PASS and exits 0 |
| Evaluate a mismatching policy | Power user/agent | JSON CLI | PASS: policy reports FAIL with criteria and exits 1 |
| Evaluate malformed policy | Release owner | Human CLI | PASS: configuration error is named and exits 2 |
| Retain incomplete security review | Release owner | Record builder | PASS: security remains UNKNOWN |

## Accessibility And Performance

- Keyboard-only/non-interactive: PASS.
- Statuses are conveyed with words, not symbols alone: PASS.
- Local response: under one second in manual runs.
- Browser, mobile, axe, and visual checks: not applicable to the terminal-only flow.

## Residual Risk

- `.fettle/security-review.json` is digest-bound in Assurance Record v1 but is
  not yet canonical producer/source/policy-bound evidence. Consumers requiring
  that trust level must keep security non-authoritative until its producer emits
  the canonical evidence contract.
- P54/P55 completion evidence was refreshed against the final-tree full-suite
  run because P81 changes their shared CLI scope.

## Decision: SHIP

The P81 behavior and repository completion evidence are ready to ship.
