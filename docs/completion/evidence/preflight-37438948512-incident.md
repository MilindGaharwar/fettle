# Preflight 37438948512 Incident and Readiness Decision

Date: 2026-10-06

Frozen candidate: `8c865a18a4a187ad782dc4db856e2cff23199253`

Verdict: **REJECT / FIX FIRST** for mutation qualification. The run is diagnostic-only and permanently non-pass.

## Preservation and reconciliation

The original run, its 50 downloaded artifacts, and archive remain unchanged under the external preserved evidence root. The restored archive SHA-256 is `8de38e2b26f7b861ecce29ce4847a9450301070d6ad1d750c8f81432f0fe55a7`.

GitHub recorded 260 jobs: 9 success, 22 failure, 228 cancelled, and 1 skipped. Of the 256 shard jobs, explicit job-ID-to-shard reconciliation records:

| Job conclusion | Artifact/report result | Shards |
|---|---|---:|
| success | valid completed report | 8 |
| failure | valid `tool_error` report | 20 |
| cancelled | valid `tool_error` report | 9 |
| cancelled | valid completed report | 5 |
| cancelled | malformed/empty report | 5 |
| cancelled | no artifact | 209 |

The 13 valid completed reports and 29 valid tool-error reports are report counts, not GitHub job conclusions. Five completed reports were uploaded by jobs GitHub later classified as cancelled. The complete 256-row ledger is retained as `job-shard-ledger.json` with SHA-256 `6afdd188272f34c78834ace1cb90b10fcea2155c28c47b4f1a10085c48180f3b`.

The monitor first observed the estimated usage above the 480-minute trigger at 08:56:17Z (`482.25`, 230 active jobs). Cancellation was recorded at the next completed observation, 08:56:29Z (`519.41`, 218 active jobs). Relative to that recorded request, 80 shard jobs had already completed: 8 successful reports, 20 failed tool-error reports, 1 cancelled job with a tool-error report, and 51 cancelled jobs without an artifact. The other 176 shard jobs completed after the request and are cancellation-affected. Their partial reports remain diagnostic and non-pass.

The earliest independently retained restoration failures are a tie at one-second log resolution:

- shard 8, job `112188581638`, completed 08:54:58Z;
- shard 27, job `112188581699`, completed 08:54:58Z.

Shard 8 is the canonical earliest record. Its complete log SHA-256 is `6a48ac8a58013677d4d6ecde385f8f701a4be497bac4276d7258c65bf335319e`. It records this command:

```text
uv run --no-sync python -m fettle.mutation_test --root . --preflight-manifest mutation-manifests/partition-8.json --json > mutation-preflight.json
```

The step exited 2 before cancellation. Its report states:

```text
Cannot execute mutmut preflight: mutation source integrity failure: fettle/quality_scan.py: changed without a matching mutation backup; whole-source manifest differs after restoration
```

Shard 8's manifest includes `fettle/quality_scan.py:417-418`. Shard 27's complete log, manifest, and execution context are also retained; its log SHA-256 is `88a406f52c82842644994986770509967b111d0d1f4eba775c9a4b4b206275bb`.

## Demonstrated root cause

The preflight path is:

1. `_preflight_shard_modules` isolates the native cache and calls `_preflight_mutmut` once per represented source module.
2. `_preflight_mutmut` writes a range patch and invokes `mutmut run --paths-to-mutate=<file> --runner "python -c pass"`.
3. `_run` recognizes `mutmut run` and delegates to `_run_mutmut_process`.
4. `_run_mutmut_process` captures all Python bytes and modes, starts a new process group/job, terminates the complete tree on completion or interruption, and verifies/restores source state.
5. mutmut 2.5.1 creates `<source>.bak` using text-mode `open(..., "w")`, which creates mode `0644`, writes the mutant, and finally uses `shutil.move(<source>.bak, <source>)`.
6. For executable `fettle/quality_scan.py`, mutmut restores the original bytes but replaces mode `0755` with the backup's mode `0644`. It consumes the backup before Fettle verifies the tree.

The earlier lifecycle repair is therefore invoked on preflight and covers normal completion, timeout, signals, and exceptions. Its evidence rule assumed any drift after mutmut returned would still have a matching backup. That assumption is false for mutmut's mode-loss behavior after a normal return.

