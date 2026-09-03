# Install Fettle

Fettle ships as one Python package named `finefettle`. The installed command is
`fettle`.

## Recommended

Requirements: Python 3.11 or newer and Git.

```bash
pipx install finefettle
fettle demo
fettle doctor
```

`pipx install finefettle` installs the complete Python-backed toolkit: Fettle,
Ruff, Semgrep, pytest, mutmut, PyYAML, and the Playwright Python library. It also
includes Fettle's rules, workflows, schemas, demo fixture, and agent bridges.
No capability extra is required for normal use.

With uv, use:

```bash
uv tool install finefettle
```

## Activate A Repository

```bash
cd your-project
fettle init --dry-run
fettle init --profile solo
fettle doctor
```

Use `team` for shared planning and delegation controls, or `enterprise` for
strict defaults and compliance evidence. Omit `--profile` for the guided setup.

## External Runtimes

A Python installer cannot safely bundle or configure every system Fettle can
govern. Install these only for the surfaces you use:

| Runtime | Needed for |
|---|---|
| Git | All repository operations |
| `playwright install` browser binaries | Browser-driven UAT |
| Claude Code, Codex CLI, Gemini CLI, or OpenCode | Live agent integration |
| Node.js/TypeScript, Go, or Rust toolchains | Native checks in those workspaces |
| SonarQube, Black Duck/Polaris, or Pact services | Optional enterprise evidence |

`fettle doctor` reports available, missing, and degraded capabilities instead of
silently treating unavailable tooling as a pass.

## Upgrade Or Remove

```bash
pipx upgrade finefettle
fettle init                 # refresh installed bridges after an upgrade

pipx uninstall finefettle
```

Capability extras from older releases remain accepted for compatibility.
`finefettle[all]` additionally installs contributor tooling and is intended for
source development, not ordinary use.
