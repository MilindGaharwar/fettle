"""Tests for fettle.uat.reconcile (Stage 5, S5.3)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fettle.evidence import parse_artifact
from fettle.uat.reconcile import (
    Verdict,
    evaluate_judgment,
    format_verdicts,
    parse_transcript,
    reconcile,
    reconcile_session,
    write_report,
)
from fettle.runners import RunnerResult

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


class TestIndependentJudgment:
    class Runner:
        def __init__(self, transcript: str, error: str = ""):
            self.transcript = transcript
            self.error = error
            self.calls = []

        def run(self, prompt, cwd, timeout_s=600):
            self.calls.append({"prompt": prompt, "cwd": cwd, "timeout_s": timeout_s})
            return RunnerResult(self.transcript, 0, 0.1, self.error)

    def test_flags_wrong_reason_pass_with_exact_artifact_reference(self, tmp_path):
        artifact = {"scenario_id": "greeter/S1", "block_sha": "abc123",
                    "block": {"observed": "fallback output", "outcome": "matches"}}
        runner = self.Runner(json.dumps({"findings": [{
            "scenario_id": "greeter/S1",
            "severity": "high",
            "summary": "The output came from a fallback, not saved state.",
            "artifact_sha": "abc123",
        }]}))

        result = evaluate_judgment(
            str(tmp_path), "SCENARIO: greeter/S1\nOUTCOME: matches\n",
            {"greeter/S1": artifact}, runner, timeout_s=30,
        )

        assert result["status"] == "completed"
        assert result["findings"][0]["severity"] == "high"
        assert result["findings"][0]["artifact"] == {
            "scenario_id": "greeter/S1", "block_sha": "abc123"}
        assert "independent reviewer" in runner.calls[0]["prompt"]
        assert "fallback output" in runner.calls[0]["prompt"]

    def test_finding_without_matching_artifact_does_not_resolve(self, tmp_path):
        runner = self.Runner(json.dumps({"findings": [{
            "scenario_id": "greeter/S1", "severity": "high",
            "summary": "Suspicious pass", "artifact_sha": "wrong",
        }]}))
        result = evaluate_judgment(
            str(tmp_path), "transcript",
            {"greeter/S1": {"scenario_id": "greeter/S1", "block_sha": "actual"}},
            runner,
        )
        assert result["status"] == "indeterminate"
        assert result["findings"] == []
        assert "artifact" in result["error"]

    def test_malformed_or_unavailable_evaluation_is_non_pass(self, tmp_path):
        malformed = evaluate_judgment(str(tmp_path), "t", {}, self.Runner("not-json"))
        unavailable = evaluate_judgment(
            str(tmp_path), "t", {}, self.Runner("", error="runner unavailable"))
        assert malformed["status"] == "indeterminate"
        assert unavailable["status"] == "tool_error"

    def test_judgment_finding_makes_report_incomplete_without_changing_verdict(self,
                                                                              tmp_path):
        judgment = {"status": "completed", "findings": [{"severity": "high"}]}
        path, err = write_report(
            str(tmp_path), {"session_id": "uat-x", "surface": "cli"},
            [Verdict("greeter/S1", "CONFIRMED")], judgment=judgment,
        )
        assert err == ""
        report = json.loads(Path(path).read_text())
        assert report["verdicts"][0]["verdict"] == "CONFIRMED"
        assert report["completion"]["complete"] is False


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
        from fettle.uat.artifacts import write_scenario_artifacts

        write_scenario_artifacts(str(wt), transcript.read_text(encoding="utf-8"),
                                 SCENARIOS, surface="cli")
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

    def test_configured_restart_probe_reconciles_against_artifact(self, tmp_path):
        from fettle.uat.session import write_restart_probe_artifact

        wt = tmp_path / "wt"
        (wt / ".fettle").mkdir(parents=True)
        text = (
            "SCENARIO: greeter/S1\nOBSERVED: $ greet Ada -> Hello, Ada!\n"
            "OUTCOME: matches\n"
            "RESTART_PROBE:\nBEFORE: profile Ada exists\n"
            "AFTER: profile Ada exists after restart\nOUTCOME: persisted\n"
            "NOTES: application was stopped and relaunched\n"
        )
        transcript = wt / ".fettle" / "t.txt"
        transcript.write_text(text)
        restart_probe = write_restart_probe_artifact(str(wt), text)
        (wt / ".fettle" / "uat-session.json").write_text(json.dumps({
            "session_id": "uat-x", "surface": "cli", "status": "completed",
            "scenario_ids": ["greeter/S1"], "transcript": str(transcript),
            "restart_probe": restart_probe,
        }))
        from fettle.uat.artifacts import write_scenario_artifacts

        write_scenario_artifacts(str(wt), text, SCENARIOS, surface="cli")
        with patch("fettle.uat.session.collect_scenarios", return_value=SCENARIOS):
            verdicts, _, err = reconcile_session(str(tmp_path), str(wt))

        assert err == ""
        assert [v.verdict for v in verdicts] == ["CONFIRMED", "CONFIRMED"]
        assert verdicts[-1].scenario_id == "__lifecycle__/restart-persistence"
        report = json.loads((wt / ".fettle" / "uat-report.json").read_text())
        assert report["lifecycle"]["restart_probe"]["verdict"] == "CONFIRMED"

    def test_configured_restart_probe_missing_evidence_cannot_pass(self, tmp_path):
        wt = tmp_path / "wt"
        (wt / ".fettle").mkdir(parents=True)
        transcript = wt / ".fettle" / "t.txt"
        transcript.write_text(
            "SCENARIO: greeter/S1\nOBSERVED: $ greet Ada -> Hello, Ada!\n"
            "OUTCOME: matches\n")
        (wt / ".fettle" / "uat-session.json").write_text(json.dumps({
            "session_id": "uat-x", "surface": "cli", "status": "completed",
            "scenario_ids": ["greeter/S1"], "transcript": str(transcript),
            "restart_probe": {"status": "missing"},
        }))
        from fettle.uat.artifacts import write_scenario_artifacts

        write_scenario_artifacts(str(wt), transcript.read_text(), SCENARIOS, "cli")
        with patch("fettle.uat.session.collect_scenarios", return_value=SCENARIOS):
            verdicts, _, err = reconcile_session(str(tmp_path), str(wt))

        assert err == ""
        assert verdicts[-1].verdict == "INDETERMINATE"
        assert "restart evidence" in verdicts[-1].note

    def test_stateless_restart_probe_is_not_applicable_in_report(self, tmp_path):
        wt = tmp_path / "wt"
        (wt / ".fettle").mkdir(parents=True)
        transcript = wt / ".fettle" / "t.txt"
        transcript.write_text(
            "SCENARIO: greeter/S1\nOBSERVED: $ greet Ada -> Hello, Ada!\n"
            "OUTCOME: matches\n")
        (wt / ".fettle" / "uat-session.json").write_text(json.dumps({
            "session_id": "uat-x", "surface": "cli", "status": "completed",
            "scenario_ids": ["greeter/S1"], "transcript": str(transcript),
            "restart_probe": {"status": "NOT_APPLICABLE", "reason": "no command"},
        }))
        from fettle.uat.artifacts import write_scenario_artifacts

        write_scenario_artifacts(str(wt), transcript.read_text(), SCENARIOS, "cli")
        with patch("fettle.uat.session.collect_scenarios", return_value=SCENARIOS):
            verdicts, _, err = reconcile_session(str(tmp_path), str(wt))

        assert err == ""
        assert [v.verdict for v in verdicts] == ["CONFIRMED"]
        report = json.loads((wt / ".fettle" / "uat-report.json").read_text())
        assert report["lifecycle"]["restart_probe"]["verdict"] == "NOT_APPLICABLE"
