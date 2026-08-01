"""Tests for fettle.runners — outbound AgentRunner protocol (Stage 4, S4.1)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from fettle.runners import AgentRunner, RUNNER_NAMES, RunnerResult, detect_runners, get_runner
from fettle.runners.claude import ClaudeRunner


class TestRegistry:
    def test_get_runner_claude(self):
        runner = get_runner("claude")
        assert runner.name == "claude"
        assert isinstance(runner, AgentRunner)  # runtime_checkable protocol

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
        assert "--dangerously-skip-permissions" in cmd
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
