# Assurance Record Example

A minimal project showing Fettle's core output: the digest-bound
Assurance Record.

## The 60-Second Version

```bash
pipx install finefettle
cd your-project
fettle init --profile solo
fettle verify          # runs your tests; binds evidence
fettle assurance       # ← the trust assessment
```

## What You're Looking At

`assurance-record.json` in this directory is the output of
`fettle assurance` on a real project (the `src/fettle_demo/` calculator
with two tests). Every dimension is backed by an evidence reference or
an honest explanation of why it's unknown.

| Dimension | Status | Why |
|---|---|---|
| behavior | **PASS** | `verify.json` exists with `exit_code: 0` — tests ran and passed |
| authorization | NOT_APPLICABLE | Solo session — no delegation capsule |
| policy_integrity | UNKNOWN | No `.fettle.toml` policy file in this demo |
| scope | UNKNOWN | Changed-file list not provided |
| security | UNKNOWN | Security evidence joins in P81 |
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

Each command produces a retained artifact that `fettle assurance`
discovers and binds into the record.
