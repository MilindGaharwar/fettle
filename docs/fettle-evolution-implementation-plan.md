# Fettle Evolution Implementation Plan

Status: APPROVED — P0–P5 active

Scope: post-v1.7 evolution of Fettle from Python-first governance to a
trustworthy, polyglot policy and evidence layer. This plan consolidates the
strategic review, competitor analysis, current audit findings, agent-facing
ergonomics gaps, semantic-delta opportunities, shell-security boundaries, and
language/framework expansion recommendations.

The user-flow contract is
[polyglot-governance.ux-spec.md](polyglot-governance.ux-spec.md). Existing
v1.6/v1.7 audit commitments remain owned by
[15-v161-audit-remediation.md](engagement/15-v161-audit-remediation.md) and are
dependencies, not duplicated work packages.

## 1. Outcome

### User Story

As a developer or platform engineer using AI coding agents, I want one Fettle
policy to produce consistent, actionable evidence across Python,
JavaScript/TypeScript, .NET, Java, and mixed repositories, so that agents can
repair problems while context is fresh and CI remains an independent assurance
boundary.

### Product Position

Fettle remains the portable governance layer between agents and engineering
evidence:

```text
agent / orchestrator / editor
            |
            v
Fettle lifecycle policy and evidence contract
            |
            +-- repository-native analyzers
            +-- tests, build, coverage, and CI
            +-- optional MCP and LSP query surfaces
            +-- external execution sandbox
            |
            v
developer repair + portable audit evidence
```

Fettle does not become a general agent orchestrator, proprietary static
analyzer, IDE suite, hosted control plane, or operating-system sandbox.

## 2. Assumptions

1. v1.7 policy-resolution parity and workflow distribution are complete.
2. Python 3.11+ and the default zero-runtime-dependency posture remain.
3. Repository-native wrappers and commands take precedence over global tools.
4. Hooks remain the deterministic enforcement boundary; MCP is optional
   preflight and explanation.
5. CI remains an independent fail-closed boundary for full analysis.
6. New languages and framework rules start advisory and graduate only from
   measured evidence.
7. Existing Python, Go, Rust, and JS/TS behavior remains supported throughout
   migration; no flag-day dispatcher rewrite is acceptable.
8. Implementation remains additive until parity tests permit removal of an old
   path; unrelated worktree changes must not be overwritten or reverted.

## 3. Decisions And Tradeoffs

### 3.1 Adapter Architecture

| Approach | Benefit | Cost/risk | Decision |
|---|---|---|---|
| Add `post_edit_<lang>.py` per language | Small initial diff | Duplicates parsing, errors, routing, and output | Reject |
| Route all checks through the existing adapter protocol immediately | Clean end state | High regression blast radius | Reject as flag day |
| Introduce one adapter-backed dispatcher check, migrate languages incrementally | Shared contract with reversible slices | Temporary dual paths | Adopt |

### 3.2 Framework Support

| Approach | Benefit | Cost/risk | Decision |
|---|---|---|---|
| Dedicated adapter per framework | Easy branding | Tool duplication and combinatorial growth | Reject |
| Framework rule packs over language adapters | Composable and testable | Requires pack detection and metadata | Adopt |
| Depend only on existing ecosystem plugins | Lowest maintenance | Cannot express Fettle process/evidence rules | Use first, supplement narrowly |

### 3.3 MCP

| Approach | Benefit | Cost/risk | Decision |
|---|---|---|---|
| Replace hooks with MCP | Rich interaction | Agent can ignore calls; weak enforcement | Reject |
| Persistent Fettle daemon | Caching and low latency | Lifecycle, security, and packaging burden | Defer |
| Thin stdio MCP adapter over shared services | Useful preflight with small scope | Another output surface to parity-test | Adopt after finding parity |

### 3.4 Shell Containment

Regex and shell parsing remain defense-in-depth mediation. Fettle will improve
classification and integrate with external sandboxes, but will not claim that
hooks provide process or network containment. eBPF/ptrace belongs in a separate
privileged, platform-specific security product.

## 4. Current Baseline And Authoritative Scope

v1.7.0 is the shipped trust baseline. The activity IDs below are the execution
source of truth; release work packages later in this document provide design
detail. Estimates include tests and documentation for one experienced engineer
and are planning ranges, not commitments.

