"""WP-141 — `fettle init` tests.

All steps are idempotent and never touch the real $HOME: tests monkeypatch
Path.home() into tmp_path.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PLUGIN_DIR)

from fettle import init_cmd  # noqa: E402
from fettle.init_cmd import run_init  # noqa: E402


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Isolated repo + fake $HOME (no agents installed)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    return proj


def _by_name(steps):
    return {s.name: s for s in steps}


class TestRepoScaffolding:
    def test_creates_config_files(self, repo) -> None:
        steps, code = run_init(repo)
        named = _by_name(steps)
        assert named[".fettle.toml"].status == "created"
        assert named[".fettle-ignore"].status == "created"
        assert (repo / ".fettle.toml").is_file()
        assert code == 0

    def test_idempotent(self, repo) -> None:
        run_init(repo)
        steps, code = run_init(repo)
        named = _by_name(steps)
        assert named[".fettle.toml"].status == "ok"
        assert named[".fettle-ignore"].status == "ok"
        assert code == 0

    def test_dry_run_writes_nothing(self, repo) -> None:
        steps, _ = run_init(repo, dry_run=True)
        assert not (repo / ".fettle.toml").exists()
        assert not (repo / ".pre-commit-config.yaml").exists()


class TestAgentDetection:
    def test_no_agents_skipped(self, repo) -> None:
        named = _by_name(run_init(repo)[0])
        assert named["claude-code"].status == "skipped"
        assert named["opencode"].status == "skipped"

    def test_claude_code_symlink_created(self, repo) -> None:
        (Path.home() / ".claude").mkdir()
        named = _by_name(run_init(repo)[0])
        assert named["claude-code"].status == "created"
        link = Path.home() / ".claude" / "plugins" / "fettle"
        assert link.is_symlink()
        assert link.resolve() == Path(PLUGIN_DIR).resolve()

    def test_claude_code_idempotent(self, repo) -> None:
        (Path.home() / ".claude").mkdir()
        run_init(repo)
        named = _by_name(run_init(repo)[0])
        assert named["claude-code"].status == "ok"

    def test_claude_code_foreign_link_flagged(self, repo, tmp_path) -> None:
        other = tmp_path / "other"
        other.mkdir()
        plugins = Path.home() / ".claude" / "plugins"
        plugins.mkdir(parents=True)
        (plugins / "fettle").symlink_to(other)
        named = _by_name(run_init(repo)[0])
        assert named["claude-code"].status == "action"

    def test_opencode_registration(self, repo) -> None:
        (Path.home() / ".config" / "opencode").mkdir(parents=True)
        named = _by_name(run_init(repo)[0])
        assert named["opencode"].status == "created"
        config = json.loads((Path.home() / ".config" / "opencode" / "config.json").read_text())
        assert any("fettle.ts" in p for p in config["plugin"])

    def test_opencode_preserves_existing_config(self, repo) -> None:
        oc_dir = Path.home() / ".config" / "opencode"
        oc_dir.mkdir(parents=True)
        (oc_dir / "config.json").write_text(json.dumps({"theme": "dark", "plugin": ["file:///x.ts"]}))
        named = _by_name(run_init(repo)[0])
        assert named["opencode"].status == "created"
        config = json.loads((oc_dir / "config.json").read_text())
        assert config["theme"] == "dark"
        assert "file:///x.ts" in config["plugin"]

    def test_opencode_idempotent(self, repo) -> None:
        (Path.home() / ".config" / "opencode").mkdir(parents=True)
        run_init(repo)
        named = _by_name(run_init(repo)[0])
        assert named["opencode"].status == "ok"

    def test_opencode_malformed_config_is_action_not_crash(self, repo) -> None:
        oc_dir = Path.home() / ".config" / "opencode"
        oc_dir.mkdir(parents=True)
        (oc_dir / "config.json").write_text("{not json")
        named = _by_name(run_init(repo)[0])
        assert named["opencode"].status == "action"


class TestPreCommit:
    def test_writes_config(self, repo) -> None:
        named = _by_name(run_init(repo)[0])
        assert named["pre-commit-config"].status == "created"
        assert "fettle-check" in (repo / ".pre-commit-config.yaml").read_text()

    def test_existing_config_untouched(self, repo) -> None:
        (repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        named = _by_name(run_init(repo)[0])
        assert named["pre-commit-config"].status == "ok"
        assert (repo / ".pre-commit-config.yaml").read_text() == "repos: []\n"


class TestInstallTools:
    def test_present_tools_reported_ok(self, repo, monkeypatch) -> None:
        monkeypatch.setattr(init_cmd.shutil, "which", lambda name: f"/fake/bin/{name}")
        named = _by_name(run_init(repo, tools=True)[0])
        for tool in init_cmd.PINNED_TOOLS:
            assert named[f"tool:{tool}"].status == "ok"

    def test_missing_uv_is_action(self, repo, monkeypatch) -> None:
        monkeypatch.setattr(init_cmd.shutil, "which", lambda name: None)
        monkeypatch.setattr(init_cmd.os.path, "isfile", lambda p: False)
        named = _by_name(run_init(repo, tools=True)[0])
        assert named["install-tools"].status == "action"


class TestCLI:
    def test_init_via_cli_json(self, repo, monkeypatch) -> None:
        monkeypatch.chdir(repo)
        proc = subprocess.run(
            [sys.executable, os.path.join(PLUGIN_DIR, "fettle", "cli.py"),
             "init", "--dry-run", "--json"],
            capture_output=True, text=True, timeout=30, cwd=str(repo),
            env={**os.environ, "HOME": str(Path.home())},
        )
        assert proc.returncode == 0
        steps = json.loads(proc.stdout)
        assert any(s["name"] == ".fettle.toml" for s in steps)
