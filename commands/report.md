# /fettle:report

Show effectiveness metrics from Fettle's trace data.

## Usage

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh report.py [--days 30]
```

Reports:
- Pass/violation/error rates
- Top violations by rule code
- Most affected files
- Tool error incidents
- Recalibrate candidates (rules always suppressed)

## Purpose

Answers: "Is Fettle helping or just annoying?" Data-driven decisions about which rules to keep, tune, or retire.
