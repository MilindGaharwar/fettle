---
id: plan-uat-strength
---

# UAT Strength Plan — Agent Acceptance At Par With, Then Stronger Than, Human UAT

Status: 2026-09-20 operator-authorized integrity repairs and requirement-based
automated acceptance work below supersede the earlier implementation deferral.
P77 human parity and enforcement graduation remain unproven.
Research basis: `docs/hypothesis-tree-uat.md` · Backlog:
`docs/backlog/uat-p7[2-7]-*.md` work items

## User story and job

As an operator shipping a product through Fettle, I want `fettle uat run`
to exercise the running product the way a skilled human acceptor does —
and to observe, remember, and account for coverage better than any human
can — so that SHIP decisions rest on acceptance evidence I did not have to
perform by hand and cannot refute.

The bar is deliberately two-sided: reach parity on human strengths
(exploration beyond scripts, skepticism, statefulness) and exceed humans on
their weak axes (observation reliability, memory, coverage accounting).

## Where we stand

Stage 5 agentic UAT already ships `doctor/run/report/manual/attest`, worktree
isolation, GWT-scenario persona prompts, transcript reconciliation, HITL
permission posture, and manual fallbacks. The active-specs-as-contract
design already answers the industry's dominant failure ("agents cannot
define correct"). The gaps versus human UAT are exploration breadth,
independent observation, statefulness, judgment depth, and — critically —
the absence of any instrument that could falsify a parity claim.

2026 external evidence (agentic-QA landscape; TestExplora; GBQA;
session-based exploratory practice) contributes three constraints the plan
must respect:

1. Agents pattern-match known failure modes and miss genuinely novel bugs —
   breadth must come from structured tours, not bigger prompts.
2. Confidently-wrong passes are worse than honest failures — verdicts must
   bind to artifacts, never self-report.
3. Autonomy is earned per rung (assistive → augmented → agentic); report-only
   stays until held-out measurement proves parity.

## Assumptions

- Active specs remain the sole definition of "correct"; candidate scenarios
  from exploration require operator attestation.
- The default v1.13.1 package includes the Playwright Python library. Browser
  binaries remain an explicit external installation; axe capture is driven by
  the target application or runner rather than silently assumed.
- Human sessions can be recorded once to seed the benchmark's human baseline.

## Tradeoffs considered

- **Smarter prompts vs more channels:** prompt-only improvement was rejected —
  it does not address confidently-wrong passes. Chosen: artifact-bound
  verification first (P72).
- **Auto-promote discovered scenarios vs attest-gate:** auto-promotion grows
  subtly-wrong suites (documented industry failure). Chosen: attestation gate,
  reusing the existing command.
- **Build benchmark first vs last:** first would stall visible capability
  behind harness work; last risks unfalsifiable claims in between. Chosen:
  capability phases P72–P76 with report-only posture, P77 as the gate that
  unblocks enforcement modes.

## Blast radius

`fettle/uat/*` session/reconcile cores, doctor probes, default-package
capability checks, new `docs/uat/` benchmark area. No change to spec discovery,
mutation, or completion gates except additive references. Existing
`test_uat_*` suites must stay green at every phase boundary.

## Milestones

| ID | Goal | Completion criteria (evidence-typed) | Depends on |
|---|---|---|---|
| P72 | Evidence hardening: screenshots + a11y-tree/DOM snapshots + HTTP logs retained per scenario step; reconciler verifies against artifacts | success: scenario verdict without artifact → `unknown`, regression-tested; error-path: tampered transcript exposed by artifacts | — |
| P73 | Beyond-spec charters (SBTM tours, personas, fuzzing) producing attestation-gated candidate scenarios + coverage accounting | success: charter run yields artifact-backed candidates, none auto-promoted; boundary: coverage accounting totals equal discovered-surface inventory | P72 |
| P74 | Web surface driver S5.5 with per-state axe-core capture feeding P72 channel | success: demo-app web session drives UI-only end-to-end; error-path: missing browser runtime → exit 2 + manual script | P72 |
| P75 | Statefulness: persistent profile, restart/interruption probes, realistic seeded data | success: restart-probe persistence verdict reconciles from artifacts; success: data diversity measured, not asserted | P72 |
| P76 | Judgment layer: independent evaluator pass over transcript+artifacts hunting wrong-reason passes; severity routing to attest | error-path: adversarial fixture flagged where primary reconciler accepted; contract: no finding resolves without artifact reference | P72 |
| P77 | Seeded-defect parity benchmark ("mutation testing for UX") over ≥10 seeds with recorded human baseline | success: metrics reproduce from canonical retained evidence; gate: zero false-verdicts and agreed discovery threshold unblocks enforcement mode | P73, P74, P75, P76 |

