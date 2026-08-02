"""Tests for fettle topology apply/status/revoke (WP-160/161, B3–B4)."""

import subprocess
import time
from pathlib import Path

import pytest

from fettle.topology_apply import (
    apply_topology, load_manifest, revoke_item, render_apply,
    render_status, topology_status,
)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "island.py").write_text("Y = 2\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "guide.md").write_text("# g\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


def _work_item(repo: Path, item_id: str, scope=(), status="open"):
    items = repo / "docs" / "work" / "items"
    items.mkdir(parents=True, exist_ok=True)
    scope_lines = "".join(f"  - {s}\n" for s in scope)
    (items / f"{item_id}.md").write_text(
        f"---\nfettle-work-item: true\nid: {item_id}\nstatus: {status}\n"
        + (f"scope:\n{scope_lines}" if scope else "")
        + f"---\n\n# {item_id}\n"
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", f"add {item_id}"], cwd=repo, check=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    r = _init_repo(tmp_path)
    monkeypatch.setattr("fettle.topology._trace_risk",
                        lambda days=30: (False, "test"))
    return r


class TestApply:
    def test_parallel_workers_provisioned(self, repo):
        _work_item(repo, "item-a", scope=("pkg/island.py",))
        _work_item(repo, "item-b", scope=("docs/guide.md",))
        manifest = apply_topology(str(repo))
        assert manifest["topology"] == "parallel-workers"
        assert manifest["errors"] == []
        assert len(manifest["items"]) == 2
        for entry in manifest["items"]:
            assert Path(entry["worktree"]).is_dir()
            assert "fettle spawn claude" in entry["spawn"]
        # claims live in the git common dir
        from fettle.work_items import load_claims
        claims = load_claims(str(repo))
        assert set(claims) == {"item-a", "item-b"}

    def test_manifest_written_and_loadable(self, repo):
        _work_item(repo, "item-a", scope=("pkg/island.py",))
        _work_item(repo, "item-b", scope=("docs/guide.md",))
        apply_topology(str(repo))
        loaded = load_manifest(str(repo))
        assert loaded["topology"] == "parallel-workers"
        assert len(loaded["items"]) == 2

    def test_solo_provisions_nothing(self, repo):
        manifest = apply_topology(str(repo))
        assert manifest["topology"] == "solo"
        assert manifest["items"] == []
        assert load_manifest(str(repo)) is None

    def test_recommends_worktrees_require(self, repo):
        _work_item(repo, "item-a", scope=("pkg/island.py",))
        _work_item(repo, "item-b", scope=("docs/guide.md",))
        manifest = apply_topology(str(repo))
        assert any("[worktrees].require" in r for r in manifest["rationale"])

    def test_render(self, repo):
        _work_item(repo, "item-a", scope=("pkg/island.py",))
        _work_item(repo, "item-b", scope=("docs/guide.md",))
        out = render_apply(apply_topology(str(repo)))
        assert "provisioned:" in out
        assert "fettle spawn claude" in out


class TestStatus:
    def _applied(self, repo):
        _work_item(repo, "item-a", scope=("pkg/island.py",))
        _work_item(repo, "item-b", scope=("docs/guide.md",))
        return apply_topology(str(repo))

    def test_no_manifest_error(self, repo):
        assert "error" in topology_status(str(repo))

    def test_workers_listed_with_claims(self, repo):
        self._applied(repo)
        data = topology_status(str(repo))
        assert len(data["workers"]) == 2
        assert all(w["claimed"] for w in data["workers"])

    def test_trace_joined_and_stop_loss(self, repo):
        manifest = self._applied(repo)
        sid = manifest["items"][0]["session_id"]
        from fettle.trace import log_decision
        for _ in range(3):
            log_decision(hook="g", status="blocked", session_id=sid)
        data = topology_status(str(repo), max_blocks=2)
        worker = data["workers"][0]
        assert worker["blocks"] == 3
        assert worker["stop_loss_breached"] is True
        assert "STOP-LOSS" in render_status(data)


class TestRevoke:
    def test_revoke_releases_and_drops(self, repo):
        _work_item(repo, "item-a", scope=("pkg/island.py",))
        _work_item(repo, "item-b", scope=("docs/guide.md",))
        apply_topology(str(repo))
        assert revoke_item(str(repo), "item-a") == ""
        from fettle.work_items import load_claims
        assert "item-a" not in load_claims(str(repo))
        assert [e["item"] for e in load_manifest(str(repo))["items"]] == ["item-b"]

    def test_revoke_unknown_item(self, repo):
        _work_item(repo, "item-a", scope=("pkg/island.py",))
        _work_item(repo, "item-b", scope=("docs/guide.md",))
        apply_topology(str(repo))
        assert revoke_item(str(repo), "nope") != "" or \
            load_manifest(str(repo))["items"]  # nothing dropped
