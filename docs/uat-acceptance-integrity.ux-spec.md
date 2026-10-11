# UAT Acceptance Integrity

## Job and Personas

When accepting a specified change, an operator needs reproducible evidence that
the required behavior actually ran, without routinely repeating tests by hand.
New users need an honest readiness result; power users need consistent JSON and
exit codes; keyboard/screen-reader users need plain diagnostics independent of
color. No new visual interface or navigation is introduced.

## Journey

1. Run `fettle uat doctor`: see capabilities and actionable blockers.
2. Run `fettle uat run` with explicit consent: preserve normal host permissions,
   isolate the session and retain actual results. Consent is not permission bypass.
3. Run `fettle uat report`: see every required scenario, evidence gaps and recovery.
   A completed exploration is not automatically a completed acceptance decision.

The normal journey is three CLI commands. Runtime is bounded by configured
timeouts, not a promised response latency. Reports survive process termination;
the user can inspect them without rerunning paid agents. Native permission blocks
must not be auto-answered or presented as passes.

## States

| State | Observable behavior |
| --- | --- |
| First-time empty | No active contract: non-pass and spec-authoring guidance |
| Cleared empty | Missing evidence: non-pass and rerun guidance, never inferred success |
| Filtered empty | Empty or reduced inventory: explicit coverage error |
| Loading brief | Running session is not acceptance evidence |
| Loading long | Bounded timeout persists incomplete state and recovery information |
| Populated | Per-scenario result, evidence basis and consistent machine-readable completion |
| Recoverable error | Malformed/stale inputs rejected with reason; preserve original evidence |
| Fatal error | Required execution/capture failed: non-pass, no success sidecar |
| Offline | Unavailable model/runtime is blocked; retained reports remain inspectable |
| Stale | Changed source/requirements invalidate prior acceptance; rerun required |

## Acceptance Scenarios

- Given valid captured execution with a complete frozen contract, when all
  required oracles pass, then the qualified surface may report acceptance.
  Positive capability is limited to the qualified read-only CLI contract path;
  ordinary explorer transcripts remain non-confirming.
- Given only agent prose and a hash of that prose, when the agent says matches,
  then the report says INDETERMINATE and explains missing independent execution.
- Given an altered artifact body, when reporting, then content mismatch is
  rejected even if the supplied hash still matches the transcript.
- Given a real failing command after scenario exploration, when reporting,
  then session, CLI, trace and canonical result all remain non-pass.
- Given empty, duplicate, removed or omitted required IDs, when reporting,
  then the missing coverage remains visible and acceptance is impossible.
- Given a normal host permission request, when unattended execution cannot
  proceed, then the scenario is blocked; no bypass flags or invented approval.
- Given old claim-only evidence, when inspected after upgrade, then observations
  remain visible but previous CONFIRMED labels are not retained as authority.

## Compatibility and Accessibility

### Approved Read-Only CLI Contract

The operator reviews an explicit action/oracle JSON contract before running
`fettle uat run --contract <path> --approve-contract <sha256> --yes --json`.
The approved digest is required; consent alone cannot approve changed content.
The command captures output without launching an explorer. Existing report
inspection revalidates controller evidence without launching commands or models.

- Given an approved exact-output oracle, when the sandboxed product emits the
  expected bytes and exit code, then the scenario is confirmed from controller
  observations, not its transcript.
- Given a seeded wrong output, when the same oracle executes, then acceptance
  fails even if the product prints `OUTCOME: matches`.
- Given changed contract/source/policy or missing controller storage, when the
  report is replayed, then acceptance is non-pass with rerun guidance.
- Given an unavailable sandbox or attempted filesystem/network/process operation
  outside its grants, when execution is requested, then no unsandboxed retry occurs.
- Given excessive output, timeout or detected secret output, when capture ends,
  then the report remains incomplete and does not publish raw secrets.

The current surface is macOS, read-only, network-free CLI only. Unsupported
surfaces remain inspectable through existing report-only/manual workflows.
Commands have finite deadlines; JSON output is one complete object, and errors
include recovery guidance. Visual UI specification is not applicable.

Preflight uses `fettle uat doctor --contract <path> --approve-contract <sha256>`.
It validates contract coverage and launches only a bounded nonce echo under the
capture sandbox, not the configured product action. A successful preflight proves
prerequisites only; the subsequent run may still fail its behavioral oracle.
Inspect the retained result using `fettle uat report --worktree <product-root>`.
This read-only path runs in the current product tree, whose bytes are frozen and
revalidated, rather than creating a write-capable agent worktree.

Keep public command names and retained observations. Do not migrate AI evidence
into operator attestation. Status changes are deliberate integrity corrections.
Diagnostics are plain text with scenario IDs and recovery actions; JSON is the
automation surface. No pointer, motion, viewport or color dependency applies.
Do not emit raw secrets, silently delete evidence, or launch a model from report
inspection without its explicitly configured evaluator.

## Isolated Network Contract: Implementation Target

Keep the doctor/run/report journey and the state table above. The next contract
version explicitly selects `api` or `web`, a digest-pinned trusted runtime,
product startup arguments, a container-local port and bounded scenario steps.
The operator approves the complete contract digest before product execution.
Doctor verifies runtime availability without running product startup commands.
There are no new UI components; keyboard/plain-text and JSON interfaces remain.

