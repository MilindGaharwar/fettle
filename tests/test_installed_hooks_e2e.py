"""TR-0 baseline: execute the commands shipped to agent hosts."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from fettle import bridge


ROOT = Path(__file__).parents[1]
PAYLOADS = json.loads(
    (ROOT / "tests/fixtures/agent_payloads/conformance.json").read_text(encoding="utf-8")
)["cases"]
HOSTS = ("claude_code", "codex", "gemini", "opencode")


def _case(name: str) -> dict:
    return next(case for case in PAYLOADS if case["name"] == name)


@pytest.fixture
def installed_hook_repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "project"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".fettle.toml").write_text(
        "# Content assertions need deterministic enforcement; latency is tested separately.\n"
        "[dispatcher]\n"
        "global_budget_ms = 5000\n"
        "[gates.config_protect]\n"
        "enabled = true\n"
        "mode = \"enforce\"\n"
        "[gates.destructive]\n"
        "enabled = true\n"
        "mode = \"enforce\"\n",
        encoding="utf-8",
    )
    (root / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")
    (root / "secret.txt").write_text(
        "token=synthetic-test-credential-1234567890\n", encoding="utf-8",
    )
    home = tmp_path / "home"
    env = {
        **os.environ,
        "HOME": str(home),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "FETTLE_PYTHON": sys.executable,
    }
    return root, env


def _command(mode: str) -> str:
    if mode == "plugin":
        hooks = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        return command.replace("${CLAUDE_PLUGIN_ROOT}", shlex.quote(str(ROOT)))
    return bridge.dispatcher_command()


def _payload(host: str, case_name: str, root: Path, **tool_input: str) -> dict:
    payload = deepcopy(_case(case_name)[host])
    serialized = json.dumps(payload).replace("/repo", str(root))
    payload = json.loads(serialized)
    if host == "opencode":
        payload["args"].update(tool_input)
    else:
        payload["tool_input"].update(tool_input)
    return payload


def _run(command: str, payload: dict, root: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=root,
        env=env,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        shell=True,
        timeout=15,
    )


@pytest.mark.parametrize("mode", ("plugin", "bridge"))
@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize(
    ("case_name", "tool_input", "reason"),
    (
        ("pre_edit", {"file_path": "ruff.toml", "filePath": "ruff.toml"}, "Config modification blocked"),
        ("pre_bash", {"command": "rm -rf build"}, "Destructive command blocked"),
        ("pre_bash", {"command": "cat secret.txt"}, "Blocked secret access"),
        ("pre_read", {"file_path": "secret.txt", "filePath": "secret.txt"}, "Blocked secret access"),
    ),
)
def test_registered_hook_commands_block_baseline_cases(
    installed_hook_repo, mode, host, case_name, tool_input, reason,
):
    root, env = installed_hook_repo

    result = _run(_command(mode), _payload(host, case_name, root, **tool_input), root, env)

    assert result.returncode == 2, result.stderr
    output = json.loads(result.stdout)
    assert output["decision"] == "block"
    assert reason in output["reason"]


@pytest.mark.parametrize("mode", ("plugin", "bridge"))
def test_registered_hook_commands_fail_closed_when_budget_expires(
    installed_hook_repo, mode,
):
    root, env = installed_hook_repo
    config = root / ".fettle.toml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "global_budget_ms = 5000", "global_budget_ms = 1"
        ),
        encoding="utf-8",
    )
    payload = _payload(
        "codex", "pre_edit", root, file_path="ruff.toml", filePath="ruff.toml"
    )

    result = _run(_command(mode), payload, root, env)

    assert result.returncode == 2, result.stderr
    output = json.loads(result.stdout)
    assert output["decision"] == "block"
    assert "could not run before the deadline" in output["reason"]


@pytest.mark.parametrize("mode", ("plugin", "bridge"))
def test_registered_hook_commands_block_malformed_policy(installed_hook_repo, mode):
    root, env = installed_hook_repo
    (root / ".fettle.toml").write_text("[gates.destructive\nenabled = true\n", encoding="utf-8")
    payload = _payload("claude_code", "pre_bash", root, command="printf safe")

    result = _run(_command(mode), payload, root, env)

    assert result.returncode == 2, result.stderr
    output = json.loads(result.stdout)
    assert output["decision"] == "block"
    assert "Policy configuration could not be loaded" in output["reason"]


@pytest.mark.parametrize("mode", ("plugin", "bridge"))
def test_registered_hook_commands_allow_safe_command(installed_hook_repo, mode):
    root, env = installed_hook_repo
    payload = _payload("claude_code", "pre_bash", root, command="printf safe")

    result = _run(_command(mode), payload, root, env)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "hookSpecificOutput": {"hookEventName": "PreToolUse"},
    }


@pytest.mark.parametrize("mode", ("plugin", "bridge"))
def test_registered_hook_commands_block_unreadable_policy(installed_hook_repo, mode):
    root, env = installed_hook_repo
    missing_policy = root / "missing-policy.toml"
    env["FETTLE_CONFIG"] = str(missing_policy)
    payload = _payload("claude_code", "pre_bash", root, command="printf safe")

    result = _run(_command(mode), payload, root, env)

    assert result.returncode == 2, result.stderr
    output = json.loads(result.stdout)
    assert output["decision"] == "block"
    assert "Policy configuration could not be loaded" in output["reason"]


def test_conformance_fixture_covers_each_hosts_required_events():
    by_name = {case["name"]: case for case in PAYLOADS}

    for name in ("pre_edit", "pre_bash", "pre_read", "stop"):
        assert set(HOSTS) <= by_name[name].keys()
