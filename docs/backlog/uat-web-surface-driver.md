---
fettle-work-item: true
id: uat-p74-web-surface
status: open
scope:
  - fettle/uat/session.py
  - fettle/uat/doctor.py
  - pyproject.toml
spec: plan-uat-strength
---

# P74 — Web surface driver (S5.5) with accessibility capture

Plan: `docs/uat-strength-plan.md`

Ship the pending Playwright web driver behind the optional
`finefettle[uat]` extra: navigation/click/read driven exactly as a person
would, axe-core accessibility scan woven into every page state, and visual
capture feeding the P72 artifact channel. Capability probe in
`fettle uat doctor` must report playwright/axe availability and degrade to
the manual click-through script (requirement-4 messaging).

## Done when

- A web session against a demo app drives all scenarios through the UI only
  and retains a11y results per page state.
- Missing playwright yields exit 2 from doctor with the manual fallback
  path, proven by test.

## Resolution

Record how it was resolved.
