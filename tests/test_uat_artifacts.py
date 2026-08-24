"""P72 contract tests — artifact-bound UAT reconciliation."""

from __future__ import annotations

from fettle.uat.artifacts import (
    block_sha,
    load_scenario_artifacts,
    write_scenario_artifacts,
)
from fettle.uat.reconcile import parse_transcript, reconcile

SCENARIOS = [{
    "id": "demo/S1",
    "title": "Demo works",
    "steps": ["Given the demo", "When it runs", "Then exit code is zero"],
    "requirements": ["R1"],
}]

TRANSCRIPT = """\
SCENARIO: demo/S1
OBSERVED: command exited 0 and printed balances
OUTCOME: matches
NOTES: ran twice to confirm

SCENARIO: demo/S2
OBSERVED: crashed on empty input
OUTCOME: differs
"""


def test_artifact_bundle_captures_reported_scenarios(tmp_path):
    worktree = tmp_path / "wt"
    worktree.mkdir()

    artifact_dir = write_scenario_artifacts(
        str(worktree), TRANSCRIPT, SCENARIOS, surface="cli"
    )

    loaded = load_scenario_artifacts(str(artifact_dir))
    assert set(loaded) == {"demo/S1"}  # S2 unreported → no artifact
    assert loaded["demo/S1"]["block_sha"] == block_sha(
        parse_transcript(TRANSCRIPT)["demo/S1"]
    )


def test_confirmed_without_artifact_degrades_when_required(tmp_path):
    worktree = tmp_path / "wt"
    worktree.mkdir()

    artifacts = write_scenario_artifacts(str(worktree), "", SCENARIOS, "cli")
    empty = load_scenario_artifacts(str(artifacts))

    verdicts = reconcile(SCENARIOS, TRANSCRIPT, artifacts=empty,
                         require_artifacts=True)

    by_id = {v.scenario_id: v for v in verdicts}
    assert by_id["demo/S1"].verdict == "INDETERMINATE"
    assert "no observation artifact" in by_id["demo/S1"].note


def test_matching_artifact_preserves_confirmation(tmp_path):
    worktree = tmp_path / "wt"
    worktree.mkdir()
    artifacts = write_scenario_artifacts(str(worktree), TRANSCRIPT, SCENARIOS, "cli")

    verdicts = reconcile(
        SCENARIOS, TRANSCRIPT,
        artifacts=load_scenario_artifacts(artifacts),
        require_artifacts=True,
    )

    by_id = {v.scenario_id: v for v in verdicts}
    assert by_id["demo/S1"].verdict == "CONFIRMED"


def test_tampered_transcript_drifts_from_artifact(tmp_path):
    worktree = tmp_path / "wt"
    worktree.mkdir()
    artifacts = write_scenario_artifacts(str(worktree), TRANSCRIPT, SCENARIOS, "cli")
    tampered = TRANSCRIPT.replace(
        "command exited 0 and printed balances",
        "everything worked perfectly",
    )

    verdicts = reconcile(
        SCENARIOS, tampered,
        artifacts=load_scenario_artifacts(artifacts),
        require_artifacts=True,
    )

    by_id = {v.scenario_id: v for v in verdicts}
    assert by_id["demo/S1"].verdict == "INDETERMINATE"
    assert "drifted" in by_id["demo/S1"].note


def test_differs_verdicts_do_not_need_artifacts(tmp_path):
    both = SCENARIOS + [{
        "id": "demo/S2",
        "title": "Empty input handled",
        "steps": ["Given empty input", "When it runs", "Then it does not crash"],
        "requirements": [],
    }]

    verdicts = reconcile(both, TRANSCRIPT, artifacts=None, require_artifacts=True)

    by_id = {v.scenario_id: v for v in verdicts}
    assert by_id["demo/S2"].verdict == "CONTRADICTED"
    assert by_id["demo/S1"].verdict == "INDETERMINATE"  # artifact required, absent


def test_backward_compatible_without_artifact_arguments():
    verdicts = reconcile(SCENARIOS, TRANSCRIPT)

    by_id = {v.scenario_id: v for v in verdicts}
    assert by_id["demo/S1"].verdict == "CONFIRMED"
