"""Fettle v0.5.0 — WP-68: Workspace/monorepo awareness.

Detect multiple workspaces within one repo. Route checks by
changed-file path.
"""

from __future__ import annotations

import glob
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path


_WORKSPACE_MARKERS = {
    "pyproject.toml": "python",
    "package.json": "javascript",
    "Cargo.toml": "rust",
    "go.mod": "go",
}

_SHARED_FILES = {
    "pnpm-lock.yaml", "yarn.lock", "package-lock.json",
    "Cargo.lock", "go.sum", "uv.lock",
    ".github", ".gitignore", "Makefile", "justfile",
    "docker-compose.yml", "docker-compose.yaml",
}


@dataclass
class WorkspaceInfo:
    """A detected workspace within a monorepo."""

    name: str
    path: str
    language: str
    marker: str


def discover_workspaces(root_dir: str) -> list[WorkspaceInfo]:
    """Discover all workspaces in a repo."""
    root = Path(root_dir)
    workspaces: list[WorkspaceInfo] = []

    # Check for explicit workspace definitions first
    pnpm_ws = _detect_pnpm_workspaces(root)
    if pnpm_ws:
        workspaces.extend(pnpm_ws)

    cargo_ws = _detect_cargo_workspaces(root)
    if cargo_ws:
        workspaces.extend(cargo_ws)

    # If explicit workspaces found, don't scan further
    if workspaces:
        return workspaces

    # Scan for nested marker files (one level deep max)
    found_nested = False
    for subdir in sorted(root.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith("."):
            continue
        for marker, lang in _WORKSPACE_MARKERS.items():
            if (subdir / marker).is_file():
                name = _extract_name(subdir, marker) or subdir.name
                rel_path = str(subdir.relative_to(root))
                workspaces.append(WorkspaceInfo(
                    name=name, path=rel_path, language=lang, marker=marker,
                ))
                found_nested = True
                break

    # If no nested workspaces, treat root as single workspace
    if not found_nested:
        for marker, lang in _WORKSPACE_MARKERS.items():
            if (root / marker).is_file():
                name = _extract_name(root, marker) or root.name
                workspaces.append(WorkspaceInfo(
                    name=name, path=".", language=lang, marker=marker,
                ))
                break

    return workspaces


def route_file_to_workspace(
    file_path: str, workspaces: list[WorkspaceInfo]
) -> WorkspaceInfo | None:
    """Route a file to its workspace. Returns None for shared/root files."""
    # Check if file is a known shared file
    base = file_path.split("/")[0] if "/" in file_path else file_path
    if base in _SHARED_FILES or file_path in _SHARED_FILES:
        return None

    # Match by path prefix (longest match wins)
    best: WorkspaceInfo | None = None
    best_len = 0
    for ws in workspaces:
        if ws.path == ".":
            # Root workspace matches everything not matched elsewhere
            if best is None:
                best = ws
            continue
        prefix = ws.path + "/"
        if file_path.startswith(prefix) and len(prefix) > best_len:
            best = ws
            best_len = len(prefix)

    # If only root workspace and file is clearly outside it
    if best and best.path == "." and len(workspaces) > 1:
        return None

    return best


def _extract_name(directory: Path, marker: str) -> str:
    """Extract project name from marker file."""
    marker_path = directory / marker
    if marker == "pyproject.toml":
        return _name_from_pyproject(marker_path)
    if marker == "package.json":
        return _name_from_package_json(marker_path)
    if marker == "Cargo.toml":
        return _name_from_cargo_toml(marker_path)
    if marker == "go.mod":
        return _name_from_go_mod(marker_path)
    return ""


def _name_from_pyproject(path: Path) -> str:
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("name", "")
    except (tomllib.TOMLDecodeError, OSError):
        return ""


def _name_from_package_json(path: Path) -> str:
    try:
        data = json.loads(path.read_text())
        return data.get("name", "")
    except (json.JSONDecodeError, OSError):
        return ""


def _name_from_cargo_toml(path: Path) -> str:
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return data.get("package", {}).get("name", "")
    except (tomllib.TOMLDecodeError, OSError):
        return ""


def _name_from_go_mod(path: Path) -> str:
    try:
        for line in path.read_text().splitlines():
            if line.startswith("module "):
                mod = line.split()[-1]
                return mod.split("/")[-1]
    except OSError:
        pass
    return ""


def _detect_pnpm_workspaces(root: Path) -> list[WorkspaceInfo]:
    """Detect pnpm workspace packages from pnpm-workspace.yaml."""
    ws_file = root / "pnpm-workspace.yaml"
    if not ws_file.is_file():
        return []
    try:
        content = ws_file.read_text()
    except OSError:
        return []

    # Simple YAML parsing for packages list (avoid pyyaml dependency)
    packages: list[str] = []
    in_packages = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "packages:" or stripped.startswith("packages:"):
            in_packages = True
            continue
        if in_packages:
            if stripped.startswith("- "):
                pattern = stripped[2:].strip().strip("'\"")
                packages.append(pattern)
            elif stripped and not stripped.startswith("#"):
                break

    workspaces: list[WorkspaceInfo] = []
    for pattern in packages:
        # Resolve glob patterns
        for match in sorted(glob.glob(str(root / pattern))):
            match_path = Path(match)
            if match_path.is_dir() and (match_path / "package.json").is_file():
                name = _name_from_package_json(match_path / "package.json") or match_path.name
                rel = str(match_path.relative_to(root))
                workspaces.append(WorkspaceInfo(
                    name=name, path=rel, language="javascript", marker="package.json",
                ))
    return workspaces


def _detect_cargo_workspaces(root: Path) -> list[WorkspaceInfo]:
    """Detect Cargo workspace members."""
    cargo_toml = root / "Cargo.toml"
    if not cargo_toml.is_file():
        return []
    try:
        with open(cargo_toml, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return []

    workspace_cfg = data.get("workspace", {})
    members = workspace_cfg.get("members", [])
    if not members:
        return []

    workspaces: list[WorkspaceInfo] = []
    for pattern in members:
        for match in sorted(glob.glob(str(root / pattern))):
            match_path = Path(match)
            member_cargo = match_path / "Cargo.toml"
            if match_path.is_dir() and member_cargo.is_file():
                name = _name_from_cargo_toml(member_cargo) or match_path.name
                rel = str(match_path.relative_to(root))
                workspaces.append(WorkspaceInfo(
                    name=name, path=rel, language="rust", marker="Cargo.toml",
                ))
    return workspaces