| ID | Activity | Release | Depends on | Estimate | State |
|---|---|---|---|---|---|
| P0 | Align roadmap, release numbering, and v1.7 baseline | v1.8 | v1.7.0 | 0.5 day | Active |
| P1 | Define canonical four-state result contract | v1.8 | P0 | 0.5–1 day | Active |
| P2 | Add actionable fields to the canonical finding | v1.8 | P1 | 0.5–1 day | Active |
| P3 | Carry findings and evidence through dispatcher transport without changing host wires | v1.8 | P1, P2 | 1–2 days | Active |
| P4 | Record repair, turn, recurrence, byte, and indeterminate eval metrics | v1.8 | P1 | 1–2 days | Active |
| P5 | Add Python and TypeScript repair/error behavioral scenarios | v1.8 | P2, P4 | 1–2 days | Active |
| P6 | Persist bounded, redacted structured evidence in trace | v1.8 | P2, P3 | 1–2 days | Complete |
| P7 | Render concise, detailed, and JSON findings in report/explain | v1.8 | P2, P6 | 1–2 days | Complete |
| P8 | Attach evidence IDs to verify, coverage, UAT, CI, and integrations | v1.8 | P6 | 2–4 days | Complete |
| P9 | Consolidate workspace models and nested routing | v1.9 | P3 | 4–7 days | Complete |
| P10 | Strengthen adapter protocol with explicit `CheckRun` state | v1.9 | P1, P9 | 3–5 days | Complete |
| P11 | Add adapter-backed dispatcher check and migrate TypeScript | v1.9 | P3, P10 | 3–5 days | Complete |
| P12 | Migrate Go, Python, and Rust after parity | v1.9 | P11 | 4–7 days | Complete |
| P13 | Centralize file and test classification | v1.9 | P9, P10 | 3–5 days | Complete |
| P14 | Verify all affected workspaces and bind evidence | v1.9 | P8, P9, P10 | 3–5 days | Complete |
| P15 | Complete repository-native JS/TS tooling | v1.10 | P10, P11 | 3–5 days | Complete |
| P16 | Discover Node workspaces and framework metadata | v1.10 | P9, P15 | 2–4 days | Planned |
| P17 | Establish web CLI/hook/LSP parity and eval corpus | v1.10 | P5, P15, P16 | 3–5 days | Planned |
| P18 | Add argv-only generic command integration | v1.10 | P1, P6, P10 | 2–4 days | Planned |
| P19 | Ingest bounded SARIF and JUnit evidence | v1.10 | P2, P18 | 3–5 days | Planned |
| P20 | Expand adversarial shell corpus and conservative classification | v1.10 | P1 | 3–5 days | Planned |
| P21 | Define optional external sandbox provider contract | v1.10 | P18, P20 | 2–4 days | Demand-gated |
| P22 | Add .NET workspace, adapter, and behavioral evals | v1.11 | P10, P14, P19 | 5–8 days | Planned |
| P23 | Add Java workspace, adapter, and behavioral evals | v1.11 | P10, P14, P19 | 5–8 days | Planned |
| P24 | Add advisory framework-pack infrastructure | v1.12 | P13, P17, P22, P23 | 3–5 days | Planned |
| P25 | Add React/Next.js pack | v1.12 | P17, P24 | 3–5 days | Evidence-gated |
| P26 | Add ASP.NET Core and Spring Boot packs | v1.12 | P22, P23, P24 | 5–8 days | Evidence-gated |
| P27 | Add HTML/HTMX pack; add Angular only on demonstrated demand | v1.12 | P17, P24 | 3–6 days | Demand-gated |
| P28 | Capture bounded pre-edit structural evidence | v1.13 | P6, P13 | 3–5 days | Evidence-gated |
| P29 | Add initial semantic-delta rules and native infra ingestion | v1.13 | P19, P28 | 5–10 days | Evidence-gated |
| P30 | Extract shared side-effect-controlled analysis service | v1.14 | P12, P17, P19 | 4–7 days | Planned |
| P31 | Add thin stdio MCP query surface | v1.14 | P30 | 3–5 days | Demand-gated |
| P32 | Graduate additional LSP languages after parity | v1.14 | P22, P23, P30 | 3–6 days | Evidence-gated |

The critical path to trustworthy polyglot verification is P0 → P1 → P3 → P9
→ P10 → P11 → P14. P4–P5 run alongside the result-contract work; P18–P21 may
run alongside the web proving ground after their dependencies close. Work
marked demand- or evidence-gated is not scheduled until its trigger is met.

## 5. Dependency Spine

```text
v1.7 correctness and policy parity
        |
        v
R1 evidence-rich finding contract + agent eval baseline
        |
        v
R2 canonical workspace and adapter execution substrate
        |
        +----------------------+-----------------------+
        v                      v                       v
R3 JS/TS proving ground   R4 generic ingestion   R5 shell hardening
        |
        +----------+-----------+
                   v
          R6 .NET and Java adapters
                   |
                   v
          R7 framework policy packs
                   |
                   v
          R8 semantic-delta checks
                   |
                   v
          R9 thin MCP + broader LSP
```

