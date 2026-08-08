# Mutation Quality Implementation Plan

Status: approved for implementation on 2026-08-08.

Related UX contract: [mutation-quality.ux-spec.md](mutation-quality.ux-spec.md)

## Outcome

Productize Fettle's fail-closed Python mutation prototype as a portable
developer workflow, then dogfood exactly that workflow on Fettle. The feature
must improve assertion quality without blocking development on inherited debt,
hiding survivors, or treating infrastructure failure as a test-quality result.

## User Story

As a developer, I want Fettle to block newly introduced behavioral gaps and
show me how to reproduce each one, so tests prove behavior rather than merely
execute code.

As a maintainer, I want an immutable full-run baseline and a monotonic ratchet,
so repository mutation quality improves toward a policy target without score
resets or permanent silent exceptions.

## Current Evidence

- The wrapper pins mutmut 2.5.1, validates engine output, distinguishes
  `unknown` and `tool_error`, and rejects zero-mutant success.
- Changed and full selection use explicit Git scope and retained JSON evidence.
- Full aggregation proves revision identity and exact, non-overlapping source
  line coverage.
- A monolithic full run exceeded 7,200 seconds. Test selection alone did not
  solve runtime. File-size balancing also failed.
- Module-local mapped tests, test-cost-weighted line chunks, and bounded shards
  are required for Fettle's repository size.
- Run `31243192196` completed 237 of 240 reports; three adjacent
  `fettle/quality_scan.py` ranges timed out. The aggregate correctly rejected
  the run. The completed reports indicated an unaccepted diagnostic score near
  44.4 percent with zero untested leakage.
