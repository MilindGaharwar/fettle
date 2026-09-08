"""P47 contract tests — advisory `fettle graph` CLI."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from fettle.graph_cli import main as graph_main
from fettle.graph_types import canonical_digest

FIXTURES = Path(__file__).parent / "fixtures" / "contextual_impact"

SPEC = """---
fettle-spec: v1
id: ledger-core
status: active
scope:
  - "src/**"
---

## Requirements

- R1. Transfers move funds.

## Scenarios

### S1. Transfer moves funds (traces R1)
Given accounts
When transfer
Then balances move
"""


def _make_repo(tmp_path: Path) -> str:
    import subprocess

    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "ledger.md").write_text(SPEC, encoding="utf-8")
    pkg = tmp_path / "src" / "fettle_demo"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "accounts.py").write_text(
        "class Account:\n    def __init__(self):\n        self.b = 0\n",
        encoding="utf-8",
    )
    (pkg / "ledger.py").write_text(
        "from fettle_demo.accounts import Account\n\n"
        "def t(s: Account, d: Account) -> None:\n"
        "    d.b += s.b\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests_t"
    tests.mkdir()
    (tests / "test_ledger.py").write_text(
        "def test_t():\n    # traces: ledger-core/S1\n    assert True\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(tmp_path)])
    for flag in (("config", "user.email", "test@fettle.invalid"), ("config", "user.name", "t")):
        subprocess.run(["git", "-C", str(tmp_path), *flag], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-qm", "init"], capture_output=True
    )
    return str(tmp_path)


def test_status_reports_digest_and_provider_completeness(tmp_path, capsys):
    root = _make_repo(tmp_path)

    assert graph_main(["status", "--root", root, "--json"]) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "completed"
    assert len(out["digest"]) == 64
    assert {p["id"] for p in out["providers"]} >= {"specs", "python_imports"}


def test_impact_closure_reaches_spec_scenarios_and_tests(tmp_path, capsys):
    root = _make_repo(tmp_path)

    assert graph_main(["impact", "--root", root, "--json", "src/fettle_demo/accounts.py"]) == 0

    out = json.loads(capsys.readouterr().out)
    keys = {a["stable_key"] for a in out["affected"]}
    assert "module:src/fettle_demo/ledger.py" in keys
    # P46+ governs edges make the governing spec part of the advisory superset.
    assert "spec:ledger-core" in keys


@pytest.mark.parametrize("json_output", [False, True])
def test_default_impact_output_matches_frozen_p47_oracle(
    tmp_path, capsys, json_output
):
    root = _make_repo(tmp_path)
    args = ["impact", "--root", root]
    if json_output:
        args.append("--json")
    args.append("src/fettle_demo/accounts.py")

    assert graph_main(args) == 0

    actual = capsys.readouterr().out
    fixture = FIXTURES / ("p47-impact.json" if json_output else "p47-impact.txt")
    if json_output:
        assert json.loads(actual) == json.loads(fixture.read_text())
    else:
        assert actual == fixture.read_text()


def test_contextual_corpus_freezes_required_and_relevance_labels():
    corpus = json.loads((FIXTURES / "corpus.json").read_text())
    scenarios = corpus["scenarios"]

    assert corpus["schema_version"] == 1
    assert {scenario["case"] for scenario in scenarios} == {
        "direct", "transitive", "excluded", "incomplete", "cycle",
        "hyperedge", "conflicting-provider", "bounded",
    }
    assert sum(scenario["held_out"] for scenario in scenarios) >= corpus["review"]["minimum_held_out_cases"]
    assert len(corpus["review"]["reviewers"]) >= 2
    assert all("required_targets" in scenario for scenario in scenarios)
    assert all("contextual_relevance" in scenario for scenario in scenarios)
    conflict = next(scenario for scenario in scenarios if scenario["case"] == "conflicting-provider")
    assert len({fact["provider"] for fact in conflict["facts"]}) == 1
    assert len({fact["fact_set"] for fact in conflict["facts"]}) > 1


def test_contextual_corpus_digest_is_order_and_checkout_independent(tmp_path):
    corpus = json.loads((FIXTURES / "corpus.json").read_text())
    shuffled = json.loads(json.dumps(corpus))
    random.Random(47).shuffle(shuffled["scenarios"])
    for scenario in shuffled["scenarios"]:
        random.Random(scenario["id"]).shuffle(scenario["facts"])

    def normalized_digest(data):
        scenarios = []
        for scenario in data["scenarios"]:
            item = dict(scenario)
            item["facts"] = sorted(
                item["facts"], key=lambda fact: tuple(sorted(fact.items()))
            )
            scenarios.append(item)
        return canonical_digest({
            "schema_version": data["schema_version"],
            "review": data["review"],
            "scenarios": sorted(scenarios, key=lambda item: item["id"]),
        })

    copied = tmp_path / "elsewhere" / "corpus.json"
    copied.parent.mkdir()
    copied.write_text(json.dumps(shuffled))
    assert normalized_digest(corpus) == normalized_digest(json.loads(copied.read_text()))


def test_impact_from_spec_reaches_governed_modules_and_tests(tmp_path, capsys):
    root = _make_repo(tmp_path)

    assert graph_main(["impact", "--root", root, "--json", "specs/ledger.md"]) == 0

    out = json.loads(capsys.readouterr().out)
    keys = {a["stable_key"] for a in out["affected"]}
    assert "scenario:ledger-core/S1" in keys
    assert "test:tests_t/test_ledger.py" in keys


def test_impact_unmatched_path_is_unknown_exit_2(tmp_path, capsys):
    root = _make_repo(tmp_path)

    assert graph_main(["impact", "--root", root, "--json", "nope/none.py"]) == 2

    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "unknown"


def test_uncommitted_root_fails_closed(tmp_path, capsys):
    (tmp_path / "x.py").write_text("x = 1\n", encoding="utf-8")

    assert graph_main(["status", "--root", str(tmp_path), "--json"]) == 2

    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "tool_error"


def test_impact_requires_paths():
    with pytest.raises(SystemExit) as excinfo:
        graph_main(["impact"])
    assert excinfo.value.code == 2  # argparse: missing required paths


def test_contextual_json_is_versioned_advisory_and_explained(tmp_path, capsys):
    root = _make_repo(tmp_path)

    assert graph_main([
        "impact", "--root", root, "--contextual", "--json",
        "src/fettle_demo/accounts.py",
    ]) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["schema_version"] == 1
    assert out["experimental"] is True
    assert out["advisory"] is True
    assert out["state"] == "complete"
    assert out["required"]
    assert all(item["score"] == sum(value for _name, value in item["score_components"])
               for item in out["required"] + out["contextual"])
    assert all(item["paths"] for item in out["required"] + out["contextual"])
    assert len(out["analysis_digest"]) == 64


def test_contextual_human_output_is_grouped_and_details_are_opt_in(tmp_path, capsys):
    root = _make_repo(tmp_path)
    args = ["impact", "--root", root, "--contextual", "src/fettle_demo/accounts.py"]

    assert graph_main(args) == 0
    concise = capsys.readouterr().out
    assert "REQUIRED" in concise
    assert "CONTEXTUAL" in concise
    assert "next: fettle graph impact" in concise
    assert "path:" not in concise
    assert len(concise.encode()) <= 2048

    assert graph_main([*args[:-1], "--detailed", args[-1]]) == 0
    detailed = capsys.readouterr().out
    assert "path:" in detailed
    assert "score:" in detailed


def test_contextual_option_is_discoverable(capsys):
    with pytest.raises(SystemExit) as excinfo:
        graph_main(["impact", "--help"])

    assert excinfo.value.code == 0
    help_text = capsys.readouterr().out
    assert "--contextual" in help_text
    assert "experimental" in help_text.lower()
    assert "--detailed" in help_text


def test_detailed_requires_contextual(capsys):
    with pytest.raises(SystemExit) as excinfo:
        graph_main(["impact", "--detailed", "src/app.py"])

    assert excinfo.value.code == 2
    assert "--detailed requires --contextual" in capsys.readouterr().err
