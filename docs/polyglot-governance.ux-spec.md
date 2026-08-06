# UX Spec: Polyglot Governance

## Jobs To Be Done

When I introduce Fettle into an existing Python, JavaScript/TypeScript, .NET,
Java, or mixed repository, I want Fettle to detect the project structure and
run the repository's native quality tools, so I can get trustworthy in-session
feedback without manually teaching Fettle every command or receiving findings
for the wrong workspace.

When an agent receives a Fettle finding, I want the message to identify the
problem, evidence, repair, and rerun command, so the agent can repair the issue
without guessing or consuming unnecessary context.

When a required tool is unavailable or fails, I want Fettle to distinguish an
unknown result from a clean result, so I do not trust a check that never ran.

## Personas

- New adopter: wants useful advisory feedback after `fettle init` without
  understanding adapters, rule packs, or workspace routing.
- Repository maintainer: wants explicit command overrides, stable findings,
  and gradual promotion from advisory to enforce.
- Platform engineer: wants centrally pinned policy, consistent behavior across
  agent hosts, and machine-readable evidence for CI and audit.
- Agent/operator: needs concise, actionable findings and deterministic rerun
  instructions within a limited context budget.
- Accessible terminal user: needs status and severity conveyed through text and
  exit codes, never color alone.

## Primary Journey

| Phase | User action | User sees | Failure to prevent |
|---|---|---|---|
| Discover | Runs `fettle init` | Detected workspaces, languages, frameworks, native commands, and missing tools | Silent misclassification |
| Confirm | Accepts detection or edits `.fettle.toml` | Exact effective configuration and provenance | Hidden defaults or wrong workspace |
| Work | Agent edits a supported file | Concise finding with location, reason, repair, and rerun command | Generic block or context flood |
| Repair | Agent changes code and reruns the check | New evidence supersedes the old verdict | Stale pass or repeated loop |
| Verify | Runs `fettle verify` | Workspace-scoped commands and a bound verification stamp | Running only the wrong stack's tests |
| Graduate | Reviews `fettle report` / `fettle ratchet` | Fire rate, overrides, tool errors, and false-positive evidence | Enforcing an unproven rule |

## Command Flow And Budgets

1. `fettle init --interactive` detects all workspaces and prints a summary.
2. The user confirms or declines the result in one prompt.
3. `fettle doctor` reports missing native tools with exact installation or
   repository-wrapper guidance.
4. Normal edits receive no output when clean and one concise repair-oriented
   finding group when violations occur.
5. `fettle explain --detailed` provides evidence only when requested.

Budgets:

- Initial setup: at most two confirmations after stack detection.
- Clean edit: no advisory output; hook completes within its configured budget.
- Violating edit: primary repair instruction visible without opening another
  command.
- Detailed diagnosis: one follow-up command.

## Required States

- First-time empty: no supported marker found; explain supported markers and
  show the `[profile.workspaces]` override route.
- Cleared empty: no active findings; show that checks ran and distinguish this
  from no applicable checks.
- Filtered empty: requested workspace, language, or rule has no matching
  evidence; name the active filter.
- Loading brief: CLI remains quiet for sub-second work.
- Loading long: minutes-world commands show the current workspace and native
  command without pretending completion.
- Populated: detected workspaces and findings are grouped by workspace.
- Error recoverable: missing tool, invalid parser output, or timeout includes
  the failed tool, consequence, and exact recovery action.
- Error fatal: invalid or weakened central policy blocks before tool execution
  and explains the trust failure.
- Offline: local hooks and cached pinned policy continue; network-backed checks
  are explicitly unknown.
- Stale: cached profile, verification stamp, or policy identifies why it is
  stale and how to refresh it.

## Finding Contract

The default agent-facing form contains, in order:

1. Decision and stable rule identifier.
2. File and location.
3. One-sentence impact.
4. One recommended action.
5. Exact rerun command.

Detailed output may additionally include tool output, policy provenance,
confidence, suppression metadata, and evidence identifiers. Raw output is
bounded and redacted. Tool failure is never represented as an empty finding
list or a pass.

## Framework Behavior

- Languages own execution adapters and native tool invocation.
- Framework packs own deterministic conventions and rules.
- Framework detection enables advisory rules only; it never silently enables
  blocking policy.
- Repository-native analyzers and plugins are preferred over equivalent Fettle
  reimplementations.
- A framework pack may add test conventions, but it cannot weaken language or
  organization policy.

## Accessibility

