Historical: superseded on 2026-10-26 by the PR advisory path; retained as evidence.

# Final Acceptance Contract and Closure Proposal

## 2026-10-22 readiness-repair outcome and dispatch decision

The owner approved completeness-based advisory acceptance for **execution integrity
only**. A diagnostic execution is complete only when every required canonical
fingerprint has one valid terminal outcome and exact identity, environment, clean
baseline, restoration, retention, and evidence validation pass. Missing, malformed,
incompatible, contradictory, stale, or indeterminate evidence is non-pass. Execution
completeness is not mutation-policy acceptance: no survivor is waived, no test-strength
threshold is approved, and full qualification remains `CLOSED_NON_PASS`.

The scoped repair started from signed head `1e4213aad608fca7bbac02df14db420bbb852b13`
and preserved the 2026-10-21 planning edits. It changes tests and documentation only:

- `tests/test_installed_artifact_canary.py` now proves the exact interpreter,
  `-m`, and `fettle.dispatcher` command shape and rejects the retained
  `021e07ea4299c8b8e62fefc460828ee1d2f78af035d3d7d7f3934a0933ab0900`
  mutation (`'-m'` to `'XX-mXX'`) plus malformed, extra-argument, wrong-module,
  and wrong-interpreter commands;
- `tests/test_uat_benchmark.py` now proves both operands of the retained
  `0e26705938892df6af5fd802fbe2c51285fd12da9947692c78e59e6f14cdefeb`
  mutation (`complete and false_verdicts == 0` to `complete or …`): matching but
  incomplete evidence and complete but mismatching evidence both remain non-pass;
- `tests/test_quality_scan.py` now supplies one requested and one off-target
  finding and asserts the requested-file outcome. This behavioral oracle covers
  `12aeccd25f18e735950ea5fe951eba375f85e2da79e9b5c50b04eb5ae0d6fef7`,
  `a7f907e22e7e446906d81ef4afe049a52987d155b5f17010155560c9f4411747`,
  and `affdd4cb46ba0c47c9ac8f4c9cc6bb7c7704003bb67073cd41affe290fbd0546`
  without asserting private intermediate implementation state.

No production defect was demonstrated and no production code changed. A new shared
baseline gate was not justified: before replay, the exact existing mapped commands
were run against clean source and all passed while importing checkout modules. The
existing executor continues to let mutmut classify mutation-induced collection or
import failures; it does not add a blanket nonzero-exit-to-killed rule.

### Verification and review

- exact mapped baselines: canary 15/15, benchmark 19/19, and combined
  assurance/CI/scanner 181/181 passed under CPython 3.12.13 and pytest 9.1.1;
- focused repair suite: 66 passed;
- full suite: 4,983 passed and 20 skipped in 637.33 seconds;
- Ruff and the 426-file Fettle scan passed; completion checkpoint validation passed;
- `git diff --check` passed;
- repository-wide `actionlint` retained one pre-existing SC2155 warning at
  `.github/workflows/release.yml:50`, outside this test-only scope.

Independent preliminary review raised no reproducible defect in the assertions after
reconciliation. Its canary concern contradicted the retained exact definition
(`'XX-mXX'` is exact); its benchmark concern overlooked that the two cases exercise
the two OR-danger boundaries; and splitting the scanner test would couple assertions
to private intermediates rather than strengthen the external result. The review's
valid timing/accounting concern is the dispatch blocker below.

### Seven-fingerprint replay: blocked before execution

Execution was identified as **provider execution** because the authorized limits are
runner-minute ceilings and retained readback is required. No provider run started and
no approved minutes were consumed. The existing `.github/workflows/mutation.yml`
`replay` route cannot represent this authorization:

1. it derives replay shards from hard-coded historical line ranges, not an exact
   canonical-fingerprint allowlist;
2. it executes every pending fingerprint in each selected whole shard, so it cannot
   guarantee exactly these seven fingerprints or one attempt each;
