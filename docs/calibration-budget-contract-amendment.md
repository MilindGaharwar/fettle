# Calibration Budget Contract Amendment

Date: 2026-10-17

This amendment changes only the successor calibration execution contract. Historical
E3 candidate `ab302eab20333127dd5cd3981d804ba06802aefd`, successor
`02022f49ebdc44757e61f915cb9cbd757c3e39da`, and run `38988846150` remain immutable
non-pass evidence and provide no qualification credit.

## Fixed authority

- cumulative calibration ceiling: **12,000 runner-minutes**;
- launch cutoff: **10,800 runner-minutes**;
- cancellation reserve: **1,200 runner-minutes**;
- worker execution deadline: **1,740 seconds**;
- order and maximum concurrency: stage 1 `8 @ 8`, stage 2 `32 @ 16`, stage 3
  `216 @ 32`;
- maximum runs: one initial run and at most one continuation in each stage.

A continuation is admissible only when the source is the initial run for that same
stage, every retried shard has a valid compatible incomplete checkpoint explicitly
classified as `deadline_exhausted`, and cumulative accounting includes every source
run. Missing, malformed, incompatible, failed, cancelled, skipped, or otherwise
indeterminate evidence is non-pass. A continuation may not itself be continued.

## Pre-spend fit

Retained evidence estimates the calibration at about 8,100 runner-minutes with ±25%
uncertainty. The upper estimate is 10,125. Six possible workflow runs reserve at most
330 runner-minutes for the three bounded support jobs (55 per run), leaving 345
runner-minutes below the 10,800 launch cutoff for repeated setup and baseline overhead
not already represented by the uncertainty bound. The 12,000 ceiling retains the full
1,200 cancellation reserve.

At the maximum authorized concurrency of 32, the existing five-minute active-job
cancellation charge is at most 160 runner-minutes. The 1,200 reserve therefore remains
supported without weakening accounting or containment. Actual usage remains
cumulative and authoritative; the estimate does not guarantee completion or permit a
launch after the cutoff.

The retained 6–8 hour no-continuation elapsed estimate remains the baseline. A used
continuation can add up to roughly 35 minutes of worker execution plus queue, setup,
accounting, assembly, and readback time. The bounded six-run package is therefore
expected to take roughly 6–12 elapsed hours, subject to provider queues.
