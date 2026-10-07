# Final Acceptance Contract and Closure Proposal

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
