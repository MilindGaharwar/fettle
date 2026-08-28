# Multi-Agent Work

Fettle coordinates delegated work with plans, topology advice, role-aware
spawning, claims, worktrees, policy capsules, and completion reports.

```bash
fettle plan start --title "Add export" --item "Write contract test"
fettle topology advise
fettle spawn claude --role tester --task "Write the failing tests"
fettle work claim export-tests
fettle brief --json
```

An agent launched through `fettle spawn` receives a digest-checked policy
capsule and lineage identity. Child policy may tighten but cannot loosen the
inherited boundary. Claims and worktrees coordinate ownership, while role
authority can separate test authorship from implementation.

These controls are defense in depth, not operating-system isolation. Start in
advisory mode, validate the target agent runner, and retain least-privilege
credentials and isolated runners where the risk requires them. Broader
end-to-end graduation evidence remains in progress.

See [Configuration](CONFIG.md) for policy and gate settings.
