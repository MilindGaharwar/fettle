# UX Spec: Assurance Integrity

Status: proposed implementation contract

Related: [assurance-policy.ux-spec.md](assurance-policy.ux-spec.md),
[assurance-integrity-implementation-plan.md](assurance-integrity-implementation-plan.md)

## Job To Be Done

When I review an agent-generated change for release, I want one evidence-linked
decision for the exact subject, effective policy, and scope, so stale, forged,
incomplete, contradictory, or misbound evidence cannot authorize it.

## Personas

- New maintainer: needs a plain-language decision and one precise next action.
- Power user or agent: needs deterministic JSON and stable exit codes.
- Release owner: needs every required PASS backed by canonical evidence.
- Accessible terminal user: needs words and evidence paths, not color or symbols
  alone.

## Journey And Budget

| Phase | User action | Sees | Recovery |
|---|---|---|---|
| Prepare | Runs producer diagnostics and evidence commands | Which required producers are ready | Correct the named environment or configuration issue |
| Assess | Runs `fettle assurance --policy NAME` | One decision for the exact subject, policy, and scope | Run the command named by each non-pass dimension |
| Reassess | Reruns assurance after producing evidence | Superseded evidence removed from authority | Investigate any remaining conflict or invalid binding |
| Export | Reads the persisted Assurance Record | Portable canonical evidence with accepted parent references | Reassess if persistence is missing, stale, or invalid |

- Common flow: one command and no prompts.
- Local identity and artifact validation should normally finish within one
  second.
- Git and tool operations must be bounded and fail visibly.
- Human and JSON output derive from the same result object.

## Required States

- First-time empty: every applicable dimension is `UNKNOWN`; no absent artifact
  establishes `NOT_APPLICABLE`.
- Cleared empty: removing a canonical sidecar immediately removes authority from
  its raw report.
- Filtered empty: an unknown policy is a configuration error.
- Loading brief: local identity and artifact validation remains quiet.
- Loading long: unexpected unbounded work or a hung Git/tool operation terminates
  as a visible environment error rather than reusing old evidence.
- Populated: every PASS identifies canonical evidence bound to the same subject,
  effective policy, scope, producer, and execution.
- Recoverable error: missing, stale, incomplete, unsupported, or incorrectly
  bound evidence reports `UNKNOWN` and a concrete producer command.
- Fatal error: malformed policy, unresolved source identity, unsafe path, or
  persistence failure exits 2 and cannot authorize release.
- Offline: local evidence evaluation remains deterministic; unavailable remote
  evidence stays non-pass.
- Stale or conflicting: a newer failure, conflicting occurrence, or old subject
  binding cannot be hidden by an earlier pass.

## Accessibility And Cognitive Load

- Text labels and reasons remain authoritative; symbols and color are optional
  decoration only.
- The first screen reports the policy decision, assessed subject, completeness,
  and failing dimensions before detailed evidence references.
- Each non-pass gives one primary recovery command where a command exists.
- Command syntax and unqualified JSON output remain compatible with the v1 UX
  contract.

## BDD Scenarios

### Scenario: Raw green report has no authority

Given a raw verify or CI report says green but its canonical sidecar is absent
When the user evaluates a policy requiring that dimension
Then the dimension is UNKNOWN, the policy fails, and the output names the rerun
command.

### Scenario: Completed mutation did not pass

Given a mutation report is complete but its domain result says `passed = false`
When the user evaluates behavior assurance
Then behavior is FAIL even if an older retained verification result passed.

### Scenario: Evidence belongs to another subject

Given complete canonical evidence is bound to another source snapshot, policy,
or scope
When the user assesses the current change
Then the evidence is rejected with its exact binding mismatch and cannot satisfy
policy.

### Scenario: Provenance anchor is forged or drifted

Given an anchor is malformed, names another commit, diverges from the ledger
prefix, or has unaccepted post-anchor records
When the user evaluates provenance
Then provenance is non-pass and distinguishes tampering from ordinary drift.

### Scenario: Equivalent clones are portable

Given two equivalent checkouts have the same source, policy, scope, and evidence
but different absolute locations
When both build an Assurance Record
Then their canonical record digests are equal.

### Scenario: Persistence cannot preserve an old pass

Given an older persisted record passed and the current assessment fails to write
its replacement
When the command finishes
Then it exits 2 and the older record cannot appear current.

### Scenario: Valid negative evidence remains failure

Given a canonical, complete, correctly bound producer artifact reports a
violation
When assurance evaluates its dimension
Then the dimension is FAIL, not UNKNOWN, and cites the accepted artifact.

## Success Criteria

- Only valid, complete, admitted canonical evidence can establish PASS.
- Raw reports remain readable diagnostics but never independently authorize.
- Applicability is explicit; absence never silently becomes not applicable.
- The effective layered policy and repository-derived scope are digest-bound.
- Human and JSON compatibility is preserved while authority becomes stricter.
- Every error state gives a reason and, where possible, one recovery action.
