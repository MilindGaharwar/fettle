# Contextual Impact Analysis Implementation Plan

Status: experimental advisory implementation complete; default rollout,
enforcement, Assurance consumption, and model reranking are not authorized.
Corpus-v2 review is complete, but implementation package CI-3 (research
hypothesis CI-2) is falsified for promotion by insufficient ranking-eligible
cases, required-impact recall below 100%, and an inconclusive paired
precision-gain interval.

UX contract: [contextual-impact.ux-spec.md](contextual-impact.ux-spec.md)

Research state:
[hypothesis-tree-contextual-impact.md](hypothesis-tree-contextual-impact.md)

The approved advisory scope is complete. Any replacement ranking experiment
requires a new hypothesis, separate approval, and a newly pre-frozen corpus.

## 1. Objective And User Story

As a developer reviewing a broad graph closure, I want deterministic required,
contextual, and excluded classifications with ranked explanations, so I can act
on likely impact without allowing relevance ranking to hide uncertainty or weaken
required verification.

The implementation adds a contextual analysis layer over immutable graph facts.
It does not replace `EphemeralGraph.closure()`, alter Assurance, or authorize CI
obligations. The first release is explicit-command, advisory, and shadow-evaluated.

## 2. Current State And Assumptions

1. `fettle/graph_cli.py::_impact_payload()` currently uses the unbounded,
   undirected `EphemeralGraph.closure()` and stable-key sorting.
2. `fettle/traversal_rules.py::traverse()` already supplies deterministic bounded,
   directional, trust-aware traversal and fail-visible provider handling for the
   planned consequential path, but is not wired to advisory graph generation or
   production provider results.
3. `ProviderResult` and `ProviderFactSet` are different contracts. The former
   builds the graph; the latter supplies complete provenance and trust needed by
   traversal. An explicit adapter is required rather than synthetic defaults.
4. `graph_builder.DEFAULT_TRAVERSAL_RULES` is generation metadata, not a valid
   `TraversalRule`; the names must remain distinct.
5. P47 human and JSON output are external compatibility surfaces. Existing
   behavior remains the oracle while contextual analysis is opt-in.
6. P48's semantic shadow is precedent, not sufficient evidence for contextual
   ranking. Each consumer and obligation surface needs its own comparison.
7. Provider drafts currently do not expose all confidence/trust details needed by
   the proposed ranker. Missing dimensions are omitted or marked unknown; they
   are never guessed.
8. `kgraph impact --file` is not valid for the installed version, and the prior
   index reported stale state. Run `kgraph index`, then use positional
   `kgraph impact <paths>` before implementation.

## 3. Approaches And Decision

| Approach | Benefit | Cost or risk | Decision |
|---|---|---|---|
| Replace `closure()` with ranked traversal | Small apparent surface | Breaks P47 semantics and couples discovery to ranking | Reject |
| Add a deterministic contextual layer over typed graph facts | Preserves compatibility, explanations, replay, and shadow comparison | Requires explicit adapters and schemas | Adopt |
| Use an LLM as the primary ranker | Potential semantic relevance | Nondeterminism, cost, disclosure, provenance, and authority risk | Defer as optional experiment |
| Add embeddings or a GNN | Potential learned graph signal | Corpus, training, drift, interpretability, and operating burden are unjustified | Reject until deterministic residual error is measured |

The adopted architecture is:

```text
immutable graph + provider results + policy/rules
    -> production fact adapter
    -> bounded typed path analysis
    -> required/contextual/excluded classification
    -> deterministic integer ranking and explanation
    -> explicit CLI rendering
    -> shadow comparison and perturbation evidence
```

## 4. Contracts

### 4.1 Production Fact Adapter

Add a pure adapter that emits, in canonical order:

- `TraversalFact` for each permitted directed endpoint transition;
- `ProviderFactSet` reconstructed from real provider identity, run state,
  completeness, trust, configuration, input, and implementation metadata;
