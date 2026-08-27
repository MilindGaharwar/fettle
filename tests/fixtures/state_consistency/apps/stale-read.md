---
fettle-consistency: v1
id: seeded-stale-read
title: Seeded stale projection
scope: ["tests/fixtures/state_consistency/apps/**"]
fact: account.name
owner: fixture-store
consistency: {model: immediate, deadline_ms: 30000, poll_interval_ms: 1000}
setup: {adapter: setup}
mutation: {adapter: mutation, retry_safe: false}
canonical_read: {adapter: canonical}
observers: [{id: projection, surface: cli, adapter: observer}]
comparator: {kind: exact}
cleanup: {adapter: cleanup}
adapters:
  setup: {kind: command, argv: [python3, stale_read.py, setup], timeout_s: 5, output: json-v1}
  mutation: {kind: command, argv: [python3, stale_read.py, mutate], timeout_s: 5, output: json-v1}
  canonical: {kind: command, argv: [python3, stale_read.py, canonical], timeout_s: 5, output: json-v1}
  observer: {kind: command, argv: [python3, stale_read.py, observer], timeout_s: 5, output: json-v1}
  cleanup: {kind: command, argv: [python3, stale_read.py, cleanup], timeout_s: 5, output: json-v1}
---