- Revision `e3706df` splits the measured hotspot into 20-line chunks. Full run
  [`31246843926`](https://github.com/MilindGaharwar/fettle/actions/runs/31246843926)
  completed all 240 shards and its aggregate on that revision. It covered all
  154 production modules and 30,441 source lines exactly once, with zero
  untested mutants, in 1,792,060 ms wall time. Its conservative diagnostic
  score was 43.3 percent: 11,363 killed, 13,227 survived, 734 timed out, and
  931 suspicious. This is the first complete full-run datum, not yet an
  accepted baseline.

## Decision

Build a dedicated mutation evidence lane, not a synchronous dispatcher hook.

The policy has three independent decisions:

1. **Evidence integrity:** enforce immediately and fail closed.
2. **Changed-code quality:** graduate `no new actionable survivors` only after
   advisory reviewer feedback demonstrates that reported mutants are useful.
3. **Repository quality:** ratchet an accepted full score upward; do not impose
   the aspirational target on inherited code on day one.

No universal 80 or 90 percent threshold is supported by the reviewed evidence.
Fettle may adopt 80 percent as its own aspirational destination after
calibration, but generic defaults do not claim it as an industry standard.
Critical paths use explicit path and mutator profiles plus zero actionable
survivors, not an arbitrary higher percentage.

## Alternatives Considered

### Put mutation under `fettle check`

Rejected for execution. Mutation work is minutes to hours and would violate
hook and PR latency budgets. `fettle check` may later consume a fresh retained
mutation verdict, but must not launch mutation execution.

### Enforce a global 70-80 percent threshold immediately

Rejected. Fettle's preliminary full evidence is near 44 percent. Immediate
enforcement would stop unrelated work or reward gaming. A ratchet plus strict
changed-code policy creates pressure in the correct place.

### Grandfather survivor IDs as suppressions

Rejected. Engine IDs are not stable semantic identities, and suppressing old
survivors hides debt. The baseline stores canonical fingerprints only to label
`existing` versus `new`; all survivors remain visible and count against score.

### Reuse `.fettle-baseline.json` or `.fettle/ratchet.json`

Rejected. The former fingerprints scanner findings and the latter promotes
rules from fire/false-positive telemetry. Mutation evidence has different
revision, engine, scope, outcome, and stability invariants. It needs a dedicated
strict schema while reusing the canonical override ledger for temporary merge
waivers.

## Configuration Contract

Add a top-level configuration with conservative defaults:

```toml
[mutation]
enabled = false
mode = "advisory"                 # advisory | enforce
engine = "mutmut"
paths = ["src/"]
exclude = ["tests/", "migrations/"]
base = "origin/main"
timeout_s = 600
full_timeout_s = 1800
score_target = 80.0               # optional repository aspiration
minimum_scored_mutants = 10
max_new_actionable_survivors = 0
max_untested = 0
max_findings_per_line = 1
max_findings_per_file = 7
default_chunk_lines = 60

# Optional after advisory calibration:
# max_mutant_timeouts = 10
# max_suspicious_mutants = 10
# full_shards = 48

[mutation.test_mappings]
"src/shared.py" = ["tests/test_shared.py"]

[mutation.chunk_lines]
"src/expensive_module.py" = 20
```

`test_mappings` supplements convention and static-import discovery. An empty
mapping remains an error. `chunk_lines` is measured operational configuration,
not source-code policy. Optional timeout and suspicious budgets are report-only
when absent and must be calibrated before enforcement. `full_shards` defaults
to one because no repository-independent shard count is defensible; maintainers
increase it from measured worker runtime. Fettle's `.fettle.toml` will contain
its current shared test mappings, `fettle/` paths, 240 full shards, and the
measured `fettle/quality_scan.py = 20` override; no Fettle path remains
hard-coded in production Python.

The schema must reject invalid modes, targets outside 0-100, negative outcome
budgets, non-positive execution timeouts/chunk sizes/shard counts, an enforce
mode with mutation disabled, and an enforce mode without compatible accepted
evidence or explicit mutant-timeout and suspicious budgets. Configuring a budget
is the machine-readable enforcement transition; its reviewed calibration
evidence remains in the accepted baseline.

## Evidence Contracts

### Canonical mutant fingerprint

Do not compare mutmut numeric IDs across runs. Derive a versioned SHA-256
fingerprint from the canonical repository-relative file, enclosing symbol or
structural AST path/occurrence anchor, mutation operator, normalized original
expression, and normalized replacement. Source line is location metadata, not
identity, so unrelated inserted lines do not create a new mutant. Retain the
engine ID only as a run-local rerun locator.

If mutmut cannot provide enough detail to construct that identity, Fettle must
mark comparison evidence `unknown`; it must not fall back to file and line only.
Fingerprints must be unique within one report. An unresolved duplicate or hash
collision makes the affected comparison `unknown` and makes the report
ineligible for enforcement or baseline establishment.

### Full report

Extend schema version 2 with:

- policy digest and source-scope digest;
- complete survivor records, not the current 20-ID truncation;
- canonical fingerprint, file, line, operator, before/after summary, mapped
  tests, and rerun command for every non-killed mutant;
- a bounded `survivor_preview` for terminal output;
- shard manifest identity and timing per module/range;
- explicit comparison decision separate from raw mutation outcome.

Reports expose raw counts without relabeling. The primary mutation score uses
decided mutants (`killed / (killed + survived)`); skipped, timed-out,
suspicious, and untested outcomes are reported separately. Untested has a
default zero budget; mutant timeout and suspicious budgets are optional and
report-only until calibrated. A worker or orchestration timeout is an
evidence-integrity failure and never becomes a mutant outcome. An aggregate
with untested mutants or a breached configured outcome budget is ineligible for
baseline establishment.

### Accepted baseline

Store `.fettle/mutation-baseline.json` in the repository. It contains:

- schema version and creation timestamp;
- calibration run IDs and report digests;
- tested revision, engine and runner identity;
- policy, source-scope, test-mapping, and line-range digests;
- exact counts and score;
- complete survivor fingerprints;
- maximum wall duration and total worker duration;
- current floor and aspirational target.

Creation requires independently executed complete full reports for the same
revision. Calibration records identity match, per-mutant outcome agreement,
runtime distribution, and invalidation inputs; Fettle initially requires two
exactly matching reports and runs another only to diagnose a mismatch, never to
outvote it. The requirement may change only from measured stability data.
Baseline updates may keep or increase the floor. Lowering the floor requires a
canonical active override scoped to `mutation.baseline`, and still cannot alter
the raw score.

### Incremental evidence

Incremental reuse is an optimization, not an authority shortcut. Cache identity
includes mutated source, covering tests, test mapping, mutation and test-runner
configuration, dependency lockfiles, installed-distribution names, versions,
direct-URL metadata, and installed `RECORD` hashes where available. Editable or
otherwise unhashed distributions use their canonical source-root content digest
instead of a nonexistent wheel hash. Identity also includes watched
fixtures/configuration, engine, Python, and platform. A changed or unknown input
reruns the affected mutants; an input that cannot be mapped invalidates the
whole cache. Scheduled full runs bypass reuse and measure cache correctness by
comparison.

### Equivalent and unproductive mutants

Reviewer feedback classifies a mutant as actionable, equivalent, or
unproductive. Equivalent or unproductive classifications require canonical
identity, owner, reason, evidence, review expiry, and exact policy scope in a
reviewed repository ledger. Evidence is typed as a reproducible behavioral
rationale, static proof with tool identity, or linked test/oracle, and is signed
against the mutant's enclosing-source context digest. They suppress only merge
disposition and duplicate review noise: the raw survivor remains visible and
the raw score is unchanged. A source-context, identity, evidence-tool, or policy
change invalidates the classification.

### Changed-scope comparison

For a pull request, compare canonical non-killed fingerprints within the
changed source scope:

- `new`: absent from the accepted baseline and not killed now;
- `existing`: present in the accepted baseline and still observable;
- `resolved`: present in the baseline scope but killed or removed now;
- `non_actionable`: matched by a valid reviewed equivalent/unproductive record;
- `waived`: new but matched by an active revision-bound override;
- `unknown`: insufficient identity or incompatible evidence.

The enforcement decision is based on non-waived new actionable survivors and
explicit outcome budgets. Non-actionable and waived mutants remain survivors in
raw counts and score. PR presentation is bounded to one actionable mutant per
line and seven per file by default; complete evidence remains in JSON.
Any non-killed mutant with unknown identity makes changed-scope enforcement
fail closed; known records may still be rendered for diagnosis.

## Command Contract

Expose the existing module through the main CLI:

```text
fettle mutation run --changed [--json] [--output PATH]
fettle mutation run --all [advanced shard options]
fettle mutation status [--report PATH] [--json]
fettle mutation show FINGERPRINT
fettle mutation baseline check REPORT...
fettle mutation baseline establish REPORT... --run-id ID [--run-id ID ...]
```

Exit codes remain consistent with Fettle:

- 0: completed and policy passed, or genuinely not applicable;
- 1: trustworthy evidence found a quality-policy violation;
- 2: configuration, tool, identity, orchestration timeout, or evidence-integrity
  failure.

## Work Packages

Each checklist item is intentionally small and independently verifiable. Tests
are named before implementation files to preserve the repository's TDD policy.

### WP1: Freeze Current Provenance

- [x] Audit run `31246843926`; its accepted aggregate completed all 240 shards,
  covered 154 modules and 30,441 lines exactly once, and has zero untested
  mutants.
- [x] Update the P34 status in `docs/fettle-evolution-implementation-plan.md`
  and `docs/ROADMAP.md`; verify run IDs and conclusions against retained JSON,
  not GitHub job color.
- [x] Preserve report `31246843926` as diagnostic provenance only; do not claim
  cross-run calibration or block later work on another run. Executable
  calibration occurs only in WP7, after schema-v2 canonical evidence exists.

### WP2: General Configuration

- [x] Add failing defaults/schema assertions in `tests/test_config_schema.py`
  for `[mutation]`, open mapping tables, modes, and numeric boundaries.
- [x] Add the disabled advisory defaults to `fettle/config.py`; run the focused
  schema tests.
- [x] Add `mutation.test_mappings` and `mutation.chunk_lines` to
  `OPEN_DICT_PATHS` in `fettle/config_schema.py`; verify unknown nested project
  paths are accepted but unknown fixed keys warn.
- [x] Add mode, range, and dependency rules in `fettle/config_schema.py`; verify
  invalid timeout, target, budget, shard, enforce-without-enable, and enforce
  without both explicit mutant-timeout and suspicious budgets cases fail.
- [x] Add policy-evaluation boundary tests for absent, zero, exact-limit, and one-over-limit
  timeout/suspicious budgets; absence reports debt in advisory mode, while an
  explicit calibrated budget controls policy in enforce mode.
- [x] Regenerate `docs/fettle.schema.json`; run its drift test.
- [x] Move `_SHARED_TESTS`, `_SHARD_LINES_BY_FILE`, paths, exclusions, and
  execution bounds from `fettle/mutation_test.py` into effective config; verify
  Fettle's existing assignment remains exact.
- [ ] Remove path, timeout, and shard-count literals from the workflow through
  the validated dynamic prepare job specified in WP6.
- [x] Add Fettle's dogfood values to `.fettle.toml`; run
  `fettle config --validate` and inspect `--print-effective`.

### WP3: Canonical Mutant Evidence

- [x] Add fixture cache/output data with two mutants on one line, line movement,
  and different transformations in `tests/fixtures/mutation/`.
- [x] Add failing tests in `tests/test_mutation_test.py` proving numeric IDs do
  not define cross-run identity and canonical details do.
- [x] Implement versioned content/structure-based fingerprinting in
  `fettle/mutation_test.py`; verify path separators, ordering, Unicode
  normalization, and unrelated line insertions are deterministic.
- [x] Add collision tests for repeated equivalent syntax, duplicate canonical
  records, and a forced digest collision; unresolved identity is `unknown` and
  cannot establish or compare a baseline.
- [x] Add tests for malformed, missing, duplicate, oversized, and unknown
  mutation details; every case must return `unknown`, not a guessed identity.
- [x] Collect full non-killed mutant details from the pinned engine into report
  schema v2; verify terminal previews remain bounded while JSON is complete.
- [x] Add one-mutant rerun commands and mapped tests to each record; execute a
  fixture rerun, parse the engine result, and verify exactly one current engine
  ID executes with the same resulting outcome as the selected report record.
- [x] Change numeric engine IDs between equivalent fixture reports and verify
  canonical comparison is unchanged; a missing, stale, or invalid current
  engine ID must refuse the rerun with exit code 2 rather than target another
  mutant.
- [x] Add schema-v1 rejection or explicit read-only migration behavior; do not
  silently compare v1 IDs with v2 fingerprints.

### WP4: Baseline And Comparison

- [ ] Add baseline fixture reports and failing calibration tests in
  `tests/test_mutation_baseline.py` for all identity, scope, count, fingerprint,
  runtime, and zero-untested invariants.
- [x] Create `fettle/mutation_baseline.py` with strict load, validate, establish,
  and atomic-write functions; verify malformed existing files are never
  overwritten.
- [ ] Add comparison tests for new, existing, resolved, waived, and unknown
  outcomes, including moved lines, two mutations on one line, and one unknown
  record among otherwise valid records; partial identity never yields a pass.
- [x] Implement comparison in `fettle/mutation_baseline.py`; verify overrides
  change only policy disposition, never outcome counts or score.
- [x] Add monotonic-floor tests: equal or higher accepted, lower refused without
  an exact active override.
- [x] Add atomic-write concurrency tests: simultaneous establish/update attempts
  use locking or compare-and-swap semantics, never overwrite newer accepted
  evidence, and never leave a parseable but mixed baseline.
- [x] Reuse `OverrideContext` and `select_override` from `fettle/overrides.py`
  with check ID `mutation.survivor`; verify expired, future, wrong-revision,
  wrong-policy, wrong-evidence, and wrong-surface records do not waive. Test the
  exact activation and expiry instants under the canonical UTC clock.
- [x] Add separate `mutation.baseline` authorization for floor reduction;
  verify a survivor override cannot authorize baseline changes.
- [ ] Add a strict reviewed equivalent/unproductive classification ledger with
  owner, typed evidence, source-context digest, expiry, and policy scope; verify
  stale source context, identity, evidence-tool identity, or policy cannot
  suppress disposition.
- [x] Validate each evidence variant independently: behavioral rationale needs
  reproducible steps and expected observation, static proof needs tool/version
  and retained result digest, and linked test/oracle needs a repository-relative
  target plus content digest. Reject missing fields, unknown types, external
  paths, digest mismatch, and malformed or oversized evidence.

### WP5: Developer CLI

- [x] Add CLI contract tests in `tests/test_cli.py` for all `fettle mutation`
  subcommands, JSON parity, and exit codes 0/1/2.
- [x] Add `cmd_mutation` and parsers in `fettle/cli.py`, delegating execution to
  existing mutation modules rather than duplicating logic.
- [ ] Add human-rendering tests for first-time, not-applicable, populated,
  violation, waived, stale, and tool-error states.
- [x] Render bounded summaries and actionable survivor sections in
  `fettle/mutation_test.py`; verify output without ANSI and under `NO_COLOR`.
- [x] Add atomic `--output` handling so interrupted execution cannot leave a
  report that appears valid.
- [ ] Run a clean fixture repository through the installed `fettle` executable,
  not a direct function call; verify weak assertions produce the documented UX.

### WP6: CI Productization

- [x] Add workflow contract tests in `tests/test_ci.py` proving PR mutation is
  changed-scope, bounded to 12 minutes, and always retains evidence.
- [x] Add a prepare job to `.github/workflows/mutation.yml` that validates
  config and emits the configured full-shard matrix; remove the literal
  Fettle-specific matrix from generic execution logic.
- [x] Make each worker consume one signed/digested partition manifest; verify a
  worker cannot silently recompute a different scope.
- [x] Make aggregate evidence integrity blocking even while score policy is
  advisory. Do not use `continue-on-error` on the validator that decides
  whether evidence is usable.
- [ ] Publish a concise GitHub job summary with status, delta, counts, new
  survivors, and artifact link; verify it never calls `tool_error` successful.
- [ ] Add changed-scope comparison against the committed baseline; preserve a
  maximum 12-minute PR lane and upload partial fail-closed evidence on timeout.
- [ ] Add minimum-scope tests below, at, and above
  `minimum_scored_mutants`; tiny scopes still enforce new actionable survivors
  while suppressing only the volatile changed-scope score decision.
- [x] Add cache reuse tests covering source, covering-test, mapping, dependency,
  fixture/configuration, engine, Python, and platform invalidation; unknown
  dependencies force execution rather than reuse.
- [x] Exercise installed wheel and editable dependencies separately: changed
  version, `RECORD`, direct URL, or editable source digest invalidates reuse;
  missing or unreadable identity fails closed instead of trusting lockfile-only
  equivalence.
- [x] Limit PR findings to one actionable mutant per line and seven per file by
  default while retaining complete machine-readable evidence.
- [x] Keep full runs scheduled/manual; verify full mutation is not added to the
  normal blocking CI critical path and periodically bypasses incremental reuse.

### WP7: Fettle Dogfood Graduation

- [ ] After schema-v2 canonical evidence exists, dispatch two independent full
  reports for one revision. Compare identities, outcomes, scope, invalidation
  inputs, and runtime; use another run only to diagnose a mismatch, never to
  outvote it.
- [ ] If a run is invalid, record the exact module/range duration in
  `docs/hypothesis-tree.md`; adjust only measured chunk configuration and rerun.
- [ ] Establish `.fettle/mutation-baseline.json` only after the measured
  calibration contract accepts independent full reports on one commit; review
  the generated diff before commit.
- [ ] Run changed-scope mutation advisory on at least ten representative Fettle
  PRs or seeded PR fixtures; record runtime, new survivors, equivalent-mutant
  claims, and tool errors.
- [ ] Require zero evidence-integrity false passes and zero unmapped production
  modules throughout the advisory window.
- [ ] Seed weak assertion, removed branch, reversed comparison, timeout,
  malformed cache, and equivalent-mutant scenarios under
  `tests/fixtures/verification/`; run them independently in CI.
- [ ] Promote `max_new_actionable_survivors = 0` to enforce only when at least
  95 percent of changed runs finish within 12 minutes, reviewer feedback exists
  for at least 100 surfaced mutants, and the confirmed non-actionable rate is
  at most 5 percent.
- [ ] Keep the repository floor at the accepted score; increase it only after a
  completed independent calibration pair proves the higher score under the
  accepted reproducibility contract.
- [ ] If maintainers adopt Fettle's local 80 percent aspiration, raise the floor
  only in small reviewed increments. Use targeted path/mutator profiles for
  security, policy, persistence, concurrency, and release code rather than a
  claimed 90 percent standard.
- [ ] Require a canonical override for any temporary regression or new survivor;
  verify expired overrides fail the next applicable run.

### WP8: Documentation And Release

- [ ] Add installation and configuration guidance to `README.md` and
  `CONTRIBUTING.md`; verify every copied command runs in a temporary project.
- [ ] Document engine support as Python/mutmut only; do not imply polyglot
  mutation support from Fettle's language adapters.
- [ ] Update `CHANGELOG.md` and `docs/ROADMAP.md` only after the dogfood
  graduation criteria pass.
- [ ] Archive this plan after implementation and retain the run IDs and baseline
  digest as provenance.

## Blast Radius

Primary files:

- `fettle/mutation_test.py`: engine, report, partition, and rendering changes.
- `fettle/mutation_baseline.py`: new strict baseline/comparison module.
- `fettle/config.py`, `fettle/config_schema.py`, `docs/fettle.schema.json`:
  public configuration contract.
- `fettle/cli.py`: developer entry points and exit semantics.
- `fettle/overrides.py`: reused unchanged if its exact matching contract is
  sufficient; any schema extension would affect all enforcing decisions and
  requires separate review.
- `.github/workflows/mutation.yml`: evidence authority and latency/cost.
- `.fettle.toml`, `.fettle/mutation-baseline.json`: Fettle dogfood policy and
  accepted evidence.
- `tests/test_mutation_test.py`, `tests/test_mutation_baseline.py`,
  `tests/test_config_schema.py`, `tests/test_cli.py`, `tests/test_ci.py`:
  integrity and user contracts.

Secondary risks:

- Config schema drift blocks commits by design.
- CLI changes touch a large command router; delegation must remain narrow.
- Mutmut cache internals are version-specific; the engine stays pinned and
  parser drift fails closed.
- Dynamic CI matrices can exceed provider limits; validation must cap shards at
  GitHub's matrix maximum and report a configuration error.
- Full survivor evidence may be large; artifacts retain complete data while
  terminal and job summaries remain bounded.

Before implementation, refresh `kgraph index` and run positional
`kgraph impact` for each primary Python file. Its result is best-effort and does
not replace tests for subprocess, SQLite, workflow, or Git behavior.

## Success Criteria

Functional:

- Independent complete full runs establish one baseline only when the measured
  calibration contract passes; any unexplained mismatch refuses establishment.
- Changed code with a seeded weak assertion produces a canonical new survivor.
- Strengthening the assertion changes that mutant to killed.
- A baseline survivor remains visible and continues to lower the honest score.
- A waiver changes only the merge disposition and expires correctly.
- Missing tools, parser drift, orchestration timeout, zero mutants, unmapped
  tests, untested mutants, missing shards, overlap, stale revision, or stale
  policy cannot pass. Mutant timeouts remain separate visible outcomes subject
  to an explicit budget.
- Fettle's 154 production modules remain mapped and every production source
  line is covered exactly once in a full run.

Operational:

- At least 95 percent of Fettle changed-scope runs complete within 12 minutes.
- Every full worker completes within 35 minutes.
- Full mutation remains outside normal blocking PR critical path.
- Full reports are reproducible for the same revision and execution identity.
- Fettle scan, Ruff, actionlint, focused tests, full tests, and seeded mutation
  verification all pass before release.

Product:

- A developer can identify and rerun a survivor without inspecting SQLite or
  knowing a shard ID.
- JSON and human output reach the same decision and recovery action.
- No GitHub green advisory status is presented as accepted mutation evidence.
- The floor never decreases without a recorded, active, exact override.

## Rollback And Stop Conditions

- Do not enforce survivor policy if the advisory false-positive rate exceeds 5
  percent, fewer than 100 findings have reviewer feedback, or changed-run
  completion falls below 95 percent within 12 minutes.
- Revert policy to advisory, not evidence integrity, if developer throughput is
  harmed. Tool and evidence failures remain non-pass.
- Stop and redesign canonical identity if equivalent runs or unrelated line
  movement produce different fingerprints; do not add fuzzy matching.
- Stop increasing the floor if teams respond by deleting valuable assertions,
  excluding meaningful source, broadening skips, or writing implementation-
  coupled tests solely to kill mutants.
- Do not add another mutation engine until Python/mutmut dogfooding graduates
  and a second language has measured demand plus equivalent evidence contracts.

## Assumptions

- Python/mutmut is the first supported engine; the contract is designed for an
  engine adapter later, but no abstraction is added until a second engine is
  approved.
- Accepted baselines are committed repository artifacts and reviewed like
  policy changes.
- GitHub Actions remains Fettle's dogfood CI, but report and baseline contracts
  are provider-neutral.
- The current canonical override ledger remains revision-bound for temporary
  merge waivers. Reviewed equivalent/unproductive classifications are separate,
  expiring policy records and never alter raw outcomes or score.
- `docs/ROADMAP.md` and `CHANGELOG.md` serve as feature tracking; this repository
  has no separate feature manifest.

## External Evidence

- [Google: Mutation Testing](https://testing.googleblog.com/2021/04/mutation-testing.html)
  supports changed covered-line execution, minimum covering tests, reviewer
  feedback, productive-mutant filtering, and bounded review output.
- [Practical Mutation Testing at Scale](https://arxiv.org/abs/2102.11378)
  reports industrial evidence for incremental changed-code mutation and
  context-based filtering, not universal score thresholds.
- [PIT incremental analysis](https://pitest.org/quickstart/incremental_analysis/)
  documents both reuse opportunities and dependency-invalidation uncertainty.
- [Stryker incremental mode](https://stryker-mutator.io/docs/stryker-js/incremental/)
  documents test/source reuse and explicit environment/configuration blind
  spots; scheduled forced runs therefore remain necessary.
- [Stryker equivalent mutants](https://stryker-mutator.io/docs/mutation-testing-elements/equivalent-mutants/)
  confirms that equivalent mutants cannot be eliminated generally and that a
  100 percent target is unsafe.
- [Infection usage](https://infection.github.io/guide/usage.html) separates
  timeout budgets from optional score treatment and supports controlled source
  exclusions.
- [mutmut documentation](https://mutmut.readthedocs.io/en/latest/) supports
  incremental execution and explicitly watches dependency/configuration inputs,
  reinforcing fail-closed invalidation.

## Compliance Gate

- Phase 0 UX: complete in `docs/mutation-quality.ux-spec.md`.
- Phase 0.5 UI: not applicable; this is a CLI/CI evidence feature with no visual
  interface. Terminal accessibility and output states are specified in UX.
- Phase 1 plan: complete in this document.
- Phase 3.5 UAT: Given/When/Then scenarios are defined in the UX specification
  before implementation.
- Feature manifest: not applicable; Fettle uses `docs/ROADMAP.md` and
  `CHANGELOG.md`.
- Implementation authorization: approved by the user on 2026-08-08.
