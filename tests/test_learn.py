"""Tests for scripts/learn.py"""

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.learn import _generate_semgrep_yaml, _save_rule, list_learned_rules


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


# --- WP-8 (audit M-01): rule_id is untrusted LLM output ---

def _rule(rule_id):
    return {
        "rule_id": rule_id,
        "severity": "ERROR",
        "message": "m",
        "pattern": "eval($X)",
        "language": "python",
        "violating_code": "eval(x)",
        "clean_code": "json.loads(x)",
    }


def test_save_rule_traversal_id_rejected(tmp_path):
    result = _save_rule(_rule("../../evil"), tmp_path)
    assert result["rule_id"].startswith("learned-")  # fell back to timestamp id
    assert not (tmp_path.parent / "evil.yml").exists()
    saved = tmp_path / "rules" / "learned" / f"{result['rule_id']}.yml"
    assert saved.exists()
    assert result["rule_id"] in saved.read_text()  # YAML carries the real id


def test_save_rule_absolute_id_rejected(tmp_path):
    result = _save_rule(_rule("/tmp/evil"), tmp_path)
    assert result["rule_id"].startswith("learned-")


def test_save_rule_nested_id_rejected(tmp_path):
    result = _save_rule(_rule("sub/dir-rule"), tmp_path)
    assert result["rule_id"].startswith("learned-")


def test_save_rule_non_string_id_rejected(tmp_path):
    result = _save_rule(_rule(["not", "a", "string"]), tmp_path)
    assert result["rule_id"].startswith("learned-")


def test_save_rule_valid_kebab_id_kept(tmp_path):
    result = _save_rule(_rule("api-timeout-2"), tmp_path)
    assert result["rule_id"] == "api-timeout-2"


def test_list_learned_rules(tmp_path):
    rules_dir = tmp_path / "rules" / "learned"
    rules_dir.mkdir(parents=True)
    (rules_dir / "rule-one.yml").write_text("rules: []")
    (rules_dir / "rule-two.yml").write_text("rules: []")
    rules = list_learned_rules(tmp_path)
    assert len(rules) == 2
