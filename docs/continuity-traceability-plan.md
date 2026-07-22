# Continuity and Work-Item Traceability Execution Plan

**Status:** Proposed
**Owners:** Disciplines (continuity behavior), Fettle (audit correlation)
**Reviewed by:** Claude Opus 4.6 (approve with changes; corrections incorporated)
**Estimated effort:** 13-18 hours plus a 2-week advisory pilot

## 1. User Story

As an engineer or coding agent resuming non-trivial work, I want a short,
current record of the objective, investigation, decisions, evidence, blockers,
and next action so that I can continue without repeating failed work or relying
on a previous session's context.

## 2. Scope Boundary

This feature is split across two existing systems:

| Concern | Owner | Artifact |
|---|---|---|
| When and how to maintain continuity | Disciplines | `discipline-continuity` skill |
| Whether the behavior changes agent output | Disciplines eval corpus | Behavioral scenarios |
| Correlating gate evidence with a work item | Fettle WP-128 | Optional trace field and audit digest |
| Evaluating end-to-end resumability | Fettle WP-133 | Resumption scenario after the pilot |

WP-F1 through WP-F3 deliver only the work-item correlation and session-audit
subset of roadmap WP-128, which remains scheduled for Fettle v1.0. Full
PR-level aggregation and the broader enterprise attribution contract remain in
WP-128 unless separately planned. WP-133's runner already exists; this plan
adds scenarios to its corpus rather than reimplementing the runner.

Fettle will not become a note store. The implementation will not add a graph
database, Obsidian or Dataview integration, GitHub synchronization, daily-note
generation, or a worklog CLI.

Personal notes remain outside both repositories. Issues and plans remain the
source of truth for requested outcomes. Worklogs contain temporary execution
state. Accepted architectural decisions belong in ADRs; repeatable operational
procedures belong in runbooks.

## 3. Assumptions

1. A continuity artifact is useful only for work likely to cross a context or
   ownership boundary; routine single-session edits must not incur this cost.
2. Markdown is sufficient for the pilot and remains readable without special
   tooling.
3. Work-item identifiers are opaque correlation strings, not necessarily
   GitHub issue numbers.
4. Fettle trace data is local and potentially sensitive. Correlation must not
   copy issue titles, prompts, command text, or worklog prose into trace events.
5. Existing trace readers tolerate additional JSON fields.
6. The current eval runner can check files and transcripts but cannot measure
   comprehension time. The two-minute handoff target therefore requires a
   manual pilot protocol until a suitable measurement seam exists.
7. At planning time, `git status` reports an existing modification to
   `skills/discipline-shipping/SKILL.md` in Disciplines and an untracked
   `integrations/vscode/package-lock.json` in Fettle. They are unrelated and
   must remain untouched.

## 4. Alternatives Considered

### A. Add a worklog gate and CLI to Fettle

Rejected. Fettle detects and records quality evidence; it should not own prose
or force note creation. There is no reliable hook signal for whether a worklog
is semantically needed, and mandatory note generation would create noise.

### B. Fold all guidance into planning, debugging, and shipping

Rejected for the pilot. Continuity spans planning, investigation, handoff, and
closure. Spreading the contract across several skills makes it difficult to
load, evaluate, and retire independently. Existing skills may link to the new
skill later, but must not duplicate its rules.

### C. Add `discipline-continuity` and keep Fettle correlation minimal

Selected. This preserves the existing boundary: process upstream in
Disciplines, deterministic evidence downstream in Fettle. The skill remains
independently measurable, while Fettle adds only machine-readable correlation
needed by the planned agent audit trail.

## 5. User Flow

1. The agent classifies work as continuity-relevant when any trigger applies:
   multi-session work, explicit handoff, incident response, non-trivial
   debugging, a high-risk change, or two rejected hypotheses.
2. The agent creates or updates one repository-local worklog associated with a
   stable work-item identifier.
3. At a meaningful checkpoint, the agent records only new evidence, decisions,
   blockers, and the next action. It does not reproduce ticket descriptions or
   raw CI output.
4. A new engineer or agent reads the worklog and continues from the stated next
   action.
5. At closure, durable information is promoted to an ADR, runbook, issue, or
   maintained documentation. Temporary investigation detail is summarized or
   removed according to repository policy.
