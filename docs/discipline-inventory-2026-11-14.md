# Discipline Inventory

Date: 2026-11-14
Status: inventory complete. This record satisfies the inventory step of the
[discipline suite review plan](discipline-suite-review-plan.md) (WP-DS-0, tasks
1 and 2). It changes no skill, package, installer or host configuration.

Related: [Experience Discipline vNext plan](experience-discipline-vnext-plan.md),
[sequencing decision of 2026-11-14](engagement/TODO.md#sequencing-decision-2026-11-14).

## What was inspected

- The disciplines source repository at commit `6016f91` (2026-07-23), thirteen
  skills.
- The installed copy used by Claude Code, a checkout of that repository at
  `~/.claude/plugins/disciplines`.
- The installed copy used by OpenCode, at `~/.config/opencode/skill`.
- The Codex skills folder.
- How Fettle refers to the disciplines: `fettle/discipline_link.py` reads short
  reminders from a configurable skills path, default
  `~/.claude/plugins/disciplines/skills`, and falls back to built-in text.

Each installed `SKILL.md` was compared with the source repository by SHA-256.

## Where each skill is

| Skill | Source repository vs. Claude Code copy | OpenCode |
|---|---|---|
| using-disciplines | identical | present |
| writing-disciplines | identical | present |
| discipline-research | identical | present |
| discipline-ux | identical | present |
| discipline-ui | identical | present |
| discipline-planning | identical | present |
| discipline-coding | identical | present |
| discipline-testing | differs: uncommitted local edits | present, the edited version |
| discipline-uat | differs: uncommitted local edits | present, the edited version |
| discipline-shipping | differs: uncommitted local edits | present, the edited version |
| discipline-continuity | identical | missing |
| discipline-architecture | identical | missing |
| discipline-adr | identical | missing |

Codex has no discipline skills. OpenCode also holds one personal presentation
skill that is not in the source repository and is out of scope.

## Findings

1. **Fettle does not package the disciplines.** No skill is in the Fettle
   source tree or wheel, and `fettle init` installs none.
2. **The three quality-critical skills run with uncommitted edits.** Testing,
   UAT and shipping differ from the source repository on the machine that runs
   them, so the published copy is stale for those three and the live copy has
   no version history.
3. **Host coverage is uneven.** The bootstrap that injects the routing index
   is a Claude Code session hook. OpenCode has no such hook and lacks three
   skills, one of which the routing index names. Codex has none.
4. **Two skills are never routed.** The routing index does not mention
   discipline-architecture or discipline-adr.
5. **Two skills break the authoring standard.** discipline-coding and
   discipline-shipping have no frontmatter, which the standard says is what
   makes a skill fire. The effect on each host is not determined.
6. **Skills name Fettle commands that do not exist.** discipline-shipping
   calls a script at a retired plugin path and its checklist names
   `fettle quality`; the current command is `fettle check`.
7. **Skills claim enforcement that does not fire on the installed path.**
   discipline-testing and discipline-shipping say Fettle blocks at Stop when
   edited files were not tested. The 2026-11-13 audit showed that gate is
   inert under the installed hooks; trust remediation TR-1 and TR-3 repair it.
8. **The suite does not meet its own evidence rule.** A behaviour-changing
   rule is meant to ship with a scenario that proves it. Three scenarios
   exist; one has produced a determinate pass. The local edits have none.
9. **Weight.** The suite is about 1,650 lines and its default is the full
   sequence when in doubt. The source repository's own baseline note records
   that this turns a small task into a run of fifteen minutes or more.

## Gaps observed in the November sessions

| Gap | In the disciplines |
|---|---|
| Tests did not exercise the path the user runs | Present: testing rules 9 and 10, shipping rule 6. Not applied. |
| No stop condition on a long effort | Present: research stop rules; shipping rule 10 on bounded fix cost. Not applied; nothing requires a budget up front. |
| A check that cannot fail was cited as proof | Partly: shipping rule 5, for specification changes only. |
| A "not found" claim was wrong | Absent. |
| An observation was reported without its meaning for the question asked | Absent. |
| A general permission was followed over a specific stop rule | Absent. |
| Finished work was left uncommitted in a temporary location | Absent; the nearest skill is not installed on the host concerned. |

## Direction decided

1. After trust remediation TR-3 merges, a narrow update in the disciplines
   repository:
   - one short skill for working under an operator's instructions: show the
     search behind a negative claim and confirm it a second way; state what an
     observation means for the question asked; a specific stop rule outranks a
     general permission; commit before waiting;
   - correct the stale commands and add the two missing frontmatter blocks;
   - extend the "can this check fail" rule from specifications to every gate
     cited as proof;
   - require a budget and a review date for any effort expected to exceed a
     day;
   - make host coverage explicit;
   - route or remove discipline-architecture and discipline-adr;
   - give each change a replay case from the November sessions.
2. After trust remediation TR-4 merges, bring the trimmed set into Fettle as
   an opt-in pack: installed by `fettle init` only on request, never by
   default, with a test that every command and gate a skill names exists.
3. The sealed evaluation, held-out sets and advisory pilot in the review and
   experience-discipline plans are deferred, and run only if the narrow update
   proves insufficient.

No active skill is changed while a controlled work queue is running.
