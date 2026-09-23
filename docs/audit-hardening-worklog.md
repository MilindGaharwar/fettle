# Audit Hardening Worklog

## 2026-09-22: Remote Checkpoint Dependency Repair

Signed-off checkpoints `235c176` and `c8e80a2` were pushed with all commit and
pre-push hooks enabled. CI run `35729628089` passed on `c8e80a2`. Mutation run
`35729628122` failed: all 11 unsuccessful replay reports retained a `tool_error`
because the missing-browser unit test imported Playwright while constructing its
mock, but the pinned mutation environment does not install that package. This
was a baseline-test setup failure, not a valid mutation score. The failed run
remains non-pass; no historical qualification result is replaced.

The test now supplies a fake Playwright API through `sys.modules` and verifies
the factory was called, so an unavailable package cannot accidentally satisfy
the missing-executable assertion. No production behavior or workflow dependency
policy changed. All 26 surface tests passed; the controller/surface mapping
passed 101 tests with Playwright imports explicitly unavailable (20 runtime
opt-ins skipped). Fresh verification of the repaired checkpoint remains required.

Follow-up on 2026-09-23: the mistakenly repository-wide local preflight hit its
1,800-second limit and remains `tool_error`, not a pass. Its raw cache and the
working diff were preserved before further work. The replacement check used a
disposable checkout, Python 3.12, mutmut 2.5.1 and the pinned whatthepatch 1.0.7,
restricted to `_playwright_available` with 120-second preflight and 300-second
replay limits. Initial preflight completed in 0.82 seconds. Narrow replay exposed
an uncovered missing-package return; an explicit unavailable-import regression
now covers it. Final surface tests: 27 passed. Final narrow replay: one mutant
killed, zero survivors/timeouts/untested outcomes, completed in 1.73 seconds.
This is scoped developmental evidence, not a replacement full qualification.
Unrelated executable-bit changes were left untouched and excluded from the repair.

## 2026-09-22: Checkpoint Review And Full Verification

Operator authorized review, verification and checkpoint commits/push on the
existing review branch. Merge, tag, release and enforcement promotion remain
separate decisions. The accumulated implementation, tests and evaluator form
one runnable checkpoint; documentation and frozen historical evidence follow
separately. Runtime/controller and browser/recovery tests are coupled, and the
runner tests import the evaluator, so finer file-level commits would be incomplete.

Review found a failed judgment subprocess could return valid empty-findings JSON
and be classified completed when `run.error` was empty. A regression reproduced
exit 7 becoming completed. Judgment now requires exit 0 as well as no transport
error; all 39 reconciliation tests passed after repair. The public privacy audit
also found three host-specific paths in unpublished acceptance notes; replaced
their prefixes with `$TMPDIR`, preserving artifact names and results. Generated
mypy caches were moved outside the source tree without changing the audit policy.

Final combined-tree verification: **3,466 tests passed in 508.40 seconds**, with
Docker and real VM-restart opt-ins enabled and no skips. Repository-wide Ruff,
CI blocking trust-boundary mypy, focused UAT/evaluator mypy, config validation,
evaluation-schema validation, rule provenance, privacy audit, Fettle changed-file
scan and whitespace checks all passed. The Docker suite left no containers or
volumes. Commit hooks and fresh remote CI must still pass before push completion
is claimed. Existing seven completion records do not establish this UAT program.

No held-out trial was rerun. The review repair changes the report-producer bytes;
previous installed-wheel studies remain historical evidence tied to their exact
wheel/evaluator identities, not qualification of the repaired checkout. Remaining
limits include local digest-pinned browser provisioning, trusted runtime/daemon,
buffered Docker/native subprocess output before size checks, heuristic screenshot
secret screening, missing structured native refusal evidence and nongeneralized
discovery. This is a reviewed development checkpoint, not a release declaration.

## 2026-09-22: Structured Read And Native Input Discovery

Investigated the exact interactive-denial thread through the pinned Codex 0.155.1
local app-server `thread/read` API, not by opening credential or session files.
The bounded temporary probe sent only initialize/initialized/read requests; it
neither resumed the agent nor answered permissions. Thread
`01a0c7f3-54b6-79c0-aa52-b9dc9916f643` returned turn
`01a0c7f3-5531-7ba3-b84b-190bb951d718` as `interrupted` with no command items.
Response SHA-256: `9f3c7a3ded88e85c88df00e499d8625af0afc888a49f1449e301b6433e0213fb`.
Although the pinned protocol defines `declined`, this saved trial does not retain
it. The TUI refusal and absent side effect remain verified, but structured denial
is still non-pass. No further manual retry was requested. A future trial needs
live request/decision correlation, not another uninstrumented TUI recording.

Added evaluation-only native input discovery to `evals/uat_cli_controller.py`.
The agent receives only written requirements and a one-string CLI interface. It
selects up to 12 distinct, bounded inputs; no source, seeded defects or expected
verdicts are supplied. Exact output expectations come from a separately reviewed,
digest-approved integer-range policy. Existing installed doctor/run/report and
canonical validation execute and judge each selected probe. Native tool attempts,
malformed/duplicate fields, invalid proposals and incomplete output fail closed.
All installed Python module bytes must match the supplied wheel. Output is
exclusively reserved before native execution, partial progress stays non-pass,
and reruns cannot overwrite a consumed trial. Native transport still buffers
output before its size check; the subprocess deadline remains the resource bound.

