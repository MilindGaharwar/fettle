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

from fettle.config_schema import generate_json_schema, validate_config  # noqa: E402


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

    def test_unknown_mode_value_warns(self) -> None:
        _, warnings = validate_config({"gates": {"lint": {"mode": "yolo"}}})
        assert any("gates.lint.mode" in w for w in warnings)


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
