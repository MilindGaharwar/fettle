# UX Spec: Change Integrity Hypergraph

Status: APPROVED; P44 contract implementation complete, later user-facing packages remain gated

Architecture: [change-integrity-architecture.md](change-integrity-architecture.md)

Implementation plan:
[change-integrity-implementation-plan.md](change-integrity-implementation-plan.md)

## Jobs To Be Done

When I change code, contracts, specifications, tests, configuration, or
documentation, I want Fettle to identify the affected repository knowledge and
required actions, so I can complete the change without overlooking dependent
artifacts.

When several agents work independently, I want Fettle to explain overlapping
impact before they edit or integrate, so concurrent work does not silently
overwrite or invalidate another agent's assumptions.

When Fettle reports that impact is resolved, I want the result bound to an exact
repository snapshot, policy, providers, graph, and evidence set, so I can trust
that stale analysis did not authorize the change.

When graph analysis cannot be trusted, I want a visible, actionable non-pass
state rather than an empty result, so I know whether to rebuild, install a tool,
run broader verification, or request an override.

## Personas

- New adopter: needs a useful first result without understanding hypergraphs,
  providers, graph generations, or content-addressed snapshots.
- Developer or agent operator: needs the affected artifacts, required actions,
  and exact next command with minimal terminal noise.
- Repository maintainer: needs provider completeness, rationale, and controlled
  graduation from advisory to enforcement.
- Platform engineer: needs stable JSON, policy provenance, immutable snapshot
  binding, retention, and failure semantics across repositories.
- Multi-agent integrator: needs claim overlap, target advancement, unresolved
  obligations, and merge-candidate evidence before integration.
- Accessible terminal user: needs status and severity conveyed through text and
  exit codes without color, animation, cursor rewriting, or mouse interaction.

## User Journey

| Phase | User action | Sees | Desired feeling | Failure to prevent |
|---|---|---|---|---|
| Discover | Runs `fettle graph status` or first impact command | Current graph capability, providers, snapshot class, and next action | Oriented | Graph jargon without a task |
| Analyze | Runs `fettle impact <paths>` | Changed inputs, affected artifacts, confidence, and required actions | In control | Empty output interpreted as unaffected |
| Work | Edits an affected artifact | Concise new or resolved obligation | Guided | Repeated full graph dumps |
| Verify | Runs the recommended command | Evidence attached to exact snapshot and obligation | Confident | Evidence from another revision accepted |
| Resolve | Marks or proves each required action | Resolution state and rationale | Complete | Checkbox completion without evidence |
| Integrate | Checks latest target or CI merge candidate | Current graph digest, overlap, unresolved work, and verdict | Safe | Worker evidence reused after target advanced |
| Recover | Encounters unavailable or corrupt graph | Plain cause, preserved work, exact repair command | Unblocked | Graph failure disables diagnosis |

## Proposed Command Surface

Names are contracts for planning and may change only through an explicit CLI
review before implementation.

### `fettle graph status [--detailed] [--json]`

Default output answers:

1. What snapshot is requested?
2. Is a matching complete graph available?
3. Which required providers are complete, incomplete, or failed?
4. Can this graph support advisory analysis or strict enforcement?
5. What exact command should the user run next?

### `fettle graph build [--snapshot working|HEAD] [--full]`

Explicitly materializes inputs and builds a graph. The command never reports
success for a partially published generation. `--full` bypasses incremental
reuse when that capability later exists.

### `fettle impact <path>... [--base REF] [--detailed] [--json]`

Default output groups:

- Changed or selected inputs.
- Directly affected artifacts.
- Required actions.
- Uncertain review items.
- Provider gaps that limit the conclusion.
- Exact verify or rebuild command.

### `fettle obligations [--open] [--work-item ID] [--json]`

Lists required impact resolutions. Resolution commands are not introduced until
the evidence and override schema is implemented; early stages remain report-only.

## Interaction and Time Budgets

- First useful advisory impact result: one command, no setup prompt when native
  providers can analyze the repository.
- Default impact output: at most five groups and 2 KiB; additional facts require
  `--detailed` or `--json`.
- Clean/current status: one concise line plus snapshot short ID.
- Hook path: no graph build, migration, or unbounded traversal inside existing
  250/400/600 ms dispatcher budgets.
- Explicit status from a warm ephemeral or admitted cache: p95 below 500 ms on
  the maintained representative corpus.
- Explicit cold graph build: visible progress after one second; cancellable
  without publishing a partial generation.
- Impact traversal: depth, fan-out, and result limits are always reported when
  truncation occurs.

## Required States

### First-Time Empty

No graph generation exists. Explain that Fettle will derive one from the
repository, identify the selected snapshot class, and show `fettle graph build`.
Do not display an empty table that resembles “no dependencies.”

