---
fettle-work-item: v2
id: installed-artifact-test-clock
status: claimed
scope:
  - docs/backlog/installed-artifact-test-clock.md
  - tests/test_installed_artifact_contract.py
spec: maintenance
---

# Remove wall-clock dependence from the installed-artifact command test

The successful command test uses fixed live-evidence timestamps while the
command compares them with the real clock. Keep success evidence current and
add command-level regression coverage proving evidence older than the
configured 90-day limit is still rejected.

## Acceptance criteria

- The command success fixture derives `observed_at` from current UTC time.
- A subprocess test rejects evidence older than 90 days.
- Fixed-clock tests remain unchanged.
- Only tests and this work-item record change.

## Audit

- `tests/test_installed_artifact_contract.py:19` supplied
  `2026-08-16T12:00:00Z` to the subprocess command at line 144. With the
  configured 90-day maximum, it remained valid through
  `2026-11-14T12:00:00Z` and failed immediately afterward. Fixed here.
- `tests/test_installed_artifact_contract.py:106` is deliberately stale and
  is evaluated with explicit `NOW`; it is date-independent and unchanged.
- `tests/test_mutation_test.py:1453`, `tests/test_assurance_adversary.py:61`,
  and `tests/test_evidence.py:50,79` use fixed `observed_at` values only for
  schema/serialization or with explicit evaluation context. They never reach
  a real-clock freshness comparison, so they have no calculated failure date
  and remain unchanged.
- `fettle/installed-host-evidence.json:6,12,24` is loaded by the installed
  canary, whose `validate_report` call validates shape but does not evaluate
  age. It has no calculated failure date and remains unchanged.

## Resolution

The command success fixture now uses the current UTC instant, while a companion
subprocess test derives a timestamp one day beyond the configured freshness
limit and confirms that the command rejects it as stale.
