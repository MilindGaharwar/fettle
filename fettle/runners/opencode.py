"""OpenCode headless adapter (Stage 13).

LIVE runner: launches ``opencode run`` (subcommand verified against
opencode's own --help). Trusted-operator use only; never runs in public
CI. OpenCode's run mode executes without interactive approval prompts,
so no permission-bypass flag is needed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fettle.runners import RunnerResult
from fettle.runners._subprocess import run_cli


class OpenCodeRunner:
    name = "opencode"

    def available(self) -> bool:
        return shutil.which("opencode") is not None

    def run(self, prompt: str, cwd: Path, timeout_s: int = 600) -> RunnerResult:
        return run_cli("opencode", ["run", prompt], cwd, timeout_s)