Product source is frozen into a controller-created read-only volume. Product
state has a distinct writable volume; neither container sees host directories,
Docker sockets or retained evidence. An internal isolated bridge has no gateway,
no external DNS and no published ports. Separate trusted collectors retain raw
responses outside the product. Images, source, contract and policy bind receipts.
An unrestricted agent is not launched by this contract path.

- Given an approved API request, when the product returns the required status
  and exact body, then the controller confirms from actual HTTP observations.
- Given a seeded wrong response, redirect, server error or output overflow,
  when assertions fail or capture is unsupported, then acceptance is non-pass.
- Given unavailable Docker, a changed image, malformed approval or missing source,
  when doctor/run executes, then it explains the blocker without a host fallback.
- Given an approved browser form flow, when the controller fills labeled fields
  and activates named controls, then it checks observed page results and retains
  independent observations, not product-supplied outcome labels.
- Given state written before an approved restart, when the same state is read
  afterward, then both actual restart completion and persistence must be observed.
- Given interruption or cleanup failure, when reporting, then missing terminal
  success cannot become acceptance. Resume requires a new complete capture;
  partial observations cannot be merged into a successful session.

Implementation and qualification are separate: these scenarios are requirements,
not a claim that API/browser/stateful acceptance is already available.

## Recovery And Browser Audit Extension

An approved rerun takes an exclusive per-product lease, recovers only journaled,
owner-labeled resources on the original Docker daemon, and starts from fresh
observations. A live controller/client or changed daemon blocks recovery. A killed
controller leaves a non-terminal checkpoint; partial observations cannot pass.

Browser contracts may explicitly add an `audit` step to the existing flow. It
requires zero axe WCAG A/AA violations, incomplete accessibility checks, page or
console errors, failed requests and HTTP error responses. A bounded viewport PNG
is retained in the external controller receipt, with its hash and producer bound
to canonical evidence. Screenshot capture is evidence, not a visual oracle.
Only synthetic, non-sensitive product content is supported for this opt-in.
Likely secret text/input content, excess output, unavailable axe or capture errors
block acceptance and suppress images. Automated axe checks do not prove complete
accessibility, and this contract does not claim human visual judgment.

- Given SIGKILL and a restarted dedicated VM, an approved fresh run removes only
  its recorded orphans and leaves unrelated resources untouched.
- Given a running controller or surviving Docker client, a concurrent run cannot
  replace its checkpoint or clean up its resources.
- Given a browser audit on a conforming synthetic form at desktop/mobile widths,
  the controller retains independent diagnostics and a bounded screenshot.
- Given an unlabeled control, JavaScript error or failed HTTP request, the audit
  is non-pass even when the expected success text is visible.
- Given missing or modified screenshot bytes, canonical evidence is invalid.

These extensions use the existing doctor/run/report commands and state table.
There is no added navigation, GUI, or routine human test-execution prerequisite.

## Isolated Native Proposals

Native agents may return action-only JSON from a separate no-host-mount VM.
The operator supplies that file via `uat run --proposal` alongside the separately
approved contract and consent. No credentials, product source, controller receipts
or expected-output oracles are sent to the proposer. Its output is untrusted:
exact action order, coverage, scenario digest and execution bounds must match the
approved contract. Proposals cannot add oracles or runtime settings. A valid
proposal still triggers fresh controller execution; native prose never confirms.

- Given changed actions, added expected output, partial coverage or malformed JSON,
  the run rejects the proposal before launching product execution.
- Given an exact action proposal, only independently captured product observations
  against the separate approved oracle can confirm acceptance.
- Given a native denial reported only in prose, absent execution events remain
  an evidence gap even when an independent check confirms no file was created.

This is an approved-action bridge, not autonomous scenario discovery or automatic
contract approval. Authentication and host permission prompts are never answered
by the bridge. Existing CLI error and stale-evidence states continue to apply.

## Requirements-Derived Discovery Study

Before expanding production discovery authority, the evaluator accepts an explicitly
digest-approved synthetic corpus. A native agent receives requirements and a
one-argument CLI interface, not source, seeds, expected verdicts or supplied tests.
It proposes at most 12 bounded input strings. A separately approved declarative
integer-range oracle supplies exact expected outputs. The existing controller
executes the selected tests and validates canonical results. The agent never judges
acceptance. This is input discovery, not adaptive exploration or general oracle
synthesis; the range-classifier domain is deliberately narrow.

The evaluator operator reviews the corpus, runs one bounded study and reads a JSON
report containing selected inputs, contradictions, missed defects and blocked cases.
Output is reserved before the first native call; an interrupted or repeated trial
cannot overwrite its evidence. Existing plain-text/JSON accessibility and state
rules apply. Missing inputs and unavailable native runtime are blocked; malformed
corpora fail before execution; stale approval requires review; no visual UI applies.
This is evaluation tooling, not a new public `fettle uat` command or a capability
promotion. The study cannot establish broad human parity.

- Given requirements with a boundary, when the agent chooses a boundary probe,
  then the independent oracle can contradict a defective product through canonical
  controller evidence, without supplying the boundary probe to the agent.
- Given a defect the chosen inputs miss, when the product passes those inputs,
  then the study records a missed defect/false pass and fails qualification.
- Given malformed, duplicate, excessive or oracle-bearing agent output, when the
  proposal is validated, then no product executes and the trial stays non-pass.
- Given an existing output or changed corpus digest, a repeated run is rejected
  before any native execution.