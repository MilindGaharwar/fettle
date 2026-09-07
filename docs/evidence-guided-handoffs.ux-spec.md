# UX Spec: Evidence-Guided Handoff Pilot

Status: proposed research contract; planning only; implementation and execution
are blocked by Assurance Integrity CS-6 graduation and separate operator approval

Related: [implementation and experiment plan](evidence-guided-handoffs-plan.md),
[portable evidence contract](evidence-artifact-contract.md), and
[Assurance Integrity](assurance-integrity.ux-spec.md)

## Job To Be Done

When work passes from planning to implementation or from implementation to
independent verification, I want Fettle to validate what candidate is in scope,
what behavior must be preserved, and what evidence can establish acceptance, so
the next agent does not reconstruct critical state from prose or silently assess
a different change.

## Personas

- New maintainer: needs a concise explanation of an invalid handoff and one exact
  repair action.
- Power user or agent: needs deterministic JSON, stable exit codes, and no
  interactive prompts.
- Release owner: needs proof that acceptance evidence belongs to the frozen
  candidate and that regressions remain explicit obligations.
- Accessible terminal user: needs text labels and paths; symbols and color are
  optional decoration only.

## Journey And Budget

| Phase | User action | Sees | Recovery |
|---|---|---|---|
| Prepare | Uses the existing host to plan or implement a bounded change | A repository-local handoff artifact produced by that host | Add the missing objective, obligation, or acceptance criterion |
| Validate | Runs the proposed `fettle handoff validate PATH` | `VALID`, `INVALID`, or `STALE`, candidate identity, and one next action | Correct the named field or regenerate the handoff against the current candidate |
| Verify | Gives an independently frozen candidate and validated handoff to the existing QA/CI workflow | Candidate-bound observations for every acceptance and preservation obligation | Produce missing evidence or return the work to implementation |
| Replan | The host consumes the verified gaps and preservation outcomes | A new bounded plan; the old plan remains provenance, not live authority | Resolve regressions before unrelated expansion |
| Compare | Reviews the pilot report | Matched treatment/control outcomes and overhead | Reject the hypothesis if quality or cost thresholds fail |

- Common validation flow: one non-interactive command after the host writes a
  handoff artifact.
- Experienced-user time budget: under five seconds excluding evidence producers.
- No new daemon, hosted service, database, or mandatory orchestrator.
- Default output shows status, handoff kind, candidate identity, unmet
  obligations, and one recovery action. Full digests remain in JSON.

## Required States

- First-time empty: no handoff exists; output explains that the pilot is optional
  and names the proposed initialization or host-generation action.
- Cleared empty: removing a handoff removes its authority; an older handoff is
  never inferred from trace or model memory.
- Filtered empty: a requested objective or obligation ID is absent; output names
  the missing ID and available IDs without treating absence as success.
- Loading brief: local parsing and identity checks remain quiet.
- Loading long: bounded source or Git identity resolution terminates visibly;
  stale validation is not reused.
- Populated: the artifact identifies its role, input candidate, bounded objective,
  preservation obligations, acceptance criteria, and parent evidence.
- Recoverable error: missing evidence, incomplete criteria, or a changed candidate
  yields `INVALID` or `STALE` and one regeneration command.
- Fatal error: malformed schema, unsafe path, digest mismatch, contradictory
  obligation, or unverifiable candidate identity exits 2.
- Offline: validation and retained-report comparison work locally; unavailable
  remote evidence remains non-pass.
- Stale or conflicting: candidate, policy, scope, or parent-evidence drift
  invalidates the handoff and cannot be hidden by an earlier valid result.

## Information Architecture

- Proposed entry point: `fettle handoff validate PATH [--json]` after the pilot is
  separately authorized.
- Artifact location: repository-local, reviewable files under `.fettle/handoffs/`;
  no persistent semantic store.
- Existing `fettle assurance`, completion, UAT, CI, role, worktree, and evidence
  contracts remain authoritative in their current domains.
- Detailed observations remain in their producer-owned artifacts and are linked
  by canonical references rather than copied into the handoff.
- The pilot adds no navigation or autonomous loop command. Host tools decide when
  to invoke planner, implementer, or verifier roles.

## Accessibility And Cognitive Load

- Human and JSON output derive from one decision object.
- `VALID`, `INVALID`, and `STALE` are always written as text.
- The first screen shows at most status, role, candidate, failed obligations, and
  one next action.
- Default output summarizes digests; `--json` exposes complete bounded records.
- Error messages use operator language and never expose secrets, prompts, hidden
  reasoning, or absolute checkout paths in portable artifacts.

## BDD Scenarios

### Scenario: Valid implementation handoff preserves verified behavior

Given a planner handoff names one bounded objective, observable acceptance
criteria, and previously verified behavior that must be preserved
When the handoff is validated against its exact input candidate
Then Fettle reports `VALID` and retains the obligations without scheduling or
executing an agent.

### Scenario: Candidate drift invalidates the handoff

Given a valid handoff is bound to candidate A
When source, policy, or declared scope changes to candidate B
Then validation reports `STALE`, identifies the mismatched binding, and the old
handoff cannot authorize implementation or acceptance.

### Scenario: Missing preservation evidence remains non-pass

Given independent verification has no candidate-bound observation for a required
preservation obligation
When the verification handoff is evaluated
Then that obligation is `UNVERIFIED`, overall acceptance is non-pass, and the
output names the evidence producer or rerun action.

### Scenario: Regression reopens verified work

Given behavior was previously verified and carried forward as a preservation
obligation
When candidate-bound evidence shows that behavior now fails
Then the obligation is `REGRESSED`, retains the prior evidence reference, and is
available as explicit input to the next plan.

### Scenario: Verifier cannot mutate the assessed candidate

Given verification begins against a captured candidate identity
When the repository changes before all observations are finalized
Then the verification result is rejected as candidate drift and no mixed-version
evidence can establish acceptance.

### Scenario: Invalid schema fails visibly

Given a handoff omits its objective, candidate binding, role, or required
acceptance criteria
When validation runs
Then it exits 2, lists the invalid fields, and does not infer them from prose,
trace, or source code.

### Scenario: Control workflow remains available

Given the pilot is disabled or not authorized
When an operator uses existing Fettle commands and a supported agent host
Then current behavior is unchanged and no handoff artifact is required.

### Scenario: Pilot evidence cannot promote itself

Given the pilot meets its provisional quality thresholds
When the report is generated
Then the result remains advisory until a human reviews the retained pairs and
explicitly authorizes roadmap adoption or enforcement.

## Success Criteria

- Every accepted observation binds one immutable candidate identity.
- Every required acceptance and preservation obligation has positive,
  candidate-bound evidence; missing or conflicting evidence remains non-pass.
- Hosts retain planning and execution control; Fettle only validates contracts
  and evidence.
- Existing workflows are unchanged when the pilot is disabled.
- Human and JSON decisions agree and every non-pass gives one recovery action.
- Pilot adoption depends on the causal and operational thresholds in the
  implementation plan, not on the paper's benchmark results alone.
