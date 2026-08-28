# UX Spec: Offline Demo

## Job To Be Done

When I am evaluating Fettle before adopting it, I want one command that proves
the detect-repair-verify loop without project setup or credentials, so I can decide
whether the product is relevant in under 20 seconds.

## Personas

- New user: runs `fettle demo` outside a project and needs an immediate result.
- Power user: expects deterministic output suitable for scripts and snapshots.
- Accessible user: receives ordered plain text that does not depend on color.

## Journey

| Phase | Action | Output | Outcome |
|---|---|---|---|
| Entry | Run `fettle demo` anywhere | Stage 1 shows the seeded source with line numbers | The bug is concrete without opening a file |
| Detect | Wait | Stage 2 names the rule and relative source location | The quality control is traceable |
| Repair | Wait | Stage 3 shows a fixture-derived diff | The corrective action is visible |
| Verify | Wait | Stage 4 reports clean detection, the real test count, and the bug's consequence | Exit 0 proves the repaired behavior |

Interaction budget: one command, no prompts, under 20 seconds.

## States

- First-time empty: not applicable; the wheel includes the fixture.
- Cleared empty: not applicable; no persistent demo state exists.
- Filtered empty: not applicable; the command has no filters.
- Loading under one second: stage headings expose progress synchronously.
- Loading over one second: the current numbered stage remains visible.
- Populated: all four stages print in order with stable text.
- Recoverable error: the failed stage prints a stable failure reason and exits non-zero.
- Fatal error: verification failure prints `REPAIR NOT VERIFIED` and exits non-zero.
- Missing prerequisite: stderr names Git and gives macOS, Debian/Ubuntu, and Windows install commands.
- Offline: normal operation; no network or API key is consulted.
- Stale: not applicable; every run copies the bundled fixture anew.

## Accessibility And Disclosure

The output uses text and numbering rather than color, animation, terminal width,
or cursor control. There are no hidden steps or interactive controls. Help text
describes the command as an offline demonstration.

## Determinism Contract

Successful stdout is byte-identical across runs and supported operating systems.
It contains no timestamps, durations, absolute paths, random identifiers, or
filesystem iteration. Temporary files and subprocess output are never exposed.
Source context and repair lines are derived from the bundled fixture rather than
duplicated display strings. Output remains approximately 30 lines or fewer.

## UAT Scenarios

Scenario: complete offline loop
  Given finefettle is installed and the current directory is not a project
  When the user runs `fettle demo` without network access
  Then four ordered stages show the source, rule, repair diff, and independent verification
  And stage 4 ends with the real-world consequence in plain language
  And the command exits 0 in under 20 seconds

Scenario: independent verification fails
  Given a bundled fixture copy has a broken behavioral assertion
  When the verifier runs
  Then stage 4 reports `REPAIR NOT VERIFIED`
  And the command exits non-zero

Scenario: Git is unavailable
  Given finefettle is installed and Git is not on PATH
  When the user runs `fettle demo`
  Then stderr says that Git is required
  And it gives install commands for macOS, Debian/Ubuntu, and Windows
  And the command exits non-zero without starting the demo stages

Scenario: repeated execution
  Given the same installed wheel
  When the user runs `fettle demo` twice
  Then stdout from both successful runs is byte-identical
