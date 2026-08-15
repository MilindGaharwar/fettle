# Adoption And Contributor Conversion Implementation Plan

Status: IMPLEMENTED for v1.11.0; Discussions deferred by demand gate

Related contracts:

- [Adoption and contributor UX](adoption-conversion.ux-spec.md)
- [Public-surface UI specification](adoption-conversion.ui-spec.md)
- [Roadmap](ROADMAP.md)
- [Contributing guide](../CONTRIBUTING.md)

## 1. Outcome

### User Story

As a developer evaluating agentic software assurance, I want to discover
Fettle, reproduce its core loop, install the promised governance surface, and
find a safe contribution path, so I can progress from visitor to adopter or
contributor without hidden setup or unsupported claims.

### Business Outcome

Improve the sequence from discovery to credible proof to adoption before adding
community surface area. Measure unique human engagement and completed journeys,
not raw clone traffic, because the current 20,149 clones from 203 unique cloners
versus 818 views from 26 unique visitors is likely automation-heavy.

### Execution Sequence

```text
baseline metrics and claim inventory
              |
              v
public metadata + release clarity
              |
              v
reproducible text demo -> visual proof
              |
              v
wheel-governance contract -> per-host implementation and graduation
              |
              v
contributor issue seeding + measured response
              |
              v
Discussions only after demand and moderation gates
```

## 2. Assumptions And Boundaries

1. GitHub repository administration and release editing are external mutations
   and require explicit owner approval immediately before execution.
2. The GitHub homepage should initially point to the canonical PyPI page; no
   marketing website is proposed.
3. The package remains Python 3.11+ with zero required runtime dependencies.
4. The installed command remains `fettle`; the distribution remains
   `finefettle`.
5. The proof must execute released behavior. It cannot rely on private state,
   unpublished code, hidden environment variables, or edited terminal output.
6. Live governance remains advisory-first. Packaging does not upgrade any gate
   or broaden host authority.
7. Clone-mode behavior remains supported until installed-wheel parity is
   demonstrated independently for each host.
8. Wheel support is claimed per host only after that host passes contract,
   integration, installed-artifact, and manual session evidence.
9. Existing user host settings must be preserved. Malformed or conflicting
   configuration is a visible non-success, never overwritten.
10. No telemetry is added. GitHub traffic and PyPI's public aggregate data are
    sufficient for the initial acquisition baseline.
11. Raw clone count is excluded from the primary funnel because current volume
    is inconsistent with unique repository traffic and likely automated.
12. Starter issues are selected only from real bounded needs. Core evidence,
    host-security, release-authority, and architecture decisions are not marked
    `good first issue`.
13. Discussions stays disabled until the demand gate in WP6 passes.
14. Existing unrelated `fettle/bdd_gate.py` and `fettle/bdd_gate.py.bak` changes
    are excluded from every work package and commit.
15. No commit, push, release edit, repository setting mutation, or issue
    publication occurs without the corresponding approval gate.

## 3. Decisions And Tradeoffs

### 3.1 Delivery Order

| Approach | Benefit | Cost/risk | Decision |
|---|---|---|---|
| Open every public channel immediately | Fast appearance of activity | Empty surfaces and unsupported promises reduce trust | Reject |
| Finish wheel parity before any public improvement | Strongest eventual funnel | Delays cheap discovery and proof gains | Reject |
| Metadata, proof, package parity, contributor path, then community | Small reversible steps; evidence before claims | Requires staged approvals | Adopt |

### 3.2 Demonstration Form

| Approach | Benefit | Cost/risk | Decision |
|---|---|---|---|
| Recording only | Fast and visually persuasive | Stales quickly; inaccessible; not reproducible | Reject |
| Text fixture only | Testable and accessible | Lower immediate comprehension | Required authority |
| Contract-tested fixture plus short recording and transcript | Reproducible and understandable | Small maintenance burden | Adopt |

