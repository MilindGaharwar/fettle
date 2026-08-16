import hashlib
import json

from fettle import bridge


def test_publish_bridge_is_atomic_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "data" / "bridge")

    first = bridge.publish_bridge(dry_run=False)
    second = bridge.publish_bridge(dry_run=False)

    assert first.status == "created"
    assert second.status == "ok"
    assert bridge.validate_bridge().ok
    assert not list((tmp_path / "data" / "bridge").glob(".*.tmp-*"))


def test_bridge_manifest_binds_every_owned_file(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge with spaces")

    bridge.publish_bridge(dry_run=False)
    root = bridge.bridge_dir()
    manifest = json.loads((root / "manifest.json").read_text())

    for relative, expected in manifest["files"].items():
        actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        assert actual == expected
    assert bridge.validate_bridge().ok
    hooks = json.loads((root / "hooks" / "hooks.json").read_text())
    command = hooks["hooks"]["SubagentStart"][0]["hooks"][0]["command"]
    assert str(root / "hooks" / "subagent_inject.js") in command
    assert ".tmp-" not in command
    assert len(list((root / "commands").glob("*.md"))) == 17


def test_validate_bridge_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")
    bridge.publish_bridge(dry_run=False)
    (bridge.bridge_dir() / "opencode" / "fettle.ts").write_text("tampered")

    validation = bridge.validate_bridge()

    assert not validation.ok
    assert validation.status == "stale"
    assert "fettle init" in validation.detail

    repaired = bridge.publish_bridge(dry_run=False)
    assert repaired.status == "created"
    assert bridge.validate_bridge().ok


def test_publish_bridge_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")

    result = bridge.publish_bridge(dry_run=True)

    assert result.status == "created"
    assert "dry-run" in result.detail
    assert not tmp_path.joinpath("bridge").exists()


def test_bridge_commands_quote_interpreter_path(tmp_path, monkeypatch):
    executable = tmp_path / "python env" / "bin" / "python"
    monkeypatch.setattr(bridge.sys, "executable", str(executable))

    command = bridge.dispatcher_command()

    assert command.startswith("'")
    assert command.endswith(" -m fettle.dispatcher")


def test_bridge_command_preserves_virtualenv_interpreter_symlink(tmp_path, monkeypatch):
    base_python = tmp_path / "base" / "python"
    base_python.parent.mkdir()
    base_python.touch()
    venv_python = tmp_path / "venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.symlink_to(base_python)
    monkeypatch.setattr(bridge.sys, "executable", str(venv_python))

    command = bridge.dispatcher_command()

    assert command == f"{venv_python} -m fettle.dispatcher"


def test_shell_command_uses_windows_serializer(monkeypatch):
    monkeypatch.setattr(bridge.os, "name", "nt")

    command = bridge._shell_command([r"C:\Python Env\python.exe", "-m", "fettle.dispatcher"])

    assert command == '"C:\\Python Env\\python.exe" -m fettle.dispatcher'


def test_link_like_detects_junction_api(monkeypatch):
    class JunctionPath:
        def is_symlink(self):
            return False

        def is_junction(self):
            return True

    assert bridge._is_link_like(JunctionPath())


def test_bridge_refuses_symlink_base(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(target, target_is_directory=True)
    monkeypatch.setattr(bridge, "bridge_base", lambda: linked)

    result = bridge.publish_bridge(dry_run=False)

    assert result.status == "error"
    assert not list(target.iterdir())
