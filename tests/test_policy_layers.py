"""Tests for WP-126: Policy layering — discover, merge, explain."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from fettle.policy_layers import (
    PolicyLayer,
    discover_layers,
    explain_config,
    load_config_layered,
    resolve_config,
    resolve_config_for_path,
    verify_bundle,
)


# ---------------------------------------------------------------------------
# Default-only resolution
# ---------------------------------------------------------------------------


def test_defaults_only_when_no_files(tmp_path):
    """With no config files anywhere, only the defaults layer is discovered."""
    layers = discover_layers(tmp_path)
    assert len(layers) == 1
    assert layers[0].name == "defaults"
    assert layers[0].priority == 0
    assert layers[0].source == "built-in"


def test_defaults_resolution_matches_builtin():
    """resolve_config with only defaults returns a copy of DEFAULTS."""
    from fettle.config import DEFAULTS

    layer = PolicyLayer(name="defaults", source="built-in", config=DEFAULTS.copy(), priority=0)
    cfg = resolve_config([layer])
    assert cfg["gates"]["lint"]["enabled"] is True
    assert cfg["gates"]["lint"]["mode"] == "advisory"


# ---------------------------------------------------------------------------
# Org + repo merge
# ---------------------------------------------------------------------------


def test_org_layer_discovered(tmp_path, monkeypatch):
    """Org pack at $XDG_CONFIG_HOME/fettle/org.toml is picked up."""
    config_home = tmp_path / "xdg_config"
    config_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    fettle_dir = config_home / "fettle"
    fettle_dir.mkdir()
    (fettle_dir / "org.toml").write_text("""
_name = "acme"
[gates.lint]
mode = "enforce"
""")

    project = tmp_path / "project"
    project.mkdir()

    layers = discover_layers(project)
    names = [lyr.name for lyr in layers]
    assert "org:acme" in names
    org_layer = next(lyr for lyr in layers if lyr.name == "org:acme")
    assert org_layer.priority == 10
    assert org_layer.config["gates"]["lint"]["mode"] == "enforce"


def test_org_plus_repo_merge(tmp_path, monkeypatch):
    """Org sets lint mode to enforce, repo overrides a different key; both apply."""
    config_home = tmp_path / "xdg_config"
    (config_home / "fettle").mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    (config_home / "fettle" / "org.toml").write_text("""
_name = "acme"
[gates.lint]
mode = "enforce"
""")

    project = tmp_path / "project"
    project.mkdir()
    (project / ".fettle.toml").write_text("""
[gates.plan]
enabled = true
""")

    layers = discover_layers(project)
    cfg = resolve_config(layers)

    # Org's enforce setting wins over defaults
    assert cfg["gates"]["lint"]["mode"] == "enforce"
    # Repo's plan enabled wins
    assert cfg["gates"]["plan"]["enabled"] is True
    # Default lint enabled still there
    assert cfg["gates"]["lint"]["enabled"] is True


def test_repo_overrides_org(tmp_path, monkeypatch):
    """Repo layer (priority 30) overrides org layer (priority 10)."""
    config_home = tmp_path / "xdg_config"
    (config_home / "fettle").mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    (config_home / "fettle" / "org.toml").write_text("""
[gates.lint]
mode = "enforce"
""")

    project = tmp_path / "project"
    project.mkdir()
    (project / ".fettle.toml").write_text("""
[gates.lint]
mode = "advisory"
""")

    layers = discover_layers(project)
    cfg = resolve_config(layers)
    assert cfg["gates"]["lint"]["mode"] == "advisory"


# ---------------------------------------------------------------------------
# Team layer
# ---------------------------------------------------------------------------


def test_team_layer_discovered(tmp_path, monkeypatch):
    """Team pack at $XDG_CONFIG_HOME/fettle/team.toml is picked up."""
    config_home = tmp_path / "xdg_config"
    (config_home / "fettle").mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    (config_home / "fettle" / "team.toml").write_text("""
_name = "platform"
[gates.docs]
enabled = true
mode = "enforce"
""")

    project = tmp_path / "project"
    project.mkdir()

    layers = discover_layers(project)
    names = [lyr.name for lyr in layers]
    assert "team:platform" in names
    team_layer = next(lyr for lyr in layers if lyr.name == "team:platform")
    assert team_layer.priority == 20


# ---------------------------------------------------------------------------
# Directory override scoping
# ---------------------------------------------------------------------------


def test_directory_override_discovered(tmp_path):
    """A .fettle.toml in a subdirectory creates a dir: layer."""
    project = tmp_path / "project"
    (project / "src" / "api").mkdir(parents=True)
    (project / "src" / "api" / ".fettle.toml").write_text("""
