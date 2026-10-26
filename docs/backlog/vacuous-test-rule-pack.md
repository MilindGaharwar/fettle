---
fettle-work-item: v2
id: vacuous-test-rule-pack
status: open
scope:
  - docs/backlog/vacuous-test-rule-pack.md
  - docs/engagement/TODO.md
spec: fettle-evolution-implementation-plan
---

# Vacuous-test rule pack and distinguishing-mutant convention

Backlog note recorded 2026-10-24. Deferred; no implementation, rule authoring,
or priority change is authorized by this item. Revisit after AH07 closes and
Phase 3 feature work is under way, in recorded TODO order.

## Source

Theorem Labs' OSS Verify enrollment skill
(`theorem-labs/oss-verify`, `.claude/skills/add-project/SKILL.md`, §3.2–3.7)
states test-strength rules that match Fettle's existing non-vacuity stance and
names concrete anti-patterns that make a test or fuzz target check nothing:

- a property written with `assert()` that `NDEBUG` removes silently;
- returning `-1` (or any "skip" value) for a failed property, so the harness
  reports pass;
- `exit()`, catch-all exception handlers, or signal handlers that hide failures;
- calling an API and ignoring its result;
- a property that no one-line change to the code under test can make fail.

Its §3.3 coverage witness (every check demonstrably executes at least once) and
§3.4 distinguishing mutant (every property has a recorded one-line change plus
input that makes it fail) are the per-test form of what Fettle's mutation
evidence measures in bulk.

## Candidate work (not approved)

1. A semgrep rule pack for the anti-patterns above, scoped first to Python
   tests (Fettle's current domain), with the C/C++ fuzz-harness variants as a
   later pack only if a non-Python workflow is selected under P4.
2. An authoring convention for new Fettle tests: a one-line comment naming the
   distinguishing mutant (change and failing input) for each behavioral
   assertion, validated by the mutation run rather than by a new gate.
3. Reuse of OSS Verify's "what a proof does not say / what you have to trust"
   wording as a model for Fettle evidence artifacts' stated limits.

## Reference material (no action)

- Google OSS-Fuzz (`google/oss-fuzz`): its ~5,000 enrolled fuzz harnesses are
  the validation dataset for a future C/C++ variant of the rule pack; OSS Verify
  reports that many break the rules above. Relevant only if P4 selects a
  non-Python workflow.
- ClusterFuzzLite: bounded, PR-scoped, advisory fuzzing with a corpus persisted
  across runs. Precedent for the changed-scope mutation advisory and for the
  parked content-addressed shard-report reuse idea; not an enrollment target.

## Boundary

This is a rule and documentation idea, not an enrollment. Fettle is not a
candidate for OSS Verify proofs: the program selects established projects, and
a halts proof over a Python CLI covers little of Fettle's actual risk surface.
Nothing here changes mutation scope, pass semantics, policy, or any accepted
hardening evidence.
