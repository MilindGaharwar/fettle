# Incident Learning UX And Acceptance Contract

> Integration precedence — current main’s November 14 sequencing decision and
> trust-remediation ownership govern execution. Earlier scheduling and review
> observations below remain historical. This merge grants no feature approval.

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/incident.md).

Status: PROPOSED; planning only. Runtime and user acceptance remain unverified.
Owner: [implementation plan](incident-learning-implementation-plan.md).
Presentation: [CLI contract](incident-learning.ui-spec.md).

## Governing Experience Standard

Use the planned [Experience Discipline vNext contract](experience-discipline-vnext.ux-spec.md)
and its [migration plan](experience-discipline-vnext-plan.md) as the design standard
requested for P0-IL. They remain proposed, not installed skills or verified runtime
behavior. Rebind to the accepted contract version in IL-1; record and resolve any
material difference before implementation. No global skill is modified here.

The current documentation correction does not require product UAT. The future
runtime is L3 Controlled for the independent reasons below, not because P0 is a
risk score. A small CLI surface does not reduce consequence.

| Trigger | P0-IL basis | Required control |
|---|---|---|
| Harm | Evidence may contain sensitive data; mistaken closure can mislead product decisions | Purpose/access/retention boundaries, explicit non-pass evidence, reversible drafting |
| Scope | Records cross producers, sessions, roles, candidates and possibly repositories | Source binding, occurrence identity, recovery and stable criterion ownership |
| Autonomy | Grouping and proposals recommend causes or priorities; writing changes retained records | Separate inform/recommend/prepare/act authority and require explicit scoped invocation |
| Uncertainty | Coverage, diagnosis, historical evidence and benefit may be unknown | Claim states and validation/containment; no implementation through an uncontrolled consequential unknown |

L3 warrants this durable spec, semantic criteria, approval and recovery plan.
Do not turn it into a universal artifact requirement for later L1 changes. An L2
sub-flow may use a short brief, but cannot bypass its enclosing L3 criterion.

## Jobs To Be Done

When an AI-agent task fails, retain enough trustworthy evidence to investigate it
without repeating the expensive run. Turn a reviewed diagnosis into a bounded
improvement and distinguish delivery from proven prevention.

## Actors And Context

- Operator: inspects incidents, grants bounded access and approves proposed work.
- Agent or maintainer: preserves evidence and drafts improvements within that scope.
- Reviewer: challenges diagnoses, source bindings and closure evidence.
- Affected user: needs understandable, accessible reporting and correction when a
   task or its verification fails; task-specific needs require supplied evidence.

These are workflow roles, not invented research personas. Actual user familiarity
and assistive-technology needs remain to be established for the pilot. Select
participants to resolve those uncertainties, not to satisfy a persona count.

## Journey

| Phase | Action | Visible result | User concern addressed |
|---|---|---|---|
| Entry | Inspect retained incidents | Scope, observed interval, capture limitations and roster | No data is not mistaken for no failures |
| Inspect | Select an incident ID | Observed/expected result, occurrences, available evidence and uncertainty | No need to remember run IDs across commands |
| Triage | Review cause and explicit candidate improvements | Hypothesis versus confirmed diagnosis; owner and approval needed | Avoid confident but unsupported explanations |
| Propose | Explicitly draft a local work item | Created path, incident links and unapproved status | No silent model, policy or repository mutation |
| Verify | Inspect candidate-bound acceptance evidence | Each criterion's actual outcome | A passing test count is not blanket prevention |
| Exit | Reopen the roster later | Retained links, unchanged history and next action | Learning survives the session |

Use this journey to expose cross-role/session handoffs and memory burden. It is
not research evidence. Carry IDs forward in output rather than requiring recall.
Do not prescribe a universal invocation count or time target. IL-5 measures actual
human effort against the manual baseline; freeze any decision threshold before
observing candidate results. Script duration is not human task time.

## Derived Transitions And Recovery

Transitions come from actual reads, persistence, identity, permissions and
cross-session handoffs. There is no required state count or loading animation.
Extend this table when implementation exposes another reachable material path.