Estimates follow the house pattern of 3–8 days each; P77 is the largest.

P75 and P76 are implemented in report-only mode. P77 now has a packaged
ten-seed manifest and reproducible retained-evidence scorer exposed through
`fettle uat benchmark`; parity and enforcement graduation remain blocked until
all ten seeds have real human evidence and reviewers commit a discovery
threshold.

The repository contains duplicate historical work-item IDs for parts of
P72-P74 with inconsistent open/done metadata. Those records do not override the
capability status above and must be reconciled before any future UAT milestone
claims completion.

## Deferred Packaging Direction

The 2026-09-20 operator request authorizes the repair program below; it does not
authorize enforcement graduation or package extraction. Separately evaluate a
versioned
first-party `finefettle-uat` distribution that owns runtime startup/readiness,
fixtures and fault controls, cleanup, incremental persistence, browser/model
probes, diagnostics, independent artifacts, and adaptive risk-guided
exploration. Core should consume its canonical evidence through the same strict
authority boundary as every other producer.

This is a packaging hypothesis, not a committed extraction. Validate external
consumer compatibility, installation UX, and ownership boundaries before
moving repository-local modules. Containers remain optional unless a concrete
isolation or reproducibility requirement justifies them.

## Sequencing and concurrency

P72 first — every later phase consumes its artifact contract. P73–P75 may
then proceed in any order, but they share session/reconcile cores: concurrent
execution is coordinated through distinct `fettle work` claims (one claim per
milestone; same-file edits serialize under claim-before-work). P76 builds on
the P72 artifact contract; P77 is last because its instrument needs
P73–P76 capabilities to be meaningful.

## Task decomposition contract

Each claimed item decomposes at execution time into tasks of one concern,
2–5 minutes each, naming exact file paths and a verification command, ordered
so the suite stays green after every task — per `discipline-planning`.

## Non-goals

- Inferring human parity or release authorization from automated acceptance.
- Auto-repairing product code from UAT findings.
- Mobile/desktop-native surfaces (future plan if demand appears).
- Any enforcement mode before P77 publishes its baseline.

## Authorized Repair Program (2026-09-20)

Goal: requirement-based automated acceptance without routine human test execution.
Given explicit requirements and authorized test access, an agent explores and
executes; independently captured observations and contract-bound oracles decide
acceptance. Human clarification is needed for unresolved requirements or authority,
not to repeat already-verifiable test actions. Existing human attestation remains
separate; no AI run is relabeled as human evidence.

Baseline: [AI-led UAT report](uat/ai-led-acceptance-2026-09-19.md), candidate
`c83f3b455fca4b8c299c701324df322279837541`. Existing 108 UAT tests pass despite
reproduced false passes. No acceptance or enforcement graduation is implied.

### Architecture and Trust Boundary

An artifact is not independent merely because it has a hash or is written by
another function. The explorer's prose is a claim. A trusted execution controller
must capture actual command exit/stdout/stderr, browser actions/state, or protocol
responses outside the explorer's write authority. Bind each observation to the
frozen requirement, scenario, attempt, session, source and execution context.
Acceptance must use those observations and a predeclared oracle, not `matches`.
An independent model may interpret evidence but cannot supply missing execution
or override failed predicates. Hashes detect drift; they do not prove origin.

The initial safe migration keeps legacy claim-only sessions inspectable
but non-confirming. Do not create a new `trusted=true` field, accept an explorer's
signature, or silently treat a JSON file as an independent capture channel.

### Detailed Ordered Todo

Each checkbox requires the stated executable evidence before it is completed.
Production edits are small slices followed immediately by focused tests.

#### R0 - Scope, UX and Reproduction

- [x] Persist this checklist before implementation; record the operator's changed goal.
- [x] Record CLI journey, eight states, Given/When/Then cases and compatibility behavior in `uat-acceptance-integrity.ux-spec.md`.
- [x] Run impact analysis and establish current dirty state; preserve prior UAT report. Graph was stale and used only as a caller hint; executable caller tests control verification.
- [x] Turn core retained false-pass examples into regressions in existing UAT test files; complete adversarial matrix remains R7.
- [x] Maintain this worklog with commands, results, decisions and remaining blockers for the safety migration; continue updating during R5-R7.

#### R1 - Stop Claim-Derived Confirmation

