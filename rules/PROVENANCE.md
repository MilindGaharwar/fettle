# Rule Provenance

Every distributable rule asset under `rules/` must have exactly one row in
this table. Paths are relative to `rules/`. The CI provenance check rejects
missing, duplicate, stale, or placeholder entries.

| File | Origin | Upstream | Licence |
| --- | --- | --- | --- |
| `.ruff.toml` | Written from scratch for Fettle; introduced in `f778435` | None | Apache-2.0 |
| `go-antipatterns.yml` | Written from scratch for Fettle; introduced in `2c4d470` with Fettle-specific metadata and tests | None | Apache-2.0 |
| `llm-antipatterns.yml` | Written from scratch for Fettle; introduced in `f778435` and extended for Fettle incidents and work packages | None | Apache-2.0 |
| `security.yml` | Written from scratch for Fettle as the immutable canonical security-review policy | None | Apache-2.0 |
| `ts-antipatterns.yml` | Written from scratch for Fettle; introduced in `717c13b` with Fettle-specific metadata and fixtures | None | Apache-2.0 |

## Audit Notes

- Audit date: 2026-08-27.
- Evidence reviewed: each file's introduction and subsequent Git history;
  rule IDs, patterns, messages, metadata, and fixtures; the
  full `semgrep/semgrep-rules` Git history through commit
  `40b8c63f75dc7c22c8a77482d73bfb864b146f7e`; and public exact-string/code
  searches where service limits permitted.
- No current rule ID or distinctive rule text matched any revision of
  `semgrep/semgrep-rules`. No Git history or source match identified a
  third-party registry repository.
- Generic security concepts such as SQL injection, swallowed errors, and
  network timeouts are ideas and do not establish copying of rule expression.
- `semgrep/semgrep-rules` is governed by the Semgrep Rules License v1.0. Any
  future rule copied or adapted from it must be flagged as non-redistributable
  and excluded from Fettle distributions.
- AGPL-3.0 and other copyleft-derived rules must be flagged separately and
  reviewed for compatibility before they enter the repository or a release.
- `.gitkeep` files and this manifest are not executable rule assets and are
  outside the table's coverage set.

## Adding Rules

Add the rule file and its provenance row in the same change. Use the actual
upstream repository, file URL, and licence for copied or adapted work; use
`None` only for work written from scratch for Fettle. Do not use placeholders
such as `unknown`, `TBD`, or `N/A`.