3. it uses a matrix with configurable parallelism rather than mandatory sequential
   execution;
4. it requires a successful same-commit 256-shard retained preflight, which would
   require the expressly forbidden full enumeration; and
5. it exposes neither separate 30-worker/10-support-readback ceilings nor a 60-minute
   overall containment deadline with an early restoration reserve.

Using that route would violate the frozen scope and accounting contract. The required
stop condition therefore fired before dispatch. The historical killed controls
`08975ae51c0ca010b851493975b33ee53a37ef706ff13f4feb2bb6506012c911`
and `2cfa4d6fe64956741bd48a5148212e73a657f2e70d43b3e130252be0105658f9`
remain diagnostic controls only; no outcome transfers. All seven replay outcomes are
unmeasured for the repair candidate.

### Full-qualification decision boundary

The final delivered repair commit, once signed and pushed, is the replay candidate;
its literal SHA and exact-head CI run are delivery evidence and replace `1e4213a…`.
Historical evidence remains useful only for definitions, killed-control expectations,
runtime planning, and regression fixtures. It supplies no current outcome credit.

Remaining workload is not just seven fingerprints: the prior campaign left 380/869
assigned fingerprints pending or unmeasured, while the repair candidate's complete
current corpus and survivor population are unknown without fresh enumeration. Known
risk clusters include installed-artifact canary, UAT benchmark, scanner scope, and
the incomplete staged-preflight unit; they must not be extrapolated to each other or
to the whole corpus.

A future full dispatch requires all of the following:

1. separately authorized infrastructure that accepts an exact canonical-fingerprint
   allowlist, proves membership after fresh local-ID resolution, runs sequentially,
   enforces separate worker/support/readback accounting and early containment, and
   retains baseline, restoration, terminal outcomes, and checksummed readback;
2. a successful seven-fingerprint replay through that route under a new exact
   candidate and environment, with disagreements investigated but not retried;
3. a fresh exact-candidate full preflight with zero rejected details/collisions,
   complete current mappings and source digests, and all 256 manifests;
4. full coverage of every current canonical fingerprint, using sequential independent
   authoritative calibrations and continuation only within one exact calibration ID
   and completely equal candidate/runtime/dependency/policy/manifest/corpus identity;
5. no missing, skipped, untested, timed-out, suspicious, conflicting, stale, or
   indeterminate required outcome; exact source byte/mode restoration after every
   attempt; and independently checksummed retention/readback; and
6. separate reporting of execution completeness and advisory mutation debt. Full
   acceptance requires a later owner decision; it cannot be inferred from completeness.

No full resource ceiling is authorized. For decision planning only, the obsolete
45,432-mutant estimate was about 8,100 runner-minutes with ±25% uncertainty
(approximately 6,075--10,125), and 6--10 elapsed hours assumed 8/16/32 concurrency
with no shard timeout. Source growth, heterogeneous mappings, queue delay, and the
unit-7 censoring make that range non-authoritative. Fresh preflight topology and the
blocked narrow replay must be measured before proposing a new ceiling. Seven results
must not be used to claim full-corpus feasibility.

## 2026-10-21 mutation-readiness addendum

Status: **repair proposal only; no repair, replay, provider dispatch, qualification,
merge, tag, or release is authorized**.

This addendum supersedes this document's 2026-10-07 candidate and cost assumptions
where they conflict. The verified delivery head is
`1e4213aad608fca7bbac02df14db420bbb852b13`; the measured diagnostic source was
`65e63d953b45d3672c24df74d0a1364b83a0157b`. Keep these intervening identities
distinct:

| Identity | Role; qualification consequence |
|---|---|
| `d342de4…` | OpenCode v2 candidate. AH00--AH07 closure is retained for this candidate only; it is not mutation qualification. |
| `2347767…` | Capacity-recovery package controller. It changed mutation execution and workflow behavior. |
| `2921b47…` | Linux diagnostic execution controller. It repaired campaign identity flow. |
| `1e4213a…` | Maintenance delivery head. It only made hook Python setup deterministic, but it remains the source identity a new run must bind. |

