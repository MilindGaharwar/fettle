# Experience Discipline vNext UX Contract

> Integration precedence — current main’s November 14 sequencing decision and
> trust-remediation ownership govern execution. Earlier scheduling and review
> observations below remain historical. This merge grants no feature approval.

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/experience.md).

Status: PROPOSED; planning only; no skill, evaluator, package, installer, host
configuration, or enforcement change is authorized

Plan: [experience-discipline-vnext-plan.md](experience-discipline-vnext-plan.md)

## User Outcome

When a coding agent receives work that changes a human experience, it must do the
smallest UX work that exposes and controls the material user risk before coding.
It must not manufacture research, mistake template completion for evidence, or
apply browser conventions to unrelated surfaces.

## Actors And Context

- Operator: needs proportionate UX rigor without ceremony on routine changes.
- Coding agent: needs deterministic routing, stop conditions, and bounded methods.
- Reviewer: needs claims, assumptions, unknowns, criteria, and evidence to remain
  traceable across planning, implementation, and UAT.
- Affected user: needs a coherent, accessible, understandable, recoverable service,
  including when AI or automation acts with delegated authority.

Personas are optional research syntheses. The discipline never invents a persona,
demographic attribute, emotion, frequency, or user need to complete a template.

## Primary Journey

```text
inspect requested and existing behavior
    -> route independent harm, scope, autonomy, and uncertainty triggers
    -> state the affected actor and observable outcome
    -> identify changed transitions, failures, recovery, and evidence gaps
    -> apply only triggered accessibility, privacy, consequence, AI, and service overlays
    -> define observable acceptance criteria
    -> plan and implement against those criteria
    -> report evidence at its true scope plus remaining unknowns
    -> monitor only when the risk or decision requires longitudinal evidence
```

## Routing Contract

The router evaluates independent triggers rather than assigning one blended risk
score:

| Trigger | Escalate when |
|---|---|
| Harm | Failure affects money, legal rights, safety, privacy, identity, reputation, access, or an irreversible outcome |
| Scope | Work spans steps, sessions, roles, systems, runtimes, or channels |
| Autonomy | A system recommends, prioritizes, communicates, or acts for a user |
| Uncertainty | A decision-driving claim is unsupported, disputed, or outside the agent's observable environment |

| Route | Required UX output |
|---|---|
| L1 Local | Inline actor, outcome, changed state, regression boundary, and verification |
| L2 Workflow | Short brief plus transition/failure table and observable criteria |
| L3 Controlled | Durable UX/service spec, stable criteria, explicit approval, verification plan, and applicable monitoring or rollback |

Surface adapters tailor the evidence and interaction vocabulary for web, mobile,
desktop, CLI/TUI, public API, voice/conversational UI, embedded runtimes, and
cross-channel services. Surface does not lower consequence.

## Evidence Contract

Decision-driving claims use one of these states:

- `VERIFIED`: directly observed with reproducible evidence.
- `SUPPORTED`: backed by supplied, repository, or cited evidence.
- `ASSUMPTION`: plausible but not verified.
- `UNKNOWN`: required information is unavailable.
- `HUMAN REVIEW REQUIRED`: the current environment cannot establish the claim.

For a claim that changes behavior, scope, priority, or risk treatment, retain its
basis, confidence, consequence if wrong, and validation or containment path. A
low-confidence, high-consequence claim without an accepted containment, rollback,
or validation path blocks implementation.

Evidence classes remain distinct:

- design-time research, task analysis, prototypes, and expert review;
- build-time functional checks and automated analysis;
- acceptance-time human walkthroughs and assistive-technology checks;
- runtime analytics, support signals, incidents, and drift monitoring.

No evidence class may be presented as proof of a different claim. In particular,
scripted automation does not prove human task time, an E2E pass is not a user
completion rate, and a clean accessibility scanner does not establish WCAG
conformance.

## Transition And Recovery Contract

L2 and L3 work describes relevant behavior as transitions:

| From/precondition | Trigger | Observable outcome | Failure or partial result | Recovery | Verification |
|---|---|---|---|---|---|

The inventory derives from actual I/O, persistence, permissions, connectivity,
concurrency, stale data, partial completion, destructive effects, and cross-session
or cross-device behavior. There is no universal state count. An irrelevant catalog
state may be omitted; an applicable but unverified state remains visible. Each
reachable success path and material failure or partial-result path has an observable
outcome and verification. Each path that can strand the user, lose work, duplicate
an effect, change privacy, or cause a destructive effect also has a recovery or an
explicit blocking unknown. L3 adds applicable cross-role, cross-session, and
cross-channel transitions.

## Blocking Gates

1. Outcome undefined: the actor, affected interaction, or observable result is
   unknown for a behavior-changing user-facing change.
2. High-consequence unknown: a material harm or authority claim is assumed or
   unknown without approved validation, containment, or rollback.
3. Uncontrolled side effect: a destructive, external, costly, privacy-changing,
   or automated action lacks proportionate preview, authority, confirmation, or
   recovery.
4. Critical recovery absent: a reachable failure can strand the user, lose work,
   duplicate effects, or conceal partial completion.
5. Known accessibility barrier: changed functionality prevents task completion
   through an applicable input or assistive-technology path, or knowingly violates
   an applicable WCAG 2.2 A/AA criterion without an approved exception.
6. Privacy or deceptive choice: new personal-data handling lacks purpose, access,
   or retention boundaries, or optional refusal/reversal is materially harder than
   acceptance without necessity.
