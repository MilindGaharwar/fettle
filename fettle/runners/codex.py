"""Codex CLI headless adapter (Stage 13).

LIVE runner: launches ``codex exec`` (non-interactive mode). Trusted-
operator use only; never runs in public CI. Approval and sandbox flags give
the run a workspace-write policy with no prompts. Fettle also bypasses the
interactive hook-trust prompt so its registered hooks execute headlessly.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fettle.runners import RunnerResult
from fettle.runners._subprocess import run_cli


class CodexRunner:
    name = "codex"

    def available(self) -> bool:
        return shutil.which("codex") is not None

    def run(self, prompt: str, cwd: Path, timeout_s: int = 600) -> RunnerResult:
        args = [
            "-a", "never", "-s", "workspace-write",
            "--dangerously-bypass-hook-trust", "exec", prompt,
        ]
        return run_cli("codex", args, cwd, timeout_s)
