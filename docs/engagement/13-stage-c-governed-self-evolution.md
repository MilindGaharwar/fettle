# Stage C design — governed self-evolution (WP-163)

Status: ACTIVE · Author: engagement session 2026-08-02 · Target release: v1.5.0
Plan source: docs/fettle-v14-multiagent-plan.md §4 (WP-163, hermes-agent translations)

## 1. Problem

Fettle accumulates evidence it never acts on. The trace records every block,
advisory, and CI failure; `fp_stamp` records overrides; `ratchet` computes
per-rule precision. But closing the loop — noticing a *repeated* failure that
no rule covers, drafting a rule for it, and promoting rules that earn trust —
is entirely manual today. Hermes-agent demonstrates the closed loop
(autonomous skill creation, self-improvement, curated memory, scheduled
maintenance); Fettle's constraint is that the harness that guards quality
must not self-modify unattended.

**Principle 5 restated as the design invariant: sensing and drafting are
autonomous; policy mutation requires a human command.**

## 2. What exists (reuse, don't duplicate)

| Capability | Where | Stage C role |
|---|---|---|
| Decision trace (blocks, advisories, findings, lineage) | `trace.py`, `~/.local/state/fettle/trace.jsonl` | raw signal for C1/C4 |
| CI failure classification | `ci_ingest.py` (`FailureClass`, `classify_failure`, `store_failure`, `load_history`) — populated by `ci_gate._ingest_failure` | recurring-failure-class signal for C1 |
| Incident → rule pipeline (LLM draft + semgrep verify + fixtures) | `learn.py` (`rules/learned/`, human approval before save) | C2 drafting engine |
| FP override signal | `fp_stamp.py` (`false-positives.jsonl`) | precision input |
| Per-rule TP/FP evidence + advisory↔enforce mode ratchet | `ratchet.py` (`.fettle/ratchet.json`, `fettle ratchet status/promote/demote`) | C3 evidence engine — **mode** lifecycle already done |
| Ungoverned-session detection | `lineage_report.py` (v1.4) | C4 lineage anomalies |
| Friction metrics | `report.py` (`compute_effectiveness`) | C4 digest input |

Gap analysis: (1) nothing detects *repeated* failure signatures; (2) `learn`
requires a human to write the incident text and saves straight to
`rules/learned/` (which `.fettle.toml [rules].extra_dirs` can load into
gates); (3) ratchet handles *mode* promotion but there is no *file* lifecycle
for machine-drafted rules; (4) no digest ties it together.

## 3. Design

### Rule lifecycle (the governance spine)

```
signature detected ──draft──▶ rules/proposed/   (autonomous, C1+C2)
rules/proposed/  ──fettle rules promote <id>──▶ rules/learned/   (HUMAN, C3)
rules/learned/   ──[rules].extra_dirs opt-in──▶ loaded by gates  (existing)
advisory rule    ──fettle ratchet promote──▶ enforce             (existing, evidence-gated)
```

Verified invariant: nothing in the codebase loads `rules/proposed/` —
`_resources.rules_dir()` serves bundled packs, project rules come only from
`.fettle.toml [rules].extra_dirs`. C2 adds a test pinning this permanently.

### C1 — failure-signature detection (`fettle/evolution.py`)

`detect_signatures(root, days=30) -> list[Signature]` — read-only, stdlib.

Two detectors:

1. **Rule-less trace clusters**: group trace entries with status in
   {blocked, block, violation} by `(hook, finding.code)`. A cluster is a
   signature when `count >= 3` distinct entries in the window AND the code is
   not already covered by a rule file in `rules/proposed/` or `rules/learned/`
   (coverage = rule id appears as a filename stem or `id:` in the YAML —
   substring-free exact match). Codes from bundled packs fire *because* a rule
   exists; they are excluded by the same check against `_resources.rules_dir()`.
2. **Recurring CI failure classes**: `ci_ingest.load_history()`; a
   `FailureClass` recurring `>= 3` times in the window is a signature (these
   describe process gaps — surfaced in insights, draftable only when the log
   tail gives a concrete pattern; otherwise marked `draftable=False`).

`Signature` dataclass: `kind` (trace-cluster | ci-class), `key`, `count`,
`first_ts`, `last_ts`, `sample_evidence` (≤3 redacted snippets — reuse
ci_ingest `_SECRET_RE` scrubbing), `draftable`.

Thresholds are constants (`MIN_OCCURRENCES = 3`), not config — no new config
surface until real-world use demands tuning (lean).

