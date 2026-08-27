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
    """Copy rules/ and templates/ into the built package (wheel resources)."""

    def run(self):
        super().run()
        # Copy rules/*.yml into the package build directory
        src_rules = Path(__file__).parent / "rules"
        if src_rules.is_dir():
            dest = Path(self.build_lib) / "fettle" / "_rules"
            dest.mkdir(parents=True, exist_ok=True)
            resources = [src_rules / "PROVENANCE.md"]
            resources.extend(
                path for path in src_rules.rglob("*")
                if path.is_file() and path.suffix in {".yml", ".yaml", ".toml"}
            )
            for resource in resources:
                if resource.is_file():
                    target = dest / resource.relative_to(src_rules)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(resource, target)
        # Copy templates/*.md so workflow commands can locate them when
        # pip-installed (WP-17; resolved at runtime via _resources.templates_dir)
        src_templates = Path(__file__).parent / "templates"
        if src_templates.is_dir():
            dest = Path(self.build_lib) / "fettle" / "_templates"
            dest.mkdir(parents=True, exist_ok=True)
            for resource in src_templates.glob("*.md"):
                shutil.copy2(resource, dest / resource.name)
        # Copy commands/*.md — canonical workflow source for `fettle workflows
        # install` (WP-18; resolved at runtime via _resources.commands_dir)
        src_commands = Path(__file__).parent / "commands"
        if src_commands.is_dir():
            dest = Path(self.build_lib) / "fettle" / "_commands"
            dest.mkdir(parents=True, exist_ok=True)
            for resource in src_commands.glob("*.md"):
                shutil.copy2(resource, dest / resource.name)
        # Copy the host-neutral SubagentStart transport used by the installed
        # governance bridge. Host hook files are generated with the exact
        # installed interpreter path during `fettle init`.
        src_subagent = Path(__file__).parent / "hooks" / "subagent_inject.js"
        if src_subagent.is_file():
            dest = Path(self.build_lib) / "fettle" / "_bridge"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_subagent, dest / src_subagent.name)


setup(cmdclass={"build_py": _BuildPyWithRules})
