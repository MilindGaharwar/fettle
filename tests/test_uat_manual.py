"""Tests for fettle.uat.manual (Stage 5, S5.4)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from fettle.uat.manual import (
    format_manual_guide,
    load_attestations,
    record_attestation,
)

SCENARIOS = [
    {"id": "greeter/S1", "title": "Basic greeting",
     "steps": ["Given the app is installed",
               "When the user runs `greet Ada`",
               'Then the output contains "Hello, Ada"'],
     "requirements": []},
]

SPEC = """\
---
fettle-spec: v1
id: greeter
status: active
scope:
  - "src/**"
---

## Requirements

- R1. Greets the user by name.

## Scenarios

### S1. Basic greeting (traces R1)

- Given the app is installed
- When the user runs `greet Ada`
- Then the output contains "Hello, Ada"
"""


class TestManualGuide:
    def test_numbered_steps_with_plain_verbs(self):
        guide = format_manual_guide(SCENARIOS)
        assert "Scenario greeter/S1: Basic greeting" in guide
        assert "1. Set up: the app is installed" in guide
        assert "2. Do: the user runs `greet Ada`" in guide
        assert '3. Check: the output contains "Hello, Ada"' in guide
        assert "fettle uat attest greeter/S1" in guide

    def test_empty_scenarios_message(self):
        guide = format_manual_guide([])
        assert "No active spec scenarios" in guide
        assert "fettle spec lint" in guide


class TestAttest:
    def _patch(self):
        return patch("fettle.uat.session.collect_scenarios",
                     return_value=SCENARIOS)

    def test_record_and_load(self, tmp_path):
        with self._patch():
            entry, err = record_attestation(str(tmp_path), "greeter/S1",
                                            "matches", "saw Hello, Ada",
                                            operator="milind")
        assert err == ""
        assert entry["source"] == "operator"  # labeled peer, never mixed
        stored = load_attestations(str(tmp_path))
        assert stored[0]["scenario_id"] == "greeter/S1"
        assert stored[0]["operator"] == "milind"

    def test_appends(self, tmp_path):
        with self._patch():
            record_attestation(str(tmp_path), "greeter/S1", "matches", "x")
            record_attestation(str(tmp_path), "greeter/S1", "differs", "y")
        assert len(load_attestations(str(tmp_path))) == 2

    def test_rejects_bad_outcome(self, tmp_path):
        with self._patch():
            _, err = record_attestation(str(tmp_path), "greeter/S1", "pass", "x")
        assert "outcome must be one of" in err

    def test_rejects_empty_evidence(self, tmp_path):
        with self._patch():
            _, err = record_attestation(str(tmp_path), "greeter/S1",
                                        "matches", "   ")
        assert "without evidence" in err

    def test_rejects_unknown_scenario(self, tmp_path):
        with self._patch():
            _, err = record_attestation(str(tmp_path), "nope/S9", "matches", "x")
        assert "unknown scenario" in err and "greeter/S1" in err


class TestCLI:
    def _repo(self, tmp_path: Path) -> Path:
        (tmp_path / ".git").mkdir()
        (tmp_path / "specs").mkdir()
        (tmp_path / "specs" / "greeter.md").write_text(SPEC)
        return tmp_path

    def test_uat_manual(self, tmp_path):
        repo = self._repo(tmp_path)
        r = subprocess.run([sys.executable, "-m", "fettle.cli", "uat", "manual"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 0
        assert "Scenario greeter/S1" in r.stdout
        assert "Record it:" in r.stdout

    def test_uat_attest_roundtrip(self, tmp_path):
        repo = self._repo(tmp_path)
        r = subprocess.run(
            [sys.executable, "-m", "fettle.cli", "uat", "attest", "greeter/S1",
             "--outcome", "matches", "--observed", "Hello, Ada printed"],
            cwd=repo, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "source: operator" in r.stdout
        data = json.loads((repo / ".fettle" / "uat-attestations.json").read_text())
        assert data[0]["observed"] == "Hello, Ada printed"

    def test_uat_attest_unknown_scenario_exit_2(self, tmp_path):
        repo = self._repo(tmp_path)
        r = subprocess.run(
            [sys.executable, "-m", "fettle.cli", "uat", "attest", "x/S9",
             "--outcome", "matches", "--observed", "y"],
            cwd=repo, capture_output=True, text=True)
        assert r.returncode == 2
        assert "unknown scenario" in r.stderr
