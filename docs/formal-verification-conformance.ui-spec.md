# UI Spec: Formal Evidence In Existing CLI Surfaces

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/formal.md).

Status: PROPOSED, 2026-10-11; presentation contract only. No dashboard, new command
namespace, visual theme, or runtime interface is authorized.

Extended 2026-10-16 for the proposed internal-assurance packages; presentation
remains planning-only and uses the same existing CLI conventions.

References: [implementation plan](formal-verification-conformance-plan.md),
[UX/BDD contract](formal-verification-conformance.ux-spec.md), and existing
[canonical evidence inspection](canonical-evidence-inspection.ux-spec.md).

## Surface And Layout

Use the current CLI finding/report conventions rather than introducing new
components. The named reference is Fettle's existing `explain --detailed`,
`report`, and Assurance evidence inspection. No browser surface is in scope.

Default reading order:

1. Claim identifier and narrowly scoped acceptance disposition.
2. Model observation and implementation conformance observation, separately.
3. Model bounds, implementation domain, and important exclusions.
4. Invalidity/counterexample reason and one concrete recovery action, if needed.
5. A retained evidence reference for optional detailed inspection.

Illustrative layout, not a new command or frozen machine schema:

```text
Claim: capsule.mode_monotonicity.v1
Model: checked within declared bounds
Conformance: failed
Scope: canonical mode leaves; 3 modeled agents; depth 2
Excluded: numeric thresholds, roles, arbitrary runtime schedules
Reason: child mode became weaker than inherited mode
Replay: <the exact command retained with this counterexample>
```

Actual bounds must come from the checked configuration, never this illustration.
Do not show an overall green/verified badge above incomplete component results.

## Tokens And Density

- Reuse existing status styles; textual result names carry all meaning.
- Use the user's terminal font and existing spacing. No new color palette.
- Prefer labeled lines over wide tables; wrap prose at terminal width without
  truncating a property, exclusion, failure reason, or recovery command.
- Keep full identities in structured/detailed output. Displayed abbreviations
  are convenience labels, never the values used for validation.
- No spinner dependency, modal, nested card, icon-only status, or interactive
  confirmation hidden in a CI run. Keep machine stdout parseable.

## Review Checks

Capture successful, counterexample, incomplete, stale, unavailable, and empty
outputs at 80 columns and redirected to files. Confirm `NO_COLOR=1`, readable
line wrapping, non-TTY behavior, bounded trace disclosure, and JSON/text semantic
agreement. A recipient must identify scope and next action without opening raw
checker logs. These are WP-FM-4/WP-FM-5 acceptance checks, not completed tests.

## Completion And Evidence Claims

FM-8 through FM-11 reuse this reading order but show the actual observations for
the selected claim; do not label a semantic evaluator run as a model check. Keep
obligation identity, expected outcome, evidence validity, established meaning,
authority and acceptance disposition distinct. Display missing/conflicting
evidence before optional detail. No scalar confidence score or aggregate badge
may hide an unresolved required obligation.

Illustrative output only; machine fields and exact states are frozen with owners
at FM-7, not introduced by this document:

```text
Claim: completion.obligation_sufficiency.v1
Obligation: required successful verification
Evidence identity: valid for the current candidate
Expected outcome: all admitted required checks succeeded
Established outcome: unknown; required observations missing
Authority: existing policy and admitted evaluator; no new approval
Disposition: required criterion not established
Recovery: run the approved profile for the missing observations
```

An actual result must name its evaluator, evidence reference and executable
recovery when available. Unknown provenance stays unknown. Untrusted annotation
text is labeled diagnostic and cannot supply the authority line, selected checks
or displayed acceptance state. Human/JSON parity tests compare these meanings;
two-run authority checks may disregard only harmless prose/occurrence differences.

Capture BDD-FM-8 through BDD-FM-13 at 80 columns, without color or a TTY, and with
bounded/redacted diagnostics. The recipient must identify what is missing, who
can establish it and what action is authorized. These are future FM-11 evidence
requirements, not a live interface or completed usability result.