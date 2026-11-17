# UX Spec: Fettle Review

> Integration precedence — current main’s November 14 sequencing decision and
> trust-remediation ownership govern execution. Earlier scheduling and review
> observations below remain historical. This merge grants no feature approval.

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/review.md).

Status: PROPOSED research and product contract; planning only; no runtime, CLI,
test, configuration, policy, or enforcement implementation is authorized

Related: [implementation plan](fettle-review-implementation-plan.md),
[visual contract](fettle-review.ui-spec.md), and
[hypothesis tree](hypothesis-tree-fettle-review.md)

## Jobs To Be Done

When I have vibe-coded a change, I want a plain-English account of what it is
supposed to do, how its important logic works, what independent evidence supports
it, and what remains risky or unknown, so I can decide what to fix or ask an
engineer to review without pretending that I can validate source code myself.

When I am preparing to code, I want ambiguity, missing states, unsafe assumptions,
and acceptance gaps exposed before implementation, so fluent generated code does
not outrun a weak specification.

## Personas

- Non-engineer builder: needs ordinary language, concrete examples, and one next
  action; cannot be expected to interpret source code or test framework output.
- Engineer or reviewer: needs exact file, symbol, requirement, evidence, and
  command references behind every summary.
- Release owner: needs the existing Assurance policy decision unchanged and every
  absent, stale, or contradictory input shown as non-pass.
- Accessible user: needs keyboard operation, semantic headings, text status
  labels, a useful terminal fallback, and no color-only meaning.

## User Journey

| Phase | User action | Sees | Feels | Main risk and recovery |
|---|---|---|---|---|
| Define | Describes desired behavior and forbidden outcomes in plain English | Draft intent, assumptions, examples, and unresolved questions | In control | AI invents intent; user must approve every requirement |
| Build | Lets an existing agent implement the change | Changed behavior, affected areas, and emerging evidence gaps | Oriented | Activity is mistaken for correctness; label activity separately |
| Review | Opens one review for the exact candidate | `READY`, `NOT READY`, or `UNKNOWN`, reasons, and prioritized actions | Informed | Summary hides detail; every statement drills into provenance |
| Understand | Expands a behavior or risk | Plain-English logic, flow/state diagram, code locations, tests, and observations | Capable | Generated explanation is wrong; mark it `ADVISORY INTERPRETATION` |
| Decide | Records a human decision outside the review result | Existing Fettle policy decision and explicit human choice | Accountable | Human approval upgrades weak evidence; it must not |
| Recover | Runs or delegates the named next action | Refreshed evidence and changed status for the same candidate | Unblocked | Candidate drift; invalidate applicability and review the new candidate |

## Primary Flow And Budgets

1. Run or open the review for the current change.
2. Read the disposition, top three reasons, and unknowns.
3. Expand one reason to see its claim-to-evidence path.
4. Run or delegate the first exact recovery action.
5. Re-run the review against the new candidate.

- Common review budget: one command or link, at most three interactions to reach
  supporting evidence.
- Experienced-user time budget: disposition and highest risk in under 60 seconds.
- Non-engineer task budget: classify a seeded change and identify the next action
  in under five minutes.
- Default view budget: one screen with disposition, scope, top reasons, unknowns,
  and next actions. Technical detail uses at most two disclosure levels.

## Required States

- First-time empty: explain that no review exists, identify the exact candidate,
  and show the command that would produce existing prerequisite evidence.
- Cleared empty: confirm that a generated presentation was removed while source
  evidence remains untouched; offer regeneration for the current candidate.
- Filtered empty: state which dimension/filter has no matching items and provide
  a clear-filter action; never imply that no risk exists.
- Loading brief: show the candidate identity and currently evaluated stage.
- Loading long: show elapsed time, bounded stage, and safe cancel action; partial
  results are labeled incomplete and cannot become ready.
- Populated: show disposition, evidence freshness, dimensions, claim map, logic
  explanation, risks, unknowns, and ordered recovery actions.
- Error recoverable: state which input is missing, stale, malformed, or
  unavailable and provide one exact rerun or repair action.
- Error fatal: preserve source data, render no stale readiness claim, and direct
  the user to a safe diagnostic path.
- Offline: retained local evidence remains inspectable; remote CI or service facts
  are `UNKNOWN` unless a valid candidate-bound artifact already exists.
- Stale: show the old review only with a prominent stale label, old and current
  candidate identities, and a regenerate action.

## Information Architecture

- Entry point: a future explicit `fettle review` command only after authorization;
  no automatic browser launch, hook, or navigation item is approved now.
- Initial output candidates: concise terminal summary, deterministic JSON, and a
  self-contained local HTML projection generated from the same review result.
- Sections, in order: Decision, What Changed, Intended Behavior, Logic Map,
  Evidence by Dimension, Risks and Unknowns, Next Actions, Technical Provenance.
- Back behavior in HTML returns to the previous section and retains expansion
  state without changing repository data.
