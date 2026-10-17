# Where New Behavior Goes — Decision Table

One row per goal → the exact mechanism to use. If a goal is missing, add it
here and the matching implementation in the same change (drift is enforced
by `tests/test_doc_claims.py::test_behavior_map_covers_public_commands`).

## Gates and checks

| Goal | Mechanism |
|---|---|
| Add a PreToolUse guard (block/advise before a tool runs) | New check module + register in `fettle/dispatcher_registry.py::CHECKS`; wire config under `[gates.<name>]` |
| Prevent secrets entering agent context | Strict runtime secret boundary before Read/Bash/nested execution; replace output only on transports with pre-model interception; report unsupported hosts truthfully |
| Add a PostToolUse quality/finding check | Same as above with `events={"PostToolUse"}`; return findings + recovery steps |
| Add an end-of-session verdict | Check with `events={"Stop"}`; bind evidence via `fettle.trace` / `EvidenceArtifact` |
| Add or change a quality rule | Rule implementation + registration, then exercise it through `fettle check`, `fettle rules`, and `fettle verification` |
| Change cumulative calibration accounting or sparse recovery admission | Emit and validate the typed `calibration_budget_decision` in `fettle/staged_preflight.py`; bind ordered run/attempt lineage, observer lifecycle, monitor floor, support reservations, and cancellation charge; replay real emitted files through same-stage continuation and forward-stage launch |
| Preserve terminal calibration accounting when primary artifact publication fails | Retain the primary artifact failure, emit one bounded digest-bound exact-byte envelope to the accounting job log, and recover it only as non-authoritative evidence from authenticated exact-attempt job metadata; see `docs/calibration-accounting-retention.md` |
| Probe live provider retention/readback without granting accounting authority | Dispatch `.github/workflows/calibration-retention-probe.yml` only with a frozen exact SHA and unique synthetic probe ID; require deliberate primary publication failure, exact-attempt log recovery, byte equality, and a retained `passed: false`, non-authoritative diagnostic result |
| Coordinate stage-3 readiness and zero-worker containment | Validate exact-attempt typed readiness in `fettle/staged_preflight.py`; use the pinned current-run artifact handoff and exact-attempt jobs API in `.github/workflows/mutation.yml`; exercise the same producer/consumer through its isolated `readback-probe` mode with no mutation workers and only non-authoritative probe output; prove parsed scripts in `tests/test_ci.py` and observer transitions in `tests/test_staged_preflight.py` |
| Add a policy control or exception | Extend the config schema and policy merge path; expose decisions through `fettle config`, `fettle policy`, `fettle overrides`, or `fettle suppressions` as appropriate |
| Change enforcement maturity | Keep the rule advisory until evidence supports `fettle ratchet`; retain the decision in `fettle ledger` |
| Prevent CI type or coverage regression without hiding existing debt | Use `fettle.quality_ratchet` with `.github/quality-ratchet.json`; enforce zero errors in the named critical type scope and independent combined/branch coverage floors from integer coverage.py counts; retain whole-source typing as a visible advisory measurement |

## Commands and surfaces

| Goal | Mechanism |
|---|---|
| Produce the canonical Assurance Record for this change | `fettle assurance` (`fettle/assurance.py` aggregating verify stamps, mutation reports, UAT reports, governance ledger, CI binding, spec coverage) |
| Demonstrate the complete control loop without setup or network | `fettle demo` (`fettle/demo.py` over the bundled fixture and independent behavioral verifier) |
| Inspect the composed gate/check pipeline with provenance | `fettle pipeline` (`fettle/pipeline_dump.py` over `dispatcher_registry.CHECKS` + policy layers) |
| Add a user-facing CLI command | `cmd_*` function + subparser + entry in `cli.py::commands` dispatch dict + tests (`tests/test_cli.py`) |
| Add an agent host transport | `fettle/agents/<host>.py` translator + conformance fixtures + `fettle init` registration |
| Add a workspace language adapter | `fettle/adapters/` + workspace marker detection in `fettle/workspace.py` |
| Add a UAT surface driver | Capability probe in `fettle/uat/doctor.py`, driver gating in `fettle/uat/session.py`, and a `fettle uat manual` fallback walkthrough |
| Add an external analysis adapter | Implement the adapter contract under `fettle/integrations/`; register it for `fettle integrations` and document credentials and failure semantics |
| Add environment or installation diagnostics | Extend the owning probe used by `fettle doctor`; keep setup changes in `fettle init` and guided material in `fettle workflows` |

