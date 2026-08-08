# UX Spec: Mutation Quality

## Jobs To Be Done

When I change production behavior, I want Fettle to show which behavioral
changes my tests would miss, so I can strengthen the tests before merging
without waiting for a repository-wide mutation run.

When I maintain a repository, I want mutation quality to improve from an
honest baseline without allowing regressions, so a target score cannot be met
by hiding tool failures, silently excluding mutants, or inherited weak tests.

## Personas Affected

- New user: needs one documented command, useful defaults, and an explanation
  when no baseline exists.
- Power user: needs changed-scope runs, JSON evidence, exact survivor reruns,
  and deterministic CI comparison.
- Accessible user: consumes plain terminal text or structured JSON; status is
  always expressed in words and exit codes, never by color alone.

## User Journey

| Phase | User action | Sees | Desired feeling | Failure prevented |
|---|---|---|---|---|
| Configure | Enables `[mutation]` and validates config | Effective paths, test mappings, limits, and policy | Confident | Silent inert configuration |
| Develop | Runs `fettle mutation run --changed` or opens a PR | Progress followed by killed and surviving changes | Informed | Coverage mistaken for assertion quality |
| Repair | Opens a survivor and runs its rerun command | File, line, mutation, tests, and expected next action | In control | Opaque mutant IDs |
| Decide | Adds an assertion or records a temporary override | New survivor removed or explicitly waived | Accountable | Permanent unreviewed suppression |
| Maintain | Reviews scheduled full evidence | Baseline, current score, delta, runtime, and debt | Oriented | Arbitrary threshold resets |

## Primary Flow

1. Run `fettle mutation run --changed`.
2. Fettle resolves the merge base, changed implementation scope, mapped tests,
   engine identity, and applicable baseline before execution.
3. Fettle prints a bounded summary: status, score, killed and non-killed
   outcomes, new survivors, existing survivors, and evidence path.
4. For each new survivor, Fettle prints file, line, mutation summary, tests
   executed, and a one-mutant rerun command.
5. The developer strengthens an assertion and reruns the command.
6. CI enforces evidence integrity immediately; survivor policy remains advisory
   until its graduation criteria are met.

Interaction budget: one command for the common path and one rerun command per
survivor. An experienced developer should understand the result within 30
seconds, excluding mutation execution time.

## Output States

- First-time empty: `not_configured`, with the minimal `[mutation]` example and
  no claim that tests passed.
- Cleared empty: `completed` with zero new survivors and explicit scored-mutant
  counts; zero generated mutants remains `unknown`, not success.
- Filtered empty: requested path has no changed implementation files;
  `not_applicable` names the merge base and filters used.
- Loading brief: terminal shows scope discovery and engine validation.
- Loading long: periodic shard/module progress includes elapsed time and the
  current bounded deadline; CI exposes active workers.
- Populated: summary plus new, existing, waived, timeout, suspicious, and
  untested groups.
- Error recoverable: missing tool, unmapped tests, timeout, or malformed
  evidence identifies the failed stage and prints a rerun or configuration
  action.
- Error fatal: incompatible evidence schema, revision, engine, or scope returns
  `unknown` or `tool_error`, exit code 2, and cannot be overridden into a pass.
- Offline: local changed-scope execution remains available; remote baseline
  retrieval is not required because the accepted baseline is repository data.
- Stale: a baseline whose source scope, watched input, or execution identity
  differs is marked incompatible and must be re-established through measured
  calibration.

## Information Architecture

- Entry point: `fettle mutation`.
- Common action: `fettle mutation run --changed`.
- Full evidence: `fettle mutation run --all`, with CI-only shard options kept
  under advanced help.
- Inspection: `fettle mutation status` and `fettle mutation show <fingerprint>`.
- Baseline lifecycle: `fettle mutation baseline establish|check`.
- Configuration: top-level `[mutation]`, because this is an asynchronous
  evidence lane rather than an editor or Stop hook.
- Persistent accepted evidence: `.fettle/mutation-baseline.json`.
- Full raw reports remain CI artifacts and are not committed.

## Accessibility

- Text labels accompany every status and count.
- Human output remains readable without ANSI color and supports `NO_COLOR`.
- JSON contains the same decisions, recovery actions, and evidence references
  as human output.
- Output is line-oriented, has stable headings, and does not animate or rewrite
  prior terminal lines when output is not a TTY.

## Progressive Disclosure

Default output shows status, score, delta, counts, new survivors, and next
action. `--verbose` shows complete existing-survivor and execution-scope data.
Raw engine output and full survivor records live in the retained JSON artifact.

## Policy Semantics

