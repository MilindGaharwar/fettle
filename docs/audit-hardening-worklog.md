# Audit Hardening Worklog

## 2026-10-05: Durable AH03 Qualification And Independent Verification

Standing authorization covered one exact run-05 execution, separate read-only
artifact verification, independent automated review, checkpoint-boundary analysis,
and external-acceptance preparation. No commit, push, publication, remote job,
host reconfiguration, policy change, coverage-file relocation, waiver, release, or
Milestone B/C work occurred.

## 2026-10-05: Acceptance Reconciliation And Remediation Review

The owner-authorized independent automated reviewer inspected containment commit
`f52a9bcbada906672595ebe515d43c71f67227d4` and process-lifecycle commit
`3fe5a545fd410b079dde6971545d7acb1ce255ec` at tree
`5a38d01a2ddf92692d583ae0afc368b743ad64d5`. It accepted the PR containment
contract and the successful POSIX descendant-termination order, but demonstrated a
fail-closed defect: when `killpg` raises after the session leader exits, the wrapper
suppressed the error and could return success before a surviving descendant wrote
source. The bounded synthetic probe returned success and later observed `LATE`.

The scoped repair now preserves `ProcessLookupError` as the conclusive already-gone
case and raises a dedicated `OSError` for other process-tree termination failures.
Restoration verification still runs before the error is surfaced. A regression
with a delayed descendant and injected `PermissionError` passes, as do all ten
focused process-wrapper cases. Windows normal-leader-exit descendant termination
remains unverified and is not claimed; the existing test is POSIX-only.

Acceptance criteria were reconciled against the governing plan. The owner-authorized
automated reviewer replaces AH07 07.4's former human-reviewer requirement. No human
acceptance or human-usability validation occurred, and none is inferred. Real-
participant parity belongs to later WP-AH13/P77, not Milestone A. Public-PyPI canary
verification belongs to later WP-AH15 and the release contract; AH05 requires the
candidate-built wheel and sdist outside the checkout, which already have positive
local and remote Linux evidence.

A private composite archive was created without modifying the original run-05
files. It contains the original qualification package plus separate package-index,
verification, independent-review, and equivalence-review attestations. Fresh
extraction verified all 105 manifest entries, all 73 original package-index entries,
and the four recorded attestation digests. Local archive SHA-256:
`12e4cba87f5e13870851f3cff0b62a37882337f17c7099261d029f4b4b1ee7e9`;
manifest SHA-256:
`a2a3013f03451c4d3a75d855d3d2831fd97b205e05ca8351b76d351f4a03ddf5`.
It is private local evidence, not published portable evidence. Storage provider,
immutable object identifier, retention enforcement, authorized readers, and any
future publication/sanitization policy remain owner decisions.

An exact-remediation-head wheel was installed in a disposable environment outside
the checkout. Isolated-home registration and generated transport probes passed for
Claude Code, Codex, Gemini, and OpenCode without accessing normal configuration,
credentials, or paid models. Evidence SHA-256:
`cf249b4162522a8d259e75355ce19b53ea264220ee1f4f997c7a39394c31182f`.
This is installed-candidate registration/transport evidence, not live-host execution.
Claude Code 2.1.234 and OpenCode 2.0.20 are locally available, but a real session
would rely on existing authentication and may incur model cost, so none was run.
Codex and Gemini are absent from PATH; minimum access is an official disposable
installation plus an authorized no-cost authentication/provider path, or an
operator-run candidate-bound transcript.

The lifecycle repair changes `fettle/mutation_test.py`, a mutation infrastructure
owner outside run-05's AH03 mutation target and mapped tests. Run-05 remains
authoritative only for its original identity and is not relabelled. The minimum
real-engine evidence for this repair is one fresh, isolated, pinned-mutmut 2.5.1
preflight and narrow replay over the changed lifecycle ranges, with source bytes,
modes, residue, process state, command output, exit, manifest, and compatibility
identity retained. Use the existing 1,740-second worker limit; stop on timeout,
termination error, source drift, residue, malformed evidence, or identity mismatch.
That targeted evidence can validate the infrastructure repair, but the required PR
check remains unknown/non-pass until explicitly dispatched under its existing
contract. A full calibration is required only if target/mapped tests, mapping,
policy, dependencies/runtime, exclusions/selection, or equivalence assumptions
change. No mutation preflight, replay, calibration, or full matrix was launched.

### Run-05 execution

The durable worktree is
`external://local/audit-hardening/run-05`. Before execution,
the frozen hashes were rechecked:

- candidate identity: `e3f3ee0bfc72545367897cd06c801116a70ad0e34106a147d217cea9f88346b1`;
- plan: `72e8e317f353d1e0c5d2d5e7ee062610e54ab58fbef4dcef84fe02b629265230`;
- handoff controller: `f44075f6153cf545e269bea29b770ae74ac4208d70e4402fb58a49b4d03e2d12`;
- cache lifecycle: `a733d24fd6f9432b681fe9c8382af7b1a74b4e905f2e56180e31250880432da4`;
- copied closed preflight cache:
  `7c737bb81f4d7c42345b69127435c1dc19362b186bb2649ff2ff9e3db143da13`.

The exact `--verify-only` path again validated source, tests, modes, runtime,
dependencies, configuration, mappings, exclusions, policy, manifests, commands,
and all 299 fingerprints. The authorized controller then ran all seven partitions
once each, sequentially, and returned `completed=[0,1,2,3,4,5,6]` and
`fresh=true`. Partition populations were 42, 49, 54, 48, 45, 41, and 20.

### Separate read-only verification

An independently authored verifier outside run-05 read the frozen package without
modifying it. It verified every terminal digest, planned command, zero exit,
empty stderr, closed cache archive, partition assignment, compatibility identity,
source byte/mode restoration, Git revision, and absence of root cache residue. It
then used the repository's canonical `aggregate_shards` evaluator and reconciled
canonical fingerprints with the prior equivalence review.

Observed result:

| Outcome | Count |
|---|---:|
| Killed | 269 |
| Survived | 30 |
| Timeout | 0 |
| Suspicious | 0 |
| Untested | 0 |
| Skipped | 0 |
| Total | 299 |

The raw score is 90.0. The 30 survivor fingerprints exactly equal the 30 reviewed
equivalence fingerprints; neither set has an extra or missing fingerprint. This is
an observed reconciliation, not normalization to the earlier historical outcome.
The source was restored and no `.mutmut-cache` root residue remained.

External verification is retained at
`external://local/audit-hardening/run-05-verification`:

- verifier SHA-256: `6f0cc037f9c8ed68bae32d369f9fdd67d809ae94e7c5d5ab59409217ee424ecf`;
- report SHA-256: `863a5f85f9ffc7f418d01d1ca8b67da328d6559e8fa912db21cef2c5a6c280f7`;
- run-05 package index SHA-256:
  `e40174d4e517623076a2b404ee3a8759a421e545fadcc8d14d1d906f5fc16db8`
  over 73 files and 1,363,689 bytes;
- external verification index SHA-256:
  `dda3d4696e1833c5b0211b877eadf1d78f559c5192e8d15536a9c6bb859edc2a`.

AH03 is locally confirmed for this frozen identity. Run-05 does not resurrect or
replace the lost earlier package; that historical attempt remains unsupported.

### Independent automated review

Read-only reviewer session `ses_ef5f3739dffejfe55SkFud6wM8` found no concrete
AH03 dispatcher defect and independently reconstructed complete 299-fingerprint
coverage and exact survivor/equivalence reconciliation. The review is retained as
`verification-final/independent-review.md`, SHA-256
`4049a3d5876da52671f3259be2e61d7d8483e39d8b9e7b0c74c882000bc4b291`.
It is automated review, not human independence or AH07 completion.

The reviewer raised two high-severity acceptance findings. First, final aggregate
verification is external to the immutable run-05 package. This matches the
authorized design for a separate read-only verifier, but leaves repository-portable
resolution blocked until an immutable evidence channel is approved. Second, the
frozen candidate is the broader Milestone A working tree rather than an AH03-only
diff and includes existing `100755` to `100644` mode changes in
`fettle/cross_review.py` and `fettle/import_graph.py`. Those files are part of the
frozen identity. Restoring them or narrowing the candidate would change identity
and require requalification, so no change was made.

### Checkpoint boundary proposal — not implemented

The current completion evaluator already distinguishes complete (exit 0),
valid-incomplete (exit 1), and invalid (exit 2). The cycle is caused by consumers:
the pre-commit hook and every CI test-matrix leg invoke strict
`fettle completion validate`, so a valid incomplete checkpoint cannot be committed
or produce successful Linux/Windows acceptance evidence. The final `required` CI
job depends on the strict test matrix and therefore also fails.

Smallest proposed cycle-breaking patch:

1. Add `fettle completion validate --checkpoint`, preserving the same evaluator
   and output but returning success only for valid evidence (complete or honestly
   incomplete); invalid or contradictory evidence remains exit 2.
2. Change only the pre-commit completion hook and the ordinary CI matrix's
   completion step to use `--checkpoint`.
3. Keep a distinct strict completion job or required acceptance workflow for merge
   eligibility after external evidence is attached. Keep release workflow
   `fettle completion validate` strict.

Separate hardening, not needed to break the commit/CI cycle: change
`fettle/release_gate.py` to reject `not completion.complete`, not merely
`not completion.valid`. The release workflow is already strict later, but the
interactive tag guard currently permits valid-incomplete completion evidence.

Required regression cases for an approved patch:

- checkpoint accepts valid-incomplete and complete evidence;
- checkpoint rejects malformed, stale, missing, contradictory, and invalid evidence;
- default validation still returns 1 for valid-incomplete and 0 only for complete;
- CI Linux/Windows/platform jobs are not skipped solely due to honest incomplete state;
- the final required merge/acceptance job remains non-pass while incomplete;
- release gate and release workflow reject valid-incomplete evidence;
- invalid evidence cannot be converted into a checkpoint pass.

Any implementation changes CLI/tests/workflows and therefore changes candidate
identity. It does not invalidate run-05's dispatcher mutation inputs if those exact
source/test/config/dependency identities remain unchanged, but a new release
candidate must bind the historical AH03 evidence through an approved compatibility
and external-artifact channel. No policy patch was implemented.

### External acceptance preparation

Read-only capability checks found Claude Code 2.1.234, OpenCode 2.0.20, and
authenticated GitHub CLI 2.97.0 for `github.com/MilindGaharwar/fettle`. Codex and
Gemini are unavailable on PATH. No host session or remote job was launched.

Prepared procedures and evidence destinations:

| Requirement | Procedure after approval | Evidence destination |
|---|---|---|
| Linux installed artifact | Run the existing `linux-wheel` CI job: build the exact wheel in `python:3.12-slim`, install by pipx, run demo, isolated provider import, `fettle init`, and bridge validation | Immutable CI run/artifact IDs indexed under approved external evidence channel |
| Windows ledger/bridge | Run existing `windows-bridge`: install exact checkout into a fresh venv; run the selected ledger concurrency/interruption tests; demo; init/doctor; tamper and recover bridge | Immutable CI logs/artifacts plus exact commit and workflow digest |
| Live hosts | In disposable repositories with the installed candidate, run independent harmless corrupt-policy deny and repaired-policy allow probes for Claude Code, Codex CLI, Gemini CLI, and OpenCode; use actual tool events, not host process exit, as oracle | Per-host sanitized command/version/config/result/transcript digests; inaccessible hosts remain blocked |
| Remote CI | After an approved checkpoint commit and push, run ordinary PR CI and mutation workflows bound to the exact commit; retain run IDs, conclusions, logs/artifact digests, and required-job result | Approved external channel referenced by repository-relative digest index |

Current decision request is consolidated: approve the checkpoint/evidence-channel
design; decide whether automated review satisfies 07.4; disposition the broader
candidate and two mode changes; authorize a checkpoint commit/push and remote CI;
and provide or authorize Codex/Gemini plus any required live-host access. AH07 stays
blocked until those decisions and results exist.

## 2026-10-05: Cache-Lifecycle Correction Budget Exhausted

The clarified authorization allowed three evidence-driven corrections for the
pre-execution cache blocker. All three remained pre-execution and ran zero
mutants:

1. Run `...-02` validated the durable plan but the executor found the final
   preflight cache still at the root.
2. Run `...-03` revalidated the plan, then a broad process-text search falsely
   classified its parent shell as an active mutation writer because the shell
   command contained the lifecycle script source text.
3. Run `...-04` revalidated the plan and narrowed process parsing to executable
   and argv tokens, but the parent shell argv still contained the literal
   `-m fettle.mutation_test` from the embedded here-document. It was again
   conservatively rejected before cache archival or deletion.

The run-03 and run-04 root preflight caches remain untouched. No partition
subprocess was launched and no terminal mutation report exists. The correction
budget is exhausted. A further attempt needs authorization. The recommended
mechanical fix is either to exclude the lifecycle process's complete ancestor
PID chain from the writer check or to invoke the already-written lifecycle
script in a separate tool call whose parent argv does not embed its source.
Candidate and acceptance inputs do not need to change.

## 2026-10-05: Authorized Checkpoint Commit Blocked By Repository Gates

The scoped checkpoint staged only this worklog and the two audit-hardening
completion records. `git diff --cached --check` and the changed-file Fettle scan
passed. The normal commit invocation was then rejected by two hooks: the scrub
audit found absolute local paths in the staged historical audit records (and a
workspace `.coverage` binary), and the completion hook correctly rejected the
intentional AH03 non-pass and AH07 blocked verdicts. No hook was bypassed, no
commit was created, and no push was attempted. The staged audit records remain
separate from unrelated unstaged work.

## 2026-10-05: Durable Plan Validated; Execution Rejected Stale Preflight Cache

