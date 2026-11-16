# UI Spec: Fettle Review

> Publication review — 2026-11-16, based on `461e73b`.
> This is proposed work or retained research provenance, not implementation approval.
> Dated observations and validation reports below describe their original candidates.
> The current [audit record](completion/audit-hardening.json) records bounded acceptance;
> mutation qualification remains `CLOSED_NON_PASS`. Rebind execution dependencies
> and evidence before any separately authorized implementation.
> See the [review record](reviews/2026-11-16/review.md).

Status: PROPOSED visual contract; no frontend implementation is authorized

UX contract: [fettle-review.ux-spec.md](fettle-review.ux-spec.md)

## Design Direction

- Reference: GitHub Checks for direct status and source linkage, combined with
  Stripe's progressive disclosure for evidence detail.
- Character: calm, forensic, and legible. It should feel like a review document,
  not an analytics dashboard or an AI chat transcript.
- Density: one-screen decision summary followed by compact evidence tables and
  expandable claim paths.
- Initial implementation preference: semantic, self-contained local HTML with no
  remote assets and no mandatory JavaScript. Reassess components only if the
  approved prototype proves that native HTML cannot meet the interaction contract.

## Visual Hierarchy

1. Candidate identity and freshness.
2. Existing Fettle disposition in a full-width decision band.
3. Three ordered blocks: reasons, unknowns, next actions.
4. Dimension matrix.
5. Claim-to-evidence paths and logic diagrams.
6. Technical provenance.

The page must not lead with charts, activity counts, or an aggregate score.

## Components

- Decision band: status text, candidate, policy, timestamp, and scope.
- Reason list: severity, plain-English statement, affected behavior, and evidence
  disclosure.
- Unknown list: missing fact, consequence, and exact recovery action.
- Dimension matrix: one row per required dimension with text status and reason.
- Claim path: ordered `intent -> scenario -> code -> test -> observation -> decision`
  nodes. Missing nodes remain visible.
- Logic map: small state/flow diagram plus equivalent ordered text and exact source
  references; always labeled `ADVISORY INTERPRETATION` when generated.
- Provenance drawer: producer, source, policy, scope, occurrence, completeness,
  freshness, independence, artifact digest, and rerun command.
- Print view: preserves status text, URLs/paths, and evidence IDs without relying
  on background color.

## Tokens

Final token values require contrast verification before implementation. The
initial direction is light-first because this is a review document:

| Token | Candidate value | Purpose |
|---|---|---|
| `--review-bg` | `#F7F8FA` | Page background |
| `--review-surface` | `#FFFFFF` | Cards and report body |
| `--review-text` | `#17202A` | Primary text |
| `--review-muted` | `#52606D` | Secondary text |
| `--review-border` | `#CBD2D9` | Grouping and table rules |
| `--review-action` | `#075985` | Links and focus-safe action color |
| `--review-verified` | `#166534` | Supplementary verified accent |
| `--review-failed` | `#B42318` | Supplementary failure accent |
| `--review-unknown` | `#8A4B08` | Supplementary unknown accent |
| `--review-advisory` | `#5B21B6` | Supplementary interpretation accent |

- Typography: system UI sans-serif; evidence IDs, digests, paths, and numeric
  values use the system monospace stack and tabular numerals.
- Scale: 28px page title, 20px section title, 16px subsection, 14-16px body, and
  no essential text below 12px.
- Spacing: 4px base grid; 16-24px section spacing; 8-12px internal spacing.
- Radius: one restrained 6px radius token; no decorative shadows required.

## Responsive Layout

- Desktop: summary and next actions use a two-column region; dimensions and claim
  paths use the full content width, capped for readable line length.
- Mobile: every region becomes one column; evidence tables become labeled records,
  never horizontally clipped grids.
- Print: single column, all disclosures expanded, links and evidence IDs visible.

## Interaction States

- Default: complete label, summary, and disclosure affordance are visible.
- Hover: underline links and lightly change disclosure background; never reveal
  information only on hover.
- Active/selected: use border, text, and icon in addition to color.
- Focus: at least a 2px high-contrast outline with offset.
- Disabled: retain readable text and explain why an action is unavailable.
- Loading: preserve final layout dimensions; use text progress rather than shimmer.
- Stale: persistent banner and watermark-like text label without obscuring content.
- Error: plain-language panel containing cause, consequence, and recovery action.

## Diagram Rules

- Prefer linear flows and small state machines over force-directed graphs.
- Limit a default diagram to seven nodes; group additional paths behind one named
  disclosure.
- Use verbs on edges and user-language labels on nodes.
- Mark missing evidence with a dashed outline plus `UNKNOWN` text.
- Never infer causality from file imports or agent chronology.
- Provide an ordered text equivalent immediately after each diagram.

## Accessibility And Validation

- WCAG AA contrast for every token pairing; statuses remain understandable in
  grayscale and high-contrast mode.
- Native headings, landmarks, lists, tables, links, buttons, and `details` where
  they fit; no clickable generic containers.
- Full keyboard traversal with no focus trap.
- Axe: zero serious or critical findings on every populated and error fixture.
- Test at 320px, 768px, and 1440px widths and at 200% zoom.
- Validate a printed/PDF rendering because users may share a review with an
  engineer; the generated HTML remains the source, not the PDF.
