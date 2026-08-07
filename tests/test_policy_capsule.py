"""Tests for fettle.policy_capsule — WP-156 (Stage A, slices A1+A2).

Design doc: docs/engagement/12-stage-a-policy-continuity.md §2.
"""

import json

import pytest

from fettle.policy_capsule import (
    ENV_VAR,
    MAX_LINEAGE_DEPTH,
    canonical_digest,
    last_error,
    merge_for_child,
    resolve_env_capsule,
    verify,
    write_capsule,
)


@pytest.fixture
def state_home(tmp_path, monkeypatch):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv(ENV_VAR, raising=False)
    return tmp_path / "state"


POLICY = {"gates": {"destructive": {"enabled": True, "mode": "enforce"}}}
ORIGIN = {"repo_root": "/r", "repo": "r", "session_id": "p1",
          "created_at": "2026-08-02T00:00:00", "fettle_version": "1.4.0"}


class TestWriteAndVerify:
    def test_round_trip(self, state_home, monkeypatch) -> None:
        path = write_capsule(POLICY, ORIGIN)
        assert path.is_file()
        assert path.parent == state_home / "fettle" / "capsules" \
            or "capsules" in str(path)
        monkeypatch.setenv(ENV_VAR, str(path))
        doc, err = resolve_env_capsule()
        assert err == ""
        assert doc is not None
        assert doc["policy"] == POLICY
        assert doc["origin"]["session_id"] == "p1"

    def test_digest_covers_only_policy_body(self) -> None:
        # Same policy, different origin → same digest (design §2.1).
        assert canonical_digest(POLICY) == canonical_digest(
            json.loads(json.dumps(POLICY)))

    def test_tampered_policy_fails_verification(self, state_home) -> None:
        path = write_capsule(POLICY, ORIGIN)
        doc = json.loads(path.read_text())
        doc["policy"]["gates"]["destructive"]["mode"] = "advisory"
        assert "digest mismatch" in verify(doc)

    def test_filename_mismatch_fails_verification(self, state_home, tmp_path) -> None:
        path = write_capsule(POLICY, ORIGIN)
        doc = json.loads(path.read_text())
        moved = tmp_path / "0000000000000000.json"
        moved.write_text(json.dumps(doc))
        assert "filename" in verify(doc, moved)

    def test_lineage_depth_cap_refuses(self, state_home) -> None:
        chain = [f"{i:016x}" for i in range(MAX_LINEAGE_DEPTH)]
        with pytest.raises(ValueError, match="depth"):
            write_capsule(POLICY, ORIGIN, lineage=chain)

    def test_lineage_chain_recorded(self, state_home) -> None:
        path = write_capsule(POLICY, ORIGIN, lineage=["aaaa", "bbbb"])
        doc = json.loads(path.read_text())
        assert doc["lineage"] == ["aaaa", "bbbb"]


class TestResolveEnvCapsule:
    def test_no_env_is_solo_mode(self, state_home) -> None:
        doc, err = resolve_env_capsule()
        assert doc is None and err == ""
        assert last_error() == ""

    def test_missing_file_fails_closed(self, state_home, monkeypatch) -> None:
        monkeypatch.setenv(ENV_VAR, str(state_home / "nope.json"))
        doc, err = resolve_env_capsule()
        assert doc is None
        assert "unreadable" in err
        assert last_error() == err

    def test_tampered_file_fails_closed(self, state_home, monkeypatch) -> None:
        path = write_capsule(POLICY, ORIGIN)
        doc = json.loads(path.read_text())
        doc["policy"]["gates"]["destructive"]["mode"] = "advisory"
        path.write_text(json.dumps(doc))
        monkeypatch.setenv(ENV_VAR, str(path))
        resolved, err = resolve_env_capsule()
        assert resolved is None
        assert "digest mismatch" in err

    def test_newer_version_skew_fails_closed(
        self, state_home, monkeypatch
    ) -> None:
        # D-A1 revised (audit H-02): an asserted capsule with an unsupported
        # schema version blocks — the version field sits outside the policy
        # digest, so a child could otherwise bump it to escape delegation.
        path = write_capsule(POLICY, ORIGIN)
        doc = json.loads(path.read_text())
        doc["fettle_capsule"] = 99
        path.write_text(json.dumps(doc))
        monkeypatch.setenv(ENV_VAR, str(path))
        resolved, err = resolve_env_capsule()
        assert resolved is None
        assert "schema version 99" in err
        assert last_error() == err

    def test_huge_version_with_bad_digest_fails_closed(
        self, state_home, monkeypatch
    ) -> None:
        # The audit's exact reproduction: version=999 + garbage digest must
        # never be treated as benign skew.
        path = state_home / "evil.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fettle_capsule": 999, "digest": "invalid"}))
        monkeypatch.setenv(ENV_VAR, str(path))
        resolved, err = resolve_env_capsule()
        assert resolved is None
        assert err != ""


