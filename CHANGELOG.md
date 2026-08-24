# Changelog

## Unreleased

### Change Integrity (P38, P45)

- Added canonical specification traceability (`fettle.trace_canonical`):
  stable-ID marker index, marker validation against active scenarios,
  executed-result binding where declaration is linked but only a passing run
  verifies, and drift evidence separating uncovered scenarios, unknown
  markers, orphan tests, governed changes without review, and executed
  coverage. Filename-substring inference in `trace_requirements` is now
  deprecated.
- Added graph-independent source snapshots (`fettle.source_snapshot`):
  deterministic committed manifests from Git tree objects, content-hashed
  working manifests covering tracked, untracked, and required-ignored inputs,
  merge-conflict non-pass detection, LFS pointer flagging, restrictive
  temporary materialization with per-byte verification, read-set
  revalidation for transient edit/restore races, and policy-provenance
  identity binding.

### Rules

- New enforced rule `test-flow-root-cwd` forbids cwd-relative roots in
  mutation-flow calls inside test functions (shard-201 lesson), with
  compliance mapping to CWE-362.

### Packaging

- Extras are real install targets now; `pip install "finefettle[all]"`
  composes every capability in one command on top of the already
  batteries-included core wheel.

### Mutation Evidence

- Added bounded automatic replay for incomplete changed-scope mutation shards
  behind one authoritative required `mutation evidence` PR check. Missing or
  non-completed initial shards retry only their original digest-bound
  manifests, and aggregation still fails closed on missing, conflicting, or
  timed-out evidence with the offending shard named.
- Isolated Fettle's own mutation-flow tests from the repository root so a
  mutated configuration default can no longer delete the live runner cache
  during self-mutation.

### Installation And Documentation

- The default `finefettle` installation now includes Fettle's Python analyzers,
  test and mutation runners, commit-hook support, behavioral-evaluation parser,
  and browser-automation library. `pipx install finefettle` is the single
  supported Python installer command; browser binaries, agent hosts, Git, and
  non-Python language toolchains remain explicit external runtimes.
- Refreshed the README and active guides around a two-minute proof, safe agent
  activation, capability boundaries, recovery, and independently bound evidence.
- Graduated Claude Code to `supported-installed` after a live candidate-wheel
  session surfaced Ruff F401 through its native `Write` lifecycle and recorded
  matching session-linked audit evidence.

## v1.11.1 — Python 3.11 Evidence Compatibility

**Released 2026-08-15**

### Fixed

- Restored canonical evidence parsing on Python 3.11 by validating serialized
  result states through the enum constructor instead of version-dependent enum
  containment behavior.

## v1.11.0 — Wheel-Native Agent Governance

**Released 2026-08-15**

### Adoption And Packaging

- Added a contract-tested two-minute assurance example with violating and clean
  fixtures, a text transcript, and an accessible terminal summary.
- Added a versioned installed-package governance bridge so the wheel can
  register Claude Code, Codex CLI, Gemini CLI, and OpenCode without a source
  checkout. Bridge manifests bind package version, interpreter, and every owned
  file; dry-run, idempotency, tamper detection, malformed host configuration,
  and paths with spaces have regression coverage.
- `fettle doctor` now validates an installed bridge and recognizes hook
  registrations for all four supported hosts.
- Added structured public bug and feature intake plus a bounded contributor
  entry path. Discussions remains demand-gated.

### Canonical Evidence

- Added a zero-runtime-dependency canonical evidence kernel with immutable
  artifacts and references, deterministic full SHA-256 content identities,
  separate execution occurrence identities, strict bounds, secret/path
  filtering, and typed fail-closed validity outcomes.
- `fettle verify` now atomically writes `.fettle/verify-evidence.json` alongside
  its legacy stamp. The artifact binds the exact source snapshot, effective
  policy, selected scope, producer implementation, command outcome, and run
  occurrence.
- The Stop gate validates canonical evidence whenever a new stamp claims it and
  reports one recovery command, `fettle verify`, for missing, malformed,
  tampered, incomplete, stale, or mismatched evidence. Legacy-only stamps remain
  supported for rollback during the migration window.
- The frozen P66 adversarial corpus now executes against the runtime validator.
  Cross-process determinism, split writes, policy/source/scope replay,
  occurrence substitution, installed-CLI output, and host-wire compatibility
  have regression coverage.
- Remote CI now writes an independent canonical sidecar bound to its exact
  candidate, policy, workflow scope, producer, toolchain, result, completeness,
  and occurrence. Copied, stale, malformed, incomplete, or mismatched evidence
  remains non-pass; local verification evidence cannot replace remote authority.
- Trace retains bounded canonical references as diagnostic-only history, while
  detailed explain and report output expose matching human/JSON acceptance and
  rejection reasons. Durable attestations remain a separate P41 boundary.
- Coverage, UAT, integrations, mutation, and override migration remain separately
  gated under P69-P70.

## v1.10.0 — Reproducible Mutation Evidence

**Released 2026-08-15**

This release turns full-repository Python mutation testing from an expensive
experiment into reproducible assurance evidence. Fettle now has an accepted,
independently reproduced mutation baseline for its own codebase, a resumable
fingerprint-keyed calibration path, and stricter separation between actionable
survivors and other evidence-debt outcomes.

### Authoritative Mutation Calibration

- Two independent full calibrations on one pinned revision produced the same
  28,723 canonical outcomes: 14,107 killed, 14,611 survived, five native
  timeouts, zero suspicious, and zero untested mutants.
- The accepted `.fettle/mutation-baseline.json` records the exact revision,
  engine and runner identities, policy and scope digests, report identities,
  survivor fingerprints, measured 49.1 percent floor, and 80 percent aspiration.
- Full calibration can resume by canonical fingerprint without rerunning
  terminal mutants. Checkpoints fail closed on incompatible execution identity,
  conflicting outcomes, missing evidence, or incomplete ledgers.
- Preflight, historical replay, full execution, aggregation, and policy remain
  separate stages. A full run is held-out verification, not a discovery tool
  for parser or engine-output defects.

### Honest Comparison And CLI Recovery

- Baseline comparison now applies `new` and `existing` only to surviving
  mutants. Native timeout, suspicious, and skipped outcomes retain their own
  debt classes and explicit budgets instead of becoming false new survivors.
- `fettle mutation status` now loads policy correctly when evaluating a retained
  report against a committed baseline.
- Regression tests cover accepted timeout debt and the baseline-present status
  command. The authoritative source report passes self-comparison with 14,611
  existing survivors, five visible timeouts, zero resolved mutants, and no score
  delta.

### Documentation And Adoption

- The README and documentation index now present Fettle by user journey: local
  evaluation, live agent governance, independent verification, mutation
  evidence, delegated work, and human-controlled policy learning.
- The configuration reference documents the mutation command and policy
  contract, including explicit evidence-debt budgets and advisory-first use.
- Behavioral-evaluation and VS Code instructions now use current executable and
  package paths.

Mutation changed-scope policy remains advisory while representative runs and
reviewer feedback establish actionability and runtime. The accepted repository
floor is evidence, not a claim that 49.1 percent is a universal quality target.

## v1.9.0 — Trustworthy Change Evidence

**Released 2026-08-07**

This release strengthens Fettle's evidence boundary: scanner failures remain
visible, change-integrity records have deterministic contracts, selected
concurrent protocols are model-checked, and multi-agent roles can enforce
authorship separation. Mutation testing is now honest and operational in an
advisory workflow, but remains evidence-gated rather than enforced.

### Evidence Integrity

- Required scanner and CI failures use canonical non-pass states instead of
  becoming clean results through malformed output, missing tools, or wrapper
  errors (P33).
