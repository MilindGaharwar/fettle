"""Tests for fettle/verify_gate.py — [gates.verify] verification gate (S7.1).

The `fettle verify` runner is exercised against tiny real projects in
tmp_path using a fast custom test_command (no nested pytest for the
happy paths); one integration test runs real pytest end to end.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

from fettle.dispatcher_types import Decision, HookContext, HookInput
from fettle.verify_gate import STAMP_RELPATH, impacted_tests, run_check, run_verify

CLI = [sys.executable, "-m", "fettle.cli"]


def _project(tmp_path: Path, test_command: str) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".fettle.toml").write_text(
        f'[profile]\ntest_command = "{test_command}"\n'
    )
    return tmp_path


def _cfg(**tests) -> dict:
    base = {"enabled": True, "mode": "advisory", "scope": "impacted",
            "timeout_s": 30, "parallel": False}
    base.update(tests)
    return {"gates": {"verify": base}}


def _write_edits(state: Path, files: list[str]) -> Path:
    state.mkdir(parents=True, exist_ok=True)
    edits = state / "edits.jsonl"
    with open(edits, "w") as fh:
        for f in files:
            fh.write(json.dumps({"file": f, "ts": time.time(),
                                 "tool": "Edit", "tested": False}) + "\n")
    return edits


class TestImpactedMapping:
    def test_impl_file_maps_to_convention_tests(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_widget.py").write_text("")
        hits = impacted_tests(str(tmp_path), [str(tmp_path / "pkg_widget/../widget.py")],
                              ["tests"])
        assert hits == ["tests/test_widget.py"]

    def test_edited_test_file_maps_to_itself(self, tmp_path):
        hits = impacted_tests(str(tmp_path), [str(tmp_path / "tests" / "test_x.py")],
                              ["tests"])
        assert hits == ["tests/test_x.py"]

    def test_suffix_convention(self, tmp_path):
        (tmp_path / "spec").mkdir()
        (tmp_path / "spec" / "widget_test.py").write_text("")
        hits = impacted_tests(str(tmp_path), [str(tmp_path / "widget.py")], ["spec"])
        assert hits == ["spec/widget_test.py"]

    def test_outside_project_ignored(self, tmp_path):
        assert impacted_tests(str(tmp_path / "repo"), ["/elsewhere/x.py"], ["tests"]) == []

    def test_no_match_returns_empty(self, tmp_path):
        (tmp_path / "tests").mkdir()
        assert impacted_tests(str(tmp_path), [str(tmp_path / "orphan.py")], ["tests"]) == []


class TestRunVerify:
    def test_green_run_writes_ok_stamp(self, tmp_path):
        repo = _project(tmp_path, f"{sys.executable} -c pass")
        stamp = run_verify(str(repo), _cfg())
        assert stamp["ok"] and stamp["exit_code"] == 0
        assert stamp["evidence_id"].startswith("ev-")
        on_disk = json.loads((repo / STAMP_RELPATH).read_text())
        assert on_disk["ok"] is True

    def test_red_run_records_failure_tail(self, tmp_path):
        repo = _project(
            tmp_path, f"{sys.executable} -c \\\"import sys; print('boom'); sys.exit(1)\\\"")
        stamp = run_verify(str(repo), _cfg())
        assert not stamp["ok"] and stamp["exit_code"] == 1
        assert "boom" in stamp["error"]

    def test_timeout_is_visible_not_silent(self, tmp_path):
        repo = _project(
            tmp_path, f"{sys.executable} -c \\\"import time; time.sleep(5)\\\"")
        stamp = run_verify(str(repo), _cfg(timeout_s=1))
        assert not stamp["ok"]
        assert "timeout" in stamp["error"]

    def test_no_command_discovered(self, tmp_path):
        (tmp_path / ".git").mkdir()
        stamp = run_verify(str(tmp_path), _cfg())
        assert not stamp["ok"] and stamp["command"] == ""
        assert "test_command" in stamp["error"]

    def test_missing_binary_lands_in_error(self, tmp_path):
        repo = _project(tmp_path, "definitely-not-a-real-binary-xyz")
        stamp = run_verify(str(repo), _cfg())
        assert not stamp["ok"]
        assert "could not launch" in stamp["error"]

    def test_impacted_scoping_with_real_pytest(self, tmp_path):
        """End-to-end: edited impl file scopes the run to its test file."""
        from fettle.test_discovery import TestConfig
        repo = tmp_path
        (repo / ".git").mkdir()
        (repo / "widget.py").write_text("def double(x):\n    return x * 2\n")
        tests_dir = repo / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_widget.py").write_text(
            "import os, sys\n"
            "sys.path.insert(0, os.getcwd())\n"
            "from widget import double\n\n"
            "def test_double():\n    assert double(2) == 4\n")
        (tests_dir / "test_other.py").write_text(
            "def test_always_red():\n    assert False\n")
        state = tmp_path / "state" / "sess-1"
        _write_edits(state, [str(repo / "widget.py")])
        tc = TestConfig(framework="pytest",
                        command=f"{sys.executable} -m pytest tests/",
                        test_roots=["tests"])
        with (patch("fettle.config.state_dir", return_value=state),
              patch("fettle.verify_gate.discover_test_config", return_value=tc)):
            stamp = run_verify(str(repo), _cfg(timeout_s=120), session_id="sess-1")
        assert stamp["scope"] == "impacted"
        assert stamp["impacted"] == ["tests/test_widget.py"]
        assert stamp["ok"], stamp["error"]  # red test_other.py NOT in scope

    def test_full_flag_ignores_scoping(self, tmp_path):
        repo = _project(tmp_path, f"{sys.executable} -c pass")
        stamp = run_verify(str(repo), _cfg(), full=True)
        assert stamp["scope"] == "full"

    def test_mixed_repo_runs_only_affected_workspaces(self, tmp_path):
        py = tmp_path / "services" / "api"
        web = tmp_path / "apps" / "web"
        untouched = tmp_path / "tools" / "worker"
        for directory in (py, web, untouched):
            directory.mkdir(parents=True)
        (py / "pyproject.toml").write_text('[project]\nname="api"\n')
        (py / "tests").mkdir()
        (web / "package.json").write_text('{"name":"web","scripts":{"test":"vitest run"}}')
        (untouched / "go.mod").write_text("module example.test/worker\n")
        py_file = py / "app.py"
        web_file = web / "app.ts"
        py_file.write_text("x = 1")
        web_file.write_text("const x = 1")
        state = tmp_path / "state" / "sess-mixed"
        _write_edits(state, [str(py_file), str(web_file)])

        completed = subprocess.CompletedProcess([], 0, "", "")
        with (patch("fettle.config.state_dir", return_value=state),
              patch("fettle.verify_gate.subprocess.run", return_value=completed) as invoke):
            stamp = run_verify(str(tmp_path), _cfg(), session_id="sess-mixed")

        assert stamp["ok"] is True
        assert [record["path"] for record in stamp["workspaces"]] == ["apps/web", "services/api"]
        assert [call.kwargs["cwd"] for call in invoke.call_args_list if call.args[0][0] != "git"] == [
            str(web), str(py),
        ]
        assert all(record["dirty_digest"] for record in stamp["workspaces"])

    def test_mixed_repo_failure_is_visible_per_workspace(self, tmp_path):
        for path, marker, content in (
            ("api", "pyproject.toml", '[project]\nname="api"\n'),
            ("web", "package.json", '{"name":"web"}'),
        ):
            root = tmp_path / path
            root.mkdir()
            (root / marker).write_text(content)
            (root / ("app.py" if path == "api" else "app.ts")).write_text("")
            if path == "api":
                (root / "tests").mkdir()
        state = tmp_path / "state" / "sess-mixed"
        _write_edits(state, [str(tmp_path / "api" / "app.py"), str(tmp_path / "web" / "app.ts")])
        results = [
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 2, "", "web failed"),
        ]

        def run_command(argv, **kwargs):
            if argv[0] == "git":
                return subprocess.CompletedProcess(argv, 0, "", "")
            return results.pop(0)

        with (patch("fettle.config.state_dir", return_value=state),
              patch("fettle.verify_gate.subprocess.run", side_effect=run_command)):
            stamp = run_verify(str(tmp_path), _cfg(), session_id="sess-mixed")

        assert stamp["ok"] is False
        assert stamp["exit_code"] == 2
        assert stamp["workspaces"][1]["error"] == "web failed"

    def test_one_affected_nested_workspace_runs_from_its_root(self, tmp_path):
        api = tmp_path / "services" / "api"
        web = tmp_path / "apps" / "web"
        api.mkdir(parents=True)
        web.mkdir(parents=True)
        (api / "pyproject.toml").write_text('[project]\nname="api"\n')
        (api / "tests").mkdir()
        source = api / "app.py"
        source.write_text("")
        (web / "package.json").write_text('{"name":"web"}')
        state = tmp_path / "state" / "sess-one"
        _write_edits(state, [str(source)])
        completed = subprocess.CompletedProcess([], 0, "", "")
        with (patch("fettle.config.state_dir", return_value=state),
              patch("fettle.verify_gate.subprocess.run", return_value=completed) as invoke):
            stamp = run_verify(str(tmp_path), _cfg(), session_id="sess-one")
        test_calls = [call for call in invoke.call_args_list if call.args[0][0] != "git"]
        assert test_calls[0].kwargs["cwd"] == str(api)
        assert stamp["workspaces"][0]["path"] == "services/api"

    def test_deleted_file_still_routes_to_affected_workspace(self, tmp_path):
        api = tmp_path / "services" / "api"
        api.mkdir(parents=True)
        (api / "pyproject.toml").write_text('[project]\nname="api"\n')
        (api / "tests").mkdir()
        deleted = api / "widget.py"
        state = tmp_path / "state" / "sess-deleted"
        _write_edits(state, [str(deleted)])
        completed = subprocess.CompletedProcess([], 0, "", "")

        with (patch("fettle.config.state_dir", return_value=state),
              patch("fettle.verify_gate.subprocess.run", return_value=completed) as invoke):
            stamp = run_verify(str(tmp_path), _cfg(), session_id="sess-deleted")

        test_calls = [call for call in invoke.call_args_list if call.args[0][0] != "git"]
        assert test_calls[0].kwargs["cwd"] == str(api)
        assert stamp["workspaces"][0]["edited"] == ["services/api/widget.py"]

    def test_nested_python_workspace_runs_impacted_tests(self, tmp_path):
        api = tmp_path / "services" / "api"
        tests = api / "tests"
        tests.mkdir(parents=True)
        (api / "pyproject.toml").write_text('[project]\nname="api"\n')
        source = api / "widget.py"
        source.write_text("x = 1\n")
        (tests / "test_widget.py").write_text("def test_widget(): assert True\n")
        (tests / "test_other.py").write_text("def test_other(): assert True\n")
        state = tmp_path / "state" / "sess-impacted"
        _write_edits(state, [str(source)])
        completed = subprocess.CompletedProcess([], 0, "", "")

        with (patch("fettle.config.state_dir", return_value=state),
              patch("fettle.verify_gate.subprocess.run", return_value=completed) as invoke):
            stamp = run_verify(str(tmp_path), _cfg(), session_id="sess-impacted")

        test_call = next(call for call in invoke.call_args_list if call.args[0][0] != "git")
        assert "tests/test_widget.py" in test_call.args[0]
        assert "tests/test_other.py" not in test_call.args[0]
        assert stamp["workspaces"][0]["scope"] == "impacted"
        assert stamp["workspaces"][0]["impacted"] == ["tests/test_widget.py"]

    def test_workspace_impacted_tests_preserve_pytest_flags(self, tmp_path):
        api = tmp_path / "services" / "api"
        tests = api / "tests"
        tests.mkdir(parents=True)
        (api / "pyproject.toml").write_text('[project]\nname="api"\n')
        source = api / "widget.py"
        source.write_text("x = 1\n")
        (tests / "test_widget.py").write_text("def test_widget(): assert True\n")
        state = tmp_path / "state" / "sess-flags"
        _write_edits(state, [str(source)])
        completed = subprocess.CompletedProcess([], 0, "", "")

        with (patch("fettle.config.state_dir", return_value=state),
              patch("fettle.verify_gate.detect_profile") as detect,
              patch("fettle.verify_gate.subprocess.run", return_value=completed) as invoke):
            from fettle.workspace import Workspace

            detect.return_value.workspaces = [Workspace(
                name="api", path="services/api", language="python",
                marker="pyproject.toml", test_command="python -m pytest tests --cov=src",
                test_roots=["tests"],
            )]
            stamp = run_verify(str(tmp_path), _cfg(), session_id="sess-flags")

        test_call = next(call for call in invoke.call_args_list if call.args[0][0] != "git")
        assert "--cov=src" in test_call.args[0]
        assert stamp["workspaces"][0]["command"].endswith("tests/test_widget.py")


def _gate_ctx(cwd: Path, config: dict) -> HookContext:
    hook_input = HookInput(
        hook_event_name="Stop", tool_name=None, tool_input={},
        cwd=cwd, session_id="sess-g", raw={},
    )
    return HookContext(
        input=hook_input, config=config,
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0, global_deadline_monotonic=999999.0,
    )


class TestStopGate:
    def test_disabled_allows(self, tmp_path):
        ctx = _gate_ctx(tmp_path, _cfg(enabled=False))
        assert run_check(ctx).decision == Decision.ALLOW

    def test_no_edits_allows(self, tmp_path):
        state = tmp_path / "state" / "sess-g"
        with patch("fettle.config.state_dir", return_value=state):
            assert run_check(_gate_ctx(tmp_path, _cfg())).decision == Decision.ALLOW

    def test_docs_only_session_allows(self, tmp_path):
        doc = tmp_path / "README.md"
        doc.write_text("x")
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(doc)])
        with patch("fettle.config.state_dir", return_value=state):
            assert run_check(_gate_ctx(tmp_path, _cfg())).decision == Decision.ALLOW

    def test_deleted_code_still_requires_verification(self, tmp_path):
        deleted = tmp_path / "removed.py"
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(deleted)])
        with patch("fettle.config.state_dir", return_value=state):
            result = run_check(_gate_ctx(tmp_path, _cfg()))
        assert result.decision == Decision.ADVISORY
        assert "fettle verify" in result.message

    def test_missing_stamp_advisory_with_command(self, tmp_path):
        src = tmp_path / "src.py"
        src.write_text("x = 1\n")
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(src)])
        with patch("fettle.config.state_dir", return_value=state):
            result = run_check(_gate_ctx(tmp_path, _cfg()))
        assert result.decision == Decision.ADVISORY
        assert "fettle verify" in result.message

    def test_enforce_blocks(self, tmp_path):
        src = tmp_path / "src.py"
        src.write_text("x = 1\n")
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(src)])
        with patch("fettle.config.state_dir", return_value=state):
            result = run_check(_gate_ctx(tmp_path, _cfg(mode="enforce")))
        assert result.decision == Decision.BLOCK

    def test_fresh_green_stamp_allows(self, tmp_path):
        src = tmp_path / "src.py"
        src.write_text("x = 1\n")
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(src)])
        stamp = tmp_path / STAMP_RELPATH
        stamp.parent.mkdir(parents=True)
        stamp.write_text(json.dumps({"ok": True, "session_id": "sess-g",
                                     "scope": "full"}))
        with patch("fettle.config.state_dir", return_value=state):
            assert run_check(_gate_ctx(tmp_path, _cfg())).decision == Decision.ALLOW

    def test_stale_stamp_advisory(self, tmp_path):
        src = tmp_path / "src.py"
        src.write_text("x = 1\n")
        stamp = tmp_path / STAMP_RELPATH
        stamp.parent.mkdir(parents=True)
        stamp.write_text(json.dumps({"ok": True, "session_id": "sess-g",
                                     "scope": "full"}))
        state = tmp_path / "state" / "sess-g"
        edits = _write_edits(state, [str(src)])  # written AFTER the stamp
        past = time.time() - 60
        import os
        os.utime(stamp, (past, past))
        os.utime(edits)  # now
        with patch("fettle.config.state_dir", return_value=state):
            result = run_check(_gate_ctx(tmp_path, _cfg()))
        assert result.decision == Decision.ADVISORY
        assert "stale" in result.message

    def test_red_stamp_surfaces_detail(self, tmp_path):
        src = tmp_path / "src.py"
        src.write_text("x = 1\n")
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(src)])
        stamp = tmp_path / STAMP_RELPATH
        stamp.parent.mkdir(parents=True)
        stamp.write_text(json.dumps({"ok": False, "error": "2 failed",
                                     "session_id": "sess-g", "scope": "full"}))
        with patch("fettle.config.state_dir", return_value=state):
            result = run_check(_gate_ctx(tmp_path, _cfg()))
        assert result.decision == Decision.ADVISORY
        assert "2 failed" in result.message

    def test_corrupt_stamp_advisory(self, tmp_path):
        src = tmp_path / "src.py"
        src.write_text("x = 1\n")
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(src)])
        stamp = tmp_path / STAMP_RELPATH
        stamp.parent.mkdir(parents=True)
        stamp.write_text("{not json")
        with patch("fettle.config.state_dir", return_value=state):
            result = run_check(_gate_ctx(tmp_path, _cfg()))
        assert result.decision == Decision.ADVISORY
        assert "unreadable" in result.message

    # --- WP-7 (audit M-04): stamp binding ---

    def test_cross_session_stamp_rejected(self, tmp_path):
        src = tmp_path / "src.py"
        src.write_text("x = 1\n")
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(src)])
        stamp = tmp_path / STAMP_RELPATH
        stamp.parent.mkdir(parents=True)
        stamp.write_text(json.dumps({"ok": True, "session_id": "sess-OTHER",
                                     "scope": "full"}))
        with patch("fettle.config.state_dir", return_value=state):
            result = run_check(_gate_ctx(tmp_path, _cfg()))
        assert result.decision == Decision.ADVISORY
        assert "another session" in result.message

    def test_legacy_stamp_without_session_rejected(self, tmp_path):
        """A hand-written or pre-WP-7 stamp proves nothing — fail closed."""
        src = tmp_path / "src.py"
        src.write_text("x = 1\n")
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(src)])
        stamp = tmp_path / STAMP_RELPATH
        stamp.parent.mkdir(parents=True)
        stamp.write_text(json.dumps({"ok": True}))
        with patch("fettle.config.state_dir", return_value=state):
            result = run_check(_gate_ctx(tmp_path, _cfg()))
        assert result.decision == Decision.ADVISORY
        assert "another session" in result.message

    def test_impacted_stamp_not_covering_edits_rejected(self, tmp_path):
        """Edited file maps to a test the impacted run never executed."""
        src = tmp_path / "widget.py"
        src.write_text("x = 1\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_widget.py").write_text("")
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(src)])
        stamp = tmp_path / STAMP_RELPATH
        stamp.parent.mkdir(parents=True)
        stamp.write_text(json.dumps({
            "ok": True, "session_id": "sess-g", "scope": "impacted",
            "impacted": ["tests/test_unrelated.py"],
        }))
        from fettle.test_discovery import TestConfig
        tc = TestConfig(framework="pytest", command="pytest tests/",
                        test_roots=["tests"])
        with (patch("fettle.config.state_dir", return_value=state),
              patch("fettle.verify_gate.discover_test_config", return_value=tc)):
            result = run_check(_gate_ctx(tmp_path, _cfg()))
        assert result.decision == Decision.ADVISORY
        assert "did not cover" in result.message

    def test_impacted_stamp_covering_edits_allows(self, tmp_path):
        src = tmp_path / "widget.py"
        src.write_text("x = 1\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_widget.py").write_text("")
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(src)])
        stamp = tmp_path / STAMP_RELPATH
        stamp.parent.mkdir(parents=True)
        stamp.write_text(json.dumps({
            "ok": True, "session_id": "sess-g", "scope": "impacted",
            "impacted": ["tests/test_widget.py"],
        }))
        from fettle.test_discovery import TestConfig
        tc = TestConfig(framework="pytest", command="pytest tests/",
                        test_roots=["tests"])
        with (patch("fettle.config.state_dir", return_value=state),
              patch("fettle.verify_gate.discover_test_config", return_value=tc)):
            assert run_check(_gate_ctx(tmp_path, _cfg())).decision == Decision.ALLOW

    def test_mtime_stale_stamp_redeemed_by_matching_tree(self, tmp_path):
        """Stamp older than edits but git tree identical to verify time — fresh."""
        import subprocess as sp
        sp.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        sp.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
        sp.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
        src = tmp_path / "src.py"
        src.write_text("x = 1\n")
        sp.run(["git", "add", "."], cwd=tmp_path, check=True)
        sp.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
        from fettle.verify_gate import _dirty_digest, _head_sha
        stamp = tmp_path / STAMP_RELPATH
        stamp.parent.mkdir(parents=True)
        stamp.write_text("{}")  # placeholder so the untracked listing is final
        state = tmp_path / "state" / "sess-g"
        edits = _write_edits(state, [str(src)])
        stamp.write_text(json.dumps({
            "ok": True, "session_id": "sess-g", "scope": "full",
            "head_sha": _head_sha(str(tmp_path)),
            "dirty_digest": _dirty_digest(str(tmp_path)),
        }))
        import os
        past = time.time() - 60
        os.utime(stamp, (past, past))
        os.utime(edits)  # edits mtime newer than stamp
        with patch("fettle.config.state_dir", return_value=state):
            assert run_check(_gate_ctx(tmp_path, _cfg())).decision == Decision.ALLOW

    def test_multi_workspace_stamp_omitting_affected_workspace_is_rejected(self, tmp_path):
        for path, marker, filename in (
            ("api", "pyproject.toml", "app.py"),
            ("web", "package.json", "app.ts"),
        ):
            root = tmp_path / path
            root.mkdir()
            (root / marker).write_text("{}" if marker == "package.json" else '[project]\nname="api"\n')
            (root / filename).write_text("")
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(tmp_path / "api" / "app.py"), str(tmp_path / "web" / "app.ts")])
        stamp = tmp_path / STAMP_RELPATH
        stamp.parent.mkdir(parents=True)
        stamp.write_text(json.dumps({
            "ok": True, "session_id": "sess-g", "scope": "full",
            "workspaces": [{"path": "api", "ok": True, "scope": "full"}],
        }))
        with patch("fettle.config.state_dir", return_value=state):
            result = run_check(_gate_ctx(tmp_path, _cfg()))
        assert result.decision == Decision.ADVISORY
        assert "web" in result.message

    def test_multi_workspace_stamp_covering_affected_workspaces_allows(self, tmp_path):
        for path, marker, filename in (
            ("api", "pyproject.toml", "app.py"),
            ("web", "package.json", "app.ts"),
        ):
            root = tmp_path / path
            root.mkdir()
            (root / marker).write_text("{}" if marker == "package.json" else '[project]\nname="api"\n')
            (root / filename).write_text("")
        state = tmp_path / "state" / "sess-g"
        _write_edits(state, [str(tmp_path / "api" / "app.py"), str(tmp_path / "web" / "app.ts")])
        stamp = tmp_path / STAMP_RELPATH
        stamp.parent.mkdir(parents=True)
        stamp.write_text(json.dumps({
            "ok": True, "session_id": "sess-g", "scope": "full",
            "workspaces": [
                {"path": "api", "ok": True, "scope": "full"},
                {"path": "web", "ok": True, "scope": "full"},
            ],
        }))
        with patch("fettle.config.state_dir", return_value=state):
            assert run_check(_gate_ctx(tmp_path, _cfg())).decision == Decision.ALLOW


class TestRegistryAndCLI:
    def test_registered_as_stop_gate(self):
        from fettle.dispatcher_registry import CHECKS
        spec = next(s for s in CHECKS if s.name == "verify_gate")
        assert spec.events == frozenset({"Stop"})
        assert spec.budget_ms <= 100  # reads a stamp; never runs tests

    def test_cli_verify_green_exit_0(self, tmp_path):
        repo = _project(tmp_path, f"{sys.executable} -c pass")
        r = subprocess.run([*CLI, "verify"], cwd=repo,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "green" in r.stdout

    def test_cli_verify_red_exit_1(self, tmp_path):
        repo = _project(
            tmp_path, f"{sys.executable} -c \\\"import sys; sys.exit(3)\\\"")
        r = subprocess.run([*CLI, "verify", "--json"], cwd=repo,
                           capture_output=True, text=True)
        assert r.returncode == 1
        assert json.loads(r.stdout)["exit_code"] == 3

    def test_cli_verify_no_command_exit_2(self, tmp_path):
        (tmp_path / ".git").mkdir()
        r = subprocess.run([*CLI, "verify"], cwd=tmp_path,
                           capture_output=True, text=True)
        assert r.returncode == 2
        assert "test_command" in r.stderr
