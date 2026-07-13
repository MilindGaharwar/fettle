"""Tests for scripts/suppressions_v2.py — WP-77: Suppressions and baselines v2."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from suppressions_v2 import (
    apply_suppressions,
    parse_inline_suppression,
    is_suppressed,
    load_baseline,
    create_baseline,
)
from finding import CheckFinding, FindingSeverity


def _f(checker="ruff", code="F401", path="src/app.py", line=10, msg="unused import"):
    return CheckFinding(checker=checker, severity=FindingSeverity.ERROR, file=path, line=line, message=msg, code=code)


def test_baseline_suppresses_existing_findings(tmp_path):
    baseline_file = tmp_path / "baseline.json"
    findings = [_f(), _f(code="E501", line=20, msg="line too long")]
    create_baseline(findings, str(baseline_file))
    baseline = load_baseline(str(baseline_file))
    filtered = apply_suppressions(findings, baseline=baseline)
    assert filtered == []


def test_new_findings_still_reported_with_baseline(tmp_path):
    baseline_file = tmp_path / "baseline.json"
    old = [_f(code="F401", line=10)]
    create_baseline(old, str(baseline_file))
    baseline = load_baseline(str(baseline_file))
    new_findings = [_f(code="F401", line=10), _f(code="S608", line=30, msg="sql injection")]
    filtered = apply_suppressions(new_findings, baseline=baseline)
    assert len(filtered) == 1
    assert filtered[0].code == "S608"


def test_inline_suppression_works():
    line_content = "import os  # fettle:ignore[F401] legacy import"
    result = parse_inline_suppression(line_content)
    assert result is not None
    assert result["rule"] == "F401"
    assert "legacy" in result["reason"]


def test_suppression_requires_reason():
    line_content = "import os  # fettle:ignore[F401]"
    result = parse_inline_suppression(line_content)
    # No reason = still parsed but flagged
    assert result is not None
    assert result["reason"] == ""


def test_expired_suppression_re_enables_finding():
    suppression_rules = [
        {"checker": "ruff", "rule": "F401", "path": "src/", "expires": "2020-01-01", "reason": "old"},
    ]
    f = _f()
    assert not is_suppressed(f, suppression_rules)


def test_active_suppression_hides_finding():
    suppression_rules = [
        {"checker": "ruff", "rule": "F401", "path": "src/", "expires": "2099-01-01", "reason": "planned fix"},
    ]
    f = _f()
    assert is_suppressed(f, suppression_rules)


def test_baseline_create_captures_current_state(tmp_path):
    baseline_file = tmp_path / "baseline.json"
    findings = [_f(), _f(code="E501", line=20, msg="long")]
    create_baseline(findings, str(baseline_file))
    assert baseline_file.exists()
    baseline = load_baseline(str(baseline_file))
    assert len(baseline) == 2


def test_invalid_baseline_file_warned(tmp_path):
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text("not json")
    baseline = load_baseline(str(baseline_file))
    assert baseline == []
