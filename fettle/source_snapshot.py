"""P45 — Graph-independent committed and working source snapshots.

Provider inputs must be identified, materialized, and revalidated without a
graph or graph store. Snapshots are canonical portable identities:

- Committed snapshots enumerate ``git ls-tree -r`` entries (modes, symlink
  blobs, gitlinks, deletions implicit in full-tree enumeration).
- Working snapshots content-hash every tracked path from the index plus
  untracked (non-ignored) files and explicitly required ignored inputs.
- Materialization writes provider inputs into a restrictive temporary
  directory and re-verifies every written byte; any failure removes the
  temporary tree, never touches user files, and returns an actionable
  canonical non-pass.

Every public function returns a result envelope:
``{"status": "completed", ...}`` or
``{"status": "tool_error", "message": ...}`` (fail-visible).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

_LFS_POINTER_PREFIX = b"version https://git-lfs"
_GITLINK_MODE = "160000"
_SYMLINK_MODE = "120000"


def _run(root: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, timeout=120,
    )


def _digest(entries: dict) -> str:
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _completed(snapshot: dict) -> dict:
    return {"status": "completed", "snapshot": snapshot}


def _failed(message: str) -> dict:
    return {"status": "tool_error", "message": message}


def _hash_file(path: Path) -> tuple[str, bool]:
    digest = hashlib.sha256()
    lfs = False
    with path.open("rb") as handle:
        head = handle.read(4096)
        if head.startswith(_LFS_POINTER_PREFIX):
            lfs = True
        digest.update(head)
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest(), lfs


def committed_snapshot(root: str, ref: str = "HEAD") -> dict:
    """Canonical manifest of the committed tree at ``ref``."""
    done = _run(root, ["rev-parse", f"{ref}^{{tree}}"])
    if done.returncode:
        return _failed(f"Cannot resolve tree for {ref!r}: {done.stderr.decode(errors='replace').strip()}")
    tree_sha = done.stdout.decode().strip()

    listed = _run(root, ["ls-tree", "-r", "-z", ref])
    if listed.returncode:
        return _failed(f"Cannot list {ref!r}: {listed.stderr.decode(errors='replace').strip()}")

    entries: dict[str, dict] = {}
    for record in listed.stdout.split(b"\0"):
        if not record:
            continue
        meta, path_bytes = record.split(b"\t", 1)
        mode, otype, oid = meta.decode().split()
        entry = {"mode": mode, "type": otype, "oid": oid}
        if otype == "commit":
            entry["kind"] = "gitlink"
        entries[path_bytes.decode()] = entry

    snapshot = {
        "kind": "committed",
        "root": str(Path(root).resolve()),
        "tree": tree_sha,
        "ref": ref,
        "entries": entries,
    }
    snapshot["digest"] = _digest({k: v for k, v in snapshot.items() if k != "root"})
    return _completed(snapshot)


def working_snapshot(root: str, required_ignored: list[str] | None = None) -> dict:
    """Content-hashed manifest of the live tree the way providers read it."""
    root_path = Path(root)
    inputs = _index_inputs(root, root_path, required_ignored or [])
    if isinstance(inputs, dict):
        return inputs
    tracked_paths, untracked_paths, ignored_paths = inputs

    outcome, failure = _working_entries(
        root_path, tracked_paths, untracked_paths, ignored_paths,
    )
    if outcome is None:
        return failure
    entries = outcome

    snapshot = {
        "kind": "working",
        "root": str(root_path.resolve()),
        "head_tree": _head_tree(root),
        "entries": entries,
    }
    snapshot["digest"] = _digest({k: v for k, v in snapshot.items() if k != "root"})
    return _completed(snapshot)


def _index_inputs(
    root: str, root_path: Path, required_ignored: list[str]
) -> tuple[list[str], list[str], list[str]] | dict:
    """Read tracked/untracked/required-ignored path lists; envelope on error."""
    index = _run(root, ["ls-files", "-s", "-z"])
    unmerged = _run(root, ["ls-files", "-u", "-z"])
    others = _run(root, ["ls-files", "--others", "--exclude-standard", "-z"])
    if index.returncode:
        return _failed("Cannot read the git index.")
    conflict = _conflict_paths(unmerged)
    if conflict:
        return conflict
    if others.returncode:
        return _failed("Cannot enumerate untracked files.")
    tracked = [
        rec.split(b"\t", 1)[1].decode()
        for rec in index.stdout.split(b"\0") if rec
    ]
    untracked = [rec.decode() for rec in others.stdout.split(b"\0") if rec]
    ignored = [p for p in required_ignored if (root_path / p).is_file()]
    return tracked, untracked, ignored


def _conflict_paths(unmerged: subprocess.CompletedProcess) -> dict | None:
    if not unmerged.stdout.strip():
        return None
    conflicted = sorted({
        rec.split(b"\t", 1)[1].decode()
        for rec in unmerged.stdout.split(b"\0") if rec
    })
    return _failed("Index has unresolved merge conflicts: " + ", ".join(conflicted))


def _working_entries(
    root_path: Path,
    tracked: list[str],
    untracked: list[str],
    ignored: list[str],
) -> tuple[dict | None, dict | None]:
    """Build entry map; returns (entries, None) or (None, error envelope)."""
    entries: dict[str, dict] = {}
    for rel, mark_untracked in (
        [(rel, False) for rel in tracked]
        + [(rel, True) for rel in sorted(set(untracked + ignored))]
    ):
        outcome = _working_entry(root_path, rel)
        if outcome is None:
            continue
        if isinstance(outcome, dict) and outcome.get("status"):
            return None, outcome
        if mark_untracked:
            outcome["untracked"] = True
        entries[rel] = outcome
    return entries, None


def _head_tree(root: str) -> str | None:
    done = _run(root, ["rev-parse", "HEAD^{tree}"])
    return done.stdout.decode().strip() if not done.returncode else None


def _working_entry(root_path: Path, rel: str) -> dict | None | dict:
    """Hash one live path; None when it vanished; envelope on hard failure."""
    path = root_path / rel
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink():
        target = os.readlink(path)
        return {
            "mode": _SYMLINK_MODE,
            "content_sha": hashlib.sha256(target.encode()).hexdigest(),
            "symlink_target": target,
        }
    if not path.is_file():
        return _failed(
            f"Cannot snapshot {rel!r}: not a regular file or symlink "
            "(submodule checkout missing?)."
        )
    mode_bits = stat.S_IMODE(path.stat().st_mode)
    content_sha, lfs = _hash_file(path)
    return {
        "mode": "100755" if mode_bits & stat.S_IXUSR else "100644",
        "content_sha": content_sha,
        **({"lfs_pointer": True} if lfs else {}),
    }


def materialize_committed(root: str, snapshot: dict, destination: str | None = None) -> dict:
    """Write committed provider inputs into a restrictive temp directory.

    Every written byte is re-verified against the manifest afterwards. Any
    failure cleans the destination and returns a canonical non-pass; source
    files are never modified.
    """
    if snapshot.get("kind") != "committed" or snapshot.get("status"):
        return _failed("Materialization requires a completed committed snapshot.")
    dest_root = Path(destination) if destination else Path(tempfile.mkdtemp(prefix="fettle-snap-"))
    try:
        dest_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        written = _write_entries(root, snapshot["entries"], dest_root)
        if isinstance(written, dict):
            shutil.rmtree(dest_root, ignore_errors=True)
            return written
        verified = verify_against(dest_root, snapshot["entries"], identity="oid")
        if verified:
            shutil.rmtree(dest_root, ignore_errors=True)
            return _failed(f"Materialized tree failed verification: {verified}")
    except OSError as exc:
        shutil.rmtree(dest_root, ignore_errors=True)
        return _failed(f"Materialization failed; no source file was touched: {exc}")
    return _completed({"destination": str(dest_root), "count": len(snapshot["entries"])})


def _write_entries(root: str, entries: dict, dest_root: Path) -> int | dict:
    count = 0
    for rel, entry in sorted(entries.items()):
        if entry.get("kind") == "gitlink":
            continue
        target = dest_root / rel
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        blob = _run(root, ["cat-file", "blob", entry["oid"]])
        if blob.returncode:
            return _failed(
                f"Object {entry['oid'][:12]} for {rel!r} is unavailable; "
                "repository objects are incomplete."
            )
        if entry["mode"] == _SYMLINK_MODE:
            os.symlink(blob.stdout.decode(), target)
            if os.readlink(target) != blob.stdout.decode():
                return _failed(f"Symlink {rel!r} did not retain its target after write.")
        else:
            target.write_bytes(blob.stdout)
            os.chmod(target, 0o755 if entry["mode"] == "100755" else 0o644)
        count += 1
    return count


def verify_against(root: str | Path, entries: dict, identity: str) -> str:
    """Re-verify a tree against expected identities ('' when equal).

    ``identity='content_sha'`` compares direct SHA-256 content hashes;
    ``identity='oid'`` hashes written bytes through ``git hash-object`` so
    materialized trees prove blob equality with the source repository.
    """
    root_path = Path(root)
    for rel, entry in sorted(entries.items()):
        if entry.get("kind") == "gitlink":
            continue
        path = root_path / rel
        drift = _verify_entry(path, rel, entry, identity)
        if drift:
            return drift
    return ""


def _verify_entry(path: Path, rel: str, entry: dict, identity: str) -> str:
    try:
        if entry["mode"] == _SYMLINK_MODE:
            if "symlink_target" not in entry:
                return ""
            actual = os.readlink(path) if path.is_symlink() else None
            return "" if actual == entry.get("symlink_target") else f"{rel}: symlink target drifted"
        return _verify_regular(path, rel, entry, identity)
    except OSError as exc:
        return f"{rel}: verification error ({exc})"


def _verify_regular(path: Path, rel: str, entry: dict, identity: str) -> str:
    if not path.is_file():
        return f"{rel}: missing after write"
    if identity == "content_sha":
        got, _lfs = _hash_file(path)
        return "" if got == entry["content_sha"] else f"{rel}: content drifted"
    hashed = _run(str(path.parent), ["hash-object", str(path)])
    if hashed.returncode or hashed.stdout.decode().strip() != entry["oid"]:
        return f"{rel}: object identity drifted"
    return ""


def revalidate_read_set(root: str, before: dict, paths: list[str] | None = None) -> dict:
    """Detect transient edit/restore races across a provider's read set."""
    after = working_snapshot(root)
    if after["status"] != "completed":
        return after
    subset = set(paths or before["snapshot"]["entries"])
    drifted = sorted(
        rel
        for rel in subset
        if before["snapshot"]["entries"].get(rel, {}).get("content_sha")
        != after["snapshot"]["entries"].get(rel, {}).get("content_sha")
        and (Path(root) / rel).exists()
    )
    return _completed({"drifted": drifted})


def bind_policy_identity(source_digest: str, policy_digest: str) -> str:
    """Bind effective-policy provenance into the source identity."""
    return hashlib.sha256(
        json.dumps({"source": source_digest, "policy": policy_digest},
                   sort_keys=True).encode()
    ).hexdigest()