Three authorized local diagnostics separated the hypotheses:

| Diagnostic | Runtime/scope | Discriminating result |
|---|---|---|
| 1 | exact shard 27 in disposable candidate checkout | reproduced exit 2; bytes remained `583976…37d`; mode changed `0755 → 0644`; no backup, residue, or worker survived |
| 2 | harmless two-line executable fixture; Python 3.12.13; mutmut 2.5.1 | reproduced the same failure and isolated mode loss from concurrency, cancellation, repository content, and generated state |
| 3 | exact shard 27 with repair; Python 3.12.13; mutmut 2.5.1 | completed 61/61 canonical details, zero collisions; exact bytes and `0755` restored; no backup, mutation residue, or worker survived |

Diagnostic SHA-256 values are `769e31a92442a1ea3cfa13f00afb67b5f42a2c22409031e0b06de74126f7666a`, `543fe0ddd9fc9aebe5130944eab5ca7d80d9b1142b9afcb1eeca87b8fceeff40`, and `a97d6af318e4bf79bbcf9b40b0da5b4169621d7420a44b1b6a768db651fef543`.

## Repair and verification

The repair reuses the existing restoration lifecycle. It permits only this narrow correction: when a file is explicitly named by the single valid `--paths-to-mutate` argument and its bytes exactly equal the pre-run bytes, restore its original mode. Content drift still requires an exact backup. Missing, duplicate, empty, absolute, parent-traversing, or out-of-scope paths grant no mode-restoration permission. Unexplained changes remain untouched and non-pass.

Regression coverage proves normal completion, timeout, `KeyboardInterrupt`, out-of-scope mode drift, malformed scope, and combined content/mode drift. Local evidence:

- focused mutation/CI suite: 271 passed;
- full suite: 4,368 passed, 20 skipped;
- Ruff: pass;
- actionlint on the changed workflow: pass;
- Fettle all-source scan: 195 files, zero findings and tool errors;
- configuration validation: pass;
- independent code-and-evidence review session `ses_eef5d5ca9ffe0UE3pkRaG8dzTC`: diagnosis and repair accepted after inspecting all five required evidence files.

A bounded `diagnostic-canary` dispatch mode was added because the prior workflow could not select one preflight shard. It validates one shard index against manifests generated on the exact candidate SHA, runs one non-matrix preflight job, always retains its diagnostic artifact, skips full-shard fan-out, and forces the sole authoritative `mutation evidence` producer to remain non-pass. It cannot publish qualification.

The authorized remote canary completed on run `37448719286` against exact repair SHA `bdae9225185b9d7497eadd1d2b853d1fa67f5187`. The prepare job and sole diagnostic shard job succeeded. Shard 27 generated and canonicalized 61 details with zero collisions under mutmut 2.5.1. The authoritative `mutation evidence` job then failed closed with exit 2 after retaining `status=unknown`, `passed=false`, and `qualification_executed=false`. No preflight matrix, full-shard execution, or qualification aggregate ran.

The three remote artifacts expire on 2027-01-04 and were copied with job logs and metadata to `external://local/audit-hardening/candidate-bdae922/canary-37448719286`. Key SHA-256 values are:

- diagnostic report: `72fdbae3694a486413a8bc2dcdb19afa1dd2c69269db8b1d70ae130f6327103e`;
- authoritative non-qualification report: `01403d8d067bd420f2ae274f45410fa99f32b17cabdb7008a402b1965fa27844`;
- shard 27 manifest: `8fb53a3bc07f2bf61c9b8ccf227c88cae6e0d70bd8764809c29308db1e9ba5f1`;
- diagnostic job log: `253b1e6611009c8c78f3ddd5b9ddf31694e4b5d32580a7b9483ac4d3139c9bfc`;
- authoritative job log: `6a75f8530ed4b38928d8a413615c804809abf1d7399f90ce1679dd91eddc05fb`.

## Resource accounting and staged plan

