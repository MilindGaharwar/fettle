# Completion Checkpoint Implementation Plan

## User Story

As a maintainer, I want valid incomplete evidence to cross commit and ordinary CI
boundaries so that remote acceptance can run without weakening merge or release.

## Assumptions

- `evaluate_manifests` remains the sole evidence evaluator.
- Exit 0/1/2 in the result remains complete/valid-incomplete/invalid.
- Only CLI process status changes under an explicit `--checkpoint` flag.
- The repository's protected required check is `CI required`.

## Tradeoff

Changing evaluator exit semantics would blur evidence state. Instead, preserve the
result and adapt only the explicit checkpoint command boundary. A separate strict CI
job keeps merge protection visible while independent jobs continue.

## Blast Radius

- `fettle/cli.py`: explicit flag and process-exit selection.
- `tests/test_completion.py`: actual CLI behavior and preserved payload assertions.
- `.pre-commit-config.yaml`: checkpoint boundary.
- `.github/workflows/ci.yml`: checkpoint in test legs, strict independent job.
- `tests/test_release_workflow.py`: workflow dependency contract.
- Release workflow and `fettle/release_gate.py`: unchanged.

## Success Criteria

1. Complete: strict and checkpoint both exit 0.
2. Every valid-incomplete fixture: strict exits 1, checkpoint exits 0, payload stays incomplete.
3. Every invalid fixture: strict and checkpoint exit 2.
4. Pre-commit uses checkpoint mode.
5. Linux and Windows jobs have no completion dependency and can run.
6. Strict completion is a separate dependency of `CI required`.
7. Release workflow remains strict.
