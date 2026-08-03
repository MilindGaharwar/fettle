"""Tests for fettle.runners — protocol, registry, and runner adapters."""

import subprocess
from unittest.mock import patch

from fettle.runners import (
    AgentRunner,
    RUNNER_NAMES,
    RunnerResult,
    detect_runners,
    get_runner,
)
from fettle.runners.claude import ClaudeRunner
from fettle.runners.codex import CodexRunner
from fettle.runners.gemini import GeminiRunner
from fettle.runners.opencode import OpenCodeRunner

import pytest


class TestRunnerResult:
    def test_success_result(self):
        r = RunnerResult(transcript="output", exit_code=0, duration_s=1.5)
        assert r.transcript == "output"
        assert r.exit_code == 0
        assert r.error == ""

    def test_error_result(self):
        r = RunnerResult("", -1, 0.0, error="timeout")
        assert r.error == "timeout"


class TestRegistry:
    def test_get_runner_claude(self):
        runner = get_runner("claude")
        assert isinstance(runner, AgentRunner)
        assert runner.name == "claude"

    def test_get_runner_codex(self):
        runner = get_runner("codex")
        assert runner.name == "codex"

    def test_get_runner_gemini(self):
        runner = get_runner("gemini")
        assert runner.name == "gemini"

    def test_get_runner_opencode(self):
        runner = get_runner("opencode")
        assert runner.name == "opencode"

    def test_get_runner_unknown_raises(self):
        with pytest.raises(ValueError, match="unknown agent runner"):
            get_runner("nonexistent")

    def test_runner_names_complete(self):
        assert "claude" in RUNNER_NAMES
        assert "codex" in RUNNER_NAMES
        assert "gemini" in RUNNER_NAMES
        assert "opencode" in RUNNER_NAMES

    def test_detect_runners_returns_dict(self):
        result = detect_runners()
        assert isinstance(result, dict)
        for name in RUNNER_NAMES:
            assert name in result
            assert isinstance(result[name], bool)


class TestClaudeRunner:
    def test_available_when_which_finds_it(self):
        with patch("shutil.which", return_value="/usr/bin/claude"):
            assert ClaudeRunner().available() is True

    def test_unavailable_when_not_on_path(self):
        with patch("shutil.which", return_value=None):
            assert ClaudeRunner().available() is False

    def test_run_not_on_path(self, tmp_path):
        with patch("shutil.which", return_value=None):
            result = ClaudeRunner().run("hello", tmp_path)
        assert result.error
        assert "not on PATH" in result.error

    def test_run_timeout(self, tmp_path):
        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 600)):
            result = ClaudeRunner().run("task", tmp_path, timeout_s=600)
        assert "timed out" in result.error

    def test_run_nonzero_exit(self, tmp_path):
        proc = subprocess.CompletedProcess(args=[], returncode=1,
                                           stdout="partial", stderr="err msg")
        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("subprocess.run", return_value=proc):
            result = ClaudeRunner().run("task", tmp_path)
        assert result.exit_code == 1
        assert "err msg" in result.error
        assert result.transcript == "partial"

    def test_run_success(self, tmp_path):
        proc = subprocess.CompletedProcess(args=[], returncode=0,
                                           stdout="done!", stderr="")
        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("subprocess.run", return_value=proc):
            result = ClaudeRunner().run("task", tmp_path)
        assert result.exit_code == 0
        assert result.error == ""
        assert result.transcript == "done!"
        assert result.duration_s >= 0


class TestCodexRunner:
    def test_unavailable_when_not_on_path(self):
        with patch("shutil.which", return_value=None):
            assert CodexRunner().available() is False


class TestGeminiRunner:
    def test_unavailable_when_not_on_path(self):
        with patch("shutil.which", return_value=None):
            assert GeminiRunner().available() is False


class TestOpenCodeRunner:
    def test_unavailable_when_not_on_path(self):
        with patch("shutil.which", return_value=None):
            assert OpenCodeRunner().available() is False
