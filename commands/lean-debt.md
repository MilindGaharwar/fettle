# /fettle:lean-debt

Report all `fettle:lean:` markers in the project — deliberate simplifications and their upgrade triggers.

## Usage

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh lean_debt.py
```

## Convention

Mark intentional simplifications with:

```python
# fettle:lean: <what>, upgrade when: <trigger>
```

Examples:
```python
# fettle:lean: flat dict dispatch, upgrade when: >5 handlers
# fettle:lean: inline validation, upgrade when: shared across 3+ files
// fettle:lean: manual retry, upgrade when: need backoff/jitter
```

Markers without "upgrade when:" are flagged as rot risks.

## Purpose

Answers: "Where did we choose simple intentionally, and when should we reconsider?" Prevents future agents from over-abstracting code that was deliberately kept lean.
