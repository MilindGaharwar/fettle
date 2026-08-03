"""Tests for fettle.claims_gate — claim-before-work gate (Stage 4, S4.3)."""

from unittest.mock import patch

from fettle.claims_gate import run_check
from fettle.dispatcher_types import Decision, HookContext, HookInput


def _ctx(tmp_path, config=None):
    inp = HookInput(
        hook_event_name="PostToolUse",
        tool_name="Write",
        tool_input={"file_path": str(tmp_path / "src" / "main.py")},
        cwd=tmp_path,
        session_id="test-session",
        raw={},
    )
    return HookContext(
        input=inp,
        config=config or {"gates": {"claims": {"enabled": True, "mode": "advisory"}},
                          "worktrees": {"root": ".fettle/worktrees", "require": False,
                                        "exempt_paths": ["docs/**", "**/*.md"]}},
        plugin_root=tmp_path,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=9999.0,
    )


class TestClaimsGateDisabled:
    def test_disabled_allows(self, tmp_path):
        ctx = _ctx(tmp_path, config={"gates": {"claims": {"enabled": False}},
                                     "worktrees": {}})
        assert run_check(ctx).decision == Decision.ALLOW


class TestClaimsGateMainWorktree:
    def test_main_worktree_no_require_allows(self, tmp_path):
        with patch("fettle.worktrees.is_linked_worktree", return_value=False):
            ctx = _ctx(tmp_path)
            assert run_check(ctx).decision == Decision.ALLOW

    def test_main_worktree_require_on_non_exempt_advisory(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("x = 1")
        config = {
            "gates": {"claims": {"enabled": True, "mode": "advisory"}},
            "worktrees": {"root": ".fettle/worktrees", "require": True,
                          "exempt_paths": ["docs/**", "**/*.md"]},
        }
        with patch("fettle.worktrees.is_linked_worktree", return_value=False), \
             patch("fettle.paths.find_repo_root", return_value=tmp_path):
            ctx = _ctx(tmp_path, config=config)
            result = run_check(ctx)
            assert result.decision == Decision.ADVISORY
            assert "require" in result.message

    def test_main_worktree_require_exempt_md_allows(self, tmp_path):
        config = {
            "gates": {"claims": {"enabled": True, "mode": "enforce"}},
            "worktrees": {"root": ".fettle/worktrees", "require": True,
                          "exempt_paths": ["docs/**", "**/*.md"]},
        }
        inp = HookInput(
            hook_event_name="PostToolUse",
            tool_name="Write",
            tool_input={"file_path": str(tmp_path / "README.md")},
            cwd=tmp_path,
            session_id="test",
            raw={},
        )
        ctx = HookContext(
            input=inp,
            config=config,
            plugin_root=tmp_path,
            hook_start_monotonic=0.0,
            global_deadline_monotonic=9999.0,
        )
        (tmp_path / ".git").mkdir()
        (tmp_path / "README.md").write_text("# Hi")
        with patch("fettle.worktrees.is_linked_worktree", return_value=False), \
             patch("fettle.paths.find_repo_root", return_value=tmp_path):
            result = run_check(ctx)
            assert result.decision == Decision.ALLOW


class TestClaimsGateLinkedWorktree:
    def test_non_fettle_branch_allows(self, tmp_path):
        with patch("fettle.worktrees.is_linked_worktree", return_value=True), \
             patch("fettle.worktrees._git", return_value=("feature/xyz\n", "")):
            ctx = _ctx(tmp_path)
            assert run_check(ctx).decision == Decision.ALLOW

    def test_fettle_branch_no_claim_advisory(self, tmp_path):
        with patch("fettle.worktrees.is_linked_worktree", return_value=True), \
             patch("fettle.worktrees._git", side_effect=[
                 ("fettle/my-item\n", ""),
                 (str(tmp_path) + "\n", ""),
             ]), \
             patch("fettle.work_items.claim_for_worktree", return_value=""):
            ctx = _ctx(tmp_path)
            result = run_check(ctx)
            assert result.decision == Decision.ADVISORY
            assert "my-item" in result.message

    def test_fettle_branch_with_claim_allows(self, tmp_path):
        with patch("fettle.worktrees.is_linked_worktree", return_value=True), \
             patch("fettle.worktrees._git", side_effect=[
                 ("fettle/my-item\n", ""),
                 (str(tmp_path) + "\n", ""),
             ]), \
             patch("fettle.work_items.claim_for_worktree", return_value="my-item"):
            ctx = _ctx(tmp_path)
            assert run_check(ctx).decision == Decision.ALLOW

    def test_enforce_mode_blocks(self, tmp_path):
        config = {"gates": {"claims": {"enabled": True, "mode": "enforce"}},
                  "worktrees": {"root": ".fettle/worktrees", "require": False}}
        with patch("fettle.worktrees.is_linked_worktree", return_value=True), \
             patch("fettle.worktrees._git", side_effect=[
                 ("fettle/item-x\n", ""),
                 (str(tmp_path) + "\n", ""),
             ]), \
             patch("fettle.work_items.claim_for_worktree", return_value=""):
            ctx = _ctx(tmp_path, config=config)
            result = run_check(ctx)
            assert result.decision == Decision.BLOCK
