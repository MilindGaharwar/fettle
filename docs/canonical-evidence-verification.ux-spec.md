# UX Spec: Canonical Verification Evidence

Status: P67 implementation contract

Implementation plan:
[fettle-evolution-implementation-plan.md](fettle-evolution-implementation-plan.md#p67-canonical-evidence-kernel-and-verification-pilot-p0)

## Jobs To Be Done

When I run `fettle verify`, I want its result bound to the exact source,
policy, scope, producer, and execution occurrence, so a green result cannot be
reused for different code or conditions.

When the Stop gate cannot validate consequential evidence, I want one concise
reason and one safe recovery command, so I can restore trustworthy evidence
without interpreting artifact internals.

When I upgrade an existing repository, I want the legacy verification stamp to
keep working during the pilot, so canonical evidence can prove parity before it
becomes the only authority path.

## Personas

- New adopter: expects `fettle verify` to run as before without learning an
  evidence schema.
- Power user or agent: needs deterministic JSON, exact rejection reasons, and
  one command that repairs invalid evidence.
- Repository maintainer: needs additive rollout, rollback to the legacy stamp,
  bounded local persistence, and no host-wire change.
- Accessible terminal user: needs status conveyed through text and exit codes,
  not color, cursor behavior, or animation.

## User Journey

| Phase | User action | Sees | Desired feeling | Failure to prevent |
|---|---|---|---|---|
| Entry | Runs `fettle verify` after editing code | Existing concise progress and verdict | Familiar | Schema details replacing the primary task |
| Execute | Waits for tests | Existing test command behavior | In control | Evidence work changing which tests run |
| Record | Verification finishes | Existing human or JSON result | Confident | A partial write appearing as valid success |
| Gate | Attempts to stop the session | Allow, or a typed evidence rejection and `fettle verify` | Unblocked | Missing or invalid evidence becoming pass |
| Recover | Runs the displayed command | Fresh stamp and canonical sidecar replace prior evidence | Complete | Multiple ambiguous recovery choices |

## Flow And Budgets

1. Run `fettle verify`.
2. If the Stop gate rejects evidence, run the displayed `fettle verify` command.

- Interaction budget: one command normally, one rerun after invalidation.
- Existing human output remains concise; schema internals are machine-readable.
- Canonical validation adds no network, graph, or external package dependency.
- Stop-hook evidence validation remains within its existing 100 ms budget.
- Artifact size is at most 1 MiB and payload size at most 768 KiB.

## Required States

### First-Time Empty

No stamp or canonical artifact exists. The Stop gate says no verification was
recorded and prints `Run: fettle verify`. It never treats absence as pass.

### Cleared Empty

Tests pass with no failures. Existing concise green output remains unchanged;
the machine result retains the complete artifact identity and bindings.

### Filtered Empty

Impacted-test discovery finds no mapped tests. Existing behavior runs the full
suite; an empty impacted scope never means there is nothing to verify.

### Loading Brief

Sub-second verification remains quiet beyond existing command behavior.

### Loading Long

Existing timeout behavior remains authoritative. Evidence records a non-pass
tool outcome if the bounded test command does not complete.

### Populated

The legacy stamp and canonical sidecar describe the same command outcome,
source state, policy, selected scope, producer, and occurrence. JSON consumers
can inspect the full bounded artifact without changing host responses.

### Error Recoverable

Missing, malformed, stale, incomplete, unsupported, or mismatched evidence
names one typed reason and prints `Run: fettle verify`. Existing evidence is
never silently repaired or reinterpreted.

### Error Fatal

Secret material, absolute paths, traversal, ambiguous Unicode, unsupported
values, or exceeded bounds prevent canonical persistence. No parseable success
artifact remains; the legacy result cannot conceal the write failure once the
canonical path becomes authoritative.

### Offline

Local verification and validation continue without network access. No external
index, graph, trace, or cache is required to authorize the result.

### Stale Or Superseded

A source, policy, scope, producer, schema, or kind-specific invalidation change
rejects the artifact with the exact mismatch class and requires `fettle verify`.
Age alone cannot establish freshness.

## Information And Disclosure

- No new navigation or command is introduced.
- Default human output remains the existing verification verdict and recovery
  command.
- `--json` retains the complete bounded machine result and artifact reference.
- Artifact internals remain in `.fettle` local machine-readable state; default
  failures show identities and reasons, never source bodies or secret values.
- The existing `.fettle/verify.json` stamp remains readable and authoritative
  during the pilot. The sidecar is additive and removable for rollback.

## Accessibility

- Every state has a textual label and stable exit behavior.
- Output remains understandable with `NO_COLOR=1` and in a non-TTY.
- Recovery requires no mouse, color recognition, animation, or interactive
  prompt.
- Human and JSON outcomes must not disagree about pass versus non-pass.

## BDD Acceptance Scenarios

### Scenario: Equal observations retain content identity

Given two independent verification runs have equal producer, source, policy,
scope, result, completeness, trust, payload, and parents
When canonical artifacts are constructed
Then they have the same full content digest
And distinct observation IDs and observed times cannot substitute for that
content identity.

### Scenario: Verification writes additive canonical evidence

Given an existing repository with the verification gate enabled
When `fettle verify` completes
Then the existing legacy stamp is written with its existing fields
And a complete canonical sidecar binds the exact source, effective policy,
selected scope, producer implementation, command outcome, and run occurrence
And existing concise human output remains unchanged.

### Scenario: Legacy rollback remains available

Given the canonical pilot is disabled or its sidecar is removed
When the Stop gate reads a fresh green legacy stamp
Then existing verification behavior remains unchanged
And no legacy truncated evidence ID is promoted to a canonical digest.

### Scenario: Copied evidence cannot authorize different inputs

Given a valid green verification artifact
When its reference is evaluated for another revision, dirty state, policy,
scope, workspace, producer, schema, or invalidation context
Then validation returns the corresponding typed non-pass reason
And the Stop gate prints `Run: fettle verify`.

### Scenario: Incomplete or non-pass evidence cannot authorize

Given an artifact reports pass with partial or unknown completeness, or reports
violation, overridden, tool error, unknown, or not applicable
When a consequential consumer validates it
Then it does not map to pass or allow.

### Scenario: Malformed or hostile evidence fails closed

Given any transformation in `tests/fixtures/evidence/adversarial-v1.json`
When the canonical validator evaluates it beside the registered base artifact
Then it returns the fixture's expected typed validity
And its consequential result is `unknown`, never pass.

### Scenario: Interrupted persistence leaves no success

Given an existing valid canonical artifact
When writing its replacement is interrupted or `os.replace` fails
Then no partial replacement is parseable as success
And the prior artifact is not represented as evidence for the new occurrence.

### Scenario: Diagnostics remain safe

Given rejected evidence contains a secret, absolute path, or source body
When its diagnostic is rendered
Then the diagnostic contains only the validity reason, bounded identities, and
`fettle verify`
And the sensitive value is absent.

## Success Criteria

- Canonical bytes and full content digests are deterministic across processes.
- Every frozen P66 adversarial fixture returns its specified validity.
- Missing or invalid consequential evidence never maps to pass.
- All existing verification and host conformance tests remain green.
- Installed-CLI UAT confirms unchanged concise output, JSON parity, offline
  operation, rollback, typed recovery, and no partial-success artifact.
- Stop-hook latency remains within 100 ms and canonical artifact bounds hold.