- Mutation analysis pins `mutmut==2.5.1`, selects changes from an explicit
  merge base, distinguishes changed and full-source runs, and fails closed on
  tool errors, parser errors, timeouts, and zero-mutant runs (P34).
- A seeded weak-assertion fixture proves the mutation wrapper reports two
  surviving mutants and a `0.0%` score rather than manufacturing success.
- Pull-request and scheduled mutation jobs retain JSON evidence. They remain
  advisory until three stable CI runs establish a baseline and ratchet.

### Change-Integrity Contracts

- Canonical source, graph, provider, traversal, freshness, closure, and
  obligation records use deterministic identities and fail-visible states
  (P44).
- An adversarial fixture corpus covers cycles, duplicate facts, malformed
  attributes, oversized output, provider failures, and path/Unicode variants.
- Runtime snapshots, graph assembly, advisory impact, and graph-bound CI remain
  proposed and do not replace existing authoritative checks in this release.

### Formal Verification And Multi-Agent Roles

- TLA+ models check Policy Capsule monotonicity and Work Item Claim safety,
  including claim exclusivity, conservative unknown scope, claim-before-work,
  and lock mutual exclusion (P43, two of five planned models).
- CI reruns TLC when modeled source changes; the `tla_sync` hook advises when
  source annotations and specifications drift.
- The authorship gate and `--role` plumbing can require test and implementation
  changes to come from separate roles in multi-agent work (P52).
- P43 and P52 remain in progress: additional models, refinement evidence,
  adversarial path coverage, and an evidenced multi-agent flow are still
  required for graduation.

### Documentation And Distribution

- README and task-oriented documentation now distinguish CLI/CI installation
  from live-agent hook installation, and describe supported agents, languages,
  evidence states, and trust boundaries without implying unshipped behavior.
- The source distribution now includes all 17 workflow command sources, so a
  wheel reconstructed from the sdist retains the same bundled workflows.
- Release CI verifies bundled rules and commands in both the wheel and an
  installation reconstructed from the sdist before OIDC publication.
- Package metadata adds Documentation and Issues links and declares version
  `1.9.0` with no runtime dependencies.

## v1.8.0 — Canonical Workspace/Adapter Substrate

**Released 2026-08-07**

The v1.7.x unreleased R2 work graduates with 2,102 passing tests and a unified
workspace/adapter layer. This release consolidates polyglot post-edit checks,
fixes agent-hook paths, and improves documentation and onboarding.

### Canonical Result States

- Every adapter operation returns one of four explicit states: `pass`,
  `violation`, `tool_error`, or `unknown`. Missing tools, timeouts, and
  malformed output are reported as degraded analysis, not clean passes.
- Findings carry actionable fields (file, line, code, message, rerun command)
  and optional evidence references. The host-wire contract remains strict and
  unchanged for Claude Code/Codex/Gemini/OpenCode transports.
- Behavioral evals report repair success, turn counts, repeated violations,
  diagnostic bytes, and indeterminate reasons, with Python and TypeScript
  held-out baselines validating the feedback loop.

### Workspace-Aware Polyglot Checks

- Workspace discovery uses one canonical model supporting nested projects
  (monorepos), longest-prefix routing, and per-workspace command overrides.
- Post-edit lint routes through one workspace-aware adapter entry point for
  Python, JavaScript/TypeScript, Go, and Rust. File classification is shared
  across gates.
- JavaScript/TypeScript checks prefer repository scripts and package-manager
  execution (ESLint/Biome, Prettier, TypeScript, Vitest/Jest, Knip). Missing
  tools, missing build scripts, and unparseable failures surface explicitly.
- Semgrep rules for TypeScript and Go now run inside their language adapters
  (`ts-antipatterns.yml`, `go-antipatterns.yml`). Obsolete standalone
  `post_edit_ts.py` and `post_edit_go.py` routes removed.
- Verification records every affected workspace while preserving the existing
  single-workspace stamp contract. Deleted code remains verification-relevant.
- Nested Python workspaces use impacted-test mapping when reliable, falling
  back to full suites instead of treating empty mapping as success.

### Agent Integration Fixes

- Claude Code/Codex/OpenCode hook paths corrected from `scripts/run.sh` to
  `fettle/run.sh`. Hooks.json and install.py now reference the correct launcher,
  protected by a regression test.
- OpenCode transport updated to use `fettle/run.sh` with clearer environment
  variable guidance in docs/OPENCODE.md.
- Workflows error messages improved: distinguish missing directory vs empty
  directory, and provide actionable hints for pipx editable-installs.

### Documentation & Onboarding

- README.md overhauled with compelling positioning, unique feature highlights,
  clear pipx installation guidance (avoid editable installs for bundled
  resources), and better structure for new users.
- All docs/ reviewed for consistency: README.md index, CONFIG.md workspace
  contract, ROADMAP.md graduation status, OPENCODE.md launcher paths.
- CONTRIBUTING.md and SECURITY.md added with development setup, verification
  guidance, and vulnerability reporting channels.
- Error messages across workflows and install paths made more actionable.

### Testing & Verification

- 2,102 collected tests passing (up from 2,100+).
- Test suite covers adapter unification, workspace routing, deleted-file
  handling, hook launcher paths, and Semgrep integration per language.
- Quality scan gates: Ruff, Fettle scan, schema/CLI consistency, eval
  validation, impacted-workspace verification.

### Breaking Changes

- The temporary `migrate_adapter` compatibility bridge removed. Adapters now
  follow the canonical `LanguageAdapter` protocol with `supports()`,
  `classify()`, and workspace-first operations.
- Standalone `post_edit_go.py` and `post_edit_ts.py` deleted. All polyglot
  post-edit checks route through `fettle.adapter_check.run_adapter_check()`.

### Migration Notes

- Existing `.fettle.toml` files remain compatible. No action required unless
  you have custom language adapters (update to workspace-first protocol).
- Agent hooks installed by v1.7.0 will auto-update paths when you run
  `fettle init` from the new checkout. Alternatively, manually update
  `scripts/run.sh` → `fettle/run.sh` in your hook configurations.
- pipx editable installs (`pipx install -e .`) bypass the build step that
  bundles `commands/` into the wheel. Use `pipx install --force .` for
  non-editable installs, or install from PyPI once v1.8.0 is published

## v1.7.0 — Workflows Everywhere

The 17 fettle workflows now install into every supported agent CLI, and
the config resolver is one honest chain:

- **`fettle workflows install`**: renders the canonical `commands/*.md`
  into native slash-command formats for Claude Code, VS Code prompts,
  Codex, Gemini CLI, and OpenCode — marker-owned files, idempotent,
  user-edited copies never overwritten. `fettle init` installs them for
  detected agents; `fettle doctor` reports drift (warn-only). Workflow
  sources ship in the wheel (`fettle/_commands/`).
- **Workflow content refresh**: all commands run via the `fettle` CLI or
  `python3 -m fettle.<module>` (no `CLAUDE_PLUGIN_ROOT` scripts); `learn`
  documents the quarantine flow (`rules/proposed/` → `fettle rules
  promote`); templates resolve from the installed package.
- **Unified config resolver** (closes audit H-05): one precedence chain
  for gates and `fettle config` — defaults → org.toml → team.toml →
  remote `[extends]` → repo → directory overrides (per-file) → env →
  capsule (tighten-only). `--print-effective` shows exactly what gates
  load; `--explain` attributes every key, including env/capsule effects.
- **Migration note**: `$XDG_CONFIG_HOME/fettle/org.toml` and `team.toml`
  previously affected only `fettle config` output; they are now enforced
  at runtime by every gate. Directory `.fettle.toml` files now affect
  per-file gates. Audit those files if you relied on them being inert.
