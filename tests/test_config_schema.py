"""WP-142 — Config schema tests.

Covers validation semantics (unknown keys warn, type mismatches error,
open dicts and None defaults unconstrained) and the anti-drift contract:
docs/fettle.schema.json must match the generator output exactly.
"""

import json
import os
import subprocess
import sys

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PLUGIN_DIR)

from fettle.config_schema import (  # noqa: E402
    MODE_ENUMS,
    RANGES,
    generate_json_schema,
    validate_config,
)
from fettle.config import DEFAULTS  # noqa: E402


class TestValidate:
    def test_empty_config_is_valid(self) -> None:
        errors, warnings = validate_config({})
        assert errors == [] and warnings == []

    def test_valid_overrides(self) -> None:
        errors, warnings = validate_config({
            "gates": {"lint": {"enabled": False, "mode": "enforce"},
                      "plan": {"threshold": 5, "risk_paths": ["**/auth/**"]}},
            "severity": {"error_rules": ["S608"]},
        })
        assert errors == [] and warnings == []

    def test_unknown_top_level_key_warns(self) -> None:
        errors, warnings = validate_config({"gatez": {}})
        assert errors == []
        assert len(warnings) == 1 and "gatez" in warnings[0]

    def test_unknown_nested_key_warns_with_path(self) -> None:
        _, warnings = validate_config({"gates": {"lint": {"enabeld": True}}})
        assert any("gates.lint.enabeld" in w for w in warnings)

    def test_type_mismatch_errors(self) -> None:
        errors, _ = validate_config({"gates": {"lint": {"enabled": "yes"}}})
        assert len(errors) == 1
        assert "gates.lint.enabled" in errors[0] and "boolean" in errors[0]

    def test_bool_is_not_integer(self) -> None:
        errors, _ = validate_config({"gates": {"plan": {"threshold": True}}})
        assert errors and "gates.plan.threshold" in errors[0]

    def test_int_accepted_for_number(self) -> None:
        errors, _ = validate_config({"gates": {"plan": {"threshold": 4}}})
        assert errors == []

    def test_table_expected(self) -> None:
        errors, _ = validate_config({"gates": "advisory"})
        assert errors and "must be a table" in errors[0]

    def test_none_default_unconstrained(self) -> None:
        # plan.module_threshold defaults to None — any type allowed
        errors, _ = validate_config({"gates": {"plan": {"module_threshold": 10}}})
        assert errors == []

    def test_open_dict_allows_arbitrary_keys(self) -> None:
        errors, warnings = validate_config(
            {"gates": {"tdd": {"path_mappings": {"src/foo": "tests/foo"}}}}
        )
        assert errors == [] and warnings == []

    def test_unknown_mode_value_errors(self) -> None:
        # WP4: lint has a declared mode enum, so a bogus mode is an error now
        errors, _ = validate_config({"gates": {"lint": {"mode": "yolo"}}})
        assert any("gates.lint.mode" in e for e in errors)


def _mode_paths(node: dict, prefix: str = ""):
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            yield from _mode_paths(value, path)
        elif key == "mode":
            yield path


def _get(cfg: dict, path: str):
    node = cfg
    for part in path.split("."):
        node = node[part]
    return node


class TestDependencyModel:
    """WP4 (Stage 2) — no invalid config states."""

    # ── per-gate mode enums ────────────────────────────────────
    def test_mode_enums_cover_exactly_the_mode_paths_in_defaults(self) -> None:
        assert set(_mode_paths(DEFAULTS)) == set(MODE_ENUMS)

    def test_every_default_mode_is_in_its_enum(self) -> None:
        for path, allowed in MODE_ENUMS.items():
            assert _get(DEFAULTS, path) in allowed, path

    def test_mode_outside_gate_enum_errors(self) -> None:
        # tdd honors advisory/strict; "enforce" would silently act as advisory
        errors, _ = validate_config({"gates": {"tdd": {"mode": "enforce"}}})
        assert len(errors) == 1
        assert "gates.tdd.mode" in errors[0]
        assert "strict" in errors[0]

    def test_mode_inside_gate_enum_ok(self) -> None:
        errors, warnings = validate_config({"gates": {"tdd": {"mode": "strict"}}})
        assert errors == [] and warnings == []

    def test_provenance_modes(self) -> None:
        errors, _ = validate_config({"gates": {"provenance": {"mode": "manifest"}}})
        assert errors == []
        errors, _ = validate_config({"gates": {"provenance": {"mode": "enforce"}}})
        assert errors and "gates.provenance.mode" in errors[0]

    # ── numeric ranges ───────────────────────────────────────────
    def test_ranges_paths_exist_and_defaults_in_range(self) -> None:
        for path, (lo, hi) in RANGES.items():
            default = _get(DEFAULTS, path)
            assert isinstance(default, (int, float)), path
            if lo is not None:
                assert default >= lo, path
            if hi is not None:
                assert default <= hi, path

    def test_out_of_range_errors(self) -> None:
        errors, _ = validate_config({"gates": {"coverage": {"threshold": 150}}})
        assert len(errors) == 1 and "gates.coverage.threshold" in errors[0]

    def test_lower_bound_errors(self) -> None:
        errors, _ = validate_config({"gates": {"plan": {"threshold": 0}}})
        assert errors and "gates.plan.threshold" in errors[0]

    def test_in_range_ok(self) -> None:
        errors, _ = validate_config({"gates": {"coverage": {"threshold": 80}}})
        assert errors == []

    # ── cross-field dependencies ──────────────────────────────────
    def test_extends_url_without_pin_errors(self) -> None:
        errors, _ = validate_config({"extends": {"url": "https://example.com/p.toml"}})
        assert len(errors) == 1 and "sha256" in errors[0]

    def test_extends_url_with_pin_ok(self) -> None:
        errors, _ = validate_config({"extends": {
            "url": "https://example.com/p.toml", "sha256": "a" * 64}})
        assert errors == []

    def test_boundaries_enabled_without_rules_warns(self) -> None:
        errors, warnings = validate_config(
            {"gates": {"architecture_boundaries": {"enabled": True}}})
        assert errors == []
        assert any("inert" in w for w in warnings)

    def test_boundaries_with_rules_clean(self) -> None:
        _, warnings = validate_config({"gates": {"architecture_boundaries": {
            "enabled": True, "rules": [{"from": "a", "deny": "b"}]}}})
        assert warnings == []

    def test_ui_colors_empty_palette_warns(self) -> None:
        _, warnings = validate_config({"gates": {"ui_colors": {"enabled": True}}})
        assert any("allowed_hex" in w for w in warnings)

    def test_tier2_enabled_with_default_backend_ok(self) -> None:
        # defaults fill model/ollama_url, so enabling tier2 alone is coherent
        _, warnings = validate_config(
            {"gates": {"lean_review": {"tier2": {"enabled": True}}}})
        assert warnings == []

    def test_tier2_enabled_with_blank_model_warns(self) -> None:
        _, warnings = validate_config({"gates": {"lean_review": {"tier2": {
            "enabled": True, "model": ""}}}})
        assert any("tier2" in w for w in warnings)

    def test_tdd_enabled_without_roots_warns(self) -> None:
        _, warnings = validate_config({"gates": {"tdd": {
            "enabled": True, "implementation_roots": []}}})
        assert any("implementation_roots" in w for w in warnings)


