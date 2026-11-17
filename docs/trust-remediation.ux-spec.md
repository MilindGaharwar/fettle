# UX Spec: Trust Remediation

Status: proposed acceptance contract for packages TR-1 to TR-4 of the
[trust remediation implementation plan](trust-remediation-implementation-plan.md).
Packages TR-5 to TR-9 extend this contract before they start.

## Job To Be Done

When I let an AI coding agent work unattended with Fettle gates enabled, I want
a gate that I configured to fire on the path that is actually installed, and I
want "tests passed" to mean that tests ran, so that I can act on a green result
without re-checking the agent's work myself.

## Personas

- Unattended-agent user: enabled gates once and expects them to hold whichever
  directory, tool or host the agent uses.
- Governed agent: needs every block to say what was blocked, why, and the one
  action that resolves it, in plain text it can act on.
- Repository owner: needs to know when policy changed during a session and
  which layer decided each setting.
- New user: runs `fettle demo`, `fettle init --dry-run`, `fettle doctor` and
  `fettle explain` first, and must not meet a crash, a hidden write, or a
  block on ordinary work.
- Accessible terminal user: needs plain text status; no meaning depends on
  colour or symbols.

## Journey

| Phase | User or agent action | Sees | Recovery |
|---|---|---|---|
| Ordinary work | Agent edits code, runs commands, commits | No prompt and no block for safe work, including commands that merely contain the word `env` | None |
| Edit feedback | Agent edits a file with any supported edit tool, from any directory in the repository | The same findings and blocks as an edit made from the repository root with the basic edit tool | Fix the finding |
| Policy attempt | Agent tries to change `.fettle.toml`, Fettle's evidence or state, or host hook settings | In enforce mode, a block naming the file; otherwise an advisory | Leave policy to the repository owner |
| Finish | Agent stops after editing code with the verify gate enabled | A block until a fresh, passing verification exists for the current source | `fettle verify` |
| Verification | `fettle verify` runs | Green only when at least one test executed and none failed; otherwise red or unknown with the counts | Fix tests, or declare a report file |
| Diagnosis | User runs `fettle doctor`, `fettle explain`, `fettle brief` | State that matches what the gates would decide | Follow the first listed action |
| First run | User runs `fettle demo` and `fettle init --dry-run` | A demo produced by the real engine; a preview that writes nothing | None |

Common safe work adds no interaction. A blocked operation needs one recovery
action.

## States

- First-time empty: no session-start record exists yet; the first hook event
  creates it silently.
- Cleared empty: the edit record is missing or deleted; the Stop gate still
  decides from the source snapshot and does not allow by default.
- Filtered empty: a session that changed no code files is allowed to stop with
  no message.
- Loading brief: hook decisions complete within the existing event budgets.
- Loading long: a required check that cannot finish in time blocks, as today.
- Populated: a block or advisory names the file, the reason and one action.
- Error recoverable: unreadable hook input or an unreadable edit record is
  "unknown", blocks where a required gate depends on it, and names
  `fettle doctor`.
- Error fatal: an unloadable policy blocks every event except an edit whose
  only target is that policy file.
- Offline: every decision in TR-1 to TR-4 is local; remote policy that is
  declared but not cached blocks with `fettle policy sync`.
- Stale: a verification stamp for a different source snapshot, session or
  commit is reported as stale by the gates, `fettle brief` and
  `fettle assurance` alike.

## Accessibility And Information

- Every block states, in this order: what was blocked, why, and one recovery
  action. No block message explains how to disable the gate that produced it.
- Existing message prefixes are kept: `Verify gate:`,
  `Config modification blocked:`, `Blocked secret access:`,
  `Required check '<name>' ...`.
- New messages use these forms:
  - `Fettle policy modification blocked: <file>. Policy is changed by the repository owner outside the agent session.`
  - `Verify gate: policy changed during this session (<n> setting(s)). Run: fettle config --explain`
  - `verify: RED — no tests executed (collected <n>, skipped <n>)`
  - `verify: UNKNOWN — the test command exited 0 but no test count is available. Set [gates.verify] report to a JUnit XML path.`
  - `Org policy is declared but not available locally. Run: fettle policy sync`
- Secret values, matching lines and raw exceptions never appear in
  model-visible output.
- Exit codes are unchanged: a hook block exits 2 and an allow exits 0;
  `fettle verify` exits 0 when green and 1 when red; a tool error exits 2.
  The new "unknown" verification result exits 1.
- `fettle config --explain` shows, for each setting a floor or protection
  rule overrode, the layer that won and the value that was ignored.
- `fettle doctor` reports, per host, whether a hook that fails to start blocks
  or continues, as recorded in the host capability file. A host whose
  behaviour is not determined is shown as "not determined", never as blocking.

## BDD Scenarios

### Scenario: Stop gate fires on the installed path (TR-1)

- Given the verify gate is enabled in enforce mode and hooks are registered as
  `fettle init` registers them
- When the agent edits a code file and then stops without running
  `fettle verify`
- Then the Stop event is blocked with the `Verify gate:` message and
  `Run: fettle verify`
- And the result is the same in clone mode and in bridge mode

### Scenario: Deleting the edit record does not release the gate (TR-1)

- Given the agent edited a code file in this session
- When the session's edit record is deleted or emptied and the agent stops
- Then the Stop event is still blocked, because the source snapshot differs
  from the session-start snapshot

### Scenario: Subdirectory work keeps repository policy (TR-1)

- Given a repository whose root policy puts config protection in enforce mode
- When the agent, working from a subdirectory, edits a protected file
- Then the edit is blocked exactly as it would be from the repository root

### Scenario: Every edit tool is governed (TR-1)

- Given a protected file and config protection in enforce mode
- When the agent uses a notebook edit, a multi-file patch, or a host-specific
  multi-edit tool that touches the protected file