No downstream release starts until its predecessor's graduation trigger is
met. Parallel work is allowed only where the graph explicitly branches.

## 6. Release Plan

### R0: v1.7 Trust Foundation

Owner: existing audit plan, not this plan. Status: COMPLETE in v1.7.0.

Required completion evidence:

- Normalized enforcement parity across Claude, Codex, Gemini, and OpenCode.
- One canonical policy resolver used by runtime and inspection.
- Capsule and MCP-trust bypass findings closed with adversarial tests.
- Verification stamps bound to session, source state, and verified scope.
- VS Code process invocation no longer interpolates untrusted shell strings.
- Existing Fettle quality scan and CI matrix green.

Graduation trigger: the v1.7 re-audit criteria pass. Polyglot work must not
build additional execution surfaces on unresolved policy divergence.

### R1: v1.8 Evidence And Agent Ergonomics

Goal: make every Fettle verdict actionable and measurable before broadening
language reach.

#### WP-201: One Canonical Finding Envelope

Change:

- Extend `fettle/dispatcher_types.py` so dispatcher results carry structured
  findings and evidence references rather than only a message string.
- Treat `fettle/finding.py` as the canonical finding schema; version it for
  additive fields including `impact`, `action`, `evidence_id`, and
  `result_state` (`pass`, `violation`, `tool_error`, `unknown`).
- Preserve host-specific rendering in `fettle/dispatcher_aggregate.py`.
- Update trace serialization in `fettle/trace.py` to store bounded structured
  evidence without source content.
- Add concise, detailed, and JSON rendering in `fettle/report.py` and
  `fettle/explain.py`.

Acceptance:

- No check crash, missing binary, timeout, or malformed tool output can become
  a pass.
- Existing check implementations can migrate one at a time through a temporary
  compatibility constructor; remove it before R2 closes.
- Output schema tests cover every decision and result state.

Verification:

```bash
python -m pytest tests/test_finding.py tests/test_output_schema.py tests/test_dispatcher.py tests/test_explain.py -q
python3 fettle/cli.py check --changed
```

#### WP-202: Evidence Artifacts

Change:

- Add bounded command, exit, timing, scope, and tool-version evidence to
  minutes-world operations.
- Attach evidence identifiers to verify, coverage, UAT, CI, and integration
  stamps.
- Never write secrets, raw source, repository identifiers, or unredacted
  environment values to global telemetry.

Primary files:

- `fettle/verify_gate.py`
- `fettle/coverage_gate.py`
- `fettle/uat/`
- `fettle/ci_gate.py`
- `fettle/integration_base.py`
- `fettle/finding.py`

Verification: stamp contract tests plus redaction fixtures.

#### WP-203: Agent-Ergonomics Evaluation Suite

Change:

- Extend `evals/scenarios/` from two scenarios to a maintained corpus covering
  finding comprehension, repair, rerun, repeated-block recovery, missing-tool
  behavior, and concise versus detailed output.
- Record repair success, turns-to-repair, repeated violation, diagnostic bytes,
  and indeterminate runs.
- Add held-out scenarios before tuning messages.

Primary files:

- `evals/README.md`
- `evals/scenarios/`
- `fettle/evals_runner.py`
- `tests/test_evals_runner.py`

Graduation trigger:

- All existing gates emit the canonical result state.
- Baseline agent metrics are recorded for at least Python and TypeScript.
- Every non-pass path supplies a recovery action.

### R2: v1.9 Canonical Workspace And Adapter Substrate

Goal: remove duplicated language assumptions and make workspace routing the
single source of execution context.

#### WP-210: Consolidate Workspace Models

Current issue: `fettle/profile.py` and `fettle/workspace.py` define overlapping
workspace models and marker registries.

Change:

- Make `fettle/workspace.py` own one `Workspace` model containing path,
  language, frameworks, manager, wrapper, commands, source roots, test roots,
  dependency files, and lockfiles.
- Make `fettle/profile.py` return those workspaces and retain cache/provenance.
- Support nested workspaces, longest-prefix routing, root shared files, and
  deleted-file routing.
- Replace the current one-level fallback with bounded marker discovery that
  excludes generated/vendor directories.
- Add config overrides per workspace, not only `profile.workspaces[0]`.

Markers added:

- `.sln`, `.slnx`, `.csproj`, `global.json`
- `pom.xml`, `mvnw`, `build.gradle`, `build.gradle.kts`, `gradlew`
- Existing Python, Node, Go, and Rust markers

Primary files:

- `fettle/workspace.py`
- `fettle/profile.py`
- `fettle/config.py`
- `fettle/config_schema.py`
- `docs/fettle.schema.json`
- `tests/test_workspace.py`
- `tests/test_profile.py`

