# UX Spec: Add-in Assurance Pilot

Status: PROPOSED; planning only; implementation is not authorized

Related: [implementation plan](add-in-assurance-implementation-plan.md),
[Assurance Integrity](assurance-integrity.ux-spec.md), and
[canonical evidence contract](evidence-artifact-contract.md)

## Job To Be Done

When I evaluate an optional analyzer against a real software change, I want its
identity, permissions, coverage, outcome, and operating cost recorded beside the
existing Assurance Record, so I can judge whether the analyzer adds trustworthy
value without allowing it to weaken or replace Fettle's current authority.

## Personas

- New maintainer: needs one existing command, a clear shadow-only label, and one
  recovery action for each non-pass state.
- Power user or automation: needs deterministic JSON, stable exit codes, exact
  bindings, and no interactive prompts.
- Release owner: needs proof that optional evidence did not change the release
  decision and cannot independently establish PASS.
- Accessible terminal user: needs text labels and paths; color and symbols are
  never required to interpret a result.

## Journey And Budget

| Phase | User action | Sees | Expected state | Recovery |
|---|---|---|---|---|
| Prepare | Runs `fettle doctor` | Ruff identity and add-in readiness | Confident | Install or pin the named prerequisite |
| Inspect | Runs `fettle pipeline` | Static add-in state, capabilities, and authority class | In control | Correct the manifest or policy mismatch |
| Execute | Runs `fettle integrations ruff-shadow` | `SHADOW PASS`, `SHADOW FAIL`, or `UNKNOWN`, never release authority | Informed | Follow one exact rerun or repair action |
| Assess | Runs `fettle assurance --policy production` | The unchanged policy decision plus the optional evidence reference | Confident | Resolve first-party evidence independently |
| Compare | Reviews the shadow ledger | Baseline/candidate differences and measured effort | Able to decide | Classify or reject every discrepancy |

- Common flow: the existing `integrations` and `assurance` commands; no new
  top-level command and no prompts.
- Experienced-user setup budget after configuration: under two minutes.
- Assurance validation budget remains under one second locally.
- Pilot add-in execution p95 budget: 30 seconds.
- Default output shows status, shadow-only authority, covered scope, elapsed
  time, evidence path, and one recovery action. Digests and environment identity
  remain in JSON and the sidecar.

## Required States

- First-time empty: the add-in is absent or disabled; output explains that it is
  optional and gives the exact configuration action. Assurance is unchanged.
- Cleared empty: deleting or invalidating the sidecar immediately removes the
  optional parent reference; no prior result remains current.
- Filtered empty: no Python files are present in the canonical scope; the result
  is `NOT_APPLICABLE` with the inspected scope recorded.
- Loading brief: the command remains quiet until bounded execution completes.
- Loading long: the declared deadline terminates execution as `UNKNOWN` and
  invalidates the prior sidecar.
- Populated clean: Ruff completes over every applicable file and emits
  `SHADOW PASS`; Assurance displays the reference but does not change verdict.
- Populated findings: Ruff findings emit `SHADOW FAIL`; Assurance still derives
  authority solely from existing admitted dimensions.
- Recoverable error: missing executable, unsupported version, stale identity,
  malformed output, or incomplete scope emits `UNKNOWN` and one rerun action.
- Fatal error: path escape, symlink escape, capability escalation, output-limit
  breach, or persistence failure exits 2 and cannot preserve an older result.
- Offline: the local pilot works without network access; any declared network
  capability is incompatible with the pilot policy.
- Stale or revoked: a changed executable, manifest, source, policy, or scope, or
  a revoked manifest, invalidates the result and prevents execution or reuse.

## Information Architecture

- Entry point: existing `fettle integrations ruff-shadow [--json]`.
- Readiness: existing `fettle doctor` integration section.
- Static inspection: existing `fettle pipeline` output.
- Authority decision: existing `fettle assurance --policy NAME`.
- Evidence: `.fettle/add-ins/ruff-shadow/` with a raw report and canonical
  sidecar; no database, daemon, registry, marketplace, or agent configuration.