class TestSchemaGeneration:
    def test_schema_shape(self) -> None:
        schema = generate_json_schema()
        assert schema["type"] == "object"
        assert schema["x-fettle-schema-version"] == 1
        assert schema["properties"]["gates"]["additionalProperties"] is False
        lint = schema["properties"]["gates"]["properties"]["lint"]
        assert lint["properties"]["enabled"] == {"type": "boolean", "default": True}
        assert "enum" in lint["properties"]["mode"]

    def test_open_dict_in_schema(self) -> None:
        schema = generate_json_schema()
        mappings = (schema["properties"]["gates"]["properties"]["tdd"]
                    ["properties"]["path_mappings"])
        assert mappings["additionalProperties"] is True

    def test_per_gate_mode_enum_in_schema(self) -> None:
        schema = generate_json_schema()
        tdd_mode = (schema["properties"]["gates"]["properties"]["tdd"]
                    ["properties"]["mode"])
        assert tdd_mode["enum"] == ["advisory", "strict"]

    def test_range_bounds_in_schema(self) -> None:
        schema = generate_json_schema()
        threshold = (schema["properties"]["gates"]["properties"]["coverage"]
                     ["properties"]["threshold"])
        assert threshold["minimum"] == 0 and threshold["maximum"] == 100

    def test_published_schema_is_current(self) -> None:
        """docs/fettle.schema.json must match the generator (anti-drift gate).

        Regenerate with:
            python -c "import json; from fettle.config_schema import generate_json_schema; \\
                open('docs/fettle.schema.json','w').write(json.dumps(generate_json_schema(), indent=2)+'\\n')"
        """
        published_path = os.path.join(PLUGIN_DIR, "docs", "fettle.schema.json")
        with open(published_path) as fh:
            published = json.load(fh)
        assert published == generate_json_schema(), (
            "docs/fettle.schema.json is stale — DEFAULTS changed; regenerate it"
        )


class TestCLIValidate:
    def _run(self, cwd) -> tuple[int, str]:
        proc = subprocess.run(
            [sys.executable, os.path.join(PLUGIN_DIR, "fettle", "cli.py"),
             "config", "--validate"],
            capture_output=True, text=True, timeout=30, cwd=str(cwd),
        )
        return proc.returncode, proc.stdout + proc.stderr

    @pytest.fixture
    def repo(self, tmp_path):
        (tmp_path / ".git").mkdir()
        return tmp_path

    def test_valid_config(self, repo) -> None:
        (repo / ".fettle.toml").write_text("[gates.lint]\nenabled = true\n")
        rc, out = self._run(repo)
        assert rc == 0 and "valid" in out

    def test_typo_warns_but_passes(self, repo) -> None:
        (repo / ".fettle.toml").write_text("[gates.lint]\nenabeld = true\n")
        rc, out = self._run(repo)
        assert rc == 0 and "enabeld" in out and "WARN" in out

    def test_type_error_fails(self, repo) -> None:
        (repo / ".fettle.toml").write_text('[gates.lint]\nenabled = "yes"\n')
        rc, out = self._run(repo)
        assert rc == 1 and "ERROR" in out

    def test_unparseable_toml_fails(self, repo) -> None:
        (repo / ".fettle.toml").write_text("[gates\n")
        rc, out = self._run(repo)
        assert rc == 1 and "not parseable" in out

    def test_no_config_is_fine(self, repo) -> None:
        rc, out = self._run(repo)
        assert rc == 0 and "defaults apply" in out
