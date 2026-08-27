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
    OPEN_DICT_PATHS,
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

    def test_named_assurance_release_policies_are_valid_config(self) -> None:
        errors, warnings = validate_config({
            "assurance": {"release": {"production": {"security": "PASS"}}},
        })

        assert errors == [] and warnings == []
        assert "assurance.release" in OPEN_DICT_PATHS

    def test_unknown_mode_value_errors(self) -> None:
        # WP4: lint has a declared mode enum, so a bogus mode is an error now
        errors, _ = validate_config({"gates": {"lint": {"mode": "yolo"}}})
        assert any("gates.lint.mode" in e for e in errors)

    def test_mutation_defaults_are_disabled_and_advisory(self) -> None:
        mutation = DEFAULTS["mutation"]

        assert mutation["enabled"] is False
        assert mutation["mode"] == "advisory"
        assert mutation["max_mutant_timeouts"] is None
        assert mutation["max_suspicious_mutants"] is None
        assert mutation["full_shards"] == 1

    @pytest.mark.parametrize("path", [
        ("gates", "coverage"),
        ("integrations", "sonarqube"),
        ("integrations", "blackduck"),
        ("integrations", "pact"),
        ("uat",),
    ])
    def test_canonical_evidence_rollback_switches_are_validated(self, path) -> None:
        config = node = {}
        for part in path:
            node[part] = {}
            node = node[part]
        node["canonical_evidence"] = False

        errors, warnings = validate_config(config)

        assert errors == [] and warnings == []

    def test_mutation_mapping_tables_allow_project_paths(self) -> None:
        config = {"mutation": {
            "test_mappings": {"src/shared.py": ["tests/test_shared.py"]},
            "chunk_lines": {"src/slow.py": 20},
        }}

        errors, warnings = validate_config(config)

        assert errors == [] and warnings == []
        assert "mutation.test_mappings" in OPEN_DICT_PATHS
        assert "mutation.chunk_lines" in OPEN_DICT_PATHS

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("mode", "silent"),
            ("score_target", 101),
            ("timeout_s", 0),
            ("full_timeout_s", 0),
            ("minimum_scored_mutants", -1),
            ("max_new_actionable_survivors", -1),
            ("max_untested", -1),
            ("max_mutant_timeouts", -1),
            ("max_suspicious_mutants", -1),
            ("max_findings_per_line", 0),
            ("max_findings_per_file", 0),
            ("default_chunk_lines", 0),
            ("full_shards", 0),
        ],
    )
    def test_invalid_mutation_setting_errors(self, field, value) -> None:
        errors, _ = validate_config({"mutation": {field: value}})

        assert any(f"mutation.{field}" in error for error in errors)

    def test_unsupported_mutation_engine_errors(self) -> None:
        errors, _ = validate_config({"mutation": {"engine": "other"}})

        assert any("mutation.engine" in error for error in errors)
        engine = generate_json_schema()["properties"]["mutation"]["properties"]["engine"]
        assert engine["enum"] == ["mutmut"]

    def test_optional_mutation_budgets_reject_non_integer_values(self) -> None:
        errors, _ = validate_config({"mutation": {"max_mutant_timeouts": "none"}})

        assert any("mutation.max_mutant_timeouts" in error for error in errors)

    def test_mutation_enforcement_requires_enabled_and_explicit_budgets(self) -> None:
        disabled, _ = validate_config({"mutation": {"mode": "enforce"}})
        missing_budget, _ = validate_config({"mutation": {
            "enabled": True,
            "mode": "enforce",
            "max_mutant_timeouts": 0,
        }})
        valid, warnings = validate_config({"mutation": {
            "enabled": True,
            "mode": "enforce",
            "max_mutant_timeouts": 0,
            "max_suspicious_mutants": 0,
        }})

        assert any("enabled" in error for error in disabled)
        assert any("max_suspicious_mutants" in error for error in missing_budget)
        assert valid == [] and warnings == []


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
        # Every `mode` key in DEFAULTS must have an enum; every enum path
        # must exist in DEFAULTS (non-mode vocab paths like worklog.scope
        # are allowed as long as they resolve).
        mode_paths = set(_mode_paths(DEFAULTS))
        assert mode_paths <= set(MODE_ENUMS)
        for path in set(MODE_ENUMS) - mode_paths:
            _get(DEFAULTS, path)  # raises KeyError on orphaned enum path

    def test_every_default_mode_is_in_its_enum(self) -> None:
        for path, allowed in MODE_ENUMS.items():
            assert _get(DEFAULTS, path) in allowed, path

    def test_mode_outside_gate_enum_errors(self) -> None:
        # lean_review honors silent/advisory; "enforce" would silently act as advisory
        errors, _ = validate_config({"gates": {"lean_review": {"mode": "enforce"}}})
        assert len(errors) == 1
        assert "gates.lean_review.mode" in errors[0]
        assert "advisory" in errors[0]

    def test_mode_inside_gate_enum_ok(self) -> None:
        # tdd blocks on "enforce" (canonical) and "strict" (legacy alias)
        for mode in ("enforce", "strict"):
            errors, warnings = validate_config({"gates": {"tdd": {"mode": mode}}})
            assert errors == [] and warnings == [], mode

    def test_provenance_modes(self) -> None:
        errors, _ = validate_config({"gates": {"provenance": {"mode": "manifest"}}})
        assert errors == []
        errors, _ = validate_config({"gates": {"provenance": {"mode": "enforce"}}})
        assert errors and "gates.provenance.mode" in errors[0]

    # ── numeric ranges ───────────────────────────────────────────
    def test_ranges_paths_exist_and_defaults_in_range(self) -> None:
        for path, (lo, hi) in RANGES.items():
            default = _get(DEFAULTS, path)
            if default is None:
                continue
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

    def test_docs_soft_mode_warns_deprecated(self) -> None:
        errors, warnings = validate_config({"gates": {"docs": {"mode": "soft"}}})
        assert errors == []  # still a valid mode — one-release tolerance
        assert any("deprecated" in w and "soft" in w for w in warnings)

    def test_complexity_enforce_bool_warns_deprecated(self) -> None:
        errors, warnings = validate_config(
            {"gates": {"complexity": {"enforce": True}}})
        assert errors == []
        assert any("deprecated" in w and "complexity" in w for w in warnings)

    def test_complexity_mode_enforce_is_valid(self) -> None:
        errors, warnings = validate_config(
            {"gates": {"complexity": {"mode": "enforce"}}})
        assert errors == []
        assert warnings == []


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
        assert tdd_mode["enum"] == ["advisory", "enforce", "strict"]

    def test_range_bounds_in_schema(self) -> None:
        schema = generate_json_schema()
        threshold = (schema["properties"]["gates"]["properties"]["coverage"]
                     ["properties"]["threshold"])
        assert threshold["minimum"] == 0 and threshold["maximum"] == 100

    def test_mutation_optional_budgets_are_nullable_non_negative_in_schema(self) -> None:
        mutation = generate_json_schema()["properties"]["mutation"]["properties"]

        assert mutation["max_mutant_timeouts"]["type"] == ["integer", "null"]
        assert mutation["max_mutant_timeouts"]["minimum"] == 0
        assert mutation["max_suspicious_mutants"]["type"] == ["integer", "null"]

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
