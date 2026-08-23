# Hypothesis Tree: Agentic UAT at par with, then stronger than, human UAT

**Metric:** seeded-defect discovery rate ≥ agreed human baseline with zero
false-verdict rate on the P77 benchmark (held-out), plus artifact-bound
reconciliation integrity on adversarial fixtures (dev).
**Best Score:** none yet — tree opened 2026-08-23.
**Nodes:** 7 total | 0 merged | 0 pruned

---

- **ROOT**: Make `fettle uat run` produce acceptance evidence at least as
  trustworthy as a skilled human acceptor, measured on seeded defects.
  - Constraint (external, 2026): agents miss genuinely novel bugs via
    prompt-only exploration; breadth needs structured tours.
  - Constraint (external, 2026): confidently-wrong passes hide better than
    honest failures; self-reported transcripts cannot be trusted alone.
  - Constraint (house): specs define correct; candidates need attestation;
    fail-visible always.

  - **D1** [FRONTIER]: Artifact-bound reconciliation (screenshots, a11y/DOM
    snapshots, HTTP logs) will eliminate false-verdicts because verdicts stop
    depending on agent self-report; falsified if adversarial fixtures still
    reconcile clean with tampered transcripts.
  - **D2** [FRONTIER]: Structured exploration charters (SBTM tours, personas,
    fuzzing) will discover out-of-spec anomalies at rates no scenario-only
    prompt reaches; falsified if charter runs surface no artifact-backed
    anomaly that scenario runs missed across demo apps.
  - **D3** [FRONTIER]: Completing the web driver with per-state accessibility
    capture will match the human strength of lived UI experience; falsified
    if UI-only sessions cannot complete representative scenarios without API
    bypass.
  - **D4** [FRONTIER]: Statefulness probes (persistent profiles, restart/
    interruption, seeded data) will expose persistence defects invisible to
    single-shot sessions; falsified if restart probes find nothing on apps
    with deliberately broken persistence.
  - **D5** [FRONTIER]: An independent evaluator pass over transcript+artifacts
    will catch passes-for-the-wrong-reason the primary reconciler accepts;
    falsified if second-pass precision collapses (flags without artifact
    justification) on adversarial fixtures.
  - **D6** [GATE]: A seeded-defect benchmark with recorded human sessions is
    the only valid parity instrument; insight propagates to every direction:
    dev improvements count only when the held-out benchmark reproduces them.
