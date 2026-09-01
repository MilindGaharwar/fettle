"""Fettle v0.5.0 — WP-67: Project profile detector.

Auto-detect project stack from marker files. Cache in .fettle/profile.json.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fettle.workspace import Workspace, discover_workspaces


@dataclass
class Profile:
    """Detected project profile."""

    languages: list[str] = field(default_factory=list)
    workspaces: list[Workspace] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "languages": self.languages,
            "workspaces": [asdict(w) for w in self.workspaces],
        }


_MARKERS = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "package.json": "javascript",
    "Cargo.toml": "rust",
    "go.mod": "go",
}


def _detect_python_workspace(root: Path, *, path: str = ".", name: str = "", marker: str = "pyproject.toml") -> Workspace:
    ws = Workspace(name=name or root.name, path=path, language="python", marker=marker)
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        ws.dependency_file = "pyproject.toml"
        ws.manager = _detect_python_manager(root)
        ws.lint_command = "ruff check ."
        ws.format_command = "ruff format --check ."
        ws.test_command = _detect_python_test_command(root)
        ws.build_command = f"{ws.manager} install -e ." if ws.manager else "pip install -e ."
    elif (root / "setup.py").is_file():
        ws.dependency_file = "setup.py"
        ws.manager = "pip"
        ws.test_command = "python -m pytest"
        ws.build_command = "pip install -e ."
    ws.source_roots = _detect_source_roots(root)
    ws.test_roots = _detect_test_roots(root)
    ws.lockfile = _find_lockfile(root, ["uv.lock", "requirements.txt", "poetry.lock", "Pipfile.lock"])
    return ws


def _detect_python_manager(root: Path) -> str:
    if (root / "uv.lock").is_file():
        return "uv"
    if (root / "poetry.lock").is_file():
        return "poetry"
    if (root / "Pipfile.lock").is_file():
        return "pipenv"
    return "pip"


def _detect_python_test_command(root: Path) -> str:
    if (root / "conftest.py").is_file() or (root / "tests").is_dir():
        return "python -m pytest"
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            if "pytest" in str(data.get("tool", {})):
                return "python -m pytest"
        except (tomllib.TOMLDecodeError, OSError):
            pass
    return ""


def _detect_node_workspace(root: Path, *, path: str = ".", name: str = "", marker: str = "package.json") -> Workspace:
    ws = Workspace(name=name or root.name, path=path, language="javascript", marker=marker)
    ws.dependency_file = "package.json"
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text())
            if "typescript" in str(data.get("devDependencies", {})):
                ws.language = "typescript"
        except (json.JSONDecodeError, OSError):
            pass
    ws.manager = _detect_node_manager(root)
    ws.lockfile = _find_lockfile(root, ["pnpm-lock.yaml", "yarn.lock", "package-lock.json", "bun.lockb"])
    ws.test_command = f"{ws.manager} test"
    ws.lint_command = f"{ws.manager} run lint"
    ws.build_command = f"{ws.manager} run build"
    return ws


def _detect_node_manager(root: Path) -> str:
    if (root / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (root / "yarn.lock").is_file():
        return "yarn"
    if (root / "bun.lockb").is_file():
        return "bun"
    return "npm"


def _detect_rust_workspace(root: Path, *, path: str = ".", name: str = "", marker: str = "Cargo.toml") -> Workspace:
    return Workspace(
        name=name or root.name,
        path=path,
        language="rust",
        marker=marker,
        dependency_file="Cargo.toml",
        lockfile="Cargo.lock" if (root / "Cargo.lock").is_file() else None,
        manager="cargo",
        lint_command="cargo clippy",
        format_command="cargo fmt --check",
        test_command="cargo test",
        build_command="cargo build",
    )


def _detect_go_workspace(root: Path, *, path: str = ".", name: str = "", marker: str = "go.mod") -> Workspace:
    return Workspace(
        name=name or root.name,
        path=path,
        language="go",
        marker=marker,
        dependency_file="go.mod",
        lockfile="go.sum" if (root / "go.sum").is_file() else None,
        manager="go",
        lint_command="golangci-lint run",
        format_command="gofmt -l .",
        test_command="go test ./...",
        build_command="go build ./...",
    )


def _detect_source_roots(root: Path) -> list[str]:
    candidates = ["src/", "lib/", "app/"]
    return [c for c in candidates if (root / c).is_dir()]


def _detect_test_roots(root: Path) -> list[str]:
    candidates = ["tests/", "test/", "spec/"]
    return [c for c in candidates if (root / c).is_dir()]


def _find_lockfile(root: Path, candidates: list[str]) -> str | None:
    for name in candidates:
        if (root / name).is_file():
            return name
    return None


def _marker_hash(root: Path) -> str:
    h = hashlib.md5(usedforsecurity=False)
    excluded = {".git", ".fettle", ".venv", "venv", "node_modules", "vendor", "target",
                "dist", "build", "out", "coverage", "__pycache__"}
    marker_names = {*_MARKERS, "global.json", "pom.xml", "build.gradle", "build.gradle.kts"}
    paths = [root / ".fettle.toml"]
    paths.extend(
        path for path in root.rglob("*")
        if path.name in marker_names
        and not any(part in excluded for part in path.relative_to(root).parts)
    )
    for path in sorted(paths):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            h.update(f"{relative}:{path.stat().st_mtime_ns}:{path.stat().st_size}".encode())
    return h.hexdigest()


def _load_cache(root: Path) -> tuple[Profile | None, str]:
    cache_dir = root / ".fettle"
    cache_file = cache_dir / "profile.json"
    if not cache_file.is_file():
        return None, ""
    try:
        data = json.loads(cache_file.read_text())
        cached_hash = data.get("_marker_hash", "")
        languages = data.get("languages", [])
        workspaces = [Workspace(**w) for w in data.get("workspaces", [])]
        return Profile(languages=languages, workspaces=workspaces), cached_hash
    except (json.JSONDecodeError, OSError, TypeError):
        return None, ""


def _save_cache(root: Path, profile: Profile, marker_hash: str) -> None:
    cache_dir = root / ".fettle"
    cache_dir.mkdir(exist_ok=True)
    data = profile.to_dict()
    data["_marker_hash"] = marker_hash
    with contextlib.suppress(OSError):
        (cache_dir / "profile.json").write_text(json.dumps(data, indent=2))


def _apply_fettle_toml_overrides(root: Path, profile: Profile) -> None:
    # WP-20 resolver, not a raw repo read: org/remote/capsule layers govern
    # [profile] too — a repo-level test_command override cannot silently
    # replace org policy (2026-08 audit).
    from fettle.config import load_config
    overrides = load_config(str(root)).get("profile", {})
    if not isinstance(overrides, dict) or not overrides or not profile.workspaces:
        return
    command_keys = ("test_command", "lint_command", "format_command", "typecheck_command", "build_command")
    for ws in profile.workspaces:
        for key in command_keys:
            # DEFAULTS ships "" for every key — empty means "not overridden".
            value = overrides.get(key)
            if isinstance(value, str) and value:
                setattr(ws, key, value)
    for workspace_override in overrides.get("workspaces", []):
        if not isinstance(workspace_override, dict):
            continue
        ws = next((item for item in profile.workspaces if item.path == workspace_override.get("path")), None)
        if ws is None:
            continue
        for key in command_keys:
            value = workspace_override.get(key)
            if isinstance(value, str) and value:
                setattr(ws, key, value)


def detect_profile(cwd: str, use_cache: bool = True) -> Profile:
    """Detect project profile from marker files at cwd."""
    root = Path(cwd)

    current_hash = _marker_hash(root)
    if use_cache:
        cached, cached_hash = _load_cache(root)
        if cached and cached_hash == current_hash:
            return cached

    languages: list[str] = []
    workspaces: list[Workspace] = []
    for discovered in discover_workspaces(str(root)):
        ws_root = root if discovered.path == "." else root / discovered.path
        if discovered.language == "python":
            ws = _detect_python_workspace(ws_root, path=discovered.path, name=discovered.name,
                                          marker=discovered.marker)
        elif discovered.language == "javascript":
            ws = _detect_node_workspace(ws_root, path=discovered.path, name=discovered.name,
                                        marker=discovered.marker)
        elif discovered.language == "rust":
            ws = _detect_rust_workspace(ws_root, path=discovered.path, name=discovered.name,
                                        marker=discovered.marker)
        elif discovered.language == "go":
            ws = _detect_go_workspace(ws_root, path=discovered.path, name=discovered.name,
                                      marker=discovered.marker)
        else:
            ws = discovered
        workspaces.append(ws)
        if ws.language not in languages:
            languages.append(ws.language)

    profile = Profile(languages=languages, workspaces=workspaces)
    _apply_fettle_toml_overrides(root, profile)
    _save_cache(root, profile, current_hash)
    return profile
