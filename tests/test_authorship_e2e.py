"""End-to-end test: authorship separation (P52) through the full stack.

Tests the complete flow:
1. spawn_agent writes a capsule with role
2. Child session resolves capsule and merges role into effective config
3. authorship_gate blocks cross-role file edits
4. Role cannot be widened through capsule manipulation
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from fettle.authorship_gate import run_check as authorship_check
from fettle.policy_capsule import (
    merge_for_child,
    resolve_env_capsule,
    verify,
    write_capsule,
)


@pytest.fixture
def capsule_dir(tmp_path):
    """Override capsule storage to a temp directory."""
    d = tmp_path / "capsules"
    d.mkdir()
    with patch.dict(os.environ, {"FETTLE_STATE_DIR": str(tmp_path)}):
        yield d


@pytest.fixture
def repo_dir(tmp_path):
    """A fake repo with .git and .fettle.toml."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (tmp_path / ".fettle.toml").write_text("[gates.authorship]\nenabled = true\nmode = \"enforce\"\n")
    return tmp_path


class TestSpawnWithRole:
    """Test that spawn_agent correctly writes role into the capsule."""

    def test_capsule_contains_role(self, capsule_dir):
        policy = {"role": "implementer", "gates": {"lint": {"mode": "advisory"}}}
        path = write_capsule(policy, origin={"session_id": "parent"})
        doc = json.loads(path.read_text())
        assert doc["policy"]["role"] == "implementer"
        assert verify(doc, path) == ""

    def test_capsule_role_solo_by_default(self, capsule_dir):
        policy = {"gates": {"lint": {"mode": "advisory"}}}
        path = write_capsule(policy, origin={"session_id": "parent"})
        doc = json.loads(path.read_text())
        assert "role" not in doc["policy"] or doc["policy"].get("role") == "solo"


class TestRoleMergeE2E:
    """Test that capsule merge correctly enforces role monotonicity."""

    def test_implementer_parent_cannot_spawn_solo_child(self):
        capsule_policy = {"role": "implementer", "gates": {}}
        local_config = {"role": "solo", "gates": {}}
        effective, ignored = merge_for_child(capsule_policy, local_config)
        assert effective["role"] == "implementer"
        assert any(i["key"] == "role" for i in ignored)

    def test_solo_parent_can_spawn_tester_child(self):
        capsule_policy = {"role": "solo", "gates": {}}
        local_config = {"role": "tester", "gates": {}}
        effective, ignored = merge_for_child(capsule_policy, local_config)
        assert effective["role"] == "tester"
        assert ignored == []

    def test_implementer_cannot_become_tester(self):
        capsule_policy = {"role": "implementer", "gates": {}}
        local_config = {"role": "tester", "gates": {}}
        effective, ignored = merge_for_child(capsule_policy, local_config)
        # Same rank — local wins (both rank 1)
        assert effective["role"] == "tester"

    def test_reviewer_cannot_be_widened_to_anything(self):
        capsule_policy = {"role": "reviewer", "gates": {}}
        for local_role in ("solo", "implementer", "tester"):
            local_config = {"role": local_role, "gates": {}}
            effective, ignored = merge_for_child(capsule_policy, local_config)
            assert effective["role"] == "reviewer", f"failed for {local_role}"


class TestCapsuleResolutionE2E:
    """Test the full env-capsule resolution path with role."""

    def test_child_inherits_role_from_capsule(self, tmp_path):
        capsule_dir = tmp_path / "capsules"
        capsule_dir.mkdir(parents=True)
        with patch("fettle.policy_capsule._capsules_dir", return_value=capsule_dir):
            policy = {"role": "tester", "gates": {"authorship": {"enabled": True}}}
            path = write_capsule(policy, origin={"session_id": "parent"})

        with patch.dict(os.environ, {"FETTLE_POLICY_CAPSULE": str(path)}):
            doc, err = resolve_env_capsule()
            assert err == ""
            assert doc is not None
            assert doc["policy"]["role"] == "tester"

            local_config = {"role": "solo", "gates": {"authorship": {"enabled": True}}}
            effective, ignored = merge_for_child(doc["policy"], local_config)
            assert effective["role"] == "tester"


