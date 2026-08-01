"""Surface detection — which ways does a user reach this app? (S5.1)

Deterministic, evidence-carrying, stdlib-only. Detection is *shown and
overridable*, never silently guessed: every detected surface carries the
concrete evidence that triggered it (design doc 10 §2).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SURFACE_NAMES = ("cli", "api", "web", "library")

_WEB_DEPS = frozenset({
    "react", "vue", "svelte", "next", "nuxt", "@angular/core", "vite",
    "astro", "solid-js", "remix", "@sveltejs/kit",
})
_API_DEPS_JS = frozenset({"express", "fastify", "koa", "@nestjs/core", "hapi"})
_API_MARKERS_PY = re.compile(r"\b(FastAPI|Flask|Django|APIRouter|Blueprint)\s*\(")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _package_json(root: Path) -> dict:
    try:
        data = json.loads(_read(root / "package.json") or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def detect_surfaces(root: str) -> list[dict]:
    """Detected surfaces with evidence: [{"name", "evidence"}, ...]."""
    root_path = Path(root)
    found: list[dict] = []

    def add(name: str, evidence: str) -> None:
        if not any(s["name"] == name for s in found):
            found.append({"name": name, "evidence": evidence})

    # --- cli
    pyproject = _read(root_path / "pyproject.toml")
    if re.search(r"^\[project\.scripts\]", pyproject, re.MULTILINE):
        add("cli", "pyproject.toml [project.scripts]")
    if "console_scripts" in _read(root_path / "setup.py") + _read(root_path / "setup.cfg"):
        add("cli", "console_scripts entry points")
    pkg = _package_json(root_path)
    if pkg.get("bin"):
        add("cli", "package.json \"bin\"")

    # --- api
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    js_api = sorted(_API_DEPS_JS & set(deps))
    if js_api:
        add("api", f"package.json dependency: {js_api[0]}")
    if (root_path / "openapi.json").is_file() or (root_path / "openapi.yaml").is_file():
        add("api", "openapi spec file at repo root")
    for candidate in ("app.py", "main.py", "src/app.py", "src/main.py", "api/main.py"):
        m = _API_MARKERS_PY.search(_read(root_path / candidate))
        if m:
            add("api", f"{candidate}: {m.group(1)}(...)")
            break

    # --- web
    js_web = sorted(_WEB_DEPS & set(deps))
    if js_web:
        add("web", f"package.json dependency: {js_web[0]}")
    if (root_path / "templates").is_dir():
        add("web", "templates/ directory")
    static = root_path / "static"
    if static.is_dir() and any(static.rglob("*.html")):
        add("web", "static/ directory with html")

    # --- library (only when nothing user-facing was found)
    if not found:
        if re.search(r"^\[project\]", pyproject, re.MULTILINE) or pkg.get("main") or pkg.get("exports"):
            add("library", "installable package with no app entry point")

    return found


def resolve_surfaces(root: str, config: dict) -> tuple[list[dict], str]:
    """Apply [uat].surfaces config: 'auto' → detect; explicit list → validate.

    Returns (surfaces, error). Explicit surfaces carry evidence
    "declared in .fettle.toml".
    """
    requested = config.get("uat", {}).get("surfaces", ["auto"])
    if requested == ["auto"]:
        return detect_surfaces(root), ""
    unknown = [s for s in requested if s not in SURFACE_NAMES]
    if unknown:
        return [], (f"unknown surface(s) in [uat].surfaces: {', '.join(unknown)} "
                    f"(valid: {', '.join(SURFACE_NAMES)})")
    return [{"name": s, "evidence": "declared in .fettle.toml"} for s in requested], ""
