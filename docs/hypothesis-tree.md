# Hypothesis Tree: Complete full mutation evidence within 35 minutes without weakening mutation scope

**Metric:** successful full-run duration_ms <= 2100000 with valid nonzero outcomes
**Best Score:** None (node None)
**Nodes:** 4 total | 0 merged | 0 pruned
**Created:** 2026-08-07

---

- **ROOT** [ACTIVE]: Complete full mutation evidence within 35 minutes without weakening mutation scope
  - **1** [RUNNING]: Use mutmut's pytest-testmon integration to select dependency-relevant tests per mutant; falsified if the full report remains incomplete or exceeds 2,100,000 ms
  - **2** [PENDING]: Shard the complete production file set into independently bounded reports and aggregate outcomes; falsified if aggregation cannot prove complete, non-overlapping scope
  - **3** [PENDING]: Use coverage contexts to select tests per mutant with full-suite survivor confirmation; falsified if contexts are incomplete or runtime remains above 2,100,000 ms
