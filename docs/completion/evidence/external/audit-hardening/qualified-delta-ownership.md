# Qualified Candidate Delta Ownership

## Identity boundary

The qualified candidate is not identified by the base commit alone. It is the exact
run-05 candidate identity
`e3f3ee0bfc72545367897cd06c801116a70ad0e34106a147d217cea9f88346b1`,
bound to frozen revision `4522a564791bce326ca4f340f7007f09e988b8e1`,
the recorded source/test/config content digests, and file modes. The complete delta
against base `2a2829cbdb1e630cbfc37b48360d91dbce8c4fd9` contains 68 paths. Eleven
of those paths also contain qualified uncommitted changes relative to the frozen
revision. The exact inventories are separately retained in
`qualified-delta-name-status.txt`, `qualified-delta-numstat.txt`,
`qualified-delta-summary.txt`, and `qualified-working-tree-delta.patch`.

## Ownership classification

| Class | Paths | Disposition |
|---|---:|---|
| Milestone A implementation, configuration, evidence, or direct regression coverage | 27 | Authorized scope for AH01-AH07 or evidence needed to qualify it |
| Concurrent UAT acceptance-integrity program | 39 | Real qualified content, but not owned by Milestone A; acceptance must acknowledge this broader candidate |
| Unowned executable-mode removals | 2 | Not justified by either plan; behaviorally regress direct execution |

### Milestone A-owned or acceptance-supporting paths (27)

`.fettle.toml`; `.github/workflows/ci.yml`; `.github/workflows/release.yml`;
`docs/audit-hardening-implementation-plan.md`; `docs/audit-hardening-worklog.md`;
`docs/audit-hardening.ux-spec.md`; `docs/backlog/audit-hardening.md`;
`fettle/action_entrypoint.py`; `fettle/config.py`; `fettle/dispatcher.py`;
`fettle/dispatcher_registry.py`; `fettle/dispatcher_types.py`;
`fettle/evidence_ledger.py`; `fettle/mutation_test.py`; `fettle/quality_scan.py`;
`pyproject.toml`; `tests/test_action_entrypoint.py`; `tests/test_config.py`;
`tests/test_dispatcher_failure_visibility.py`; `tests/test_dispatcher_registry.py`;
`tests/test_distribution.py`; `tests/test_evidence_ledger.py`;
`tests/test_mutation_test.py`; `tests/test_quality_scan.py`;
`tests/test_boundary_scan.py`; `tests/test_runners.py`; `tests/test_spec_model.py`.

The last three tests include qualification-strengthening coverage across shared
boundaries. They support Milestone A acceptance but also touch shared/UAT behavior.

### Concurrent UAT acceptance-integrity paths (39)

`docs/CAPABILITIES.md`; `docs/plan-index.md`;
`docs/uat-acceptance-integrity.ux-spec.md`; `docs/uat-strength-plan.md`;
all nine `docs/uat/*` files in the delta; all seven `evals/uat*` files;
`fettle/cli.py`; `fettle/runners/__init__.py`; all eight changed/new
`fettle/uat/*` files; `tests/test_assurance_record.py`; `tests/test_cli.py`;
`tests/test_uat_artifacts.py`; `tests/test_uat_benchmark.py`;
`tests/test_uat_p73.py`; `tests/test_uat_reconcile.py`;
`tests/test_uat_session.py`; `tests/test_uat_surfaces.py`.

These changes are part of the exact candidate and cannot be ignored or represented
as Milestone A-only. Their presence is not, by itself, evidence that Milestone A is
invalid; it is an acceptance-scope decision for the reviewer and user.

### Executable-mode removals (2)

- `fettle/cross_review.py`: `100755` to `100644`, no content change.
- `fettle/import_graph.py`: `100755` to `100644`, no content change.

Both are importable modules and neither is a `pyproject.toml` console entry point.
Focused module tests pass (33 tests), and `python file.py` / `python -m module`
remain usable. Direct `./fettle/cross_review.py` and `./fettle/import_graph.py`
execution now fails with exit 126. Both were intentionally tracked executable at
the base; `cross_review.py` retains a shebang and direct-script usage. Recommend
correcting both modes in the next candidate, not retaining the removals. Do not
change run-05: mode restoration changes candidate identity and requires re-binding
all acceptance evidence; whether it triggers new mutation qualification is a
separate approved scope decision.
