"""Tests for fettle.uat surface detection + capability probe (Stage 5, S5.1)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from fettle.uat.doctor import format_report, probe
from fettle.uat.surfaces import detect_surfaces, resolve_surfaces

CLI = [sys.executable, "-m", "fettle.cli"]


def test_controller_unavailable_platform_is_explicitly_blocked(monkeypatch, tmp_path):
    from fettle.uat import controller
    from fettle.uat.doctor import probe_contract

    monkeypatch.setattr(controller.sys, "platform", "linux")
    capability = probe_contract(str(tmp_path), {}, "missing.json", "unapproved")
    assert not capability.ready
    assert "no unsandboxed fallback" in capability.why


def test_controller_readiness_failure_does_not_run_actions(monkeypatch, tmp_path):
    from fettle.uat import controller

    monkeypatch.setattr(controller, "capability_error", lambda: "sandbox unavailable")
    with patch("fettle.uat.controller._execute") as execute:
        result = controller.run_contract_session(str(tmp_path), {}, "missing", "invalid", True)
    assert result.status == "error"
    assert "sandbox unavailable" in result.error
    execute.assert_not_called()


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


class TestDetection:
    def test_cli_from_pyproject_scripts(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "pyproject.toml").write_text(
            "[project]\nname = \"x\"\n\n[project.scripts]\nx = \"x.cli:main\"\n")
        surfaces = detect_surfaces(str(repo))
        assert [s["name"] for s in surfaces] == ["cli"]
        assert "project.scripts" in surfaces[0]["evidence"]

    def test_cli_from_package_json_bin(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "package.json").write_text(json.dumps({"bin": {"x": "cli.js"}}))
        assert [s["name"] for s in detect_surfaces(str(repo))] == ["cli"]

    def test_api_from_express_dep(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "package.json").write_text(json.dumps(
            {"dependencies": {"express": "^4"}}))
        surfaces = detect_surfaces(str(repo))
        assert [s["name"] for s in surfaces] == ["api"]
        assert "express" in surfaces[0]["evidence"]

    def test_api_from_fastapi_marker(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
        surfaces = detect_surfaces(str(repo))
        assert [s["name"] for s in surfaces] == ["api"]
        assert "FastAPI" in surfaces[0]["evidence"]

    def test_web_from_react_dep(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "package.json").write_text(json.dumps(
            {"dependencies": {"react": "^18", "express": "^4"}}))
        names = [s["name"] for s in detect_surfaces(str(repo))]
        assert "web" in names and "api" in names  # full-stack app: both

    def test_web_from_templates_dir(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "templates").mkdir()
        assert "web" in [s["name"] for s in detect_surfaces(str(repo))]

    def test_library_fallback(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "pyproject.toml").write_text("[project]\nname = \"just-a-lib\"\n")
        assert [s["name"] for s in detect_surfaces(str(repo))] == ["library"]

    def test_nothing_detected(self, tmp_path):
        assert detect_surfaces(str(_repo(tmp_path))) == []

    def test_malformed_package_json_ignored(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "package.json").write_text("{not json")
        assert detect_surfaces(str(repo)) == []


class TestResolve:
    def test_auto_delegates_to_detection(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "templates").mkdir()
        surfaces, err = resolve_surfaces(str(repo), {"uat": {"surfaces": ["auto"]}})
        assert err == ""
        assert [s["name"] for s in surfaces] == ["web"]

    def test_explicit_list_validated(self, tmp_path):
        surfaces, err = resolve_surfaces(str(_repo(tmp_path)),
                                         {"uat": {"surfaces": ["cli", "api"]}})
        assert err == ""
        assert [s["name"] for s in surfaces] == ["cli", "api"]
        assert all("declared" in s["evidence"] for s in surfaces)

    def test_unknown_surface_errors(self, tmp_path):
        _, err = resolve_surfaces(str(_repo(tmp_path)),
                                  {"uat": {"surfaces": ["mobile"]}})
        assert "unknown surface" in err and "mobile" in err


def _cfg(**uat) -> dict:
    base = {"surfaces": ["auto"], "app_url": "", "start_command": "",
            "runner": "claude", "timeout_s": 1800, "mode": "report"}
    base.update(uat)
    return {"uat": base}


class TestProbe:
    def test_missing_startup_executable_cannot_report_ready(self, tmp_path):
        repo = _repo(tmp_path)
        with patch("fettle.runners.detect_runners", return_value={"claude": True}):
            caps, error = probe(str(repo), _cfg(surfaces=["cli"],
                                start_command="/definitely/missing/uat-app"))
        assert not error
        assert not caps[0].ready
        assert "start_command" in caps[0].why

    def test_missing_browser_runtime_cannot_report_available(self, tmp_path):
        from fettle.uat.doctor import _playwright_available

        with patch("playwright.sync_api.sync_playwright") as factory:
            factory.return_value.__enter__.return_value.chromium.executable_path = str(
                tmp_path / "absent-chromium")
            assert not _playwright_available()

    def test_ready_cli_surface(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "pyproject.toml").write_text("[project.scripts]\nx = \"x:main\"\n")
        with patch("fettle.runners.claude.shutil.which", return_value="/usr/bin/claude"):
            caps, err = probe(str(repo), _cfg())
        assert err == ""
        assert len(caps) == 1 and caps[0].ready

    def test_runner_missing_gap_has_why_fix_manual(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "pyproject.toml").write_text("[project.scripts]\nx = \"x:main\"\n")
        with patch("fettle.runners.claude.shutil.which", return_value=None):
            caps, _ = probe(str(repo), _cfg())
        assert not caps[0].ready
        assert caps[0].why and caps[0].fix and caps[0].manual  # three-part contract

    def test_web_without_playwright_gap(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "templates").mkdir()
        with patch("fettle.runners.claude.shutil.which", return_value="/usr/bin/claude"), \
             patch("fettle.uat.doctor._playwright_available", return_value=False):
            caps, _ = probe(str(repo), _cfg(app_url="http://localhost:3000"))
        web = next(c for c in caps if c.surface == "web")
        assert not web.ready
        assert "reinstall finefettle" in web.fix and "playwright install" in web.fix
        assert any("attest" in step for step in web.manual)

    def test_web_no_reachability_gap(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "templates").mkdir()
        with patch("fettle.runners.claude.shutil.which", return_value="/usr/bin/claude"), \
             patch("fettle.uat.doctor._playwright_available", return_value=True):
            caps, _ = probe(str(repo), _cfg())
        web = next(c for c in caps if c.surface == "web")
        assert not web.ready
        assert "app_url" in web.why

    def test_no_surfaces_gap_suggests_declaration(self, tmp_path):
        caps, _ = probe(str(_repo(tmp_path)), _cfg())
        assert len(caps) == 1 and not caps[0].ready
        assert "[uat]" in caps[0].fix

    def test_format_report_gap_block(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "templates").mkdir()
        with patch("fettle.runners.claude.shutil.which", return_value="/usr/bin/claude"), \
             patch("fettle.uat.doctor._playwright_available", return_value=False):
            caps, _ = probe(str(repo), _cfg(app_url="http://x"))
        surfaces, _ = resolve_surfaces(str(repo), _cfg())
        text = format_report(surfaces, caps)
        assert "✗ Cannot run UAT on the web surface" in text
        assert "Why:" in text and "Fix:" in text and "Or do it manually:" in text


class TestCLI:
    def test_corrupt_configuration_cannot_report_ready(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / ".fettle.toml").write_text("[uat")
        result = subprocess.run([*CLI, "uat", "doctor", "--json"],
                                cwd=repo, capture_output=True, text=True)
        assert result.returncode == 2
        assert "invalid UAT configuration" in result.stderr
        assert "Traceback" not in result.stderr

    def test_uat_doctor_json(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "pyproject.toml").write_text("[project.scripts]\nx = \"x:main\"\n")
        r = subprocess.run([*CLI, "uat", "doctor", "--json"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode in (0, 1)  # ready depends on claude presence on host
        data = json.loads(r.stdout)
        assert data["surfaces"][0]["name"] == "cli"
        assert "capabilities" in data

    def test_uat_doctor_exit_1_on_gap(self, tmp_path):
        repo = _repo(tmp_path)  # no surfaces at all → gap
        r = subprocess.run([*CLI, "uat", "doctor"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 1
        assert "Cannot" in r.stdout

    def test_uat_unknown_surface_exit_2(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / ".fettle.toml").write_text("[uat]\nsurfaces = [\"mobile\"]\n")
        r = subprocess.run([*CLI, "uat", "doctor"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 2
        assert "unknown surface" in r.stderr
