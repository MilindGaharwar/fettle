# UX Spec: Completion Evidence

Status: implementation contract

## Jobs To Be Done

When I review or release a milestone, I want completion to be derived from its
required evidence, so a timeout, skipped check, or missing artifact can never be
reported as successful completion.

When work is incomplete, I want one precise reason and recovery action without
losing valid implementation or error-path evidence.

## Personas

- New maintainer: needs `fettle completion validate` to state whether work is
  complete and what to run next.
- Power user or agent: needs deterministic JSON, criterion-level verdicts, and
  fail-closed schema validation.
- Release owner: needs commit, Stop, CI, and tag paths to reject contradictory
  completion claims.
- Accessible terminal user: needs textual states and exit codes independent of
  color or interactivity.

## Journey

| Phase | User action | Sees | Failure prevented |
|---|---|---|---|
| Record | Updates a milestone manifest | Required criteria and typed evidence | Prose becoming authority |
| Validate | Runs `fettle completion validate` | Complete or incomplete plus exact reasons | Timeout interpreted as pass |
| Recover | Runs the displayed command | New criterion evidence | Ambiguous remediation |
| Complete | Changes status to complete | Success only when every required criterion passes | Premature checkbox closure |
| Release | Commits, stops, or tags | Enforcement of the same decision | Local/CI disagreement |

## Flow And Budget

1. Maintain `docs/completion/<milestone>.json` beside the human report.
2. New work items use `fettle-work-item: v2`; record evidence and a same-ID
   completion manifest before changing the work item to `status: done`.
3. Run `fettle completion validate`.
4. If incomplete, run the displayed recovery command and update evidence.

- Common flow: one validation command, one recovery command after failure.
- Validation performs local bounded file reads only and targets less than 100 ms
  for 100 manifests.
- Human and JSON output derive from one result object.

## Required States

- First-time empty: no manifests is valid and reports no completion claims.
- Cleared empty: an `in_progress` manifest with no completed criteria remains
  visibly incomplete, not erroneous.
- Filtered empty: validating an unknown milestone exits 2 and names it.
- Loading brief: validation is synchronous with no progress animation.
- Loading long: not applicable; exceeding the bounded budget is a tool error.
- Populated: each milestone shows status and required criterion verdicts.
- Error recoverable: a required non-pass criterion exits 1 with its recovery.
- Error fatal: malformed, duplicate, unsupported, unsafe, or contradictory
  evidence exits 2 and cannot establish completion.
- Offline: validation remains local and deterministic.
- Stale: revision-bound evidence for another revision is non-pass.

## Information And Accessibility

- Entry point: `fettle completion validate [--milestone ID] [--json]`.
- Default output shows milestone decision and non-pass required criteria only.
- JSON preserves all bounded criteria and reasons.
- States use words and stable exit codes, not color.
- Operation is keyboard-only and non-interactive.
- Markdown UAT reports remain explanatory; the JSON manifest is authoritative.

## Evidence Semantics

- Criterion kinds are `success` and `error_path`.
- A required success criterion passes only with verdict `confirmed`.
- A required error-path criterion passes only with verdict `confirmed`; its
  evidence may describe an observed timeout or failure without promoting that
  outcome to success elsewhere.
- `timeout`, `blocked`, `unobserved`, `indeterminate`, `skipped`, `missing`, and
  `failed` are non-pass verdicts.
- `complete` is derived. A manifest claiming `complete` while any required
  criterion is non-pass is contradictory and invalid.
- One evidence reference cannot satisfy criteria with different expected
  outcomes.
- Missing, malformed, stale, or unsupported evidence is never a pass.

## BDD Scenarios

### Scenario: Required success is confirmed

Given every required success criterion has independently observed passing evidence
When completion is validated
Then the milestone is complete and validation exits 0.

### Scenario: Required success times out

Given a required installed-CLI success criterion
When its observed verdict is timeout
Then the milestone remains incomplete and validation exits 1.

### Scenario: Timeout confirms only an error path

Given an error-path criterion requires demonstrating timeout handling
When a timeout is observed and the handling matches expectations
Then that error-path criterion may be confirmed
And no success criterion is confirmed by the same observation.

### Scenario: Required evidence is absent

Given a required criterion has no evidence reference
When completion is validated
Then validation exits 2 with a missing-evidence reason.

### Scenario: Completion claim contradicts evidence

Given a manifest claims complete or a UAT decision claims SHIP
And a required criterion is timeout, blocked, skipped, or unobserved
When completion is validated
Then validation exits 2 and names the contradiction.

### Scenario: Honest work in progress remains valid

Given a manifest is in progress with one required timeout criterion
When completion is validated
Then the manifest is valid but incomplete and validation exits 1.

### Scenario: Human and JSON decisions agree

Given complete and incomplete manifests
When validation is rendered as human text and JSON
Then milestone status, criterion verdicts, reasons, and recovery actions match.

### Scenario: Release cannot bypass invalid completion

Given a changed manifest claims complete with non-pass required evidence
When the user stops, commits, CI validates, or creates a release tag
Then the applicable enforcement path rejects the claim with the same reason.

## Success Criteria

- The P63 timeout cannot coexist with an authoritative complete claim.
- Every required criterion maps to typed, existing evidence.
- In-progress work remains representable without weakening enforcement.
- CLI, Stop, commit/CI, and release paths share one validator.
- The exact P63 incident remains a permanent regression fixture.