- rejected-fact records for malformed, unattributed, conflicting, or unsupported
  graph relationships.

Do not infer trust from edge names. Extend `ProviderResult` only with data that a
provider can prove. If a required field is unavailable, contextual traversal is
`unknown`; existing P47 closure remains available as advisory legacy output.

Hyperedges with more than two endpoints expand according to explicit role and
direction rules, not all-pairs adjacency. Duplicate transitions canonicalize to
one fact while retaining corroborating provider identities separately.

### 4.2 Contextual Result

Introduce frozen canonical records, preferably in one new module until reuse is
proven:

- `ImpactPath`: seed, target, ordered typed steps, depth, provider set, digest.
- `ImpactCandidate`: target, classification, score components, accepted paths,
  rejected reasons, action, digest.
- `ContextualImpactResult`: snapshot, graph, policy/rule, providers, seeds,
  required/contextual/excluded candidates, traversal state, limits, digest.

Classification precedence is `required > contextual > excluded`. A target with
one required path remains required even if other paths are rejected. `unknown`
or `limit_reached` applies to the result as a whole and blocks complete/empty
claims.

### 4.3 Policy And Obligation Relevance

The initial rule set is versioned Python data, reviewed beside tests. It may map
node kind, change class, edge type, role, direction, and trust class to:

- required impact and an existing `ObligationTemplate`;
- contextual review without obligation; or
- exclusion with a stable reason code.

Ranking does not create obligations. Only a matching approved rule may do so,
and shadow mode serializes proposed obligations separately from authoritative
ones. No generic policy DSL is introduced.

### 4.4 Deterministic Ranking

Use integer components and lexicographic tie-breaking. Initial components, in
priority order, are:

1. required/policy relevance;
2. shortest accepted path length;
3. strongest accepted trust class;
4. edge confidence when explicitly provided;
5. provider completeness;
6. number of independent corroborating providers or paths;
7. stable target identity.

Weights and enum ordering are versioned and digest-bound. Tests recompute every
score from its explanation. Floats, timestamps, iteration order, and model output
are forbidden from deterministic ranking.

### 4.5 Compatibility

- No option: preserve current `affected`, `count`, human rendering, and exit codes.
- `--contextual`: return a versioned additive result with `required`,
  `contextual`, `excluded`, `limitations`, and `analysis_digest`.
- Contextual items remain a subset/annotation of the legacy advisory superset
  during shadow mode. Any missing legacy item is retained in comparison evidence.
- Schema replacement requires a separate versioned migration proposal.

## 5. Work Packages

Effort estimates include implementation, focused tests, review fixes, and manual
CLI verification, but not the multi-repository shadow observation period.

### CI-0: Freeze UX, Oracle, And Evaluation Corpus (1-2 days)

Files:

- `docs/contextual-impact.ux-spec.md`
- `docs/hypothesis-tree-contextual-impact.md`
- `tests/fixtures/contextual_impact/` (new)
- `tests/test_graph_cli.py`
- `fettle/evals_runner.py`

Tasks:

1. Capture current P47 human, JSON, and exit-code golden fixtures.
2. Define labeled direct, transitive, excluded, incomplete, cycle, hyperedge,
   conflicting-provider, and bounded cases.
3. Split repository scenarios into development and `held_out: true` sets before
   score tuning.
4. Record required-impact labels independently from contextual relevance labels.
5. Define precision at 10 as relevant contextual targets in the first ten
   contextual results divided by `min(10, contextual results returned)`. Freeze
   relevance guidance, minimum held-out size, reviewer identities, disagreement
   resolution, and report raw agreement before tuning.
6. Verify frozen fixtures are insertion-order and checkout-path independent.

Gate: contract review approves labels, held-out isolation, compatibility oracle,
and zero-miss safety metric.

Verification:

```bash
python3 -m pytest tests/test_graph_cli.py tests/test_evals_runner.py -q
```

