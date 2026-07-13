"""Fettle v0.5.0 — WP-82: Entry point wiring checker.

Verify declared console scripts resolve to real modules/functions.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from finding import CheckFinding, FindingSeverity


def check_entry_points(cwd: str) -> list[CheckFinding]:
    """Verify entry points in pyproject.toml resolve correctly."""
    root = Path(cwd)
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return []

    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return []

    scripts = data.get("project", {}).get("scripts", {})
    if not scripts:
        return []

    findings: list[CheckFinding] = []
    for name, spec in scripts.items():
        result = _verify_entry_point(root, name, spec)
        if result:
            findings.append(result)
    return findings


def _verify_entry_point(root: Path, name: str, spec: str) -> CheckFinding | None:
    """Verify a single entry point spec like 'myapp.cli:main'."""
    if ":" not in spec:
        return CheckFinding(
            checker="entry-points",
            severity=FindingSeverity.ERROR,
            file="pyproject.toml",
            line=0,
            message=f"Entry point '{name}' has invalid format: '{spec}' (expected 'module.path:function')",
            blocking=False,
        )

    module_path, func_name = spec.rsplit(":", 1)
    parts = module_path.split(".")

    # Try to find the module file
    candidates = [
        root / Path(*parts).with_suffix(".py"),
        root / Path(*parts) / "__init__.py",
        root / "src" / Path(*parts).with_suffix(".py"),
        root / "src" / Path(*parts) / "__init__.py",
    ]

    module_file = None
    for candidate in candidates:
        if candidate.is_file():
            module_file = candidate
            break

    if module_file is None:
        return CheckFinding(
            checker="entry-points",
            severity=FindingSeverity.ERROR,
            file="pyproject.toml",
            line=0,
            message=f"Entry point '{name}': module '{module_path}' not found",
            suggested_fix=f"Create {parts[-1]}.py or check the module path in [project.scripts]",
            blocking=False,
        )

    # Check if function exists in the module
    try:
        source = module_file.read_text()
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return None

    defined_names = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            defined_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_names.add(target.id)
        elif isinstance(node, ast.ClassDef):
            defined_names.add(node.name)

    if func_name not in defined_names:
        return CheckFinding(
            checker="entry-points",
            severity=FindingSeverity.ERROR,
            file=str(module_file),
            line=0,
            message=f"Entry point '{name}': function '{func_name}' not found in {module_file.name}",
            suggested_fix=f"Define 'def {func_name}():' in {module_file.name}",
            blocking=False,
        )

    return None
