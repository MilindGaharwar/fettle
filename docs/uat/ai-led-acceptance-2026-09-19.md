# AI-Led UAT: Autonomous Acceptance Readiness

Request date: 2026-09-19. Execution crossed into 2026-09-20 on the host clock.
Candidate: `c83f3b455fca4b8c299c701324df322279837541`.
Decision: **FIX FIRST. Not accepted for unattended acceptance decisions.**

## Goal and Acceptance Boundary

The operator's goal is no routine human UAT execution when requirements and
functionality are clearly understood. This evaluation uses AI-led testing to
assess that goal, not to substitute invented human observations into P77.

For a bounded, explicit contract, an automated acceptance decision should require
complete scenario coverage, independently captured observations, validated
requirement/source/session identity, successful execution, and no unresolved
contradictions. Missing or ambiguous evidence must remain non-pass. Requirement
clarification and permission grants are distinct from manually repeating tests.

This goal changes the direction in the existing
[UAT strength plan](../uat-strength-plan.md), which reserves acceptance for a
human and defers additional implementation. This report does not silently change
that policy, graduate enforcement, or claim human parity. It records executed
evidence and the conditions for a separate automated-acceptance contract.

## Method and Identity

- Three AI-directed lanes: public CLI acceptance, adversarial evidence integrity,
  and real session orchestration using a constrained injected driver.
- Main agent independently verified Git HEAD, reproduced the tampered-artifact
  false pass, and ran the black-box evidence verifier: 14 checks verified across
  77 retained CLI invocations; nine installed CLI/UAT files match the checkout.
- All 108 existing `tests/test_uat*` tests passed in 4.52 seconds. Passing tests
  did not prevent the acceptance defects below.
- Installed candidate: finefettle 1.13.1 in the disposable September 19 wheel
  environment, not the public PyPI distribution. Host: macOS, Python 3.12.13.
- The live driver executed actual installed CLI commands and derived observations
  from captured stdout, stderr, exit codes and a real subprocess timeout. It
  exercised production `run_session`, worktrees, claims, checkpoints, artifacts,
  public reporting and canonical evidence without mocking those components.
- The injected driver is deterministic and AI-authored, not the shipped
  autonomous explorer. No native runner with disabled permissions was launched.
- Synthetic transcripts and benchmark rows are adversarial inputs only. Even
  synthetic rows labeled `human` provide no human baseline or parity evidence.

## Requirement Coverage

Contracts: [Stage 5 requirements](../engagement/10-stage5-agentic-uat.md) and
[UAT strength plan](../uat-strength-plan.md).

| Journey / criterion | Observed result | Decision |
| --- | --- | --- |
| Discover CLI/API/web/library surface; explain missing capabilities | Marker detection and overrides work; malformed config, absent browser runtime and nonexistent startup executable can still report ready | FAIL readiness |
| Generate walkthrough from active GWT specifications | Active scenarios included, draft excluded; numbered actions and IDs preserved | PASS bounded CLI |
| Refuse launch without consent | No worktree or runner launched | PASS |
| Preserve native permission workflow | Shipped launch explicitly disables permission checks | BLOCKED native E2E |
| Run CLI happy path in isolation | Demo, help, unknown command and invalid option produce expected outputs; separate worktree, claims and checkpoints verified | PASS injected driver |
| Keep real runner failure non-pass through report | Session records `tool_error/partial`; report returns exit 0, complete=true and canonical pass | FAIL |
| Handle real bounded subprocess timeout | Session timeout; report exit 1 with blocked/unobserved scenarios; child process reaped | PASS bounded handling |
| Require trustworthy scenario artifacts | Missing artifacts and transcript drift rejected; altered bodies and copied/stale artifacts accepted | FAIL |
| Account for all required scenarios | Missing IDs disappear, empty coverage returns exit 0, duplicate IDs can count twice | FAIL |
| Bind report to current requirements and originating evidence | Changed requirements or absent session evidence can remain valid/pass | FAIL |
| Prove actual restart persistence | Contradictory before/after prose labeled persisted can confirm without a restart | FAIL consumer; live restart untested |
| Independently evaluate wrong-reason passes | Malformed/unbound findings rejected; review coverage and independent observation not established | UNVERIFIED model quality |
| Benchmark acceptance readiness | Default unset threshold blocks graduation, but supported custom manifests can graduate empty/contradictory evidence | FAIL scorer integrity |
| Operate web UI with screenshots, network and accessibility evidence | No safe native browser session executed | UNVERIFIED |
| Resume interruption, persistent profiles, exploratory discovery | Some unit coverage; no complete live workflow evidence in this evaluation | UNVERIFIED |

Live lifecycle verification: **54/57 harness checks passed**. The three failed
checks are exit status, completion and canonical state for the same real runner
failure. This is not a 95% product acceptance score. Expected rejection of invalid
CLI input is a passing scenario; the extra failing driver operation must still
prevent a completed-session claim.

## Release-Blocking Findings

