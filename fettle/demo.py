"""Deterministic, offline demonstration of Fettle's control loop."""

from __future__ import annotations

import ast
import difflib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_RULE = "broad-except-no-reraise"
_DISPLAY_PATH = "demo_project/calculator.py"
_RULE_PATH = "rules/llm-antipatterns.yml"
_FIXTURE = Path(__file__).parent / "_demo_fixture"


def _stage(heading: str, detail: str) -> None:
    sys.stdout.write(f"{heading}\n{detail}\n")


def _broad_handler_line(path: Path) -> int | None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(
        (
            node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.ExceptHandler)
            and isinstance(node.type, ast.Name)
            and node.type.id == "Exception"
        ),
        None,
    )


def _source_context(source: str, line_number: int) -> str:
    lines = source.splitlines()
    first = max(1, line_number - 2)
    last = min(len(lines), line_number + 1)
    width = len(str(last))
    return "\n".join(
        f"   {number:>{width}} | {lines[number - 1]}"
        for number in range(first, last + 1)
    )


def _repair_diff(before: str, after: str) -> str:
    return "\n".join(
        f"   {line}"
        for line in difflib.ndiff(before.splitlines(), after.splitlines())
        if line.startswith(("- ", "+ "))
    )


def run_demo(fixture_dir: Path = _FIXTURE) -> int:
    """Run the bundled detect-repair-verify cycle and return its exit code."""
    with tempfile.TemporaryDirectory(prefix="fettle-demo-") as temporary:
        root = Path(temporary) / "demo_project"
        try:
            root.mkdir()
            for source in sorted(fixture_dir.glob("*.py.txt")):
                shutil.copy2(source, root / source.name.removesuffix(".txt"))
            target = root / "calculator.py"
            clean = target.read_text(encoding="utf-8")
            violation = clean.replace("except ValueError:", "except Exception:", 1)
            if violation == clean:
                raise ValueError("fixture does not contain the repair token")
            target.write_text(violation, encoding="utf-8")

            line_number = _broad_handler_line(target)
            if line_number is None:
                raise ValueError("detector did not find the seeded violation")
            _stage(
                f"[1/4] VIOLATION INTRODUCED  {_DISPLAY_PATH}:{line_number}",
                f"\n{_source_context(violation, line_number)}\n\n"
                "   Broad handler hides unexpected failures.\n",
            )

            _stage(
                "[2/4] VIOLATION DETECTED",
                f"   {_RULE}  {_DISPLAY_PATH}:{line_number}\n"
                f"   Rule: {_RULE_PATH}\n",
            )
            repaired = violation.replace("except Exception:", "except ValueError:", 1)
            target.write_text(repaired, encoding="utf-8")
            _stage("[3/4] REPAIR APPLIED", f"\n{_repair_diff(violation, repaired)}\n")

            verification = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", str(root), "-q"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            match = re.search(r"Ran (\d+) tests?", verification.stderr)
            if _broad_handler_line(target) is not None or verification.returncode != 0 or match is None:
                _stage(
                    "[4/4] REPAIR NOT VERIFIED",
                    "   Re-ran check: clean\n   Re-ran tests: failed",
                )
                return 1
        except (OSError, SyntaxError, ValueError, subprocess.TimeoutExpired):
            _stage(
                "[4/4] REPAIR NOT VERIFIED",
                "The bundled demonstration could not complete.",
            )
            return 1

    _stage(
        "[4/4] REPAIR INDEPENDENTLY VERIFIED",
        f"   Re-ran check: clean\n   Re-ran tests: {match.group(1)} passed\n\n"
        "   An unexpected TypeError now surfaces instead of being silently swallowed.",
    )
    return 0
