"""Tests for scripts/paths.py — path utilities."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from paths import (
    find_repo_root, resolve_path, is_within_repo,
    relative_to_repo, is_implementation_file, is_test_file, is_excluded,
)


def test_find_repo_root_from_subdir(tmp_path):
    (tmp_path / ".git").mkdir()
    subdir = tmp_path / "src" / "pkg"
    subdir.mkdir(parents=True)
    root = find_repo_root(subdir)
    assert root == tmp_path


def test_find_repo_root_with_fettle_toml(tmp_path):
    (tmp_path / ".fettle.toml").write_text("")
    root = find_repo_root(tmp_path)
    assert root == tmp_path


def test_find_repo_root_returns_none(tmp_path):
    root = find_repo_root(tmp_path / "nonexistent")
    assert root is None


def test_is_within_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    file_inside = tmp_path / "src" / "app.py"
    file_inside.parent.mkdir()
    file_inside.touch()
    assert is_within_repo(file_inside, tmp_path) is True


def test_is_not_within_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "other" / "file.py"
    outside.parent.mkdir()
    outside.touch()
    assert is_within_repo(outside, repo) is False


def test_traversal_attack_blocked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    malicious = repo / ".." / "secret.py"
    assert is_within_repo(malicious, repo) is False


def test_relative_to_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    file_path = tmp_path / "src" / "app.py"
    file_path.parent.mkdir()
    file_path.touch()
    rel = relative_to_repo(file_path, tmp_path)
    assert rel == os.path.join("src", "app.py")


def test_is_implementation_file():
    assert is_implementation_file("app.py") is True
    assert is_implementation_file("index.ts") is True
    assert is_implementation_file("main.rs") is True
    assert is_implementation_file("config.toml") is False
    assert is_implementation_file("README.md") is False


def test_is_test_file():
    assert is_test_file("test_app.py") is True
    assert is_test_file("tests/test_main.py") is True
    assert is_test_file("app.test.ts") is True
    assert is_test_file("src/app.py") is False


def test_is_excluded():
    patterns = ["node_modules/", "__pycache__/", ".venv/"]
    assert is_excluded("node_modules/pkg/index.js", patterns) is True
    assert is_excluded("src/__pycache__/mod.pyc", patterns) is True
    assert is_excluded("src/app.py", patterns) is False
