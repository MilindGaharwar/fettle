"""P73 contract tests — exploration charters and candidate isolation."""

from __future__ import annotations

import json

import pytest

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

    assert parsed == [
        {"candidate_id": "huge-amount", "observed": "transferring 99999999999999 cents succeeded silently",
         "why_interesting": "no upper bound on transfer size"},
        {"candidate_id": "unicode-name", "observed": "name with emoji corrupted the audit line",
         "why_interesting": "encoding assumption in the audit path"},
    ]


@pytest.mark.parametrize("text,expected", [
    ("", []), ("OBSERVED: stray observation\nWHY-INTERESTING: stray reason\n", []),
    ("CANDIDATE: blank\n\nignored text\n", [{"candidate_id": "blank", "observed": "", "why_interesting": ""}]),
    ("  CANDIDATE: spaced id  \n  ObSeRvEd: first line  \n\nsecond line\n WhY-InTeReStInG: reason  \n",
     [{"candidate_id": "spaced id", "observed": "first line second line", "why_interesting": "reason"}]),
    ("CANDIDATE: first\nCANDIDATE: second\nOBSERVED:\nWHY-INTERESTING:reason\n",
     [{"candidate_id": "first", "observed": "", "why_interesting": ""},
      {"candidate_id": "second", "observed": "", "why_interesting": "reason"}]),
])
def test_candidate_fields_preserve_exact_content(text, expected):
    assert parse_candidates(text) == expected


def test_scenario_blocks_are_never_mistaken_for_candidates():
    transcript = CHARTER_TRANSCRIPT  # contains a real verdict block too

    verdicts = reconcile(SCENARIOS, transcript)
    candidates = parse_candidates(transcript)

    assert [v.verdict for v in verdicts] == ["INDETERMINATE"]
    assert len(candidates) == 2
    assert all("SCENARIO" not in c["candidate_id"] for c in candidates)


@pytest.mark.parametrize("section", ["SCENARIO: demo/S1", "RESTART_PROBE:"])
@pytest.mark.parametrize("following_candidate", [False, True])
def test_verdict_sections_do_not_overwrite_candidate_evidence(section, following_candidate):
    transcript = (
        "CANDIDATE: retained-finding\nOBSERVED: original observation\n"
        "WHY-INTERESTING: original reason\n"
        f"{section}\nOBSERVED: unrelated verdict observation\n"
        "OUTCOME: matches\nNOTES: verdict notes\n"
    )
    expected = [{"candidate_id": "retained-finding", "observed": "original observation",
                 "why_interesting": "original reason"}]
    if following_candidate:
        transcript += "CANDIDATE: next-finding\nOBSERVED: next observation\n"
        expected.append({"candidate_id": "next-finding", "observed": "next observation", "why_interesting": ""})
    assert parse_candidates(transcript) == expected


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
