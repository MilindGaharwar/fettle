# Fettle Pre-Deployment Checklist: {SERVICE_NAME}

**Date:** {DATE}
**Reviewer:** 
**Status:** DRAFT

---

## 1. Time Model
- [ ] No `datetime.now()` in pipeline/source code (use clock injection)
- [ ] All timestamps include timezone info
- [ ] Backfill mode tested with historical dates
- **Auto-check findings:** {AUTO_FINDINGS}

## 2. Error Handling
- [ ] No bare `except: pass` patterns
- [ ] All `except Exception` blocks log or re-raise
- [ ] All external API calls have explicit timeouts
- [ ] All retry logic uses exponential backoff
- [ ] Connection errors included in retry tuple
- **Auto-check findings:** {AUTO_FINDINGS}

## 3. LLM Output Parsing
- [ ] No regex parsing of LLM output
- [ ] Structured output via tool_use or Instructor
- [ ] Output validation with Pydantic models
- [ ] Graceful fallback on malformed output
- **Auto-check findings:** {AUTO_FINDINGS}

## 4. Data Persistence
- [ ] All critical data persisted to DB before processing continues
- [ ] Atomic file writes (tempfile + rename pattern)
- [ ] No data loss on process restart
- [ ] Checkpoint/resume mechanism for long operations
- **Auto-check findings:** {AUTO_FINDINGS}

## 5. External Dependencies
- [ ] All HTTP clients have timeouts configured
- [ ] Rate limiting respected for external APIs
- [ ] Credential refresh mechanism in place
- [ ] Circuit breaker or fallback for unreliable services
- **Auto-check findings:** {AUTO_FINDINGS}

## 6. Resource Lifecycle
- [ ] All opened resources (files, connections, processes) are closed
- [ ] Cleanup logic runs even on failure (try/finally or context managers)
- [ ] Temp files cleaned up after use
- [ ] Log rotation configured
- [ ] Database connections pooled and bounded
- **Auto-check findings:** {AUTO_FINDINGS}

## 7. Observability
- [ ] Structured logging configured
- [ ] Key operations emit timing metrics
- [ ] Error rates trackable
- [ ] Health check endpoint or watchdog integration
- **Auto-check findings:** {AUTO_FINDINGS}

## 8. Testing Coverage
- [ ] Unit tests for core logic
- [ ] Integration tests for external dependencies
- [ ] Failure-path tests (network errors, malformed data, timeouts)
- [ ] Resume/recovery tests (kill and restart)
- [ ] Test count: {TEST_COUNT} tests in {TEST_FILES} files
- **Auto-check findings:** {AUTO_FINDINGS}

---

## Summary

| Section | Status | Issues |
|---------|--------|--------|
| Time Model | {STATUS} | {COUNT} |
| Error Handling | {STATUS} | {COUNT} |
| LLM Output Parsing | {STATUS} | {COUNT} |
| Data Persistence | {STATUS} | {COUNT} |
| External Dependencies | {STATUS} | {COUNT} |
| Resource Lifecycle | {STATUS} | {COUNT} |
| Observability | {STATUS} | {COUNT} |
| Testing Coverage | {STATUS} | {COUNT} |

**Overall:** {PASS_COUNT}/8 sections passing