### Cleared Empty

The current complete graph produced no affected artifacts or open obligations.
State which providers and scope support that conclusion. Distinguish this from
no applicable providers.

### Filtered Empty

The selected path, work item, provider, or obligation filter has no matches.
Name the filter and show how to clear it.

### Loading Brief

Remain quiet for sub-second status and traversal operations.

### Loading Long

Show phase (`materializing`, `provider`, `assembling`, `validating`), provider
name where safe, elapsed time, and cancellation behavior. Never claim a
generation exists before atomic publication.

### Populated

Group direct impact, transitive impact, obligations, uncertain review, and
provider limitations. Show confidence in text, not only color.

### Error Recoverable

For provider timeout, lock contention, malformed output, graph mismatch, or
cache corruption, state what failed, whether existing source work is safe, and
one exact recovery command. Preserve all operator work.

### Error Fatal

For policy tampering, path escape, unverifiable required snapshot, or invalid
strict override, reject the action and direct the user to a graph-independent
diagnostic command. Do not offer a silent fallback.

### Offline

Native local providers continue. Network-backed providers are `unknown` or
`unavailable` with their last successful historical generation labelled as
historical. Required CI policy decides whether the operation fails.

### Stale or Superseded

Show the historical graph's snapshot and the requested snapshot. Offer rebuild
or historical inspection. Never label a superseded graph current and never use
it to authorize a critical action.

### Incomplete

Name each missing or failed required provider and which conclusions are unsafe.
Do not collapse incomplete into “zero affected files.”

### Corrupt

Report digest or schema validation failure. Offer cache removal and full
rebuild. `doctor` and recovery remain available without opening the graph.

## Finding Contract

Default operator-facing findings contain, in order:

1. Decision and stable rule identifier.
2. Snapshot short ID and `current`, `incomplete`, or `superseded` label.
3. Affected artifact or obligation.
4. One-sentence reason naming the traversed relationship.
5. Confidence/trust class in text.
6. Recommended action.
7. Exact rerun or verification command.

Detailed output may add full digests, provider identities, edge roles,
traversal path, policy provenance, limits, and evidence IDs. Raw provider output
is bounded and redacted.

## Advisory, Strict, and Regulated Modes

| Mode | Behavior |
|---|---|
| Advisory | Reports impact, obligations, uncertainty, and provider failure; no graph fact blocks |
| Strict | Requires complete approved providers, immutable snapshot binding, resolved obligations, non-overlapping strict claims, and current integration evidence |
| Regulated | Adds retained attestations, authorized expiring overrides, protected integration, and organization-defined signing/approval requirements |

Mode changes follow existing layered policy and delegation monotonicity. A child
session cannot use local configuration to weaken inherited strict policy.

## Progressive Disclosure

- Default: verdict, affected groups, obligations, limitations, next command.
- `--detailed`: traversal paths, provider completeness, full confidence and
  provenance, snapshot composition, and timing.
- `--json`: complete stable machine contract.
- Historical generations, provider internals, and cache diagnostics remain
  hidden unless requested or needed for recovery.

## Accessibility

- Text labels accompany all statuses; ANSI color is optional decoration.
- Output remains understandable under `NO_COLOR=1`.
- Machine output uses stable fields and documented exit codes.
- Long-running progress appends bounded lines when stderr is not a TTY rather
  than continually rewriting one line.
- No instruction depends on icons, color, cursor movement, or mouse input.
- Tables have equivalent JSON and concise line-oriented forms.

## BDD Acceptance Scenarios

### Scenario: First graph build from an immutable commit

Given a repository has a committed HEAD and supported native artifacts
When the operator builds a graph for HEAD
Then Fettle materializes the exact Git tree
And every provider reads that snapshot
And the completed graph records source, policy, provider, rule-set, and graph digests
And no partial generation is visible before publication.

### Scenario: Identical source produces an identical graph

Given source snapshot, effective policy, provider manifest, and traversal rules are unchanged
When two clean builds run in separate processes
Then their canonical source and graph digests are byte-identical
And insertion order, absolute checkout path, and process timing do not change them.

### Scenario: Working tree changes during graph construction

Given an advisory working-snapshot graph is being built
When a covered file changes while inputs are materialized or providers run
Then Fettle does not publish a mixed graph as current
And it retries within policy or reports the build as unknown
And the operator sees the changed path class and rebuild command.

### Scenario: File changes and is restored during construction

Given graph construction has started
When a file changes, a provider could observe the transient content, and the file is restored before completion
Then no graph built from mixed live reads is published
And acceptance depends on providers reading an immutable materialization or a fully revalidated read set.

### Scenario: Repository changes after validation but before an action

Given Fettle validated graph generation G
When the mutable worktree changes before an irreversible external action
Then Fettle either executes against immutable snapshot G or rejects the mutable-target action
And it does not attest that the current worktree was governed by G.

