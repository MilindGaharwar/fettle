"""Gemini CLI headless adapter (Stage 13).

LIVE runner: launches ``gemini -p`` (non-interactive prompt mode).
Trusted-operator use only; never runs in public CI. Instead of ``--yolo``
(blanket bypass), edits are auto-approved via ``--approval-mode auto_edit``
and only the shell tool is pre-approved via ``--allowed-tools``; other
confirmation-gated tools (web fetch, MCP) are denied in -p mode.
Spec-derived (CLI not installed locally) — re-verify on a live install.
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
        args = ["--approval-mode", "auto_edit",
                "--allowed-tools", "run_shell_command", "-p", prompt]
        return run_cli("gemini", args, cwd, timeout_s)