A second unique durable checkout was created at
`external://local/audit-hardening/run-02`. The corrected
`ah03-durable-harness-v2` used `os.open(..., os.O_RDONLY)`, `os.fsync(fd)`, and
guaranteed descriptor closure. It atomically finalized, file- and
directory-synced, and read-back verified the persistence probe and all critical
pre-execution artifacts. Harness SHA-256:
`67e18395a5689af9018f3383b7d9e5deaf3cead14c24999d0d32e9e52e22ebfb`.

Compatibility passed for source, tests, file modes, configuration inputs,
dependencies, Python 3.12.13 Darwin-arm64 runtime, mappings, configured
exclusions, and effective policy. The qualification aggregate identities equal
the authorized frozen identities. The newer local-acceptance identity includes
later documentation and completion-record edits; those files are not mutation
inputs and were not used to infer qualification compatibility. The exact
qualification identity SHA-256 is
`e3f3ee0bfc72545367897cd06c801116a70ad0e34106a147d217cea9f88346b1`.

Seven persisted manifests and per-manifest preflights were selectable and
assigned 42, 49, 54, 48, 45, 41, and 20 fingerprints. Their union was exactly
299, with no omissions, duplicates, or extras. Execution-plan SHA-256:
`70734b3a42f178a5551ad7b706e8aa7145cd59a71797957e9a3833eab3a6d9e8`.

The executor stopped before launching partition 0 because the final manifest
preflight had left `.mutmut-cache` at the checkout root. The executor's fresh
state guard classified it as stale and raised before invoking
`fettle.mutation_test`. The closed preflight cache was retained and read-back
verified at
`qualification-evidence/preexecution-failure/preflight-mutmut-cache.sqlite`,
SHA-256 `b82b270b774561e1c528efb0769b4cef8b5d4bf8d98b1151fb5c443a273fe999`.
No mutant executed and no terminal report exists. Source/test/input identities
remain exact and no mutation residue was found.

This is an unsuccessful pre-execution staging attempt, not a qualification
result. No automatic replacement mutation execution is authorized. The exact
recovery is to start in another unique durable directory, retain a snapshot of
the known preflight cache, remove that cache before partition execution, prove
the root execution state is fresh, and otherwise use the already validated
candidate and plan unchanged.

The authorized local checkpoint commit records documentation and completion
state only. Its parent is the frozen qualification revision
`4522a564791bce326ca4f340f7007f09e988b8e1`. The commit changes repository
revision identity but does not change the qualified production source, mapped
tests, mutation configuration inputs, dependencies, mappings, exclusions, or
policy. Historical qualification evidence remains bound to the detached frozen
candidate and is not relabeled to the checkpoint revision.

## 2026-10-05: Durable Replacement Qualification Stopped At Persistence Gate

The operator authorized one additional seven-partition AH03 qualification with
mandatory durable retention. A unique checkout was created at
`external://local/audit-hardening/run-01`; it and its
evidence directory remain in place and must not be deleted or overwritten.

Before compatibility checks, manifest generation, preflight, or mutation
execution, the durable-write harness wrote and fsynced a 4,096-byte random probe
and successfully read it back with SHA-256
`4ac223d1f7f0a13460894729ebd8ef7b6b8281ed27f909311955ba51b0a11252`.
The subsequent directory-fsync step incorrectly called `Path.open("rb")` on the
directory. macOS rejected that harness operation with `IsADirectoryError`.
The validation command exited 1. No manifests were generated, no mutation cache
was created, no mutants executed, and no terminal reports exist.

The attempt stopped under the explicit failed-persistence/integrity rule. The
smallest recovery is harness-only: open the directory with `os.open(path,
os.O_RDONLY)`, call `os.fsync(fd)`, close it, and then rerun pre-execution
validation in a new unique durable run directory. No candidate, dependency,
policy, mapping, timeout, exclusion, or production/test input change is needed.
Because no mutant executed, the authorized qualification itself was not
consumed; however, continuing requires operator direction under the stop rule.

## 2026-10-05: Local Acceptance Through AH06

Current-candidate evidence is retained durably at
`external://local/audit-hardening/candidate-acceptance`. Its initial
candidate identity SHA-256 is
`8b914da742cfdbf0ce4332d5264e9ffff4054cc80e0e7bb1621117c0dc170960` and
its evidence-index SHA-256 is
`aa2e7be6f71759556bba76965b2f51c07d17ac311911e4886b34b2c27303c0e0`.
The index binds each retained output to its content digest. Completion-record
edits made after that snapshot are separately visible in the working-tree diff.

- AH01: 165 focused tests passed. A real clean scan returned `pass`/exit 0.
  A fresh Python environment with neither analyzer returned structured
  `tool_error` entries for Ruff and Semgrep and exit 2.
- AH02: 21 focused tests passed. Whitespace-only scope returned exit 2 with an
  explicit scope error. A clean enforce-mode scan returned exit 0 and wrote
  findings metadata and SARIF.
- AH03 non-mutation criteria: 293 focused tests passed. A live malformed-policy
  fixture denied the safe synthetic request with exit 2, named `fettle doctor`
  as recovery, and wrote a `config_error` trace. This does not cure the missing
  raw mutation package described below.
- AH04: 59 focused race, interruption, rotation, anchor, and tamper tests passed.
  A live 24-process workload produced sequences 1 through 24 exactly once and
  verified the chain. The first stdin-based process-pool harness failed because
  macOS spawn requires a real script path; it remains retained. The corrected
  script-file workload tested a materially different harness and passed.
- AH05: 21 packaging/workflow tests passed. Fresh wheel
  `74b15c92...d189d` and sdist `90f118b5...dd65` both contain
  `fettle/providers`, install into separate Python 3.12 environments outside
  the checkout, resolve imports only from those environments, and pass demo,
  help, and graph-status probes. Two fixture-input failures (unsupported
  `demo --json`; graph repository without `HEAD`) remain retained before the
  corrected documented invocations.
- AH06: 339 tests passed with 20 declared skips. A live generated profile kept
  boundary zero as `"0"`, retained valid email and phone formats, and retained
  Unicode, whitespace, and punctuation classes.

The final local sweep passed 4,299 tests with 20 declared skips, Ruff, a
195-file all-source Fettle scan, and an 11-file changed scan. AH01, AH02, AH04,
AH05, and AH06 are locally confirmed. AH03 remains non-pass because its raw
qualification package is missing. AH07 remains blocked by AH03 and unavailable
independent review, additional supported-platform, live-host, and remote-CI
evidence. No commit, push, release, waiver, or Milestone B/C work occurred.

## 2026-10-05: AH03 Qualification Completed, Raw Recovery Package Lost

The third and final infrastructure-planning correction used
`write_partition_manifests()` directly with the frozen candidate's effective
configuration: dispatcher-only scope, configured exclusions preserved,
`default_chunk_lines = 60`, no path override, and seven partitions. Preflight
assigned all 299 canonical fingerprints exactly once across partitions of 42,
49, 54, 48, 45, 41, and 20 fingerprints. There were no omissions, duplicate
assignments, or extras. The corrected execution-plan SHA-256 was
`bd615b658dabeb9f618917cdc03e2105da887c35c44980586aba6832c00e6830`;
the frozen identity SHA-256 was
`ac8aec3e4bf2bf42acc74087f8877e351336c05284d3af72ee6d164b681ee0e1`.

One authorized sequential qualification then completed all seven partitions:
269 killed, 30 survived, and zero timeout, suspicious, untested, or skipped
outcomes. The aggregate SHA-256 was
`8ca6d1201b7cac629ce6148897879fba418028347cfaa577b47cb4d94dae4e68`.
The 30 raw survivors exactly matched the separately reviewed 30-fingerprint
equivalence set. There were no novel non-killed fingerprints; all 178
actionable baseline findings were absent, and the original held-out suspicious
fingerprint `5f97b56a...f5829` was killed. Frozen-file and source-restoration
checks reported no identity errors or mutation residue.

The recovery checkout and its raw qualification package were created under the
approved temporary OpenCode directory. Environment cleanup removed that
directory before the package was copied to durable project storage. The
recorded terminal transcript and hashes remain historical, unsupported evidence
and conversation provenance, but the
raw seven reports, manifests, and aggregate are no longer locally inspectable.
Under the missing-evidence rule, AH03 remains non-pass. No replacement mutation
execution is authorized; another qualification requires operator approval.

The earlier original held-out, diagnostic, ordering, and failed replacement
artifacts remain distinct historical evidence and are not relabeled as this
qualification's terminal package.

## 2026-10-04: Cluster 19 Numeric Grouping And Equivalence Review

Independent verification confirmed the Cluster 18 candidate and ledger. Cluster
19 grouped the remaining 62 numeric fingerprints before adding tests. They did
not have one root cause, but reduced to two mechanisms: 29 stable-sort `order`
constants and 33 per-check `budget_ms` constants. One parameterized real-dispatcher
deadline test covered all registered owners and killed all 33 unresolved budget
fingerprints under canonical Python 3.12 replay. It tests the deadline delivered
to each owner, not a registry snapshot or 33 bespoke implementations.

The 29 remaining order mutations received a separate exhaustive selection-order
review. Twenty-eight `N -> N+1` mutations preserve the selected sequence for every
registered event/tool/extension context. The sole sequence change swaps optional
`tla_sync_stop` with best-effort `session_report`; both remain selected, neither
consumes the other's state or output, and the aggregate result is unchanged. All
29 are therefore accepted as equivalent for these exact canonical mutations.

Specifically, `tla_sync_stop` reads only `tla_sync._edited_verified_files` and
filesystem mtimes, builds a local stale-spec list, and returns allow or advisory
without writing an artifact (`fettle/tla_sync.py:77-108`). `session_report` reads
the active plan, verify/CI stamps, edit history, and claims, writes only its own
`.fettle/reports/<session>.json`, and always returns allow
(`fettle/session_report.py:72-109,126-134`); it neither imports nor reads TLA state,
and TLA does not read reports. The dispatcher runs both unless an earlier check
blocks or the global budget is already exhausted, while neither of these checks
blocks (`fettle/dispatcher.py:191-218,290-291`); swapping their adjacent positions
therefore introduces no new early return. `session_report` emits no aggregate
message, TLA contributes the same Stop `systemMessage`, and repository searches
found no consumer of check timing or relative advisory/report position, so the
swap changes neither artifact content nor observable output ordering.

The `_lazy.__qualname__` mutation also received a dedicated accept/reject review.
It is accepted as equivalent: repository-wide searches found no production or
test consumer of the assigned metadata; the closure still imports and invokes
the same module attribute with the same context and result; and dispatcher
selection, output, traces, timing, and durable artifacts do not inspect runner
`__qualname__`. The exact mutant remains survived under compatible canonical
replay, as expected for an observationally equivalent change. The retained review
is `evidence/cluster-19-equivalence-review.json`, SHA-256
`964c1bb677aa4d3486eb4cf4fbb96621c18f252c639078da302906c3a802a1db`.

The exact candidate passes 497 focused dispatcher-owner tests. The developmental
ledger now records 178 evidence-supported actionable test gaps, 30 accepted
equivalence candidates, zero production defects, zero engine artifacts, and zero
unresolved findings. Its SHA-256 is
`09b760cef4006b811ae46e1d6bb73055e70adb7454abb5df52c0a3ac5f4254c4`.
One initial shard-2 attempt failed before execution because its canonical manifest
had not been copied locally; the error was retained as non-authoritative, source
identity remained valid, and only shard 2 was rerun after copying the unchanged
canonical manifest.

This is the mandated stop point before one fresh held-out qualification. AH03 is
pending that separately authorized qualification and is not claimed complete.
No full qualification, commit, push, release, waiver, timeout increase, Milestone
B/C work, or AH01/AH02/AH04-AH07 work occurred.

## 2026-10-04: Dispatcher Behavioral Routing Remediation Through Cluster 18

Clusters 10-18 continued the bounded supported-runtime dispatcher remediation in
`external://local/audit-hardening/dispatcher-remediation`. Real dispatcher
boundary tests now distinguish optional output sanitization from required Stop
quality enforcement; exercise enforced commit-message, coverage, lint, and
complexity checks; preserve optional architecture/provenance semantics; record
successful pushes for later CI verification; surface post-tool and TLA
diagnostics; and verify durable session-report and Bash-audit artifacts plus
worklog Stop messaging. A final precedence cluster verifies that the first
safety/recovery decision remains destructive before artifact, spawn before
release, TDD before BDD, deploy before artifact, artifact before spawn, and
local verification before remote CI. No production source changed.

Every cluster used CPython 3.12.13, a fresh 299-fingerprint preflight with zero
collisions, focused tests, and only the canonical manifests containing selected
fingerprints. Candidate changes triggered sequential revalidation of all prior
credits. Two compatibility-refresh commands reached the harness time limit; each
was retained as non-authoritative infrastructure evidence, confirmed to have no
remaining child process, source drift, or residue, and resumed only for the
missing shard. A timeout was never treated as a mutation verdict.

The exact current candidate passes 462 focused dispatcher-owner tests. The
developmental ledger now records 145 evidence-supported actionable test gaps and
63 unresolved findings, with zero demonstrated production defects, accepted
equivalence candidates, or engine artifacts. The remaining set is 62 numeric
order/budget mutations and one `_lazy.__qualname__` metadata mutation. No runtime
consumer of that metadata was found, but it remains unresolved pending dedicated
equivalence review; no implementation-mirroring assertion was added. The ledger
SHA-256 is `92c495e7535bdeb57fd2da22558f13728323fc51bf89ebaae85fccd8de108f2f`.

