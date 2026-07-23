---
name: security-review
description: Run security-focused review using ruff S-rules and semgrep OWASP patterns
argument-hint: "[path]"
user-invocable: true
allowed-tools: Bash, Read
---

Run a security review on the target path.

## Procedure

1. **Determine target.** Use `$ARGUMENTS` if provided, otherwise the current working directory.

2. **Run the scanner:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/security_review.py --path TARGET
   ```

3. **Present findings** grouped by severity (CRITICAL/HIGH first).

4. **For each finding**, explain:
   - What the vulnerability is
   - How it could be exploited
   - The recommended fix

5. **Offer to fix** the highest-severity findings automatically.

## Scope

- **Python:** ruff S-rules (full) + semgrep OWASP
- **TypeScript/JavaScript/Go:** semgrep OWASP only
- **Other languages:** limited to semgrep generic rules

This is NOT a comprehensive security audit. It runs available static analysis
tools. For production security assessments, complement with manual review and
dedicated SAST tools.
