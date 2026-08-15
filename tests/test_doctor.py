"""Doctor self-check tests — the fail-visible contract.

Missing optional tools must be warnings (exit 0, consequence stated);
only missing REQUIRED tools may fail the check. A doctor that cries wolf
gets ignored; one that stays silent hides degraded gate coverage.
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import doctor  # noqa: E402
from fettle import doctor as package_doctor

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_DIR, "scripts", "doctor.py")


def test_missing_optional_tool_is_warning_not_failure(monkeypatch):
    real_which = doctor._which
    monkeypatch.setattr(
        doctor, "_which",
        lambda name: None if name in ("semgrep", "cargo", "shellcheck", "claude") else real_which(name),
    )
    checks = doctor.check_environment()
    by_name = {c["name"]: c for c in checks}
    for optional in ("semgrep", "cargo", "shellcheck", "claude"):
        assert by_name[optional]["ok"] is False
        assert by_name[optional]["required"] is False
        assert "skipped" in by_name[optional]["detail"] or "unavailable" in by_name[optional]["detail"]
    # Missing optionals alone must not make the environment unhealthy
    assert not [c for c in checks if c["required"] and not c["ok"]]


def test_missing_required_tool_fails(monkeypatch):
    monkeypatch.setattr(doctor, "_which", lambda name: None)
    checks = doctor.check_environment()
    required_failures = [c for c in checks if c["required"] and not c["ok"]]
    assert [c["name"] for c in required_failures] == ["ruff"]
    assert "disabled" in next(c for c in checks if c["name"] == "ruff")["detail"]


def test_json_mode_shape_and_exit_code():
    proc = subprocess.run(
        [sys.executable, SCRIPT, "--json"],
        capture_output=True, text=True, timeout=60,
    )
    data = json.loads(proc.stdout)
    assert isinstance(data["healthy"], bool)
    names = [c["name"] for c in data["checks"]]
    assert names[0] == "python"
    assert "ruff" in names
    assert proc.returncode == (0 if data["healthy"] else 1)


def test_python_check_reports_interpreter():
    checks = doctor.check_environment()
    py = checks[0]
    assert py["name"] == "python"
    assert py["ok"] is (sys.version_info >= (3, 11))
    assert sys.version.split()[0] in py["detail"]


def test_bridge_health_reports_valid_and_tampered_states(tmp_path, monkeypatch):
    from fettle import bridge

    monkeypatch.setattr(bridge, "bridge_base", lambda: tmp_path / "bridge")
    assert package_doctor.check_bridge_health() == []

    bridge.publish_bridge(dry_run=False)
    healthy = package_doctor.check_bridge_health()[0]
    assert healthy["ok"] is True

    (bridge.bridge_dir() / "opencode" / "fettle.ts").write_text("tampered")
    stale = package_doctor.check_bridge_health()[0]
    assert stale["ok"] is False
    assert "fettle init" in stale["detail"]


def test_runner_governance_recognizes_registered_hosts(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".claude" / "plugins" / "fettle").mkdir(parents=True)
    (home / ".codex").mkdir()
    (home / ".codex" / "hooks.json").write_text('{"command":"fettle"}')
    (home / ".gemini").mkdir()
    (home / ".gemini" / "settings.json").write_text('{"command":"fettle"}')
    (home / ".config" / "opencode").mkdir(parents=True)
    (home / ".config" / "opencode" / "config.json").write_text('{"plugin":"fettle"}')
    monkeypatch.setattr(package_doctor.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(package_doctor, "_which", lambda name: f"/bin/{name}")

    checks = package_doctor.check_runner_governance()

    assert len(checks) == 4
    assert all(check["ok"] for check in checks)


def test_mutation_readiness_is_informational_when_disabled(monkeypatch):
    monkeypatch.setattr("fettle.config.load_config", lambda _root: {
        "mutation": {"enabled": False},
    })

    check = package_doctor.check_mutation_readiness()[0]

    assert check == {
        "name": "mutation", "required": False, "ok": True,
        "status": "disabled",
        "detail": "disabled — enable [mutation] before running mutation preflight",
    }


def test_mutation_readiness_names_missing_tool_recovery(monkeypatch):
    monkeypatch.setattr("fettle.config.load_config", lambda _root: {
        "mutation": {"enabled": True},
    })
    monkeypatch.setattr(package_doctor, "_which", lambda _name: None)

    check = package_doctor.check_mutation_readiness()[0]

    assert check["ok"] is False
    assert check["status"] == "unavailable"
    assert "mutmut==2.5.1" in check["detail"]
    assert "requirements-mutation.txt" in check["detail"]


def test_mutation_readiness_rejects_unsupported_version(monkeypatch):
    monkeypatch.setattr("fettle.config.load_config", lambda _root: {
        "mutation": {"enabled": True},
    })
    monkeypatch.setattr(package_doctor, "_which", lambda _name: "/bin/mutmut")
    monkeypatch.setattr(package_doctor, "_version_of", lambda *_args: "mutmut version 3.0.0")

    check = package_doctor.check_mutation_readiness()[0]

    assert check["ok"] is False
    assert check["status"] == "unsupported"
    assert "expected 2.5.1" in check["detail"]


def test_mutation_readiness_ready_has_preflight_next_action(monkeypatch):
    monkeypatch.setattr("fettle.config.load_config", lambda _root: {
        "mutation": {"enabled": True},
    })
    monkeypatch.setattr(package_doctor, "_which", lambda _name: "/bin/mutmut")
    monkeypatch.setattr(package_doctor, "_version_of", lambda *_args: "mutmut version 2.5.1")

    check = package_doctor.check_mutation_readiness()[0]

    assert check["ok"] is True
    assert check["status"] == "ready"
    assert "fettle mutation preflight" in check["detail"]


# ─── WP-16: SYSTEM_TOOLS tier (shellcheck via brew/apt) ─────────────────────


def test_system_install_argv_prefers_brew():
    from fettle.supply_chain import system_install_argv
    argv = system_install_argv("shellcheck", which=lambda n: "/opt/homebrew/bin/brew" if n == "brew" else None)
    assert argv == ["brew", "install", "shellcheck"]


def test_system_install_argv_apt_uses_noninteractive_sudo():
    from fettle.supply_chain import system_install_argv
    argv = system_install_argv("shellcheck", which=lambda n: "/usr/bin/apt-get" if n == "apt-get" else None)
    assert argv == ["sudo", "-n", "apt-get", "install", "-y", "shellcheck"]


def test_system_install_argv_none_without_package_manager():
    from fettle.supply_chain import system_install_argv, system_install_hint
    assert system_install_argv("shellcheck", which=lambda n: None) is None
    hint = system_install_hint("shellcheck", which=lambda n: None)
    assert "shellcheck" in hint and "package manager" in hint


def test_system_install_hint_strips_sudo_n_flag():
    from fettle.supply_chain import system_install_hint
    hint = system_install_hint("shellcheck", which=lambda n: "/usr/bin/apt-get" if n == "apt-get" else None)
    assert hint == "sudo apt-get install -y shellcheck"


def test_missing_shellcheck_warn_carries_install_command(monkeypatch):
    real_which = doctor._which
    monkeypatch.setattr(
        doctor, "_which",
        lambda name: None if name == "shellcheck" else real_which(name),
    )
    checks = doctor.check_environment()
    sc = next(c for c in checks if c["name"] == "shellcheck")
    assert sc["ok"] is False and sc["required"] is False
    assert "install:" in sc["detail"]  # exact per-OS command on the warn line


def test_fix_installs_missing_system_tool():
    installed = {"done": False}

    def fake_run(cmd, **kw):
        installed["done"] = True
        assert cmd == ["brew", "install", "shellcheck"]
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def fake_which(name):
        if name == "brew":
            return "/opt/homebrew/bin/brew"
        if name == "shellcheck" and installed["done"]:
            return "/opt/homebrew/bin/shellcheck"
        return None

    checks = [{"name": "shellcheck", "required": False, "ok": False, "detail": "not on PATH"}]
    log = doctor.apply_mechanical_fixes(checks, run=fake_run, which=fake_which)
    assert log == ["fixed: installed shellcheck"]
    assert checks[0]["ok"] is True
    assert "/opt/homebrew/bin/shellcheck" in checks[0]["detail"]


def test_fix_system_tool_without_package_manager_reports_not_errors():
    checks = [{"name": "shellcheck", "required": False, "ok": False, "detail": "not on PATH"}]
    log = doctor.apply_mechanical_fixes(checks, run=None, which=lambda n: None)
    assert len(log) == 1 and log[0].startswith("cannot fix shellcheck:")
    assert checks[0]["ok"] is False  # never claim success


def test_fix_system_tool_surfaces_installer_failure():
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, "", "Error: no bottle available")

    checks = [{"name": "shellcheck", "required": False, "ok": False, "detail": "not on PATH"}]
    log = doctor.apply_mechanical_fixes(
        checks, run=fake_run,
        which=lambda n: "/opt/homebrew/bin/brew" if n == "brew" else None,
    )
    assert log == ["fix failed for shellcheck: Error: no bottle available"]
    assert checks[0]["ok"] is False


def test_install_system_tools_reports_present_tool_ok(monkeypatch):
    from fettle import init_cmd
    monkeypatch.setattr(init_cmd.shutil, "which", lambda n: f"/usr/bin/{n}")
    steps = init_cmd.install_system_tools(dry_run=False)
    assert [(s.name, s.status) for s in steps] == [("tool:shellcheck", "ok")]


def test_install_system_tools_dry_run_names_the_command(monkeypatch):
    from fettle import init_cmd
    monkeypatch.setattr(
        init_cmd.shutil, "which",
        lambda n: "/opt/homebrew/bin/brew" if n == "brew" else None,
    )
    steps = init_cmd.install_system_tools(dry_run=True)
    assert steps[0].status == "created"
    assert "brew install shellcheck" in steps[0].detail


def test_install_system_tools_no_manager_is_actionable(monkeypatch):
    from fettle import init_cmd
    monkeypatch.setattr(init_cmd.shutil, "which", lambda n: None)
    steps = init_cmd.install_system_tools(dry_run=False)
    assert steps[0].status == "action"
    assert "shellcheck" in steps[0].detail
