"""Deterministic, offline demonstration of Fettle's control loop."""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_RULE = "FETTLE-DEMO-001"
_FIXTURE = Path(__file__).parent / "_demo_fixture"


def _stage(heading: str, detail: str) -> None:
    sys.stdout.write(f"{heading}\n{detail}\n")


def _has_broad_handler(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.ExceptHandler)
        and isinstance(node.type, ast.Name)
        and node.type.id == "Exception"
        for node in ast.walk(tree)
    )


def run_demo() -> int:
    """Run the bundled detect-repair-verify cycle and return its exit code."""
    with tempfile.TemporaryDirectory(prefix="fettle-demo-") as temporary:
        root = Path(temporary) / "demo"
        try:
            root.mkdir()
            for source in sorted(_FIXTURE.glob("*.py.txt")):
                shutil.copy2(source, root / source.name.removesuffix(".txt"))
            target = root / "calculator.py"
            clean = target.read_text(encoding="utf-8")
            violation = clean.replace("except ValueError:", "except Exception:", 1)
            if violation == clean:
                raise ValueError("fixture does not contain the repair token")
            target.write_text(violation, encoding="utf-8")

            _stage(
                "[1/4] VIOLATION INTRODUCED",
                "Broad exception handling now hides unexpected failures.",
            )
            if not _has_broad_handler(target):
                raise ValueError("detector did not find the seeded violation")

            _stage("[2/4] VIOLATION DETECTED", f"{_RULE}: broad Exception handler found.")
            repaired = violation.replace("except Exception:", "except ValueError:", 1)
            target.write_text(repaired, encoding="utf-8")
            _stage("[3/4] REPAIR APPLIED", "The handler now catches ValueError only.")

            verification = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", str(root), "-q"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if _has_broad_handler(target) or verification.returncode != 0:
                _stage("[4/4] REPAIR NOT VERIFIED", "Behavioral tests failed.")
                return 1
        except (OSError, SyntaxError, ValueError, subprocess.TimeoutExpired):
            _stage(
                "[4/4] REPAIR NOT VERIFIED",
                "The bundled demonstration could not complete.",
            )
            return 1

    _stage("[4/4] REPAIR INDEPENDENTLY VERIFIED", "Behavioral tests passed.")
    return 0
