---
name: ops-review
description: Run operational readiness review checklist
argument-hint: "<service-name>"
user-invocable: true
allowed-tools: Bash, Read, Glob, Grep, Write, Agent
---

Run a Production Readiness Review (PRR) checklist for the target service.

## Procedure

1. **Determine service name.** Use `$ARGUMENTS` if provided. If not provided, derive the name from the current working directory basename.

2. **Create output directory.** Create `.fettle/` in the current working directory if it doesn't already exist:
   ```
   mkdir -p .fettle
   ```

3. **Copy the ops-review template.** Read the template from `${CLAUDE_PLUGIN_ROOT}/templates/ops-review.md` and write it to `.fettle/ops-review-{name}.md`, replacing `{SERVICE_NAME}` with the service name and `{DATE}` with today's date.

4. **Run automated checks on the codebase.** Use Grep and Glob to scan for operational readiness indicators and pre-fill the template sections:

   **Deployment (Section 1):**
   - Search for systemd service files: Glob for `*.service` files in the project or `/etc/systemd/`.
   - Search for Docker configs: Glob for `Dockerfile`, `docker-compose.yml`, `docker-compose.yaml`, `compose.yml`, `compose.yaml`.
   - Search for `SIGTERM`, `signal.signal`, `signal_handler`, `GracefulExit`, `shutdown` patterns in Python files.
   - Search for hardcoded secrets: patterns like `password=`, `api_key=`, `secret=` followed by string literals (not env var lookups).
   - If service file or Docker config found, mark deployment item as [PASS]. Otherwise [FAIL].
   - If graceful shutdown handling found, mark that item as [PASS]. Otherwise [?].
   - If hardcoded secrets found, mark secrets item as [FAIL] with file:line. Otherwise [PASS].

   **Monitoring (Section 2):**
   - Search for health check patterns: `health`, `heartbeat`, `ping`, `/healthz`, `/health` in route definitions or scripts.
   - Search for watchdog patterns: `watchdog`, `WatchdogSec`, `sd_notify`, `systemd.watchdog`.
   - If health check found, mark as [PASS]. Otherwise [FAIL].
   - If watchdog found, mark as [PASS]. Otherwise [?].

   **Alerting (Section 3):**
   - Search for alerting/notification patterns: `telegram`, `slack`, `send_message`, `smtp`, `email`, `alert`, `notify`, `webhook` in source files.
   - If notification mechanism found, mark as [PASS] with details. Otherwise [FAIL].
   - Mark dedup/severity and escalation items as [?] for manual review.

   **Resilience (Section 4):**
   - Search for timeout patterns: `httpx.Timeout`, `timeout=`, `socket.settimeout`, `aiohttp.*timeout`, `requests.*timeout`.
   - Search for retry patterns: `tenacity`, `@retry`, `backoff`, `retry_on`, `max_retries`, `Retry(`.
   - Search for circuit breaker patterns: `circuit_breaker`, `CircuitBreaker`, `pybreaker`.
   - If timeouts found, mark timeout item as [PASS]. Otherwise [FAIL].
   - If retry with backoff found, mark retry item as [PASS]. Otherwise [FAIL].
   - If circuit breaker found, mark as [PASS]. Otherwise [?].

   **Data Safety (Section 5):**
   - Search for backup patterns: `backup`, `dump`, `pg_dump`, `sqlite3 .backup`, `shutil.copy`.
   - Search for atomic write patterns: `tempfile`, `os.rename`, `os.replace`, `Path.replace`.
   - If backup mechanism found, mark as [PASS]. Otherwise [?].
   - If atomic writes found, mark as [PASS]. Otherwise [?].

   **Capacity (Section 6):**
   - Search for resource limit patterns: `ulimit`, `MemoryLimit`, `LimitNOFILE`, `--memory`, `mem_limit`.
   - Search for log rotation: `RotatingFileHandler`, `TimedRotatingFileHandler`, `logrotate`, `maxBytes`.
   - If log rotation found, mark as [PASS]. Otherwise [FAIL].
   - Mark remaining items as [?].

   **Security (Section 7):**
   - Search for secrets in source: hardcoded API keys, passwords, tokens (string literals assigned to variables named `key`, `secret`, `password`, `token`).
   - Search for `os.getenv` or `environ` for secret loading (good practice).
   - Search for input validation: `pydantic`, `validator`, `validate`, `sanitize`.
   - If secrets loaded from env, mark as [PASS]. If hardcoded, mark as [FAIL] with file:line.
   - If input validation found, mark as [PASS]. Otherwise [?].

   **Runbooks (Section 8):**
   - Search for runbook/operations documentation: Glob for `RUNBOOK*`, `OPERATIONS*`, `ops-*.md`, `runbook*.md`, `TROUBLESHOOTING*`.
   - Search for `README.md` with sections about deployment, operations, or troubleshooting.
   - If runbook documentation found, mark as [PASS]. Otherwise [FAIL].

   **Testing:**
   - Count test files matching `test_*.py` or `*_test.py` using Glob.
   - Count total test functions (`def test_`) using Grep.
   - Report test count in findings.

5. **Fill the summary table.** For each section, set the status:
   - **PASS** — all auto-checks passed
   - **FAIL** — at least one auto-detected issue
   - **REVIEW** — needs manual inspection

6. **Write the completed checklist** to `.fettle/ops-review-{name}.md`.

7. **Present the results to the user.** Show:
   - A summary of auto-detected findings (with file:line references where applicable)
   - The overall pass/fail count
   - Which sections need manual review

8. **Ask the user** to review and complete any remaining [?] items.
