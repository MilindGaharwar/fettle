#!/usr/bin/env python3
"""Run the packaged GitHub Action entrypoint from a source checkout."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from action_entrypoint import _findings_to_sarif, main  # noqa: E402,F401


if __name__ == "__main__":
    sys.exit(main())