| From/precondition | Trigger | Observable outcome | Failure or partial result | Recovery | Verification |
|---|---|---|---|---|---|
| No retained records or active filters | Inspect scope | Count and coverage are distinct; filters visible | No data or unreadable source does not mean no failures | Remove filter or supply an approved source; keep unknown coverage explicit | IL-UX-06 |
| Authorized source available | Retain occurrence | Stable occurrence and evidence references | Missing permission, malformed input, foreign identity or secret risk | Stop affected write, preserve source, request corrected scope/input | IL-UX-01/03/04/05 |
| Occurrence already recorded | Import or retry | Same event adds nothing; new attempt remains distinct | Conflicting identity or concurrent duplicate write | Surface conflict; inspect existing record before retry, never auto-merge cause | IL-UX-02/07 |
| Source log rotated or artifact removed | Reinspect incident | Retained artifact usable or reference explicitly unavailable | Stale candidate or missing required bytes | Restore approved matching artifact or retain non-pass; never relabel fresh | IL-UX-04/06 |
| Incident awaiting triage | Recommend cause or improvement | Sources, uncertainty and alternatives visible | Weak or conflicting evidence; untrusted instructions | Keep hypothesis open, request evidence/review; do not execute embedded instructions | IL-UX-01/05/09 |
| Reviewed draft and scoped local-write approval | Create improvement | Editable work item with links, no active policy change | Interrupted write, offline provider, disk/permission failure | Preserve original evidence, inspect partial result, retry idempotently or use deterministic draft | IL-UX-07/08 |
| Another session or reviewer resumes | Inspect record and acceptance evidence | History, approval needed and criterion outcomes persist | Investigation closed but fix open; timeout-only success claim | Keep claims separate; obtain applicable evidence through existing completion owner | IL-UX-10/11 |
| Untrusted long text in terminal/non-TTY | Render human or JSON view | Readable text, neutralized controls, clean JSON | Unsupported assistive path or interrupted read | Emit bounded stderr diagnostic; retain inputs and block unsupported acceptance claim | IL-UX-12 |

## Claim States And Evidence Scope

Use the shared states VERIFIED, SUPPORTED, ASSUMPTION, UNKNOWN and HUMAN REVIEW
REQUIRED for decision-driving claims. These are epistemic labels, not another
work-item status or completion evaluator. Retain basis, confidence, consequence
if wrong, and validation/containment path. Conflicting sources remain visible.

| Claim | Current planning state and basis | Consequence if wrong | Validation or containment |
|---|---|---|---|
| Existing trace/learning/work-item owners provide reusable foundations | SUPPORTED by inspected local source; not the latest delivered candidate | Wrong integration boundary | Rebind source and producer/consumer tests at IL-0/1 |
| Proposed flow can reduce investigation effort | ASSUMPTION; no measured comparison | Added ceremony and cost | IL-0 manual walkthrough, IL-5 frozen human-effort comparison |
| Historic evidence is available and safe to retain | UNKNOWN until source/access inspection | Privacy loss or unsupported diagnosis | No copying/export until permissions and redaction/retention reviewed |
| A proposed cause explains a particular incident | UNKNOWN until incident-specific evidence; HUMAN REVIEW REQUIRED for disputed cause | Wrong fix or prioritization | Reproducer or appropriate domain investigation plus reviewer decision |
| CLI is usable through applicable assistive technology | UNKNOWN until acceptance-time checks | User excluded from task completion | Named runtime/technology walkthrough; no conformance claim from snapshots |

Keep design-time analysis, build-time checks, acceptance-time human/assistive
checks and runtime incidents/monitoring separate. A scripted CLI pass does not
measure human completion rate; a schema-valid record does not confirm its cause.
Runtime recurrence statistics must state observed coverage and cannot prove that
unobserved sources were failure-free.

## Shared Blocking Gates Applied

The linked vNext contract owns the nine gates. This table maps their application;
it does not introduce an independently evolving rule set or aggregate UX score.