- Text labels accompany severity and status; ANSI color is optional decoration.
- Human output remains understandable with `NO_COLOR=1`.
- Machine output has stable JSON fields and exit codes.
- Progress output does not continually rewrite one terminal line when stderr is
  not a TTY.
- Instructions do not rely on icons, color, or mouse interaction.

## Progressive Disclosure

- Default: detected stack, active checks, primary finding, repair, rerun.
- `--detailed`: evidence, provenance, native command output, timing.
- `--json`: full stable machine contract.
- Advanced command and workspace overrides remain in `.fettle.toml`; the setup
  flow does not ask about them unless detection is rejected.

## BDD Acceptance Scenarios

### Scenario: Required scanner cannot produce evidence

Given a CI policy requires Ruff or Semgrep
When the binary is missing, exits abnormally, times out, or returns malformed output
Then Fettle reports `tool_error`, not pass
And names the failed tool and recovery action
And the CI command exits non-zero while an interactive hook remains visibly fail-open.

### Scenario: Red-before-green evidence is reconstructed

Given a pull request adds a behavior test and implementation change
When the verification job evaluates the selected test against the merge base
Then it records the expected failure against the unmodified base
And records the passing result against the candidate revision
And binds both commands, revisions, and outputs to one evidence identifier.

### Scenario: A gate is overridden

Given an enforcing gate blocks a change and policy permits an override
When an authorized operator supplies a reason and expiry
Then the change can proceed according to policy
And Fettle records the actor, gate, reason, timestamp, expiry, affected revision,
and prior evidence identifier
And reports the override distinctly from a pass.

### Scenario: Mutation analysis produces no trustworthy result

Given changed implementation files are selected for mutation analysis
When the engine creates no mutants or its result cannot be parsed
Then Fettle reports `unknown` or `tool_error`, not a 100% mutation score
And identifies the selected files and the exact rerun command.

### Scenario: A network-backed check is unavailable

Given a local verification command includes an optional network integration
When the operator is offline or the service is unavailable
Then local checks continue
And the network check is displayed as unknown with its last successful evidence time
And an enforcing CI policy fails unless a recorded override applies.

### Scenario: First edit in a detected TypeScript workspace

Given a repository has `package.json`, `tsconfig.json`, and an ESLint script
When the user initializes Fettle and an agent edits a `.tsx` file
Then Fettle routes the file to that workspace
And invokes the configured local lint path
And reports a violation with location, repair, and rerun command
And does not run checks belonging to another workspace.

### Scenario: Mixed .NET and React repository

Given a repository contains a solution under `backend/` and a Node workspace
under `frontend/`
When files in both workspaces are edited and `fettle verify` runs
Then Fettle runs the appropriate test command from each affected workspace
And the verification stamp records both commands and scopes
And the Stop gate rejects a stamp that omits either edited workspace.

### Scenario: Missing native analyzer

Given a Java workspace enables a SpotBugs-backed check
And the configured wrapper or plugin cannot execute it
When Fettle evaluates the workspace
Then the result is `tool_error` or `unknown`, not pass
And the user sees an actionable setup or configuration instruction
And enforce behavior follows the explicit policy for tool errors.

### Scenario: Clean framework fixture

Given a clean ASP.NET Core, Spring Boot, React, or HTMX fixture
When its advisory framework pack runs
Then Fettle emits no framework violation
And records that the applicable checks completed.

### Scenario: Agent repairs a framework violation

Given a framework rule reports a high-confidence violation
When the agent follows the suggested repair and reruns the supplied command
Then the violation disappears
And native build and tests remain green
And the behavioral evaluation records a successful repair.

### Scenario: Unsupported framework remains usable

Given a supported language uses an unknown framework
When an agent edits source code
Then language-native checks and generic process gates still run
And Fettle does not require a framework pack.

### Scenario: Shell guard encounters ambiguous execution

Given destructive or package-install intent is obscured by nested shell syntax
When enforce mode cannot classify the command safely
Then Fettle blocks with an ambiguous-command reason
And states that the guard is mediation rather than operating-system isolation.

## UX Success Metrics

- At least 95% correct workspace routing on the maintained fixture corpus.
- Zero clean fixtures blocked by a newly introduced framework pack.
- At least 80% live-agent repair success before a rule is considered for
  default advisory activation.
- Median block-to-repair cycle of at most two agent turns.
- Every non-pass verdict provides a next action; every actionable finding
  provides a rerun command when one exists.
- No tool error or timeout is serialized as pass.
