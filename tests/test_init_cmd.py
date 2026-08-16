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
        assert named["codex"].status == "skipped"
        assert named["gemini"].status == "skipped"

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

    def test_opencode_transport_uses_current_launcher(self) -> None:
        transport = (Path(PLUGIN_DIR) / "integrations" / "opencode" / "fettle.ts").read_text()
        assert 'join(pluginRoot, "fettle", "run.sh")' in transport
        assert 'join(pluginRoot, "scripts", "run.sh")' not in transport

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

    def test_codex_registration(self, repo) -> None:
        (Path.home() / ".codex").mkdir()
        named = _by_name(run_init(repo)[0])
        assert named["codex"].status == "created"
        assert named["codex-enable"].status == "action"  # features.hooks toggle
        config = json.loads((Path.home() / ".codex" / "hooks.json").read_text())
        for event in ("PreToolUse", "PostToolUse", "Stop"):
            groups = config["hooks"][event]
            assert any("dispatcher.py" in h["command"]
                       for g in groups for h in g["hooks"])
        assert config["hooks"]["PreToolUse"][0]["matcher"] == "Write|Edit|Bash"

    def test_codex_idempotent_and_preserves_existing(self, repo) -> None:
        codex_dir = Path.home() / ".codex"
        codex_dir.mkdir()
        (codex_dir / "hooks.json").write_text(json.dumps({
            "hooks": {"PreToolUse": [{"matcher": "Bash",
                                       "hooks": [{"type": "command", "command": "other-hook"}]}]},
        }))
        run_init(repo)
        named = _by_name(run_init(repo)[0])
        assert named["codex"].status == "ok"
        config = json.loads((codex_dir / "hooks.json").read_text())
        pre = config["hooks"]["PreToolUse"]
        assert any(h["command"] == "other-hook" for g in pre for h in g["hooks"])
        assert any("dispatcher.py" in h["command"] for g in pre for h in g["hooks"])

    def test_codex_malformed_config_is_action_not_crash(self, repo) -> None:
        codex_dir = Path.home() / ".codex"
        codex_dir.mkdir()
        (codex_dir / "hooks.json").write_text("{not json")
        named = _by_name(run_init(repo)[0])
        assert named["codex"].status == "action"

    def test_gemini_registration(self, repo) -> None:
        (Path.home() / ".gemini").mkdir()
        named = _by_name(run_init(repo)[0])
        assert named["gemini"].status == "created"
        config = json.loads((Path.home() / ".gemini" / "settings.json").read_text())
        for event in ("BeforeTool", "AfterTool", "AfterAgent"):
            groups = config["hooks"][event]
            assert any("dispatcher.py" in h["command"]
                       for g in groups for h in g["hooks"])
        before = config["hooks"]["BeforeTool"][0]
        assert before["matcher"] == "run_shell_command|write_file|replace"
        assert before["hooks"][0]["timeout"] == 10000  # Gemini timeouts are ms

    def test_gemini_idempotent_and_preserves_existing(self, repo) -> None:
        gemini_dir = Path.home() / ".gemini"
        gemini_dir.mkdir()
        (gemini_dir / "settings.json").write_text(json.dumps({"theme": "dark"}))
        run_init(repo)
        named = _by_name(run_init(repo)[0])
        assert named["gemini"].status == "ok"
        config = json.loads((gemini_dir / "settings.json").read_text())
        assert config["theme"] == "dark"

    def test_gemini_malformed_config_is_action_not_crash(self, repo) -> None:
        gemini_dir = Path.home() / ".gemini"
        gemini_dir.mkdir()
        (gemini_dir / "settings.json").write_text("{not json")
        named = _by_name(run_init(repo)[0])
        assert named["gemini"].status == "action"

    def test_wheel_mode_publishes_bridge_and_registers_all_hosts(
        self, repo, monkeypatch, tmp_path
    ) -> None:
        from fettle import bridge

        for directory in (".claude", ".codex", ".gemini"):
            (Path.home() / directory).mkdir()
        (Path.home() / ".config" / "opencode").mkdir(parents=True)
        monkeypatch.setattr(init_cmd, "_is_clone_mode", lambda: False)
        monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")

        named = _by_name(run_init(repo)[0])

        assert named["bridge"].status == "created"
        assert named["claude-code"].status == "created"
        assert named["codex"].status == "created"
        assert named["gemini"].status == "created"
        assert named["opencode"].status == "created"
        assert bridge.validate_bridge().ok

    def test_wheel_mode_dry_run_does_not_write_home(self, repo, monkeypatch, tmp_path) -> None:
        from fettle import bridge

        (Path.home() / ".codex").mkdir()
        before = sorted(str(path.relative_to(Path.home())) for path in Path.home().rglob("*"))
        monkeypatch.setattr(init_cmd, "_is_clone_mode", lambda: False)
        monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")

        named = _by_name(run_init(repo, dry_run=True)[0])

        after = sorted(str(path.relative_to(Path.home())) for path in Path.home().rglob("*"))
        assert before == after
        assert named["bridge"].status == "created"
        assert not tmp_path.joinpath("bridge").exists()

    def test_wheel_mode_upgrades_owned_bridge_registrations(
        self, repo, monkeypatch, tmp_path
    ) -> None:
        from fettle import bridge

        for directory in (".claude", ".codex", ".gemini"):
            (Path.home() / directory).mkdir()
        opencode_dir = Path.home() / ".config" / "opencode"
        opencode_dir.mkdir(parents=True)
        base = tmp_path / "bridge"
        old = base / "1.11.0"
        old.mkdir(parents=True)
        (old / "manifest.json").write_text(json.dumps({
            "schema_version": 1, "fettle_version": "1.11.0", "files": {"old": "digest"},
        }))
        plugins = Path.home() / ".claude" / "plugins"
        plugins.mkdir()
        (plugins / "fettle").symlink_to(old)
        old_uri = (old / "opencode" / "fettle.ts").as_uri()
        current_uri = (base / bridge.__version__ / "opencode" / "fettle.ts").as_uri()
        (opencode_dir / "config.json").write_text(json.dumps({
            "theme": "dark", "plugin": ["file:///foreign.ts", old_uri, current_uri],
        }))
        old_command = "/old/venv/bin/python -m fettle.dispatcher"
        current_command = f"{sys.executable} -m fettle.dispatcher"
        codex_config = {"hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "foreign-hook"}]},
            {"matcher": "Write|Edit|Bash", "hooks": [{"type": "command", "command": old_command}]},
            {"matcher": "Write|Edit|Bash", "hooks": [{"type": "command", "command": current_command}]},
        ]}}
        gemini_config = {"hooks": {"BeforeTool": [
            {"matcher": "run_shell_command", "hooks": [{"type": "command", "command": "foreign-hook"}]},
            {"matcher": "run_shell_command|write_file|replace",
             "hooks": [{"type": "command", "command": old_command}]},
            {"matcher": "run_shell_command|write_file|replace",
             "hooks": [{"type": "command", "command": current_command}]},
        ]}}
        (Path.home() / ".codex" / "hooks.json").write_text(json.dumps(codex_config))
        (Path.home() / ".gemini" / "settings.json").write_text(json.dumps(gemini_config))
        monkeypatch.setattr(init_cmd, "_is_clone_mode", lambda: False)
        monkeypatch.setattr(bridge, "bridge_base", lambda: base)

        named = _by_name(run_init(repo)[0])

        current = bridge.bridge_dir()
        assert named["claude-code"].status == "created"
        assert (plugins / "fettle").resolve() == current.resolve()
        config = json.loads((opencode_dir / "config.json").read_text())
        assert config["theme"] == "dark"
        assert "file:///foreign.ts" in config["plugin"]
        assert old_uri not in config["plugin"]
        assert sum("fettle.ts" in uri for uri in config["plugin"]) == 1
        for path in (Path.home() / ".codex" / "hooks.json",
                     Path.home() / ".gemini" / "settings.json"):
            text = path.read_text()
            assert old_command not in text
            assert "foreign-hook" in text
            assert text.count("-m fettle.dispatcher") == 3


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
        monkeypatch.setattr(init_cmd, "_is_clone_mode", lambda: True)
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
