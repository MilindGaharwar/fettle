"""Tests for fettle.uat.surfaces — surface detection."""

import json

from fettle.uat.surfaces import detect_surfaces


class TestDetectSurfaces:
    def test_cli_from_pyproject_scripts(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[project.scripts]\nmycli = \"pkg.cli:main\"\n"
        )
        surfaces = detect_surfaces(str(tmp_path))
        names = [s["name"] for s in surfaces]
        assert "cli" in names

    def test_cli_from_package_json_bin(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({"bin": {"myapp": "./index.js"}}))
        surfaces = detect_surfaces(str(tmp_path))
        names = [s["name"] for s in surfaces]
        assert "cli" in names

    def test_web_from_react_dep(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "dependencies": {"react": "^18.0.0"}
        }))
        surfaces = detect_surfaces(str(tmp_path))
        names = [s["name"] for s in surfaces]
        assert "web" in names

    def test_api_from_express(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "dependencies": {"express": "^4.0.0"}
        }))
        surfaces = detect_surfaces(str(tmp_path))
        names = [s["name"] for s in surfaces]
        assert "api" in names

    def test_api_from_fastapi(self, tmp_path):
        src = tmp_path / "app.py"
        src.write_text("from fastapi import FastAPI\napp = FastAPI()\n")
        surfaces = detect_surfaces(str(tmp_path))
        names = [s["name"] for s in surfaces]
        assert "api" in names

    def test_empty_project_no_surfaces(self, tmp_path):
        surfaces = detect_surfaces(str(tmp_path))
        assert surfaces == []

    def test_evidence_field_present(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project.scripts]\nx = \"x:main\"\n")
        surfaces = detect_surfaces(str(tmp_path))
        assert all("evidence" in s for s in surfaces)
