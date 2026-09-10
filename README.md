<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/MilindGaharwar/fettle/main/assets/wordmark-dark.svg">
    <img src="https://raw.githubusercontent.com/MilindGaharwar/fettle/main/assets/wordmark-light.svg" alt="Fettle" height="160">
  </picture>
</p>

<h3 align="center">The open-source trust layer for AI coding agents</h3>

<p align="center"><strong>Catch mistakes while the agent still has context. Prove what passed before the change ships.</strong></p>

<p align="center">
  <a href="https://pypi.org/project/finefettle/"><img src="https://img.shields.io/pypi/v/finefettle?label=PyPI&color=brightgreen" alt="PyPI"></a>
  <a href="https://github.com/MilindGaharwar/fettle/actions/workflows/ci.yml"><img src="https://github.com/MilindGaharwar/fettle/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/finefettle/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-lightgrey" alt="Apache 2.0 license"></a>
</p>

<p align="center">
  <a href="#try-it-in-two-minutes">Quick start</a> ·
  <a href="#why-fettle">Why Fettle</a> ·
  <a href="#one-package-the-complete-python-toolkit">Install</a> ·
  <a href="#capabilities">Capabilities</a> ·
  <a href="docs/README.md">Docs</a>
</p>

```bash
pipx install finefettle
fettle demo
```

One command installs Fettle's complete Python-backed toolkit: Ruff, Semgrep,
pytest, mutmut, PyYAML, Playwright's Python library, bundled rules, workflows,
schemas, demo fixtures, and agent-host bridges. No API key, hosted control plane,
or repository is needed for the demo. Python 3.11+ and Git are prerequisites.

> **fettle** *(v.)* - a foundry term for trimming and cleaning a rough casting.

## Why Fettle

AI coding agents changed the unit of software work. It is no longer only a diff;
it is a chain of authority, edits, delegated workers, tests, exceptions, and
remote verdicts. Most tools inspect one link after the agent has moved on.
Fettle governs the chain while preserving CI as the independent boundary.

```text
intent -> authority -> action -> evidence -> independent verification
                    Fettle trust boundary
```

Fettle is unusual because these controls live in one local, inspectable system:

| Strength | Why it matters |
|---|---|
| In-session feedback | Findings reach the agent while it still understands the code and can repair it. |
| Evidence-bound decisions | Verification and assurance bind verdicts to source, policy, scope, producer, and execution instead of trusting free-floating JSON. |
| Fail-visible semantics | Missing tools, stale artifacts, malformed reports, timeouts, and crashes remain non-pass outcomes. |
| Delegation-safe policy | Digest-checked capsules carry policy and lineage to child agents; delegated work may tighten constraints, not silently loosen them. |
| Host-neutral governance | Claude Code, Codex CLI, Gemini CLI, and OpenCode share one normalized dispatcher and `.fettle.toml` policy. |
| Local-first operation | Core governance runs in your environment without sending source or hidden reasoning to a Fettle service. |
| Measured promotion | Rules and gates begin advisory and move toward enforcement from retained evidence, not confidence alone. |

Fettle does not replace tests, code review, CI, an agent orchestrator, or a
sandbox. It connects them into a control loop and makes unsupported trust visible.

## Try It in Two Minutes

```bash
pipx install finefettle
fettle demo
```

The deterministic offline demo introduces a broad exception handler, detects it,
applies the repair, and independently reruns four tests:

```text
[1/4] VIOLATION INTRODUCED  demo_project/calculator.py:4
[2/4] VIOLATION DETECTED    broad-except-no-reraise
[3/4] REPAIR APPLIED        Exception -> ValueError
[4/4] REPAIR VERIFIED       Re-ran check: clean; re-ran tests: 4 passed
```

The checked-in [assurance loop](examples/assurance-loop/README.md) contains the
fixtures, complete transcript, reset path, and drift test.

To use Fettle in a repository:

