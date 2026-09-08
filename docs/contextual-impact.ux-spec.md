# UX Spec: Contextual Impact Analysis

Status: PROPOSED; planning only; implementation and enforcement are not authorized

Parent contract: [change-integrity.ux-spec.md](change-integrity.ux-spec.md)

Implementation plan:
[contextual-impact-implementation-plan.md](contextual-impact-implementation-plan.md)

## Jobs To Be Done

When a graph closure contains many possible dependencies, I want Fettle to show
which impacts require action, which deserve contextual review, and which were
excluded, so I can focus without mistaking a ranked list for proof of safety.

When Fettle recommends an artifact, I want a short deterministic explanation and
an inspectable path, so I can verify why it appears without reconstructing the
graph manually.

When providers are incomplete or traversal bounds are reached, I want uncertainty
shown as a non-pass state with a broader verification action, not hidden by a low
rank or empty result.

## Personas

- New adopter: needs plain `required`, `review`, and `excluded` language without
  understanding trust classes or graph incidence roles.
- Developer or agent operator: needs the highest-value actions first, one command,
  stable ordering, and bounded output.
- Maintainer: needs complete paths, policy/rule identity, provider completeness,
  comparison evidence, and a reversible promotion decision.
- Accessible terminal user: needs classifications and uncertainty conveyed in
  text and exit codes, without color, icons, cursor control, or a mouse.

## User Journey

| Phase | User action | Sees | Desired feeling | Failure to prevent |
|---|---|---|---|---|
| Enter | Runs `fettle graph impact <paths>` | Current advisory superset exactly as today | Oriented | Silent contract break |
| Evaluate | Explicitly requests contextual analysis | Required actions first, then review candidates, limitations, and next command | Focused | Rank interpreted as authority |
| Explain | Requests detailed or JSON output | Typed path, accepted/rejected rules, trust, completeness, and score components | Confident | Opaque score |
| Recover | Analysis is incomplete or bounded | Unsafe conclusions and broader verification command | Unblocked | Empty result interpreted as safe |
| Compare | Maintainer runs shadow evaluation | Legacy/contextual differences grouped by cause | In control | Aggregate metric hides misses |

## Command And Compatibility Contract

The first implementation must not alter default P47 behavior. Existing
`fettle graph impact <paths>` human output, JSON keys, advisory status, and exit
codes remain the compatibility oracle.

Contextual output is reached through an explicit experimental option chosen in
the contract review. Preferred surface:

```text
fettle graph impact <paths> --contextual [--detailed] [--json]
```

Adding a separate command is acceptable only if parser compatibility cannot be
proven. Replacing `affected`, changing its meaning, or silently reordering the
default output is not acceptable. During shadow evaluation, contextual output
cannot block work, create Assurance PASS, or remove an item from the legacy
advisory superset.

## Finding Contract

Every contextual result has exactly one classification:

- `required`: directly affected, policy-mandated, or independently corroborated;
  ranking cannot demote or hide it.
- `contextual`: plausible transitive impact that merits review but is not an
  obligation.
- `excluded`: considered and rejected with a machine-readable reason such as
  direction, rule, trust, provider, policy, cycle, or bound.

Default human output shows required items, the highest-ranked contextual items,
limitations, and one next command. Excluded items and full paths require
`--detailed` or `--json`. Each displayed result includes classification, stable
artifact identity, one-sentence relationship reason, and action. Detailed output
adds score components, typed path, provider and rule identities, completeness,
and exclusion reason.

The deterministic sort key is part of the JSON contract. Equal scores use stable
artifact identity as the final tie-breaker. A score is relevance ordering only;
it is never displayed as probability or confidence of correctness.

## Interaction And Time Budgets

- One explicit command produces the first contextual result.
- Default output remains at most five groups and 2 KiB.
- All required items appear before contextual items; none are hidden by a result
  cap.
- Explicit traversal and ranking stay within the existing graph command budget
  plus an initially measured 20% p95 allowance.