#### WP-211: Strengthen The Adapter Protocol

Change `fettle/adapters/__init__.py` to define:

```python
class LanguageAdapter(Protocol):
    language: str
    extensions: frozenset[str]
    def supports(self, workspace: Workspace) -> bool: ...
    def classify(self, path: str, workspace: Workspace) -> FileKind: ...
    def lint(self, workspace: Workspace, files: list[str]) -> CheckRun: ...
    def format_check(self, workspace: Workspace, files: list[str]) -> CheckRun: ...
    def typecheck(self, workspace: Workspace, files: list[str]) -> CheckRun: ...
    def test(self, workspace: Workspace, files: list[str], scope: str) -> CheckRun: ...
    def build(self, workspace: Workspace) -> CheckRun: ...
    def dependency_check(self, workspace: Workspace) -> CheckRun: ...
```

`CheckRun` contains findings plus result state, command evidence, scope, and
tool errors. It does not return an empty list for execution failure.

Primary files:

- `fettle/adapters/__init__.py`
- `fettle/adapters/python_adapter.py`
- `fettle/adapters/typescript_adapter.py`
- `fettle/adapters/go_adapter.py`
- `fettle/adapters/rust_adapter.py`
- `fettle/tool_runner.py`
- `tests/test_adapter.py`
- `tests/test_polyglot_adapters.py`

#### WP-212: Adapter-Backed Dispatcher Check

Change:

- Add `fettle/adapter_check.py` as the single PostToolUse entry point.
- Resolve target file to workspace, select its adapter, and run only fast
  configured checks within the hook deadline.
- Migrate JS/TS first, then Go, then Python and Rust after parity tests.
- Remove `post_edit_ts.py` and `post_edit_go.py` only after their parity suites
  pass; retain no permanent dual paths.

Primary files:

- `fettle/adapter_check.py`
- `fettle/dispatcher_registry.py`
- `fettle/post_edit_ts.py`
- `fettle/post_edit_go.py`
- `tests/test_dispatcher.py`
- `tests/test_post_edit_ts.py`
- `tests/test_post_edit_go.py`

#### WP-213: Central File And Test Classification

Change:

- Move implementation/test/generated/config classification behind adapter and
  workspace APIs.
- Replace hardcoded extension and command lists in `quality_gate.py`,
  `verify_gate.py`, `tdd_gate.py`, `paths.py`, `bench.py`,
  `lean_sniffers.py`, and `lean_debt.py`.
- Ensure unsupported languages remain neutral rather than silently exempting a
  supported workspace.

Verification:

- A matrix test supplies each language's implementation, test, generated,
  dependency, and configuration paths to every affected gate.
- Existing Python classifications remain unchanged.

#### WP-214: Multi-Workspace Verification

Change:

- `fettle verify` groups edited code by workspace.
- Run impacted tests where the adapter has a reliable mapping; otherwise run
  the affected workspace's full suite.
- Stamp every workspace, command, source-state digest, and scope.
- Stop gate rejects omitted affected workspaces.

Graduation trigger:

- Python, JS/TS, Go, and Rust parity suites pass through `adapter_check`.
- No production gate owns a private implementation-extension list.
- Mixed Python/Node fixture runs only affected workspace commands.
- Hook latency remains inside configured budgets at p95.

Status 2026-08-05: graduated. The adapter-backed dispatcher owns all four
language routes; TypeScript and Go Semgrep parity is covered through adapter
tests and the retired hook modules are removed. Classification has no private
production implementation-extension list, deleted files remain verification
relevant, reliable Python impacted tests run per affected workspace, and a
100-invocation adapter-routing p95 contract enforces the 150 ms hook budget.

### R3: v1.10 JavaScript/TypeScript And Web Baseline

Goal: use the highest-value, partially implemented stack to prove the complete
polyglot flow.

#### WP-220: Complete Native JS/TS Tooling

- Resolve local tools through package-manager execution (`pnpm exec`, `npm
  exec`, `yarn exec`, `bunx`) before global PATH.
- Prefer repository scripts when present.
- Support ESLint or Biome lint, Biome or Prettier format, `tsc --noEmit`,
  Vitest/Jest tests, and configured build scripts.
- Correct package-manager install/build semantics; do not use `yarn ci` or
  `pnpm ci` where unsupported.
- Parse stderr as well as stdout where native tools use it.

Primary files:

- `fettle/adapters/typescript_adapter.py`
- `fettle/tool_runner.py`
- `fettle/profile.py`
- `tests/test_typescript_adapter.py`

#### WP-221: Node Workspace Discovery