### CI-1: Provider Metadata And Fact Adapter (2-4 days)

Files:

- `fettle/providers/base.py`
- `fettle/providers/` provider implementations
- `fettle/hypergraph.py`
- `fettle/graph_builder.py`
- `fettle/traversal_rules.py`
- `fettle/contextual_impact.py` (new)
- `tests/test_graph_providers.py`
- `tests/test_contextual_impact.py` (new)

Tasks:

1. Inventory which provider identity/trust/completeness fields are provable.
2. Add only missing canonical provider metadata to `ProviderResult`.
3. Preserve provider ownership per edge; remove `_fact_set_for()`'s first
   edge-type-owner ambiguity where duplicate edge types can occur.
4. Convert incidences into directional `TraversalFact` records under explicit
   role rules.
5. Convert provider results into real `ProviderFactSet` records.
6. Return stable rejection reasons for unattributed or unsupported facts.
7. Prove duplicate, conflict, cycle, and multi-endpoint behavior.
8. Prove `complete=True` without required trust or identity metadata produces
   `unknown`, never a synthetic trusted fact set.
9. Given two providers emitting the same edge type, prove edge ownership remains
   explicit and the canonical result is stable regardless of provider order.

Gate: all required facts have real provider provenance; unavailable metadata
causes `unknown`, never a trusted synthetic value.

Verification:

```bash
python3 -m pytest tests/test_graph_providers.py tests/test_traversal_rules.py tests/test_contextual_impact.py -q
```

### CI-2: Paths, Classification, And Explanations (3-5 days)

Files:

- `fettle/contextual_impact.py`
- `fettle/traversal_rules.py`
- `tests/test_contextual_impact.py`
- `tests/fixtures/contextual_impact/`

Tasks:

1. Enumerate bounded accepted paths deterministically without changing
   `EphemeralGraph.closure()`.
2. Preserve shortest path plus bounded corroborating paths per target.
3. Apply classification precedence and stable exclusion reason codes.
4. Generate obligations only from approved required rules and complete traversal.
5. Canonically digest paths, candidates, and aggregate result.
6. Verify every displayed decision can be reconstructed from serialized facts.
7. Prove limits and incomplete providers never become exclusions or empty success.

Gate: CI-1 hypothesis passes with 100% required recall and zero nondeterministic
replays on development and held-out fixtures.

Verification:

```bash
python3 -m pytest tests/test_contextual_impact.py tests/test_traversal_rules.py -q
```

### CI-3: Deterministic Ranking (2-3 days)

Files:

- `fettle/contextual_impact.py`
- `tests/test_contextual_impact.py`
- `fettle/evals_runner.py`
- `evals/contextual_impact/` (new, if consistent with current eval layout)

Tasks:

1. Freeze integer component enums and lexicographic precedence.
2. Rank only within classification; required always precedes contextual.
3. Serialize every component and final deterministic sort key.
4. Add paired stable-key-baseline versus ranker metrics.
5. Tune on development scenarios only.
6. Run held-out evaluation once after the candidate is frozen.

Gate: zero missed/demoted required impacts, deterministic replay, and at least
10% relative contextual precision-at-10 improvement on held-out cases. A smaller
gain may remain experimental but cannot progress toward authority.

Verification:

```bash
python3 -m pytest tests/test_contextual_impact.py tests/test_evals_runner.py -q
```

### CI-4: Explicit CLI Surface (2-3 days)

Files:

- `fettle/graph_cli.py`
- `fettle/cli.py`
- `tests/test_graph_cli.py`
- `tests/test_cli.py`
- `docs/README.md`

Tasks:

1. Add the reviewed explicit contextual option and detailed rendering.
2. Add `fettle graph impact --help` text and README guidance naming the option's
   experimental, advisory-only status and its fallback behavior.
