# /fettle:learn

Generate a semgrep rule from an incident description.

## Usage

When the user invokes `/fettle:learn`, ask for the incident details:

1. What failed? (the bug or vulnerability)
2. What code pattern caused it?
3. What should it look like instead?

Then run:
```bash
fettle learn --incident "INCIDENT_TEXT" --auto-save
```

The drafted rule lands in the `rules/proposed/` quarantine (status: proposed)
with:
- Semgrep pattern
- Citation (incident reference)
- Violating fixture (tests/fixtures/learned/)
- Clean fixture (tests/fixtures/learned/)

Proposals are NEVER loaded by gates. Promotion to `rules/learned/` is an
explicit human step.

## Verification

After generating, verify the rule works against its fixtures:
```bash
semgrep --config rules/proposed/<rule-id>.yml tests/fixtures/learned/<rule-id>_violation.py
```

Should match the violation fixture and NOT match the clean fixture.

## Approval

Review the quarantined proposals and promote the good ones:
```bash
fettle rules list
fettle rules promote <rule-id>
```

Promotion moves the rule to `rules/learned/` (status: learned), where it can
be loaded via `.fettle.toml`. `fettle rules promote` refuses proposals with
an empty pattern.