Campaign `39592379015` is terminal and `CLOSED_NON_PASS`: 489 of 869 assigned
fingerprints reached terminal outcomes, 380 remained pending or unmeasured, units
0--6 completed, unit 7 was incomplete, and units 8--11 did not start. Readback
`39595844326` intentionally failed closed. Its ten minutes remain
`conservative_ceiling_charged`; the campaign's 42 worker, two support, nine monitor,
and ten readback minutes are non-transferable. Neither run may be resumed, refilled,
or reinterpreted. The historical 12,000 runner-minute ceiling is expired authority.

### Effective contract before execution

`.fettle.toml` enables mutation over `fettle/`, uses mutmut 2.5.1, a 600-second
changed-run timeout, a 1,800-second full timeout, 256 full shards, and
`python -m pytest -x --assert=plain {mapped_tests}`. Its mutation mode is
`advisory`. `evaluate_policy()` therefore reports survivor limits and score as debt,
but still fails malformed or incomplete required evidence. No current decision
ratifies a numeric qualification score. The committed 49.1 baseline is bound to
`9eef2fa…`, not this head. It and its survivor set cannot transfer.

The rebuilt corpus labels generated mutants `survived` because enumeration used the
deliberate `python -c pass` runner. Those labels are enumeration metadata, not test
outcomes. Canonical fingerprints are authoritative; mutmut numeric IDs are only
run-local locators.

### Read-only findings and classification

The exact mapped commands collect cleanly at `1e4213a…`: eight canary tests, the UAT
benchmark test module, and the combined assurance/CI/quality-scan set. Imports of
`fettle.installed_artifact_canary`, `fettle.uat.benchmark`, and
`fettle.quality_scan` resolve to this checkout. This rules out a current static
collection or checkout-import error for these commands. It does not prove per-mutant
execution.

| Fingerprint | Finding | Classification and proposed disposition |
|---|---|---|
| `021e07ea…` | Canary `_command_binds_python`: `'-m'` → `'XX-mXX'` | **Test gap.** Existing canary tests stub transport probing and never assert accepted and rejected command shapes. Add a direct table test; no production change proposed. |
| `0e267059…` | Benchmark `_score_controller_reports`: `complete and false_verdicts == 0` → `complete or …` | **Test gap.** Add valid-but-incomplete and complete-with-mismatch cases proving both `expected_states_matched` and `calibration_passed` stay false. No production change proposed. |
| `12aeccd…` | Scanner explicit target set → `None` | **Test gap.** Retained as survived in four calibrations. Current explicit-file test yields no normalized in-scope finding, so target-set use is not observed. |
| `a7f907e…` | Scanner in-scope predicate inverted | **Test gap.** Retained as survived in four calibrations for the same missing mixed-finding oracle. |
| `affdd4c…` | Scanner finding key `'file'` changed | **Test gap.** Retained as survived in four calibrations; no non-empty explicit-file finding reaches this lookup. |
| `08975ae…` | Scanner ignore predicate inverted | **Killed control, not an unresolved survivor.** Four retained checkpoints killed it (78.787--113.540 seconds). Keep the existing ignore regression. |
| `2cfa4d6…` | Scanner filtered finding list → `None` | **Killed control, not an unresolved survivor.** Four retained checkpoints killed it (4.047--4.749 seconds). Keep it as a replay control. |

Do not generalize these records to either whole cluster. The two selected canary and
benchmark fingerprints have enumeration records but no retained executed outcome.
No reviewed-equivalent waiver or production defect is established. The waiver file
remains empty.

The execution adapter accepts mutmut's documented bit-mask outcomes and reconstructs
state from `mutmut results`; it does not independently identify why pytest returned
nonzero. A pre-existing mapped-test collection/import failure could therefore make
mutants look killed. The clean read-only collections reduce that risk at this head,
but a future executable package must add an exact pre-mutation baseline gate. A
mutation-induced syntax/import/collection failure is a valid kill only after that
same mapped command has passed against restored unmutated source.

