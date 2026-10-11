"""Tests for scripts/cli.py — CLI entry point."""

import os
import sys
import json
import subprocess
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


@pytest.fixture
def uat_cli_context(tmp_path):
    from argparse import Namespace

    arguments = Namespace(uat_action="run", contract=None, approve_contract=None,
                          proposal=None, yes=False, surface="cli", json=True)
    config = {"uat": {"enabled": True}}
    with patch("fettle.paths.find_repo_root", return_value=tmp_path) as root_probe, \
            patch("fettle.config.load_config", return_value=config) as load:
        yield arguments, config, root_probe, load


@pytest.mark.parametrize("error", [OSError("unreadable"), TypeError("type"), ValueError("policy")])
def test_uat_configuration_errors_fail_closed(uat_cli_context, capsys, error):
    from fettle.cli import cmd_uat

    arguments, _, _, load = uat_cli_context
    load.side_effect = error
    with pytest.raises(SystemExit) as exit_info:
        cmd_uat(arguments)
    assert exit_info.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == f"Error: invalid UAT configuration: {error}; repair policy and retry\n"


def test_uat_requires_repository(uat_cli_context, capsys):
    from fettle.cli import cmd_uat

    arguments, _, root_probe, load = uat_cli_context
    root_probe.return_value = None
    with pytest.raises(SystemExit) as exit_info:
        cmd_uat(arguments)
    assert exit_info.value.code == 2
    load.assert_not_called()
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "Error: not inside a repository (no .git or .fettle.toml found)\n"


@pytest.mark.parametrize("contract,approval,proposal,message", [
    (None, None, "proposal.json", "--proposal requires a separately approved --contract"),
    (None, "digest", None, "--contract and --approve-contract are required together for capture"),
    ("contract.json", None, None, "--contract and --approve-contract are required together for capture"),
])
def test_uat_capture_requires_paired_approval(
    uat_cli_context, capsys, contract, approval, proposal, message,
):
    from fettle.cli import cmd_uat

    arguments, _, _, _ = uat_cli_context
    arguments.contract, arguments.approve_contract, arguments.proposal = contract, approval, proposal
    with patch("fettle.uat.session.run_session") as run, \
            patch("fettle.uat.controller.run_contract_session") as capture, \
            pytest.raises(SystemExit) as exit_info:
        cmd_uat(arguments)
    assert exit_info.value.code == 2
    run.assert_not_called()
    capture.assert_not_called()
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == f"Error: {message}\n"


@pytest.mark.parametrize("contract,status,worktree,error,checkpoint,rec_error,exit_code,reconciled", [
    (False, "completed", "tree", "", {"acceptance_complete": True}, "", 0, True),
    (False, "completed", "tree", "", {}, "", 1, True),
    (False, "completed", "tree", "runner failed", {"acceptance_complete": True}, "", 1, True),
    (False, "completed", "tree", "", {"acceptance_complete": True}, "invalid evidence", 1, True),
    (False, "error", "tree", "runner failed", {}, "", 1, False),
    (True, "completed", "tree", "", {"acceptance_complete": True,
     "session_error": "retained diagnostic", "judgment": {"status": "completed", "findings": []}}, "", 0, True),
    (True, "error", "tree", "capture failed", {}, "", 1, True),
    (True, "error", "", "capture failed", {}, "", 1, False),
])
def test_uat_run_preserves_evidence_and_acceptance_status(
    uat_cli_context, tmp_path, capsys, contract, status, worktree, error,
    checkpoint, rec_error, exit_code, reconciled,
):
    from fettle.cli import cmd_uat
    from fettle.uat.reconcile import Verdict
    from fettle.uat.session import SessionResult

    arguments, config, _, load = uat_cli_context
    if contract:
        arguments.contract, arguments.approve_contract = "contract.json", "approved-digest"
        arguments.proposal, arguments.yes = "proposal.json", True
    result = SessionResult("session-1", "cli", worktree=worktree,
                           transcript_path="transcript.txt", scenario_ids=["feature/S1"],
                           status=status, error=error)
    verdict = Verdict("feature/S1", "CONFIRMED", "actual observation", "retained note")
    with patch("fettle.uat.session.run_session", return_value=result) as run, \
            patch("fettle.uat.controller.run_contract_session", return_value=result) as capture, \
            patch("fettle.uat.reconcile.reconcile_session", return_value=([verdict], checkpoint, rec_error)) as reconcile, \
            pytest.raises(SystemExit) as exit_info:
        cmd_uat(arguments)
    assert exit_info.value.code == exit_code
    load.assert_called_once_with(str(tmp_path), strict=True)
    if contract:
        capture.assert_called_once_with(str(tmp_path), config, "contract.json", "approved-digest",
                                        True, "cli", proposal_path="proposal.json")
        run.assert_not_called()
    else:
        run.assert_called_once_with(str(tmp_path), config, "cli", consent=False)
        capture.assert_not_called()
    if reconciled:
        reconcile.assert_called_once_with(str(tmp_path), worktree)
    else:
        reconcile.assert_not_called()
    expected = {
        "session_id": "session-1", "surface": "cli", "worktree": worktree,
        "transcript": "transcript.txt", "scenarios": ["feature/S1"], "status": status,
        "error": rec_error or error,
        "acceptance_complete": checkpoint.get("acceptance_complete", False),
        "session_error": checkpoint.get("session_error", ""),
        "judgment": checkpoint.get("judgment", {"status": "NOT_APPLICABLE", "findings": []}),
        "verdicts": [{"scenario_id": "feature/S1", "verdict": "CONFIRMED",
                      "observed": "actual observation", "note": "retained note"}] if reconciled else [],
    }
    output = capsys.readouterr()
    assert output.err == ""
    assert output.out == json.dumps(expected, indent=2) + "\n"