| Shared gate | P0-IL application |
|---|---|
| 1 Outcome undefined | Actor, requested action and observable incident/improvement result must be defined |
| 2 High-consequence unknown | Unknown evidence rights, retention or diagnosis-based consequential action needs accepted containment or review |
| 3 Uncontrolled side effect | File writes, model submission, export and policy actions require explicit scope and suitable preview/recovery |
| 4 Critical recovery absent | Partial writes, duplicate effects and unavailable evidence must not strand the operator or conceal loss |
| 5 Known accessibility barrier | Changed inspection/drafting must work through the applicable terminal/assistive path; unsupported acceptance remains blocked |
| 6 Privacy or deceptive choice | Explain collection purpose, access and retention; refusal of optional model/export use must leave the local flow usable |
| 7 Agent authority mismatch | Recommendations are not authorization; no self-approved policy, priority-driven execution or source expansion |
| 8 False verification claim | Source, fixture, human and runtime evidence retain their actual scope; no timeout-to-success inference |
| 9 Broken controlled-work traceability | Every IL-UX criterion below requires an implementation owner and scoped verification reference |

Stop the affected implementation when a gate is unresolved. Exceptions require an
external owner, reason, review/expiry point and residual risk; an agent cannot
self-approve a high-consequence exception. Unknown legal applicability requires
human review, not an autonomous compliance assertion.

Authority progresses from inform (source-linked inspection), recommend (editable
cause/priority suggestions), prepare (previewed proposal) to act (explicit local
write). Consequential commit, publication, external model submission or policy
promotion needs its own approval and recourse; none is implied by draft creation.

## Information Architecture And Persistence

Use existing work, learn and report command families. Exact proposed flags and
exit behavior are frozen in IL-1; no new dashboard or top-level service. Roster
summary and incident detail are the two disclosure levels. Keep evidence locations
and next actions in the detail output. Work items and canonical evidence retain
knowledge; runtime claims retain ownership; no new mutable roster cache is an
authority. Read-only inspection must leave file content and modification times
unchanged. No automatic issue publication or deletion command is part of v1.

## Accessibility And Runtime Boundaries

Use labeled plain text, stable headings, wrapped prose and full IDs in detail.
Respect NO_COLOR and non-TTY output, avoid cursor control, and emit clean JSON
without progress mixed into stdout. Test 80- and 120-column terminals, long paths,
Unicode text and screen-reader linear reading. ANSI/control bytes from untrusted
logs must not execute terminal sequences. Browser layouts, axe, LCP and mandatory
network requests are inapplicable to this local CLI; adding a web surface requires
a separate spec. Verify each claimed OS/runtime; one platform is not all hosts.

## BDD Scenarios

These stable semantic IDs carry through plan, implementation and UAT. BDD is a
convenient expression of observable outcomes, not a required syntax for all work.

1. Given a retained local failure with available evidence, when an operator
   inspects it and explicitly drafts an improvement, then one unapproved work item
   links the incident, observed failure and evidence without applying a fix.
2. Given the same source event twice, when it is imported again, then occurrence
   count is unchanged; given a distinct retry with identical text, count increases
   and the original event remains available.
3. Given identical messages from different repositories, when candidates are
   grouped, then identities remain separate and no shared cause is assumed.
4. Given a missing, stale, foreign or malformed required artifact, when the roster
   and completion consumer inspect the item, then they preserve its non-pass
   evidence state and show recovery rather than verified closure.
5. Given a raw trace with a secret or a command-like instruction, when evidence is
   retained or a proposal drafted, then redaction/input limits apply and no command,
   network request, policy change or approval follows from that text.
6. Given capture failed or the trace was rotated, when no incidents are returned,
   then the operator sees the known coverage limitation, not a zero-failure claim.
7. Given an interrupted local write, when the operator retries, then the original
   failure is retained, partial state is visible and no duplicate or false success
   is produced.
8. Given an offline environment with no model credentials, when the operator
   inspects and drafts locally, then the useful deterministic flow succeeds and
   read-only commands do not write files.
9. Given a research source-attribution error or spreadsheet formula-verification
   failure, when a synthetic record is processed, then generic incident links work
   without demanding a Python test or Semgrep rule as its domain evidence.
