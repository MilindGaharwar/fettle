"""Tests for learn.py proposal drafting — rules/proposed/ quarantine (WP-163, C2)."""

from pathlib import Path

import pytest

import fettle
from fettle.evolution import MIN_OCCURRENCES
from fettle.learn import (
    PROPOSED_RULES_DIR,
    draft_proposals,
    list_proposed_rules,
)
from fettle.trace import log_decision


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("FETTLE_PARENT_SESSION", raising=False)
    monkeypatch.delenv("FETTLE_POLICY_CAPSULE", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    return root


def _fire(code, message=""):
    log_decision(hook="post_edit", status="violation", tool="Edit",
                 findings=[{"code": code, "message": message or code}])


def _seed_signature(code="prop-test-code", message=""):
    for _ in range(MIN_OCCURRENCES):
        _fire(code, message)


_NO_LLM = lambda brief: None  # noqa: E731


class TestEvidenceBrief:
    def test_brief_written_when_no_llm(self, env):
        _seed_signature()
        results = draft_proposals(env, days=1, generate=_NO_LLM)
        assert len(results) == 1
        assert results[0]["mode"] == "brief"
        path = env / PROPOSED_RULES_DIR / "prop-test-code.yml"
        assert path.is_file()
        text = path.read_text()
        assert "status: proposed" in text
        assert "origin: fettle-evolution" in text
        assert "pattern: ''" in text
        assert "fettle rules promote prop-test-code" in text

    def test_evidence_redacted_in_brief(self, env):
        _seed_signature(message="leak ghp_abcdefghij1234567890 here")
        draft_proposals(env, days=1, generate=_NO_LLM)
        text = (env / PROPOSED_RULES_DIR / "prop-test-code.yml").read_text()
        assert "ghp_abcdefghij1234567890" not in text
        assert "***REDACTED***" in text


class TestLLMPath:
    def test_llm_rule_saved_as_proposal(self, env):
        _seed_signature()
        fake_rule = {
            "rule_id": "ignored-llm-id",
            "severity": "WARNING",
            "message": "caught it",
            "pattern": "dangerous_call(...)",
            "language": "python",
            "citation": "trace signature",
        }
        results = draft_proposals(env, days=1, generate=lambda brief: dict(fake_rule))
        assert results[0]["mode"] == "llm"
        # signature-derived id wins over the LLM's — it is the dedup key
        assert results[0]["rule_id"] == "prop-test-code"
        text = (env / PROPOSED_RULES_DIR / "prop-test-code.yml").read_text()
        assert "origin: fettle-evolution" in text
        assert "status: proposed" in text
        assert "dangerous_call(...)" in text


class TestGovernance:
    def test_second_run_is_deduplicated(self, env):
        _seed_signature()
        assert len(draft_proposals(env, days=1, generate=_NO_LLM)) == 1
        # existing proposal covers the code → no new signature, no rewrite
        assert draft_proposals(env, days=1, generate=_NO_LLM) == []

    def test_dry_run_writes_nothing(self, env):
        _seed_signature()
        results = draft_proposals(env, days=1, save=False, generate=_NO_LLM)
        assert results and results[0]["path"] == ""
        assert not (env / PROPOSED_RULES_DIR).exists()

    def test_no_signatures_no_proposals(self, env):
        assert draft_proposals(env, days=1, generate=_NO_LLM) == []
        assert list_proposed_rules(env) == []

    def test_proposed_dir_is_never_loaded_by_gates(self):
        """Pin the quarantine: only the evolution loop mentions rules/proposed.

        If a gate or resource loader ever references the proposals dir,
        principle 5 (autonomy never weakens policy) is broken.
        """
        allowed = {"learn.py", "evolution.py", "rules_cmd.py"}
        pkg = Path(fettle.__file__).parent
        offenders = [
            py.name for py in pkg.glob("*.py")
            if py.name not in allowed and "rules/proposed" in py.read_text(encoding="utf-8")
        ]
        assert offenders == []
