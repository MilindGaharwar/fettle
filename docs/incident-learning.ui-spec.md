# Incident Learning CLI Presentation Contract

Status: PROPOSED; not an implemented command reference.
Scope: local terminal and JSON only. No browser application, component library,
new navigation system or frontend dependency is required.

Owner: [implementation plan](incident-learning-implementation-plan.md).
Flow and BDD: [UX contract](incident-learning.ux-spec.md).

## Proportional Presentation

Follow the [planned vNext contract](experience-discipline-vnext.ux-spec.md) through
the P0-IL L3 route and IL-UX criteria. This file owns CLI presentation only; it
does not duplicate risk routing, claim-state definitions or blocking gates.
No fixed persona count, state catalog, click budget or browser metric applies.
Future small presentation changes may use L1 inline evidence when their actual
consequence permits; they need not recreate this document.

## Reference And Components

Use existing Fettle report/work command conventions, with GitHub CLI's concise
list-to-detail interaction as a reference, not a dependency. Reuse current CLI
formatting helpers where suitable. Components are plain-text summary rows,
key/value detail sections, stderr diagnostics and versioned JSON objects.

## Proposed Command Surface

IL-1 must verify parser compatibility and freeze spelling before implementation.
Candidate options are `fettle report --incidents [--json]` for read-only roster
inspection and `fettle learn --from-trace --proposal-kind improvement` for explicit
local deterministic proposal creation. These options do not exist by virtue of
this document. Preserve existing command defaults and rule-generation behavior.
Do not retrofit silent model calls into the proposed generic improvement mode.
Choose an incident-detail selector under the same report surface during IL-1.

## Output Order

1. Scope and observation window; explicit capture/evidence limitations.
2. Incident ID, short observed failure and occurrence count.
3. Diagnosis confidence, linked improvement and approval needed.
4. Delivery state and criterion-evidence state, kept separate.
5. Next action; detail includes full artifact identity, location and availability.

Stable text labels: UNKNOWN, UNAVAILABLE, PROPOSED, APPROVAL REQUIRED and VERIFIED
describe the corresponding field, never a global verdict. In particular VERIFIED
must name its criterion and candidate; it is not synonymous with all issues fixed.
Display epistemic claim state, evidence availability, work-item delivery and
approval separately. SUPPORTED, ASSUMPTION and HUMAN REVIEW REQUIRED use the
shared claim contract; they are not new lifecycle states. A cause suggestion
shows basis, uncertainty, material alternatives and how to correct it. Refusing
optional model assistance must preserve the usable local path.

## Rendering Rules

- Use terminal-default foreground/background. Optional existing semantic colors
  are enhancements only; every meaning has a text label. Respect NO_COLOR.
- Use the user's monospace terminal font. Do not add typography assets or cursor
  animations. Align numeric counts; use labeled blocks where a table cannot fit.
- At 80 columns, wrap descriptions and use detail blocks. Never truncate an ID
  required for an action without providing its full value in detail/JSON.
- Default state is unfiltered inspection; selected state names active filters;
  unavailable actions show their prerequisite. Hover is inapplicable to this CLI.
- Escape untrusted terminal controls and keep progress/errors out of JSON stdout.
  JSON has an explicit version and separate errors, coverage and evidence fields;
  exact field names, error aggregation and exits are frozen with IL-1.
- A successful report command means inspection completed, not that listed work
  passed. Invalid input/read failures must be distinguishable from a valid report
  containing open items. Completion validation retains its own exit semantics.
- No mandatory interactive confirmation for read-only inspection. Write/model
  operations require explicit invocation and the approved scope; automated callers
  must never hang on a hidden prompt or silently approve themselves.

## Presentation Verification

Use existing report/CLI tests with golden human and parsed JSON assertions where
appropriate. Include 0, 1 and 1000 synthetic records; long IDs, Unicode, unavailable
evidence and malicious ANSI content. Count selected tests to prevent an empty test
selection from passing. Confirm stdout/stderr separation and no file writes during
inspection. IL-5 records actual keyboard and screen-reader usability; no visual
or human acceptance is claimed by these planned assertions.