- [x] Label transcript-derived artifacts as claims, not independent observations.
- [x] Make claim-only `matches` indeterminate, including legacy artifacts; preserve useful diagnostics.
- [x] Validate claim JSON shapes, body hashes, scenario identity and scenario steps. Independent observation context remains R5.
- [x] Prevent copied, duplicate, stale, missing and malformed claims from granting acceptance; malformed artifact lists no longer crash.
- [x] Preserve contradictory attempts as unresolved rather than allowing last-match overwrite. Full attempt histories remain R5.
- [x] Make restart prose non-confirming without actual process/state evidence.
- [x] Verify positive parser behavior and negative claim/tamper/replay/restart controls.

#### R2 - Lifecycle and Canonical Evidence

- [x] Require a completed, error-free session and successful required capture before completion.
- [x] Validate checkpoint shape, canonical session sidecar, retained transcript and frozen contract before completion; incomplete reports remain inspectable.
- [ ] Bind frozen source, policy, scope, producer and session identity to current validation context.
- [x] Reject missing/tampered sidecars, transcripts and changed requirements as acceptance evidence on report replay.
- [x] Derive trace, CLI status, saved completion and canonical result from the same predicate; failed sidecar publication downgrades saved completion.
- [x] Test real exit-2 process propagation, unsuccessful terminal states and missing dependency recovery; full native interruption/recovery remains R7.
- [x] Make atomic checkpoint/report failure non-pass; verify collector interruption and cleanup failure cannot reuse success. Recovery uses a fresh complete session; hard-kill orphan recovery remains unqualified.

#### R3 - Exact Coverage

- [x] Freeze required scenarios and contract digest before execution; reject empty/duplicate inventories when reporting.
- [x] Reject duplicate active scenario IDs and invalid specification findings. Repository-wide duplicate spec lint remains separate.
- [x] Exclude default `.fettle` worktrees from spec discovery without hiding `.fettle` work items. Arbitrary custom nested worktree roots remain to qualify.
- [x] Reject missing/removed/subset inventories explicitly instead of intersecting them away; per-ID gap rendering remains future UX refinement.
- [x] Count product coverage separately from restart and evaluator checks; auxiliary failure still prevents completion.
- [x] Make empty verdict lists and restart-only reports non-pass at CLI, report and canonical output surfaces.
- [ ] Test added/removed/changed scenarios, duplicate attempts and nested worktrees.

#### R4 - Permission-Respecting Execution

- [x] Inspect all supported runner commands and evaluator launches for bypass flags.
- [x] Route UAT exploration/evaluation through explicit Claude manual permissions or Codex on-request/read-only commands, without automatic tool grants or hook-trust bypass. Other callers unchanged.
- [ ] Unsupported noninteractive approval must return blocked with actionable recovery.
- [ ] Keep secrets out of model prompts/transcripts; no invented or auto-answered approval.
- [x] Reject corrupt policy, unavailable startup executable and missing Chromium runtime; runtime reachability/auth/version qualification remains R7.
- [ ] Test no-consent, blocked permission, invalid config, unavailable runner/browser and cleanup.
- [ ] Verify native host behavior with normal approvals; do not infer it from mocks.

#### R5 - Independent Capture and Contract Oracles

- [x] Define versioned controller receipts and validate source/policy/runtime/session/oracle context; canonical references are required, not defaulted.
- [x] Define the trusted-controller/untrusted-product boundary for deterministic contracts. An unrestricted native explorer is not attached.
- [x] Implement controller-owned CLI/API capture with bounded processes, timeouts and raw outputs for the qualified runtimes below.
- [ ] Implement controller-owned browser action/state/network capture, screenshots and accessibility evidence.
- [x] Bind each deterministic controller attempt to approved actions and requirement oracles before execution; unrestricted explorer attempts remain unsupported.
- [x] Keep retained controller evidence outside tested-process access; document local trust limits. No unrestricted same-user agent guarantee.
- [x] Evaluate explicit deterministic assertions from captured observations; never from prose labels.
- [ ] Give judgment evaluators requirements and evidence; require per-scenario review coverage.
- [ ] Retain conflicts and require evidence-backed resolution; no majority-vote substitution for truth.
- [x] Run positive and negative CLI/API/browser/restart fixtures through actual capture and installed public report/canonical paths.

#### R6 - Benchmark Integrity and Calibration

- [x] Validate manifest shape, at least ten unique named seeds and finite threshold range. Ground-truth schema remains R5/R6 follow-on.
- [ ] Reject empty, shared, contradictory and provenance-free evidence even with valid hashes.
- [x] Add version-2 controller calibration deriving metrics from canonical reports and unique retained captures. Legacy asserted metric rows remain descriptive and non-promoting.
- [x] Distinguish deterministic controller conformance from agent discovery and historical human-parity measurement.
- [ ] Freeze held-out fixtures and risk-specific thresholds before calibration.
- [ ] Run independent defect-discovery trials; retain misses and false passes as failures.
- [ ] Require zero observed false passes, full required coverage and agreed discovery thresholds.
- [x] State residual risk; no finite benchmark or fixture conformance proves universal correctness.