3. Forward contextual and detailed options explicitly through
   `fettle/cli.py::cmd_graph`; do not assume the nested parser receives them.
4. Preserve no-option compatibility fixtures byte-for-byte where stable output is
   promised and structurally for JSON.
5. Group required, contextual, limitations, and next command within 2 KiB.
6. Expose excluded candidates and complete provenance only in detailed/JSON mode.
7. Verify help, `NO_COLOR`, redirected output, path errors, provider errors, and
   limits.
8. Manually run the complete UX journey in a fresh sample repository.

Gate: contextual output is discoverable in one command, default P47 behavior is
unchanged, and no graph result affects hooks, CI, or Assurance.

Verification:

```bash
python3 -m pytest tests/test_graph_cli.py tests/test_cli.py -q
NO_COLOR=1 python3 -m fettle.cli graph impact fettle/graph_cli.py --contextual
python3 -m fettle.cli graph impact fettle/graph_cli.py --contextual --json
```

### CI-5: Shadow Comparison And Perturbation (3-5 days)

Files:

- `fettle/graph_shadow.py`
- `fettle/contextual_impact.py`
- `fettle/evals_runner.py`
- `tests/test_graph_shadow.py`
- `tests/test_contextual_impact.py`

Tasks:

1. Compare required sets and proposed obligations against each relevant legacy
   oracle separately.
2. Classify differences as contextual defect, oracle defect, unsupported case,
   expected advisory difference, or proposed behavior change.
3. Deterministically remove each optional provider and low-confidence/contextual
   edge class one at a time.
4. Record required-set invariance and attributable contextual deltas.
5. Bind comparison evidence to source, graph, policy/rule, provider, and analysis
   digests.
6. Aggregate counts without source bodies or repository identity.

Gate: zero unexplained narrower required results, zero required-obligation changes
under optional perturbations, and no hidden incomplete state.

Verification:

```bash
python3 -m pytest tests/test_graph_shadow.py tests/test_contextual_impact.py tests/test_evals_runner.py -q
```

### CI-6: Shadow Observation And Decision (minimum 20 accepted cases)

Files:

- `docs/contextual-impact-shadow-register.jsonl` (new)
- `docs/contextual-impact-graduation.md` (new after collection)

Admission requires CI-0 through CI-5 passing. Each accepted case records corpus
class, immutable identities, oracle labels, differences, latency, output size,
and reviewer classification. Repeated unchanged runs and synthetic-only cases do
not count toward the minimum.

Promotion to default advisory presentation requires:

1. zero unexplained missed or demoted required impacts;
2. zero required-obligation instability under optional perturbations;
3. 100% explanation and recovery-action completeness;
4. byte-identical deterministic replay for identical inputs;
5. held-out contextual precision at 10 at least 10% relatively above stable-key
   ordering, or a separately approved product-value threshold;
6. p95 contextual-analysis overhead at most 20% over graph construction plus
   closure, and default output at most 2 KiB; and
7. explicit operator approval per consumer.

Failure of an integrity threshold blocks promotion. Missing evidence is
`INCONCLUSIVE`, not success. Rollback is disabling/removing the explicit
contextual option; the unchanged P47 path remains available.

### CI-7: Optional Model Experiment (deferred, separately authorized)

Only after CI-6 identifies persistent high-value residual noise may a model
reranker be proposed. It receives bounded canonical candidate metadata, never
source bodies by default. Model, provider, prompt, parameters, input, output, and
selection digests are retained. The deterministic required set and exit status
are immutable. Failure falls back visibly to deterministic ordering.

This experiment cannot produce obligations, PASS, exclusions, suppression, or
enforcement. Promotion requires a powered paired held-out study, a privacy and
threat-model review, explicit cost/latency bounds, and separate approval.

## 6. Blast Radius

Direct runtime risk:

