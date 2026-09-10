"""Tests for the behavioral eval harness (scripts/evals_runner.py) — WP-133.

Static side only (CI-safe, per the quorum safety model): scenario schema
validation, check evaluation against fake transcripts/workdirs, and
three-valued verdict composition. Live agent launches are faked through
the injectable runner seam — the unit suite never starts a real CLI.
"""

import os
import json
import sys
import textwrap
from pathlib import Path

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EVALS_DIR = os.path.join(PLUGIN_DIR, "evals", "scenarios")

sys.path.insert(0, os.path.join(PLUGIN_DIR))
from fettle.evals_runner import (  # noqa: E402
    EvalMetrics,
    Scenario,
    Verdict,
    discover_scenarios,
    evaluate_contextual_corpus,
    evaluate_contextual_rankings,
    load_scenario,
    run_scenario,
    validate_contextual_corpus,
)


def _write_scenario(tmp_path, body):
    d = tmp_path / "my-scenario"
    d.mkdir()
    (d / "scenario.yaml").write_text(textwrap.dedent(body))
    return d


VALID = """
    id: my-scenario
    language: python
    held_out: true
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
    assert s.language == "python"
    assert s.held_out is True
    assert len(s.checks) == 2


def test_unknown_language_rejected(tmp_path):
    d = _write_scenario(tmp_path, VALID.replace("language: python", "language: brainfuck"))
    with pytest.raises(ValueError, match="language"):
        load_scenario(d)


def test_held_out_must_be_boolean(tmp_path):
    d = _write_scenario(tmp_path, VALID.replace("held_out: true", "held_out: eventually"))
    with pytest.raises(ValueError, match="held_out"):
        load_scenario(d)


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
    assert result.metrics.repair_success is True
    assert result.metrics.repeated_violation is False
    assert result.metrics.diagnostic_bytes == len(result.transcript.encode("utf-8"))
    assert result.metrics.indeterminate_reason is None


def test_fail_when_file_check_fails(tmp_path):
    def runner(prompt, cwd):
        (cwd / "calc.py").write_text('def divide(a, b):\n    print("dbg")\n    return a / b\n')
        return "I added divide with a debug print"

    result = run_scenario(_load(tmp_path), runner=runner, workdir=tmp_path / "run")
    assert result.verdict == Verdict.FAIL
    assert result.metrics.repair_success is False
    assert result.metrics.repeated_violation is True
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
    assert "agent CLI missing" in result.metrics.indeterminate_reason


def test_turns_to_repair_recorded_when_runner_supplies_them(tmp_path):
    class Result:
        transcript = "I added divide to calc.py"
        error = ""
        turns = 2

    class Runner:
        def run(self, prompt, cwd, timeout_s):
            (cwd / "calc.py").write_text("def divide(a, b):\n    return a / b\n")
            return Result()

    result = run_scenario(_load(tmp_path), runner=Runner(), workdir=tmp_path / "run")
    assert isinstance(result.metrics, EvalMetrics)
    assert result.metrics.turns_to_repair == 2
    assert result.metrics.to_dict() == {
        "repair_success": True,
        "turns_to_repair": 2,
        "repeated_violation": False,
        "diagnostic_bytes": len(result.transcript.encode("utf-8")),
        "indeterminate_reason": None,
    }


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


# ── scenario path containment (L-06) ─────────────────────────────────


def test_setup_file_escaping_workdir_is_indeterminate(tmp_path):
    evil = VALID.replace("setup_files:", "setup_files:\n      ../escape.py: \"pwned\"", 1)
    scenario = load_scenario(_write_scenario(tmp_path, evil))
    called = {}

    def runner(prompt, cwd):
        called["ran"] = True
        return "x"

    result = run_scenario(scenario, runner=runner, workdir=tmp_path / "sub" / "run")
    assert result.verdict == Verdict.INDETERMINATE
    assert "containment" in result.transcript
    assert not called  # the agent never launched
    assert not (tmp_path / "sub" / "escape.py").exists()


def test_absolute_setup_path_is_indeterminate(tmp_path):
    evil = VALID.replace("setup_files:", f"setup_files:\n      {tmp_path}/abs.py: \"pwned\"", 1)
    scenario = load_scenario(_write_scenario(tmp_path, evil))
    result = run_scenario(scenario, runner=lambda p, c: "x", workdir=tmp_path / "run")
    assert result.verdict == Verdict.INDETERMINATE
    assert not (tmp_path / "abs.py").exists()


def test_file_check_escaping_workdir_fails_check(tmp_path):
    (tmp_path / "secret.txt").write_text("hunter2")
    evil = VALID.replace("path: calc.py", "path: ../secret.txt")
    scenario = load_scenario(_write_scenario(tmp_path, evil))
    result = run_scenario(scenario, runner=lambda p, c: "I added divide",
                          workdir=tmp_path / "run")
    assert result.verdict == Verdict.FAIL
    escaped = [c for c in result.checks if "escapes" in c.detail]
    assert escaped and not escaped[0].passed



# ── shipped scenarios stay statically valid (CI gate) ────────────────


def test_shipped_scenarios_validate():
    dirs = discover_scenarios(EVALS_DIR)
    assert dirs, "no shipped eval scenarios found"
    for d in dirs:
        load_scenario(d)  # raises on schema violation


def test_shipped_scenarios_cover_python_and_typescript_with_held_out_cases():
    scenarios = [load_scenario(d) for d in discover_scenarios(EVALS_DIR)]
    for language in ("python", "typescript"):
        assert any(s.language == language for s in scenarios)
        assert any(s.language == language and s.held_out for s in scenarios)


def test_contextual_precision_at_10_uses_returned_result_denominator():
    cases = [{
        "id": "small",
        "held_out": True,
        "ranked_contextual": ["a", "noise", "b"],
        "contextual_relevance": ["a", "b"],
    }]

    report = evaluate_contextual_rankings(cases, held_out=True)

    assert report == {
        "split": "held_out",
        "case_count": 1,
        "relevant_in_top_10": 2,
        "returned_in_top_10": 3,
        "precision_at_10_basis_points": 6667,
    }


def test_contextual_evaluation_keeps_development_and_held_out_separate():
    cases = [
        {"id": "dev", "held_out": False, "ranked_contextual": ["x"],
         "contextual_relevance": []},
        {"id": "held", "held_out": True, "ranked_contextual": ["y"],
         "contextual_relevance": ["y"]},
    ]

    development = evaluate_contextual_rankings(cases, held_out=False)
    held_out = evaluate_contextual_rankings(cases, held_out=True)

    assert development["case_count"] == 1
    assert development["precision_at_10_basis_points"] == 0
    assert held_out["case_count"] == 1
    assert held_out["precision_at_10_basis_points"] == 10_000


def test_contextual_precision_is_zero_when_no_contextual_results_returned():
    report = evaluate_contextual_rankings([
        {"id": "empty", "held_out": True, "ranked_contextual": [],
         "contextual_relevance": ["expected"]},
    ], held_out=True)

    assert report["returned_in_top_10"] == 0
    assert report["precision_at_10_basis_points"] == 0


def _contextual_case(case_id, split, group, *, ranker_relevant_first=True):
    candidates = []
    for index in range(12):
        relevant = index in {9, 11}
        score = 100 - index if not ranker_relevant_first else (200 if relevant else 100 - index)
        candidates.append({
            "stable_key": f"module:{index:02d}.py",
            "score": score,
            "depth": 2,
            "relevance": "relevant" if relevant else "irrelevant",
            "rationale": "changed behavior" if relevant else "no observed dependency",
            "reviews": [
                {"reviewer": "reviewer-a", "relevance": "relevant" if relevant else "irrelevant",
                 "rationale": "first blind review"},
                {"reviewer": "reviewer-b", "relevance": "relevant" if relevant else "irrelevant",
                 "rationale": "second blind review"},
            ],
        })
    return {
        "id": case_id,
        "split": split,
        "group": group,
        "repository_digest": "repo-digest",
        "revision": "revision-digest",
        "graph_digest": "graph-digest",
        "provider_digest": "provider-digest",
        "oracle_digest": "oracle-digest",
        "ranking_eligible": True,
        "required_targets": ["module:required.py"],
        "actual_required": ["module:required.py"],
        "candidates": candidates,
    }


def _contextual_corpus(cases, *, minimum_cases=1):
    return {
        "schema_version": 2,
        "review": {
            "reviewers": ["reviewer-a", "reviewer-b"],
            "labeling": "blind-randomized",
            "minimum_ranking_cases_per_split": minimum_cases,
            "minimum_candidates_per_case": 10,
            "minimum_relevant_per_case": 2,
            "minimum_irrelevant_per_case": 2,
        },
        "cases": cases,
    }


def test_contextual_corpus_v2_derives_paired_rankings_from_one_candidate_universe():
    corpus = _contextual_corpus([
        _contextual_case("held-1", "held_out", "repo-a/payments"),
    ])

    report = evaluate_contextual_corpus(corpus, split="held_out")

    assert report["case_count"] == 1
    assert report["ranker_precision_at_10_basis_points"] == 2000
    assert report["baseline_precision_at_10_basis_points"] == 1000
    assert report["paired_case_deltas_basis_points"] == [1000]
    assert report["paired_gain_ci95_basis_points"] == [1000, 1000]
    assert report["required_recall_basis_points"] == 10_000
    assert report["evaluation_ready"] is True
    assert report["promotion_ready"] is True


def test_contextual_corpus_v2_rejects_group_leakage_between_splits():
    corpus = _contextual_corpus([
        _contextual_case("dev-1", "development", "repo-a/payments"),
        _contextual_case("held-1", "held_out", "repo-a/payments"),
    ])

    with pytest.raises(ValueError, match="split leakage"):
        validate_contextual_corpus(corpus)


@pytest.mark.parametrize("mutation, reason", [
    (lambda case: case["candidates"].__delitem__(slice(9, None)), "at least 10 candidates"),
    (lambda case: [item.update(relevance="relevant") for item in case["candidates"]],
     "at least 2 irrelevant"),
    (lambda case: case["candidates"][0].update(rationale=""), "rationale"),
])
def test_contextual_corpus_v2_rejects_non_discriminating_cases(mutation, reason):
    case = _contextual_case("held-1", "held_out", "repo-a/payments")
    mutation(case)

    with pytest.raises(ValueError, match=reason):
        validate_contextual_corpus(_contextual_corpus([case]))


def test_contextual_corpus_v2_requires_enough_cases_before_promotion():
    corpus = _contextual_corpus([
        _contextual_case("held-1", "held_out", "repo-a/payments"),
    ], minimum_cases=20)

    report = evaluate_contextual_corpus(corpus, split="held_out")

    assert report["promotion_ready"] is False
    assert report["blocking_reasons"] == ["requires at least 20 ranking-eligible held_out cases"]


def test_contextual_corpus_v2_development_split_cannot_authorize_promotion():
    corpus = _contextual_corpus([
        _contextual_case("dev-1", "development", "repo-a/payments"),
    ])

    report = evaluate_contextual_corpus(corpus, split="development")

    assert report["evaluation_ready"] is True
    assert report["promotion_ready"] is False
    assert report["blocking_reasons"] == ["promotion requires the frozen held_out split"]


def test_contextual_corpus_v2_requires_immutable_case_identity():
    case = _contextual_case("held-1", "held_out", "repo-a/payments")
    case["graph_digest"] = ""

    with pytest.raises(ValueError, match="immutable identity"):
        validate_contextual_corpus(_contextual_corpus([case]))


def test_contextual_corpus_v2_requires_blind_reviews_from_declared_reviewers():
    case = _contextual_case("held-1", "held_out", "repo-a/payments")
    case["candidates"][0]["reviews"] = case["candidates"][0]["reviews"][:1]

    with pytest.raises(ValueError, match="declared reviewer"):
        validate_contextual_corpus(_contextual_corpus([case]))


def test_contextual_corpus_v2_rejects_negative_ranking_values():
    case = _contextual_case("held-1", "held_out", "repo-a/payments")
    case["candidates"][0]["depth"] = -1

    with pytest.raises(ValueError, match="non-negative integer"):
        validate_contextual_corpus(_contextual_corpus([case]))


def test_contextual_corpus_v2_cannot_prove_recall_without_required_targets():
    case = _contextual_case("held-1", "held_out", "repo-a/payments")
    case["required_targets"] = []
    case["actual_required"] = []

    report = evaluate_contextual_corpus(_contextual_corpus([case]), split="held_out")

    assert report["required_recall_basis_points"] is None
    assert "requires at least one required-impact label" in report["blocking_reasons"]


def test_contextual_corpus_v2_reports_zero_baseline_as_unmeasurable_gain():
    case = _contextual_case("held-1", "held_out", "repo-a/payments")
    for index, candidate in enumerate(case["candidates"]):
        relevant = index in {10, 11}
        candidate["relevance"] = "relevant" if relevant else "irrelevant"
        candidate["score"] = 200 if relevant else 100 - index

    report = evaluate_contextual_corpus(_contextual_corpus([case]), split="held_out")

    assert report["relative_gain_basis_points"] is None
    assert report["blocking_reasons"] == ["baseline precision is zero; relative gain is undefined"]


def test_shipped_contextual_corpus_v2_is_collection_ready_not_promotion_ready():
    corpus = json.loads((
        Path(PLUGIN_DIR) / "tests" / "fixtures" / "contextual_impact" / "corpus-v2.json"
    ).read_text())

    assert validate_contextual_corpus(corpus) == []
    assert evaluate_contextual_corpus(corpus, split="held_out")["promotion_ready"] is False


# ── WP-11 (audit M-07): missing PyYAML must fail with guidance ───────


def test_missing_pyyaml_exits_with_install_hint(monkeypatch, capsys):
    import importlib

    class _BlockYaml:
        def find_spec(self, name, path=None, target=None):
            if name == "yaml":
                raise ImportError("blocked for test")
            return None

    monkeypatch.delitem(sys.modules, "yaml", raising=False)
    monkeypatch.delitem(sys.modules, "fettle.evals_runner", raising=False)
    monkeypatch.setattr(sys, "meta_path", [_BlockYaml()] + sys.meta_path)
    with pytest.raises(SystemExit) as exc:
        importlib.import_module("fettle.evals_runner")
    assert exc.value.code == 2
    assert "install 'finefettle[evals]'" in capsys.readouterr().err


def test_pyyaml_declared_in_evals_extra():
    pyproject = os.path.join(PLUGIN_DIR, "pyproject.toml")
    with open(pyproject, "rb") as fh:
        import tomllib

        data = tomllib.load(fh)
    dependencies = data["project"]["optional-dependencies"]["evals"]
    assert any(dep.startswith("pyyaml") for dep in dependencies)
