# UAT Parity Benchmark

`fettle uat benchmark --evidence evidence.json` validates retained agent and
human runs against the canonical ten-seed manifest and reproduces discovery,
false-verdict, and coverage metrics.

Each run in the evidence file must contain:

```json
{
  "seed_id": "p77-01-lost-restart-state",
  "actor": "agent",
  "discovered": true,
  "false_verdict": false,
  "coverage_observed": 3,
  "coverage_total": 4,
  "artifact": {
    "path": "artifacts/p77-01-agent.json",
    "digest": "sha256:<digest of the retained artifact>"
  }
}
```

The top-level document is `{"schema_version": 1, "runs": [...]}`. Artifact
paths are relative to the evidence file and may not escape that directory.

Exit code `0` means every graduation criterion passed. Exit code `1` means the
evidence is valid but graduation remains blocked. Exit code `2` means evidence
is malformed, duplicated, unknown, unavailable, or digest-invalid.

The committed discovery threshold is intentionally `null`. No parity claim or
enforcement graduation is valid until retained human evidence exists for all
ten seeds and reviewers agree and commit the threshold.
