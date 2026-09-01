"""Claude Code headless adapter — extracted from evals_runner._claude_runner.

LIVE runner: launches ``claude -p``. Trusted-operator use only; never runs
in public CI. Runs with a scoped ``--allowedTools`` list instead of
``--dangerously-skip-permissions``: in print mode, tools outside the list
are denied without prompting (deny-by-default), so repo-derived prompt
content cannot reach network or MCP tools while shell/file tools still
run unattended.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from fettle.runners import RunnerResult

#: Deny-by-default tool grant for unattended runs (UAT/evals/spawn).
ALLOWED_TOOLS = "Bash Read Glob Grep Write Edit TodoWrite"


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
                [claude, "-p", "--allowedTools", ALLOWED_TOOLS, prompt],
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
