# UX Spec: Canonical Security Evidence

Status: implementation contract

Related: [Assurance Integrity](assurance-integrity.ux-spec.md) and the
[implementation plan](canonical-security-evidence-implementation-plan.md).

## Job To Be Done

When I prepare an exact change for production, I want the existing security
review command to publish source-, policy-, and scope-bound evidence, so the
production assurance policy can require security `PASS` without trusting a
replayed, partial, or hand-edited report.

## Personas

- New maintainer: needs one command and a precise recovery action.
- Power user or agent: needs deterministic JSON, stable exit codes, and a
  machine-verifiable sidecar.
- Release owner: needs missing tools, findings, malformed output, and stale
  evidence to remain non-pass.
- Accessible terminal user: needs text statuses and paths; color and symbols
  are never required to understand the result.

## Journey And Budget

| Phase | User action | Sees | Recovery |
|---|---|---|---|
| Prepare | Installs Fettle and enters the repository | Existing security command and prerequisites | Run `fettle doctor` if Ruff or Semgrep is unavailable |
| Produce | Runs `python -m fettle.security_review --path . --json` | Raw JSON on stdout and an atomic canonical sidecar | Fix the named tool error and rerun the same command |
| Assess | Runs `fettle assurance --policy production` | Security `PASS`, `FAIL`, or `UNKNOWN` with evidence paths | Resolve findings or rerun the producer for the exact current change |
| Review | Opens the retained report and sidecar | Portable findings plus exact source, policy, scope, and producer bindings | Reject malformed, stale, or conflicting evidence |

- Common path: two non-interactive commands and no prompts.
- The review retains the existing bounded Ruff and Semgrep timeouts.
- Assurance validates retained evidence locally without network access.

## Required States

- First-time empty: security is `UNKNOWN` and names the producer command.
- Cleared empty: deleting the sidecar immediately removes authority from the
  raw report.
- Filtered empty: a target containing no supported files is non-pass unless the
  producer can prove complete applicable coverage; absence is never a pass.
- Loading brief: stdout remains quiet until the review result is ready.
- Loading long: Ruff or Semgrep timeout produces exit 2 and no current
  authoritative sidecar.
- Populated clean: both required tools complete, the raw report is retained,
  the sidecar is valid, and Assurance reports security `PASS`.
- Populated findings: findings produce exit 1 and canonical `violation`
  evidence; Assurance reports security `FAIL`.
- Error recoverable: a missing tool or tool failure produces exit 2, removes
  stale authority, and names the failed prerequisite.
- Error fatal: malformed paths, unsafe output, or persistence failure produces
  exit 2 and cannot leave an older pass appearing current.
- Offline: Ruff runs locally; Semgrep must use an installed, immutable ruleset
  identity rather than downloading an unpinned registry policy at assessment
  time.
- Stale or conflicting: source, revision, effective-policy, scope, producer,
  implementation, digest, or observation mismatch is `UNKNOWN`, never `PASS`.

## Information And Accessibility

- Keep the entry point `python -m fettle.security_review`; do not add another
  top-level command.
- Keep raw JSON on stdout for current consumers.
- Retain `.fettle/security-review.json` and publish canonical
  `.fettle/security-review.evidence.json` atomically.
- Human and JSON status use words and paths; terminal color is optional.
- The first failure names one recovery action and never emits secrets or
  absolute checkout paths in canonical evidence.

## Progressive Disclosure

- Default output contains findings, tool completeness, and the coverage limit.
- Exact source, policy, scope, producer, and ruleset digests live in the
  sidecar for automated verification.
- Assurance shows the sidecar reference and a concise mismatch reason rather
  than dumping the complete artifact.

## BDD Scenarios

### Scenario: Complete clean review authorizes security

Given Ruff and Semgrep complete against the exact repository scope with an
immutable policy identity and report no findings
When the user runs the security review and then production assurance
Then the producer atomically retains canonical `pass` evidence and Assurance
reports security `PASS` with both report and sidecar references.

### Scenario: A finding remains a valid failure

Given a required scanner completes and reports a security finding
When the user runs the security review and then production assurance
Then the producer retains canonical `violation` evidence, exits 1, and
Assurance reports security `FAIL`, not `UNKNOWN`.

### Scenario: Missing or failed tooling cannot pass

Given Ruff or Semgrep is missing, times out, returns malformed output, or fails
When the user runs the security review
Then the command exits 2, invalidates any prior sidecar, and production
assurance reports security `UNKNOWN` with the rerun action.

### Scenario: Replayed evidence cannot pass

Given a valid sidecar belongs to another source snapshot, revision, effective
policy, scope, producer implementation, or ruleset
When the user runs production assurance
Then security is `UNKNOWN` and the exact binding class is reported.

### Scenario: Persistence failure cannot preserve an old pass

Given an older security sidecar passed and the current review cannot atomically
persist its replacement
When the producer finishes
Then it exits 2 and the older sidecar cannot appear current.

### Scenario: Equivalent clones remain portable

Given equivalent checkouts have the same source, effective policy, scope,
producer, ruleset, and observations but different absolute paths
When both produce canonical security evidence
Then their content bindings are equal and neither artifact contains an absolute
checkout path.

## Success Criteria

- Only complete Ruff and Semgrep execution against an immutable declared
  ruleset can produce canonical `pass` or `violation` evidence.
- Missing, malformed, partial, stale, conflicting, or unbound evidence never
  satisfies `security = "PASS"`.
- The raw report remains compatible and diagnostic-only without its sidecar.
- Existing exit codes remain 0 clean, 1 findings, and 2 environment/tool or
  persistence failure.
- Assurance Record evidence includes the accepted security sidecar as a parent.
- Twenty real shadow assessments contain no unexplained decision differences
  before explicit operator approval enables production enforcement.
