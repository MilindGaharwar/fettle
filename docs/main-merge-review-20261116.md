# Audit branch integration into current main — 16 November 2026

Review base: main `55a40b6`; audit branch `b3d6f07`.
The audit history predates squashed integration PRs #46/#47 and subsequent main
work. The 30 main-only commits include D4 close-out, source verification,
installed-hook trust tests and the November 14 owner sequencing decision.
Those decisions and implementations are preserved.

## Resolution policy and scope

Resolved 53 conflicting paths in an isolated worktree. Current main's mutation
engine, PR advisory workflow, immutable test mappings, worklog, D4 acceptance,
installed-artifact fixtures and refactored tests supersede older audit versions.
No workflow, mutation engine, trust gate or version downgrade is introduced.
Main's TODO, roadmap and program-index sequencing remains authoritative. WLI is
owned by TR-5; the November 14 discipline decision supersedes earlier pilot
scheduling. Historical audit-branch review records describe their own candidates.
Publication annotations explicitly retain that precedence.

Retained scanner changes require Semgrep >=1.185 and a finite 600-second full
scan budget, with timeout still a non-pass; parser/budget regression tests cover
that boundary. Native sandbox tests qualify an interpreter that can actually
start under the unchanged policy before asserting forbidden operations. Two
additional staged-preflight tests retain whole-corpus aggregation and explicit
representation-inventory/tamper coverage. Main's newer tests are preserved.

Formal-plan tables retain the reviewed method and negative-case corrections.
Proposed plans remain proposals, not new implementation approval. Existing
completion evidence and failed mutation qualification are not promoted.

## Validation and publication

The candidate receives focused scanner, staged-preflight, UAT, distribution and
documentation tests; full Fettle, completion and privacy checks; whitespace and
staged local-link checks. Exact outcomes are retained with the PR. VM/Docker
qualification in the audit history applies to `4030de0`, not automatically to
this new main merge candidate. No repeated live qualification is claimed here.

Main requires `CI required` and `mutation evidence`, strict up-to-date status,
and applies protection to administrators. This integration must pass through a
PR and those required checks. No force push, admin override, suppressed finding,
private history or unrelated dirty work is permitted. Local originals and the
117 protected packet/answer hashes are checked separately.

Local results: full Fettle scan passed across 432 files with zero findings/tool
errors; completion validation passed; privacy scrub and whitespace checks passed;
264 local Markdown links/anchors resolved in the staged candidate. Focused test
results are retained in the PR. Live VM/Docker opt-in tests are skipped in this
merge-focused run; their earlier candidate-specific evidence is preserved.

Integration correction: CI matrix pins were still 1.168.0 while the incoming
package requires >=1.185. The three pins now use 1.185.0, with a regression
checking blocking matrix versions against the package floor. Main advisory and
D4 workflows remain intact. A sandboxed local parser recheck failed on missing
certificate trust access; its unchanged trusted rerun is retained separately.

## Owner-released update — 17 November 2026

Fetched and merged main `bf26796946fb76a911d231e1e998df093357e06a`, containing
#78 and #80, without rebasing. Main's mutation advisory exclusions and trust
remediation remain intact; the mutation engine, staged-preflight runtime and
mutation workflows are unchanged relative to that main snapshot. Refreshed the
[status-evidence table](reviews/2026-11-16/status-main-evidence.md) against it.

The first full local suite reported 5,191 passed, 29 skipped and one failure in
the strict mutation-owner mapping assertion. The incoming main already retains
two canonical corpus tests in `tests/test_mutation_corpus.py`; the older audit
branch duplicated them in `tests/test_staged_preflight.py`, adding an unintended
cross-owner import. Both function ASTs were compared and found identical.
Removed only those duplicate copies and their import; the canonical tests and
ownership assertion remain unchanged. This is a test-layout reconciliation,
not a relaxed gate. The corrected head requires fresh full-suite qualification;
this record does not credit the failed run as a pass. No workflow was rerun to
hide the failure, and no remote push had occurred when it was found.
