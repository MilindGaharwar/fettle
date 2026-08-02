"""Tests for fettle/rules_cmd.py — rule file lifecycle (WP-163, C3)."""

import json

import pytest

from fettle.rules_cmd import (
    demote_rule_file,
    list_rules,
    promote_rule_file,
    promotion_candidates,
    render_candidates,
    render_rules_table,
)

_COMPLETE = """rules:
  - id: {rid}
    pattern: dangerous_call(...)
    message: "caught"
    languages: [python]
    severity: WARNING
    metadata:
      origin: fettle-evolution
      status: proposed
"""

_BRIEF = """rules:
  - id: {rid}
    pattern: ''
    message: "evidence brief"
    languages: [python]
    severity: WARNING
    metadata:
      origin: fettle-evolution
      status: proposed
"""


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def _proposal(root, rid, template=_COMPLETE):
    d = root / "rules" / "proposed"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{rid}.yml").write_text(template.format(rid=rid))


def _learned(root, rid):
    d = root / "rules" / "learned"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{rid}.yml").write_text(
        _COMPLETE.format(rid=rid).replace("status: proposed", "status: learned"))


class TestPromote:
    def test_promote_moves_file_and_updates_status(self, root):
        _proposal(root, "good-rule")
        ok, msg = promote_rule_file(root, "good-rule")
        assert ok, msg
        assert not (root / "rules" / "proposed" / "good-rule.yml").exists()
        text = (root / "rules" / "learned" / "good-rule.yml").read_text()
        assert "status: learned" in text

    def test_empty_pattern_refused(self, root):
        _proposal(root, "brief-rule", _BRIEF)
        ok, msg = promote_rule_file(root, "brief-rule")
        assert not ok and "empty pattern" in msg
        assert (root / "rules" / "proposed" / "brief-rule.yml").exists()

    def test_missing_proposal_refused(self, root):
        ok, msg = promote_rule_file(root, "ghost")
        assert not ok and "no proposal" in msg

    def test_existing_learned_refused(self, root):
        _proposal(root, "dup-rule")
        _learned(root, "dup-rule")
        ok, msg = promote_rule_file(root, "dup-rule")
        assert not ok and "already exists" in msg


class TestDemote:
    def test_demote_moves_back_with_reason(self, root):
        _learned(root, "noisy-rule")
        ok, msg = demote_rule_file(root, "noisy-rule", "too many FPs")
        assert ok, msg
        text = (root / "rules" / "proposed" / "noisy-rule.yml").read_text()
        assert "status: proposed" in text
        assert "too many FPs" in text
        assert not (root / "rules" / "learned" / "noisy-rule.yml").exists()

    def test_reason_required(self, root):
        _learned(root, "some-rule")
        ok, msg = demote_rule_file(root, "some-rule", "  ")
        assert not ok and "reason" in msg

    def test_missing_learned_refused(self, root):
        ok, msg = demote_rule_file(root, "ghost", "because")
        assert not ok and "no learned rule" in msg


class TestListAndCandidates:
    def test_list_joins_evidence(self, root, tmp_path):
        _proposal(root, "brief-rule", _BRIEF)
        _learned(root, "hot-rule")
        trace = tmp_path / "state" / "fettle"
        trace.mkdir(parents=True)
        with open(trace / "trace.jsonl", "w") as f:
            for _ in range(6):
                f.write(json.dumps({
                    "hook": "post_edit", "status": "violation",
                    "findings": [{"code": "hot-rule"}],
                    "timestamp": "2026-08-02T10:00:00",
                }) + "\n")
        rows = {r["id"]: r for r in list_rules(root)}
        assert rows["brief-rule"]["stage"] == "proposed"
        assert rows["brief-rule"]["pattern_empty"] is True
        assert rows["hot-rule"]["stage"] == "learned"
        assert rows["hot-rule"]["fires"] == 6

    def test_candidates_promote_bar(self, root, tmp_path):
        _learned(root, "hot-rule")
        trace = tmp_path / "state" / "fettle"
        trace.mkdir(parents=True)
        with open(trace / "trace.jsonl", "w") as f:
            for _ in range(6):
                f.write(json.dumps({
                    "hook": "post_edit", "status": "violation",
                    "findings": [{"code": "hot-rule"}],
                    "timestamp": "2026-08-02T10:00:00",
                }) + "\n")
        data = promotion_candidates(root)
        assert [r["id"] for r in data["promote"]] == ["hot-rule"]
        assert data["demote"] == []

    def test_candidates_demote_bar(self, root, tmp_path):
        _learned(root, "noisy-rule")
        state = tmp_path / "state" / "fettle"
        state.mkdir(parents=True)
        with open(state / "trace.jsonl", "w") as f:
            for _ in range(4):
                f.write(json.dumps({
                    "hook": "post_edit", "status": "violation",
                    "findings": [{"code": "noisy-rule"}],
                    "timestamp": "2026-08-02T10:00:00",
                }) + "\n")
        with open(state / "false-positives.jsonl", "w") as f:
            for _ in range(3):
                f.write(json.dumps({
                    "rule": "noisy-rule", "timestamp": "2026-08-02T10:00:00",
                }) + "\n")
        data = promotion_candidates(root)
        assert [r["id"] for r in data["demote"]] == ["noisy-rule"]
        assert data["promote"] == []  # FP rate 75% > 20%

    def test_render_paths(self, root):
        assert "fettle learn --from-trace" in render_rules_table([])
        _proposal(root, "brief-rule", _BRIEF)
        assert "needs pattern" in render_rules_table(list_rules(root))
        out = render_candidates(promotion_candidates(root))
        assert "Pending proposals: 1" in out
