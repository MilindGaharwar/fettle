# UX Spec: Work-Item Lifecycle Integrity

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/lifecycle.md).

Status: PROPOSED planning contract; no parser, CLI, hook, CI, release, migration,
or enforcement implementation is authorized

Related: [implementation plan](work-item-lifecycle-integrity-plan.md),
[completion UX contract](completion-evidence.ux-spec.md), and
[existing hypothesis tree](completion-lifecycle-hypothesis-tree.md)

## Jobs To Be Done

When I maintain or review Fettle work, I want contradictory lifecycle records to
fail with an exact explanation before protected merge or release, so an `open`
item cannot silently carry final closure and a `done` item cannot outrun its
required evidence.

When validation fails, I want the item, conflicting fields, source locations, and
manual recovery choices, so I can correct the authoritative record without an
automatic tool guessing which claim is true.

## Personas

- Maintainer: needs one bounded command that validates every work item and names
  the smallest safe correction.
- Coding agent: needs stable JSON fields, exit codes, and explicit authority
  boundaries rather than interpreting Markdown prose.
- Reviewer: needs the historical contradiction and every migration disposition
  preserved for independent comparison.
- Release owner: needs lifecycle and criterion-level completion validation to
  remain separate, required checks.

## Authority Contract

- Work-item `status` is the sole persistent delivery state.
- New v2 records use `open` or `done`. Runtime ownership remains solely in the
  shared `claims.json`; it never changes delivery state.
- `closure: final` is a declarative consistency marker, not evidence and not a
  second completion verdict. `done` requires it; `open` forbids it.
- For v2 `done` items, the existing completion evaluator remains the sole
  criterion-level evidence authority. Lifecycle validation reuses its result and
  does not reinterpret evidence.
- Legacy v1 records remain readable and must satisfy basic lifecycle consistency;
  no historical completion manifest is fabricated.
- Authorization, implementation delivery, evidence qualification, research
  graduation, promotion, Assurance, and ephemeral claim ownership remain
  distinct concepts.
- Markdown headings and prose, including `## Resolution`, never determine state.
  The legacy `done`-without-Resolution warning is removed rather than made
  authoritative.
- Contradictions block and name manual recovery choices. Validation never
  automatically changes status, closure, prose, or evidence.

## User Journey

| Phase | User action | Sees | Recovery or boundary |
|---|---|---|---|
| Author | Creates or edits a work item | Supported lifecycle and closure fields | New v2 records cannot author persistent `claimed` |
| Validate | Runs `fettle work validate` | Valid result or exact structured findings | Fix the named field or evidence; no auto-fix |
| Complete | Marks bounded work delivered | Final closure marker plus existing v2 completion result | Wider program graduation remains separate |
| Reopen | Returns delivered work to active state | `open` with no active final marker | Historical prose and manifests remain records, not current closure |
| Commit | Runs installed pre-commit checks | Fast full-repository lifecycle feedback | Hooks are convenience controls and may be bypassed |
| Merge | Opens or updates a protected change | Required lifecycle and completion jobs | Merge prevention is claimed only with verified branch protection |
| Release | Starts the governed release path | Lifecycle and completion validation before build | Invalid state stops release before artifact creation |

## Primary Flow And Budget

1. Edit the structured work-item record.
2. Run `fettle work validate`.
3. If invalid, inspect the rule, item ID, exact field locations, and recovery.
4. Correct the record manually.
5. Run lifecycle and completion validation.
6. Submit the change to required CI.

- Common path: one validation command and no more than one recovery cycle.
- Human and JSON output derive from the same finding set.
- Validation scans the full repository; changed-only success cannot establish
  repository consistency.
- The command is local, offline, deterministic, and non-interactive.

## Required States

- Clean: all records satisfy lifecycle consistency; exit 0.
- Open: no active final closure marker; partial implementation may be described as
  progress without changing delivery state.
- Done: final closure marker is present; v2 criterion evidence also passes the
  existing completion evaluator.
- Legacy claimed: readable only during migration, clearly identified, and invalid
  for newly authored v2 records.
- Malformed: invalid front matter, duplicate keys, unsupported values, or unsafe
  identity fields produce a blocking error.
- Contradiction: status, closure, identity, or applicable completion result
  disagree; output names each conflicting location.
- Logical identity conflict: multiple records claim one canonical milestone or an
  alias/supersession target is missing or cyclic.