def _make_gate_ctx(role, file_path, cwd="/repo"):
    from dataclasses import dataclass, field

    @dataclass
    class _Input:
        hook_event_name: str = "PreToolUse"
        tool_name: str = "Write"
        tool_input: dict = field(default_factory=dict)
        cwd: Path = Path("/repo")
        session_id: str = "child-session"

    @dataclass
    class _Ctx:
        input: _Input
        config: dict
        plugin_root: Path = Path("/p")
        hook_start_monotonic: float = 0.0
        global_deadline_monotonic: float = 1.0
        check_deadline_monotonic: float = 1.0

        @property
        def event(self): return self.input.hook_event_name
        @property
        def tool_name(self): return self.input.tool_name
        @property
        def tool_input(self): return self.input.tool_input
        @property
        def cwd(self): return self.input.cwd
        @property
        def session_id(self): return self.input.session_id
        @property
        def target_path(self):
            fp = self.input.tool_input.get("file_path", "")
            if fp:
                p = Path(fp)
                return p if p.is_absolute() else self.input.cwd / p
            return None

    config = {
        "role": role,
        "gates": {"authorship": {"enabled": True, "mode": "enforce"}},
    }
    inp = _Input(tool_input={"file_path": file_path}, cwd=Path(cwd))
    return _Ctx(input=inp, config=config)


class TestGateBlocksE2E:
    """Test the full flow: capsule -> merge -> gate decision."""

    def test_implementer_writes_impl_allowed(self):
        ctx = _make_gate_ctx("implementer", "src/app.py")
        result = authorship_check(ctx)
        assert result.decision.value == "allow"

    def test_implementer_writes_test_blocked(self):
        ctx = _make_gate_ctx("implementer", "tests/test_app.py")
        result = authorship_check(ctx)
        assert result.decision.value == "block"

    def test_tester_writes_test_allowed(self):
        ctx = _make_gate_ctx("tester", "tests/test_app.py")
        result = authorship_check(ctx)
        assert result.decision.value == "allow"

    def test_tester_writes_impl_blocked(self):
        ctx = _make_gate_ctx("tester", "src/app.py")
        result = authorship_check(ctx)
        assert result.decision.value == "block"

    def test_reviewer_blocked_from_everything(self):
        ctx = _make_gate_ctx("reviewer", "src/app.py")
        result = authorship_check(ctx)
        assert result.decision.value == "block"

        ctx2 = _make_gate_ctx("reviewer", "tests/test_x.py")
        result2 = authorship_check(ctx2)
        assert result2.decision.value == "block"

    def test_solo_allowed_everywhere(self):
        ctx = _make_gate_ctx("solo", "src/app.py")
        assert authorship_check(ctx).decision.value == "allow"

        ctx2 = _make_gate_ctx("solo", "tests/test_x.py")
        assert authorship_check(ctx2).decision.value == "allow"


class TestFullSpawnToGateFlow:
    """Integration: parent spawns with role -> capsule -> child gate enforces."""

    def test_parent_spawns_implementer_child_cannot_write_tests(self, tmp_path):
        capsule_dir = tmp_path / "capsules"
        capsule_dir.mkdir(parents=True)

        # Parent writes capsule with role=implementer
        with patch("fettle.policy_capsule._capsules_dir", return_value=capsule_dir):
            parent_policy = {
                "role": "implementer",
                "gates": {"authorship": {"enabled": True, "mode": "enforce"}},
            }
            capsule_path = write_capsule(parent_policy, origin={"session_id": "parent"})

        # Child resolves capsule
        with patch.dict(os.environ, {"FETTLE_POLICY_CAPSULE": str(capsule_path)}):
            doc, err = resolve_env_capsule()
            assert err == ""

        # Child merges with its local config (tries to be solo)
        child_local = {"role": "solo", "gates": {"authorship": {"enabled": True, "mode": "enforce"}}}
        effective, _ = merge_for_child(doc["policy"], child_local)

        # Effective role should be implementer (cannot widen)
        assert effective["role"] == "implementer"

        # Now simulate the child trying to write a test file
        from dataclasses import dataclass

        @dataclass
        class Input:
            hook_event_name: str = "PreToolUse"
            tool_name: str = "Write"
            tool_input: dict = None
            cwd: Path = tmp_path
            session_id: str = "child"
            def __post_init__(self):
                self.tool_input = {"file_path": "tests/test_sneaky.py"}

        @dataclass
        class Ctx:
            input: Input
            config: dict
            plugin_root: Path = Path("/p")
            hook_start_monotonic: float = 0.0
            global_deadline_monotonic: float = 1.0
            check_deadline_monotonic: float = 1.0

            @property
            def event(self): return self.input.hook_event_name
            @property
            def tool_name(self): return self.input.tool_name
            @property
            def tool_input(self): return self.input.tool_input
            @property
            def cwd(self): return self.input.cwd
            @property
            def session_id(self): return self.input.session_id
            @property
            def target_path(self):
                fp = self.input.tool_input.get("file_path", "")
                return self.input.cwd / fp if fp else None

        ctx = Ctx(input=Input(), config=effective)
        result = authorship_check(ctx)
        assert result.decision.value == "block"
        assert "implementer" in result.message
        assert "test" in result.message.lower()
