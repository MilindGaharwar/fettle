"""Codex CLI headless adapter (Stage 13).

LIVE runner: launches ``codex exec`` (non-interactive mode). Trusted-
operator use only; never runs in public CI. ``--full-auto`` is the quorum
approach's Codex equivalent of Claude's --dangerously-skip-permissions:
in exec mode approval prompts cannot be answered, so the run gets a
sandboxed workspace-write policy with no prompts.
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
        return run_cli("codex", ["exec", "--full-auto", prompt], cwd, timeout_s)
