# AI-1 Failing Regression Evidence

Date: 2026-09-03

Command:

```bash
uv run pytest tests/test_assurance_integrity.py -q
```

Initial result: seven intended failures, each at the final Assurance Record
boundary. After confirming each failure reason, every regression was marked
strict `xfail` so the repository suite remains usable. A corrected behavior
becomes XPASS and fails until its marker is deliberately removed.

| Regression | Current result | Required result |
|---|---|---|
| Raw green verify stamp without canonical sidecar | `behavior = PASS` | `behavior = UNKNOWN` and policy FAIL |
| Raw green CI status without canonical sidecar | `ci = PASS` | `ci = UNKNOWN` and policy FAIL |
| Completed mutation with `passed = false` | `behavior = PASS` | `behavior = FAIL` and policy FAIL |
| Parseable forged ledger anchor | `provenance = PASS` | `provenance = UNKNOWN` and policy FAIL |
| Unbound raw clean security review | `security = PASS` | `security = UNKNOWN` and policy FAIL |
| Caller-supplied non-repository scope | `scope = PASS` | `scope = UNKNOWN` and policy FAIL |
| Equivalent repositories in different locations | Different record digests | Equal portable record digests |

No production code was changed during AI-1. These failures established the
implementation contract for AI-2 through AI-6 and must not be weakened to make
the suite green.

## AI-2 Shared Context Evidence

Command:

```bash
uv run pytest tests/test_assurance_integrity.py -q
```

Result: `4 passed, 5 xfailed`. AI-2 deliberately resolved the scope-authority
and clone-portability regressions. The five producer acceptance gaps remain
strict `xfail` for AI-3 through AI-5.

| Scenario | Result |
|---|---|
| Caller supplies a false changed-file list | PASS: ignored; scope comes from Git |
| Equivalent clones in different locations | PASS: canonical record digests match |
| Effective organization policy changes | PASS: effective-policy digest changes |
| Working source changes | PASS: subject snapshot digest changes |
| Source identity cannot be resolved | PASS: CLI reports unavailable and exits 2 |

Terminal UAT confirmed `fettle assurance --json` reports one working subject,
effective policy, and Git-derived scope. An invalid repository reports
`Assurance unavailable` rather than crashing or reusing evidence.

## AI-3 Canonical Verify And CI Evidence

Command:

```bash
uv run pytest tests/test_assurance_integrity.py tests/test_assurance_record.py \
  tests/test_verify_gate.py tests/test_ci_gate.py -q
```

Result: `141 passed, 3 xfailed`.

| Scenario | Result |
|---|---|
| Raw green verify stamp without canonical sidecar | PASS: behavior is `UNKNOWN`; policy fails |
| Raw green CI status without canonical sidecar | PASS: CI is `UNKNOWN`; policy fails |
| Valid canonical verify violation | PASS: behavior remains `FAIL`; policy fails |
| Canonical verify evidence for an old source | PASS: rejected as `wrong_source` |
| Canonical CI evidence under an old policy | PASS: rejected as `wrong_policy` |

The three remaining strict `xfail` cases are mutation result semantics,
provenance anchor verification, and canonical security authority. They remain
assigned to AI-4 and AI-5.

## AI-4 Canonical Mutation And UAT Evidence

Commands:

```bash
uv run pytest tests/test_assurance_integrity.py tests/test_assurance_record.py \
  tests/test_mutation_test.py tests/test_uat_reconcile.py -q
uv run ruff check fettle/assurance.py fettle/mutation_test.py \
  fettle/uat/reconcile.py tests/test_assurance_integrity.py \
  tests/test_assurance_record.py tests/test_mutation_test.py \
  tests/test_uat_reconcile.py
```

Focused result: `245 passed, 2 xfailed`. Full result: `3036 passed, 2 xfailed`.
The changed-file Fettle scan, Ruff, config validation, and diff integrity checks
also passed.

| Scenario | Required result |
|---|---|
| Complete canonical mutation violation with an older verify pass | Behavior is `FAIL`; policy fails |
| Mutation tool error or incomplete report | Behavior is `UNKNOWN`; policy fails |
| Mutation evidence bound to old source or policy | Rejected as `wrong_source` or `wrong_policy` |
| UAT report edited after sidecar creation | Rejected as `tampered` |
| UAT evaluator unresolved | UAT is `UNKNOWN`; policy cannot pass |
| Newer canonical UAT contradiction replaces an older pass | UAT is `FAIL` |

