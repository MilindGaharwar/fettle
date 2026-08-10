# Hypothesis Tree: Complete full mutation evidence within 35 minutes without weakening mutation scope

**Metric:** successful full-run duration_ms <= 2100000 with valid nonzero outcomes
**Best Score:** 1792060 ms (node 2)
**Nodes:** 5 total | 1 merged | 2 pruned
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
  - **4** [PRUNED]: Use paired full calibration runs to discover remaining engine-detail grammar; falsified if deterministic parser defects invalidate both runs after expensive shard execution
    - Evidence: Runs `31293693197` and `31293694402` exposed a nested mutation test deleting mutmut's live cache; runs `31295617487` and `31295618462` then exposed deletion-only and invalid-Python canonicalization gaps after shard execution.
    - Evidence: A clean local preflight at revision `638520dce7f2526078c50a5e208b00a45b961789` failed closed after its configured 1,800-second bound on 2026-08-09. No replay or calibration was authorized from that result.
    - Insight: Full runs are held-out outcome verification, not efficient mutation-vocabulary discovery. Generate and canonicalize the complete engine-detail corpus first, replay narrow historical failures, and launch the second calibration only after the first is authoritative.
    - Evidence: Replay run `31352719033` repeated preflight before execution, while scheduled run `31357150059` competed for the same repository worker capacity. The replay then exhausted internal capacity in seven shards rather than exposing a parser defect.
    - Insight: Treat preflight as immutable SHA-bound input to replay and calibration, not a repeated stage. Require an explicit retained run ID, verify its revision and shard topology before fanout, keep schedules preflight-only, and serialize authoritative non-PR runs without cancelling retained evidence.
    - Evidence: Preflight `31367078934` on `ea69ec7` failed closed only on shard 242: mutmut mutant 89 represented one triple-quoted f-string mutation as two valid hunks. The exact retained manifest reproduced locally, and the generic multi-hunk fixture repaired all `51 generated == 51 canonicalized` details with zero collisions.
    - Insight: One semantic mutation may span multiple non-overlapping unified-diff hunks. Validate every hunk header and old-side source context, reduce overlapping context to changed segments, reject conflicting edits, and apply accepted edits in reverse source order.
    - Evidence: Retained-evidence replay `31373029137` on `5b8607a` skipped preflight and selected 41 current shards from archived-range intersections. Exactly shard 138 failed: `fettle/init_cmd.py:181-240` consumed about 1,124 seconds before the next module inherited only 676 seconds and timed out.
    - Insight: Mixed-module shard failures must be attributed from sorted execution order and remaining timeout, not the final file named in the timeout. Split the measured `init_cmd.py` hotspot to 20-line chunks while preserving 256 shards and the 1,800-second authority bound.
    - Evidence: Replay `31383363914` on `0cd38f6` proved the `init_cmd.py` split and retained-preflight reuse, then failed only on shards 203 and 206. Sorted execution and remaining budgets attribute them to `coverage_gate.py:181-234` exhausting 1,426 seconds and `ratchet.py:181-240` exhausting 1,263 seconds.
    - Insight: Replay exposes expensive co-located ranges beyond the archived target ranges. Apply the same measured 20-line split only to `coverage_gate.py` and `ratchet.py`; do not raise the 256-shard topology or 1,800-second authority bound.
