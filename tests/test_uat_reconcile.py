"""Tests for fettle.uat.reconcile (Stage 5, S5.3)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fettle.evidence import parse_artifact
from fettle.uat.reconcile import (
    format_verdicts,
    parse_transcript,
    reconcile,
    reconcile_session,
    write_report,
)

SCENARIOS = [
    {"id": "greeter/S1", "title": "Basic greeting",
     "steps": ["Given the app is installed",
               "When the user runs `greet Ada`",
               'Then the output contains "Hello, Ada"'],
     "requirements": ["Greets the user by name."]},
    {"id": "greeter/S2", "title": "Missing name",
     "steps": ["Given the app is installed",
               "When the user runs `greet`",
               "Then a usage error is shown"],
     "requirements": []},
]


class TestParseTranscript:
    def test_blocks_extracted(self):
        text = ("noise before\n"
                "SCENARIO: greeter/S1\n"
                "OBSERVED: $ greet Ada\nHello, Ada!\n"
                "OUTCOME: matches\n"
                "NOTES: exit code 0\n")
        blocks = parse_transcript(text)
        assert blocks["greeter/S1"]["outcome"] == "matches"
        assert "Hello, Ada!" in blocks["greeter/S1"]["observed"]  # multi-line
        assert blocks["greeter/S1"]["notes"] == "exit code 0"

    def test_later_block_wins(self):
        text = ("SCENARIO: greeter/S1\nOUTCOME: differs\n"
                "SCENARIO: greeter/S1\nOBSERVED: retried ok\nOUTCOME: matches\n")
        assert parse_transcript(text)["greeter/S1"]["outcome"] == "matches"

    def test_empty_transcript(self):
        assert parse_transcript("") == {}


class TestReconcile:
    def test_confirmed_with_real_evidence(self):
        text = ("SCENARIO: greeter/S1\nOBSERVED: $ greet Ada -> Hello, Ada!\n"
                "OUTCOME: matches\n"
                "SCENARIO: greeter/S2\nOBSERVED: usage: greet NAME\nOUTCOME: matches\n")
        verdicts = reconcile(SCENARIOS, text)
        assert [v.verdict for v in verdicts] == ["CONFIRMED", "CONFIRMED"]

    def test_unobserved_is_first_class(self):
        text = ("SCENARIO: greeter/S1\nOBSERVED: $ greet Ada -> Hello, Ada!\n"
                "OUTCOME: matches\n")
        verdicts = reconcile(SCENARIOS, text)
        assert verdicts[1].verdict == "UNOBSERVED"
        assert "never reported" in verdicts[1].note

    def test_contradicted_and_blocked(self):
        text = ("SCENARIO: greeter/S1\nOBSERVED: Hola, Ada\nOUTCOME: differs\n"
                "SCENARIO: greeter/S2\nOBSERVED: binary missing\n"
                "OUTCOME: could-not-attempt\n")
        verdicts = reconcile(SCENARIOS, text)
        assert [v.verdict for v in verdicts] == ["CONTRADICTED", "BLOCKED"]

    def test_parroted_match_downgrades_to_indeterminate(self):
        text = ("SCENARIO: greeter/S1\n"
                'OBSERVED: the output contains "Hello, Ada"\n'
                "OUTCOME: matches\n")
        v = reconcile(SCENARIOS[:1], text)[0]
        assert v.verdict == "INDETERMINATE"
        assert "auto-answer" in v.note

    def test_empty_evidence_downgrades(self):
        text = "SCENARIO: greeter/S1\nOBSERVED:\nOUTCOME: matches\n"
        assert reconcile(SCENARIOS[:1], text)[0].verdict == "INDETERMINATE"

    def test_unknown_outcome_indeterminate(self):
        text = "SCENARIO: greeter/S1\nOBSERVED: stuff\nOUTCOME: maybe\n"
        v = reconcile(SCENARIOS[:1], text)[0]
        assert v.verdict == "INDETERMINATE" and "maybe" in v.note


class TestArtifactsAndSummary:
    def test_write_report(self, tmp_path):
        verdicts = reconcile(SCENARIOS, "")
        path, err = write_report(str(tmp_path), {"session_id": "uat-x",
                                                 "surface": "cli"}, verdicts)
        assert err == ""
        data = json.loads(Path(path).read_text())
        assert data["session_id"] == "uat-x"
        assert len(data["verdicts"]) == 2
        assert data["completion"] == {
            "complete": False,
            "required_total": 2,
            "required_confirmed": 0,
        }

    def test_canonical_report_references_full_report_without_transcript(self, tmp_path):
        verdicts = reconcile(SCENARIOS, "")
        path, err = write_report(str(tmp_path), {
            "session_id": "uat-x", "surface": "cli", "redacted_lines": 2,
        }, verdicts)
        assert err == ""
        report = json.loads(Path(path).read_text())
        artifact = parse_artifact(
            (tmp_path / ".fettle" / "uat-report.evidence.json").read_bytes()
        )
        assert "canonical_evidence" not in report
        assert artifact.payload["report"]["path"] == "uat-report.json"
        assert artifact.payload["report"]["digest"] == (
            "sha256:" + __import__("hashlib").sha256(Path(path).read_bytes()).hexdigest()
        )
        assert artifact.payload["redacted_lines"] == 2
        assert artifact.payload["completion"]["required_total"] == 2
        assert artifact.payload["verdicts"] == (
            {"scenario_id": "greeter/S1", "verdict": "UNOBSERVED"},
            {"scenario_id": "greeter/S2", "verdict": "UNOBSERVED"},
        )
        assert "observed" not in str(artifact.payload)

    def test_canonical_report_sidecar_can_be_rolled_back(self, tmp_path):
        verdicts = reconcile(SCENARIOS, "")
        path, err = write_report(str(tmp_path), {
            "session_id": "uat-x", "surface": "cli", "canonical_evidence": False,
        }, verdicts)
        assert err == ""
        assert "canonical_evidence" not in json.loads(Path(path).read_text())
        assert not (tmp_path / ".fettle" / "uat-report.evidence.json").exists()

    def test_canonical_write_failure_preserves_report_and_returns_diagnostic(self, tmp_path):
        verdicts = reconcile(SCENARIOS, "")
        with patch("fettle.uat.reconcile._write_bytes_atomic", side_effect=OSError("full")):
            path, err = write_report(
                str(tmp_path), {"session_id": "uat-x", "surface": "cli"}, verdicts,
            )
        assert err == "canonical UAT report evidence unavailable: full"
        assert json.loads(Path(path).read_text())["completion"]["complete"] is False

    def test_format_verdicts_expands_problems(self):
        text = ("SCENARIO: greeter/S1\nOBSERVED: Hola\nOUTCOME: differs\n"
                "NOTES: wrong language\n")
        out = format_verdicts(reconcile(SCENARIOS, text))
        assert "CONTRADICTED: 1" in out and "UNOBSERVED: 1" in out
        assert "observed: Hola" in out and "note: wrong language" in out


class TestReconcileSession:
    def test_end_to_end_from_checkpoint(self, tmp_path):
        wt = tmp_path / "wt"
        (wt / ".fettle").mkdir(parents=True)
        transcript = wt / ".fettle" / "t.txt"
        transcript.write_text(
            "SCENARIO: greeter/S1\nOBSERVED: $ greet Ada -> Hello, Ada!\n"
            "OUTCOME: matches\n")
        (wt / ".fettle" / "uat-session.json").write_text(json.dumps({
            "session_id": "uat-x", "surface": "cli", "status": "completed",
            "scenario_ids": ["greeter/S1"], "transcript": str(transcript)}))
        with patch("fettle.uat.session.collect_scenarios",
                   return_value=SCENARIOS):
            verdicts, cp, err = reconcile_session(str(tmp_path), str(wt))
        assert err == ""
        assert [v.verdict for v in verdicts] == ["CONFIRMED"]  # S2 not in session
        assert (wt / ".fettle" / "uat-report.json").exists()

    def test_missing_checkpoint(self, tmp_path):
        verdicts, _, err = reconcile_session(str(tmp_path), str(tmp_path))
        assert verdicts == [] and "no session checkpoint" in err

    def test_missing_transcript(self, tmp_path):
        (tmp_path / ".fettle").mkdir()
        (tmp_path / ".fettle" / "uat-session.json").write_text(
            json.dumps({"session_id": "x", "status": "error"}))
        _, _, err = reconcile_session(str(tmp_path), str(tmp_path))
        assert "no transcript" in err