- Completion non-pass: existing v2 completion validation is missing, stale,
  malformed, incomplete, or contradictory; lifecycle output reports that result
  without recomputing it.
- External protection unknown: repository workflows are valid, but host branch or
  release protection cannot be verified; no merge-prevention claim is made.

## Output Contract

Human and JSON findings expose the same bounded fields:

- rule and severity;
- item ID and lifecycle state;
- source file and exact line;
- closure state and exact line when present;
- conflicting item, file, and line when applicable;
- completion result reference for a v2 evidence non-pass;
- plain-language message and manual recovery.

No result claims that local hooks cannot be bypassed. A protected-merge guarantee
requires evidence that the host requires the named aggregate CI check.

## Accessibility

- Every state and severity is expressed in text, not color.
- Human output is concise, line-oriented, and usable with a screen reader.
- JSON contains stable fields rather than terminal formatting.
- Recovery commands are copyable and require no interactive input.
- Multiple findings use deterministic item, rule, file, and line ordering.

## BDD Scenarios

### Scenario: Historical P46 contradiction is blocked

Given a work item is `open` and carries the structured final closure marker
When repository lifecycle validation runs
Then validation exits nonzero
And names both the status and closure locations
And offers manual choices to remove final closure or establish valid completion
And does not choose either repair automatically.

### Scenario: Clean open work remains valid

Given a v2 work item is `open` with no final closure marker
When lifecycle validation runs
Then the item is valid regardless of non-authoritative progress prose
And no completion claim is inferred from a `## Resolution` heading.

### Scenario: Valid legacy completion remains readable

Given a legacy v1 item is `done` with final closure
When lifecycle validation runs
Then basic lifecycle consistency passes
And no historical v2 completion manifest is fabricated or required.

### Scenario: Valid v2 completion uses the existing evaluator

Given a v2 item is `done` with final closure and a same-ID complete manifest
When lifecycle validation runs
Then it reuses the existing completion evaluator's result
And does not independently reinterpret criterion evidence.

### Scenario: Missing or stale v2 evidence stays non-pass

Given a v2 item is `done` with final closure
And its completion evidence is missing, stale, malformed, or incomplete
When lifecycle validation runs
Then the lifecycle result is non-pass with the existing completion reason
And final closure cannot override that evidence result.

### Scenario: Partial delivery does not become done

Given an open P77-style item describes delivered infrastructure and unmet human
graduation criteria in prose
When lifecycle validation runs
Then the item remains open
And prose does not create final closure or broader program graduation.

### Scenario: Resolution placeholder has no authority

Given an open legacy item contains a placeholder `## Resolution` heading
When lifecycle validation runs
Then the heading alone does not create final closure
And migration may correct the prose only through a separately accepted editorial
disposition.

### Scenario: Persistent claimed state cannot hide runtime ownership

Given a legacy record says `claimed` but `claims.json` has no live owner
When lifecycle validation runs during migration
Then it identifies the legacy state and recovery
And does not invent a runtime claim.

### Scenario: Logical aliases cannot create two authorities

Given two records declare the same canonical milestone or an alias cycle
When lifecycle validation runs
Then validation exits nonzero with both records and exact identity fields
And naming similarity alone is never used to merge them.

### Scenario: Direct edits cannot bypass the repository boundary

Given a contributor directly edits a work item into a P46-style contradiction
And all unrelated unit tests pass
When the blocking lifecycle CI job runs
Then the required aggregate remains non-pass.

### Scenario: Release checks run before build

Given the repository contains a lifecycle contradiction
When the governed release workflow starts
Then lifecycle and completion validation fail in preflight
And no distribution artifact is built from that state.

### Scenario: External protection is not assumed

Given repository workflows contain the lifecycle job
But authenticated branch-protection evidence is unavailable
When enforcement status is reported
Then workflow enforcement is verified
And protected-merge enforcement is `UNKNOWN`.

## Success Criteria

- The historical P46 contradiction is a permanent failing regression fixture.
- Every supported state, closure, version, identity, and applicable manifest
  combination has a deterministic validity, exit, and recovery result.
- The live corpus passes without a baseline or permanent suppression after an
  independently reviewed migration.
- Lifecycle validation never creates a second criterion-evidence decision.
- Required CI and release preflight invoke lifecycle and completion validation.
- Human and JSON findings agree and identify exact conflict locations.
- No automatic repair can convert ambiguous evidence into completion.
