# Fettle Operational Readiness Review: {SERVICE_NAME}

**Date:** {DATE}
**Reviewer:**
**Status:** DRAFT

---

## 1. Deployment
- [ ] Systemd service file or container config exists
- [ ] Service auto-starts on boot
- [ ] Graceful shutdown handled (SIGTERM)
- [ ] Environment variables documented
- [ ] Secrets managed securely (not hardcoded)
- **Auto-check findings:** {AUTO_FINDINGS}

## 2. Monitoring
- [ ] Health check or heartbeat mechanism
- [ ] Watchdog integration (process auto-restart)
- [ ] Resource usage monitoring (CPU, memory, disk)
- [ ] Log aggregation configured
- **Auto-check findings:** {AUTO_FINDINGS}

## 3. Alerting
- [ ] Failure notifications reach operator within 5 minutes
- [ ] Alert channel configured (Telegram/Slack/email)
- [ ] Alert fatigue mitigated (dedup, severity levels)
- [ ] Escalation path defined
- **Auto-check findings:** {AUTO_FINDINGS}

## 4. Resilience
- [ ] All external calls have timeouts
- [ ] Retry with exponential backoff for transient failures
- [ ] Circuit breaker for cascading failure prevention
- [ ] Graceful degradation on partial outage
- **Auto-check findings:** {AUTO_FINDINGS}

## 5. Data Safety
- [ ] Backups configured and tested
- [ ] Data corruption detection (checksums, validation)
- [ ] Recovery procedure documented and tested
- [ ] Atomic writes for critical files
- **Auto-check findings:** {AUTO_FINDINGS}

## 6. Capacity
- [ ] Resource limits configured (memory, CPU, disk)
- [ ] Growth projections assessed
- [ ] Cleanup/rotation for logs and temp files
- [ ] Database size management
- **Auto-check findings:** {AUTO_FINDINGS}

## 7. Security
- [ ] No secrets in code or config files
- [ ] API keys rotatable without downtime
- [ ] Input validation on external data
- [ ] Dependency vulnerabilities checked
- **Auto-check findings:** {AUTO_FINDINGS}

## 8. Runbooks
- [ ] Startup/shutdown procedure documented
- [ ] Common failure scenarios and fixes documented
- [ ] Rollback procedure defined
- [ ] On-call escalation path defined
- **Auto-check findings:** {AUTO_FINDINGS}

---

## Summary

| Section | Status | Issues |
|---------|--------|--------|
| Deployment | {STATUS} | {COUNT} |
| Monitoring | {STATUS} | {COUNT} |
| Alerting | {STATUS} | {COUNT} |
| Resilience | {STATUS} | {COUNT} |
| Data Safety | {STATUS} | {COUNT} |
| Capacity | {STATUS} | {COUNT} |
| Security | {STATUS} | {COUNT} |
| Runbooks | {STATUS} | {COUNT} |

**Overall:** {PASS_COUNT}/8 sections passing
