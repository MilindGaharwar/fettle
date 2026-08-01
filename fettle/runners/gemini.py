"""Gemini CLI headless adapter (Stage 13).

LIVE runner: launches ``gemini --yolo -p`` (non-interactive prompt mode).
Trusted-operator use only; never runs in public CI. ``--yolo`` is the
quorum approach's Gemini equivalent of Claude's
--dangerously-skip-permissions: in -p mode approval prompts cannot be
answered and stall the run to timeout.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fettle.runners import RunnerResult
from fettle.runners._subprocess import run_cli


class GeminiRunner:
    name = "gemini"

    def available(self) -> bool:
        return shutil.which("gemini") is not None

    def run(self, prompt: str, cwd: Path, timeout_s: int = 600) -> RunnerResult:
        return run_cli("gemini", ["--yolo", "-p", prompt], cwd, timeout_s)
