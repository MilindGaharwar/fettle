# UX Spec: Scoped Formal Verification Evidence

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/formal.md).

Status: PROPOSED, 2026-10-11; planning only, no interface change or live evaluation
authorized. Implements the experience boundary for the
[conformance plan](formal-verification-conformance-plan.md).

Planning extension, 2026-10-16: FM-7 through FM-11 add scoped completion,
aggregation and authority-flow claims to the same inspection flow. This is not
an interface implementation, new authority, or acceptance of the proposed UAT.

## Jobs To Be Done And Personas

When a critical implementation changes, I want to see what was checked, whether
the evidence still applies, and what remains unproven, so I can make an informed
acceptance decision without interpreting raw TLC output.

- New adopter: needs to distinguish a checked model from a verified program.
- Maintainer or agent: needs deterministic JSON, exact scope, and replay commands.
- Accessible terminal user: needs complete meaning without color, motion, a mouse,
  or an interactive prompt.
- Acceptance owner: needs independent evidence and an explicit approval boundary.

## Session Narrative

1. A maintainer changes a capsule mode-merge branch.
2. The existing edit advisory names the affected claim, not a verified file.
3. Previous evidence is shown as inapplicable to the new source snapshot.
4. The maintainer starts the explicitly authorized verification profile.
5. The runner reports the selected property, bounds, and time limit.
6. The unchanged model passes, but a conformance assertion fails.
7. The result names the operation and the expected and actual mode ranks.
8. A short replay command reproduces the counterexample in isolation.
9. The maintainer repairs the implementation without weakening the property.
10. A rerun retains separate model and conformance observations.
11. Explain/report shows the finite scope and excluded policy classes.
12. The acceptance owner decides against the existing criteria; the tool never
    announces that all Fettle source or all agent behavior has been proved safe.

## Journey And Budgets

| Stage | User action | Sees | Desired feeling | Failure prevented |
|---|---|---|---|---|
| Entry | Changes mapped code | Affected claim and invalidation reason | Oriented | Trusting stale evidence |
| Run | Starts approved profile | Property, bounds, progress, time limit | In control | Silent or unbounded work |
| Inspect | Reads result | Model and conformance separately, with exclusions | Informed | A model pass hiding broken code |
| Recover | Runs displayed replay | Exact expected/actual mismatch | Able to act | Unusable checker trace |
| Accept | Uses existing assurance flow | Criteria, evidence, unresolved obligations | Certain about limits | Automatic policy or approval escalation |

Normal flow: one verification invocation, one optional detailed inspection.
Recovery: at most one displayed replay command before returning to the edited
code. No menu or additional top-level CLI namespace. Proposed comprehension
target: an experienced recipient identifies claim, scope, and next action within
60 seconds in the frozen UAT cases. Freeze runtime targets in WP-FM-0; a longer
run reports progress without implying that exploration will complete.

## Required States

| State | User-visible behavior |
|---|---|
| First-time empty | No formal evidence recorded; name the selected claim and approved execution route, not a clean result |
| Cleared empty | Previously retained evidence is unavailable; required criterion remains non-pass; show regeneration route |
| Filtered empty | No admitted property matches this scope; do not widen selection or report that the project passed |
| Loading brief | Name the active profile without animation or repeated output noise |
| Loading long | Show model/conformance phase and resource limit; cancellation leaves an incomplete observation |
| Populated | Separate model result, conformance result, validity, bounded scope, and acceptance disposition |
| Recoverable error | Name missing tool, timeout, stale input, or failed case; preserve evidence and provide one concrete recovery |
| Fatal error | Reject malformed/unsafe/unsupported evidence; no success fallback and no raw secret/path disclosure |
| Offline | Permit already-installed local verification; report unavailable installation/remote evidence honestly; history stays diagnostic |
| Stale | Explain the changed source/model/config/tool/oracle binding; touching or backdating files cannot restore validity |

## Information, Accessibility, And Persistence

