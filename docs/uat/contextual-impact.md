# Contextual Impact UAT

Date: 2026-09-09

Status: advisory flow accepted; promotion blocked

## Scenarios

| Scenario | Outcome |
|---|---|
| Discover contextual mode from `fettle graph impact --help` | Pass |
| Run concise `--contextual` analysis from a repository path | Pass |
| Request paths, score components, and exclusions with `--detailed` | Pass |
| Request machine-readable output with `--json` | Pass |
| Use `--detailed` without `--contextual` | Pass: rejected with exit 2 and guidance |
| Encounter incomplete or conflicting provider evidence | Pass: visible non-success state |
| Reach depth, fan-out, or result bounds | Pass: visible `limit_reached`; no inferred exclusions |
| Run legacy impact without contextual flags | Pass: frozen P47 text and JSON unchanged |

## Human Verification

- Help text identifies contextual mode as experimental and advisory.
- Concise output groups required and contextual results and stays below the
  2 KiB default-output budget on the exercised repository flow.
- Detailed JSON includes state, paths, score components, exclusions, limitations,
  and an analysis digest.
- No browser or axe-core run applies because this change has no web surface.

## Evaluation Decision

All eight frozen corpus cases matched expected states and required labels. The
held-out ranker and stable-key baseline both scored 10,000 precision-at-10 basis
points, a 0% relative gain. The feature remains explicit and advisory; promotion
to default presentation, enforcement, Assurance, or model reranking is blocked.
