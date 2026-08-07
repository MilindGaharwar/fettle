# Hypothesis Tree: Complete full mutation evidence within 35 minutes without weakening mutation scope

**Metric:** successful full-run duration_ms <= 2100000 with valid nonzero outcomes
**Best Score:** None (node None)
**Nodes:** 4 total | 0 merged | 1 pruned
**Created:** 2026-08-07

---

- **ROOT** [ACTIVE]: Complete full mutation evidence within 35 minutes without weakening mutation scope
  - Constraint: Dependency-selected pytest-testmon execution did not complete full mutation scope within 1,800 seconds.
  - **1** [PRUNED]: Use mutmut's pytest-testmon integration to select dependency-relevant tests per mutant; falsified if the full report remains incomplete or exceeds 2,100,000 ms
    - Evidence: Run `31193102459` at revision `a56c68c452b60a6e697e3b41853a79556c711910` retained `tool_error`: "Mutation run timed out after 1800s".
    - Insight: Test dependency selection alone is insufficient to bound a repository-wide mutmut run; measure total completion time before sizing independently bounded shards.
  - **2** [SELECTED]: Shard the complete production file set into independently bounded reports and aggregate outcomes; falsified if aggregation cannot prove complete, non-overlapping scope
  - **3** [PENDING]: Use coverage contexts to select tests per mutant with full-suite survivor confirmation; falsified if contexts are incomplete or runtime remains above 2,100,000 ms
