# Fettle Behavioral Evals — WP-133

> Shape stolen with attribution from
> [superpowers-evals](https://github.com/prime-radiant-inc/superpowers-evals)
> (quorum), radically slimmed. Rule *matching* is proven by
> `tests/test_rule_integrity.py` fixtures; this lab proves the step after:
> **do the gates change agent behavior?**

## Safety model (quorum's line, kept)

- **Static side — CI-safe.** Scenario schema validation, check evaluation,
  verdict composition. Runs in pytest with a fake runner
  (`tests/test_evals_runner.py`). Never launches an agent CLI, never needs
  API keys. `python scripts/evals_runner.py validate` is the CI entry.
- **Live side — trusted-operator only, never public CI.** `run` launches
  `claude -p` in a scratch workdir with Fettle hooks active and grades the
  transcript plus resulting files. Costs tokens; transcripts may be
  sensitive. Results are gitignored.

## Anatomy

```
evals/scenarios/<name>/scenario.yaml
  id            defaults to the directory name
  prompt        what the agent is asked to do
  setup_files   files seeded into the scratch workdir
  checks        file_matches | file_not_matches |
                transcript_matches | transcript_not_matches
```

Verdicts are three-valued: `pass` (0) — every check passed; `fail` (1) — a
check failed; `indeterminate` (2) — runner error or empty transcript when
transcript checks exist. Never conflate fail with indeterminate: one is
evidence, the other is a broken experiment.

## Commands

```bash
python3 scripts/evals_runner.py validate                 # CI-safe
python3 scripts/evals_runner.py run evals/scenarios/hook-catches-debug-statement   # LIVE
```
