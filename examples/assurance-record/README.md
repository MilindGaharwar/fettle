# Assurance Record Example

A minimal project showing Fettle's core output: the digest-bound
Assurance Record.

## The 60-Second Version

```bash
pipx install finefettle
cd your-project
fettle init --profile solo
fettle verify          # runs your tests; binds evidence
fettle assurance       # the trust assessment + persisted canonical artifact
```

## What You're Looking At

`assurance-record.json` in this directory illustrates the JSON output from
`fettle assurance --json`. The command also atomically writes
`.fettle/assurance-record.evidence.json`, a portable canonical artifact that
can be parsed with `fettle.evidence.parse_artifact`. Every dimension is backed
by an accepted evidence reference or an honest explanation of why it is unknown.

| Dimension | Status | Why |
|---|---|---|
| behavior | UNKNOWN | This minimal snapshot retains no canonical verify or mutation evidence |
| authorization | NOT_APPLICABLE | Solo session — no delegation capsule |
| policy_integrity | **PASS** | Effective layered policy is digest-bound |
| scope | **PASS** | Scope is derived from Git, not caller input |
| security | UNKNOWN | Raw security reports are diagnostic until a canonical producer is approved |
| independence | UNKNOWN | Solo session — no role separation or spawn lineage |
| provenance | UNKNOWN | No governance ledger retained |
| uat | UNKNOWN | No UAT report retained |
| ci | NOT_APPLICABLE | No retained CI verdict |

The transparency is the point: Fettle never turns missing evidence into
a pass. Dimensions with no data say UNKNOWN and explain why.

## Making It Fuller

Run more of Fettle's evidence generators before `fettle assurance`:

```bash
fettle mutation run --changed --json   # populates behavior dimension further
fettle ci wait                          # populates the CI dimension
fettle uat run --surface cli            # populates the UAT dimension
```

Each command produces retained evidence that `fettle assurance` validates
before use. Accepted canonical artifacts are parent-linked from the persisted
Assurance Record. Missing, stale, malformed, or mismatched evidence cannot pass.
