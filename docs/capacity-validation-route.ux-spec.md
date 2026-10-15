# UX Spec: Capacity Model-Validation Route

## Jobs To Be Done

When I need to validate mutation-duration predictions without starting a
qualification campaign, I want one registered route to enumerate the exact
candidate corpus, freeze an informative sample, and execute only that sample,
so I can obtain bounded modeling evidence without creating qualification input.

## Personas Affected

- New maintainer: needs explicit preparation and execution stages that cannot
  fall through to replay or calibration.
- Power maintainer: needs deterministic JSON identities, exact digests, and
  reproducible readback.
- Accessible operator: consumes stable text labels and JSON states; status is
  never conveyed by color or animation.

## User Journey

| Phase | Operator action | Sees | Desired feeling | Failure prevented |
|---|---|---|---|---|
| Prepare | Dispatches `capacity-validation` stage `prepare` at an exact SHA | Candidate-bound manifests, corpus, frozen 12-unit plan, and separate preparation cost | Confident | Parent evidence relabeled as current |
| Review | Reads the plan and records its digest | Units, fingerprints, mapped-test groups, rationale, predictions, and gaps | In control | Outcome-driven substitution |
| Execute | Separately dispatches stage `execute` with preparation run and plan digest | Three admitted batches of at most four workers | Contained | Full-corpus or calibration fan-out |
| Read back | Downloads non-authoritative experiment artifacts | Complete, partial, censored, missing, and conflicting states plus separate ledgers | Oriented | Incomplete evidence interpreted as pass |
| Decide | Compares frozen predictions with observations | Model-validation conclusion only | Informed | Validation mistaken for qualification |

Interaction budget: three dispatches and one digest transfer. Preparation and
execution remain separate so enumeration cost is visible and execution requires
an immutable reviewed sample; terminal provider readback remains separate so it
can observe the execution attempt after its final timestamp exists.

## States

- First-time empty: no preparation run; execution is rejected with the required
  preparation inputs.
- Cleared empty: a preparation with no canonical mutants is non-pass and cannot
  produce a sample.
- Filtered empty: fewer than six eligible mapped-test groups with two nonempty
  units each is non-pass; selection is not weakened silently.
- Loading brief: identity and manifest validation.
- Loading long: enumeration exposes 256 bounded workers and execution exposes
  the current four-worker batch.
- Populated: exact corpus, plan, units, predictions, ledgers, and limitations.
- Error recoverable: a bounded artifact retrieval failure retains the failed
  state and permits only a new separately authorized dispatch, never an
  automatic rerun.
- Error fatal: malformed, stale, duplicate, missing, conflicting, foreign, or
  nonterminal evidence is non-pass and cannot enter calibration consumers.
- Offline: local fixture validation can exercise all producers and consumers;
  provider execution is not implied.
- Stale: candidate, environment, mappings, plan, preparation run, or workflow
  identity mismatch rejects execution before workers start.

## Information Architecture

- Entry: existing registered `.github/workflows/mutation.yml`.
- Mode: `capacity-validation`; stage: `prepare`, `execute`, or terminal `readback`.
- Preparation outputs: `capacity-validation-preparation-*` only.
- Execution outputs: `capacity-validation-unit-*`, accounting, and readback
  only. Names never match mutation calibration, checkpoint, report, or preflight
  qualification artifact patterns.
- Every displayed ceiling is labeled `not_granted` until a new complete
  prerequisite-to-measurement authorization is issued; the closed zero-spend
  grant is never shown as available capacity.
- Back/escape behavior: invalid input stops at admission; no fallback mode.

## Accessibility

- Every state has a word label and machine-readable status.
- Retained JSON is the decision record; job names, conclusions, and artifact
  links provide the workflow-level status and recovery path.
- Output is bounded and line-oriented; no progress animation is required.

## Progressive Disclosure

Default readback shows status, selected-unit count, completed/censored/missing
counts, four ledgers, and next action. Full canonical fingerprints and raw
bounded diagnostics remain in retained artifacts.

## UAT Scenarios

### Scenario: Preparation freezes a deterministic sample

Given an exact candidate and a complete canonical enumeration
When the preparation stage applies the reviewed selection policy
Then it emits exactly 12 distinct range units with exact-once fingerprints and
the same bytes on repeated construction.

### Scenario: Execution cannot broaden scope

Given a digest-bound preparation plan
When execution is dispatched with a missing, foreign, stale, or malformed input
Then no sample worker starts and the route does not fall back to replay,
calibration, preflight, or full-corpus execution.

### Scenario: Bounded batches execute once

Given a valid frozen plan
When execution starts
Then at most four units run concurrently, each unit appears once, run attempt is
one, and admission occurs before each later batch.

### Scenario: Worker deadline preserves cleanup

Given a worker's provider job has a 20-minute envelope
When its internal mutation deadline is reached earlier
Then unfinished fingerprints remain pending, cleanup and restoration execute,
and the observation is censored rather than completed.

### Scenario: Experiment evidence cannot qualify

Given any complete or partial capacity-validation artifact
When calibration, continuation, or qualification consumers inspect it
Then strict schema and artifact namespaces reject it as authoritative input.

### Scenario: Ordinary CI stays dormant

Given a push, pull request, schedule, or another mutation mode
When workflows evaluate
Then no capacity-validation preparation or sample worker starts and existing
mutation behavior is unchanged.