- **shellcheck bootstrap**: `fettle init` installs shellcheck (brew/apt),
  and `fettle doctor --fix` repairs a missing install; the doctor warning
  carries the per-OS install command.
- Alignment fixes: VS Code extension is Python-only and drops never-read
  settings (M-12); `fettle explain` renders finding locations from the
  global trace (L-01); both trace stores documented (L-02); orphaned CI
  template removed (L-05); evals scenarios are contained to their
  workdir — path escapes cannot read or write outside it (L-06).

## v1.6.2 — CI Truth

CI now proves what the docs claim (audit M-08/M-09/M-10/M-11/L-07):

- **Blocking lint job**: `ruff check fettle tests` gates every push.
- **Coverage job**: branch coverage with a no-regression floor of 65
  (measured baseline 67%; subprocess-driven hook tests are invisible
  to coverage) — the floor ratchets toward the config gate's 80.
  `coverage.xml` published as a build artifact.
- **Python matrix**: 3.11 / 3.12 / 3.13 block on ubuntu, 3.12 on
  macOS; Python 3.14 and newest-semgrep legs run as non-blocking
  canaries.
- **Supply-chain pins**: every workflow tool pip-pinned exactly and
  every third-party action pinned by commit SHA; the reusable workflow
  drops its unused `pull-requests: write` permission.
- **Type-check honesty**: a non-blocking mypy job backs the
  `Typing :: Typed` classifier until the baseline reaches zero.

## v1.6.1 — Hardened Gates

Remediation of a two independent external audits (both at v1.6.0): every
HIGH and MEDIUM finding closed, plus the integration adapters finally
wired to the CLI.

- **Hook contract fixed** (H-01/C1): gates read the normalized
  `hook_event_name` field and block reasons survive the dispatcher —
  Stop/UX/plan blocks no longer silently downgrade.
- **Capsule version skew fails closed** (H-02): an env-asserted policy
  capsule newer than the runtime is now a hard error, not a silent
  fallback to defaults.
- **MCP trust gate hardened** (H-03/H-04): package-install regex covers
  newline/env/command/`python -m pip` bypasses (21-variant corpus);
  file-path checks resolve `~` and relative paths identically in both
  the subprocess and dispatcher paths; `doctor` surfaces env allowlist
  redirects.
- **Verify stamps bound to their session** (M-04): stamps carry
  session id + HEAD sha + dirty digest; foreign or out-of-scope stamps
  fail closed, unchanged trees are redeemed.
- **Injection surfaces closed**: learned-rule ids validated/slugged with
  path-containment asserts (M-01); VS Code extension shell-quotes every
  interpolated value (M-02); telemetry/cross-review endpoints must be
  https or real loopback, CI repo slugs regex-pinned (M-05).
- **Truthful plumbing**: `fettle doctor` propagates its exit code in CI
  (M-06); claims ledger writes are flocked + atomic (M-03/WP-5); trace
  log rotates (WP-6); `evals` needs `pip install 'finefettle[evals]'`
  and says so (M-07).
- **Registry imports are lazy**: gate modules load at call time —
  registry import ~46 ms vs ~79 ms eager, verified by a purity test.
- **`fettle integrations`** (C14): SonarQube / Black Duck / Pact
  adapters now reachable — `fettle integrations [name] [--json]`, new
  `[integrations.*]` config sections, doctor readiness probes.
  Exit contract: 0 pass, 1 findings, 2 misconfigured/unavailable.
- **Honest config output** (H-05 stopgap): `fettle config
  --print-effective` names the sources it does not include (central
  policy, env overrides, capsules) until the resolvers are unified.
- Test tree consolidated under `tests/` (canonical `pytest tests/ -q`);
  suite: 1989 passed. `ruff check` clean across `fettle/` and `tests/`.

## v1.6.0 — Reliable Sessions

Every session now has a governed shape: plan before work, worklog while
working, structured completion report after — and orchestrators can read
all of it in one poll.

- **Session plans** (`fettle/session_plan.py`): `fettle plan start
  --title … --item …` writes a frontmattered checklist to
  `.fettle/plans/`; `fettle plan check <text>` ticks items;
  `fettle plan status` shows progress. The planning gate accepts a fresh
  session plan as planning evidence (`[gates.plan].session_plans`,
  default on), and at Stop the worklog check reconciles the plan —
  unchecked items become an advisory, never a block.
- **Worklog scope** (`[gates.worklog].scope = "daily"|"session"`):
  `session` requires the worklog to have been updated during *this*
  session, not just today — closing the stale-worklog loophole.
- **`fettle init --interactive` / `--profile solo|team|enterprise`**:
  a five-question interview (or a preset) generates an annotated
  `.fettle.toml` matched to team size, strictness, compliance, and
  multi-agent use. Never overwrites without `--force`; every profile's
  output is schema-validated by test.
- **Completion contract** (`[gates.session_report]`, off by default):
  at Stop, a session writes `.fettle/reports/<session>.json` — files
  edited, claims held, plan progress, verify/CI stamp state. Never
  blocks; write failures are silent. The enterprise profile enables it.
- **`fettle topology report`**: predicted-vs-actual join over the last
  topology — recomputed footprints against actually-edited files from
  completion reports, pairwise overlaps, per-worker friction, stamp
  state. Facts, not verdicts.
- **`fettle brief [--json]`**: one offline poll for orchestrators —
  active plan, claims, topology workers, cached CI verdict, open rule
  proposals, top friction codes, recent completion reports.
- **UX batch**: bare `fettle` inside a repo renders the brief dashboard
  (offline, cached CI only) instead of a manpage; `fettle doctor --fix`
  applies mechanical fixes only (wiring declared-but-uninstalled
  pre-commit hooks, then re-verifying); every dispatcher block appends
  "→ fettle explain — full context for this decision".
- **`fettle learn` is now a first-class subcommand** — the documented
  `fettle learn --from-trace [--auto-save]` / `--incident` interface
  previously required invoking the module directly.

## v1.5.0 — Governed Self-Evolution

