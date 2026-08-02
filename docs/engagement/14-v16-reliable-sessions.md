# 14 — v1.6 "Reliable Sessions" (design)

Date: 2026-08-02 · Status: ACTIVE · Prior art: existing `[gates.plan]`
(quality_gate.scan_planning), `[gates.worklog]` (fettle/worklog.py),
`[gates.advisory]` dedup, plan_validator.py (5-phase WP format),
topology.py/topology_apply.py, lineage_report.py, insights.py.

## Problem

Four gaps, one theme — sessions are where reliability is won or lost:

1. Plans and worklogs exist as gates but don't close the loop: the plan
   gate only checks *a recently-touched `*plan*.md` exists*; the worklog
   gate only checks *a daily file exists*. Neither is session-scoped,
   neither reconciles planned-vs-done, and nothing survives context
   compaction in a structured way.
2. `fettle init` is detect-and-scaffold; it never asks the user the
   undetectable questions (team shape, enforcement appetite), so configs
   start generic.
3. Topology advises and provisions but never learns whether the advice
   was good; orchestrators must parse five files to know session state;
   children end without a structured completion report.
4. The blank `fettle` command is a missed front door; doctor diagnoses
   but never fixes; gate messages don't point at `fettle explain`.

## Non-goals

- No new daemon, no background processes — CLI + gates only.
- Advisory dedup: already shipped in `[gates.advisory]` — out of scope.
- plan_validator's 5-phase WP format stays as-is for big plans
  (/plan-activate); session plans are deliberately lighter.
- No policy autonomy changes: everything here is sensing, prompting,
  and reporting; enforcement stays ratchet-governed.

## Slices

### A — Session plans + worklog loop closure

`fettle plan start [--title T]` writes `.fettle/plans/<yyyymmdd>-<slug>.md`:
markdown with `- [ ]` checklist items (frontmatter: `fettle-plan`,
created, session_id). `fettle plan status|check` list/tick items.

Gate changes (extend, don't duplicate):
- `scan_planning` also accepts an *active session plan* (a
  `.fettle/plans/*.md` with unchecked or checked items, mtime within
  `max_age_hours`) — not just `*plan*.md` in docs/.
- `[gates.worklog]` gains `scope = "daily" | "session"` (default daily,
  unchanged). Session scope: today's entry must have been modified
  *during this session* (mtime ≥ session start derived from first trace
  entry of the session), so a morning entry doesn't satisfy an evening
  session.
- New Stop reconciliation (inside worklog check, no new CheckSpec):
  if a session plan is active and has unchecked items at Stop, surface
  them (advisory text: "planned N, done M — confirm or update"). Never
  blocks on *content*, only presence per existing mode.

Decisions:
- D-A1: extend existing gates; no new `[gates.session_plan]` section.
  New keys only: `plan.session_plans = true` (accept .fettle/plans/),
  `worklog.scope`. → schema regen required.
- D-A2: session-plan format is a checklist, validated leniently
  (frontmatter key + ≥1 checkbox); the 5-phase validator is not applied.
- D-A3: plans live in state dir (`.fettle/plans/`), agent-agnostic; any
  of the four agent brands (or a resumed session) reads the same file.
- D-A4: reconciliation is always advisory prose appended to the worklog
  finding; blocking remains governed by worklog.mode.

### B — `fettle init --interactive` + profiles

- TTY interview, ≤5 questions, each mapping to config with an
  explanatory comment in the emitted .fettle.toml:
  1. solo/team → worktrees/claims defaults
  2. enforcement appetite (advisory-first | strict) → gate modes
  3. compliance/secrets sensitivity → security gates + bash_audit
  4. multi-agent planned? → agent_spawn/capsules/worktrees.require
  5. confirm detected stack (languages, CI provider)
- `--profile solo|team|enterprise`: same presets non-interactively;
  non-TTY without --profile keeps today's behavior exactly.
- D-B1: interview writes an *annotated* .fettle.toml (comments per
  choice); never overwrites an existing one without --force.
- D-B2: presets are data (PROFILES dict in init_cmd), tested key-by-key
  against config_schema validation.

### C — Topology outcomes + orchestrator surface

- `fettle topology report`: read-only join of topology manifest
  (git-common-dir/fettle/topology.json) × edits.jsonl per worktree ×
  trace lineage × verify/ci stamps → predicted-vs-actual footprints,
  conflict-prediction precision, ungoverned spawn count, per-child gate
  friction, wall-clock per lineage subtree.
- `fettle brief [--json]`: one poll for orchestrators — active claims,
  per-child last trace status, open advisories/frictions, CI verdict,
  proposal counts (reuses insights internals; no new state).
- Child completion contract: at Stop, a small writer (pattern:
  ci_push_record) appends `.fettle/reports/<session>.json` — session_id,
  parent, claims held/released, files edited, last verify/ci stamp,
  plan items done/total. Synergizer merges structured reports instead of
  transcripts.
- D-C1: completion report is best-effort (never blocks, budget ≤50ms,
  write failures silent-warn like trace).
- D-C2: no speedup *estimates* — report facts (durations, conflicts);
  interpretation stays human/insights.

### D — UX batch

- Bare `fettle` (no subcommand) → dashboard: version, repo, gate modes
  summary, last CI verdict, open proposals, top friction (7d), one
  suggested next action. Replaces bare print_help (help stays at -h).
- `fettle doctor --fix`: mechanical repairs only (create missing state
  dirs, reinstall hook symlinks/commit guards, regenerate stale schema
  pointer) — each fix printed; anything judgmental stays a finding.
- Gate finding texts gain a pointer: "→ fettle explain <CODE>" where an
  explain entry exists (single helper, applied to gates with codes).
- D-D1: dashboard must render in <1s offline (reads state files only;
  CI verdict from cached ci-status.json, never network).

### E — Release v1.6.0

CHANGELOG, README status + roadmap row, ROADMAP row, version bumps,
schema regen (A/B change DEFAULTS), full suite, one push, `fettle ci
wait`. Tagging only on explicit approval.

## Slice order

A → B → C → D → E. Each slice: tests + self-check + local commit.
