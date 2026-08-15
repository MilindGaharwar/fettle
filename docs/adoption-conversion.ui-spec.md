# UI Spec: Adoption Proof And Public Surfaces

Status: v1.11.0 visual contract

UX contract: [adoption-conversion.ux-spec.md](adoption-conversion.ux-spec.md)

## Scope

This work changes static GitHub, PyPI, terminal-recording, release, and issue
surfaces. It does not introduce an application frontend, component library,
custom navigation, or hosted analytics dashboard.

## Reference And Visual Language

- Reference: Astral's `uv` repository documentation for concise command-first
  developer onboarding, adapted to Fettle's existing foundry wordmark and sober
  assurance language.
- Preserve the existing README typography and centered wordmark. Do not add a
  marketing microsite, decorative gradients, testimonial cards, or dashboard
  imagery.
- The proof should feel like a real terminal session, not a product trailer:
  one command at a time, readable pace, no simulated typing mistakes, and no
  claims that are absent from the transcript.

## Components

| Surface | Component | Contract |
|---|---|---|
| GitHub About | Description, homepage, topics | Short category statement, canonical PyPI link, no unsupported terms |
| README | Existing heading, proof media, transcript, command block | Native Markdown/HTML only; media has dimensions, alt text, and fallback link |
| Proof | Terminal capture plus static poster | 16:9 or compact terminal ratio; readable at 720 px width; under 5 MB target |
| Release | Native GitHub release Markdown | Outcome summary, adoption impact, boundaries, evidence, changelog link |
| Issues | GitHub issue forms/templates and labels | Structured prompts; no custom CSS or external form |
| Discussions | Native GitHub categories, only after demand gate | `Q&A` and `Show and tell` initially; no empty category sprawl |

No shadcn/ui or Tremor components apply because no web application UI is being
built. GitHub-native controls are the accessible component system.

## Tokens

Use only colors already present in the Fettle wordmarks and terminal's standard
theme. Semantic status is always duplicated in text.

| Token | Use |
|---|---|
| `fettle-wordmark-light` | Existing light-background wordmark asset |
| `fettle-wordmark-dark` | Existing dark-background wordmark asset |
| `surface-terminal` | Near-black terminal background from the chosen recorder theme |
| `text-terminal` | Off-white terminal foreground with at least 4.5:1 contrast |
| `status-pass` | Existing terminal success accent plus the word `pass` or `verified` |
| `status-nonpass` | Existing warning/error accent plus explicit status and recovery text |

Do not recolor actual command output to manufacture hierarchy. If annotations
are necessary, put them in the transcript rather than over the recording.

## Typography And Density

- README and GitHub surfaces retain GitHub's native type and spacing.
- Terminal capture uses a common monospace face at a minimum apparent size of
  16 px when displayed at 720 px width.
- Keep command lines short enough to avoid horizontal panning on mobile.
- Show at most five conceptual beats: introduce defect, detect, explain,
  repair, verify.

## Visual States

### Proof Media

- Default: static poster clearly names the demonstrated loop.
- Hover/focus: GitHub-native linked-image focus and cursor behavior.
- Active: opens the full recording or source transcript.
- Unavailable: alt text, transcript, and command block preserve all meaning.

### Command Links And CTAs

- Default: descriptive native Markdown links.
- Hover/focus: GitHub-native state; no custom focus suppression.
- Active/visited: browser-native state is acceptable.
- Disabled: do not render unavailable actions as links; state `planned` in text.

### Issue Labels

- Default: text label identifies category and effort.
- Selected/filtering: GitHub-native issue filter state.
- Closed: issue status and closing comment explain the outcome.
- Blocked: explicit `blocked` label and dependency link, never color alone.

## Recording Storyboard

| Beat | Terminal action | Visible outcome | Maximum time |
|---|---|---|---:|
| Context | Show disposable demo tree and Fettle version | Version-bound, small example | 5 s |
| Detect | Run the documented changed-scope check | One known non-pass finding | 12 s |
| Explain | Run the documented explanation path | Reason and next action | 10 s |
| Repair | Apply the fixture's tiny documented repair | Changed line remains legible | 10 s |
| Verify | Run check/verify contract selected during implementation | Textual clean/verified state | 15 s |

Target runtime is 35-55 seconds. Provide a static poster and transcript. Avoid
autoplay audio and loops longer than one minute.

## Responsive And Accessibility Checks

- Verify README at approximately 375 px and 1440 px viewport widths through a
  browser or GitHub preview.
- Media must not force horizontal page scrolling on mobile.
- Alt text explains the result, not the pixels: for example, `Terminal proof:
  Fettle detects, explains, and verifies repair of a known defect`.
- Transcript headings follow the README hierarchy and each command is plain
  text in a fenced code block.
- Recording contains no flashing and no information available only through
  timing, color, or audio.
- Poster and terminal text meet WCAG AA contrast.

## Visual Acceptance

- The README remains recognizably Fettle and gains only one high-signal visual.
- The visual proof appears before detailed capability exposition without
  displacing the two-minute text path.
- Mobile and dark/light GitHub rendering remain legible.
- The recording matches a clean replay of the checked-in demo contract.
- No generated badge, topic, screenshot, or label implies unsupported runtime
  behavior.