Fettle now learns from its own evidence — without ever changing policy on
its own. Sensing and drafting are autonomous; promotion is a human command
(WP-163, adapted from hermes-agent's closed learning loop).

- **Failure-signature sensing** (`fettle/evolution.py`): read-only
  detectors find repeated friction the rules don't cover — the same
  `(hook, code)` blocking or firing ≥ 3× in the window with no covering
  rule file, and recurring CI failure classes from the ingested history.
  Evidence samples are secret-redacted.
- **Proposal quarantine** (`fettle learn --from-trace [--auto-save]`):
  draftable signatures become rule proposals in `rules/proposed/` — a
  directory no gate ever loads (pinned by test). With a local LLM the
  full learn pipeline drafts the rule; without one, a deterministic
  *evidence brief* ships with an empty pattern that promotion refuses
  until a human completes it.
- **`fettle rules list|promote|demote`**: the human gate. `promote <id>`
  moves a completed proposal to `rules/learned/` (loadable via
  `[rules].extra_dirs`); `promote --candidates` computes promote/demote
  candidates from ratchet evidence (fires vs FP stamps) — stats are
  computed, decisions are not. `demote <id> --reason` returns a noisy
  rule to quarantine. Mode (advisory→enforce) stays with `fettle ratchet`
  and its evidence bar.
- **`fettle insights [--days 7]`**: read-only weekly digest — top
  friction gates, emerging failure signatures, rule-pipeline candidates,
  ungoverned lineage sessions. Cron recipes (insights, drafting, nightly
  hash verification) documented in docs/CONFIG.md — recipes, not a daemon.

## v1.4.0 — Governed Delegation

Policy now survives delegation: when an agent spawns another agent, the
child inherits the parent's effective policy as a tamper-evident capsule.

- **WP-156 — Policy capsules** (`fettle/policy_capsule.py`): the effective
  config is serialized to a sha256-digest-named capsule under
  `$XDG_STATE_HOME/fettle/capsules/`; children resolve it via
  `FETTLE_POLICY_CAPSULE` and merge it monotonically — a child can only
  tighten policy, never weaken it (mode ladder, enabled=true wins,
  direction-aware numeric thresholds; local weakenings are surfaced, not
  silently applied). Tampered or missing capsules fail closed: the new
  `capsule_guard` check (first PreToolUse check) blocks every tool call
  until re-spawned. `FETTLE_GATE_MODE=off` cannot defeat a capsule.
- **WP-157 — `fettle spawn <runner> --task ...`**: the blessed path for
  launching child agents (claude/codex/gemini/opencode via the Stage 13
  runner registry). Writes the capsule, chains lineage (depth cap 16),
  exports `FETTLE_POLICY_CAPSULE` + `FETTLE_PARENT_SESSION`, optionally
  provisions and claims a per-item worktree (`--worktree ITEM`), and logs
  the spawn to the audit trail.
- **WP-157 — `[gates.agent_spawn]`** (default on, advisory): detects raw
  nested agent launches (`claude -p`, `codex exec`, `gemini -p/--yolo`,
  `opencode run`) and points at `fettle spawn`; launches composed with
  hook-bypass flags (`--dangerously-skip-permissions`, `--yolo`,
  `--full-auto`) or `FETTLE_GATE_MODE=off` block in `enforce`.
  `fettle doctor` gains a per-runner hook-parity probe.
- **WP-158 — Lineage**: every trace entry carries `parent_session_id` +
  `capsule_digest` (audit schema v2, additive). `fettle report --lineage`
  renders the delegation forest — who spawned whom, under which capsule,
  with per-session edit/block/advisory counts and `UNGOVERNED` flags.
- **WP-162 — `[worktrees].require`** (default off): when on, main-worktree
  edits to non-exempt paths (default exempt: `docs/**`, `**/*.md`) are
  gated behind `fettle worktree create <id> && fettle work claim <id>`,
  honoring `gates.claims.mode`.
- **WP-159 — `fettle topology advise`**: deterministic, explainable
  topology recommendation (solo / writer-reviewer / pipeline /
  parallel-workers) from open work items, spec links, trace friction, and
  *footprint disjointness* — each item's `scope` globs widened one hop
  along the import graph; overlapping (or unknowable) footprints refuse
  to parallelize, with the overlap named.
- **WP-160/161 — `fettle topology apply` / `status` / `revoke`**: apply
  provisions worktrees + claims for the advised topology, writes a
  `topology.json` manifest to the shared git common dir, and emits the
  `fettle spawn` commands; status joins manifest × claims × trace with
  per-worker stop-loss flags (`--max-blocks`); revoke releases an item.
  No supervisor daemon — coordination stays claims-file + trace.
- **Unified blocking-mode vocabulary**: `gates.tdd.mode` and
  `gates.ci_bootstrap.mode` now accept `enforce` (the canonical blocking
  spelling used by every other blocking gate) in addition to `strict`,
  which remains a fully supported legacy alias. No behavior change for
  existing configs.

## v1.3.1 — Parity & Provenance

- **Stage 13 — full hook parity for Codex CLI, Gemini CLI, and OpenCode**:
  - *Inbound*: new `fettle.agents.codex` and `fettle.agents.gemini`
    translators — Codex's Claude-compatible wire (detected via its
    `turn_id` extension, native `shell`/`apply_patch` tool ids mapped
    defensively) and Gemini's `BeforeTool`/`AfterTool`/`AfterAgent`
    events with `run_shell_command`/`write_file`/`replace`/`read_file`
    tools all normalize to the same event model, pinned by shared
    conformance fixtures across all four agents.
  - *Event-correct output wire*: blocks now always carry top-level
    `decision: "block"` + `reason`; `permissionDecision` is emitted on
    PreToolUse only, and Stop/SubagentStop output never carries
    `hookSpecificOutput` (Codex parses hook output with
    deny-unknown-fields — the old blanket shape was illegal there).
    Stop advisories ride `systemMessage`; a clean Stop is `{}`.
  - *Registration*: `fettle init` now wires `~/.codex/hooks.json` (with
    an action step for the `features.hooks` toggle) and
    `~/.gemini/settings.json` (Gemini timeouts in ms) — idempotent JSON
    merges that preserve existing entries, like the OpenCode step.
  - *Outbound*: headless `AgentRunner` adapters for `codex exec
    --full-auto`, `gemini --yolo -p`, and `opencode run` join `claude`
    in the runner registry (shared subprocess core, same fail-visible
    contract); `fettle doctor`/UAT probe all four, and
    `FETTLE_EVAL_RUNNER` selects the evals agent.
- **Stage 12 — WP-148 opt-in telemetry**: anonymous aggregate counters
  (decisions / fired / blocked / overridden / tool errors) with a fully
  documented payload (`fettle-telemetry/1`) — no code, paths, repo names,
  rule ids, or session ids, pinned by test. **Default off**; only the
  org's digest-pinned central policy (`[extends]`) can enable it — a
  repo-level `enabled = true` is ignored and surfaced. `fettle telemetry
  status|show|send`: status explains provenance, show prints the exact
  payload, send is fire-and-forget (5 s timeout, refused when disabled,
  failure never blocks anything).
- **Stage 11 — WP-147 supply-chain posture**: releases now ship with
  Sigstore-signed SLSA provenance (GitHub native attestation on every
  artifact — verify with `gh attestation verify`) and a CycloneDX SBOM
  generated from the exact wheel that publishes, attached to the GitHub
  release. Consumer side: `fettle doctor --verify-hashes` checks each
  pinned tool's installed files against its wheel RECORD hashes —
  tampering is a required failure, version drift a warning, and tools
  not installed as Python distributions are reported as skipped, never
  silently omitted. `PINNED_TOOLS` moved to its canonical home in
  `fettle/supply_chain.py` (init_cmd re-exports).
- **Stage 10 — WP-146 compliance evidence**: every bundled rule and ruff
  security code now carries CWE / OWASP ASVS / SOC 2 tags
  (`metadata.compliance` in the rule packs, canonical mapping in
  `fettle/compliance.py`, pinned in sync by test). New
  `fettle report --compliance [--json]` joins the mapping with the audit
  trail: per control, which rules enforce it and how often they
  fired/blocked in the window — evidence of enforcement, not a
  certification. Unmapped fired rules are surfaced, never dropped.

## v1.3.0 — Evidence Loop

- **Stage 8 — Remote CI verification gate**: `[gates.ci]` + `fettle ci
  status|wait` — born from a real incident: remote CI was red for eight
  consecutive runs while local pre-push stayed green (subprocess CLI
  tests needed an editable install the CI checkout lacked). The gate
  closes the loop: a PostToolUse hook records every `git push` in the
  session; the Stop gate (100 ms budget) then requires a fresh stamp
  proving the pushed commit's remote verdict is green — missing, stale,
  wrong-commit, or red all surface as unverified, with the failing run
  named and a local reproduction command from the failure-ingest
  pipeline (`ci_ingest`/`ci_diagnose` gain their first real caller).
  `fettle ci wait` polls GitHub Actions (gh CLI, REST fallback) and
  writes the stamp. OFF by default, advisory first; Fettle's own repo
  runs it in enforce mode.