- Evidence integrity is never advisory: missing, malformed, incomplete,
  overlapping, stale, or tool-error evidence cannot pass.
- The repository score is always reported honestly. Overrides never increase
  it and baseline survivors remain visible.
- Initial survivor reporting is advisory. `max_new_actionable_survivors = 0`
  becomes enforceable only after reviewer feedback demonstrates acceptable
  actionability and runtime; no universal score threshold is implied.
- A changed-scope score is a secondary signal and is enforced only when the
  configured minimum mutant count avoids a volatile tiny denominator.
- Mutant timeouts, suspicious outcomes, and untested mutants are separate
  visible debt classes. Untested has a default zero budget; mutant timeout and
  suspicious budgets remain report-only until explicitly calibrated and
  configured. A worker/orchestration timeout is an evidence error, not a score
  outcome. Untested mutants are never accepted as valid completed scope.
- Reviewed equivalent/unproductive classifications require canonical identity,
  owner, evidence, scope, and expiry. They suppress policy disposition and
  duplicate review noise only; raw survivor counts and score remain unchanged.
- Review output defaults to one actionable mutant per line and seven per file;
  retained JSON remains complete.
- An override is revision-bound, scoped to one canonical mutant fingerprint,
  owned, reasoned, and expiring. It waives the merge decision only; it does not
  relabel or remove the survivor.

## UAT Scenarios

### Scenario: Strong changed-code tests

Given a compatible accepted baseline and changed production code
When all meaningful changed-scope mutants are killed
Then Fettle reports no new survivors, retains complete JSON evidence, and exits
successfully.

### Scenario: Coverage theater

Given ordinary tests execute a changed branch but assert the wrong behavior
When mutation removes or reverses that branch
Then Fettle reports a new survivor with location, mutation, mapped tests, and a
single-mutant rerun command.

### Scenario: Existing mutation debt

Given the accepted baseline contains existing survivors
When a PR introduces no new survivor
Then Fettle reports both the unchanged debt and zero new survivors without
blocking solely because the global target has not yet been reached.

### Scenario: New survivor under enforcement

Given changed-survivor policy has graduated to enforce
When a PR introduces one non-waived survivor
Then Fettle exits nonzero and explains that the developer must strengthen the
test or provide an applicable override.

### Scenario: Reviewed equivalent-mutant classification

Given a reviewer demonstrates that one survivor cannot alter observable behavior
When an unexpired reviewed classification matches its canonical identity,
policy scope, owner, and evidence
Then Fettle labels it non-actionable for policy but leaves it in the raw
survivor count and score, and invalidates the classification when identity or
policy changes.

### Scenario: Broken evidence

Given a worker times out, mutmut changes output grammar, a shard is omitted, or
execution uses a different revision
When Fettle evaluates the report
Then it returns `tool_error` or `unknown`, score `null`, and exit code 2.

### Scenario: Baseline establishment

Given independently executed complete full reports from one revision satisfy
the configured measured calibration contract
When a maintainer runs `fettle mutation baseline establish`
Then Fettle writes one canonical baseline containing report identities, score,
counts, scope digest, survivor fingerprints, and maximum runtime.

### Scenario: Baseline manipulation

Given reports differ in revision, engine, test mapping, source ranges, outcome
counts, or survivor fingerprints
When baseline establishment is attempted
Then Fettle refuses to write or update the baseline.

### Scenario: Engine IDs change across equivalent runs

Given two complete reports describe the same canonical mutants with different
run-local mutmut IDs
When Fettle compares them and a developer requests one survivor
Then comparison uses canonical fingerprints, and the printed rerun command uses
only the selected report's current engine ID and reruns exactly that mutant.

### Scenario: Partial unknown identity

Given one changed-scope non-killed mutant lacks enough canonical detail while
the other records are valid
When changed-survivor policy is evaluated
Then Fettle renders the known diagnostics but returns `unknown` and cannot pass
enforcement or establish a baseline.

### Scenario: Classification evidence becomes stale

Given an equivalent-mutant record matched an earlier source-context digest
When enclosing behavior or its evidence-tool identity changes
Then the raw survivor remains unchanged, the classification no longer suppresses
policy disposition, and Fettle requests renewed review evidence.

## UX Success Criteria

- Every non-killed changed mutant has a file, line, classification, and rerun
  action, or the report is not eligible for enforcement.
- Tool and evidence errors are distinguishable from test-quality violations.
- The common changed-scope command requires no shard knowledge.
- No accepted result depends on GitHub's advisory job color.
- Seeded weak assertions are detected in both human and JSON output.
- Reviewer feedback distinguishes actionable findings from equivalent or
  unproductive mutants before survivor policy can graduate.
