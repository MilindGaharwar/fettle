"""Tests for scripts/changeset.py — WP-71: Git change-set detection."""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.changeset import (
    ChangeStatus,
    get_staged,
    get_unstaged,
    get_untracked,
    get_vs_base,
    get_changed_files,
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


def _init_repo(tmp_path):
    _git(tmp_path, "init", "--initial-branch=main")
    _git(tmp_path, "config", "user.email", "test@test.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "initial.txt").write_text("initial")
    _git(tmp_path, "add", "initial.txt")
    _git(tmp_path, "commit", "-m", "initial")
    return tmp_path


def test_detects_staged_changes(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "new.py").write_text("x = 1")
    _git(repo, "add", "new.py")
    files = get_staged(str(repo))
    assert any(f.path == "new.py" for f in files)


def test_detects_unstaged_changes(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "initial.txt").write_text("modified")
    files = get_unstaged(str(repo))
    assert any(f.path == "initial.txt" and f.status == ChangeStatus.MODIFIED for f in files)


def test_detects_untracked_files(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "untracked.py").write_text("y = 2")
    files = get_untracked(str(repo))
    assert any(f.path == "untracked.py" for f in files)


def test_merge_base_diff_against_main(tmp_path):
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "-b", "feature")
    (repo / "feature.py").write_text("z = 3")
    _git(repo, "add", "feature.py")
    _git(repo, "commit", "-m", "feature commit")
    files = get_vs_base(str(repo), base="main")
    assert any(f.path == "feature.py" for f in files)


def test_renamed_files_tracked(tmp_path):
    repo = _init_repo(tmp_path)
    _git(repo, "mv", "initial.txt", "renamed.txt")
    files = get_staged(str(repo))
    assert any(f.status == ChangeStatus.RENAMED for f in files)


def test_deleted_files_included(tmp_path):
    repo = _init_repo(tmp_path)
    os.remove(repo / "initial.txt")
    _git(repo, "add", "initial.txt")
    files = get_staged(str(repo))
    assert any(f.status == ChangeStatus.DELETED for f in files)


def test_ignored_files_excluded(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / ".gitignore").write_text("*.log\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "add gitignore")
    (repo / "debug.log").write_text("log data")
    files = get_untracked(str(repo))
    assert not any(f.path == "debug.log" for f in files)


def test_no_git_repo_handled_gracefully(tmp_path):
    files = get_changed_files(str(tmp_path))
    assert files == []


def test_empty_diff_returns_empty_list(tmp_path):
    repo = _init_repo(tmp_path)
    files = get_staged(str(repo))
    assert files == []