```bash
cd your-project
fettle init --dry-run
fettle init --profile solo       # solo | team | enterprise
fettle doctor
fettle check --changed
fettle verify
fettle assurance
```

`fettle init --dry-run` shows every proposed change. `fettle doctor` reports
which capabilities are available or degraded. Start advisory; enforce only after
you have measured signal and tested recovery in your own workflow.

## One Package, the Complete Python Toolkit

The PyPI project is `finefettle`; the installed command is `fettle`.

```bash
pipx install finefettle
# or
uv tool install finefettle
```

The default wheel declares and installs every Python runtime Fettle invokes and
contains its runtime resources. Release CI installs the exact wheel with both
pip and pipx, runs the demo outside the checkout, verifies bundled resources and
executables, rebuilds from the source distribution, generates a CycloneDX SBOM,
and publishes provenance attestations.

A Python package cannot safely embed system-owned runtimes. Install Git first;
add browser binaries (`playwright install`), agent CLIs, language toolchains, or
external services only for the surfaces you use. `fettle doctor` reports these
boundaries rather than pretending an unavailable capability passed. See the
[installation guide](docs/INSTALLATION.md).

## The Trust Loop

1. **Observe early.** Hooks normalize agent events and route changed files to
   configured checks.
2. **Return actionable findings.** The agent sees location, reason, and recovery
   while its working context is intact.
3. **Verify independently.** `fettle verify` runs repository tests and binds the
   result to the exact source and policy.
4. **Assess the whole change.** `fettle assurance` evaluates nine dimensions and
   explains every pass, failure, and unknown.
5. **Retain evidence.** Canonical artifacts, remote CI, mutation reports, UAT,
   and the governance ledger preserve what actually happened.

```text
Assurance Record c04c9a206c05 · PARTIAL · commit 25f4957
  PASS     behavior
  PASS     provenance
  UNKNOWN  security      raw review is not canonical evidence
  UNKNOWN  independence  no retained role-bound authorship decisions
```

Missing evidence does not become success. Failed assessment or persistence also
invalidates an older assurance record so stale approval cannot look current.

## Capabilities

| Area | Shipped capability | Boundary |
|---|---|---|
| Agent lifecycle | Claude Code, Codex CLI, Gemini CLI, and OpenCode transports are implemented and contract-tested | Installation, registration, trust, execution, verification, and enforcement differ; `fettle doctor` reports local evidence without inferring verification |
| Runtime secret boundary | Pre-tool secret access blocking on all four hosts; pre-model output protection on Claude Code and Gemini | Codex and OpenCode output filtering is unsupported; Fettle is not a sandbox |
| Quality | Ruff, bundled Semgrep rules, baselines, suppressions, noise budgets, dependency and boundary checks | `fettle check` is Python plus language-neutral Semgrep; post-edit routing is broader |
| Polyglot workspaces | Python, JavaScript/TypeScript, Go, and Rust post-edit and verification routing | Native toolchains remain external |
| Verification | Test execution with canonical source, policy, scope, producer, and occurrence bindings | Local evidence does not replace remote CI |
| Assurance | Nine-dimension canonical Assurance Record and frozen baseline comparison tooling | Graduation of stronger security enforcement still requires real shadow evidence |
| Mutation quality | Python preflight, changed/full execution, replay, stable fingerprints, accepted baselines, survivor enforcement | Python and pinned `mutmut==2.5.1` only |
| Delegated work | Plans, worktrees, claims, topology, role-aware spawn, policy capsules, lineage, completion reports | Defense in depth, not OS isolation |
| Specifications | Markdown specs, lint, scenario inventory, trace coverage, and canonical drift evidence | Declared links count only when execution evidence passes |
| User acceptance | CLI, API, web, and library sessions; manual walkthroughs; artifact-bound verdicts; seeded benchmark | Report-only unless separately promoted by policy |
| Change intelligence | Deterministic source snapshots and advisory graph `status`, `impact`, and `shadow` | Graph results are advisory |
| State consistency | Contract templates, lint, listing, and execution across modeled views | Contract-specific adapters define observable reach |
| Operations | Digest-pinned central policy, telemetry controls, integrations, compliance/lineage reports, tamper-evident ledger | External services are opt-in |
| Guided workflows | 17 packaged workflows for quality, security, planning, review, and governance | Workflows guide reasoning; CLI behavior stays deterministic |

