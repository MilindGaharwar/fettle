---
fettle-work-item: v2
id: work-item-lifecycle-integrity
status: open
scope:
  - fettle/work_items.py
  - fettle/cli.py
  - fettle/completion.py
  - fettle/completion_gate.py
  - fettle/providers/work_item_provider.py
  - fettle/semantic.py
  - fettle/graph_shadow.py
  - fettle/topology.py
  - fettle/topology_apply.py
  - tests/test_work_items.py
  - tests/test_completion.py
  - tests/test_completion_gate.py
  - tests/test_graph_providers.py
  - tests/test_semantic.py
  - tests/test_topology.py
  - tests/test_topology_apply.py
  - tests/test_release_workflow.py
  - .pre-commit-config.yaml
  - .github/workflows/ci.yml
  - .github/workflows/release.yml
  - docs/backlog/*.md
  - docs/work-item-lifecycle-integrity*.md
  - docs/plan-index.md
  - docs/engagement/TODO.md
spec: work-item-lifecycle-integrity
---

# Work-Item Lifecycle Integrity

Planning only. No parser, CLI, fixture, migration, hook, workflow, release, or
enforcement implementation is authorized.

Plan: [work-item-lifecycle-integrity-plan.md](../work-item-lifecycle-integrity-plan.md)

UX contract: [work-item-lifecycle-integrity.ux-spec.md](../work-item-lifecycle-integrity.ux-spec.md)

## Acceptance Criteria

- The committed historical P46 contradiction is a permanent non-pass fixture.
- New v2 work items have one structured delivery state and an unambiguous final
  closure marker without creating a second criterion-evidence authority.
- The existing completion evaluator remains authoritative for v2 completion.
- Every supported lifecycle, closure, version, identity, and applicable manifest
  combination has a deterministic result and manual recovery.
- Repository-wide validation rejects contradictions before required CI and release
  build, subject to verified external protection settings.
- The live corpus is reconciled without fabricated evidence, permanent baselines,
  or suppressions.
- Authorization, delivery, qualification, graduation, promotion, Assurance, and
  runtime claim ownership remain distinct.
