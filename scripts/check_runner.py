"""Fettle v0.5.0 — WP-74: Check runner core.

Orchestrates checkers with timeout, result aggregation, and exit codes.
"""

from __future__ import annotations

import time
import concurrent.futures
from dataclasses import dataclass, field
from typing import Any, Protocol

from finding import CheckFinding, CheckResult, FindingSeverity, sort_findings


class CheckerProtocol(Protocol):
    """Protocol that all checkers must implement."""

    name: str

    def check(self, files: list[str]) -> list[CheckFinding]: ...


@dataclass
class CheckerRegistration:
    """A registered checker with its tier membership."""

    name: str
    checker: Any
    tiers: list[str] = field(default_factory=list)
    timeout_s: float | None = None


class CheckRunner:
    """Orchestrates checkers per tier with timeout and aggregation."""

    def __init__(
        self,
        per_checker_timeout_s: float = 30.0,
        tier_timeout_s: float = 15.0,
    ):
        self.per_checker_timeout_s = per_checker_timeout_s
        self.tier_timeout_s = tier_timeout_s
        self._registrations: list[CheckerRegistration] = []

    def register(self, reg: CheckerRegistration) -> None:
        self._registrations.append(reg)

    def run(self, tier: str, files: list[str]) -> CheckResult:
        """Run all checkers registered for this tier."""
        start = time.monotonic()
        applicable = [r for r in self._registrations if tier in r.tiers]

        if not applicable:
            return CheckResult(findings=[], duration_ms=0.0)

        all_findings: list[CheckFinding] = []
        tier_deadline = start + self.tier_timeout_s

        for reg in applicable:
            remaining = tier_deadline - time.monotonic()
            if remaining <= 0:
                all_findings.append(CheckFinding(
                    checker=reg.name,
                    severity=FindingSeverity.WARNING,
                    file="",
                    line=0,
                    message=f"{reg.name}: deferred (tier budget exhausted)",
                ))
                continue

            checker_timeout = min(
                reg.timeout_s or self.per_checker_timeout_s,
                remaining,
            )
            findings = self._run_one(reg, files, checker_timeout)
            all_findings.extend(findings)

        elapsed_ms = (time.monotonic() - start) * 1000
        return CheckResult(
            findings=sort_findings(all_findings),
            duration_ms=elapsed_ms,
        )

    def _run_one(
        self, reg: CheckerRegistration, files: list[str], timeout_s: float
    ) -> list[CheckFinding]:
        """Run a single checker with timeout."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(reg.checker.check, files)
            try:
                result = future.result(timeout=timeout_s)
                if isinstance(result, list):
                    return result
                return []
            except concurrent.futures.TimeoutError:
                return [CheckFinding(
                    checker=reg.name,
                    severity=FindingSeverity.WARNING,
                    file="",
                    line=0,
                    message=f"{reg.name}: timed out after {timeout_s:.0f}s",
                )]
            except Exception as e:  # noqa: BLE001
                import sys
                print(f"fettle: checker {reg.name} crashed: {e}", file=sys.stderr)
                return [CheckFinding(
                    checker=reg.name,
                    severity=FindingSeverity.WARNING,
                    file="",
                    line=0,
                    message=f"{reg.name} crashed: {e}",
                )]
