# Audit Hardening UX Acceptance Contract

Date: 2026-09-18. Status: immediate repairs authorized and locally exercised;
independent acceptance and later enhancement designs remain pending.
Plan: [work packages](audit-hardening-implementation-plan.md).

## Jobs To Be Done And Personas

When I use Fettle to approve a change, I want to know which required checks really
ran and how to recover from incomplete execution, so a green result is trustworthy.

- New user: installs a wheel, follows help, runs a first check without checkout knowledge.
- Power user: automates JSON/exit-code consumption and runs concurrent agent sessions.
- Accessible user: uses keyboard and screen reader, plain text, and non-color terminals.

## Day-In-The-Life

1. A maintainer opens a repository before reviewing a change.
2. They install Fettle into an isolated tool environment.
3. They run help and find the existing check and doctor commands.
4. Doctor identifies unavailable prerequisites without claiming enforcement worked.
5. They run a quality check for an explicit scope.
6. A required analyzer is unavailable; the result is a non-pass with recovery guidance.
7. They restore the prerequisite and repeat the same command.
8. The clean result now represents completed checks rather than empty findings alone.
9. A parallel agent writes evidence without corrupting the other session's history.
10. An enforced hook cannot run in time; it blocks with a reason rather than allowing silently.
11. The maintainer resolves the cause and retries the original operation.
12. CI independently checks the candidate; only validated results support completion.

## Journey And Interaction Budget

| Phase | Action | Sees | Likely feeling | Design response |
|---|---|---|---|---|
| Entry | Install, help, doctor | Actual installed capabilities | Uncertain | No source-checkout dependency or implied verification |
| Core | Run check or hook | Pass, violation, or unavailable with reason | Needs confidence | Required execution failures cannot look clean |
| Recovery | Follow named recovery action | Preserved scope and actionable retry | Frustrated | No unexplained traceback or lost evidence |
| Exit | Inspect CI/evidence | Exact candidate outcome and limitations | Informed | Unknown and stale remain visibly non-pass |

No extra command on the healthy path. Target: identify the failing prerequisite and
next recovery action within 30 seconds from an error result; verify with manual UAT.
Recovery path should require at most doctor, the necessary operator repair, and retry.
Hook latency uses the existing configured budgets; exceeding them must not weaken policy.

## States

| State | Expected CLI behavior |
|---|---|
| First-time empty | Explain missing setup/evidence and next action; no fabricated pass |
| Cleared empty | Explicit missing evidence after reset; never reuse removed approval |
| Filtered empty | Distinguish legitimate no-applicable-files from invalid or zero scan scope |
| Loading under 1 second | Stable output and correct final exit; no unnecessary chatter |
| Loading over 1 second | Bounded execution, useful diagnostics, no partial success claim |
| Populated | Human result and JSON agree on findings, validity, and scope |
| Recoverable error | Name analyzer, lock, environment, or input cause and retry action |
| Fatal error | Nonzero exit with preserved evidence; do not silently rebuild suspect ledger |
| Offline | Local checks remain usable; unavailable external checks stay explicitly unknown |
| Stale | Show why evidence is stale and which producer must rerun |

## Information And Accessibility

Retain existing command names, JSON shapes where valid, and noninteractive usage.
Use text labels in addition to color; send diagnostics to stderr without corrupting
machine-readable stdout. No browser UI, animation, new navigation, or mouse requirement.
Preserve source/scope identity and retained evidence across retries. Default output
shows result, cause, and next action; detailed provenance uses existing inspection commands.

## UAT Scenarios

### AH-UAT-01: Failed Analyzers Cannot Look Clean
Given an explicit source fixture and unavailable required analyzers,
when the user invokes the standalone scan or CI self-scan,
then exit is nonzero and output identifies incomplete analysis even with no findings.
Given functioning analyzers and clean source, the same command completes successfully.

### AH-UAT-02: Invalid Action Evidence
Given empty scan paths, malformed scanner output, or contradictory status and exit,
when the Action runs in advisory or enforce mode,
then it reports execution failure rather than zero-findings success.
Valid advisory findings remain advisory; valid enforced errors remain blocking.

### AH-UAT-03: Required Hook Misses Deadline
Given an explicitly enforced check and an earlier check that exhausts the event budget,
when the synthetic tool request reaches the dispatcher,
then the operation is not allowed solely because the required check was skipped,
and the user receives an actionable failure reason. No destructive command is executed.
Optional advisory omissions must not be converted into blanket hard failures.

Given corrupt local policy, an unavailable explicit policy file, or an exception
while loading policy, the hook blocks before selecting checks and names doctor
and retry as the recovery path. Repairing that policy restores the normal path.
Given registry selection failure, applicable required checks remain non-pass;
advisory-only configurations report unavailable checks without a blocking verdict.
Compound checks preserve event semantics: plan/UX blocks before edits, not after;
enabled test enforcement blocks at Stop. Diagnostic config inspection remains
permissive and must not be mistaken for successful enforcement.

### AH-UAT-04: Concurrent Evidence
Given two independent processes writing to the same ledger,
when their read/append operations overlap or encounter rotation/anchoring,
then accepted records form one valid ordered chain or the operation fails visibly.
Existing corrupt evidence remains inspectable and is never silently repaired.

### AH-UAT-05: Installed Graph Command
Given a fresh wheel installation outside the source checkout with Git available,
when the user runs graph status in a disposable supported repository,
then provider imports succeed and the result describes the actual repository.
Editable-install hooks and PYTHONPATH must not rescue missing package contents.

### AH-UAT-06: Valid UAT Classes
Given the same profile seed,
when the user generates a UAT profile twice,
then outputs are deterministic, zero is numeric zero, valid email remains valid,
and deliberately invalid values are labeled separately from valid classes.

## Admission Limits

These scenarios cover immediate correctness repairs, not all later enhancements.
AH11 must extend this contract with tested command-discovery flows before coding.
AH12 requires a dedicated UI specification, threat model, and accessible prototype.
Polyglot parity, human UAT parity, and contextual ranking remain separately gated.