class TestMonotonicMerge:
    """D-A2 semantics: children may only tighten, never loosen."""

    def test_mode_child_cannot_weaken(self) -> None:
        cap = {"gates": {"lint": {"mode": "enforce"}}}
        loc = {"gates": {"lint": {"mode": "advisory"}}}
        eff, ignored = merge_for_child(cap, loc)
        assert eff["gates"]["lint"]["mode"] == "enforce"
        assert ignored and ignored[0]["key"] == "gates.lint.mode"

    def test_mode_child_may_tighten(self) -> None:
        cap = {"gates": {"lint": {"mode": "advisory"}}}
        loc = {"gates": {"lint": {"mode": "enforce"}}}
        eff, ignored = merge_for_child(cap, loc)
        assert eff["gates"]["lint"]["mode"] == "enforce"
        assert ignored == []

    def test_enabled_true_wins_both_directions(self) -> None:
        cap = {"gates": {"tdd": {"enabled": True}}}
        loc = {"gates": {"tdd": {"enabled": False}}}
        eff, ignored = merge_for_child(cap, loc)
        assert eff["gates"]["tdd"]["enabled"] is True
        assert ignored

        cap2 = {"gates": {"tdd": {"enabled": False}}}
        loc2 = {"gates": {"tdd": {"enabled": True}}}
        eff2, ignored2 = merge_for_child(cap2, loc2)
        assert eff2["gates"]["tdd"]["enabled"] is True
        assert ignored2 == []

    def test_directed_numeric_min(self) -> None:
        cap = {"gates": {"complexity": {"max_cyclomatic": 8}}}
        loc = {"gates": {"complexity": {"max_cyclomatic": 15}}}
        eff, ignored = merge_for_child(cap, loc)
        assert eff["gates"]["complexity"]["max_cyclomatic"] == 8
        assert ignored

    def test_directed_numeric_max(self) -> None:
        cap = {"gates": {"coverage": {"threshold": 90}}}
        loc = {"gates": {"coverage": {"threshold": 60}}}
        eff, _ = merge_for_child(cap, loc)
        assert eff["gates"]["coverage"]["threshold"] == 90
        # child tightening upward is kept
        eff2, ignored2 = merge_for_child(
            {"gates": {"coverage": {"threshold": 60}}},
            {"gates": {"coverage": {"threshold": 90}}})
        assert eff2["gates"]["coverage"]["threshold"] == 90
        assert ignored2 == []

    def test_loosening_list_capsule_wins(self) -> None:
        # D-A2: a child ADDING exempt_paths weakens policy → capsule wins.
        cap = {"gates": {"tdd": {"exempt_paths": ["docs/**"]}}}
        loc = {"gates": {"tdd": {"exempt_paths": ["docs/**", "src/**"]}}}
        eff, ignored = merge_for_child(cap, loc)
        assert eff["gates"]["tdd"]["exempt_paths"] == ["docs/**"]
        assert ignored and ignored[0]["key"] == "gates.tdd.exempt_paths"

    def test_plumbing_keys_stay_local(self) -> None:
        # D-A5: machine-local paths must not leak across checkouts.
        cap = {"paths": {"trace_dir": "/parent/checkout/.fettle"},
               "worktrees": {"root": "/parent/wts", "require": True}}
        loc = {"paths": {"trace_dir": ".fettle"},
               "worktrees": {"root": ".fettle/worktrees", "require": False}}
        eff, ignored = merge_for_child(cap, loc)
        assert eff["paths"]["trace_dir"] == ".fettle"
        assert eff["worktrees"]["root"] == ".fettle/worktrees"
        # worktrees.require is POLICY (not plumbing) → capsule wins
        assert eff["worktrees"]["require"] is True

    def test_capsule_silent_keys_keep_local(self) -> None:
        # A newer fettle in the child knows gates the capsule doesn't.
        cap = {"gates": {"lint": {"mode": "advisory"}}}
        loc = {"gates": {"lint": {"mode": "advisory"},
                         "brand_new_gate": {"enabled": True, "mode": "enforce"}}}
        eff, ignored = merge_for_child(cap, loc)
        assert eff["gates"]["brand_new_gate"]["mode"] == "enforce"
        assert ignored == []

    def test_string_conflict_capsule_wins(self) -> None:
        cap = {"extends": {"url": "https://org/policy.toml", "sha256": "aa"}}
        loc = {"extends": {"url": "https://evil/policy.toml", "sha256": "bb"}}
        eff, ignored = merge_for_child(cap, loc)
        assert eff["extends"]["url"] == "https://org/policy.toml"
        assert len(ignored) == 2

    def test_findings_are_capped(self) -> None:
        cap = {"x": {f"k{i}": f"cap{i}" for i in range(40)}}
        loc = {"x": {f"k{i}": f"loc{i}" for i in range(40)}}
        _, ignored = merge_for_child(cap, loc)
        assert len(ignored) == 20

    # P52: role merge semantics

    def test_role_child_cannot_widen(self) -> None:
        cap = {"role": "implementer"}
        loc = {"role": "solo"}
        eff, ignored = merge_for_child(cap, loc)
        assert eff["role"] == "implementer"
        assert ignored and ignored[0]["key"] == "role"

    def test_role_child_may_narrow(self) -> None:
        cap = {"role": "solo"}
        loc = {"role": "tester"}
        eff, ignored = merge_for_child(cap, loc)
        assert eff["role"] == "tester"
        assert ignored == []

    def test_role_same_rank_keeps_local(self) -> None:
        cap = {"role": "implementer"}
        loc = {"role": "tester"}
        eff, ignored = merge_for_child(cap, loc)
        assert eff["role"] == "tester"
        assert ignored == []

    def test_role_reviewer_cannot_be_widened(self) -> None:
        cap = {"role": "reviewer"}
        loc = {"role": "implementer"}
        eff, ignored = merge_for_child(cap, loc)
        assert eff["role"] == "reviewer"
        assert ignored
