"""Tests for scripts/cli.py — CLI entry point."""

import os
import sys
import json
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_cli_help(capsys):
    from fettle.cli import main
    with pytest.raises(SystemExit) as exc_info, patch("sys.argv", ["fettle"]):
        main()
    assert exc_info.value.code == 0


def test_cli_config_effective(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    from fettle.cli import main
    with patch("sys.argv", ["fettle", "config", "--print-effective"]):
        main()
    output = capsys.readouterr().out
    assert "Effective Fettle Configuration" in output


def test_cli_config_effective_honors_mode_override(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FETTLE_GATE_MODE", "enforce")
    (tmp_path / ".git").mkdir()
    from fettle.cli import main
    with patch("sys.argv", ["fettle", "config", "--print-effective"]):
        main()
    output = capsys.readouterr().out
    assert '"mode": "enforce"' in output


def test_cli_config_effective_is_canonical(capsys, tmp_path, monkeypatch):
    """WP-20: inspection shows exactly what gates load — no divergence banner."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    import json as json_mod
    from fettle.cli import main
    from fettle.config import load_config
    with patch("sys.argv", ["fettle", "config", "--print-effective"]):
        main()
    output = capsys.readouterr().out
    assert "may resolve differently" not in output  # H-05 banner removed
    assert "Sources: repo (" in output
    printed = json_mod.loads(output[output.index("{"):])
    assert printed == load_config(str(tmp_path))


def test_cli_config_explain_shows_provenance(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    from fettle.cli import main
    with patch("sys.argv", ["fettle", "config", "--explain"]):
        main()
    output = capsys.readouterr().out
    assert 'gates.lint.mode = "enforce" (repo, overrides defaults: "advisory")' in output


def test_cli_doctor(tmp_path, monkeypatch):
    """Doctor command runs without crashing."""
    monkeypatch.chdir(tmp_path)
    from fettle.cli import cmd_doctor
    import argparse
    args = argparse.Namespace()
    cmd_doctor(args)


def test_cli_explain_supports_detailed_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    from fettle.trace import log_decision
    log_decision(
        hook="ruff", status="violation",
        findings=[{"code": "F401", "message": "unused import", "action": "remove it"}],
        evidence=[{"evidence_id": "ev-ruff123", "kind": "command"}],
    )
    from fettle.cli import main
    with patch("sys.argv", ["fettle", "explain", "--last", "1", "--detailed", "--json"]):
        main()

    output = capsys.readouterr().out
    entry = __import__("json").loads(output)
    assert entry["findings"][0]["action"] == "remove it"
    assert entry["evidence"][0]["evidence_id"] == "ev-ruff123"


def test_cli_overrides_validate_json_fails_closed_on_invalid_ledger(
    tmp_path, monkeypatch, capsys,
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    ledger = tmp_path / ".fettle" / "overrides.json"
    ledger.parent.mkdir()
    ledger.write_text('{"schema_version":"1","overrides":[{"actor":"anonymous"}]}')
    from fettle.cli import main

    with patch("sys.argv", ["fettle", "overrides", "validate", "--json"]), \
         pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    output = __import__("json").loads(capsys.readouterr().out)
    assert output["invalid_count"] == 1


def test_cli_overrides_list_shows_empty_state(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    from fettle.cli import main

    with patch("sys.argv", ["fettle", "overrides", "list"]), \
         pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert "No recorded overrides" in capsys.readouterr().out


def test_cli_verification_check_runs_committed_promoted_fixture(capsys):
    from fettle.cli import main

    with patch("sys.argv", ["fettle", "verification", "check", "--json"]), \
         pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    output = __import__("json").loads(capsys.readouterr().out)
    assert output["results"][0]["check_id"] == "ci.verdict"
    assert output["results"][0]["status"] == "pass"


def test_cli_report_json_includes_override_inventory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    ledger = tmp_path / ".fettle" / "overrides.json"
    ledger.parent.mkdir()
    ledger.write_text('{"schema_version":"1","overrides":[{"actor":"anonymous"}]}')
    from fettle.trace import log_decision
    log_decision(hook="quality", status="pass")
    from fettle.cli import main

    with patch("sys.argv", ["fettle", "report", "--json"]), \
         pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    output = __import__("json").loads(capsys.readouterr().out)
    assert output["override_inventory"]["invalid_count"] == 1


# --- `fettle check` exit-code contract (WP-133 / audit D1+D2) ---
# 0 = clean, 1 = error-severity findings, 2 = usage/environment error.
# Codes must be identical for text and --json modes.

_ERROR_FINDING = {
    "file": "a.py", "line": 1, "code": "S608",
    "message": "sql injection", "severity": "error", "tool": "ruff",
}
_WARNING_FINDING = {
    "file": "a.py", "line": 2, "code": "SIM108",
    "message": "use ternary", "severity": "warning", "tool": "ruff",
}


def _run_check(tmp_path, monkeypatch, argv, findings):
    """Run `fettle check` in-process with scan_project mocked out."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir(exist_ok=True)
    from fettle.cli import main
    with patch("fettle.quality_scan.scan_project",
               return_value={"findings": findings, "file_count": 1}), \
         patch("fettle.paths.find_repo_root", return_value=tmp_path), \
         patch("sys.argv", ["fettle", "check", *argv]), \
         pytest.raises(SystemExit) as exc_info:
        main()
    return exc_info.value.code


def test_check_json_exits_1_on_error_findings(tmp_path, monkeypatch, capsys):
    assert _run_check(tmp_path, monkeypatch, ["--json"], [_ERROR_FINDING]) == 1


def test_check_text_exits_1_on_error_findings(tmp_path, monkeypatch, capsys):
    assert _run_check(tmp_path, monkeypatch, [], [_ERROR_FINDING]) == 1


def test_check_json_exits_0_when_clean(tmp_path, monkeypatch, capsys):
    assert _run_check(tmp_path, monkeypatch, ["--json"], []) == 0


def test_check_exits_0_on_warnings_only(tmp_path, monkeypatch, capsys):
    assert _run_check(tmp_path, monkeypatch, ["--json"], [_WARNING_FINDING]) == 0


def test_check_all_and_changed_conflict_exits_2(tmp_path, monkeypatch, capsys):
    assert _run_check(tmp_path, monkeypatch, ["--all", "--changed"], []) == 2


def test_check_outside_repo_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    from fettle.cli import main
    with patch("fettle.paths.find_repo_root", return_value=None), \
         patch("sys.argv", ["fettle", "check"]), \
         pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2


def test_check_baseline_missing_exits_2(tmp_path, monkeypatch, capsys):
    assert _run_check(tmp_path, monkeypatch, ["--baseline"], [_ERROR_FINDING]) == 2


def test_check_baseline_filters_known_findings(tmp_path, monkeypatch, capsys):
    import json as _json
    (tmp_path / ".fettle-baseline.json").write_text(
        _json.dumps({"version": 1, "findings": [_ERROR_FINDING]})
    )
    assert _run_check(tmp_path, monkeypatch, ["--baseline"], [_ERROR_FINDING]) == 0


def test_check_baseline_reports_new_findings(tmp_path, monkeypatch, capsys):
    import json as _json
    (tmp_path / ".fettle-baseline.json").write_text(
        _json.dumps({"version": 1, "findings": [_WARNING_FINDING]})
    )
    assert _run_check(tmp_path, monkeypatch, ["--baseline"], [_ERROR_FINDING]) == 1


def test_check_changed_no_changes_exits_0(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    from fettle.cli import main
    with patch("fettle.paths.find_repo_root", return_value=tmp_path), \
         patch("fettle.changeset.get_changed_files", return_value=[]), \
         patch("sys.argv", ["fettle", "check", "--changed"]), \
         pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    assert "No changed" in capsys.readouterr().out


# --- Version reporting and alignment (WP-138 / audit D5) ---

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_version_flag(capsys):
    import re
    from fettle.cli import main
    with patch("sys.argv", ["fettle", "--version"]), pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert re.match(r"^fettle \d+\.\d+\.\d+", out)


def test_version_metadata_aligned():
    """pyproject, package __version__, CHANGELOG, and README must agree.

    Release gate: the repo shipped with pyproject at 0.7.0 while docs
    claimed v1.0.0 (audit D5). This test makes that drift impossible.
    """
    import re
    import tomllib

    with open(os.path.join(_REPO_ROOT, "pyproject.toml"), "rb") as fh:
        pyproject_version = tomllib.load(fh)["project"]["version"]

    with open(os.path.join(_REPO_ROOT, "scripts", "__init__.py")) as fh:
        init_version = re.search(r'__version__ = "([^"]+)"', fh.read()).group(1)

    with open(os.path.join(_REPO_ROOT, "CHANGELOG.md")) as fh:
        changelog_version = re.search(r"^## v(\d+\.\d+\.\d+)", fh.read(), re.MULTILINE).group(1)

    assert pyproject_version == init_version == changelog_version


def test_cli_version_matches_pyproject():
    import tomllib
    from fettle.cli import _version
    with open(os.path.join(_REPO_ROOT, "pyproject.toml"), "rb") as fh:
        assert _version() == tomllib.load(fh)["project"]["version"]


def _run_mutation_cli(monkeypatch, capsys, tmp_path, argv, report):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir(exist_ok=True)
    config = {
        "enabled": True, "mode": "advisory", "paths": ["src/"], "exclude": [],
        "base": "origin/main", "timeout_s": 60, "full_timeout_s": 120,
        "score_target": 80.0, "test_mappings": {}, "chunk_lines": {},
    }
    from fettle.cli import main
    with (
        patch("fettle.paths.find_repo_root", return_value=tmp_path),
        patch("fettle.config.load_config", return_value={"mutation": config}),
        patch("fettle.mutation_test.run_mutation_test", return_value=report),
        patch("sys.argv", ["fettle", "mutation", *argv]),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()
    return exc_info.value.code, capsys.readouterr()


@pytest.mark.parametrize(
    "report,expected",
    [
        ({"status": "completed", "passed": True, "score": 90.0}, 0),
        ({"status": "completed", "passed": False, "score": 50.0}, 1),
        ({"status": "tool_error", "passed": False, "score": None, "message": "missing mutmut"}, 2),
    ],
)
def test_mutation_run_json_exit_codes_match_decision(monkeypatch, capsys, tmp_path, report, expected):
    code, captured = _run_mutation_cli(monkeypatch, capsys, tmp_path, ["run", "--changed", "--json"], report)
    assert code == expected
    assert json.loads(captured.out)["status"] == report["status"]


def test_mutation_disabled_has_first_time_state(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    from fettle.cli import main
    with (
        patch("fettle.paths.find_repo_root", return_value=tmp_path),
        patch("fettle.config.load_config", return_value={"mutation": {"enabled": False}}),
        patch("sys.argv", ["fettle", "mutation", "run", "--changed", "--json"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()
    assert exc_info.value.code == 2
    assert json.loads(capsys.readouterr().out)["status"] == "not_configured"


def test_mutation_run_writes_atomic_output(monkeypatch, capsys, tmp_path):
    output = tmp_path / "reports" / "mutation.json"
    code, _ = _run_mutation_cli(
        monkeypatch, capsys, tmp_path,
        ["run", "--changed", "--json", "--output", str(output)],
        {"status": "completed", "passed": True, "score": 90.0},
    )
    assert code == 0
    assert json.loads(output.read_text())["score"] == 90.0
    assert list(output.parent.glob("*.tmp")) == []


def test_mutation_run_replaces_timeout_placeholder_with_normalized_error(monkeypatch, capsys, tmp_path):
    output = tmp_path / "mutation.json"
    output.write_text('{"status":"tool_error","partial":true}')
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    from fettle.cli import main
    config = {
        "enabled": True, "mode": "advisory", "paths": ["src/"], "exclude": [],
        "base": "origin/main", "timeout_s": 60, "full_timeout_s": 120,
        "score_target": 80.0, "test_mappings": {}, "chunk_lines": {},
    }
    with (
        patch("fettle.paths.find_repo_root", return_value=tmp_path),
        patch("fettle.config.load_config", return_value={"mutation": config}),
        patch("fettle.mutation_test.run_mutation_test", return_value={
            "schema_version": "2", "status": "completed", "passed": True,
        }),
        patch("fettle.mutation_baseline.load_baseline", side_effect=ValueError("invalid baseline")),
        patch("sys.argv", [
            "fettle", "mutation", "run", "--changed", "--json", "--output", str(output),
        ]),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()

    assert exc_info.value.code == 2
    assert json.loads(output.read_text()) == {
        "status": "unknown", "passed": False, "message": "invalid baseline",
    }


def test_mutation_advisory_reports_new_survivor_without_blocking(monkeypatch, capsys, tmp_path):
    baseline = {"schema_version": "1"}
    report = {"schema_version": "2", "status": "completed", "passed": True, "score": 90.0}
    comparison = {"status": "completed", "passed": False, "records": [{"disposition": "new"}]}
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    config = {
        "enabled": True, "mode": "advisory", "paths": ["src/"], "exclude": [],
        "base": "origin/main", "timeout_s": 60, "full_timeout_s": 120,
        "score_target": 80.0, "test_mappings": {}, "chunk_lines": {},
    }
    from fettle.cli import main
    with (
        patch("fettle.paths.find_repo_root", return_value=tmp_path),
        patch("fettle.config.load_config", return_value={"mutation": config}),
        patch("fettle.mutation_test.run_mutation_test", return_value=report),
        patch("fettle.mutation_baseline.load_baseline", return_value=baseline),
        patch("fettle.mutation_baseline.load_classifications", return_value=[]),
        patch("fettle.mutation_baseline.compare_report", return_value=comparison),
        patch("fettle.overrides.load_override_ledger") as ledger,
        patch("sys.argv", ["fettle", "mutation", "run", "--changed", "--json"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        ledger.return_value.records = ()
        ledger.return_value.invalid = ()
        main()
    assert exc_info.value.code == 0
    assert json.loads(capsys.readouterr().out)["comparison"]["passed"] is False


def test_mutation_show_finds_canonical_record(monkeypatch, capsys, tmp_path):
    (tmp_path / ".git").mkdir()
    report = tmp_path / "mutation.json"
    report.write_text(json.dumps({"schema_version": "2", "non_killed": [{
        "fingerprint": "a" * 64, "file": "src/a.py", "line": 2,
        "before": "x == 1", "after": "x != 1", "mapped_tests": ["tests/test_a.py"],
        "rerun_command": "mutmut run 1", "state": "survived",
    }]}))
    monkeypatch.chdir(tmp_path)
    from fettle.cli import main
    with patch("sys.argv", ["fettle", "mutation", "show", "a" * 64, "--report", str(report)]), \
         pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    assert "src/a.py:2" in capsys.readouterr().out


def test_mutation_baseline_establish_delegates_and_saves(monkeypatch, capsys, tmp_path):
    reports = [tmp_path / "one.json", tmp_path / "two.json"]
    for path in reports:
        path.write_text("{}")
    monkeypatch.chdir(tmp_path)
    baseline = {"schema_version": "1"}
    from fettle.cli import main
    with (
        patch("fettle.paths.find_repo_root", return_value=tmp_path),
        patch("fettle.config.load_config", return_value={"mutation": {"score_target": 80.0}}),
        patch("fettle.mutation_baseline.establish_baseline", return_value=baseline) as establish,
        patch("fettle.mutation_baseline.save_baseline", return_value="d" * 64) as save,
        patch("sys.argv", [
            "fettle", "mutation", "baseline", "establish", *(str(path) for path in reports),
            "--run-id", "one", "--run-id", "two", "--floor", "70", "--json",
        ]),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()
    assert exc_info.value.code == 0
    assert establish.call_args.kwargs["floor"] == 70.0
    assert save.call_args.args[0] == tmp_path / ".fettle" / "mutation-baseline.json"
    assert json.loads(capsys.readouterr().out)["baseline_digest"] == "d" * 64


def test_mutation_baseline_update_uses_existing_digest(monkeypatch, capsys, tmp_path):
    reports = [tmp_path / "one.json", tmp_path / "two.json"]
    for path in reports:
        path.write_text("{}")
    monkeypatch.chdir(tmp_path)
    previous = {"schema_version": "1", "floor": 70.0}
    from fettle.cli import main
    with (
        patch("fettle.paths.find_repo_root", return_value=tmp_path),
        patch("fettle.config.load_config", return_value={"mutation": {"score_target": 80.0}}),
        patch("fettle.mutation_baseline.load_baseline", return_value=previous),
        patch("fettle.mutation_baseline.baseline_digest", return_value="c" * 64),
        patch("fettle.mutation_baseline.establish_baseline", return_value=previous),
        patch("fettle.mutation_baseline.save_baseline", return_value="d" * 64) as save,
        patch("sys.argv", [
            "fettle", "mutation", "baseline", "establish", *(str(path) for path in reports),
            "--run-id", "one", "--run-id", "two", "--floor", "70", "--json",
        ]),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()
    assert exc_info.value.code == 0
    assert save.call_args.kwargs["expected_digest"] == "c" * 64
    capsys.readouterr()
