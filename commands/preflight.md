---
name: preflight
description: Run pre-deployment FMEA quality checklist for a service or agent
argument-hint: "<service-name>"
user-invocable: true
allowed-tools: Bash, Read, Glob, Grep, Write, Agent
---

Run a pre-deployment FMEA (Failure Mode and Effects Analysis) quality checklist for the target service.

## Procedure

1. **Determine service name.** Use `$ARGUMENTS` if provided. If not provided, derive the name from the current working directory basename.

2. **Create output directory.** Create `.fettle/` in the current working directory if it doesn't already exist:
   ```
   mkdir -p .fettle
   ```

3. **Copy the preflight template.** Read the template from `${CLAUDE_PLUGIN_ROOT}/templates/preflight.md` and write it to `.fettle/preflight-{name}.md`, replacing `{SERVICE_NAME}` with the service name and `{DATE}` with today's date.

4. **Run automated checks on the codebase.** Use Grep and Glob to scan for known anti-patterns and pre-fill the template sections:

   **Time Model (Section 1):**
   - Search for `datetime.now` across all Python files. Any hit is a [FAIL] — record file:line.
   - Search for `datetime.utcnow` as well (deprecated in Python 3.12+). Any hit is a [FAIL].
   - If no hits, mark as [PASS].

   **Error Handling (Section 2):**
   - Search for `except.*:.*pass` or bare `except:` patterns. Any hit is a [FAIL] — record file:line.
   - Search for `AsyncClient` (or `httpx.Client`, `requests.get`, `requests.post`) without `timeout` on the same line or within 5 lines. Flag as [FAIL] if timeout is missing.
   - If no hits, mark as [PASS].

   **LLM Output Parsing (Section 3):**
   - Search for `re.search`, `re.findall`, `re.match` patterns that appear to parse LLM output (look in pipeline/, agents/, or similar directories). Any hit is a [FAIL] — record file:line.
   - If no hits, mark as [PASS].

   **Data Persistence (Section 4):**
   - Search for `.write_text(` or `.write_bytes(` on paths that are NOT in `/tmp` or using tempfile. Flag as [?] for manual review with file:line.
   - Search for absence of atomic write patterns (no `tempfile` + `rename`/`replace` pattern). Flag as [?].

   **External Dependencies (Section 5):**
   - Search for HTTP client instantiations without explicit timeout. Flag as [FAIL] with file:line.
   - Mark remaining items as [?] for manual review.

   **Resource Lifecycle (Section 6):**
   - Search for `open(` without a `with` statement context manager. Flag as [?] with file:line.
   - Mark as [?] for manual review.

   **Observability (Section 7):**
   - Search for `logging.` or `logger.` or `structlog` usage. If found, mark as [PASS]. If absent, mark as [FAIL].
   - Mark remaining items as [?].

   **Testing Coverage (Section 8):**
   - Count test files matching `test_*.py` or `*_test.py` using Glob.
   - Count total test functions (`def test_`) using Grep.
   - Pre-fill `{TEST_COUNT}` and `{TEST_FILES}` in the template.
   - If zero test files, mark as [FAIL]. Otherwise mark as [?] for manual assessment of coverage quality.

5. **Fill the summary table.** For each section, set the status based on findings:
   - **PASS** — all auto-checks passed and no issues found
   - **FAIL** — at least one auto-detected issue
   - **REVIEW** — needs manual inspection (items marked [?])

6. **Write the completed checklist** to `.fettle/preflight-{name}.md`.

7. **Present the results to the user.** Show:
   - A summary of auto-detected issues (with file:line references)
   - The overall pass/fail count
   - Which sections still need manual review ([?] items)

8. **Ask the user** to review and complete any remaining [?] items.

9. **Suggest** running the full automated scan:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/quality_scan.py --root .
   ```
