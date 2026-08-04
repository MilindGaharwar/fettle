# 17 — v1.7.0 WP-20: Config resolver unification

Status: implemented (this WP)
Inputs: dual-audit finding H-05; owner decision 2026-08-03 (fold layers into
`load_config`; `policy_layers` becomes the provenance engine); WP-15 stopgap
banner in `fettle config --print-effective`.

## 1. Problem

Fettle has two config resolvers that disagree:

| | `config.load_config()` (runtime, 43 call sites) | `policy_layers` (inspection: `fettle config`) |
|---|---|---|
| chain | defaults → remote `[extends]` → repo → env → capsule | defaults → org.toml → team.toml → repo → dir overrides |
| org/team packs | **ignored** | merged |
| remote `[extends]` | merged (cache-only) | **ignored** |
| `FETTLE_GATE_MODE` env | applied | applied only in `load_config_layered` |
| policy capsule | applied (tighten-only) | **ignored** |
| `FETTLE_CONFIG` env | honored | **ignored** |
| directory `.fettle.toml` | **ignored** | discovered via rglob, path-scoped |

Consequences: `--print-effective` can show a config no gate ever runs with
(H-05); org/team packs look like policy but enforce nothing; directory
overrides are documented surface with zero runtime effect.

## 2. Decision

One resolver, owned by `fettle/config.py`. Canonical precedence (later wins):

```
defaults → org.toml → team.toml → remote [extends] → repo (.fettle.toml)
        → directory overrides (path-scoped) → env → capsule (tighten-only)
```

- `load_config(cwd=None, for_path=None)` is the only entry point. Signature
  gains optional `for_path`; all 43 existing call sites remain valid.
- **Directory overrides apply only on path-scoped resolution.** Gates that
  operate on a single file (`post_edit`, `post_edit_ts`) pass
  `for_path=<edited file>`. Pathless callers resolve at root scope — same
  answer as today for repos without directory configs.
- `config.resolve_with_provenance(cwd, for_path) -> (cfg, layers)` exposes
  the same merge with a `PolicyLayer` list (name, source, fragment). Env and
  capsule appear as pseudo-layers whose fragment is the **applied diff**
  (not the raw input), so `--explain` never shows a capsule "winning" a key
  it could not tighten.
- `policy_layers.py` keeps provenance/explain rendering (`explain_config`,
  `_print_explain`) over `resolve_with_provenance`. Its private discovery/
  resolution duplicates and the dead `cmd_policy()` CLI shim are deleted.
  `load_config_layered` remains one release as a thin deprecated alias of
  `load_config`.
- `cmd_config --print-effective` calls the canonical resolver → the WP-15
  H-05 banner is removed. Parity is by construction and locked by a test
  asserting `resolve_with_provenance()[0] == load_config()`.

## 3. Design points

**Directory discovery must not slow hooks.** The old inspection path rglobs
the whole tree. In the runtime path we instead walk **ancestors** of
`for_path` from the file's directory up to (excluding) the repo root — only
those directories' `.fettle.toml` can apply to the file, and it is O(depth)
stat calls instead of O(tree). Ancestor dirs that are hidden or noise
(`node_modules`, `__pycache__`, `.venv`) are skipped, matching the old
rglob filter. The rglob survives only for `--explain`'s "path-scoped layers
present in this repo" listing.

**Remote `[extends]` stays keyed off the repo config** (org/team packs do
not trigger fetches) and stays cache-only in hook paths; only its merge
position is now explicit: under repo, over team.

**org/team `_name`** keys are popped for layer naming before merging (as
before) so they never leak into the effective config.

**`FETTLE_CONFIG`** (alternate repo-config path) is honored by the unified
resolver — fixing a silent inspection/runtime divergence.

**Corrupt layer files** are fail-visible per layer (stderr + skip), never a
silent fall-through to defaults for the other layers.

**Tighten-only stays capsule-only.** org/team/dir merge plainly, like repo.

## 4. Rejected alternatives

- *Make `policy_layers.load_config_layered` the runtime loader:* touches 43
  call sites, loses remote/env/capsule handling, and rglobs on every hook.
- *Full-tree directory discovery at runtime:* latency on large repos for a
  feature most repos don't use; ancestors are sufficient and exact.
- *Provenance objects returned from `load_config` itself:* changes the
  return type at 43 call sites; a parallel `resolve_with_provenance` is
  strictly additive.

## 5. Migration note (CHANGELOG)

`$XDG_CONFIG_HOME/fettle/org.toml` and `team.toml` previously affected only
`fettle config` output; from v1.7.0 they are enforced at runtime by every
gate. Directory `.fettle.toml` files now affect per-file gates. Remove or
audit those files if you relied on them being inert.

## 6. Test plan

- Full-chain precedence test (org < team < remote < repo < dir < env <
  capsule) with all eight layers live.
- Ancestor-walk scoping: file in `src/api/` picks up `src/api/.fettle.toml`
  and `src/.fettle.toml`, deeper wins; sibling dirs and root scope don't.
- Parity: `resolve_with_provenance()[0] == load_config()`; pathless
  `load_config` unchanged vs v1.6.2 for repos without packs.
- `FETTLE_CONFIG` honored; corrupt org.toml skipped fail-visible.
- Env/capsule pseudo-layers carry applied diffs in provenance.
- Existing `tests/test_policy_layers.py` updated to the delegating API.
- Hook wiring: `post_edit` resolves with `for_path` (directory override
  observable in gate behavior).
