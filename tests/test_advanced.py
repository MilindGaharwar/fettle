"""Tests for Phase 7 advanced features — WP-98,99,100,101,102."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from schema_drift import check_schema_drift
from migration_safety import check_migration_safety
from ai_summaries import format_ai_summary
from health_dashboard import HealthMetrics
from finding import CheckFinding, FindingSeverity


# --- WP-98: Schema drift ---

def test_drift_detected_when_schema_changes(tmp_path):
    schema = tmp_path / "schema.prisma"
    schema.write_text("model User { id Int }")
    generated = tmp_path / "generated" / "client.ts"
    generated.parent.mkdir()
    generated.write_text("// old generated code")
    import time
    time.sleep(0.05)
    schema.write_text("model User { id Int\n name String }")
    config = [{"source": "schema.prisma", "output": "generated/client.ts", "command": "prisma generate"}]
    findings = check_schema_drift(str(tmp_path), config)
    assert len(findings) >= 1
    assert "drift" in findings[0].message.lower() or "stale" in findings[0].message.lower()


def test_no_drift_when_output_matches(tmp_path):
    schema = tmp_path / "schema.prisma"
    schema.write_text("model User { id Int }")
    generated = tmp_path / "generated" / "client.ts"
    generated.parent.mkdir()
    import time
    time.sleep(0.05)
    generated.write_text("// freshly generated")
    config = [{"source": "schema.prisma", "output": "generated/client.ts", "command": "prisma generate"}]
    findings = check_schema_drift(str(tmp_path), config)
    assert findings == []


# --- WP-99: Migration safety ---

def test_detects_drop_column(tmp_path):
    migration = tmp_path / "migration.sql"
    migration.write_text("ALTER TABLE users DROP COLUMN email;")
    findings = check_migration_safety([str(migration)])
    assert len(findings) >= 1
    assert any("drop" in f.message.lower() for f in findings)


def test_detects_not_null_without_default(tmp_path):
    migration = tmp_path / "migration.sql"
    migration.write_text("ALTER TABLE users ADD COLUMN age INTEGER NOT NULL;")
    findings = check_migration_safety([str(migration)])
    assert len(findings) >= 1


def test_safe_migration_passes(tmp_path):
    migration = tmp_path / "migration.sql"
    migration.write_text("ALTER TABLE users ADD COLUMN bio TEXT;")
    findings = check_migration_safety([str(migration)])
    assert findings == []


# --- WP-100: AI summaries ---

def test_suggested_fix_included():
    findings = [CheckFinding(
        checker="ruff", severity=FindingSeverity.ERROR,
        file="app.py", line=10, message="unused import os",
        suggested_fix="Remove `import os`",
    )]
    summary = format_ai_summary(findings, duration_ms=120)
    assert "Remove" in summary


def test_session_summary_format():
    findings = [
        CheckFinding(checker="ruff", severity=FindingSeverity.ERROR, file="a.py", line=1, message="err", blocking=True),
        CheckFinding(checker="ruff", severity=FindingSeverity.WARNING, file="b.py", line=2, message="warn"),
        CheckFinding(checker="ruff", severity=FindingSeverity.INFO, file="c.py", line=3, message="info"),
    ]
    summary = format_ai_summary(findings, duration_ms=150)
    assert "1 blocking" in summary
    assert "1 warning" in summary or "1 advisory" in summary


def test_output_concise():
    findings = [CheckFinding(
        checker="ruff", severity=FindingSeverity.ERROR,
        file="app.py", line=10, message="x" * 200,
    )]
    summary = format_ai_summary(findings, duration_ms=50)
    # Each finding line should be under 500 chars
    for line in summary.splitlines():
        assert len(line) <= 500


# --- WP-101+102: Health dashboard ---

def test_stores_metrics_per_run(tmp_path):
    metrics = HealthMetrics(str(tmp_path / "metrics.jsonl"))
    metrics.record(findings=3, duration_ms=120, tier="fast", commit="abc")
    entries = metrics.recent(10)
    assert len(entries) == 1


def test_findings_trend_direction(tmp_path):
    metrics = HealthMetrics(str(tmp_path / "metrics.jsonl"))
    for i in range(5):
        metrics.record(findings=i, duration_ms=100, tier="fast", commit=f"c{i}")
    trend = metrics.trend()
    assert trend == "increasing"


def test_stable_shows_no_drift(tmp_path):
    metrics = HealthMetrics(str(tmp_path / "metrics.jsonl"))
    for i in range(5):
        metrics.record(findings=2, duration_ms=100, tier="fast", commit=f"c{i}")
    trend = metrics.trend()
    assert trend == "stable"


def test_handles_empty_history(tmp_path):
    metrics = HealthMetrics(str(tmp_path / "metrics.jsonl"))
    assert metrics.recent(10) == []
    assert metrics.trend() == "unknown"
