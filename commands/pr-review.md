---
name: pr-review
description: Generate a PR review report aggregating quality scan, coverage, complexity, and breaking changes
argument-hint: ""
user-invocable: true
allowed-tools: Bash, Read
---

Generate a structured PR review by orchestrating existing Fettle checks.

## Procedure

1. **Run the orchestrator:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pr_review.py --root .
   ```

2. **Present the report** with sections: changes, quality scan, coverage, breaking changes, checklist.

3. **Highlight any issues** that need attention before merging.

4. **Offer to fix** quality scan errors if present.
