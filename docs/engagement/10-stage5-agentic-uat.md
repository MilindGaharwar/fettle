# Stage 5 — Agentic UAT (WP3, the headline)

Status: design (Stage 5 approved 2026-08-01 with operator scope input) ·
inputs: 03 (sequencing), 05 (Hive intervention nodes, checkpoint recovery),
06 (WP1 backlog #5 evaluator-optimizer), Stage 3 (specs), Stage 4
(worktrees, claims, runners) · operator requirements this stage (verbatim
intent, 2026-08-01):

1. **UAT is not backend-only** — it must exercise the app *as an actual
   user would*, including the front end.
2. **Different app types need different UAT options** — the workflow must
   adapt to what is being built.
3. **If user permissions are required, obtaining them is part of the
   enforced workflow** — never bypassed, never auto-answered.
4. **If something is not possible, say so clearly** — and hand the user
   easy-to-read, step-by-step manual instructions for exactly the part
   automation could not cover.

## 1. Core stance

UAT is Fettle's *independent* acceptance layer: it does **not** trust the
repo's own test suite (that is WP2/Stage 3's territory). A UAT session
takes the repo's *active specs* as the contract, explores the running
product the way a user would, and reconciles what it observed against
each spec scenario. Output is an evidence artifact (WP1 backlog #1), not
a feeling.

Non-negotiables inherited: fail-visible (an incomplete session must never
read as clean — Stage 0 posture), minutes-world execution (CLI command,
never the hook dispatcher), stdlib-only core (browser automation is an
optional extra), graceful HITL (a session that auto-answers its own
permission questions is broken by definition).

## 2. Surfaces — requirement 2

A repo declares (or Fettle detects) which *surfaces* a user reaches it
through. Each surface has its own driver, capability probe, and manual
fallback:

| Surface | Detected from | Driver (v1) | Manual fallback |
|---|---|---|---|
| `cli` | console_scripts / bin entries / Makefile run targets | subprocess via fettle.runners agent | numbered command script |
| `api` | FastAPI/Flask/Express/route files, openapi.json | agent + stdlib http probes | curl script per scenario |
| `web` | package.json framework deps, templates/, static/ | agent + Playwright (optional extra `finefettle[uat]`) | click-through script per scenario |
| `library` | importable package, no app entry | agent writes/executes usage snippets | REPL walkthrough |

Config: `[uat] surfaces = ["auto"]` (default) or explicit list;
`app_url`, `start_command`, `runner = "claude"`, `timeout_s`,
`mode` (report-only in this stage). Detection result is always shown and
overridable — never silently guessed wrong.

## 3. Session anatomy

1. **Probe** — `fettle uat doctor`: which surfaces are detectable, which
   drivers are available (runner CLI? playwright? start_command works?).
   Anything missing → requirement-4 messaging (see §5). Exit 2 when the
   requested surface cannot run at all.
2. **Isolate** — provision a fettle worktree (`uat-<timestamp>`), claim
   it (Stage 4 primitives). The product runs from the worktree; the main
   checkout is never touched.
3. **Explore** — the runner agent gets a *persona prompt* built from the
   active specs' scenarios (Given/When/Then → user goals, not test
   scripts) plus surface driver instructions. v0 explorer is naive by
   design: follow the spec's user journeys, note everything surprising.
4. **Checkpoint** — session state (scenario queue, observations so far)
   persists in the worktree (`.fettle/uat-session.json`); a crashed or
   interrupted session resumes, never restarts (Hive checkpoint pattern).
5. **Reconcile** — every observation maps to `<spec-id>/S<n>` where
   possible; each scenario ends CONFIRMED / CONTRADICTED / UNOBSERVED /
   BLOCKED(reason). UNOBSERVED is a first-class verdict — silence is
   never success.
6. **Report** — evidence artifact (JSON) + human summary: per-scenario
   verdicts with the observation trail, everything the session could
   not do and why, and the manual steps handed to the user (§5).

## 4. Permissions & HITL — requirement 3

Interaction points are **intervention nodes** (Hive pattern): explicit
pause + question + timeout + escalation policy, not ad-hoc prompts.

- **Session start is consent**: `fettle uat run` prints what will happen
  (worktree, start_command, agent runner, browser) and requires `--yes`
  or interactive confirmation before anything launches. No silent side
  effects.
- **Privileged steps pause**: anything needing credentials, real
  accounts, destructive-looking flows (payment, deletion, email-sending)
  → the session PAUSES with a numbered request to the operator. Timeout
  → the scenario ends BLOCKED("operator input required: …"), never
  guessed. Secrets are typed by the operator into their own terminal —
  never through the agent transcript.
- **Auto-answer detection**: the reconciler flags transcript patterns
  where the agent answered its own intervention question — that is a
  broken session (INDETERMINATE), not a passed one.

## 5. "Not possible" messaging — requirement 4

Every capability gap produces the same three-part block, human-first:

```
✗ Cannot test the web surface automatically
  Why:  playwright is not installed (optional extra)
  Fix:  pip install 'finefettle[uat]'   — then re-run
  Or do it manually (5 steps, ~3 min):
    1. Start the app:  npm run dev
    2. Open http://localhost:3000/checkout
    3. Add any item to the cart, change its quantity to 3
    4. Expect: the total updates without a page reload   [checkout-flow/S1]
    5. Paste what you saw into: fettle uat attest checkout-flow/S1
```

Manual steps are *generated from the spec scenarios themselves* (GWT →
numbered actions + expectation + scenario id), so the human is executing
the same contract the agent would have. `fettle uat attest` records the
human observation into the same evidence artifact — human and agent
evidence are peers, and attested scenarios are labeled as
operator-attested (provenance, never laundered into "automated").

## 6. Slices

| Slice | Content |
|---|---|
| S5.1 | `[uat]` config + surface detection + `fettle uat doctor` (capability probe with §5 messaging) |
| S5.2 | Session core: worktree provisioning, persona prompt from specs, runner launch, checkpoint file, report schema — `cli`/`api` surfaces first |
| S5.3 | Reconciler: observations → per-scenario verdicts (incl. UNOBSERVED/BLOCKED), auto-answer detection, evidence artifact + human summary |
| S5.4 | Manual-fallback generator + `fettle uat attest` (requirement 4 end-to-end) |
| S5.5 | Web surface via optional Playwright extra + intervention-node pauses (requirements 1+3 end-to-end) |
| S5.6 | Docs, CHANGELOG, work note, TODO |

Deliberate deferrals: evaluator-optimizer loop over UAT findings (WP1 #5,
after v1 evidence exists); multi-persona exploration; CI-mode UAT;
Stop-event bdd sweep integration (D-S3.4 lands when session-end evidence
requirements are defined here — revisit in S5.3).