Developmental study: four expected states matched, including two detected defects
and one blocked write. This was not held-out evidence. Focused runner tests:
78 passed; Ruff and focused evaluator mypy passed. Adjacent preflight: 159 passed,
20 opt-in Docker/VM-restart tests skipped, Fettle clean. Those skipped gates were
not newly verified; prior full-suite evidence belongs to its earlier checkpoint.
The available `kgraph impact FILE` graph was stale and treated as advisory only.

An independently delegated author produced two suites and twelve variants without
reading implementation, candidate prompts, developmental cases or selected inputs.
The author disclosed inherited platform context and static-only fixture checks in
[provenance](uat/native-discovery-corpus-provenance.md). The main agent reviewed
source safety and requirement/oracle consistency before executing the frozen corpus
once, sequentially, with no prompt/corpus tuning or retries.

- Corpus SHA-256: `6067cee014a6e86dd529d630d687e1e730ba866e4a35d13903022ba3016d6b37`.
- Evaluator SHA-256: `249514a3f4fe14843703b8d6a89f8f88fb9f0337ad60ab90a4b3a5d01c02961a`.
- Installed wheel SHA-256: `3118991c1c9a3d231c663ffdad44c1ea24420dacc1638593b5cd42474032b29b`.
- Result: 12/12 expected states, 8/8 defects discovered, two healthy passes,
  two timeouts retained as unknown, zero false passes/alarms/missed defects.
- Retained 144 observations and both native-selected input lists in
  [qualification](uat/native-discovery-qualification.json). These sanitized records
  are not portable canonical authority; canonical validation occurred in the live
  isolated evaluation before temporary products and receipts were cleaned up.

The study qualifies bounded requirements-derived input selection for synthetic
range classifiers, not adaptive exploration, arbitrary oracle synthesis, a new
production discovery command, human parity or enforcement promotion. Production
implementation was unchanged in this slice. `fettle completion validate` passed
the seven existing records, none of which covers this UAT program. Structured
native denial and general discovery remain open. No commit/push/release authorized.

## 2026-09-22: Interactive Permission Refusal

The operator directly declined the exact command permission request for
`/usr/bin/touch /tmp/fettle-native-interactive-denial` in the isolated native VM.
The output-only recording shows the native approval menu, selection of
`No, and tell Codex what to do differently`, and `You canceled the request`.
The session was interrupted and the operator exited with `/quit`. Independent
checks found the target absent both afterward and after fresh-session recovery.
No approval was automatically answered, and no credential files were accessed.

Recording: `/home/lima.guest/native-denial-output.t6XcMelH`, 38,597 bytes,
2026-09-22 07:10:05 through 07:10:32 UTC, recorder command exit 0. SHA-256:
`fe54f204d818201a3512f56c291836cec62c8f62c7df4a526810139e4d897db6`.
An output-only copy is retained in the host session temporary directory.
The recording also displays `Ran ... (no output)` after cancellation. This is
conflicting UI evidence, not proof that the command executed or that a structured
denial event was captured. The verified scope is the displayed permission request,
operator refusal, absent side effect and successful fresh-session recovery;
machine-verifiable denial classification remains non-pass pending unambiguous
native event evidence. No overall UAT or enforcement graduation is inferred.

Fresh recovery session `01a0c7f4-757a-71f0-82a9-9f35a1cf948c` retained normal
on-request approval and read-only sandbox settings. Its completed command event
reported `/usr/bin/printf fettle-after-interactive-denial-ok`, exact output,
exit 0 and `turn.completed`. The synthetic denied-write target remained absent.

Two setup attempts are not counted as command-denial evidence: the first recorder
stopped on terminal access because GNU timeout created a background process group
(fixed with `--foreground` and a real terminal probe); the second ended when the
operator declined the initial directory-trust prompt. The empty test directory
was checked before the operator explicitly trusted it in the final trial.
No application code changed in this verification step, and no held-out corpus
was rerun. Independent native defect discovery remains unqualified.

## 2026-09-22: Authenticated Native Proposal Bridge

Operator completed direct device authentication. Status independently reported
`Logged in using ChatGPT`; no credentials were read or copied. Authenticated
Codex in `fettle-native` executed the exact printf smoke with a completed command
event and exit 0. A read-only write-denial attempt left the synthetic target
absent, but its JSON stream contained only denial prose, not a command event.
That native denial evidence remains incomplete; it is not promoted to a pass.
Fresh-session printf subsequently succeeded. A separate actual one-second
interruption exited 124 with no terminal success; a new session then executed
host-source/controller-path/Docker-socket absence tests with command exit 0.
No permission request was auto-answered or bypassed. These absence probes are
not a general network attack or VM escape qualification.

Added optional `fettle uat run --proposal <json>` on the existing approved-contract
path. The untrusted proposal must exactly match action order, scenario digest,
coverage, arguments/steps and timeouts, excluding expected-output oracles. Duplicate
fields, malformed/oversized/symlink files, boolean substitution, missing coverage,
command replacement and oracle injection reject before capture. Proposals cannot
approve contracts or become acceptance evidence. JSON format is
`{schema_version: 1, scenario_digest: ..., actions: [...]}`; action/step `expect`
fields stay solely in the separately approved contract. This gate checks matching
actions, not native authorship, and does not introduce an automatic agent launcher.

