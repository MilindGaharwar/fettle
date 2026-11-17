"""TR-2 control-plane and policy-floor acceptance tests."""

from __future__ import annotations

from argparse import Namespace
import hashlib
from pathlib import Path

import pytest

from fettle.config import load_config, resolve_with_provenance
from fettle.dispatcher_types import CheckSpec
from fettle.policy_capsule import merge_for_child
from fettle.policy_remote import PolicyError
from fettle.dispatcher_types import HookContext, HookInput
from fettle.loop_detect import run_check as run_loop_check
from fettle.edit_journal import record_session_start
from fettle.policy_integrity import run_check as run_policy_integrity
from fettle.cli import cmd_config
from fettle.config_protect import _control_plane_name
from fettle.assurance import build_assurance_record


def test_org_gate_mode_is_a_floor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_home = tmp_path / "config"
    pack = config_home / "fettle" / "org.toml"
    pack.parent.mkdir(parents=True)
    pack.write_text('[gates.verify]\nenabled = true\nmode = "enforce"\n')
    root = tmp_path / "project"
    root.mkdir()
    (root / ".fettle.toml").write_text(
        '[gates.verify]\nenabled = false\nmode = "advisory"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    config, layers = resolve_with_provenance(str(root))

    assert config["gates"]["verify"] == {
        **config["gates"]["verify"], "enabled": True, "mode": "enforce"
    }
    org = next(layer for layer in layers if layer.name.startswith("org:"))
    assert {item["key"] for item in org.ignored} >= {
        "gates.verify.enabled", "gates.verify.mode",
    }


def test_org_release_policy_cannot_be_widened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_home = tmp_path / "config"
    pack = config_home / "fettle" / "org.toml"
    pack.parent.mkdir(parents=True)
    pack.write_text('[assurance.release.production]\nsecurity = "PASS"\n')
    root = tmp_path / "project"
    root.mkdir()
    (root / ".fettle.toml").write_text(
        '[assurance.release.production]\nsecurity = "PASS|UNKNOWN"\n'
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    config = load_config(str(root))

    assert config["assurance"]["release"]["production"]["security"] == "PASS"


def test_capsule_silence_does_not_allow_child_disabled_checks() -> None:
    effective, ignored = merge_for_child(
        {"gates": {"verify": {"enabled": True, "mode": "enforce"}}},
        {
            "gates": {"verify": {"enabled": True, "mode": "enforce"}},
            "dispatcher": {"disabled_checks": ["verify_gate"]},
        },
    )

    assert effective.get("dispatcher", {}).get("disabled_checks", []) == []
    assert any(item["key"] == "dispatcher.disabled_checks" for item in ignored)


def test_fail_closed_check_ignores_repository_disable(tmp_path: Path) -> None:
    (tmp_path / ".fettle.toml").write_text(
        '[dispatcher]\ndisabled_checks = ["critical"]\n'
        '[dispatcher.checks.critical]\nenabled = false\n'
    )
    config = load_config(str(tmp_path))
    spec = CheckSpec("critical", lambda _ctx: None, frozenset({"PreToolUse"}), fail_closed=True)

    assert spec.is_enabled(config) is True
    assert {item["key"] for item in config.policy_ignored} == {
        "dispatcher.disabled_checks", "dispatcher.checks.critical.enabled",
    }


def test_floor_can_disable_fail_closed_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_home = tmp_path / "config"
    pack = config_home / "fettle" / "org.toml"
    pack.parent.mkdir(parents=True)
    pack.write_text('[dispatcher]\ndisabled_checks = ["critical"]\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    spec = CheckSpec("critical", lambda _ctx: None, frozenset({"PreToolUse"}), fail_closed=True)

    assert spec.is_enabled(load_config(str(tmp_path))) is False


def test_repository_cannot_disable_policy_integrity_check(tmp_path: Path) -> None:
    (tmp_path / ".fettle.toml").write_text(
        '[dispatcher]\ndisabled_checks = ["policy_integrity"]\n'
    )
    config = load_config(str(tmp_path))
    from fettle.dispatcher_registry import CHECKS
    spec = next(item for item in CHECKS if item.name == "policy_integrity")

    assert spec.protected_from_repo_disable is True
    assert spec.is_enabled(config) is True


def test_environment_override_cannot_weaken_org_floor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_home = tmp_path / "config"
    pack = config_home / "fettle" / "org.toml"
    pack.parent.mkdir(parents=True)
    pack.write_text('[gates.lint]\nenabled = true\nmode = "enforce"\n')
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("FETTLE_GATE_MODE", "off")

    lint = load_config(str(tmp_path))["gates"]["lint"]

    assert lint["enabled"] is True
    assert lint["mode"] == "enforce"


def test_strict_declared_remote_policy_requires_verified_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FETTLE_POLICY_CACHE_DIR", str(tmp_path / "cache"))
    (tmp_path / ".fettle.toml").write_text(
        '[extends]\nurl = "https://example.com/policy.toml"\nsha256 = "' + "a" * 64 + '"\n'
    )

    with pytest.raises(PolicyError, match="fettle policy sync"):
        load_config(str(tmp_path), strict=True)


def test_strict_declared_remote_policy_rejects_tampered_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    expected = hashlib.sha256(b'[gates.lint]\nmode = "enforce"\n').hexdigest()
    (cache / f"{expected}.toml").write_text('[gates.lint]\nmode = "off"\n')
    monkeypatch.setenv("FETTLE_POLICY_CACHE_DIR", str(cache))
    (tmp_path / ".fettle.toml").write_text(
        '[extends]\nurl = "https://example.com/policy.toml"\n'
        f'sha256 = "{expected}"\n'
    )

    with pytest.raises(PolicyError, match="fettle policy sync"):
        load_config(str(tmp_path), strict=True)


def test_loop_state_uses_redirected_fettle_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("FETTLE_LOOP_STATE_DIR", raising=False)
    root = tmp_path / "project"
    root.mkdir()
    config = load_config(str(root))
    context = HookContext(
        HookInput("PostToolUse", "Read", {"file_path": "README.md"}, root, "tr2-state", {}),
        config, root, 0.0, 999999999.0,
    )

    run_loop_check(context)

    assert (tmp_path / "state" / "fettle" / "tr2-state" / "tr2-state.loop.jsonl").is_file()


def test_policy_change_during_session_blocks_in_enforce_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = tmp_path / "project"
    root.mkdir()
    (root / ".fettle.toml").write_text(
        '[gates.config_protect]\nenabled = true\nmode = "enforce"\n'
    )
    original = load_config(str(root))
    original_digest = __import__("hashlib").sha256(
        __import__("json").dumps(original, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    record_session_start(
        "tr2-policy", root, original_digest,
        config_protect_enabled=True, config_protect_mode="enforce",
    )
    changed = {**original, "gates": {**original["gates"], "lint": {
        **original["gates"]["lint"], "mode": "enforce",
    }, "config_protect": {"enabled": False, "mode": "advisory"}}}
    context = HookContext(
        HookInput("Stop", None, {}, root, "tr2-policy", {}), changed, root, 0.0, 999999999.0,
    )

    result = run_policy_integrity(context)

    assert result.decision.value == "block"
    assert "policy changed during this session" in result.message


def test_policy_change_blocks_when_current_policy_enforces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = tmp_path / "project"
    root.mkdir()
    original = load_config(str(root))
    original_digest = __import__("hashlib").sha256(
        __import__("json").dumps(original, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    record_session_start(
        "tr2-current-enforce", root, original_digest,
        config_protect_enabled=True, config_protect_mode="advisory",
    )
    changed = {**original, "gates": {**original["gates"], "config_protect": {
        "enabled": True, "mode": "enforce",
    }}}
    context = HookContext(
        HookInput("Stop", None, {}, root, "tr2-current-enforce", {}),
        changed, root, 0.0, 999999999.0,
    )

    result = run_policy_integrity(context)

    assert result.decision.value == "block"
    assert "policy changed during this session" in result.message


def test_policy_change_makes_assurance_integrity_non_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = tmp_path / "project"
    root.mkdir()
    __import__("subprocess").run(["git", "init", "-q", str(root)], check=True)
    record_session_start(
        "tr2-assurance", root, "0" * 64,
        config_protect_enabled=True, config_protect_mode="enforce",
    )

    dimension = build_assurance_record(str(root))["record"]["dimensions"]["policy_integrity"]

    assert dimension["status"] == "FAIL"
    assert "changed during the session" in dimension["reason"]


def test_missing_session_policy_evidence_makes_assurance_integrity_non_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = tmp_path / "project"
    root.mkdir()
    __import__("subprocess").run(["git", "init", "-q", str(root)], check=True)

    dimension = build_assurance_record(str(root))["record"]["dimensions"]["policy_integrity"]

    assert dimension["status"] == "UNKNOWN"
    assert "no session-start policy evidence" in dimension["reason"]


def test_control_plane_detection_resolves_symlink(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    policy = root / ".fettle.toml"
    policy.write_text("")
    alias = root / "policy-link"
    alias.symlink_to(policy)

    assert _control_plane_name(alias, root) == "policy-link"


def test_control_plane_probe_does_not_create_state_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    root = tmp_path / "project"
    root.mkdir()

    assert _control_plane_name(root / "README.md", root) is None
    assert not state.exists()


def test_config_explain_reports_ignored_repository_disable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".git").mkdir()
    (root / ".fettle.toml").write_text(
        '[dispatcher]\ndisabled_checks = ["policy_integrity"]\n'
    )
    monkeypatch.chdir(root)

    cmd_config(Namespace(validate=False, print_effective=False, explain=True))

    output = capsys.readouterr().out
    assert "ignored weakening attempts:" in output
    assert "dispatcher.disabled_checks (repo)" in output
