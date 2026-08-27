---
fettle-work-item: true
id: p83-assurance-adversary
status: done
scope:
  - tests/
  - fettle/
spec: assurance-record-plan
---

# P83 — Assurance Adversary v1

Codify existing tamper/adversary coverage into a named suite (ledger
tampering, transcript drift, capsule tamper, docs-claims); add stale-
evidence injection, scope-manipulation attempt, policy-downgrade attempt.
Each adversary is a test proving detection. Feeds the P77 benchmark.

## Resolution

`tests/test_assurance_adversary.py` is the stable P83 benchmark entry point. It
injects ledger edits, transcript drift, capsule digest tampering, documentation
omission, stale evidence, wrong-scope replay, and numeric/list policy
downgrades into the production validators. Every case asserts a block,
tampered/indeterminate verdict, typed non-pass, or preservation of the stricter
parent policy; no parallel test-only validator was introduced.