### 3.3 Packaged Governance Assets

| Approach | Benefit | Cost/risk | Decision |
|---|---|---|---|
| Point hosts into `site-packages` | Minimal implementation | Environment paths move; plugin roots are brittle; uninstall state is unclear | Reject |
| Reuse a global source checkout | Existing behavior | Preserves the central adoption gap | Reject |
| Materialize a versioned bridge in user data that invokes the installed CLI | Stable host path; dry-run and integrity checks are possible | Requires lifecycle and upgrade contract | Recommend, freeze in WP3 before implementation |

The bridge must contain only host transport assets and immutable metadata. Core
Python logic remains in the installed package and is invoked through a stable,
quoted executable contract. The design must explicitly handle pipx environment
paths, upgrades, uninstalls, stale bridges, spaces in paths, and host timeout
semantics before code is authorized.

### 3.4 Contributor Backlog

| Approach | Benefit | Cost/risk | Decision |
|---|---|---|---|
| Label roadmap epics as beginner work | Quickly fills tracker | Misleads contributors and creates review burden | Reject |
| Publish 3-5 independently reproducible, non-authority tasks | Honest first contribution path | Requires maintainer curation | Adopt |
| Wait for unsolicited issues | No curation cost | No visible entry point | Reject |

### 3.5 Discussions

Discussions is not an acquisition strategy by itself. Enable it only after at
least one of these rolling 30-day demand signals exists and the owner commits to
a response cadence:

- three distinct external users ask usage or design questions that do not fit a
  reproducible defect issue; or
- two external pull requests or issue contributors need a shared Q&A surface;
  or
- 25 stars and at least ten weekly unique repository visitors for four
  consecutive weeks.

The moderation gate additionally requires named categories, a pinned welcome
post, security-routing language, and an owner response target of five business
days. Otherwise Discussions remains disabled.

## 4. Baseline And Success Measures

Record a dated baseline immediately before external mutations:

| Measure | Current observed baseline | Target after 30 days |
|---|---:|---:|
| GitHub unique visitors, trailing 14 days | 26 | Directional increase; report value, do not promise a percentage from one sample |
| GitHub stars | 2 | Diagnostic only; no vanity target gates product work |
| Forks / open issues / open PRs | 0 / 0 / 0 | At least three actionable public issues; external engagement reported separately |
| Repository topics | None | 8-10 accurate topics |
| Homepage | None | Canonical PyPI URL |
| Release v1.10.0 body | Changelog link only | Outcome-oriented notes with boundaries and changelog |
| Runnable public proof | README commands only | Contract-tested fixture, transcript, and short proof |
| Wheel live-governance path | Requires checkout | Graduated per supported host; no blanket claim before parity |

Primary measures:

- successful clean replay of the two-minute proof;
- `fettle init --dry-run` to `fettle doctor` completion from an installed wheel;
- external issue comments, pull requests, and accepted contributions;
- unique repository visitors and PyPI downloads as separate directional series.

Guardrails:

- support burden and unresolved questions;
- demo drift failures;
- initialization errors or partial host wiring;
- issue closure without contributor-ready outcomes;
- no increase in unsupported security or enforcement claims.

## 5. Blast Radius

`kgraph impact README.md pyproject.toml setup.py fettle/init_cmd.py --json`
identified direct impact on `fettle.cli.cmd_init` and
`fettle.cli.cmd_workflows`; dynamic host processes and cross-language TypeScript
edges are outside kgraph's analysis and require explicit tests.