### Unit 7 cost evidence

Unit 7 covered `fettle/staged_preflight.py:181--240`, three mapped test files, and 158
fingerprints. Its 745-second job is not 745 seconds of mutant attempts: about four
seconds was external setup, 454.497 seconds belongs to completed attempts, and
266.892 seconds combines baseline/regeneration with censored work and cannot be split
further from retained evidence. The remaining interval is wrapper/teardown overhead.
This supports intrinsic mapped-command cost, but does not isolate collection,
regeneration, test, or mutation cost. It does not authorize concurrency or narrower
mappings as a remedy.

### Bounded repair package

Implement only after owner approval:

1. Add direct canary command-shape regressions in
   `tests/test_installed_artifact_canary.py` for exact interpreter, `-m`, module,
   malformed quoting, extra arguments, and a different interpreter.
2. Add benchmark regressions in `tests/test_uat_benchmark.py` for a valid partial
   controller corpus with zero false verdicts and a complete corpus containing a
   mismatch. Both acceptance booleans must remain fail closed.
3. Add one scanner regression in `tests/test_quality_scan.py` whose scanner result
   contains one requested-file finding and one off-target finding. Assert only the
   requested finding survives normalization. This single behavioral oracle targets
   the set construction, membership direction, and `'file'` lookup without changing
   scanner behavior.
4. Add a baseline validation seam in `fettle/mutation_test.py` before any canonical
   mutant execution: run each distinct exact mapped pytest command once against
   restored source; require exit 0, successful collection, and checkout-source import
   identity. Retain command, exit, bounded diagnostics, collection identity, source
   digest, and restoration digest. Missing, nonzero, stale, or conflicting baseline
   evidence is an execution error and cannot become a kill.
5. Add fixtures in `tests/test_mutation_test.py` proving pytest exit 0 admits mutation
   attempts, baseline exits 1--5 admit none, collection/import failure remains
   non-pass, mutated-source collection failure can be recorded as killed only after a
   matching clean baseline, and source bytes/mode are restored on every path.

Do not change scope, mappings, timeout, score calculation, advisory mode, survivor
limits, or completion criteria in this repair.

### Validation funnel and stop conditions

Use fixtures first, then baseline preflight, then narrow replay, then a separately
authorized held-out full run:

1. Run focused unit tests and the three exact mapped commands without mutation.
2. Run a fresh local preflight for the repaired exact SHA and require exact corpus,
   mapping, policy, dependency, environment, and source identities; zero rejected
   details and fingerprint collisions; clean restoration; and no cache reuse unless
   its complete compatibility identity matches.
3. Narrowly replay exactly the seven fingerprints in the table, sequentially, by
   canonical fingerprint. Require the five test-gap mutants and both killed controls
   to be killed, baseline evidence to pass, no untested/skipped/timeout/suspicious
   state, and exact source restoration after every attempt. A numeric mutmut ID may be
   used only after fresh fingerprint-to-ID resolution.
4. Stop immediately on baseline failure, fingerprint drift, incompatible cache,
   corpus mismatch, tool error, timeout, missing outcome, contradictory outcome,
   restoration mismatch, accounting breach, or any unexpected survivor. Retain the
   non-pass package; do not retry it into a pass.
5. Only after the narrow replay passes may an owner consider a fresh authoritative
   qualification. Run independent calibrations sequentially and never share terminal
   outcomes. Read back retained checksums independently before acceptance.

For planning only, the narrow package should receive a new ceiling of **30 worker
runner-minutes plus 10 support/readback runner-minutes**, with one worker at a time
and a **60-minute elapsed stop**. This is conservative relative to the retained five
scanner durations (9.3 runner-minutes at their observed maxima) and complete canary
and benchmark diagnostic units (6 and 9 charged minutes). It is a requested ceiling,
not authority, and unused minutes do not transfer. No full-qualification ceiling can
be responsibly proposed until fresh preflight and narrow-replay timings exist.

