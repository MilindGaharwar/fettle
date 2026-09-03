# Onboarding Clarity Plan — Making Fettle Understandable in 60 Seconds

Source: audit + GPT cross-review convergence on "ease of understanding" as
the weakest dimension (6/10). The technology is world-class; the front door
is a maze.

Status: completed and superseded by the current README, documentation index,
offline demo, assurance-record example, and complete default installer.

## Diagnosis

A new user landing on the README sees 33 CLI commands, 20+ gates, 40+ docs.
The quick-start leads with `fettle check --changed` (a linter result). The
product's actual "aha" — the digest-bound Assurance Record answering "can I
trust this change?" — requires reading five docs to discover.

## Changes (surgical, no rewrite)

### C1 — README quick-start: lead with the Assurance Record

Replace the current "Evaluate the CLI" quick-start:

```bash
pipx install finefettle
cd your-project
fettle init --profile solo
# ... make a change, let your agent work ...
fettle assurance
```

…with the output shown inline (digest, dimensions, completeness). The
linter result moves to a "also included" mention. The assurance record IS
the product; the quick-start should prove it.

### C2 — Surface the behavior map and event map

Add to the README's Documentation table:
- "How do I add new behavior?" → docs/behavior-map.md
- "What events does Fettle dispatch?" → docs/event-map.md

Link both from CONTRIBUTING.md.

### C3 — Advertise profiles as the first decision

After install, before any other step: "choose your profile — solo (default),
team (delegation gates), enterprise (strict + compliance)." One line each.

### C4 — Add a second example: the Assurance Record on a real change

New `examples/assurance-record/` with a realistic multi-file change,
showing `fettle assurance --json` output with all nine dimensions
populated. This becomes the README's hero example.

## Success criteria

- A new user can go from `pipx install` to seeing their first Assurance
  Record in under 2 minutes.
- The README's first code block produces the product's core output.
- The behavior map and event map are linked from README + CONTRIBUTING.
- The profiles are explained before any gate configuration.
