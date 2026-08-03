"""Tests for fettle.capsule_guard — fail-closed tamper check (Stage A, A3)."""

import json

from fettle.capsule_guard import run_check
from fettle.dispatcher_types import Decision, HookContext, HookInput


def _ctx(tmp_path, monkeypatch, capsule_env=""):
    monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
    if capsule_env:
        monkeypatch.setenv("FETTLE_POLICY_CAPSULE", capsule_env)
    else:
        monkeypatch.delenv("FETTLE_POLICY_CAPSULE", raising=False)
    inp = HookInput(
        hook_event_name="PreToolUse",
        tool_name="Write",
        tool_input={"file_path": "/tmp/x.py"},
        cwd=tmp_path,
        session_id="test-session",
        raw={},
    )
    return HookContext(
        input=inp,
        config={"gates": {}},
        plugin_root=tmp_path,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=9999.0,
    )


class TestCapsuleGuard:
    def test_no_env_allows(self, tmp_path, monkeypatch):
        ctx = _ctx(tmp_path, monkeypatch)
        result = run_check(ctx)
        assert result.decision == Decision.ALLOW

    def test_missing_capsule_blocks(self, tmp_path, monkeypatch):
        ctx = _ctx(tmp_path, monkeypatch, capsule_env="/nonexistent/capsule.json")
        result = run_check(ctx)
        assert result.decision == Decision.BLOCK
        assert "tampered or missing" in result.hook_specific_output.get("permissionDecisionReason", "")

    def test_tampered_capsule_blocks(self, tmp_path, monkeypatch):
        capsule_path = tmp_path / "bad.json"
        capsule_path.write_text(json.dumps({
            "fettle_capsule": 1,
            "digest": "0000000000000000",
            "policy": {"gates": {}},
            "origin": {},
            "lineage": [],
        }))
        ctx = _ctx(tmp_path, monkeypatch, capsule_env=str(capsule_path))
        result = run_check(ctx)
        assert result.decision == Decision.BLOCK

    def test_valid_capsule_allows(self, tmp_path, monkeypatch):
        from fettle.policy_capsule import write_capsule
        monkeypatch.setenv("FETTLE_STATE_DIR", str(tmp_path / "state"))
        policy = {"gates": {"lint": {"enabled": True}}}
        path = write_capsule(policy, {"repo": "t", "repo_root": "/t",
                                       "session_id": "p", "created_at": "x",
                                       "fettle_version": "1.0"})
        ctx = _ctx(tmp_path, monkeypatch, capsule_env=str(path))
        result = run_check(ctx)
        assert result.decision == Decision.ALLOW

    def test_newer_version_capsule_blocks(self, tmp_path, monkeypatch):
        # Audit H-02: asserted capsule with unsupported schema version is
        # fail-closed — the version field is outside the policy digest.
        from fettle.policy_capsule import canonical_digest
        policy = {"gates": {}}
        capsule_path = tmp_path / "future.json"
        capsule_path.write_text(json.dumps({
            "fettle_capsule": 999,
            "digest": canonical_digest(policy),
            "policy": policy,
            "origin": {},
            "lineage": [],
        }))
        ctx = _ctx(tmp_path, monkeypatch, capsule_env=str(capsule_path))
        result = run_check(ctx)
        assert result.decision == Decision.BLOCK
        assert "schema version 999" in result.message
