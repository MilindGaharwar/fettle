# Assurance Integrity Prior-v1 Baseline Protocol

Status: required CS-6 collection protocol

Related: [implementation plan](../assurance-integrity-implementation-plan.md),
[security evidence plan](../canonical-security-evidence-implementation-plan.md),
and [shadow register](assurance-integrity-shadow-assessments.md)

## Purpose

Produce a machine-reproducible prior-v1 decision and a hardened decision for
the same real change, policy, scope, retained evidence, and runtime state. This
protocol prevents memory, prose interpretation, a moving Git checkout, or a
different evidence set from becoming the baseline.

## Frozen Baseline

| Property | Value |
|---|---|
| Protocol version | `1` |
| Baseline implementation | `29fad420040ddee2201aea8b5b3838f7eb2a8a74` |
| Package version at baseline | `1.12.1` |
| First excluded hardening commit | `f911f0eb88da0e026bca575d02ebc8e9432c3a04` |
| Policy | One captured canonical projection of the candidate's effective `[assurance.release.production]` policy |
| Scope | Exact ordered changed-file paths captured once from the candidate checkout |
| Runtime state | One copied `XDG_STATE_HOME` snapshot shared by both evaluations |

Commit `29fad42` is the last Assurance implementation before the hardening
series and already implements named release-policy evaluation. Tag `v1.12.0`
is not the baseline because it predates named Assurance policies. Later tags are
not used because they contain some of the behavior being evaluated.

Both records are evaluated against the captured policy projection by the
protocol comparator. The historical evaluator's policy loader is not used:
prior v1 read only `.fettle.toml`, while the hardened evaluator resolves layered
policy. Calling both loaders would compare different requirements rather than
different evidence semantics.

No assessment row may be accepted until a reviewed collector/normalizer
implements this protocol and passes fixtures covering deterministic capture,
policy projection, state freezing, normalization, tamper rejection, and
comparison. Hand-executed approximations may rehearse the process but do not
count toward the 20 rows.

## Unit Of Assessment

One row represents one distinct real change in a dedicated worktree before
merge. The worktree must contain the complete intended change as staged,
unstaged, or untracked files relative to its current `HEAD`. A clean checkout,
a repeated unchanged run, or a synthetic fixture does not count.

The assessment is invalid if any of these change between capture and the second
evaluation:

- `HEAD`;
- porcelain-v1 Git status including untracked files;
- content digest of every changed file, with deleted paths represented
  explicitly;
- `.fettle.toml` bytes;
- any retained evidence consumed by either evaluator;
- the copied trace and claim state;
- `FETTLE_POLICY_CAPSULE` or any other authority-bearing environment input.

## Retained Bundle

Create one immutable bundle per candidate under an external assessment store,
not inside the candidate repository. The bundle name is the full SHA-256 of the
capture manifest. Retain:

```text
capture.json
changed-files.json
prior-v1.raw.json
prior-v1.decision.json
hardened.raw.json
hardened.decision.json
comparison.json
source/<changed path>              # exact bytes for non-deleted changed files
state/fettle/trace.jsonl          # when present
state/claims.json                 # when present
```

`capture.json` records:

- protocol version;
- baseline commit and SHA-256 of its `fettle/assurance.py`;
- hardened implementation commit and SHA-256 of its `fettle/assurance.py`;
- candidate `HEAD`, source snapshot digest, effective-policy digest, and scope
  digest;
- sorted changed paths with Git status and content digest or `deleted` marker;
- digests of every retained input file consumed by either evaluator;
- Python version, platform, Fettle versions, UTC capture time, and relevant
  environment-variable names with values redacted and separately digested;
- capture-manifest digest.

The capture-manifest digest covers every captured field except `captured_at` and
the digest field itself. Identical candidate inputs therefore have one stable
bundle identity; the timestamp remains provenance metadata, not semantic input.

The bundle may contain repository-relative paths and digests. It must not retain
absolute checkout paths, environment values, credentials, or unrelated trace
records. If safe trace minimization cannot preserve the records consumed by the
independence evaluator, encrypt the external bundle and record only its digest
and controlled location in the register.

## Procedure

### 1. Prepare The Candidate

1. Use a dedicated worktree containing exactly one real change.
2. Record the PR or work-item identifier and expected changed scope.
3. Run the normal producers needed by the production policy, including:

```bash
uv run python -m fettle.security_review --path . --json
```

4. Do not edit, stage, commit, rebase, regenerate evidence, or run a command that
   appends authority-bearing trace state until both evaluations and the final
   fingerprint check complete.