- No contextual analysis runs in hooks, CI gates, or Assurance during shadow mode.

## Required States

- First-time empty: explain that no graph was built and provide the exact build
  command; never show zero impact.
- Cleared empty: state that complete accepted providers found no required or
  contextual impact, and name that scope.
- Filtered empty: name the requested path/filter and how to clear or correct it.
- Loading brief: remain quiet below one second.
- Loading long: show current deterministic phase and cancellation behavior.
- Populated: group required, contextual, limitations, and next action.
- Error recoverable: preserve work, name the failed provider/rule, and show one
  rerun or broader-verification command.
- Error fatal: reject malformed policy, digest mismatch, or path escape and route
  to graph-independent diagnosis.
- Offline: continue complete local providers and identify unavailable optional
  enrichment; do not imply it ran.
- Stale: identify requested and analyzed snapshots and refuse authoritative use.
- Incomplete or bounded: use `unknown` or `limit_reached`; never convert omitted
  candidates to `excluded` or unaffected.

## Accessibility And Progressive Disclosure

- Classification, state, and limitations are text labels, not color alone.
- `NO_COLOR=1` and redirected output preserve meaning and stable ordering.
- Default output contains decisions and actions; `--detailed` contains paths and
  score components; `--json` contains the complete canonical result.
- No interactive prompts, animations, or cursor-dependent controls are added.

## BDD Acceptance Scenarios

### Scenario: Existing callers receive unchanged output

Given a maintained P47 fixture and no contextual option
When the operator runs graph impact in human and JSON modes
Then output and exit behavior match the frozen compatibility fixtures
And no contextual field changes the meaning of `affected`.

### Scenario: Required impact cannot be ranked away

Given a direct or policy-mandated impact and many contextual candidates
When contextual ranking runs with any valid weights
Then the required impact appears in the required group
And result caps, optional providers, and ranking cannot remove or demote it.

### Scenario: Contextual result explains its path

Given a candidate reached through accepted typed relationships
When detailed output is requested
Then Fettle names every path edge, direction, role, provider, and rule
And the score can be recomputed from displayed integer components.

### Scenario: Rejected candidate remains inspectable

Given a graph neighbor is rejected by direction, trust, provider, policy, or bound
When JSON output is requested
Then it appears as excluded with the exact reason
And it is not represented as unaffected.

### Scenario: Required provider is incomplete

Given an applicable required provider is missing, partial, failed, or conflicting
When contextual analysis runs
Then the result is unknown rather than empty or complete
And Fettle names unsafe conclusions and a broader verification action.

### Scenario: Optional provider perturbation changes advice only

Given required results are supported by complete approved providers
When an optional provider is removed in a deterministic perturbation
Then no required result or obligation disappears
And contextual differences identify that provider as their cause.

### Scenario: Traversal reaches a bound

Given depth, fan-out, or result limits truncate exploration
When contextual analysis runs
Then the state is `limit_reached`
And omitted candidates are not classified as excluded or safe.

### Scenario: Shadow evaluation finds a narrower result

Given the legacy oracle requires an impacted artifact
When contextual analysis omits or demotes it below required
Then the comparison records an unexplained narrower result
And promotion remains blocked regardless of aggregate precision.

### Scenario: Optional model reranking is unavailable

Given a later experiment enables an advisory model reranker
When the model is unavailable, malformed, or nondeterministic
Then deterministic results remain complete and unchanged
And no model output can remove required evidence or create PASS.

## UX Success Metrics

- Zero required impacts hidden, demoted, or removed in maintained and held-out
  evaluation.
- 100% of displayed results have a deterministic explanation.
- 100% of non-complete states include one recovery or broader-verification action.
- Default output stays within 2 KiB and one-command task completion.
- Identical canonical inputs produce byte-identical JSON and ordering.
- Existing P47 compatibility fixtures remain unchanged until an explicit schema
  version and migration are approved.