1. **Claim-derived artifacts can falsely confirm acceptance.** The verifier
   compares a stored hash with the transcript without validating the retained
   body or independent observations. Tampered bodies, wrong context and copied
   claims pass. See [artifacts.py](../../fettle/uat/artifacts.py#L23) and
   [reconcile.py](../../fettle/uat/reconcile.py#L256).
2. **Unsuccessful sessions become successful reports.** Confirmed both with
   synthetic lifecycle states and an actual failing command. Missing/tampered
   session sidecars and stale requirements also do not reliably prevent pass.
   See [reconcile.py](../../fettle/uat/reconcile.py#L573).
3. **Coverage accounting permits vacuous or incomplete success.** Unknown IDs
   vanish, subsets omit required scenarios, duplicates double-count and an empty
   verdict list returns exit 0. Restart-only prose can create complete=true with
   no product coverage. See [reconcile.py](../../fettle/uat/reconcile.py#L590)
   and [cli.py](../../fettle/cli.py#L1737).
4. **Restart outcome trusts self-report.** Nonempty contradictory before/after
   strings plus `persisted` can confirm without process or state evidence. See
   [reconcile.py](../../fettle/uat/reconcile.py#L110).
5. **Benchmark graduation trusts asserted metrics.** With a custom threshold,
   an empty file reused across seeds/actors, contradictory files, zero coverage,
   or an empty manifest can graduate. The shipped unset threshold still blocks
   graduation; it does not repair these consumer defects. See
   [benchmark.py](../../fettle/uat/benchmark.py#L87).
6. **Native permission posture contradicts the original intervention contract.**
   Consent text explicitly states permission checks are disabled. No such runner
   was used here. See [session.py](../../fettle/uat/session.py#L43).

Additional findings: malformed checkpoint/artifact/manifest shapes raise
tracebacks; doctor readiness does not establish runtime capability; later retry
claims overwrite earlier contradictory outcomes; evaluator coverage is not
required. Default nested worktrees also cause recursive spec discovery to
duplicate active scenarios, observed during a real run. Supported sibling
worktrees allowed the lifecycle matrix to finish; production was not changed.

## Conditions for No Routine Human UAT

These are acceptance requirements, not an approved implementation or release:

1. Freeze a unique, versioned requirement/scenario inventory before execution.
   Reject missing, duplicate, changed or unauthorized reduced scope.
2. Capture actual tool/process/browser observations independently of model prose,
   binding bytes to scenario, attempt, source, session and environment. A model
   should explore and interpret evidence, not manufacture its own pass oracle.
3. Validate the entire execution-to-report chain. Errors, timeouts, failed
   captures, stale inputs, missing evidence and conflicts cannot become pass.
4. Require explicit expected outcomes for each criterion. Preserve attempts and
   contradictory results; use independent evaluation where deterministic
   assertions cannot decide. Ambiguity means clarification, not automatic pass.
5. Provide a permission-respecting native runner and verify real CLI/API/library/
   browser workflows, startup/readiness, restart, interruption, cleanup, boundary
   inputs and relevant accessibility requirements.
6. Calibrate on held-out seeded defects with known ground truth and independent
   review of the test oracle. Commit risk-specific discovery thresholds and
   require zero observed false passes in that calibration. Neither zero observed
   false passes nor a test pass rate proves zero future risk.
7. Define an explicit automated-acceptance policy for covered contracts. Human
   benchmark parity is a separate empirical claim; do not relabel AI sessions or
   silently repurpose the existing human-attestation channel.

## Reproduction and Evidence Retention

Raw evidence is retained locally under these temporary directories. It is not
committed, portable CI evidence, or guaranteed to survive temporary-file cleanup:

```text
$TMPDIR/fettle-uat-blackbox-k0BrDXfG
$TMPDIR/fettle-uat-integrity-R6wA8J9M
$TMPDIR/fettle-lifecycle-retry-Zv39wLsV
```

Each contains `REPORT.md`, executable reproduction scripts and raw results.
Black-box evidence includes `evidence-index.json` and per-command stdout/stderr/
exit files. Integrity evidence includes `session-results.json`,
`artifact-results.json` and `benchmark-results.json`. Lifecycle evidence includes
`results.json`, `evidence-manifest.json`, raw command logs and final worktrees.

Read-only verification of retained black-box evidence:

```sh
node "$TMPDIR/fettle-uat-blackbox-k0BrDXfG/verify-evidence.cjs"
```

Minimal reproduced public CLI counterexample, using retained synthetic inputs:

```sh
cd "$TMPDIR/fettle-uat-blackbox-k0BrDXfG/cli"
"$TMPDIR/fettle-audit-sep19-wheel/bin/fettle" uat report \
  --worktree ../session-artifact-tampered --json
```

Actual result: both scenarios CONFIRMED despite altered artifact content.
The lifecycle report contains replay instructions; replay overwrites its current
logs, so preserve the original evidence before rerunning.

## Worklog and Limits

Requirements and existing authority policy were read before probing. Independent
agents exercised functional and adversarial paths; the parent checked the central
false-pass reproduction and evidence identity. An initial lifecycle attempt was
blocked by sandboxed linked-Git metadata; a standalone disposable repository and
normal filesystem authorization resolved it. No security control was bypassed.

All probe child processes were reaped. Disposable fixture commits were test setup
only. No production implementation, global configuration, trust state, public
release, enforcement mode or existing human evidence was changed. No main-repo
commit, push or merge was performed for this evaluation.

Full native autonomous/browser end-to-end acceptance remains blocked or
unverified, not completed. Production fixes span the evidence authority boundary
and require a separately scoped implementation. Existing green PR checks predate
this report and do not invalidate these newly reproduced findings.