---
name: plan-activate
description: Activate a development plan -- required before editing implementation files
---

# /fettle:plan-activate

Activate a development plan to unlock implementation file edits.

## Steps

1. Ask the user which plan file to activate. If they provide a path, use it. If not, search for `.md` files in `docs/plans/` and present the list.

2. Read the plan file completely.

3. Run the structural validator:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plan_validator.py <PLAN_PATH>
   ```
   If it fails, report every error verbatim and do NOT activate. The errors name the exact WP and missing method type. Fix the plan first.

4. Check for adversarial review:
   - Look for a `## Council Review` or `## Adversarial Review` section in the plan, OR
   - Check if a council report file is referenced in the plan header (e.g., `council_report: /path/to/report.md`)
   - If neither exists: **WARN** the user that no adversarial review is on record. For plans
     with implementation tasks, recommend running:
     ```bash
     python3 /tmp/fettle/tools/council.py --role adversarial < <BRIEF_FILE>
     ```
     before activation. Strongly recommended but does not hard-block (council rate limits are real).

5. If validation passes, write the marker file:
   ```bash
   echo '{"plan": "<PLAN_PATH>", "approved": true, "ts": <UNIX_TIMESTAMP>}' > .fettle/state/active-plan.json
   ```

6. Confirm activation:
   ```
   Plan activated: <plan name>
   Path: <plan path>
   Work packages: <count>
   Implementation file edits are now allowed.
   ```

## Validation rules enforced (plan_validator.py)

Every WP containing at least one implementation method task
(TDD, BUILD, FIX, REFACTOR, CODE, INTEGRATION) must also contain:

| Required method | What it checks |
|-----------------|----------------|
| TDD | Unit tests written before implementation |
| INTEGRATION | End-to-end test against the running system |
| REGRESSION | Named failure scenario (must cite incident/bug -- generic "regression test" is blocked) |
| LIVE | Exact command + observable outcome (must include an actual command -- "verify it works" is blocked) |

WPs containing only INSPECT, VERIFY, REVIEW, or PROPERTY tasks are exempt.

## Notes
- Only one plan can be active at a time -- activating a new one replaces the old
- The marker is persistent at .fettle/state/active-plan.json (survives reboots)
- To deactivate, run /fettle:plan-complete
- Validator callable standalone: python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plan_validator.py plan.md