| Area | Risk | Required containment |
|---|---|---|
| README and docs | Claims drift from released behavior | Demo contract tests and installed-wheel replay before editing claims |
| GitHub metadata/releases | Public, immediate external mutation | Capture before-state JSON and obtain approval |
| Package build | Missing or executable-bit-lost assets | Inspect wheel/sdist manifests and install both in clean environments |
| `fettle init` | User home and repository mutation | Isolated HOME tests, dry-run invariants, idempotency, conflict cases |
| Claude Code | Plugin-root and manifest conventions | Host-specific installed-session UAT; no parity inference from another host |
| Codex CLI | Hook schema and enablement | Preserve explicit feature-toggle action and timeout semantics |
| Gemini CLI | Millisecond timeout and event vocabulary | Host-specific wire tests |
| OpenCode | TypeScript plugin path and process launch | Package bridge test plus real OpenCode session UAT |
| Upgrade/uninstall | Stale bridge points to removed environment | Version/integrity doctor state and documented cleanup |
| Contributor issues | Review burden or misleading scope | Maintainer review before labels/publication |
| Release workflow | Generated notes omit required structure | Template/contract validation before changing automation |

## 6. Work Packages

Every work package is independently approvable. WP3-WP4 are the highest-risk
package and require a second owner approval after the bridge contract is frozen.

### WP0: Freeze Baseline And Claims

Estimate: 30-45 minutes. Dependencies: owner approval to start read-only work.

- [ ] Save a dated baseline in `docs/engagement/adoption-baseline-2026-08.md`
  containing `gh repo view`, traffic views/clones, release metadata, and PyPI
  project links. Verify every figure includes collection date and window.
- [ ] Inventory every README and docs claim about wheel versus clone behavior in
  the same baseline file. Verify each claim links to a file and line.
- [ ] Run the current README evaluation commands from the released wheel in a
  clean temporary environment. Record commands, exit codes, and elapsed time;
  do not reinterpret failures as success.
- [ ] Define a 30-day review date and measurement query in the baseline file.
  Verify raw clones are explicitly excluded from primary conversion evidence.

Exit: a reproducible before-state exists before any public or package mutation.

### WP1: Public Discovery And Release Clarity

Estimate: 45-75 minutes. Dependencies: WP0 and explicit approval for GitHub
mutations.

- [ ] Review the proposed topics against shipped behavior. Initial candidates:
  `ai-agents`, `developer-tools`, `software-quality`, `python`, `cli`,
  `claude-code`, `codex-cli`, `gemini-cli`, `opencode`, `devsecops`. Verify each
  topic has direct support in `README.md` or remove it.
- [ ] Capture `gh repo view MilindGaharwar/fettle --json
  homepageUrl,repositoryTopics,description` before mutation in the baseline.
- [ ] Set the homepage to `https://pypi.org/project/finefettle/` and apply only
  approved topics with `gh repo edit`. Re-query JSON and compare exact values.
- [ ] Draft v1.10.0 release notes in a temporary review artifact first, using
  sections: outcome, what changed, adoption/upgrade, evidence, known boundaries,
  full changelog. Verify all numbers against `CHANGELOG.md`.
- [ ] Update the existing v1.10.0 release only after owner approval. Re-fetch the
  release body and verify links, headings, and unchanged tag/assets.
- [ ] Add `.github/release.yml` only if GitHub-generated note categories improve
  future release structure without replacing authored outcome/boundary text.
  Verify behavior against a draft release or documented GitHub schema.

Exit: search metadata is accurate and v1.10.0 communicates user outcomes without
changing code or overstating package behavior.

### WP2: Reproducible Two-Minute Proof

Estimate: 0.5-1 day. Dependencies: WP0; released commands selected from actual
clean replay.

- [ ] Choose the smallest disposable fixture after replay. Prefer one Python
  file and one deterministic finding; reject examples requiring Semgrep download,
  network access, agent settings, or private state.
- [ ] Add the fixture under `examples/assurance-loop/` with only source,
  `.fettle.toml` if required, and a short README. Verify a fresh copy starts in
  the documented violating state.
- [ ] Add one reset script only if Git cannot provide a clearer reset command.
  Any script must be cross-platform Python, not shell-specific. Verify reset is
  idempotent.
