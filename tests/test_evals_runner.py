"""Tests for the behavioral eval harness (scripts/evals_runner.py) — WP-133.

Static side only (CI-safe, per the quorum safety model): scenario schema
validation, check evaluation against fake transcripts/workdirs, and
three-valued verdict composition. Live agent launches are faked through
the injectable runner seam — the unit suite never starts a real CLI.
"""

import os
import sys
import textwrap

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EVALS_DIR = os.path.join(PLUGIN_DIR, "evals", "scenarios")

sys.path.insert(0, os.path.join(PLUGIN_DIR))
from fettle.evals_runner import (  # noqa: E402
    Scenario,
    Verdict,
    discover_scenarios,
    load_scenario,
    run_scenario,
)


def _write_scenario(tmp_path, body):
    d = tmp_path / "my-scenario"
    d.mkdir()
    (d / "scenario.yaml").write_text(textwrap.dedent(body))
    return d


VALID = """
    id: my-scenario
    prompt: "Add a divide function to calc.py"
    setup_files:
      calc.py: |
        def add(a, b):
            return a + b
    checks:
      - type: file_not_matches
        path: calc.py
        regex: "print\\\\("
      - type: transcript_matches
        regex: "divide"
"""


# ── schema validation ────────────────────────────────────────────────


def test_valid_scenario_loads(tmp_path):
    s = load_scenario(_write_scenario(tmp_path, VALID))
    assert isinstance(s, Scenario)
    assert s.id == "my-scenario"
    assert len(s.checks) == 2


def test_missing_prompt_rejected(tmp_path):
    d = _write_scenario(tmp_path, "id: x\nchecks: []\n")
    with pytest.raises(ValueError, match="prompt"):
        load_scenario(d)


def test_unknown_check_type_rejected(tmp_path):
    d = _write_scenario(
        tmp_path,
        "id: x\nprompt: p\nchecks:\n  - type: telepathy\n    regex: y\n",
    )
    with pytest.raises(ValueError, match="telepathy"):
        load_scenario(d)


def test_empty_checks_rejected(tmp_path):
    d = _write_scenario(tmp_path, "id: x\nprompt: p\nchecks: []\n")
    with pytest.raises(ValueError, match="check"):
        load_scenario(d)


# ── verdict composition ──────────────────────────────────────────────


def _load(tmp_path):
    return load_scenario(_write_scenario(tmp_path, VALID))


def test_pass_when_all_checks_pass(tmp_path):
    def runner(prompt, cwd):
        (cwd / "calc.py").write_text("def divide(a, b):\n    return a / b\n")
        return "I added divide to calc.py"

    result = run_scenario(_load(tmp_path), runner=runner, workdir=tmp_path / "run")
    assert result.verdict == Verdict.PASS


def test_fail_when_file_check_fails(tmp_path):
    def runner(prompt, cwd):
        (cwd / "calc.py").write_text('def divide(a, b):\n    print("dbg")\n    return a / b\n')
        return "I added divide with a debug print"

    result = run_scenario(_load(tmp_path), runner=runner, workdir=tmp_path / "run")
    assert result.verdict == Verdict.FAIL
    assert any(not c.passed for c in result.checks)


def test_fail_when_transcript_check_fails(tmp_path):
    def runner(prompt, cwd):
        (cwd / "calc.py").write_text("def divide(a, b):\n    return a / b\n")
        return "I did something unrelated"

    result = run_scenario(_load(tmp_path), runner=runner, workdir=tmp_path / "run")
    assert result.verdict == Verdict.FAIL


def test_indeterminate_when_runner_raises(tmp_path):
    def runner(prompt, cwd):
        raise RuntimeError("agent CLI missing")

    result = run_scenario(_load(tmp_path), runner=runner, workdir=tmp_path / "run")
    assert result.verdict == Verdict.INDETERMINATE


def test_indeterminate_on_empty_transcript_with_transcript_checks(tmp_path):
    def runner(prompt, cwd):
        (cwd / "calc.py").write_text("def divide(a, b):\n    return a / b\n")
        return ""

    result = run_scenario(_load(tmp_path), runner=runner, workdir=tmp_path / "run")
    assert result.verdict == Verdict.INDETERMINATE


def test_setup_files_seeded_into_workdir(tmp_path):
    seen = {}

    def runner(prompt, cwd):
        seen["calc"] = (cwd / "calc.py").read_text()
        (cwd / "calc.py").write_text("def divide(a, b):\n    return a / b\n")
        return "divide added"

    run_scenario(_load(tmp_path), runner=runner, workdir=tmp_path / "run")
    assert "def add" in seen["calc"]


# ── shipped scenarios stay statically valid (CI gate) ────────────────


def test_shipped_scenarios_validate():
    dirs = discover_scenarios(EVALS_DIR)
    assert dirs, "no shipped eval scenarios found"
    for d in dirs:
        load_scenario(d)  # raises on schema violation