## Evidence and programs

| Goal | Mechanism |
|---|---|
| Bind a decision into durable evidence | `fettle.trace.build_evidence` / `fettle.evidence_ledger.append_record` |
| Add an evidence consumer | Parse with `fettle.evidence.parse_artifact`, validate applicability with `validate_artifact`, and preserve every invalid or incomplete state as non-pass |
| Add a graph provider (structure intelligence) | `fettle/providers/` adapter returning NodeDraft/EdgeDraft; register in `default_providers()` and expose diagnostics through `fettle graph` |
| Add a state-consistency contract type | Extend frozen schema in `fettle/state_consistency.py` via SC1 review — never ad-hoc keys |
| Author or lint a state-consistency contract | `fettle consistency init|lint|list` (`fettle/state_consistency.py` frozen schema + lint) |
| Add mutation methodology automation | Follow the staged model: preflight → execution → policy (`fettle/mutation_test.py`) |
| Validate mutation capacity without creating qualification evidence | Reuse canonical enumeration, runner accounting, and `execute_pending_mutations`; isolate dispatch under the registered `.github/workflows/mutation.yml` `capacity-validation` mode; admit fixed 16-worker preparation batches only after conservative aggregate reservations; freeze numerical decision and timer-specific censoring rules before enumeration; emit only strict `capacity_validation_*` artifacts that calibration, continuation, aggregation, and qualification consumers reject |
| Continue a partial staged preflight | Admit the source through `fettle.staged_preflight.validate_source_handoff`, revalidate compatible reports, and dispatch only the proven missing wave |
| Bound staged-preflight usage during transient GitHub job metadata | `fettle.staged_preflight.account_runner_minutes` with an explicit observation timestamp and workflow job timeout; charge dispatch-to-observation exposure without trusting revision-prone start metadata to reduce it, retain each raw snapshot and accounting result, and keep malformed or unbounded states non-pass |
| Observe bounded calibration worker waves and recover interrupted partial producers | Derive the finite lifecycle with `fettle.staged_preflight.calibration_observer_contract`; retain anomalous provider records in `account_runner_minutes`; validate cancelled producers separately and admit failed/timed-out checkpoint-only recovery only with exact producer/upload step outcomes plus source-run artifact provenance in `plan_calibration_continuation`; publish reports atomically and consolidate only an explicit validated representation inventory |
| Add a mutation target | Add the source path under `[mutation].paths`; add exact `[mutation.test_mappings]` entries when import discovery cannot select its tests; validate with `fettle mutation preflight --all` before `fettle mutation run` |
| Add or change a specification | Author the scenario under `specs/`, then use `fettle spec lint`, `fettle spec coverage`, and `fettle links` to close its evidence chain |
| Add an assurance input or release criterion | Produce a canonical `EvidenceArtifact`, aggregate it in `fettle assurance`, and compare evaluator changes with `fettle assurance-baseline` |
| Add operational reporting | Derive retained evidence through `fettle report`, `fettle insights`, or `fettle brief`; measure noise separately with `fettle bench` |
| Add anonymous operational metrics | Define bounded counters and aggregation in `fettle telemetry`; keep collection off unless organization policy enables it |
| Add CI or verification behavior | Keep local selection in `fettle verify`; put remote gate orchestration in `fettle ci` and baseline management in `fettle baseline` |

## Delegation and coordination

| Goal | Mechanism |
|---|---|
| Spawn a constrained child agent | `fettle spawn --role …` with capsule lineage (tighten-only) |
| Coordinate parallel items | Work items + claims (`fettle work claim`); use `fettle topology` for conflict advice and outcomes |
| Record or execute an implementation plan | Use `fettle plan`; feed recurring failures to `fettle learn` rather than silently changing policy |

## Public utility commands

| Goal | Mechanism |
|---|---|
| Explain a gate decision | Extend the trace vocabulary and renderer used by `fettle explain`; include a recovery action |
| Demonstrate the control loop | Keep `fettle demo` offline, deterministic, and independently verified |

## Infrastructure commands

`fettle completion`, `fettle lsp`, and `fettle worktree` are deliberately
excluded from the extension drift predicate. Their lifecycle and protocol
contracts are enforced by dedicated subsystem tests. The test contains the
same explicit frozen whitelist; there is no catch-all exemption.
