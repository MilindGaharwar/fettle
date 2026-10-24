"""P72 contract tests — artifact-bound UAT reconciliation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from fettle.uat.artifacts import (
    _safe_name,
    block_sha,
    capture_web_page,
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


@pytest.mark.parametrize("identifier,expected", [
    ("demo/S1", "demo_S1"), ("../demo//S1", ".._demo_S1"),
    ("AZaz09-._", "AZaz09-._"), ("demo?!: name", "demo_name"),
])
def test_artifact_names_preserve_safe_characters(identifier, expected):
    assert _safe_name(identifier) == expected


def test_block_digest_uses_sorted_compact_json():
    expected = hashlib.sha256(b'{"a":1,"z":"caf\\u00e9"}').hexdigest()
    assert block_sha({"z": "caf\u00e9", "a": 1}) == expected
    assert block_sha({"a": 1, "z": "caf\u00e9"}) == expected


def test_artifact_bundle_preserves_exact_claim_projection(tmp_path):
    worktree = tmp_path / "new" / "worktree"
    scenarios = [{"id": "demo/missing"}, *SCENARIOS, {"id": "demo/S2"}]
    with patch("fettle.uat.artifacts.time.time", return_value=1234.56789):
        directory = write_scenario_artifacts(str(worktree), TRANSCRIPT, scenarios, "web")
    assert directory == str(worktree / ".fettle" / "uat-artifacts")
    assert sorted(path.name for path in Path(directory).iterdir()) == ["demo_S1.json", "demo_S2.json"]
    blocks = {
        "demo/S1": {"observed": "command exited 0 and printed balances", "outcome": "matches", "notes": "ran twice to confirm"},
        "demo/S2": {"observed": "crashed on empty input", "outcome": "differs", "notes": ""},
    }
    expected = {}
    for identifier, block in blocks.items():
        expected[identifier] = {
            "schema_version": 1, "evidence_basis": "agent-claim", "scenario_id": identifier,
            "surface": "web", "captured_at": 1234.568, "block": block,
            "block_sha": hashlib.sha256(json.dumps(block, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "steps": SCENARIOS[0]["steps"] if identifier == "demo/S1" else [],
        }
        assert (Path(directory) / (identifier.replace("/", "_") + ".json")).read_text() == json.dumps(
            expected[identifier], indent=2, sort_keys=True)
    assert load_scenario_artifacts(str(worktree)) == expected
    assert load_scenario_artifacts(directory) == expected
    assert write_scenario_artifacts(str(worktree), TRANSCRIPT.replace("printed balances", "printed updated balances"),
                                    scenarios, "web") == directory
    assert load_scenario_artifacts(directory)["demo/S1"]["block"]["observed"] == "command exited 0 and printed updated balances"


@pytest.mark.parametrize("bad", [None, [], {}, {"scenario_id": None}, {"scenario_id": ""}, {"scenario_id": 17}])
def test_loader_skips_malformed_record_and_keeps_later_evidence(tmp_path, bad):
    (tmp_path / "a.json").write_text(json.dumps(bad))
    valid = {"scenario_id": "demo/S1", "block": {"observed": "retained"}}
    (tmp_path / "z.json").write_text(json.dumps(valid))
    assert load_scenario_artifacts(str(tmp_path)) == {"demo/S1": valid}


@pytest.mark.parametrize("fault", ["json", "encoding", "directory"])
def test_loader_continues_after_unreadable_json(tmp_path, fault):
    target = tmp_path / "a.json"
    if fault == "directory":
        target.mkdir()
    else:
        target.write_bytes(b"not json" if fault == "json" else b"\xff")
    valid = {"scenario_id": "demo/S1"}
    (tmp_path / "z.json").write_text(json.dumps(valid))
    assert load_scenario_artifacts(str(tmp_path)) == {"demo/S1": valid}


def test_duplicate_artifacts_never_reenter_inventory(tmp_path):
    for index in range(3):
        (tmp_path / f"duplicate-{index}.json").write_text(json.dumps({"scenario_id": "demo/S1", "attempt": index}))
    valid = {"scenario_id": "demo/S2"}
    (tmp_path / "valid.json").write_text(json.dumps(valid))
    (tmp_path / "ignored.tmp").write_text(json.dumps({"scenario_id": "demo/S3"}))
    assert load_scenario_artifacts(str(tmp_path)) == {"demo/S2": valid}


def test_loader_missing_location_has_no_artifacts(tmp_path):
    assert load_scenario_artifacts(str(tmp_path / "absent")) == {}


def test_loader_prefers_retained_bundle_over_root_json(tmp_path):
    bundle = tmp_path / ".fettle" / "uat-artifacts"
    bundle.mkdir(parents=True)
    (tmp_path / "unrelated.json").write_text(json.dumps({"scenario_id": "unrelated"}))
    valid = {"scenario_id": "demo/S1"}
    (bundle / "retained.json").write_text(json.dumps(valid))
    assert load_scenario_artifacts(str(tmp_path)) == {"demo/S1": valid}


@pytest.fixture
def browser_capture(monkeypatch):
    import sys

    factory = MagicMock()
    browser = factory.return_value.__enter__.return_value.chromium.launch.return_value
    page = browser.new_page.return_value
    page.url = "https://example.test/redirected"
    page.locator.return_value.aria_snapshot.return_value = "- heading: Account"
    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "playwright.sync_api", SimpleNamespace(sync_playwright=factory))
    return factory, browser, page


@pytest.mark.parametrize("existing", [True, False])
def test_web_capture_preserves_browser_contract_and_artifact_paths(tmp_path, browser_capture, existing):
    factory, browser, page = browser_capture
    destination = tmp_path / "nested" / "capture"
    if existing:
        destination.mkdir(parents=True)

    def screenshot(*, path, full_page):
        assert full_page is True
        Path(path).write_bytes(b"captured image")

    page.screenshot.side_effect = screenshot
    result = capture_web_page("https://example.test/start", str(destination))
    assert result == {"status": "completed", "screenshot": str(destination / "_page.png"),
                      "a11y": str(destination / "_a11y.json"), "url": "https://example.test/redirected"}
    factory.assert_called_once_with()
    factory.return_value.__enter__.return_value.chromium.launch.assert_called_once_with()
    browser.new_page.assert_called_once_with(viewport={"width": 1280, "height": 720})
    page.goto.assert_called_once_with("https://example.test/start", wait_until="networkidle", timeout=30_000)
    page.screenshot.assert_called_once_with(path=str(destination / "_page.png"), full_page=True)
    page.locator.assert_called_once_with("body")
    page.locator.return_value.aria_snapshot.assert_called_once_with()
    browser.close.assert_called_once_with()
    factory.return_value.__exit__.assert_called_once_with(None, None, None)
    assert (destination / "_page.png").read_bytes() == b"captured image"
    assert (destination / "_a11y.json").read_text() == json.dumps({"aria_snapshot": "- heading: Account"}, indent=2)


@pytest.mark.parametrize("boundary", ["launch", "new_page", "goto", "screenshot", "snapshot", "close"])
def test_web_capture_failure_preserves_diagnostic(tmp_path, browser_capture, boundary, caplog):
    factory, browser, page = browser_capture
    method = {"launch": factory.return_value.__enter__.return_value.chromium.launch,
              "new_page": browser.new_page, "goto": page.goto, "screenshot": page.screenshot,
              "snapshot": page.locator.return_value.aria_snapshot, "close": browser.close}[boundary]
    method.side_effect = RuntimeError("capture unavailable")
    assert capture_web_page("https://example.test/start", str(tmp_path)) == {
        "status": "tool_error", "message": "web capture failed: RuntimeError: capture unavailable"}
    assert [(record.levelname, record.getMessage()) for record in caplog.records] == [
        ("WARNING", "web capture failed: RuntimeError: capture unavailable")]


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


def test_matching_claim_artifact_cannot_confirm_execution(tmp_path):
    worktree = tmp_path / "wt"
    worktree.mkdir()
    artifacts = write_scenario_artifacts(str(worktree), TRANSCRIPT, SCENARIOS, "cli")

    verdicts = reconcile(
        SCENARIOS, TRANSCRIPT,
        artifacts=load_scenario_artifacts(artifacts),
        require_artifacts=True,
    )

    by_id = {v.scenario_id: v for v in verdicts}
    assert by_id["demo/S1"].verdict == "INDETERMINATE"
    assert "independent execution" in by_id["demo/S1"].note


def test_tampered_artifact_body_is_rejected(tmp_path):
    artifacts = write_scenario_artifacts(str(tmp_path), TRANSCRIPT, SCENARIOS, "cli")
    loaded = load_scenario_artifacts(artifacts)
    loaded["demo/S1"]["block"]["observed"] = "actually crashed"
    verdict = reconcile(SCENARIOS, TRANSCRIPT, loaded, require_artifacts=True)[0]
    assert verdict.verdict == "INDETERMINATE"
    assert "content" in verdict.note


def test_malformed_artifact_shape_is_ignored(tmp_path):
    (tmp_path / "bad.json").write_text("[]")
    assert load_scenario_artifacts(str(tmp_path)) == {}


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


def test_legacy_claims_without_artifact_arguments_cannot_confirm():
    verdicts = reconcile(SCENARIOS, TRANSCRIPT)

    by_id = {v.scenario_id: v for v in verdicts}
    assert by_id["demo/S1"].verdict == "INDETERMINATE"
