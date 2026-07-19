"""Minimal setup.py to ship rules/ as package data inside the wheel.

All metadata lives in pyproject.toml. This file exists solely because
setuptools package_data cannot reference files outside the package directory,
and rules/ lives at the repo root for backwards compatibility with the
clone-into-plugins install path.
"""

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


class _BuildPyWithRules(build_py):
    """Copy rules/ into the built package so they ship inside the wheel."""

    def run(self):
        super().run()
        # Copy rules/*.yml into the package build directory
        src_rules = Path(__file__).parent / "rules"
        if src_rules.is_dir():
            dest = Path(self.build_lib) / "fettle" / "_rules"
            dest.mkdir(parents=True, exist_ok=True)
            for pattern in ("*.yml", "*.toml"):
                for resource in src_rules.glob(pattern):
                    shutil.copy2(resource, dest / resource.name)
            # Also copy learned/ subdirectory if present
            learned = src_rules / "learned"
            if learned.is_dir():
                dest_learned = dest / "learned"
                dest_learned.mkdir(parents=True, exist_ok=True)
                for yml in learned.glob("*.yml"):
                    shutil.copy2(yml, dest_learned / yml.name)


setup(cmdclass={"build_py": _BuildPyWithRules})