- Detect npm, pnpm, Yarn, and Bun workspaces.
- Detect TypeScript from dependencies or `tsconfig*.json`.
- Detect React, Next.js, Angular, Vue/Nuxt, Svelte/SvelteKit, and HTMX markers
  as metadata without enabling strict rules.
- Route lockfile changes to all workspaces sharing that lockfile.

#### WP-222: Web LSP Parity

- Refactor `fettle/lsp_server.py` to consume the adapter-backed check service.
- Publish JS/TS diagnostics only after CLI versus LSP parity tests pass.
- Keep unsupported language selectors out of the VS Code extension.

#### WP-223: Web Behavioral Evals

Add live and static scenarios for:

- Unhandled promise
- Unsafe SQL construction
- Debug artifact
- Missing loading/error state
- Missing native analyzer
- Mixed frontend/backend workspace routing

Graduation trigger: JS/TS hook, CLI, LSP, and verify findings agree on the
maintained fixture corpus.

### R4: v1.10 Generic External Evidence Ingestion

This release may run parallel to R3 after R2 closes.

#### WP-230: Generic Command Integration

Add a configured integration capable of executing argv arrays without a shell,
with timeout, cwd, environment allowlist, expected output format, and severity
mapping.

#### WP-231: SARIF And JUnit Ingestion

- Normalize SARIF findings into `CheckFinding`.
- Normalize JUnit suite/test failures into evidence artifacts.
- Preserve external rule identifiers and locations.
- Reject malformed or oversized input as tool error.

Primary files:

- `fettle/integration_base.py`
- `fettle/integrations.py`
- `fettle/finding.py`
- `tests/test_integrations.py`
- `tests/test_sarif.py`
- `tests/test_junit.py`

Outcome: Snyk, TruffleHog, Checkmarx, SonarQube, and similar tools primarily
need documented recipes, not bespoke permanent adapters.

### R5: v1.10 Shell Mediation Hardening

This release may run parallel to R3/R4 after R1 establishes structured errors.

#### WP-240: Adversarial Shell Corpus

Extend fixtures for nested shells, command substitution, encoded execution,
pipes to interpreters, environment wrappers, SSH commands, Bash file writes,
network exfiltration shapes, and infrastructure mutation.

#### WP-241: Conservative Classification

- Keep exact allow-list semantics.
- In enforce mode, block ambiguous high-risk commands that contain a protected
  operation but cannot be safely parsed.
- Make the reason and escape route explicit.
- Record classification confidence and rule identifier.

#### WP-242: External Sandbox Contract

Document and implement an optional execution-provider interface that can hand
an agent command to an external sandbox. Fettle supplies policy and receives
the verdict; it does not implement eBPF, ptrace, containers, or network
namespaces itself.

Graduation trigger: adversarial corpus results are published with known false
positive and false negative classes; documentation never calls the hook guard
a sandbox.

### R6: v1.11 .NET And Java

Goal: add the two highest-value enterprise backends on the common substrate.

#### WP-250: .NET Workspace And Adapter

Detection:

- `.sln`, `.slnx`, `.csproj`, `global.json`, `Directory.Build.props`,
  `Directory.Packages.props`, `packages.lock.json`
- Project references and test projects
- ASP.NET Core and common test frameworks as metadata

Native operations:

- Format: `dotnet format --verify-no-changes`
- Build/type analysis: `dotnet build --no-restore`
- Test: `dotnet test --no-build` where prior evidence permits, otherwise normal
  `dotnet test`
- Dependency audit: `dotnet list package --vulnerable --include-transitive`
- Coverage: configured Coverlet output
- Static analysis: repository-configured Roslyn analyzers; no forced vendor
  analyzer dependency

Test conventions:

- `*Tests.cs`, `*Test.cs`, test projects, xUnit/NUnit/MSTest markers
- Namespace/project-reference mapping before filename fallback

Primary files:

- `fettle/adapters/dotnet_adapter.py`
- `fettle/workspace.py`
- `fettle/adapters/__init__.py`
- `fettle/coverage_gate.py`
- `tests/test_dotnet_adapter.py`
- `tests/fixtures/dotnet/`

#### WP-251: Java Workspace And Adapter

Detection:

- Maven reactor through `pom.xml` and `mvnw`
- Gradle multi-project builds through `settings.gradle*`, `build.gradle*`, and
  `gradlew`
- Java/Kotlin source sets and test source sets
- Spring Boot metadata

Native operations:

- Prefer `./mvnw` or `./gradlew`; global Maven/Gradle is fallback only.
- Compile/build and test through repository lifecycle commands.
- Ingest Checkstyle, SpotBugs, PMD, Error Prone, JaCoCo, and dependency-check
  reports only when configured by the repository.
- Do not auto-modify `pom.xml` or Gradle files to install plugins.

Test conventions:

