"""WP-17 anti-drift: commands/*.md must track the real CLI.

The workflow command files are prompts that tell agents which commands to
run. They rotted once already (19 ${CLAUDE_PLUGIN_ROOT}/scripts refs after
the CLI shipped) — these tests pin them to reality the same way the schema
drift test pins docs/fettle.schema.json to config.DEFAULTS.
"""

import re
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COMMANDS = sorted((REPO / "commands").glob("*.md"))


def _cli_subcommands() -> set[str]:
    """The dispatch dict in cli.main() is the source of truth."""
    src = (REPO / "fettle" / "cli.py").read_text(encoding="utf-8")
    subs = set(re.findall(r'^\s+"([a-z-]+)": cmd_[a-z_]+,$', src, re.MULTILINE))
    assert "check" in subs and "doctor" in subs, "failed to parse cli.py dispatch dict"
    return subs


def test_commands_exist():
    assert len(COMMANDS) >= 17


def test_no_claude_plugin_root_refs():
    """Commands must be host-agnostic — no Claude-plugin-only path variables."""
    offenders = [c.name for c in COMMANDS if "CLAUDE_PLUGIN_ROOT" in c.read_text(encoding="utf-8")]
    assert offenders == [], f"CLAUDE_PLUGIN_ROOT referenced in: {offenders}"


def test_no_scripts_run_sh_refs():
    offenders = [c.name for c in COMMANDS if "scripts/run.sh" in c.read_text(encoding="utf-8")]
    assert offenders == [], f"legacy scripts/run.sh referenced in: {offenders}"


def test_active_hook_launchers_exist(capsys):
    hooks = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for groups in hooks["hooks"].values()
        for group in groups
        for hook in group["hooks"]
        if hook["type"] == "command" and "run.sh" in hook["command"]
    ]
    assert commands
    assert all("/fettle/run.sh" in command for command in commands)
    assert (REPO / "fettle" / "run.sh").is_file()

    from fettle.install import install_hooks

    install_hooks(REPO)
    assert f"bash {REPO}/fettle/run.sh post_edit.py" in capsys.readouterr().out


def test_every_referenced_fettle_subcommand_exists():
    known = _cli_subcommands()
    unknown: list[str] = []
    for cmd_file in COMMANDS:
        text = cmd_file.read_text(encoding="utf-8")
        # `fettle <word>` where fettle is a standalone token (not .fettle.toml,
        # .fettle/ paths, or prose like "Fettle checks" — lowercase + space).
        for sub in re.findall(r"(?<![.\w/-])fettle ([a-z][a-z0-9-]*)", text):
            if sub not in known:
                unknown.append(f"{cmd_file.name}: fettle {sub}")
    assert unknown == [], f"commands reference nonexistent subcommands: {unknown}"


def test_every_referenced_fettle_module_exists():
    missing: list[str] = []
    for cmd_file in COMMANDS:
        text = cmd_file.read_text(encoding="utf-8")
        for mod in re.findall(r"python3? -m (fettle\.[a-z_]+)", text):
            rel = mod.replace(".", "/") + ".py"
            if not (REPO / rel).is_file():
                missing.append(f"{cmd_file.name}: {mod}")
    assert missing == [], f"commands reference nonexistent modules: {missing}"


def test_templates_referenced_by_commands_exist():
    """ops-review/preflight resolve templates via _resources.templates_dir()."""
    from fettle._resources import templates_dir
    tdir = templates_dir()
    for name in ("ops-review.md", "preflight.md"):
        assert (tdir / name).is_file(), f"missing template {name} in {tdir}"
