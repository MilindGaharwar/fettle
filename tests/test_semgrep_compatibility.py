"""Exercise the Python syntax that failed with the older installed parser."""
import os
from unittest.mock import patch
from fettle import quality_scan
from fettle.result import ResultStatus
from fettle.tool_runner import RunResult


def test_structural_pattern_matching_parses(tmp_path):
    source = tmp_path / "width.py"
    source.write_text("from enum import Enum\nclass Width(Enum):\n    ZERO = 0\n    def width(self):\n        match self:\n            case Width.ZERO:\n                return 0\n            case _:\n                return 1\n")
    with patch.dict(os.environ, {"SEMGREP_SEND_METRICS": "off", "SEMGREP_ENABLE_VERSION_CHECK": "0"}):
        result = quality_scan.execute_semgrep([str(source)])
    assert result.status in {ResultStatus.PASS, ResultStatus.VIOLATION}, result.message


def test_scanner_budgets_remain_bounded_and_timeouts_fail(monkeypatch):
    budgets = []
    monkeypatch.setattr(quality_scan, "_resolve_tool", lambda name: "/bin/" + name)
    def timeout(self, command):
        budgets.append(self.timeout_s)
        return RunResult(returncode=-1, timed_out=True)
    monkeypatch.setattr(quality_scan.ToolRunner, "run", timeout)
    for scan in (quality_scan.execute_ruff, quality_scan.execute_semgrep):
        assert scan([__file__]).status == ResultStatus.TOOL_ERROR
    assert budgets == [120.0, 600.0]
