# UAT Report: TR-2 Control Plane and Policy Floors

Date: 2026-11-15

## User flow

A coding agent invokes an installed Fettle hook. Fettle resolves repository and
governing policy, protects policy and session control files from in-session
writes, preserves stricter enforcement floors, and reports ignored weakening
attempts through `fettle config --explain`. A repository owner repairs malformed
policy outside the agent session; agent events remain blocked until it loads.

## Scenarios tested

| Scenario | Launch modes | Result |
|---|---|---|
| Edit or create Fettle policy, evidence, redirected state, or host hook settings | Plugin and installed bridge | Pass: enforce mode blocks with recovery guidance |
| Attempt a recognized shell write to the control plane | Plugin and installed bridge | Pass: target is detected and blocked |
| Use advisory protection | Plugin and installed bridge | Pass: warning is visible without a deny decision |
| Attempt agent repair of malformed or remotely incomplete policy | Plugin and installed bridge | Pass: the edit blocks with owner recovery guidance |
| Disable a protected check in repository policy | Resolver and installed hook | Pass: the check still runs and `config --explain` reports the ignored attempt |
| Weaken an organisation, remote, or capsule floor | Resolver and installed hook | Pass: the stricter modeled enforcement value wins |
| Load a missing, malformed, or tampered declared remote policy | Installed hook | Pass: outcome blocks with `fettle policy sync` guidance |
| Change effective policy after session start | Stop hook and Assurance Record | Pass: Stop blocks and policy integrity is non-pass |
| Resolve trace and gate state from different repositories | Hook checks | Pass: redirected state and repository root remain isolated |
| Commit, amend, or switch branches after a code edit | Plugin and installed bridge | Pass: Stop compares code-changing commits with session-start `HEAD`; documentation-only commits allow |
| Send advisory and blocking targets in either order | Plugin and installed bridge | Pass: every target runs, the block wins, and one advisory summary reports its target count |
| Move a patch target into protected config | Plugin and installed bridge | Pass: the move destination is protected |
| Send malformed native pre-tool input | Plugin and installed bridge | Pass: Claude and Gemini pre-tool names block; malformed non-pre-tool input remains a traced allow |
| Attempt to delete redirected session state after a shell edit | Plugin and installed bridge | Pass: the governed delete blocks before execution; state remains and Stop blocks without verification |
| Remove session-start evidence after changing code, then Stop | Plugin and installed bridge | Pass: Stop does not recreate evidence and blocks for missing verification |
| Stop as the first event in a clean tree | Plugin and installed bridge | Pass: Stop allows with a policy-integrity advisory and creates no session-start record |

## Automated evidence

- Installed-path acceptance: 86 passed in 27.41 seconds.
- Full regression on the secured TR-2 commit: 5,191 passed, 20 skipped, with
  the one known `test_module_cli_validates_reports` wall-clock failure inherited
  from `main`.
- Ruff: clean.
- Fettle scan: successful with the same three legacy protocol-print warnings
  already present in TR-1.

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

SHIP. The final installed-path UAT reported 110 passed in both launch modes,
and all required package gates passed. The fresh bounded mutation preflight
timed out after 7,200 seconds and is retained as a truthful non-result; no
narrow replay was authorized and no mutation credit is claimed.