Reuse the existing [evidence inspection flow](canonical-evidence-inspection.ux-spec.md)
and the [CLI presentation contract](formal-verification-conformance.ui-spec.md).
Default output includes claim, outcome, scope, and recovery. Details reveal
assumptions, evidence references, bindings, and counts; they are not prerequisites
for seeing exclusions or non-pass states. Persist domain evidence through the
existing canonical retention path, not terminal history or an in-memory badge.

All statuses have text and stable machine fields. Human/JSON outputs must agree.
Support `NO_COLOR=1`, redirected stdout, keyboard-only use, and an 80-column
terminal. No accessibility meaning depends on alignment, icons, or hyperlinks.
Counterexample detail is bounded/redacted without changing its stated outcome;
if safe reproducibility cannot be retained, expose that limitation explicitly.

## Agency And Approval

| Action | Authority |
|---|---|
| Inspect local bindings and name invalidated evidence | Automatic within existing hook permissions |
| Suggest a bounded profile or replay | Suggest only |
| Execute checker or project code | Explicitly authorized run/CI profile; isolated environment |
| Change property, assumptions, scope, or budgets | Reviewed change with new evidence identity |
| Promote a required criterion or change policy | Explicit operator approval |
| Hide a timeout, relax requirements to pass, or declare whole-program proof | Never |

## BDD Acceptance Scenarios

### BDD-FM-1: A scoped successful observation

Given complete matching model and conformance evidence for the admitted domain
When the recipient inspects the result
Then it names the finite model bounds and tested implementation scope separately
And it does not claim unbounded verification or proof of excluded behavior.

### BDD-FM-2: The implementation diverges from a passing model

Given unchanged TLC passes and a seeded weaker-local-wins implementation fails
When the profile completes
Then conformance is non-pass with expected/actual values and a replay command
And the model pass cannot satisfy the combined claim.

### BDD-FM-3: Evidence is stale despite unchanged timestamps

Given a complete report for candidate A
When source, model, configuration, mapping, test oracle, or tool bytes change
Then old evidence is rejected with the exact binding mismatch
And no modification-time comparison or copied report can restore applicability.

### BDD-FM-4: Execution cannot establish a result

Given a missing tool, timeout, cancellation, crash, or malformed output
When the run or consumer evaluates it
Then the required obligation remains non-pass with its reason and recovery
And an exit code or partial log cannot manufacture a complete observation.

### BDD-FM-5: Nothing applicable was checked

Given no selected property, an excluded input, or only skipped required cases
When verification is requested
Then scope/applicability and executed counts make the gap visible
And the result never says the requested required criterion passed.

### BDD-FM-6: Recipient reads without color or a TTY

Given successful, failing, stale, and incomplete retained reports
When human and JSON output are captured without a TTY and with NO_COLOR enabled
Then claim, scope, result, validity, and recovery agree in both representations
And no state or caveat is conveyed only by styling.

### BDD-FM-7: Optional evidence does not create authority

Given the new formal input is advisory and a previous report is removed
When Assurance evaluates the change
Then it shows the missing observation without silently adding a required gate
And an explicitly required formal criterion, if later approved, remains non-pass.

UAT record requirements: exact candidate/profile, scenario ID, observed output,
reviewer, elapsed comprehension time, verdict, and unresolved limitation. Scripted
fixtures validate mechanics; an independent recipient walkthrough validates
comprehension. Neither has been executed by creating this planning document.

## Internal Assurance Continuation

Actual actors: the maintainer investigating a completion result, the domain
evaluator owner defining what an observation establishes, and the acceptance
owner deciding readiness. Use existing completion and Assurance inspection; no
new navigation surface or generic persona exercise is required.

Journey: select a scoped result -> see each required obligation and its expected
outcome -> inspect evidence applicability and semantic observation -> see the
authorized evaluator and unresolved reason -> perform the approved recovery ->
reevaluate the current candidate -> obtain the existing acceptance disposition.
The consumer must not require the recipient to infer success from a hash or to
read raw artifact JSON to find a missing obligation.