### Owner decisions required

Before any execution, the owner must select both:

1. **Acceptance rule.** Recommended: preserve effective advisory policy and define
   qualification as complete, compatible, determinate evidence with all required
   fingerprints accounted for; survivors remain explicit advisory debt and do not
   satisfy a numeric threshold. Alternative: ratify a numeric score/survivor rule in
   a separate policy decision before freezing the candidate. Do not infer one from
   49.1 or from prose.
2. **Resource authority.** Approve, reduce, or reject the proposed 30+10-minute narrow
   ceiling. Authorize any later full run separately after measured re-estimation.

Until both choices and the bounded repair are approved, mutation qualification stays
`CLOSED_NON_PASS`. Advisory reporting, AH00--AH07 closure, exact-head CI, completion
validation, and mutation qualification remain separate decisions.

Date: 2026-10-07

Status: **bounded implementation authorized and completed locally; mutation execution remains unauthorized**

## Decision

Do not calibrate `0fc41fdfee13e09f4bda3dc5eee177030882aa36` and do not treat
the current PR head `2752f01c426fc9a02f22b56ea37ce10f9b3dda25` as the final
candidate. The delivery target must be one future commit containing the complete
intended executable tree, including the bounded calibration-interface repair, the
supported `setup-uv` action upgrade, and resolution of the current required Windows
CI failure. Freeze that commit before generating a new preflight.

The final executable SHA is deliberately **unset** until those authorized changes
exist. Inventing a SHA now or qualifying `2752f01…` before changing its workflows
would recreate the moving-target problem. Let:

- `E` = the future frozen executable candidate SHA; and
- `H` = the final PR head after calibration and completion evidence is recorded.

`H` may differ from `E` only by an explicitly allowlisted evidence-only documentation
commit. A preimplemented finalization path must prove that restriction and exact
executable-tree equality before publishing the required `mutation evidence` result
on `H`. Any source, test, policy, dependency, action, or workflow change after `E`
invalidates applicability and requires a new candidate and preflight.

This is the recommended acceptance target because the current PR intentionally adds
executable behavior. Narrowing the PR back to `0fc41fd…` would discard existing work;
qualifying only `0fc41fd…` would leave the shipped module unqualified.

## Delta from retained evidence

Between retained candidate `0fc41fd…` and current head `2752f01…`, the repository
adds or changes 14 files, 3,777 insertions, and 16 deletions. The mutation-relevant
delta is:

| Area | Delta |
|---|---|
| Product package | New `fettle/staged_preflight.py`: 1,022 lines, about 977 nonblank/noncomment lines and 6,728 AST nodes; it is included in the distributed `fettle` package |
| Workflows | 512 added/3 removed lines in `.github/workflows/mutation.yml`; new 305-line aggregation-recovery and 466-line continuation workflows |
| Tests | 121 added/2 removed lines in `tests/test_ci.py`; new 703-line `tests/test_staged_preflight.py` |
| Policy/dependencies | `.fettle.toml` and `requirements-mutation.txt` are byte-identical to `0fc41fd…` |

The new module is about 2.4% of the prior Python source by nonblank/noncomment lines
and has a convention-mapped owner test, `tests/test_staged_preflight.py`. It is inside
the configured mutation path `fettle/`. The retained 45,432-mutant corpus therefore
cannot qualify it.

## What retained evidence remains usable

Recovery run `37560100974`, attempt 1, remains accepted for `0fc41fd…` only:

- artifact `mutation-preflight-aggregation-recovery-37560100974-1`;
- exactly 256 nested reports: 8 from run `37464324954`, 32 from
  `37476889333`, and 216 from `37550308775`, all attempt 1;
- exactly 256 `manifests/partition-*.json` files;
- corpus digest
  `155a02b863d6b440211e09eef8daf189098554ca5871c5a484e7b65a3b005be2`;
