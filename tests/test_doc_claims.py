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
    assert re.search(r"- \[x\] .*S5\.5\b.*web surface.*shipped", todo), (
        "the shipped S5.5 web-driver claim disappeared; amend this executable "
        "contract explicitly if product scope changes"
    )

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
    """README's replay and survivor-enforcement claims must match required CI."""
    readme = _read("README.md")
    workflow = _read(".github/workflows/mutation.yml")

    mutation_row = next(
        (line for line in readme.splitlines() if line.startswith("| Mutation quality |")),
        "",
    )
    assert "replay" in mutation_row and "survivor enforcement" in mutation_row, (
        "README mutation capability must state replay and survivor enforcement"
    )
    assert "needs: [changed-prepare, changed-shard, changed-replay-prepare, changed-replay]" \
        in workflow
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
    import ast

    names = set()
    for agent_file in (Path(ROOT) / "fettle" / "agents").glob("*.py"):
        tree = ast.parse(agent_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not any(
                isinstance(target, ast.Name)
                and target.id in {"KNOWN_EVENTS", "_EVENT_MAP"}
                for target in node.targets
            ):
                continue
            value_node = (
                node.value.args[0]
                if isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "frozenset"
                else node.value
            )
            value = ast.literal_eval(value_node)
            names.update(value.values() if isinstance(value, dict) else value)

    registry = ast.parse(
        (Path(ROOT) / "fettle" / "dispatcher_registry.py").read_text(
            encoding="utf-8")
    )
    for node in ast.walk(registry):
        if not isinstance(node, ast.Call) or not (
            isinstance(node.func, ast.Name) and node.func.id == "CheckSpec"
        ):
            continue
        events = next((kw.value for kw in node.keywords if kw.arg == "events"), None)
        assert events is not None, "CheckSpec without events"
        names.update(ast.literal_eval(events.args[0]))

    assert names, "no events discovered — discovery regex broke"
    event_map = (Path(ROOT) / "docs" / "event-map.md").read_text(
        encoding="utf-8")
    headings = {
        line.removeprefix("### ") for line in event_map.splitlines()
        if line.startswith("### ")
    }
    assert headings == names, (
        f"event map drift: missing={sorted(names - headings)}, "
        f"stale={sorted(headings - names)}"
    )

    for event in names:
        section = event_map.split(f"### {event}\n", 1)[1].split("\n### ", 1)[0]
        assert "| **Durability** |" in section, f"{event} has no durability row"
        assert "| **Consumers** |" in section, f"{event} has no consumers row"
        consumer = section.split("| **Consumers** |", 1)[1].split("|", 1)[0].strip()
        assert consumer, f"{event} has an empty consumers row; use 'none' explicitly"


def test_behavior_map_covers_new_public_commands():
    """Drift predicate (item 12, scoped per GLM review).

    Freezes today's top-level CLI surface: any NEW dispatch command must be
    added to docs/behavior-map.md (or consciously moved into the whitelist
    with a documentation pointer) before it can merge.
    """
    import ast

    src = (Path(ROOT) / "fettle" / "cli.py").read_text(encoding="utf-8")
    table = (Path(ROOT) / "docs" / "behavior-map.md").read_text(
        encoding="utf-8")

    tree = ast.parse(src)
    registered = set()
    public = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "commands"
            for target in node.targets
        ) and isinstance(node.value, ast.Dict):
            registered.update(
                key.value for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not (
            node.func.attr == "add_parser"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subparsers"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            continue
        help_value = next((kw.value for kw in node.keywords if kw.arg == "help"), None)
        if help_value is not None:
            public.add(node.args[0].value)

    assert registered, "dispatch dict discovery broke"
    assert public, "public parser discovery broke"
    assert registered == public, (
        f"dispatch/parser mismatch: registered-only={sorted(registered - public)}, "
        f"parser-only={sorted(public - registered)}"
    )

    covered = {name for name in public
               if f"fettle {name}" in table or f"`{name}`" in table}

    infrastructure_commands = {"completion", "lsp", "worktree"}

    missing = sorted(public - covered - infrastructure_commands)
    assert not missing, (
        f"new public commands missing from docs/behavior-map.md: {missing}"
    )
