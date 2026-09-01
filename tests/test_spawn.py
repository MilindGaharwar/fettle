"""Tests for fettle.spawn — governed child-agent launch (WP-157, A4)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fettle.policy_capsule import ENV_VAR, write_capsule
from fettle.runners import RUNNER_NAMES, RunnerResult
from fettle.spawn import spawn_agent


class FakeRunner:
    """Records the env the child would inherit at launch time."""

    name = "fake"

    def __init__(self, *, available: bool = True, exit_code: int = 0):
        self._available = available
        self._exit_code = exit_code
        self.calls: list[dict] = []

    def available(self) -> bool:
        return self._available

    def run(self, prompt: str, cwd: Path, timeout_s: int = 600) -> RunnerResult:
        self.calls.append({
            "prompt": prompt,
            "cwd": str(cwd),
            "timeout_s": timeout_s,
            "capsule_env": os.environ.get(ENV_VAR, ""),
            "parent_env": os.environ.get("FETTLE_PARENT_SESSION", ""),
        })
        return RunnerResult("child transcript", self._exit_code, 0.1)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.delenv("FETTLE_PARENT_SESSION", raising=False)
    monkeypatch.delenv("FETTLE_GATE_MODE", raising=False)
    return tmp_path


@pytest.fixture
def repo(env):
    repo = env / "repo"
    repo.mkdir()
    (repo / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    return repo


def _git_repo(env) -> Path:
    repo = env / "gitrepo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@fettle.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


class TestGovernedRun:
    """2026-08 audit: UAT/evals launches must export capsule lineage too."""

    def test_exports_capsule_env_and_restores(self, repo) -> None:
        from fettle.spawn import governed_run

        runner = FakeRunner()
        result = governed_run(runner, "probe the app", str(repo), 60)

        assert result.transcript == "child transcript"
        call = runner.calls[0]
        assert call["capsule_env"], "child saw no FETTLE_POLICY_CAPSULE"
        assert Path(call["capsule_env"]).is_file()
        assert call["parent_env"]
        assert os.environ.get(ENV_VAR) is None  # restored

    def test_provisioning_failure_launches_ungoverned_but_traced(
        self, repo, monkeypatch,
    ) -> None:
        from fettle import spawn as spawn_module

        traced: list[dict] = []
        monkeypatch.setattr(
            "fettle.trace.log_decision",
            lambda *a, **k: traced.append({"args": a, "kwargs": k}),
        )
        monkeypatch.setattr(
            "fettle.policy_capsule.write_capsule",
            lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
        )
        runner = FakeRunner()

        result = spawn_module.governed_run(runner, "probe", str(repo), 60)

        assert result.transcript == "child transcript"  # still launched
        assert runner.calls[0]["capsule_env"] == ""     # ungoverned
        assert traced, "ungoverned launch left no trace"
        assert traced[0]["kwargs"]["findings"][0]["code"] == "UNGOVERNED_LAUNCH"


class TestSpawnAgent:
    def test_child_inherits_capsule_and_parent_session(self, repo) -> None:
        runner = FakeRunner()
        result = spawn_agent("fake", "do the task", str(repo), runner=runner)
        assert result.error == ""
        call = runner.calls[0]
        assert call["capsule_env"] == result.capsule_path
        assert call["parent_env"] == result.session_id
        assert call["prompt"] == "do the task"
        # The capsule carries the repo's effective policy.
        doc = json.loads(Path(result.capsule_path).read_text())
        assert doc["policy"]["gates"]["lint"]["mode"] == "enforce"
        assert doc["lineage"] == []

    def test_env_restored_after_launch(self, repo) -> None:
        spawn_agent("fake", "t", str(repo), runner=FakeRunner())
        assert ENV_VAR not in os.environ
        assert "FETTLE_PARENT_SESSION" not in os.environ

    def test_chained_lineage(self, repo, monkeypatch) -> None:
        parent = write_capsule(
            {"gates": {"lint": {"mode": "enforce"}}},
            {"session_id": "grandparent"},
        )
        monkeypatch.setenv(ENV_VAR, str(parent))
        result = spawn_agent("fake", "t", str(repo), runner=FakeRunner())
        assert result.error == ""
        assert result.lineage == [parent.stem]
        doc = json.loads(Path(result.capsule_path).read_text())
        assert doc["lineage"] == [parent.stem]

    def test_refuses_tampered_parent_capsule(self, repo, monkeypatch) -> None:
        parent = write_capsule({"gates": {}}, {"session_id": "p"})
        doc = json.loads(parent.read_text())
        doc["policy"] = {"gates": {"lint": {"mode": "silent"}}}
        parent.write_text(json.dumps(doc))
        monkeypatch.setenv(ENV_VAR, str(parent))
        result = spawn_agent("fake", "t", str(repo), runner=FakeRunner())
        assert "unverifiable capsule" in result.error

    def test_worktree_provisioned_claimed_and_used_as_cwd(self, env) -> None:
        repo = _git_repo(env)
        runner = FakeRunner()
        result = spawn_agent("fake", "t", str(repo),
                             worktree_item="item-x", runner=runner)
        assert result.error == ""
        assert "item-x" in result.child_cwd
        assert runner.calls[0]["cwd"] == result.child_cwd
        assert Path(result.child_cwd).is_dir()
        from fettle.work_items import claim_for_worktree
        assert claim_for_worktree(str(repo), result.child_cwd) == "item-x"

    def test_runner_unavailable(self, repo) -> None:
        result = spawn_agent("fake", "t", str(repo),
                             runner=FakeRunner(available=False))
        assert "not available" in result.error

    def test_not_a_repo(self, env) -> None:
        bare = env / "bare"
        bare.mkdir()
        result = spawn_agent("fake", "t", str(bare), runner=FakeRunner())
        assert "not inside a repository" in result.error

    def test_spawn_logged_to_trace(self, repo) -> None:
        result = spawn_agent("fake", "t", str(repo), runner=FakeRunner())
        trace = Path(os.environ["XDG_STATE_HOME"]) / "fettle" / "trace.jsonl"
        entries = [json.loads(line) for line in trace.read_text().splitlines()]
        spawn_entries = [e for e in entries if e["hook"] == "spawn"]
        assert spawn_entries
        finding = spawn_entries[-1]["findings"][0]
        assert finding["capsule"] == result.capsule_digest
        assert spawn_entries[-1]["session_id"] == result.session_id

    def test_child_failure_surfaces(self, repo) -> None:
        result = spawn_agent("fake", "t", str(repo),
                             runner=FakeRunner(exit_code=3))
        assert result.error == ""
        assert result.run.exit_code == 3


class TestCliContract:
    def test_cli_runner_choices_match_registry(self) -> None:
        # cli.py hardcodes choices (lazy-import discipline) — pin the set.
        import inspect

        from fettle import cli
        src = inspect.getsource(cli.main)
        for name in RUNNER_NAMES:
            assert f'"{name}"' in src

    def test_spawn_help_exits_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "fettle.cli", "spawn", "--help"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "--worktree" in proc.stdout
