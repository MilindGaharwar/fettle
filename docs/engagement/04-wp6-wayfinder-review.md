# WP6 — Wayfinder Skill Review

Source: mattpocock/skills, `skills/engineering/wayfinder/SKILL.md` (fetched
2026-08-01; repo v1.1.0, ~198k stars). Companion skills referenced: /grilling,
/domain-modeling, /research, /prototype, /to-spec, /to-tickets.

## What Wayfinder is

A planning discipline for work "too big for one agent session". The unit is a
**decision ticket** — a question whose resolution is a decision, not a build
slice. The canonical artifact is a **map**: a single tracker issue
(`wayfinder:map`) whose body is an *index*, never a store:

- **Destination** — one or two lines; every session orients to it first.
- **Notes** — domain, skills to consult, standing preferences.
- **Decisions so far** — one line per closed ticket, gist + link (detail lives
  only in the ticket).
- **Not yet specified** — the "fog of war": in-scope questions not yet sharp
  enough to ticket.
- **Out of scope** — consciously ruled-out work; never graduates back.

Tickets are child issues typed `research` / `prototype` / `grilling` / `task`,
each flagged **HITL** (human answers for themselves — the agent never stands
in) or **AFK** (agent alone). Mechanics that make it work concurrently:

1. **Claim-before-work**: assigning the ticket *is* the claim; concurrent
   sessions skip assigned tickets.
2. **Native blocking edges** render the *frontier* (open + unblocked +
   unclaimed) visually in the tracker.
3. **One ticket per session** (research tickets excepted — they fan out as
   parallel subagents on throwaway branches).
4. **Resolution protocol**: answer as a closing comment, close the issue,
   append a one-line pointer to the map — then graduate any fog the answer
   sharpened into new tickets (create, then wire edges in a second pass).
5. **Plan, don't do**: the pull to "just do the work" is the signal you've
   reached the map's edge and should hand off.
6. **Refer by name**, never bare ids — ids ride inside link text.

## Assessment for Fettle

Strongest planning-coordination model reviewed so far: it solves multi-session
context loss with *tracker-native* state instead of bespoke memory, and its
invariants are mechanically checkable — which is exactly Fettle's trade.

### Adopt (feeds WP5 coordination substrate + Pillar 5)

- **Index-vs-store separation** for Fettle's todo/worknotes primitives: the
  TODO is an index of one-line gists + links; detail lives in exactly one
  place. Prevents the divergence Fettle's two competing worklog models show.
- **Claim semantics** for concurrent workstreams (WP7 worktrees): a worktree
  session claims a work item before edits; unclaimed = takeable. Fettle can
  *gate* this: flag edits in a worktree with no claimed item.
- **HITL/AFK typing** maps 1:1 onto Fettle's graceful-interruption
  non-negotiable (WP3): a HITL step that an agent auto-answers is a
  detectable, gateable violation ("grilling agent that answers its own
  questions has broken this").
- **Fog-of-war discipline** for plan_validator: "ticket when the question is
  sharp, fog when it isn't" is a lintable rule for plan docs — flag plans that
  pre-slice unknowns into fake-precise tasks.

### Do not adopt

- Tracker dependency as a *requirement* — Fettle must work offline/local-first;
  the local-markdown fallback pattern (which Wayfinder itself specifies) is
  the primary mode for Fettle, tracker sync optional.
- One-decision-per-session cadence as enforced policy — right for humans
  driving maps, too rigid for Fettle's supervised agent teams (Pillar 4);
  keep it advisory.

### Gate ideas extracted (candidates, not commitments)

| Invariant | Check |
|---|---|
| Claim before work | edit in workstream with no claimed item → advisory |
| Decision lives in one place | same decision text duplicated across docs → advisory |
| Resolution recorded on close | item closed with no resolution note → advisory |
| Out-of-scope never resumed | commit touches item listed out-of-scope → block (enforce mode) |
