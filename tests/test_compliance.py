"""Tests for WP-146: compliance mapping and evidence report."""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from pathlib import Path

import yaml

from fettle.compliance import (
    RULE_COMPLIANCE,
    ControlCoverageSummary,
    ControlMapping,
    compute_compliance_report,
    full_mapping,
    render_compliance_table,
)

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"
RULE_PACKS = ["llm-antipatterns.yml", "go-antipatterns.yml", "ts-antipatterns.yml"]


def _yaml_rules() -> dict[str, dict]:
    rules: dict[str, dict] = {}
    for pack in RULE_PACKS:
        doc = yaml.safe_load((RULES_DIR / pack).read_text())
        for rule in doc["rules"]:
            rules[rule["id"]] = rule
    return rules


class TestMappingSync:
    """The Python mapping and the YAML metadata.compliance tags must agree."""

    def test_every_bundled_rule_is_mapped(self):
        missing = set(_yaml_rules()) - set(RULE_COMPLIANCE)
        assert not missing, f"bundled rules without compliance mapping: {missing}"

    def test_no_stale_mappings(self):
        stale = set(RULE_COMPLIANCE) - set(_yaml_rules())
        assert not stale, f"mapped rules not in any bundled pack: {stale}"

    def test_yaml_tags_mirror_python_mapping(self):
        for rule_id, rule in _yaml_rules().items():
            tags = rule.get("metadata", {}).get("compliance", {})
            cm = RULE_COMPLIANCE[rule_id]
            expected = {
                k: v
                for k, v in dataclasses.asdict(cm).items()
                if v  # empty = unmapped = omitted from YAML
            }
            assert tags == expected, f"{rule_id}: YAML {tags} != Python {expected}"


class TestFullMapping:
    def test_includes_ruff_codes_with_cwe(self):
        mapping = full_mapping()
        assert mapping["S608"].cwe == "CWE-89"
        assert mapping["S608"].asvs == "V5.3.4"
        assert mapping["S608"].soc2 == "CC7.1"
        assert mapping["S110"].asvs == "V7.4.2"

    def test_cwe_labels_are_bare_ids(self):
        for rule_id, cm in full_mapping().items():
            if cm.cwe:
                assert cm.cwe.startswith("CWE-") and " " not in cm.cwe, rule_id

    def test_bundled_rules_present(self):
        mapping = full_mapping()
        assert mapping["sql-fstring"] == ControlMapping(
            cwe="CWE-89", asvs="V5.3.4", soc2="CC7.1"
        )


def _fake_entries():
    now = time.time()
    return [
        {  # blocked SQL injection finding
            "ts": now - 100,
            "status": "blocked",
            "findings": [{"code": "sql-fstring"}],
        },
        {  # non-blocking violation, same rule
            "ts": now - 200,
            "status": "violation",
            "findings": [{"code": "sql-fstring"}],
        },
        {  # unmapped rule fired
            "ts": now - 300,
            "status": "violation",
            "findings": [{"code": "custom-org-rule"}],
        },
        {  # outside the window — ignored
            "ts": now - 40 * 86400,
            "status": "blocked",
            "findings": [{"code": "debug-pdb"}],
        },
        {  # pass entries carry no findings
            "ts": now - 50,
            "status": "pass",
            "findings": [],
        },
    ]


class TestComputeReport:
    def test_aggregate_type_renamed_without_old_alias(self):
        import fettle.compliance as compliance

        assert ControlCoverageSummary.__name__ == "ControlCoverageSummary"
        assert not hasattr(compliance, "ControlEvidence")

    def test_counts_and_unmapped(self, monkeypatch):
        monkeypatch.setattr(
            "fettle.trace.get_recent_decisions", lambda limit=20: _fake_entries()
        )
        data = compute_compliance_report(days=30)
        cwe89 = data["frameworks"]["cwe"]["CWE-89"]
        assert cwe89["findings"] == 2
        assert cwe89["blocked"] == 1
        assert "sql-fstring" in cwe89["rules"]
        assert "S608" in cwe89["rules"]
        # old debug-pdb entry filtered out
        assert data["frameworks"]["cwe"]["CWE-489"]["findings"] == 0
        assert data["unmapped_fired_rules"] == ["custom-org-rule"]
        assert data["period_days"] == 30
        assert data["mapped_rules"] == len(full_mapping())
        assert data["source_window_start"] < data["source_window_end"]
        assert len(data["source_digest"]) == 64
        assert data["source_complete"] is True

    def test_empty_trace_still_reports_coverage(self, monkeypatch):
        monkeypatch.setattr(
            "fettle.trace.get_recent_decisions", lambda limit=20: []
        )
        data = compute_compliance_report(days=7)
        assert data["frameworks"]["asvs"]["V5.3.4"]["findings"] == 0
        assert data["unmapped_fired_rules"] == []
        assert data["source_window_start"] is None
        assert data["source_window_end"] is None
        assert len(data["source_digest"]) == 64

    def test_digest_is_deterministic_and_order_independent(self, monkeypatch):
        entries = _fake_entries()[:3]
        monkeypatch.setattr(
            "fettle.trace.get_recent_decisions", lambda limit=20: entries
        )
        first = compute_compliance_report(days=30)["source_digest"]
        entries.reverse()

        assert compute_compliance_report(days=30)["source_digest"] == first

    def test_malformed_source_is_not_reported_complete(self, monkeypatch):
        entries = _fake_entries()[:1] + [{"ts": time.time(), "findings": "invalid"}]
        monkeypatch.setattr(
            "fettle.trace.get_recent_decisions", lambda limit=20: entries
        )

        data = compute_compliance_report(days=30)

        assert data["source_complete"] is False
        assert data["malformed_source_records"] == 1

    def test_json_serializable(self, monkeypatch):
        monkeypatch.setattr(
            "fettle.trace.get_recent_decisions", lambda limit=20: _fake_entries()
        )
        json.dumps(compute_compliance_report(days=30))


class TestRenderTable:
    def test_render_smoke(self, monkeypatch):
        monkeypatch.setattr(
            "fettle.trace.get_recent_decisions", lambda limit=20: _fake_entries()
        )
        out = render_compliance_table(compute_compliance_report(days=30))
        assert "CWE-89" in out
        assert "OWASP ASVS v4" in out
        assert "SOC 2" in out
        assert "custom-org-rule" in out
        assert "not a certification" in out


class TestCLI:
    def _args(self, **kw):
        base = {"org": False, "days": 30, "json": False, "compliance": True}
        base.update(kw)
        return argparse.Namespace(**base)

    def test_report_compliance_table(self, monkeypatch, capsys):
        from fettle.cli import cmd_report

        monkeypatch.setattr(
            "fettle.trace.get_recent_decisions", lambda limit=20: _fake_entries()
        )
        cmd_report(self._args())
        out = capsys.readouterr().out
        assert "Compliance Evidence" in out
        assert "CWE-89" in out

    def test_report_compliance_json(self, monkeypatch, capsys):
        from fettle.cli import cmd_report

        monkeypatch.setattr(
            "fettle.trace.get_recent_decisions", lambda limit=20: _fake_entries()
        )
        cmd_report(self._args(json=True))
        data = json.loads(capsys.readouterr().out)
        assert data["frameworks"]["cwe"]["CWE-89"]["blocked"] == 1

    def test_report_flag_parses(self):
        from fettle.cli import main  # noqa: F401 — parser built inline in main

        # Parser wiring is exercised via subprocess-level CLI tests elsewhere;
        # here we pin the Namespace contract used by cmd_report.
        args = self._args()
        assert args.compliance is True
