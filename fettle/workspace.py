"""Fettle v0.5.0 — WP-68: Workspace/monorepo awareness.

Detect multiple workspaces within one repo. Route checks by
changed-file path.
"""

from __future__ import annotations

import glob
import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


_WORKSPACE_MARKERS = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "package.json": "javascript",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "global.json": "dotnet",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "java",
}

_EXCLUDED_DIRS = frozenset({
    ".git", ".fettle", ".venv", "venv", "node_modules", "vendor", "target",
    "dist", "build", "out", "coverage", "__pycache__",
})

_SHARED_FILES = {
    "pnpm-lock.yaml", "yarn.lock", "package-lock.json",
    "Cargo.lock", "go.sum", "uv.lock",
    ".github", ".gitignore", "Makefile", "justfile",
    "docker-compose.yml", "docker-compose.yaml",
}


@dataclass
class Workspace:
    """Canonical detected workspace and its native execution metadata."""

    name: str = ""
    path: str = "."
    language: str = ""
    marker: str = ""
    frameworks: list[str] = field(default_factory=list)
    manager: str = ""
    wrapper: str | None = None
    test_command: str = ""
    lint_command: str = ""
    format_command: str = ""
    typecheck_command: str = ""
    build_command: str = ""
    dependency_file: str = ""
    dependency_files: list[str] = field(default_factory=list)
    lockfile: str | None = None
    lockfiles: list[str] = field(default_factory=list)
    source_roots: list[str] = field(default_factory=list)
    test_roots: list[str] = field(default_factory=list)


WorkspaceInfo = Workspace


def discover_workspaces(root_dir: str) -> list[Workspace]:
    """Discover all workspaces in a repo."""
    root = Path(root_dir)
    workspaces: list[Workspace] = []

    # Check for explicit workspace definitions first
    pnpm_ws = _detect_pnpm_workspaces(root)
    if pnpm_ws:
        workspaces.extend(pnpm_ws)

    cargo_ws = _detect_cargo_workspaces(root)
    if cargo_ws:
        workspaces.extend(cargo_ws)

    seen = {(ws.path, ws.language) for ws in workspaces}
    candidates = [root]
    candidates.extend(
        path for path in root.rglob("*")
        if path.is_dir() and not any(part in _EXCLUDED_DIRS for part in path.relative_to(root).parts)
    )
    for directory in sorted(candidates):
        marker_found = False
        for marker, lang in _WORKSPACE_MARKERS.items():
            if not (directory / marker).is_file():
                continue
            marker_found = True
            rel_path = "." if directory == root else directory.relative_to(root).as_posix()
            if (rel_path, lang) not in seen:
                workspaces.append(Workspace(
                    name=_extract_name(directory, marker) or directory.name,
                    path=rel_path, language=lang, marker=marker,
                ))
                seen.add((rel_path, lang))
        if not marker_found:
            project_files = sorted(directory.glob("*.csproj"))
            solution_files = sorted(directory.glob("*.sln")) + sorted(directory.glob("*.slnx"))
            if project_files or solution_files:
                rel_path = "." if directory == root else directory.relative_to(root).as_posix()
                if (rel_path, "dotnet") not in seen:
                    marker = (project_files or solution_files)[0].name
                    workspaces.append(Workspace(
                        name=directory.name, path=rel_path, language="dotnet", marker=marker,
                    ))
                    seen.add((rel_path, "dotnet"))
    return sorted(workspaces, key=lambda ws: (ws.path, ws.language))


def route_file_to_workspace(
    file_path: str, workspaces: list[Workspace]
) -> Workspace | None:
    """Route a file to its workspace. Returns None for shared/root files."""
    # Check if file is a known shared file
    base = file_path.split("/")[0] if "/" in file_path else file_path
    if base in _SHARED_FILES or file_path in _SHARED_FILES:
        return None

    # Match by path prefix (longest match wins)
    best: Workspace | None = None
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


def _detect_pnpm_workspaces(root: Path) -> list[Workspace]:
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

    workspaces: list[Workspace] = []
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


def _detect_cargo_workspaces(root: Path) -> list[Workspace]:
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

    workspaces: list[Workspace] = []
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
