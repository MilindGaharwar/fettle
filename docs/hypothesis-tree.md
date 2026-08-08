# Hypothesis Tree: Complete full mutation evidence within 35 minutes without weakening mutation scope

**Metric:** successful full-run duration_ms <= 2100000 with valid nonzero outcomes
**Best Score:** 1792060 ms (node 2)
**Nodes:** 4 total | 1 merged | 1 pruned
**Created:** 2026-08-07

---

- **ROOT** [DONE]: Complete full mutation evidence within 35 minutes without weakening mutation scope
  - Constraint: Dependency-selected pytest-testmon execution did not complete full mutation scope within 1,800 seconds.
  - Constraint: A monolithic diagnostic run did not complete within 7,200 seconds; full evidence must execute as independently bounded shards.
  - Constraint: Twelve source-size-balanced shards all exceeded 1,800 seconds; source bytes substantially underpredict mutation work.
  - **1** [PRUNED]: Use mutmut's pytest-testmon integration to select dependency-relevant tests per mutant; falsified if the full report remains incomplete or exceeds 2,100,000 ms
    - Evidence: Run `31193102459` at revision `a56c68c452b60a6e697e3b41853a79556c711910` retained `tool_error`: "Mutation run timed out after 1800s".
    - Insight: Test dependency selection alone is insufficient to bound a repository-wide mutmut run; measure total completion time before sizing independently bounded shards.
  - **2** [MERGED]: Shard the complete production file set into independently bounded reports and aggregate outcomes; falsified if aggregation cannot prove complete, non-overlapping scope
    - Evidence: Diagnostic run `31197332468` at revision `23dec2b14d7a0afc759b223919b31dafc5fab524` retained `tool_error`: "Mutation run timed out after 7200s".
    - Evidence: Held-out run `31209029718` at revision `bbfcdb42fed3f2e3fc956f8a8d63b9f500c83344` retained eleven shard reports, all `tool_error` after 1,800 seconds; shard 8 lost its runner with exit 143 and the aggregate correctly rejected the incomplete set.
    - Insight: File-byte balancing preserves deterministic coverage but does not estimate mutant runtime; refine to 48 independently bounded partitions while retaining exact fail-closed aggregation.
    - Evidence: Run `31246843926` at revision `e3706df3ca4f788482e6e58388eb5cbfab23e6a7` completed all 240 shards and aggregated 154 modules and 30,441 source lines exactly once with zero untested mutants in 1,792,060 ms.
    - Insight: Test-cost-weighted line partitions plus measured hotspot chunking can bound full mutation without weakening scope; aggregate report integrity, not job color, is the acceptance authority.
  - **3** [CANCELLED]: Use coverage contexts to select tests per mutant with full-suite survivor confirmation; the objective was met without adding this complexity