6. If the repository activates a Fettle plan with a work-item identifier,
   Fettle attaches that opaque identifier to subsequent trace evidence and the
   WP-128 audit digest.

## 6. Continuity Artifact Contract

The skill will recommend a repository-selected location rather than impose a
global folder. If the repository has no convention, use
`docs/worklogs/<work-item-id>.md` during the pilot.

```markdown
---
work_item: GH-405
status: active
owner: milind
updated: 2026-07-22
---

# Objective
One outcome statement; link to the issue or plan instead of copying it.

# Current State
Facts a new person needs before acting.

# Investigation
## 2026-07-22T14:30Z
- Hypothesis:
- Action:
- Observation:
- Conclusion:

# Decisions
- Decision, rationale, and ADR link when architecturally significant.

# Evidence
- Command or artifact reference, outcome, and timestamp. No secrets or raw dumps.

# Blockers
- Blocker, owner, and required resolution.

# Next Action
- Exactly one concrete continuation action.
```

Required properties:

- One active artifact per work item per repository.
- UTC timestamps for investigation checkpoints.
- No credentials, personal data, full prompts, or unredacted command output.
- Links instead of duplicated issue descriptions and CI logs.
- `Next Action` contains exactly one executable continuation step.
- Status is one of `active`, `blocked`, or `closed`.

## 7. Work Packages

### WP-C1: Define the behavior and red evaluation (2-3 hours)

**Repository:** `~/.claude/plugins/disciplines`

1. Create an issue or design note proposing the new core skill, as required by
   `CONTRIBUTING.md`; verify the proposal names the generic use case and avoids
   personal or organization-specific conventions.
2. Add
   `evals/scenarios/continuity-handoff-creates-resumable-worklog/scenario.yaml`
   before the skill. Seed a repository with an issue summary, an incomplete
   implementation, two failed hypotheses, and test evidence. Prompt the agent
   to hand off the work.
3. Require the scenario to verify a worklog contains `Objective`, `Current
   State`, structured investigation evidence, `Blockers`, and exactly one `Next
   Action`; verify it does not copy a seeded secret-like token or the complete
   raw test log.
4. Run static validation and record that the live scenario fails or does not
   reliably satisfy the contract before adding the skill. An indeterminate run
   is not red evidence and must be reported separately.

**Verification:**

```bash
python3 ~/.claude/plugins/fettle/scripts/evals_runner.py validate --root evals/scenarios
FETTLE_EVAL_TIMEOUT_S=3600 python3 ~/.claude/plugins/fettle/scripts/evals_runner.py run evals/scenarios/continuity-handoff-creates-resumable-worklog
```

### WP-C2: Implement `discipline-continuity` (2-3 hours)

**Repository:** `~/.claude/plugins/disciplines`

1. Create `skills/discipline-continuity/SKILL.md` following the
   `writing-disciplines` structure contract and the 250-line limit.
2. Put trigger-rich routing in frontmatter: multi-session work, handoffs,
   incidents, non-trivial debugging, high-risk work, and two rejected
   hypotheses. Explicitly exclude routine single-session edits and personal
   journaling.
3. Define checkable rules for artifact selection, checkpoint updates,
   investigation structure, secret minimization, one-next-action handoff, and
   closure promotion.
4. Add anti-patterns for chronological activity dumps, duplicated tracker
   content, raw logs, stale `Current State`, multiple ambiguous next actions,
   and treating a worklog as an ADR.
5. Add a `## Cross-Cutting Skills` section immediately after the phase map in
   `skills/using-disciplines/SKILL.md`. List `discipline-continuity` in a small
   trigger table without assigning a numbered SDLC phase; do not duplicate its
   rules in planning, research, or shipping.
6. Update `README.md`, `CHANGELOG.md`, and plugin metadata where skill inventory
   or version changes require it.
7. Re-run the behavioral scenario. A pass must show the complete artifact and
   no seeded sensitive content. Record model, CLI version, timeout, verdict,
   and limitations in `evals/BASELINE.md`.

**Verification:**

