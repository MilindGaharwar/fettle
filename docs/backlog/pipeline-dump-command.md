---
fettle-work-item: true
id: pipeline-dump-command
status: open
scope:
  - fettle/cli.py
  - fettle/doctor.py
  - tests/test_pipeline_dump.py
spec: improvement-plan
---

# Pipeline dump — print the composed gate/hook pipeline with provenance

Adopted from DeepSeek Harness's `--dump-config` pattern: a single command
that boots the real composition and prints every effective row with its
source layer, so the onboarding cliff becomes visible instead of hidden.

Deliverable: `fettle doctor --pipeline` printing one row per active
check/gate/hook binding:

```
check/gate   events                    hosts            enabled  mode      source
authorship   PreToolUse                claude,codex,…   true     advisory  repo .fettle.toml
verify       Stop                      *                false    advisory  defaults
…
```

Differentiation from `config --explain` (which prints effective config
*values* with provenance): `--pipeline` answers the runtime question —
*given a HookContext (event, host), which checks select, in what order,
and why*. The dispatcher CHECKS registry is static, so "wired host" means:
transports whose KNOWN_EVENTS intersect the check's event set.

## Done when

- Golden test over a fixture config with ≥2 layers shows each row's source
  layer correctly (defaults vs org vs repo).
- Every dispatcher-registered check appears exactly once per wired host.
- `--json` emits machine-readable rows; docs section added to CONFIG.md.

## Resolution

Record how it was resolved.