### C2 — proposal drafting (`rules/proposed/`, extend `learn.py`)

- `PROPOSED_RULES_DIR = "rules/proposed"`; proposals carry
  `metadata.origin: fettle-evolution`, `metadata.signature`, evidence counts,
  and `metadata.status: proposed`.
- `fettle learn --from-trace [--days N] [--auto-save]`: runs C1, and for each
  draftable signature builds an incident brief from the evidence, then:
  - **LLM available** (existing Ollama path): full learn pipeline — rule +
    fixtures + semgrep verification — but saved to `rules/proposed/`.
  - **No LLM** (the common case; also CI cron): write an *evidence brief*
    proposal — a YAML stub with the signature, counts, samples, and an empty
    `pattern:` for a human or a later LLM pass to fill. Honest, deterministic,
    testable.
- `fettle learn --incident` (human-initiated) keeps writing to
  `rules/learned/` — the human IS the approval. Machine-initiated drafts are
  the ones that need the proposal quarantine.
- Pinning test: grep-level assertion that no non-test module references
  `rules/proposed` except evolution/learn/rules_cmd.

### C3 — rule file lifecycle (`fettle/rules_cmd.py`)

`fettle rules list` — table of proposed + learned rules with ratchet evidence
(fires/TP/FP via `ratchet.aggregate_evidence`) joined by rule id.
`fettle rules promote <id>` — move `rules/proposed/<id>.yml` →
`rules/learned/<id>.yml` (+ fixtures), set `metadata.status: learned`. Refuses
if the proposal has an empty `pattern` (evidence briefs must be completed
first). Explicit human command; no evidence threshold for *file* promotion —
the human judgment is the gate (mode promotion stays evidence-gated in
ratchet).
`fettle rules promote --candidates` — read-only: proposals whose codes kept
firing since drafting, learned advisory rules meeting ratchet's promote bar
(≥5 fires, FP ≤20%), and noisy learned rules (FP >50%, ≥3 fires) as demote
candidates. Computed stats, human decisions — verbatim from the plan table.
`fettle rules demote <id> --reason` — move learned → proposed (out of any
`extra_dirs` load path), record reason in metadata.

Boundary with ratchet: ratchet = *mode* of a loaded rule; rules_cmd = *which
files exist where*. `rules list` cross-references both so the operator sees
one picture.

### C4 — `fettle insights` (read-only digest)

`fettle insights [--days 7] [--json]` — four sections, all recomputed from
existing sources, no state written:
1. **Friction** — top gates by blocks+advisories (`report.compute_effectiveness`).
2. **Emerging failures** — C1 signatures.
3. **Rule pipeline** — C3 candidates (promote/demote/pending proposals).
4. **Lineage anomalies** — ungoverned sessions (`lineage_report.compute_lineage`).

Cron recipes documented in CONFIG.md (recipes, not a daemon): weekly
`fettle insights` + `fettle learn --from-trace --auto-save` + nightly
`fettle doctor --verify-hashes`.

## 4. Slices

| Slice | Deliverable | Tests |
|---|---|---|
| C0 | this doc | — |
| C1 | `evolution.py` detect_signatures | synthetic trace + ci history fixtures; covered-code exclusion; redaction |
| C2 | `rules/proposed/` + `learn --from-trace` | evidence-brief determinism; LLM path monkeypatched; gate-isolation pin |
| C3 | `rules_cmd.py` + CLI `rules` | promote/demote file moves; empty-pattern refusal; candidates join |
| C4 | `insights.py` + CLI; cron recipes in docs | digest composition with all sources empty/populated |
| C5 | CHANGELOG/README/CONFIG.md, version 1.5.0, full suite, push | release-gate alignment |

## 5. Decisions

- **D-C1** Thresholds are constants, not config — no tuning surface before
  evidence of need.
- **D-C2** No-LLM path ships evidence briefs rather than failing: the sensing
  loop must not depend on an optional local model.
- **D-C3** Human-initiated `learn --incident` still writes `rules/learned/`
  directly; only machine-initiated drafts are quarantined in `rules/proposed/`.
- **D-C4** File promotion needs no evidence threshold (human judgment is the
  gate); mode promotion keeps ratchet's evidence bar. Demotion of a
  *machine-drafted* rule returns it to proposed; bundled packs are out of
  scope for demote (they version with the product).
- **D-C5** `insights` writes nothing — a digest with side effects would be a
  daemon in disguise.
- **D-C6** CI failure-class signatures are surfaced but only draftable with a
  concrete log pattern — process gaps usually need process fixes, not semgrep.
