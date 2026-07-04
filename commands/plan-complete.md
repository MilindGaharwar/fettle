---
name: plan-complete
description: Deactivate the current plan after all work packages are complete
---

# /fettle:plan-complete

Deactivate the current development plan.

## Steps

1. Check if .fettle/state/active-plan.json exists. If not, report No active plan.

2. Read and display the active plan info (path, activation time).

3. Ask the user to confirm completion.

4. On confirmation, delete the marker and tracking files via Bash:
   rm .fettle/state/active-plan.json
   rm -f /tmp/fettle-edits.jsonl

5. Confirm: Plan completed and deactivated. Implementation file edits are now gated again.
