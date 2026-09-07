---
fettle-work-item: true
id: event-map-doc
status: done
scope:
  - docs/event-map.md
  - tests/test_doc_claims.py
spec: improvement-plan
---

# Canonical producer→consumer event map

Adopted from dsh's event-producer-consumer doc: one indexed page listing
every hook/dispatcher event, its per-host support, producers, and consumers
(checks, trace, evidence artifacts), classified as **durable** (recorded in
trace/evidence) or **live** (in-session only).

## Done when

- `docs/event-map.md` covers every event the dispatcher can dispatch across
  Claude Code, Codex CLI, Gemini CLI, and OpenCode.
- Source of truth for the drift predicate: the union of each agent
  transport's KNOWN_EVENTS frozenset plus every event literal in
  CheckSpec.event sets — enumerated across all `fettle/agents/*.py`
  modules, not just the static dispatcher registry.
- Each event row states durability and at least one consumer or "none".

## Resolution

Replaced the hard-coded event-name regex with structural discovery across every
agent transport's `KNOWN_EVENTS` or `_EVENT_MAP` declaration and every
`CheckSpec.events` set. The predicate now rejects missing and stale event
sections and requires each section to state durability and consumers. Corrected
the `PreToolUse` consumer inventory to match the registry.