- **Stage 7 — Functional-test verification + consistency pass (WP2, WP9)**:
  `[gates.verify]` + `fettle verify` — the CLI runs the discovered test
  suite (honors `[profile].test_command`; `scope = "impacted"` maps edited
  files to tests by name for pytest, falling back to the full suite) and
  writes a verification stamp; the Stop gate (100 ms budget) checks stamp
  freshness against tracked edits — stale, missing, or red means
  unverified. Timeouts and launch failures surface in the stamp, never
  silently. OFF by default, advisory first (`mode = "enforce"` to block).
  Config consistency (WP9): vestigial `gates.subagent.mode` removed
  (unknown keys warn, not error); `[gates.complexity]` gains
  `mode = "advisory"|"enforce"` (legacy `enforce = true` still honored,
  with a deprecation warning); `[gates.docs]` `"soft"` is now a deprecated
  alias for `"enforce"` (one-release tolerance, validation warns).
  Repo hygiene: 14 executed/superseded planning docs moved to
  `docs/archive/` with frozen-status banners; work notes unified under
  `docs/engagement/worknotes/`; consolidated forward roadmap in
  `docs/ROADMAP.md`.
- **Stage 6 — Semantic layer (Pillar 2, thin slice)**: `fettle links` —
  one deterministic link graph fused on demand from artifacts already in
  git: specs (requirements/scenarios), trace-marked tests, work items,
  UAT verdicts, operator attestations. No persisted index — the
  repository is the database. `fettle links <id>` shows everything
  attached to any known ID (unknown → exit 2 with closest matches);
  `fettle links --orphans` reports broken evidence chains with concrete
  fixes. Graphify consume-optional (D3 closed): when
  `graphify-out/graph.json` exists, spec scopes gain `scopes` edges to
  the code files graphify extracted; absent or malformed → identical
  behavior minus enrichment, never an error.
- **Stage 5 — Agentic UAT (WP3)**: `fettle uat` — acceptance testing by
  an autonomous agent acting as a first-time user, independent of the
  repo's own test suite. `uat doctor` detects surfaces (cli/api/web/
  library, evidence-carrying, overridable via `[uat].surfaces`) and
  probes capability; every gap reports what's not possible, why, the
  exact fix, and numbered manual steps. `uat run --surface S --yes`
  (explicit consent required) provisions an isolated `uat-<timestamp>`
  worktree with a Stage-4 claim, builds a persona prompt from active
  specs' GWT scenarios, runs the agent, scrubs suspected secrets from
  the transcript, and reconciles into per-scenario verdicts: CONFIRMED /
  CONTRADICTED / BLOCKED / UNOBSERVED (silence is a gap, not a pass) /
  INDETERMINATE (claimed match without independent evidence — auto-answer
  detection). Evidence artifact `uat-report.json`; `uat report`
  re-reconciles past sessions. When automation can't run: `uat manual`
  prints a numbered Set up/Do/Check walkthrough per scenario and `uat
  attest` records operator observations as a labeled peer of agent
  evidence (source: operator). Web surface via optional
  `pip install 'finefettle[uat]'` (playwright) — core stays stdlib-only.
- **Stage 4 — Agent infrastructure (WP7 + WP5 + runners)**: `fettle
  worktree create|list|remove` — one git worktree per work item under
  `[worktrees].root` (branch `fettle/<item-id>`; removal refuses when
  dirty; branches kept). Work items — markdown files with a
  `fettle-work-item` frontmatter key — plus `fettle work
  list|claim|release`; claims live in the shared git common dir so every
  worktree sees them, and stale claims (worktree gone) are takeable. New
  `[gates.claims]` (off, advisory|enforce): edits in a fettle-managed
  worktree with no claimed item get an advisory naming the fix. New
  `fettle.runners` package: outbound AgentRunner protocol (claude adapter
  first; evals consume it; failures land in `RunnerResult.error`, never
  silently). `.git`-as-file (linked worktree) handling fixed in trace
  repo identity and doctor hook checks.
- **Stage 3 — Living specs (Pillar 1 seed)**: markdown spec format with
  frontmatter (`fettle-spec` key; id/status/scope), numbered requirements,
  and Given/When/Then scenarios that trace to requirements. New `fettle
  spec lint` (format errors with concrete fixes), `fettle spec list`, and
  `fettle spec coverage` (evidence artifact: which scenarios have a
  trace-marked test via `# traces: <spec-id>/S<n>`). New `[gates.bdd]`
  (off by default, advisory|enforce): editing an implementation file
  inside an active spec's scope surfaces scenarios that have no traced
  test — deterministic, never runs tests.
- **Stage 2 (WP4) — Config dependency model**: no invalid config states.
  Validation now enforces per-gate mode vocabularies (a mode a gate's code
  doesn't honor — e.g. `tdd.mode = "enforce"`, which silently acted as
  advisory — is an error), numeric ranges (e.g. `coverage.threshold` 0–100),
  and cross-field dependencies (`extends.url` requires a valid sha256 pin;
  enabling `architecture_boundaries` without rules, `ui_colors` without a
  palette, or `lean_review.tier2` with a blank model warns that the feature
  is inert). The published JSON schema carries the per-gate enums and
  bounds; `fettle doctor` validates the project's `.fettle.toml`.
- **Stage 0 — Failure visibility**: no gate, scanner, or telemetry path
  fails silently anymore. Dispatcher fail-open events (input/config/registry
  errors, check crashes, budget exhaustion) are written to the audit trace;
  a check failing ≥3× in 24h raises an in-session advisory. `fettle doctor`
  and `fettle report` surface fail-open dispatch events and audit-trace
  writability. `fettle security-review` exits 2 with an INCOMPLETE REVIEW
  section when ruff/semgrep fail; `pr-review` marks failed scans UNAVAILABLE;
  `threat-model` flags failed probes instead of reporting "None detected".
  Audit-trace and health-telemetry write failures warn once on stderr.
  The MCP trust gate now fails closed on a corrupt/unreadable allowlist.
- **WP-145 — Audit & reporting**: trace entries carry a versioned audit
  schema (v2: adds `schema` + `repo` fields; v1 entries remain readable).
  New `fettle report [--org]` CLI — `--org` rolls decisions up per repo
  (decisions, violations, blocks, tool errors, top codes) for platform-team
  visibility. `fettle check --junit FILE` emits JUnit XML for enterprise CI
  dashboards (GitLab/Jenkins/Azure DevOps), joining the existing SARIF output.
- **WP-144 — Central policy distribution**: `[extends]` in .fettle.toml
  layers a digest-pinned org policy under repo config (defaults → org →
  repo → env). Content-addressed cache means a synced policy never goes
  stale; sha256 verified on fetch AND on every cache read (tampered cache
  files are discarded). Hooks resolve cache-only — never any network in
  the hook path. New `fettle policy sync|status`; doctor warns on
  configured-but-unsynced policies. Offline-safe by design.

## v1.2.0 — Independence

The engine decouples from any single agent: real package namespace,
agent abstraction with conformance contracts, one-command setup,
validated config schema, and CI parity across GitHub/GitLab/pre-commit.

- **WP-142 — Config schema v1**: `fettle config --validate` checks
  .fettle.toml against the built-in defaults — unknown keys warn (typo'd
  settings silently doing nothing is the classic config failure), type
  mismatches error, mode values are vocabulary-checked. A JSON Schema is
  published at docs/fettle.schema.json, generated from `config.DEFAULTS`;
  an anti-drift test fails when DEFAULTS change without regeneration.
- **WP-143 — CI parity templates**: GitLab CI template
  (templates/gitlab-ci.yml) joins the GitHub Action and pre-commit hooks —
  one .fettle.toml, identical findings at every chokepoint. Consumer
  pre-commit template re-pinned from v0.4.2 to v1.0.2.
