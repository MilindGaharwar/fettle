# Hypothesis Tree: Plain-English Software Quality Review

**Objective:** enable a non-engineer to judge one software change's intended
behavior, implemented logic, evidence, risks, and readiness without treating an
AI explanation as proof

**Primary metrics:** correct user classification of `ready`, `not ready`, and
`unknown`; false-ready rate; time to identify the highest-severity unresolved
risk; and successful completion of the recommended next action

**Best score:** not measured

**Status:** planning complete; no experiment or implementation authorized

---

- **ROOT** [ACTIVE]: A plain-English, evidence-linked assurance case will let
  non-engineers review vibe-coded changes more accurately than raw CLI output or
  an ungrounded AI code review.
  - Constraint: Fettle remains the decision and evidence authority. Generated
    prose and diagrams are advisory projections.
  - Constraint: Missing, stale, malformed, contradictory, skipped, or
    inapplicable-without-reason evidence remains visible and non-pass.
  - Constraint: No numeric quality score may hide dimension-level failures or
    unknowns.
  - Constraint: The review must reuse existing public Fettle outputs before
    proposing a new producer, scanner, database, or hosted service.
  - **1** [SELECTED, BLOCKED]: Generate one local, read-only assurance case from
    existing canonical and diagnostic Fettle outputs.
    - Hypothesis: A change-centered summary plus claim-to-evidence map will let
      target users correctly classify at least 90% of seeded review cases, with
      zero false-ready decisions, because intent, evidence, and unknowns are
      presented together in user language.
    - Falsification: any false-ready classification; less than 90% correct
      classification; median time above five minutes; or more than 10% of users
      cannot identify the first recommended recovery action.
    - Evidence needed: at least five representative changes and ten blinded
      review sessions, including clean, failed, stale, contradictory, and
      incomplete evidence cases.
    - Blocker: separate operator authorization for WP-FR-1 or later.
  - **2** [DEFERRED]: Improve only the existing terminal renderers.
    - Hypothesis: Better `assurance`, `explain`, and `brief` wording may provide
      enough comprehension without a composed report.
    - Falsification: users still have to correlate multiple commands or cannot
      connect a requirement to code, tests, and observed outcomes.
  - **3** [DEFERRED]: Add an AI-only conversational code reviewer.
    - Hypothesis: Natural-language interrogation may be easier than a structured
      report because users can ask follow-up questions.
    - Falsification: model claims cannot be traced to evidence, repeated runs
      disagree materially, or plausible prose creates a false-ready decision.
    - Constraint: this can supplement the assurance case, never replace its
      deterministic facts and explicit unknowns.
  - **4** [PRUNED]: Use imported agent trajectories as the primary explanation
    source.
    - Evidence: trajectories describe agent activity, not whether requirements
      are correct or software behavior is verified; raw content also creates
      material privacy and provenance risk.
    - Insight: explain the resulting change and its evidence, not the model's
      private reasoning path.
  - **5** [PRUNED]: Present one aggregate quality score.
    - Evidence: a weighted score can conceal a critical security failure or turn
      missing evidence into apparent partial credit.
    - Insight: preserve dimension states and release-policy decisions; summarize
      them in prose without inventing a new authority.

## Convergence Rule

- If node 1 meets all comprehension and zero-false-ready thresholds, propose the
  smallest retained review surface that passed the study.
- If terminal-only output performs equally well, prune the HTML surface.
- If interpretation errors cluster around generated logic explanations, retain
  deterministic evidence views and remove or narrow AI prose.
- After three non-improving presentation variants, reconsider whether missing
  evidence or unclear requirements, rather than presentation, is the root cause.
