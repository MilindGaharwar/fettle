"""Tests for scripts/learn.py"""

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from learn import _generate_semgrep_yaml, _save_rule, list_learned_rules


def test_generate_semgrep_yaml():
    rule = {
        "rule_id": "test-rule",
        "severity": "ERROR",
        "message": "Test violation",
        "pattern": "$X = eval(...)",
        "language": "python",
        "citation": "INC-2026-001",
        "fix_suggestion": "Don't use eval",
    }
    yaml = _generate_semgrep_yaml(rule)
    assert "test-rule" in yaml
    assert "ERROR" in yaml
    assert "eval" in yaml
    assert "INC-2026-001" in yaml


def test_save_rule(tmp_path):
    rule = {
        "rule_id": "unsafe-eval",
        "severity": "ERROR",
        "message": "Unsafe eval usage",
        "pattern": "eval($X)",
        "language": "python",
        "violating_code": "result = eval(user_input)",
        "clean_code": "result = json.loads(user_input)",
        "citation": "Security incident 2026-01",
        "fix_suggestion": "Use json.loads instead",
    }
    result = _save_rule(rule, tmp_path)
    assert result["rule_id"] == "unsafe-eval"
    assert (tmp_path / "rules" / "learned" / "unsafe-eval.yml").exists()
    assert (tmp_path / "tests" / "fixtures" / "learned" / "unsafe-eval_violation.py").exists()
    assert (tmp_path / "tests" / "fixtures" / "learned" / "unsafe-eval_clean.py").exists()


def test_list_learned_rules_empty(tmp_path):
    rules = list_learned_rules(tmp_path)
    assert rules == []


def test_list_learned_rules(tmp_path):
    rules_dir = tmp_path / "rules" / "learned"
    rules_dir.mkdir(parents=True)
    (rules_dir / "rule-one.yml").write_text("rules: []")
    (rules_dir / "rule-two.yml").write_text("rules: []")
    rules = list_learned_rules(tmp_path)
    assert len(rules) == 2