- **WP-141 — `fettle init`**: one idempotent command replaces the symlink
  ritual — repo scaffolding (.fettle.toml, .fettle-ignore), Claude Code
  plugin symlink, OpenCode plugin registration, commit-time guard setup
  (.pre-commit-config.yaml + `pre-commit install`), and `--install-tools`
  for pinned ruff/semgrep/pre-commit via uv (explicit user action — hooks
  never install anything, per audit D6). `fettle doctor` now warns when a
  repo declares pre-commit hooks that aren't wired — closing the gap behind
  the 2026-07-24 CI scrub failure.
- **WP-140 — Agent abstraction layer**: new `fettle.agents` package — native
  agent payloads (Claude Code hook JSON, OpenCode plugin events) normalize
  into the dispatcher's event model through per-agent translators. Payload
  parsing lives only in translators; the dispatcher consumes normalized
  events exclusively. Conformance fixture suite asserts both agents'
  payloads normalize identically — payload drift breaks tests, not users.
  The dispatcher now accepts OpenCode's native event shapes directly (the
  TypeScript shim's pre-shaping keeps working during the deprecation window).
- **Lean sniffer determinism**: `FETTLE_LEAN_MAX_RUNTIME_MS` env override —
  the 200 ms production budget could expire before any sniffer ran on a
  loaded machine, making hook behavior (and its tests) nondeterministic.
  Tests now run with a deterministic budget.
- **WP-139 — Package restructure**: `scripts/` renamed to `fettle/` — a real
  package namespace with absolute `fettle.*` imports throughout (~470 import
  sites rewritten). Fettle no longer pollutes `sys.path` with collision-prone
  top-level names (`config`, `cache`, `profile`…). Public API defined in
  `fettle/__init__.py` (`load_config`, `scan_project`, `find_repo_root`,
  `__version__`), lazily loaded. A `scripts` → `fettle` symlink keeps existing
  hook configs and muscle memory working for one release (deprecation window).
  Internal subpackage reorganization (core/gates/surfaces) deferred.

## v1.0.2 — finefettle on PyPI

- **Package renamed to `finefettle` on PyPI** (“in fine fettle”) — the
  `fettle` name belongs to an unrelated project. Console script and import
  name remain `fettle`.
- **Trusted Publishing release workflow**: pushing a `v*` tag builds,
  tests, smoke-tests the wheel, and publishes to PyPI via GitHub OIDC —
  no long-lived tokens. Tag must match pyproject version (enforced).
- **Commit-time guards**: repo now runs scrub-audit + fettle-check +
  rules-validate as pre-commit hooks (`pre-commit install`); the CI
  scrub-audit failure of 2026-07-24 (leaked local path in a plan doc)
  is caught before a commit exists.

## v1.0.1 — Trustworthy Core (Phase 0 hotfix arc)

Correctness fixes from the 2026-07 full-repo audit (D1–D4). See
[docs/fettle-enterprise-product-plan.md](docs/fettle-enterprise-product-plan.md)
for the full enterprise arc (WP-133..WP-153).

### Fixed
- **CLI exit-code contract (D1)**: `fettle check` now exits `0` (clean),
  `1` (error-severity findings), `2` (usage/environment error) — identically
  in text and `--json` modes. Previously `--json` always exited 0, silently
  passing CI gates.
- **`fettle check` flags wired (D2)**: `--changed` scans only git-changed
  Python files (via changeset detection), `--fix` applies safe ruff autofixes
  before scanning, `--baseline` reports only findings absent from
  `.fettle-baseline.json` (accepts both wrapper-dict and legacy list formats).
  `--all` and `--changed` together is now a usage error. All four flags were
  previously accepted but ignored.
- **MCP trust gate allowlist path (D3)**: the default
  `~/.config/fettle/mcp-allowlist.json` path is now `expanduser`-resolved —
  the literal `~` was never expanded, so the default allowlist never loaded.
  Protected-path checks also resolve paths, blocking writes to the allowlist
  via its absolute path, not just the literal `~` form.
- **LR012 duplicate-helper sniffer (D4)**: replaced per-function `git grep`
  calls with a 40 ms timeout by one batched grep with a 0.5 s timeout —
  detection was nondeterministic under load (and its test flaky).
- **Hook launcher no longer auto-installs tools (D6)**: `run.sh` ran an
  unpinned `uv tool install ruff/semgrep` inside the hook path on every
  invocation where a tool was missing — a supply-chain and latency risk.
  Missing tools are now reported by `fettle doctor` and skipped with a
  warning by the individual checks.
- **Destructive-guard allowlist matching (D7)**: `allow_commands` entries
  now match a whole command segment exactly (whitespace-normalized).
  Substring matching let one allowed entry forgive an entire chained
  command (`rm -rf node_modules; rm -rf ~`).
- **Hook timeouts corrected to seconds (D8)**: `hooks.json` declared
  10000/15000/60000 — Claude Code interprets hook timeouts in seconds, so a
  hung hook could block a session for hours. Now 10/15/60 s (5 s SubagentStart).

### Added
- `fettle --version` — reads pyproject.toml in clone mode, package metadata
  when pip-installed.
- Release-gate test asserting pyproject, `__version__`, CHANGELOG, and README
  versions all agree.
- Ruff self-lint config in pyproject.toml and a `.fettle-ignore` excluding
  `tests/fixtures` (intentional-violation corpora) from self-scans (D9);
  repo is now self-check clean.

### Internal
- `quality_scan.scan_project()` accepts a `files=` parameter for targeted
  scans; `run_ruff`/`run_semgrep` accept target lists.
- 12 new regression tests pin the exit-code contract and allowlist resolution.
- Version metadata aligned (pyproject said 0.7.0 while docs said v1.0.0).

## v1.0.0 — Enterprise Integration + SWEBOK Coverage

### Enterprise Features (v1.0 plan)
- **WP-L — Extended secret scanner**: Azure Storage, Azure AD, GCP Service Account,
  GCP API Key, Bearer Token patterns. Config: `boundary.extra_secret_patterns`.
- **WP-N — Provenance policy gate**: 4 modes (none/manifest/marker/commit) for
  AI-generated code disclosure. PostToolUse(Write), new files only.
- **WP-O — Artifact verification gate**: PreToolUse(Bash) blocks publish without
  signed/scanned evidence. Evidence bound to exact artifact identity + exit code.
- **WP-P — Security review command**: `/fettle:security-review` orchestrating ruff
  S-rules + semgrep p/owasp-top-ten with CWE references.
- **WP-Q — Threat model command**: `/fettle:threat-model` STRIDE template with
  auto-detected entry points, data stores, and auth mechanisms.
- **WP-R — PR review orchestration**: `/fettle:pr-review` aggregates quality scan +
  coverage + complexity + breaking-change detection.
- **WP-S — SonarQube adapter**: IntegrationAdapter protocol, quality gate + issues API.
- **WP-T — Black Duck/Polaris adapter**: CLI invocation, SARIF parsing, subprocess security.
- **WP-U — Pact adapter**: Broker API for contract verification status.
- **WP-V — Architecture boundary rules**: import direction enforcement from .fettle.toml rules.
- **WP-W — ADR + Architecture discipline skills** in Disciplines plugin.

### SWEBOK v4 Gap Coverage
- **WP-X1 — Technical debt dashboard**: TODO/suppression count, complexity trend, A-E rating.
- **WP-X2 — Deployment safety gate**: PreToolUse(Bash) verifies tests ran, health endpoint
  exists, no debug flags before deploy commands.
- **WP-X3 — Release gate**: CHANGELOG/semver enforcement on `git tag`.
- **WP-X4 — Mutation testing command**: wraps mutmut, changed files only, configurable threshold.
- **WP-X5 — Requirements traceability**: links spec files to tests via naming + markers.

### Infrastructure
- **IntegrationAdapter protocol**: shared 5-state result model (pass/fail/unavailable/
  misconfigured/not_enabled) with configurable fail-open/fail-closed.
