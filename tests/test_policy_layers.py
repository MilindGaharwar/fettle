"""Tests for the unified config resolver (WP-20) and provenance engine.

One resolver: defaults → org → team → remote [extends] → repo → directory
overrides (path-scoped) → env → capsule. Inspection == runtime by parity.
"""

import copy

import pytest

from fettle.config import (
    DEFAULTS,
    PolicyLayer,
    load_config,
    resolve_with_provenance,
)
from fettle.policy_layers import (
    discover_directory_layers,
    discover_layers,
    explain_config,
    load_config_layered,
    resolve_config,
)


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch, tmp_path):
    """Every test gets an empty XDG config home and clean fettle env."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg_config"))
    for var in ("FETTLE_GATE_MODE", "FETTLE_POLICY_CAPSULE", "FETTLE_CONFIG"):
        monkeypatch.delenv(var, raising=False)


def _packs_dir(tmp_path):
    d = tmp_path / "xdg_config" / "fettle"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _project(tmp_path):
    p = tmp_path / "project"
    p.mkdir(exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Default-only resolution
# ---------------------------------------------------------------------------


def test_defaults_only_when_no_files(tmp_path):
    """With no config files anywhere, only the defaults layer exists."""
    cfg, layers = resolve_with_provenance(str(_project(tmp_path)))
    assert [lyr.name for lyr in layers] == ["defaults"]
    assert layers[0].source == "built-in"
    assert cfg == DEFAULTS
    assert cfg is not DEFAULTS  # deep-copied, never aliased


# ---------------------------------------------------------------------------
# Org / team / repo layers
# ---------------------------------------------------------------------------


def test_org_layer_discovered_and_enforced(tmp_path):
    packs = _packs_dir(tmp_path)
    (packs / "org.toml").write_text('_name = "acme"\n[gates.lint]\nmode = "enforce"\n')
    project = _project(tmp_path)

    cfg, layers = resolve_with_provenance(str(project))
    org = next(lyr for lyr in layers if lyr.name == "org:acme")
    assert org.source == str(packs / "org.toml")
    assert "_name" not in cfg  # popped for naming, never merged
    # H-05 closed: the pack is enforced at runtime, not just displayed.
    assert load_config(str(project))["gates"]["lint"]["mode"] == "enforce"


def test_team_layer_discovered(tmp_path):
    packs = _packs_dir(tmp_path)
    (packs / "team.toml").write_text('_name = "platform"\n[gates.docs]\nenabled = true\n')

    cfg, layers = resolve_with_provenance(str(_project(tmp_path)))
    assert "team:platform" in [lyr.name for lyr in layers]
    assert cfg["gates"]["docs"]["enabled"] is True


def test_precedence_org_team_repo(tmp_path):
    """Same key set at every level: repo > team > org > defaults."""
    packs = _packs_dir(tmp_path)
    (packs / "org.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    (packs / "team.toml").write_text('[gates.lint]\nmode = "soft"\n')
    project = _project(tmp_path)
    (project / ".fettle.toml").write_text('[gates.lint]\nmode = "advisory"\n')

    cfg, layers = resolve_with_provenance(str(project))
    assert cfg["gates"]["lint"]["mode"] == "advisory"
    chain = explain_config(layers, "gates.lint.mode")
    assert [c["layer"] for c in chain] == ["defaults", "org:org", "team:team", "repo"]
    assert chain[-1]["value"] == "advisory"


def test_org_plus_repo_merge_disjoint_keys(tmp_path):
    packs = _packs_dir(tmp_path)
    (packs / "org.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    project = _project(tmp_path)
    (project / ".fettle.toml").write_text("[gates.plan]\nenabled = true\n")

    cfg = load_config(str(project))
    assert cfg["gates"]["lint"]["mode"] == "enforce"
    assert cfg["gates"]["plan"]["enabled"] is True
    assert cfg["gates"]["lint"]["enabled"] is True  # default survives


# ---------------------------------------------------------------------------
# Remote [extends] layer — under repo, over team
# ---------------------------------------------------------------------------


def test_remote_layer_between_team_and_repo(tmp_path, monkeypatch):
    packs = _packs_dir(tmp_path)
    (packs / "team.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    project = _project(tmp_path)
    (project / ".fettle.toml").write_text(
        '[extends]\nurl = "https://example.com/policy.toml"\nsha256 = "abc"\n'
        '[gates.docs]\nenabled = true\n'
    )
    import fettle.policy_remote as pr
    monkeypatch.setattr(
        pr, "resolve_cached_policy",
        lambda raw: {"gates": {"lint": {"mode": "soft"}, "plan": {"enabled": True}}},
    )

    cfg, layers = resolve_with_provenance(str(project))
    names = [lyr.name for lyr in layers]
    assert names == ["defaults", "team:team", "remote", "repo"]
    remote = layers[names.index("remote")]
    assert remote.source == "https://example.com/policy.toml"
    # remote overrides team; repo's disjoint key still applies
    assert cfg["gates"]["lint"]["mode"] == "soft"
    assert cfg["gates"]["plan"]["enabled"] is True
    assert cfg["gates"]["docs"]["enabled"] is True


# ---------------------------------------------------------------------------
# Directory overrides — path-scoped only, ancestor walk
# ---------------------------------------------------------------------------


def test_directory_override_applies_for_path_only(tmp_path):
    project = _project(tmp_path)
    (project / "src" / "api").mkdir(parents=True)
    (project / "src" / "api" / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')

    inside = load_config(str(project), for_path=str(project / "src" / "api" / "handler.py"))
    assert inside["gates"]["lint"]["mode"] == "enforce"

    outside = load_config(str(project), for_path=str(project / "src" / "handler.py"))
    assert outside["gates"]["lint"]["mode"] == "advisory"

    pathless = load_config(str(project))
    assert pathless["gates"]["lint"]["mode"] == "advisory"


def test_nested_directory_overrides_deeper_wins(tmp_path):
    project = _project(tmp_path)
    (project / "src" / "api").mkdir(parents=True)
    (project / "src" / ".fettle.toml").write_text(
        '[gates.lint]\nmode = "soft"\n[gates.docs]\nenabled = true\n'
    )
    (project / "src" / "api" / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')

    cfg, layers = resolve_with_provenance(
        str(project), for_path=str(project / "src" / "api" / "handler.py")
    )
    assert [lyr.name for lyr in layers if lyr.name.startswith("dir:")] == [
        "dir:src", "dir:src/api",
    ]
    assert cfg["gates"]["lint"]["mode"] == "enforce"  # deeper wins
    assert cfg["gates"]["docs"]["enabled"] is True    # shallower still merges


def test_directory_override_beats_repo(tmp_path):
    project = _project(tmp_path)
    (project / ".fettle.toml").write_text('[gates.lint]\nmode = "soft"\n')
    (project / "src").mkdir()
    (project / "src" / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')

    cfg = load_config(str(project), for_path=str(project / "src" / "x.py"))
    assert cfg["gates"]["lint"]["mode"] == "enforce"


def test_relative_for_path_resolved_against_root(tmp_path):
    project = _project(tmp_path)
    (project / "src").mkdir()
    (project / "src" / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')

    cfg = load_config(str(project), for_path="src/x.py")
    assert cfg["gates"]["lint"]["mode"] == "enforce"


def test_for_path_outside_root_gets_root_scope(tmp_path):
    project = _project(tmp_path)
    (project / "src").mkdir()
    (project / "src" / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')

    cfg = load_config(str(project), for_path=str(tmp_path / "elsewhere" / "x.py"))
    assert cfg["gates"]["lint"]["mode"] == "advisory"


def test_hidden_and_noise_ancestors_ignored(tmp_path):
    project = _project(tmp_path)
    for noise in (".git", "node_modules"):
        (project / noise / "pkg").mkdir(parents=True)
        (project / noise / "pkg" / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')

    for noise in (".git", "node_modules"):
        cfg = load_config(str(project), for_path=str(project / noise / "pkg" / "x.py"))
        assert cfg["gates"]["lint"]["mode"] == "advisory"


def test_discover_directory_layers_listing(tmp_path):
    project = _project(tmp_path)
    (project / "src" / "api").mkdir(parents=True)
    (project / "src" / "api" / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    (project / "node_modules" / "pkg").mkdir(parents=True)
    (project / "node_modules" / "pkg" / ".fettle.toml").write_text("[gates.lint]\n")
    (project / ".fettle.toml").write_text("[gates.plan]\n")  # repo layer, not a dir layer

    listed = discover_directory_layers(project)
    assert [lyr.name for lyr in listed] == ["dir:src/api"]


def test_discover_layers_excludes_dir_layers(tmp_path):
    project = _project(tmp_path)
    (project / "src").mkdir()
    (project / "src" / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')

    assert [lyr.name for lyr in discover_layers(project)] == ["defaults"]


# ---------------------------------------------------------------------------
# Env and capsule pseudo-layers (applied diffs)
# ---------------------------------------------------------------------------


def test_env_mode_pseudo_layer(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_GATE_MODE", "enforce")
    cfg, layers = resolve_with_provenance(str(_project(tmp_path)))
    env = layers[-1]
    assert env.name == "env:FETTLE_GATE_MODE"
    assert env.source == "FETTLE_GATE_MODE=enforce"
    # Applied diff only: docs.mode already defaults to "enforce", so only
    # the lint change is attributed to the env layer.
    assert env.config == {"gates": {"lint": {"mode": "enforce"}}}
    assert cfg["gates"]["lint"]["mode"] == "enforce"


def test_env_off_pseudo_layer_disables_gates(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_GATE_MODE", "off")
    cfg, layers = resolve_with_provenance(str(_project(tmp_path)))
    env = next(lyr for lyr in layers if lyr.name == "env:FETTLE_GATE_MODE")
    assert env.config["gates"]["lint"] == {"enabled": False}
    assert not cfg["gates"]["lint"]["enabled"]


def test_no_env_layer_when_mode_is_noop(tmp_path):
    """No FETTLE_GATE_MODE → no env pseudo-layer at all."""
    _, layers = resolve_with_provenance(str(_project(tmp_path)))
    assert not any(lyr.name.startswith("env:") for lyr in layers)


def test_capsule_pseudo_layer_carries_applied_diff(tmp_path, monkeypatch):
    import fettle.policy_capsule as pc

    def fake_capsule(cfg):
        out = copy.deepcopy(cfg)
        out["gates"]["lint"]["mode"] = "enforce"
        return out

    monkeypatch.setattr(pc, "apply_env_capsule", fake_capsule)
    cfg, layers = resolve_with_provenance(str(_project(tmp_path)))
    assert layers[-1].name == "capsule"
    assert layers[-1].config == {"gates": {"lint": {"mode": "enforce"}}}
    assert cfg["gates"]["lint"]["mode"] == "enforce"


def test_capsule_applies_over_env(tmp_path, monkeypatch):
    """Kill-switch env vars cannot weaken delegated policy (D-A3)."""
    import fettle.policy_capsule as pc

    def fake_capsule(cfg):
        out = copy.deepcopy(cfg)
        out["gates"]["lint"]["enabled"] = True
        return out

    monkeypatch.setattr(pc, "apply_env_capsule", fake_capsule)
    monkeypatch.setenv("FETTLE_GATE_MODE", "off")
    cfg, layers = resolve_with_provenance(str(_project(tmp_path)))
    assert cfg["gates"]["lint"]["enabled"] is True
    assert layers[-1].name == "capsule"


# ---------------------------------------------------------------------------
# FETTLE_CONFIG + corrupt layers
# ---------------------------------------------------------------------------


def test_fettle_config_env_honored(tmp_path, monkeypatch):
    alt = tmp_path / "alt.toml"
    alt.write_text('[gates.lint]\nmode = "enforce"\n')
    monkeypatch.setenv("FETTLE_CONFIG", str(alt))

    cfg, layers = resolve_with_provenance(str(_project(tmp_path)))
    repo = next(lyr for lyr in layers if lyr.name == "repo")
    assert repo.source == str(alt)
    assert cfg["gates"]["lint"]["mode"] == "enforce"


def test_corrupt_org_toml_skipped_fail_visible(tmp_path, capsys):
    packs = _packs_dir(tmp_path)
    (packs / "org.toml").write_text("this is not valid [[[ toml")
    (packs / "team.toml").write_text("[gates.docs]\nenabled = true\n")

    cfg, layers = resolve_with_provenance(str(_project(tmp_path)))
    assert not any(lyr.name.startswith("org:") for lyr in layers)
    assert cfg["gates"]["docs"]["enabled"] is True  # other layers unaffected
    assert "could not parse" in capsys.readouterr().err


def test_corrupt_repo_toml_skipped_fail_visible(tmp_path, capsys):
    project = _project(tmp_path)
    (project / ".fettle.toml").write_text("invalid {{{ toml content")

    _, layers = resolve_with_provenance(str(project))
    assert [lyr.name for lyr in layers] == ["defaults"]
    assert "could not parse" in capsys.readouterr().err


def test_missing_config_home_no_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nonexistent"))
    _, layers = resolve_with_provenance(str(_project(tmp_path)))
    assert [lyr.name for lyr in layers] == ["defaults"]


# ---------------------------------------------------------------------------
# Parity: inspection == runtime (H-05)
# ---------------------------------------------------------------------------


def test_inspection_equals_runtime(tmp_path, monkeypatch):
    packs = _packs_dir(tmp_path)
    (packs / "org.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    (packs / "team.toml").write_text("[gates.docs]\nenabled = true\n")
    project = _project(tmp_path)
    (project / ".fettle.toml").write_text("[gates.plan]\nenabled = true\n")
    monkeypatch.setenv("FETTLE_GATE_MODE", "soft")

    assert resolve_with_provenance(str(project))[0] == load_config(str(project))


def test_load_config_layered_is_deprecated_alias(tmp_path):
    project = _project(tmp_path)
    (project / ".fettle.toml").write_text('[gates.lint]\nmode = "enforce"\n')
    assert load_config_layered(str(project)) == load_config(str(project))


# ---------------------------------------------------------------------------
# Provenance explanation (unit)
# ---------------------------------------------------------------------------


def test_explain_single_layer():
    layers = [PolicyLayer("defaults", "built-in", {"gates": {"lint": {"mode": "advisory"}}})]
    assert explain_config(layers, "gates.lint.mode") == [
        {"layer": "defaults", "value": "advisory"}
    ]


def test_explain_override_chain():
    layers = [
        PolicyLayer("defaults", "built-in", {"gates": {"lint": {"mode": "advisory"}}}),
        PolicyLayer("repo", "/project/.fettle.toml", {"gates": {"lint": {"mode": "enforce"}}}),
    ]
    result = explain_config(layers, "gates.lint.mode")
    assert result == [
        {"layer": "defaults", "value": "advisory"},
        {"layer": "repo", "value": "enforce"},
    ]


def test_explain_missing_key():
    layers = [PolicyLayer("defaults", "built-in", {"gates": {}})]
    assert explain_config(layers, "nonexistent.key.path") == []


def test_resolve_config_merges_in_list_order():
    layers = [
        PolicyLayer("a", "x", {"k": 1, "sub": {"a": 1}}),
        PolicyLayer("b", "y", {"k": 2, "sub": {"b": 2}}),
    ]
    assert resolve_config(layers) == {"k": 2, "sub": {"a": 1, "b": 2}}
