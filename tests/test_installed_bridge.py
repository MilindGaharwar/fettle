import hashlib
import json
import os
import shlex
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from fettle import bridge


@pytest.mark.parametrize(
    ("xdg_value", "expected"),
    [
        (None, Path("home") / ".local" / "share" / "fettle" / "bridge"),
        ("", Path("home") / ".local" / "share" / "fettle" / "bridge"),
        ("custom data", Path("custom data") / "fettle" / "bridge"),
    ],
)
def test_bridge_base_honors_xdg_data_home_on_linux(tmp_path, monkeypatch, xdg_value, expected):
    home = tmp_path / "home"
    monkeypatch.setattr(bridge.sys, "platform", "linux")
    monkeypatch.setattr(bridge.os, "name", "posix")
    monkeypatch.setenv("HOME", str(home))
    if xdg_value is None:
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    else:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / xdg_value) if xdg_value else "")

    assert bridge.bridge_base() == tmp_path / expected


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
    assert shlex.split(command) == ["node", str(root / "hooks" / "subagent_inject.js")]
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


@pytest.mark.parametrize("relative", ["/tmp/outside", "../outside", "commands/../../outside", ""])
def test_validate_bridge_rejects_manifest_paths_outside_root(tmp_path, monkeypatch, relative):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")
    bridge.publish_bridge(dry_run=False)
    manifest_path = bridge.bridge_dir() / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][relative] = hashlib.sha256(b"outside").hexdigest()
    manifest_path.write_text(json.dumps(manifest))

    validation = bridge.validate_bridge()

    assert not validation.ok
    assert validation.status == "stale"
    assert "manifest file path" in validation.detail
    assert "fettle init" in validation.detail


def test_validate_bridge_allows_literal_encoded_path_characters(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")
    bridge.publish_bridge(dry_run=False)
    root = bridge.bridge_dir()
    special = root / "commands" / "%2e%2e guide.md"
    special.write_text("safe")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["commands/%2e%2e guide.md"] = hashlib.sha256(b"safe").hexdigest()
    manifest_path.write_text(json.dumps(manifest))

    assert bridge.validate_bridge().ok


def test_validate_bridge_rejects_manifest_symlink_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")
    bridge.publish_bridge(dry_run=False)
    outside = tmp_path / "outside"
    outside.write_text("outside")
    linked = bridge.bridge_dir() / "commands" / "linked.md"
    linked.symlink_to(outside)
    manifest_path = bridge.bridge_dir() / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["commands/linked.md"] = hashlib.sha256(b"outside").hexdigest()
    manifest_path.write_text(json.dumps(manifest))

    validation = bridge.validate_bridge()

    assert not validation.ok
    assert validation.status == "stale"
    assert "manifest file path escapes bridge root" in validation.detail
    assert "fettle init" in validation.detail


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

    assert shlex.split(command) == [str(executable), "-m", "fettle.dispatcher"]


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


@pytest.mark.parametrize("target_type", ["file", "directory"])
def test_publish_bridge_refuses_foreign_version_target(tmp_path, monkeypatch, target_type):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")
    root = bridge.bridge_dir()
    root.parent.mkdir(parents=True)
    if target_type == "file":
        root.write_text("foreign")
    else:
        root.mkdir()
        (root / "sentinel").write_text("foreign")

    result = bridge.publish_bridge(dry_run=False)

    assert result.status == "error"
    assert "not manifest-owned" in result.detail
    assert (root.read_text() if root.is_file() else (root / "sentinel").read_text()) == "foreign"


def test_concurrent_fresh_publication_converges_on_valid_bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")
    barrier = threading.Barrier(2)
    real_write_tree = bridge._write_tree

    def synchronized_write_tree(root, published_root):
        real_write_tree(root, published_root)
        barrier.wait(timeout=5)

    monkeypatch.setattr(bridge, "_write_tree", synchronized_write_tree)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: bridge.publish_bridge(dry_run=False), range(2)))

    assert sorted(result.status for result in results) == ["created", "ok"]
    assert bridge.validate_bridge().ok
    assert not list(bridge.bridge_base().glob(f".{bridge.__version__}.tmp-*"))


