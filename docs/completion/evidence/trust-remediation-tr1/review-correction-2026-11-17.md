# TR-1 review correction — 2026-11-17

This correction is additive. It does not rewrite or invalidate the retained
TR-1 evidence. Independent review of PR #80 at head `070c35e` found five gaps,
fixed and regression-tested on the TR-2 pull-request branch:

| Finding | Correction |
|---|---|
| T-1 | The source snapshot did not detect committed code, amended code commits, or code-changing branch switches. Session-start `HEAD` comparison now covers those cases while documentation-only commits remain allowed. |
| T-2 | Multi-target fan-out stopped at the first advisory. Every target now runs, the most severe result wins in either order, and one per-check advisory summary reports the affected-target count. |
| T-3 | Required-check registration used ineffective keys for `boundary_rules` and `runtime_output_guard`, and claimed an enforcing mode for `provenance_gate` that the check does not implement. The boundary key now matches `gates.architecture_boundaries`; the two ineffective entries were removed; `worklog` and `post_bash_doc_check` retained their correct keys. |
| T-4 | Patch target extraction ignored `*** Move to:` destinations. Move destinations now reach config protection. |
| T-5 | Malformed-input blocking recognized only truncated Claude `PreToolUse`. It now derives native pre-tool names from the translators and covers non-object input plus Gemini `BeforeTool`; malformed non-pre-tool input remains an allowed, traced error. |

The original E11 evidence covered configured required checks already wired to
their real enforcing key and direct integrity-check blocks. It did **not** cover
an exception inside each of `boundary_rules`, `runtime_output_guard`,
`provenance_gate`, `worklog`, and `post_bash_doc_check` under the configuration
that each check actually reads. T-3 adds enforce/advisory exception routing for
every check with a real enforcing mode and explicitly removes the two entries
for checks without one.

The original E6 evidence covered truncated Claude `PreToolUse`, malformed
journal lines, and deleted or emptied journal files after an edit. It did
**not** cover a valid JSON non-object naming a pre-tool event or a truncated
Gemini `BeforeTool` payload. T-5 adds those cases in both installed launch
modes and preserves traced allow for malformed input naming no pre-tool event.
