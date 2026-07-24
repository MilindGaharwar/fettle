"""Fettle v0.5.0 — WP-70: Tool execution abstraction.

Common subprocess runner all checkers use. Handles timeouts, env
passthrough, redaction, tool-missing detection, and provides a fake
executor for deterministic testing.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass


@dataclass
class RunResult:
    """Result of running an external tool."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    tool_missing: bool = False

    @property
    def error_message(self) -> str:
        if self.timed_out:
            return f"Timed out (exit {self.returncode})"
        if self.tool_missing:
            return "Tool not found: command not on PATH"
        if self.returncode != 0:
            return self.stderr.strip() or f"Exit code {self.returncode}"
        return ""


class ToolRunner:
    """Run external tools with timeout, env control, and error handling."""

    def __init__(
        self,
        timeout_s: float = 30.0,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        redact_env_keys: list[str] | None = None,
    ):
        self.timeout_s = timeout_s
        self.cwd = cwd
        self.env = env
        self.redact_env_keys = set(redact_env_keys or [])

    def run(self, cmd: list[str]) -> RunResult:
        run_env: dict[str, str] | None = None
        if self.env:
            run_env = {**os.environ, **self.env}

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.timeout_s,
                cwd=self.cwd,
                env=run_env,
            )
            return RunResult(
                returncode=proc.returncode,
                stdout=proc.stdout.decode("utf-8", errors="replace"),
                stderr=proc.stderr.decode("utf-8", errors="replace"),
            )
        except subprocess.TimeoutExpired:
            return RunResult(returncode=-1, timed_out=True)
        except FileNotFoundError:
            return RunResult(returncode=-1, tool_missing=True)
        except OSError as e:
            return RunResult(returncode=-1, stderr=str(e), tool_missing=True)

    def describe_env(self) -> str:
        """Describe env vars for logging, with secrets redacted."""
        if not self.env:
            return "(inherited)"
        parts = []
        for k, v in sorted(self.env.items()):
            if k in self.redact_env_keys:
                parts.append(f"{k}=***")
            else:
                parts.append(f"{k}={v}")
        return " ".join(parts)


class FakeRunner:
    """Deterministic test double for ToolRunner."""

    def __init__(self, responses: dict[tuple[str, ...], RunResult] | None = None):
        self.responses = responses or {}
        self.calls: list[list[str]] = []

    def run(self, cmd: list[str]) -> RunResult:
        self.calls.append(cmd)
        key = tuple(cmd)
        if key in self.responses:
            return self.responses[key]
        return RunResult(returncode=-1, tool_missing=True)
