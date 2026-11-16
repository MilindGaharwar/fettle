# Deferred Decision: Agent Trajectory And ATIF Inspection

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/review.md).

Status: NO_GO as a standalone Fettle program; retained as research provenance

Date: 2026-09-27

## Decision

Do not implement an ATIF parser, trajectory inspection command, trajectory store,
or external-trajectory replay path. No concrete diagnostic consumer was found
that existing Fettle trace, lineage, session-report, ledger, or a narrowly scoped
future run-manifest field could not serve with less risk.

The original proposal was replaced by the
[Fettle Review plan](fettle-review-implementation-plan.md), which addresses the
actual user need: understand one change's intent, logic, evidence, risks, and
unknowns in plain English and visually.

## Evidence

- Fettle already normalizes host events, composes deterministic check decisions,
  propagates tighten-only delegated policy, records lineage and decision traces,
  emits completion reports, validates canonical evidence, and evaluates Assurance
  and completion independently.
- Jaz revision `0803d4971be785e95b80054b02259664d70fa3da` supplied useful lifecycle
  ideas but is an agent runtime, not a Fettle authority.
- The inspected Jaz recorder emits `ATIF-v1.7`; the observed Harbor RFC identifies
  `ATIF-v1.8`. Similar fields do not establish compatibility.
- Raw trajectories may include prompts, reasoning, messages, tool arguments,
  observations, credentials, personal data, paths, images, and audio references.
- A trajectory can report activity and declared lineage. It cannot establish
  requirement correctness, security, UAT success, or release readiness.

## Preserved Constraints

- Execution context and later inspection context must never be merged.
- Missing historical source, policy, scope, producer, and environment bindings
  remain unknown; current Assurance context cannot backfill them.
- Imported declarations cannot populate Fettle-observed facts, establish candidate
  identity, enter an attested claim set, satisfy completion, alter Assurance, or
  become a P42 replay oracle.
- `INSPECTED` would mean parser status only, never successful software.
- No external references, media, commands, network requests, or model calls may be
  followed from untrusted trajectory content.

## Ownership Of Remaining Work

- The delivered P41 successor owns durable commit-linked governance evidence.
- Any future host-neutral run manifest requires a separately authorized P41
  follow-up and only fields a named consumer needs and Fettle can truthfully
  observe.
- P42 remains the owner of deterministic replay for Fettle-owned events, checks,
  and recorded runner responses. External model or host replay remains a non-goal.
- Shared delegated budgets remain a separate policy/lifecycle gap and are not
  justified by ATIF support.

## Reconsideration Gate

Reopen this decision only when a named supported-host diagnostic question cannot
be answered by existing evidence or a smaller truthful manifest extension. A new
proposal must freeze the exact producer and format version, real sanitized
fixtures, privacy limits, non-authority semantics, and a measurable stop rule
before parser code is considered.
