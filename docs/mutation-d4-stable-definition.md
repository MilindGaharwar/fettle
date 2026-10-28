# D4 Stable Full-Scope Mutation Definition

Status: qualification contract; no run has qualified under this definition yet.
Full-corpus mutation qualification remains `CLOSED_NON_PASS`.

## Purpose

D4 stability is evidence that Fettle can repeat one complete full mutation
measurement without changing the measured corpus or importing prior terminal
outcomes. It is not a claim that the current score or survivor set is acceptable.
Only three runs satisfying every criterion below may support a later baseline or
ratchet proposal.

## Frozen corpus

Before run 1, retain one canonical full-scope preflight corpus and its identity:

- exact `main` revision and clean source tree;
- canonical mutant fingerprints and generated-detail validation;
- complete ordered 256-shard manifest topology and manifest digests;
- mutation paths, source-file digests, mapped-test paths and digests;
- pinned mutation runtime and dependency-lock digests;
- effective mutation policy and configuration digest; and
- runner image, operating system, Python, and mutation-engine identity.

Runs 1–3 must consume that same immutable corpus identity. The source revision,
manifests, dependencies, policy, environment, or expected shard membership may
not change between runs. If any identity changes, the sequence resets at run 1
with a newly retained corpus. Independent runs may share this immutable input,
but never a native cache, checkpoint, shard report, or terminal outcome.

## Qualifying run

A run qualifies only when all of these statements are true:

1. **Fresh:** it starts with no `.mutmut-cache`, Fettle mutation cache, prior
   checkpoints, recovered reports, or reused shard result. Every selected mutant
   is executed in that run.
2. **Full scope:** all 256 expected manifests dispatch against the frozen corpus.
   Sparse continuation, advisory reuse, changed-scope evidence, capacity probes,
   and fixture runs do not qualify.
3. **Complete:** exactly one compatible terminal report exists for every shard;
   all 256 reports aggregate; no shard is missing, duplicated, malformed,
   conflicting, stale, skipped, blocked, indeterminate, or represented only by a
   timeout or checkpoint.
4. **Identity-bound:** the aggregate validates the exact revision, corpus,
   manifest, dependency, policy, engine, environment, run, and attempt lineage.
5. **Non-reused:** the aggregate records zero reused shards and no terminal
   outcome originates in another run or attempt.
6. **Canonical:** generated details equal canonicalized details; rejected details
   and fingerprint collisions are zero. Run-local mutmut numeric IDs are not used
   for cross-run identity.
7. **Retained:** the corpus, all manifests and reports, aggregate, evidence index,
   workflow metadata, and bounded diagnostics remain downloadable and their
   recorded digests verify.
8. **Honest result:** every outcome class and every survivor remains visible.
   A policy failure may be a valid complete measurement, but it is not silently
   converted into a pass or treated as approval of test strength.

Missing, malformed, partial, stale, conflicting, skipped, blocked, or
indeterminate evidence is a non-pass. A timeout can prove timeout handling only;
it cannot satisfy completion.

## Three-run sequence

The qualifying runs must be dispatched sequentially: run 2 starts only after run
1 reaches a terminal state and its retained evidence validates; run 3 follows the
same rule for run 2. They must be consecutive D4 qualification attempts on the
frozen corpus. An intervening failed, cancelled, incomplete, recovered, reused,
or identity-incompatible attempt breaks the sequence and resets the count to
zero. Provider reruns are separate attempts and do not erase the original
terminal state.

For each run, retain at least:

| Field | Required evidence |
|---|---|
| Identity | revision, run and attempt, corpus digest, policy digest, engine and environment |
| Topology | 256 expected, 256 dispatched, 256 compatible terminal reports, 0 missing |
| Reuse | 0 reused shards; fresh execution provenance for every shard |
| Outcomes | killed, survived, timeout, suspicious, skipped, untested, and total counts |
| Integrity | rejected details, collisions, duplicate origins, and incompatible reports |
| Timing | dispatch, completion, wall time, and per-shard engine time |
| Retention | artifact names, provider artifact IDs, digests, and evidence-index location |

## Survivor-delta reconciliation

Compare runs by canonical fingerprint, never native numeric ID. For each adjacent
pair, retain the unchanged, added, removed, and outcome-transition sets with file
and owning module. Every delta must have a concrete explanation supported by the
retained reports.

Because the corpus is frozen, source or test edits cannot explain a delta within
one sequence. Permitted explanations are bounded observed nondeterminism, an
engine outcome transition, or a proven evidence defect. Unexplained deltas,
fingerprint drift, missing details, or contradictory classifications invalidate
stability and reset the sequence. Raw survivors remain visible; reconciliation
does not waive, suppress, or reclassify them as passing.

## Graduation boundary

After three qualifying runs, publish a comparison containing the common corpus
identity, each run's retained evidence, outcome totals, timing, and all explained
survivor deltas. That comparison permits a separate baseline or ratchet proposal.
It does not itself:

- accept a mutation score or survivor inventory;
- change `passed = skipped == 0` or any outcome budget;
- grant advisory evidence qualification authority;
- waive existing or new survivors;
- enable enforcement; or
- retire any workflow.

Any baseline, policy ratchet, qualification transition, or workflow retirement
requires explicit subsequent approval.
