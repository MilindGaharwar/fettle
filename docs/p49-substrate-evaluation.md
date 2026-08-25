# P49 Substrate Evaluation — Evidence Ledger as Durable Commit-Linked Evidence

Date: 2026-08-24 · Status: RECOMMENDED — gap 1 implemented (coverage field + tests)
Decision owner: Milind · Unblocks: P49 CI obligations & graph-bound attestations

## Question

P49's dependency is "P41, or an approved successor, supplying durable
commit-linked evidence." The original P41 scope included six slices; the new
`fettle/evidence_ledger.py` implements a subset. Does the ledger satisfy the
requirement?

## Evaluation against P41's acceptance criteria

| Original criterion | Ledger today | Verdict |
|---|---|---|
| Editing/deleting middle record breaks verification | `verify_chain` pinpoints exact sequence on edit or delete | ✅ |
| Commits identify governing evidence when Fettle owns the flow | `anchor()` binds terminal digest to HEAD; `verify_anchor` distinguishes growth from divergence | ✅ |
| Externally created commits report coverage unknown | Anchors require a resolvable commit; non-repo roots return `tool_error`; no anchor → status `unanchored` | ⚠️ partial — add explicit `coverage: unknown` field for externally-committed flows |
| Secrets / raw prompts not persisted by default | Secret-like keys and model-output dropped at append time | ✅ |
| Tamper-evident, not immutable | Documented posture; rotation preserves continuity via checkpoints + retention metadata | ✅ |

## Gaps before P49 may rely on it

1. **Coverage field** — add `coverage: known | unknown` to anchor records so
   external-commit flows are explicitly marked rather than silently absent.
2. **Query surface** — `read_ledger` returns raw records; P49 needs
   filter-by-kind / since-anchor helpers (small).
3. **CI artifact anchoring** — optionally accept an artifact URL as an
   alternative anchor target alongside commits.

## Recommendation

Approve `evidence_ledger.py` as **the approved successor to original-P41**
for durable governance evidence, Gap 1 (explicit coverage field) is now implemented and tested.
Slices 4–6 of the original plan remain separately gated advisory features,
unchanged. On ratification, update the evolution-plan row for P41 to
"Complete via successor (`evidence_ledger`)" and flip P49's dependency to
satisfied.

## Rollback

The ledger is additive; reverting is a file deletion per repository. No
existing authority consumes it yet.
