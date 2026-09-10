# Capability Matrix

Fettle describes support by surface. A broad label such as "polyglot" or
"agent-compatible" is not enough to make an operational decision.

| Area | Current scope | Important boundary |
|---|---|---|
| Agent lifecycle | Claude Code, Codex CLI, Gemini CLI, and OpenCode transports are implemented and contract-tested | Local installation, registration, trust, execution, verification, and enforcement differ; `fettle doctor` does not infer verification from registration |
| Runtime secret boundary | Strict pre-tool blocking on all four hosts; output replacement on Claude Code and withholding on Gemini | Pre-model output filtering is unsupported on Codex and OpenCode; this is defense in depth, not a sandbox |
| Post-edit adapters | Python, JavaScript/TypeScript, Go, Rust | Native tools must be installed for their workspace |
| `fettle check` | Python Ruff plus bundled language-neutral Semgrep rules | Not the complete polyglot adapter surface |
| `fettle verify` | Affected discovered workspaces with configured test commands | Impacted-test narrowing is Python-specific; local verification does not replace CI |
| LSP / VS Code | Python diagnostics from Ruff and bundled Semgrep rules | Hook-only process gates are not editor diagnostics |
| Evidence assurance | Canonical nine-dimension record bound to source, policy, scope, producer, and occurrence | A missing or invalid producer artifact remains non-pass |
| Assurance baseline | Reproducible collect, human review, and verified summary for prior-v1 versus hardened decisions | Graduation requires 20 distinct accepted real changes and explicit operator approval |
| Mutation evidence | Python preflight, changed/full execution, replay, retained schema-v2 reports, and accepted baseline comparison | Python only; pinned `mutmut==2.5.1`; full runs are held-out verification |
| Delegation | Plans, worktrees, claims, topology, spawn, capsules, role authority, completion, and lineage reports | Defense in depth, not process or credential isolation |
| Living specifications | Markdown spec lint, inventory, scenario-to-test coverage, and canonical drift evidence | A declared link is not verified until its execution evidence passes |
| User acceptance | CLI, API, web, and library sessions; manual walkthroughs; operator attestation; seeded benchmark | Automation requires consent; unavailable observation remains visible |
| Change intelligence | Deterministic source snapshots and advisory graph `status`, `impact`, `shadow`, and explicit contextual ranking | Contextual promotion failed required-recall, sample-size, and precision-evidence gates; graph output does not authorize |
| State consistency | Contract template, validation, listing, and execution | Comparator/model support and reach are explicit in each contract |
| Governance ledger | Hash-chained records with commit and CI-artifact anchoring | Unknown anchor coverage remains unknown |
| External integrations | SonarQube, Black Duck/Polaris, Pact | Disabled by default; credentials stay in environment-managed integrations |
| Guided workflows | 17 packaged workflows across supported agents | Workflows guide reasoning; CLI commands remain deterministic automation |
| Policy operations | Layered local policy, digest-pinned central policy, tighten-only delegation capsules, explainable provenance | Effective behavior depends on the host's enforce/notify capability |

## Result Semantics

Fettle preserves `pass`, `violation`, `tool_error`, and `unknown`, plus explicit
surface-specific non-applicable outcomes. Missing, stale, malformed, conflicting,
or incomplete evidence does not become clean.

## Installation Boundary

`pipx install finefettle` installs all Python-backed capabilities and bundled
runtime resources. Git remains required. Browser binaries, agent CLIs,
JavaScript/TypeScript, Go, and Rust toolchains, and external services remain in
their native distribution channels. Run `fettle doctor` for the effective
capability inventory on a machine.

See [Configuration](CONFIG.md), [Installation](INSTALLATION.md), and the
[task-oriented documentation index](README.md).
