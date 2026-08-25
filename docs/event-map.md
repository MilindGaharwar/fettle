# Fettle Event Map — Producers, Consumers, and Durability

Canonical index of every hook/dispatcher event in Fettle's pipeline, across
all four agent hosts. If an event is dispatched, it appears here; drift is
enforced by `tests/test_doc_claims.py::test_event_map_covers_all_events`.

## Durability classes

| Class | Meaning |
|---|---|
| **Durable** | The decision/finding is appended to the audit trace (`.fettle/trace.jsonl`) and/or bound into an evidence artifact — survives the session |
| **Live** | Exists only inside the agent session (hook response to the host); not independently retained |

All gate decisions on **PreToolUse**, **PostToolUse**, and **Stop** are
durable (logged via `fettle.trace.log_decision` when the trace is writable)
*and* live (the hook response itself). **SubagentStart** is live-only
routing information.

## Events

### PreToolUse

| | |
|---|---|
| **Producers** | Agent hosts, translated per transport into `HookContext` |
| **Host support** | Claude Code · Codex CLI · Gemini CLI · OpenCode |
| **Durability** | Durable (decision logged) + Live (hook response) |
| **Consumers** | 12 checks incl. `authorship_gate`, `destructive_guard`, `capsule_guard`, `mcp_trust_gate`, `boundary_rules`, `config_protect`, `bash_audit`, `loop_detect`, `tdd_gate`, `claims_gate`, `artifact_gate`, `deploy_gate` |

Fires before a tool executes. Checks may block (enforce), advise
(advisory), or allow. This is where file-authority (P52) and destructive-
command protection live.

### PostToolUse

| | |
|---|---|
| **Producers** | Agent hosts, translated per transport |
| **Host support** | Claude Code · Codex CLI · Gemini CLI · OpenCode |
| **Durability** | Durable (findings logged) + Live (advisory context returned) |
| **Consumers** | 17 checks incl. `adapter_check`, `quality_gate`, `complexity_check`, `coverage_gate`, `boundary_rules`, `scope_creep`, `post_bash_doc_check`, `provenance_gate`, `lean_sniffers`, `session_report` |

Fires after a tool completes. Returns findings and recovery steps while the
generation loop can still act on them.

### Stop

| | |
|---|---|
| **Producers** | Agent hosts, translated per transport |
| **Host support** | Claude Code · Gemini CLI · OpenCode (Codex: per conformance fixtures) |
| **Durability** | Durable (verdict + verification stamp) + Live (stop decision) |
| **Consumers** | 9 checks incl. `verify_gate`, `stop_quality_gate`, `ci_gate`, `ci_push_record`, `completion_gate`, `completion_manifest_gate`, `commit_message`, `worklog`, `tla_sync_stop` |

Fires when the agent session ends its turn. Enforces the verification-stamp
contract and remote-CI binding before a session may claim completion.

### SubagentStart

| | |
|---|---|
| **Producers** | Claude Code |
| **Host support** | **Claude Code only** — enforced by `tests/test_host_event_parity.py` and the capability matrix (`fettle/host_capabilities.py`) |
| **Durability** | Live (routing only) |
| **Consumers** | Dispatcher routing; capsule/worktree context injection for spawned children |

**Why not the other hosts?** Their extension APIs expose no subagent-start
signal: Codex's hook feature and Gemini's event set (BeforeTool/AfterTool/
AfterAgent) have no such event, and OpenCode's plugin API v1 offers
tool/session events only. This is a host capability, not a Fettle gap.

**Delegation is still host-equal.** `fettle spawn` works identically on all
four hosts through env lineage (`FETTLE_POLICY_CAPSULE` +
`FETTLE_PARENT_SESSION`), which the dispatcher reads host-agnostically.
If a future host version emits a subagent-start signal, the parity test
fails and demands a matrix + translator update before it can be used.

Fires when a subagent session starts. Carries capsule lineage so delegated
children inherit tightened policy (never loosened).

## Cross-cutting consumers (not event-specific)

- **Audit trace** (`fettle.trace`) — receives every durable decision;
  hash-chain upgrade path via `fettle.evidence_ledger`.
- **Evidence artifacts** (`EvidenceArtifact`) — canonical records for
  verify stamps, UAT reports, ledger anchors.
- **Health telemetry / CI push record** — bounded operational signals.
