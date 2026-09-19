# Audit Hardening Worklog

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
- [ ] Commit verified changes and push; watch exact-candidate remote CI to completion.
- [ ] Record platform/live-host evidence and remaining human UAT prerequisites.
- [ ] Reassess AH08-AH15 admission in dependency order; do not bypass missing gates.
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