7. Agent authority mismatch: automated behavior exceeds granted scope or lacks
   controls appropriate to its authority.
8. False verification claim: evidence is used to establish a property it did not
   measure.
9. Broken controlled-work traceability: an L3 criterion has no implementation
   owner or verification reference.

All other methods and heuristics are advisory unless a repository policy makes
them required. Exceptions must name an owner, reason, expiry or review point, and
residual risk; the agent cannot self-approve a high-consequence exception.
When a gate applies, the agent stops the affected implementation until the missing
decision or control is supplied and verified. It may propose controls, experiments,
or rollback, but it cannot approve its own exception to a gate.

## Accessibility And Inclusion

- WCAG 2.2 is the current web conformance baseline where applicable. WCAG 3 and
  APCA are emerging or supplemental and cannot replace WCAG 2.2 conformance.
- Evidence states its exact pages, components, activated states, complete process,
  runtime, tools, manual checks, assistive technologies, and unverified areas.
- Automated checks are combined with applicable keyboard, focus, labels, status,
  error, zoom/reflow, target, motion, and assistive-technology checks.
- Native semantics are preferred. ARIA is used only where native semantics cannot
  express the interaction.
- Relevant disabled participants may provide usability evidence, but no individual
  represents a disability group and user testing alone does not prove conformance.
- Cognitive accessibility includes understandable language, memory support,
  predictable behavior, correction, and access to help.

## AI And Agent Authority

| Authority | Example | Minimum control |
|---|---|---|
| Inform | Explain or summarize | Relevant sources, limits, uncertainty, correction |
| Recommend | Rank or propose | Basis, material alternatives, calibrated reliance, user decision |
| Prepare | Draft an action | Editable preview or diff; no side effect before approval |
| Act | Execute a reversible action | Scoped permission, status, interrupt, audit, rollback |
| Commit | Execute a consequential or irreversible action | Fresh consent, identity/authority check, independent verification where required, recourse |

Applicable reviews also cover untrusted input, least privilege, confirmation
freshness, safe degradation, generated-versus-retrieved information, retention and
secondary use, model or policy changes, and disparate impact.

## Privacy And Deceptive Design

Changes involving consent, subscription, cancellation, deletion, collection,
sharing, personalization, or sensitive inference must expose purpose, necessity,
access, retention, and reversal. Hidden material terms, obstruction, confirmshaming,
unsupported urgency or scarcity, disguised choices, preselected optional consent,
and asymmetric acceptance/refusal are blocking unless an applicable requirement and
reviewed necessity justify the difference.

The discipline flags legal review when applicability is unknown. It does not make
autonomous legal-compliance claims.

## Method Selection

JTBD, behavioral segments, personas, task flows, journey maps, service blueprints,
content prototypes, progressive disclosure analysis, click counts, and time studies
are optional methods. The agent selects one only when it reduces a named uncertainty
and states what decision the method informs. User journeys and service blueprints
are expected for temporal, cross-role, or cross-channel complexity, not for every
visible component.

## Acceptance Handoff

Every route has observable acceptance criteria. Stable semantic IDs are required
only for L3 work or L2 work spanning artifacts, owners, or sessions. Each retained
ID links the user outcome to an implementation owner and correctly scoped UAT
evidence. BDD is permitted but not required syntax.

## BDD Scenarios

### Scenario: Routine work stays proportionate

Given an existing button receives a spacing-only correction
When the agent routes the change
Then it uses L1 and verifies the changed presentation and accessibility boundary
And it does not invent personas, research, a journey map, or a standalone UX spec.

### Scenario: Consequence outranks interaction size

Given a single control permanently deletes a workspace
When the agent routes the change
Then harm triggers L3 even though the code change may be local
And authority, dependent data, consequence comprehension, partial failure, and
recourse are resolved before implementation.

### Scenario: Evidence scope remains truthful

Given Playwright completes checkout and axe reports no violations
When the agent reports verification
Then it reports scripted behavior and automated accessibility scope only
And it does not claim measured human task time, user completion rate, or WCAG
conformance.

### Scenario: Surface changes the method, not the risk

Given a destructive CLI command can partially complete
When the agent applies the discipline
Then it covers help, noninteractive behavior, stdout/stderr, exit codes,
confirmation, interruption, idempotency, partial side effects, and recovery
And it does not require clicks, browser navigation, or visual empty states.

### Scenario: Agent authority is bounded

Given an assistant can draft and send customer refunds
When the experience is designed
Then drafting is separated from acting or committing
And sending remains blocked until scoped authority, editable preview, fresh
confirmation, limits, audit, interruption, and recourse are verified.

### Scenario: Unknowns remain visible

Given analytics and interviews conflict about an automatic action
When the agent evaluates the evidence
Then both sources and their limitations remain visible
And a high-consequence unresolved conflict blocks or uses an approved reversible
experiment instead of being converted into a confident persona claim.

## Success Criteria

- Held-out behavioral evaluations detect both unsafe under-analysis and ritual
  over-processing.
- L1 work avoids durable UX artifacts unless another trigger requires one.
- L3 work never proceeds on a high-consequence unknown without accepted control.
- UX, Planning, UI, and UAT consume one authority contract without contradictory
  persona, state, metric, or evidence requirements.
- Installed discipline content is versioned, integrity-checked, dry-runnable,
  non-destructive to foreign files, and reversible.
- Accessibility, usability, and protection claims never exceed their evidence.
