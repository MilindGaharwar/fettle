"""Tests for scripts/check_runner.py — WP-74: Check runner core."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from check_runner import CheckRunner, CheckerRegistration
from finding import CheckFinding, FindingSeverity


class FakeChecker:
    """Test checker that returns predetermined findings."""

    def __init__(self, name, findings=None, delay_s=0, crash=False):
        self.name = name
        self._findings = findings or []
        self._delay_s = delay_s
        self._crash = crash

    def check(self, files):
        if self._crash:
            raise RuntimeError(f"{self.name} crashed")
        if self._delay_s:
            import time
            time.sleep(self._delay_s)
        return self._findings


def _make_finding(checker="ruff", severity=FindingSeverity.ERROR, file="x.py", line=1, msg="err"):
    return CheckFinding(checker=checker, severity=severity, file=file, line=line, message=msg)


def test_runs_registered_checkers():
    runner = CheckRunner()
    runner.register(CheckerRegistration(
        name="ruff",
        checker=FakeChecker("ruff", [_make_finding()]),
        tiers=["fast", "changed", "full"],
    ))
    result = runner.run(tier="fast", files=["x.py"])
    assert len(result.findings) == 1


def test_aggregates_findings_from_multiple_checkers():
    runner = CheckRunner()
    runner.register(CheckerRegistration(
        name="ruff",
        checker=FakeChecker("ruff", [_make_finding(checker="ruff")]),
        tiers=["fast"],
    ))
    runner.register(CheckerRegistration(
        name="semgrep",
        checker=FakeChecker("semgrep", [_make_finding(checker="semgrep")]),
        tiers=["fast"],
    ))
    result = runner.run(tier="fast", files=["x.py"])
    assert len(result.findings) == 2
    checkers = {f.checker for f in result.findings}
    assert "ruff" in checkers
    assert "semgrep" in checkers


def test_per_checker_timeout_enforced():
    runner = CheckRunner(per_checker_timeout_s=1)
    runner.register(CheckerRegistration(
        name="slow",
        checker=FakeChecker("slow", delay_s=5),
        tiers=["fast"],
    ))
    result = runner.run(tier="fast", files=["x.py"])
    # Should produce a tool error finding, not hang
    assert any("timeout" in f.message.lower() or "timed out" in f.message.lower() for f in result.findings)


def test_tier_budget_enforced():
    runner = CheckRunner(tier_timeout_s=1)
    runner.register(CheckerRegistration(
        name="slow1",
        checker=FakeChecker("slow1", delay_s=3),
        tiers=["fast"],
    ))
    runner.register(CheckerRegistration(
        name="slow2",
        checker=FakeChecker("slow2", delay_s=3),
        tiers=["fast"],
    ))
    result = runner.run(tier="fast", files=["x.py"])
    # At least one should report deferred/timeout
    assert result.duration_ms < 5000


def test_exit_code_0_on_pass():
    runner = CheckRunner()
    runner.register(CheckerRegistration(
        name="ruff",
        checker=FakeChecker("ruff", []),
        tiers=["fast"],
    ))
    result = runner.run(tier="fast", files=["x.py"])
    assert result.exit_code == 0


def test_exit_code_1_on_warnings_only():
    runner = CheckRunner()
    runner.register(CheckerRegistration(
        name="ruff",
        checker=FakeChecker("ruff", [_make_finding(severity=FindingSeverity.WARNING)]),
        tiers=["fast"],
    ))
    result = runner.run(tier="fast", files=["x.py"])
    assert result.exit_code == 1


def test_exit_code_2_on_blocking_findings():
    runner = CheckRunner()
    runner.register(CheckerRegistration(
        name="ruff",
        checker=FakeChecker("ruff", [_make_finding(severity=FindingSeverity.ERROR)]),
        tiers=["fast"],
    ))
    result = runner.run(tier="fast", files=["x.py"])
    assert result.exit_code == 2


def test_checker_crash_produces_tool_error_finding():
    runner = CheckRunner()
    runner.register(CheckerRegistration(
        name="crasher",
        checker=FakeChecker("crasher", crash=True),
        tiers=["fast"],
    ))
    result = runner.run(tier="fast", files=["x.py"])
    assert any("crash" in f.message.lower() for f in result.findings)
    assert result.findings[0].severity == FindingSeverity.WARNING


def test_empty_checker_list_passes():
    runner = CheckRunner()
    result = runner.run(tier="fast", files=["x.py"])
    assert result.exit_code == 0
    assert result.findings == []
