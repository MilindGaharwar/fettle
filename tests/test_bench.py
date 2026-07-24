"""WP-118 — Noise benchmark (`fettle bench`).

Runs rule packs over pinned corpora, computes findings-per-KLOC per rule,
and compares against committed budgets. A rule regressing past its budget
fails the bench — institutionalizing the measure-on-real-code step that
caught the 9,058-finding unawaited-promise flood before it shipped.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(PLUGIN_DIR / "scripts"))
from fettle.bench import BenchResult, load_budgets, run_bench  # noqa: E402

_ENV = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")}


def _has_semgrep() -> bool:
    try:
        r = subprocess.run(["semgrep", "--version"], capture_output=True, timeout=5, env=_ENV)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not _has_semgrep(), reason="semgrep not available")


def _make_corpus(tmp_path, n_clean_lines=1000, n_violations=2):
    """Synthetic Python corpus: known LOC, known violation count."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    clean_lines = "\n".join(f"x{i} = {i}" for i in range(n_clean_lines))
    (corpus / "clean.py").write_text(clean_lines + "\n")
    violations = "\n".join(
        f"def f{i}():\n    try:\n        pass\n    except:\n        pass"
        for i in range(n_violations)
    )
    (corpus / "dirty.py").write_text(violations + "\n")
    return corpus


def _write_budgets(tmp_path, budgets):
    path = tmp_path / "budgets.json"
    path.write_text(json.dumps(budgets))
    return path


# ── measurement ──────────────────────────────────────────────────────


def test_bench_measures_findings_and_kloc(tmp_path):
    corpus = _make_corpus(tmp_path, n_clean_lines=1000, n_violations=2)
    result = run_bench({"synthetic": str(corpus)}, budgets={})
    assert isinstance(result, BenchResult)
    m = result.measurements["synthetic"]
    assert m.kloc == pytest.approx(1.01, abs=0.02)
    assert m.findings_per_rule.get("bare-except-swallow") == 2


def test_bench_rate_computed_per_kloc(tmp_path):
    corpus = _make_corpus(tmp_path, n_clean_lines=1000, n_violations=2)
    result = run_bench({"synthetic": str(corpus)}, budgets={})
    rate = result.measurements["synthetic"].rate_per_kloc("bare-except-swallow")
    assert rate == pytest.approx(2 / 1.01, rel=0.05)


# ── budget enforcement ───────────────────────────────────────────────


def test_bench_passes_within_budget(tmp_path):
    corpus = _make_corpus(tmp_path, n_violations=2)
    budgets = {"synthetic": {"bare-except-swallow": 5.0}}
    result = run_bench({"synthetic": str(corpus)}, budgets=budgets)
    assert result.passed
    assert result.violations == []


def test_bench_fails_over_budget(tmp_path):
    corpus = _make_corpus(tmp_path, n_violations=10)
    budgets = {"synthetic": {"bare-except-swallow": 1.0}}
    result = run_bench({"synthetic": str(corpus)}, budgets=budgets)
    assert not result.passed
    assert any("bare-except-swallow" in v for v in result.violations)


def test_unbudgeted_rule_with_findings_is_reported_not_failed(tmp_path):
    # New rules start unbudgeted: visible in the report, not blocking.
    corpus = _make_corpus(tmp_path, n_violations=2)
    result = run_bench({"synthetic": str(corpus)}, budgets={"synthetic": {}})
    assert result.passed
    assert "bare-except-swallow" in result.unbudgeted["synthetic"]


# ── budget file I/O ──────────────────────────────────────────────────


def test_load_budgets_missing_file_returns_empty(tmp_path):
    assert load_budgets(tmp_path / "nope.json") == {}


def test_load_budgets_reads_json(tmp_path):
    path = _write_budgets(tmp_path, {"c": {"r": 1.5}})
    assert load_budgets(path) == {"c": {"r": 1.5}}


def test_update_budgets_writes_current_rates(tmp_path):
    corpus = _make_corpus(tmp_path, n_violations=2)
    out = tmp_path / "budgets.json"
    result = run_bench({"synthetic": str(corpus)}, budgets={}, update_budgets_path=out)
    written = json.loads(out.read_text())
    measured = result.measurements["synthetic"].rate_per_kloc("bare-except-swallow")
    assert written["synthetic"]["bare-except-swallow"] == pytest.approx(measured, rel=0.01)


def test_updated_budgets_pass_immediate_reverify(tmp_path):
    # Regression: budgets rounded DOWN failed their own re-verify at the
    # equality boundary. Budgets must round up.
    corpus = _make_corpus(tmp_path, n_clean_lines=997, n_violations=3)
    out = tmp_path / "budgets.json"
    run_bench({"synthetic": str(corpus)}, budgets={}, update_budgets_path=out)
    result = run_bench({"synthetic": str(corpus)}, budgets=load_budgets(out))
    assert result.passed, result.violations


# ── missing corpus is indeterminate, not pass ────────────────────────


def test_missing_corpus_dir_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_bench({"gone": str(tmp_path / "does-not-exist")}, budgets={})
