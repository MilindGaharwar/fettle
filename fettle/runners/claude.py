"""Claude Code headless adapter — extracted from evals_runner._claude_runner.

LIVE runner: launches ``claude -p``. Trusted-operator use only; never runs
in public CI. Runs with --dangerously-skip-permissions (the quorum
approach): in non-interactive print mode, permission prompts cannot be
answered and stall the run to timeout.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from fettle.runners import RunnerResult


class ClaudeRunner:
    name = "claude"

    def available(self) -> bool:
        return shutil.which("claude") is not None

    def run(self, prompt: str, cwd: Path, timeout_s: int = 600) -> RunnerResult:
        claude = shutil.which("claude")
        if not claude:
            return RunnerResult("", -1, 0.0,
                                error="claude CLI not on PATH — live runs unavailable")
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [claude, "-p", "--dangerously-skip-permissions", prompt],
                capture_output=True, text=True,
                timeout=timeout_s, cwd=str(cwd),
            )
        except subprocess.TimeoutExpired:
            return RunnerResult("", -1, time.monotonic() - start,
                                error=f"claude run timed out after {timeout_s}s")
        duration = time.monotonic() - start
        error = ""
        if proc.returncode != 0:
            stderr_tail = (proc.stderr or "").strip()[-500:]
            error = f"claude exited {proc.returncode}: {stderr_tail or 'no stderr'}"
        return RunnerResult(proc.stdout, proc.returncode, duration, error=error)
