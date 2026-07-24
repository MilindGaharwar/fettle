# Fettle v1.0 — Enterprise Integration Plan

**Authored by:** Claude Opus, reviewed by GPT-5.6 Sol
**Status:** Revised after Sol's NEEDS WORK verdict (9 conditions addressed)
**Scope:** Integrate 12 enterprise Copilot skills into Fettle (2 skipped: epic-creation, okf-builder)
**Total effort:** 50-80 hours (revised from 16-24 after Sol's feedback)

---

## Sol Review Conditions (all addressed below)

1. AI policy → configurable provenance/disclosure modes (not universal headers)
2. Artifact gate → bind evidence to exact immutable artifact + exit status
3. Define PASS/FAIL/UNAVAILABLE semantics with configurable fail-open/fail-closed
4. Vendor integrations behind optional provider adapters
5. Narrow OWASP/threat-model claims to supported languages + tool-delegated
6. PR review → orchestration mode over existing checks (not new implementation)
7. Architecture → guidance in Disciplines, boundary rules as separate enforceable gate
8. Credential/endpoint/subprocess/redaction security requirements
9. Re-estimated with tests, docs, fixtures, cross-platform

---

## Architecture: Integration Provider Interface

All external integrations implement a common adapter interface:

```python
class IntegrationResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"     # tool not installed / endpoint unreachable
    MISCONFIGURED = "misconfigured" # config present but invalid
    NOT_ENABLED = "not_enabled"     # not configured

@dataclass
class IntegrationReport:
    status: IntegrationResult
    findings: list[CheckFinding]
    summary: str
    tool_version: str | None = None

class IntegrationAdapter(Protocol):
    name: str
    def is_available(self) -> IntegrationResult: ...
    def run(self, cwd: str, config: dict) -> IntegrationReport: ...
```

**Fail-open/fail-closed policy per integration:**
```toml
[integrations.sonarqube]
on_unavailable = "warn"  # "ignore" | "warn" | "fail"
```

- `ignore`: silently skip
- `warn`: advisory in output
- `fail`: block (CI mode only, never in interactive hooks)

---

## Credential Security Requirements (applies to all integrations)

1. Tokens referenced via `token_env` (env var name) only — NEVER plaintext in .fettle.toml
2. `.fettle.toml` is scanned for accidental embedded credentials at load time
3. Tokens never logged, never on command lines (use env vars or stdin)
4. Subprocess output redacted before surfacing
5. HTTPS required by default; HTTP is explicit noisy opt-in (`allow_insecure = true`)
6. Authorization headers not forwarded on redirects
7. Subprocess output capped (max 1MB SARIF/JSON)
8. External JSON/SARIF parsed as untrusted input (no eval, schema validation)
9. Integration caches in state_dir (gitignored), never in source

---

## Tier 1: Extend Existing Checks (3-4 hrs)

### WP-L: Extend Secret Scanner

**Scope:** Add Azure/GCP credential patterns. Do NOT treat `vault kv get` as a secret — that's proper retrieval.

**New patterns to add to `secret_scan.py`:**
- Azure Storage Key: `DefaultEndpointsProtocol=https;AccountKey=...`
- GCP Service Account Key: `"private_key": "-----BEGIN...`
- Azure AD Client Secret: `[a-zA-Z0-9~.]{34}` after client_secret assignments
- Generic Bearer Token in code: `Authorization.*Bearer\s+[A-Za-z0-9._-]{20,}`

**Config:**
```toml
[gates.secrets]
extra_patterns = []  # Org-specific regex additions
```

**NOT adding:** Vault references, rotation policy (those are process guidance, not leakage detection).

**Effort:** 2 hrs (patterns + tests)

### WP-M: TDD Green Phase Gap

**Scope:** Review `tdd_gate.py` against enterprise tdd-workflow skill for gaps.

**Identified gap:** Current implementation checks test-before-impl ordering but does NOT verify:
- That the test actually FAILED before implementation (red phase)
- That the test PASSED after implementation (green phase)

**Decision:** These require bash output parsing of test results, which is unreliable. Document this as a known limitation. The ordering check (test file edited first) is the enforceable proxy. True red-green-refactor verification is process guidance → Disciplines.

**Effort:** 1 hr (documentation + skill update)

---

## Tier 2: New Hook Checks (8-12 hrs)

### WP-N: Provenance Policy Gate

**Replaces:** "ai-generated-code-policy" (renamed per Sol's feedback)

**Design:** Configurable provenance disclosure — NOT "every file must have a header."

**Supported modes:**
- `"none"` — no provenance enforcement (default)
- `"manifest"` — AI-touched files tracked in `.fettle/provenance.jsonl` (audit log only)
- `"marker"` — new files require a configurable marker comment (advisory)
- `"commit"` — commit messages must include provenance tag (advisory via commit_message check)

**Implementation:** PostToolUse(Write), order=62, budget_ms=30

```python
def run_check(ctx):
    # Only fires on NEW files (not edits to existing)
    # Only fires when mode != "none"
    # Respects exempt_paths and file-type awareness
    # Binary/generated/lockfile/JSON → always exempt
```

**Config:**
```toml
[gates.provenance]
enabled = false
mode = "none"        # none | manifest | marker | commit
marker_text = ""     # Only used in "marker" mode
exempt_paths = ["**/*.json", "**/*.lock", "**/migrations/**", "**/*.generated.*"]
```

**Effort:** 4 hrs (implementation + file-type detection + tests)

### WP-O: Artifact Verification Gate

**Design (revised per Sol):** Bind evidence to EXACT immutable artifact.

**State model:**
```python
@dataclass
class VerificationEvidence:
    artifact_id: str        # e.g., image digest, npm package@version
    digest: str | None      # sha256 of artifact if available
    verification_type: str  # "checksum" | "signature" | "scan"
    command_exit_code: int
    timestamp: float
    session_id: str
    invalidated: bool = False  # Set true on rebuild/mutation
```

**Hook:** PreToolUse(Bash), order=11, budget_ms=40

**Detection:** Regex-match publish commands, extract artifact identity from command args. Check state for matching verification evidence that:
- Has the same artifact_id
- Was recorded AFTER the last build/mutation of that artifact
- Had exit_code == 0
- Is from the current session

**Evidence capture:** PostToolUse(Bash) records verification commands (checksum, cosign, trivy, etc.) with extracted artifact identity and exit code.

**Config:**
```toml
[gates.artifact_integrity]
enabled = false
mode = "advisory"
publish_patterns = [
    'docker push\s+(\S+)',
    'npm publish',
    'pip upload',
    'gh release create',
]
verification_patterns = [
    'cosign sign',
    'trivy image',
    'sha256sum',
    'docker trust sign',
]
```

**Limitations (documented):** Shell aliases, piped commands, and `sh -c` wrappers may bypass regex detection. The gate is a workflow reminder with evidence tracking, not a tamper-proof security boundary.

**Effort:** 6 hrs (state model + evidence capture + correlation + tests)

---

## Tier 3: New Commands (25-40 hrs)

### WP-P: Security Review Command

**Replaces:** "security-review" skill

**What it actually does (scoped per Sol):**
- Runs ruff `S` rules (Python-specific security)
- Runs semgrep with `p/owasp-top-ten` community ruleset if semgrep available
- Checks for common patterns: SQL injection, XSS, CSRF tokens, hardcoded creds, insecure deserialization
- **Supported languages:** Python (full), TypeScript/JavaScript (semgrep only), others (semgrep generic rules)
- Does NOT claim comprehensive OWASP coverage — clearly states it runs available tools

**Output:** Structured findings with CWE references where available.

**Command:** `/fettle:security-review [path]`

**Effort:** 6-8 hrs (tool orchestration + pattern library + output formatting + tests)

### WP-Q: Threat Model Command

**Replaces:** "threat-modeling" skill

**What it actually does (scoped per Sol):**
- **LLM-assisted, not deterministic auto-detection** — uses the configured review provider
- Template-based STRIDE analysis: prompts the LLM to identify threats given the codebase context
- User reviews and edits the output
- Produces `docs/threat-model-{service}.md` with structured sections
- Auto-populates what it can: entry points (HTTP routes), data stores (DB connections), auth mechanisms (from grep)

**Not claiming:** Automatic trust boundary detection or comprehensive threat enumeration. This is a structured guide, not a replacement for a security architect.

**Command:** `/fettle:threat-model [service-name]`

**Effort:** 5-6 hrs (template + LLM prompt + auto-population + output)

### WP-R: PR Review Orchestration

**Replaces:** "pr-review" skill

**Design (per Sol):** Orchestration over existing checks, NOT a new implementation.

**What it does:**
1. Runs `quality_scan.py` → collects findings
2. Runs `coverage_gate.py` logic → gets coverage %
3. Runs `complexity_check.py` → gets complexity summary
4. Collects `git diff --stat` → file list and sizes
5. Checks for breaking changes (API signature changes, removed exports)
6. Formats as PR-ready markdown checklist

**NOT duplicating:** Does not re-implement review logic. Aggregates existing Fettle outputs into PR format.

**Command:** `/fettle:pr-review`

**Effort:** 4-5 hrs (orchestration + formatting + breaking-change detection)

### WP-S: SonarQube Integration Adapter

**Architecture:** Optional adapter behind `IntegrationAdapter` protocol.

**What it does:**
- Calls SonarQube API: `/api/qualitygates/project_status`, `/api/issues/search`
- Reports: quality gate status, new issues by severity, coverage delta
- Normalizes to Fettle's `IntegrationReport` format

**Security:**
- Token via env var only (validated at startup)
- HTTPS required (allow_insecure explicit opt-in)
- Response size capped at 1MB
- No auth headers forwarded on redirects

**Config:**
```toml
[integrations.sonarqube]
enabled = false
endpoint = ""
project_key = ""
token_env = "SONAR_TOKEN"
on_unavailable = "warn"
allow_insecure = false
```

**Command:** `/fettle:sonar-gate`

**Effort:** 4-5 hrs (API client + adapter + error handling + tests)

### WP-T: Black Duck / Polaris SCA Adapter

**Architecture:** Optional adapter, invokes CLI tool.

**What it does:**
- Invokes `polaris` or `blackduck` CLI with configured project
- Parses SARIF output (schema-validated, size-capped)
- Reports: critical/high CVEs, license violations, outdated deps
- Normalizes to `IntegrationReport`

**Security:**
- CLI path resolved and validated (no shell invocation)
- Subprocess timeout (configurable, default 300s)
- Output capped at 1MB before parsing
- Token via env var, passed as env to subprocess (not on command line)

**Config:**
```toml
[integrations.blackduck]
enabled = false
cli_path = "polaris"
project_name = ""
token_env = "POLARIS_TOKEN"
scan_timeout_s = 300
on_unavailable = "warn"
```

**Command:** `/fettle:sca-scan`

**Effort:** 4-5 hrs (CLI invocation + SARIF parsing + adapter + tests)

### WP-U: Pact Contract Testing Adapter

**Architecture:** Optional adapter, calls Pact Broker API.

**What it does:**
- Calls Pact Broker API: `/pacts/provider/{provider}/latest`
- Reports: unverified contracts, failed verifications, pending interactions
- Normalizes to `IntegrationReport`

**Config:**
```toml
[integrations.pact]
enabled = false
broker_url = ""
token_env = "PACT_BROKER_TOKEN"
on_unavailable = "warn"
```

**Command:** `/fettle:contract-test`

**Effort:** 3-4 hrs (API client + adapter + tests)

---

## Tier 4: Discipline Skills (3-4 hrs)

### WP-V: Architecture Discipline + Boundary Rules

**Two parts:**

1. **Discipline skill** (`discipline-architecture`): C4 model awareness, bounded contexts, when to consult the architecture. Process guidance only.

2. **Boundary rules gate** (enforceable): Machine-readable dependency direction rules in `.fettle.toml`:
```toml
[gates.architecture_boundaries]
enabled = false
rules = [
    {from = "ui/**", to = "domain/**", allow = true},
    {from = "domain/**", to = "infrastructure/**", allow = false},
]
```
This is a separate check that can block imports violating declared boundaries — distinct from process guidance.

**Effort:** 3 hrs (skill + boundary config + import check extension)

### WP-W: ADR Discipline

**Discipline skill** (`discipline-adr`): When to write ADRs, template, status lifecycle, naming conventions. Pure process guidance, no enforcement hook.

**Effort:** 1 hr (skill file)

---

## Summary

| WP | Tier | What | Hours | Risk |
|---|---|---|---|---|
| L | 1 | Extend secret scanner (Azure/GCP) | 2 | Low |
| M | 1 | TDD green phase documentation | 1 | Low |
| N | 2 | Provenance policy gate | 4 | Low |
| O | 2 | Artifact verification gate | 6 | Medium |
| P | 3 | Security review command | 6-8 | Medium |
| Q | 3 | Threat model command (LLM-assisted) | 5-6 | Medium |
| R | 3 | PR review orchestration | 4-5 | Low |
| S | 3 | SonarQube adapter | 4-5 | Low |
| T | 3 | Black Duck/Polaris SCA adapter | 4-5 | Low |
| U | 3 | Pact contract testing adapter | 3-4 | Low |
| V | 4 | Architecture discipline + boundary rules | 3 | Low |
| W | 4 | ADR discipline | 1 | Low |
| **Total** | | | **43-55** | |

**With tests, docs, fixtures, cross-platform:** multiply by 1.4x → **60-77 hours**

---

## Execution Order

```
Phase 1 (immediate, no new architecture):
  WP-L (secrets) + WP-M (TDD docs)

Phase 2 (new hooks, builds on v0.8/v0.9 infrastructure):
  WP-N (provenance) + WP-O (artifact)

Phase 3a (commands, no external deps):
  WP-P (security-review) + WP-Q (threat-model) + WP-R (PR review)

Phase 3b (integration adapters — requires IntegrationAdapter interface first):
  IntegrationAdapter protocol → WP-S (SonarQube) → WP-T (Black Duck) → WP-U (Pact)

Phase 4 (discipline skills, independent):
  WP-V (architecture) + WP-W (ADR)
```

---

## What This Does NOT Include

- Epic creation or OKR tooling (out of scope — project management)
- Comprehensive OWASP coverage across all languages (we run available tools, not claim universal detection)
- Tamper-proof artifact verification (we provide evidence tracking, not a cryptographic chain of custody)
- Automatic architecture enforcement from code analysis (we enforce declared boundary rules only)
