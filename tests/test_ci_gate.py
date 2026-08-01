"""Tests for [gates.ci] — remote CI verification gate (Stage 8)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

from fettle import ci_gate
from fettle.dispatcher_types import HookContext, HookInput


# ── helpers ───────────────────────────────────────────────────────────────


def _git_repo(tmp_path: Path, remote: str | None = None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / "a.txt").write_text("x\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    if remote:
        subprocess.run(["git", "remote", "add", "origin", remote], cwd=repo, check=True)
    return repo


def _cfg(**ci: object) -> dict:
    base: dict = {"enabled": True, "mode": "advisory", "timeout_s": 5, "poll_s": 1}
    base.update(ci)
    return {"gates": {"ci": base}}


def _ctx(cwd: Path, config: dict, *, event: str = "Stop",
         tool: str | None = None, command: str = "") -> HookContext:
    tool_input: dict = {"command": command} if command else {}
    return HookContext(
        input=HookInput(
            hook_event_name=event, tool_name=tool, tool_input=tool_input,
            cwd=cwd, session_id="ci-test-session", raw={},
        ),
        config=config, plugin_root=cwd,
        hook_start_monotonic=0.0, global_deadline_monotonic=1e12,
    )


def _run(name: str, status: str = "completed", conclusion: str = "success") -> dict:
    return {"databaseId": 1, "workflowName": name, "status": status,
            "conclusion": conclusion, "url": f"https://x/{name}"}


# ── summarize ─────────────────────────────────────────────────────────────


class TestSummarize:
    def test_no_runs_is_not_a_pass(self) -> None:
        overall, detail = ci_gate.summarize([])
        assert overall == "no-runs"
        assert "no workflow runs" in detail

    def test_all_green(self) -> None:
        overall, _ = ci_gate.summarize([_run("CI"), _run("Docs", conclusion="skipped")])
        assert overall == "success"

    def test_any_red_names_the_run(self) -> None:
        overall, detail = ci_gate.summarize([_run("CI"), _run("Lint", conclusion="failure")])
        assert overall == "failure"
        assert "Lint" in detail

    def test_cancelled_is_not_green(self) -> None:
        overall, _ = ci_gate.summarize([_run("CI", conclusion="cancelled")])
        assert overall == "failure"

    def test_pending_reported(self) -> None:
        overall, detail = ci_gate.summarize([_run("CI", status="in_progress", conclusion="")])
        assert overall == "pending"
        assert "CI" in detail


class TestGithubRemote:
    def test_ssh_url(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path, "git@github.com:owner/name.git")
        assert ci_gate._github_repo(str(repo)) == "owner/name"

    def test_https_url_no_suffix(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path, "https://github.com/owner/name")
        assert ci_gate._github_repo(str(repo)) == "owner/name"

    def test_non_github_remote(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path, "https://gitlab.com/owner/name.git")
        assert ci_gate._github_repo(str(repo)) is None


# ── run_ci_status (minutes-world; _query_runs patched) ────────────────────


class TestRunCIStatus:
    def test_green_writes_ok_stamp(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path)
        with patch.object(ci_gate, "_query_runs", return_value=([_run("CI")], "")):
            stamp = ci_gate.run_ci_status(str(repo), _cfg())
        assert stamp["ok"] is True
        assert stamp["overall"] == "success"
        on_disk = json.loads((repo / ci_gate.STAMP_RELPATH).read_text())
        assert on_disk["sha"] == stamp["sha"] and len(stamp["sha"]) == 40

    def test_red_stamp_has_detail(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path)
        runs = [_run("CI", conclusion="failure")]
        with patch.object(ci_gate, "_query_runs", return_value=(runs, "")), \
             patch.object(ci_gate, "_ingest_failure", return_value="python3 -m pytest --tb=short"):
            stamp = ci_gate.run_ci_status(str(repo), _cfg())
        assert stamp["ok"] is False
        assert stamp["overall"] == "failure"
        assert "CI" in stamp["error"]
        assert stamp["reproduce"] == "python3 -m pytest --tb=short"

    def test_query_error_is_error_never_silent_pass(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path)
        with patch.object(ci_gate, "_query_runs", return_value=(None, "no network")):
            stamp = ci_gate.run_ci_status(str(repo), _cfg())
        assert stamp["ok"] is False
        assert stamp["overall"] == "error"
        assert "no network" in stamp["error"]

    def test_not_a_repo(self, tmp_path: Path) -> None:
        stamp = ci_gate.run_ci_status(str(tmp_path), _cfg())
        assert stamp["ok"] is False
        assert "not a git repository" in stamp["error"]

    def test_wait_polls_until_complete(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path)
        answers = iter([
            ([_run("CI", status="in_progress", conclusion="")], ""),
            ([_run("CI")], ""),
        ])
        with patch.object(ci_gate, "_query_runs", side_effect=lambda *a: next(answers)), \
             patch.object(ci_gate.time, "sleep"):
            stamp = ci_gate.run_ci_status(str(repo), _cfg(), wait=True)
        assert stamp["ok"] is True

    def test_status_does_not_poll(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path)
        pending = ([_run("CI", status="queued", conclusion="")], "")
        with patch.object(ci_gate, "_query_runs", return_value=pending) as q:
            stamp = ci_gate.run_ci_status(str(repo), _cfg(), wait=False)
        assert stamp["overall"] == "pending"
        assert q.call_count == 1

    def test_wait_reports_progress(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path)
        answers = iter([
            ([_run("CI", status="in_progress", conclusion="")], ""),
            ([_run("CI")], ""),
        ])
        lines: list[str] = []
        with patch.object(ci_gate, "_query_runs", side_effect=lambda *a: next(answers)), \
             patch.object(ci_gate.time, "sleep"):
            stamp = ci_gate.run_ci_status(
                str(repo), _cfg(), wait=True, progress=lines.append)
        assert stamp["ok"] is True
        assert len(lines) == 1
        assert "0/1 runs completed" in lines[0]

    def test_wait_grace_period_for_runs_to_appear(self, tmp_path: Path) -> None:
        # Right after a push GitHub hasn't created runs yet: wait mode must
        # keep polling through early no-runs instead of reporting no-runs.
        repo = _git_repo(tmp_path)
        answers = iter([([], ""), ([_run("CI")], "")])
        lines: list[str] = []
        with patch.object(ci_gate, "_query_runs", side_effect=lambda *a: next(answers)), \
             patch.object(ci_gate.time, "sleep"):
            stamp = ci_gate.run_ci_status(
                str(repo), _cfg(), wait=True, progress=lines.append)
        assert stamp["ok"] is True
        assert "waiting for runs to appear" in lines[0]

    def test_status_no_runs_is_immediate(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path)
        with patch.object(ci_gate, "_query_runs", return_value=([], "")) as q:
            stamp = ci_gate.run_ci_status(str(repo), _cfg(), wait=False)
        assert stamp["overall"] == "no-runs"
        assert q.call_count == 1


# ── push recorder ─────────────────────────────────────────────────────────


class TestRecordPush:
    def test_push_recorded(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path)
        state = tmp_path / "state"
        state.mkdir()
        ctx = _ctx(repo, _cfg(), event="PostToolUse", tool="Bash",
                   command="git push origin main")
        with patch("fettle.config.state_dir", return_value=state):
            result = ci_gate.record_push(ctx)
        assert result.decision.value == "allow"
        entries = [json.loads(x) for x in (state / ci_gate.PUSHES_FILENAME).read_text().splitlines()]
        assert len(entries) == 1 and len(entries[0]["sha"]) == 40

    def test_non_push_ignored(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path)
        state = tmp_path / "state"
        state.mkdir()
        ctx = _ctx(repo, _cfg(), event="PostToolUse", tool="Bash",
                   command="git status && echo push me")
        with patch("fettle.config.state_dir", return_value=state):
            ci_gate.record_push(ctx)
        assert not (state / ci_gate.PUSHES_FILENAME).exists()

    def test_disabled_gate_records_nothing(self, tmp_path: Path) -> None:
        repo = _git_repo(tmp_path)
        state = tmp_path / "state"
        state.mkdir()
        ctx = _ctx(repo, _cfg(enabled=False), event="PostToolUse", tool="Bash",
                   command="git push")
        with patch("fettle.config.state_dir", return_value=state):
            ci_gate.record_push(ctx)
        assert not (state / ci_gate.PUSHES_FILENAME).exists()


# ── Stop gate ─────────────────────────────────────────────────────────────


def _record(state: Path, sha: str, ts: float | None = None) -> None:
    (state / ci_gate.PUSHES_FILENAME).write_text(
        json.dumps({"sha": sha, "ts": ts or time.time(), "command": "git push"}) + "\n"
    )


def _stamp(repo: Path, sha: str, *, ok: bool, ts: float | None = None, **extra: object) -> None:
    path = repo / ci_gate.STAMP_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = {"ok": ok, "sha": sha, "overall": "success" if ok else "failure",
             "runs": [], "reproduce": "", "error": "", "ts": ts or time.time()}
    stamp.update(extra)
    path.write_text(json.dumps(stamp))


class TestStopGate:
    def test_disabled_allows(self, tmp_path: Path) -> None:
        assert ci_gate.run_check(_ctx(tmp_path, _cfg(enabled=False))).decision.value == "allow"

    def test_no_push_allows(self, tmp_path: Path) -> None:
        state = tmp_path / "state"
        state.mkdir()
        with patch("fettle.config.state_dir", return_value=state):
            assert ci_gate.run_check(_ctx(tmp_path, _cfg())).decision.value == "allow"

    def test_push_without_stamp_advises(self, tmp_path: Path) -> None:
        state = tmp_path / "state"
        state.mkdir()
        _record(state, "a" * 40)
        with patch("fettle.config.state_dir", return_value=state):
            result = ci_gate.run_check(_ctx(tmp_path, _cfg()))
        assert result.decision.value == "advisory"
        assert "fettle ci wait" in result.message

    def test_push_without_stamp_enforce_blocks(self, tmp_path: Path) -> None:
        state = tmp_path / "state"
        state.mkdir()
        _record(state, "a" * 40)
        with patch("fettle.config.state_dir", return_value=state):
            result = ci_gate.run_check(_ctx(tmp_path, _cfg(mode="enforce")))
        assert result.decision.value == "block"

    def test_fresh_green_stamp_allows(self, tmp_path: Path) -> None:
        state = tmp_path / "state"
        state.mkdir()
        _record(state, "a" * 40, ts=time.time() - 60)
        _stamp(tmp_path, "a" * 40, ok=True)
        with patch("fettle.config.state_dir", return_value=state):
            assert ci_gate.run_check(_ctx(tmp_path, _cfg())).decision.value == "allow"

    def test_stamp_for_other_commit_is_stale(self, tmp_path: Path) -> None:
        state = tmp_path / "state"
        state.mkdir()
        _record(state, "a" * 40)
        _stamp(tmp_path, "b" * 40, ok=True)
        with patch("fettle.config.state_dir", return_value=state):
            result = ci_gate.run_check(_ctx(tmp_path, _cfg()))
        assert result.decision.value == "advisory"
        assert "different commit" in result.message

    def test_stamp_older_than_push_is_stale(self, tmp_path: Path) -> None:
        state = tmp_path / "state"
        state.mkdir()
        _stamp(tmp_path, "a" * 40, ok=True, ts=time.time() - 3600)
        _record(state, "a" * 40)
        with patch("fettle.config.state_dir", return_value=state):
            result = ci_gate.run_check(_ctx(tmp_path, _cfg()))
        assert result.decision.value == "advisory"
        assert "stale" in result.message

    def test_red_stamp_carries_detail_and_reproduce(self, tmp_path: Path) -> None:
        state = tmp_path / "state"
        state.mkdir()
        _record(state, "a" * 40, ts=time.time() - 60)
        _stamp(tmp_path, "a" * 40, ok=False,
               error="CI: failure (https://x/CI)", reproduce="python3 -m pytest")
        with patch("fettle.config.state_dir", return_value=state):
            result = ci_gate.run_check(_ctx(tmp_path, _cfg()))
        assert result.decision.value == "advisory"
        assert "https://x/CI" in result.message
        assert "python3 -m pytest" in result.message

    def test_corrupt_stamp_is_a_problem_not_a_pass(self, tmp_path: Path) -> None:
        state = tmp_path / "state"
        state.mkdir()
        _record(state, "a" * 40)
        path = tmp_path / ci_gate.STAMP_RELPATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{nope")
        with patch("fettle.config.state_dir", return_value=state):
            result = ci_gate.run_check(_ctx(tmp_path, _cfg()))
        assert result.decision.value == "advisory"
        assert "unreadable" in result.message


# ── registry + CLI wiring ─────────────────────────────────────────────────


class TestRegistryAndCLI:
    def test_registry_pins(self) -> None:
        from fettle.dispatcher_registry import CHECKS
        by_name = {c.name: c for c in CHECKS}
        rec = by_name["ci_push_record"]
        assert rec.events == frozenset({"PostToolUse"})
        assert rec.tools == frozenset({"Bash"})
        assert rec.budget_ms <= 100
        gate = by_name["ci_gate"]
        assert gate.events == frozenset({"Stop"})
        assert gate.budget_ms <= 100

    def test_cli_wait_green_exit_0(self, tmp_path: Path, monkeypatch, capsys) -> None:
        repo = _git_repo(tmp_path)
        monkeypatch.chdir(repo)
        from fettle import cli
        args = argparse.Namespace(ci_action="wait", sha=None, json=True, root=".")
        with patch.object(ci_gate, "_query_runs", return_value=([_run("CI")], "")):
            try:
                cli.cmd_ci(args)
            except SystemExit as e:
                assert e.code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["ok"] is True

    def test_cli_status_red_exit_1(self, tmp_path: Path, monkeypatch, capsys) -> None:
        repo = _git_repo(tmp_path)
        monkeypatch.chdir(repo)
        from fettle import cli
        args = argparse.Namespace(ci_action="status", sha=None, json=False, root=".")
        runs = [_run("CI", conclusion="failure")]
        with patch.object(ci_gate, "_query_runs", return_value=(runs, "")), \
             patch.object(ci_gate, "_ingest_failure", return_value=""):
            try:
                cli.cmd_ci(args)
            except SystemExit as e:
                assert e.code == 1
        assert "✗" in capsys.readouterr().out

    def test_cli_status_query_error_exit_2(self, tmp_path: Path, monkeypatch) -> None:
        repo = _git_repo(tmp_path)
        monkeypatch.chdir(repo)
        from fettle import cli
        args = argparse.Namespace(ci_action="status", sha=None, json=False, root=".")
        with patch.object(ci_gate, "_query_runs", return_value=(None, "boom")):
            try:
                cli.cmd_ci(args)
            except SystemExit as e:
                assert e.code == 2

    def test_cli_help_lists_actions(self) -> None:
        r = subprocess.run(
            [sys.executable, "-m", "fettle.cli", "ci", "--help"],
            capture_output=True, text=True,
        )
        assert "status" in r.stdout and "wait" in r.stdout