- Pilot comparison: append-only documentation register under `docs/engagement/`.
- Back/navigation behavior: not applicable to the non-interactive CLI.
- State persists only as repository-local portable artifacts and reviewed
  configuration. No automatic policy mutation or remembered approval exists.

## Accessibility And Cognitive Load

- Human and JSON output derive from one result object.
- Status is always written as `SHADOW PASS`, `SHADOW FAIL`, `UNKNOWN`,
  `NOT_APPLICABLE`, or `REVOKED`; color is optional decoration.
- The first screen contains at most: status, authority class, coverage summary,
  elapsed time, evidence path, and recovery action.
- Findings are bounded and summarized; full bounded detail remains in the raw
  report.
- Errors use operator language and never expose secrets or absolute checkout
  paths in canonical evidence.

## BDD Scenarios

### Scenario: Clean shadow result cannot grant authority

Given the draft Ruff add-in manifest and exact executable identity are valid
And Ruff reports no findings over every applicable file in the canonical scope
When the operator runs the add-in and production assurance
Then the add-in emits canonical `SHADOW PASS` evidence
And the Assurance Record references it as advisory evidence
And the production decision is identical to the decision without that evidence.

### Scenario: Findings remain visible but non-authoritative

Given Ruff reports one or more findings over the complete applicable scope
When the operator runs the add-in
Then the result is `SHADOW FAIL`, findings and coverage are retained, and the
output names the evidence path
And no existing Assurance dimension is silently replaced or downgraded.

### Scenario: Capability escalation is rejected before execution

Given the manifest requests network, repository writes, an undeclared
environment variable, or a command outside the approved fixed invocation
When the operator runs the add-in
Then Fettle exits 2 without invoking Ruff
And the output identifies the incompatible capability without exposing secrets.

### Scenario: Invalid identity cannot reuse an old pass

Given a prior shadow sidecar passed
And the executable, manifest, source, policy, scope, or adapter implementation
has changed
When the operator reruns or evaluates assurance
Then the old sidecar is invalidated and the add-in is `UNKNOWN`
And the old pass cannot appear current.

### Scenario: Revocation prevents execution and reuse

Given a human-reviewed manifest is in `revoked` state
When the operator explicitly requests the add-in or evaluates retained evidence
Then Fettle does not execute it, reports `REVOKED`, and rejects retained results.

### Scenario: Malformed output fails visibly

Given Ruff exits successfully but its output is malformed, truncated, oversized,
or inconsistent with its exit code
When the adapter validates the result
Then it emits `UNKNOWN`, invalidates prior authority, and exits 2.

### Scenario: Timeout is contained as an execution failure

Given Ruff exceeds the configured wall-clock deadline
When the adapter terminates it
Then the result is `UNKNOWN`, elapsed time and timeout are recorded, and no
partial output becomes complete evidence.

### Scenario: Non-applicable scope is explicit

Given the canonical changed scope contains no Python files
When the operator runs the add-in
Then the result is `NOT_APPLICABLE`, the inspected scope is bound, and no files
are silently omitted from a claimed complete Python scope.

### Scenario: Replay reproduces content, not occurrence

Given identical source, policy, scope, manifest, executable, configuration, and
normalized Ruff observations
When the assessment is replayed in a compatible environment
Then the canonical content digest matches
And the observation identifier and observation time remain distinct.

### Scenario: Host isolation is not overstated

Given the pilot runs a trusted, pinned Ruff executable in a subprocess
When the operator inspects the result
Then the output describes declared and observed capabilities
And it does not claim that Fettle supplied an OS sandbox or prevented behavior
that the host did not technically contain.

## Success Criteria

- The normal journey uses existing commands and never adds release authority.
- Missing, malformed, partial, stale, conflicting, or revoked add-in evidence is
  visible and never satisfies a release criterion.
- Every result binds the exact source, effective policy, canonical scope,
  manifest, executable, adapter implementation, configuration, and output.
- A direct pinned Ruff invocation and the adapter agree on normalized findings
  for every accepted pilot assessment.
- Human and JSON output agree and always identify the result as shadow-only.
- Every non-pass gives one safe recovery action.
