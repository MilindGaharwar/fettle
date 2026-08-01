# Stage 4 — Worktrees (WP7), Coordination Substrate (WP5), Runners Protocol

Status: design accepted (Stage 4 approved 2026-08-01) · implements sequencing
stage 4 of 03-open-questions-and-sequencing.md · inputs: 04 (Wayfinder),
05 (Hive/Graphify/Obsidian), 06 (WP1 backlog), decision D4 (runner coverage).

Stage 4 builds the three pieces of agent infrastructure Stage 5's UAT needs:
somewhere isolated to run (worktrees), a shared notion of who is doing what
(work items + claims), and a uniform way to launch a headless agent
(`fettle.runners`). None of them is an orchestrator — that remains an
explicit non-goal (05 §1).

## 1. `fettle.runners` — outbound agent protocol

Mirror of the inbound `fettle.agents` pattern (WP-140), in the outbound
direction. Today the only agent-launch primitive is
`evals_runner._claude_runner` — private, claude-only, hardcoded.

### 1.1 Protocol

```python
@dataclass
class RunnerResult:
    transcript: str          # agent's final output (stdout)
    exit_code: int
    duration_s: float
    error: str = ""          # non-empty → run failed (fail-visible, never raise-and-lose)

class AgentRunner(Protocol):
    name: str                                    # "claude", "codex", ...
    def available(self) -> bool: ...             # binary on PATH + sane
    def run(self, prompt: str, cwd: Path, timeout_s: int) -> RunnerResult: ...
```

- `fettle/runners/__init__.py`: protocol + `get_runner(name)` +
  `detect_runners()` (capability probe, feeds doctor).
- `fettle/runners/claude.py` first (extracted from evals_runner; behavior
  preserved incl. `--dangerously-skip-permissions` + `FETTLE_EVAL_TIMEOUT_S`).
- D4 coverage (codex, gemini cli, antigravity, opencode) lands as adapters
  behind the same protocol; each ships only when a conformance fixture
  exists (no aspirational stubs). A capability matrix lives in this doc's
  work note as adapters land.
- `evals_runner.run_scenario` consumes the protocol (`runner: AgentRunner`);
  its test seams (plain callables) stay supported via a thin shim.
- Timeouts/subprocess failure → `RunnerResult(error=...)`, never a silent
  empty transcript (Stage 0 posture).

## 2. WP7 — worktrees spine (`fettle worktree`)

Isolation substrate for concurrent workstreams and UAT sessions.

### 2.1 Model

- `fettle worktree create <item-id>` → `git worktree add
  .fettle/worktrees/<item-id> -b fettle/<item-id>` (branch from HEAD).
- `fettle worktree list` → path, branch, claimed item, dirty state.
- `fettle worktree remove <item-id>` → refuses when dirty (no destructive
  shortcut); `--force` documented but never default.
- Root configurable: `[worktrees] root = ".fettle/worktrees"`. Default stays
  inside the repo (state travels with the checkout, gitignored by init's
  scaffolding) — scanners and spec/workspace discovery add `.fettle` to
  their skip lists so nested worktrees are never double-scanned.

### 2.2 `.git`-file audit (risk flagged in 03 §C)

In a linked worktree `.git` is a *file* pointing at the common dir.
Audit + fix in this slice: `paths.find_repo_root` (and anything matching
`(p / ".git").is_dir()`) must accept both file and dir; state that must be
shared across worktrees (claims, audit trace) resolves via
`git rev-parse --git-common-dir`, per-worktree state stays local.

## 3. WP5 — coordination substrate (work items + claims)

Adopts the Wayfinder findings (04): index-vs-store separation, claim
semantics, local-first markdown (tracker sync explicitly out of scope).

### 3.1 Format — knowledge versioned with code

- `docs/work/INDEX.md` — index only: one line per item (id, status, gist,
  link). Detail lives in exactly one place:
- `docs/work/items/<id>.md` — frontmatter detected by `fettle-work-item`
  key (same detection philosophy as specs, D-S3.1): `id` (kebab), `status`
  (open | claimed | done), optional `scope` (globs), optional `spec`
  (spec-id link — ties Pillar 5 to Pillar 1). Body: free markdown; a
  `## Resolution` section is expected when status becomes done
  (Wayfinder "resolution recorded on close").
- `fettle work list|show <id>` — read surface; lint (dupes, index/store
  divergence) rides on `fettle work list` like spec lint.

### 3.2 Claims — runtime state, not knowledge

Claims say "session X in worktree Y is working item Z now" — they are
ephemeral coordination state, so they live in the shared git common dir
(`<common-dir>/fettle/claims.json`), never in committed docs. `fettle work
claim <id>` / `release <id>`; claiming an item claimed by a live other
session refuses (unclaimed = takeable, stale claims — worktree gone —
are reclaimable).

### 3.3 Gate: `[gates.claims]` (off by default, advisory-first)

Wayfinder's mechanically-checkable invariant: an edit inside a *linked
fettle worktree* with no claimed item → advisory naming the fix
(`fettle work claim <id>`). Main-worktree edits are exempt (solo flow
must stay frictionless). Mode advisory|enforce in MODE_ENUMS. Other gate
ideas from 04 (decision-duplication, out-of-scope resumption) deferred —
recorded as candidates, not commitments.

### 3.4 Worklog model resolution (open question #10)

Per-work-item notes win: an item's markdown file is its work note. The
daily `[gates.worklog]` stays for repos that use it, but docs stop
recommending both; continuity-traceability plan's per-item model is the
documented default going forward. No code removal in this stage.

## 4. Slices

| Slice | Content | Tests |
|---|---|---|
| S4.1 | `fettle.runners` protocol + claude adapter + evals_runner consumption | protocol conformance, adapter (mocked subprocess), evals regression |
| S4.2 | `fettle/worktrees.py` + `fettle worktree create/list/remove` + `.git`-file audit | tmp-repo worktree lifecycle, dirty-refusal, root-detection with .git file |
| S4.3 | work-item format + `fettle work` CLI + claims + `[gates.claims]` | format lint, claim lifecycle, gate advisory/enforce, MODE_ENUMS pin |
| S4.4 | docs (README/CONFIG), CHANGELOG, work note, TODO | consistency suite |

Deliberate deferrals: tracker sync (out of scope, local-first primary);
codex/gemini/antigravity/opencode adapters (post-conformance-fixture);
decision-duplication + out-of-scope gates (candidates); worklog code
removal (docs-only deprecation this stage).
