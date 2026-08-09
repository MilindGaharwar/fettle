# Advisory Code-Intelligence Evaluation

Status: COMPLETE; local advisory use only, no Fettle or agent integration

Date: 2026-08-09

## Decision

`codebase-memory-mcp` v0.9.0 is useful for optional, operator-run code search,
but it is not admitted as a Fettle provider, evidence source, or authority. Its
fast local index was responsive, yet the evaluated interface did not bind
ordinary query results to the complete working source and configuration identity
required by Fettle. Default exclusions also omitted `docs/` and fixture inputs.

Keep the binary outside the repository for bounded experiments. Do not register
it with an agent, run its MCP server, enable watching or automatic indexing, or
use its output to resolve an obligation or authorize an action.

## Supply-Chain And Runtime Boundary

- Release: `DeusData/codebase-memory-mcp` v0.9.0, standard macOS arm64 binary.
- Archive checksum: verified against the release `checksums.txt` before install.
- Installed binary SHA-256:
  `dc7a383664b5fda407f22a81df538c6282c5dbbcc58cf3c97605dbd5dcf13d79`.
- Install target: `~/.local/bin/codebase-memory-mcp` via `--skip-config`.
- Sigstore/SLSA provenance: **not verified**. GitHub verification failed with
  `verifying with issuer "sigstore.dev"`; checksum verification is not a
  substitute for provenance verification.
- Configuration after install: `auto_index=false`, `auto_watch=false`; no agent
  configuration was changed and no UI, daemon, or MCP process remained running.
- Repository persistence was disabled. No `.codebase-memory/` artifact was
  created. Local derived cache usage after evaluation was approximately 19 MB.

## Reproduction

Run only from a trusted operator shell. The index is derived, deletable state.

```bash
codebase-memory-mcp --version
codebase-memory-mcp config set auto_watch false
codebase-memory-mcp config set auto_index false
codebase-memory-mcp cli index_repository \
  --repo-path /absolute/path/to/fettle \
  --mode fast \
  --persistence false
codebase-memory-mcp cli index_status \
  --project <project-name>
codebase-memory-mcp cli search_code \
  --project <project-name> \
  --pattern EvidenceReference \
  --mode compact \
  --limit 20
codebase-memory-mcp cli search_graph \
  --project <project-name> \
  --query "evidence reference" \
  --limit 20
codebase-memory-mcp cli detect_changes \
  --project <project-name> \
  --scope all \
  --depth 2 \
  --since HEAD
```

Project names are tool-derived and machine-specific. Discover the current name
with `codebase-memory-mcp cli list_projects` rather than treating this value as
portable identity.

## Observations

| Check | Observed result | Interpretation |
|---|---|---|
| Fast index | 0.96 s; 5,981 nodes and 32,833 edges | Suitable latency for an explicit advisory command |
| Index coverage | 27 excluded directories; `docs/`, `tests/fixtures/`, `.fettle/`, and generated/vendor paths omitted | Not complete enough for documentation, policy, adversarial-fixture, or authoritative impact claims |
| Symbol search | 0.31 s for `EvidenceReference`; relevant implementation and tests returned | Useful discovery aid; result limits and inferred enrichment remain visible |
| Graph search | 0.06 s; 52 matches with truncation reported | Useful broad navigation, not proof of dependency or completeness |
| Architecture overview | 0.15 s | Included false route/layer inferences from path-like fixture strings, so structural summaries require source verification |
| Dirty changes | Detected the modified documentation path twice and returned no impacted symbols | Dirty awareness exists, but duplicate paths and excluded docs prevent reliable impact use |
| Freshness/status | Reported `ready` and committed `head_sha`; did not expose a complete dirty source, policy, configuration, or provider digest | A query cannot establish that its graph exactly matches the candidate being governed |
| Failure behavior | Missing required CLI input returned an error and published no project | Failure was visible and contained; the message initially resembled a worker crash until its log was inspected |
| Background activity | No process remained after one-shot commands | Compatible with the bounded experiment boundary |

Token savings were not claimed: the CLI exposed neither token accounting nor a
controlled agent baseline. Tool-call count was seven substantive evaluation
operations after installation and configuration. Future value claims must compare
task success, elapsed time, calls, and cost against the same held-out tasks without
the index.

## Admission Criteria For Any Re-Evaluation

Reconsider provider status only if a later version can demonstrate all of the
following on held-out repositories:

1. Exact source snapshot, dirty content, policy/configuration, tool, and provider
   identity on every result.
2. Explicit applicability and completeness, including exclusions, parse failures,
   unsupported languages, generated content, fixtures, and deletions.
3. Deterministic bounded output with stale, partial, corrupt, and unavailable
   states that cannot become successful authority.
4. No agent configuration mutation, background process, network dependency, or
   repository persistence unless separately approved.
5. Measured improvement in repair success or cost per verified software change,
   not only faster retrieval or fewer tokens.
6. Independent provenance verification and a reviewed upgrade/revocation path.

Even after admission, external graph facts start as `external` or `heuristic`,
run in shadow mode, and cannot grant authority. Git-native snapshots, Fettle
policy, portable evidence, and independent CI remain the decision boundary.

## Memory-System Design Reference

`TencentCloud/TencentDB-Agent-Memory` was reviewed only as a design reference.
Potentially useful ideas are layered memory, provenance, access control, and
role-specific retrieval. Fettle must not adopt its dependency, inferred summaries,
default capture/retention behavior, or best-effort degradation as authoritative
evidence. Memory informs; evidence proves; policy decides; authority permits.
