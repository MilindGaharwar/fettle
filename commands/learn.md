# /fettle:learn

Generate a semgrep rule from an incident description.

## Usage

When the user invokes `/fettle:learn`, ask for the incident details:

1. What failed? (the bug or vulnerability)
2. What code pattern caused it?
3. What should it look like instead?

Then run:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh learn.py --incident "INCIDENT_TEXT" --auto-save
```

The generated rule lands in `rules/learned/<rule-id>.yml` with:
- Semgrep pattern
- Citation (incident reference)
- Violating fixture (tests/fixtures/learned/)
- Clean fixture (tests/fixtures/learned/)

## Verification

After generating, verify the rule works:
```bash
semgrep --config rules/learned/<rule-id>.yml tests/fixtures/learned/<rule-id>_violation.py
```

Should match the violation fixture and NOT match the clean fixture.
