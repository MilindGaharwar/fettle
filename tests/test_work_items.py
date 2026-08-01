"""Tests for fettle.work_items + [gates.claims] — WP5 (Stage 4, S4.3)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from fettle.dispatcher_types import Decision, HookContext, HookInput
from fettle.work_items import (
    claim_for_worktree,
    claim_item,
    discover_work_items,
    is_work_item_text,
    lint_work_items,
    load_claims,
    parse_work_item,
    release_item,
)
from fettle.worktrees import create_worktree

CLI = [sys.executable, "-m", "fettle.cli"]

VALID_ITEM = """\
---
fettle-work-item: v1
id: checkout-totals
status: open
scope:
  - src/checkout/**
spec: checkout-flow
---

# Checkout totals recalculate

Detail lives here, once.
"""


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


@pytest.fixture
def repo(tmp_path):
    return _init_repo(tmp_path)


class TestFormat:
    def test_detection_by_frontmatter_key(self):
        assert is_work_item_text(VALID_ITEM)
        assert not is_work_item_text("# Just a doc\n")

    def test_parse_valid(self):
        item, findings = parse_work_item(VALID_ITEM, "docs/work/items/checkout-totals.md")
        assert item is not None
        assert item.item_id == "checkout-totals"
        assert item.status == "open"
        assert item.scope == ["src/checkout/**"]
        assert item.spec == "checkout-flow"
        assert findings == []

    def test_invalid_status_errors(self):
        item, findings = parse_work_item(VALID_ITEM.replace("status: open", "status: wip"))
        assert item is None
        assert any("invalid status" in f["message"] for f in findings)
        assert all(f["fix"] for f in findings)

    def test_done_without_resolution_warns(self):
        item, findings = parse_work_item(VALID_ITEM.replace("status: open", "status: done"))
        assert item is not None
        assert any("no resolution" in f["message"] for f in findings)

    def test_done_with_resolution_clean(self):
        text = VALID_ITEM.replace("status: open", "status: done") + "\n## Resolution\nShipped.\n"
        item, findings = parse_work_item(text)
        assert item is not None and item.has_resolution
        assert findings == []

    def test_discover_and_duplicate_lint(self, repo):
        items_dir = repo / "docs" / "work" / "items"
        items_dir.mkdir(parents=True)
        (items_dir / "a.md").write_text(VALID_ITEM)
        (items_dir / "b.md").write_text(VALID_ITEM)  # same id — duplicate
        found = discover_work_items(str(repo))
        assert len(found) == 2
        findings = lint_work_items(str(repo))
        assert any("duplicate item id" in f["message"] for f in findings)


class TestClaims:
    def test_claim_and_release_lifecycle(self, repo):
        assert claim_item(str(repo), "item-x", "sess-1", str(repo)) == ""
        claims = load_claims(str(repo))
        assert claims["item-x"]["session_id"] == "sess-1"
        assert release_item(str(repo), "item-x") == ""
        assert load_claims(str(repo)) == {}

    def test_live_claim_refused_for_other_worktree(self, repo):
        wt, _ = create_worktree(str(repo), "wt-a", {})
        assert claim_item(str(repo), "item-y", "sess-1", str(wt)) == ""
        err = claim_item(str(repo), "item-y", "sess-2", str(repo))
        assert "claimed by session sess-1" in err

    def test_stale_claim_reclaimable(self, repo):
        gone = repo.parent / "gone-worktree"
        assert claim_item(str(repo), "item-z", "sess-1", str(gone)) == ""
        assert claim_item(str(repo), "item-z", "sess-2", str(repo)) == ""  # takeable
        assert load_claims(str(repo))["item-z"]["session_id"] == "sess-2"

    def test_same_worktree_reclaim_ok(self, repo):
        assert claim_item(str(repo), "item-w", "sess-1", str(repo)) == ""
        assert claim_item(str(repo), "item-w", "sess-1b", str(repo)) == ""

    def test_claims_shared_across_worktrees(self, repo):
        wt, _ = create_worktree(str(repo), "wt-b", {})
        assert claim_item(str(repo), "item-v", "sess-1", str(wt)) == ""
        # visible when loaded FROM the linked worktree (common-dir storage)
        assert load_claims(str(wt))["item-v"]["session_id"] == "sess-1"
        assert claim_for_worktree(str(wt), str(wt)) == "item-v"

    def test_release_unclaimed_errors(self, repo):
        assert "not claimed" in release_item(str(repo), "never-claimed")


def _gate_ctx(cwd: Path, enabled: bool = True, mode: str = "advisory") -> HookContext:
    hook_input = HookInput(
        hook_event_name="PostToolUse",
        tool_name="Edit",
        tool_input={"file_path": str(cwd / "src.py")},
        cwd=cwd,
        session_id="test-claims",
        raw={},
    )
    return HookContext(
        input=hook_input,
        config={"gates": {"claims": {"enabled": enabled, "mode": mode}}},
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=999999.0,
    )


class TestClaimsGate:
    def test_disabled_allows(self, repo):
        from fettle.claims_gate import run_check
        wt, _ = create_worktree(str(repo), "gate-a", {})
        assert run_check(_gate_ctx(wt, enabled=False)).decision == Decision.ALLOW

    def test_main_worktree_exempt(self, repo):
        from fettle.claims_gate import run_check
        assert run_check(_gate_ctx(repo)).decision == Decision.ALLOW

    def test_unclaimed_fettle_worktree_advisory(self, repo):
        from fettle.claims_gate import run_check
        wt, _ = create_worktree(str(repo), "gate-b", {})
        result = run_check(_gate_ctx(wt))
        assert result.decision == Decision.ADVISORY
        assert "fettle work claim gate-b" in result.message

    def test_claimed_worktree_allows(self, repo):
        from fettle.claims_gate import run_check
        wt, _ = create_worktree(str(repo), "gate-c", {})
        assert claim_item(str(wt), "gate-c", "sess-1", str(wt)) == ""
        assert run_check(_gate_ctx(wt)).decision == Decision.ALLOW

    def test_enforce_mode_blocks(self, repo):
        from fettle.claims_gate import run_check
        wt, _ = create_worktree(str(repo), "gate-d", {})
        assert run_check(_gate_ctx(wt, mode="enforce")).decision == Decision.BLOCK

    def test_non_fettle_worktree_exempt(self, repo):
        from fettle.claims_gate import run_check
        path = repo.parent / "plain-wt"
        subprocess.run(["git", "worktree", "add", str(path), "-b", "feature/x"],
                       cwd=repo, check=True, capture_output=True)
        assert run_check(_gate_ctx(path)).decision == Decision.ALLOW

    def test_mode_enum_registered(self):
        from fettle.config_schema import MODE_ENUMS
        assert MODE_ENUMS["gates.claims.mode"] == frozenset({"advisory", "enforce"})

    def test_registered_in_dispatcher(self):
        from fettle.dispatcher_registry import CHECKS
        spec = next(c for c in CHECKS if c.name == "claims_gate")
        assert spec.events == frozenset({"PostToolUse"})


class TestCLI:
    def test_work_list_claim_release_roundtrip(self, repo):
        items_dir = repo / "docs" / "work" / "items"
        items_dir.mkdir(parents=True)
        (items_dir / "checkout-totals.md").write_text(VALID_ITEM)

        r = subprocess.run([*CLI, "work", "claim", "checkout-totals"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

        r = subprocess.run([*CLI, "work", "list", "--json"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 0
        import json
        data = json.loads(r.stdout)
        row = next(i for i in data["items"] if i["id"] == "checkout-totals")
        assert row["claimed_by"]
        assert row["spec"] == "checkout-flow"

        r = subprocess.run([*CLI, "work", "release", "checkout-totals"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

    def test_work_list_lint_errors_exit_1(self, repo):
        items_dir = repo / "docs" / "work" / "items"
        items_dir.mkdir(parents=True)
        (items_dir / "bad.md").write_text(VALID_ITEM.replace("status: open", "status: bogus"))
        r = subprocess.run([*CLI, "work", "list"], cwd=repo, capture_output=True, text=True)
        assert r.returncode == 1
        assert "invalid status" in r.stdout
