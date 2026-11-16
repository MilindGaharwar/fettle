# UAT Report: TR-1 Shipped Hook Path

Date: 2026-11-14

## Review correction — 2026-11-17

Review of PR #80 found T-1 through T-5, fixed on the TR-2 pull-request branch:
committed and branch-switched code is compared with session-start `HEAD`;
multi-target checks evaluate every target and retain the most severe result;
required-check keys match the enforcing configuration actually read; patch move
destinations are protected; and malformed native pre-tool input is recognized
across supported host vocabularies.

For E11, the report previously covered required checks whose registry wiring
was already correct and direct blocks from integrity checks. It did not cover
exceptions in all five reviewed checks under each check's real configuration.
The correction covers enforce/advisory exception routing for
`boundary_rules`, `worklog`, and `post_bash_doc_check`, and records that
`runtime_output_guard` and `provenance_gate` have no enforcing mode.

For E6, the report previously covered truncated Claude `PreToolUse`, malformed
journal lines, and deleted or emptied journal files. It did not cover non-object
JSON naming `PreToolUse` or truncated Gemini `BeforeTool`. Those cases now block
in both launch modes; malformed input naming no pre-tool event remains a traced
allow.

## User flow

A supported coding agent invokes the hook command installed by Fettle. The
command normalizes the host event, finds repository policy from the invocation
directory, applies every relevant check to every target, records edits once,
and returns a host-compatible allow or block decision.

## Scenarios tested

| Scenario | Launch modes | Result |
|---|---|---|
| Edit code, then stop without `fettle verify` | Plugin and installed bridge | Pass: Stop blocks with recovery guidance |
| Delete or empty the edit journal after an edit | Plugin and installed bridge | Pass: source-state evidence still requires verification |
| Supply a malformed journal | Plugin and installed bridge | Pass: malformed evidence remains unknown and blocks in enforce mode |
| Invoke a protected edit from a repository subdirectory | Plugin and installed bridge | Pass: repository-root policy applies |
| Use NotebookEdit, apply_patch, or multiedit aliases | Plugin and installed bridge | Pass: canonical edit policy applies |
| Supply multiple targets where one is protected | Plugin and installed bridge | Pass: target fan-out blocks the event |
| Add a repository-local `fettle` package | Plugin and installed bridge | Pass: isolated launch does not import it |
| Supply malformed PreToolUse JSON | Plugin and installed bridge | Pass: malformed authorizing input is not allowed |
| Remove every usable Python interpreter | Plugin launcher | Pass: readable failure and exit 1 |
| Invoke a legacy check script payload | Legacy script command | Pass: the public wrapper reaches canonical `run_check` behavior |

## Automated evidence

- Installed-path UAT: 145 passed in 24.93 seconds.
- Entry-point compatibility: 280 passed in 66.48 seconds.
- Dispatcher reader/core compatibility: 241 passed in 59.13 seconds.
- Full unexcluded regression: 5,157 passed, 23 skipped in 592.60 seconds.

## States

- Success: safe tool events continue with host-compatible output.
- Blocked: policy violations and missing verification return a reason and next
  action.
- Empty: sessions without applicable changes continue.
- Malformed: malformed PreToolUse input and malformed journals remain non-pass.
- Missing dependency: the launcher reports the missing interpreter and exits 1.
- Recovery: visible block and error states include a repair or verification
  command.
- Offline: all TR-1 decisions use local policy and local evidence.
- Concurrent/multi-target: every extracted target is evaluated; one blocking
  target blocks the event.

## Accessibility

- Text and exit-code operation: Pass.
- Keyboard-only operation: Pass; commands are non-interactive.
- Color independence: Pass; decisions and recovery steps are words and exit
  codes, not color alone.
- Browser/axe checks: Not applicable to this CLI and agent-hook change.

## Mutation observation

The bounded narrow replay completed for all three new production modules in
3,023.712 seconds. It reported 114 killed and 144 surviving mutants, with zero
timeouts, suspicious, untested, or skipped outcomes. The survivors are retained
as test-strength debt; they were not hidden by exclusions, threshold changes,
skips, or mutation pragmas.

## Decision

SHIP for the TR-1 behavior contract. The implementation and user flows pass.
The narrow mutation replay is complete but survivor-bearing and must not be
described as a mutation pass.
