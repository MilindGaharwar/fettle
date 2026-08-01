"""Tests for fettle.bdd_gate — spec scenario coverage gate (Stage 3, S3.3)."""

from __future__ import annotations

from pathlib import Path

from fettle.bdd_gate import run_check
from fettle.dispatcher_types import Decision, HookContext, HookInput

SPEC = """\
---
fettle-spec: v1
id: checkout-flow
status: active
scope:
  - src/checkout/**
---

## Requirements
- R1. Cart total recalculates.

## Scenarios
### S1. total updates (traces R1)
- Given a cart
- When quantity changes
- Then the total updates
"""


def _ctx(repo: Path, file_path: str, *, enabled: bool = True,
         mode: str = "advisory", event: str = "PostToolUse") -> HookContext:
    hook_input = HookInput(
        hook_event_name=event,
        tool_name="Edit",
        tool_input={"file_path": str(repo / file_path)},
        cwd=repo,
        session_id="test-bdd",
        raw={},
    )
    return HookContext(
        input=hook_input,
        config={"gates": {"bdd": {"enabled": enabled, "mode": mode}}},
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=999999.0,
    )


def _repo(tmp_path: Path, spec: str = SPEC) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "checkout").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs" / "checkout.md").write_text(spec)
    return tmp_path


def test_disabled_allows(tmp_path):
    repo = _repo(tmp_path)
    result = run_check(_ctx(repo, "src/checkout/cart.py", enabled=False))
    assert result.decision == Decision.ALLOW


def test_file_outside_scope_allows(tmp_path):
    repo = _repo(tmp_path)
    result = run_check(_ctx(repo, "src/other/thing.py"))
    assert result.decision == Decision.ALLOW


def test_uncovered_scenario_advisory(tmp_path):
    repo = _repo(tmp_path)
    result = run_check(_ctx(repo, "src/checkout/cart.py"))
    assert result.decision == Decision.ADVISORY
    assert "checkout-flow/S1" in result.message
    assert "# traces: checkout-flow/S1" in result.message  # actionable fix


def test_covered_scenario_allows(tmp_path):
    repo = _repo(tmp_path)
    (repo / "tests" / "test_cart.py").write_text(
        "# traces: checkout-flow/S1\ndef test_total():\n    pass\n")
    result = run_check(_ctx(repo, "src/checkout/cart.py"))
    assert result.decision == Decision.ALLOW


def test_enforce_mode_blocks(tmp_path):
    repo = _repo(tmp_path)
    result = run_check(_ctx(repo, "src/checkout/cart.py", mode="enforce"))
    assert result.decision == Decision.BLOCK


def test_draft_spec_does_not_govern(tmp_path):
    repo = _repo(tmp_path, SPEC.replace("status: active", "status: draft"))
    result = run_check(_ctx(repo, "src/checkout/cart.py"))
    assert result.decision == Decision.ALLOW


def test_no_file_path_allows(tmp_path):
    repo = _repo(tmp_path)
    ctx = _ctx(repo, "src/checkout/cart.py")
    ctx.input.tool_input.clear()
    assert run_check(ctx).decision == Decision.ALLOW


def test_file_outside_project_allows(tmp_path):
    repo = _repo(tmp_path)
    hook_input = HookInput(
        hook_event_name="PostToolUse", tool_name="Edit",
        tool_input={"file_path": "/elsewhere/cart.py"},
        cwd=repo, session_id="test-bdd", raw={},
    )
    ctx = HookContext(
        input=hook_input,
        config={"gates": {"bdd": {"enabled": True, "mode": "advisory"}}},
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0, global_deadline_monotonic=999999.0,
    )
    assert run_check(ctx).decision == Decision.ALLOW


def test_registered_in_dispatcher(tmp_path):
    from fettle.dispatcher_registry import CHECKS

    spec = next(c for c in CHECKS if c.name == "bdd_gate")
    assert spec.events == frozenset({"PostToolUse"})
    assert spec.tools == frozenset({"Write", "Edit"})


def test_mode_enum_registered():
    from fettle.config_schema import MODE_ENUMS

    assert MODE_ENUMS["gates.bdd.mode"] == frozenset({"advisory", "enforce"})
