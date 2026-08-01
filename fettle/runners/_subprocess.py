"""Shared subprocess core for CLI-backed agent runners (Stage 13).

Same fail-visible contract as the Claude adapter: expected failures
(binary missing, timeout, non-zero exit) land in ``RunnerResult.error``,
never as exceptions, and a partial transcript is preserved as evidence.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from fettle.runners import RunnerResult


def run_cli(binary: str, args: list[str], cwd: Path, timeout_s: int) -> RunnerResult:
    """Run ``binary args…`` in *cwd* and map the outcome to a RunnerResult."""
    resolved = shutil.which(binary)
    if not resolved:
        return RunnerResult("", -1, 0.0,
                            error=f"{binary} CLI not on PATH — live runs unavailable")
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [resolved, *args],
            capture_output=True, text=True,
            timeout=timeout_s, cwd=str(cwd),
        )
    except subprocess.TimeoutExpired:
        return RunnerResult("", -1, time.monotonic() - start,
                            error=f"{binary} run timed out after {timeout_s}s")
    duration = time.monotonic() - start
    error = ""
    if proc.returncode != 0:
        stderr_tail = (proc.stderr or "").strip()[-500:]
        error = f"{binary} exited {proc.returncode}: {stderr_tail or 'no stderr'}"
    return RunnerResult(proc.stdout, proc.returncode, duration, error=error)