@pytest.mark.parametrize("checkpoint,error,exit_code", [
    ({}, "", 1),
    ({"session_id": "session-1", "acceptance_complete": True,
      "session_error": "", "judgment": {"status": "completed", "findings": []}}, "", 0),
    ({"session_id": "session-1", "acceptance_complete": False,
      "session_error": "incomplete evidence"}, "", 1),
    ({}, "missing evidence", 2),
])
@pytest.mark.parametrize("json_output", [True, False])
def test_uat_report_preserves_verdict_and_failure(
    uat_cli_context, tmp_path, capsys, checkpoint, error, exit_code, json_output,
):
    from fettle.cli import cmd_uat
    from fettle.uat.reconcile import Verdict

    arguments, _, _, _ = uat_cli_context
    arguments.uat_action, arguments.worktree, arguments.json = "report", "session-tree", json_output
    verdict = Verdict("feature/S1", "BLOCKED", "permission denied", "needs approval")
    with patch("fettle.uat.reconcile.reconcile_session", return_value=([verdict], checkpoint, error)) as reconcile, \
            patch("fettle.uat.reconcile.format_verdicts", return_value="formatted verdict") as render, \
            pytest.raises(SystemExit) as exit_info:
        cmd_uat(arguments)
    reconcile.assert_called_once_with(str(tmp_path), "session-tree")
    assert exit_info.value.code == exit_code
    output = capsys.readouterr()
    if error:
        assert output.out == ""
        assert output.err == "Error: missing evidence\n"
        render.assert_not_called()
    elif json_output:
        expected = {
            "session_id": checkpoint.get("session_id", ""),
            "acceptance_complete": checkpoint.get("acceptance_complete", False),
            "session_error": checkpoint.get("session_error", ""),
            "judgment": checkpoint.get("judgment", {"status": "NOT_APPLICABLE", "findings": []}),
            "verdicts": [{"scenario_id": "feature/S1", "verdict": "BLOCKED",
                          "observed": "permission denied", "note": "needs approval"}],
        }
        assert output.out == json.dumps(expected, indent=2) + "\n"
        assert output.err == ""
        render.assert_not_called()
    else:
        expected = "formatted verdict\n"
        if checkpoint.get("session_error"):
            expected += "  session: incomplete evidence\n"
        assert output.out == expected
        assert output.err == ""
        render.assert_called_once_with([verdict])


