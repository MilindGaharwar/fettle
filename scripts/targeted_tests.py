"""Fettle v0.5.0 — WP-86+87: Targeted test selection + confidence scoring.

Run only tests covering changed files. Includes confidence scoring
to determine when targeted tests are sufficient vs full suite needed.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


_CONFIG_FILES = {
    "pyproject.toml", "setup.py", "setup.cfg",
    "requirements.txt", "uv.lock", "poetry.lock",
    "Pipfile.lock", "package.json", "pnpm-lock.yaml",
    "Cargo.toml", "Cargo.lock", "go.mod", "go.sum",
    ".env", "Makefile", "justfile", "docker-compose.yml",
    "Dockerfile", ".github",
}


@dataclass
class SelectedTests:
    """Result of test selection with confidence."""

    selected: list[str] = field(default_factory=list)
    confidence: Confidence = Confidence.LOW
    run_full: bool = False
    reason: str = ""


def select_tests(
    cwd: str,
    changed_files: list[str],
    test_roots: list[str] | None = None,
) -> TestSelection:
    """Select tests to run based on changed files."""
    if not changed_files:
        return SelectedTests(reason="no changes")

    # Strategy 1: config/lockfile change → full suite
    if _has_config_change(changed_files):
        return SelectedTests(
            run_full=True,
            confidence=Confidence.LOW,
            reason="config/lockfile changed — full suite needed",
        )

    # Strategy 2: changed file IS a test → run it directly
    direct_tests = [f for f in changed_files if _is_test_file(f)]
    if direct_tests:
        non_test_changes = [f for f in changed_files if not _is_test_file(f)]
        if not non_test_changes:
            return SelectedTests(
                selected=direct_tests,
                confidence=Confidence.HIGH,
                reason="only test files changed",
            )
        # Mix of test and source — run the tests directly + find dependents
        dependent = _find_dependent_tests(cwd, non_test_changes, test_roots or [])
        all_tests = list(set(direct_tests + dependent))
        return SelectedTests(
            selected=all_tests,
            confidence=Confidence.HIGH if dependent else Confidence.MEDIUM,
            reason="test files + dependent tests",
        )

    # Strategy 3: import graph — find tests that import changed modules
    if test_roots:
        dependent = _find_dependent_tests(cwd, changed_files, test_roots)
        if dependent:
            return SelectedTests(
                selected=dependent,
                confidence=Confidence.MEDIUM,
                reason="import graph analysis",
            )

    # Strategy 4: no mapping found
    return SelectedTests(
        confidence=Confidence.LOW,
        run_full=True,
        reason="no test mapping found — full suite recommended",
    )


def _has_config_change(files: list[str]) -> bool:
    """Check if any changed file is a config/lockfile."""
    for f in files:
        basename = os.path.basename(f)
        if basename in _CONFIG_FILES:
            return True
        if f.startswith(".github"):
            return True
    return False


def _is_test_file(path: str) -> bool:
    """Check if a path looks like a test file."""
    basename = os.path.basename(path)
    return (
        basename.startswith("test_")
        or basename.endswith("_test.py")
        or "/tests/" in path
        or "/test/" in path
        or path.startswith("tests/")
        or path.startswith("test/")
    )


def _find_dependent_tests(
    cwd: str, source_files: list[str], test_roots: list[str]
) -> list[str]:
    """Find test files that import any of the changed source modules."""
    root = Path(cwd)
    # Convert source files to importable module names (multiple forms)
    source_modules = set()
    for f in source_files:
        module = _path_to_module(f)
        if module:
            source_modules.add(module)
            # Also add all prefix forms: src.util → {src.util, src, util}
            parts = module.split(".")
            for i in range(len(parts)):
                source_modules.add(".".join(parts[i:]))

    if not source_modules:
        return []

    # Scan test files for imports
    dependent: list[str] = []
    for test_root in test_roots:
        test_dir = root / test_root
        if not test_dir.is_dir():
            continue
        for test_file in test_dir.rglob("test_*.py"):
            imports = _get_imports(test_file)
            if imports & source_modules:
                rel = str(test_file.relative_to(root))
                dependent.append(rel)

    return dependent


def _path_to_module(path: str) -> str:
    """Convert a file path to a Python module name."""
    if not path.endswith(".py"):
        return ""
    return path.removesuffix(".py").replace("/", ".").replace("\\", ".")


def _get_imports(file_path: Path) -> set[str]:
    """Extract imported module names from a Python file."""
    try:
        source = file_path.read_text()
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
            imports.add(node.module)
    return imports
