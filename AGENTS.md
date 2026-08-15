# Repository Agent Instructions

## Mutation Evidence

- Treat full mutation runs as held-out verification, not an iteration loop.
- Use fixtures, then preflight, then narrow replay, then a full run.
- Trust canonical fingerprints, not run-local mutmut numeric IDs.
- Reuse caches only when their complete compatibility identity validates.
- Run independent authoritative calibrations sequentially and never share their
  terminal outcomes.
- Preserve missing, malformed, partial, stale, or conflicting evidence as a
  non-pass. See `docs/mutation-quality-playbook.md` before changing mutation
  behavior.
