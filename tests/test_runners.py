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
    @pytest.mark.parametrize("proposal", [
        None, [], {}, {"inputs": []}, {"inputs": [1]}, {"inputs": [True]},
        {"inputs": ["x", "x"]}, {"inputs": ["\0"]}, {"inputs": ["x" * 65]},
        {"inputs": ["\u00e9" * 33]}, {"inputs": [str(number) for number in range(13)]},
        {"inputs": ["0"], "expect": "pass"},
    ])
    def test_discovery_rejects_invalid_inputs(self, proposal):
        from evals.uat_cli_controller import discovery_inputs

        with pytest.raises(ValueError):
            discovery_inputs(proposal)

    @pytest.mark.parametrize("value,expected", [
        ("", "invalid"), (" 0", "invalid"), ("1.0", "invalid"),
        ("\u0661", "invalid"), ("1\n", "invalid"), ("+", "invalid"),
        ("-3", "outside"), ("-2", "inside"), ("+2", "inside"),
        ("3", "outside"), ("000", "inside"), ("-0", "inside"),
    ])
    def test_discovery_oracle_boundaries(self, value, expected):
        from evals.uat_cli_controller import range_oracle

        policy = {"minimum": -2, "maximum": 2, "inside": "inside",
                  "outside": "outside", "invalid": "invalid"}
        assert range_oracle(policy, value) == {
            "exit_code": 0, "stdout": expected + "\n", "stderr": ""}

    def test_native_discovery_gets_requirements_not_seed_or_oracle(self):
        from evals.uat_cli_controller import discovery_inputs, native_discovery

        with patch("evals.uat_cli_controller._native_json", return_value=(
                {"inputs": ["", "-1", "0", "1", "x" * 64]}, {"terminal_event": "turn.completed"})) as call:
            inputs, record = native_discovery("Accept the inclusive range 0 through 1.")
        assert inputs == ["", "-1", "0", "1", "x" * 64]
        assert record["terminal_event"] == "turn.completed"
        assert call.call_args.args[0].endswith("Accept the inclusive range 0 through 1.")
        assert discovery_inputs({"inputs": [str(number) for number in range(12)]})

    def test_discovery_metrics_preserve_misses_and_blocks(self):
        from evals.uat_cli_controller import discovery_metrics

        metrics = discovery_metrics([
            {"expected_state": "violation", "state": "pass"},
            {"expected_state": "violation", "state": "unknown"},
            {"expected_state": "violation", "state": "violation"},
            {"expected_state": "pass", "state": "violation"},
            {"expected_state": "unknown", "state": "unknown"},
        ])
        assert metrics == {"cases": 5, "matched": 2, "defects": 3, "discovered": 1,
                           "missed_defects": 2, "false_passes": 1, "false_alarms": 1, "blocked": 2}

    def test_discovery_reserves_output_and_preserves_partial_failure(self, tmp_path):
        import json
        from evals.uat_cli_controller import main

        corpus = tmp_path / "corpus.json"
        corpus.write_text("{}")
        wheel = tmp_path / "candidate.whl"
        wheel.write_bytes(b"candidate")
        output = tmp_path / "trial.json"
        arguments = ["eval", "--python", "python", "--wheel", str(wheel), "--output", str(output),
                     "--native-discovery-corpus", str(corpus), "--approve-discovery-corpus", "approved"]

        def interrupted(_python, _wheel, _corpus, record, path):
            assert json.loads(path.read_text())["status"] == "started"
            record["cases"] = [{"state": "violation"}]
            raise OSError("interrupted synthetic trial")

        with patch("sys.argv", arguments), patch("evals.uat_cli_controller.load_discovery_corpus", return_value={}), \
                patch("evals.uat_cli_controller.qualify_discovery", side_effect=interrupted) as qualify:
            with pytest.raises(SystemExit) as first:
                main()
            assert first.value.code == 1
            retained = output.read_bytes()
            record = json.loads(retained)
            assert record["status"] == "blocked" and record["passed"] is False
            assert record["cases"] == [{"state": "violation"}]
            with pytest.raises(FileExistsError):
                main()
            assert qualify.call_count == 1 and output.read_bytes() == retained

    def test_native_discovery_rejects_tool_execution(self):
        import json
        from evals.uat_cli_controller import native_discovery

        events = [{"type": "item.completed", "item": {"type": "command_execution"}},
                  {"type": "item.completed", "item": {"type": "agent_message", "text": '{"inputs":["0"]}'}},
                  {"type": "turn.completed"}]
        with patch("evals.uat_cli_controller.subprocess.run", return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="\n".join(json.dumps(event) for event in events), stderr="")):
            with pytest.raises(ValueError, match="tool action"):
                native_discovery("Accept zero")

    @pytest.mark.parametrize("mutation", ["valid", "approval", "boolean", "bounds", "duplicate",
                                           "no-control", "extra", "symlink"])
    def test_discovery_corpus_validation(self, mutation, tmp_path):
        import json
        from evals.uat_cli_controller import digest, load_discovery_corpus

        suite = {"id": "range", "requirements": "Inclusive 0 to 1.",
                 "oracle": {"minimum": 0, "maximum": 1, "inside": "in", "outside": "out", "invalid": "bad"},
                 "cases": [{"id": "healthy", "source": "print('in')", "expected_state": "pass"},
                           {"id": "defect", "source": "print('out')", "expected_state": "violation"}]}
        corpus = {"schema_version": 1, "suites": [suite]}
        if mutation == "boolean":
            suite["oracle"]["minimum"] = False
        elif mutation == "bounds":
            suite["oracle"]["minimum"] = 2
        elif mutation == "duplicate":
            corpus["suites"].append(suite)
        elif mutation == "no-control":
            suite["cases"][0]["expected_state"] = "violation"
        elif mutation == "extra":
            corpus["approval"] = True
        path = tmp_path / "corpus.json"
        path.write_text(json.dumps(corpus))
        approval = digest(path.read_bytes()) if mutation != "approval" else "wrong"
        if mutation == "symlink":
            link = tmp_path / "linked.json"
            link.symlink_to(path)
            path = link
        if mutation == "valid":
            assert load_discovery_corpus(path, approval) == corpus
        else:
            with pytest.raises(ValueError):
                load_discovery_corpus(path, approval)

    @pytest.mark.parametrize("output,exit_code", [
        ('', 0), ('{"type":"turn.started"}\n', 0),
        ('{"type":"turn.failed"}\n', 0),
        ('{"type":"turn.completed"}\n', 1),
        ('{"type":"turn.completed"}\n', 0),
        ('x' * 1048577, 0),
        ('[]\n', 0), ('{"type":"turn.completed","type":"turn.completed"}\n', 0),
    ])
    def test_native_proposal_incomplete_transport_is_nonpass(self, output, exit_code):
        from evals.uat_cli_controller import native_proposal

        with patch("evals.uat_cli_controller.subprocess.run", return_value=subprocess.CompletedProcess(
                args=[], returncode=exit_code, stdout=output, stderr="")):
            with pytest.raises(ValueError):
                native_proposal({"schema_version": 1, "scenario_digest": "frozen", "actions": []})

    def test_native_proposal_transport_keeps_normal_permissions(self):
        import json
        from evals.uat_cli_controller import native_proposal

        payload = {"schema_version": 1, "scenario_digest": "frozen", "actions": []}
        events = [
            {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(payload)}},
            {"type": "turn.completed"},
        ]
        with patch("evals.uat_cli_controller.subprocess.run", return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="\n".join(json.dumps(event) for event in events), stderr="")) as run:
            proposal, record = native_proposal(payload)
        assert proposal == payload
        assert record["terminal_event"] == "turn.completed"
        command = run.call_args.args[0]
        assert command[:2] == ["limactl", "shell"]
        assert "--ask-for-approval on-request --sandbox read-only" in command[-1]
        assert "--approve-for-me" not in command[-1]
        assert "bypass" not in command[-1]
        assert run.call_args.kwargs["timeout"] == 200

    @pytest.mark.parametrize("name", ["claude", "codex"])
    def test_uat_runner_preserves_permissions(self, name, tmp_path):
        from fettle.runners import get_uat_runner

        with patch("fettle.runners._subprocess.run_cli", return_value=RunnerResult("", 0, 0)) as run:
            get_uat_runner(name).run("probe", tmp_path, 30)
        binary, arguments, cwd, timeout = run.call_args.args
        assert binary == name and cwd == tmp_path and timeout == 30
        assert arguments[-1] == "probe"
        assert not set(arguments) & (BYPASS_FLAGS | {
            "--dangerously-bypass-hook-trust", "--allowedTools", "--allowed-tools", "auto_edit",
        })
        if name == "codex":
            assert arguments == ["--ask-for-approval", "on-request", "exec",
                                 "--sandbox", "read-only", "probe"]
        else:
            assert arguments == ["--permission-mode", "manual", "-p", "probe"]

    @pytest.mark.parametrize("name", ["gemini", "opencode", "unknown"])
    def test_unqualified_uat_runner_is_blocked(self, name):
        from fettle.runners import get_uat_runner

        with pytest.raises(ValueError, match="permission-preserving"):
            get_uat_runner(name)

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
