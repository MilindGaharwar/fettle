"""Tests for scripts/baseline.py"""

import json
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from baseline import create_baseline, load_baseline, filter_new_violations, _fingerprint


def test_create_baseline(tmp_path):
    findings = [
        {"tool": "ruff", "file": "app.py", "line": 10, "code": "F401", "message": "unused"},
        {"tool": "semgrep", "file": "db.py", "line": 5, "code": "sql-fstring", "message": "injection"},
    ]
    baseline = create_baseline(findings, tmp_path)
    assert baseline["findings_count"] == 2
    assert (tmp_path / ".fettle-baseline.json").exists()


def test_load_baseline(tmp_path):
    data = {"version": 1, "findings_count": 1, "fingerprints": ["ruff:a.py:1:F401"], "findings": []}
    (tmp_path / ".fettle-baseline.json").write_text(json.dumps(data))
    loaded = load_baseline(tmp_path)
    assert loaded["findings_count"] == 1


def test_load_baseline_missing(tmp_path):
    assert load_baseline(tmp_path) is None


def test_filter_new_violations():
    baseline = {
        "fingerprints": ["ruff:app.py:10:F401"],
        "findings": [{"tool": "ruff", "file": "app.py", "line": 10, "code": "F401"}],
    }
    findings = [
        {"tool": "ruff", "file": "app.py", "line": 10, "code": "F401", "message": "old"},
        {"tool": "ruff", "file": "new.py", "line": 5, "code": "F401", "message": "new"},
    ]
    new = filter_new_violations(findings, baseline)
    assert len(new) == 1
    assert new[0]["file"] == "new.py"


def test_filter_no_baseline():
    findings = [{"tool": "ruff", "file": "a.py", "line": 1, "code": "X"}]
    new = filter_new_violations(findings, None)
    assert len(new) == 1


def test_fingerprint_stable():
    f = {"tool": "ruff", "file": "x.py", "line": 10, "code": "F401"}
    assert _fingerprint(f) == "ruff:x.py:10:F401"
    assert _fingerprint(f) == _fingerprint(f)
