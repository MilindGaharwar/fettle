# UX Spec: Offline Demo

## Job To Be Done

When I am evaluating Fettle before adopting it, I want one command that proves
the detect-repair-verify loop without setup or credentials, so I can decide
whether the product is relevant in under 20 seconds.

## Personas

- New user: runs `fettle demo` outside a project and needs an immediate result.
- Power user: expects deterministic output suitable for scripts and snapshots.
- Accessible user: receives ordered plain text that does not depend on color.

## Journey

| Phase | Action | Output | Outcome |
|---|---|---|---|
| Entry | Run `fettle demo` anywhere | Stage 1 introduces a known violation | The demonstration starts without setup |
| Detect | Wait | Stage 2 names the detected rule | The quality control is visible |
| Repair | Wait | Stage 3 states the bounded repair | The corrective action is visible |
| Verify | Wait | Stage 4 reports independent verification | Exit 0 proves the repaired behavior |

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

## UAT Scenarios

Scenario: complete offline loop
  Given finefettle is installed and the current directory is not a project
  When the user runs `fettle demo` without network access
  Then four ordered stages introduce, detect, repair, and independently verify the fixture
  And the command exits 0 in under 20 seconds

Scenario: independent verification fails
  Given the repaired fixture does not satisfy its behavioral tests
  When the verifier runs
  Then stage 4 reports `REPAIR NOT VERIFIED`
  And the command exits non-zero

Scenario: repeated execution
  Given the same installed wheel
  When the user runs `fettle demo` twice
  Then stdout from both successful runs is byte-identical