```bash
python3 ~/.claude/plugins/fettle/scripts/evals_runner.py validate --root evals/scenarios
FETTLE_EVAL_TIMEOUT_S=3600 python3 ~/.claude/plugins/fettle/scripts/evals_runner.py run evals/scenarios/continuity-handoff-creates-resumable-worklog
```

### WP-C3: Pilot continuity behavior without enforcement (2 weeks elapsed)

**Repositories:** At least two representative projects; no Fettle code change

1. Select 5-10 qualifying work items, including debugging, multi-session
   implementation, and one explicit human-to-agent or agent-to-agent handoff.
2. Measure checkpoint update effort manually from start to finish. Target:
   median at or below one minute.
3. Give each handoff to a fresh session with only the repository and worklog.
   Ask it to state the objective, current state, last rejected hypothesis,
   blocker, and next action before editing. Target: all five facts correct and
   first relevant action started within two minutes.
4. Record duplication, stale-state, sensitive-data, and unnecessary-worklog
   incidents. Do not count an item as successful merely because a file exists.
5. Continue only if at least 80% of handoffs satisfy all five facts, no secret
   exposure occurs, and users judge the update burden acceptable.

**Rollback:** Remove the skill from `using-disciplines` routing if it creates
routine-work noise or fewer than 80% of qualified handoffs are resumable. Keep
the scenario and pilot report as evidence of the rejected approach.

### WP-F1: Specify privacy-safe work-item correlation in WP-128 (1-2 hours)

**Repository:** `~/.claude/plugins/fettle`

1. Expand WP-128 in `docs/ROADMAP.md` with the correlation contract before
   implementation.
2. Define `work_item_id` as optional, opaque, trimmed, and capped at 128 ASCII
   characters. Reject control characters and path separators. Do not resolve
   remote tracker content.
3. Define source precedence for the first release:
   `.fettle/state/active-plan.json` field `work_item_id`, then absent. Do not
   infer IDs from branch names, commit messages, issue URLs, prompts, or command
   text.
4. Define missing or malformed metadata as `unknown`, never a gate failure.
5. Document that traces contain identifiers only, not worklog prose or issue
   titles, and remain governed by existing local retention and gitignore rules.

**Verification:** Semantic review confirms the roadmap, config/state model, and
privacy statement describe the same precedence and failure behavior.

### WP-F2: Add correlation metadata at the trace seam (3-4 hours)

**Repository:** `~/.claude/plugins/fettle`

1. Write failing unit tests in `tests/test_trace.py` for valid, missing,
   malformed, oversized, and legacy active-plan markers.
2. Add a small resolver in `scripts/trace.py` or a single-purpose sibling module
   that reads `<cwd>/.fettle/state/active-plan.json` safely, enforces the WP-F1
   constraints, and returns `None` on any error.
3. Extend `log_decision()` with optional `cwd` and `work_item_id` keyword-only
   inputs. Explicit input takes precedence over resolver output. Existing call
   sites remain valid and old JSONL remains readable.
4. Add `work_item_id` only when valid; do not emit an empty field. Preserve
   fail-open behavior if the marker cannot be read.
5. Update the active-plan command contract so new activations may record a
   user-supplied work-item identifier. Specifically, change the JSON template
   written by step 5 of `commands/plan-activate.md` to include
   `"work_item_id": "<VALIDATED_ID>"` only when supplied; retain the legacy
   three-field JSON when absent. Keep this as command behavior rather than
   adding a helper until a reproduced quoting or portability failure justifies
   code. Test both marker shapes through the resolver's roundtrip fixtures. Do
   not require an identifier and do not change plan gating behavior.
6. Audit every `log_decision()` caller before editing. Update callers that
   already receive repository context: `post_edit.py`, `post_edit_ts.py`,
   `ux_spec_gate.py`, and `ui_colors_gate.py`. Inspect `autofix.py`,
   `fp_stamp.py`, and any newly discovered callers; leave them unchanged when
   they cannot provide an authoritative `cwd` rather than deriving one from a
   file path or process directory. Record the resulting coverage limitation in
   the audit documentation. Do not alter the generic hook-event schema solely
   for this feature.
7. Add tests proving explicit `work_item_id` takes precedence over marker
   resolution and that callers without `cwd` remain backward compatible.
8. Add a regression test proving trace output contains no plan body, issue
   title, command text, or marker fields other than the validated identifier.

