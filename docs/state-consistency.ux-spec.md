# UX Spec: State Consistency Contracts

Status: PROPOSED; contract design approved for planning, implementation not authorized

Implementation plan:
[state-consistency-implementation-plan.md](state-consistency-implementation-plan.md)

## Jobs To Be Done

When one workflow updates business state that appears in other views, APIs, or
processes, I want Fettle to verify that every declared observer converges on the
new value, so users do not see contradictory versions of the same fact.

When an application intentionally exposes a snapshot, replica, or eventually
consistent projection, I want the contract to state the permitted delay and
comparison semantics, so expected lag is not reported as a defect.

When a consistency check cannot establish a trustworthy result, I want a
visible `unknown` or `tool_error` with a reproducible command, so missing setup,
ambiguous selectors, and timeouts never become a clean result.

## Personas

- Application developer: wants to describe one mutation and its dependent
  observations without building a custom test framework.
- Test engineer: wants deterministic, replayable cross-view journeys against
  real persistence and clear failure evidence.
- Repository maintainer: wants advisory adoption, bounded CI cost, and measured
  precision before enforcement.
- Platform engineer: wants a stable contract and JSON evidence across web, API,
  CLI, and library surfaces without storing credentials or sensitive values.
- Agent/operator: needs a concise finding that names the divergent observer,
  expected relation, observed relation, and exact rerun command.
- Accessible terminal user: needs status conveyed through text and exit codes,
  not color, animation, or cursor behavior.

## User Journey

| Phase | User action | Sees | Desired feeling | Failure to prevent |
|---|---|---|---|---|
| Discover | Runs `fettle consistency init` | A minimal contract template and links to repository-native test adapters | Oriented | Generated guesses represented as truth |
| Define | Names canonical state, mutation, observers, comparator, and consistency window | Lint feedback and unresolved placeholders | Precise | Multiple writable owners hidden by prose |
| Validate | Runs `fettle consistency lint` | Contract validity, adapter capability, and missing secret references | Confident | Invalid contract accepted until CI |
| Exercise | Runs `fettle consistency run <id>` | Mutation phase, observer checks, timing, and bounded progress | In control | Partial execution displayed as pass |
| Diagnose | Reviews a divergence | Canonical value fingerprint, divergent observer, timeline, likely class, and rerun | Unblocked | Secret values or raw payloads leaked |
| Repair | Fixes ownership, refresh, invalidation, or race behavior and reruns | Superseding evidence and all observers converged | Complete | Old evidence reused after source/config changed |
| Graduate | Reviews retained advisory evidence | Fire rate, tool errors, runtime, flakes, and overrides | Safe | Enforcement based on one clean run |

## Proposed Command Surface

Names are planning contracts and require explicit CLI review before
implementation.

### `fettle consistency init [--id ID]`

Creates a repository-owned example contract with placeholders. It does not infer
canonical ownership or silently add generated contracts.

### `fettle consistency lint [PATH] [--json]`

Validates schema, IDs, paths, secret references, observer uniqueness, comparator
compatibility, timeout bounds, and consistency semantics without running the
application.

### `fettle consistency run [ID...] [--json] [--keep-evidence]`

Executes selected contracts in an isolated run. Default output answers:

1. Which mutation succeeded?
2. Which canonical read established the expected state?
3. Which observers converged, diverged, timed out, or could not be evaluated?
4. Was the contract immediate, bounded-eventual, snapshot, or monotonic?
5. What exact command reproduces the result?

### `fettle consistency report [--contract ID] [--json]`

Reports retained outcome counts, p50/p95 convergence time, flakes, tool errors,
and active overrides. It never reports a missing run as a pass.

## Interaction And Time Budgets

- First contract template: one command and no interactive questionnaire.
- Lint: p95 below 500 ms for 100 contracts on the maintained fixture corpus.
- Immediate contract: default hard bound 30 seconds.
- Bounded-eventual contract: explicit poll interval and deadline, maximum five
  minutes unless organization policy permits more.
- Default output: at most five sections and 3 KiB; raw adapter output requires
  `--detailed` or retained evidence.
- Normal edit hooks do not start applications, browsers, containers, or network
  requests. Execution is an explicit minutes-world command or CI job.
- Cancellation stops new observations and records the run as incomplete.

## Required States

### First-Time Empty

No contracts exist. Explain the purpose, show `fettle consistency init`, and
state that Fettle cannot infer business ownership safely.

### Cleared Empty

All selected contracts ran and converged. Name the contract count, source
revision, policy digest, and evidence ID. Do not collapse this into quiet
non-applicability.

### Filtered Empty

No contract matches the requested ID, tag, or changed scope. Name the filter and
show the command to list or clear it.

### Loading Brief

Remain quiet for lint and sub-second probes.

### Loading Long

Show contract ID, phase (`setup`, `mutate`, `canonical-read`, `observe`,
`cleanup`), elapsed time, and deadline. Never print secrets or full values.

### Populated

Group results as converged, divergent, stale, timed out, and unavailable. Show
observer name, surface, duration, evidence fingerprint, and next action.

### Error Recoverable

For a missing adapter, unavailable application, ambiguous selector, transient
timeout, or failed cleanup, preserve evidence and show one exact recovery or
rerun command.

### Error Fatal

For path escape, inline secret material, invalid policy weakening, unsupported
executable form, or corrupt evidence, stop before mutation where possible and
name the trust failure.

### Offline

