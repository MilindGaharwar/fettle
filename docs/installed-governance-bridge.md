# Installed Governance Bridge Contract

Status: implementation contract

## Outcome

An installed `finefettle` wheel can register supported agent hosts without a
Fettle source checkout. Host events invoke the exact Python environment that ran
`fettle init`; core policy and dispatcher code remain inside the installed
package.

## Authority Boundary

- The bridge contains transport configuration only. It carries no policy and
  grants no authority beyond the user's existing host configuration.
- The Python dispatcher remains the single normalized gate implementation.
- Hooks remain session-continuity feedback. CI remains independently
  authoritative.
- Initialization preserves unrelated host settings and never repairs malformed
  settings by overwriting them.

## Runtime Matrix

| Host | Events | Transport | Timeout unit | Installed command |
|---|---|---|---|---|
| Claude Code | PreToolUse, PostToolUse, Stop | Generated `hooks/hooks.json` | seconds | absolute interpreter + `-m fettle.dispatcher` |
| Claude Code | SubagentStart | Bundled JavaScript transport | seconds | Node script in bridge |
| Codex CLI | PreToolUse, PostToolUse, Stop | `~/.codex/hooks.json` | seconds | absolute interpreter + `-m fettle.dispatcher` |
| Gemini CLI | BeforeTool, AfterTool, AfterAgent | `~/.gemini/settings.json` | milliseconds | absolute interpreter + `-m fettle.dispatcher` |
| OpenCode | tool before/after, session idle | Generated TypeScript plugin | host/plugin-defined | absolute interpreter + `-m fettle.dispatcher` |

The absolute interpreter path is serialized as an argument, never concatenated
from repository or event input. Paths embedded in shell command fields are
quoted with the platform's standard command serializer. OpenCode uses Node's
`spawn` with an argv array and no shell.

## Location And Manifest

The bridge root follows operating-system user-data conventions:

- macOS: `~/Library/Application Support/fettle/bridge`
- Windows: `%LOCALAPPDATA%/fettle/bridge`
- other platforms: `$XDG_DATA_HOME/fettle/bridge` or
  `~/.local/share/fettle/bridge`

Files are generated in a sibling temporary directory, assigned user-only write
permissions where supported, and atomically published. On Windows, the bridge
inherits the user's profile ACL because POSIX mode bits do not enforce a DACL.
Windows command serialization and junction detection are covered by portable
contract tests. Blocking CI also publishes and repairs the bridge on a native
`windows-latest` runner from a Python path containing spaces.
`manifest.json` records:

- schema version;
- Fettle package version;
- absolute Python executable, preserving virtual-environment identity;
- SHA-256 digest for every bridge-owned file.

Publication never follows an existing bridge symlink or a junction detectable
by the running Python version. A non-directory bridge, foreign file, malformed
manifest, or digest conflict is an actionable non-success. Cleanup may remove
only a verified manifest-owned bridge.

## Lifecycle

| State | Result |
|---|---|
| First install | Preview all files/settings in dry-run; publish bridge before host references |
| Same-version rerun | Validate digests and report `ok`; no writes |
| Upgrade | Publish a complete replacement atomically, then retain stable host paths |
| Interrupted publication | Existing bridge remains; temporary directory is never authoritative |
| Missing/tampered file | Doctor reports the exact file and `run: fettle init` |
| Executable removed | Doctor reports stale environment and requests reinstall/re-init |
| Malformed host config | Preserve it and report manual action |
| Uninstall | Host may retain a stale reference; doctor cannot run, so package docs provide manual removal |

Downgrades use the same explicit `fettle init` action and replace only a valid,
manifest-owned bridge. They never rewrite foreign content.

## Windows Verification And Recovery

Run these commands in PowerShell from a Git repository:

```powershell
pipx install finefettle
fettle init --dry-run --json
fettle init --json
fettle doctor --json
```

The dry run must report the bridge as `created` without creating
`$env:LOCALAPPDATA\fettle\bridge`. Initialization then publishes the bridge,
and doctor reports its bridge check with `"ok": true` (`supported-installed`).

If doctor reports `stale`, preserve the reported path and run `fettle init`
again. Fettle replaces only a manifest-owned bridge and doctor must then return
`"ok": true`. If initialization reports `conflict`, do not delete or overwrite
the path: inspect the foreign or malformed content and move it aside manually
before retrying. A missing `fettle` executable requires reinstalling with
`pipx install --force finefettle`, followed by `fettle init` and `fettle doctor`.

## Capability States

- `supported-installed`: installed bridge, host registration, transport contract,
  public artifact canary, and fresh real-host evidence validate.
- `contract-tested`: installed bridge, registration, transport contract, and
  public artifact canary validate, but real-host evidence is blocked or absent.
- `clone-supported`: checkout transport validates.
- `manual-action`: a documented host toggle or restart remains.
- `conflict`: foreign or malformed state prevents safe registration.
- `stale`: bridge version, executable, or digest no longer matches.
- `unavailable`: host is not detected.

Aggregate output cannot convert `conflict`, `stale`, or `manual-action` into a
clean host result.

The reviewed authority for release claims is
`fettle/host-capabilities.json`. `supported-installed` currently applies to
Claude Code, Codex CLI, and OpenCode. Gemini CLI remains `contract-tested`
because its live OAuth path is blocked upstream by `UNSUPPORTED_CLIENT`.

## Threat Review

| Threat | Control |
|---|---|
| Shell injection through executable path | Standard quoting; OpenCode argv arrays; no event data in commands |
| Symlink replacement | Refuse symlink bridge roots and publish by atomic directory replacement |
| Writable parent substitution | User-owned data root; bridge files are not treated as elevated authority |
| Malicious host JSON | Strict object/list shape checks; preserve and stop on malformed data |
| Executable substitution | Manifest binds normalized executable; doctor verifies it exists |
| Partial update | Build complete temporary tree and publish manifest with the tree |
| Stale/downgraded transport | Package version and per-file digests are validated |
| Broad deletion | Cleanup restricted to verified manifest-owned paths |
| Secret capture | Bridge stores no credentials, prompts, source, event bodies, or output |

## Graduation Evidence

A host is documented as wheel-supported only after:

1. isolated-home contract tests cover clean, existing, malformed, dry-run, and
   idempotent states;
2. wheel and sdist smoke tests validate bridge files and one normalized event;
3. the host-specific transport test validates event names and timeout units;
4. a real host session is observed where available; unavailable external host
   access remains a visible UAT limitation, not inferred success.
