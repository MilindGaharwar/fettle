"""Tests for fettle/evolution.py — failure-signature sensing (WP-163, C1)."""

import json
import time

import pytest

from fettle.evolution import (
    FAILURE_HISTORY_RELPATH,
    MIN_OCCURRENCES,
    Signature,
    covered_rule_ids,
    detect_signatures,
)
from fettle.trace import log_decision


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated state dir + repo root."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("FETTLE_PARENT_SESSION", raising=False)
    monkeypatch.delenv("FETTLE_POLICY_CAPSULE", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    return root


def _fire(code, status="violation", hook="post_edit", message=""):
    log_decision(hook=hook, status=status, tool="Edit",
                 findings=[{"code": code, "message": message or code}])


def _write_ci_history(root, classification, n, summary="FAILED tests/test_x.py"):
    path = root / FAILURE_HISTORY_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        for i in range(n):
            f.write(json.dumps({
                "run_id": f"{classification}-{i}",
                "classification": classification,
                "summary": summary,
                "commit": "abc123",
            }) + "\n")


class TestTraceClusters:
    def test_repeated_uncovered_code_is_a_signature(self, env):
        for _ in range(MIN_OCCURRENCES):
            _fire("evo-test-unique-code")
        sigs = detect_signatures(env, days=1)
        assert [s.key for s in sigs] == ["post_edit/evo-test-unique-code"]
        sig = sigs[0]
        assert sig.kind == "trace-cluster"
        assert sig.count == MIN_OCCURRENCES
        assert sig.draftable is True
        assert sig.first_ts <= sig.last_ts

    def test_below_threshold_is_silent(self, env):
        for _ in range(MIN_OCCURRENCES - 1):
            _fire("evo-test-rare-code")
        assert detect_signatures(env, days=1) == []

    def test_pass_entries_do_not_count(self, env):
        for _ in range(MIN_OCCURRENCES):
            _fire("evo-test-passing", status="pass")
        assert detect_signatures(env, days=1) == []

    def test_blocked_statuses_count(self, env):
        _fire("evo-test-blocked", status="blocked")
        _fire("evo-test-blocked", status="block")
        _fire("evo-test-blocked", status="violation")
        sigs = detect_signatures(env, days=1)
        assert sigs and sigs[0].count == 3

    def test_old_entries_outside_window_excluded(self, env, monkeypatch):
        real_time = time.time
        monkeypatch.setattr(time, "time", lambda: real_time() - 10 * 86400)
        for _ in range(MIN_OCCURRENCES):
            _fire("evo-test-stale-code")
        monkeypatch.setattr(time, "time", real_time)
        assert detect_signatures(env, days=1) == []
        assert detect_signatures(env, days=30)  # wider window sees them

    def test_covered_by_learned_rule_file_excluded(self, env):
        learned = env / "rules" / "learned"
        learned.mkdir(parents=True)
        (learned / "evo-test-covered.yml").write_text(
            "rules:\n  - id: evo-test-covered\n    pattern: foo\n")
        for _ in range(MIN_OCCURRENCES):
            _fire("evo-test-covered")
        assert detect_signatures(env, days=1) == []

    def test_covered_by_inner_id_excluded(self, env):
        proposed = env / "rules" / "proposed"
        proposed.mkdir(parents=True)
        (proposed / "some-other-name.yml").write_text(
            "rules:\n  - id: evo-test-inner-id\n    pattern: foo\n")
        for _ in range(MIN_OCCURRENCES):
            _fire("evo-test-inner-id")
        assert detect_signatures(env, days=1) == []

    def test_samples_are_redacted_and_deduped(self, env):
        for _ in range(MIN_OCCURRENCES):
            _fire("evo-test-secret", message="token ghp_abcdefghij1234567890 leaked")
        sig = detect_signatures(env, days=1)[0]
        assert sig.sample_evidence == ["token ***REDACTED*** leaked"]

    def test_distinct_hooks_are_distinct_signatures(self, env):
        for _ in range(MIN_OCCURRENCES):
            _fire("evo-test-multi", hook="post_edit")
            _fire("evo-test-multi", hook="quality_gate")
        keys = {s.key for s in detect_signatures(env, days=1)}
        assert keys == {"post_edit/evo-test-multi", "quality_gate/evo-test-multi"}


class TestCIClasses:
    def test_recurring_test_class_is_draftable(self, env):
        _write_ci_history(env, "test", MIN_OCCURRENCES)
        sigs = detect_signatures(env, days=1)
        assert [s.key for s in sigs] == ["test"]
        assert sigs[0].kind == "ci-class"
        assert sigs[0].draftable is True

    def test_environment_class_not_draftable(self, env):
        _write_ci_history(env, "environment", MIN_OCCURRENCES,
                          summary="Permission denied")
        sig = detect_signatures(env, days=1)[0]
        assert sig.draftable is False
        assert sig.count == MIN_OCCURRENCES

    def test_below_threshold_silent(self, env):
        _write_ci_history(env, "test", MIN_OCCURRENCES - 1)
        assert detect_signatures(env, days=1) == []

    def test_missing_history_file_ok(self, env):
        assert detect_signatures(env, days=1) == []


class TestOrdering:
    def test_sorted_by_count_desc(self, env):
        for _ in range(MIN_OCCURRENCES):
            _fire("evo-test-small")
        for _ in range(MIN_OCCURRENCES + 2):
            _fire("evo-test-big")
        keys = [s.key for s in detect_signatures(env, days=1)]
        assert keys == ["post_edit/evo-test-big", "post_edit/evo-test-small"]

    def test_to_dict_round_trip(self, env):
        sig = Signature(kind="trace-cluster", key="h/c", count=3,
                        sample_evidence=["x"], draftable=True)
        d = sig.to_dict()
        assert d["key"] == "h/c" and d["draftable"] is True


class TestCoverage:
    def test_bundled_pack_ids_are_covered(self, env):
        # A real rule id from the bundled packs must be covered even with
        # no project rules/ dirs — bundled fires are not gaps.
        covered = covered_rule_ids(env)
        assert covered  # bundled packs exist in the clone
