"""Tests for fettle.tla_sync — TLA+ spec staleness advisory."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import fettle.tla_sync as tla_sync
from fettle.tla_sync import run_check


@dataclass
class FakeInput:
    hook_event_name: str = "PostToolUse"
    tool_name: str = "Edit"
    tool_input: dict = None
    cwd: Path = Path("/repo")
    session_id: str = "test-session"

    def __post_init__(self):
        if self.tool_input is None:
            self.tool_input = {}


@dataclass
class FakeContext:
    input: FakeInput
    config: dict = None
    plugin_root: Path = Path("/plugin")
    hook_start_monotonic: float = 0.0
    global_deadline_monotonic: float = 1.0
    check_deadline_monotonic: float = 1.0

    def __post_init__(self):
        if self.config is None:
            self.config = {}

    @property
    def cwd(self):
        return self.input.cwd

    @property
    def target_path(self):
        fp = self.input.tool_input.get("file_path", "")
        if fp:
            p = Path(fp)
            return p if p.is_absolute() else self.input.cwd / p
        return None

    @property
    def session_id(self):
        return self.input.session_id


def setup_function():
    tla_sync._advised_this_session.clear()


class TestTlaSync:
    def test_advises_on_verified_file(self):
        ctx = FakeContext(input=FakeInput(
            tool_input={"file_path": "fettle/policy_capsule.py"},
            session_id="s1",
        ))
        result = run_check(ctx)
        assert result.decision.value == "advisory"
        assert "PolicyCapsule" in result.message

    def test_allows_unverified_file(self):
        ctx = FakeContext(input=FakeInput(
            tool_input={"file_path": "fettle/dispatcher.py"},
            session_id="s2",
        ))
        result = run_check(ctx)
        assert result.decision.value == "allow"

    def test_once_per_session_per_spec(self):
        ctx = FakeContext(input=FakeInput(
            tool_input={"file_path": "fettle/policy_capsule.py"},
            session_id="s3",
        ))
        r1 = run_check(ctx)
        assert r1.decision.value == "advisory"
        r2 = run_check(ctx)
        assert r2.decision.value == "allow"

    def test_different_spec_fires_separately(self):
        ctx1 = FakeContext(input=FakeInput(
            tool_input={"file_path": "fettle/policy_capsule.py"},
            session_id="s4",
        ))
        ctx2 = FakeContext(input=FakeInput(
            tool_input={"file_path": "fettle/work_items.py"},
            session_id="s4",
        ))
        r1 = run_check(ctx1)
        r2 = run_check(ctx2)
        assert r1.decision.value == "advisory"
        assert r2.decision.value == "advisory"

    def test_ignores_pre_tool_use(self):
        ctx = FakeContext(input=FakeInput(
            hook_event_name="PreToolUse",
            tool_input={"file_path": "fettle/policy_capsule.py"},
            session_id="s5",
        ))
        result = run_check(ctx)
        assert result.decision.value == "allow"

    def test_no_target_allows(self):
        ctx = FakeContext(input=FakeInput(
            tool_input={},
            session_id="s6",
        ))
        result = run_check(ctx)
        assert result.decision.value == "allow"


class TestTlaSyncStop:
    def test_stop_no_edits_allows(self, tmp_path):
        tla_sync._edited_verified_files.clear()
        ctx = FakeContext(input=FakeInput(
            hook_event_name="Stop",
            tool_input={},
            cwd=tmp_path,
            session_id="stop1",
        ))
        result = run_check(ctx)
        assert result.decision.value == "allow"

    def test_stop_stale_spec_advises(self, tmp_path):
        tla_sync._edited_verified_files.clear()
        src = tmp_path / "fettle" / "policy_capsule.py"
        spec = tmp_path / "specs" / "tla" / "PolicyCapsule.tla"
        src.parent.mkdir(parents=True)
        spec.parent.mkdir(parents=True)
        spec.write_text("old spec")
        time.sleep(0.05)
        src.write_text("new code")

        tla_sync._edited_verified_files.add("fettle/policy_capsule.py")
        ctx = FakeContext(input=FakeInput(
            hook_event_name="Stop",
            tool_input={},
            cwd=tmp_path,
            session_id="stop2",
        ))
        result = run_check(ctx)
        assert result.decision.value == "advisory"
        assert "PolicyCapsule.tla" in result.message

    def test_stop_fresh_spec_allows(self, tmp_path):
        tla_sync._edited_verified_files.clear()
        src = tmp_path / "fettle" / "policy_capsule.py"
        spec = tmp_path / "specs" / "tla" / "PolicyCapsule.tla"
        src.parent.mkdir(parents=True)
        spec.parent.mkdir(parents=True)
        src.write_text("code")
        time.sleep(0.05)
        spec.write_text("updated spec")

        tla_sync._edited_verified_files.add("fettle/policy_capsule.py")
        ctx = FakeContext(input=FakeInput(
            hook_event_name="Stop",
            tool_input={},
            cwd=tmp_path,
            session_id="stop3",
        ))
        result = run_check(ctx)
        assert result.decision.value == "allow"
