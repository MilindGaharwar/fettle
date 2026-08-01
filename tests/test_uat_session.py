"""Tests for fettle.uat.session (Stage 5, S5.2)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from fettle.runners import RunnerResult
from fettle.uat.session import (
    build_prompt,
    collect_scenarios,
    load_checkpoint,
    run_session,
)

SPEC = """\
---
fettle-spec: v1
id: greeter
status: active
scope:
  - "src/**"
---

## Requirements

- R1. Greets the user by name.

## Scenarios

### S1. Basic greeting (traces R1)

- Given the app is installed
- When the user runs `greet Ada`
- Then the output contains "Hello, Ada"
"""


def _git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path,
                   capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path,
                   capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path,
                   capture_output=True, check=True)
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = \"x\"\n\n[project.scripts]\ngreet = \"x:main\"\n")
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "greeter.md").write_text(SPEC)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path,
                   capture_output=True, check=True)
    return tmp_path


def _cfg() -> dict:
    return {
        "uat": {"surfaces": ["auto"], "app_url": "", "start_command": "",
                "runner": "claude", "timeout_s": 1800, "mode": "report"},
        "worktrees": {"root": ".fettle/worktrees"},
    }


class FakeRunner:
    name = "fake"

    def __init__(self, transcript="SCENARIO: greeter/S1\nOUTCOME: matches", error=""):
        self.transcript, self.error = transcript, error
        self.calls: list[dict] = []

    def run(self, prompt, cwd, timeout_s=600):
        self.calls.append({"prompt": prompt, "cwd": cwd, "timeout_s": timeout_s})
        return RunnerResult(transcript=self.transcript, exit_code=0,
                            duration_s=0.1, error=self.error)


class TestScenariosAndPrompt:
    def test_collect_scenarios_active_only(self, tmp_path):
        repo = _git_repo(tmp_path)
        (repo / "specs" / "draft.md").write_text(
            SPEC.replace("id: greeter", "id: draft-one")
                .replace("status: active", "status: draft"))
        scenarios = collect_scenarios(str(repo))
        assert [s["id"] for s in scenarios] == ["greeter/S1"]
        assert "When the user runs `greet Ada`" in scenarios[0]["steps"]
        assert scenarios[0]["requirements"] == ["Greets the user by name."]

    def test_prompt_contains_persona_and_steps(self, tmp_path):
        repo = _git_repo(tmp_path)
        prompt = build_prompt("cli", collect_scenarios(str(repo)), _cfg()["uat"])
        assert "first-time user" in prompt
        assert "do not read source code" in prompt
        assert "greeter/S1" in prompt
        assert 'Then the output contains "Hello, Ada"' in prompt
        assert "could-not-attempt" in prompt  # honest-failure channel

    def test_prompt_access_from_app_url(self):
        cfg = {"app_url": "http://localhost:8000"}
        assert "http://localhost:8000" in build_prompt("api", [], cfg)

    def test_prompt_access_from_start_command(self):
        cfg = {"start_command": "npm run dev"}
        assert "npm run dev" in build_prompt("api", [], cfg)


class TestRunSession:
    def _run(self, repo, runner=None, surface="cli"):
        with patch("fettle.runners.claude.shutil.which",
                   return_value="/usr/bin/claude"):
            return run_session(str(repo), _cfg(), surface,
                               runner=runner or FakeRunner())

    def test_happy_path(self, tmp_path):
        repo = _git_repo(tmp_path)
        runner = FakeRunner()
        result = self._run(repo, runner)
        assert result.status == "completed", result.error
        assert result.scenario_ids == ["greeter/S1"]
        assert Path(result.worktree).is_dir()
        assert "greeter/S1" in runner.calls[0]["prompt"]
        assert runner.calls[0]["cwd"] == result.worktree
        transcript = Path(result.transcript_path).read_text()
        assert "OUTCOME: matches" in transcript

    def test_checkpoint_written_and_resumable(self, tmp_path):
        repo = _git_repo(tmp_path)
        result = self._run(repo)
        cp = load_checkpoint(result.worktree)
        assert cp["status"] == "completed"
        assert cp["session_id"] == result.session_id
        assert cp["transcript"] == result.transcript_path

    def test_worktree_is_claimed(self, tmp_path):
        from fettle.work_items import claim_for_worktree
        repo = _git_repo(tmp_path)
        result = self._run(repo)
        assert claim_for_worktree(str(repo), result.worktree) == result.session_id

    def test_runner_error_surfaces(self, tmp_path):
        repo = _git_repo(tmp_path)
        result = self._run(repo, FakeRunner(transcript="partial",
                                            error="runner timed out after 1800s"))
        assert result.status == "timeout"
        assert "timed out" in result.error
        assert load_checkpoint(result.worktree)["status"] == "timeout"

    def test_undrivable_surface_names_doctor(self, tmp_path):
        repo = _git_repo(tmp_path)
        result = self._run(repo, surface="web")
        assert result.status == "error"
        assert "not drivable" in result.error and "uat doctor" in result.error

    def test_capability_gap_blocks(self, tmp_path):
        repo = _git_repo(tmp_path)
        with patch("fettle.runners.claude.shutil.which", return_value=None):
            result = run_session(str(repo), _cfg(), "cli", runner=FakeRunner())
        assert result.status == "error"
        assert "capability gap" in result.error

    def test_no_scenarios_blocks(self, tmp_path):
        repo = _git_repo(tmp_path)
        (repo / "specs" / "greeter.md").unlink()
        result = self._run(repo)
        assert result.status == "error"
        assert "no active spec scenarios" in result.error


class TestCLI:
    def test_uat_run_json_with_gap(self, tmp_path):
        import json as _json
        repo = _git_repo(tmp_path)
        r = subprocess.run(
            [sys.executable, "-m", "fettle.cli", "uat", "run",
             "--surface", "web", "--json"],
            cwd=repo, capture_output=True, text=True)
        assert r.returncode == 1
        data = _json.loads(r.stdout)
        assert data["status"] == "error"
        assert "not drivable" in data["error"]