- aggregate SHA-256
  `dded4dfe0ba8fcb9a1eccd995d7e2e31b68215c3468884dc418dd8709699f173`;
- manifest-topology digest
  `f3280d619e47f23c3a961facdbebe3893ca24b90f655572bb2380ec0e41a7ccc`;
- plan identity CPython 3.12.14, dependency SHA-256
  `c00bd24f7b87c160202ad3b3b2f14f7521ea4e88582d032a7805a584f69e9d46`,
  and policy SHA-256
  `d8b332681d0e6607e9976d18ce50154eca69ed259885c440bcb0b3b8cdce5448`.

Its per-shard reports contain mutation results and manifest digests; candidate,
runtime, dependency, policy, run, attempt, and origin bindings are supplied by the
retained continuation plan and recovery record. The consumer must validate the whole
package, not a report in isolation.

Runs `37464324954`, `37476889333`, and `37550308775` remain permanently non-pass.
The recovery package remains useful as historical evidence, a regression fixture for
artifact parsing, and a resource-estimation baseline. It is **not** reusable as the
preflight corpus or execution checkpoint for `E`: revision, source corpus, and chosen
runtime differ. No old terminal calibration outcome may be imported.

## Runtime identity

Use **CPython 3.12.13** for the fresh preflight and calibration of `E`. This preserves
the established hardening runtime identity. Pin the patch version in every active
qualification job; do not use the floating string `3.12`.

The repository's compatibility envelope includes `platform.python_version()` in the
environment digest and requires exact identity equality for cache/checkpoint reuse.
Consequently, 3.12.13 and 3.12.14 are neither assumed compatible nor declared
universally incompatible: they are different identities, so retained execution
checkpoints cannot cross between them. The old 3.12.14 preflight remains valid for
its old candidate and provenance, while the 3.12.13 final-candidate run starts clean.

Before fan-out, a clean GitHub-hosted fixture must prove that exact CPython 3.12.13,
the hash-locked mutation dependencies, mutmut 2.5.1, and the candidate install all
resolve. A different patch version is a failed setup gate, not an automatic fallback.

## Frozen requirement list

The governing AH07 criterion is `docs/audit-hardening-implementation-plan.md` task
07.3: supported-platform wheel/host smoke checks and failure-path UAT; inaccessible
hosts remain unverified, not passed. The specific installed-host UAT contract says:

- run a real session on every **available and authenticated** host; and
- record every unavailable host as blocked with an exact recovery action.

Therefore Codex and Gemini are not unconditional execution requirements. They are
required inventory rows. If unavailable or unauthenticated at the frozen evidence
boundary, they remain explicit blocked limitations rather than preventing completion
of the available-host procedure. Current read-only inventory finds Claude Code
2.1.234 and OpenCode 2.0.20; Codex and Gemini are absent from `PATH`. Earlier
candidate evidence cannot be silently relabelled for `E`.

This availability-based reading supersedes the worklog's earlier sentence that all
four live executions were mandatory. Any stricter all-four-host requirement is a new
owner decision and must be made before `E` is frozen.

Keep these obligations separate:

| Obligation | Passing evidence | Current state |
|---|---|---|
| Exact-candidate CI | Required CI jobs on `E`, including Windows and installed-wheel checks | Non-pass: run `37560916857` failed Windows lifecycle and strict completion |
| Mutation qualification | Fresh preflight and authoritative calibration for `E`, then an applicability proof for evidence-only `H` | Not run; old preflight is not applicable |
| Checkpoint validation | `fettle completion validate --checkpoint` reports valid evidence, even if honestly incomplete | Previously passed; does not imply completion |
| Strict milestone completion | Every AH07 criterion has current retained evidence and `fettle completion validate` exits 0 | Incomplete; must remain non-pass until all criteria pass |

PR #46 protects `CI required` and `mutation evidence`. A calibration report, a
checkpoint result, and strict completion are not substitutes for one another.