AH03 therefore remains failed. The narrow replay ledger is developmental evidence,
not an authoritative score or held-out full qualification. AH01, AH02, AH04,
AH05, and AH06 remain unobserved against a frozen final candidate; AH07 remains
blocked. Commit, push, release, full qualification, waivers, timeout increases,
and Milestones B/C remain outside authorization.

## 2026-10-03: Supported Python Revalidation And Config-Protection Cluster

AH00 was rerun against the current isolated dispatcher candidate using CPython
3.12.13, the repository's mutation/CI default. The environment used the
hash-pinned `requirements-mutation.txt` toolchain, mutmut 2.5.1, pytest 9.1.1,
whatthepatch 1.0.7, build 1.6.1, and Playwright 1.62.0 from `uv.lock` to satisfy
the complete project dependency contract. `pip check`, `python -m build
--version`, Git 2.54.0, disposable `git init`, 416 focused dispatcher-owner
tests, and `fettle check --all --root fettle --json` all pass; the Fettle scan
covered 195 files with no findings or tool errors. The current environment
record is `evidence/ah00-py312-final/environment-current.json` in the isolated
checkout, SHA-256
`3b394d02a075a7a717544f2934597aa8930bd4dccc3f0ec3cc430e2436701bec`.

Python 3.14 evidence remains retained under its original identity and remains
valid only for its historical diagnostic/development purpose. It is neither
relabelled as supported-runtime evidence nor discarded. No native mutation
cache or terminal outcome crossed runtime identities.

A fresh Python 3.12 preflight reproduced all 299 canonical fingerprints with
zero collisions. The selected baseline manifests were then replayed sequentially
under each exact current candidate and the original 600-second timeout. All previously
credited fingerprints remained killed. The next bounded `config_protect`
cluster added exact public-boundary coverage for Write and Edit routing and
killed five additional selected survivors: check name, module owner, event, and
both tool routes. No production defect was demonstrated and no production file
changed. A subsequent `agent_spawn_gate` ownership cluster killed its selected
policy and module-routing survivors through the real PreToolUse/Bash boundary.
The current candidate passes 417 focused dispatcher-owner tests. Its ledger
records 66 supported-runtime actionable test gaps and 142 unresolved findings,
SHA-256
`3d246b34fc7d9a0d0b7e29f5d92a90f2eb2216c819f8f0f52e1fcd928534642b`.

AH00 is therefore confirmed for the current development candidate. AH03 remains
failed, AH01/AH02/AH04/AH05/AH06 remain unobserved for an exact final candidate,
and AH07 remains blocked. This is not a full mutation qualification or a final
Milestone A acceptance claim.

Remaining package timing and access requirements are unchanged: AH01 and AH02
must replay their focused, regression, workflow-contract, and disposable live
fixtures after the dispatcher candidate is frozen; AH04 must then run its
integration, interruption, concurrent live workload, and supported-platform
checks; AH05 requires freshly built wheel and sdist environments outside the
checkout; AH06 requires focused tests plus live generated-profile validation.
AH07 runs only after AH01-AH06 have current evidence and requires the full local
verification set, supported-platform wheel/host smoke checks, failure-path UAT,
and an independent reviewer. Remote CI, non-local supported platforms, live host
access, installed-artifact environments, and independent review require operator
access or explicit coordination. Commit, push, release, and held-out full
mutation qualification remain separately approval-gated.

## 2026-10-03: Milestone A Criterion Reconciliation And First Remediation Hypothesis

The authoritative Milestone A definition remains WP-AH00 through WP-AH07 in
`docs/audit-hardening-implementation-plan.md`. Milestone B remains the mutation
Trust Kernel/dogfood graduation program, and Milestone C remains the separately
gated Fettle Review plan. Neither downstream milestone is started here.

The new schema-v1 completion record is
`docs/completion/audit-hardening.json`, with supporting reconciliation in
`docs/completion/evidence/audit-hardening.json`. It intentionally claims
`in_progress` / `FIX_FIRST`. AH00 is failed because the active candidate
environment is Python 3.14.6 while the agreed range is 3.11-3.13. AH03 is
failed by exact-candidate dispatcher evidence. AH01, AH02, AH04, AH05, and AH06
are unobserved for the final candidate: earlier successful observations retain
historical value but do not qualify the current working-tree identity. AH07 is
blocked on those prerequisites and independent/platform/host/remote/artifact
acceptance. This distinction prevents missing evaluation from being rewritten
as either success or demonstrated failure.

The retained dispatcher aggregate is a diagnostic baseline, not final
qualification. Candidate source and all mapped tests match the current working
tree byte-for-byte. All 40 reports use revision `4522a564...`, shard count 40,
and one source, mapping, and policy digest; every terminal record is compatible.
The canonical aggregate itself accepted the manifest set's complete,
non-overlapping executable scope. A separate physical-line comparison was not
used as the aggregation contract because comments and blank lines are not the
engine's executable mutation ranges.

First bounded cluster contract: when secret protection, MCP trust, or
destructive-command enforcement applies, the real dispatcher selection and
lazy execution boundary must invoke the owning check; an unavailable or
incomplete required check must deny rather than allow. Falsifiable hypothesis:
the surviving module-target/event/tool/name mutations for these gates survive
because tests substitute `select_checks` or inspect registry structure instead
of exercising the real registry through `dispatcher.main`; public-boundary
tests with harmless payloads will distinguish those mutations without asserting
the whole registry snapshot. A production change is justified only if those
tests expose incorrect unmutated behavior.

Seven bounded dispatcher clusters subsequently exercised the real registry and
dispatcher boundary in the isolated exact-source checkout
`external://local/audit-hardening/dispatcher-remediation`. Each candidate
iteration passed focused tests, generated a fresh 299-fingerprint preflight with
zero collisions, and replayed only the baseline range manifests containing its
selected fingerprints. No production source changed. The added tests distinguish
required/trust routing, policy ownership, final-decision gates, completion
manifests, capsule/quality gates, lifecycle enforcement, and delivery enforcement.

The current evidence-supported ledger is
`evidence/dispatcher-survivor-ledger-current.json` in that isolated checkout,
SHA-256 `95402b3672252850d4661beb1e2ceb237bb7452f149ac97c51a1115c2f0828ae`.
It classifies 59 unique baseline survivors as actionable test gaps with
discriminating narrow-replay kills and leaves 149 unresolved. It records zero
demonstrated production defects, equivalence candidates, or engine artifacts.
Only explicitly selected fingerprints are credited; adjacent kills in a replay
range remain unclassified. These developmental results do not alter the retained
299-mutant diagnostic baseline or authorize final qualification.

The baseline's 40 manifests and reports were also revalidated against the
canonical executable-range contract. All partition/report ranges match, ranges
are non-overlapping, all identity sets are singular and equal to the aggregate,
and every aggregate outcome count equals the sum of its reports. The retained
verification is
`external://local/audit-hardening/dispatcher-qualification/evidence/dispatcher-baseline-contract-verification.json`,
SHA-256 `f692893fa3ebba6a5481f475397c96c4a1653668f721187c98866247566fe1a3`.
This does not claim every physical source line is executable or mutable.

## 2026-10-03: Dispatcher Aggregate And Milestone A Non-Pass

The replacement dispatcher qualification in
`external://local/audit-hardening/dispatcher-qualification` completed all
40 deterministic 10-line partitions at the unchanged 600-second timeout. All
40 terminal records have compatible revision, shard identity, source manifest,
and residue checks. The final source manifest matches the frozen candidate and
no `.bak`, `.orig`, or `.rej` residue remains.

The first process was externally terminated while shard 30 was running. Its
71.230-second report records `tool_error` and signal 15; it is retained as
`shard-30/mutation-report-attempt-1-interrupted.json` with a separate terminal
record and is not counted as an outcome. Source restoration succeeded after the
interruption. The resumed runner reused only the 30 already compatible terminal
records and reran shards 30-39. `evidence/all-partitions-terminal.json` is now
`completed` with 40/40 compatible records (SHA-256
`ac7e9b25911dd04536d6dd04a3d1b8a3d90daa7c92ca208b4c81901663808e18`).

Canonical aggregation completed with revision
`4522a564791bce326ca4f340f7007f09e988b8e1`, 299 scored mutants, 91 killed,
208 survived, and zero timeout, suspicious, untested, or skipped outcomes. The
score is 30.4. `evidence/dispatcher-aggregate.json` has SHA-256
`1ea08a3e8f2b5d30add7226739c899b0c463868105e850a8b4a96130984a33db`.
Its source, mapping, and policy digests are respectively
`91568ddea4c6c66508e6a164328d28e850bfdb7bc190be8b3849f00c6938a2bc`,
`a1ffe6a8be8d5e206d2defcf7d5c86fb4047ecf472b882bee3217e663f48c0c4`,
and `e7a0eb817b672a3254abccf18782034b3bdc3d800336d8df86ff6d92e759ddf6`.
Canonical validation is `valid/pass` when the artifact is referenced by its
repository-relative evidence path. The report's `passed: true` reflects the
configured advisory policy only; it is not hardening acceptance.

All 208 survivors remain unresolved non-passes. Of these, 207 mutate registry
metadata constants (module targets, names, policy associations, events, tools,
extensions, order, or budgets); one mutates `_lazy`'s diagnostic
`__qualname__`. No survivor has evidence-backed equivalence or engine-artifact
classification. Broad snapshot assertions would test implementation shape and
manufacture kills, so none were added. The bounded classification is retained
in `evidence/dispatcher-survivor-classification.json` (SHA-256
`408d9b9802f0619dd5db34339698133986c28d814aaf30dc101fa02a7d02473d`).

Current non-mutation checks are green: the full suite passed **4,185 tests with
20 skips in 422.63 seconds**; whole-source Ruff, `git diff --check`, and
`fettle check --changed` passed. `fettle completion validate` validates seven
pre-existing records but still contains no Milestone A record. A refreshed
candidate reconciliation is retained at
`external://local/audit-hardening/recovery/candidate-reconciliation-20261003.json`.
The two unexplained mode-only files remain preserved and unqualified.

**Decision:** Milestone A remains non-passing because dispatcher behavioral
evidence does not distinguish 208 mutations, and exact-candidate independent,
supported-platform, live-host, remote, and installed-artifact acceptance is
also incomplete. Milestone B must not start until A passes; Milestone C remains
queued behind B. No commit, push, tag, release, timeout increase, mapping change,
scope broadening, or waiver was made.

## 2026-10-03: Restart Evidence Loss And Managed-Signal Repair

The OpenCode server restart removed the approved temporary directory that held
the in-progress 40-partition dispatcher run, its detached checkout, and the
previous recovery/candidate snapshots. The directory was absent before any
inspection command could run, and the approved OpenCode temporary root was
empty. Consequently, shards reported complete before the restart, the partial
shard 17 state, and the earlier temporary snapshots are retained only as
historical provenance in this worklog; none is reusable terminal evidence and
no aggregate may be reconstructed from the recorded prose.

The mutation wrapper's new real-subprocess SIGTERM fixture initially timed out:
raising `InterruptedError` directly from a Python signal handler did not
reliably wake `Popen.communicate()` while it waited on child pipes. A bounded
second `communicate()` attempt also regressed the simulated `KeyboardInterrupt`
contract by permitting another interruption before restoration. The final
implementation instead installs handlers before launch, records SIGHUP/SIGTERM,
and immediately kills the mutmut child's isolated process group. Normal
`communicate()` control flow then resumes, source restoration and residue
verification run, and the wrapper raises an interruption rather than returning
a successful result. A signal arriving after handler installation but before
child launch is also recorded and causes the newly launched group to terminate
before waiting.

Current focused evidence: `.venv/bin/python -m pytest -q
tests/test_mutation_test.py` passed **186 tests in 4.88 seconds**, including the
real SIGTERM restoration fixture and the prior timeout, keyboard-interrupt,
content/mode-drift, residue, and missing-manifest contracts. Ruff, `git diff
--check`, and `.venv/bin/fettle check --changed` passed. No new `.bak`, `.orig`,
or `.rej` residue was found outside `.git` and `.venv`. This verifies managed
signal cleanup for the current working candidate; external SIGKILL still cannot
run in-process cleanup. The dispatcher qualification must therefore restart in
a fresh disposable checkout from preflight, with new non-overwriting manifests.

## 2026-10-02: Bounded Recovery Attempt and Runners Reconciliation

Made one bounded, read-only attempt to recover the pre-incident contents of
`fettle/boundary_scan.py`. The search covered VS Code local history, OpenCode
snapshots and session records, retained session diffs, Git stashes and
unreachable objects, repository and approved-temp patches/backups, and prior
tool outputs. It found no VS Code resource-history entry for this exact file,
no copy in OpenCode snapshots, empty retained session diffs, no stash or
patch/backup containing the prior bytes, and no trusted session record that
captured the file before `git checkout -- fettle/boundary_scan.py`.

The prior contents are therefore **not recoverable from the retained
artifacts**. The current file still matches HEAD and `origin/main` byte for
byte (SHA-256
`9c208e95f18d92d08127fc9558f07d372445e1fe66f08c90dcd973079e99cb2f`),
but that proves only the current state. It does not prove that no legitimate
uncommitted edits were lost. No baseline acceptance is recorded here; the
operator must explicitly decide whether to accept the current HEAD-matching
file as the intended baseline with that uncertainty. No dispatcher diagnosis
or mutation run may begin before that decision.

Reconciled the runners result without rerunning mutation tooling. The apparent
change from **36/38 to 37/38** is not an additional reviewed behavioral kill.
It is one raw engine classification caused by pytest invocation shape:

- Canonical fingerprint
  `e3c5d0d87fb3c4a7fc0f810a90091db77f0910023f8da433797ef02d4030cde3`
  changes `[*self.arguments, prompt]` to the syntactically invalid
  `[/self.arguments, prompt]` in `UATRunner.run`.
