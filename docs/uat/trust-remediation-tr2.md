# UAT Report: TR-2 Control Plane and Policy Floors

Date: 2026-11-17 (updated after pull-request review)

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
| Stop unchanged without Git history | Plugin and installed bridge | Pass: non-repository and unborn-repository sessions allow |
| Verification triggered by snapshot or `HEAD` change | Plugin and installed bridge | Pass: message names that cause instead of claiming zero edits |

Findings R-1 through R-6 were reproduced in review on 2026-11-17 and fixed in
this rework. The red and green outputs are retained under
`$TMPDIR/phase-hl/hl11/r1/` through `$TMPDIR/phase-hl/hl11/r6/`.

## Automated evidence

- Installed-path acceptance: 147 passed in 87.34 seconds.
- Targeted TR-2 and review-follow-up regression: 522 passed in 90.55 seconds.
- Full regression on the reworked candidate: 5,323 passed, 20 skipped in
  710.05 seconds.
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

SHIP LOCALLY. The corrected installed scenarios pass in both launch modes, and
all required local criteria are confirmed. The one bounded mutation diagnostic
timed out after 600 seconds as a tool error; it is retained as a non-pass, no
mutation credit is claimed, and remote pull-request mutation evidence remains
required after push.