## Node.js warning and supported action upgrade

Latest mutation PR run `37560916928` emitted both:

```text
[DEP0040] DeprecationWarning: The `punycode` module is deprecated.
Node.js 20 is deprecated. The following actions target Node.js 20 but are being
forced to run on Node.js 24: astral-sh/setup-uv@d0cc045d...
```

The emitter is `astral-sh/setup-uv` commit
`d0cc045d04ccac9d8b7881df0226f9e82c39688e`, tag v6.8.0, whose `action.yml`
declares `node20`. It appears 18 times across:

- `.github/workflows/mutation-pr.yml` (2);
- `.github/workflows/mutation.yml` (11);
- `.github/workflows/staged-preflight-aggregation-recovery.yml` (1); and
- `.github/workflows/staged-preflight-continuation.yml` (4).

GitHub began forcing Node 24 on 2026-06-16 and announced Node 20 removal for
2026-09-23. That deadline has passed. These messages are deprecation/runtime warnings,
not the cause of the run's failure: the containment workflow deliberately returned
non-pass because qualification was not executed. The latest CI failure separately
contains a Windows mode assertion and intentionally strict incomplete completion.

The smallest supported upgrade is `astral-sh/setup-uv` v7.0.0 pinned to full commit
`eb1897b8dc4b5d5bfe39a428a8f2304605e0983c`. It declares `node24`. Review found no
use of its removed `server-url` input and no affected self-hosted runner. Compatibility
review must still cover its changed cache-directory handling, forced cache pruning,
cancellation behavior, GitHub-hosted runner requirement (runner 2.328.0 or newer),
macOS newer than 13.4, and lack of ARM32 support. Action runtime Node 24 does not
change project runtime CPython 3.12.13 or mutmut's runtime. Do not set
`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` or suppress the warnings.

Because the deadline has passed and the action is already being forced onto Node 24,
include this pinned upgrade in `E`; do not defer it until after qualification.

## Smallest calibration-interface repair

Do not build an adapter around the old recovery artifact. Generate a fresh preflight
for `E` using the conventional manifest and aggregate artifacts already expected by
`.github/workflows/mutation.yml`, then extend that existing workflow rather than add
another orchestration workflow.

The bounded repair must:

1. pin CPython 3.12.13 and `setup-uv` v7.0.0 in active mutation paths;
2. generate and retain a fresh 256-manifest preflight for exact SHA `E`;
3. accept three sequential calibration stages over the predeclared 8/32/216 shard
   sets, with maximum concurrency 8/16/32;
4. retain compatible terminal checkpoints only under one calibration ID and a fully
   equal candidate/runtime/dependency/policy/manifest/corpus envelope;
5. validate cumulative jobs and runner minutes before launch and completion, upload
   bounded diagnostics with `always()`, retain artifacts for 90 days, restore source,
   aggregate authoritatively, and independently read back checksums;
6. publish `mutation evidence` on `E` only after complete successful calibration;
7. provide a finalization mode, implemented before `E` is frozen, that runs on `H`,
   proves `E..H` is evidence-only and executable-tree-identical, verifies the retained
   calibration, and then publishes `mutation evidence` on `H`; and
8. fail closed on missing, malformed, stale, duplicate, conflicting, incompatible,
   skipped, cancelled, or indeterminate evidence.

This repair changes executable workflows and therefore changes the delivery candidate.
Any helper added under `fettle/` is also shipped and mutation-relevant. Prefer existing
`fettle.mutation_test` primitives and workflow-local bounded validation; do not add a
second product helper merely to consume the historical package.

Required fixtures cover exact runtime setup, the new preflight artifact schema,
8/32/216 topology and concurrency, v7 action inputs/cache behavior, checkpoint
compatibility, retention, cancellation, cumulative accounting, source restoration,
aggregation/readback, authoritative check naming, and rejection of every non-document
or non-allowlisted `E..H` change. The current Windows failure
`test_mutmut_process_timeout_restores_in_scope_mode_only_drift` must be diagnosed and
fixed without weakening POSIX restoration assertions; its fix belongs in `E`.

