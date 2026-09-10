# Security Policy

## Supported versions

Security fixes target the latest released version and the `main` branch. Older
releases may not receive patches.

## Report a vulnerability

If GitHub shows **Privately report a security vulnerability** on the repository's
Security tab, use that channel. If it is unavailable, open a minimal public
issue requesting private contact from the maintainer, without vulnerability
details.

In the private report, include the affected version or commit, reproduction
steps, impact, and any suggested mitigation. Never put live credentials,
private source code, exploit details, or sensitive agent transcripts in a
public issue.

You should receive an acknowledgement within 7 days. Please allow time to
validate and release a fix before public disclosure.

## Security boundaries

Fettle is application-level quality governance, not an operating-system
sandbox. Shell mediation, policy capsules, worktrees, and agent hooks are
defense-in-depth controls; use least-privilege credentials, isolated runners,
repository protections, and independent CI for hard boundaries.

Fettle's strict runtime secret boundary can block protected file reads,
environment dumps, and recognized nested shell reads before execution on Claude
Code, Codex CLI, Gemini CLI, and OpenCode. Scanner failures on this boundary fail
closed. Pre-model tool-output protection is transport-dependent: Claude Code can
receive replacement output and Gemini can withhold affected output, while Codex
and OpenCode output filtering is unsupported. Detection is not exhaustive and
does not replace secret managers, host isolation, or credential scoping.

Host registration is not proof of trust, execution, or verification. Use
`fettle doctor` for the separate local states and exercise the integration before
depending on it.

The default installation includes Fettle's Python analyzers and execution
runtimes. Agent hosts, browser binaries, Git, non-Python language toolchains,
and external services retain their own supply chains and permissions. Pin and
review the resolved Python dependency graph according to your threat model; use
`fettle doctor --verify-hashes` to inspect installed Python tool records.

Official tagged releases are published through PyPI Trusted Publishing. The
GitHub release includes distributions and a CycloneDX SBOM; GitHub build
provenance can be checked with `gh attestation verify`.
