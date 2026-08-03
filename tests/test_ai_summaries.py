"""Tests for fettle.ai_summaries — AI-agent optimized finding summaries."""

from fettle.ai_summaries import format_ai_summary
from fettle.finding import CheckFinding, FindingSeverity


class TestFormatAiSummary:
    def test_empty_findings(self):
        assert format_ai_summary([]) == "No findings."

    def test_single_blocking(self):
        findings = [CheckFinding(
            checker="ruff", severity=FindingSeverity.ERROR,
            file="app.py", line=10, message="undefined name",
            blocking=True,
        )]
        result = format_ai_summary(findings)
        assert "1 blocking" in result
        assert "app.py:10" in result
        assert "undefined name" in result
        assert "fettle check" in result

    def test_mixed_findings(self):
        findings = [
            CheckFinding(checker="ruff", severity=FindingSeverity.ERROR,
                         file="a.py", line=1, message="err", blocking=True),
            CheckFinding(checker="ruff", severity=FindingSeverity.WARNING,
                         file="b.py", line=2, message="warn"),
            CheckFinding(checker="ruff", severity=FindingSeverity.INFO,
                         file="c.py", line=3, message="info"),
        ]
        result = format_ai_summary(findings, duration_ms=42.5)
        assert "1 blocking" in result
        assert "1 warning" in result
        assert "1 info" in result
        assert "42ms" in result

    def test_truncation_at_10(self):
        findings = [CheckFinding(checker="x", severity=FindingSeverity.WARNING,
                                 file=f"f{i}.py", line=i, message=f"m{i}")
                    for i in range(15)]
        result = format_ai_summary(findings)
        assert "and 5 more" in result

    def test_suggested_fix_shown(self):
        findings = [CheckFinding(
            checker="ruff", severity=FindingSeverity.WARNING,
            file="x.py", line=1, message="unused import",
            suggested_fix="remove the import",
        )]
        result = format_ai_summary(findings)
        assert "fix: remove the import" in result