#### R7 - Qualification and Rollout

- [ ] Replay every retained adversarial finding against repaired code, not the old wheel.
- [x] Run all UAT and full repository tests plus nonempty Fettle checks for the safety migration; repeat after independent capture implementation.
- [ ] Verify installed wheel outside checkout and real permission-respecting host sessions.
- [ ] Exercise CLI/API/library/web workflows, error/recovery, restart and interruption as applicable.
- [ ] Retain portable sanitized evidence and requirement-to-evidence traceability in the repository/CI.
- [x] Run completion validation for existing records; this repair program has not graduated and no new completion claim was fabricated.
- [ ] Introduce automated acceptance only for qualified contracts/surfaces; unknown remains non-pass.
- [ ] Keep report-only compatibility, explain migration, and separately authorize enforcement promotion.
- [ ] Commit/push/merge/release only with the applicable operator authorization; verify remote gates after a push.

### Verification and Worklog

Owning mechanisms: `fettle/uat/artifacts.py`, `session.py`, `reconcile.py`,
`doctor.py`, `benchmark.py`; CLI status in `fettle/cli.py`; runner commands in
`fettle/runners/`; spec inventory in `fettle/spec_model.py`. Shared API changes
require neighboring caller tests. Use existing test files and canonical evidence
utilities. No full mutation calibration as an iteration loop.

2026-09-20: Plan persisted before production edits. Initial local hypothesis:
`_confirm_gate` validates a copied transcript digest, not independent execution;
therefore an unchanged self-claim can confirm even when its artifact body is
altered. Cheapest discriminator: existing artifact/reconciler fixtures plus a
claim-only false-pass regression. First repair will remove that false authority,
not rename claims as observations. This closes false passes but does not itself
deliver independent capture or enable unattended acceptance.

### Implemented Safety Migration (2026-09-20)

- Claim artifacts and caller-supplied confirmations cannot grant acceptance.
  Existing claim-only sessions remain inspectable but are INDETERMINATE; benchmark
  graduation is explicitly blocked until independent capture/oracles are qualified.
  This is an intentional temporary loss of unsupported positive acceptance, not
  completion of the automated-acceptance goal.
- Session report validation binds terminal state, sidecar, transcript, producer,
  frozen scenario contract and inventory. It does not yet provide immutable
  explorer-independent storage or bind every product source/runtime dependency.
- UAT-only runner commands preserve permissions. Installed help verified Codex
  on-request/read-only and Claude `manual` mode. Gemini/OpenCode are blocked for
  UAT until a permission-preserving mode is qualified. No live paid native host
  session was executed for this repair; flags/tests are not live-host acceptance.
- Existing benchmark metric aggregation remains descriptive; even a supplied
  threshold cannot graduate asserted rows. Empty/reused artifacts, zero-sized
  coverage and invalid manifests are rejected. Semantic metric derivation remains
  open, rather than trusting a new self-declared provenance field.
- Verification so far: 132 UAT tests, 254 affected-consumer tests at the earlier
  boundary checkpoint, targeted mypy clean across ten UAT/runner/spec sources,
  and Ruff clean. Initial full run found two obsolete assurance expectations and
  one shared skip-list regression; all three were corrected and their affected
  test suites passed. Final full-suite result is recorded below when available.
- Retained replay: `fettle-uat-repaired-replay-i4cynyu0/corrected-results.json`
  under TMPDIR. Ten copied historical fixtures now return exit 1 or 2 without
  CONFIRMED results or tracebacks. Original transcripts were relocated into the
  copies' evidence directory. Initial replay hit missing transcripts and is not
  counted as defect-specific evidence. Sandbox trace-write warnings mean this
  replay proves CLI behavior, not durable governance logging.
- Added a real subprocess regression: exit 2 without a populated runner error
  still yields failed session, incomplete report and non-pass canonical evidence.
- Worktree/spec discovery regression exposed a shared skip-list consumer; the
  final exclusion is local to spec discovery, preserving work-item discovery.

### Remaining Critical Path

### R5 First Qualified Slice: Read-Only CLI (2026-09-21)

Operator authorized continuing in priority order. First deliverable: run one
approved CLI action per required scenario, capture actual bytes and exit status,
and evaluate exact assertions. No model or shell interprets the contract. Existing
exploratory sessions stay non-confirming. API, browser, stateful writes and parity
are not implied by this slice.

