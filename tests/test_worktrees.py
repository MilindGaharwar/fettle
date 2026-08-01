"""Tests for fettle.worktrees — WP7 worktree spine (Stage 4, S4.2)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from fettle.worktrees import (
    create_worktree,
    git_common_dir,
    is_linked_worktree,
    list_worktrees,
    remove_worktree,
    worktrees_root,
)

CLI = [sys.executable, "-m", "fettle.cli"]


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


CFG: dict = {}  # defaults: root = .fettle/worktrees


class TestCreate:
    def test_create_makes_worktree_and_branch(self, repo):
        path, err = create_worktree(str(repo), "checkout-flow", CFG)
        assert err == ""
        assert path == worktrees_root(str(repo), CFG) / "checkout-flow"
        assert (path / "README.md").is_file()
        out = subprocess.run(["git", "branch", "--list", "fettle/checkout-flow"],
                             cwd=repo, capture_output=True, text=True).stdout
        assert "fettle/checkout-flow" in out

    def test_invalid_id_rejected(self, repo):
        path, err = create_worktree(str(repo), "Bad_ID!", CFG)
        assert path is None
        assert "invalid item id" in err

    def test_existing_path_refused(self, repo):
        create_worktree(str(repo), "item-a", CFG)
        path, err = create_worktree(str(repo), "item-a", CFG)
        assert path is None
        assert "already exists" in err

    def test_custom_root_config(self, repo):
        cfg = {"worktrees": {"root": ".fettle/wt"}}
        path, err = create_worktree(str(repo), "item-b", cfg)
        assert err == ""
        assert path == repo / ".fettle" / "wt" / "item-b"


class TestGitFileHandling:
    """.git is a FILE in linked worktrees — the audit this slice fixes."""

    def test_common_dir_same_from_main_and_linked(self, repo):
        path, _ = create_worktree(str(repo), "item-c", CFG)
        assert git_common_dir(str(path)) == git_common_dir(str(repo))
        assert (path / ".git").is_file()  # precondition of the whole audit

    def test_is_linked_worktree(self, repo):
        path, _ = create_worktree(str(repo), "item-d", CFG)
        assert is_linked_worktree(str(path)) is True
        assert is_linked_worktree(str(repo)) is False

    def test_find_repo_root_inside_linked_worktree(self, repo):
        from fettle.paths import find_repo_root
        path, _ = create_worktree(str(repo), "item-e", CFG)
        assert find_repo_root(path) == path

    def test_trace_repo_name_inside_linked_worktree(self, repo):
        from fettle.trace import _repo_name
        path, _ = create_worktree(str(repo), "item-f", CFG)
        assert _repo_name(str(path / "README.md")) == "item-f"


class TestList:
    def test_list_annotates_managed_and_dirty(self, repo):
        path, _ = create_worktree(str(repo), "item-g", CFG)
        (path / "new.py").write_text("x = 1\n")
        rows, err = list_worktrees(str(repo), CFG)
        assert err == ""
        managed = [r for r in rows if r["managed"]]
        assert len(managed) == 1
        assert managed[0]["item"] == "item-g"
        assert managed[0]["branch"] == "fettle/item-g"
        assert managed[0]["dirty"] is True
        main = [r for r in rows if not r["managed"]]
        assert len(main) == 1


class TestRemove:
    def test_remove_clean_worktree(self, repo):
        path, _ = create_worktree(str(repo), "item-h", CFG)
        assert remove_worktree(str(repo), "item-h", CFG) == ""
        assert not path.exists()
        # branch deliberately kept
        out = subprocess.run(["git", "branch", "--list", "fettle/item-h"],
                             cwd=repo, capture_output=True, text=True).stdout
        assert "fettle/item-h" in out

    def test_remove_dirty_refused_without_force(self, repo):
        path, _ = create_worktree(str(repo), "item-i", CFG)
        (path / "wip.py").write_text("work in progress\n")
        err = remove_worktree(str(repo), "item-i", CFG)
        assert "uncommitted changes" in err
        assert path.exists()

    def test_remove_dirty_with_force(self, repo):
        path, _ = create_worktree(str(repo), "item-j", CFG)
        (path / "wip.py").write_text("work in progress\n")
        assert remove_worktree(str(repo), "item-j", CFG, force=True) == ""
        assert not path.exists()

    def test_remove_missing_errors(self, repo):
        assert "no worktree" in remove_worktree(str(repo), "ghost", CFG)


class TestCLI:
    def test_create_list_remove_roundtrip(self, repo):
        r = subprocess.run([*CLI, "worktree", "create", "cli-item"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "fettle/cli-item" in r.stdout

        r = subprocess.run([*CLI, "worktree", "list", "--json"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 0
        import json
        rows = json.loads(r.stdout)
        assert any(row.get("item") == "cli-item" for row in rows)

        r = subprocess.run([*CLI, "worktree", "remove", "cli-item"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

    def test_create_invalid_id_exit_2(self, repo):
        r = subprocess.run([*CLI, "worktree", "create", "Not_Valid"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 2
        assert "invalid item id" in r.stderr

    def test_remove_dirty_exit_1(self, repo):
        subprocess.run([*CLI, "worktree", "create", "dirty-item"],
                       cwd=repo, capture_output=True, text=True)
        wt = repo / ".fettle" / "worktrees" / "dirty-item"
        (wt / "wip.py").write_text("x\n")
        r = subprocess.run([*CLI, "worktree", "remove", "dirty-item"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 1
        assert "uncommitted" in r.stderr