### Scenario: Required provider fails

Given a strict traversal requires the Python import provider
When parsing fails, the provider times out, or output is malformed
Then dependent impact is `unknown` or `tool_error`, not unaffected
And strict verification exits non-zero
And an interactive advisory remains visibly fail-open without success attestation.

### Scenario: Optional heuristic provider is unavailable

Given native authoritative and derived providers are complete
And an optional heuristic provider is unavailable
When advisory impact runs
Then Fettle reports the missing enrichment
And preserves conclusions supported by complete approved providers
And does not imply the heuristic provider ran.

### Scenario: Unknown work-item scope conflicts conservatively

Given one live strict work item has no complete predicted footprint
When another strict agent attempts a concurrent claim
Then Fettle refuses parallel authorization
And explains that unknown scope conflicts with all strict claims
And identifies the scope or provider evidence needed to proceed.

### Scenario: Two graph-expanded claims overlap

Given two work items have disjoint declared globs but graph expansion reaches a shared caller
When strict claims are acquired concurrently
Then exactly one incompatible claim set can be authorized
And the refusal identifies the shared artifact and traversal reason
And no lost update occurs in coordination state.

### Scenario: Edit exceeds accepted footprint

Given an agent holds a strict work-item claim with accepted footprint F
When it edits a governed file outside F
Then Fettle records a scope-change event
And recalculates overlap and obligations
And does not silently treat the original footprint as sufficient.

### Scenario: Target branch advances before integration

Given worker evidence is bound to base B and candidate C
When the target advances to B2 before integration
Then Fettle recomputes the graph and obligations for the resulting merge candidate
And rejects evidence that applies only to B plus C
And reports the exact stale and requested snapshot IDs.

### Scenario: Obligations are resolved

Given impact closure I contains required obligations
When each obligation is updated, verified unchanged, marked not applicable with reason, or validly overridden
Then completion evidence records each resolution and its supporting evidence
And the closure is complete only for its exact graph and snapshot.

### Scenario: Override is invalid

Given strict policy permits only authorized, expiring overrides
When an override lacks actor, reason, expiry, revision, policy digest, graph digest, or prior evidence
Then Fettle rejects it
And reports the missing field and approval route
And does not serialize the result as pass.

### Scenario: Graph cache is corrupt

Given an optional persisted cache was admitted and its generation fails digest or referential validation
When a graph-dependent command runs
Then Fettle marks the cache corrupt and does not query it for authorization
And `fettle doctor` remains available
And the operator receives an exact delete-and-rebuild action.

### Scenario: Graph store is locked or read-only

Given the optional store cannot open or publish within its bounded timeout
When a critical graph operation runs
Then Fettle reports unavailable and does not fall back to a superseded generation
And an advisory command can continue only without success attestation.

### Scenario: Graph construction exceeds limits

Given a repository or provider exceeds configured files, bytes, runtime, nodes, incidences, or traversal limits
When analysis runs
Then Fettle stops safely and identifies the exceeded limit
And reports affected conclusions as incomplete
And preserves graph-independent editing and recovery commands.

### Scenario: CI verifies the immutable merge candidate

Given a pull request is evaluated in a merge queue or synthetic merge worktree
When required change-integrity verification runs
Then evidence records base, candidate, resulting tree or merge commit, policy, providers, graph, and obligations
And any required provider failure or unresolved obligation fails closed.

### Scenario: Direct bypass has no Fettle attestation

Given a user writes files directly or commits with local hooks bypassed
When no graph-bound Fettle verification ran
Then Fettle does not claim those actions were governed
And independent CI reconstructs the required graph and rejects stale or missing evidence according to policy.

### Scenario: Historical graph inspection

Given a valid graph exists for an older snapshot
When the operator requests historical details explicitly
Then Fettle displays the generation as superseded with its original context
And no command can use it to authorize the current snapshot.

### Scenario: Recovery works without the graph

Given graph construction and optional storage are unavailable
When the operator runs graph status, doctor, or rebuild diagnostics
Then the graph-independent kernel reports the failure and recovery route
And destructive-command and delegated-policy protections remain operational.

## UX Success Metrics

- 100% of non-pass graph outcomes include a specific next action.
- Zero required provider failures are represented as unaffected or pass.
- Zero superseded generations authorize a current critical action.
- Identical immutable inputs produce identical graph digests across maintained platforms.
- Median advisory impact requires one command and at most one follow-up command.
- Default output remains within the existing 2 KiB advisory budget.
- No graph build or migration runs inside an interactive hook.
- Graph failure never prevents `doctor`, status diagnosis, or cache recovery.
- Strict mode is not offered until the maintained adversarial BDD corpus passes.
