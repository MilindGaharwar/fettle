# Fettle v1.0 — Enterprise Integration (Fettle-Compliant Plan)

**Authored by:** Claude Opus
**Reviewed by:** GPT-5.6 Sol (pending)
**Total effort:** 60-77 hours across 12 work packages

---

## Work Packages

### WP-L: Extend Secret Scanner — Azure/GCP Patterns (2 hrs)

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Add Azure Storage Key pattern: `DefaultEndpointsProtocol=https;AccountKey=...` | CODE | Unit test: pattern matches real Azure connection string format |
| 2 | Add GCP Service Account Key pattern: `"private_key": "-----BEGIN...` in JSON context | CODE | Unit test: matches GCP key file content, does not match generic private key in non-JSON |
| 3 | Add Azure AD Client Secret pattern: assignment of 34-char alphanumeric after `client_secret` | CODE | Unit test: matches `client_secret = "abc..."`, does not match short values or comments |
| 4 | Add Bearer Token in source pattern: `Authorization.*Bearer\s+[A-Za-z0-9._-]{20,}` | CODE | Unit test: matches hardcoded bearer, does not match env-var references |
| 5 | Add `[gates.secrets].extra_patterns` config for org-specific additions | CODE | Unit test: custom pattern from config fires on matching content |
| 6 | Write failing test: Azure connection string in Python source triggers blocking finding | TDD | Test fails before pattern added, passes after |
| 7 | Integration test: full dispatcher invocation with file containing GCP key | INTEGRATION | `echo '{"hook_event_name":"PostToolUse"...}' \| python3 dispatcher.py` returns block with secret finding |
| 8 | Regression test: `vault kv get secret/db` in a shell script does NOT trigger (it's proper retrieval, not leakage) | REGRESSION | Vault retrieval commands produce no findings; only leaked values are flagged; existing secret tests still pass |
| 9 | Live verification: create a temp file with Azure key, run dispatcher, observe block | LIVE | `echo 'conn = "DefaultEndpointsProtocol=https;AccountKey=abc123..."' > /tmp/test.py && echo '{"hook_event_name":"PostToolUse","tool_name":"Write","tool_input":{"file_path":"/tmp/test.py"}...}' \| python3 scripts/dispatcher.py` returns exit code 2 |

---

### WP-M: TDD Green Phase Documentation (1 hr)

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Document known limitation: tdd_gate checks ordering only, not red/green phases | INSPECT | README and docstring updated with explicit limitation statement |
| 2 | Update discipline-testing skill to include red-green-refactor as process guidance | INSPECT | Skill file contains guidance on verifying test failure before implementation |
| 3 | Add config comment in defaults explaining what is and isn't enforced | INSPECT | Config comment present in config.py |

---

### WP-N: Provenance Policy Gate (4 hrs)

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Implement `provenance_gate.py` with 4 modes: none, manifest, marker, commit | CODE | Unit test: each mode produces expected behavior (none=allow, manifest=log, marker=advisory, commit=advisory) |
| 2 | Manifest mode: append to `.fettle/provenance.jsonl` on new file creation | CODE | Unit test: new file write creates JSONL entry with path, timestamp, session_id |
| 3 | Marker mode: check new files for configurable marker text, advisory if missing | CODE | Unit test: new file without marker → advisory; file with marker → allow |
| 4 | File-type awareness: exempt binary, JSON, lockfiles, generated, migrations | CODE | Unit test: new .json file never triggers; new .py file does |
| 5 | Register in dispatcher: PostToolUse(Write), order=62, budget_ms=30 | CODE | Dispatcher selects check for Write events on .py files |
| 6 | Write failing test: new Python file created without provenance marker in marker mode | TDD | Test fails before gate logic, passes after |
| 7 | Integration test: full hook flow creating a new .py file in manifest mode | INTEGRATION | After hook runs, `.fettle/provenance.jsonl` contains entry for the new file |
| 8 | Regression test: editing an existing file never triggers provenance check regardless of mode | REGRESSION | Edit to existing file produces no provenance finding in any mode; only new file creation fires the gate |
| 9 | Live verification: set mode=marker, create new Python file via Write tool | LIVE | `echo '{"hook_event_name":"PostToolUse","tool_name":"Write","tool_input":{"file_path":"/tmp/new_module.py","content":"x=1"}...}' \| python3 scripts/dispatcher.py` returns advisory about missing marker |

---

### WP-O: Artifact Verification Gate (6 hrs)

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Define `VerificationEvidence` dataclass with artifact_id, digest, type, exit_code, timestamp, invalidated flag | CODE | Unit test: dataclass instantiates, serializes to JSON, deserializes correctly |
| 2 | PostToolUse(Bash) evidence capture: detect verification commands, extract artifact identity, record to state | CODE | Unit test: `cosign sign ghcr.io/org/app:v1` → evidence recorded with artifact_id=`ghcr.io/org/app:v1` |
| 3 | PreToolUse(Bash) gate: detect publish commands, check for matching valid evidence | CODE | Unit test: `docker push ghcr.io/org/app:v1` with prior cosign evidence → allow |
| 4 | Evidence invalidation: rebuild/mutation commands clear evidence for affected artifact | CODE | Unit test: `docker build -t ghcr.io/org/app:v1` invalidates prior evidence for that image |
| 5 | Register dual-hook check: PreToolUse(Bash) order=11, PostToolUse(Bash) order=98 | CODE | Dispatcher routes correctly for both events |
| 6 | Write failing test: `docker push` attempted without any verification evidence | TDD | Test fails before gate logic, passes after |
| 7 | Integration test: record cosign evidence, then attempt push, verify allowed | INTEGRATION | Full dispatcher flow: PostToolUse records evidence → PreToolUse allows push |
| 8 | Inversion test: evidence with exit_code=1 (failed verification) does NOT satisfy the gate — produces degraded/unknown status | REGRESSION | Failed verification command (exit_code=1) does not count as valid evidence; subsequent push still triggers advisory; score < 0.5 equivalent for gate confidence |
| 9 | Live verification: attempt `docker push` in a session with no prior verification | LIVE | `echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"docker push ghcr.io/org/app:latest"}...}' \| python3 scripts/dispatcher.py` returns advisory about missing verification |

---

### WP-P: Security Review Command (6-8 hrs)

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Implement `/fettle:security-review` command that orchestrates ruff S-rules + semgrep OWASP | CODE | Command file created with correct procedure steps |
| 2 | Ruff security scan: invoke `ruff check --select S` on target path | CODE | Unit test: known SQL injection pattern produces S608 finding |
| 3 | Semgrep OWASP scan: invoke `semgrep --config p/owasp-top-ten` if semgrep available | CODE | Unit test: XSS pattern produces semgrep finding with CWE reference |
| 4 | Graceful absence: if semgrep unavailable, report Python-only coverage from ruff | CODE | Unit test: semgrep missing → runs ruff only, reports limitation |
| 5 | Output formatter: structured findings with file, line, CWE, severity, recommendation | CODE | Unit test: output contains CWE-89 for SQL injection finding |
| 6 | Write failing test: known-vulnerable Python file with SQL injection | TDD | Test fails before scan logic, passes after |
| 7 | Integration test: run command on a fixture directory with known OWASP violations | INTEGRATION | Command produces findings for SQL injection, XSS, hardcoded creds in fixture files |
| 8 | Regression test: clean code with no vulnerabilities produces zero findings; test-only files with assert statements don't trigger S-rules | REGRESSION | Clean fixture directory produces zero security findings; test files with `assert` not flagged as security issues |
| 9 | Live verification: run security-review on Fettle's own scripts directory | LIVE | `bash scripts/run.sh security_review.py --path scripts/` produces findings report (may be empty if Fettle is clean, but command completes without error) |

---

### WP-Q: Threat Model Command (5-6 hrs)

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Implement `/fettle:threat-model` command with STRIDE template | CODE | Command file created, template has all 6 STRIDE categories |
| 2 | Auto-populate entry points: grep for HTTP route decorators, API endpoints | CODE | Unit test: Flask/FastAPI route decorators extracted as entry points |
| 3 | Auto-populate data stores: grep for DB connections, file writes, cache usage | CODE | Unit test: SQLAlchemy connection string detected as data store |
| 4 | LLM-assisted analysis: prompt configured review provider for threat identification | CODE | Unit test: mock LLM returns structured threats, parsed into template |
| 5 | Output: `docs/threat-model-{name}.md` with STRIDE sections, identified threats, mitigations | CODE | Unit test: output file contains all sections with populated content |
| 6 | Write failing test: command on a service with HTTP routes produces non-empty threat model | TDD | Test fails before auto-population logic, passes after |
| 7 | Integration test: run on a fixture Flask app, verify entry points and data stores detected | INTEGRATION | Fixture app with 3 routes and 1 DB connection → threat model lists all 3 entry points and the data store |
| 8 | Regression test: command on an empty directory produces a valid template with "no entry points detected" rather than crashing | REGRESSION | Empty project produces valid markdown template with explicit "none detected" notes; no crash, no stack trace |
| 9 | Live verification: run threat-model on this project | LIVE | `bash scripts/run.sh threat_model.py --name sol-orchestrator --root /Users/MMILIND/projects/sol-orchestrator` produces docs/threat-model-sol-orchestrator.md |

---

### WP-R: PR Review Orchestration Command (4-5 hrs)

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Implement `/fettle:pr-review` command that aggregates existing check outputs | CODE | Command file orchestrates quality_scan + coverage + complexity + git diff |
| 2 | Quality scan integration: run quality_scan.py, collect findings count and top issues | CODE | Unit test: mock quality_scan output parsed into summary |
| 3 | Coverage integration: read coverage.json if available, report diff coverage % | CODE | Unit test: coverage data parsed into "Coverage: 85% of changed lines" |
| 4 | Breaking change detection: compare exported symbols before/after via git diff | CODE | Unit test: removed function from __init__.py flagged as breaking change |
| 5 | Output as PR-ready markdown checklist | CODE | Unit test: output contains checkboxes, findings summary, coverage, complexity |
| 6 | Write failing test: PR with removed export produces breaking-change finding | TDD | Test fails before detection logic, passes after |
| 7 | Integration test: run on a git repo with staged changes, verify all sections populated | INTEGRATION | Run in a repo with changes: quality, coverage, complexity, and diff sections all present in output |
| 8 | Regression test: run in a repo with no staged changes produces "nothing to review" message, not a crash | REGRESSION | Clean working tree produces informative "no changes to review" message; no error, no empty output |
| 9 | Live verification: run pr-review in the Fettle repo after a code change | LIVE | `bash scripts/run.sh pr_review.py --root .` produces markdown output with quality summary and diff stats |

---

### WP-S: SonarQube Integration Adapter (4-5 hrs)

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Implement `IntegrationAdapter` protocol in `scripts/integration_base.py` | CODE | Unit test: protocol defines is_available() and run() methods |
| 2 | Implement `SonarQubeAdapter` calling `/api/qualitygates/project_status` and `/api/issues/search` | CODE | Unit test: mock HTTP responses parsed into IntegrationReport |
| 3 | Security: HTTPS required, token via env var, no auth on redirects, response size capped | CODE | Unit test: HTTP endpoint rejected; redirect to different host drops auth header; >1MB response truncated |
| 4 | Config validation: endpoint, project_key, token_env all required when enabled | CODE | Unit test: missing project_key → IntegrationResult.MISCONFIGURED |
| 5 | Create `/fettle:sonar-gate` command invoking the adapter | CODE | Command file calls adapter and formats output |
| 6 | Write failing test: SonarQube reports FAIL quality gate status | TDD | Test fails before adapter parsing logic, passes after |
| 7 | Integration test: mock SonarQube server returns quality gate OK with 2 issues → report shows pass with findings | INTEGRATION | Full adapter run against mock HTTP responses → IntegrationReport with status=PASS, 2 findings |
| 8 | Regression test: SonarQube endpoint unreachable → degraded/unknown result with UNAVAILABLE status, on_unavailable=warn produces advisory not crash | REGRESSION | Unreachable endpoint produces UNAVAILABLE with degraded status and clear message; on_unavailable="warn" → advisory; on_unavailable="ignore" → silent; on_unavailable="fail" → block; status is never falsely PASS when connection fails |
| 9 | Live verification: run sonar-gate asserting status output contains defined state and nodes > 0 in report | LIVE | `bash scripts/run.sh sonar_adapter.py --check` outputs JSON with `"status":"not_enabled"` or `"status":"unavailable"` — verify output contains the status field and report has facts > 0 lines describing the configuration state |

---

### WP-T: Black Duck / Polaris SCA Adapter (4-5 hrs)

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Implement `BlackDuckAdapter` invoking CLI and parsing SARIF output | CODE | Unit test: sample SARIF JSON parsed into IntegrationReport with CVE findings |
| 2 | CLI invocation security: resolve path, no shell, timeout, output cap, token via env | CODE | Unit test: CLI path validated; shell=False; subprocess timeout configured |
| 3 | SARIF parsing: schema-validate, extract critical/high findings, license violations | CODE | Unit test: SARIF with 3 results → 3 CheckFindings with correct severity mapping |
| 4 | Config: cli_path, project_name, token_env, scan_timeout_s, on_unavailable | CODE | Unit test: missing CLI → UNAVAILABLE; missing project_name → MISCONFIGURED |
| 5 | Create `/fettle:sca-scan` command | CODE | Command file invokes adapter and formats output |
| 6 | Write failing test: SARIF with critical CVE produces FAIL status | TDD | Test fails before SARIF severity mapping, passes after |
| 7 | Integration test: mock CLI produces SARIF output → adapter returns structured report | INTEGRATION | Subprocess mock returns SARIF JSON → IntegrationReport with status=FAIL, critical CVE listed |
| 8 | Regression test: CLI not installed → graceful UNAVAILABLE; CLI produces empty output → PASS not crash | REGRESSION | Missing polaris binary produces UNAVAILABLE with install suggestion; empty SARIF output produces PASS (no vulnerabilities found); malformed SARIF produces UNAVAILABLE with parse error note |
| 9 | Live verification: run sca-scan and observe graceful behavior | LIVE | `bash scripts/run.sh blackduck_adapter.py --check` reports UNAVAILABLE (polaris not installed) or runs scan if available |

---

### WP-U: Pact Contract Testing Adapter (3-4 hrs)

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Implement `PactAdapter` calling Pact Broker API for verification status | CODE | Unit test: mock broker response with verified + unverified contracts parsed correctly |
| 2 | Security: HTTPS, token via env, response cap, no auth on redirects | CODE | Unit test: HTTP rejected; large response truncated |
| 3 | Report: unverified contracts, failed verifications, awaiting-review interactions | CODE | Unit test: 2 verified + 1 unverified → IntegrationReport with 1 finding |
| 4 | Create `/fettle:contract-test` command | CODE | Command file invokes adapter |
| 5 | Write failing test: unverified contract produces FAIL status | TDD | Test fails before broker response parsing, passes after |
| 6 | Integration test: mock broker with mixed verification status → correct report | INTEGRATION | Mock returns 3 contracts (2 verified, 1 failed) → report shows FAIL with 1 finding identifying the failed contract |
| 7 | Regression test: broker unreachable → UNAVAILABLE with degraded/unknown status; empty response (no contracts) → PASS | REGRESSION | Network timeout produces UNAVAILABLE with degraded status and broker URL in message; zero contracts produces PASS with "no contracts found" summary; status is explicitly unknown when broker is unreachable |
| 8 | Live verification: run contract-test command asserting status output contains result state | LIVE | `bash scripts/run.sh pact_adapter.py --check` outputs JSON with `"status":"not_enabled"` or `"status":"unavailable"` — verify output contains one of the defined states and facts > 0 lines emitted |

---

### WP-V: Architecture Discipline + Boundary Rules (3 hrs)

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Create `discipline-architecture` skill in Disciplines plugin | CODE | Skill file exists with C4 model awareness, bounded context guidance |
| 2 | Implement boundary rules config: `[gates.architecture_boundaries].rules` with from/to/allow | CODE | Unit test: rule `{from="ui/**", to="domain/**", allow=true}` permits matching import |
| 3 | Implement import boundary check: at PostToolUse(Write/Edit) for Python, check imports against rules | CODE | Unit test: `ui/page.py` importing `infrastructure.db` with `allow=false` rule → advisory |
| 4 | Register in dispatcher: PostToolUse, order=65, budget_ms=50 | CODE | Dispatcher selects check for .py file edits when boundaries configured |
| 5 | Write failing test: import violating declared boundary produces advisory | TDD | Test fails before boundary check logic, passes after |
| 6 | Integration test: file with cross-boundary import, boundary rules configured | INTEGRATION | Full dispatcher invocation with import violation → advisory in output |
| 7 | Regression test: file with no imports or imports within allowed boundaries produces no findings; unconfigured boundaries (empty rules) never fires | REGRESSION | File importing within same boundary produces no finding; empty `rules = []` means check never fires; file with no imports produces no finding |
| 8 | Live verification: configure a boundary rule and edit a file that violates it | LIVE | Add `rules = [{from="scripts/**", to="tests/**", allow=false}]` to .fettle.toml, then `echo '{"hook_event_name":"PostToolUse","tool_name":"Edit","tool_input":{"file_path":"scripts/test_helper.py"}...}' \| python3 scripts/dispatcher.py` shows boundary advisory |

---

### WP-W: ADR Discipline Skill (1 hr)

| # | Task | Method | Verify by |
|---|---|---|---|
| 1 | Create `discipline-adr` skill with ADR template, status lifecycle, naming conventions | INSPECT | Skill file exists at ~/.claude/plugins/disciplines/skills/discipline-adr/SKILL.md |
| 2 | Include when-to-write triggers: significant decisions, architecture changes, rejected alternatives | INSPECT | Skill content covers trigger conditions and anti-patterns |
| 3 | Include ADR template: title, status, context, decision, consequences | INSPECT | Template section present with all 5 required sections |

---

## Execution Order

```
Phase 1 (no new architecture):
  WP-L + WP-M

Phase 2 (new hooks):
  WP-N + WP-O

Phase 3a (commands, no external deps):
  WP-P + WP-Q + WP-R

Phase 3b (integration adapters):
  IntegrationAdapter base (part of WP-S) → WP-S → WP-T → WP-U

Phase 4 (discipline skills):
  WP-V + WP-W
```

## Summary

| WP | Tier | What | Hours |
|---|---|---|---|
| L | 1 | Extend secret scanner (Azure/GCP) | 2 |
| M | 1 | TDD green phase documentation | 1 |
| N | 2 | Provenance policy gate | 4 |
| O | 2 | Artifact verification gate | 6 |
| P | 3 | Security review command | 6-8 |
| Q | 3 | Threat model command | 5-6 |
| R | 3 | PR review orchestration | 4-5 |
| S | 3 | SonarQube adapter | 4-5 |
| T | 3 | Black Duck/Polaris SCA adapter | 4-5 |
| U | 3 | Pact contract testing adapter | 3-4 |
| V | 4 | Architecture discipline + boundary rules | 3 |
| W | 4 | ADR discipline skill | 1 |
| **Total** | | | **43-55 (×1.4 = 60-77 with tests/docs)** |
