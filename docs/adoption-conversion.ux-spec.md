# UX Spec: Adoption And Contributor Conversion

Status: v1.11.0 implementation contract

Implementation plan: [adoption-conversion-implementation-plan.md](adoption-conversion-implementation-plan.md)

## Jobs To Be Done

When I discover Fettle through GitHub, PyPI, or a recommendation, I want to
understand its concrete value and reproduce one assurance loop in two minutes,
so I can decide whether it belongs in my development workflow.

When I install Fettle from PyPI, I want the advertised agent-governance path to
work without cloning Fettle's source, so installation method does not silently
reduce the product to a scanner.

When I consider contributing, I want a bounded problem, acceptance criteria,
and exact verification commands, so I can submit a useful first pull request
without reverse-engineering the repository's trust model.

When I evaluate a release, I want user outcomes, upgrade implications, and
known boundaries, so I can assess it without reconstructing the changelog.

## Personas

- New adopter: arrives with little context and gives the project at most two
  minutes before deciding whether to continue.
- Platform or power user: compares host coverage, evidence semantics,
  installation behavior, and operational boundaries before adoption.
- Prospective contributor: needs a small, truthful task with a reproducible
  baseline and an unambiguous definition of done.
- Accessible terminal and web user: needs semantic headings, descriptive link
  text, text transcripts, keyboard-accessible controls, and status that does
  not depend on color, motion, or audio.

## User Journey

| Phase | User action | Sees | Desired feeling | Failure to prevent |
|---|---|---|---|---|
| Discover | Finds Fettle through search, a topic, PyPI, or a shared link | Precise description, relevant topics, current release | Oriented | Generic metadata or an unclear category |
| Understand | Opens the README | Problem, supported scope, and one visual proof near the top | Interested | Architecture detail before demonstrated value |
| Prove | Runs the demo commands in a disposable repository | Known finding, explanation, repair path, verification | Confident | A prerecorded claim that cannot be reproduced |
| Adopt | Installs the wheel and previews initialization | Exact files/settings that would change | In control | Source-clone requirement appearing after installation |
| Govern | Initializes one detected host and runs doctor | Installed bridge, host status, and recovery steps | Safe | Partial wiring reported as success |
| Contribute | Opens a starter issue | Scope, affected files, acceptance criteria, commands | Capable | Broad roadmap item labeled as easy |
| Track | Reads a release | Outcomes, upgrade notes, evidence, boundaries | Informed | Changelog-only release body |
| Engage | Seeks help after community demand exists | One moderated discussion category and response expectations | Welcome | Empty or unmoderated community surface |

## Flows And Budgets

### Evaluation Flow

1. Open the repository and understand the assurance loop without scrolling
   through subsystem detail.
2. Play the short proof or open its text transcript.
3. Run the same commands in the supplied disposable demo repository.
4. Follow the displayed next action to documentation or installation.

- Click budget: at most two clicks from repository landing to runnable proof.
- Time budget: value proposition understood in 30 seconds; proof reproduced in
  two minutes on a machine with Python 3.11+ and `pipx`.
- Memory budget: all commands remain together; no value must be copied from a
  previous page.

### Wheel Adoption Flow

1. Run `pipx install finefettle`.
2. In a disposable repository, run `fettle init --dry-run`.
3. Review every repository and host-level mutation before it occurs.
4. Run `fettle init` and then `fettle doctor`.
5. Trigger a known advisory finding and inspect its recovery action.

- Interaction budget: three commands after package installation.
- Safety budget: no host configuration mutation during `--dry-run`; existing
  unrelated settings are preserved; malformed settings remain an actionable
  non-success state.
- Compatibility budget: clone and wheel paths produce equivalent normalized
  host behavior before README claims are changed.

### Contributor Flow

1. Filter issues by `good first issue` or `help wanted`.
2. Select an issue whose body names outcome, non-goals, files, and checks.
3. Follow `CONTRIBUTING.md` setup.
4. Reproduce the baseline, make the bounded change, and run listed checks.

- Click budget: at most three clicks from README to a suitable issue.
- Time budget: task suitability understood in five minutes; development setup
  reaches a valid `fettle doctor` result in ten minutes, excluding downloads.

## Required States

### First-Time Empty

- No demonstration yet: README shows a truthful text command sequence and a
  clearly labeled planned visual proof, never an empty media placeholder.
- No contributor issues yet: contribution link explains that starter tasks are
  being curated and does not imply an active backlog.
- No Discussions yet: support routes to issues for reproducible defects and the
  private security channel for vulnerabilities.

### Cleared Empty

- A demo run with no finding states that the fixture may have been repaired or
  the wrong directory was used, then gives a reset command.
- An issue filter with all starter tasks completed celebrates that state and
  links to `help wanted`, not to a dead end.

### Filtered Empty

- GitHub label filters with no matches retain a clear-filter route.
- Documentation search or browser find has no custom UI requirement; headings
  and descriptive language provide native-browser information scent.

### Loading Brief

- README media reserves dimensions to avoid layout movement. No custom spinner
  is needed for a static repository page.

### Loading Long

- The proof has a text transcript and runnable commands directly below or
  beside it, so slow media never blocks evaluation.