- `*Test.java`, `*Tests.java`, `*IT.java`, JUnit/TestNG source roots
- Maven/Gradle module mapping before filename fallback

Primary files:

- `fettle/adapters/java_adapter.py`
- `fettle/workspace.py`
- `fettle/adapters/__init__.py`
- `fettle/coverage_gate.py`
- `tests/test_java_adapter.py`
- `tests/fixtures/java/`

#### WP-252: Enterprise Stack Behavioral Evals

At least one live repair scenario and one missing-tool scenario per language,
plus a mixed React/.NET and React/Java workspace scenario.

Graduation trigger:

- Clean fixture, violation fixture, malformed-output fixture, timeout fixture,
  and native sample project pass for each adapter.
- No repository build file is modified by setup.
- Wrapper-first execution is demonstrated in tests.

### R7: v1.12 Framework Policy Packs

Framework packs contain high-confidence rules not already covered by native
ecosystem analyzers. Every rule requires fire and silent fixtures, source
metadata, suggested repair, and an advisory-only observation period.

#### WP-260: Framework Pack Infrastructure

- Add pack metadata: language, framework markers, required analyzer, rules,
  default mode, confidence, and compatibility range.
- Auto-detection recommends packs but does not silently enforce them.
- `fettle doctor` explains inactive packs and missing analyzers.
- `fettle rules list` filters by language and framework.

Primary files:

- `fettle/rule_loader.py`
- `fettle/rule_integrity.py`
- `fettle/profile.py`
- `fettle/doctor.py`
- `rules/packs/`
- `tests/test_rule_integrity.py`

#### WP-261: React And Next.js Pack

Initial candidates:

- Unsafe HTML injection
- Missing loading/error/empty handling where deterministically identifiable
- Unstable list keys
- Server/client boundary misuse
- Missing page metadata where framework convention is unambiguous
- Accessibility checks delegated to established ESLint plugins where possible

Do not recreate `eslint-plugin-react`, `eslint-plugin-react-hooks`,
`eslint-plugin-jsx-a11y`, or Next.js core-web-vitals rules.

#### WP-262: ASP.NET Core Pack

Initial candidates:

- Sensitive logging
- Insecure CORS configuration
- Sync-over-async patterns
- Missing cancellation-token propagation in configured application layers
- Unsafe model-binding and authorization patterns only where high confidence
- Entity Framework migration hazards

#### WP-263: Spring Boot Pack

Initial candidates:

- Insecure actuator exposure
- Sensitive logging and configuration secrets
- Unsafe controller binding or expression use
- Entity exposure and transaction-boundary rules only where deterministic
- Blocking calls in explicitly reactive modules

#### WP-264: HTML And HTMX Pack

Initial candidates:

- Missing CSRF integration for state-changing requests
- Unsafe dynamic `hx-*` URL construction
- Unescaped fragment insertion
- Duplicate IDs likely after fragment swaps
- Missing progressive fallback for critical actions
- Focus restoration and accessible status behavior

Template support starts with plain HTML, Razor, Thymeleaf, and JSX-supported
patterns. Jinja support reuses Python-side parsing where possible.

#### WP-265: Angular Pack

Angular follows React because it has a strong enterprise footprint and builds
on the TS adapter. Initial support should consume Angular ESLint and framework
build output before adding Fettle-native rules.

Deferred until demand: Vue/Nuxt, Svelte/SvelteKit, Kotlin-specific, mobile, and
desktop framework packs.

Graduation trigger for each pack:

- Zero findings on its maintained clean corpus.
- Acceptable field false-positive rate defined before observation begins.
- At least 80% agent repair success in behavioral evals.
- No rule becomes enforce-by-default.

### R8: v1.13 Stateful Semantic-Delta Checks

Goal: detect harmful removals and session-level drift that ordinary linting
cannot see, without whole-repository snapshots.

#### WP-270: Bounded Pre-Edit Evidence

- On PreToolUse for an edited file, cache a bounded content hash and targeted
  structural summary in session state.
- On PostToolUse, compare only that file and relevant git diff.
- Respect privacy, file-size, and event-budget limits.
- Do not create a persistent semantic database.

#### WP-271: Initial Delta Rules

Candidates, in evidence order:

1. Removed error-handling block.
2. Weakened or skipped test assertion.
3. Removed authorization or validation check.
4. Deleted public API without corresponding usage/spec update.
5. Excessive file creation in one session.
6. Large edit without subsequent verification.
7. Dependency manifest change without lockfile consistency.

Use language ASTs where standard and cheap; otherwise use native analyzer or
structured diff. Regex-only rules remain advisory and clearly identified.

#### WP-272: Infrastructure Semantic Integration

