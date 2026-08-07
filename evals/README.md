# Fettle Behavioral Evaluations

Static rule fixtures answer "did the analyzer match?" This lab answers the more
important product question: **did the feedback help an agent change behavior?**

> Structure adapted with attribution from
> [superpowers-evals](https://github.com/prime-radiant-inc/superpowers-evals)
> (quorum), radically slimmed. Rule *matching* is proven by
> `tests/test_rule_integrity.py` fixtures; this lab proves the step after:
> **do the gates change agent behavior?**

## Safety model (quorum's line, kept)

- **Static side — CI-safe.** Scenario schema validation, check evaluation,
  verdict composition. Runs in pytest with a fake runner
  (`tests/test_evals_runner.py`). Never launches an agent CLI, never needs
  API keys. `python3 scripts/evals_runner.py validate` is the CI entry.
- **Live side — trusted-operator only, never public CI.** `run` launches
  `claude -p` in a scratch workdir with Fettle hooks active and grades the
  transcript plus resulting files. Costs tokens; transcripts may be
  sensitive. Results are gitignored.

## Anatomy

```
evals/scenarios/<name>/scenario.yaml
  id            defaults to the directory name
  language      python | typescript (required for release baselines)
  held_out      true when reserved from message tuning
  prompt        what the agent is asked to do
  setup_files   files seeded into the scratch workdir
  checks        file_matches | file_not_matches |
                transcript_matches | transcript_not_matches
```

Verdicts are three-valued: `pass` (0) — every check passed; `fail` (1) — a
check failed; `indeterminate` (2) — runner error or empty transcript when
transcript checks exist. Never conflate fail with indeterminate: one is
evidence, the other is a broken experiment.

Each run also records `repair_success`, `turns_to_repair`,
`repeated_violation`, UTF-8 `diagnostic_bytes`, and `indeterminate_reason`.
`turns_to_repair` remains null for runners that expose only final output; the
harness does not infer turns from prose.

## Commands

```bash
python3 scripts/evals_runner.py validate                 # CI-safe
python3 scripts/evals_runner.py run evals/scenarios/hook-catches-debug-statement   # LIVE
```

Run static validation for every contribution that changes a scenario, grader,
diagnostic message, or language rule. Live runs require an installed Claude CLI
and should use a trusted scratch environment; inspect generated transcripts
before sharing them.

## Interpreting Results

- `pass` means every declared observable check passed.
- `fail` is valid negative evidence: the agent did not achieve the scenario.
- `indeterminate` means the experiment itself was not trustworthy and must not
  be counted as a pass or failure.

Compare language and message changes against held-out scenarios. Do not tune a
diagnostic on the same scenarios used to claim improvement.
