# UAT Report: TR-2 Control Plane and Policy Floors

Date: 2026-11-15

## User flow

A coding agent invokes an installed Fettle hook. Fettle resolves repository and
governing policy, protects policy and session control files from in-session
writes, preserves stricter enforcement floors, and reports ignored weakening
attempts through `fettle config --explain`. A repository owner can still repair
a malformed root policy instead of being locked out by that malformed file.

## Scenarios tested

| Scenario | Launch modes | Result |
|---|---|---|
| Edit or create Fettle policy, evidence, redirected state, or host hook settings | Plugin and installed bridge | Pass: enforce mode blocks with recovery guidance |
| Attempt a recognized shell write to the control plane | Plugin and installed bridge | Pass: target is detected and blocked |
| Use advisory protection | Plugin and installed bridge | Pass: warning is visible without a deny decision |
| Repair a malformed root `.fettle.toml` | Plugin and installed bridge | Pass: the policy file itself remains repairable |
| Disable a protected check in repository policy | Resolver and installed hook | Pass: the check still runs and `config --explain` reports the ignored attempt |
| Weaken an organisation, remote, or capsule floor | Resolver and installed hook | Pass: the stricter modeled enforcement value wins |
| Load a missing, malformed, or tampered declared remote policy | Installed hook | Pass: outcome blocks with `fettle policy sync` guidance |
| Change effective policy after session start | Stop hook and Assurance Record | Pass: Stop blocks and policy integrity is non-pass |
| Resolve trace and gate state from different repositories | Hook checks | Pass: redirected state and repository root remain isolated |

## Automated evidence

- Installed-path acceptance: 86 passed in 27.41 seconds.
- Full regression after the mutation cleanup change: 5,195 passed, 20 skipped
  in 623.86 seconds.
- Ruff: clean.
- Fettle scan: successful with the same three legacy protocol-print warnings
  already present in TR-1.
- Mutation cleanup regressions: 338 passed, including restored bytes,
  mode-only restoration, and delayed backup visibility.

## Manual protocol

The installed plugin and bridge commands were exercised with observable allow,
advisory, and block outcomes. Recovery text was checked for malformed local
policy and unavailable declared remote policy. This is a CLI/hook change; there
is no browser page or DOM surface, so axe-core is not applicable.

## Severity assessment

No critical, high, medium, or low user-flow defects remain in the exercised
TR-2 behavior. Mutation verification is an unresolved release-evidence blocker,
not a hidden UAT pass.

## Decision

FIX_FIRST. User acceptance behavior passes, but TR-2 cannot ship until a
successful mutation preflight authorizes the required narrow replay and that
replay completes within 60 minutes.
