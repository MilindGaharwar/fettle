# Stage A — Policy Continuity Across Delegation (WP-156..158, WP-162)

Design doc for v1.4.0 Pillar A of [fettle-v14-multiagent-plan.md](../fettle-v14-multiagent-plan.md).
Slices A0–A7, each a local commit. Written 2026-08-02.

---

## 1. Threat model — and its honest boundary

**In scope: negligent delegation.** An executor agent spawns a child agent
(Claude Task subagent, `codex exec`, `gemini -p`, `opencode run`) and the
child runs under weaker policy than the parent — because policy is
repo-anchored (`.fettle.toml` discovered from cwd) while delegation is not.
Verified escape routes today:

- E1: child spawned in a cwd outside the repo → `load_config` finds no
  `.fettle.toml` → defaults (most gates off).
- E2: child launched with permission-bypass flags
  (`--dangerously-skip-permissions`, `--yolo`, `--full-auto`) on a machine
  where `fettle init <runtime>` was never run → no hooks at all.
- E3: child (or parent, composing the child's env) sets
  `FETTLE_GATE_MODE=off` — the emergency kill switch is an unauthenticated
  env var.
- E4: no lineage — even when a child *is* governed, nothing records that its
  session descends from the parent's, so audits cannot answer "was all work
  in this release made under org policy, including sub-agents?"

**Out of scope: a malicious parent.** The parent composes the child's entire
environment; a truly adversarial parent can strip `FETTLE_POLICY_CAPSULE`,
unset `PATH`, or binary-patch the child. Fettle's counter to that class is
not runtime machinery — it is the *downstream* chokepoints (pre-commit, CI
gate, `report --lineage` flagging capsule-less sessions in enforce repos).
We state this plainly in docs; pretending otherwise would be security
theater. The same posture OWASP ASI takes: mitigate orchestration-level
negligence in-band, detect adversarial gaps out-of-band.

## 2. The capsule (WP-156, slices A1–A3)

A **policy capsule** is a content-addressed snapshot of the parent's
effective merged policy (defaults → org `[extends]` → repo → env), written
at spawn time and handed to children by env var.

### 2.1 Format

```
$XDG_STATE_HOME/fettle/capsules/<digest16>.json     (FETTLE_STATE_DIR honored)
{
  "fettle_capsule": 1,
  "digest": "<sha256 hex of canonical-JSON policy body>",
  "policy": { ...effective merged config, gates+severity+rules+boundary... },
  "origin": {
    "repo_root": "/abs/path", "repo": "basename",
    "session_id": "...", "created_at": "ISO-8601",
    "fettle_version": "1.4.0"
  },
  "lineage": ["<parent capsule digest16>", ...]   # oldest first, max depth 16
}
```

- Canonical JSON = `json.dumps(policy, sort_keys=True, separators=(",", ":"))`.
  Digest covers **only** the `policy` body (origin/lineage are provenance,
  not policy — they may differ between re-serializations without changing
  what is enforced).
- Filename = first 16 hex chars of digest. Env var
  `FETTLE_POLICY_CAPSULE=<absolute path>` carries it.
- **D-A1 (versioning):** `fettle_capsule` is an int, bumped only on
  incompatible schema change. A reader seeing an *unknown newer* version
  does not treat it as tampering (mixed-version fleets are normal): capsule
  is ignored, a loud stderr line + `capsule_version_skew` advisory finding
  is emitted. Tampering (digest mismatch, filename/digest mismatch,
  unparseable JSON at a path the env asserts exists) **fails closed** —
  block on Pre.

### 2.2 Verification & resolution — `fettle/policy_capsule.py`

```python
write_capsule(policy, origin, lineage) -> Path          # atomic tmp+rename
resolve_env_capsule() -> tuple[dict|None, str]          # (capsule, err)
verify(capsule_doc) -> str                              # "" ok | reason
merge_for_child(capsule_policy, local_effective) -> tuple[dict, list[Finding-ish]]
```

`resolve_env_capsule` outcomes: no env → `(None, "")` (normal solo mode);
env set but file missing/unreadable/tampered → `(None, "<reason>")` — the
non-empty reason is what the guard check (2.4) blocks on.

### 2.3 Monotonic merge — the load-bearing semantics (slice A2)

Child effective policy = `merge_for_child(capsule.policy, local_effective)`.
**Default rule: the capsule wins.** A child may deviate only in the
*stricter* direction, per key class:

| Key class | Membership | Rule |
|---|---|---|
| Gate modes | `gates.*.mode` | ladder `off/silent/none/report(0) < advisory(1) < soft/enforce/strict(2)`; effective = max |
| Enable flags | `gates.*.enabled` | `True` wins (more enforcement) |
| Directed numerics | explicit `STRICTER_DIRECTION` table, e.g. `complexity.max_cyclomatic: "min"`, `coverage.threshold: "max"`, `loop_detect.threshold: "min"` | take the stricter end |
| Loosening lists | `exempt_paths`, `allow_patterns`, `allow_commands`, `paths.ignore` | capsule wins outright — additions weaken (**D-A2**: yes, a child adding `exempt_paths` weakens policy) |
| Everything else | strings, dicts, unclassified numerics | capsule wins |

Every ignored child deviation is surfaced as an advisory finding
(`capsule_override_ignored`, naming key + both values) — silent policy
correction is its own failure mode. The direction table lives beside
`MODE_ENUMS` in `config_schema.py` style: explicit, tested, and the schema
consistency test guards its key paths against DEFAULTS drift.

**Non-keys:** `paths.trace_dir`, `worktrees.root`, `review.*`, `uat.app_url`
etc. are machine-local plumbing — capsule policy for them is recorded but
the *local* value is used (a child in another checkout must not inherit the
parent's absolute paths). A `PLUMBING_KEYS` allowlist enumerates these; it
is the only place capsule loses by design.

### 2.4 Integration point (slice A3)

`load_config(cwd)` gains, after existing layering:

```
local = defaults → org(cache) → repo → env-mode
capsule, err = resolve_env_capsule()
if capsule: effective = merge_for_child(capsule.policy, local)
```

- One chokepoint covers every surface — dispatcher, `fettle check`,
  quality gates, verify, LSP — because all call `load_config`.
- **D-A3 (env kill switches):** with a verified capsule present,
  `FETTLE_GATE_MODE` may only *strengthen* (off/weakening ignored + finding).
  `FETTLE_DISABLE_DISPATCHER=1` exits before config load and remains an
  acknowledged E-class residual (documented; detectable post-hoc via
  lineage gaps) — closing it would break fettle's own debuggability.
- **D-A4 (tamper handling):** `load_config` cannot block (it returns a
  dict). Verification error → capsule ignored, stderr warning, and the
  error is exposed via `policy_capsule.last_error()` (module-level, set per
  resolution). A new dispatcher check `capsule_guard` (PreToolUse, first in
  registry order, ~1ms) re-resolves and **blocks** on non-empty error —
  independent of whether the repo has any `.fettle.toml` (tampering is the
  attack regardless of venue).

## 3. `fettle spawn` + `[gates.agent_spawn]` (WP-157, slices A4–A5)

### 3.1 The blessed path

`fettle spawn <runner> --task "..." [--worktree ITEM] [--timeout N]`:

1. Load effective config (which may itself already be capsule-derived —
   chains compose: child capsule's `lineage` = parent's lineage + parent's
   digest; depth cap 16, exceeded → refuse).
2. `write_capsule(...)`; export `FETTLE_POLICY_CAPSULE` in the child env
   (subprocess env, not shell export).
3. `--worktree ITEM`: provision via existing `create_worktree` +
   `claim_item`, run child with cwd = worktree.
4. Launch via existing runner registry (`get_runner(name).run(...)` — the
   Stage 13 adapters unchanged; env injection added to `run_cli`).
5. Trace: `log_decision("spawn", "pass", ...)` with lineage fields (§4).

### 3.2 The guarded escape — `[gates.agent_spawn]`

New gate (DEFAULTS: `{"enabled": True, "mode": "advisory"}`; MODE_ENUMS
`{advisory, enforce}`), PreToolUse on Bash commands. Detection patterns
(word-boundary, precision over recall — same philosophy as destructive_guard):

```
claude\s+(-p|--print)\b            codex\s+exec\b
gemini\b.*(\s-p\b|--prompt\b|--yolo\b)      opencode\s+run\b
```

Findings ladder:
- nested launch, `FETTLE_POLICY_CAPSULE` not in the command's env context →
  advisory: "ungoverned agent spawn — use `fettle spawn <runner>`".
- nested launch **with a bypass flag** (`--dangerously-skip-permissions`,
  `--yolo`, `--full-auto`) and no capsule → advisory in `advisory`,
  **block in `enforce`**.
- `env FETTLE_GATE_MODE=off <agent>` composition → same block class.

False-positive guards: skip inside quoted strings/heredocs is *not*
attempted (bash parsing is a tarpit); instead patterns require the agent
binary at a command position (start, after `&&`/`;`/`|`), matching
destructive_guard's proven approach. `fettle doctor` gains a per-runner
hook-parity probe: runner installed but its runtime never `fettle init`-ed
→ warn (E2 visibility).

## 4. Lineage (WP-158, slice A6)

- Trace schema v2 is additive-tolerant: new optional fields
  `parent_session_id`, `capsule_digest` on every record (empty when solo).
  Sources: `FETTLE_PARENT_SESSION` env (set by spawn) + resolved capsule.
  No schema version bump needed (v2 contract: consumers tolerate unknown
  keys); bump to 3 only if a consumer must *rely* on the fields — defer.
- `fettle report --lineage [--days N]`: groups trace by session, builds the
  parent→child forest, renders tree with per-node counts (edits, blocks,
  advisories) and capsule digests. Sessions with edits but no capsule in a
  repo where `agent_spawn.mode = "enforce"` → flagged `UNGOVERNED`.
- Joins `--compliance`: lineage table appended so the auditor's question is
  answerable in one artifact.

## 5. `[worktrees].require` (WP-162, slice A6)

```toml
[worktrees]
root = ".fettle/worktrees"
require = false                      # true → main-worktree edits are gated
exempt_paths = ["docs/**", "**/*.md"]
```

`claims_gate` today returns `allow()` when `not is_linked_worktree(cwd)`.
New behavior when `require = true`: main-worktree edit to a non-exempt path
→ finding `main-worktree edit requires a work-item worktree — fettle
worktree create <id> && fettle work claim <id>`, honoring
`gates.claims.mode` (advisory default, enforce blocks). Everything else
(claims semantics inside worktrees) unchanged. `topology apply` (v1.4.x)
will set `require = true` in its managed repos.

## 6. Slice A0 — the red test (evidence-first)

`tests/test_policy_continuity_e2e.py` — deterministic delegation-chain
test, **xfail(strict=False) until A3 lands, then flips to pass** (the
commit that lands A3 removes the marker):

1. tmp "org repo" with `.fettle.toml`: `lint.mode="enforce"`,
   `agent_spawn.mode="enforce"`.
2. Simulated parent: `load_config(repo)` → `write_capsule(...)`.
3. Simulated child: `subprocess.run([sys.executable, "-m", "fettle", "check", f.py],
   cwd=<bare tmp dir with a lint violation>, env={FETTLE_POLICY_CAPSULE: path})`
   → asserts the violation is reported at capsule severity (E1 closed).
4. Tamper the capsule file → child run must fail closed (guard behavior).
5. Env `FETTLE_GATE_MODE=off` + capsule → still enforced (E3 closed).

A live evals scenario (real `codex exec` child) is deliberately deferred to
the v1.4.x topology work — it needs live runners and proves the same
mechanics this test pins deterministically.

## 7. Slice map & decisions index

| Slice | Ships | Tests |
|---|---|---|
| A0 | red e2e (xfail) | 3 asserts above |
| A1 | policy_capsule.py write/resolve/verify | round-trip, tamper, version-skew, atomicity, depth cap |
| A2 | merge_for_child + STRICTER_DIRECTION + PLUMBING_KEYS | merge matrix per key class, override-ignored findings |
| A3 | load_config integration + capsule_guard check + FETTLE_GATE_MODE neutering | e2e flips green; cwd-escape; guard block |
| A4 | `fettle spawn` + runner env injection + FETTLE_PARENT_SESSION | FakeRunner e2e: env, worktree, claim, trace |
| A5 | [gates.agent_spawn] + doctor runner-parity probe + schema regen | pattern fixtures per runner (violating+clean), bypass-flag block |
| A6 | lineage trace fields + report --lineage + [worktrees].require + schema regen | 3-level forest; UNGOVERNED flag; require gate matrix |
| A7 | CHANGELOG, CONFIG.md, README; version 1.4.0 | docs claims verified against code |

Decisions: **D-A1** version skew ≠ tamper (ignore + warn) · **D-A2** list
additions weaken → capsule wins · **D-A3** kill-switch env vars can only
strengthen under capsule · **D-A4** guard check blocks on tamper even with
no repo config · **D-A5** plumbing keys stay local · **D-A6** lineage depth
cap 16 · **D-A7** trace stays schema v2 (additive fields).