User flow: review a version-1 JSON contract, approve its SHA-256 digest, then use
`fettle uat run --contract <path> --approve-contract <sha256> --yes --json`.
The contract contains `schema_version`, `scenario_digest` (the canonical digest of
active scenarios), and `actions`: exactly one object per scenario with
`scenario_id`, absolute executable `argv`, integer `timeout_s` (1-60), and `expect`
containing integer `exit_code` plus exact UTF-8 `stdout` and `stderr`. Unknown
fields, duplicate JSON keys, missing coverage and stale scenario bindings fail.
Approval is a caller authority boundary, not a digest supplied by an explorer.

Threat model: the controller, operator-approved contract, installed Fettle and OS
are trusted. The child application and its output are untrusted. The macOS driver
uses a deny-by-default OS sandbox: read-only product/system runtime access, no
network, no child processes, no filesystem writes, and no access to the external
controller evidence store. A minimal environment excludes inherited credentials.
Missing sandbox capability is blocked, never an unsandboxed fallback. No claim is
made against a compromised OS or a separate actor with unrestricted same-user
shell access. Such an explorer requires a separate OS identity/container boundary
before connection; this slice never launches that explorer.

Observations are versioned, bounded, controller-retained records outside the
product tree, bound to the session, root, source inventory, policy, scenario
contract, oracle and runtime identity. Reports revalidate this retained record;
in-tree JSON and transcript labels cannot grant authority. Product bytes and
contract must remain unchanged across execution and replay. Secret detection
blocks publication rather than persisting unredacted output.

- [x] Validate contract and sandbox capability before any action; contract doctor probes only a harmless nonce echo.
- [x] Capture bounded raw process outputs; timeout, denied operation and output
  overflow remain non-pass, including when a matching exit code was expected.
- [x] Retain controller observations outside the product sandbox and verify context on report replay; unrestricted same-user actors remain outside the trust guarantee.
- [x] Derive report, trace, CLI and canonical completion from a shared predicate.
- [x] Verify actual pass, seeded output defect, stale source, forged/replayed
  report, missing receipt, permission denial and timeout through public paths.

Owning files: new `fettle/uat/controller.py` for this distinct execution authority;
existing session/reconciler/CLI for routing and consumers. Reuse UAT test files.
The first executable discriminator is real sandboxed CLI output versus a seeded
wrong output, not a mocked confirmation. Stale kgraph output supplies caller hints
only. No package extraction, new model dependency or general sandbox framework.

The first read-only CLI slice now supplies controller-owned observations and
approved deterministic oracles without launching an explorer. Broader R5 still
requires transports for API/browser/stateful actions and a separately isolated
explorer. Ordinary same-user shell access would invalidate the controller-store
boundary; do not attach such an explorer to this implementation. A hash, explorer
signature, second model opinion or `trusted` flag cannot replace isolation.
R6 calibration and broader R7 qualification remain open. No enforcement promotion
or human-parity claim is authorized by this progress report.

### CLI Controller Verification (2026-09-21)

Implemented `fettle/uat/controller.py` and routed approved contracts through the
existing doctor/run/report commands and canonical consumer. Exact output and
exit-code assertions cover all active scenarios. Missing approval, malformed
contract/receipt, stale source/policy/oracle, sandbox failure, timeout, output
overflow and sidecar publication failure are non-pass. Legacy claim-only sessions
remain non-confirming. Checkpoint publication is atomic.

The macOS sandbox denies writes, network access and process forks with termination
on denial; `/dev/dtracehelper` is the measured runtime-device exception. It allows
system-runtime reads, excludes user-home/product data except frozen inputs, and
explicitly denies controller-store reads. This is not a hermetic runtime: shared
system libraries are trusted, executable bytes and platform identity are bound,
and adversarial external same-user/root processes are not covered. No Linux,
Windows, API, browser, unrestricted-agent or stateful-write qualification is implied.

Evidence:

- Full repository suite: 3,372 passed in 402.07s. Subsequent doctor text-rendering
  fix passed all five public-process success/error cases; no full-suite claim is
  extended to untested later behavior.
- Real native controller suite: 22 tests passed before the final text-rendering
  assertion; portable completion/readiness checks also pass.
- Ruff and UAT-package mypy passed; nonempty external Fettle scan passed before
  final qualification tooling. Repeat quality checks before final checkpoint.
- Fresh wheel installed with isolated `python -I` imports from site-packages;
  `pip check` passed. The earlier audit wheel was not reused.
- Reproducible installed doctor/run/report/canonical qualification:
  [runner](../evals/uat_cli_controller.py),
  [sanitized observations and wheel identity](uat/cli-controller-qualification.json).
  Actual success is `pass`, seeded wrong output is `violation`, denied write is
  `unknown`, and forged report content is rejected for every case.