Contracts requiring network or browser services are `unavailable`. Fully local
contracts may run. Historical evidence is labelled historical, never current.

### Stale Or Superseded

Evidence whose source revision, contract digest, adapter version, or policy
digest changed is stale. Show both identities and require a rerun.

## Contract Authoring Experience

Each contract declares:

- Stable ID, title, tags, and governed source scope.
- Logical fact and one canonical owner description.
- Setup and deterministic cleanup strategy.
- Mutation adapter and success predicate.
- Canonical read adapter used to establish the expected post-mutation value.
- One or more observers with surface and adapter references.
- Comparator: exact, normalized, subset, set, numeric tolerance, or a
  repository-owned named predicate.
- Consistency model: immediate, bounded eventual, immutable snapshot, or
  monotonic.
- Poll interval, deadline, retry safety, redaction, and evidence retention.

Executable actions are repository-owned argv or adapter references. The
contract format does not embed arbitrary shell strings, credentials, or a new
general-purpose expression language.

## Finding Contract

The default finding contains, in order:

1. Decision and stable code such as `cross-view-state-inconsistency`,
   `stale-read`, `missing-invalidation`, or `consistency-tool-error`.
2. Contract ID and source revision.
3. Mutation and canonical observer names.
4. Divergent observer and surface.
5. Expected and observed fingerprints or redacted summaries.
6. Consistency model, elapsed time, and deadline.
7. One recommended action and exact rerun command.

Fettle may suggest a likely cause, but evidence reports the observed divergence
without claiming that cache invalidation, duplicate ownership, or a race is the
proven root cause.

## Progressive Disclosure

- Default: verdict, contract, divergent observers, timing, action, rerun.
- `--detailed`: phase timeline, adapter exits, comparator details, retries,
  provenance, and redacted bounded output.
- `--json`: complete stable machine contract.
- Raw values, browser traces, payloads, and application logs remain excluded by
  default and require explicit repository retention policy.

## Accessibility

- Text labels accompany every status and severity.
- Output remains understandable with `NO_COLOR=1`.
- Stable JSON fields and exit codes mirror human-readable states.
- Non-TTY progress appends bounded lines instead of rewriting a cursor line.
- Instructions require no mouse, color recognition, animation, or visual-only
  comparison.

## BDD Acceptance Scenarios

### Scenario: Immediate cross-view consistency succeeds

Given a contract declares Profile as the mutation surface and Checkout as an observer
And both resolve the same customer name from real persistence
When the runner changes the name to a unique generated value
Then the canonical read establishes that generated value
And Checkout observes an equivalent value within the immediate deadline
And the evidence is bound to the source revision and contract digest.

### Scenario: A stale observer is reported

Given the canonical read returns the newly written customer name
And Order History continues to return the previous name
When the immediate deadline expires
Then Fettle reports `cross-view-state-inconsistency`
And identifies Order History as divergent
And does not assert an unproven root cause
And prints an exact rerun command.

### Scenario: Bounded eventual consistency converges

Given a search projection is allowed to lag for 30 seconds
When the canonical store changes and the projection initially returns the old value
Then Fettle polls only at the declared interval
And reports convergence when the projection matches before the deadline
And records the convergence duration rather than a violation.

### Scenario: Eventual consistency misses its deadline

Given a projection has a declared 30-second convergence deadline
When it remains stale for longer than 30 seconds
Then Fettle reports `stale-read`
And records the final redacted observation and elapsed time
And exits non-zero only when the active policy enforces this graduated contract.

### Scenario: Canonical state cannot be established

Given a mutation command reports success
When the canonical read is unavailable, malformed, or ambiguous
Then Fettle reports `unknown` or `tool_error`, not observer divergence and not pass
And it does not compare observers against a guessed expected value.

### Scenario: Mutation fails before observation

Given a valid contract and isolated test identity
When the mutation fails or times out
Then no observer result is represented as consistency evidence
And cleanup still runs within its bound
And the result names the mutation failure and recovery action.

### Scenario: Delayed older response cannot overwrite newer state

Given two safe mutations A and B are issued in order
And the response for A arrives after B
When every declared observer is read after both operations settle
Then each observer resolves to B
Or Fettle reports a temporal state divergence with the operation timeline.

### Scenario: Snapshot behavior is intentional

Given an invoice contract declares an immutable historical snapshot
When the customer display name changes
Then the invoice observer may retain the captured name
And Fettle evaluates the snapshot predicate instead of demanding current-state equality.

### Scenario: Sensitive values remain redacted

Given a consistency contract observes a token-bearing response
When evidence is rendered or retained
Then raw secrets and configured sensitive fields are absent
And only permitted fingerprints or redacted summaries remain.

### Scenario: Invalid contract cannot execute

Given a contract embeds an inline credential, shell string, path escape, or unknown comparator
When the operator runs lint or execution
Then Fettle reports a configuration error before mutation
And provides a safe contract correction.

## UX Success Criteria

- A new adopter can create and lint the example contract in under five minutes
  using only command help and generated comments.
- Every failure distinguishes divergence, stale read, tool failure, unknown,
  non-applicability, and intentional snapshot behavior.
- No clean result is possible unless mutation, canonical read, all required
  observers, comparator, and cleanup evidence satisfy the contract.
- One concise finding is sufficient to identify the failing observer and rerun.
- Manual UAT confirms human output under normal, `NO_COLOR`, non-TTY, timeout,
  offline, and stale-evidence conditions.