Extended the installed evaluator to obtain action-only JSON over stdin from the
separate signed-in VM, with on-request approval, read-only sandbox, ephemeral
sessions and bounded execution. No product source, expected outputs or controller
receipts are sent to the agent. Three installed cases passed through public
CLI/run/report/canonical validation: success, seeded contradiction and sandbox
write blocked as unknown. Each case also rejected injected oracle fields before
execution; forged reports remained non-pass. Native transcript hashes identify
transport output, not independent product evidence. See
[native bridge qualification](uat/native-proposal-qualification.json).

Wheel SHA-256 `3118991c1c9a3d231c663ffdad44c1ea24420dacc1638593b5cd42474032b29b`.
Focused runner/controller tests: 72 passed. Full current suite including Docker
and real VM restart: **3,427 passed in 489.24 seconds**. Editor diagnostics clean;
Ruff and focused controller/evaluator mypy passed. `kgraph` unavailable in PATH.
Earlier independently held-out API corpus was not rerun or tuned; its evidence
belongs to its recorded older wheel, not this updated candidate.

Remaining: interactive native approval/denial event capture and independently
authored end-to-end native defect-discovery trials. The bridge only echoes approved
actions, so it is not autonomous scenario discovery or broad native UAT completion.
No commit, push, release or promotion authorization. Authentication remains only
on the dedicated VM disk; stop VMs at checkpoint without removing that state.

## 2026-09-22: Plain Native VM Prerequisite

Operator authorized autonomous continuation until direct authentication or a
genuine blocker. Created a separate Lima 2.2.0 `fettle-native` plain VZ VM:
2 CPUs, 4 GiB RAM, 12 GiB disk. Debian 13 ARM64 image dated 20260712-2537,
SHA-512 `8543d795f2fde630eb66c492f245a8c1da19dedc636e0a8e7b3d0f95920e1a05aa911ef2d82d177d41cc53ced5fccbd2a3945d07fa5e15018914c4d864bb07ed`.
Removed floating-image fallbacks. No host mounts, application port forwarding,
containerd, Docker socket, SSH-agent or X11 forwarding. Lima's management SSH
remains host-initiated over vsock. Guest mount inspection confirmed no shared
host filesystem; controller receipts stay outside the VM. The VM has outbound
networking for authentication/provider access; this is not an egress-isolation
claim. The controller's Colima VM remains stopped.

Transferred only the previously verified Codex 0.155.1 archive and public CA.
Guest binary SHA-256 matches
`298d3d73d0bbc1367e58a370df5b6216fe30ce0a92e8b6b0afb0377a958dc335`.
This Linux build uses `codex sandbox <command>`, not `sandbox linux <command>`.
With on-request approvals and read-only sandbox, printf succeeded and touch in
`/tmp` failed with `Read-only file system`; the target remained absent. No kernel,
AppArmor, seccomp, elevated-capability or native sandbox bypass was needed.
This resolves the nested-container prerequisite blocker, not agent integration.

Public CA fingerprint matches the previously approved host trust root. TLS
verification to `auth.openai.com` returned verify result 0; its root URL returned
HTTP 403, so device authentication availability is not yet established.
`codex login status` returned `Not logged in`. Native state is private to
`/home/lima.guest/native-state`. No existing credentials were copied or read.

**Pending operator action:** direct device sign-in in the dedicated VM. Leave
credentials and device codes outside chat. VM is intentionally running for this
step. Authenticated proposals, approval-denial/recovery, evidence-access attacks
and independent native qualification remain unverified. No shipping authorized.

## 2026-09-22: Recovery, Browser Audit And Independent Qualification

Implemented external atomic resource journals and exclusive per-product leases.
Docker clients inherit the lease, ownership is recorded before create, and
recovery requires both journaled names and owner labels on the original daemon
and socket. Acquired reruns invalidate prior acceptance before recovery; rejected
concurrent runs leave the active checkpoint alone. Cleanup is verified before
publishing receipts. Actual controller SIGKILL, surviving-client exclusion,
Colima stop/start, orphan cleanup, unrelated-volume preservation and fresh
acceptance passed. Recovery is a full new run, never partial-evidence merging.

Opt-in browser audits now retain bounded viewport PNGs, axe-core 4.10.3 WCAG A/AA
violations/incomplete checks, page/console errors and failed/error HTTP requests.
Axe runs in an isolated JavaScript world. Qualified offline observer image:
`sha256:0b5a9b1dd96db0948671a77d0dee1fd17653c51c7bfc8133a6e6f343164e8e54`.
Desktop/mobile positive captures and seeded label/page/console/HTTP/external
request failures passed; retained PNGs were viewed, and altered screenshot
hashes rejected. Screenshots are evidence, not visual oracles; synthetic inputs
only, single-frame audit, heuristic secret screening, no comprehensive a11y claim.

Review found unreachable per-scenario assertion validation and a misplaced API
runtime return; both repaired with focused regressions before qualification.
Full current suite: **3,411 passed in 489.64 seconds**, Docker and dedicated VM
restart explicitly enabled. Installed wheel digest:
`sha256:1bc2d0b9d0e989ff0285232471bd04000037567979b15d083991b7ac7e419af0`.
Installed developmental CLI3/network12 controls matched expected states; the
three expected unknown network controls still prevent developmental calibration.

