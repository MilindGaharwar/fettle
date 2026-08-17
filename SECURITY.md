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

The default Python installation includes Fettle's analyzers and Python-side
automation dependencies so users receive one coherent, inspectable environment.
Agent hosts, browser binaries, Git, non-Python language toolchains, and external
services retain their own supply chains and permissions. Pin and review the
complete dependency graph according to your threat model; use
`fettle doctor --verify-hashes` to inspect installed Python tool records.

Official tagged releases are published through PyPI Trusted Publishing. The
GitHub release includes distributions and a CycloneDX SBOM; GitHub build
provenance can be checked with `gh attestation verify`.