- [ ] Add `tests/test_assurance_loop_example.py` to execute the authoritative
  command sequence and assert semantic states and exit codes, not unstable full
  output snapshots.
- [ ] Freeze the exact detect, explain, repair, and verify transcript in
  `examples/assurance-loop/README.md`. Verify every command by copy-paste in a
  clean installed-wheel environment.
- [ ] Add a concise proof section to `README.md` after the opening explanation
  and before `Start in Two Minutes`. Keep commands adjacent to the media and link
  to the fixture.
- [ ] Record the approved storyboard with no edited output. Add a compressed
  asset under `assets/` only if it meets the UI size/readability budget; otherwise
  host a release asset and retain a checked-in static poster.
- [ ] Add alt text, dimensions, poster/fallback, and a text transcript. Preview
  README at mobile and desktop widths in light and dark GitHub themes.
- [ ] Time three clean replays. Record median and maximum in the example README;
  if any exceeds two minutes excluding download, simplify before publishing.

Exit: the proof is executable without media, the media matches the executable
proof, and drift fails an automated test.

### WP3: Freeze Installed-Governance Bridge Contract

Estimate: 0.5-1 day. Dependencies: WP0-WP2. This package produces design and
test fixtures only; implementation requires renewed owner approval.

- [ ] Inventory every runtime path used by `hooks/hooks.json`,
  `hooks/subagent_inject.js`, `fettle/run.sh`, `integrations/opencode/fettle.ts`,
  `fettle/init_cmd.py`, and `fettle/doctor.py`. Record each host's executable,
  event, timeout unit, stdin, stdout, and failure behavior in
  `docs/installed-governance-bridge.md`.
- [ ] Define a platform-specific user-data root using standard OS conventions,
  with versioned bridge directory, atomic publication, manifest digest, owner
  permissions, and no repository-write authority.
- [ ] Define the bridge lifecycle for install, dry run, no-op rerun, package
  upgrade, downgrade refusal or explicit confirmation, interrupted publication,
  package uninstall, stale executable, and cleanup.
- [ ] Define a stable dispatcher entry point that avoids unquoted shell
  interpolation and preserves stdin/stdout and host exit behavior. Reject any
  design that embeds user-controlled paths in a shell command without safe
  serialization.
- [ ] Define per-host capability states: `supported-installed`, `clone-only`,
  `manual-action`, `conflict`, `stale`, and `unavailable`. Ensure no aggregate
  success hides a host non-success.
- [ ] Add red/green contract fixtures for valid, missing, malformed, tampered,
  stale, conflicting, path-with-space, and interrupted bridges under
  `tests/fixtures/installed_bridge/`.
- [ ] Run a threat review covering symlink replacement, writable parent
  directories, command injection, malicious host config, executable
  substitution, downgrade, and partial updates.
- [ ] Present the frozen contract, residual risks, exact implementation files,
  and host graduation matrix for explicit approval before WP4.

Exit: no production behavior changes; implementation can proceed without making
architecture decisions during coding.

### WP4: Implement And Graduate Wheel Governance Per Host

Estimate: 2-4 days after contract approval. Dependencies: approved WP3.

- [ ] Add bridge resource resolution to `fettle/_resources.py`. Verify clone,
  source-tree, wheel, and sdist resolution with explicit tests.
- [ ] Extend `setup.py` and `pyproject.toml` package data only for assets named by
  the frozen contract. Build artifacts and inspect their file lists and modes.
- [ ] Add the smallest bridge publication/lifecycle module under `fettle/`.
  Verify atomicity, permissions, integrity, stale state, conflict handling, and
  path-with-space cases before wiring `init`.
- [ ] Modify `fettle/init_cmd.py` so `--dry-run` reports bridge and host mutations
  without writing. Verify repository and fake HOME trees are byte-identical.
- [ ] Preserve clone behavior while making installed behavior explicit. Verify
  idempotent second run and no overwrite of malformed or foreign host entries.
