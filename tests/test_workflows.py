"""WP-18 — cross-environment workflow distribution.

Renderer goldens per host, frontmatter parsing, TOML escaping, marker
idempotency, scope matrix, resource resolution, init wiring, doctor probe.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from fettle import workflows
from fettle._resources import commands_dir
from fettle.workflows import (
    AGENTS,
    MD_MARKER,
    TOML_MARKER,
    Workflow,
    check_workflows,
    install,
    install_for_init,
    list_rows,
    load_workflows,
    parse_command,
    render_claude,
    render_codex,
    render_gemini,
    render_opencode,
    render_vscode,
    target_path,
)

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Fake $HOME with every agent 'installed'."""
    home = tmp_path / "home"
    for d in (".claude", ".codex", ".gemini", ".config/opencode"):
        (home / d).mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return home


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".github").mkdir(parents=True)  # makes vscode 'detected'
    return repo


W = Workflow(name="quality", description='Run "full" scan',
             argument_hint="[--baseline FILE]", user_invocable=True,
             body="# /fettle:quality\n\nRun `fettle check --all` with $ARGUMENTS.\n")


# ── Parsing ─────────────────────────────────────────────────────────────

def test_parse_frontmatter():
    w = parse_command(REPO / "commands" / "quality.md")
    assert w.name == "quality"
    assert w.description.startswith("Run full Fettle quality scan")
    assert w.argument_hint == "[--baseline FILE]"
    assert w.user_invocable
    assert w.body.startswith("Run `fettle check --all`")
    assert "---" not in w.body.split("\n")[0]


def test_parse_no_frontmatter_falls_back(tmp_path):
    p = tmp_path / "thing.md"
    p.write_text("# /fettle:thing\n\nDoes the thing.\n\nMore text.\n")
    w = parse_command(p)
    assert w.name == "thing"
    assert w.description == "Does the thing."
    assert w.user_invocable


def test_parse_user_invocable_false(tmp_path):
    p = tmp_path / "hidden.md"
    p.write_text("---\nname: hidden\nuser-invocable: false\n---\nbody\n")
    assert not parse_command(p).user_invocable
    (tmp_path / "shown.md").write_text("---\nname: shown\n---\nbody\n")
    names = [w.name for w in load_workflows(tmp_path)]
    assert names == ["shown"]


def test_load_workflows_covers_all_command_files():
    flows = load_workflows()
    assert len(flows) == len(list((REPO / "commands").glob("*.md")))


# ── Renderers ───────────────────────────────────────────────────────────

def test_render_vscode_golden():
    out = render_vscode(W)
    assert out.startswith('---\nname: "fettle-quality"\n')
    assert 'description: "Run \\"full\\" scan"' in out
    assert 'argument-hint: "[--baseline FILE]"' in out
    assert MD_MARKER in out
    assert "$ARGUMENTS refers to any text" in out  # bridge preamble
    assert "Run `fettle check --all` with $ARGUMENTS." in out


def test_render_vscode_no_preamble_without_arguments():
    w = Workflow("x", "d", "", True, "no placeholders here\n")
    assert "$ARGUMENTS" not in render_vscode(w)


def test_render_codex_golden():
    out = render_codex(W)
    assert "name:" not in out  # codex derives the name from the filename
    assert 'description: "Run \\"full\\" scan"' in out
    assert MD_MARKER in out
    assert "$ARGUMENTS" in out  # native support — body untouched


def test_render_opencode_golden():
    out = render_opencode(W)
    assert out.startswith('---\ndescription: "Run \\"full\\" scan"\n---\n')
    assert MD_MARKER in out


def test_render_claude_keeps_canonical_fields():
    out = render_claude(W)
    assert 'name: "quality"' in out
    assert 'argument-hint: "[--baseline FILE]"' in out


def test_render_gemini_golden():
    out = render_gemini(W)
    assert out.startswith(TOML_MARKER)
    assert 'description = "Run \\"full\\" scan"' in out
    assert "{{args}}" in out and "$ARGUMENTS" not in out
    assert 'prompt = """' in out


def test_render_gemini_escapes_toml():
    w = Workflow("x", 'quo"te', "", True, 'back\\slash and """ triple\n')
    out = render_gemini(w)
    assert 'description = "quo\\"te"' in out
    assert "back\\\\slash" in out
    assert '\\"\\"\\"' in out  # embedded triple-quote cannot terminate the string


def test_gemini_renders_are_valid_toml():
    import tomllib
    for w in load_workflows():
        data = tomllib.loads(render_gemini(w))
        assert data["prompt"].strip()
        assert "CLAUDE_PLUGIN_ROOT" not in data["prompt"]


def test_all_renderers_handle_all_commands():
    renderers = (render_claude, render_vscode, render_codex,
                 render_gemini, render_opencode)
    for w in load_workflows():
        for render in renderers:
            out = render(w)
            assert w.description.split('"')[0][:20] in out or w.description == ""


# ── Scope matrix ────────────────────────────────────────────────────────