10. Given an investigation was completed but its proposed fix remains open, when
    the roster is read, then investigation completion is not presented as delivered
    prevention; a new recurrence preserves the previous history.
11. Given a timeout-handling test passed but the required successful execution was
    never observed, when closure is requested, then the success criterion remains
    non-pass under the existing completion evaluator.
12. Given long or untrusted text in an 80-column non-TTY terminal, when an incident
    is inspected, then content remains readable, terminal escapes are neutralized,
    JSON parses and status does not depend on color.

## Criterion Ownership And Handoff

IL-UX-01 through IL-UX-12 refer respectively to the numbered scenarios above.
File owners below are proposed implementation boundaries, not implemented claims.
IL-1 assigns a responsible person/agent and IL-5 attaches the actual evidence
reference, candidate, runtime, result, reviewer and remaining unknowns for each ID.

| Criterion | Implementation owner | Build-time verification | Acceptance/runtime scope |
|---|---|---|---|
| IL-UX-01 | [learn.py](../fettle/learn.py), [work_items.py](../fettle/work_items.py) | IL-3 actual draft-to-parser fixture | Operator identifies evidence and next approval |
| IL-UX-02 | [evolution.py](../fettle/evolution.py) | IL-3 same-event/new-attempt fixture | Repeat ingestion count and preserved history |
| IL-UX-03 | [evolution.py](../fettle/evolution.py) | IL-3 foreign-repository fixture | Reviewer checks grouping boundaries |
| IL-UX-04 | [evidence.py](../fettle/evidence.py), [report.py](../fettle/report.py) | IL-2/4 missing/foreign/stale artifact checks | Operator sees non-pass and recovery |
| IL-UX-05 | [trace.py](../fettle/trace.py), [learn.py](../fettle/learn.py) | IL-2/3 redaction and instruction-injection fixtures | Reviewed data-use scope; no implied export |
| IL-UX-06 | [trace.py](../fettle/trace.py), [report.py](../fettle/report.py) | IL-2/4 rotation/empty/coverage checks | Operator distinguishes no data from no failures |
| IL-UX-07 | [evidence_ledger.py](../fettle/evidence_ledger.py), [learn.py](../fettle/learn.py) | IL-2/3 interrupted-write and retry checks | Restart walkthrough preserves data and visible partial state |
| IL-UX-08 | [learn.py](../fettle/learn.py), [cli.py](../fettle/cli.py) | IL-3/4 offline/no-write inspection tests | Local flow without credentials or model consent |
| IL-UX-09 | [work_items.py](../fettle/work_items.py), [learn.py](../fettle/learn.py) | IL-1/3 synthetic research/spreadsheet fixtures | No live domain effectiveness claim from fixtures |
| IL-UX-10 | [work_items.py](../fettle/work_items.py), [report.py](../fettle/report.py) | IL-4 existing completion-boundary checks | Reviewer distinguishes investigation and fix closure |
| IL-UX-11 | [report.py](../fettle/report.py), [cli.py](../fettle/cli.py) | IL-4 timeout-not-success regression | Required success remains non-pass without its evidence |
| IL-UX-12 | [report.py](../fettle/report.py), [cli.py](../fettle/cli.py) | IL-4 control-byte/JSON/width checks | Named keyboard/screen-reader/runtime observation, not generic conformance |

## Manual UAT Protocol

Use a disposable repository and fresh local state at the exact packaged candidate.
Record actual actor/task context, platform/interpreter, applicable assistive
technology, source identities and results by IL-UX criterion. Do not invent a
persona or imply one participant represents a disability group.
Walk the complete inspect-to-draft-to-verify flow, interrupt a write, remove a
required artifact and repeat offline. Verify files after restarting the command.
Ask users to identify what is known, what is uncertain, which action needs approval
and whether the fix is actually verified. Record mistakes and assistance.

Required critical scenarios must all pass; skipped, blocked and unobserved cases
remain non-pass. Privacy loss, false closure and unauthorized side effects block
rollout. Independently review outcomes; do not count automated cross-review as a
human session. Report speed/effort separately from correctness and preserve null
results. No live host or model access is authorized by this protocol.