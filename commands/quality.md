---
name: quality
description: Run full Fettle quality scan on the current project
argument-hint: "[--baseline FILE]"
user-invocable: true
allowed-tools: Bash, Read, Grep, Glob
---

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/quality_scan.py --root $PWD` (pass any additional arguments from $ARGUMENTS).

Present the results to the user, grouped by severity. If there are errors, suggest specific fixes based on the rule messages. If a baseline is available, highlight only new findings.

After presenting results, offer to:
1. Fix the errors automatically (if any)
2. Update the baseline with `--update-baseline`
3. Run a cross-review with `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cross_review.py`
