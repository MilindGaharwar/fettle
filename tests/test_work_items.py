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

    def test_v2_work_item_requires_completion_evidence_when_done(self):
        text = VALID_ITEM.replace("fettle-work-item: v1", "fettle-work-item: v2")

        item, findings = parse_work_item(text)

        assert item is not None
        assert item.requires_completion is True
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

    # --- WP-5 (audit C3): concurrent read-modify-write integrity ---

    def _spawn_claimers(self, repo, tmp_path, jobs):
        """Launch one process per (item, sess, worktree), gated on a barrier file."""
        plugin_root = str(Path(__file__).resolve().parent.parent)
        barrier = tmp_path / "go"
        procs = []
        for item, sess, wt in jobs:
            code = (
                "import os, sys, time\n"
                f"sys.path.insert(0, {plugin_root!r})\n"
                "from fettle.work_items import claim_item\n"
                f"while not os.path.exists({str(barrier)!r}): time.sleep(0.001)\n"
                f"err = claim_item({str(repo)!r}, {item!r}, {sess!r}, {wt!r})\n"
                "print('ERR:' + err)\n"
            )
            procs.append(subprocess.Popen(
                [sys.executable, "-c", code],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ))
        barrier.write_text("")
        outs = []
        for p in procs:
            out, err = p.communicate(timeout=30)
            assert p.returncode == 0, err
            outs.append(out.strip().removeprefix("ERR:"))
        return outs

    def test_concurrent_same_item_exactly_one_winner(self, repo, tmp_path):
        wts = []
        for i in range(4):
            wt, _ = create_worktree(str(repo), f"wt-race-{i}", {})
            wts.append(str(wt))
        results = self._spawn_claimers(
            repo, tmp_path,
            [("item-race", f"sess-{i}", wts[i]) for i in range(4)],
        )
        winners = [r for r in results if r == ""]
        assert len(winners) == 1, results
        assert all("claimed by session" in r for r in results if r != "")

    def test_concurrent_distinct_items_no_lost_update(self, repo, tmp_path):
        results = self._spawn_claimers(
            repo, tmp_path,
            [(f"item-{i}", f"sess-{i}", str(repo)) for i in range(4)],
        )
        assert results == ["", "", "", ""]
        claims = load_claims(str(repo))
        assert sorted(claims) == [f"item-{i}" for i in range(4)]

    def test_release_unclaimed_errors(self, repo):
        assert "not claimed" in release_item(str(repo), "never-claimed")


def _gate_ctx(cwd: Path, enabled: bool = True, mode: str = "advisory",
              worktrees_cfg: dict | None = None, file_path: str = "") -> HookContext:
    hook_input = HookInput(
        hook_event_name="PostToolUse",
        tool_name="Edit",
        tool_input={"file_path": file_path or str(cwd / "src.py")},
        cwd=cwd,
        session_id="test-claims",
        raw={},
    )
    config: dict = {"gates": {"claims": {"enabled": enabled, "mode": mode}}}
    if worktrees_cfg is not None:
        config["worktrees"] = worktrees_cfg
    return HookContext(
        input=hook_input,
        config=config,
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


class TestWorktreeRequire:
    """[worktrees].require (WP-162, A6) — main-worktree edits gated."""

    REQUIRE = {"root": ".fettle/worktrees", "require": True,
               "exempt_paths": ["docs/**", "**/*.md"]}

    def test_require_off_main_worktree_exempt(self, repo):
        from fettle.claims_gate import run_check
        cfg = dict(self.REQUIRE, require=False)
        assert run_check(_gate_ctx(repo, worktrees_cfg=cfg)).decision == Decision.ALLOW

    def test_require_on_advises_on_code_edit(self, repo):
        from fettle.claims_gate import run_check
        result = run_check(_gate_ctx(repo, worktrees_cfg=self.REQUIRE))
        assert result.decision == Decision.ADVISORY
        assert "fettle worktree create" in result.message

    def test_require_on_enforce_blocks(self, repo):
        from fettle.claims_gate import run_check
        result = run_check(_gate_ctx(repo, mode="enforce", worktrees_cfg=self.REQUIRE))
        assert result.decision == Decision.BLOCK

    def test_exempt_paths_allowed(self, repo):
        from fettle.claims_gate import run_check
        for path in ("docs/notes.txt", "README.md", "docs/a/b.rst"):
            ctx = _gate_ctx(repo, worktrees_cfg=self.REQUIRE,
                            file_path=str(repo / path))
            assert run_check(ctx).decision == Decision.ALLOW, path

    def test_linked_worktree_unaffected_by_require(self, repo):
        from fettle.claims_gate import run_check
        wt, _ = create_worktree(str(repo), "req-a", {})
        assert claim_item(str(wt), "req-a", "sess-1", str(wt)) == ""
        ctx = _gate_ctx(wt, worktrees_cfg=self.REQUIRE)
        assert run_check(ctx).decision == Decision.ALLOW

    def test_gate_disabled_wins(self, repo):
        from fettle.claims_gate import run_check
        ctx = _gate_ctx(repo, enabled=False, worktrees_cfg=self.REQUIRE)
        assert run_check(ctx).decision == Decision.ALLOW


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