- [ ] Extend `fettle/doctor.py` to validate bridge version, digest, executable,
  package version, and each detected host registration. Verify every non-success
  has one recovery action.
- [ ] Add isolated-HOME unit tests in `tests/test_init_cmd.py` and doctor tests for
  every bridge fixture. Keep host assertions separate.
- [ ] Add installed wheel and sdist smoke tests to `.github/workflows/release.yml`:
  initialize in a fake HOME, validate bridge manifest/assets, run a normalized
  event, and assert no checkout instruction for graduated hosts.
- [ ] Graduate Codex only after its contract and real-session UAT pass; update
  README wording for Codex only.
- [ ] Graduate Gemini only after its contract and real-session UAT pass; update
  README wording for Gemini only.
- [ ] Graduate OpenCode only after TypeScript bridge launch and real-session UAT
  pass; update `docs/OPENCODE.md` and README wording for OpenCode only.
- [ ] Graduate Claude Code only after plugin discovery, SubagentStart transport,
  and real-session UAT pass; update README wording for Claude only.
- [ ] Run clean pipx upgrade UAT from the previous release and verify bridge
  replacement, rollback instructions, and stale-state detection.
- [ ] Update `CHANGELOG.md`, `README.md`, `docs/README.md`, and relevant host
  guides only with capabilities that individually graduated.

Exit: each claimed host works from an installed artifact in a new process;
ungraduated hosts remain honestly clone-only.

### WP5: Contributor-Ready Backlog

Estimate: 2-3 hours. Dependencies: WP1; WP2 provides one likely documentation
maintenance surface but is not required.

- [ ] Add `.github/ISSUE_TEMPLATE/bug.yml` with reproduction, expected/actual
  canonical state, Fettle version, install mode, host, and redaction reminder.
  Verify security reports route to `SECURITY.md`.
- [ ] Add `.github/ISSUE_TEMPLATE/feature.yml` with user outcome, current
  workaround, evidence of demand, boundaries, and willingness to contribute.
- [ ] Add `.github/ISSUE_TEMPLATE/config.yml` with blank issues enabled only if
  needed and links to security and contributor guidance. Validate YAML syntax.
- [ ] Audit `ROADMAP.md`, docs drift, examples, and test ergonomics for five
  candidate tasks. Reject any task requiring architecture, authority semantics,
  secrets, release rights, or host access unavailable to contributors.
- [ ] For each retained task, reproduce the baseline and draft exact likely
  files, non-goals, acceptance criteria, and commands locally before publication.
- [ ] Publish three tasks first; use `good first issue` only when one focused PR
  can close the task, otherwise use `help wanted`. Verify labels and dependency
  links through `gh issue view`.
- [ ] Add a short contributor-entry link in `README.md` and `CONTRIBUTING.md`
  only after issues exist. Verify no dead filtered link.
- [ ] Review issue response and completion after 30 days before publishing the
  remaining candidates.

Exit: at least three truthful, independently actionable issues exist and the
repository routes contributors to them.

### WP6: Demand-Gated Discussions

Estimate: 45-90 minutes when admitted. Dependencies: WP5 and demand threshold.

- [ ] At the 30-day review, record whether a demand and moderation gate from
  section 3.5 passed. If not, record `deferred` and make no repository mutation.
- [ ] If admitted, obtain explicit owner approval and enable Discussions with
  only `Q&A` and `Show and tell` categories initially.
- [ ] Publish a pinned welcome post that defines scope, five-business-day
  response expectation, issue routing, code of conduct, and private security
  routing.
- [ ] Verify category names, links, pinned status, and anonymous visitor view.
- [ ] Review after 30 days; disable or consolidate inactive surfaces if they add
  moderation cost without improving user support.

Exit: Discussions exists only with evidenced demand and an operating owner.

### WP7: Verification, Review, And Shipping

Estimate: 0.5-1 day across approved packages. Dependencies: each implemented
package.