The monitor's `539.23` runner-minute figure is an estimate from summed observed job intervals, not a provider billing statement. The 480-minute trigger was sampled rather than continuous. At the first over-threshold observation, 230 jobs were still active. The cancellation request was recorded about 12 seconds later, when the estimate had reached `519.41`. GitHub then took about 115 seconds to settle the run; active jobs fell 218 → 17 → 7 → 3 → 0, adding the remaining estimated usage. Monitoring and cancellation therefore cannot guarantee a hard cap.

The 28 shard jobs that reached GitHub success/failure before cancellation account for 28.08 observed job-minutes. The 42 shards with valid reports account for 43.80 observed job-minutes. These durations exclude or only partly represent cancelled setup and teardown and are not billed-usage evidence.

The successful canary does not authorize a replacement preflight. A future authorization should use staged dispatches with immutable manifests and no automatic retries:

1. 8 representative shards, maximum parallelism 2; stop on any integrity/tool error.
2. 32 shards, maximum parallelism 4; stop and reconcile every job and artifact.
3. Remaining unchanged scope, maximum parallelism 8, in separately authorized waves.

Use a planning estimate of 2.0 runner-minutes per shard plus 15% setup/aggregation overhead: about 590 runner-minutes for 256 shards. Reserve at least 25% additional authorized headroom (about 740 runner-minutes total authorization) for accounting and cancellation lag. This is a planning bound, not a guaranteed cap. Each wave needs its own owner-approved budget and stop decision; qualification scope, timeouts, corpus, and acceptance criteria remain unchanged.

## Readiness and authorization

The one-shard remote diagnostic canary is complete and supports readiness for a separately authorized staged preflight. It remains diagnostic and does not satisfy preflight, calibration, or qualification.

Additional authorization now needed: approval of the staged preflight plan, explicit per-wave runner-minute budget/headroom, and exact repair candidate SHA. Calibration remains disabled until a complete accepted preflight and separate calibration authorization. Portable evidence and authenticated host work retain their independent approval requirements.

Milestone A and AH07 remain incomplete.

## Staged preflight 37464324954 stopped after wave 1

The authorized one-attempt staged preflight ran on 2026-10-06 with frozen executable
candidate `0fc41fdfee13e09f4bda3dc5eee177030882aa36` and separate orchestration commit
`891562ba4909b16e6252a0eb7e8674393f43eba0`. Run `37464324954`, attempt 1, froze a
complete 256-manifest topology and executed only wave 1: shards `8, 27, 28, 37, 48,
50, 51, 53` at maximum parallelism 2.

All eight shard jobs and the manifest-bound wave validator passed. Independent local
read-back reproduced exact membership, 629 generated/canonicalized details, zero
collisions, and the validator's eight report digests. The plan SHA-256 is
`1e712595d7c6adccbd17aa284eaf4821afda82c9b61798022eeb6ea861190294`; the accepted
wave-1 validation SHA-256 is
`42d41dc932b33506b7b8e4d2d2d597b40192285aac2e76fc9aa9891d4bccaec4`.

The budget gate then rejected GitHub's job-timing response as contradictory. Three
skipped jobs reported `completed_at` one second before `started_at`: job
`112271421433` (`mutation (complete detail corpus)`), job `112271422153` (`mutation
evidence`), and the subsequently skipped wave-2 placeholder job `112274836403`.
The first two contradictory records were present in the budget gate's response. The
gate therefore returned `staged preflight rejected: job timing is reversed` and exit
2. Excluding skipped jobs only for diagnosis, non-skipped observed usage was 11.97
runner-minutes, below the 20-minute wave-2 launch ceiling. That diagnostic does not
override the fail-closed decision.

Waves 2 and 3, full-corpus aggregation, and final staged evidence did not execute.
The run is permanently non-pass and will not be retried, resumed, or substituted.
Calibration remains blocked. The downloaded plan, 256 manifests, eight reports,
wave validation, API metadata, and gate log are retained at
`external://local/audit-hardening/candidate-0fc41fd/staged-preflight-37464324954`.
The downloaded 268-file corpus digest is
`d0740e31f2a51fe37d829cf39db7923ada054f450e4edc77e47939ddd9e82a4e`; the complete
preserved-tree checksum index has SHA-256
`2254c5f0492427712a97a0bc55d1fdba3ebb16cfa7b69182394e71297af5c9f5`.
