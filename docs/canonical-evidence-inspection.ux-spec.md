# UX Spec: Canonical CI Evidence Inspection

Status: P68 implementation contract

Implementation plan:
[fettle-evolution-implementation-plan.md](fettle-evolution-implementation-plan.md#p68-ci-trace-and-inspection-binding-p0)

## Jobs To Be Done

When I check remote CI, I want the result bound to the exact candidate, policy,
scope, producer, toolchain, completeness, and execution occurrence, so copied or
stale evidence cannot authorize my push.

When evidence is rejected, I want `fettle explain` and `fettle report` to show
the same safe reason and one recovery command, so I can restore trustworthy
evidence without reading artifact JSON.

When I inspect local history, I want canonical references clearly labeled as
available diagnostics rather than attestations, so trace retention cannot be
mistaken for durable proof.

## Personas

- New adopter: expects `fettle ci status|wait` and the existing Stop-gate flow
  to remain concise and recoverable.
- Power user or agent: needs deterministic JSON, exact accepted/rejected
  reasons, and complete bounded bindings.
- Repository maintainer: needs independent CI authority, additive trace data,
  legacy rollback, rotation, and no new persistence service.
- Accessible terminal user: needs state conveyed by text and exit codes, never
  color, animation, or an interactive prompt.

## User Journey

| Phase | User action | Sees | Desired feeling | Failure to prevent |
|---|---|---|---|---|
| Entry | Runs `fettle ci status` or `fettle ci wait` | Existing concise remote verdict | Familiar | Local verification substituting for CI |
| Record | CI query completes | Existing stamp plus canonical sidecar | Confident | Partial evidence appearing successful |
| Gate | Stops after a push | Allow, or one typed rejection and `fettle ci wait` | Certain | Copied evidence authorizing another candidate |
| Inspect | Runs `fettle explain --detailed` | Producer, scope, bindings, result, completeness, freshness, validity | Informed | Trace being described as attestation |
| Aggregate | Runs `fettle report` or `--json` | Matching evidence acceptance/rejection counts and recent reasons | Oriented | Human and JSON decisions disagreeing |
| Recover | Runs the displayed command | Fresh independently queried CI evidence | Unblocked | Ambiguous repair choices |

## Flow And Budgets

1. Run `fettle ci wait` after pushing.
2. If the Stop gate rejects evidence, run the displayed `fettle ci wait` again.
3. Optionally run `fettle explain --detailed` for bindings and rejection detail.

- Interaction budget: one command normally, one rerun after invalidation.
- CI querying keeps its existing network timeout and polling behavior.
- Stop-hook validation remains within its existing 100 ms budget and performs
  no network access.
- Trace references remain bounded by existing entry, retention, and rotation
  limits; full artifacts remain repository-local sidecars.

## Required States

### First-Time Empty

No CI stamp or artifact exists. After a recorded push, the gate says remote CI
was never checked and prints `Run: fettle ci wait`. Explain/report retain their
existing useful empty-state text.

### Cleared Empty

The remote query completed but found no workflow runs. This is `unknown`, never
pass, and the output says no runs were found.

### Filtered Empty

No workflows match the exact candidate. The result is the same visible no-runs
non-pass; Fettle does not broaden the query to another revision.

### Loading Brief

`status` performs one query and returns the current state without extra noise.

### Loading Long

`wait` retains existing bounded progress updates. Timeout or pending CI remains
non-pass and keeps one recovery command.

### Populated

The legacy stamp and canonical sidecar describe the same remote runs, exact
candidate, effective policy, selected workflow scope, Fettle producer,
GitHub Actions toolchain, result, completeness, and occurrence. Detailed
inspection says `valid` and whether policy accepted the observation.

### Error Recoverable

Missing, unavailable, malformed, tampered, incomplete, stale, wrong-source,
wrong-policy, wrong-scope, or wrong-producer evidence names that reason and
prints `Run: fettle ci wait`.

### Error Fatal

An unsupported schema, unsafe payload, impossible run identity, or failed
atomic persistence cannot leave a parseable new success. The gate fails closed
when a stamp claims canonical evidence that cannot be validated.

### Offline

The remote query reports a tool/network error and exits 2. Previously retained
trace data may be inspected as diagnostic history but cannot authorize CI.

### Stale Or Superseded

A candidate, policy, scope, producer, implementation, schema, or occurrence
change rejects the artifact. A timestamp alone cannot restore applicability.

## Information And Disclosure

- No new command or navigation is introduced.
- Default CI output remains the concise remote verdict and recovery action.
- `fettle explain --detailed` shows canonical evidence details; the default
  explain view stays concise.
- `fettle report` adds aggregate accepted/rejected evidence counts and recent
  rejection reasons; `--json` preserves the corresponding bounded records.
- Every trace-retained canonical item includes explicit availability and the
  label `diagnostic_only`; it is never called signed, attested, or authoritative
  merely because its content digest validates.
- Legacy CI stamps and trace v1/v2 entries remain readable for rollback. A
  stamp that claims canonical evidence must validate it and cannot fall back.

## Accessibility

- Every state has a textual name and stable exit behavior.
- Output remains understandable with `NO_COLOR=1` and in a non-TTY.
- Digest prefixes are labels, not the only indication of validity.
- Human and JSON output derive from the same stored inspection fields.
- Recovery requires no mouse, color recognition, animation, or prompt.

## BDD Acceptance Scenarios

### Scenario: Independent CI evidence is accepted

Given GitHub Actions returns complete green runs for the pushed candidate
When `fettle ci wait` records the result
Then the sidecar binds candidate, policy, workflow scope, producer, toolchain,
result, completeness, and a unique observation ID
And the Stop gate accepts only that exact occurrence and bindings.

### Scenario: Copied evidence cannot authorize another candidate

Given a valid green CI artifact and stamp for candidate A
When either is copied into the stamp for candidate B or a prior run occurrence
Then the gate rejects it with the exact mismatch reason
And prints `Run: fettle ci wait`.

### Scenario: Local evidence cannot substitute for CI

Given local verification or local trace records a passing observation
When no independently queried CI artifact exists for the push
Then the CI gate remains non-pass
And no local reference is promoted to CI authority.

### Scenario: Invalid remote evidence fails closed

Given CI is missing, pending, red, unavailable, malformed, incomplete, or from
the wrong policy, scope, producer, or occurrence
When the consequential gate evaluates it
Then it cannot map to pass or allow
And the typed validity and recovery action are inspectable.

### Scenario: Trace retains a portable diagnostic reference

Given canonical CI evidence has been produced
When the decision is appended to trace
Then trace stores a bounded portable reference with explicit availability,
inspection result, and `diagnostic_only`
And it does not embed source bodies, secrets, absolute paths, or an attestation.

### Scenario: Trace loss cannot manufacture acceptance

Given a canonical CI sidecar exists
When trace append fails, trace rotates, or retained history is unavailable
Then CI validation still uses the independently persisted sidecar and stamp
And the trace failure remains visible without converting any result to pass.

### Scenario: Legacy trace replay remains readable

Given trace v1 or existing v2 evidence entries without canonical fields
When explain and report read them
Then they preserve existing output without guessing canonical validity
And truncated legacy IDs are not promoted to artifact digests.

### Scenario: Human and JSON inspection agree

Given accepted and rejected canonical references in trace
When the user runs explain/report in human and JSON modes
Then producer, scope, source/policy binding, result, completeness, freshness,
availability, validity, acceptance, and recovery are semantically identical.

### Scenario: P41 integration remains a boundary

Given a canonical artifact digest and immutable candidate identity
When a future P41 implementation adds a signature or platform attestation
Then it binds those identities without defining another evidence schema
And P68 itself makes no signed or durable-attestation claim.

## Success Criteria

- Missing or invalid consequential evidence never maps to pass.
- CI evidence cannot authorize another revision, policy, scope, producer, or
  occurrence, and local verification cannot substitute for remote CI.
- Atomic sidecar/stamp writes cannot leave a parseable new success.
- Trace redaction, bounds, rotation, visible append failure, and tolerant legacy
  reads remain intact.
- Explain/report human and JSON decisions match for accepted and rejected
  evidence.
- Installed-CLI UAT covers green, red, unavailable, copied, legacy, trace-loss,
  and recovery flows with Stop-gate validation below 100 ms.