- **Codebase rationalization**: deleted 11 dead modules + 6 orphaned tests (-1,585 lines).
- **JSON schema contract tests**: 16 tests validating dispatcher output against Claude Code schema.
- **TypeScript adapter tests**: 21 dedicated integration tests.
- **Worklog gate**: daily worklog enforcement at Stop hook.
- **CI fix**: resolved semgrep false positive on f-strings.

## v0.9.0 — Engineering Discipline Enforcement

- **WP-K — Branch coverage gate**: extends coverage_gate.py to check
  missing_branches from coverage.json. Only flags branches originating from
  edited lines. Config: `gates.coverage.minimum_branch_percent`.
- **WP-H — Function complexity limits**: new complexity_check.py with
  cyclomatic and cognitive complexity per modified function (stdlib ast only).
  Config: `gates.complexity.max_cyclomatic`, `max_cognitive`.
- **WP-J — Enhanced plan thresholds**: risk paths (auth/security/migration
  globs), module count, and line estimation independently trigger plan gate.
  Config: `gates.plan.risk_paths`, `module_threshold`, `line_threshold`.
- **WP-I — TDD phase enforcement**: detects test-before-implementation ordering.
  Advisory mode only in v0.9. Config: `gates.tdd`.
- **VS Code extension**: new `integrations/vscode/` launches LSP server for
  inline diagnostics in VS Code.

## v0.8.0 — Discipline Integration

- **WP-A — Surface lean findings**: lean_sniffers returns advisory (not just
  silent JSONL) when `gates.lean_review.mode = "advisory"`.
- **WP-B — Normalized advisory contract**: Advisory dataclass, persisted
  AdvisoryDeduplicator, format_advisories renderer, aggregator cross-check cap.
  Config: `gates.advisory`.
- **WP-B2 — Migrate lean_sniffers onto AdvisoryDeduplicator**: single dedup
  mechanism across all advisory output.
- **WP-C — Discipline link pilot**: loop_detect injects 2-sentence debugging
  reminder from discipline-debugging (or fallback). Config: `gates.discipline_link`.
- **WP-D — Cooperative budget enforcement**: per-check deadline in HookContext,
  overrun logging, lean_sniffers honors dispatcher deadline.
- **WP-E — Bash structured audit**: privacy-first event logging (hash only by
  default, opt-in redacted capture). Config: `gates.bash_audit`.
- **WP-F — Diff coverage gate**: reads pre-existing coverage.json, staleness
  guard, advisory/enforce per mode. Config: `gates.coverage`.
- **WP-G — Shared discipline_link helper**: trigger-to-skill mappings ready for
  expansion after pilot metric passes.
- **hookEventName fix**: dispatcher now includes hookEventName in all output
  (fixes Claude Code Stop hook validation error).
- **bench/doctor PATH fix**: tools at ~/.local/bin found via _which() fallback.

## v0.7.0

- **WP-122 (partial) — Git-installable Python package**: console entry points,
  bundled rule resources, and `python -m fettle`. PyPI publication is deferred
  because that project name belongs to an unrelated package.
- **WP-123 — GitHub Action and reusable workflow**: advisory/enforce modes,
  SARIF output, and pull-request annotations.
- **WP-125 — LSP diagnostics**: `fettle lsp` publishes ruff and semgrep findings
  to editors over stdio JSON-RPC.
- **WP-126 (partial) — policy layering**: defaults, organization, team,
  repository, and directory-scoped configuration with `fettle config --explain`.
  Cryptographic bundle signing remains open.
- **OpenCode integration**: translates OpenCode tool/session lifecycle events
  into the existing dispatcher protocol while preserving Claude Code support.

## v0.6.0 arc

- **WP-124 (pulled forward) — pre-commit integration**: published
  `.pre-commit-hooks.yaml` with `fettle-check` (changed-files quality scan)
  and `fettle-rules-validate` (project rule packs must pass `--validate`);
  consumer snippet in `templates/pre-commit-config.yaml`. Same policy at the
  commit chokepoint regardless of editor/agent.
- **WP-133 (scaffold) — behavioral eval lab** (`evals/`,
  `scripts/evals_runner.py`): quorum-inspired, slimmed. Scenario dirs with
  prompt/setup_files/checks; three-valued verdicts; static side CI-safe
  (`evals_runner.py validate` + fake-runner unit tests), live side
  (`claude -p`) trusted-operator only. Two seed scenarios: hook-catches-debug-statement,
  plan-gate-nudges-multifile.
- **WP-116 — Rule-pack integrity gates** (`tests/test_rule_integrity.py`):
  every rule in every pack must have a `fire/` and a `silent/` fixture under
  `tests/fixtures/rulepacks/<pack>/<rule-id>/` — fixture-less rules fail the
  suite. Mutation check proves `--validate` catches the duplicate-key defect
  class that shipped in v0.4.0; generated project rules must validate too.
  46 fixtures added (23 rules × fire/silent). **Immediately caught a dead
  rule**: `string-built-sql-ts` never fired — semgrep's ellipsis does not
  match inside template literals; rewritten as `pattern-regex` (also covers
  SQL templates assigned to variables).
- **WP-117 — Tool-version canary CI leg**: ubuntu job against newest semgrep
  (`continue-on-error`, non-blocking) to surface upstream behavior changes
  early; pinned legs stay authoritative.
- **WP-119 — Ratchet workflow** (`scripts/ratchet.py`): evidence-based
  rule promotion/demotion. `fettle ratchet status` shows per-rule mode,
  fire count, FP rate, and promotion eligibility. `promote` only succeeds
  when a rule has ≥5 fires and ≤20% FP rate (aggregated from trace JSONL
  and false-positive stamps). `demote` requires a reason. `sync`
  re-aggregates without changing modes. Makes advisory-first a measured
  product feature instead of a convention. (21 tests)
- **WP-120 — Suppressions with expiry and owner**
  (`scripts/suppressions_v3.py`): structured suppression model with
  `# fettle:ignore[rule-id] reason=... owner=@handle until=YYYY-MM-DD`
  inline comments and `.fettle/suppressions.json` file-level entries.
  Expired suppressions become findings themselves; ownerless suppressions
  flagged in reports. CLI: `fettle suppressions {list|add|remove|report|expired}`.
  (28 tests)
- **WP-121 — Loaded-rules health telemetry**
  (`scripts/health_telemetry.py`): every hook run can log rules
  loaded/skipped per config source into trace (`record_loaded_rules`);
  `check_health` detects zero-rule packs and drops; `doctor_check()`
  discovers expected packs from `rules/*.yml` and asserts health.
  Standalone CLI for debugging. (16 tests)

## v0.4.2 — Go post-edit check (2026-07-16)

- **Go route** (`scripts/post_edit_go.py`, registered in the dispatcher for
  `.go` edits): semgrep runs the new built-in `rules/go-antipatterns.yml`
  (empty-error-swallow, debug-print, sql-string-concat, http-client-no-timeout)
  plus project rules from `.fettle/rules/`; golangci-lint runs when the anchor
  root has a `go.mod`. Enforce mode blocks on ERROR findings.
  End-to-end test proves a project-local Go rule (e.g. DVA3's
  `no-direct-kafka-produce`) fires through the hook (`tests/test_post_edit_go.py`).

## v0.4.1 — Rule config fixes + anchored semgrep scans (2026-07-16)

- **Fix: `ts-antipatterns.yml` was invalid** — duplicate `pattern-not-inside` keys
  (`unawaited-promise`) and `patterns` + sibling `pattern-not-inside`
  (`fetch-without-timeout`) made semgrep reject the whole config, silently
  disabling **all** TS/JS checks. Also fixed AND-vs-OR misuse: `empty-catch-block`,
  `string-built-sql-ts`, `regex-llm-output-ts` used `patterns:` (AND) where
  `pattern-either:` (OR) was intended and could never fire.
