"""Resolve Python tools installed alongside Fettle without exporting their apps."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def resolve_tool(name: str) -> str | None:
    """Prefer an explicit PATH tool, then the executable in Fettle's environment."""
    found = shutil.which(name)
    if found:
        return found
    candidate = Path(sys.executable).parent / (f"{name}.exe" if os.name == "nt" else name)
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None
