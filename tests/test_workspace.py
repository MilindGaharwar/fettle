"""Tests for scripts/workspace.py — WP-68: Workspace/monorepo awareness."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from workspace import (
    discover_workspaces,
    route_file_to_workspace,
)


def test_detects_multiple_workspaces(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "pyproject.toml").write_text('[project]\nname = "backend"\n')
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"name": "frontend"}')
    workspaces = discover_workspaces(str(tmp_path))
    assert len(workspaces) >= 2
    names = [w.name for w in workspaces]
    assert "backend" in names
    assert "frontend" in names


def test_routes_backend_file_to_python_workspace(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "pyproject.toml").write_text('[project]\nname = "backend"\n')
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"name": "frontend"}')
    workspaces = discover_workspaces(str(tmp_path))
    ws = route_file_to_workspace("backend/app.py", workspaces)
    assert ws is not None
    assert ws.name == "backend"


def test_routes_frontend_file_to_node_workspace(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "pyproject.toml").write_text('[project]\nname = "backend"\n')
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"name": "frontend"}')
    workspaces = discover_workspaces(str(tmp_path))
    ws = route_file_to_workspace("frontend/App.tsx", workspaces)
    assert ws is not None
    assert ws.name == "frontend"


def test_shared_lockfile_triggers_all_workspaces(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "pyproject.toml").write_text('[project]\nname = "backend"\n')
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text('{"name": "frontend"}')
    workspaces = discover_workspaces(str(tmp_path))
    ws = route_file_to_workspace("pnpm-lock.yaml", workspaces)
    # Shared files route to None (meaning: affects all)
    assert ws is None


def test_root_only_repo_is_single_workspace(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
    workspaces = discover_workspaces(str(tmp_path))
    assert len(workspaces) == 1
    assert workspaces[0].path == "."


def test_nested_pyproject_not_confused_with_root(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "root"\n')
    sub = tmp_path / "packages" / "sub"
    sub.mkdir(parents=True)
    (sub / "pyproject.toml").write_text('[project]\nname = "sub"\n')
    workspaces = discover_workspaces(str(tmp_path))
    names = [w.name for w in workspaces]
    assert "root" in names or "." in [w.path for w in workspaces]


def test_pnpm_workspace_packages_detected(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "root"}')
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'apps/*'\n  - 'libs/*'\n")
    apps = tmp_path / "apps" / "web"
    apps.mkdir(parents=True)
    (apps / "package.json").write_text('{"name": "web"}')
    libs = tmp_path / "libs" / "shared"
    libs.mkdir(parents=True)
    (libs / "package.json").write_text('{"name": "shared"}')
    workspaces = discover_workspaces(str(tmp_path))
    names = [w.name for w in workspaces]
    assert "web" in names
    assert "shared" in names


def test_cargo_workspace_members_detected(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[workspace]\nmembers = ["crates/core", "crates/cli"]\n')
    core = tmp_path / "crates" / "core"
    core.mkdir(parents=True)
    (core / "Cargo.toml").write_text('[package]\nname = "core"\nversion = "0.1.0"\n')
    cli = tmp_path / "crates" / "cli"
    cli.mkdir(parents=True)
    (cli / "Cargo.toml").write_text('[package]\nname = "cli"\nversion = "0.1.0"\n')
    workspaces = discover_workspaces(str(tmp_path))
    names = [w.name for w in workspaces]
    assert "core" in names
    assert "cli" in names


def test_deleted_file_routes_correctly(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "pyproject.toml").write_text('[project]\nname = "backend"\n')
    workspaces = discover_workspaces(str(tmp_path))
    # Deleted file still routes by path prefix
    ws = route_file_to_workspace("backend/removed.py", workspaces)
    assert ws is not None
    assert ws.name == "backend"


def test_file_outside_all_workspaces_handled(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "pyproject.toml").write_text('[project]\nname = "backend"\n')
    workspaces = discover_workspaces(str(tmp_path))
    ws = route_file_to_workspace("docs/README.md", workspaces)
    # File outside any workspace -> None
    assert ws is None