- Raw runtime receipts are controller-local; the checked-in sanitized qualification
  summary is reproducibility evidence, not a portable acceptance authority token.

Next boundary: define and qualify a network-capable, separately isolated execution
environment before API/browser/stateful or unrestricted-agent acceptance. The
current deny-network/read-only policy must not be weakened to declare those
surfaces supported. Initial local inventory had no Docker or bubblewrap executable;
the operator subsequently authorized container provisioning below.
No commit, push, merge, release, benchmark graduation or human parity is claimed.

### Container Follow-On: Trust Resolved (2026-09-21)

- Operator selected local container provisioning and confirmed installation.
  Installed Colima 0.10.3, Docker CLI 29.8.1 and Lima 2.2.0 through Homebrew.
  Homebrew also performed its default cleanup of old caches/unused versions;
  this side effect was disclosed. Disable automatic cleanup on further installs.
- Created profile `fettle-uat`: Apple virtualization, 2 CPUs, 4 GiB RAM, 20 GiB
  data disk, no host mounts, no SSH-agent forwarding, no SSH-config modification,
  no automatic default-context change, no port forwarding or login service.
  Runtime mount inspection reported no virtiofs/9p/sshfs mounts; Docker's current
  context remained `default`. Daemon reported AppArmor and built-in seccomp.
- The first public image pull failed at Docker Hub authentication with
  `x509: certificate signed by unknown authority`. Host curl completed TLS
  validation against the same endpoint (HTTP 405 for HEAD); VM trust is unresolved.
  No image or container was created. No TLS verification bypass was used.
- Operator asked the agent to discover the existing approved CA. Host curl used
  an existing CA bundle; independent System-keychain inspection found the proxy
  issuer and its root, with the root present in administrator trust settings.
  Exported only public certificates from that keychain, not from the endpoint.
  Verified root CA constraints, validity through September 2040, proxy chain,
  and an exact SHA-256 match between the export and keychain record.
- Root certificate SHA-256:
  `54CF95398E8B319283E3BB8B2E75D36F23BD6F47F3D3E05AA4A826AA4121A5E2`.
  Host curl validated Docker Hub with that root explicitly selected. Installed
  only this root in profile `fettle-uat` at
  `/usr/local/share/ca-certificates/fettle-corp-prj-root-ca.crt`, updated the
  guest CA bundle and restarted the idle Docker daemon. Guest fingerprint matched.
  No host trust changes, private-key access, or TLS verification bypass occurred.
- Verified pull of `alpine:3.23` succeeded, resolving the trust blocker. Pin future
  probes to `docker.io/library/alpine@sha256:85fe1e81d6758c208f3e1eed4338a1997e19d4be002d4dd32d3100c9a8c010a0`.
  The previous work claim remains released; no login service is enabled.
- Next: qualify non-root/read-only/drop-capability/network isolation before adding
  API/browser/stateful drivers. Provisioning and image acquisition are not
  transport acceptance.

Final checkpoint quality: Ruff clean, mypy clean for nine UAT source files,
external nonempty Fettle scan clean, and seven existing completion records valid.
None of those existing completion records asserts this repair program complete.

### Isolated API, Browser And Restart Checkpoint (2026-09-21)

Implemented in `fettle/uat/network_controller.py`, routed through the existing
approved-contract doctor/run/report flow. Version 1 CLI contracts are unchanged.
Version 2 supports deterministic API and browser actions with no agent launch.

- [x] Real container boundary: 25 checks pass. Non-root product/observer, no host
  mounts or Docker socket, read-only rootfs, dropped capabilities, seccomp,
  no-new-privileges, memory/CPU/PID limits, isolated internal bridge without gateway
  or default route, local HTTP positive and external TCP/DNS negative.
  [Runner](../evals/uat_container_boundary.py) and
  [observations](uat/container-boundary-qualification.json).
- [x] API: exact status/body assertions, no redirect following, bounded UTF-8
  responses and scenario deadlines, independent trusted collector, changed source
  rejected before Docker creation. Product bytes uploaded to a read-only source
  volume must match the frozen inventory digests.
- [x] Browser: real Chromium with its sandbox enabled; label/role-based
  goto/fill/click/text steps at desktop/mobile viewport sizes. Service workers and
  downloads disabled; requests restricted to product origin. A version-pinned
  official seccomp profile plus a `chroot` allowance supports Chromium's nested
  sandbox without granting capabilities or disabling AppArmor. The exact effective
  profile digest is checked before execution.
  [Capability probe](../evals/uat_browser_boundary.py),
  [offline Dockerfile](../evals/uat-browser-runtime.Dockerfile), and
  [probe evidence](uat/browser-boundary-qualification.json).
