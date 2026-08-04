<p align="center">
  <img src="https://raw.githubusercontent.com/MilindGaharwar/fettle/main/assets/logo.svg" alt="fettle" width="110">
</p>

<h1 align="center">Fettle for VS Code</h1>

<p align="center"><b>The quality harness for AI-generated code — live in your editor.</b></p>

Surfaces Fettle's current Python LSP findings as native VS Code diagnostics,
using the workspace's `.fettle.toml`. Agent hooks and editor diagnostics share
configuration but do not yet run an identical set of gates.

→ Main project: [github.com/MilindGaharwar/fettle](https://github.com/MilindGaharwar/fettle)

## Features

- **Live diagnostics** on Python files
- **Ruff and Fettle's bundled Semgrep findings** through the LSP path
- **Auto-reload** when `.fettle.toml` changes
- **Commands:** restart server, run full scan, view report

## Requirements

- Python >= 3.11
- Fettle installed at `~/.claude/plugins/fettle` (or set `fettle.pluginPath`)
- `ruff` and optionally `semgrep` on PATH or at `~/.local/bin`

## Installation

### From source (development)

```bash
cd ~/.claude/plugins/fettle/integrations/vscode
npm install
npm run compile
```

Then in VS Code: `Ctrl+Shift+P` → "Developer: Install Extension from Location..." → select this directory.

### From VSIX (distribution)

```bash
cd ~/.claude/plugins/fettle/integrations/vscode
npm install
npm run vscode:prepublish
npx @vscode/vsce package
code --install-extension fettle-0.9.0.vsix
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `fettle.enable` | `true` | Enable/disable Fettle |
| `fettle.pluginPath` | auto-detected | Path to Fettle plugin root |
| `fettle.pythonPath` | auto-detected | Python >= 3.11 interpreter |

## Commands

- **Fettle: Restart Language Server** — restart after config changes
- **Fettle: Run Quality Scan** — full project scan in terminal
- **Fettle: Show Effectiveness Report** — view pass/violation rates

## How it works

The extension launches Fettle's built-in LSP server for Python diagnostics.
Hook-only process gates, shell guards, and Stop-time checks are not editor
diagnostics.

Project config is read from `.fettle.toml` at the workspace root.
