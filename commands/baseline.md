# /fettle:baseline

Manage violation baselines for gradual adoption.

## Usage

### Create baseline (snapshot current state)
```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh baseline.py create
```
Saves all current findings to `.fettle-baseline.json`. These findings are grandfathered.

### Check against baseline (only new violations)
```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh baseline.py check
```

### Update baseline (after fixing some findings)
```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh baseline.py update
```

## Purpose

Allows adoption in legacy repos without fixing all existing issues first.
Only NEW violations are reported; existing ones are tracked but not blocking.
