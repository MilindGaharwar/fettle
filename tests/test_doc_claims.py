"""Docs-claims gate (improvement plan item 1).

High-value documentation claims become executable predicates: a claim may
only read as done when code reality agrees. Advisory-by-design — these are
tests, not hook blocks — but they are house tests and must stay green.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_todo_s55_web_claim_matches_drivable_surfaces():
    """TODO claims Stage-5 S5.5 (web surface) done only if web is drivable."""
    todo = _read("docs/engagement/TODO.md")
    claim_done = re.search(r"- \[x\] .*S5\.5\b.*", todo)
    if not claim_done:
        return  # claim amended or removed; nothing to validate

    from fettle.uat.session import drivable_surfaces

    assert "web" in drivable_surfaces(), (
        "TODO marks S5.5 web surface [x] but session.py excludes 'web' "
        "from DRIVABLE_SURFACES — ship the driver or amend the claim."
    )


def test_readme_replay_gate_claim_matches_workflow():
    """README advertises a required mutation replay gate; workflow must prove it."""
    readme = _read("README.md")
    workflow = _read(".github/workflows/mutation.yml")

    if "replay gate" not in readme and "automatically replays" not in readme:
        return
    assert "--prepare-replay-matrix" in workflow
    assert "mutation evidence" in workflow


def test_readme_single_install_claim_matches_pyproject():
    """README quick start uses finefettle[all]; pyproject must compose it."""
    readme = _read("README.md")
    if 'finefettle[all]' not in readme:
        return

    import tomllib

    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = data["project"]["optional-dependencies"]
    assert any("finefettle[dev]" in dep for dep in extras["all"])
