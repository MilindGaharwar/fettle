"""Tests for fettle.runners — outbound AgentRunner protocol (Stage 4 / Stage 13)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from fettle.runners import AgentRunner, RUNNER_NAMES, RunnerResult, detect_runners, get_runner
from fettle.runners.claude import ClaudeRunner
from fettle.runners.codex import CodexRunner
from fettle.runners.gemini import GeminiRunner
from fettle.runners.opencode import OpenCodeRunner

#: (runner class, binary, flags that MUST appear in argv)
CLI_RUNNERS = [
    (CodexRunner, "codex", [
        "-a", "never", "-s", "workspace-write", "--dangerously-bypass-hook-trust", "exec",
    ]),
    (GeminiRunner, "gemini", [
        "--approval-mode", "auto_edit", "--allowed-tools", "run_shell_command", "-p",
    ]),
    (OpenCodeRunner, "opencode", ["run"]),
]
CLI_IDS = [binary for _, binary, _ in CLI_RUNNERS]

#: Permission-bypass flags the agent_spawn_gate blocks in child launches —
#: fettle's own runners must never carry them (2026-08 audit HIGH-4).
BYPASS_FLAGS = {"--dangerously-skip-permissions", "--yolo", "--full-auto"}


class TestRegistry:
    def test_get_runner_claude(self):
        runner = get_runner("claude")
        assert runner.name == "claude"
        assert isinstance(runner, AgentRunner)  # runtime_checkable protocol

    def test_registry_has_all_four_agents(self):
        assert sorted(RUNNER_NAMES) == ["claude", "codex", "gemini", "opencode"]

    def test_get_runner_unknown_raises_with_names(self):
        with pytest.raises(ValueError, match="claude"):
            get_runner("nonexistent-agent")

    def test_registry_names_all_resolvable(self):
        for name in RUNNER_NAMES:
            assert get_runner(name).name == name

    def test_detect_runners_probes_all(self):
        probed = detect_runners()
        assert set(probed) == set(RUNNER_NAMES)
        assert all(isinstance(v, bool) for v in probed.values())


class TestClaudeRunner:
    def test_unavailable_when_binary_missing(self):
        with patch("fettle.runners.claude.shutil.which", return_value=None):
            runner = ClaudeRunner()
            assert runner.available() is False
            result = runner.run("do things", Path("/tmp"))
            assert result.error  # fail-visible, no raise
            assert result.exit_code == -1

    def test_successful_run(self, tmp_path):
        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="I did the thing", stderr="")
        with patch("fettle.runners.claude.shutil.which", return_value="/usr/bin/claude"), \
             patch("fettle.runners.claude.subprocess.run", return_value=proc) as mock_run:
            result = ClaudeRunner().run("prompt", tmp_path, timeout_s=30)
        assert result.transcript == "I did the thing"
        assert result.exit_code == 0
        assert result.error == ""
        cmd = mock_run.call_args[0][0]
        assert "--allowedTools" in cmd
        assert not BYPASS_FLAGS & set(cmd)
        assert mock_run.call_args.kwargs["timeout"] == 30
        assert mock_run.call_args.kwargs["cwd"] == str(tmp_path)

    def test_nonzero_exit_sets_error_keeps_transcript(self, tmp_path):
        proc = subprocess.CompletedProcess(
            args=[], returncode=2, stdout="partial output", stderr="boom")
        with patch("fettle.runners.claude.shutil.which", return_value="/usr/bin/claude"), \
             patch("fettle.runners.claude.subprocess.run", return_value=proc):
            result = ClaudeRunner().run("prompt", tmp_path)
        assert result.transcript == "partial output"  # partial evidence kept
        assert "exited 2" in result.error
        assert "boom" in result.error

    def test_timeout_sets_error(self, tmp_path):
        exc = subprocess.TimeoutExpired(cmd="claude", timeout=5)
        with patch("fettle.runners.claude.shutil.which", return_value="/usr/bin/claude"), \
             patch("fettle.runners.claude.subprocess.run", side_effect=exc):
            result = ClaudeRunner().run("prompt", tmp_path, timeout_s=5)
        assert "timed out after 5s" in result.error
        assert result.exit_code == -1


class TestCliRunners:
    """Codex/Gemini/OpenCode adapters share the _subprocess core — same
    fail-visible contract as ClaudeRunner, pinned per adapter."""

    def test_codex_places_global_flags_before_exec(self, tmp_path):
        proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
        with patch("fettle.runners._subprocess.shutil.which", return_value="/usr/bin/codex"), \
             patch("fettle.runners._subprocess.subprocess.run", return_value=proc) as mock_run:
            CodexRunner().run("prompt", tmp_path)
        assert mock_run.call_args[0][0] == [
            "/usr/bin/codex", "-a", "never", "-s", "workspace-write",
            "--dangerously-bypass-hook-trust", "exec", "prompt",
        ]

    @pytest.mark.parametrize("cls,binary,flags", CLI_RUNNERS, ids=CLI_IDS)
    def test_protocol_conformance(self, cls, binary, flags):
        runner = cls()
        assert isinstance(runner, AgentRunner)
        assert runner.name == binary

    @pytest.mark.parametrize("cls,binary,flags", CLI_RUNNERS, ids=CLI_IDS)
    def test_unavailable_when_binary_missing(self, cls, binary, flags):
        with patch(f"fettle.runners.{binary}.shutil.which", return_value=None), \
             patch("fettle.runners._subprocess.shutil.which", return_value=None):
            runner = cls()
            assert runner.available() is False
            result = runner.run("do things", Path("/tmp"))
            assert result.error  # fail-visible, no raise
            assert result.exit_code == -1

    @pytest.mark.parametrize("cls,binary,flags", CLI_RUNNERS, ids=CLI_IDS)
    def test_successful_run(self, cls, binary, flags, tmp_path):
        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="I did the thing", stderr="")
        with patch("fettle.runners._subprocess.shutil.which", return_value=f"/usr/bin/{binary}"), \
             patch("fettle.runners._subprocess.subprocess.run", return_value=proc) as mock_run:
            result = cls().run("prompt", tmp_path, timeout_s=30)
        assert result.transcript == "I did the thing"
        assert result.exit_code == 0
        assert result.error == ""
        cmd = mock_run.call_args[0][0]
        for flag in flags:
            assert flag in cmd, f"{binary} argv missing {flag}: {cmd}"
        assert not BYPASS_FLAGS & set(cmd), f"{binary} argv carries a bypass flag: {cmd}"
        assert cmd[-1] == "prompt"
        assert mock_run.call_args.kwargs["timeout"] == 30
        assert mock_run.call_args.kwargs["cwd"] == str(tmp_path)

    @pytest.mark.parametrize("cls,binary,flags", CLI_RUNNERS, ids=CLI_IDS)
    def test_nonzero_exit_sets_error_keeps_transcript(self, cls, binary, flags, tmp_path):
        proc = subprocess.CompletedProcess(
            args=[], returncode=2, stdout="partial output", stderr="boom")
        with patch("fettle.runners._subprocess.shutil.which", return_value=f"/usr/bin/{binary}"), \
             patch("fettle.runners._subprocess.subprocess.run", return_value=proc):
            result = cls().run("prompt", tmp_path)
        assert result.transcript == "partial output"  # partial evidence kept
        assert "exited 2" in result.error
        assert "boom" in result.error

    @pytest.mark.parametrize("cls,binary,flags", CLI_RUNNERS, ids=CLI_IDS)
    def test_timeout_sets_error(self, cls, binary, flags, tmp_path):
        exc = subprocess.TimeoutExpired(cmd=binary, timeout=5)
        with patch("fettle.runners._subprocess.shutil.which", return_value=f"/usr/bin/{binary}"), \
             patch("fettle.runners._subprocess.subprocess.run", side_effect=exc):
            result = cls().run("prompt", tmp_path, timeout_s=5)
        assert "timed out after 5s" in result.error
        assert result.exit_code == -1


class TestEvalsIntegration:
    """evals_runner consumes the protocol; the plain-callable seam survives."""

    def _scenario(self, tmp_path):
        from fettle.evals_runner import Check, Scenario
        return Scenario(
            id="s", prompt="add divide",
            checks=(Check(type="transcript_matches", regex="divide"),),
        )

    def test_agent_runner_object_accepted(self, tmp_path):
        from fettle.evals_runner import Verdict, run_scenario

        class FakeRunner:
            name = "fake"
            def available(self):
                return True
            def run(self, prompt, cwd, timeout_s=600):
                return RunnerResult("added divide", 0, 0.1)

        result = run_scenario(self._scenario(tmp_path), runner=FakeRunner(),
                              workdir=tmp_path / "run")
        assert result.verdict == Verdict.PASS

    def test_runner_error_maps_to_indeterminate(self, tmp_path):
        from fettle.evals_runner import Verdict, run_scenario

        class BrokenRunner:
            name = "broken"
            def available(self):
                return False
            def run(self, prompt, cwd, timeout_s=600):
                return RunnerResult("", -1, 0.0, error="CLI not on PATH")

        result = run_scenario(self._scenario(tmp_path), runner=BrokenRunner(),
                              workdir=tmp_path / "run")
        assert result.verdict == Verdict.INDETERMINATE

    def test_plain_callable_still_works(self, tmp_path):
        from fettle.evals_runner import Verdict, run_scenario

        result = run_scenario(self._scenario(tmp_path),
                              runner=lambda prompt, cwd: "divide added",
                              workdir=tmp_path / "run")
        assert result.verdict == Verdict.PASS
