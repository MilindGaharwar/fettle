"""Item 9 contract tests — pipeline dump with per-row provenance."""

from __future__ import annotations

import subprocess

from fettle.pipeline_dump import dump_pipeline


def _init_repo_with_config(tmp_path, config_body: str) -> str:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)])
    (root / ".fettle.toml").write_text(config_body, encoding="utf-8")
    for flag in (("config", "user.email", "test@fettle.invalid"), ("config", "user.name", "t")):
        subprocess.run(["git", "-C", str(root), *flag], capture_output=True)
    return str(root)


def test_every_dispatcher_check_appears_as_a_row(tmp_path):
    from fettle.dispatcher_registry import CHECKS

    result = dump_pipeline(str(tmp_path))

    names = {r["name"] for r in result["rows"]}
    assert names == {c.name for c in CHECKS}


def test_defaults_layer_reported_when_no_repo_config(tmp_path):
    root = _init_repo_with_config(
        tmp_path, "[project]\nname = 'x'\nversion = '0'\n")

    result = dump_pipeline(root)

    quality = next(r for r in result["rows"] if r["name"] == "quality_gate")
    assert result["layers"][0]["name"] == "defaults"
    assert quality["source"] == "defaults"


def test_repo_layer_overrides_source_and_mode(tmp_path):
    root = _init_repo_with_config(tmp_path, """\
[gates.quality_gate]
enabled = true
mode = "enforce"
""")

    result = dump_pipeline(root)

    quality = next(r for r in result["rows"] if r["name"] == "quality_gate")
    assert quality["source"] != "defaults"
    assert quality["mode"] == "enforce"
    assert quality["enabled"] is True


def test_dump_is_deterministic_and_modes_are_valid(tmp_path):
    first = dump_pipeline(str(tmp_path))
    second = dump_pipeline(str(tmp_path))

    assert first == second
    valid = {"advisory", "enforce", "strict", "off"}
    assert all(r["mode"] in valid for r in first["rows"])


def test_events_match_check_spec(tmp_path):
    from fettle.dispatcher_registry import CHECKS

    spec_events = {c.name: sorted(c.events) for c in CHECKS}
    result = dump_pipeline(str(tmp_path))

    for row in result["rows"]:
        assert row["events"] == spec_events[row["name"]]