- The canonical outer invocation was `.venv/bin/python -m
  fettle.mutation_test --paths fettle/runners/__init__.py --base origin/main
  --json`. Its mapped test runner expanded to `python -m pytest -x
  --assert=plain tests/test_runners.py tests/test_runners_protocol.py
  tests/test_spawn.py tests/test_uat_reconcile.py tests/test_uat_session.py`.
  The malformed mutant caused collection to stop with exit code 1, which
  mutmut 2.5.1 recorded as killed.
- The narrower `pytest tests/test_runners.py -q` invocation produced exit code
  2 for the same collection `SyntaxError`. Mutmut's `tests_pass()` treats every
  return code other than 1 as passing, so that invocation can classify the
  same mutant as survived.

Accordingly, the preserved accounting is: **37 raw engine-reported kills, but
only 36 reviewed behavioral/assertion kills**; fingerprint `e3c5d0d8...0cde3`
remains a separate collection-error/tool-classification case. The remaining
engine-reported survivor is fingerprint
`29829fd35065c6452675c3a05d1337b6f2d9325647589be503dd5b2b8eb7023c`
(`AgentRunner.run` Protocol default `600 -> 601`), retained under the narrowly
scoped equivalence reasoning below and not converted into kill credit. Thus
the reviewed partition of 38 is 36 behavioral kills, one collection-error
classification, and one equivalence candidate; it is not 37 reviewed kills.
The original canonical terminal JSON is still missing. This reconciliation
uses the contemporaneous recorded command, fingerprints, and reproduced exit
semantics only; it does not reconstruct successful qualification from native
cache state.

### Functional reconstruction after exact recovery failed

Before further execution, preserved the current worktree and mutation cache
artifacts without overwriting prior backups at
`$TMPDIR/opencode/fettle-recovery-20261002T220639.wxl3u136`. The snapshot
contains binary tracked/staged patches, the untracked-file inventory, HEAD,
current `boundary_scan.py`, its tests, this worklog, and both mutation caches.
Its manifest SHA-256 is
`883f079ecbe715c1ab6d05e1aeb3bbdd6be17a19934a7c59af62f4a63197753d`.

**Recovered exactly:** Git retains the complete committed scanner lineage.
The July implementation commit `afd62e52dbe63c0d397427cddd98c94471ff3f2e`
defines the three detectors, tracked-file scan, `.fettle-ignore`, false-positive
exceptions, and fail-closed CI integration. Commit
`803201097b64c04fd7026483e653ef287324a1ab` adds boundary-specific exclusions.
The current 209-byte-line file is byte-identical to that latest committed
lineage. The two incident mutations are known exactly from contemporaneous
diff evidence: `_SECRET_ASSIGN = None` and `text=False`.

**Not recovered exactly:** no artifact contains any uncommitted pre-incident
version. Functional reconstruction cannot establish that its bytes equalled
HEAD, and this entry makes no such historical claim.

**Reconstructed and independently verified:** reviewed the original task,
archived requirements, configuration, direct callers (`fettle.cli.cmd_check`,
`fettle.ci._gate_boundary`, and `fettle.uat.session._redact_secrets`), Git
history, and the owning tests. Added three discriminating integration tests in
`tests/test_boundary_scan.py` for explicit original-contract obligations that
previously lacked direct evidence: `.fettle-ignore` exclusion, Git tracked-only
selection, and visible-file fallback outside a Git repository (including
hidden and known-noise directory exclusion). All 17 owning tests pass. The
broader caller-focused run (`tests/test_boundary_scan.py`, `tests/test_ci.py`,
and `tests/test_uat_session.py`) passes 385 tests with 20 expected opt-in skips.
Ruff is clean.

Disposable-copy fault injection also verifies the two incident corruptions are
observable: replacing `_SECRET_ASSIGN` with `None` fails
`test_flags_high_entropy_assignment` with `AttributeError`; changing
`subprocess.run(..., text=True, ...)` to `text=False` fails
`test_integration_scan_repo_finds_planted_key` with a bytes/string path
`TypeError`. Outputs are retained under
`$TMPDIR/opencode/fettle-boundary-secret-none.rf3or_rx` and
`$TMPDIR/opencode/fettle-boundary-incident-check.mseli_wa`. The first directory
contains the valid corrected `_SECRET_ASSIGN` reproduction; an earlier
malformed fixture in the second directory is explicitly non-evidence.

**Remaining uncertainty and impact:** arbitrary erased uncommitted improvements
cannot be identified or restored. The practical impact is limited to unknown
behavior beyond the documented and independently tested contract; no known
required scanner behavior is missing. `boundary.extra_secret_patterns` is a
separate pre-existing integration concern, not evidence of an erased scanner
edit: Git commit `9722c6dc62aa727de09b091e8425580e418fce79` introduced it for
`fettle/secret_scan.py`, and that module owns its tests. It was not silently
moved into `boundary_scan.py` during recovery.

On that evidence, source-integrity review is resolved as a functional repair:
the current production file is retained, the missing contract evidence is
added, and historical uncertainty remains explicit. This authorizes only the
previously scoped isolated dispatcher diagnosis, not a full mutation run or a
claim that historical bytes were recovered.

### Dispatcher timeout diagnosis

Created detached disposable worktree
`$TMPDIR/opencode/fettle-dispatcher-diagnosis.5cl439sv/checkout` at exact HEAD
`4522a564791bce326ca4f340f7007f09e988b8e1`, then copied only the current
`tests/test_dispatcher_registry.py` candidate into it. Candidate identity:
production SHA-256
`4a44ac7b53601c944a283c6aa1fd64bb3cfcfbd69a927a500da279274663bf84`,
test SHA-256
`6db84f5fcde134956c7cffe325a7b5a5a62f42b0659a1b8de3170cd0d25ce1a1`.
The primary worktree and its caches were not used for mutation execution.

Ran the exact unmutilated mapped command first, adding only pytest's duration
reporting:

```
python -m pytest -x --assert=plain --durations=0 \
  tests/test_dispatcher_registry.py tests/test_agent_spawn_gate.py \
  tests/test_bdd_gate.py tests/test_ci_gate.py \
  tests/test_dispatcher_failure_visibility.py \
  tests/test_host_event_parity.py tests/test_pipeline_dump.py \
  tests/test_verify_gate.py tests/test_work_items.py
```

It exited 0: **306 passed in 16.89 seconds** (17.152430 seconds wall time).
No individual test exceeded 0.17 seconds. Whole-file preflight then completed
in 30.985610 seconds with **299 generated, 299 canonicalized, zero
collisions**. Therefore the prior 600-second timeout is explained by serial
corpus capacity, not a baseline hang: even 299 baseline-equivalent executions
would take roughly 84 minutes before mutation overhead.

Used Fettle's manifest/range seam rather than weakening the nine-file mapping
or increasing the timeout. A 10-line chunk size isolated the three changed
predicate ranges. The first preflight attempt for lines 31–40 failed closed
because mutmut's optional `whatthepatch` dependency was absent; its retained
JSON is `tool_error` and earns no credit. Installed `whatthepatch==1.0.7` only
under the disposable diagnosis directory, regenerated the environment
identity, and reran sequentially:

| Range | Behavior | Preflight | Replay | Wall time |
| --- | --- | ---: | ---: | ---: |
| 31–40 | `_quality_requires_execution` | 27 canonical, 0 collisions | 27 killed, 0 non-killed | 36.417752 s |
| 61–70 | capsule `required_when` plus adjacent metadata | 7 canonical, 0 collisions | 4 killed, 3 survived | 72.441761 s |
| 91–100 | MCP `required_when` plus adjacent metadata | 12 canonical, 0 collisions | 5 killed, 7 survived | 142.028448 s |

All replays completed under the unchanged 600-second timeout with zero mutant
timeouts, suspicious, untested, or skipped outcomes. The common source,
mapping, and policy digests are respectively
`91568ddea4c6c66508e6a164328d28e850bfdb7bc190be8b3849f00c6938a2bc`,
`a1ffe6a8be8d5e206d2defcf7d5c86fb4047ecf472b882bee3217e663f48c0c4`,
and `e7a0eb817b672a3254abccf18782034b3bdc3d800336d8df86ff6d92e759ddf6`.
The compatibility identity digest retained after adding the isolated patch
dependency is
`779e339656f4243592452044442622876f418698be2d409c04c2c9f288333c54`.

Every mutant on the three new `required_when` expressions was engine-killed.
The ten survivors are separate, adjacent pre-existing `CheckSpec` metadata:
module names, event/tool sets, order, and budget values. They are not credited
as predicate failures, kills, or equivalents and were not broadened into this
bounded repair.

Important evidence limit: `validate_canonical_evidence` rejects each retained
partial report as `malformed` because standalone reports have
`selection: "shard"`; canonical validation accepts only complete `all` or
`changed` aggregate reports. The replay JSON, manifests, compatibility
identity, stdout/stderr, commands, timings, exit statuses, and validation
results are retained under the diagnosis directory, but they remain
**diagnostic narrow-replay evidence, not authoritative canonical completion
evidence**. Running the other 37 partitions solely to produce an aggregate
would exceed this bounded diagnosis and approach a full-file qualification,
so it was not done. The original dispatcher timeout remains non-passing; it is
now diagnosed rather than erased.

## 2026-10-02: Read-Only Handoff Integrity Review — Phase 2 Blocked

Reviewed the reported checkpoint before starting another mutation cluster.
HEAD is still `4522a564791bce326ca4f340f7007f09e988b8e1`; merge-base with
`origin/main` is `2a2829cbdb1e630cbfc37b48360d91dbce8c4fd9`. The working tree contains
substantial pre-existing edits from several sessions. This review preserved
them and made no source, test, cache, configuration, or backup changes. The
only new edit is this worklog entry. At review time, the non-document tracked
edits already present were `fettle/cross_review.py`, `fettle/import_graph.py`,
`tests/test_dispatcher_registry.py`, `tests/test_runners.py`,
`tests/test_spec_model.py`, and `tests/test_uat_session.py`; numerous modified
and untracked planning documents were also preserved. This list attributes no
ownership and does not treat those prior edits as reviewed by this entry.

### Integrity result and blocker

`fettle/boundary_scan.py` currently matches both the index and HEAD byte for
byte (SHA-256
`9c208e95f18d92d08127fc9558f07d372445e1fe66f08c90dcd973079e99cb2f`).
Its current `_SECRET_ASSIGN` is the compiled regular expression and its
`git ls-files` subprocess uses `text=True`, so the two reported live mutants
are not present. No `*.bak`, `*.orig`, `*.rej`, or editor-suffix backup remains
outside excluded `.git`/`.venv` directories, and no active mutmut,
`fettle.mutation_test`, or pytest process was found.

That establishes restoration to HEAD, but **does not establish restoration to
the pre-run working-tree state**. The prior entry says the file was restored
with `git checkout -- fettle/boundary_scan.py`, but it records no pre-run hash
or snapshot. Read-only searches found no retained `boundary_scan.py.bak`,
stash, snapshot copy, matching unreachable Git blob, canonical report, or
other artifact from which legitimate uncommitted pre-run bytes could be
reconstructed. Git history shows no branch diff for this file, and the
`boundary_scan.py` bytes at HEAD equal the bytes at `origin/main`; the branch
as a whole does not equal `origin/main`. That file-level equality cannot prove
there were no uncommitted edits before checkout. Therefore the possibility
that checkout discarded legitimate work remains unresolved. Per the
operator's stop condition, Phase 2 did not start and no mutation command was
run.

### Evidence reconciliation

The repository retains `.fettle/mutation-cache/identity.json` plus
`.fettle/mutation-cache/mutmut-cache.sqlite` for the spec-model run. The
identity digest is
`0d70c243a9d00279ebea2edb69b1a48330899541dc5a3eda88d6488e716bb178`.
It records Darwin arm64, Python 3.14.6, mutmut 2.5.1, pytest 9.1.1, path
`fettle/spec_model.py`, base `origin/main`, timeout 600 seconds, mapping
`fettle/spec_model.py -> tests/test_spec_model.py`, the complete dependency
identity, and watched-file hashes. All retained watched-file hashes match the
current files. The scoped SQLite cache contains exactly 302 records: 227
`ok_killed` and 75 `bad_survived`.