Producer commands are preparation, not part of the paired evaluation. Their
retained outputs must exist before the capture manifest is created.

### 2. Capture One Input Set

The collector must create `capture.json` and `changed-files.json` in one pass.
It must derive changed files through `fettle.changeset.get_changed_files`, sort
and deduplicate repository-relative paths, reject paths outside the repository,
and include untracked and deleted entries.

Copy the current trace into the bundle's isolated `state/fettle/trace.jsonl`.
Both evaluators must run with `XDG_STATE_HOME` set to the copied `state`
directory. Copy the repository's shared claim record into `state/claims.json`
for retention when present, and record its digest. Claims have no supported
state-directory override, so both evaluators read the same live Git-common-dir
file while work-item activity is paused. Recompute that file's digest after both
runs; a missing, created, removed, or changed claim file invalidates the row.

The collector must reject an empty scope, a dirty submodule, an unresolved merge,
or unreadable retained evidence. It prints the capture digest and bundle path.

### 3. Run Prior-v1 Read-only

Extract the baseline package from the pinned commit into a temporary directory;
do not check it out over the candidate and do not install it into the candidate
environment. Verify the extracted `fettle/assurance.py` digest against
`capture.json`.

Invoke its record builder, not its CLI:

```python
result = build_assurance_record(candidate_root, changed_files=exact_paths)
```

Run with the extracted baseline package first on `PYTHONPATH`, the frozen
`XDG_STATE_HOME`, and the captured authority-bearing environment. The library
path is mandatory because the historical CLI persists
`.fettle/assurance-record.evidence.json` and would mutate candidate evidence.

Write the complete returned object to `prior-v1.raw.json`. The wrapper must make
no network calls and must fail if imports resolve to the candidate package. The
baseline's weaker validation is expected historical behavior and is exactly
what the shadow comparison measures; it must not be repaired in the wrapper.

### 4. Run The Hardened Evaluator

Invoke the candidate's installed/source-tree command with the same frozen state:

```bash
uv run fettle assurance --policy production --json
```

Capture stdout as `hardened.raw.json`, stderr separately if non-empty, and the
exit code. The expected CLI mapping is `PASS=0`, `FAIL=1`, and `CONFIG_ERROR` or
execution failure `=2`. The comparator independently recomputes both decisions
from their dimension vectors and the frozen policy projection; it rejects a
hardened CLI status that disagrees. Do not use shell success alone as the
decision.

### 5. Normalize And Compare

For each raw result, derive a decision projection containing only:

```json
{
  "evaluator": {"commit": "<full commit>", "implementation_digest": "sha256:..."},
  "subject": {"head": "<commit>", "source_snapshot_digest": "sha256:..."},
  "policy": {"name": "production", "digest": "sha256:...", "status": "PASS|FAIL|CONFIG_ERROR"},
  "scope": {"digest": "sha256:...", "paths": []},
  "dimensions": {
    "authorization": "PASS|FAIL|UNKNOWN|NOT_APPLICABLE",
    "policy_integrity": "PASS|FAIL|UNKNOWN|NOT_APPLICABLE",
    "scope": "PASS|FAIL|UNKNOWN|NOT_APPLICABLE",
    "behavior": "PASS|FAIL|UNKNOWN|NOT_APPLICABLE",
    "security": "PASS|FAIL|UNKNOWN|NOT_APPLICABLE",
    "independence": "PASS|FAIL|UNKNOWN|NOT_APPLICABLE",
    "provenance": "PASS|FAIL|UNKNOWN|NOT_APPLICABLE",
    "uat": "PASS|FAIL|UNKNOWN|NOT_APPLICABLE",
    "ci": "PASS|FAIL|UNKNOWN|NOT_APPLICABLE"
  },
  "completeness": "COMPLETE|PARTIAL",
  "semantic_input_digest": "sha256:..."
}
```

Apply the same frozen policy function to each dimension vector: sort criteria by
dimension name; map provenance `PASS` to `COMPLETE` and every other provenance
status to `PARTIAL`; split `|` alternatives without inference; return `PASS`
only if every actual status is listed, otherwise `FAIL`. Unsupported dimensions
or statuses return `CONFIG_ERROR`. The comparator implementation and its digest
are recorded in `comparison.json`.

The prior-v1 projection uses the capture manifest's source, policy, and scope
identity because the old record did not carry all three canonical fields. This
is an explicit comparison envelope, not evidence that prior v1 bound those
inputs itself.

