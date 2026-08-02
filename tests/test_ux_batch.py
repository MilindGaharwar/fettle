"""Tests for the v1.6 slice D UX batch: bare `fettle` dashboard,
`doctor --fix` (mechanical only), explain pointer on blocks."""

import sys
from types import SimpleNamespace

import pytest

from fettle.dispatcher_aggregate import Aggregator
from fettle.dispatcher_types import CheckResult


# ─── bare `fettle` dashboard ─────────────────────────────────────────────────


def _run_cli(monkeypatch, argv):
    from fettle import cli
    monkeypatch.setattr(sys, "argv", ["fettle", *argv])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    return exc.value.code


def test_bare_fettle_in_repo_shows_dashboard(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    import fettle.paths
    monkeypatch.setattr(fettle.paths, "find_repo_root", lambda: tmp_path)
    code = _run_cli(monkeypatch, [])
    out = capsys.readouterr().out
    assert code == 0
    assert "fettle brief" in out          # dashboard, not manpage
    assert "fettle -h — commands" in out  # discoverability footer
    assert "usage:" not in out


def test_bare_fettle_outside_repo_prints_help(monkeypatch, capsys):
    import fettle.paths
    monkeypatch.setattr(fettle.paths, "find_repo_root", lambda: None)
    code = _run_cli(monkeypatch, [])
    out = capsys.readouterr().out
    assert code == 0
    assert "usage:" in out


# ─── doctor --fix ────────────────────────────────────────────────────────────


def test_fix_installs_declared_unwired_hooks():
    from fettle.doctor import apply_mechanical_fixes
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    checks = [
        {"name": "commit-guards", "required": False, "ok": False, "detail": "d"},
        {"name": "push-guards", "required": False, "ok": True, "detail": "d"},
        {"name": "config", "required": False, "ok": False, "detail": "invalid"},
    ]
    log = apply_mechanical_fixes(checks, run=fake_run, which=lambda n: "/usr/bin/pre-commit")
    assert log == ["fixed: installed pre-commit hooks"]
    assert calls == [["pre-commit", "install", "--hook-type", "pre-commit"]]
    # config failure needs judgement — never auto-fixed


def test_fix_reports_missing_binary_instead_of_failing():
    from fettle.doctor import apply_mechanical_fixes
    checks = [{"name": "push-guards", "required": False, "ok": False, "detail": "d"}]
    log = apply_mechanical_fixes(checks, run=None, which=lambda n: None)
    assert len(log) == 1 and "pre-commit binary not found" in log[0]


def test_fix_noop_when_nothing_fixable():
    from fettle.doctor import apply_mechanical_fixes
    checks = [{"name": "commit-guards", "required": False, "ok": True, "detail": "d"}]
    assert apply_mechanical_fixes(checks, which=lambda n: "/x") == []


def test_fix_surfaces_installer_failure():
    from fettle.doctor import apply_mechanical_fixes

    def fake_run(cmd, **kw):
        return SimpleNamespace(returncode=1, stdout="", stderr="boom: no git dir")

    checks = [{"name": "commit-guards", "required": False, "ok": False, "detail": "d"}]
    log = apply_mechanical_fixes(checks, run=fake_run, which=lambda n: "/x")
    assert log == ["fix failed for pre-commit: boom: no git dir"]


# ─── explain pointer on blocks ───────────────────────────────────────────────


def test_block_reason_points_at_fettle_explain():
    agg = Aggregator(total_budget_ms=400, hook_event_name="PostToolUse")
    agg.add_result("gate", CheckResult.block("Bad edit"), 5)
    output, code = agg.finish()
    assert code == 2
    assert output["reason"].startswith("Bad edit")
    assert "fettle explain" in output["reason"]


def test_pointer_not_duplicated_when_message_already_has_it():
    agg = Aggregator(total_budget_ms=400, hook_event_name="Stop")
    agg.add_result("gate", CheckResult.block("Nope — run fettle explain"), 5)
    output, _ = agg.finish()
    assert output["reason"].count("fettle explain") == 1


def test_advisories_carry_no_pointer():
    agg = Aggregator(total_budget_ms=400, hook_event_name="Stop")
    agg.add_result("gate", CheckResult.advisory("heads up"), 5)
    output, code = agg.finish()
    assert code == 0
    assert "fettle explain" not in output.get("systemMessage", "")
