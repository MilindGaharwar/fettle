"""P47 contract tests — advisory `fettle graph` CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fettle.graph_cli import main as graph_main

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
    for flag in (("config", "user.email", "t@t"), ("config", "user.name", "t")):
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