[gates.lint]
mode = "enforce"
""")

    layers = discover_layers(project)
    dir_layers = [lyr for lyr in layers if lyr.priority == 40]
    assert len(dir_layers) == 1
    assert dir_layers[0].name == "dir:src/api"


def test_directory_override_scoped_to_path(tmp_path):
    """Directory overrides apply only to files within that directory."""
    project = tmp_path / "project"
    (project / "src" / "api").mkdir(parents=True)
    (project / "src" / "api" / ".fettle.toml").write_text("""
[gates.lint]
mode = "enforce"
""")

    layers = discover_layers(project)

    # File inside src/api/ gets the override
    cfg_inside = resolve_config_for_path(layers, "src/api/handler.py", project)
    assert cfg_inside["gates"]["lint"]["mode"] == "enforce"

    # File outside src/api/ does NOT get the override
    cfg_outside = resolve_config_for_path(layers, "src/utils/helper.py", project)
    assert cfg_outside["gates"]["lint"]["mode"] == "advisory"


def test_multiple_directory_overrides(tmp_path):
    """Multiple directories can have independent overrides."""
    project = tmp_path / "project"
    (project / "src" / "api").mkdir(parents=True)
    (project / "src" / "web").mkdir(parents=True)

    (project / "src" / "api" / ".fettle.toml").write_text("""
[gates.lint]
mode = "enforce"
""")
    (project / "src" / "web" / ".fettle.toml").write_text("""
[gates.docs]
enabled = true
""")

    layers = discover_layers(project)

    cfg_api = resolve_config_for_path(layers, "src/api/handler.py", project)
    assert cfg_api["gates"]["lint"]["mode"] == "enforce"
    assert cfg_api["gates"]["docs"]["enabled"] is False  # web override doesn't apply

    cfg_web = resolve_config_for_path(layers, "src/web/page.py", project)
    assert cfg_web["gates"]["lint"]["mode"] == "advisory"  # api override doesn't apply
    assert cfg_web["gates"]["docs"]["enabled"] is True


# ---------------------------------------------------------------------------
# Provenance explanation
# ---------------------------------------------------------------------------


def test_explain_single_layer():
    """Explain shows a single source when only defaults define a key."""
    layers = [PolicyLayer(
        name="defaults", source="built-in",
        config={"gates": {"lint": {"mode": "advisory"}}},
        priority=0,
    )]
    result = explain_config(layers, "gates.lint.mode")
    assert len(result) == 1
    assert result[0] == {"layer": "defaults", "value": "advisory"}


def test_explain_override_chain():
    """Explain shows the full chain: defaults -> repo override."""
    layers = [
        PolicyLayer(
            name="defaults", source="built-in",
            config={"gates": {"lint": {"mode": "advisory"}}},
            priority=0,
        ),
        PolicyLayer(
            name="repo", source="/project/.fettle.toml",
            config={"gates": {"lint": {"mode": "enforce"}}},
            priority=30,
        ),
    ]
    result = explain_config(layers, "gates.lint.mode")
    assert len(result) == 2
    assert result[0] == {"layer": "defaults", "value": "advisory"}
    assert result[1] == {"layer": "repo", "value": "enforce"}


def test_explain_missing_key():
    """Explain returns empty list for a key that no layer sets."""
    layers = [PolicyLayer(
        name="defaults", source="built-in",
        config={"gates": {"lint": {"mode": "advisory"}}},
        priority=0,
    )]
    result = explain_config(layers, "nonexistent.key.path")
    assert result == []


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------


def test_priority_order_is_correct(tmp_path, monkeypatch):
    """Layers come back sorted: defaults < org < team < repo < dir."""
    config_home = tmp_path / "xdg_config"
    (config_home / "fettle").mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    (config_home / "fettle" / "org.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    (config_home / "fettle" / "team.toml").write_text('[gates.docs]\nenabled = true\n')

    project = tmp_path / "project"
    project.mkdir()
    (project / ".fettle.toml").write_text('[gates.plan]\nenabled = true\n')
    (project / "src").mkdir()
    (project / "src" / ".fettle.toml").write_text('[gates.lint]\nmode = "advisory"\n')

    layers = discover_layers(project)
    priorities = [lyr.priority for lyr in layers]
    assert priorities == sorted(priorities)
    assert priorities == [0, 10, 20, 30, 40]


# ---------------------------------------------------------------------------
# Missing / corrupt layer files handled gracefully
# ---------------------------------------------------------------------------


def test_corrupt_org_toml_skipped(tmp_path, monkeypatch, capsys):
    """A corrupt org.toml is skipped with a warning, not a crash."""
    config_home = tmp_path / "xdg_config"
    (config_home / "fettle").mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    (config_home / "fettle" / "org.toml").write_text("this is not valid [[[ toml")

    project = tmp_path / "project"
    project.mkdir()

    layers = discover_layers(project)
    # Only defaults should be present (org was skipped)
    assert len(layers) == 1
    assert layers[0].name == "defaults"

    captured = capsys.readouterr()
    assert "could not parse" in captured.err


def test_corrupt_repo_toml_skipped(tmp_path, capsys):
    """A corrupt .fettle.toml in the repo is skipped gracefully."""
    project = tmp_path / "project"
    project.mkdir()
    (project / ".fettle.toml").write_text("invalid {{{ toml content")

    layers = discover_layers(project)
    assert len(layers) == 1
    assert layers[0].name == "defaults"

    captured = capsys.readouterr()
    assert "could not parse" in captured.err


def test_missing_config_home_no_crash(tmp_path, monkeypatch):
    """If XDG_CONFIG_HOME points to nonexistent dir, no crash."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nonexistent"))

    project = tmp_path / "project"
    project.mkdir()

    layers = discover_layers(project)
    assert len(layers) == 1
    assert layers[0].name == "defaults"


