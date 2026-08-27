"""P45 contract tests — graph-independent source snapshots."""

from __future__ import annotations

import os
import stat
import subprocess


from fettle.source_snapshot import (
    bind_policy_identity,
    committed_snapshot,
    materialize_committed,
    revalidate_read_set,
    working_snapshot,
)


def _git(root, *args):
    out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _commit_file(root, rel, content, executable=False):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = 0o755 if executable else 0o644
    with open(path, "w") as handle:
        handle.write(content)
    os.chmod(path, mode)
    _git(root, "add", rel)
    _git(root, "-c", "user.email=test@fettle.invalid", "-c", "user.name=t", "commit", "-qm", rel)


def _init_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(str(root), "init", "-q")
    _git(str(root), "config", "core.symlinks", "true")
    _git(str(root), "config", "user.email", "test@fettle.invalid")
    _git(str(root), "config", "user.name", "t")
    return str(root)


def test_committed_identity_is_deterministic(tmp_path):
    root = _init_repo(tmp_path)
    _commit_file(root, "src/app.py", "value = 1\n")

    first = committed_snapshot(root)
    second = committed_snapshot(root)

    assert first["status"] == "completed"
    assert first["snapshot"]["digest"] == second["snapshot"]["digest"]


def test_committed_identity_tracks_the_tree(tmp_path):
    root = _init_repo(tmp_path)
    _commit_file(root, "src/app.py", "value = 1\n")
    before = committed_snapshot(root)

    _commit_file(root, "src/app.py", "value = 2\n")
    after = committed_snapshot(root)

    assert before["snapshot"]["digest"] != after["snapshot"]["digest"]


def test_working_identity_reflects_untracked_content(tmp_path):
    root = _init_repo(tmp_path)
    _commit_file(root, "src/app.py", "value = 1\n")
    base = working_snapshot(root)["snapshot"]["digest"]

    untracked = tmp_path / "repo" / "notes.txt"
    untracked.write_text("hello\n")
    with_untracked = working_snapshot(root)["snapshot"]["digest"]

    untracked.write_text("hello!\n")
    after_edit = working_snapshot(root)["snapshot"]["digest"]

    assert base != with_untracked
    assert with_untracked != after_edit


def test_unmerged_index_is_canonical_non_pass(tmp_path):
    root = _init_repo(tmp_path)
    _commit_file(root, "f.txt", "base\n")
    head = _git(str(root), "symbolic-ref", "--short", "HEAD").strip()
    _git(str(root), "checkout", "-b", "side")
    _commit_file(root, "f.txt", "side\n")
    _git(str(root), "checkout", head)
    _commit_file(root, "f.txt", "main\n")
    merged = subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", "side"],
        cwd=root, capture_output=True, text=True,
    )
    assert merged.returncode != 0 or "CONFLICT" in merged.stdout + merged.stderr

    result = working_snapshot(root)

    assert result["status"] == "tool_error"
    assert "conflict" in result["message"].lower()


def test_materialize_preserves_modes_and_symlinks(tmp_path):
    root = _init_repo(tmp_path)
    _commit_file(root, "bin/run.sh", "#!/bin/sh\n", executable=True)
    _commit_file(root, "src/app.py", "value = 1\n")
    if hasattr(os, "symlink"):
        link = tmp_path / "repo" / "link.py"
        link.symlink_to("src/app.py")
        _git(root, "add", "link.py")
        _git(root, "-c", "user.email=test@fettle.invalid", "-c", "user.name=t", "commit", "-qm", "link")
    snap = committed_snapshot(root)

    result = materialize_committed(root, snap["snapshot"])
    dest = result["snapshot"]["destination"]

    run_sh = os.path.join(dest, "bin/run.sh")
    assert os.stat(run_sh).st_mode & stat.S_IXUSR
    if hasattr(os, "symlink"):
        assert os.path.islink(os.path.join(dest, "link.py"))
    with open(os.path.join(dest, "src/app.py")) as handle:
        assert handle.read() == "value = 1\n"


def test_materialize_failure_cleans_dest_and_keeps_source(tmp_path):
    root = _init_repo(tmp_path)
    _commit_file(root, "src/app.py", "value = 1\n")
    snap = committed_snapshot(root)
    snap["snapshot"]["entries"]["src/missing.bin"] = {
        "mode": "100644", "type": "blob", "oid": "0" * 40,
    }

    result = materialize_committed(root, snap["snapshot"])

    assert result["status"] == "tool_error"
    assert "incomplete" in result["message"]
    assert not list(tmp_path.glob("fettle-snap-*"))


def test_revalidation_detects_transient_edits(tmp_path):
    root = _init_repo(tmp_path)
    _commit_file(root, "src/app.py", "value = 1\n")
    before = working_snapshot(root)

    (tmp_path / "repo" / "src" / "app.py").write_text("value = 2\n")
    result = revalidate_read_set(root, before)

    assert result["snapshot"]["drifted"] == ["src/app.py"]


def test_lfs_pointer_content_is_flagged(tmp_path):
    root = _init_repo(tmp_path)
    pointer = (
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:deadbeef\n"
        "size 3\n"
    )
    _commit_file(root, "assets/model.bin", pointer)

    snap = working_snapshot(root)

    entry = snap["snapshot"]["entries"]["assets/model.bin"]
    assert entry.get("lfs_pointer") is True


def test_policy_binding_changes_source_identity():
    base = bind_policy_identity("source-digest", "policy-a")
    other = bind_policy_identity("source-digest", "policy-b")

    assert base != other
    assert len(base) == 64