This is compatible native cache state, **not a retained canonical terminal
JSON report**. No canonical spec replay report containing status, canonical
fingerprints, source-scope digest, test-mapping digest, policy digest, exact
runner field, and terminal outcome was found in the repository or approved
OpenCode temp area. No retained dispatcher timeout report was found either.
The implementation's canonical runner is `python -m pytest -x --assert=plain
{mapped_tests}`, and the worklog records the invocations, but prose plus native
cache cannot replace a canonical report. This integrity review supersedes the
evidentiary status implied by the older entry's phrase “Canonical replay”:
that older paragraph is contemporaneous prose about a run whose terminal JSON
is no longer retained, not independently reusable canonical evidence.
Consequently:

- `302 generated / 227 killed / 75 survived` is corroborated as native cache
  state under the retained compatible cache identity, not independently
  validated canonical terminal evidence.
- The earlier line-based review may support only this narrow prose claim:
  **none of the 75 recorded native-cache survivors was reported on current
  lines 205–207**. It is not proof that changed behavior is fully covered and
  no fresh fingerprint claim is made here.
- The dispatcher run remains a reported 600-second `tool_error` with no score,
  pass, or kill credit. Missing terminal JSON is an additional retention gap.
- The root `.mutmut-cache` was regenerated after the incident (current
  SHA-256 `7b93f24fcd2e22b489cdf0614e14bb3d087cdd48ad5438616dde3291e6da5f26`)
  and contains unrelated accumulated state. It cannot restore provenance for
  the lost prior generation or authorize reuse.

### Focused behavior review

The `discover_specs` production change is not a new uncommitted edit: Git
history places it in commit `235c17659f1749e72cb2831be058032540f51e92`.
It correctly applies skip-directory matching to
`md.relative_to(root_path).parts`, so an ancestor outside the requested root
named `build` does not suppress discovery, while an in-root `.fettle`
directory is excluded. Existing sorting, Markdown selection, unreadable-file
continuation, non-spec continuation, relative result paths, and parsing flow
are unchanged. The two uncommitted regressions directly distinguish the
ancestor and `.fettle` cases; the prior worklog's temporary pre-fix run is
prose-only because its raw output was not retained.

The dispatcher additions are meaningful direct predicate assertions. They
cover Stop/test-gate state, presence of `stop_hook_active` (including a false
value), event/tool rejection, UX/plan gates, bootstrap modes and disabled
state, empty gates, capsule environment presence, and MCP trust configuration.
The earlier count was inaccurate: pytest collects **21 added parametrized
cases**, not 16. Current focused verification in the recorded environment:

- `.venv/bin/python -m pytest -q tests/test_dispatcher_registry.py
  tests/test_spec_model.py` -> **89 passed in 1.30 seconds** (33 dispatcher,
  56 spec).
- `.venv/bin/ruff check fettle/dispatcher_registry.py fettle/spec_model.py
  tests/test_dispatcher_registry.py tests/test_spec_model.py` -> clean.

No dispatcher replay was retried, no timeout was increased, and no canonical
mapping was weakened. No confirmed-kill, equivalence, or completion claim is
added by this review. The next action requires operator resolution of the
`boundary_scan.py` pre-run-state uncertainty (for example, supplying a trusted
pre-incident snapshot or explicitly accepting HEAD as the intended state).
Only then should one bounded cluster be selected and run in a disposable
checkout with candidate identity verified before preflight and narrow replay.

## 2026-10-02: Spec Discovery Mutation Repair (fettle/spec_model.py) + Incident Note

Continued remediation without a new commit or push; same HEAD
`4522a564791bce326ca4f340f7007f09e988b8e1`, same environment of record (Python
3.14.6, mutmut 2.5.1). Per operator instruction, this is the last cluster for
this session — no further cluster was selected after it.

### Selection (source/diff inspection only, no sizing mutation runs)

Read the branch diff against `origin/main` directly rather than running
exploratory mutation passes to compare candidates. `fettle/dispatcher_types.py`
(18-line diff) was set aside before any mutation run: a static grep for
top-level and nested imports of `fettle.dispatcher_types` across `tests/*.py`
(matching `fettle.mutation_test._mapped_tests`'s `ast.walk`-based import
discovery, which maps on *any* import location, not just top-level) found 35
owning test files — too broad to bound. `fettle/dispatcher_registry.py` (36-line
diff) mapped to a smaller 9 files by the same static check and was attempted
next (below); `fettle/spec_model.py` (3-line diff) mapped to exactly one file,
`tests/test_spec_model.py`, and was the file this entry's evidence covers.

### Abandoned attempt: fettle/dispatcher_registry.py (no canonical evidence — timeout)

The diff adds `_quality_requires_execution` (a `required_when` predicate for
the `quality_gate` check) and two inline `required_when` lambdas (`capsule_guard`
gated on `FETTLE_POLICY_CAPSULE` env var, `mcp_trust_gate` gated on its own
config key). None of these had direct unit tests — only indirect exercise
through `fettle/dispatcher_types.py::CheckSpec.requires_execution` (a sibling,
already-tested method) in `tests/test_dispatcher_failure_visibility.py`.

Added `TestQualityRequiresExecution` and `TestRequiredWhenPredicates` to
`tests/test_dispatcher_registry.py` (16 new focused cases covering the `Stop`
branch, the `stop_hook_active` branch regardless of tool, the
non-`PreToolUse`/wrong-tool false cases, the `ux_spec`/`plan` gate branch, the
`ci_bootstrap` mode set membership and its disabled-gate case, and both inline
lambdas). All pass directly: `pytest tests/test_dispatcher_registry.py -q` →
33 passed. Ruff clean.

The canonical replay (`fettle.mutation_test --paths
fettle/dispatcher_registry.py --base origin/main --json`) mapped to 9 test
files via import discovery, several of which spawn real subprocesses
(`test_ci_gate.py`, `test_verify_gate.py`, `test_work_items.py`), and **timed
out after 600s** (`status: tool_error`, `"Mutation run timed out after 600s"`).
Per the mutation playbook, a timeout must not be reinterpreted as killed or
survived. **No canonical mutation evidence exists for this cluster.** The new
tests are retained as valid, directly-verified (pytest-passing) regression
coverage for previously-untested predicates, but are explicitly **not**
credited with any kill count and this is **not** claimed as a finished
cluster — it is an unresolved attempt, separated out from the finished
cluster below.

### Incident: interrupted mutation runs left a production file mutated on disk

Before narrowing to `fettle/spec_model.py`, two broader operations were
attempted and aborted:

1. The global `fettle mutation preflight` CLI (no `--paths` scoping available)
   was run twice to check readiness; both runs operated over the full
   configured `[mutation].paths = ["fettle/"]` scope, took several minutes
   with no output, and were killed as impractical for bounded per-file
   iteration — this command is a full/global readiness step, not a narrow-replay
   tool, and should not be used for single-cluster work.
2. The `fettle/dispatcher_registry.py` canonical replay above, which ran real
   mutmut mutation/execution for 600s before timing out.

After these, `git status` showed `fettle/boundary_scan.py` modified with two
*unintended* changes neither authored nor requested this session:
`_SECRET_ASSIGN = re.compile(...)` replaced with `_SECRET_ASSIGN = None`, and
a `subprocess.run(..., text=True, ...)` call changed to `text=False`, plus a
stray `fettle/boundary_scan.py.bak` file (mutmut's own pre-mutation backup,
holding only the first of the two changes). This is a leftover from one of
the interrupted/timed-out mutmut invocations above applying a mutant to disk
and not restoring it before being killed or timing out. Verified via `git
diff` and reverted completely with `git checkout -- fettle/boundary_scan.py`;
confirmed clean after (`git diff --stat` empty, no `.bak` files anywhere under
`fettle/` via `find fettle -name "*.bak"`). No other stray modifications were
found in a full `git status` sweep of `fettle/` and `tests/`.

**Lesson retained for future sessions:** after any interrupted or timed-out
mutmut/`fettle.mutation_test` invocation — not just a clean completion — run a
full `git status`/`git diff` sweep of the whole tracked tree (not only the
targeted file) before trusting the working tree, and search for stray `*.bak`
files. A killed background process does not guarantee the mutation engine
restored the source file it was mutating.

#### 2026-10-02 containment repair

The mutation wrapper now runs every `mutmut run` in its own process group and
records the byte content and executable mode of every repository Python source
before launch. On a managed timeout or `KeyboardInterrupt`, it terminates the
whole group before checking restoration. If a file differs, Fettle restores it
only when mutmut left a regular `.bak` whose bytes exactly match the pre-run
source. Any unmatched drift, mode drift, missing source, new `.bak`/`.orig`/`.rej`
residue, or a nominally successful mutmut process that required repair becomes a
source-integrity tool error. Existing residue is not silently deleted.

Focused regression evidence: `tests/test_mutation_test.py` has 185 passing tests,
including real subprocess timeout restoration, simulated interrupt restoration,
unexplained content/mode drift and residue rejection, missing-manifest rejection,
and repaired-but-rejected nominal success.
Ruff and `fettle check --changed` pass. An external `SIGKILL` of Fettle itself
cannot execute in-process cleanup, so held-out runs remain confined to disposable
checkouts with external before/after source manifests and residue checks.

A replacement recovery snapshot now lives outside the restart-cleared temporary
root at `external://local/audit-hardening/recovery`. Its manifest SHA-256
is `4f212879d9144287518ea9e619011ee7e236a31fdc079e5d0189d0889f3c6bff`.
It retains binary working/index patches, all 12 untracked files, HEAD and merge
base, and byte/mode identities for 37 dirty entries. Ownership remains separated:
10 hardening files, 25 future-planning files, and the two unexplained mode-only
files `fettle/cross_review.py` and `fettle/import_graph.py` as preserved and
unqualified.

Fresh dispatcher evidence is rooted at
`external://local/audit-hardening/dispatcher-qualification`, a detached
checkout at the same HEAD with an isolated virtual environment. Candidate hashes
are unchanged for `fettle/dispatcher_registry.py`
(`4a44ac7b53601c944a283c6aa1fd64bb3cfcfbd69a927a500da279274663bf84`)
and `tests/test_dispatcher_registry.py`
(`6db84f5fcde134956c7cffe325a7b5a5a62f42b0659a1b8de3170cd0d25ce1a1`).
The exact nine-file mapped baseline passed **306 tests in 18.88 seconds**. Fresh
dispatcher-only preflight completed in 29.923 seconds with 299 generated, 299
canonicalized, and zero collisions.

One mistakenly invoked `--all` mutation run was externally timed out after 120
seconds; the managed SIGTERM path emitted explicit `tool_error`, preserved the
465-file Python manifest, and left no residue. It is retained as failed evidence.
The first partition attempt then failed before engine execution because manifests
were generated with 10-line chunks while runtime recomputation still read the
repository's 60-line default. That configuration mismatch is also retained as
non-pass. The disposable checkout alone now sets `default_chunk_lines = 10`;
regenerated manifest digests exactly match the initial 40-manifest set. Test
mapping and the 600-second shard timeout remain unchanged.

Separately, the shared `.mutmut-cache` (mutmut's own native resume cache, not
canonical evidence — the playbook treats it as disposable local state) lost
its prior accumulated generation (6,242,304 bytes, dated 2026-09-23) during
these interrupted attempts and is now a smaller, session-local regeneration
(4,923,392 bytes, dated today). This does not affect any canonical fingerprint
recorded in this worklog, which comes from `fettle.mutation_test`'s JSON
reports and `_canonical_mutant` digests, not from this cache file; it is noted
for transparency only.

### Finished cluster: fettle/spec_model.py — discover_specs directory-skip fix

The diff changes one `if` condition in `discover_specs`:

```
-        if any(part in _SKIP_DIRS for part in md.parts):
+        if any(part in _SKIP_DIRS or part == ".fettle"
+               for part in md.relative_to(root_path).parts):
```

This is a real behavioral fix, not cosmetic: the old code checked
`md.parts` — the **absolute** path's components — against `_SKIP_DIRS`
(`.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `dist`, `build`). Any
ancestor directory *above* the scanned root that happened to share one of
those names (e.g. a checkout living under a path containing `.../build/...`)
would silently cause every spec under that root to be skipped — a false
"zero specs found," not a crash. The fix scopes the check to
`md.relative_to(root_path).parts` (only components inside the scanned tree)
and adds `.fettle` (fettle's own state directory) to the exclusion.

`tests/test_spec_model.py::TestRepoLevel` had `test_skip_dirs_excluded`
(a `node_modules` subdirectory *inside* the scanned repo), which does not
discriminate old vs. new behavior — it passes identically either way, since
inside-tree skip-dir names are unaffected by the absolute-vs-relative change.
Added two new cases:

- `test_fettle_state_dir_excluded`: a spec under `.fettle/sub/` inside the
  scanned repo must still be excluded (the new `.fettle` member).
- `test_skip_dirs_match_only_within_scanned_root`: a scanned root nested under
  an ancestor literally named `build` (`tmp_path/build/actual-root`, with a
  valid spec directly inside `actual-root`) must still be discovered — the
  skip check must not fire on ancestors outside the scanned tree.

Confirmed both are genuinely discriminating, not vacuous: temporarily reverted
`discover_specs` to the pre-fix `md.parts` form and reran just these two
cases — both failed (`assert 0 == 1` and `assert 2 == 1` respectively, exactly
as the bug predicts), then restored the fix (`git diff --stat` on the source
file confirmed byte-identical to HEAD afterward) and reran the full file: all
pass.

Canonical replay (`fettle.mutation_test --paths fettle/spec_model.py --base
origin/main --json`, `tests_run = ["tests/test_spec_model.py"]`, single
mapped file, no multi-file invocation-shape concern this time): 302 mutants,
227 killed, 75 survived, score 75.2 (engine-reported developmental result for
this exact mapping, not a qualification verdict). Every one of the 75
survivors was enumerated and checked by file line against the diff's changed
span (current lines 205–207); **none fall inside it** — e.g. the nearest
`discover_specs` survivors are at line 203 (the function's pre-existing
`Spec | None` return-type annotation, mutated to `Spec & None` — a
string-only annotation under `from __future__ import annotations`, never
evaluated at runtime, likely equivalent but not reviewed/classified this
session), line 209 (pre-existing `errors="replace"` on `md.read_text`), and
lines 211/213 (pre-existing `continue`→`break` mutations in the unrelated
unreadable-file and non-spec-file branches). All 75 are pre-existing code
outside this diff and were **not** remediated, per explicit scope guidance to
prefer the small changed behavior over remediating unrelated pre-existing
code; they are left as unresolved historical findings, not reviewed
equivalents and not killed.

`tests/test_spec_model.py`: 56 passed in 1.28s. Ruff clean on
`fettle/spec_model.py` and `tests/test_spec_model.py` (the former has no diff
from HEAD — only the test file changed). Required external `python3
~/.claude/plugins/fettle/scripts/cli.py check --changed`: no issues found.
`.mutmut-cache` moved aside before the replay and restored after (to the
state noted in the incident section above, since the pristine original was
already gone before this replay began).

### Summary for this session

- **Confirmed kills (canonical, this cluster):** all mutants in
  `discover_specs`'s changed span (lines 205–207) — none appear among the 75
  survivors.
- **Reviewed equivalence candidates:** none newly classified this session
  (the `Spec | None → Spec & None` annotation mutation is flagged as a likely
  candidate but explicitly left unreviewed, not counted).
- **Tool/evidence failures:** the `fettle/dispatcher_registry.py` replay
  (timeout, no score); the stray `fettle/boundary_scan.py` mutation-on-disk
  incident (found and reverted); `.mutmut-cache`'s prior generation lost
  (disposable tool state, not evidence).
- **Unresolved findings:** the 75 pre-existing `fettle/spec_model.py`
  survivors outside the diff's changed span; the `dispatcher_registry.py`
  predicates added this session have passing direct tests but no mutation
  kill evidence.

No production code was changed (only `tests/test_spec_model.py` and
`tests/test_dispatcher_registry.py`). No threshold, waiver, or assertion was
weakened. No commit, push, or full qualification run was made. Operator
instructed to stop after this cluster; no further cluster was selected.

## 2026-10-02: Subprocess Core Mutation Repair (fettle/runners/_subprocess.py)

Continued remediation without a new commit or push; same HEAD
`4522a564791bce326ca4f340f7007f09e988b8e1`, same environment of record as the
runners-cluster entry below (Python 3.14.6, mutmut 2.5.1).

Sizing check before committing to a cluster: ran the canonical pipeline
against `fettle/action_entrypoint.py` first (`--paths
fettle/action_entrypoint.py --base origin/main --json`): 230 mutants, 106
killed, 124 survived, score 46.1 (engine-reported, not a qualification
verdict) — spread across `main` (69),
`_findings_to_sarif` (43), and the new `_validated_findings` (12), almost
all pre-existing historical code outside this branch's diff. Too large for
one bounded pass; not selected. Documented here as a sizing data point, not
as evidence for or against this file's specific survivors — none were
inspected individually. Candidate for a future, explicitly multi-session
cluster.

Selected `fettle/runners/_subprocess.py` instead (39 lines, explicitly mapped
in `.fettle.toml` to `tests/test_runners.py`, no diff vs `origin/main` so
`--base` selection found nothing — required `--all` with `--paths` to mutate
this one unchanged file; confirmed this does not touch any other configured
path). Canonical run
(`python -m fettle.mutation_test --paths fettle/runners/_subprocess.py --all
--json`): 32 mutants, 17 killed, 15 survived, score 53.1 (engine-reported
developmental result, not qualification), `tests_run =
["tests/test_runners.py"]`.

14 of the 15 survivors were real gaps in `TestCliRunners` (shared by
Codex/Gemini/OpenCode via `run_cli`): the missing-binary and timeout paths
only asserted `result.error` was truthy, never the exact message, transcript,
or duration; `subprocess.run`'s `capture_output`/`text` kwargs were never
asserted; the non-timeout duration and the empty/truncated-stderr formatting
branches (`stderr_tail or 'no stderr'`, the `[-500:]` bound) had no coverage
at all. Fixed by strengthening `test_unavailable_when_binary_missing`,
`test_successful_run`, `test_nonzero_exit_sets_error_keeps_transcript`, and
`test_timeout_sets_error` to exact values (duration pinned via
`monkeypatch`-free `patch("fettle.runners._subprocess.time.monotonic", lambda:
next(ticks))` with a fixed two-value iterator), and adding
`test_nonzero_exit_with_empty_stderr_reports_no_stderr` and
`test_nonzero_exit_truncates_stderr_tail_to_500_chars` (501-char stderr,
asserts the exact 500-char tail).

Re-ran the canonical pipeline after the fixes: 32 mutants, 31 killed, 1
survived, score 96.9 (an engine-reported developmental result for this file's
current mapping, not a qualification outcome — see the classification caveat
below for why the remaining count is not a settled score). `tests/test_runners.py`:
87 passed in 0.12 s (was 81 before this session's two clusters). Ruff clean on
both touched files. Required external `python3 ~/.claude/plugins/fettle/scripts/cli.py
check --changed`: no issues found. No production code was changed.

**One survivor remains, and it reproduces the identical tool/evidence
limitation documented below for the runners cluster — generalizing it, not
re-deriving a new explanation.** `mutmut show 9`:

```
-            [resolved, *args],
+            [resolved, /args],
```

Canonical fingerprint (via `fettle.mutation_test._canonical_mutant`, operator
`textual`): `a15e1422bff229de9aa30d98a0a27d93f283eed942480ac68654829b90c8134f`
(source-context digest
`f46d9ce385c5d6f5cf2c47153fe6cfd908786895c9e7c36914e509bf47885e05`). Confirmed
`SyntaxError` via `ast.parse`. Reproduced the exact canonical single-file
invocation (`pytest -x --assert=plain tests/test_runners.py`, matching this
file's explicit `.fettle.toml` mapping): exit code **2** ("Interrupted: 1
error during collection"), because there is only one mapped test file and
`-x` has no "next target" to advance past the all-collection-failed state to
an overall tests-failed exit. This is the same `returncode != 1` mutmut
classification gap as the runners cluster, but here it manifests even under
the file's own canonical single-file mapping (not only a hand-run narrow
replay), because `_subprocess.py` has no fallback to a multi-file mapping.

This is **unresolved classification evidence, not a mutant that is inherently
non-killable**. The mutation itself (a genuine, non-equivalent break) does not
determine the recorded outcome — the exact test-runner invocation and pytest's
collection behavior under that invocation do. The runners-cluster sibling
fingerprint (same underlying `*args` pattern) was recorded `killed` under a
multi-file `-x` mapping; this file's single-file `.fettle.toml` mapping
records `survived` for the structurally identical case. Widening this file's
test mapping to a second file (matching `fettle/runners/__init__.py`'s
mapping) or adding an explicit regression asserting successful import of
`fettle.runners._subprocess` would both change the recorded classification —
the finding is retained as unresolved pending that follow-up, not credited as
killed, not waived, and not declared equivalent.

The shared `.mutmut-cache` was moved aside before this cluster's runs and
restored byte-identical afterward.

This is a scoped developmental check on one file, not a refreshed full
mutation qualification. No new commit or push has occurred.

## 2026-10-02: Runners Module Mutation Repair (fettle/runners/__init__.py)

Continued remediation without a new commit or push; HEAD remains unpublished
local commit `4522a56`, confirmed unchanged from the prior checkpoint. Working
tree still carries the prior session's uncommitted doc/test changes and several
unrelated planning documents from a separate session; all were left untouched
to preserve existing work.

Selected `fettle/runners/__init__.py` (101 lines) as the next bounded cluster:
it is inside the branch's actual changed-vs-`origin/main` scope (the `UATRunner`
dataclass and `get_uat_runner` addition), small, and had no prior narrow-replay
evidence recorded in this worklog.

Environment of record: Python 3.14.6 (`.venv/bin/python`,
`sys.executable=external://local/tooling/python`), mutmut
2.5.1 (pinned, matches `pyproject.toml`), revision
`4522a564791bce326ca4f340f7007f09e988b8e1` (full `git rev-parse HEAD`),
merge-base `2a2829cbdb1e630cbfc37b48360d91dbce8c4fd9` against `origin/main`.

An initial discriminating pass used a hand-run `mutmut run --paths-to-mutate
fettle/runners/__init__.py --runner "<venv>/bin/python -m pytest
tests/test_runners.py -q" --CI` (native IDs only, single mapped test file).
That is a useful fast signal for iteration but is **not** the canonical
evidence path: native mutmut IDs are run-local locators (per the mutation
playbook), and a hand-picked single test file does not reproduce fettle's own
test-mapping discovery. All evidence below instead comes from fettle's own
canonicalizing pipeline, run directly against the module (not the `fettle`
CLI wrapper, which only exposes `--changed`/`--all` over the full configured
path set):

```
.venv/bin/python -m fettle.mutation_test \
  --paths fettle/runners/__init__.py --base origin/main --json
```

This is additive, standalone evidence for this one file's cluster — it is
**not** subtracted from or reconciled with the tracked developmental inventory
total (currently 1,368/4,478 historical fingerprints with narrow kill
evidence, 3,110 remaining per the prior session). That union uses a different
accounting convention (internally consistent completed preflight/replay pairs)
and this cluster's fingerprints have not been cross-checked against it; no
claim is made here about the aggregate count changing.

**Before fixes** (reconstructed from the hand-run pass above, native-ID only,
not re-verified canonically before the fix because the test changes below are
already applied in the working tree): 38 mutants, 29 killed, 9 survived
(native IDs 1, 4, 6, 15, 16, 23, 24, 37, 38). Fixed 1, 4, 15, 16, 23 and 37/38
by adding or strengthening assertions in `tests/test_runners.py`:
`test_runner_result_is_frozen`, `test_runner_result_default_error_is_empty_string`,
`test_uat_runner_defaults_to_600s_timeout`, and exact-message assertions
(replacing `pytest.raises(..., match="claude")` /
`match="permission-preserving"` substring checks, which mutmut's `XX`-wrapped
string-literal mutations and separator mutations still satisfied) in
`test_get_runner_unknown_raises_with_names` and
`test_unqualified_uat_runner_is_blocked`.

**Canonical run after the fixes** (`fettle.mutation_test`, command above,
mapped tests auto-discovered by fettle's owner/import-graph convention —
broader than the hand-run's single file):

- `tests_run`: `tests/test_runners.py`, `tests/test_runners_protocol.py`,
  `tests/test_spawn.py`, `tests/test_uat_reconcile.py`,
  `tests/test_uat_session.py`
- `test_runner`: `python -m pytest -x --assert=plain {mapped_tests}`
- killed 37, survived 1, timeout 0, suspicious 0, untested 0, skipped 0
- score 97.4 (threshold 80.0, mode advisory, passed) — an engine-reported
  developmental result for this exact mapping/command, not a qualification
  verdict; one of the two fingerprints discussed below has an unresolved,
  invocation-dependent classification, so this score should not be read as a
  settled measure of this file's protection until that is resolved
- `source_scope_digest` `0976e8f7acb14f41b3e8d5784911ab16444e56754314ef652708375015d213e4`,
  `test_mapping_digest` `fa5173761458fe1bfe334ccbe561eda5335b89c2647ef5a25f27910187bd30a0`,
  `policy_digest` `e7a0eb817b672a3254abccf18782034b3bdc3d800336d8df86ff6d92e759ddf6`

One canonical survivor fingerprint remains:

- `29829fd35065c6452675c3a05d1337b6f2d9325647589be503dd5b2b8eb7023c`
  (native ID 6 in the hand-run cache; native IDs are not stable across runs
  and are cited only as a cross-reference for this session): `AgentRunner.run`
  Protocol stub, `timeout_s: int = 600 → 601`. The value is introspectable
  (`inspect.signature(AgentRunner.run).parameters["timeout_s"].default`), so
  this is not an unobservable mutant — the equivalence claim is narrower: no
  concrete runner consults or inherits this default. `ClaudeRunner.run`,
  `CodexRunner.run`, `GeminiRunner.run`, `OpenCodeRunner.run`, and
  `UATRunner.run` each independently declare their own literal `timeout_s:
  int = 600` (confirmed by direct inspection of all five files); Python
  Protocols provide no implementation inheritance, so this stub's default can
never reach a call. The supported behavioral contract is **scoped strictly to
the verified call paths that exist today**: the five concrete runners this
repository ships, each independently redeclaring and exercising its own
`timeout_s` default — `UATRunner`'s by `test_uat_runner_defaults_to_600s_timeout`
added this session, the four CLI runners' by their existing conformance tests.
This equivalence claim does not extend to any hypothetical future caller that
might invoke `AgentRunner.run` through the Protocol itself (none exists in
this codebase today); it is equivalent relative to the currently supported
contract, not equivalent in general. Not killed because it is unobservable —
it is introspectable — but equivalent because nothing in the supported
contract consults it. No test was added against the Protocol annotation
itself (that would test the stub, not production behavior).

**Native-ID 24 is a separate, unresolved tool/evidence case, not folded into
the canonical "killed" count above without qualification.** `mutmut show 24`:

```
-        return run_cli(self.name, [*self.arguments, prompt], cwd, timeout_s)
+        return run_cli(self.name, [/self.arguments, prompt], cwd, timeout_s)
```

Its canonical fingerprint (computed directly via
`fettle.mutation_test._canonical_mutant`, operator `textual` because the
mutated source fails `ast.parse`):
`e3c5d0d87fb3c4a7fc0f810a90091db77f0910023f8da433797ef02d4030cde3`
(symbol `UATRunner.run`, source-context digest
`834908206d879d78e9ffc3eb0353aa63f55e329c59f499aeeb521b77e5099d70`).

Applying this mutant produces a Python `SyntaxError` confirmed by `ast.parse`.
Its raw pytest exit status is **invocation-shape-dependent**, reproduced both
ways:

- `pytest tests/test_runners.py -q` (single file, no `-x`): exit code **2**
  ("Interrupted: 1 error during collection").
- `pytest -x --assert=plain tests/test_runners.py
  tests/test_runners_protocol.py tests/test_spawn.py
  tests/test_uat_reconcile.py tests/test_uat_session.py` (fettle's actual
  canonical mapped command for this file): exit code **1** ("1 error in
  0.12s", stopped after the first collection failure).

Mutmut's own `tests_pass()` (`mutmut/__init__.py:866`) is `return returncode !=
1`, so the single-file invocation's exit code 2 would be misrecorded as
"tests pass" (survived) despite total breakage, while the canonical
multi-file `-x` invocation's exit code 1 is recorded as killed. The canonical
run above does **not** list this fingerprint among `non_killed`, so mutmut's
own bookkeeping currently calls it killed for this file/mapping/version
combination. That classification is retained as-is, but **not presented as a
verified, intentional regression**: nothing in `tests/test_runners.py`
deliberately asserts import succeeds or exercises this exact line; the exit
code 1 is an incidental consequence of collection-order and the `-x` flag,
not an authored assertion.

This is unresolved classification evidence, not proof the mutant is
non-killable — the mutation is a genuine, non-equivalent break; what is
unsettled is which exit code a given invocation produces and therefore which
bucket mutmut's binary `returncode != 1` check assigns it to. The exact
runner command and pytest's collection behavior under it are the material
facts, not the mutant's intrinsic testability. A nonzero pytest exit must not
be generically read as "killed" — this entry documents the specific
mechanism so a future session does not rely on today's incidental exit-1
outcome as deliberate coverage, and does not mistake a differently-shaped
invocation (e.g. a narrower replay, a reordered mapping, or a future mapping
change) for a regression. No waiver, equivalence classification, or kill
credit is claimed for fingerprint `e3c5d0d8...0cde3` beyond the literal,
caveated mutmut bookkeeping state recorded here. A follow-up (out of this
session's bounded scope) would be an explicit regression asserting successful
import/construction of `fettle.runners`, which would make the protection
deliberate and invocation-independent rather than an artifact of command
shape.

Reran the focused tests with the recorded environment to confirm the current
(unmutated) source passes: `pytest -x --assert=plain tests/test_runners.py
tests/test_runners_protocol.py tests/test_spawn.py tests/test_uat_reconcile.py
tests/test_uat_session.py` → 800 passed, 20 opt-in skips, 31.19 s. Ruff clean
on `fettle/runners/__init__.py` and `tests/test_runners.py`. Required external
`python3 ~/.claude/plugins/fettle/scripts/cli.py check --changed`: no issues
found. No production code was changed; no threshold, waiver, or assertion was
weakened; no mutant was declared equivalent without the reasoning above.

The shared `.mutmut-cache` was moved aside before each raw-mutmut invocation
and restored byte-identical afterward (verified via directory listing) so
this cluster's work does not disturb other sessions' retained cache state.

This is a scoped developmental check on one file, not a refreshed full
mutation qualification. No new commit or push has occurred.

## 2026-09-23: Network Lifecycle Mutation Repair After 4522a56

Continued remediation without a new commit or push. Added 48 cases to the
existing session test module, with no production-code, threshold, or waiver
changes. Coverage now checks frozen source validation, the inclusive size
budget, exact isolation options, non-isolated network rejection, and cleanup
after each partial setup failure. Action tests cover request grouping, restart
identity, fractional deadlines, bounded/redacted failure output, continuation,
final product state, and aggregate cleanup failures. Browser tests use the real
artifact validator with a generated valid PNG, checking per-action artifacts,
qualified runtime options, schema rejection, and sensitive-output suppression.
These mocked execution tests are not runtime or browser acceptance evidence.

Every replay used a fresh archived checkout with the current test file, pinned
minimal dependencies, preflight, and canonical fingerprint inclusion checks.
Retained artifacts under `$TMPDIR`:

| Directory | Generated | Killed | Survived |
| --- | ---: | ---: | ---: |
| `fettle-network-owned-setup.4YFY6Isp` | 149 | 139 | 10 |
| `fettle-network-setup-followup.RGEM1l3x` | 43 | 39 | 4 |
| `fettle-network-owned-actions.ajKX1Kdl` | 170 | 119 | 51 |
| `fettle-network-actions-followup.YJdstBhb` | 88 | 84 | 4 |
| `fettle-network-policy.v3A3VHhX` | 45 | 45 | 0 |

All five runs completed with zero timeout, suspicious, or untested outcomes.
The six remaining historical network findings are equivalence candidates,
retained without waivers or kill credit:

- `0f2973914b8dc36dc283a990592a18d9ec37e6cde2f01af1e1b317140f0e3656`:
  integer versus true division of the fixed even response limit compares the
  same boundary against integer string lengths.
- `b4d843be569dd2688258f460d7e8d83174a11365262abeaf1d5c87bc7e36ca7a`:
  uncreated-resource flags initialized to `None` remain falsey; successful
  creation overwrites each flag with `True` before cleanup reads it.
- `eab41a39a8f547dac1b62cd5f13e35d4347c6bbdd844680d120838d16dd541a6`
  and `5f31e3551dc83c4b0eed41ac428e227662f803ffacd82812a29bb79b4dc32f6d`:
  initial stdout is overwritten by successful serialization or the exception
  handler before an observation is returned.
- `8c6fa4ac2c3b6284abc486d1c32fafa38e3f805f10d1ca73a7ce83c17413b0b3`
  and `f9a6c363988dbb3079669127d23eb44ac698d6b0a55e8be7477a292a531c4413`:
  the pre-raise stdout reset is overwritten by the catching handler's reset.

The newly generated bounded-read-offset survivor
`a0ba6978c075a8672b8028b9d80afbdd70ca70406fcd18554efc0da7ec3d8165`
also remains for explicit review. Reading limit-plus-two instead of
limit-plus-one does not change a stable, size-checked file, but file-growth
behavior needs classification; no implementation-spy assertion was added just
to manufacture a kill.

Owning-module regression: 338 passed, 20 runtime opt-in skips in 17.28 seconds.
The 48 new focused cases pass in the no-Playwright environment. Editor
diagnostics are clear. One initial overly broad test selector also selected a
VM/Git fixture that hit the known sandbox restriction; narrowing the selector
passed, and the complete owning module passed unsandboxed with working Git.
No global Git configuration or unrelated executable-bit changes were altered.

Developmental inventory now has narrow kill evidence for 1,368/4,478 historical
findings, with 3,110 remaining, based on 53 internally consistent completed
preflight/replay pairs. The network remainder fell from 316 to six. This union
is backlog accounting only, not an authoritative mutation score. Equivalence
review, the remaining module repairs, fresh full runtime verification, and
held-out full mutation qualification remain pending. Further commits while
findings remain require explicit operator approval; push is not authorized.

## 2026-09-23: Authorized Local Preservation Checkpoint

The operator explicitly requested a local commit to preserve the current work
after disclosure of the outstanding mutation findings. This checkpoint includes
the mutation mapping, candidate isolation, regression tests, and worklog only;
the two unrelated executable-bit changes remain excluded. No push is authorized.
This is not mutation qualification or milestone completion: 3,420 historical
findings still lack narrow kill evidence, and full runtime-enabled verification,
equivalence review, and fresh full mutation qualification remain pending.

## 2026-09-23: Post-Checkpoint Mutation Repair

Operator approved local checkpoint `941c6cf`, including DCO sign-off and all
applicable commit hooks. Its seven intended files were committed; unrelated
executable-bit changes remain untouched. Neither it nor `8797060` was pushed.
Further commits with mutation failures require new explicit approval.

The full ledger mapping ran assurance tests before the bounded lock regression.
Mapping now retains every discovered and explicit test, but runs the existing
convention-named owner test first, then the remaining tests deterministically.
The mapping fixture failed before the change; all 175 harness tests passed
afterward. Fresh full-mapping replay killed the historical lock-loop timeout
fingerprint with all four files in 14.085 seconds, without timeout, suspicious,
or untested outcomes. Mutation testing the changed ordering line killed 4/4.
The mapping digest changes, so previous cache identities cannot authorize reuse.
`kgraph` was unavailable; execution and mapping call sites were inspected directly.

The expanded 21-file CLI baseline passed 791 tests with 20 expected runtime
opt-in skips in the pinned minimal environment (40.159 seconds wall time).
This is not browser acceptance or proof every shard fits its budget. No timeout
budget, mapped test set, waiver, or score threshold was weakened.

Added 65 focused CLI cases for UAT capture consent, strict configuration,
reconciliation, acceptance exit status, exact evidence output, human diagnostics,
reporting, manual attestation, benchmark rendering, and capability readiness.
These use real result dataclasses with mocked execution boundaries; frozen
benchmark studies were not rerun. First scoped replay killed 67/69, retaining
one suspicious failure and one apparent equivalent. The next replay killed
137/143, including the suspicious fingerprint, with no timing failures. The
missing-operator follow-up killed 3/3. The acceptance-decision replay also killed
9/9 using all 21 CLI files in 54.156 seconds.

Developmental canonical inventory now covers 197/201 historical `cmd_uat`
findings. Four historical and two newly generated survivors appear equivalent:
five change the default `doctor` string in comparisons against other actions;
the sixth changes a local no-error sentinel from the empty string to `None`,
both false before the same output path. None is waived or counted as killed.
Artifacts are retained under `$TMPDIR` in `fettle-ledger-full-mapping.E5VKrG3P`,
`fettle-owner-order-replay.UOyvwmJr`, `fettle-cli-uat-dispatch.GKpM57C9`,
`fettle-cli-uat-reporting.13hDpoJj`, `fettle-cli-uat-operator.7AxdNff8`, and
`fettle-cli-uat-full-mapping.AbxwBhZW`. Scoped outcomes are not combined into
an authoritative mutation score. Full qualification and remote checks remain open.

The operator explicitly selected the final gate: **zero unresolved actionable
survivors**, separately reviewed equivalents, complete fresh mutation evidence,
and no tool errors, timeouts, or untested outcomes. The existing advisory score
policy alone cannot establish this gate. No new commit or push has occurred.

Specification CLI tests now assert complete subprocess output, warning/error
separation, missing-repository behavior, discovery continuation, and multiple
trace sources. All 54 specification tests pass. Initial command replay killed
85/92, including all 91 historical targets in its corpus; seven observed gaps
were then covered and a fresh focused replay killed 19/19. Artifacts:
`fettle-cli-spec-contract.JqwLaa0T`, `fettle-cli-spec-followup.P72oyruB`.

Reconciliation tests now cover exact transcript boundaries, conflicting retries,
restart artifact identity, judgment schema and artifact references, completion
criteria, verdict rendering, and canonical session identity. Restart replay
killed 129/136; judgment replay killed 82/92 (its range also included adjacent
auto-answer logic). Follow-ups covered the actionable heuristic and diagnostic
gaps. Completion replay killed every one of its 50 mutants; its combined
heuristic range retained one equivalent-candidate whitespace mutation. Early
session-error/formatting replay killed 48/53. A valid retained-artifact fixture
then killed the five web-readiness survivors: full session identity replay
killed 87/93, and canonical payload/non-pass follow-up killed 7/7.

Remaining scoped equivalence candidates are retained, not waived: unevaluated
local annotations, equivalent falsey parser sentinels, defaults for guaranteed
parser keys, valid-grammar whitespace removal, and judgment/session defaults
whose values do not reach an accepted evidence path. These classifications still
require review. A recovery-action mutation also needs explicit classification;
no claim is made that all reconciliation findings are resolved.

Reconciliation artifacts are under `$TMPDIR`: `fettle-reconcile-restart.rWNvfMyp`,
`fettle-reconcile-judgment.HbEDSEfv`, `fettle-reconcile-heuristic.3QDxUPJ3`,
`fettle-reconcile-completion.GIUhQvy2`, `fettle-reconcile-session-errors.Pi3FwarE`,
`fettle-reconcile-session-identity.Cb1OIWEw`, and
`fettle-reconcile-identity-followup.kNlP3Rni`. The accumulated edited test modules
and documentation checks passed **561 tests in 7.04 seconds**, with clean pinned
Ruff. This is not a refreshed full runtime-enabled suite.

Report persistence now has exact projection, capture replacement, directory,
canonical failure, and optional trace-failure tests. Its replay killed 99/110;
the follow-up killed 25/25, including all eleven survivors. Session orchestration
replay killed 89/104, then 25/25 on the survivor expressions. An intermediate
single-line preflight omitted one multiline Boolean expression and was stopped
before execution; expanding that expression included every target fingerprint.
All 41 historical report and 64 orchestration findings have narrow kill evidence.

Canonical report producer/validator tests use a valid retained session and
regenerated sidecars to distinguish semantic conflicts from stale hashes.
Replay killed 155/162, then 12/12 on captured-pass and disagreement boundaries.
All 28 historical targets in that slice have narrow kill evidence. Atomic-write
and digest checks cover flush-before-replace, failure cleanup, recursive parent
creation, strict Unicode JSON, and non-finite values. Replay killed 14/17, then
3/4; the remaining empty-string-to-None cleanup sentinel is an equivalent
candidate, not waived or counted as killed. Capture-validator mocks establish
orchestration contracts only, not independent runtime acceptance.

New artifacts under `$TMPDIR`: `fettle-reconcile-report.sASfTZKs`,
`fettle-reconcile-report-followup.YZPgDCc7`,
`fettle-reconcile-orchestration.4DfFjxmN`,
`fettle-reconcile-orchestration-followup.bf1bmGE6` (incomplete target selection),
`fettle-reconcile-orchestration-complete.yFy9WQdp`,
`fettle-reconcile-canonical.ybMroVCg`,
`fettle-reconcile-canonical-followup.S2cRh3i6`,
`fettle-reconcile-atomic.XzdxQLsE`, and
`fettle-reconcile-atomic-followup.8WhXNyYF`.
Accumulated edited-module and documentation checks now pass **702 tests in
8.42 seconds**, with clean Ruff and editor diagnostics. Full runtime-enabled
qualification remains pending; no new commit or push has occurred.

Candidate-isolation tests exposed a production defect: removing only scenario
headers let subsequent scenario/restart fields overwrite a preceding candidate's
observation. Four regression cases failed before the fix. The masking helper now
excludes complete verdict sections until the next candidate header; all 14
charter tests pass. Candidate replay killed 40/45. Exact claim-integrity tests
and a no-space candidate-field boundary killed 63/65 in the next slice; both
remaining claim mutants were subsequently killed with the full seven-file
mapping. Constant/default replay killed 10/10. Five historical masking mutations
belong to replaced code and are not counted as kills. New masking sentinels and
an unevaluated annotation remain equivalent candidates pending explicit review.

Observation artifact tests now cover exact serialized claims, canonical hashes,
safe filenames, duplicate-ID ambiguity, malformed/unreadable input continuation,
repeat writes, and browser capture parameters and diagnostics. Bundle replay
killed 61/62; browser/repeat-write follow-up killed 34/34. All 47 historical
artifact findings have narrow kill evidence. Browser boundaries use injected
optional-dependency-safe mocks, not a new runtime-browser qualification.

The owner-first mapping now falls back to the nested-module convention when the
flat owner is absent, while preserving flat-owner precedence, entry-point
exclusions, and every imported/explicit mapping. Its regression failed before
the change; all 179 harness tests pass. Self-mutation killed 20/23, then 10/10
on the remaining boundaries. A controlled seven-file comparison retained the
same test bytes, 13 fingerprints, and outcomes (10 killed, three equivalent
candidates): observed runtime decreased from 218.060 to 181.783 seconds.
This single comparison is not proof all shards fit their budgets. No timeout,
selection coverage, score threshold, or waiver was weakened.

Additional artifacts under `$TMPDIR`: `fettle-reconcile-candidates.G0RGXpGf`,
`fettle-reconcile-claims.hYAwfebt`, `fettle-reconcile-full-mapping.MljJKdp4`,
`fettle-reconcile-constants.ozSIn0RZ`, `fettle-observation-artifacts.n1Ht54ns`,
`fettle-browser-artifacts.D7jK9SfK`, `fettle-nested-owner-replay.bDBMsRWq`,
`fettle-nested-owner-followup.XGlQCdoz`, and
`fettle-reconcile-owner-first.V0J2VS0h`.

The complete affected mappings plus edited CLI/specification/documentation
modules passed **1,165 tests with 20 runtime opt-in skips in 49.07 seconds**.
An initial sandboxed attempt failed during Git fixture initialization because
Git could not read its normal user configuration; the unchanged suite passed
unsandboxed. Ruff and editor diagnostics are clean. The full runtime-enabled
suite, fresh full mutation qualification, equivalence review, and remote checks
remain pending. No new commit or push has occurred.

The developmental inventory now has narrow kill evidence for **1,058/4,478**
historical fingerprints, with **3,420 remaining**. Each counted replay has a
completed preflight and execution with matching generated/outcome cardinality;
the union is progress tracking only, never an authoritative aggregate or score.

## 2026-09-23: Mutation Evidence Repair In Progress

Retained all 256 initial reports from run `35729628122`: 245 completed and
11 tool errors, with 3,838 killed, 4,476 survived and one timeout in the retained
counts. The aggregate remains non-pass; these incomplete counts are not a valid
global mutation score. No new commit or push is authorized while mutation
failures remain without explicit operator permission. Local commit `8797060`
predates that instruction and remains unpublished; the remote head is `c8e80a2`.

Canonical fingerprint comparison exposed a harness defect: mutmut 2.5.1 stores
zero-based cache line numbers, but range collection compared them directly with
one-based source ranges. This omitted each range's first line and could admit
the following line from an existing cache. Three boundary fixtures failed
before the coordinate conversion and passed afterward. Mutation and specification
modules passed 222 tests. Older range-filtered corpora must not be reused as
complete qualification evidence; the failed historical reports remain retained.

Strengthened specification evidence tests for empty reports, missing IDs,
dependency-directory exclusion, unreadable and malformed text, unknown-marker
continuation, exact evidence fields, zero scenarios and fractional coverage.
A fresh bounded replay with the corrected harness generated 44 mutants and
included all 20 historical survivor fingerprints in the selected coverage lines:
44 killed, zero survivors, timeouts, suspicious or untested outcomes (45.45 s).
The ledger acquisition regression catches repeated successful lock acquisition
before concurrent tests can hang. Ledger tests: 47 passed. Its exact historical
timeout fingerprint was killed in 4.10 s with the ledger-only narrow mapping;
this does not establish the outcome under the full CI test mapping.

A disposable environment installed the hash-pinned mutation requirements and
confirmed Playwright was absent. The formerly failing controller/surface
baseline passed 102 tests, with 20 existing Docker/VM opt-in skips. This verifies
optional-dependency isolation, not browser runtime acceptance. Explicit CLI
mappings now include nine existing subprocess-based test files missed by direct
import discovery. All 21 selected files passed their baseline: 576 passed,
20 opt-in skips, 49.17 s. A fresh one-line CLI replay included both retained
`spec coverage` dispatch fingerprints and killed both in 105.54 s.

Network evidence follow-up added runtime-independent contract tests in the
existing session suite. Canonical replay included every historical target in
each selected function: browser steps 70/70 killed, browser settings 37/37
killed (36 historical targets), and expected-observation formatting 29/29
killed. Shared API/web contract replay initially killed 206/222; its range
also included two lines of the formatter subsequently verified separately.
Focused sequencing, printable-path and precise-diagnostic regressions then
killed 30/31 mutants on the remaining contract lines. Screenshot validation
initially killed 54/56; malformed high-byte dimensions exposed the remaining
two truncation mutants, and the follow-up dimension slice killed all ten.
These checks use synthetic pinned profile bytes and generated PNG data, not
claims about real browser execution or visual quality.

The remaining contract survivor is fingerprint
`0f2973914b8dc36dc283a990592a18d9ec37e6cde2f01af1e1b317140f0e3656`:
`LIMIT // 2` becomes `LIMIT / 2`. With the fixed `LIMIT = 65536`, this changes
an integer threshold of 32768 into the exactly representable float 32768.0;
comparison with integer UTF-8 byte totals has the same result. This is a
reasoned equivalence classification, not a killed mutant or approved waiver.
No survivor waiver or scoring policy was changed. Intermediate combined
verification passed 550 tests with 20 runtime opt-in skips; Ruff, Fettle and
editor diagnostics were clean. Later screenshot/formatting tests have focused
passing evidence; accumulated verification must be refreshed before shipping.

The refreshed verification passed all **3,692 tests in 557.07 seconds**, with
Docker and VM-restart opt-ins enabled and no skips. The dedicated runtime had
no remaining containers or volumes after its preceding 337-test integration
check. Docker transport replay killed 18/18 mutants, including all 14 historical
targets. Runtime identity replay killed 55/56 and classified one slow failure
as suspicious; its separately retained one-line replay killed both generated
mutants, including that fingerprint. The changed range-coordinate line itself
was mutation-tested against the full harness test module: 3/3 killed.

A developmental fingerprint inventory now has narrow kill evidence for 379 of
4,478 distinct retained non-killed fingerprints; 4,099 have no such evidence
yet. This inventory combines scoped development checks for progress tracking
only, not authoritative calibration outcomes or a mutation score. The original
11 tool errors and the historical range-filter defect still require fresh full
evidence on a qualified revision. No new commit or push has been made.

These are scoped developmental checks, not a full mutation qualification or
completion claim. Other survivor clusters, runtime-enabled checks, fresh full
evidence and remote verification remain open. No threshold or waiver was relaxed.

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

## 2026-10-05: Integration And Automated-Acceptance Authorization

The owner authorized integration of the qualified run-05 working-tree candidate,
the reviewed checkpoint mechanism, executable-mode repair, and release-gate
hardening on a separate branch. The accepted review scope is the exact 68-path
candidate: Milestone A plus concurrent UAT acceptance-integrity work. This is not
blanket acceptance of every change, and the base commit alone does not identify the
qualified candidate. Run-05 and its raw evidence remain unchanged.

The owner also replaced AH07 07.4's previous human-independent-review requirement
with independent automated acceptance because no human reviewer is available. The
automated reviewer must operate read-only in a separate isolated session, inspect
artifacts directly, execute relevant checks, and issue criterion-by-criterion
verdicts with evidence and limitations. This replacement applies only to reviewer
type. No human acceptance or human-usability validation was performed. Platform,
live-host, artifact, remote-CI, participant-dependent usability, and strict
completion requirements remain unchanged and non-pass when unavailable.

Integration branch `audit/hardening-integration-20261005` started from revision
`4522a564791bce326ca4f340f7007f09e988b8e1`. The exact qualified nine-file content
overlay was applied. The two mode-only regressions were corrected to `100755`; a
missing shebang in `fettle/import_graph.py` was exposed by the new direct-execution
test and repaired. Checkpoint mode preserves the evaluator payload and changes only
process exit for valid-incomplete evidence. Strict completion remains an independent
dependency of `CI required`; release validation remains strict. The interactive tag
gate now rejects both invalid and valid-incomplete completion evidence.

The first bootstrap commit attempt was blocked by supported pre-commit safeguards:
the modified hook configuration was unstaged, the worktree lacked a pytest-capable
`.venv`, and copied completion evidence had a stale digest after path sanitization.
No hook was bypassed. The supported recovery staged the checkpoint boundary with the
qualified overlay, provided a worktree-local ignored link to the existing isolated
Python 3.12 environment, and rebound the completion manifest to the transformed
evidence digest. Subsequent hooks passed.

The inactive `.coverage` file was verified to have no open writer and moved outside
the scanned tree to `external://local/audit-hardening/preserved/original.coverage`.
Its SHA-256 remains
`2ee0135d567926157d1fecafb81f0fb09391cdd6de1c31f18b46cad1242f2435`.
It was not deleted. A separate sanitized run-05 copy contains all 100 files; only 34
absolute-path tokens across 21 files were replaced. Its transformation-manifest
SHA-256 is `34f1a531ef883f7bb293e5290a9badfab66e5e883c17ac10cbb1d8057ffc639c`;
the local archive SHA-256 is
`4de5f7f44fcc591a4d7a566b80658dc51fa7365182bd95ee0099934f0706b7dd`.
The sanitized copy is distribution material, not historical qualification evidence,
and was not uploaded.

## 2026-10-05: PR Fan-Out Containment And Mutation Incident Diagnosis

PR #46 remains open and unmerged. Historical candidate `b81ef588de3a20cc3ed8e1938de8c10ef7f295cb`,
tree `53869aefa41e577db921d487358fa3850033afde`, run-05, and the cancelled
run `37279176089` remain immutable baselines. No mutation qualification was run.

Containment commit `f52a9bcbada906672595ebe515d43c71f67227d4` keeps the unfiltered
`pull_request` trigger and required `mutation evidence` context, but PRs now only
prepare changed-scope manifests. No PR execution or replay matrix is created.
Mutation-relevant scope emits `status=unknown`, `passed=false`, and fails the
required check; genuinely empty mutation scope may pass as explicitly
non-applicable. Preflight, replay, and calibration remain available through
maintainer `workflow_dispatch`; retained-preflight identity checks, survivor
enforcement, thresholds, and strict completion are unchanged. Branch protection
still requires `CI required` and `mutation evidence`; no repository setting was
changed.

Remote run `37300585637` confirmed containment. It ran one preparation job and one
required evidence job. All preflight, full-shard, and aggregate jobs were skipped.
The required evidence job failed as designed because this PR has mutation-relevant
scope and no dispatched qualification. This is a truthful non-pass, not a waiver.

The retained incident contains 256 distinct shard identities and 289 report
attempts: 256 initial, 32 replay, and one aggregate. Outcomes are 84 completed,
185 tool errors, 19 malformed replay artifacts, and one unknown aggregate. The 19
malformed records are zero-byte files created by shell redirection before their
cancelled replay commands produced JSON. They contain no mutation verdict. The
completed reports remain partial diagnostics and were not combined into a score.
The private attempt-level inventory binds each attempt to its manifest, command,
candidate revision, outcome, artifact digest, and initial/replay relationship.

The dominant restoration incident is consistent with a demonstrated local
process-lifecycle defect. Each initial shard used an isolated hosted-runner
checkout, rejecting shared cross-shard source state as the primary explanation.
Within each job, however, the wrapper started mutmut as a POSIX process-group
leader but skipped process-group termination after a normal leader exit. A surviving
descendant could therefore write a mutant after the wrapper's restoration check.
A harmless delayed-writer fixture reproduces this against `b81ef588`: the wrapper
returns success, then `quality_scan.py` changes. The minimal repair terminates the
POSIX process group immediately after `communicate()` even if the leader has exited,
before checking source integrity. The same fixture preserves exact bytes and mode
for both `quality_scan.py` and `import_graph.py` after the repair. Existing timeout,
SIGTERM, keyboard-interrupt, unexplained-drift, and restoration-integrity tests
remain enabled; no error is suppressed and no timeout changes.

The retained reports establish the expected state as the exact pre-run bytes and
mode and the actual state as unequal without a matching byte-identical `.bak`.
They do not serialize the exact post-failure bytes or mode, so those values are not
reconstructed. This demonstrated defect is consistent with both restoration
families, but the retained evidence cannot prove it caused every occurrence.
Timeouts remain separately classified and unexplained by this repair.

The fix changes mutation infrastructure, so ordinary CI and focused process tests
must be reassessed for the resulting candidate. Run-05 itself is not relabelled and
does not need replacement: the acceptance contract requires its already-qualified
exact dispatcher target, tests, mapping, policy, dependency lock, and frozen
configuration—not a new broad mutation qualification for workflow/process-wrapper
changes. The smallest justified verification is the harmless descendant fixture,
the focused mutation suite, ordinary CI, and strict incomplete completion. A new
full matrix or failed-shard replay is neither required nor authorized.
