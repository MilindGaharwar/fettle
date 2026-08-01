"""Outbound agent-runner protocol — Stage 4 (S4.1), design doc 09.

Mirror of the inbound ``fettle.agents`` pattern (WP-140), in the outbound
direction: a uniform way for Fettle surfaces (evals today, agentic UAT in
Stage 5) to launch a headless coding agent and get its transcript back.

Fail-visible contract: a runner never raises for an expected failure mode
(binary missing, timeout, non-zero exit) and never returns a silently empty
transcript — failures land in ``RunnerResult.error``.

Adapters are added only alongside a conformance test (no aspirational
stubs). Current adapters: claude.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RunnerResult:
    """Outcome of one headless agent run."""

    transcript: str          # agent's final output (stdout)
    exit_code: int
    duration_s: float
    error: str = ""          # non-empty → the run failed; transcript may be partial


@runtime_checkable
class AgentRunner(Protocol):
    """A headless coding agent Fettle can launch."""

    name: str

    def available(self) -> bool:
        """True when the agent CLI is present and launchable."""
        ...

    def run(self, prompt: str, cwd: Path, timeout_s: int = 600) -> RunnerResult:
        """Run the agent on ``prompt`` inside ``cwd``. Never raises for
        expected failures — see RunnerResult.error."""
        ...


def get_runner(name: str) -> AgentRunner:
    """Look up a registered runner by name. Raises ValueError for unknown."""
    if name == "claude":
        from fettle.runners.claude import ClaudeRunner
        return ClaudeRunner()
    raise ValueError(
        f"unknown agent runner '{name}' (registered: {', '.join(sorted(RUNNER_NAMES))})")


RUNNER_NAMES: frozenset[str] = frozenset({"claude"})


def detect_runners() -> dict[str, bool]:
    """Availability probe over all registered runners (feeds doctor/UAT)."""
    return {name: get_runner(name).available() for name in sorted(RUNNER_NAMES)}
