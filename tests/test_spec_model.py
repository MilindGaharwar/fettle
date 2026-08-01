"""Tests for fettle.spec_model — living spec parser and lint (Stage 3)."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from fettle.spec_model import (
    discover_specs,
    extract_trace_markers,
    is_spec_text,
    lint_specs,
    parse_spec,
    scenario_coverage,
)

VALID_SPEC = """\
---
fettle-spec: v1
id: checkout-flow
status: active
scope:
  - src/checkout/**
---

# Checkout flow

Free prose here is fine.

## Requirements
- R1. Cart total recalculates on quantity change.
- R2. Payment failures show a retryable error state.

## Scenarios
### S1. quantity change updates total (traces R1)
- Given a cart with 2 items
- When the quantity of one item is set to 3
- Then the displayed total equals the recomputed sum

### S2. payment declined (traces R2)
- Given a valid cart at the payment step
- When the provider declines the card
- Then a retryable error is shown and the cart is preserved
"""


def _errors(findings):
    return [f for f in findings if f["severity"] == "ERROR"]


class TestDetection:
    def test_valid_spec_detected(self):
        assert is_spec_text(VALID_SPEC)

    def test_plain_markdown_not_detected(self):
        assert not is_spec_text("# Just a doc\n\nSome text.\n")

    def test_frontmatter_without_key_not_detected(self):
        assert not is_spec_text("---\ntitle: readme\n---\n# Doc\n")

    def test_unterminated_frontmatter_not_detected(self):
        assert not is_spec_text("---\nfettle-spec: v1\n# never closed\n")


class TestParsing:
    def test_valid_spec_parses_clean(self):
        spec, findings = parse_spec(VALID_SPEC, "docs/checkout.md")
        assert spec is not None
        assert _errors(findings) == []
        assert spec.spec_id == "checkout-flow"
        assert spec.status == "active"
        assert spec.scope == ["src/checkout/**"]
        assert set(spec.requirements) == {"R1", "R2"}
        assert [s.id for s in spec.scenarios] == ["S1", "S2"]
        assert spec.scenarios[0].traces == ["R1"]

    def test_non_spec_returns_none_with_error(self):
        spec, findings = parse_spec("# Not a spec\n", "docs/x.md")
        assert spec is None
        assert _errors(findings)

    def test_bad_id_errors(self):
        text = VALID_SPEC.replace("id: checkout-flow", "id: Checkout Flow!")
        _, findings = parse_spec(text)
        assert any("kebab-case" in f["message"] for f in _errors(findings))

    def test_bad_status_errors(self):
        text = VALID_SPEC.replace("status: active", "status: live")
        _, findings = parse_spec(text)
        assert any("'live'" in f["message"] for f in _errors(findings))

    def test_missing_status_defaults_to_draft(self):
        text = VALID_SPEC.replace("status: active\n", "")
        spec, findings = parse_spec(text)
        assert spec.status == "draft"
        assert _errors(findings) == []

    def test_findings_carry_fix_field(self):
        _, findings = parse_spec(VALID_SPEC.replace("status: active", "status: bogus"))
        assert all("fix" in f and f["fix"] for f in findings)


class TestLintRules:
    def test_scenario_missing_then_errors(self):
        text = VALID_SPEC.replace(
            "- Then the displayed total equals the recomputed sum\n", "")
        _, findings = parse_spec(text)
        assert any("no 'Then' step" in f["message"] and "S1" in f["message"]
                   for f in _errors(findings))

    def test_trace_to_missing_requirement_errors(self):
        text = VALID_SPEC.replace("(traces R1)", "(traces R9)")
        _, findings = parse_spec(text)
        assert any("R9" in f["message"] and "does not exist" in f["message"]
                   for f in _errors(findings))

    def test_untraced_requirement_warns(self):
        text = VALID_SPEC.replace("(traces R2)", "(traces R1)")
        _, findings = parse_spec(text)
        warnings = [f for f in findings if f["severity"] == "WARNING"]
        assert any("R2" in f["message"] for f in warnings)
        assert _errors(findings) == []

    def test_duplicate_requirement_id_errors(self):
        text = VALID_SPEC.replace(
            "- R2. Payment failures show a retryable error state.",
            "- R1. A duplicate.")
        _, findings = parse_spec(text)
        assert any("Duplicate requirement" in f["message"] for f in _errors(findings))

    def test_duplicate_scenario_id_errors(self):
        text = VALID_SPEC.replace("### S2.", "### S1.")
        _, findings = parse_spec(text)
        assert any("Duplicate scenario" in f["message"] for f in _errors(findings))

    def test_empty_spec_warns_inert(self):
        text = "---\nfettle-spec: v1\nid: empty-spec\n---\n# Empty\n"
        spec, findings = parse_spec(text)
        assert spec is not None
        assert any("inert" in f["message"] for f in findings)
        assert _errors(findings) == []


class TestRepoLevel:
    @pytest.fixture
    def repo(self, tmp_path):
        (tmp_path / "docs").mkdir()
        (tmp_path / "src" / "checkout").mkdir(parents=True)
        (tmp_path / "src" / "checkout" / "cart.py").write_text("x = 1\n")
        (tmp_path / "docs" / "checkout.md").write_text(VALID_SPEC)
        (tmp_path / "docs" / "readme.md").write_text("# Not a spec\n")
        return tmp_path

    def test_discover_finds_only_specs(self, repo):
        results = discover_specs(str(repo))
        assert len(results) == 1
        assert results[0][0].spec_id == "checkout-flow"

    def test_lint_clean_repo(self, repo):
        assert _errors(lint_specs(str(repo))) == []

    def test_duplicate_spec_id_across_files_errors(self, repo):
        (repo / "docs" / "copy.md").write_text(VALID_SPEC)
        findings = lint_specs(str(repo))
        assert any("already used by" in f["message"] for f in _errors(findings))

    def test_dead_scope_glob_warns(self, repo):
        text = VALID_SPEC.replace("src/checkout/**", "src/nonexistent/**")
        (repo / "docs" / "checkout.md").write_text(text)
        findings = lint_specs(str(repo))
        assert any("matches nothing" in f["message"] for f in findings
                   if f["severity"] == "WARNING")

    def test_skip_dirs_excluded(self, repo):
        hidden = repo / "node_modules" / "pkg"
        hidden.mkdir(parents=True)
        (hidden / "spec.md").write_text(VALID_SPEC)
        assert len(discover_specs(str(repo))) == 1


class TestCLI:
    @pytest.fixture
    def repo(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "docs").mkdir()
        (tmp_path / "src" / "checkout").mkdir(parents=True)
        (tmp_path / "src" / "checkout" / "cart.py").write_text("x = 1\n")
        (tmp_path / "docs" / "checkout.md").write_text(VALID_SPEC)
        return tmp_path

    def _run(self, repo, *argv):
        return subprocess.run(
            [sys.executable, "-m", "fettle.cli", "spec", *argv],
            capture_output=True, text=True, cwd=str(repo),
        )

    def test_lint_clean_exit_zero(self, repo):
        result = self._run(repo, "lint")
        assert result.returncode == 0, result.stdout + result.stderr

    def test_lint_error_exit_one(self, repo):
        (repo / "docs" / "checkout.md").write_text(
            VALID_SPEC.replace("(traces R1)", "(traces R9)"))
        result = self._run(repo, "lint")
        assert result.returncode == 1
        assert "fix:" in result.stdout

    def test_lint_json(self, repo):
        result = self._run(repo, "lint", "--json")
        data = json.loads(result.stdout)
        assert data["error_count"] == 0

    def test_list_shows_spec(self, repo):
        result = self._run(repo, "list", "--json")
        rows = json.loads(result.stdout)
        assert rows[0]["id"] == "checkout-flow"
        assert rows[0]["requirements"] == 2
        assert rows[0]["scenarios"] == 2

    def test_default_action_is_lint(self, repo):
        result = self._run(repo)
        assert result.returncode == 0
        assert "valid" in result.stdout


class TestTraceMarkers:
    def test_python_marker(self):
        assert extract_trace_markers("# traces: checkout-flow/S1\n") == ["checkout-flow/S1"]

    def test_js_marker(self):
        assert extract_trace_markers("// traces: checkout-flow/S2\n") == ["checkout-flow/S2"]

    def test_comma_separated(self):
        assert extract_trace_markers("# traces: a-b/S1, a-b/S2\n") == ["a-b/S1", "a-b/S2"]

    def test_singular_form_and_multiple_lines(self):
        text = "# trace: x-y/S1\ncode()\n# traces: x-y/S2\n"
        assert extract_trace_markers(text) == ["x-y/S1", "x-y/S2"]

    def test_no_marker(self):
        assert extract_trace_markers("def test_x():\n    pass\n") == []


class TestScenarioCoverage:
    @pytest.fixture
    def repo(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "docs").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "docs" / "checkout.md").write_text(VALID_SPEC)
        return tmp_path

    def test_covered_scenario_lists_evidence(self, repo):
        (repo / "tests" / "test_cart.py").write_text(
            "# traces: checkout-flow/S1\ndef test_total():\n    pass\n")
        report = scenario_coverage(str(repo))
        spec = report["specs"][0]
        s1 = next(r for r in spec["scenarios"] if r["id"] == "S1")
        assert s1["covered"] and s1["covered_by"] == ["tests/test_cart.py"]
        s2 = next(r for r in spec["scenarios"] if r["id"] == "S2")
        assert not s2["covered"] and s2["covered_by"] == []
        assert report["totals"] == {
            "scenarios": 2, "covered": 1, "coverage_percent": 50.0}

    def test_spec_level_marker_is_coarse_not_coverage(self, repo):
        (repo / "tests" / "test_cart.py").write_text(
            "# traces: checkout-flow\ndef test_total():\n    pass\n")
        report = scenario_coverage(str(repo))
        spec = report["specs"][0]
        assert spec["covered"] == 0
        assert spec["spec_level_traces"] == ["tests/test_cart.py"]

    def test_unknown_scenario_marker_surfaced(self, repo):
        (repo / "tests" / "test_cart.py").write_text("# traces: checkout-flow/S9\n")
        report = scenario_coverage(str(repo))
        assert report["unknown_traces"][0]["reason"] == "spec 'checkout-flow' has no scenario S9"

    def test_unknown_spec_marker_surfaced(self, repo):
        (repo / "tests" / "test_cart.py").write_text("# traces: no-such-spec/S1\n")
        report = scenario_coverage(str(repo))
        assert "no spec with id" in report["unknown_traces"][0]["reason"]

    def test_non_spec_shaped_marker_ignored(self, repo):
        (repo / "tests" / "test_cart.py").write_text("# traces: WP-154\n")
        report = scenario_coverage(str(repo))
        assert report["unknown_traces"] == []

    def test_js_test_file_scanned(self, repo):
        (repo / "tests" / "cart.test.ts").write_text("// traces: checkout-flow/S2\n")
        report = scenario_coverage(str(repo))
        s2 = next(r for r in report["specs"][0]["scenarios"] if r["id"] == "S2")
        assert s2["covered_by"] == ["tests/cart.test.ts"]

    def test_no_scenarios_is_100_percent(self, tmp_path):
        (tmp_path / ".git").mkdir()
        report = scenario_coverage(str(tmp_path))
        assert report["totals"]["coverage_percent"] == 100.0

    def test_cli_coverage_json(self, repo):
        (repo / "tests" / "test_cart.py").write_text(
            "# traces: checkout-flow/S1, checkout-flow/S2\n")
        result = subprocess.run(
            [sys.executable, "-m", "fettle.cli", "spec", "coverage", "--json"],
            capture_output=True, text=True, cwd=str(repo),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["totals"]["covered"] == 2

    def test_cli_coverage_human(self, repo):
        result = subprocess.run(
            [sys.executable, "-m", "fettle.cli", "spec", "coverage"],
            capture_output=True, text=True, cwd=str(repo),
        )
        assert result.returncode == 0
        assert "0/2 scenarios covered" in result.stdout