def test_hidden_dirs_skipped_for_directory_overrides(tmp_path):
    """Hidden directories and node_modules are not scanned for overrides."""
    project = tmp_path / "project"
    (project / ".git" / "hooks").mkdir(parents=True)
    (project / ".git" / "hooks" / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    (project / "node_modules" / "pkg").mkdir(parents=True)
    (project / "node_modules" / "pkg" / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')

    layers = discover_layers(project)
    dir_layers = [lyr for lyr in layers if lyr.priority == 40]
    assert len(dir_layers) == 0


# ---------------------------------------------------------------------------
# Signed bundles (stub)
# ---------------------------------------------------------------------------


def test_verify_bundle_valid(tmp_path):
    """A valid TOML with _signed field passes verification."""
    bundle = tmp_path / "bundle.toml"
    bundle.write_text("""
_signed = "placeholder-signature-v1"
[gates.lint]
mode = "enforce"
""")
    assert verify_bundle(bundle) is True


def test_verify_bundle_missing_signed_field(tmp_path):
    """A valid TOML without _signed field fails verification."""
    bundle = tmp_path / "bundle.toml"
    bundle.write_text("""
[gates.lint]
mode = "enforce"
""")
    assert verify_bundle(bundle) is False


def test_verify_bundle_invalid_toml(tmp_path):
    """Invalid TOML fails verification."""
    bundle = tmp_path / "bundle.toml"
    bundle.write_text("not valid [[[ toml")
    assert verify_bundle(bundle) is False


def test_verify_bundle_missing_file(tmp_path):
    """Nonexistent file fails verification."""
    assert verify_bundle(tmp_path / "nonexistent.toml") is False


# ---------------------------------------------------------------------------
# load_config_layered backwards compatibility
# ---------------------------------------------------------------------------


def test_load_config_layered_no_files(tmp_path, monkeypatch):
    """load_config_layered with no config files returns same as defaults."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty_xdg"))
    # Clear any FETTLE_GATE_MODE
    monkeypatch.delenv("FETTLE_GATE_MODE", raising=False)

    from fettle.config import DEFAULTS

    cfg = load_config_layered(str(tmp_path))
    assert cfg["gates"]["lint"]["mode"] == DEFAULTS["gates"]["lint"]["mode"]
    assert cfg["gates"]["lint"]["enabled"] == DEFAULTS["gates"]["lint"]["enabled"]


def test_load_config_layered_with_repo_file(tmp_path, monkeypatch):
    """load_config_layered picks up repo .fettle.toml like load_config does."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty_xdg"))
    monkeypatch.delenv("FETTLE_GATE_MODE", raising=False)

    (tmp_path / ".fettle.toml").write_text("""
[gates.lint]
mode = "enforce"
""")
    cfg = load_config_layered(str(tmp_path))
    assert cfg["gates"]["lint"]["mode"] == "enforce"


def test_load_config_layered_env_override(tmp_path, monkeypatch):
    """FETTLE_GATE_MODE env var still works with layered loader."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty_xdg"))
    monkeypatch.setenv("FETTLE_GATE_MODE", "enforce")

    cfg = load_config_layered(str(tmp_path))
    assert cfg["gates"]["lint"]["mode"] == "enforce"
