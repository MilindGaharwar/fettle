"""Tests for fettle.spec_model — living spec parser and lint (Stage 3)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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

    def test_outside_repository_exits_two(self, tmp_path):
        result = self._run(tmp_path, "lint")
        assert result.returncode == 2
        assert result.stdout == ""
        assert result.stderr == "Error: not inside a repository (no .git or .fettle.toml found)\n"

    def test_list_continues_after_missing_spec(self, repo, monkeypatch, capsys):
        from argparse import Namespace
        from fettle.cli import cmd_spec

        spec, findings = parse_spec(VALID_SPEC, "docs/checkout.md")
        monkeypatch.setattr("fettle.paths.find_repo_root", lambda: repo)
        monkeypatch.setattr("fettle.spec_model.discover_specs", lambda root: [(None, []), (spec, findings)])
        with pytest.raises(SystemExit) as exit_info:
            cmd_spec(Namespace(spec_action="list", json=True))
        assert exit_info.value.code == 0
        assert json.loads(capsys.readouterr().out) == [{
            "id": "checkout-flow", "path": "docs/checkout.md", "status": "active",
            "requirements": 2, "scenarios": 2, "lint_errors": 0,
        }]

    def test_warning_is_not_lint_error(self, repo):
        (repo / "docs" / "checkout.md").write_text(VALID_SPEC.replace("(traces R1)", ""))
        result = self._run(repo, "lint", "--json")
        assert result.returncode == 0
        report = json.loads(result.stdout)
        assert report["error_count"] == 0
        assert len(report["findings"]) == 1
        assert report["findings"][0]["severity"] == "WARNING"
        listed = self._run(repo, "list", "--json")
        assert listed.returncode == 0
        assert json.loads(listed.stdout)[0]["lint_errors"] == 0

    def test_lint_clean_exit_zero(self, repo):
        result = self._run(repo, "lint")
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout == "\u2713 All specs valid.\n"
        assert result.stderr == ""

    def test_lint_error_exit_one(self, repo):
        (repo / "docs" / "checkout.md").write_text(
            VALID_SPEC.replace("(traces R1)", "(traces R9)"))
        result = self._run(repo, "lint")
        assert result.returncode == 1
        assert result.stdout == (
            "  [ERROR] docs/checkout.md:18 \u2014 Scenario S1 traces R9, which does not exist.\n"
            "      fix: Add 'R9.' under ## Requirements or fix the traces list.\n"
            "  [WARNING] docs/checkout.md:1 \u2014 Requirement R1 has no scenario tracing it.\n"
            "      fix: Add a scenario with '(traces R1)' or remove R1.\n"
            "\n2 finding(s).\n"
        )
        assert result.stderr == ""

    def test_lint_json(self, repo):
        result = self._run(repo, "lint", "--json")
        assert result.returncode == 0
        assert result.stdout == json.dumps({"findings": [], "error_count": 0}, indent=2) + "\n"
        assert result.stderr == ""

    def test_list_shows_spec(self, repo):
        result = self._run(repo, "list", "--json")
        assert result.returncode == 0
        assert result.stdout == json.dumps([{
            "id": "checkout-flow", "path": "docs/checkout.md", "status": "active",
            "requirements": 2, "scenarios": 2, "lint_errors": 0,
        }], indent=2) + "\n"
        assert result.stderr == ""

    @pytest.mark.parametrize("invalid", [False, True])
    def test_list_human_reports_lint_errors(self, repo, invalid):
        if invalid:
            (repo / "docs" / "checkout.md").write_text(VALID_SPEC.replace("(traces R1)", "(traces R9)"))
        result = self._run(repo, "list")
        assert result.returncode == 0
        assert result.stdout == (
            f"  {'checkout-flow':<24} {'active':<11} 2R/2S  docs/checkout.md"
            + ("  (1 lint error(s))" if invalid else "") + "\n"
        )
        assert result.stderr == ""

    @pytest.mark.parametrize("json_output", [False, True])
    def test_list_ignores_non_specs(self, repo, json_output):
        (repo / "docs" / "checkout.md").write_text("---\nfettle-spec: v1\n# unterminated frontmatter\n")
        result = self._run(repo, "list", *(["--json"] if json_output else []))
        assert result.returncode == 0
        assert result.stdout == ("[]\n" if json_output else
                                 "No specs found (markdown files with 'fettle-spec' frontmatter).\n")
        assert result.stderr == ""

    def test_default_action_is_lint(self, repo):
        result = self._run(repo)
        assert result.returncode == 0
        assert result.stdout == "\u2713 All specs valid.\n"
        assert result.stderr == ""


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
    def test_empty_repository_returns_complete_empty_report(self, tmp_path, monkeypatch):
        def unexpected_scan(root):
            pytest.fail("test files must not be scanned without specifications")

        monkeypatch.setattr("fettle.spec_model._iter_test_files", unexpected_scan)
        assert scenario_coverage(str(tmp_path)) == {
            "specs": [],
            "unknown_traces": [],
            "totals": {"scenarios": 0, "covered": 0, "coverage_percent": 100.0},
        }

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
        assert spec["path"] == "docs/checkout.md"
        assert spec["covered"] == 1
        assert spec["total"] == 2
        assert report["totals"] == {
            "scenarios": 2, "covered": 1, "coverage_percent": 50.0}

    def test_spec_without_id_does_not_create_coverage_rows(self, repo):
        (repo / "docs" / "missing-id.md").write_text(
            VALID_SPEC.replace("id: checkout-flow\n", ""))
        report = scenario_coverage(str(repo))
        assert [spec["id"] for spec in report["specs"]] == ["checkout-flow"]
        assert report["totals"]["scenarios"] == 2

    def test_dependency_test_markers_do_not_count_as_evidence(self, repo):
        dependency = repo / "node_modules" / "package" / "test_cart.py"
        dependency.parent.mkdir(parents=True)
        dependency.write_text("# traces: checkout-flow/S1\n")
        report = scenario_coverage(str(repo))
        assert report["totals"]["covered"] == 0
        assert report["specs"][0]["scenarios"][0]["covered_by"] == []

    def test_unreadable_test_does_not_hide_later_evidence(self, repo, monkeypatch):
        unreadable = repo / "tests" / "test_a.py"
        unreadable.write_text("# traces: checkout-flow/S1\n")
        (repo / "tests" / "test_z.py").write_text("# traces: checkout-flow/S2\n")
        read_text = Path.read_text

        def read_unless_unavailable(path, *args, **kwargs):
            if path == unreadable:
                raise OSError("unavailable")
            return read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_unless_unavailable)
        report = scenario_coverage(str(repo))
        assert report["totals"]["covered"] == 1
        assert report["specs"][0]["scenarios"][1]["covered_by"] == ["tests/test_z.py"]

    def test_invalid_utf8_does_not_hide_trace_markers(self, repo):
        (repo / "tests" / "test_cart.py").write_bytes(
            b"\xff\n# traces: checkout-flow/S1\n")
        report = scenario_coverage(str(repo))
        assert report["specs"][0]["scenarios"][0]["covered_by"] == ["tests/test_cart.py"]

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
        assert report["unknown_traces"] == [{
            "test": "tests/test_cart.py", "marker": "checkout-flow/S9",
            "reason": "spec 'checkout-flow' has no scenario S9",
        }]

    def test_unknown_spec_marker_surfaced(self, repo):
        (repo / "tests" / "test_cart.py").write_text(
            "# traces: no-such-spec/S1, checkout-flow/S2\n")
        report = scenario_coverage(str(repo))
        assert report["unknown_traces"] == [{
            "test": "tests/test_cart.py", "marker": "no-such-spec/S1",
            "reason": "no spec with id 'no-such-spec'",
        }]
        assert report["specs"][0]["scenarios"][1]["covered_by"] == ["tests/test_cart.py"]

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

    def test_empty_specification_has_complete_zero_totals(self, repo):
        (repo / "docs" / "checkout.md").write_text(
            "---\nfettle-spec: v1\nid: checkout-flow\n---\n# Empty\n")
        report = scenario_coverage(str(repo))
        assert report["specs"][0]["scenarios"] == []
        assert report["totals"] == {
            "scenarios": 0, "covered": 0, "coverage_percent": 100.0}

    def test_fractional_coverage_rounded_to_one_decimal(self, repo):
        (repo / "docs" / "checkout.md").write_text(
            VALID_SPEC + "\n### S3. retry payment (traces R2)\n- Then payment succeeds\n")
        (repo / "tests" / "test_cart.py").write_text("# traces: checkout-flow/S1\n")
        report = scenario_coverage(str(repo))
        assert report["totals"] == {
            "scenarios": 3, "covered": 1, "coverage_percent": 33.3}

    def test_cli_coverage_json(self, repo):
        (repo / "tests" / "test_cart.py").write_text(
            "# traces: checkout-flow/S1, checkout-flow/S2\n")
        result = subprocess.run(
            [sys.executable, "-m", "fettle.cli", "spec", "coverage", "--json"],
            capture_output=True, text=True, cwd=str(repo),
        )
        assert result.returncode == 0
        assert result.stdout == json.dumps(scenario_coverage(str(repo)), indent=2) + "\n"
        assert result.stderr == ""

    def test_cli_coverage_human(self, repo):
        (repo / "tests" / "test_cart.py").write_text("# traces: checkout-flow/S1, missing/S1\n")
        (repo / "tests" / "test_checkout.py").write_text("# traces: checkout-flow/S1\n")
        result = subprocess.run(
            [sys.executable, "-m", "fettle.cli", "spec", "coverage"],
            capture_output=True, text=True, cwd=str(repo),
        )
        assert result.returncode == 0
        assert result.stdout == (
            "  checkout-flow (active): 1/2 scenarios covered\n"
            "    \u2713 S1. quantity change updates total \u2190 tests/test_cart.py, tests/test_checkout.py\n"
            "    \u2717 S2. payment declined\n"
            "  [WARNING] tests/test_cart.py: marker 'missing/S1' \u2014 no spec with id 'missing'\n"
            "\n1/2 scenarios covered (50.0%).\n"
        )
        assert result.stderr == ""
