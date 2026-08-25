# Mutation Ratchet Decision Memo — Changed-Scope Survivor Enforcement

Date: 2026-08-24 · Author: engineering session (agent) · Decision owner: Milind
Status: RATIFIED; enforcement DEMOTED to advisory after first triage (2026-08-25) — see below

## Question

May Fettle's own repository flip changed-scope survivor handling from
advisory to enforcement, per milestone D4 ("three retained stable
mutation-workflow runs remain before baseline and ratchet graduation")?

## Evidence

### Qualifying retained runs (required `mutation evidence` gate)

Since the required gate launched on 2026-08-23 (commit `16c2e34`, PR #11),
the following completed with `conclusion=success` and retained
evidence artifacts (workflow `mutation.yml`):

| Run | Commit | Date |
|---|---|---|
| 32623791036 | `16c2e34` | 2026-08-23 (PR #11 merge validation) |
| 32628787313 | `326cf22` | 2023-08-23 (PR #12) |
| 32653879797 / 32654483698 / 32657050034 | plan docs | 2026-08-23 |
| 32693487381 / 32695881671 / 32700341103 / 32707019008 / 32716169117 / 32723594867 | P38–P52 series | 2026-08-24 |

Count: **≥10 qualifying stable runs** across six distinct heads — far above
the three-run trigger. Scheduled main-branch runs (`06febb2`, `835ad31`)
provide additional independent confirmation.

### Stability criteria

- No infra-failure verdicts among qualifying runs; the one historical
  failure (`957df8f`) was a genuine shard-201 finding, fixed and re-proven.
- Replay machinery exercised end-to-end (38 missing shards replayed during
  the Aug-17 incident run and again on request).

### Actionability criterion (reviewer-confirmed)

The shard-201 incident produced a real product defect fix
(`test: keep mutation flows out of repository root`, merged as part of
PR #11 lineage): mutation testing surfaced a mutated-default path that
deleted live runner state. Reviewer confirmed and merged. Runtime overhead:
full fan-out ≈60–90 minutes wall clock on free runners, acceptable for this
repository's cadence.

## Recommendation

1. Flip `.fettle.toml` → `[mutation] mode = "enforce"` for **changed-scope
   survivor enforcement** on this repository's pull requests.
2. Keep full-scope runs scheduled/manual (held-out verification only).
3. Rollback: set mode back to `"advisory"` (single line) if a false-positive
   survivor ever blocks an unrelated change; record the incident per the
   playbook (item 34).

## Not proposed

- Flipping enforcement for downstream consumers' repos — each repository
  graduates independently.
- Zero-new-survivor enforcement beyond changed scope.

## Operator actions to enact

```bash
# after ratification
uv run fettle config --explain | grep mutation   # confirm effective keys
# edit .fettle.toml: [mutation] mode = "enforce"
git commit -am "policy: enforce changed-scope survivor gate"
```

## First enforced-week triage checklist

### First triage result (2026-08-25, run 32806910288)

The flip landed on the same PR that introduced ~3,000 lines of new
un-hardened code, so enforcement immediately blocked on its own
introduction:

- 53 shards failed under enforce; retained reports show ~1,832 surviving
  mutants in changed scope.
- Histogram: cli.py 1,087 · uat/session 179 · evidence_ledger 135 ·
  graph_cli 110 · reconcile 103 · state_consistency 89 · artifacts 45 ·
  graph_shadow 53 · spec_provider 28 · __init__ 4.
- Machinery verdict: WORKS AS DESIGNED (correct blocking, precise reports,
  fail-closed aggregation). Timing verdict: PREMATURE for current repo
  maturity.

### Decision

Demoted to advisory per the pre-agreed rollback line. Path back to
enforcement (choose one):

1. **Hardening sprint** — kill the cli.py cluster (largest, legacy debt)
   then the new-module clusters; re-attempt enforcement when survivors in
   changed scope drop below an agreed bar (e.g., <50).
2. **Scoped enforcement** — extend the workflow to enforce only when no
   NEW modules appear in the survivor histogram (needs ratchet tooling).

Either way, the machinery itself needs no changes.


Run after ~5 enforced PRs (or 14 days, whichever first):

- [ ] Any false-positive survivor blocks? Record each: shard, mutant id,
      whether tests genuinely missed it, and suppress-or-fix outcome.
- [ ] Median added wall-clock per PR acceptable? (gate adds ~60–90 min
      fan-out; if unacceptable, narrow `paths` before demoting mode.)
- [ ] Zero silent passes: confirm every changed-scope PR produced a report
      artifact (docs-claims predicate + workflow artifacts).
- [ ] If all clean → propose full-scope (all-files) survivor consideration
      as the next ratchet step; if not → rollback line above.