### Populated

- Metadata, proof, release notes, starter issues, and installation instructions
  agree on package name, command name, supported hosts, and current boundaries.

### Error Recoverable

- Missing tool, unsupported host, malformed host configuration, unavailable
  media, or failed demo command names what happened and gives one next command
  or link. User-owned files and configuration remain intact.

### Error Fatal

- If packaged bridge integrity or compatibility cannot be established,
  initialization does not claim governance is wired. It reports the affected
  host, avoids partial authority claims, and links to the clone path or removal
  instructions.

### Offline

- README transcript and demo repository remain usable after clone. Wheel
  initialization performs no hidden network access; optional tool installation
  remains explicit.

### Stale Or Superseded

- The proof identifies the Fettle version it was recorded against. Release and
  demo contract checks fail when commands, expected output, or version claims
  drift. Old packaged bridges are replaced only after a dry-run-visible version
  comparison.

## Information Architecture And Disclosure

- GitHub About supplies category and supported-host discovery terms; topics do
  not become an exhaustive capability claim.
- README defaults to problem, proof, quick start, and boundaries. Architecture,
  formal verification, and detailed capability tables remain below the proof.
- The visual proof sits after the opening explanation and before the detailed
  quick start. Its transcript is adjacent and uses descriptive links.
- Advanced installation details and per-host recovery remain in active guides,
  linked from the exact failure state.
- Contributor tasks live in GitHub Issues. The roadmap remains strategic and is
  not converted wholesale into beginner issues.
- Discussions remain disabled until the demand gate in the implementation plan
  passes.

## Accessibility

- Media has a concise accessible name, a text transcript, no autoplay audio,
  no rapid flashing, and no information conveyed only by animation or color.
- Motion should be limited to purposeful terminal progression and respect a
  static fallback; the transcript is authoritative.
- README and issue templates use one H1 followed by ordered semantic headings.
- Link text names its destination or action; avoid repeated `learn more` links.
- Terminal examples work in `NO_COLOR=1`; expected states include textual
  labels and exit behavior.
- GitHub-native controls retain their default keyboard and focus behavior.

## Progressive Disclosure

- Default: one problem statement, one proof, one evaluation command sequence,
  and one next adoption action.
- Detailed: supported-host matrix, evidence semantics, packaging internals,
  operational boundaries, and contributor verification.
- No primary command or known limitation is hidden solely inside media.

## UX Metrics

- A clean-machine evaluator reproduces the text proof in at most two minutes,
  excluding package download, in three consecutive trials.
- Every proof command and expected state is contract-tested.
- README media has a transcript and useful fallback when blocked.
- Wheel initialization from a clean environment yields no source-clone action
  for every host declared wheel-supported.
- A contributor can identify issue scope, baseline, and checks from the issue
  body without maintainer clarification.
- GitHub unique visitors, PyPI downloads, demo completions where measurable,
  issue engagement, and external pull requests are tracked separately. Raw
  clone count is not treated as acquisition because automation dominates it.

## BDD Acceptance Scenarios

### Scenario: A new visitor can reproduce the proof

Given a clean disposable repository and the released wheel
When the visitor follows the README proof commands in order
Then Fettle reports the documented known finding
And `fettle explain` provides the documented recovery direction
And the repaired state can be verified without undocumented setup.

### Scenario: Media failure does not block evaluation

Given the README animation cannot load or motion is unsuitable
When the visitor reaches the proof section
Then an adjacent transcript describes every meaningful state
And the same runnable commands remain available as text.

### Scenario: Wheel initialization previews all mutations

Given Fettle was installed from a wheel and one supported host is detected
When the user runs `fettle init --dry-run`
Then no repository or home-directory file changes
And every proposed bridge and configuration mutation is listed.

### Scenario: Wheel governance survives a new process

Given wheel initialization completed for a supported host
When that host starts a new session and emits a supported event
Then the packaged Fettle dispatcher receives the normalized event
And an advisory finding is returned through that host's native surface
And `fettle doctor` does not request a source checkout.

### Scenario: Existing host settings are preserved

Given a supported host configuration contains unrelated valid settings
When wheel initialization adds Fettle
Then unrelated settings are byte-equivalent or semantically equivalent as the
host format permits
And a second initialization is idempotent.

### Scenario: Broken bridge evidence is visible

Given a packaged bridge is missing, malformed, stale, or points to an
unavailable executable
When initialization or doctor validates it
Then that host is not reported as governed
And one specific recovery action is shown.

### Scenario: A starter issue is genuinely bounded

Given a prospective contributor opens a `good first issue`
When they read its body
Then it names the user outcome, non-goals, exact likely files, acceptance
criteria, and verification commands
And it does not delegate a trust-boundary or architecture decision to them.

### Scenario: A release communicates adoption impact

Given a user opens a GitHub release
When they read its body
Then they can identify major outcomes, installation or upgrade implications,
known boundaries, verification links, and the full changelog.

### Scenario: Discussions remain demand-gated

Given the repository has not met the documented community-demand threshold
When public surfaces are configured
Then Discussions remains disabled
And defect and security support routes remain explicit.
