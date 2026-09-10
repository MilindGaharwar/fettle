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

The initial eight-case corpus established deterministic behavior but contained no
irrelevant contextual candidates, so it could not test ranking lift. It was
superseded by the reviewed 40-case corpus-v2 evaluation.

Both blinded reviews and owner reconciliation resolved all 434 disagreements
across 37 cases. Under the frozen eligibility rule, 10 development and 7 held-out
cases remained eligible, below the required 20 per split. Development required
recall was 96.30%; held-out required recall was 78.05%. On eligible held-out
cases, ranker precision at 10 was 20.00% versus 17.14% for stable-key ordering,
a 16.69% relative gain, but the paired 95% gain interval of 0 to 5.71 percentage
points included zero.

The implementation package CI-3 ranking promotion gate, corresponding to
research hypothesis CI-2, is falsified by sub-100% required recall, insufficient
eligible cases, and inconclusive precision evidence. The feature remains explicit
and advisory; promotion to default presentation, enforcement, Assurance, or model
reranking is blocked. The authoritative retained result is
`docs/contextual-impact-corpus/evaluation.json`.