- [ ] Run focused tests after each work package and keep the system green before
  starting the next package.
- [ ] Before changing packaging behavior, load the testing discipline and add
  contract, error, boundary, and regression evidence defined in WP3.
- [ ] Run `uv run --extra dev ruff check fettle tests`.
- [ ] Run focused demo, init, doctor, workflow, resource, CLI, and packaging
  suites, then `uv run --extra dev pytest` when behavior changes.
- [ ] Run `uv run fettle config --validate` and `uv run fettle check --changed`.
- [ ] Run `git diff --check` and inspect wheel/sdist contents from clean builds.
- [ ] Run `kgraph impact` on every changed Python/package file and review dynamic
  host edges manually.
- [ ] Build and install wheel and sdist into separate clean environments; execute
  the demo and bridge smoke paths from outside the checkout.
- [ ] Perform real host UAT separately and sequentially. Never infer one host's
  result from another or share terminal outcomes across calibrations.
- [ ] Preview README on mobile/desktop, light/dark, media-blocked, and
  keyboard-only paths; verify transcript completeness.
- [ ] Run the repository-required Fettle quality scan before declaring any
  package complete.
- [ ] Run `fettle completion validate` before claiming a milestone complete.
- [ ] Review `git status` and exclude `fettle/bdd_gate.py` and
  `fettle/bdd_gate.py.bak` from all intended diffs and commits.
- [ ] Request separate approval before commit, push, GitHub metadata mutation,
  release editing, issue publication, or Discussions enablement.

Exit: every required criterion has evidence; missing, stale, skipped, blocked,
contradictory, or indeterminate evidence remains non-pass.

## 7. Package Approval Gates

| Gate | Decision requested | Evidence required before request |
|---|---|---|
| G0 | Start WP0-WP2 planning execution | This plan, UX spec, UI spec |
| G1 | Mutate GitHub metadata and v1.10.0 release | Captured before-state and reviewed exact values/body |
| G2 | Implement WP4 | Frozen WP3 bridge contract, threat review, red/green fixtures, per-host matrix |
| G3 | Publish contributor issues | Reviewed issue bodies, reproduced baselines, labels |
| G4 | Enable Discussions | Recorded demand threshold, moderation owner, welcome text |
| G5 | Commit/push/release | Full verification evidence and intended-file diff |

Approval of G0 does not imply approval of G1-G5.

## 8. Completion Criteria

This initiative is complete only when all applicable criteria pass:

- metadata and release notes are accurate and externally verified;
- the authoritative proof runs from the released artifact within its time
  budget and the visual proof has an equivalent transcript;
- every README wheel-governance claim has installed-artifact and real-host
  evidence for that host;
- dry-run, preservation, idempotency, malformed input, stale bridge, upgrade,
  and cleanup behaviors pass;
- at least three published contributor issues meet the bounded-task contract;
- Discussions is either admitted with evidence and moderation or explicitly
  retained as disabled;
- automated, installed-artifact, UX, accessibility, and manual UAT evidence is
  complete;
- Fettle quality scan and `fettle completion validate` pass;
- no unrelated worktree changes are included.

Timeout, skipped host access, missing traffic data, or a successful clone-mode
test cannot satisfy an installed-wheel success criterion.

## 9. Rollback

- GitHub topics/homepage: restore captured before-state with `gh repo edit`.
- Release body: restore the captured original body; never move or recreate tag
  assets as part of copy rollback.
- README proof: revert the proof section and media reference while retaining the
  executable example if it remains useful and correct.
- Bridge: remove only manifest-owned versioned assets after integrity and path
  checks; restore preserved host configuration entries; never recursively delete
  an unverified user-data path.
- Host graduation: revert documentation claim for that host independently and
  retain visible doctor recovery.
- Issues: close with a transparent reason rather than deleting contribution
  history.
- Discussions: lock/archive with routing notice before disabling if community
  content exists.