Do not build custom Terraform/Kubernetes parsers. Define optional adapters for
established plan/diff tools and ingest their structured output. Block execution
only on explicit policy and high-confidence native-tool evidence.

Graduation trigger: p95 hot-path cost remains within event budgets and each
rule has measured precision plus clean/violation/delta fixtures.

### R9: v1.14 Optional MCP And Expanded Editor Support

#### WP-280: Shared Analysis Service

Extract side-effect-controlled service functions used by CLI, dispatcher, LSP,
and MCP. A parity test feeds one workspace/file/config into every surface and
compares canonical findings.

#### WP-281: Thin MCP Server

Initial tools:

- `check_content(content, file_path)`
- `check_changed()`
- `explain_finding(finding_id)`
- `get_effective_policy(path)`
- `get_session_brief()`
- `list_rules(language, framework)`

Constraints:

- Stdio transport first.
- No daemon, remote endpoint, policy mutation, automatic suppression, or
  network requirement.
- MCP responses are guidance; hooks and CI retain enforcement.
- Content passed for preflight is not written to telemetry or trace.

#### WP-282: LSP Language Graduation

Add each language selector only after adapter CLI/LSP parity passes. Publish
tool errors as explicit diagnostics or status, not an empty diagnostic set.

Graduation trigger: the same fixture produces the same canonical findings over
CLI, hook, LSP, and MCP, modulo transport fields.

## 7. Cross-Cutting Test Strategy

### Unit Contract

Each adapter and pack requires:

- Detection tests
- Workspace routing tests
- Clean parser output
- Violating parser output
- Malformed output
- Missing tool
- Timeout
- Non-zero exit with empty output
- Path containing spaces
- Monorepo/root wrapper behavior

### Rule Integrity

Every Fettle-native rule requires:

- `tests/fixtures/rulepacks/<pack>/<rule>/fire/`
- `tests/fixtures/rulepacks/<pack>/<rule>/silent/`
- Metadata source and intended action
- Semgrep or native analyzer validation
- Stable rule identifier

### Integration Matrix

| Surface | Required evidence |
|---|---|
| Hook | Correct host response and budget behavior |
| CLI | Correct finding and exit contract |
| Verify | Correct workspace command and bound stamp |
| LSP | Canonical finding parity before activation |
| MCP | Canonical finding parity before release |
| CI | Independent full check remains green |

### Behavioral Evaluation

Each promoted language/framework has:

- One happy repair scenario
- One clean scenario
- One missing-tool/error recovery scenario
- One held-out scenario
- Recorded turns, diagnostic bytes, repair result, and indeterminate reason

### Manual Acceptance

For each release, use a fresh sample repository rather than only fixtures:

1. Initialize Fettle from checkout and clean wheel.
2. Review stack/workspace detection.
3. Trigger one native violation through a supported agent.
4. Follow the displayed repair and rerun instruction.
5. Run workspace verification.
6. Confirm Stop verdict and evidence report.
7. Repeat in a mixed-workspace repository.

File the report under `docs/uat/` for each language or framework graduation.

## 8. Security Requirements

- Execute configured tools as argv arrays with `shell=False`.
- Resolve target paths inside their declared workspace before invocation.
- Prefer repository wrappers but reject symlink/path traversal outside policy.
- Bound tool time, output size, and input file count.
- Redact secrets before persistence or rendering.
- Validate SARIF/JUnit/JSON payload size and shape.
- Do not send source to network services without explicit integration policy.
- Framework detection cannot enable telemetry or weaken central policy.
- MCP cannot mutate policy, approve packages, or suppress enforcing rules.
- Missing tools and parser failures remain visible and policy-controlled.

## 9. Performance Budgets

- PreToolUse total default: 250 ms.
- PostToolUse total default: 400 ms.
- Stop-hook inspection default: 600 ms.
- Native compile/test/build operations run only in minutes-world commands.
- Fast per-edit adapters target p95 below 150 ms individually; if a repository
  tool cannot meet that target, run a cheaper check in-hook and defer the full
  analyzer to `fettle verify` or CI.
- Profile/workspace discovery is cached by marker content/mtime and invalidated
  when any relevant marker changes.

## 10. Observability And Graduation

Measure locally and through existing privacy-preserving aggregate telemetry:

- Applicable checks
- Pass, violation, tool error, unknown
- Check duration and budget overrun
- Rule fire, override, suppression, and recurrence
- Repair success and turns in evals
- Workspace routing failures

Do not add repository names, paths, source snippets, session identifiers, or
raw commands to aggregate telemetry. OpenTelemetry export and a hosted control
plane remain deferred until a concrete enterprise consumer requires them.

## 11. Blast Radius

High-risk modules:

