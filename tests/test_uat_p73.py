"""P73 contract tests — exploration charters and candidate isolation."""

from __future__ import annotations

import json

from fettle.uat.reconcile import parse_candidates, reconcile
from fettle.uat.session import build_prompt

SCENARIOS = [{
    "id": "demo/S1",
    "title": "Demo works",
    "steps": ["Given the demo", "When it runs", "Then it passes"],
    "requirements": [],
}]

CHARTER_TRANSCRIPT = """\
SCENARIO: demo/S1
OBSERVED: exited 0, output matched
OUTCOME: matches

CANDIDATE: huge-amount
OBSERVED: transferring 99999999999999 cents succeeded silently
WHY-INTERESTING: no upper bound on transfer size

CANDIDATE: unicode-name
OBSERVED: name with emoji corrupted the audit line
WHY-INTERESTING: encoding assumption in the audit path
"""


def _cfg(explore=None):
    cfg = {}
    if explore is not None:
        cfg["explore"] = explore
    return cfg


def test_charter_appended_only_when_explore_enabled():
    without = build_prompt("cli", SCENARIOS, _cfg())
    with_explore = build_prompt("cli", SCENARIOS, _cfg(explore=True))

    assert "Exploration Charter" not in without
    assert "Exploration Charter" in with_explore
    for tour in ("SABOTEUR", "MONEY TOUR", "SUPERMODEL"):
        assert tour in with_explore


def test_charters_instruct_candidate_blocks_not_verdicts():
    prompt = build_prompt("cli", SCENARIOS, _cfg(explore=True))

    assert "CANDIDATE:" in prompt
    assert "NOT scenario verdicts" in prompt


def test_candidates_parsed_with_fields(tmp_path):
    parsed = parse_candidates(CHARTER_TRANSCRIPT)

    ids = [c["candidate_id"] for c in parsed]
    assert ids == ["huge-amount", "unicode-name"]
    assert "99999999999999" in parsed[0]["observed"]
    assert parsed[1]["why_interesting"].startswith("encoding")


def test_scenario_blocks_are_never_mistaken_for_candidates():
    transcript = CHARTER_TRANSCRIPT  # contains a real verdict block too

    verdicts = reconcile(SCENARIOS, transcript)
    candidates = parse_candidates(transcript)

    assert [v.verdict for v in verdicts] == ["CONFIRMED"]
    assert len(candidates) == 2
    assert all("SCENARIO" not in c["candidate_id"] for c in candidates)


def test_candidates_never_become_verdicts(tmp_path):
    from fettle.uat.reconcile import write_report

    verdicts = reconcile(SCENARIOS, CHARTER_TRANSCRIPT)
    path, err = write_report(str(tmp_path), {"session_id": "s",
                                             "surface": "cli"},
                             verdicts,
                             candidates=parse_candidates(CHARTER_TRANSCRIPT))
    assert err == ""

    report = json.loads((tmp_path / ".fettle" / "uat-report.json")
                        .read_text(encoding="utf-8"))
    assert len(report["candidate_scenarios"]) == 2
    assert report["candidate_scenarios"][0]["candidate_id"] == "huge-amount"
    # verdict list untouched by candidates
    assert [v["scenario_id"] for v in report["verdicts"]] == ["demo/S1"]