- Then the event is blocked and the message names the protected file
- And a multi-file event is blocked if any one target is protected

### Scenario: The repository cannot replace the hook program (TR-1)

- Given the repository contains a directory named `fettle` with its own
  `dispatcher.py`, or a file named like a standard-library module
- When any hook event runs
- Then the decision is the one the installed Fettle makes

### Scenario: Unreadable input is not an allow (TR-1)

- Given a required gate applies to the event
- When the hook input cannot be parsed, or the edit record contains a line
  that cannot be parsed
- Then the outcome is "unknown", the event is blocked, and the message names
  `fettle doctor`

### Scenario: An enforce-mode gate that crashes blocks (TR-1)

- Given any gate is configured in enforce mode
- When that gate raises an error while running
- Then the event is blocked with the `Required check '<name>' failed closed`
  message

### Scenario: Policy cannot be edited from inside the session (TR-2)

- Given config protection is in enforce mode
- When the agent edits or creates `.fettle.toml`, a file under `.fettle/`, or a
  host hook settings file, by an edit tool or by a recognised shell write
- Then the event is blocked with the `Fettle policy modification blocked:`
  message
- And in advisory mode the same event is allowed with an advisory

### Scenario: A fail-closed check cannot be disabled by repository config (TR-2)

- Given the repository policy lists a fail-closed check under
  `[dispatcher] disabled_checks`
- When a hook event runs
- Then the check still runs
- And `fettle config --explain` reports the ignored entry and the reason

### Scenario: Organisation policy is a floor (TR-2)

- Given an organisation pack sets a gate to enforce mode and the repository
  sets it to advisory
- When a hook event runs
- Then the gate runs in enforce mode
- And `fettle config --explain` names the organisation layer as the winner

### Scenario: Declared remote policy that is unavailable blocks (TR-2)

- Given the repository declares `[extends]` and the policy is not cached or
  its cache fails verification
- When a hook event runs
- Then the event is blocked with the recovery action `fettle policy sync`

### Scenario: A policy change during the session is visible (TR-2)

- Given the effective policy at Stop differs from the policy at session start
- When the agent stops
- Then in enforce mode the Stop event is blocked with the
  `policy changed during this session` message, and otherwise an advisory is
  shown
- And the Assurance Record's policy integrity dimension is not PASS

### Scenario: A broken policy file is repaired by the owner (TR-2)

- Given the repository policy file cannot be loaded
- When the agent attempts to edit that file
- Then the edit is blocked with "fix `.fettle.toml` in your editor, then run
  `fettle doctor`", and every event stays blocked until the owner repairs the
  file outside the agent session
- And unavailable remote policy instead keeps the existing recovery action
  `fettle policy sync`

### Scenario: An edited stamp cannot pass (TR-3)

- Given the last verification failed
- When the stamp's `ok` field is changed to true and the agent stops
- Then the Stop event is blocked, because the gate reads the validated
  artifact's result

### Scenario: Zero executed tests is not a pass (TR-3)

- Given the test command exits 0 but every test was skipped or none ran
- When `fettle verify` runs
- Then it prints the `no tests executed` message with the counts, exits 1,
  and the Stop gate blocks

### Scenario: A command with no test count is unknown (TR-3)

- Given a custom test command that produces no test report
- When `fettle verify` runs and the command exits 0
- Then the result is "unknown" with the message naming `[gates.verify] report`
- And for one minor release the Stop gate reports this without blocking

### Scenario: CI evidence for another commit does not count (TR-3)

- Given a retained CI stamp for an earlier commit
- When `fettle assurance` assesses the current commit
- Then the CI dimension is UNKNOWN and says the evidence is for a different
  commit

### Scenario: Status views agree with the gates (TR-3)

- Given the source changed after the last passing verification
- When the user runs `fettle brief`
- Then verification is shown as stale, not green

### Scenario: Ordinary commands are not blocked as secret access (TR-4)

- Given no credential is involved
- When the agent runs a commit whose message contains the word `env`, a
  command that starts with `/usr/bin/env python3`, a command containing an
  unbalanced apostrophe inside a here-document, or reads a file that does not
  exist
- Then the secret boundary allows the event

### Scenario: A dry run writes nothing (TR-4)

- Given any repository state
- When the user runs `fettle init` with a profile and `--dry-run`, with or
  without `--force`
- Then no file in the repository or the home directory changes, and the
  output lists what would be written

### Scenario: Explain works after a failed verification (TR-4)

- Given the most recent recorded decision is a failed verification
- When the user runs `fettle explain`
- Then it describes the failed verification and its recovery action, and
  does not raise an error

### Scenario: The demo runs the real engine (TR-4)

- Given a fresh install with no network
- When the user runs `fettle demo`
- Then the detection step is produced by Fettle's scan engine, and the output
  names the engine that ran

### Scenario: A missing scanner does not hide other findings (TR-4)

- Given Semgrep is not installed and Ruff reports findings
- When the user runs `fettle check`
- Then the Ruff findings are printed, followed by the scanner error, and the
  exit code is 2

### Scenario: Doctor does not say healthy when a required capability is missing (TR-4)

- Given a required tool is missing or the policy file cannot be parsed
- When the user runs `fettle doctor`
- Then the summary says "degraded" and lists the first action to take

## Success Criteria

- Every scenario above has a test that drives the hook command as registered,
  in both launch modes where the scenario is on the hook path.
- For each scenario that describes a current defect, the test fails on the
  merge base and passes on the head.
- Ordinary safe work produces no new prompt, block or advisory.
- Hook event budgets and measured latency do not regress.
- No message tells the reader how to disable the gate that produced it.
- No scenario is satisfied by a skipped or expected-failure test.