- `fettle/dispatcher_registry.py`: every in-session check selection.
- `fettle/dispatcher_types.py` and `fettle/dispatcher_aggregate.py`: every host
  response and exit decision.
- `fettle/config.py` and policy resolver: every gate.
- `fettle/profile.py` / `fettle/workspace.py`: command cwd and stack routing.
- `fettle/verify_gate.py`: Stop completion and trusted evidence.
- `fettle/adapters/`: minutes-world commands and new per-edit checks.
- `fettle/lsp_server.py`: editor diagnostics.
- `rules/` and rule loading: clean-code false positives.

Required controls:

- Land one adapter migration at a time.
- Keep parity tests before deleting old paths.
- Use advisory defaults and ratchet evidence.
- Re-run four-agent event conformance after dispatcher changes.
- Run packaging smoke tests whenever rules, fixtures, commands, or optional
  surfaces are added.

The graph was re-indexed before P0–P5 implementation. Rerun `kgraph index` and
`kgraph impact <file>` whenever the worktree changes before a later work
package begins.

## 12. Historical Release-Level Estimate

The activity-level estimates in **Current Baseline And Authoritative Scope**
supersede this original coarse sizing. This table remains only to preserve the
mapping from the initial R1-R9 proposal.

Sizing uses S (days), M (about one week), L (two to three weeks), and XL
(multi-release), including tests and documentation for one experienced
engineer.

| Release | Scope | Estimate |
|---|---|---|
| R1 | Finding contract, evidence, eval baseline | L |
| R2 | Workspace and adapter consolidation | XL |
| R3 | Complete JS/TS and web parity | L |
| R4 | Generic command/SARIF/JUnit ingestion | M |
| R5 | Shell corpus and external sandbox contract | M-L |
| R6 | .NET and Java | XL |
| R7 | Pack infrastructure + first four packs | XL |
| R8 | Semantic-delta checks | L-XL, evidence-gated |
| R9 | Shared service, MCP, broader LSP | L |

Recommended staffing: one architectural owner for R1/R2, then separate adapter
owners can implement .NET and Java in parallel against the frozen contract.
Framework packs should follow, not overlap, initial adapter development.

## 13. Implementation Task Contract

Every work package is decomposed during its planning session into small tasks
that name exact files and leave tests green. The minimum sequence for each is:

1. Add or update the behavior contract test.
2. Add clean, violation, and error fixtures.
3. Implement the smallest production change.
4. Run focused tests.
5. Run cross-surface parity tests if shared code changed.
6. Run the full suite for behavior-changing Python code.
7. Run `python3 fettle/cli.py check --changed`.
8. Run the relevant behavioral evaluation.
9. Perform manual acceptance in a clean sample repository.
10. Update configuration schema, docs, changelog, and roadmap in the same
    release slice when the public contract changes.

No work package is complete based only on parser unit tests.

## 14. Release Success Criteria

The program is successful when:

1. One policy resolves identically for CLI, hooks, LSP, MCP, and CI inputs.
2. Python, JS/TS, .NET, and Java edits route to the correct workspace and
   native tools.
3. Mixed repositories verify every affected workspace and no unaffected one.
4. Tool failure and unknown analysis are never represented as clean.
5. Every actionable finding carries location, impact, action, and rerun.
6. React/Next.js, ASP.NET Core, Spring Boot, and HTMX packs meet their clean
   corpus and behavioral-eval gates.
7. Semantic-delta rules stay inside latency budgets with measured precision.
8. MCP improves preflight and repair but cannot bypass hook or CI enforcement.
9. Fettle documents shell mediation honestly and delegates containment to
   external sandboxes.
10. The full test suite, Fettle scan, package smoke, and remote CI are green at
    every release boundary.

## 15. Explicit Non-Goals

- Kernel-level eBPF or ptrace enforcement.
- Default-deny network namespaces managed by Fettle.
- A persistent semantic database.
- Whole-repository AST snapshots on every tool call.
- A supervisor daemon or general multi-agent orchestration platform.
- Cryptographic approval by another probabilistic reviewer agent.
- Automatic promotion of learned or framework rules.
- A hosted enterprise telemetry control plane without validated demand.
- Bespoke permanent adapters for every commercial scanner.
- Enforce-by-default framework heuristics.

## 16. Planning Gate Status

- Phase 0 UX: complete in `docs/polyglot-governance.ux-spec.md`.
- Phase 0.5 UI: not applicable; this plan changes CLI, hook, LSP, and protocol
  behavior but introduces no visual interface.
- Phase 1 plan: complete in this document.
- Phase 3.5 UAT scenarios: defined in the UX spec; per-release executable
  scenarios remain required before implementation.
- Feature manifest: not applicable; this repository does not maintain one.
- Implementation authorization: approved for P0–P5.
