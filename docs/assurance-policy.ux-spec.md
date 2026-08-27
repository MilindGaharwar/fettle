# UX Spec: Assurance Sufficiency Policy

Status: implementation contract

## Jobs To Be Done

When I review an agent-generated change for release, I want one evidence-linked
answer to why it is trustworthy, so I can distinguish a releasable change from
missing, failed, or indeterminate assurance.

## Personas

- New maintainer: needs plain-language statuses and a precise next action.
- Power user or agent: needs deterministic JSON and stable exit codes.
- Release owner: needs policy mismatches and malformed policy to fail closed.
- Accessible terminal user: needs words and evidence paths, not color or symbols
  alone.

## Journey And Budget

| Phase | User action | Sees | Failure prevented |
|---|---|---|---|
| Inspect | Runs `fettle assurance` | Every dimension, reason, and evidence path | Unsupported confidence claims |
| Decide | Adds `--policy production` | PASS/FAIL decision and criterion mismatches | Prose interpreted as release authority |
| Recover | Follows the reported missing evidence or policy reason | A concrete artifact or policy correction | Guesswork after failure |
| Automate | Adds `--json` | The same record and policy decision | Human/machine disagreement |

- Common flow: one command and no prompts or clicks.
- Local artifact reads should complete in under one second.
- JSON and human output derive from the same result object.

## Required States

- First-time empty: dimensions are `UNKNOWN` or `NOT_APPLICABLE` with reasons;
  no absence becomes a pass.
- Cleared empty: removing retained evidence immediately returns the affected
  dimension to `UNKNOWN`.
- Filtered empty: an unknown policy name is a configuration error naming the
  missing table.
- Loading brief: synchronous local reads remain quiet.
- Loading long: not applicable; no network or unbounded scan occurs.
- Populated: each assertion shows actual status, expected status, and evidence.
- Error recoverable: a valid policy mismatch exits 1 and names each mismatch.
- Error fatal: malformed or unsupported policy exits 2 and cannot authorize a
  release.
- Offline: evaluation remains local and deterministic.
- Stale: stale or incomplete evidence remains non-pass at its source dimension.

## Information And Accessibility

- Entry point: `fettle assurance [--root .] [--policy NAME] [--json]`.
- Default output starts with `Why should I trust this change?` and includes
  textual status labels plus evidence references for every assertion.
- `--policy` evaluates `[assurance.release.<NAME>]` in `.fettle.toml`.
- A value is an exact required status or alternatives separated by `|`.
  Provenance uses the documented `COMPLETE|PARTIAL` vocabulary; other
  dimensions use `PASS|FAIL|UNKNOWN|NOT_APPLICABLE`.
- Policy evaluation is non-interactive and conveys no information by color.

## BDD Scenarios

### Scenario: Production policy passes

Given every configured production criterion matches the assurance vector
When the user runs `fettle assurance --policy production`
Then the policy decision is PASS, every assertion names its evidence, and the
command exits 0.

### Scenario: Required evidence is absent

Given production requires security PASS and no complete security review is retained
When the user evaluates the production policy
Then security is reported as UNKNOWN, the policy decision is FAIL, and the
command exits 1.

### Scenario: Policy allows alternatives

Given production permits independence `PASS|UNKNOWN`
When independence is UNKNOWN
Then that criterion passes without changing the underlying vector status.

### Scenario: Policy is malformed

Given the selected policy contains an unknown dimension or unsupported status
When the user evaluates it
Then evaluation reports a configuration error and exits 2.

### Scenario: Human and JSON output agree

Given a policy has passing and failing criteria
When the user requests human output and JSON output
Then both expose the same policy status, actual values, expected values, reasons,
and evidence references.

## Success Criteria

- Missing, malformed, partial, or conflicting evidence never satisfies policy.
- Every human assertion includes evidence references or explicitly says `none`.
- Policy evaluation does not mutate the assurance vector or infer a numeric score.
- Existing unqualified `fettle assurance --json` remains machine-compatible.
- The v1 security dimension digest-binds the retained security-review output but
  does not upgrade it to canonical producer/source/policy-bound evidence.
