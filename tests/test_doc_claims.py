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
    """TODO claims the web *driver* shipped (P74).

    The claim is about the code path existing and degrading honestly, not
    about every environment carrying browser binaries: mutation-worker
    venvs install with --no-deps and legitimately exclude web. So assert
    the contract, not the environment.
    """
    todo = _read("docs/engagement/TODO.md")
    if not re.search(r"- \[x\] .*S5\.5\b.*", todo):
        return  # claim amended or removed; nothing to validate

    from fettle.uat.session import drivable_surfaces

    try:
        import playwright  # noqa: F401

        browsers_available = True
    except ImportError:
        browsers_available = False

    surfaces = drivable_surfaces()
    if browsers_available:
        assert "web" in surfaces, (
            "playwright is installed but session.py excludes 'web' from "
            "drivable surfaces — the S5.5 driver path is broken."
        )
    else:
        assert "web" not in surfaces, (
            "playwright absent yet 'web' reported drivable — capability "
            "probe is lying about browser availability."
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
    """README quick start uses plain finefettle; it must carry all runtimes."""
    readme = _read("README.md")
    installation = _read("docs/INSTALLATION.md")
    assert "pipx install finefettle" in readme
    assert "pipx install finefettle" in installation
    assert "No capability extra is required for normal use" in installation
    assert "`playwright install` browser binaries" in installation

    import tomllib

    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = data["project"]["dependencies"]
    for capability in ("mutmut", "playwright", "pytest", "pyyaml", "ruff", "semgrep"):
        assert any(dep.split("=", 1)[0].split(">", 1)[0] == capability for dep in dependencies)


def test_current_documentation_version_matches_package():
    import tomllib

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]

    assert f"v{version}" in _read("docs/ROADMAP.md")
    citation = _read("CITATION.cff")
    assert f"version: {version}" in citation
    assert 'name: "Milind"' in citation


def test_event_map_covers_all_dispatcher_and_transport_events():
    """Drift predicate: every dispatched/transported event appears in the map."""
    import re

    event_re = re.compile(r'"(PreToolUse|PostToolUse|Stop|SubagentStart)"')
    names = set()
    for agent_file in (Path(ROOT) / "fettle" / "agents").glob("*.py"):
        names.update(event_re.findall(agent_file.read_text(encoding="utf-8")))
    registry = (Path(ROOT) / "fettle" / "dispatcher_registry.py") \
        .read_text(encoding="utf-8")
    names.update(event_re.findall(registry))

    assert names, "no events discovered — discovery regex broke"
    event_map = (Path(ROOT) / "docs" / "event-map.md").read_text(
        encoding="utf-8")
    missing = sorted(n for n in names if f"### {n}" not in event_map)
    assert not missing, f"events missing from docs/event-map.md: {missing}"


def test_behavior_map_covers_new_public_commands():
    """Drift predicate (item 12, scoped per GLM review).

    Freezes today's top-level CLI surface: any NEW dispatch command must be
    added to docs/behavior-map.md (or consciously moved into the whitelist
    with a documentation pointer) before it can merge.
    """
    import re

    src = (Path(ROOT) / "fettle" / "cli.py").read_text(encoding="utf-8")
    table = (Path(ROOT) / "docs" / "behavior-map.md").read_text(
        encoding="utf-8")

    # Top-level dispatch entries only ("name": cmd_name).
    registered = set(re.findall(r'"([a-z_]+)":\s*cmd_[a-z_]+', src))
    assert registered, "dispatch dict discovery broke"

    # Commands already represented in the decision table.
    covered = {name for name in registered
               if f"fettle {name}" in table or f"`{name}`" in table}

    # Frozen inventory: existing commands documented elsewhere (CONFIG.md,
    # plan-index.md, subsystem docs). New commands must leave this set by
    # joining the table.
    documented_elsewhere = {
        "baseline", "bench", "brief", "check", "ci", "completion",
        "config", "doctor", "explain", "init", "insights", "integrations",
        "learn", "links", "lsp", "mutation", "overrides", "plan", "policy",
        "ratchet", "report", "rules", "spec", "suppressions", "telemetry",
        "topology", "uat", "verification", "verify", "workflows",
        # Wave-3 additions: documented in plan-index + decision memo until
        # their table rows land with the next docs pass.
        "graph", "ledger",
    }

    missing = sorted(registered - covered - documented_elsewhere)
    assert not missing, (
        f"new public commands missing from docs/behavior-map.md: {missing}"
    )
