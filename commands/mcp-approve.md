---
name: mcp-approve
description: Run the Zero-Trust Validation Protocol to audit and approve an MCP package for installation
argument-hint: "<package>@<version>"
user-invocable: true
allowed-tools: Bash, Read, Write, Grep, Glob, Agent
---

Run the full 5-phase MCP Zero-Trust Validation Protocol to audit a package, then — with human approval — add it to the root-owned allowlist ledger.

## Procedure

1. **Parse arguments.** Extract package name and exact version from $ARGUMENTS (e.g., `@playwright/mcp@0.0.70`). If no version is pinned, STOP and ask for an exact version — unpinned packages are never approved.

2. **Check if already approved.** Read the allowlist ledger and check if this exact package@version is already present. If so, report it and stop.

3. **Phase 1 — Package Provenance & Supply Chain**
   - Run `npm view <package>@<version> --json` to get publisher, download stats, repo link, publish date
   - Verify publisher is the expected organization
   - Cross-reference npm maintainers against known project contributors
   - Check for recent ownership transfers or suspicious maintainer changes
   - Run `npm audit` for known CVEs
   - Present findings to user with PASS/WARN/FAIL for each check

4. **Phase 2 — Source Code Review**
   - Download without installing: `npm pack <package>@<version>`
   - Extract tarball to `/tmp/mcp-audit-<package>/`
   - Review ALL runtime files (not just README)
   - Grep for red flags: `child_process.exec`, `eval(`, `Function(`, `fs.writeFile`, `process.env`, outbound network calls, obfuscated code
   - Map every exposed MCP tool to its blast radius
   - Count total lines of runtime code
   - Present findings to user

5. **Phase 3 — Dependency Tree Audit**
   - Count transitive dependencies
   - Check `npm audit` on full resolved tree
   - Flag dependencies with <100 weekly downloads or recent ownership transfers
   - Present findings to user

6. **Phase 4 — Runtime Isolation Test**
   - Start the MCP server in a subprocess
   - Check ports opened (`ss -tulpn`), filesystem paths touched, DNS lookups
   - Test one benign operation and observe side effects
   - Verify no unexpected phone-home or persistent connections
   - Present findings to user

7. **Phase 5 — Permission Scoping**
   - Recommend MCP tool allowlist for settings.json
   - Recommend network restrictions if supported
   - Recommend `--isolated` mode if available
   - Recommend output directory restrictions
   - Present recommendations to user

8. **Compute tarball SHA256.**
   Run sha256sum on the downloaded tarball.

9. **Write audit report.** Save the full audit report (all 5 phases with findings) to `.fettle/audits/<package>-<version>.md` with date and auditor.

10. **Present summary and ask for human approval.** Show:
    - Overall verdict: APPROVE / REJECT / CONDITIONAL
    - Phase-by-phase summary (PASS/WARN/FAIL)
    - Any conditions or restrictions
    - Ask: "Do you approve adding <package>@<version> to the allowlist?"

11. **If approved**, update the ledger via sudo. Use a Python script that:
    - Reads the current allowlist ledger
    - Adds the new package entry with version, sha256, audit date, auditor, report path, and approved_by_human=true
    - Writes to a temp file then sudo copies it to the ledger path
    - Sets ownership to root:root and permissions to 0644

12. **Confirm** the ledger was updated by reading it back.

## Rules
- NEVER skip any phase. All 5 phases are mandatory.
- NEVER approve without explicit human confirmation in the conversation.
- NEVER install the package during the audit — only `npm pack` (download without install).
- If any phase produces a FAIL, recommend REJECT and explain why.
- Clean up audit artifacts from /tmp/ after completion.
