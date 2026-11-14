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
        "PYTHONPATH": str(ROOT),
    }
    return root, env


def _command(mode: str) -> str:
    if mode == "plugin":
        hooks = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
        command = hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        return command.replace("${CLAUDE_PLUGIN_ROOT}", shlex.quote(str(ROOT)))
    return bridge.dispatcher_command()


def _event_command(mode: str, event: str) -> str:
    if mode == "plugin":
        hooks = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
        command = hooks["hooks"][event][0]["hooks"][0]["command"]
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


def _run_raw(command: str, payload: str, root: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=root, env=env, input=payload, text=True,
        capture_output=True, shell=True, timeout=15,
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


@pytest.mark.parametrize("mode", ("plugin", "bridge"))
def test_registered_hook_records_edit_and_stop_requires_verify(installed_hook_repo, mode):
    root, env = installed_hook_repo
    (root / ".fettle.toml").write_text(
        "[gates.verify]\nenabled = true\nmode = \"enforce\"\n",
        encoding="utf-8",
    )
    target = root / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "commit", "-qm", "base"],
        check=True,
    )
    session = "tr1-edit"
    pre = _payload("claude_code", "pre_edit", root, file_path=str(target))
    pre["session_id"] = session
    assert _run(_event_command(mode, "PreToolUse"), pre, root, env).returncode == 0
    target.write_text("value = 2\n", encoding="utf-8")
    post = _payload("claude_code", "post_write", root, file_path=str(target))
    post["session_id"] = session
    assert _run(_event_command(mode, "PostToolUse"), post, root, env).returncode == 0

    stop = _payload("claude_code", "stop", root)
    stop["session_id"] = session
    result = _run(_event_command(mode, "Stop"), stop, root, env)

    assert result.returncode == 2, result.stderr
    assert "no verification run recorded this session" in json.loads(result.stdout)["reason"]


@pytest.mark.parametrize("mode", ("plugin", "bridge"))
def test_registered_hook_detects_edit_after_journal_is_deleted(installed_hook_repo, mode):
    root, env = installed_hook_repo
    (root / ".fettle.toml").write_text(
        "[gates.verify]\nenabled = true\nmode = \"enforce\"\n",
        encoding="utf-8",
    )
    target = root / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "commit", "-qm", "base"],
        check=True,
    )
    session = "tr1-deleted"
    pre = _payload("claude_code", "pre_edit", root, file_path=str(target))
    pre["session_id"] = session
    assert _run(_event_command(mode, "PreToolUse"), pre, root, env).returncode == 0
    target.write_text("value = 2\n", encoding="utf-8")
    post = _payload("claude_code", "post_write", root, file_path=str(target))
    post["session_id"] = session
    assert _run(_event_command(mode, "PostToolUse"), post, root, env).returncode == 0
    journal = Path(env["XDG_STATE_HOME"]) / "fettle" / session / "edits.jsonl"
    journal.unlink()

    stop = _payload("claude_code", "stop", root)
    stop["session_id"] = session
    result = _run(_event_command(mode, "Stop"), stop, root, env)

    assert result.returncode == 2, result.stderr
    assert "no verification run recorded this session" in json.loads(result.stdout)["reason"]


@pytest.mark.parametrize("mode", ("plugin", "bridge"))
def test_registered_hook_uses_project_policy_from_subdirectory(installed_hook_repo, mode):
    root, env = installed_hook_repo
    subdir = root / "nested"
    subdir.mkdir()
    payload = _payload("claude_code", "pre_edit", root, file_path="../ruff.toml")
    payload["cwd"] = str(subdir)

    result = _run(_event_command(mode, "PreToolUse"), payload, subdir, env)

    assert result.returncode == 2, result.stderr
    assert "Config modification blocked" in json.loads(result.stdout)["reason"]


@pytest.mark.parametrize("mode", ("plugin", "bridge"))
@pytest.mark.parametrize(
    "payload",
    (
        {
            "hook_event_name": "PreToolUse", "tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": "ruff.toml"}, "session_id": "tr1-notebook",
        },
        {
            "hook_event_name": "PreToolUse", "tool_name": "apply_patch", "turn_id": "tr1",
            "tool_input": {"command": "*** Begin Patch\n*** Update File: ruff.toml\n+x\n*** Update File: safe.txt\n+y\n*** End Patch"},
            "session_id": "tr1-codex",
        },
        {
            "type": "tool.execute.before", "tool": "multiedit",
            "args": {"edits": [{"filePath": "safe.txt"}, {"filePath": "ruff.toml"}]},
            "sessionID": "tr1-opencode",
        },
    ),
)
def test_registered_hook_blocks_edit_aliases_and_multi_target_events(
    installed_hook_repo, mode, payload,
):
    root, env = installed_hook_repo
    payload = {**payload, "cwd": str(root), "directory": str(root)}

    result = _run(_event_command(mode, "PreToolUse"), payload, root, env)

    assert result.returncode == 2, result.stderr
    assert "Config modification blocked" in json.loads(result.stdout)["reason"]


@pytest.mark.parametrize("mode", ("plugin", "bridge"))
def test_registered_hook_ignores_repository_local_fettle_package(installed_hook_repo, mode):
    root, env = installed_hook_repo
    local = root / "fettle"
    local.mkdir()
    (local / "__init__.py").write_text("", encoding="utf-8")
    (local / "dispatcher.py").write_text("print('{}')\n", encoding="utf-8")
    payload = _payload("claude_code", "pre_bash", root, command="rm -rf build")

    result = _run(_event_command(mode, "PreToolUse"), payload, root, env)

    assert result.returncode == 2, result.stderr
    assert "Destructive command blocked" in json.loads(result.stdout)["reason"]


@pytest.mark.parametrize("mode", ("plugin", "bridge"))
def test_registered_hook_blocks_malformed_pretool_input(installed_hook_repo, mode):
    root, env = installed_hook_repo

    result = _run_raw(
        _event_command(mode, "PreToolUse"),
        '{"hook_event_name":"PreToolUse",',
        root,
        env,
    )

    assert result.returncode == 2, result.stderr
    assert "Malformed PreToolUse input" in json.loads(result.stdout)["reason"]


@pytest.mark.parametrize("mode", ("plugin", "bridge"))
def test_registered_hook_treats_malformed_journal_as_unknown(installed_hook_repo, mode):
    root, env = installed_hook_repo
    (root / ".fettle.toml").write_text(
        "[gates.verify]\nenabled = true\nmode = \"enforce\"\n",
        encoding="utf-8",
    )
    session = "tr1-malformed-journal"
    journal = Path(env["XDG_STATE_HOME"]) / "fettle" / session / "edits.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text("not-json\n", encoding="utf-8")
    stop = _payload("claude_code", "stop", root)
    stop["session_id"] = session

    result = _run(_event_command(mode, "Stop"), stop, root, env)

    assert result.returncode == 2, result.stderr
    assert "no verification run recorded this session" in json.loads(result.stdout)["reason"]