def test_target_paths(repo, home):
    assert target_path("vscode", "project", "quality", repo) == \
        repo / ".github" / "prompts" / "fettle-quality.prompt.md"
    assert target_path("vscode", "user", "quality", repo) is None
    assert target_path("codex", "project", "quality", repo) is None
    assert target_path("codex", "user", "quality", repo) == \
        home / ".codex" / "prompts" / "fettle-quality.md"
    assert target_path("gemini", "project", "quality", repo) == \
        repo / ".gemini" / "commands" / "fettle" / "quality.toml"
    assert target_path("opencode", "user", "quality", repo) == \
        home / ".config" / "opencode" / "commands" / "fettle-quality.md"
    assert target_path("claude", "project", "quality", repo) == \
        repo / ".claude" / "commands" / "fettle" / "quality.md"


def test_unsupported_scopes_are_actions(repo, home):
    steps = install(["codex"], "project", repo)
    assert steps[0].status == "action" and "--user" in steps[0].detail
    steps = install(["vscode"], "user", repo)
    assert steps[0].status == "action"


# ── Install semantics ───────────────────────────────────────────────────

def test_install_creates_and_is_idempotent(repo, home):
    steps = install(["vscode"], "project", repo)
    assert steps[0].status == "created"
    files = list((repo / ".github" / "prompts").glob("fettle-*.prompt.md"))
    assert len(files) == len(load_workflows())
    again = install(["vscode"], "project", repo)
    assert again[0].status == "ok" and "current" in again[0].detail


def test_install_updates_marker_owned_but_not_user_owned(repo, home):
    install(["vscode"], "project", repo)
    target = repo / ".github" / "prompts" / "fettle-quality.prompt.md"
    # marker present → regenerated
    target.write_text(target.read_text() + "\ndrift\n")
    steps = install(["vscode"], "project", repo)
    assert steps[0].status == "created" and "drift" not in target.read_text()
    # marker stripped → user-owned, never clobbered
    owned = target.read_text().replace(MD_MARKER, "")
    target.write_text(owned)
    steps = install(["vscode"], "project", repo)
    conflicts = [s for s in steps if s.status == "action"]
    assert conflicts and "without the fettle marker" in conflicts[0].detail
    assert target.read_text() == owned


def test_install_dry_run_writes_nothing(repo, home):
    steps = install(["gemini"], "project", repo, dry_run=True)
    assert steps[0].status == "created" and "(dry-run)" in steps[0].detail
    assert not (repo / ".gemini").exists()


def test_install_detect_skips_missing_hosts(repo, tmp_path, monkeypatch):
    bare = tmp_path / "barehome"
    bare.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: bare))
    steps = install(["codex"], "user", repo, detect=True)
    assert steps[0].status == "skipped"


def test_install_claude_defers_to_plugin_symlink(repo, home):
    link = home / ".claude" / "plugins" / "fettle"
    link.parent.mkdir(parents=True)
    link.symlink_to(REPO)
    steps = install(["claude"], "project", repo)
    assert steps[0].status == "ok" and "plugin symlink" in steps[0].detail


def test_install_for_init_covers_detected_hosts(repo, home):
    statuses = {s.name: s.status for s in install_for_init(repo, dry_run=True)}
    assert set(statuses) == {f"workflows:{a}" for a in AGENTS}
    assert statuses["workflows:codex"] == "created"  # user scope, dry-run


# ── Doctor probe ────────────────────────────────────────────────────────

def test_check_workflows_reports_missing_then_current(repo, home, monkeypatch):
    monkeypatch.setattr(workflows.Path, "cwd", staticmethod(lambda: repo))
    checks = {c["name"]: c for c in check_workflows(repo)}
    assert not checks["workflows-vscode"]["ok"]
    assert "fettle workflows install" in checks["workflows-vscode"]["detail"]
    install(["vscode"], "project", repo)
    checks = {c["name"]: c for c in check_workflows(repo)}
    assert checks["workflows-vscode"]["ok"]


def test_check_workflows_user_owned_counts_as_current(repo, home):
    install(["vscode"], "project", repo)
    target = repo / ".github" / "prompts" / "fettle-quality.prompt.md"
    target.write_text(target.read_text().replace(MD_MARKER, "") + "\nmine\n")
    checks = {c["name"]: c for c in check_workflows(repo)}
    assert checks["workflows-vscode"]["ok"]


# ── Listing + CLI + resources ───────────────────────────────────────────

def test_list_rows_invocations():
    rows = {r["name"]: r for r in list_rows()}
    q = rows["quality"]
    assert q["invocations"]["claude"] == "/fettle:quality"
    assert q["invocations"]["vscode"] == "/fettle-quality"
    assert q["invocations"]["codex"] == "/prompts:fettle-quality"
    assert q["invocations"]["gemini"] == "/fettle:quality"


def test_commands_dir_resolution(tmp_path, monkeypatch):
    assert commands_dir() == REPO / "commands"  # clone mode
    override = tmp_path / "plug"
    (override / "commands").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(override))
    assert commands_dir() == override / "commands"


def test_cli_workflows_list_smoke():
    proc = subprocess.run(
        [sys.executable, "-m", "fettle", "workflows", "list", "--json"],
        capture_output=True, text=True, cwd=str(REPO), timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    import json
    names = [w["name"] for w in json.loads(proc.stdout)["workflows"]]
    assert "quality" in names and "preflight" in names