**Verification:**

```bash
pytest tests/test_trace.py tests/test_report.py -q
ruff check scripts/trace.py tests/test_trace.py
```

### WP-F3: Build the WP-128 audit digest (3-4 hours)

**Repository:** `~/.claude/plugins/fettle`

1. Write failing tests for grouping mixed trace events by `session_id` and
   `work_item_id`, including old events without either field and malformed
   JSONL lines.
2. Add a dedicated audit report module rather than overloading the existing
   effectiveness metrics in `scripts/report.py`.
3. Produce a deterministic JSON representation containing schema version,
   generated timestamp, work-item ID or `unknown`, session IDs, attempted
   tools/checks available in trace, blocks, advisories, ignored/repeated
   findings when determinable, and evidence references.
4. Produce a concise Markdown view from the same data model. Label unavailable
   facts as `unknown`; never infer that missing evidence passed.
5. Add a command surface under the existing Fettle CLI or `/fettle:report`
   command only after the report module is independently tested. Support
   filtering by exact work-item ID and session ID.
6. Cap input size and output records using existing trace limits. Skip malformed
   lines with a visible degraded-data count.
7. Update `docs/CONFIG.md`, `README.md`, and `CHANGELOG.md` with privacy,
   retention, and backward-compatibility behavior.

First-release audit coverage is intentionally limited to decision events in
the global XDG trace written by `scripts/trace.py`. Project-local finding,
metric, and gate-error entries written by `post_edit.py` are excluded. The
report must label this limitation and must not claim a complete activity or
finding history. Unifying the two trace streams requires a separate schema and
migration decision under the remaining WP-128 scope.

**Verification:**

```bash
pytest tests/test_agent_audit.py tests/test_trace.py -q
python3 scripts/agent_audit.py --work-item GH-405 --json
```

The live command must report a defined state even when no matching records
exist; it must not crash or claim a pass.

### WP-E1: End-to-end resumption evaluation (2 hours after pilot)

**Repositories:** Disciplines scenario corpus and Fettle WP-133 runner

1. Add a second scenario that seeds a completed handoff artifact and asks a
   fresh agent to continue a bounded implementation.
2. Check that the agent first identifies the expected next action and then
   changes only the intended file while avoiding a seeded rejected approach.
3. Keep wall-clock timing in the manual pilot protocol. Do not add a special
   timing check type until there is evidence that automated timing is stable
   across models and environments.
4. Run the scenario with and without `discipline-continuity` in isolated
   workdirs. Treat this as comparative evidence, not a claim of causality from
   a single run.
5. Record all pass, fail, and indeterminate outcomes. Require at least three
   determinate runs per condition before updating routing or enforcement.

**Verification:** Static scenario validation plus recorded live-run results in
the appropriate baseline file.

## 8. Blast Radius

### Disciplines

- Session bootstrap context grows when `using-disciplines` adds the new skill.
- Routing ambiguity may cause the skill to load on routine work.
- New behavior must coexist with `discipline-research` for multi-session
  hypothesis trees without creating two competing logs.
- Existing shipping-skill modifications are out of scope and must not be
  overwritten.

### Fettle

- `scripts/trace.py` has multiple callers and shares state conventions with
  health telemetry, ratchet, CLI explain, and reports.
- Two trace shapes currently coexist: decision events from `trace.py` and
  project-local finding/metric entries from `post_edit.py`. WP-F1 must decide
  explicitly which streams WP-128 consumes before implementation. This plan's
  first release consumes only the global decision trace and labels that
  limitation; it must not silently claim complete audit coverage.
- Active-plan marker changes affect plan activation and completion commands but
  must not alter whether editing is allowed.
- Audit output can expose activity metadata; identifier validation, local-only
  defaults, bounded output, and no prose ingestion are required.

## 9. Security and Privacy Review

- Treat worklogs and traces as sensitive engineering metadata.
- Never ingest credentials, environment values, full prompts, raw shell
  history, or unrestricted tool output into worklogs or audit reports.
- Validate identifiers before writing them to JSONL or using them as filters.
- Never use a work-item identifier as a file path.
- Use exact equality for filtering; do not evaluate identifiers as regex.
- Preserve fail-open hooks, but surface degraded audit data visibly.
- Keep network access out of trace resolution and report generation.