@pytest.mark.parametrize("judgment,diagnostic", [
    ({}, ""),
    ({"status": "NOT_APPLICABLE"}, ""),
    ({"status": "completed"}, ""),
    ({"status": "tool_error", "error": "judge unavailable"}, "  judgment: tool_error: judge unavailable\n"),
    ({"status": "tool_error"}, "  judgment: tool_error: \n"),
    ({"status": "completed", "findings": [{"id": "finding-1"}]},
     "  judgment: 1 finding(s); operator attestation required\n"),
])
def test_uat_human_run_preserves_diagnostics(uat_cli_context, capsys, judgment, diagnostic):
    from fettle.cli import cmd_uat
    from fettle.uat.reconcile import Verdict
    from fettle.uat.session import SessionResult

    arguments, _, _, _ = uat_cli_context
    arguments.json = False
    result = SessionResult("session-1", "api", worktree="session-tree",
                           transcript_path="session-transcript", status="completed", error="runner failed")
    verdicts = [Verdict("feature/S1", "BLOCKED")]
    with patch("fettle.uat.session.run_session", return_value=result), \
            patch("fettle.uat.reconcile.reconcile_session", return_value=(verdicts, {"judgment": judgment}, "")), \
            patch("fettle.uat.reconcile.format_verdicts", return_value="formatted verdict") as render, \
            pytest.raises(SystemExit) as exit_info:
        cmd_uat(arguments)
    assert exit_info.value.code == 1
    render.assert_called_once_with(verdicts)
    output = capsys.readouterr()
    assert output.out == ("UAT session session-1 on 'api': completed\n"
                          "  worktree:   session-tree\n"
                          "  transcript: session-transcript\n"
                          "formatted verdict\n" + diagnostic)
    assert output.err == "  error: runner failed\n"


@pytest.mark.parametrize("action", ["manual", "attest"])
@pytest.mark.parametrize("failure", [None, "exception", "returned"])
@pytest.mark.parametrize("operator", ["operator-1", None])
def test_uat_manual_actions_preserve_operator_evidence(
    uat_cli_context, tmp_path, capsys, monkeypatch, action, failure, operator,
):
    from fettle.cli import cmd_uat

    arguments, _, _, _ = uat_cli_context
    arguments.uat_action = action
    arguments.scenario_id, arguments.outcome, arguments.observed = "feature/S1", "matches", "actual output"
    if operator is None:
        monkeypatch.delenv("USER", raising=False)
    else:
        monkeypatch.setenv("USER", operator)
    scenarios = [{"id": "feature/S1"}]
    entry = {"scenario_id": "feature/S1", "outcome": "matches"}
    with patch("fettle.uat.session.collect_scenarios", return_value=scenarios) as collect, \
            patch("fettle.uat.manual.format_manual_guide", return_value="manual guide") as render, \
            patch("fettle.uat.manual.record_attestation", return_value=(entry, "invalid evidence" if failure == "returned" else "")) as record:
        if failure == "exception":
            (collect if action == "manual" else record).side_effect = ValueError("invalid evidence")
        with pytest.raises(SystemExit) as exit_info:
            cmd_uat(arguments)
    failed = failure == "exception" or action == "attest" and failure == "returned"
    assert exit_info.value.code == (2 if failed else 0)
    output = capsys.readouterr()
    assert output.err == ("Error: invalid evidence\n" if failed else "")
    if failed:
        assert output.out == ""
    elif action == "manual":
        assert output.out == "manual guide\n"
        render.assert_called_once_with(scenarios)
    else:
        assert output.out == "Recorded operator attestation for feature/S1: matches (source: operator)\n"
    if action == "manual":
        collect.assert_called_once_with(str(tmp_path))
        record.assert_not_called()
    else:
        record.assert_called_once_with(str(tmp_path), "feature/S1", "matches", "actual output", operator=operator or "")
        collect.assert_not_called()


@pytest.mark.parametrize("status,ready,exit_code", [("invalid", True, 2), ("scored", False, 1), ("scored", True, 0)])
@pytest.mark.parametrize("json_output", [True, False])
def test_uat_benchmark_requires_valid_graduation(uat_cli_context, capsys, status, ready, exit_code, json_output):
    from fettle.cli import cmd_uat

    arguments, _, _, _ = uat_cli_context
    arguments.uat_action, arguments.evidence, arguments.manifest = "benchmark", "evidence.json", "manifest.json"
    arguments.json = json_output
    scored = {"status": status, "metrics": {"agent": {"discovery_rate": 0.75, "false_verdicts": 2,
                                                    "coverage_rate": 0.5}},
              "errors": ["invalid provenance"], "graduation": {"ready": ready, "blockers": ["human parity unproven"]}}
    with patch("fettle.uat.benchmark.score_benchmark", return_value=scored) as score, \
            pytest.raises(SystemExit) as exit_info:
        cmd_uat(arguments)
    score.assert_called_once_with("evidence.json", manifest_path="manifest.json")
    assert exit_info.value.code == exit_code
    output = capsys.readouterr()
    if json_output:
        assert output.out == json.dumps(scored, indent=2) + "\n"
        assert output.err == ""
    else:
        assert output.out == (f"UAT parity benchmark: {status}\n"
                              "  agent: discovery=0.75 false-verdicts=2 coverage=0.5\n"
                              "  blocked: human parity unproven\n")
        assert output.err == "  error: invalid provenance\n"