- [x] Stateful restart: bounded 16 MiB session-state tmpfs volume at `/state`;
  separate read-only networkless keeper preserves its mount through restart.
  Actual changed startup identity plus post-restart state read are required.
  Seeded state loss contradicts the oracle. State is intentionally removed after
  the session, not persisted into future sessions.
- [x] Interrupted collector/cleanup-failure injections remain non-pass and cannot
  reuse an earlier success; fresh complete rerun recovers with a new session ID.
- [x] Installed native Codex smoke trial via `get_uat_runner("codex")`: actual
  read-only/on-request invocation returned exit 0 in 21.6 seconds and the requested
  `fettle-native-readonly-ok` output. No elevation was requested. The trial ran in
  a disposable repository and did not inspect credentials, Docker or controller
  storage. This is a runner smoke result, not a canonical acceptance observation
  or qualification of native-agent approval recovery/defect discovery.
- [x] Installed public qualification: 12 fixed network cases, all expected states
  matched; five seeded contradictions detected; zero false passes. Nine of twelve
  scenarios have behavioral observations; overflow, timeout and missing-control
  controls remain unknown. Canonical calibration must not pass with 75% coverage.
  [Installed runner](../evals/uat_cli_controller.py) and
  [network evidence](uat/network-controller-qualification.json).
- [x] Full regression checkpoint: 3,398 tests passed with Docker tests enabled.
  Later source-byte binding and calibration-predicate edits have focused passing
  tests; the earlier full run is not represented as covering those later edits.

#### Contract And Runtime Scope

Use `fettle uat doctor --contract contract.json --approve-contract sha256:...`,
then `fettle uat run --surface api --contract contract.json
--approve-contract sha256:... --yes --json`, then the existing report command.
For browser contracts select `--surface web`. The contract surface must match.
Doctor checks availability, not successful behavioral acceptance. Report validation
requires the same local runtime/context and retained receipts; an offline VM is a
non-pass prerequisite failure, not portable offline acceptance.

Version-2 top-level fields are `schema_version`, `scenario_digest`, `surface`,
`runtime_image`, `context`, `product` and `actions`, plus `browser` for web.
`product` contains a `/product/` Python script `argv` and port 1024-65535.
The qualified Python image is the immutable `IMAGE` constant in the controller;
arbitrary images, languages, external services and credentials are unsupported.
Each action has `scenario_id`, `timeout_s` and `steps`. API steps have `method`,
product-relative `path`, UTF-8 `body`, and `expect: {status_code, body}`. An explicit
`{restart: true}` step restarts the product and requires subsequent behavioral
evidence. Browser settings bind the qualified local image, absolute verified
`seccomp_path` and fixed `viewport: {width, height}`. Browser steps are:
`{op: goto, path}`, `{op: fill, label, value}`, `{op: click, role, name}`, and
`{op: text, role, name, expect}`. Every browser scenario needs a text assertion.
Each group after restart has a fresh browser context; login/cookie persistence
across browser contexts is not supported by this version.

Trusted source staging runs networkless with container UID 0, no capabilities and
only its disposable source volume writable. Product and observer remain non-root.
The Docker daemon, VM kernel, pinned images and controller are trusted. This is
not a container-escape proof or protection from an unrestricted host/daemon actor.

#### Remaining Non-Pass Gates

- Browser audits now retain viewport PNGs, bounded isolated-world axe WCAG A/AA
  diagnostics and page/console/network failures. Add `{op: audit, expect: ...}`
  after browser actions, with all six lists empty: `page_errors`, `console_errors`,
  `failed_requests`, `http_errors`, `accessibility_violations`, and
  `accessibility_incomplete`. One audit per scenario, at most eight per receipt,
  PNG at most 512 KiB. Single-frame synthetic pages only; screenshots do not
  establish visual correctness, and axe does not establish complete accessibility.
- Twelve developmental fixtures remain conformance, with three expected unknowns
  excluded from behavioral coverage. A separate independently authored frozen
  twelve-case API corpus passed one installed-wheel trial with full observations
  and zero false verdicts. This establishes bounded deterministic API calibration,
  not native-agent discovery, human parity or enforcement graduation. See
  [held-out evidence](uat/heldout-controller-qualification.json).
- Native agent approval/recovery remains unqualified. Nested-container Bubblewrap
  was blocked without a policy bypass. A separate pinned plain Debian Lima VM
  now passes native read-only execution and denied-write checks without host
  mounts, Docker socket or credential forwarding. Direct sign-in is complete.
  Authenticated execution and fresh-session recovery after a real timeout passed.
  The installed action-proposal bridge passed three CLI fixtures and rejected
  oracle injection. A later recorded interactive trial shows the exact command
  permission prompt and operator cancellation; independent checks confirmed no
  file creation, and fresh-session command execution succeeded. The TUI also
  printed an ambiguous `Ran ... (no output)` line after cancellation, so structured
  denial classification remains non-pass, not inferred from prose or exit 0.
  Independent native defect discovery remains open. See the latest worklog for
  recording identity and limits. This is not an autonomous scenario generator.
