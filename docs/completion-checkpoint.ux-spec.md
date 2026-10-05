# UX Spec: Completion Checkpoint Validation

## Job To Be Done

When I need to publish an honest intermediate checkpoint for remote acceptance,
I want structurally valid incomplete evidence to pass the checkpoint boundary, so
platform jobs can run without implying that the milestone is complete.

## Personas

- New contributor: needs one explicit command and truthful next steps.
- Maintainer: needs automation-safe exit codes without weakening merge protection.
- Accessible CLI user: needs complete text/JSON status without color-only meaning.

## Journey

| Phase | Action | Output | Risk controlled |
|---|---|---|---|
| Entry | Run `fettle completion validate --checkpoint` | Same completion report as strict mode | No new evidence interpretation |
| Core | Inspect incomplete criteria | Verdict, reason, and recovery remain visible | Incomplete cannot look complete |
| Exit | Publish checkpoint for CI | Process succeeds only when evidence is structurally valid | Invalid evidence still blocks |

Time budget: one command; no prompts; same runtime as strict validation.

## States

- No manifests: valid under the existing evaluator; output remains “no manifests”.
- Complete: process exit 0; `complete: true`.
- Valid incomplete: checkpoint process exit 0; `complete: false` and recovery retained.
- Invalid, malformed, missing, contradictory, or unsafe evidence: process exit 2.
- Stale evidence: preserve the evaluator's valid-incomplete result and stale reason;
  checkpoint may carry it, but strict merge/release acceptance remains non-pass.
- Loading/offline states: not applicable; validation is synchronous and local.
- Fatal environment error: exit 2 with the existing repository error.

## Accessibility And Disclosure

Text and JSON carry the full decision. Exit status is an automation signal, not the
only status. The `--checkpoint` flag explicitly names the relaxed boundary; default
validation stays strict.

## UAT Scenarios

Scenario: honest incomplete checkpoint
  Given structurally valid incomplete completion evidence
  When validation runs with `--checkpoint`
  Then the process exits 0 while output remains incomplete with recovery guidance

Scenario: invalid checkpoint
  Given malformed, missing, contradictory, or unsafe evidence
  When validation runs with `--checkpoint`
  Then the process exits 2 and reports the validation errors

Scenario: strict merge acceptance
  Given valid incomplete evidence
  When the strict CI completion job runs without `--checkpoint`
  Then it exits 1 and the stable required merge gate remains non-pass