Operator explicitly authorized an independent evaluator. A separate agent,
without implementation/test access, authored and froze twelve API cases before
execution. Corpus SHA-256:
`c0109c3d8994fc9028cf955c2cc2857bff724f321c184215111bfd4570db484f`.
One installed-wheel trial: 12/12 expected states, 12/12 observed captures, zero
false passes/verdicts, canonical calibration passed; graduation remains false.
No retries or tuning on held-out outcomes. See the
[retained trial](uat/heldout-controller-qualification.json). This is independent
deterministic API qualification, not native-agent discovery or human parity.

Operator also authorized a dedicated native runtime and normal separate sign-in.
Built Codex 0.155.1 Linux ARM64 from npm-integrity-verified bytes, image
`sha256:7620e39c31ce90e770490d86ce9c36dba71438e8c0c2c8e797368716453c274c`.
Before authentication, networkless native sandbox probe failed: default Docker
seccomp denied namespaces; the existing scoped namespace profile progressed to
`bwrap: Failed to make / slave: Operation not permitted`. Native integration is
**blocked**, not qualified. No credentials copied, sign-in started, Docker socket
or controller storage exposed, SYS_ADMIN granted, AppArmor/sysctl changed, or
sandbox/approval bypass used. A compatible separately isolated native host is
required before normal sign-in and approval/recovery qualification can proceed.

No commit, push, merge, release or enforcement promotion. Prior remote CI does
not cover these uncommitted changes. Seven existing completion records do not
establish completion of this program.

## 2026-09-21: Ordered Container And Network Acceptance

Operator authorized the four recommended steps in order. Container boundary
qualification passed 25 actual checks before API implementation. API contracts,
browser actions and stateful restart then ran through the controller receipt and
public report/canonical path. Full suite checkpoint: 3,398 passed with Docker
tests enabled. Later focused source-byte, deadline and calibration checks passed.

Browser startup initially failed under default seccomp. The version-matched
Playwright profile permitted namespace creation, then exposed a conditional
`chroot` denial. A digest-bound per-container syscall allowance resolved startup
with Chromium sandbox enabled, no added capabilities, and no VM-wide AppArmor
change. Initial restart lost tmpfs state; a read-only networkless keeper fixed the
mount lifecycle, verified by actual POST/restart/GET and seeded state-loss tests.

Fresh installed-wheel evaluation used isolated imports and actual CLI/API/web
flows. Twelve fixed network cases matched expected states, with five observed
seeded contradictions and zero false passes. Three deliberate blocked cases have
no successful behavioral observation: coverage is 9/12, not 100%. Corrected the
calibration predicate to require full observed coverage rather than treating
expected unknowns as calibration success. No parity or enforcement graduation.

Installed Codex runner smoke used Fettle's read-only/on-request arguments in a
disposable repository. Exit 0, 21.6 seconds, expected printf marker returned, no
elevation requested. Retained as smoke evidence only; it cannot substitute for
independent capture or native-agent approval/recovery qualification.

The [detailed checkpoint](uat-strength-plan.md) records reproducible tooling,
runtime identities, required contract fields and the remaining gates. No agent
was attached to the host controller store; native-agent isolated capture, browser
visual/accessibility breadth and hard-kill recovery remain unqualified. No current
changes have been committed or pushed; earlier remote CI is not current evidence.

## 2026-09-21: Container CA Recovery

Operator asked the agent to locate the approved CA rather than requiring manual
certificate details. Read-only inspection identified an existing administrator-
trusted root in the macOS System keychain. Its public export matched the keychain
SHA-256 fingerprint, had valid CA constraints, and verified the corporate proxy
chain. Explicit host TLS validation with that root succeeded.

Installed only that root into the task-owned `fettle-uat` VM and verified the guest
fingerprint. Docker Hub image acquisition then succeeded without weakening TLS.
The [UAT plan](uat-strength-plan.md) records the root fingerprint, guest path and
pinned image digest. Host trust was unchanged; no private keys were accessed.
API/browser/stateful transport and isolation qualification remain pending.

## 2026-09-21: Evidence Reconciliation

The September 19 pending CI and Codex entries below are historical. Candidate
`c83f3b455fca4b8c299c701324df322279837541` passed required CI run
`35426206197` and mutation run `35426206213`. PR #44 remains open; these results
do not cover the subsequent uncommitted UAT integrity repairs.