- Actual controller SIGKILL followed by dedicated VM stop/start now passes
  non-pass reporting, inherited-client lease exclusion, daemon-bound ownership
  cleanup, unrelated-resource preservation and fresh-run recovery tests. This is
  not physical host power-loss durability or arbitrary VM/daemon migration.
- No new commit, push, merge, release or enforcement promotion. Existing seven
  completion records do not cover this program.

### Ordered Discovery Study

The next slice is evaluation-only requirements-derived CLI input discovery in
`evals/uat_cli_controller.py`, reusing installed doctor/run/report and canonical
receipt validation. No production permissions or acceptance semantics change.
Native agents select up to 12 inputs from requirements; a digest-approved finite
integer-range policy, not model output, computes exact oracles. All product
variants share the same selected input set; seed/source metadata stays private
to the evaluator. Malformed proposals, missing evidence and missed defects fail.
The UX/BDD contract is in `uat-acceptance-integrity.ux-spec.md`; no visual design
or new public command manifest entry applies.

Sequence: parser/oracle fixtures and rejection checks; developmental installed
study; independently authored frozen corpus; one exact-candidate held-out run;
review and completion evidence. Record native transcript identity, corpus and
wheel digests, actual observations and false-pass/blocked/missed-defect counts.
Preserve output before starting paid work; no held-out iteration. This slice is
bounded input selection, not arbitrary scenario generation or adaptive discovery.
Production discovery and structured native denial evidence remain separate gates.

Study checkpoint: the independently frozen two-suite corpus ran once against the
installed wheel and recorded evaluator identity. It matched all 12 expected states:
8/8 defects discovered, two healthy passes, two timeout unknowns, zero false passes,
false alarms or missed defects. All 144 observations were retained. See
[qualification](uat/native-discovery-qualification.json) and
[independent provenance](uat/native-discovery-corpus-provenance.md).
This consumed corpus must not be rerun as held-out or used to tune the candidate.
The result establishes synthetic range-classifier input selection only, not broad
production discovery. Separately, reading the prior denial thread via the native
structured API returned an interrupted turn with no command items; the structured
denial criterion remains non-pass. Future approval qualification needs live event
correlation rather than repeated uninstrumented operator trials.

September 22 verification: 3,411 tests passed, including Docker and real VM
restart; subsequent installed CLI3/network12 and independently frozen API12
qualification ran against the same implementation. The
[worklog](audit-hardening-worklog.md) records identities, limits and the native
runtime blocker. Earlier historical checkpoints below are not current status.

Later authenticated-native checkpoint: 3,427 tests passed, including Docker and
real VM restart. Use `uat run --proposal proposal.json --contract contract.json
--approve-contract sha256:... --yes` for action-only JSON produced outside the
controller. The proposal must match all approved actions exactly, with `expect`
fields omitted; it cannot change the approved oracle or grant permissions.
[Installed native proposal evidence](uat/native-proposal-qualification.json)
records the bounded three-case bridge qualification and candidate wheel digest.
The older independently held-out API qualification was not rerun and must not be
represented as qualification of this later wheel.

### Final Safety-Migration Verification

2026-09-20 local checks (no commit, push, merge or release):

```sh
python -m pytest tests/ -q
# 3343 passed in 359.68s
mypy --follow-imports=silent --cache-dir "$TMPDIR/fettle-uat-mypy" \
  fettle/uat fettle/runners/__init__.py fettle/spec_model.py
# Success: no issues found in 10 source files
python3 ~/.claude/plugins/fettle/scripts/cli.py check --changed
# No issues found; changed Python files present
python -m fettle completion validate
# Seven existing records validate; none establishes this program complete
git diff --check
# Clean
```

Commands used the existing Python 3.12 audit environment and Command Line Tools
Git. Ruff passed for all edited Python files. The optional wider type scan of
the entire CLI exposed pre-existing errors outside this repair; no whole-CLI
type-clean claim is made. Native host flag syntax was checked against installed
help, not substituted for live runtime approval tests.

The next implementation boundary is explicit: define the trusted capture
controller and requirement-oracle contract before allowing any positive UAT
decision. Running more model sessions against the old claim channel cannot close
that gap. Human baseline collection is not a prerequisite to implementing this
requirement-based channel; it is necessary only for a separate human-parity claim.
