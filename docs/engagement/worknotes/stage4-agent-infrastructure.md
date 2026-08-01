# Work note — Stage 4: agent infrastructure (WP7 + WP5 + runners)

Commits: 8d2cad4 (design), ec9c5a8 (S4.1), be6605e (S4.2), 178e22c (S4.3),
this commit (S4.4). Design doc: 09-stage4-worktrees-coordination-runners.md.

## What shipped

- **S4.1 — fettle.runners**: outbound AgentRunner protocol mirroring the
  inbound fettle.agents pattern (WP-140). RunnerResult carries a
  fail-visible `error` field (partial transcripts kept — evidence over
  tidiness). Claude adapter extracted from `evals_runner._claude_runner`;
  evals_runner consumes the protocol, plain-callable test seam preserved.
- **S4.2 — worktree spine**: `fettle worktree create|list|remove`; one
  worktree per work item under `[worktrees].root` (default
  `.fettle/worktrees`), branch `fettle/<item-id>`. Removal refuses when
  dirty; `--force` exists but is never default; branches always kept.
  `.git`-as-file audit fixed trace._repo_name (isdir → exists) and
  doctor's hook checks (hooks live in the git *common* dir).
- **S4.3 — work items + claims + [gates.claims]**: Wayfinder model —
  items are committed markdown knowledge (`fettle-work-item` frontmatter
  key, index-vs-store, Resolution expected on done); claims are runtime
  state in `<git-common-dir>/fettle/claims.json` visible to every
  worktree. Gate: unclaimed edit in a fettle-managed worktree →
  advisory naming the exact fix.

## Decisions

- **D-S4.1** Runner failures return, never raise; evals maps a runner
  error to INDETERMINATE (broken experiment ≠ failed behavior).
- **D-S4.2** Adapters beyond claude land only with conformance fixtures
  (D4 coverage list stands; no aspirational stubs).
- **D-S4.3** Worktree removal never deletes the branch — unmerged work
  is the operator's call, not a cleanup side effect.
- **D-S4.4** Fettle-managed = branch starts with `fettle/` (robust to
  worktree relocation; no path heuristics).
- **D-S4.5** Main worktree is always exempt from [gates.claims] — the
  solo flow must stay frictionless; coordination cost only where
  coordination happens.
- **D-S4.6** Stale claim = claiming worktree no longer exists →
  silently takeable (Wayfinder "unclaimed = takeable").
- **D-S4.7** Worklog model: per-item notes are the documented default;
  daily [gates.worklog] stays for repos using it (docs-only deprecation,
  no code removal this stage).

## Verification

- 49 new tests (12 runners + 16 worktrees + 21 work items/claims/gate),
  real tmp git repos for worktree/claim lifecycles; schema anti-drift
  pin covers both new mode enums. Guard chain green on every commit;
  full suite on push.

## Follow-ups

- Wayfinder gate candidates not adopted (decision-duplication,
  out-of-scope resumption) — recorded in 04, revisit post-UAT.
- `fettle work show <id>` and INDEX.md divergence lint — when usage
  patterns exist (Stage 5 will generate them).
- Runner capability matrix grows as adapters land (codex, gemini,
  opencode, antigravity).