See the detailed [capability matrix](docs/CAPABILITIES.md) and
[task-oriented documentation](docs/README.md).

## Built for Real Failure Modes

Fettle distinguishes `pass`, `violation`, `tool_error`, `unknown`, and explicit
non-applicable states. Its regression suite pins adversarial cases including
forged verification stamps, deleted canonical references, stale CI evidence,
tampered policy capsules, crashed analyzers, unsafe agent-runner flags, and
incomplete mutation shards.

Selected high-risk protocols also have TLA+ models. Releases use PyPI Trusted
Publishing, SHA-pinned GitHub Actions, build provenance attestations, public-wheel
canaries, and an attached SBOM.

## Common Journeys

### Add Agent Governance

```bash
fettle init --profile team
fettle doctor
fettle workflows list
fettle explain
```

### Coordinate Delegated Work

```bash
fettle plan start --title "Add export" --item "Write contract test"
fettle topology advise
fettle spawn claude --role tester --task "Write the failing tests"
fettle brief --json
```

### Build Trust Evidence

```bash
fettle verify
fettle ci status
fettle mutation preflight --all --json
fettle assurance
fettle ledger status
```

### Connect Requirements to Outcomes

```bash
fettle spec lint
fettle spec coverage
fettle uat doctor
fettle uat manual
fettle consistency lint
```

## Honest Boundaries

- Hooks optimize feedback speed; protected CI remains the independent authority.
- Capsules, claims, shell mediation, and role gates are not a security sandbox.
- Python has the richest analyzer, mutation, and editor support.
- Browser engines, agent CLIs, external services, and non-Python toolchains are
  intentionally not bundled into the Python environment.
- Graph intelligence is advisory. UAT and stronger assurance policies graduate
  only from retained evidence and explicit operator decisions.
- Runtime secret checks reduce accidental disclosure at agent tool boundaries,
  but Codex and OpenCode cannot filter tool output before model exposure.
- Fettle records decisions and observable evidence, not hidden chain-of-thought.

## Documentation

| Goal | Guide |
|---|---|
| Install, upgrade, or remove Fettle | [Installation](docs/INSTALLATION.md) |
| Pick the right command | [Documentation index](docs/README.md) |
| Compare supported surfaces | [Capability matrix](docs/CAPABILITIES.md) |
| Configure gates and policy | [Configuration](docs/CONFIG.md) |
| Govern multiple agents | [Multi-agent guide](docs/MULTI-AGENT.md) |
| Connect OpenCode | [OpenCode integration](docs/OPENCODE.md) |
| Run mutation evidence safely | [Mutation playbook](docs/mutation-quality-playbook.md) |
| Understand evidence identity | [Evidence contract](docs/evidence-artifact-contract.md) |
| Review shipped and planned work | [Roadmap](docs/ROADMAP.md) |
| Contribute | [Contributing](CONTRIBUTING.md) |
| Report a vulnerability | [Security](SECURITY.md) |

## Contributing

Contributions are welcome. Fettle favors focused changes, explicit failure
states, clean and violating fixtures, and verification proportional to risk.
Start with [CONTRIBUTING.md](CONTRIBUTING.md) or a
[`good first issue`](https://github.com/MilindGaharwar/fettle/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22good%20first%20issue%22).

## License

Fettle v1.12.1 and later are licensed under the [Apache License 2.0](LICENSE).
Earlier releases retain their published MIT license. See [TRADEMARK.md](TRADEMARK.md)
for permitted use of the Fettle name and logos.