Exclude generated timestamps, absolute roots, occurrence IDs, presentation
text, and evidence-file paths from semantic comparison. Preserve them in raw
outputs where safe and record each raw file's byte digest in `comparison.json`.
`semantic_input_digest` covers the canonical projection before that field is
added; it is the reproducible decision identity. Compare:

- overall production-policy status;
- every policy criterion's actual status and pass/fail result;
- all nine dimension statuses;
- completeness.

Write all changed fields to `comparison.json`; an empty difference list is still
recorded. Never compare Assurance Record digests directly because prior v1 and
the hardened record intentionally canonicalize different structures.

### 6. Verify The Capture Did Not Move

Recompute the complete pre-evaluation capture fingerprint after both evaluations,
excluding only the hardened Assurance sidecar that the current CLI is specified
to replace. The row is invalid if any other captured input differs. Also verify
that each recorded raw-output digest matches its retained file and that rerunning
normalization over those retained raw files produces byte-identical canonical
projections.

### 7. Classify And Accept

Each difference receives exactly one classification:

- `intentional_hardening`: expected consequence of a named reviewed hardening
  change, with commit and evidence reference;
- `defect`: unexpected behavior requiring correction and a fresh assessment;
- `unresolved`: insufficient evidence; the row does not count.

There is no generic `expected`, `tool drift`, or `environment` acceptance class.
Environment/tool instability makes the row invalid and requires a new capture.

A row is accepted only when:

- the input fingerprint is unchanged;
- both evaluators completed from the pinned implementations;
- the collector/comparator implementation and its conformance fixtures are
  reviewed and digest-bound;
- raw outputs, normalized projections, and comparison are retained and digested;
- every difference is `intentional_hardening` with a concrete code/change
  reference, or there are no differences;
- no hardened false pass is present;
- a human reviewer signs the row after inspecting the retained bundle.

## Reproduction

A reviewer reproduces a row by obtaining the exact candidate commit/worktree
content, restoring the retained non-repository evidence and frozen state,
verifying `capture.json`, and rerunning both evaluators and normalization.
Semantic projections and differences must be byte-identical; raw outputs may
differ only in explicitly excluded volatile fields such as `generated_at`.

If uncommitted content can no longer be reconstructed exactly, the row is not
reproducible and must be removed from the accepted count. Therefore the
candidate patch or equivalent immutable source archive must be retained with the
external bundle until graduation.

## Collection And Review Commands

Use an assessment store outside the candidate repository. Collection always
creates an unaccepted bundle and retains the exact bytes of every non-deleted
changed file:

```bash
uv run fettle assurance-baseline collect \
  --root /path/to/candidate-worktree \
  --store ~/.local/share/fettle/cs6-assessments \
  --json
```

After inspecting both decisions and `comparison.json`, create a JSON array with
one entry per difference. Use an empty array when there are no differences:

```json
[
  {
    "path": "dimensions.security",
    "classification": "intentional_hardening",
    "evidence": "commit <sha> and review reference <path>"
  }
]
```

Record the review once. A bundle cannot be reviewed a second time or accepted
when any classification is `defect` or `unresolved`:

```bash
uv run fettle assurance-baseline review \
  --bundle ~/.local/share/fettle/cs6-assessments/<capture-digest> \
  --change <PR-or-work-item> \
  --reviewer Milind \
  --reviewer-email 20487933+MilindGaharwar@users.noreply.github.com \
  --classifications /path/to/classifications.json \
  --json
```

Generate progress and the checked-in register only from verified reviews:

```bash
uv run fettle assurance-baseline summarize \
  --store ~/.local/share/fettle/cs6-assessments \
  --register docs/engagement/assurance-integrity-shadow-assessments.md \
  --json
```

## Failure Rules

- Any missing baseline commit, digest mismatch, package import ambiguity, live
  state read, changed candidate fingerprint, malformed output, or incomplete
  bundle invalidates the row.
- A baseline weakness may explain an intentional hardened rejection, but it
  cannot excuse a hardened pass that contradicts valid negative evidence.
- Failed rows remain in the append-only register with `Accepted = no`; corrected
  reruns receive a new row and bundle.
- No row collected before this protocol was frozen counts unless it can be
  reconstructed and reproduced under this exact protocol.

## Graduation Output

After 20 accepted rows, generate a summary directly from the retained normalized
projections and comparisons. The summary reports counts by prior/hardened
decision pair, changed dimension, and classification, plus rejected rows and
reasons. Hand-entered totals are not graduation evidence.

The completed register, generated summary, retained bundle digests, technical
quality gates, and explicit operator decision together satisfy CS-6. The
twentieth row alone does not authorize enforcement or release.