- `fettle/hypergraph.py`: edge ownership and incidence interpretation.
- `fettle/providers/`: provider identity, completeness, and deterministic output.
- `fettle/traversal_rules.py`: closure and obligation identity semantics.
- `fettle/graph_cli.py` and `fettle/cli.py`: public human/JSON/exit contracts.
- `fettle/graph_shadow.py`: parity evidence and promotion decisions.

Indirect risk:

- graph generation digest changes if provider metadata enters canonical output;
- tests or automation consuming P47 `affected` ordering;
- future topology, verification, CI obligations, and Assurance consumers;
- performance on high-fanout repositories and disclosure of repository structure.

Before each runtime package:

```bash
kgraph index
kgraph impact fettle/hypergraph.py fettle/graph_builder.py fettle/traversal_rules.py fettle/graph_cli.py
```

Review provider, graph-shadow, topology, verification, and evidence call sites
from that fresh result. Do not rely on the earlier stale index.

## 7. Security, Privacy, And Failure Rules

- Normalize and validate repository-relative paths; no path escape or source-body
  inclusion in telemetry.
- Bound path count, depth, fan-out, result count, diagnostics, and output bytes.
- Reject malformed and conflicting canonical metadata before analysis.
- Keep model/network use disabled by default and absent from deterministic phases.
- Never treat provider absence, timeout, parse error, or truncation as no impact.
- Digest-bind every comparison and retained result to exact source, graph, policy,
  rule, providers, and implementation.

## 8. Overall Verification And Completion

### Execution Evidence (2026-09-09, superseded baseline)

- All eight frozen scenarios reproduced their expected state and required-impact
  labels, including incomplete, conflicting-provider, cycle, hyperedge, and
  bounded cases.
- Development precision at 10: ranker 10,000 basis points; stable-key baseline
  10,000 basis points; relative gain 0%.
- Held-out precision at 10: ranker 10,000 basis points; stable-key baseline
  10,000 basis points; relative gain 0% across four held-out cases.
- The frozen corpus has no irrelevant contextual candidates, so it establishes
  required recall and deterministic behavior but cannot demonstrate ranking lift.
- This initial run did not pass CI-3's 10% relative-gain gate. The explicit
  `--contextual` command remains experimental and advisory-only; CI-6 promotion
  and CI-7 model work remain blocked.
- Corpus-v2 evaluation infrastructure now derives stable-key baseline and ranker
  orderings from one candidate universe, rejects development/held-out group
  leakage, and requires discriminating labels and immutable case identities.
- The corpus-v2 draft collected 20 intended development cases and 20 intended
  held-out cases from Fettle, AlphaAgent, and AlphaOS history. Its 13 subsystem
  groups do not cross splits. Review showed that not all collected cases met the
  predeclared ranking-eligibility floor. Rank-blind packets are retained in
  `docs/contextual-impact-corpus/`.
- Corpus-v2 reconciliation resolved all 434 disagreements across 37 cases. After
  applying the predeclared minimum of two relevant and two irrelevant candidates,
  only 10 development and 7 held-out cases remained ranking-eligible, below the
  required 20 per split. Labels were not altered to satisfy the threshold.
- The frozen held-out result was ranker precision 2,000 basis points versus 1,714
  for stable-key ordering, a 1,669-basis-point relative gain. Its paired 95% gain
  interval was 0 to 571 basis points, so improvement was not established.
- Held-out required-impact recall was 7,805 basis points, below the mandatory
  10,000. This independently falsifies promotion. The complete machine-readable
  result is retained in `docs/contextual-impact-corpus/evaluation.json`.
- Full automated verification passed after the unrelated Assurance regression
  was resolved.

After every accepted package run focused tests, then:

```bash
python3 -m pytest -q
ruff check fettle tests
fettle check --all
git diff --check
fettle completion validate
```

Completion means the approved advisory scope and its evidence pass. It does not
authorize default-on behavior, Assurance consumption, obligations, CI blocking,
or any model experiment. Each is a separate promotion decision with rollback.
