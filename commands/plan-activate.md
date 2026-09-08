---
name: plan-activate
description: Create an active session plan before editing implementation files
---

# /fettle:plan-activate

Create a session checklist that Fettle's planning gate recognizes.

## Steps

1. Ask the user for a short plan title and the concrete implementation steps.

2. Confirm the proposed checklist with the user. Include at least one step.

3. Create the plan through the canonical CLI, repeating `--item` for each step:
   ```bash
   fettle plan start --title "<TITLE>" --item "<STEP 1>" --item "<STEP 2>"
   ```

4. Verify Fettle recognizes the plan:
   ```bash
   fettle plan status
   ```

5. Confirm activation:
   ```
   Plan activated: <plan name>
    Checklist: <plan path>
   Work packages: <count>
   Implementation file edits are now allowed.
   ```

## Notes
- The newest plan in `.fettle/plans/` is active and survives reboots
- For a heavyweight plan document, validate it separately with `python3 -m fettle.plan_validator <PLAN_PATH>`
- To deactivate, run /fettle:plan-complete
