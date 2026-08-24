---
fettle-work-item: true
id: p41-commit-linked-evidence
status: done
scope:
  - fettle/evidence_ledger.py
  - fettle/cli.py
  - tests/test_evidence_ledger.py
spec: change-integrity-implementation-plan
---

# P41 — Commit-linked governance evidence ledger

## Resolution

Delivered `fettle/evidence_ledger.py`: versioned hash-chained JSONL ledger
(sequence + prev-hash + content hash per record), secret-like payload keys
dropped by default, `verify_chain` pinpointing the first tampered sequence,
`anchor` binding the terminal digest to a repository commit, `verify_anchor`
distinguishing post-anchor growth (normal drift) from prefix divergence
(tampering), and rotation that prunes history through a checkpoint record
while preserving chain continuity plus retention metadata. CLI:
`fettle ledger status|verify|anchor`. Acceptance criteria proven in
tests/test_evidence_ledger.py (10 tests): middle edit/delete breaks at the
exact sequence; commit identifies governing evidence; secrets not persisted.

Scope note: slices 4–6 (loop-detect extension, diff thresholds, token/wall-
clock ceilings) remain separate advisory features per their own gating —
tracked in the evolution plan, not closed by this item.
