"""Pipeline dump contract tests: runtime selection, hosts, and provenance."""

from __future__ import annotations

import json
import subprocess
from argparse import Namespace

import pytest

from fettle.pipeline_dump import dump_pipeline


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    for name in ("FETTLE_CONFIG", "FETTLE_GATE_MODE", "FETTLE_POLICY_CAPSULE"):
        monkeypatch.delenv(name, raising=False)


def _init_repo_with_config(tmp_path, config_body: str) -> str:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".fettle.toml").write_text(config_body, encoding="utf-8")
    return str(root)


def test_every_check_appears_once_per_wired_host(tmp_path):
    from fettle.dispatcher_registry import CHECKS
    from fettle.host_capabilities import host_capabilities

    result = dump_pipeline(str(tmp_path))

    expected = {
        (check.name, host)
        for check in CHECKS
        for host, capabilities in host_capabilities().items()
        if check.events.intersection(capabilities["dispatcher_events"])
    }
    actual = [(row["name"], row["host"]) for row in result["rows"]]
    assert len(actual) == len(set(actual))
    assert set(actual) == expected


def test_registry_default_reports_truthful_selection_source(tmp_path):
    result = dump_pipeline(str(tmp_path))

    quality = next(
        row for row in result["rows"]
        if row["name"] == "quality_gate" and row["host"] == "claude_code"
    )
    assert quality["enabled"] is True
    assert quality["mode"] == "check-defined"
    assert quality["source"] == "registry"
    assert quality["source_key"] == "enabled_by_default"


def test_dispatcher_check_override_wins_over_disabled_list(tmp_path, monkeypatch):
    packs = tmp_path / "xdg" / "fettle"
    packs.mkdir(parents=True)
    (packs / "org.toml").write_text(
        '[dispatcher]\ndisabled_checks = ["quality_gate", "worklog"]\n',
        encoding="utf-8",
    )
    root = _init_repo_with_config(tmp_path, """\
[dispatcher.checks.quality_gate]
enabled = true
""")

    result = dump_pipeline(root)

    quality_rows = [row for row in result["rows"] if row["name"] == "quality_gate"]
    assert quality_rows
    assert all(row["enabled"] is True for row in quality_rows)
    assert all(row["source"] == "repo" for row in quality_rows)
    assert all(
        row["source_key"] == "dispatcher.checks.quality_gate.enabled"
        for row in quality_rows
    )
    worklog_rows = [row for row in result["rows"] if row["name"] == "worklog"]
    assert all(row["enabled"] is False for row in worklog_rows)
    assert all(row["source"] == "org:org" for row in worklog_rows)


def test_disabled_list_reports_owning_layer(tmp_path):
    root = _init_repo_with_config(
        tmp_path, '[dispatcher]\ndisabled_checks = ["quality_gate"]\n',
    )

    result = dump_pipeline(root)

    quality_rows = [row for row in result["rows"] if row["name"] == "quality_gate"]
    assert all(row["enabled"] is False for row in quality_rows)
    assert all(row["source"] == "repo" for row in quality_rows)
    assert all(row["source_key"] == "dispatcher.disabled_checks" for row in quality_rows)


def test_host_events_and_authority_are_explicit(tmp_path):
    result = dump_pipeline(str(tmp_path))

    quality = {
        row["host"]: row for row in result["rows"] if row["name"] == "quality_gate"
    }
    assert quality["claude_code"]["events"] == ["PostToolUse", "PreToolUse", "Stop"]
    assert quality["claude_code"]["authority"] == {
        "PostToolUse": "block", "PreToolUse": "block", "Stop": "block",
    }
    assert quality["opencode"]["authority"] == {
        "PostToolUse": "notify", "PreToolUse": "block", "Stop": "notify",
    }


def test_dump_is_deterministic(tmp_path):
    assert dump_pipeline(str(tmp_path)) == dump_pipeline(str(tmp_path))


def test_pipeline_cli_json_matches_dump(tmp_path, capsys):
    from fettle.cli import cmd_pipeline

    cmd_pipeline(Namespace(root=str(tmp_path), json=True))

    assert json.loads(capsys.readouterr().out) == dump_pipeline(str(tmp_path))


def test_pipeline_cli_text_has_host_and_provenance(tmp_path, capsys):
    from fettle.cli import cmd_pipeline

    cmd_pipeline(Namespace(root=str(tmp_path), json=False))

    lines = capsys.readouterr().out.splitlines()
    quality = next(
        line for line in lines
        if "quality_gate" in line and "claude_code" in line
    )
    assert "PostToolUse,PreToolUse,Stop" in quality
    assert "on" in quality
    assert "check-defined" in quality
    assert "PostToolUse=block,PreToolUse=block,Stop=block" in quality
    assert "registry:enabled_by_default" in quality