The isolated Codex retry observed an actual corrupt-policy denial followed by
successful marker execution after repair, using normal host trust and read-only
sandboxing. Denial thread: `01a0b8cf-56f3-7ae2-bc9c-e3e6be80e8fa`; recovery
thread: `01a0b8cf-b7f5-75f2-8d85-b031a0ab4858`. An initial fixture was valid TOML
and was excluded from failure-path evidence. The final candidate record is
retained in [PR #44's evidence addendum](https://github.com/MilindGaharwar/fettle/pull/44#issuecomment-5740531348).
This is host policy enforcement evidence, not qualification of the new UAT driver.

Human timing/accessibility acceptance remains deferred. AH07 is not declared
complete, and its dependent expansion packages remain gated. The public wheel
was not replaced by this work. The current authorized priority is the
[UAT integrity repair checklist](uat-strength-plan.md): independent observation
and requirement-based acceptance, not human-parity measurement.

The safety migration's last recorded full suite passed 3,343 tests; its final
documentation check passed six tests. Temporary raw UAT probe directories are
not durable acceptance records. Preserve sanitized controller observations and
their requirement bindings as part of the new capture path before graduation.

## 2026-09-19: Candidate Acceptance And Shipping

Operator requested all next steps in priority order, including commit and push
after verification. No tag, publication, new research experiment, or invented
human acceptance is authorized. The existing AH07 dependency still gates P2/P3.

- [x] Confirm worktree scope and acquire the audit-hardening claim.
- [x] Build today's wheel and sdist; retain hashes and source identity.
- [x] Install each artifact outside the checkout; verify import origins, provider
  inventory, help, demo, graph status, and harmless failure/recovery flows.
- [x] Obtain independent review; resolve findings with focused regressions.
- [x] Run candidate tests, Fettle, completion validation, and diff hygiene.
- [x] Commit verified changes and push through the protected-branch PR path.
- [ ] Watch exact-candidate remote CI to completion; see PR checks for final verdict.
- [x] Record live-host evidence and remaining human UAT prerequisites.
- [x] Reassess AH08-AH15 admission in dependency order; do not bypass missing gates.
- [ ] Finalize evidence and release the work claim.

Artifact hypothesis: explicit provider packaging and current dispatcher/config
code survive installation without editable-checkout leakage. Discriminating check:
clean wheel/sdist environments using isolated Python from a disposable committed
repository, with imported module paths required to reside in site-packages.

Evidence so far:
- Fresh wheel SHA-256: `7f6b528f8fef2d3cd7d2f0cde1b6ef555bed4da2234edb34a0f027cf10938f62`.
- Fresh sdist SHA-256: `45fa31b363ab7c0403075495005b0c0236a540546c640c7122aa8cd53baa093c`.
- Artifacts: `$TMPDIR/fettle-audit-sep19-artifacts`; build log:
  `$TMPDIR/fettle-audit-sep19-build.log`. Built from this pending audit diff.
- Separate new wheel/sdist environments pass `pip check`. Isolated imports
  resolve inside each environment's site-packages; all five providers, CLI help,
  demo, graph JSON, corrupt-policy Stop block and repaired-policy retry pass.
- Operator explicitly authorized a fresh read-only review subagent. Its review
  reports no blocking code findings. This is independent automated code review,
  not human UAT or platform execution. Reviewer claims about remote passes and
  release requirements were not supported and are not adopted: ordinary push CI
  includes required Windows and installed-wheel jobs; no release is necessary.
- Final candidate suite: 3,314 passed in 404.94s, combined branch-aware coverage
  75.28%, existing floor 65 passed. Reports: `$TMPDIR/fettle-audit-sep19-suite.log`
  and `$TMPDIR/fettle-audit-sep19-coverage.json`. Fettle, Ruff, seven-module mypy,
  existing completion records, plan validation and diff hygiene pass.
- Fresh installed-environment advisory scan initially reported two duplicate
  entries for pip 26.1.2 (CVE-2026-13346). Upgraded pip in both disposable artifact
  environments to 26.2.1; re-audit reports no known vulnerabilities and pip check
  passes. No project dependency was changed. Reports:
  `$TMPDIR/fettle-audit-sep19-advisories{,-fixed}.json`.
- Downloaded public PyPI 1.13.1 wheel SHA-256:
  `64876ed1a51c90bfa25c99e91fa91ded55aa1c9a834f5080383279845ce91945`.
  Its archive contains no `fettle/providers/` files, confirming the published
  omission. It is not the repaired candidate; no replacement was published.
- Host inventory: Claude Code 2.1.234, Codex 0.155.0-alpha.9, OpenCode 1.18.20.
  Gemini/Antigravity unavailable. Operator authorized bounded authenticated
  disposable host probes and explicitly deferred human acceptance. Human timing,
  accessibility observations and P77's ten human sessions remain missing.
  - Hardening commit: `229e224`. All commit and full pre-push hooks passed.
    Direct main push was rejected by branch protection; no bypass attempted.
    Operator explicitly authorized branch `audit/hardening-acceptance` and
    [PR #44](https://github.com/MilindGaharwar/fettle/pull/44), now published.
  - Initial scrub hook rejected generated coverage/mypy binary caches containing
    local paths. Moved only those generated caches outside the checkout and reran
    the enabled hook successfully. No source changes or hook suppression needed.

  ### Current Candidate Live-Host Evidence

  Both probes used the September 19 installed wheel, disposable repositories,
  90-second session bounds, and only the harmless command
  `printf FETTLE_AUDIT_MARKER`. No permission bypass or global settings edits.
  Host process exit 0 is not the oracle: actual tool-result events determine deny
  and allow. These probes cover PreToolUse policy failure/recovery, not every hook.

  | Host | Corrupt local policy | Repaired policy | Limit |
  |---|---|---|---|
  | Claude Code 2.1.234 | Tool error names unavailable policy and doctor/retry; no marker executed | Tool succeeds and emits marker | Explicit candidate hook settings, not global installed registration |
  | OpenCode 1.18.20 | Bash tool state error names unavailable policy | Bash tool completed, exit 0 and marker output | Candidate-generated project plugin; no global registration changes |
  | Codex 0.155.0-alpha.9 | Not run | Not run | Candidate hooks require operator review/trust through `/hooks`; bypass flag deliberately unused |
  | Gemini / Antigravity | Unavailable | Unavailable | Executables absent |

  Claude deny tool ID `toolu_01FND1AxWCBHYBEcSk4zFjcx`; recovery
  `toolu_01NcNRVWRwWuhSsQhXvtDvdn`. Total reported model cost approximately $0.118.
  OpenCode deny session `ses_f481c1920ffeJn3sRgezu1HL9B`; recovery
  `ses_f481c0641ffe9dBxQQEPoi6pbL`. Its harness cleanup raced with a late state
  write after both observed outcomes; subsequent process inspection found no probe
  process, only disposable state files. This cleanup failure is not a product pass.

  ### Remaining Priority Gates

  1. Required PR CI must be green for the exact candidate, including Windows ledger
    and installed Linux wheel. No merge or release is implied by branch publication.
  2. Codex candidate hook trust needs operator interaction. Human acceptance was
    explicitly deferred; the 30-second recovery target and P77 parity remain unknown.
  3. AH07 is consequently incomplete. AH08 branch ratchet and AH09 representative
    performance benchmark remain dependency-gated; existing measurements are retained,
    not promoted to acceptance. AH10 extraction lacks measured justification.
  4. AH11-AH14 still require their user evidence/design/research admission. The request
    to proceed does not supply absent human observations or frozen research budgets.
  5. Public 1.13.1 remains unrepaired until a separately authorized release; current
    artifact/host evidence is not substituted for public distribution acceptance.

## 2026-09-19: Dispatcher Continuation

- [x] Confirm prior worktree state and reacquire `audit-hardening` claim.
- [x] Reproduce registry failure under enforced/advisory and always-required policy.
- [x] Repair dispatch-level failure decisions; verify event-correct output and recovery.
- [x] Review compound policy associations against their owning gate semantics.
- [x] Run focused regressions, static checks, Fettle and completion validation.
- [x] Retain current evidence and unresolved admission criteria.
- [x] Release claim after final documentation validation.

Hypothesis: registry selection failure currently erases mandatory checks by replacing
the selected list with an empty list. Paired policy tests are the discriminating check.
Independent acceptance and the previously recorded external gates remain open.

Implementation evidence:
- Registry failure: five red tests, then all pass with required checks blocking
  and advisory-only selection failures reporting recovery without blocking.
- Configuration exceptions and malformed runtime structures: three event-family
  regressions and six malformed-shape regressions reproduced, then repaired.
- Compound quality gate: 12 blocking regressions plus 12 advisory controls;
  all 24 pass after event-sensitive required-execution metadata. Stop tests and
  PreToolUse plan/UX/CI bootstrap retain their existing blocking semantics.
- MCP trust enabled, delegated capsule present, and Stop import/contract guard
  now retain blocking policy when execution fails. Inactive guards stay optional.
- Config loader: optional keyword-only `strict` flag rejects corrupt local layers
  and unavailable explicit policy paths. Dispatcher opts in; diagnostic callers
  keep their existing permissive behavior. Default optional files may be absent.
- Focused config/failure tests: 89 passed. Dispatcher integration run before the
  loader follow-up: 195 passed. Seven-module mypy and whole-source Ruff pass.
- Pylance signature compatibility: all 154 call sites compatible. Runtime snippet
  tool has no editor interpreter; verified Python 3.12 terminal used instead.
- Real dispatcher process: corrupt policy exit 2 with `fettle doctor` recovery;
  repair the same policy, retry, exit 0. No real tool operation was executed.
- Required external Fettle changed scan passes. Full regression suite: 3,312
  passed in 358.11s; report `$TMPDIR/fettle-audit-continuation-suite.log`.
- AH04 follow-up: abrupt writer termination before writing and after durable
  flush both release the OS lock and retain the expected complete records. Both
  new tests pass; final ledger/assurance/config/failure subset: 147 passed.
- Windows CI now runs the exact seven concurrency, timeout and interruption tests
  after package installation and checks their exit explicitly. The seven tests
  pass on macOS; Windows execution remains pending remote CI, not inferred.
- Both CI and release now include the config owner in the same seven-module type
  gate. No new type errors; all source/test Ruff and editor diagnostics pass.
- Final required external Fettle scan passes; seven pre-existing completion
  records validate. No audit completion manifest or done status was fabricated.
- No production code changed after the 3,312-test run; the two added interruption
  tests and workflow wiring were validated separately afterward.

Current scope limits: strict loading applies to local layers consumed by the
dispatcher; remote-policy cache freshness and per-target directory policy routing
are not newly implemented. A policy changed between parent and legacy subprocess
loads is not covered by a snapshot binding. Those are distinct follow-up boundaries,
not evidence that required-check enforcement is universal.

This continuation does not refresh the 2026-09-18 wheel hashes: they describe the
earlier candidate, not today's source. New candidate artifact and remote platform
acceptance must bind to today's source before shipping. No commit, push, tag,
release, live authenticated host session, or human UAT evidence was produced.

## 2026-09-18: Implementation Session

Operator authorized starting and completing the planned activities. No automatic
commit, push, release, legal consent, or enforcement promotion is inferred.

### Execution Checklist

- [x] Recheck dirty worktree: only the four planning documents are modified/new.
- [x] Find working Git without system changes: Command Line Tools Git, with access
  to the linked worktree's external metadata, works; Xcode launcher remains blocked.
- [x] Identify supported Python 3.12.13; current 3.14 environment has no broken dependencies.
- [x] Claim work and provision isolated Python 3.12 verification tools; impact queried.
- [x] AH01 scanner: four red regressions -> structured scan owner -> 100 scanner/CLI tests pass.
- [x] AH02 Action: twelve red regressions -> scope/result validation -> 18 tests pass.
- [x] AH03 dispatcher: two red enforce cases, advisory preserved -> 70 dispatcher contract tests pass.
- [x] AH04 ledger: red controlled race -> OS serialization -> 52 ledger/assurance tests pass;
  independent-process and bounded timeout/retry tests also pass (3 selected).
- [x] AH05 packaging repair: inventory regression failed for providers; declaration
  repaired; 4 distribution tests and isolated wheel graph/demo smoke pass.
- [x] AH06 UAT: red class-membership regression -> preserve values -> all 23 session tests pass.
- [x] AH07 local verification: full tests, lint, Fettle, completion and limitations recorded.
- [ ] AH07 independent acceptance: reviewer, platform and live-host evidence remain missing.
- [ ] AH08-AH15: execute admitted measurements/discovery; retain external blockers.

Use `PATH=/Library/Developer/CommandLineTools/usr/bin:$PATH` for Git-backed checks.
Do not mistake sandbox failure to access the shared Git directory for missing Git.

Focused test success above records implementation progress, not full work-package
completion. Independent acceptance, platform limits, and criteria remain to be closed.
The explicit `policy_gates` association binds mode-controlled dispatcher checks to
existing policy; optional advisory checks retain fail-open behavior. Ledger locking
uses standard-library OS facilities without adding a runtime dependency.

### Retained Local Evidence

Verification environment: macOS 26.7 arm64, Python 3.12.13 in
`$TMPDIR/fettle-audit-py312`; Git 2.54.0 from Command Line Tools. Put the venv
first and CLT second on PATH: CLT also contains an older Python without tomllib.
No Xcode license was accepted. kgraph returned a stale, truncated impact view;
it was not treated as authoritative. The `audit-hardening` work item was claimed.

| Check | Observed result | Limit |
|---|---|---|
| Full `pytest tests/ -q --cov=fettle --cov-branch` | 3,260 passed in 389.56s | Before final directory-only Action guard; that guard has 21 passing focused tests |
| Whole-source Ruff | Pass | Local Ruff 0.16.8, CI pins 0.15.20 |
| Six-module mypy 2.3.0 | Pass | `--follow-imports=silent --ignore-missing-imports`; not whole-repo proof |
| External required Fettle `check --changed` | Pass, no issues | Initial old-interpreter attempt failed; corrected PATH succeeded |
| Workspace Fettle changed scan | Pass, 13 Python files, no findings/tool errors | Not a live-host acceptance verdict |
| `fettle completion validate` | Seven existing records validate | No audit completion record asserted |
| Scanner live missing/recovered tools | Exit 2 / exit 0, scope contains 7 Python files | Empty-tool venv required; PATH alone does not hide sibling tools |
| Action live whitespace/valid directory | Exit 2 / exit 0 | No GitHub-hosted run |
| Ledger concurrency | Independent processes, timeout/retry, append/rotate/anchor serialization pass | POSIX only; crash-durability and Windows acceptance open |
| Isolated wheel | Imports originate in site-packages; demo and graph status pass | Graph fixture needs a real HEAD commit, even with no source files |
| Dependency advisory lookup | No known vulnerabilities: 82 runtime and 119 audit packages; zero skips | Point-in-time advisory data, not proof of absence |

Full-suite coverage: 19,472/24,906 statements, 6,514/9,532 branches;
75.46% combined and 68.34% branch coverage. Selected combined coverage:
dispatcher 82.11%, ledger 89.09%, Action 92.31%, scanner 71.73%.
Subprocess coverage is not complete. Initial whole-repo mypy measured 178 errors
in 39 files before three local ledger annotations were repaired; it is not the
final debt count. No blanket type cleanup or speculative coverage-floor increase.

Temporary raw reports (not durable completion manifests):
`$TMPDIR/fettle-audit-final-suite.log`, `fettle-audit-coverage.json`,
`fettle-audit-mypy.log`, `fettle-audit-performance.json`,
`fettle-audit-dependencies.json`, `fettle-audit-wheel-advisories.json`.
Prefixes other than the first are also relative to `$TMPDIR`.

### Performance Observation

30 warm in-process dispatcher invocations per event, disposable local root,
all 30 returned 0 for each event. This measures caller elapsed time, not cold
process startup or a representative production policy. Sequential append uses
durable flushes and ends with a verified 1,000-record chain.

| Slice | p50 ms | p95 ms | p99 ms |
|---|---|---|---|
| PreToolUse Bash, harmless echo request | 66.916 | 70.264 | 70.933 |
| PostToolUse Read, missing fixture path | 63.592 | 69.164 | 69.448 |
| Ledger first 100 appends | 0.257 | 0.350 | 0.462 |
| Ledger last 100 appends | 1.797 | 1.968 | 3.761 |

No speedup, tail-latency SLO, absence of omissions, or benchmark completion is
inferred. Concurrent and slow-check benchmark accounting remains to be frozen.

### Recovery And Compatibility Notes

- Standalone scanner now returns 2 with structured tool errors when analysis
  fails; baseline updates do not overwrite evidence on that failure path.
- Action paths are shell-quoted existing directories, not files or glob patterns.
  Malformed results and partial multi-root failures exit 2 even in advisory mode.
- Selected enforced checks block on omitted, absent, unknown or failed results
  and suggest `fettle doctor` plus retry. Optional advisory behavior is retained.
- Artifact association uses the actual `artifact_integrity` policy key.
- Ledger lock contention has a bounded five-second timeout; retry after the
  holder completes. Reading also needs permission to create/open the lock file.
  Do not remove a live lock file or rewrite a suspect ledger to force success.
- UAT profile identity remains seeded metadata; values are no longer made unique
  by suffixes that break numeric/email/phone classes. No parity promotion claimed.

### Open Acceptance Gates

Historical September 18 state (superseded by the September 19 continuation):
AH03 remains partial: config-load and registry failures retain legacy fail-open
behavior; compound enabled-only quality gates and other policy associations need
review. No claim that every mandatory path is now covered. AH04 needs platform and
process-interruption evidence. AH07 needs an independent reviewer, not self-review
renamed as independence. AH08/AH09 have local baselines, not all ratchets/benchmarks.
AH10-AH15 decisions are recorded in the plan; blocked dependencies were not bypassed.
No human sessions, new held-out corpus, demand approval, remote CI, public wheel
identity, commit, push, release, or authenticated host session is fabricated.

### Final Local Checkpoint

- Final Action directory-root guard: all 21 Action tests pass. Pinned mypy 2.3.0
  for six critical modules, whole-source Ruff, and editor diagnostics pass.
- Required external Fettle changed scan passes. Workspace full source scan passes
  with 192 Python files, zero findings and zero tool errors. No `.fettle/rules/`
  or `.lint/semgrep/` project packs were present; no rule files were edited.
- Plan validator passes for 16 packages; local document links and `git diff --check`
  pass. Existing completion records validate; the audit work item remains open.
- Final wheel and sdist both rebuilt successfully after retrying sandboxed build
  dependency access with host access. Each was installed in a separate clean
  environment. Isolated imports, all five providers, demo, and graph status pass
  outside the checkout in a disposable committed repository.
- Final artifacts in `$TMPDIR/fettle-audit-final-artifacts`:
  wheel SHA-256 `bb5579e6f31d4cc0ff2390c82e9521e844871e603075cb07e4b7692b881ed344`;
  sdist SHA-256 `c64128840adab63b66fb64a12bb37d25dda16405b038e856eca379245e62df9a`.
- No commit, push, tag or release. Repository changes are retained for review.
  This is a partial implementation checkpoint, not completion of all 16 packages.

## 2026-09-18: Planning Session

Request: persist prioritized recommendations, detailed tasks, and work packages;
report readiness without beginning implementation.

### Session Checklist

- [x] Review local plan conventions, validator, ownership map, and program index.
- [x] Separate six reproduced findings from future opportunities and unverified areas.
- [x] Draft 16 prioritized packages with owners, dependencies, estimates, and acceptance.
- [x] Define immediate CLI UX states and Given/When/Then acceptance scenarios.
- [x] Persist plan and worklog; add program-index navigation.
- [x] Validate plan structure and local Markdown references.
- [x] Run required Fettle and completion checks; retain exact results below.
- [x] Prepare readiness handoff with environment/approval limits; implementation remains unstarted.

### Decisions And Constraints

- Documentation only; no behavior changes, new features, commits, or releases.
- Planning metadata lives in this worklog because session memory is empty and the
  active editor instruction prohibits creating new session-memory files.
- `fettle work claim audit-hardening-planning` failed: cannot resolve shared Git
  directory. Claim not acquired; do not treat documentation creation as a work claim.
- Git-dependent tests previously failed with exit 69 due to unaccepted Xcode license.
  Operator must resolve the legal/system prerequisite; agent does not accept terms.
- The earlier audit's fresh wheel build lacked setuptools; existing local v1.13.1
  artifact confirmed missing providers with isolated imports excluding site hooks.
- Keep existing advisory policy outside required-check repair; AH03 needs explicit
  review before tightening dispatcher failure semantics.
- Reuse roadmap ownership for UX, UAT parity, polyglot, and contextual research.
- No root FEATURES.md exists; proposed enhancements are inventoried in this plan
  and remain gated, rather than creating a competing product manifest.

### Audit Baseline (Historical, Not Fix Evidence)

- Whole-source Ruff passed; full Fettle scan passed for 192 files outside sandbox.
- Selected Git-independent suite: 79 passed. Broader tests blocked on Git/Xcode.
- Completion validation passed for existing registered milestones only.
- Isolated probes reproduced scanner false success, Action false success,
  enforce-mode deadline omission, duplicate ledger sequence, missing wheel providers,
  and class-invalid UAT values. Convert these probes to durable regressions per package.
- Live hosts, public wheel identity, dependency advisories, and remote CI were not audited.

### Planning Validation

- `python -m fettle.plan_validator docs/audit-hardening-implementation-plan.md`:
  PASS, 16 work packages with required verification methods.
- Local-reference check: PASS, all Markdown links and referenced test paths exist;
  all 16 package identifiers are unique.
- Editor diagnostics: no errors in the four edited Markdown files.
- Required external `python3 ~/.claude/plugins/fettle/scripts/cli.py check --changed`:
  exited successfully, reported no changed Python files. This is not documentation
  correctness evidence; the structural/link checks above supply that evidence.
- `python -m fettle completion validate`: PASS for the seven existing registered
  milestones. No new implementation milestone was marked complete.
- No application behavior changed, so no application test pass or UX execution is
  claimed for this planning session. Historical audit results remain separate above.
- Planning is ready for operator review. Implementation requires authorization;
  full Git-dependent acceptance remains blocked until AH00 resolves prerequisites.

### Next Session

After operator authorization, begin WP-AH00 and claim a real work item. Then execute
AH01's failing regression before changing the scanner owner. Do not mark a package
complete from prose or checkboxes; attach current criterion-specific evidence.