@pytest.mark.parametrize("contract,approval,surface", [
    (None, None, "cli"), ("contract.json", "digest", "cli"),
    ("contract.json", None, "api"), (None, "digest", "web"),
])
@pytest.mark.parametrize("ready", [True, False])
@pytest.mark.parametrize("json_output", [True, False])
def test_uat_doctor_reports_capabilities(
    uat_cli_context, tmp_path, capsys, contract, approval, surface, ready, json_output,
):
    from fettle.cli import cmd_uat
    from fettle.uat.doctor import Capability

    arguments, config, _, _ = uat_cli_context
    del arguments.uat_action
    arguments.contract, arguments.approve_contract, arguments.json = contract, approval, json_output
    capabilities = [Capability(surface, ready, "runtime detail", "missing capability", "install runtime", ["manual step"])]
    surfaces = [{"name": surface, "evidence": "repository detection"}]
    with patch("fettle.uat.surfaces.resolve_surfaces", return_value=(surfaces, "")) as resolve, \
            patch("fettle.uat.doctor.probe", return_value=(capabilities, "")) as probe, \
            patch("fettle.uat.doctor.probe_contract", return_value=capabilities[0]) as capture, \
            patch("fettle.uat.doctor.format_report", return_value="capability report") as render, \
            pytest.raises(SystemExit) as exit_info:
        cmd_uat(arguments)
    assert exit_info.value.code == (0 if ready else 1)
    if contract or approval:
        capture.assert_called_once_with(str(tmp_path), config, contract or "", approval or "")
        resolve.assert_not_called()
        probe.assert_not_called()
        surfaces = [{"name": surface, "evidence": "approved read-only contract" if surface == "cli"
                     else "approved isolated controller contract"}]
    else:
        resolve.assert_called_once_with(str(tmp_path), config)
        probe.assert_called_once_with(str(tmp_path), config)
        capture.assert_not_called()
    output = capsys.readouterr()
    assert output.err == ""
    if json_output:
        expected = {"surfaces": surfaces, "capabilities": [{"surface": surface, "ready": ready,
                    "detail": "runtime detail", "why": "missing capability", "fix": "install runtime",
                    "manual": ["manual step"]}]}
        assert output.out == json.dumps(expected, indent=2) + "\n"
        render.assert_not_called()
    else:
        assert output.out == "capability report\n"
        render.assert_called_once_with(surfaces, capabilities)


@pytest.mark.parametrize("phase", ["resolve", "probe"])
def test_uat_doctor_errors_are_not_readiness(uat_cli_context, capsys, phase):
    from fettle.cli import cmd_uat

    arguments, _, _, _ = uat_cli_context
    arguments.uat_action = "doctor"
    with patch("fettle.uat.surfaces.resolve_surfaces", return_value=([], "unavailable" if phase == "resolve" else "")), \
            patch("fettle.uat.doctor.probe", return_value=([], "unavailable")) as probe, \
            pytest.raises(SystemExit) as exit_info:
        cmd_uat(arguments)
    assert exit_info.value.code == 2
    if phase == "resolve":
        probe.assert_not_called()
    else:
        probe.assert_called_once()
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "Error: unavailable\n"


def test_cli_help(capsys):
    from fettle.cli import main
    with pytest.raises(SystemExit) as exc_info, patch("sys.argv", ["fettle", "-h"]):
        main()
    assert exc_info.value.code == 0
    assert "consistency         State-consistency contracts (P53/SC2)" in capsys.readouterr().out


def test_assurance_baseline_help_lists_review_and_summary(capsys):
    from fettle.cli import main

    with pytest.raises(SystemExit) as exc_info, patch(
        "sys.argv", ["fettle", "assurance-baseline", "-h"],
    ):
        main()

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert "review" in output
    assert "summarize" in output


def test_assurance_human_output_explains_evidence(tmp_path, capsys):
    from argparse import Namespace
    from fettle.cli import cmd_assurance

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".fettle").mkdir()

    cmd_assurance(Namespace(root=str(tmp_path), json=False, policy=None))

    output = capsys.readouterr().out
    assert "Why should I trust this change?" in output
    assert "Evidence: none" in output