def test_publish_bridge_removes_partial_temporary_tree_after_write_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")

    def fail_write_tree(root, published_root):
        del published_root
        (root / "partial").write_text("incomplete")
        raise OSError("disk full")

    monkeypatch.setattr(bridge, "_write_tree", fail_write_tree)

    result = bridge.publish_bridge(dry_run=False)

    assert result.status == "error"
    assert not bridge.bridge_dir().exists()
    assert not list(bridge.bridge_base().glob(f".{bridge.__version__}.tmp-*"))


def test_publish_bridge_preserves_foreign_legacy_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")
    bridge.publish_bridge(dry_run=False)
    (bridge.bridge_dir() / "opencode" / "fettle.ts").write_text("tampered")
    foreign = bridge.bridge_base() / f".{bridge.__version__}.backup"
    foreign.mkdir()
    (foreign / "sentinel").write_text("foreign")

    result = bridge.publish_bridge(dry_run=False)

    assert result.status == "created"
    assert (foreign / "sentinel").read_text() == "foreign"


def test_publish_bridge_restores_prior_root_when_install_replace_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")
    bridge.publish_bridge(dry_run=False)
    root = bridge.bridge_dir()
    (root / "opencode" / "fettle.ts").write_text("tampered")
    prior_manifest = (root / "manifest.json").read_bytes()
    real_replace = os.replace

    def fail_install(source, destination):
        if Path(destination) == root and ".tmp-" in Path(source).name:
            raise OSError("interrupted install")
        real_replace(source, destination)

    monkeypatch.setattr(bridge.os, "replace", fail_install)

    result = bridge.publish_bridge(dry_run=False)

    assert result.status == "error"
    assert (root / "manifest.json").read_bytes() == prior_manifest
    assert (root / "opencode" / "fettle.ts").read_text() == "tampered"
    assert not list(bridge.bridge_base().glob(f".{bridge.__version__}.backup-*"))


def test_publish_bridge_restores_prior_root_after_failed_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")
    bridge.publish_bridge(dry_run=False)
    root = bridge.bridge_dir()
    (root / "opencode" / "fettle.ts").write_text("prior")
    stale = bridge.BridgeValidation(False, "stale", "candidate invalid")
    monkeypatch.setattr(bridge, "validate_bridge", lambda: stale)

    result = bridge.publish_bridge(dry_run=False)

    assert result.status == "error"
    assert (root / "opencode" / "fettle.ts").read_text() == "prior"
    assert not list(bridge.bridge_base().glob(f".{bridge.__version__}.backup-*"))


def test_publish_bridge_removes_fresh_root_after_failed_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")
    stale = bridge.BridgeValidation(False, "stale", "candidate invalid")
    monkeypatch.setattr(bridge, "validate_bridge", lambda: stale)

    result = bridge.publish_bridge(dry_run=False)

    assert result.status == "error"
    assert not bridge.bridge_dir().exists()
    assert not list(bridge.bridge_base().glob(f".{bridge.__version__}.backup-*"))


def test_publish_bridge_retains_backup_when_rollback_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")
    bridge.publish_bridge(dry_run=False)
    root = bridge.bridge_dir()
    (root / "opencode" / "fettle.ts").write_text("prior")
    stale = bridge.BridgeValidation(False, "stale", "candidate invalid")
    monkeypatch.setattr(bridge, "validate_bridge", lambda: stale)
    real_replace = os.replace

    def fail_restore(source, destination):
        if Path(source).name == "root" and Path(destination) == root:
            raise OSError("restore blocked")
        real_replace(source, destination)

    monkeypatch.setattr(bridge.os, "replace", fail_restore)

    result = bridge.publish_bridge(dry_run=False)

    backups = list(bridge.bridge_base().glob(f".{bridge.__version__}.backup-*/root"))
    assert result.status == "error"
    assert "rollback failed" in result.detail
    assert str(backups[0]) in result.detail
    assert (backups[0] / "opencode" / "fettle.ts").read_text() == "prior"
