---
name: worklog
description: Create or view daily worklog entries
argument-hint: "[view|create|today]"
user-invocable: true
allowed-tools: Bash, Read, Write
---

Manage the daily worklog at `.fettle/worklog/YYYY-MM-DD.md`.

## Procedure

1. **Parse arguments.** Default action is "today" (show or create today's entry).
   - `view` — show last 7 days of completed items
   - `create` — create today's template if missing
   - `today` — open today's entry (create if needed)

2. **For "view":** Run:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/worklog.py view
   ```
   Present the recent entries.

3. **For "create" or "today":**
   - Check if `.fettle/worklog/YYYY-MM-DD.md` exists
   - If not, create the template
   - Read and present the file to the user
   - Offer to help fill in the "Completed" section from this session's work

4. **Auto-populate from session context:**
   - Review files modified this session
   - Review commits made
   - Review decisions discussed
   - Suggest entries for the "Completed" and "Decisions" sections

## Template

```markdown
# Worklog: YYYY-MM-DD

## Completed
- [what shipped or was accomplished]

## Decisions
- [key choices made and why]

## Blockers / Risks
- None (or describe blockers)

## Next Actions
- [what carries forward to tomorrow]
```

## Notes

- The worklog gate (Stop hook) advisories if no entry exists for today
- Enable enforcement: `[gates.worklog] enabled = true` in `.fettle.toml`
- Worklogs are gitignored by default (in `.fettle/`)
- To track in git: add `.fettle/worklog/` to your repo
