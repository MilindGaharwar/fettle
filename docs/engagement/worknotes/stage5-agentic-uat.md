# Work notes — Stage 5: Agentic UAT (WP3)

Design: docs/engagement/10-stage5-agentic-uat.md. Commits: 031d368 (S5.1),
17df3e4 (S5.2), bcdf784 (S5.3), 07f8fc0 (S5.4), 44c6e8f (S5.5), S5.6 docs.

## Decisions

- **D-S5.1 — Surface detection is evidence-carrying and overridable.**
  Deterministic markers only (pyproject scripts, package.json bin/deps,
  framework regexes, templates dir); each surface reports its evidence
  string. `[uat].surfaces` overrides detection entirely; unknown names
  are a hard usage error (exit 2), never silently skipped.
- **D-S5.2 — Every capability gap is a three-part contract**: what's not
  possible, why, exact fix, and numbered manual steps (operator
  requirement 4). Rendered identically in `uat doctor` and run errors.
- **D-S5.3 — Persona prompt distrusts the repo**: agent is told it has
  never seen the codebase, must not read source or fix anything, and has
  an honest-failure channel (`OUTCOME: could-not-attempt`). Structured
  SCENARIO/OBSERVED/OUTCOME blocks make reconciliation parseable without
  trusting free prose.
- **D-S5.4 — UNOBSERVED is first-class.** A scenario the agent never
  reported on is a gap, not a pass. Exit 0 from `uat run` requires all
  verdicts CONFIRMED.
- **D-S5.5 — Auto-answer detection**: a "matches" outcome whose OBSERVED
  is empty or merely parrots the Then-expectation downgrades to
  INDETERMINATE. Agent claims are never taken at face value.
- **D-S5.6 — Consent is explicit** (`--yes`): sessions run an agent with
  permission checks disabled; the refusal message states exactly what
  will happen (operator requirement 3).
- **D-S5.7 — Operator evidence is a labeled peer** (`source: operator`),
  never mixed with agent evidence. Attestations without observed
  evidence are rejected.
- **D-S5.8 — Secrets never persist through transcripts**: boundary
  scanner runs before persisting; suspect lines are replaced with a
  REDACTED marker and counted in the checkpoint.
- **D-S5.9 — Web is an optional extra** (`finefettle[uat]` → playwright);
  core stays stdlib-only. Without it, errors point to both the extra and
  `fettle uat manual`.
- **D-S5.10 — `[uat].mode` only supports `report`** for now: gating on
  UAT verdicts waits until evidence accrues that verdicts are stable
  (advisory→gate graduation pattern, WP1 #7).

## Deferrals

- Stop-event bdd sweep (D-S3.4): still deferred — the reconciler gives a
  richer end-of-session accounting than a Stop-event sweep would; revisit
  only if sessions show scenario drift the bdd gate misses.
- Evaluator-optimizer loop over UAT verdicts (WP1 #5), multi-persona
  sessions, CI-mode UAT: after Stage 6/7.
- `api` surface currently uses the same runner-driven flow as `cli`
  (agent calls the API with curl etc.); dedicated HTTP-level drivers only
  if evidence shows the generic flow is insufficient.
