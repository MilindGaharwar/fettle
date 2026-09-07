# Hypothesis Tree: Evidence-Guided Handoffs

**Objective:** improve independently verified agent changes without making Fettle
an orchestrator

**Primary metrics:** regression escape rate, verified completion rate, and cost
per verified change

**Best score:** not measured

**Status:** planning complete; execution blocked by CS-6 and separate approval

---

- **ROOT** [ACTIVE]: Harness-neutral, evidence-guided handoffs improve verified
  software changes at bounded cost.
  - Constraint: Fettle validates authority and evidence; supported hosts retain
    agent scheduling, reasoning, retries, and implementation strategy.
  - Constraint: Missing, stale, malformed, conflicting, or mixed-candidate
    evidence remains non-pass.
  - Constraint: The HoH paper motivates but does not establish local causality;
    the pilot requires matched real changes and retained evidence.
  - **1** [SELECTED, BLOCKED]: Validate candidate-bound handoffs and preservation
    obligations using existing canonical evidence.
    - Hypothesis: Explicit candidate, objective, acceptance, and preservation
      bindings will reduce regression escapes or improve verified completion
      because later roles no longer reconstruct validated state from prose.
    - Falsification: any candidate-binding false accept; a higher observed
      regression escape rate; neither a 10-point verified-completion gain nor a
      25% relative regression reduction; median wall-clock overhead above 20%;
      median token overhead above 25%; or recovery success below 90%.
    - Evidence needed: 20 accepted matched pairs across at least two hosts and two
      task classes, under the frozen protocol in the implementation plan.
  - **2** [DEFERRED]: Improve only host guidance and prompt templates.
    - Hypothesis: Better role prompts may improve outcomes without a runtime
      contract because agents can self-maintain the required state.
    - Falsification: stale or mixed-candidate evidence remains undetectable, or
      prompt-only treatment does not improve verified outcomes under matched work.
    - Constraint: This cannot become an authority mechanism because prose is not
      independently verifiable.
  - **3** [PRUNED]: Build a Fettle-owned planner-developer-QA loop.
    - Evidence: Fettle's approved product position explicitly excludes becoming a
      general agent orchestrator; existing hosts already own invocation.
    - Insight: Adopt HoH's outcome contracts at Fettle's assurance boundary, not
      its scheduler topology.
  - **4** [PRUNED]: Add persistent semantic project memory before the pilot.
    - Evidence: repository artifacts, canonical references, Git history, and
      progressive disclosure can represent the proposed state without a new
      authority-bearing database.
    - Insight: Persistence is an optimization requiring measured admission, not
      a prerequisite for evidence continuity.

## Convergence Rule

- If node 1 passes all integrity and operational thresholds, propose an advisory
  integration; do not enable enforcement automatically.
- If integrity holds but the effect estimate is inconclusive, refine one causal
  mechanism and freeze a new pilot before collecting more data.
- If node 1 fails an integrity threshold or worsens regression escapes, prune it.
- After three non-improving contract variants, move up to the root and reconsider
  whether handoff validation is the correct intervention rather than tuning the
  schema further.
