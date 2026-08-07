"""Tests for fettle.authorship_gate — role-based file authority (P52)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest

from fettle.authorship_gate import ROLE_RANK, VALID_ROLES, run_check


@dataclass
class FakeInput:
    hook_event_name: str = "PreToolUse"
    tool_name: str = "Write"
    tool_input: dict = None
    cwd: Path = Path("/repo")
    session_id: str = "test-session"

    def __post_init__(self):
        if self.tool_input is None:
            self.tool_input = {}


@dataclass
class FakeContext:
    input: FakeInput
    config: dict
    plugin_root: Path = Path("/plugin")
    hook_start_monotonic: float = 0.0
    global_deadline_monotonic: float = 1.0
    check_deadline_monotonic: float = 1.0

    @property
    def event(self):
        return self.input.hook_event_name

    @property
    def tool_name(self):
        return self.input.tool_name

    @property
    def tool_input(self):
        return self.input.tool_input

    @property
    def cwd(self):
        return self.input.cwd

    @property
    def session_id(self):
        return self.input.session_id

    @property
    def target_path(self):
        fp = self.input.tool_input.get("file_path", "")
        if fp:
            p = Path(fp)
            return p if p.is_absolute() else self.cwd / p
        return None


def _ctx(role="solo", file_path="src/app.py", enabled=True, mode="enforce"):
    return FakeContext(
        input=FakeInput(tool_input={"file_path": file_path}),
        config={
            "role": role,
            "gates": {"authorship": {"enabled": enabled, "mode": mode}},
        },
    )


class TestGateDisabled:
    def test_disabled_allows_everything(self):
        ctx = _ctx(role="implementer", file_path="tests/test_foo.py", enabled=False)
        result = run_check(ctx)
        assert result.decision.value == "allow"

    def test_missing_config_allows(self):
        ctx = FakeContext(
            input=FakeInput(tool_input={"file_path": "tests/test_x.py"}),
            config={"role": "implementer"},
        )
        result = run_check(ctx)
        assert result.decision.value == "allow"


class TestSoloRole:
    def test_solo_can_edit_implementation(self):
        result = run_check(_ctx(role="solo", file_path="src/app.py"))
        assert result.decision.value == "allow"

    def test_solo_can_edit_tests(self):
        result = run_check(_ctx(role="solo", file_path="tests/test_app.py"))
        assert result.decision.value == "allow"

    def test_default_role_is_solo(self):
        ctx = FakeContext(
            input=FakeInput(tool_input={"file_path": "tests/test_x.py"}),
            config={"gates": {"authorship": {"enabled": True, "mode": "enforce"}}},
        )
        result = run_check(ctx)
        assert result.decision.value == "allow"


class TestImplementerRole:
    def test_can_edit_implementation(self):
        result = run_check(_ctx(role="implementer", file_path="src/app.py"))
        assert result.decision.value == "allow"

    def test_blocked_from_test_files(self):
        result = run_check(_ctx(role="implementer", file_path="tests/test_app.py"))
        assert result.decision.value == "block"

    def test_blocked_from_test_prefix(self):
        result = run_check(_ctx(role="implementer", file_path="test_utils.py"))
        assert result.decision.value == "block"

    def test_advisory_mode_warns_not_blocks(self):
        result = run_check(_ctx(role="implementer", file_path="tests/test_x.py", mode="advisory"))
        assert result.decision.value == "advisory"

    def test_can_edit_config_files(self):
        result = run_check(_ctx(role="implementer", file_path="pyproject.toml"))
        assert result.decision.value == "allow"

    def test_can_edit_unknown_files(self):
        result = run_check(_ctx(role="implementer", file_path="README.md"))
        assert result.decision.value == "allow"


class TestTesterRole:
    def test_can_edit_tests(self):
        result = run_check(_ctx(role="tester", file_path="tests/test_app.py"))
        assert result.decision.value == "allow"

    def test_blocked_from_implementation(self):
        result = run_check(_ctx(role="tester", file_path="src/app.py"))
        assert result.decision.value == "block"

    def test_blocked_from_py_implementation(self):
        result = run_check(_ctx(role="tester", file_path="fettle/dispatcher.py"))
        assert result.decision.value == "block"

    def test_advisory_mode_warns_not_blocks(self):
        result = run_check(_ctx(role="tester", file_path="src/main.py", mode="advisory"))
        assert result.decision.value == "advisory"

    def test_can_edit_config_files(self):
        result = run_check(_ctx(role="tester", file_path=".fettle.toml"))
        assert result.decision.value == "allow"


class TestReviewerRole:
    def test_blocked_from_any_file(self):
        result = run_check(_ctx(role="reviewer", file_path="src/app.py"))
        assert result.decision.value == "block"

    def test_blocked_from_tests_too(self):
        result = run_check(_ctx(role="reviewer", file_path="tests/test_app.py"))
        assert result.decision.value == "block"

    def test_advisory_mode_warns(self):
        result = run_check(_ctx(role="reviewer", file_path="src/x.py", mode="advisory"))
        assert result.decision.value == "advisory"


class TestNoTargetPath:
    def test_no_file_path_allows(self):
        ctx = _ctx(role="implementer", file_path="")
        result = run_check(ctx)
        assert result.decision.value == "allow"


class TestRoleRank:
    def test_all_valid_roles_have_ranks(self):
        for role in VALID_ROLES:
            assert role in ROLE_RANK

    def test_solo_is_least_restrictive(self):
        assert ROLE_RANK["solo"] == 0

    def test_reviewer_is_most_restrictive(self):
        assert ROLE_RANK["reviewer"] == max(ROLE_RANK.values())

    def test_implementer_and_tester_same_rank(self):
        assert ROLE_RANK["implementer"] == ROLE_RANK["tester"]