## Cost and elapsed-time estimate

The old corpus remains only a planning baseline: 45,432 mutants, 186,095 mapped-test
assignments, and about 7,950 expected calibration runner-minutes. The new module adds
roughly 2.4% source size but may have a disproportionate mapped-test cost. A provisional
estimate for `E` is therefore **about 8,100 runner-minutes, with ±25% uncertainty**.
The authoritative estimate must be recomputed from the fresh preflight's actual corpus,
mappings, and retained timing before calibration authorization.

Plan separately for:

| Activity | Expected runner-minutes | Expected elapsed time | Authorization ceiling |
|---|---:|---:|---:|
| Fresh 8/32/216 preflight | 360–450 | 1–2 hours | propose 800, separately approved |
| Sequential 8/32/216 calibration | about 8,100 provisional | 6–8 hours including setup/readback and normal queues | retain 12,000 only as an unapproved ceiling pending fresh-corpus recalculation |

Elapsed estimates assume maximum concurrency 8/16/32 and no shard timeout. They are
not billing guarantees. Queue delay, heterogeneous mapped tests, cancellation latency,
and a larger-than-linear corpus can increase wall time. The old preflight allocation's
remainder is not credit toward either authorization.

## Executable closure sequence and stage gates

1. **Owner decisions before code:** approve the availability-based host contract;
   approve a durable digest-bound run-05 store; authorize only the bounded workflow,
   action, and Windows portability repair; approve CPython 3.12.13.
2. **Implement once:** make the bounded repair, action upgrade, and Windows fix; run
   actionlint, focused fixtures, full tests, Ruff, Fettle, and independent review.
   Any finding is repaired before freezing, not after.
3. **Freeze `E`:** record its literal SHA, executable-tree digest, policy/dependency
   hashes, workflow digests, runtime, and required-check list. No executable edits
   after this point.
4. **Exact-head CI gate:** run ordinary CI on `E`. Stop unless all substantive jobs,
   including Windows and installed-wheel checks, pass. Strict completion may remain
   non-pass only because external evidence and calibration are still outstanding.
5. **Fresh preflight gate:** dispatch only after separate authorization. Validate
   clean 3.12.13 setup, exact `E`, zero collisions/rejections, all 256 manifests,
   retention, readback, and actual resource accounting. Stop on any non-pass.
6. **Re-estimate and authorize calibration:** derive stage workloads from the new
   corpus. The prior 12,000-minute number is not approved automatically.
7. **Calibrate sequentially:** stage 1 (8), retain/read back/account; stage 2 (32),
   retain/read back/account; stage 3 (216), aggregate/restore/read back/account. Do not
   start a stage without explicit approval of the prior stage's terminal package.
8. **Complete external evidence:** execute only separately authorized safe probes on
   available authenticated hosts and bind the approved durable archive locator.
9. **Create evidence-only `H`:** update completion records with immutable run and
   artifact identities. The preimplemented finalization mode must reject any change
   outside the allowlist or any executable-tree mismatch.
10. **Satisfy exact PR-head checks:** ordinary CI on `H` must make strict completion
    and `CI required` pass; finalization on `H` must publish `mutation evidence` only
    after proving applicability from `E`. Branch protection then sees both required
    contexts on the exact PR head.

On failure, retain the terminal package and keep the result non-pass. Compatible
terminal shard outcomes may resume only within the same calibration ID and exact
envelope. Do not rerun a failed shard, substitute evidence, loosen scope or thresholds,
change runtime, or continue after an accounting breach without a new explicit plan.

The owner authorized the bounded workflow/action/Windows repair, its tests, scoped
commits, and normal pushes on 2026-10-07. No mutation preflight, calibration,
authenticated host call, artifact upload outside normal CI, merge, release,
acceptance-policy change, or milestone-complete claim is authorized.