- **Fix: TS rule precision** — the resurrected rules measured ~9,000 findings on a
  23-file UI5 app. `unawaited-promise` now targets known promise-returning APIs
  (fetch/axios) instead of every statement-level call (semgrep OSS has no type
  inference), and ignores `.then()`/`.catch()` chains. `regex-llm-output-ts` is
  path-scoped to `agents/`, `pipeline/`, `llm/` like its Python counterpart.
  Same app now: 2 findings, both true positives (`tests/test_ts_rules.py`).
- **Project-local rules** (`scripts/project_rules.py`): projects extend the
  built-in rule packs via `.fettle.toml` — `[rules] extra_dirs` adds project
  semgrep rule files (default `.fettle/rules/`), `promise_apis` extends
  `unawaited-promise` with project-specific promise-returning APIs (validated
  identifiers only; rule generated and cached under `.fettle/generated/`).
  Both post-edit hooks pass the extra configs to semgrep.
- **Noise audit** of `llm-antipatterns.yml` on three real codebases: rules
  confirmed precise when scans are correctly anchored (mis-anchored scans
  defeated `paths.exclude` — same class of bug as the hook anchoring fix).
- **Fix: path-filter anchoring** (`scripts/semgrep_util.py`): semgrep ≥ 1.136
  resolves `paths.include`/`exclude` against the git project root; files outside a
  git repo silently escaped path-scoped rules and exclusions. Both hooks
  (`post_edit.py`, `post_edit_ts.py`) now scan via `anchored_semgrep_args()` —
  git root, else session cwd, else file dir — with `--project-root .`.
- **Tests** (`tests/test_semgrep_anchor.py`): every file under `rules/` must pass
  `semgrep --validate` (catches dead-config regressions), plus anchoring contract
  tests. Test harnesses in `test_rules.py`/`test_debug_detect.py` pin
  `--project-root` for non-git tmpdirs.

## v0.4.0 — Intelligence + Extensibility (2026-07-07)

- **TypeScript/JS rules** (`rules/ts-antipatterns.yml`): 5 semgrep rules for TS/JS
- **Cross-review** (`review.py`): provider-agnostic LLM code review
- **SARIF output** (`sarif.py`): GitHub code scanning format
- **Result caching** (`cache.py`): skip re-scanning unchanged files
- **Autofix** (`autofix.py`): safe ruff fixes with trace logging
- **Checker protocol** (`checker.py`): formal ABC for tool plugins (Ruff, Semgrep built-in)
- **Policy engine** (`policy.py`): central decision point for hook behavior
- **Event model** (`event.py`): typed FettleEvent replaces raw JSON
- **Install UX** (`install.py`): `fettle install config|hooks|ignore|all|status`
- **TS hook** (`post_edit_ts.py`): wired in hooks.json for TS/JS files

## v0.3.0 — Foundation for v0.3/v0.4 roadmap

### New modules
- **Result taxonomy** (`scripts/result.py`): PASS, VIOLATION, TOOL_ERROR, CONFIG_ERROR, SKIPPED. Finding dataclass with tool/severity/path/line/code/message/fixable.
- **Path resolver** (`scripts/paths.py`): centralized resolution, traversal protection, repo boundary checks, symlink safety.
- **CLI** (`scripts/cli.py`): `fettle check`, `fettle config --print-effective`, `fettle explain`, `fettle baseline`, `fettle doctor`.
- **Trace** (`scripts/trace.py`): persistent JSONL logging of all hook decisions.
- **Explain** (`scripts/explain.py`): human-readable explanation of last hook decision.
- **Baseline** (`scripts/baseline.py`): snapshot violations for incremental enforcement.
- **Learn** (`scripts/learn.py`): LLM-generated semgrep rules from incident descriptions.
- `pyproject.toml`: package metadata + console script `fettle`.
- 3 new slash commands: `/fettle:learn`, `/fettle:explain`, `/fettle:baseline`.
- `rules/learned/` directory for incident-derived rules.
- 33 new tests (test_result, test_paths, test_trace, test_baseline, test_learn, test_cli).

### External audit
- `docs/archive/audit-2026-07-07.md`: independent code audit with prioritized TODO.

## Unreleased

- Stop-hook import checks understand src-layout packages (`src/<pkg>/`)
  and skip dependencies declared in pyproject/requirements even when no
  .venv exists to probe (ephemeral `uv run --with` envs) — a second
  round of import false positives on real-world project layouts.
- Stop-hook cross-file checks no longer flood real projects with false
  positives:
  `stop_quality_gate.py` discovers the project root by walking up to
  `pyproject.toml`/`setup.py`/`.git` instead of using the edited file's own
  directory; `check_imports` recognizes packages installed in the project's
  `.venv` (the hook's interpreter can't import them); `check_contracts`
  accepts `from pkg import submodule` without an `__init__` re-export.

- Removed `effectiveness_report.py`: it depended on a private logging tool
  no public install has; the tool's name joined the scrub-audit pattern.
  The effectiveness loop returns in v0.4.0 built on Fettle's own trace files.
- Rust/shell gate tests now run on ubuntu CI (cargo + shellcheck installed);
  cargo is resolved from PATH instead of a hardcoded Linux toolchain path.
- README documents the seven plugin slash commands.

## v0.2.1 (2026-07-04)

Fixes surfaced by dogfooding the project scan on a real multi-package repo:

- `quality_scan.py` findings and baselines now use root-relative paths, so a
  committed baseline matches on CI and other machines. Legacy absolute-path
  baselines are normalized on load and keep working.
- `.fettle-ignore` patterns now actually filter project-scan findings (they
  were only applied to the file count).
- File discovery prunes hidden dirs, `node_modules`, `venv`, `build`, `dist`
  (a `.venv` inflated the scanned-file count 40x).
- The project scan reads `[severity]` from `.fettle.toml` instead of
  hardcoded rule sets — CONFIG.md's "single source" claim is now true.
- New test suite for `quality_scan.py` (10 tests: baselines, portability,
  ignores, severity config, exit codes).

## v0.2.0 (2026-07-04)

First public release. Fettle began as a private quality-enforcement plugin;
this release makes it portable, configurable, and installable.

### Added
- `.fettle.toml` per-repo configuration: per-gate enables, severity single
  source, paths, review provider (docs/CONFIG.md).
- Session-scoped state under `$XDG_STATE_HOME/fettle/<session_id>/` — no
  cross-session interference.
- Portable interpreter launcher (`scripts/run.sh`) and `scripts/doctor.py`
  environment self-check.
- Authoritative plugin hook wiring (`hooks/hooks.json`) across PreToolUse /
  PostToolUse / Stop — enforcement installs with the plugin.
- Rule metadata (`origin`, `citation`) on every semgrep rule.
- CI (ubuntu + macos), permanent private-string scrub audit.

### Changed
- Opinionated process gates (plan, UX-spec, UI colors, doc-before-push,
  tests, MCP trust) are now **opt-in** and default off; the core lint gate
  defaults to advisory. Every block message names the config key that
  disables it.
- The legacy `QUALITY_GATE_MODE` env var is gone; mode lives in
  `.fettle.toml` (`[gates.lint].mode`, `[gates.docs].mode`) with
  `FETTLE_GATE_MODE` as the emergency override (`off` disables all gates).
- Fail-visible policy: missing or failing analysis tools emit warnings and
  `gate_error` trace events instead of silently passing.
- Python floor: 3.11 (stdlib tomllib).

### Fixed
- Baseline save crash on bare filenames.
- Test suite: 163 passed / 0 failed (was 53 failures against
  pre-consolidation script paths).
