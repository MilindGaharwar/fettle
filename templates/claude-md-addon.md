## Definition of Done (Services / Agents / Pipelines)

A service is NOT done until ALL are true:

1. `/fettle:preflight` completed — every item addressed
2. `ruff` + `semgrep` pass with zero errors
3. Failure-path tests for every external dependency
4. Resume/recovery tested: kill at each stage, restart, verify
5. Alerting: failure notification reaches operator within 5 min
6. Resource lifecycle: cleanup for logs, DB, temp files, credentials
7. Monitoring: health check or watchdog integration active
8. `/fettle:ops-review` completed with zero open items