| Condition | Required experience and recovery | Owner/evidence |
|---|---|---|
| No admitted criterion or no selected required obligation | Explicit unqualified/unknown scope, never vacuous success; show the contract/inventory review route | FM-7/FM-8; BDD-FM-8/9 |
| Valid identity but insufficient meaning | Distinguish intact evidence from an unestablished criterion; name the admitted evaluator and missing observation | FM-8; BDD-FM-8 |
| Timeout, cancellation or unfinished evaluation | Preserve diagnostic evidence; required success stays unresolved; offer the authorized rerun, not automatic work | FM-8; BDD-FM-10 |
| Missing, conflicting or newly stale evidence | Show the affected required obligation and deterministic reason; return to current-candidate evaluation | FM-9; BDD-FM-9/12 |
| Untrusted annotation claims approval | Authority and selected checks remain unchanged; keep diagnostic text bounded and separate | FM-10; BDD-FM-11 |
| Legitimately repaired evidence | Show the reevaluated scoped result without implying unrelated claims passed | FM-8/FM-11; BDD-FM-12 |
| Legacy or advisory-only observation | Preserve current behavior; state the new claim was not established and do not add policy requirements | FM-8/FM-11; BDD-FM-13 |

Reuse the required offline, fatal/recoverable error, accessible terminal and
persistence behaviors above. Unknown and rejected must not look like approved
completion. An artifact's self-declared trust label is never presented as approval
authority. The independent recipient walkthrough must cover both recovery and
correct refusal; no runtime UAT or fixed comprehension result is claimed here.

### BDD-FM-8: Integrity does not establish sufficiency

Given a current, well-formed, digest-matching artifact for an opted-in criterion
And its authorized semantic evaluator has not established the expected outcome
When the recipient inspects completion
Then evidence integrity and criterion sufficiency are shown separately
And the criterion remains non-pass with a named missing observation and recovery.

### BDD-FM-9: Required evidence cannot disappear into success

Given a fixed approved inventory, policy, scope and required obligation
When evidence is removed, made uncertain, or contradicted by another observation
Then the new claim cannot become eligible by omission or favorable selection
And the affected obligation and unresolved reason remain visible.

### BDD-FM-10: Correct timeout handling is not successful work

Given a required success criterion and a separately specified timeout-handling test
When the underlying operation times out within the allowed handling contract
Then timeout handling may be confirmed against its own expected outcome
And the required success criterion remains unestablished, with separate evidence.

### BDD-FM-11: Untrusted annotations cannot acquire authority

Given two valid observations with identical trusted policy and semantic inputs
And annotations differ only in untrusted claims of approval or skipped checks
When the real consumer evaluates each observation
Then eligibility, selected checks, required obligations and effective policy agree
And diagnostic or occurrence differences do not conceal an authority difference.

### BDD-FM-12: Authorized evidence changes permit recovery

Given an unresolved criterion with an explicit recovery action
When an authorized evaluator supplies complete evidence for the current candidate
Then reevaluation may establish that criterion and names the changed observation
And stale candidate evidence and unrelated unresolved criteria remain non-pass.

### BDD-FM-13: New qualification does not rewrite legacy authority

Given a legacy manifest or an advisory-only internal claim
When the extended result is inspected alongside existing acceptance criteria
Then the legacy behavior and existing policy remain unchanged
And the recipient can distinguish existing acceptance from the unestablished new
semantic qualification, without an implied stronger proof or new required gate.

FM-11 acceptance retains the scenario IDs, exact candidate/claim/evaluator/input
identities, human and JSON outputs, reviewer, observation and recovery verdicts.
Scripted checks cover all six scenarios; an independently reviewed recipient
walkthrough covers the actual decision/recovery tasks. Freeze accepted usability
limits at FM-7; a timer alone cannot establish comprehension or correctness.