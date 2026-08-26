# Where New Behavior Goes — Decision Table

One row per goal → the exact mechanism to use. If a goal is missing, add it
here and the matching implementation in the same change (drift is enforced
by `tests/test_doc_claims.py::test_behavior_map_covers_public_commands`).

## Gates and checks

| Goal | Mechanism |
|---|---|
| Add a PreToolUse guard (block/advise before a tool runs) | New check module + register in `fettle/dispatcher_registry.py::CHECKS`; wire config under `[gates.<name>]` |
| Add a PostToolUse quality/finding check | Same as above with `events={"PostToolUse"}`; return findings + recovery steps |
| Add an end-of-session verdict | Check with `events={"Stop"}`; bind evidence via `fettle.trace` / `EvidenceArtifact` |

## Commands and surfaces

| Goal | Mechanism |
|---|---|
| Produce the canonical Assurance Record for this change | `fettle assurance` (`fettle/assurance.py` aggregating verify stamps, mutation reports, UAT reports, governance ledger, CI binding, spec coverage) |
| Classify mutation survivors into behavioral vs waived | `fettle mutation_classify` (`fettle/survivor_classify.py` + waiver registry) |
| Inspect the composed gate/check pipeline with provenance | `fettle pipeline` (`fettle/pipeline_dump.py` over `dispatcher_registry.CHECKS` + policy layers) |
| Add a user-facing CLI command | `cmd_*` function + subparser + entry in `cli.py::commands` dispatch dict + tests (`tests/test_cli.py`) |
| Add an agent host transport | `fettle/agents/<host>.py` translator + conformance fixtures + `fettle init` registration |
| Add a workspace language adapter | `fettle/adapters/` + workspace marker detection in `fettle/workspace.py` |
| Add a UAT surface driver | Capability probe in `fettle/uat/doctor.py`, driver gating in `fettle/uat/session.py`, manual fallback walkthrough |

## Evidence and programs

| Goal | Mechanism |
|---|---|
| Bind a decision into durable evidence | `fettle.trace.build_evidence` / `fettle.evidence_ledger.append_record` |
| Add a graph provider (structure intelligence) | `fettle/providers/` adapter returning NodeDraft/EdgeDraft; register in `default_providers()` |
| Add a state-consistency contract type | Extend frozen schema in `fettle/state_consistency.py` via SC1 review — never ad-hoc keys |
| Add mutation methodology automation | Follow the staged model: preflight → execution → policy (`fettle/mutation_test.py`) |

## Delegation and coordination

| Goal | Mechanism |
|---|---|
| Spawn a constrained child agent | `fettle spawn --role …` with capsule lineage (tighten-only) |
| Coordinate parallel items | Work items + claims (`fettle work claim`); topology advisor for conflicts |

## Internal commands (excluded from drift predicate)

`spawn`, `worktree`, `completion`, `lsp`, and other infrastructure commands
are covered by their own subsystem tests rather than this table.
