# Hypothesis Tree: Contextual Impact Analysis

Status: CI-1 passed on the original fixtures; research hypothesis CI-2
(implementation package CI-3) is falsified for promotion because corpus-v2
required recall fell below 100%, the eligible sample was underpowered, and the
paired precision-gain interval included zero

Objective: improve the usefulness of advisory impact analysis while preserving
zero missed required impacts, deterministic reproducibility, visible uncertainty,
and the existing P47 contract.

Primary metrics are required-impact recall, unexplained-narrower count, contextual
precision at 10, explanation completeness, deterministic replay, and p95 overhead.
Held-out results, not development fixtures, determine progress.

## ROOT CI-0

Hypothesis: separating required impact from ranked contextual review will reduce
operator noise without weakening change-integrity coverage.

Falsification: any unexplained missed/demoted required impact, nondeterministic
result, hidden incomplete state, or no useful precision improvement at acceptable
cost falsifies promotion.

Constraints:

- Existing undirected `EphemeralGraph.closure()` remains the compatibility oracle.
- Ranking never creates, removes, or resolves obligations.
- Missing, partial, conflicting, bounded, malformed, or stale evidence is non-pass.
- No branch may change Assurance or enforcement during research.
- Corpus-v2 review uses two distinct fresh-context blinded AI reviewers; each
  receives only its randomized packet and referenced repository revisions, and
  the owner reconciles disagreements.

## CI-1: Typed Deterministic Paths

Parent: CI-0

Hypothesis: adapting graph incidences to typed directional facts and applying
explicit rules will preserve all required oracle impacts while producing
inspectable rejection reasons.

Falsification: a maintained or held-out required impact is absent without an
approved oracle-defect classification, or any output varies with insertion order.

Expected improvement: 100% explanation coverage and zero unexplained narrower
required results; ranking quality is not yet expected to improve.

## CI-2: Deterministic Context Ranking

Parent: CI-0

Hypothesis: integer ranking by policy relevance, path length, trust, edge
confidence, provider completeness, and independent corroboration will improve
contextual precision at 10 over stable-key ordering without reducing required
recall.

Falsification: held-out precision at 10 does not improve, required recall drops
below 100%, ordering is unstable, or p95 analysis overhead exceeds 20%.

Expected improvement: at least 10% relative contextual precision at 10 on the
held-out corpus, with zero required-impact regressions.

Evidence, 2026-09-09: the initial four-case held-out split tied stable-key ordering
at 10,000 precision basis points because it contained no irrelevant contextual
candidates. This did not test the hypothesis. Corpus v2 therefore requires at
least 20 ranking-eligible cases per split, at least 10 candidates per case, at
least two relevant and two irrelevant labels, blind review, immutable identities,
and repository/subsystem group isolation between development and held-out data.

Evidence, 2026-09-10: both blinded reviews and owner reconciliation completed for
all 40 collected cases, resolving all 434 disagreements. Only 10 development and
7 held-out cases met the frozen two-relevant/two-irrelevant eligibility floor,
below the required 20 per split. On the eligible held-out cases, deterministic
ranking produced 2,000 precision basis points versus 1,714 for stable-key ordering
(1,669 basis points relative gain), but the paired 95% interval was 0 to 571 and
required-impact recall was only 7,805 basis points. CI-2 is therefore falsified
for promotion; labels were not changed after evaluation.

## CI-3: Perturbation Stability

Parent: CI-0

Hypothesis: deterministic removal of optional providers and low-confidence
contextual edges will identify brittle recommendations before authority changes,
while required obligations remain invariant.

Falsification: perturbation removes any required result/obligation, fails to name
the causal provider/edge set, or adds more than 25% p95 evaluation overhead.

Expected improvement: every unstable contextual result is attributable and no
required result is unstable.

## CI-4: Model Reranking

Parent: CI-0

Status: blocked; CI-2 did not pass held-out evaluation.

Hypothesis: an optional model can improve contextual precision at 10 beyond the
deterministic ranker while leaving the deterministic required set immutable.

Falsification: no statistically credible paired improvement, non-replayable
provenance, source disclosure beyond policy, excessive latency/cost, or any effect
on required evidence, obligations, PASS, or exit status.

Expected improvement: at least 5% relative precision at 10 beyond CI-2, evaluated
on held-out cases with model, prompt, input, and output digests retained.

## Experiment Order And Convergence

1. Freeze oracle labels and held-out partition before tuning.
2. Execute CI-1; prune the program if required recall cannot reach 100%.
3. Execute CI-2 only after CI-1 passes.
4. CI-2 did not pass. Do not execute CI-3 or retune against reviewed labels.
5. Execute CI-4 only by separate approval and only if deterministic residual
   noise justifies its operational and governance cost.

Three consecutive non-improving ranking experiments trigger a strategy review,
not weight tuning. Eight consecutive non-improving experiments close the tree and
retain the best deterministic advisory behavior.

Any replacement ranking experiment starts a new hypothesis branch and freezes a
new corpus before scoring. It cannot relabel this reviewed corpus to satisfy a
threshold.
