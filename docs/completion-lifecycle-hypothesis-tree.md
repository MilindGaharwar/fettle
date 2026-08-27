# Completion Lifecycle Hypothesis Tree

## Objective

Prevent work-item status, plans, and completion evidence from becoming separate
claims while preserving existing repositories.

## H1: Versioned Work-Item Linkage (Selected)

Hypothesis: requiring every v2 `done` item to have a same-ID manifest bound to
its current declared scope will prevent stale or missing evidence because all
completion boundaries evaluate the same identity.

Falsification: Stop, release, or explicit validation passes when a v2 item lacks
a manifest, has malformed metadata, or its scoped files changed after evidence.

Evidence: changed-only scanning and self-declared revisions were falsified by
GLM review; full v2 scanning plus current scope identity is required.

## H2: Embed Evidence In Work Items (Rejected)

Hypothesis: one Markdown file would eliminate synchronization errors.

Falsification: machine validation requires complex nested evidence, making the
planning artifact noisy and weakening strict schema validation.

## H3: Derive Status Only From Manifests (Rejected)

Hypothesis: removing status from work items would create one authority.

Falsification: discovery and coordination would require manifest joins for every
item and force a breaking migration of legacy repositories.

## Constraints

- Legacy tracked v1 work items remain readable.
- Newly added v1 work items are invalid; new work must use v2.
- Completion metadata cannot participate in scope identity, avoiding circular
  digests.
- Missing, malformed, empty, or changed scope is non-pass.