- No review database is proposed. Any generated file is derived, replaceable,
  candidate-bound output and grants no authority.

## Status And Language Contract

- Overall disposition uses the existing policy result vocabulary where available.
  Presentation aliases must map exactly and visibly, for example `FIX_FIRST` to
  `NOT READY` and an indeterminate decision to `UNKNOWN`.
- Dimension states are `VERIFIED`, `FAILED`, `UNKNOWN`, `NOT APPLICABLE`, and
  `ADVISORY`. `NOT APPLICABLE` requires a reason.
- Never use `looks good`, `probably safe`, percentages, stars, letter grades, or a
  synthesized quality score.
- Separate three statement classes:
  - `OBSERVED`: valid Fettle evidence reports a fact.
  - `DERIVED`: deterministic Fettle policy or mapping derives a result.
  - `ADVISORY INTERPRETATION`: generated prose or a diagram explains code.
- An advisory interpretation cannot satisfy a requirement, change a dimension,
  remove an unknown, or alter the release decision.

## Review Dimensions

The report always accounts for these dimensions, even when the result is unknown
or not applicable:

- Intent fidelity and requirement coverage.
- Functional and boundary behavior.
- Failure and recovery behavior.
- State consistency and concurrency where applicable.
- Authentication, authorization, injection, secret, dependency, and unsafe-I/O
  security concerns.
- Privacy and data handling.
- Maintainability and change complexity.
- Test relevance and mutation strength where supported.
- Change impact and preservation obligations.
- UX states and accessibility for user-facing changes.
- Performance and bounded-resource behavior where applicable.
- Operational readiness, rollback, observability, and configuration.
- Evidence integrity: producer, source, policy, scope, occurrence, completeness,
  freshness, independence, and contradictions.

## Accessibility

- One logical heading hierarchy and skip link in HTML.
- Keyboard order follows summary, dimensions, claims, then provenance; native
  disclosure controls work with Enter and Space.
- Status is always text plus shape/icon; color is supplementary.
- Diagrams have equivalent ordered text and do not require spatial interpretation.
- Focus is always visible; target size is at least 44 by 44 CSS pixels on touch.
- Text and UI meet WCAG AA contrast; motion is unnecessary and omitted initially.
- Terminal output contains the same disposition, reasons, unknowns, and actions.

## BDD Scenarios

### Scenario: Non-engineer identifies a release blocker

Given a candidate has passing unit tests but a valid security violation
When the user opens its review
Then the review says `NOT READY`
And names the security issue in plain English
And links it to the exact evidence and one recovery action
And no passing dimension dilutes or hides the blocker.

### Scenario: Missing evidence stays unknown

Given the change has no candidate-bound UAT result
When the review is generated
Then the relevant behavior or UX dimension says `UNKNOWN`
And explains what was not observed
And does not infer success from source code, test names, or an AI explanation.

### Scenario: Logic explanation is useful but non-authoritative

Given an optional model describes a payment state transition
When the user expands the logic map
Then the prose and diagram are labeled `ADVISORY INTERPRETATION`
And show exact source references
And any unsupported branch is marked unknown
And the explanation does not alter Assurance or completion.

### Scenario: Candidate drift invalidates applicability

Given a review was generated for candidate A
When the working source becomes candidate B
Then the old review is prominently `STALE`
And cannot display a current ready decision
And the recovery action regenerates evidence for candidate B.

### Scenario: Contradictory evidence is not averaged

Given two applicable sources disagree about one required behavior
When the review is composed
Then the dimension is `UNKNOWN` or `FAILED` according to the existing consumer
And both sources and the contradiction are visible
And no numeric average converts the conflict into partial success.

### Scenario: A clean review remains scoped

Given every policy-required dimension has valid candidate-bound evidence
When the review reports the existing ready decision
Then it names the exact candidate, policy, scope, and evidence freshness
And states what was not assessed
And does not claim universal correctness or absence of all defects.

### Scenario: Offline review preserves remote unknowns

Given no retained candidate-bound remote CI evidence is available
When the review runs offline
Then local evidence remains inspectable
And remote CI is `UNKNOWN`
And the review performs no network access unless a future explicit mode is
separately authorized.

### Scenario: Presentation failure cannot preserve stale readiness

Given report generation fails after a previous ready report exists
When the user opens the output path
Then the previous report is not represented as current
And the failure names the candidate and safe recovery action
And no source evidence is deleted or modified.

## Success Criteria

- In blinded evaluation, target users correctly classify at least 90% of seeded
  cases and make zero false-ready decisions.
- Every visible conclusion resolves to an existing source, policy, evidence, or
  explicitly advisory interpretation.
- Users identify the highest-severity unresolved risk and first recovery action in
  under five minutes.
- Terminal, JSON, and HTML projections agree on dispositions and reason ordering.
- Axe reports zero serious or critical violations; keyboard-only and screen-reader
  walkthroughs complete every review task.
- No report creation changes Assurance, completion, gates, hooks, evidence,
  repository source, or release state.