def test_assurance_invalid_repository_exits_two(tmp_path, capsys):
    from argparse import Namespace
    from fettle.cli import cmd_assurance

    with pytest.raises(SystemExit) as exc_info:
        cmd_assurance(Namespace(root=str(tmp_path), json=False, policy=None))

    assert exc_info.value.code == 2
    assert "Assurance unavailable:" in capsys.readouterr().out


def test_assurance_persists_canonical_record(tmp_path, capsys):
    from argparse import Namespace

    from fettle.cli import cmd_assurance
    from fettle.evidence import parse_artifact

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".fettle").mkdir()

    cmd_assurance(Namespace(root=str(tmp_path), json=True, policy=None))

    payload = json.loads(capsys.readouterr().out)
    artifact = parse_artifact(
        (tmp_path / ".fettle" / "assurance-record.evidence.json").read_bytes(),
    )
    assert artifact.payload["record"]["digest"] == payload["record"]["digest"]


def test_assurance_persistence_failure_exits_two_without_stale_record(
    tmp_path, monkeypatch, capsys,
):
    from argparse import Namespace

    from fettle.cli import cmd_assurance

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    state = tmp_path / ".fettle"
    state.mkdir()
    output = state / "assurance-record.evidence.json"
    output.write_text("old passing record", encoding="utf-8")
    monkeypatch.setattr(
        "fettle.assurance.write_evidence",
        lambda *_args: {"status": "tool_error", "message": "disk full"},
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_assurance(Namespace(root=str(tmp_path), json=False, policy=None))

    assert exc_info.value.code == 2
    assert "Assurance persistence failed: disk full" in capsys.readouterr().out
    assert not output.exists()


def test_failed_assessment_removes_stale_record(tmp_path, capsys):
    from argparse import Namespace

    from fettle.cli import cmd_assurance

    state = tmp_path / ".fettle"
    state.mkdir()
    output = state / "assurance-record.evidence.json"
    output.write_text("old passing record", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        cmd_assurance(Namespace(root=str(tmp_path), json=False, policy=None))

    assert exc_info.value.code == 2
    assert "Assurance unavailable:" in capsys.readouterr().out
    assert not output.exists()


def test_assurance_policy_json_exits_one_on_mismatch(tmp_path, capsys):
    from argparse import Namespace
    from fettle.cli import cmd_assurance

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".fettle").mkdir()
    (tmp_path / ".fettle.toml").write_text(
        '[assurance.release.production]\nsecurity = "PASS"\n', encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_assurance(Namespace(root=str(tmp_path), json=True, policy="production"))

    payload = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 1
    assert payload["policy"]["status"] == "FAIL"
    assert payload["policy"]["criteria"][0]["evidence"] == []


def test_assurance_policy_exits_two_on_configuration_error(tmp_path, capsys):
    from argparse import Namespace
    from fettle.cli import cmd_assurance

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".fettle").mkdir()
    (tmp_path / ".fettle.toml").write_text(
        '[assurance.release.production]\nconfidence = "PASS"\n', encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        cmd_assurance(Namespace(root=str(tmp_path), json=False, policy="production"))

    assert exc_info.value.code == 2
    assert "Configuration error: unknown dimension confidence" in capsys.readouterr().out


def test_assurance_policy_parser_exits_zero_on_match(tmp_path, monkeypatch, capsys):
    from fettle.cli import main

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".fettle").mkdir()
    (tmp_path / ".fettle.toml").write_text(
        '[assurance.release.local]\nauthorization = "NOT_APPLICABLE"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv", ["fettle", "assurance", "--root", str(tmp_path),
                      "--policy", "local"],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert "Release policy local: PASS" in capsys.readouterr().out


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


def test_mutation_preflight_human_output_is_actionable():
    from fettle.cli import _render_mutation

    output = _render_mutation({
        "status": "completed", "passed": True, "engine_version": "2.5.1",
        "files": ["src/app.py"], "generated": 2, "canonicalized": 2,
        "collisions": 0,
    })

    assert "Engine: mutmut 2.5.1" in output
    assert "Scope: 1 file(s)" in output
    assert "Rejected details: 0" in output
    assert "Next: fettle mutation run --changed" in output


@pytest.mark.parametrize(
    ("report", "exit_code"),
    [
        ({"status": "completed", "passed": True}, 0),
        ({"status": "completed", "passed": False}, 1),
        ({"status": "tool_error", "passed": False}, 2),
        ({"status": "unknown", "passed": False}, 2),
    ],
)
def test_mutation_exit_contract(report, exit_code):
    from fettle.cli import _mutation_exit

    assert _mutation_exit(report) == exit_code


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


@pytest.mark.parametrize("output_mode", [[], ["--json"]])
def test_check_exits_2_when_required_scanner_fails(
    tmp_path, monkeypatch, capsys, output_mode
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    from fettle.cli import main

    result = {
        "status": "tool_error",
        "tool_errors": [
            {"tool": "semgrep", "status": "tool_error", "message": "semgrep timed out"}
        ],
        "findings": [],
        "file_count": 1,
    }
    with patch("fettle.quality_scan.scan_project", return_value=result), \
         patch("fettle.paths.find_repo_root", return_value=tmp_path), \
         patch("sys.argv", ["fettle", "check", "--all", *output_mode]), \
         pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2
    output = capsys.readouterr()
    rendered = output.out if output_mode else output.err
    assert "semgrep timed out" in rendered


def test_graph_forwards_contextual_and_detailed_options():
    from fettle.cli import main

    with patch("fettle.graph_cli.main", return_value=0) as graph_main, \
         patch("sys.argv", [
             "fettle", "graph", "impact", "src/app.py", "--contextual", "--detailed",
         ]), \
         pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert graph_main.call_args.args[0] == [
        "impact", "--root", ".", "--contextual", "--detailed", "src/app.py",
    ]


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


def test_mutation_preflight_reports_readiness_and_writes_output(monkeypatch, capsys, tmp_path):
    output = tmp_path / "preflight.json"
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    config = {"enabled": True, "paths": ["src/"], "exclude": [], "test_mappings": {}}
    report = {
        "status": "completed", "passed": True, "engine_version": "2.5.1",
        "generated": 12, "canonicalized": 12, "collisions": 0,
    }
    from fettle.cli import main
    with (
        patch("fettle.paths.find_repo_root", return_value=tmp_path),
        patch("fettle.config.load_config", return_value={"mutation": config}),
        patch("fettle.mutation_test.run_mutation_preflight", return_value=report) as preflight,
        patch("sys.argv", ["fettle", "mutation", "preflight", "--all", "--json", "--output", str(output)]),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()

    assert exc_info.value.code == 0
    preflight.assert_called_once_with(str(tmp_path), config)
    assert json.loads(output.read_text()) == report
    assert json.loads(capsys.readouterr().out) == report


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


def test_mutation_status_compares_retained_report_with_baseline(monkeypatch, capsys, tmp_path):
    report_path = tmp_path / "mutation.json"
    report = {"schema_version": "2", "status": "completed", "passed": True}
    report_path.write_text(json.dumps(report))
    baseline = {"schema_version": "1"}
    comparison = {"status": "completed", "passed": True, "records": []}
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    from fettle.cli import main
    with (
        patch("fettle.paths.find_repo_root", return_value=tmp_path),
        patch("fettle.config.load_config", return_value={"mutation": {"mode": "advisory"}}),
        patch("fettle.mutation_baseline.load_baseline", return_value=baseline),
        patch("fettle.mutation_baseline.load_classifications", return_value=[]),
        patch("fettle.mutation_baseline.compare_report", return_value=comparison),
        patch("fettle.overrides.load_override_ledger") as ledger,
        patch("sys.argv", ["fettle", "mutation", "status", "--report", str(report_path), "--json"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        ledger.return_value.records = ()
        ledger.return_value.invalid = ()
        main()

    assert exc_info.value.code == 0
    assert json.loads(capsys.readouterr().out)["comparison"] == comparison


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


def _run_consistency_cli(argv):
    from fettle.cli import main

    with patch("sys.argv", ["fettle", "consistency", *argv]), \
         pytest.raises(SystemExit) as exc_info:
        main()
    return exc_info.value.code


def test_consistency_init_creates_template_and_protects_existing_file(tmp_path, capsys):
    target = tmp_path / "specs" / "account-sync.md"

    assert _run_consistency_cli(["init", "--root", str(tmp_path), "--id", "account-sync"]) == 0
    assert target.read_text(encoding="utf-8").startswith("---\nfettle-consistency: v1\n")
    assert capsys.readouterr().out == (
        f"Created: {target}\n"
        "Fill in the placeholders and run `fettle consistency lint` to validate.\n"
    )

    target.write_text("keep me", encoding="utf-8")
    assert _run_consistency_cli(["init", "--root", str(tmp_path), "--id", "account-sync"]) == 1
    assert target.read_text(encoding="utf-8") == "keep me"
    assert capsys.readouterr().out == f"Already exists: {target} — use --force to overwrite\n"

    assert _run_consistency_cli([
        "init", "--root", str(tmp_path), "--id", "account-sync", "--force",
    ]) == 0
    assert "fettle-consistency: v1" in target.read_text(encoding="utf-8")

    assert _run_consistency_cli(["init", "--root", str(tmp_path), "--id", "second"]) == 0
    assert (tmp_path / "specs" / "second.md").is_file()


def test_consistency_init_uses_defaults_from_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert _run_consistency_cli(["init"]) == 0
    assert (tmp_path / "specs" / "new-contract.md").is_file()


def test_consistency_init_creates_missing_root(tmp_path):
    root = tmp_path / "missing" / "root"

    assert _run_consistency_cli(["init", "--root", str(root)]) == 0
    assert (root / "specs" / "new-contract.md").is_file()


def test_consistency_requires_an_action(capsys):
    assert _run_consistency_cli([]) == 2
    assert "the following arguments are required: consistency_action" in capsys.readouterr().err


def test_consistency_help_describes_commands(capsys):
    assert _run_consistency_cli(["--help"]) == 0
    assert capsys.readouterr().out == """\
usage: fettle consistency [-h] {init,lint,list,run} ...

positional arguments:
  {init,lint,list,run}
    init                Create a new contract from template
    lint                Validate all contracts
    list                List contracts
    run                 Run selected contracts

options:
  -h, --help            show this help message and exit
"""


def test_consistency_lint_reports_valid_and_invalid_contracts(tmp_path, capsys):
    valid = """\
fettle-consistency: v1
id: account-sync
scope: ["src/**"]
fact: account.name
owner: accounts
consistency: {model: immediate}
observers: [{id: api, surface: api, adapter: read_account}]
comparator: {kind: exact}
"""
    (tmp_path / "valid.md").write_text(valid, encoding="utf-8")

    assert _run_consistency_cli(["lint", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "All consistency contracts pass lint.\n"

    (tmp_path / "invalid.md").write_text("fettle-consistency: v1\nid: invalid\n", encoding="utf-8")
    assert _run_consistency_cli(["lint", "--root", str(tmp_path)]) == 1
    assert capsys.readouterr().out.startswith(
        "  [ERROR] missing required key 'fact'\n"
        "      fix: add 'fact: ...'\n"
    )


def test_consistency_lint_uses_working_directory_by_default(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "invalid.md").write_text("fettle-consistency: v1\nid: invalid\n", encoding="utf-8")

    assert _run_consistency_cli(["lint"]) == 1
    assert "missing required key 'fact'" in capsys.readouterr().out


def test_consistency_lint_ignores_contracts_in_tool_directories(tmp_path, capsys):
    for directory in (".git", ".venv", "node_modules"):
        path = tmp_path / directory
        path.mkdir()
        (path / "invalid.md").write_text("fettle-consistency: v1\n", encoding="utf-8")

    assert _run_consistency_cli(["lint", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "All consistency contracts pass lint.\n"


def test_consistency_lint_continues_after_ignored_and_unmarked_files(tmp_path, capsys):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored.md").write_text("fettle-consistency: v1\n", encoding="utf-8")
    (tmp_path / "plain.md").write_text("not a contract\n", encoding="utf-8")
    (tmp_path / "z-invalid.md").write_text("fettle-consistency: v1\nid: invalid\n", encoding="utf-8")

    assert _run_consistency_cli(["lint", "--root", str(tmp_path)]) == 1
    assert "missing required key 'fact'" in capsys.readouterr().out


def test_consistency_lint_warning_only_is_nonblocking(tmp_path, capsys):
    (tmp_path / "contract.md").write_text("fettle-consistency: v1\n", encoding="utf-8")
    from fettle.state_consistency import Finding
    warning = Finding("contract.md", 1, "WARNING", "review this", "confirm it")

    with patch("fettle.state_consistency.discover_contracts", return_value=([], [warning])):
        assert _run_consistency_cli(["lint", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "  [WARNING] review this\n      fix: confirm it\n"


def test_consistency_lint_replaces_invalid_utf8(tmp_path, capsys):
    (tmp_path / "contract.md").write_bytes(b"fettle-consistency: v1\nid: bad\xff\n")

    assert _run_consistency_cli(["lint", "--root", str(tmp_path)]) == 1
    assert "invalid id" in capsys.readouterr().out


def test_consistency_list_shows_contract_summary_and_empty_state(tmp_path, capsys):
    assert _run_consistency_cli(["list", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "No consistency contracts found.\n"

    contract = """\
fettle-consistency: v1
id: account-sync
scope: ["src/accounts/**", "src/api/**", "ignored/**"]
fact: account.name
owner: accounts
consistency: {model: eventual}
observers: [{id: api, surface: api, adapter: read_account}]
comparator: {kind: normalized}
"""
    (tmp_path / "a-not-contract.md").write_text("ordinary markdown", encoding="utf-8")
    (tmp_path / "account.md").write_text(contract, encoding="utf-8")
    (tmp_path / "broken.md").write_text("fettle-consistency: v1\nid: broken\n", encoding="utf-8")
    (tmp_path / "invalid-utf8.md").write_bytes(b"ordinary markdown\xff")

    assert _run_consistency_cli(["list", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == (
        "  account-sync                         eventual     1 observers  "
        "scope: src/accounts/**, src/api/**\n"
    )


def test_consistency_list_uses_working_directory_by_default(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "contract.md").write_text("""\
fettle-consistency: v1
id: local-contract
scope: ["src/**"]
fact: account.name
owner: accounts
consistency: {model: immediate}
observers: [{id: api, surface: api, adapter: read_account}]
comparator: {kind: exact}
""", encoding="utf-8")

    assert _run_consistency_cli(["list"]) == 0
    assert "local-contract" in capsys.readouterr().out


def test_consistency_list_json_is_stable_and_includes_source(tmp_path, capsys):
    contract = """\
fettle-consistency: v1
id: account-sync
scope: ["src/**"]
fact: account.name
owner: accounts
consistency: {model: immediate}
observers: [{id: api, surface: api, adapter: read_account}]
comparator: {kind: exact}
"""
    (tmp_path / "contract.md").write_text(contract, encoding="utf-8")

    assert _run_consistency_cli(["list", "--root", str(tmp_path), "--json"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "contracts": [{
            "id": "account-sync", "model": "immediate",
            "observers": 1, "path": "contract.md", "scope": ["src/**"],
        }],
        "status": "completed",
    }


def test_consistency_lint_executable_reports_missing_manifests_without_running(
        tmp_path, capsys):
    contract = """\
fettle-consistency: v1
id: account-sync
scope: ["src/**"]
fact: account.name
owner: accounts
consistency: {model: immediate}
mutation: {adapter: rename_account, retry_safe: false}
canonical_read: {adapter: read_account}
observers: [{id: api, surface: api, adapter: read_api}]
comparator: {kind: exact}
cleanup: {adapter: delete_account}
"""
    (tmp_path / "contract.md").write_text(contract, encoding="utf-8")

    assert _run_consistency_cli([
        "lint", "--root", str(tmp_path), "--executable", "--json",
    ]) == 1

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "config_error"
    assert any("has no manifest" in finding["message"] for finding in result["findings"])


def test_consistency_run_selects_exact_ids_and_reports_filtered_empty(
        tmp_path, capsys):
    contract = """\
fettle-consistency: v1
id: account-sync
scope: ["src/**"]
fact: account.name
owner: accounts
consistency: {model: immediate}
mutation: {adapter: mutate, retry_safe: false}
canonical_read: {adapter: read}
observers: [{id: api, surface: api, adapter: read}]
comparator: {kind: exact}
cleanup: {adapter: cleanup}
adapters:
  mutate: {kind: command, argv: [tool, mutate], timeout_s: 1, output: json-v1}
  read: {kind: command, argv: [tool, read], timeout_s: 1, output: json-v1}
  cleanup: {kind: command, argv: [tool, cleanup], timeout_s: 1, output: json-v1}
"""
    (tmp_path / "contract.md").write_text(contract, encoding="utf-8")
    completed = {"contract_id": "account-sync", "outcome": "unknown"}

    with patch("fettle.consistency_runner.execute_contract", return_value=completed) as execute:
        assert _run_consistency_cli([
            "run", "account-sync", "--root", str(tmp_path), "--json",
        ]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "results": [completed], "status": "completed",
    }
    assert execute.call_args.args[1].id == "account-sync"

    assert _run_consistency_cli([
        "run", "missing", "--root", str(tmp_path), "--json",
    ]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "not_found"