The two remaining strict `xfail` cases are provenance anchor verification and
canonical security authority, assigned to AI-5.

## AI-5 Provenance, Authorization, And Security

Commands:

```bash
uv run pytest tests/test_evidence_ledger.py tests/test_assurance_record.py \
  tests/test_assurance_integrity.py -q
uv run pytest -q
uv run ruff check fettle/assurance.py fettle/evidence_ledger.py \
  tests/test_assurance_record.py tests/test_evidence_ledger.py \
  tests/test_assurance_integrity.py
```

Focused result: `90 passed`. Full result: `3043 passed`. The two AI-5 strict
`xfail` markers were removed, leaving no expected failures.

| Scenario | Required result |
|---|---|
| Parseable forged or malformed ledger/anchor | Provenance is `UNKNOWN`; policy fails |
| Anchor bound to another commit | Provenance is `UNKNOWN`; policy fails |
| Valid anchor followed by newer ledger records | Provenance is `UNKNOWN`; policy fails |
| Valid zero-drift anchor for the assessed commit | Provenance is `PASS` |
| Incidental repository capsule | Authorization is `NOT_APPLICABLE` |
| Explicit valid delegation capsule | Authorization is `PASS` |
| Explicit invalid delegation capsule | Authorization is `FAIL` |
| Raw security review, clean or with findings | Security remains diagnostic `UNKNOWN`; policy fails |

The security producer does not yet emit canonical source-, policy-, and
scope-bound evidence. AI-5 therefore does not infer an authoritative `PASS` or
`FAIL` from its raw report. This preserves the documented v1 report format and
prevents unbound local JSON from authorizing release.

## AI-6 Portable Record Persistence

Commands:

```bash
uv run pytest tests/test_assurance_record.py tests/test_cli.py \
  tests/test_assurance_integrity.py tests/test_evidence.py -q
uv run pytest -q
uv run ruff check fettle tests
```

Focused result: `147 passed`. Broader assurance/evidence result: `229 passed`.
Full result: `3050 passed`.

| Scenario | Required result |
|---|---|
| Successful CLI assessment | Atomically writes a parseable `EvidenceArtifact` v1 |
| Record contains local checkout root and generation time | Persisted payload omits both; occurrence time remains in `observed_at` |
| Equivalent clones assess equivalent content | Persisted artifact digests match |
| Accepted canonical producer evidence | Persisted as bound parent references |
| Assessment fails while an older artifact exists | Older artifact is removed; CLI exits 2 |
| Atomic replacement fails | Temporary and older artifacts are absent; CLI exits 2 |

The interactive and JSON command output retain the existing schema-v1 record.
Only the persisted evidence payload uses the portable projection.

## AI-7 Record-Level Adversary And Dogfood

Commands:

```bash
uv run pytest tests/test_assurance_adversary.py tests/test_assurance_integrity.py \
  tests/test_assurance_record.py tests/test_cli.py -q
uv build
uv run fettle assurance --root . --json
<isolated-wheel>/bin/fettle assurance --root <working-tree> --json
```

The focused adversary and record suite passed with `132 passed`. The source-tree
and isolated installed-wheel commands assessed the same working tree and
produced equal canonical record digests and dimension vectors. The digest is
not embedded here because editing this tracked evidence changes the assessed
working snapshot.
The installed artifact parsed as `fettle.assurance.record` with an `unknown`
result, retained the assessed revision and snapshot digest, and omitted both the
checkout root and `generated_at` from its portable payload.

| Adversary | Final policy result |
|---|---|
| Forged raw green verify report | FAIL; behavior remains `UNKNOWN` |
| Raw security report | FAIL; security remains diagnostic `UNKNOWN` |
| Malformed or forged provenance | FAIL; provenance remains `UNKNOWN` |
| Tampered delegation capsule | FAIL; authorization is `FAIL` |

The checked-in example now reflects the hardened schema-v1 output from a clean
checkout. Enforcement graduation remains open: 20 real shadow assessments and
explicit operator authorization have not been collected and are not inferred
from automated tests or these dogfood runs.

Final technical gates passed: the full suite reported `3054 passed`; Ruff,
configuration validation, `fettle check --changed`, and `git diff --check` were
clean. The governance commands remained fail-closed: completion validation
reported stale scope digests in the historical P54, P55, and P81 records, and
production-policy evaluation reported that `[assurance.release.production]` is
not configured. These pre-existing governance inputs were not rewritten or
invented during AI-7.