## 10. Success Criteria

### Automated

- All Disciplines scenarios statically validate.
- Continuity artifact scenario passes with all required sections and no seeded
  sensitive content.
- Existing Fettle trace consumers accept old and enriched entries.
- Invalid active-plan metadata produces no `work_item_id` and no hook failure.
- Audit grouping is deterministic and reports malformed/skipped records.
- Full test suites and Fettle quality scans pass in both repositories.

### Pilot

- At least 80% of qualified handoffs recover all five required facts.
- Median checkpoint update time is at or below one minute.
- A fresh session starts the correct next action within two minutes in at least
  80% of determinate trials.
- Zero secrets or personal data are captured.
- Fewer than 20% of worklogs substantially duplicate issue or CI content.
- Routine single-session work receives no continuity requirement.

## 11. Release and Rollback

1. Release `discipline-continuity` as an advisory methodology addition first.
2. Complete the two-week pilot before Fettle correlation implementation is
   promoted beyond an experimental roadmap item.
3. Ship trace correlation as optional metadata with no enforcement behavior.
4. Ship WP-128 reporting only after old-trace and malformed-data tests pass.
5. Do not introduce a blocking continuity gate in this plan.

Rollback is additive and low-risk:

- Remove continuity routing from `using-disciplines`; retain artifacts and eval
  results for learning.
- Stop writing `work_item_id`; existing readers ignore the absent field.
- Disable or remove the audit command without changing stored trace entries.
- Never delete user worklogs automatically.

## 12. Execution Order

```text
WP-C1 red scenario
  -> WP-C2 discipline-continuity
  -> WP-C3 two-week pilot
       -> decision gate
          -> WP-F1 correlation specification
          -> WP-F2 trace metadata
          -> WP-F3 audit digest
          -> WP-E1 end-to-end comparative evaluation
```

No Fettle implementation begins until the pilot decision gate passes. This
prevents building audit infrastructure for a continuity practice that users do
not maintain or that fails to improve resumability.

## 13. Opus Review Disposition

Claude Opus 4.6 reviewed this plan on 2026-07-22 and returned **approve with
changes**. Incorporated findings: executable active-plan marker behavior,
explicit `log_decision()` call-site audit, partial-WP-128 scope, global-trace
coverage limitation, and exact cross-cutting skill placement. One finding was
not incorporated: Opus reported that
`skills/discipline-shipping/SKILL.md` did not exist, but direct file inspection
and `git status` confirmed that it exists and has a pre-existing modification.

## 14. Compliance Gate

- Phase 0 UX: Not applicable; no end-user interface.
- Phase 0.5 UI: Not applicable; no visual design.
- Phase 1 plan: This document.
- Phase 3 behavioral acceptance: BDD scenarios below and WP-C1/WP-E1 evals.
- Feature manifest: Disciplines README/CHANGELOG and Fettle ROADMAP/CHANGELOG are
  updated in their respective work packages.

### Acceptance Scenarios

```gherkin
Scenario: A qualifying task is handed to a fresh session
  Given a work item has two rejected hypotheses and unfinished implementation
  When the current agent prepares a handoff
  Then one continuity artifact states the objective, current state, evidence,
       blocker, and exactly one next action
  And it does not copy secrets or complete raw logs

Scenario: Routine work does not create documentation tax
  Given a low-risk edit will finish in one session
  When the agent applies continuity routing
  Then no worklog is required

Scenario: Fettle correlates evidence without ingesting prose
  Given an active plan contains a valid work_item_id
  When Fettle records a trace decision
  Then the trace includes only the validated identifier as correlation metadata
  And no plan body, issue title, prompt, or command text is copied

Scenario: Correlation metadata is malformed
  Given an active plan contains an oversized or unsafe work_item_id
  When Fettle records a trace decision
  Then the event is recorded without work_item_id
  And the quality hook remains available

Scenario: An audit reads historical traces
  Given trace data contains enriched, legacy, and malformed records
  When the audit digest is generated
  Then valid records are grouped deterministically
  And legacy records are labeled unknown
  And malformed records are counted as degraded data rather than silently passed
```
