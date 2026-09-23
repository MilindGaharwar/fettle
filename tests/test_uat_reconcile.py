"""Tests for fettle.uat.reconcile (Stage 5, S5.3)."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from fettle.evidence import parse_artifact
from fettle.uat.reconcile import (
    _looks_parroted,
    Verdict,
    evaluate_judgment,
    format_verdicts,
    parse_transcript,
    parse_restart_probe,
    reconcile_restart_probe,
    reconcile,
    reconcile_session,
    validate_canonical_evidence,
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
        assert blocks == {"greeter/S1": {"observed": "$ greet Ada\nHello, Ada!",
                         "outcome": "matches", "notes": "exit code 0"}}

    def test_conflicting_retry_is_unresolved(self):
        text = ("SCENARIO: greeter/S1\nOUTCOME: differs\n"
                "SCENARIO: greeter/S1\nOBSERVED: retried ok\nOUTCOME: matches\n")
        assert parse_transcript(text) == {"greeter/S1": {
            "observed": "retried ok", "outcome": "conflicting-attempts",
            "notes": "conflicting reports require independent attempt evidence"}}

    @pytest.mark.parametrize("section", ["RESTART_PROBE:", "CANDIDATE: discovery-1"])
    def test_sections_cannot_overwrite_scenario_fields(self, section):
        text = ("SCENARIO: greeter/S1\nnoise\nOBSERVED: first\n continuation \n\n"
                "OUTCOME: differs\nNOTES: retained\n" + section +
                "\nOBSERVED: injected\nOUTCOME: matches\nNOTES: injected\n"
                "SCENARIO: greeter/S2\n")
        assert parse_transcript(text) == {
            "greeter/S1": {"observed": "first\ncontinuation", "outcome": "differs", "notes": "retained"},
            "greeter/S2": {"observed": "", "outcome": "", "notes": ""},
        }

    def test_identical_retries_and_three_scenarios_stay_separate(self):
        block = "SCENARIO: greeter/S1\nOBSERVED: first\nOUTCOME: differs\n"
        text = block + block + "SCENARIO: greeter/S2\nOBSERVED: second\nSCENARIO: greeter/S3\nOBSERVED: third\n"
        assert parse_transcript(text) == {
            "greeter/S1": {"observed": "first", "outcome": "differs", "notes": ""},
            "greeter/S2": {"observed": "second", "outcome": "", "notes": ""},
            "greeter/S3": {"observed": "third", "outcome": "", "notes": ""},
        }

    @pytest.mark.parametrize("section", ["SCENARIO: greeter/S1", "CANDIDATE: discovery-1"])
    def test_final_restart_probe_preserves_multiline_fields_and_boundaries(self, section):
        text = ("RESTART_PROBE:\nBEFORE: stale\nAFTER: stale\n"
                "RESTART_PROBE:\nignored prose\nBEFORE: before\n detail-before \n\n"
                "AFTER: after\n detail-after \nOUTCOME: lost\nNOTES: note\n detail-note\n"
                + section + "\nBEFORE: injected\nAFTER: injected\n")
        assert parse_restart_probe(text) == {
            "before": "before\ndetail-before", "after": "after\ndetail-after",
            "outcome": "lost", "notes": "note\ndetail-note",
        }

    def test_absent_and_empty_restart_probe_are_distinct(self):
        assert parse_restart_probe("ordinary transcript") is None
        assert parse_restart_probe("RESTART_PROBE:\n") == {
            "before": "", "after": "", "outcome": "", "notes": ""}

    def test_empty_transcript(self):
        assert parse_transcript("") == {}


class TestRestartEvidence:
    @pytest.mark.parametrize("session,expected", [
        ({}, None),
        ({"restart_probe": {"status": "NOT_APPLICABLE"}}, None),
        ({"restart_probe": "malformed"}, "malformed restart evidence; rerun UAT"),
        ({"restart_probe": {"status": "pending"}}, "configured session has no complete restart evidence"),
    ])
    def test_probe_status_is_not_acceptance(self, tmp_path, session, expected):
        result = reconcile_restart_probe(str(tmp_path), session, "")
        assert result == (None if expected is None else
                          Verdict("__lifecycle__/restart-persistence", "INDETERMINATE", note=expected))

    @pytest.mark.parametrize("content", [None, "not-json", "[]", "{}"])
    def test_missing_or_malformed_artifact_is_non_pass(self, tmp_path, content):
        state = tmp_path / ".fettle"
        state.mkdir()
        if content is not None:
            (state / "uat-restart-probe.json").write_text(content)
        result = reconcile_restart_probe(str(tmp_path), {"restart_probe": {"status": "captured"}}, "RESTART_PROBE:\n")
        note = ("restart evidence artifact is missing or malformed" if content in (None, "not-json")
                else "restart evidence drifted from the retained artifact")
        assert result == Verdict("__lifecycle__/restart-persistence", "INDETERMINATE", note=note)

    @pytest.mark.parametrize("outcome,verdict,note", [
        ("persisted", "INDETERMINATE", "restart claim lacks independent process and state evidence"),
        (" LOST ", "CONTRADICTED", "retained note"),
        ("could-not-attempt", "BLOCKED", "retained note"),
        ("unknown", "INDETERMINATE", "unrecognized restart outcome 'unknown'"),
    ])
    @pytest.mark.parametrize("fault", [None, "before", "after", "digest", "block", "transcript"])
    def test_restart_claim_requires_exact_retained_evidence(self, tmp_path, outcome, verdict, note, fault):
        block = {"before": "before state", "after": "after state", "outcome": outcome.strip(), "notes": "retained note"}
        if fault in {"before", "after"}:
            block[fault] = ""
        transcript = "RESTART_PROBE:\n" + "\n".join(f"{key.upper()}: {value}" for key, value in block.items())
        digest = "sha256:" + hashlib.sha256(json.dumps(block, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        artifact = {"block": dict(block), "block_sha": digest}
        if fault == "digest":
            artifact["block_sha"] = "wrong"
        if fault == "block":
            artifact["block"]["notes"] = "different"
        if fault == "transcript":
            transcript = "no restart probe"
        state = tmp_path / ".fettle"
        state.mkdir()
        (state / "uat-restart-probe.json").write_text(json.dumps(artifact))
        result = reconcile_restart_probe(str(tmp_path), {"restart_probe": {"status": "captured"}}, transcript)
        if fault in {"digest", "block", "transcript"}:
            expected = Verdict("__lifecycle__/restart-persistence", "INDETERMINATE",
                               note="restart evidence drifted from the retained artifact")
        elif fault in {"before", "after"}:
            expected = Verdict("__lifecycle__/restart-persistence", "INDETERMINATE", note="restart evidence is incomplete")
        else:
            expected = Verdict("__lifecycle__/restart-persistence", verdict, "after state", note)
        assert result == expected


class TestReconcile:
    def test_verdict_defaults_are_empty_text(self):
        verdict = Verdict("greeter/S1", "UNOBSERVED")
        assert verdict.scenario_id == "greeter/S1"
        assert verdict.verdict == "UNOBSERVED"
        assert verdict.observed == ""
        assert verdict.note == ""

    @pytest.mark.parametrize("require_artifacts", [True, False])
    @pytest.mark.parametrize("fault", ["none", "missing", "container", "block", "digest", "identity", "steps", "drift"])
    def test_retained_claims_preserve_exact_non_authoritative_diagnostic(self, require_artifacts, fault):
        block = {"observed": "actual command output", "outcome": "MaTcHeS", "notes": "claimed note"}
        retained = {**block, "observed": "different retained observation"} if fault == "drift" else dict(block)
        artifact = {"scenario_id": "greeter/S1", "steps": SCENARIOS[0]["steps"], "block": retained,
                    "block_sha": hashlib.sha256(json.dumps(retained, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
        if fault == "container":
            artifact = []
        elif fault == "block":
            artifact["block"] = []
        elif fault == "digest":
            artifact["block_sha"] = "wrong digest"
        elif fault == "identity":
            artifact["scenario_id"] = "other/S1"
        elif fault == "steps":
            artifact["steps"] = ["Then changed behavior"]
        artifacts = {} if fault == "missing" else {"greeter/S1": artifact}
        text = "SCENARIO: greeter/S1\nOBSERVED: actual command output\nOUTCOME: MaTcHeS\nNOTES: claimed note\n"
        if fault == "missing" and require_artifacts:
            note = "claimed match but no observation artifact was retained"
        elif fault in {"container", "block", "digest", "identity", "steps"}:
            note = "artifact content or scenario contract is invalid"
        elif fault == "drift":
            note = "transcript drifted from the captured observation artifact"
        else:
            note = ("agent claim lacks independent execution evidence; "
                    "retain observations and rerun with a qualified capture driver")
        assert reconcile(SCENARIOS[:1], text, artifacts, require_artifacts) == [
            Verdict("greeter/S1", "INDETERMINATE", "actual command output", note)]

    @pytest.mark.parametrize("observed,steps,expected", [
        ("", [], True), ("  \"\"  ", [], True),
        (" HELLO ", ["Then hello"], True),
        ("\"hello\"", ["THEN \"Hello\""], True),
        ("then hello", ["Then hello"], True),
        ("hello", ["Given hello", "When hello"], False),
        ("XhelloX", ["Then hello"], False),
        ("hello", ["Then XhelloX"], False),
        ("actual output", ["Then hello"], False),
        ("second", ["Then first", "Then second"], True),
        ("output", [], False),
    ])
    def test_auto_answer_heuristic_preserves_observed_content(self, observed, steps, expected):
        assert _looks_parroted(observed, {"steps": steps}) is expected

    def test_auto_answer_without_expected_steps_is_not_parroting(self):
        assert _looks_parroted("actual output", {}) is False

    def test_claimed_command_output_is_not_independent_evidence(self):
        text = ("SCENARIO: greeter/S1\nOBSERVED: $ greet Ada -> Hello, Ada!\n"
                "OUTCOME: matches\n"
                "SCENARIO: greeter/S2\nOBSERVED: usage: greet NAME\nOUTCOME: matches\n")
        verdicts = reconcile(SCENARIOS, text)
        note = ("agent claim lacks independent execution evidence; "
            "retain observations and rerun with a qualified capture driver")
        assert verdicts == [Verdict("greeter/S1", "INDETERMINATE", "$ greet Ada -> Hello, Ada!", note),
                    Verdict("greeter/S2", "INDETERMINATE", "usage: greet NAME", note)]

    def test_unobserved_is_first_class(self):
        text = ("SCENARIO: greeter/S1\nOBSERVED: $ greet Ada -> Hello, Ada!\n"
                "OUTCOME: matches\n")
        verdicts = reconcile(SCENARIOS, text)
        assert verdicts[1] == Verdict("greeter/S2", "UNOBSERVED", note="agent never reported on this scenario")

    def test_contradicted_and_blocked(self):
        text = ("SCENARIO: greeter/S1\nOBSERVED: Hola, Ada\nOUTCOME: differs\n"
            "NOTES: wrong greeting\n"
                "SCENARIO: greeter/S2\nOBSERVED: binary missing\n"
            "OUTCOME: could-not-attempt\nNOTES: install application\n")
        verdicts = reconcile(SCENARIOS, text)
        assert verdicts == [Verdict("greeter/S1", "CONTRADICTED", "Hola, Ada", "wrong greeting"),
                    Verdict("greeter/S2", "BLOCKED", "binary missing", "install application")]

    def test_parroted_match_downgrades_to_indeterminate(self):
        text = ("SCENARIO: greeter/S1\n"
                'OBSERVED: the output contains "Hello, Ada"\n'
                "OUTCOME: matches\n")
        v = reconcile(SCENARIOS[:1], text)[0]
        assert v == Verdict("greeter/S1", "INDETERMINATE", 'the output contains "Hello, Ada"',
                    "claimed match without independent evidence (auto-answer suspected)")

    def test_empty_evidence_downgrades(self):
        text = "SCENARIO: greeter/S1\nOBSERVED:\nOUTCOME: matches\n"
        assert reconcile(SCENARIOS[:1], text)[0].verdict == "INDETERMINATE"

    def test_unknown_outcome_indeterminate(self):
        text = ("SCENARIO: greeter/S1\nOBSERVED: stuff\nOUTCOME: maybe\n"
                "SCENARIO: greeter/S2\nOBSERVED: no binary\nOUTCOME: could-not-attempt\n")
        assert reconcile(SCENARIOS, text) == [
            Verdict("greeter/S1", "INDETERMINATE", "stuff", "unrecognized outcome 'maybe'"),
            Verdict("greeter/S2", "BLOCKED", "no binary"),
        ]


class TestIndependentJudgment:
    class Runner:
        def __init__(self, transcript: str, error: str = "", exit_code: int = 0):
            self.transcript = transcript
            self.error = error
            self.exit_code = exit_code
            self.calls = []

        def run(self, prompt, cwd, timeout_s=600):
            self.calls.append({"prompt": prompt, "cwd": cwd, "timeout_s": timeout_s})
            return RunnerResult(self.transcript, self.exit_code, 0.1, self.error)

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

    @pytest.mark.parametrize("severity", ["low", "medium", "high", "critical"])
    def test_judgment_normalizes_findings_and_binds_prompt(self, tmp_path, severity):
        artifacts = {
            "greeter/S2": {"block_sha": "sha-second", "block": {"observed": "second"}},
            "greeter/S1": {"block_sha": "sha-first", "block": {"observed": "first"}},
        }
        runner = self.Runner(json.dumps({"findings": [
            {"scenario_id": "greeter/S2", "severity": severity.upper(), "summary": "  retained finding  ", "artifact_sha": "sha-second"},
            {"scenario_id": "greeter/S1", "severity": "low", "summary": "second finding", "artifact_sha": "sha-first"},
        ]}))
        result = evaluate_judgment(str(tmp_path), "original transcript", artifacts, runner, timeout_s=17)
        assert result == {"status": "completed", "error": "", "findings": [
            {"scenario_id": "greeter/S2", "severity": severity, "summary": "retained finding",
             "artifact": {"scenario_id": "greeter/S2", "block_sha": "sha-second"}, "resolution": "operator-attestation-required"},
            {"scenario_id": "greeter/S1", "severity": "low", "summary": "second finding",
             "artifact": {"scenario_id": "greeter/S1", "block_sha": "sha-first"}, "resolution": "operator-attestation-required"},
        ]}
        references = [{"scenario_id": "greeter/S1", "block_sha": "sha-first", "block": {"observed": "first"}},
                      {"scenario_id": "greeter/S2", "block_sha": "sha-second", "block": {"observed": "second"}}]
        prompt = (
            "You are an independent reviewer of a completed UAT session. Hunt for "
            "passes for the wrong reason and missed confusion or friction. Do not "
            "change primary verdicts. Return only JSON as "
            '{"findings":[{"scenario_id":"...","severity":"low|medium|high|critical",'
            '"summary":"...","artifact_sha":"..."}]}. Every finding must cite '
            "one exact artifact SHA from the supplied references.\n\n"
            f"ARTIFACTS:\n{json.dumps(references, sort_keys=True)}\n\nTRANSCRIPT:\noriginal transcript"
        )
        assert runner.calls == [{"prompt": prompt, "cwd": str(tmp_path), "timeout_s": 17}]

    @pytest.mark.parametrize("payload", [{}, [], None, {"findings": None}, {"findings": {}}, {"findings": "text"}])
    def test_malformed_findings_container_is_indeterminate(self, tmp_path, payload):
        result = evaluate_judgment(str(tmp_path), "transcript", {}, self.Runner(json.dumps(payload)))
        assert result["status"] == "indeterminate"
        assert result["findings"] == []
        assert result["error"].startswith("malformed evaluator output: ")
        if isinstance(payload, dict) and "findings" in payload:
            assert result["error"] == "malformed evaluator output: findings must be a list"

    @pytest.mark.parametrize("field,value", [
        ("scenario_id", None), ("scenario_id", "unknown"), ("severity", None), ("severity", "invalid"),
        ("summary", None), ("summary", "  "), ("artifact_sha", None), ("artifact_sha", "wrong"),
    ])
    def test_invalid_later_finding_discards_partial_results(self, tmp_path, field, value):
        valid = {"scenario_id": "greeter/S1", "severity": "high", "summary": "finding", "artifact_sha": "sha-first"}
        invalid = {**valid, field: value}
        runner = self.Runner(json.dumps({"findings": [valid, invalid]}))
        result = evaluate_judgment(str(tmp_path), "transcript", {"greeter/S1": {"block_sha": "sha-first"}}, runner)
        assert result == {"status": "indeterminate", "findings": [],
                          "error": "evaluator finding lacks valid severity or exact artifact reference"}

    @pytest.mark.parametrize("finding", [None, [], "finding", 7])
    def test_non_object_finding_is_non_pass(self, tmp_path, finding):
        result = evaluate_judgment(str(tmp_path), "transcript", {}, self.Runner(json.dumps({"findings": [finding]})))
        assert result == {"status": "indeterminate", "findings": [], "error": "evaluator finding must be an object"}

    @pytest.mark.parametrize("error,exit_code", [("runner unavailable", 0), ("runner unavailable", 7), ("", 7)])
    def test_runner_failure_has_exact_non_pass_diagnostic(self, tmp_path, error, exit_code):
        result = evaluate_judgment(str(tmp_path), "transcript", {}, self.Runner('{"findings":[]}', error, exit_code))
        assert result == {"status": "tool_error", "findings": [],
                          "error": error or "evaluator exited 7; rerun UAT judgment"}

    def test_empty_findings_preserve_default_artifact_references(self, tmp_path):
        runner = self.Runner('{"findings":[]}')
        assert evaluate_judgment(str(tmp_path), "transcript", {"greeter/S1": {}}, runner) == {
            "status": "completed", "findings": [], "error": ""}
        assert '{"block": {}, "block_sha": "", "scenario_id": "greeter/S1"}' in runner.calls[0]["prompt"]
        assert runner.calls[0]["timeout_s"] == 600

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

    def test_failed_evaluator_cannot_confirm_empty_findings(self, tmp_path):
        result = evaluate_judgment(
            str(tmp_path), "t", {}, self.Runner('{"findings":[]}', exit_code=7))
        assert result["status"] == "tool_error"
        assert result["findings"] == []
        assert "7" in result["error"]

    def test_judgment_finding_makes_report_incomplete_without_changing_verdict(self,
                                                                              tmp_path):
        judgment = {"status": "completed", "findings": [{"severity": "high"}]}
        path, err = write_report(
            str(tmp_path), {"session_id": "uat-x", "surface": "cli"},
            [Verdict("greeter/S1", "CONFIRMED")], judgment=judgment,
        )
        assert err == ""
        report = json.loads(Path(path).read_text())
        assert report["verdicts"][0]["verdict"] == "INDETERMINATE"
        assert report["completion"]["complete"] is False


class TestArtifactsAndSummary:
    def test_atomic_report_write_flushes_before_replace(self, tmp_path):
        import os
        from fettle.uat.reconcile import _write_bytes_atomic

        target = tmp_path / "nested" / "evidence" / "report.json"
        content = b"new evidence\x00\xff"
        synchronized = []
        original_sync, original_replace = os.fsync, os.replace

        def synchronize(descriptor):
            assert os.pread(descriptor, len(content), 0) == content
            synchronized.append(descriptor)
            original_sync(descriptor)

        def replace(source, destination):
            assert synchronized
            assert Path(source).parent == target.parent
            assert Path(source).suffix == ".tmp"
            assert Path(source).read_bytes() == content
            assert destination == target
            original_replace(source, destination)

        with patch("fettle.uat.reconcile.os.fsync", side_effect=synchronize) as sync, \
                patch("fettle.uat.reconcile.os.replace", side_effect=replace) as swap, \
                patch("fettle.uat.reconcile.os.unlink", wraps=os.unlink) as unlink:
            _write_bytes_atomic(target, content)
        assert sync.call_count == 1
        assert swap.call_count == 1
        unlink.assert_not_called()
        assert target.read_bytes() == content
        assert list(target.parent.iterdir()) == [target]
        _write_bytes_atomic(target, b"replacement")
        assert target.read_bytes() == b"replacement"

    @pytest.mark.parametrize("boundary", ["fsync", "replace"])
    def test_atomic_report_failure_preserves_old_file_and_removes_temporary(self, tmp_path, boundary):
        from fettle.uat.reconcile import _write_bytes_atomic

        target = tmp_path / "report.json"
        target.write_bytes(b"retained evidence")
        with patch(f"fettle.uat.reconcile.os.{boundary}", side_effect=OSError("disk unavailable")):
            with pytest.raises(OSError, match="^disk unavailable$"):
                _write_bytes_atomic(target, b"new evidence")
        assert target.read_bytes() == b"retained evidence"
        assert list(tmp_path.iterdir()) == [target]

    def test_report_digest_is_canonical_unicode_json(self):
        from fettle.uat.reconcile import _digest

        expected = "sha256:" + hashlib.sha256('{"a":1,"z":"caf\u00e9"}'.encode()).hexdigest()
        assert _digest({"z": "caf\u00e9", "a": 1}) == expected
        assert _digest({"a": 1, "z": "caf\u00e9"}) == expected

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_report_digest_rejects_non_finite_values(self, value):
        from fettle.uat.reconcile import _digest

        with pytest.raises(ValueError, match="Out of range float values are not JSON compliant"):
            _digest({"value": value})

    def test_report_creates_nested_directory_and_preserves_empty_metadata(self, tmp_path):
        target = tmp_path / "new" / "worktree"
        with patch("fettle.trace.build_evidence", return_value={"evidence_id": "evidence-1"}) as build:
            path, error = write_report(str(target), {"canonical_evidence": False}, [])
        assert error == ""
        assert path == str(target / ".fettle" / "uat-report.json")
        report = json.loads(Path(path).read_text())
        assert report["session_id"] == ""
        assert report["surface"] == ""
        build.assert_called_once_with("uat_report", exit_code=1, scope="")

    def test_format_verdicts_exact_counts_marks_and_problem_details(self):
        verdicts = [Verdict("feature/S1", "CONFIRMED", "hidden observation", "hidden note"),
                    Verdict("feature/S2", "CONTRADICTED", "first line\nsecond line", "wrong output"),
                    Verdict("feature/S3", "BLOCKED", "", "permission denied"),
                    Verdict("feature/S4", "UNOBSERVED"),
                    Verdict("feature/S5", "INDETERMINATE", "unverified"),
                    Verdict("feature/S6", "CONFIRMED")]
        assert format_verdicts(verdicts) == (
            "UAT verdicts \u2014 CONFIRMED: 2  CONTRADICTED: 1  BLOCKED: 1  UNOBSERVED: 1  INDETERMINATE: 1\n"
            "  \u2713 feature/S1: CONFIRMED\n"
            "  \u2717 feature/S2: CONTRADICTED\n"
            "      observed: first line\n"
            "      note: wrong output\n"
            "  \u25cb feature/S3: BLOCKED\n"
            "      note: permission denied\n"
            "  ? feature/S4: UNOBSERVED\n"
            "  ~ feature/S5: INDETERMINATE\n"
            "      observed: unverified\n"
            "  \u2713 feature/S6: CONFIRMED"
        )
        assert format_verdicts([]) == "UAT verdicts \u2014 no scenarios"

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
        from fettle.uat.reconcile import _write_bytes_atomic

        def fail_sidecar(path, content):
            if path.name == "uat-report.evidence.json":
                raise OSError("full")
            _write_bytes_atomic(path, content)

        with patch("fettle.uat.reconcile._write_bytes_atomic", side_effect=fail_sidecar):
            path, err = write_report(
                str(tmp_path), {"session_id": "uat-x", "surface": "cli"}, verdicts,
            )
        assert err == "canonical UAT report evidence unavailable: full"
        assert json.loads(Path(path).read_text())["completion"]["complete"] is False

    def test_canonical_validation_preserves_unresolved_evaluator_as_unknown(self, tmp_path):
        verdicts = [Verdict("greeter/S1", "CONFIRMED", observed="ran")]
        path, err = write_report(str(tmp_path), {
            "session_id": "uat-x", "surface": "cli",
        }, verdicts, judgment={"status": "tool_error", "findings": [], "error": "timeout"})
        assert err == ""
        report = json.loads(Path(path).read_text())

        result = validate_canonical_evidence(str(tmp_path), report)

        assert result.validity.value == "valid"
        assert result.result_state.value == "unknown"

    def test_canonical_validation_detects_report_projection_tampering(self, tmp_path):
        verdicts = [Verdict("greeter/S1", "CONFIRMED", observed="ran")]
        path, err = write_report(str(tmp_path), {
            "session_id": "uat-x", "surface": "cli",
        }, verdicts)
        assert err == ""
        report = json.loads(Path(path).read_text())
        report["completion"]["required_total"] = 2

        result = validate_canonical_evidence(str(tmp_path), report)

        assert result.validity.value == "tampered"
        assert result.result_state.value == "unknown"

    def test_format_verdicts_expands_problems(self):
        text = ("SCENARIO: greeter/S1\nOBSERVED: Hola\nOUTCOME: differs\n"
                "NOTES: wrong language\n")
        out = format_verdicts(reconcile(SCENARIOS, text))
        assert "CONTRADICTED: 1" in out and "UNOBSERVED: 1" in out
        assert "observed: Hola" in out and "note: wrong language" in out


def test_completion_counts_product_scenarios_not_lifecycle_checks():
    from fettle.uat.reconcile import _completion

    verdicts = [{"scenario_id": "greeter/S1", "verdict": "CONFIRMED"},
                {"scenario_id": "__lifecycle__/restart", "verdict": "BLOCKED"}]
    completion = _completion(verdicts, {"scenario_ids": ["greeter/S1"]},
                             {"status": "NOT_APPLICABLE"}, "")
    assert completion == {"complete": False, "required_total": 1, "required_confirmed": 1}


@pytest.mark.parametrize("identifiers", [[], ["greeter/S1", "greeter/S1"], ["other/S1"]])
def test_completion_rejects_inexact_product_inventory(identifiers):
    from fettle.uat.reconcile import _completion

    verdicts = [{"scenario_id": identifier, "verdict": "CONFIRMED"} for identifier in identifiers]
    assert not _completion(verdicts, {"scenario_ids": ["greeter/S1"]},
                           {"status": "NOT_APPLICABLE"}, "")["complete"]


@pytest.mark.parametrize("required,total", [
    (None, 2), ([], 2), ("greeter/S1", 2), ({"greeter/S1": True}, 2),
    ([None], 2), ([""], 2), ([7], 2), (["greeter/S1", "greeter/S1"], 2),
    (["greeter/S1"], 1), (["greeter/S1", "other/S1"], 2),
])
def test_completion_invalid_or_inexact_required_inventory(required, total):
    from fettle.uat.reconcile import _completion

    verdicts = [{"scenario_id": "greeter/S1", "verdict": "CONFIRMED"},
                {"scenario_id": "greeter/S2", "verdict": "BLOCKED"}]
    assert _completion(verdicts, {"scenario_ids": required}, {"status": "NOT_APPLICABLE"}, "") == {
        "complete": False, "required_total": total, "required_confirmed": 1}


@pytest.mark.parametrize("judgment,judgment_pass", [
    ({"status": "NOT_APPLICABLE"}, True), ({"status": "completed", "findings": []}, True),
    ({"status": "completed"}, False), ({"status": "completed", "findings": [{}]}, False),
    ({"status": "completed", "findings": None}, False), ({"status": "tool_error", "findings": []}, False),
    ({}, False),
])
@pytest.mark.parametrize("session_error", ["", "runner failed"])
def test_completion_requires_all_criteria_not_only_product_verdicts(judgment, judgment_pass, session_error):
    from fettle.uat.reconcile import _completion

    verdicts = [{"scenario_id": "greeter/S2", "verdict": "CONFIRMED"},
                {"scenario_id": "greeter/S1", "verdict": "CONFIRMED"},
                {"scenario_id": "__lifecycle__/restart", "verdict": "CONFIRMED"}]
    assert _completion(verdicts, {"scenario_ids": ["greeter/S1", "greeter/S2"]}, judgment, session_error) == {
        "complete": judgment_pass and not session_error, "required_total": 2, "required_confirmed": 2}


@pytest.mark.parametrize("verdicts,judgment", [
    (None, {}), ({}, {}), ([None], {}), ([{}], {}),
    ([{"scenario_id": 7, "verdict": "CONFIRMED"}], {}),
    ([{"scenario_id": "greeter/S1", "verdict": "unknown"}], {}),
    ([], None), ([], []),
])
def test_completion_malformed_inputs_raise_visible_error(verdicts, judgment):
    from fettle.uat.reconcile import _completion

    with pytest.raises(ValueError, match="^malformed UAT verdicts or judgment$"):
        _completion(verdicts, {"scenario_ids": ["greeter/S1"]}, judgment, "")


class TestReconcileSession:
    @pytest.fixture(params=["cli", "web"])
    def retained_session(self, tmp_path, monkeypatch, request):
        from fettle.uat.session import _write_session_evidence

        state = tmp_path / ".fettle"
        state.mkdir()
        transcript = state / "transcript.txt"
        transcript.write_text("retained observation\n")
        config = {"enabled": True}
        contract_digest = "sha256:" + hashlib.sha256(json.dumps(
            SCENARIOS, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        policy_digest = "sha256:" + hashlib.sha256(json.dumps(
            config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        session = {"session_id": "session-1", "status": "completed", "surface": request.param,
                   "scenario_ids": ["greeter/S1", "greeter/S2"], "transcript": str(transcript),
                   "contract_digest": contract_digest, "policy_digest": policy_digest}
        if request.param == "web":
            session["web_capture"] = {"status": "completed"}
        session["canonical_evidence_reference"] = _write_session_evidence(str(tmp_path), session, config)
        monkeypatch.setattr("fettle.uat.session.collect_scenarios", lambda root: SCENARIOS)
        return session

    def test_retained_session_identity_validates(self, tmp_path, retained_session):
        from fettle.uat.reconcile import _session_error

        assert _session_error(str(tmp_path), retained_session) == ""

    @pytest.fixture
    def retained_report(self, tmp_path, retained_session):
        (tmp_path / ".fettle" / "uat-session.json").write_text(json.dumps(retained_session))
        path, error = write_report(str(tmp_path), retained_session, reconcile(SCENARIOS, ""))
        assert error == ""
        return json.loads(Path(path).read_text())

    def test_canonical_report_validates_exact_identity(self, tmp_path, retained_session, retained_report):
        from datetime import datetime
        from uuid import UUID
        from fettle import __version__

        def digest(value):
            return "sha256:" + hashlib.sha256(json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

        artifact = parse_artifact((tmp_path / ".fettle" / "uat-report.evidence.json").read_bytes())
        result = validate_canonical_evidence(str(tmp_path), retained_report)
        assert result.validity.value == "valid"
        assert result.result_state.value == "violation"
        assert result.recovery_action == ""
        assert artifact.producer == {"id": "fettle.uat.report", "version": __version__,
                                     "implementation_digest": "sha256:" + hashlib.sha256(
                                         (Path(__file__).parents[1] / "fettle" / "uat" / "reconcile.py").read_bytes()).hexdigest()}
        assert artifact.source["snapshot_digest"] == digest({
            "session_id": "session-1", "session_evidence": retained_session["canonical_evidence_reference"]})
        assert artifact.policy_digest == digest({"canonical_evidence": True})
        assert artifact.scope_digest == digest({"surface": retained_session["surface"], "scenario_ids": retained_session["scenario_ids"]})
        assert artifact.trust_class == "derived"
        assert artifact.completeness == "complete"
        assert artifact.observation_id.startswith("uat-report-")
        assert UUID(artifact.observation_id.removeprefix("uat-report-")).version == 4
        assert artifact.observed_at.endswith("Z")
        assert datetime.fromisoformat(artifact.observed_at).utcoffset().total_seconds() == 0
        assert artifact.payload["redacted_lines"] == 0

    @pytest.mark.parametrize("field,value,validity", [
        ("judgment", [], "malformed"), ("completion", [], "malformed"),
        ("verdicts", {}, "malformed"), ("verdicts", [None], "malformed"),
        ("verdicts", [{"scenario_id": 17, "verdict": "BLOCKED"}], "malformed"),
        ("verdicts", [{"scenario_id": "greeter/S1", "verdict": "invalid"}], "malformed"),
        ("verdicts", [{"scenario_id": "greeter/S1", "verdict": "CONFIRMED"}], "tampered"),
        ("session_id", "other", "tampered"), ("surface", "other", "tampered"),
    ])
    def test_report_projection_cannot_override_canonical_evidence(self, tmp_path, retained_report, field, value, validity):
        retained_report[field] = value
        result = validate_canonical_evidence(str(tmp_path), retained_report)
        assert result.validity.value == validity
        assert result.result_state.value == "unknown"
        assert result.recovery_action == "fettle uat report"

    @pytest.mark.parametrize("field,value,validity", [
        ("verdicts", None, "malformed"), ("completion", [], "malformed"), ("report", [], "malformed"),
        ("verdicts", [], "tampered"), ("completion", {}, "tampered"),
        ("report", {"path": "uat-report.json", "digest": "sha256:" + "0" * 64}, "tampered"),
        ("session_id", "other", "tampered"), ("surface", "other", "tampered"),
        ("result_state", "pass", "tampered"),
    ])
    def test_regenerated_report_sidecar_cannot_hide_projection_drift(self, tmp_path, retained_report, field, value, validity):
        from fettle.evidence import EvidenceArtifact

        path = tmp_path / ".fettle" / "uat-report.evidence.json"
        arguments = parse_artifact(path.read_bytes()).to_dict()
        del arguments["schema_version"], arguments["artifact_digest"]
        if field == "result_state":
            arguments[field] = value
        else:
            arguments["payload"][field] = value
        path.write_bytes(EvidenceArtifact.create(**arguments).to_bytes())
        result = validate_canonical_evidence(str(tmp_path), retained_report)
        assert result.validity.value == validity
        assert result.result_state.value == "unknown"
        assert result.recovery_action == "fettle uat report"

    @pytest.mark.parametrize("fault,validity", [("missing", "missing"), ("malformed", "malformed"), ("report_missing", "malformed")])
    def test_missing_report_evidence_is_not_pass(self, tmp_path, retained_report, fault, validity):
        path = tmp_path / ".fettle" / ("uat-report.json" if fault == "report_missing" else "uat-report.evidence.json")
        if fault == "malformed":
            path.write_text("not json")
        else:
            path.unlink()
        result = validate_canonical_evidence(str(tmp_path), retained_report)
        assert result.validity.value == validity
        assert result.result_state.value == "unknown"
        assert result.recovery_action == "fettle uat report"

    @pytest.mark.parametrize("status,state", [("completed", "violation"), ("NOT_APPLICABLE", "violation"),
                                              ("tool_error", "unknown"), ("indeterminate", "unknown")])
    def test_report_judgment_controls_canonical_result(self, tmp_path, retained_session, status, state):
        (tmp_path / ".fettle" / "uat-session.json").write_text(json.dumps(retained_session))
        path, error = write_report(str(tmp_path), retained_session, reconcile(SCENARIOS, ""),
                                   judgment={"status": status, "findings": []})
        assert error == ""
        result = validate_canonical_evidence(str(tmp_path), json.loads(Path(path).read_text()))
        assert result.validity.value == "valid"
        assert result.result_state.value == state

    @pytest.mark.parametrize("fault", ["none", "capture_error", "verdict_drift", "session_error", "uncaptured"])
    def test_canonical_capture_pass_requires_consistent_independent_evidence(self, tmp_path, retained_session, fault):
        session = {**retained_session, "capture_mode": "contract"}
        checkpoint = tmp_path / ".fettle" / "uat-session.json"
        checkpoint.write_text(json.dumps(session))
        captured = [{"scenario_id": scenario["id"], "verdict": "CONFIRMED", "observed": "captured output", "note": "oracle"}
                    for scenario in SCENARIOS]
        with patch("fettle.uat.controller.validate_capture", return_value=(captured, "")) as validate:
            path, error = write_report(str(tmp_path), session, [])
            assert error == ""
            report = json.loads(Path(path).read_text())
            assert report["completion"] == {"complete": True, "required_total": 2, "required_confirmed": 2}
            if fault == "capture_error":
                validate.return_value = (captured, "invalid capture")
            elif fault == "verdict_drift":
                validate.return_value = ([{**item, "observed": "different output"} for item in captured], "")
            elif fault == "session_error":
                session["error"] = "runner failed"
                checkpoint.write_text(json.dumps(session))
            elif fault == "uncaptured":
                del session["capture_mode"]
                checkpoint.write_text(json.dumps(session))
            result = validate_canonical_evidence(str(tmp_path), report)
        assert result.validity.value == ("valid" if fault == "none" else "tampered")
        assert result.result_state.value == ("pass" if fault == "none" else "unknown")
        assert result.recovery_action == ("" if fault == "none" else "fettle uat report")

    @pytest.mark.parametrize("fault", ["none", "root", "capture", "write", "session"])
    def test_capture_reconciliation_preserves_acceptance_boundary(self, tmp_path, retained_session, fault):
        session = {**retained_session, "capture_mode": "contract"}
        if fault == "session":
            session["error"] = "runner failed"
        (tmp_path / ".fettle" / "uat-session.json").write_text(json.dumps(session))
        captured = [{"scenario_id": scenario["id"], "verdict": "CONFIRMED", "observed": "captured", "note": "oracle"}
                    for scenario in SCENARIOS]
        root = str(tmp_path / "other") if fault == "root" else str(tmp_path / ".")
        capture_error = "capture rejected" if fault == "capture" else ""
        write_error = "report unavailable" if fault == "write" else ""
        with patch("fettle.uat.controller.validate_capture", return_value=(captured, capture_error)) as validate, \
                patch("fettle.uat.reconcile.write_report", return_value=("report.json", write_error)) as write:
            verdicts, checkpoint, error = reconcile_session(root, str(tmp_path))
        if fault in {"root", "capture"}:
            assert verdicts == []
            assert checkpoint == session
            assert error == ("controller report must be inspected from its original product root" if fault == "root" else capture_error)
            validate.assert_called_once_with(str(tmp_path), session)
            write.assert_not_called()
        else:
            judgment = {"status": "NOT_APPLICABLE", "findings": []}
            assert verdicts == [Verdict(**item) for item in captured]
            assert error == write_error
            assert checkpoint == {**session, "judgment": judgment, "acceptance_complete": fault == "none",
                                  "session_error": "session did not complete successfully; rerun UAT" if fault == "session" else ""}
            write.assert_called_once_with(str(tmp_path), checkpoint, verdicts, judgment=judgment)
            assert validate.call_count == (1 if fault == "session" else 2)

    @pytest.mark.parametrize("judgment,expected_pass", [
        ({"status": "NOT_APPLICABLE", "findings": []}, True),
        ({"status": "completed", "findings": []}, True),
        ({"status": "completed", "findings": [{"severity": "high"}]}, False),
        ({"status": "tool_error", "findings": []}, False),
    ])
    @pytest.mark.parametrize("timeout", [None, "17"])
    def test_session_forwards_evaluator_and_preserves_judgment(
        self, tmp_path, retained_session, judgment, expected_pass, timeout,
    ):
        session = {**retained_session, "evaluator_runner": "reviewer", "evaluator_timeout_s": timeout}
        (tmp_path / ".fettle" / "uat-session.json").write_text(json.dumps(session))
        evaluator = object()
        with patch("fettle.runners.get_uat_runner", return_value=evaluator) as runner, \
                patch("fettle.uat.reconcile.evaluate_judgment", return_value=judgment) as evaluate:
            verdicts, checkpoint, error = reconcile_session(str(tmp_path), str(tmp_path))
        assert error == ""
        assert [verdict.scenario_id for verdict in verdicts] == session["scenario_ids"]
        assert checkpoint["judgment"] == judgment
        assert checkpoint["judgment_pass"] is expected_pass
        assert checkpoint["acceptance_complete"] is False
        assert checkpoint["session_error"] == ""
        runner.assert_called_once_with("reviewer")
        evaluate.assert_called_once_with(str(tmp_path), "retained observation\n", {}, evaluator,
                                         timeout_s=600 if timeout is None else 17)
        report = json.loads((tmp_path / ".fettle" / "uat-report.json").read_text())
        assert report["judgment"] == judgment

    @pytest.mark.parametrize("failure", [TypeError("bad evaluator"), ValueError("unknown evaluator")])
    def test_session_evaluator_failure_is_retained(self, tmp_path, retained_session, failure):
        session = {**retained_session, "evaluator_runner": "reviewer"}
        (tmp_path / ".fettle" / "uat-session.json").write_text(json.dumps(session))
        with patch("fettle.runners.get_uat_runner", side_effect=failure):
            _, checkpoint, error = reconcile_session(str(tmp_path), str(tmp_path))
        assert error == ""
        assert checkpoint["judgment"] == {"status": "tool_error", "findings": [], "error": str(failure)}
        assert checkpoint["judgment_pass"] is False
        assert checkpoint["acceptance_complete"] is False

    @pytest.mark.parametrize("capture_error,canonical_error", [("", False), ("invalid capture", False), ("", True)])
    def test_report_uses_validated_capture_and_downgrades_persistence_failure(
        self, tmp_path, retained_session, capture_error, canonical_error,
    ):
        session = {**retained_session, "capture_mode": "contract", "canonical_evidence": canonical_error}
        captured = [{"scenario_id": scenario["id"], "verdict": "CONFIRMED", "observed": "captured output", "note": "capture oracle"}
                    for scenario in SCENARIOS]
        with patch("fettle.uat.controller.validate_capture", return_value=(captured, capture_error)) as validate, \
                patch("fettle.trace.build_evidence", return_value={"evidence_id": "evidence-1"}) as build, \
                patch("fettle.uat.reconcile._write_report_evidence", side_effect=OSError("disk full")) as canonical:
            path, error = write_report(str(tmp_path), session, [Verdict("greeter/S1", "CONFIRMED", "caller claim")])
        assert validate.call_count == 2
        for call in validate.call_args_list:
            assert call.args == (str(tmp_path), session)
            assert call.kwargs == {}
        report = json.loads(Path(path).read_text())
        assert report["completion"]["complete"] is (not capture_error and not canonical_error)
        assert report["completion"]["required_confirmed"] == (0 if capture_error else 2)
        build.assert_called_once_with("uat_report", exit_code=1 if capture_error else 0, scope=session["surface"])
        if capture_error:
            assert report["verdicts"][0]["verdict"] == "INDETERMINATE"
            assert report["session_error"] == "invalid capture"
        else:
            assert report["verdicts"] == captured
        if canonical_error:
            assert error == "canonical UAT report evidence unavailable: disk full"
            assert report["session_error"] == error
            canonical.assert_called_once()
        else:
            assert error == ""
            canonical.assert_not_called()
        assert Path(path).read_text() == json.dumps(report, indent=2) + "\n"

    @pytest.mark.parametrize("canonical", [True, False])
    def test_report_preserves_exact_projection_and_untrusted_confirmation(self, tmp_path, retained_session, canonical):
        session = {**retained_session, "canonical_evidence": canonical}
        candidates = [{"candidate_id": "review-1", "observed": "unexpected behavior"}]
        verdicts = [Verdict("greeter/S1", "CONFIRMED", "claimed observation", "claimed note"),
                    Verdict("greeter/S2", "BLOCKED", "missing binary", "install application"),
                    Verdict("__lifecycle__/restart-persistence", "CONTRADICTED", "state lost", "restart failed")]
        with patch("fettle.trace.build_evidence", return_value={"evidence_id": "evidence-1"}) as build, \
                patch("fettle.uat.reconcile.log_evidenced_decision") as log:
            path, error = write_report(str(tmp_path), session, verdicts, candidates=candidates)
        assert error == ""
        assert path == str(tmp_path / ".fettle" / "uat-report.json")
        expected = {
            "session_id": "session-1", "surface": session["surface"], "evidence_id": "evidence-1",
            "candidate_scenarios": candidates, "judgment": {"status": "NOT_APPLICABLE", "findings": []},
            "session_error": "", "verdicts": [
                {"scenario_id": "greeter/S1", "verdict": "INDETERMINATE", "observed": "claimed observation",
                 "note": "caller-supplied confirmation lacks independent execution evidence"},
                {"scenario_id": "greeter/S2", "verdict": "BLOCKED", "observed": "missing binary", "note": "install application"},
                {"scenario_id": "__lifecycle__/restart-persistence", "verdict": "CONTRADICTED", "observed": "state lost", "note": "restart failed"},
            ],
            "completion": {"complete": False, "required_total": 2, "required_confirmed": 0},
            "lifecycle": {"restart_probe": {"verdict": "CONTRADICTED", "observed": "state lost", "note": "restart failed"}},
        }
        assert Path(path).read_text() == json.dumps(expected, indent=2) + "\n"
        build.assert_called_once_with("uat_report", exit_code=1, scope=session["surface"])
        sidecar = tmp_path / ".fettle" / "uat-report.evidence.json"
        if canonical:
            artifact = parse_artifact(sidecar.read_bytes())
            log.assert_called_once_with(str(tmp_path), hook="uat_report", status=artifact.result_state,
                                        evidence=[{
                                            "artifact_digest": artifact.artifact_digest, "kind": artifact.kind,
                                            "schema_version": artifact.schema_version, "expected": {
                                                "source_snapshot_digest": artifact.source["snapshot_digest"],
                                                "policy_digest": artifact.policy_digest, "scope_digest": artifact.scope_digest,
                                                "producer_id": artifact.producer["id"],
                                            }, "availability": "available",
                                        }], tool="fettle uat report", file=path, session_id="session-1")
        else:
            assert not sidecar.exists()
            log.assert_not_called()

    @pytest.mark.parametrize("failure", [OSError("disk full"), TypeError("invalid projection"), ValueError()])
    def test_canonical_failure_persists_non_pass_and_diagnostic(self, tmp_path, retained_session, failure):
        expected_error = "canonical UAT report evidence unavailable: " + (str(failure) or type(failure).__name__)
        with patch("fettle.uat.reconcile._write_report_evidence", side_effect=failure):
            path, error = write_report(str(tmp_path), retained_session, [Verdict("greeter/S1", "BLOCKED")])
        assert error == expected_error
        report = json.loads(Path(path).read_text())
        assert report["session_error"] == expected_error
        assert report["completion"]["complete"] is False
        assert report["candidate_scenarios"] == []
        assert report["lifecycle"] == {"restart_probe": {"verdict": "NOT_APPLICABLE", "note": "restart probe not configured"}}

    def test_report_write_failure_returns_no_report_path(self, tmp_path, retained_session):
        with patch("fettle.uat.reconcile._write_bytes_atomic", side_effect=OSError("disk full")):
            assert write_report(str(tmp_path), retained_session, []) == ("", "cannot write UAT report: disk full")

    def test_trace_logging_failure_does_not_discard_written_evidence(self, tmp_path, retained_session):
        with patch("fettle.uat.reconcile.log_evidenced_decision", side_effect=RuntimeError("trace unavailable")):
            path, error = write_report(str(tmp_path), retained_session, [Verdict("greeter/S1", "BLOCKED")])
        assert error == ""
        assert Path(path).is_file()
        assert parse_artifact((tmp_path / ".fettle" / "uat-report.evidence.json").read_bytes()).kind == "fettle.uat.report"

    @pytest.mark.parametrize("field,value,message", [
        ("scenario_ids", None, "session evidence has malformed payload; rerun UAT"),
        ("transcript", [], "session evidence has malformed payload; rerun UAT"),
        ("result_state", "unknown", "session evidence is invalid or incomplete; rerun UAT"),
    ])
    def test_valid_artifact_container_cannot_hide_bad_session_payload(
        self, tmp_path, retained_session, field, value, message,
    ):
        from fettle.evidence import EvidenceArtifact
        from fettle.uat.reconcile import _session_error

        path = tmp_path / ".fettle" / "uat-session.evidence.json"
        arguments = parse_artifact(path.read_bytes()).to_dict()
        del arguments["schema_version"], arguments["artifact_digest"]
        if field == "result_state":
            arguments[field] = value
        else:
            arguments["payload"][field] = value
        artifact = EvidenceArtifact.create(**arguments)
        path.write_bytes(artifact.to_bytes())
        retained_session["canonical_evidence_reference"]["artifact_digest"] = artifact.artifact_digest
        assert _session_error(str(tmp_path), retained_session) == message

    @pytest.mark.parametrize("fault,message", [
        ("contract", "session contract is missing or stale; rerun UAT"),
        ("inventory", "session scenario inventory is invalid; rerun UAT"),
        ("escape", "session transcript escapes retained evidence directory"),
        ("transcript", "session evidence conflicts with checkpoint; rerun UAT"),
        ("reference", "session evidence conflicts with checkpoint; rerun UAT"),
        ("session_id", "session evidence conflicts with checkpoint; rerun UAT"),
        ("policy", "session evidence is invalid or incomplete; rerun UAT"),
        ("missing", "session evidence is missing or malformed; rerun UAT"),
        ("malformed", "session evidence is missing or malformed; rerun UAT"),
        ("missing_transcript_key", "session evidence is missing or malformed; rerun UAT"),
    ])
    def test_retained_session_drift_remains_non_pass(self, tmp_path, retained_session, fault, message):
        from fettle.uat.reconcile import _session_error

        session = retained_session
        evidence = tmp_path / ".fettle" / "uat-session.evidence.json"
        if fault == "contract":
            session["contract_digest"] = "sha256:" + "0" * 64
        elif fault == "inventory":
            session["scenario_ids"].reverse()
        elif fault == "escape":
            session["transcript"] = str(tmp_path / "outside.txt")
        elif fault == "transcript":
            Path(session["transcript"]).write_text("changed observation")
        elif fault == "reference":
            session["canonical_evidence_reference"]["artifact_digest"] = "sha256:" + "0" * 64
        elif fault == "session_id":
            session["session_id"] = "changed-session"
        elif fault == "policy":
            session["policy_digest"] = "sha256:" + "0" * 64
        elif fault == "missing":
            evidence.unlink()
        elif fault == "malformed":
            evidence.write_text("not-json")
        elif fault == "missing_transcript_key":
            del session["transcript"]
        assert _session_error(str(tmp_path), session) == message

    def test_missing_scenarios_cannot_validate_retained_session(self, tmp_path, retained_session, monkeypatch):
        from fettle.uat.reconcile import _session_error

        monkeypatch.setattr("fettle.uat.session.collect_scenarios", lambda root: [])
        assert _session_error(str(tmp_path), retained_session) == "session contract is missing or stale; rerun UAT"

    @pytest.mark.parametrize("status,error", [("error", ""), ("timeout", ""), (None, ""), ("completed", "runner failed")])
    def test_session_error_requires_successful_run(self, tmp_path, status, error):
        from fettle.uat.reconcile import _session_error

        assert _session_error(str(tmp_path), {"status": status, "error": error}) == "session did not complete successfully; rerun UAT"

    @pytest.mark.parametrize("field", ["artifact_error", "canonical_evidence_error", "validation_error"])
    def test_retained_error_is_not_lost(self, tmp_path, field):
        from fettle.uat.reconcile import _session_error

        assert _session_error(str(tmp_path), {"status": "completed", field: 17}) == "17"

    def test_retained_error_precedence(self, tmp_path):
        from fettle.uat.reconcile import _session_error

        session = {"status": "completed", "artifact_error": "artifact failed",
                   "canonical_evidence_error": "canonical failed", "validation_error": "validation failed"}
        assert _session_error(str(tmp_path), session) == "artifact failed"
        del session["artifact_error"]
        assert _session_error(str(tmp_path), session) == "canonical failed"

    @pytest.mark.parametrize("error", ["", "capture evidence invalid"])
    def test_controller_session_uses_capture_validator(self, tmp_path, error):
        from fettle.uat.reconcile import _session_error

        session = {"status": "completed", "capture_mode": "contract"}
        with patch("fettle.uat.controller.validate_capture", return_value=([], error)) as validate:
            assert _session_error(str(tmp_path), session) == error
        validate.assert_called_once_with(str(tmp_path), session)

    @pytest.mark.parametrize("capture", [None, [], {}, {"status": "failed"}])
    def test_web_requires_completed_capture_before_other_evidence(self, tmp_path, capture):
        from fettle.uat.reconcile import _session_error

        assert _session_error(str(tmp_path), {"status": "completed", "surface": "web", "web_capture": capture}) == (
            "required web capture is missing or failed; rerun UAT")

    @pytest.mark.parametrize("scenario_ids", [[], None, {}, "greeter/S1", [""], [17],
                                               ["greeter/S1", "greeter/S1"], ["greeter/missing"]])
    def test_invalid_inventory_never_succeeds(self, tmp_path, scenario_ids):
        folder = tmp_path / ".fettle"
        folder.mkdir()
        transcript = folder / "t.txt"
        transcript.write_text("SCENARIO: greeter/S1\nOUTCOME: matches\n")
        (folder / "uat-session.json").write_text(json.dumps({
            "status": "completed", "transcript": str(transcript),
            "scenario_ids": scenario_ids,
        }))
        with patch("fettle.uat.session.collect_scenarios", return_value=SCENARIOS):
            verdicts, checkpoint, error = reconcile_session(str(tmp_path), str(tmp_path))
        assert error == ("required scenario coverage changed or is incomplete; rerun UAT"
                 if scenario_ids == ["greeter/missing"] else
                 "session requires a nonempty unique scenario inventory; rerun UAT")
        assert verdicts == []
        assert not checkpoint.get("acceptance_complete")

    @pytest.mark.parametrize("status", ["error", "timeout", "running", None])
    def test_failed_session_cannot_be_promoted_by_verdicts(self, tmp_path, status):
        path, error = write_report(str(tmp_path), {
            "session_id": "failed", "surface": "cli", "status": status,
            "scenario_ids": ["greeter/S1"],
        }, [Verdict("greeter/S1", "CONFIRMED", observed="claimed pass")])
        assert not error
        report = json.loads(Path(path).read_text())
        assert report["completion"]["complete"] is False
        assert "did not complete" in report["session_error"]
        artifact = parse_artifact((tmp_path / ".fettle" / "uat-report.evidence.json").read_bytes())
        assert artifact.result_state == "unknown"

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
                   return_value=SCENARIOS[:1]):
            verdicts, cp, err = reconcile_session(str(tmp_path), str(wt))
        assert err == ""
        assert [v.verdict for v in verdicts] == ["INDETERMINATE"]
        assert (wt / ".fettle" / "uat-report.json").exists()

    def test_missing_checkpoint(self, tmp_path):
        assert reconcile_session(str(tmp_path), str(tmp_path)) == (
            [], {}, f"no session checkpoint found in {tmp_path}")

    @pytest.mark.parametrize("transcript", [None, "", 17, []])
    def test_missing_transcript(self, tmp_path, transcript):
        (tmp_path / ".fettle").mkdir()
        session = {"session_id": "x", "status": "error", "transcript": transcript}
        (tmp_path / ".fettle" / "uat-session.json").write_text(
            json.dumps(session))
        assert reconcile_session(str(tmp_path), str(tmp_path)) == (
            [], session, "session has no transcript (did the run complete?)")

    @pytest.mark.parametrize("fault", ["escape", "read", "scenarios"])
    def test_session_input_errors_preserve_diagnostic(self, tmp_path, retained_session, fault):
        session = dict(retained_session)
        if fault == "escape":
            session["transcript"] = str(tmp_path / "outside.txt")
        elif fault == "read":
            Path(session["transcript"]).unlink()
        (tmp_path / ".fettle" / "uat-session.json").write_text(json.dumps(session))
        with patch("fettle.uat.session.collect_scenarios", side_effect=ValueError("invalid spec")):
            verdicts, checkpoint, error = reconcile_session(str(tmp_path), str(tmp_path))
        assert verdicts == []
        assert checkpoint == session
        if fault == "escape":
            assert error == "session transcript escapes retained evidence directory"
        elif fault == "read":
            assert error == f"cannot read transcript: [Errno 2] No such file or directory: '{session['transcript']}'"
        else:
            assert error == "invalid spec"

    @pytest.mark.parametrize("stale", [True, False])
    @pytest.mark.parametrize("write_error", ["", "write failed"])
    def test_session_requires_artifacts_and_preserves_default_judgment(
        self, tmp_path, retained_session, stale, write_error,
    ):
        session = dict(retained_session)
        if stale:
            session["contract_digest"] = "old contract"
        (tmp_path / ".fettle" / "uat-session.json").write_text(json.dumps(session))
        expected = [Verdict("greeter/S1", "BLOCKED", "missing application")]
        with patch("fettle.uat.reconcile.reconcile", return_value=expected) as reconcile_claims, \
                patch("fettle.uat.reconcile.write_report", return_value=("report.json", write_error)) as write, \
                patch("fettle.runners.get_uat_runner") as runner:
            verdicts, checkpoint, error = reconcile_session(str(tmp_path), str(tmp_path))
        assert verdicts == expected
        assert error == write_error
        judgment = {"status": "NOT_APPLICABLE", "findings": []}
        contract_error = "scenario contract is missing or changed; rerun UAT"
        assert checkpoint == {**session, **({"validation_error": contract_error} if stale else {}),
                              "judgment": judgment, "judgment_pass": True, "acceptance_complete": False,
                              "session_error": contract_error if stale else ""}
        reconcile_claims.assert_called_once_with(SCENARIOS, "retained observation\n", artifacts={}, require_artifacts=True)
        runner.assert_not_called()
        write.assert_called_once_with(str(tmp_path), checkpoint, expected, candidates=[], judgment=judgment)

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
        with patch("fettle.uat.session.collect_scenarios", return_value=SCENARIOS[:1]):
            verdicts, _, err = reconcile_session(str(tmp_path), str(wt))

        assert err == ""
        assert [v.verdict for v in verdicts] == ["INDETERMINATE", "INDETERMINATE"]
        assert verdicts[-1].scenario_id == "__lifecycle__/restart-persistence"
        report = json.loads((wt / ".fettle" / "uat-report.json").read_text())
        assert report["lifecycle"]["restart_probe"]["verdict"] == "INDETERMINATE"

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
        with patch("fettle.uat.session.collect_scenarios", return_value=SCENARIOS[:1]):
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
        with patch("fettle.uat.session.collect_scenarios", return_value=SCENARIOS[:1]):
            verdicts, _, err = reconcile_session(str(tmp_path), str(wt))

        assert err == ""
        assert [v.verdict for v in verdicts] == ["INDETERMINATE"]
        report = json.loads((wt / ".fettle" / "uat-report.json").read_text())
        assert report["lifecycle"]["restart_probe"]["verdict"] == "NOT_APPLICABLE"
