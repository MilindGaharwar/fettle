---
name: mcp-revoke
description: Revoke a previously approved MCP package from the allowlist ledger
argument-hint: "<package>"
user-invocable: true
allowed-tools: Bash, Read
---

Remove a package from the root-owned allowlist ledger.

## Procedure

1. **Parse arguments.** Extract package name from $ARGUMENTS (e.g., `@playwright/mcp`).

2. **Check current ledger.** Read the allowlist ledger and verify the package exists. If not found, report and stop.

3. **Show current entry.** Display the package's version, audit date, auditor, and report path.

4. **Confirm with human.** Ask: "Are you sure you want to revoke <package> from the allowlist? This will block all future installations and executions."

5. **If confirmed**, remove from ledger via sudo. Use a Python script that:
   - Reads the current allowlist ledger
   - Removes the package entry from the packages dict
   - Writes to a temp file then sudo copies it to the ledger path
   - Sets ownership to root:root and permissions to 0644

6. **Confirm** the ledger was updated by reading it back and verifying the package is no longer listed.

7. **Report** what was removed and remind the user that:
   - Any installed instance of this package will still exist on disk
   - Future attempts to install or execute it will be blocked by all 3 layers
   - To fully remove it, also uninstall the package manually

## Rules
- NEVER revoke without explicit human confirmation in the conversation.
- Always show what is being removed before asking for confirmation.
