"""Fettle v0.5.0 — WP-67: Project profile detector.

Auto-detect project stack from marker files. Cache in .fettle/profile.json.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Workspace:
    """A single workspace within a project."""

    path: str = "."
    language: str = ""
    manager: str = ""
    test_command: str = ""
    lint_command: str = ""
    format_command: str = ""
    typecheck_command: str = ""
    build_command: str = ""
    dependency_file: str = ""
    lockfile: str | None = None
    source_roots: list[str] = field(default_factory=list)
    test_roots: list[str] = field(default_factory=list)


@dataclass
class Profile:
    """Detected project profile."""

    languages: list[str] = field(default_factory=list)
    workspaces: list[Workspace] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "languages": self.languages,
            "workspaces": [vars(w) for w in self.workspaces],
        }


_MARKERS = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "package.json": "javascript",
    "Cargo.toml": "rust",
    "go.mod": "go",
}


def _detect_python_workspace(root: Path) -> Workspace:
    ws = Workspace(language="python")
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


def _detect_node_workspace(root: Path) -> Workspace:
    ws = Workspace(language="javascript")
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


def _detect_rust_workspace(root: Path) -> Workspace:
    return Workspace(
        language="rust",
        dependency_file="Cargo.toml",
        lockfile="Cargo.lock" if (root / "Cargo.lock").is_file() else None,
        manager="cargo",
        lint_command="cargo clippy",
        format_command="cargo fmt --check",
        test_command="cargo test",
        build_command="cargo build",
    )


def _detect_go_workspace(root: Path) -> Workspace:
    return Workspace(
        language="go",
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
    for marker in sorted(_MARKERS.keys()):
        p = root / marker
        if p.is_file():
            h.update(f"{marker}:{p.stat().st_mtime_ns}".encode())
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
    toml_path = root / ".fettle.toml"
    if not toml_path.is_file():
        return
    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return
    overrides = data.get("profile", {})
    if not overrides or not profile.workspaces:
        return
    ws = profile.workspaces[0]
    for key in ("test_command", "lint_command", "format_command", "typecheck_command", "build_command"):
        if key in overrides:
            setattr(ws, key, overrides[key])


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

    for marker, lang in _MARKERS.items():
        if (root / marker).is_file() and lang not in languages:
            languages.append(lang)

    if "python" in languages:
        workspaces.append(_detect_python_workspace(root))
    if "javascript" in languages or "typescript" in languages:
        ws = _detect_node_workspace(root)
        if ws.language == "typescript" and "javascript" in languages:
            languages.remove("javascript")
            languages.append("typescript")
        workspaces.append(ws)
    if "rust" in languages:
        workspaces.append(_detect_rust_workspace(root))
    if "go" in languages:
        workspaces.append(_detect_go_workspace(root))

    profile = Profile(languages=languages, workspaces=workspaces)
    _apply_fettle_toml_overrides(root, profile)
    _save_cache(root, profile, current_hash)
    return profile
