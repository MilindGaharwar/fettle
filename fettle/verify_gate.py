"""[gates.verify] — functional test verification gate (Stage 7, S7.1; closes WP2).

Two worlds, one contract (same split as Stage 5 UAT):

- ``fettle verify`` (CLI, minutes-world) actually *runs* the project's test
  suite — command resolved via fettle/test_discovery.py (which honors the
  ``[profile] test_command`` override in .fettle.toml), optionally scoped to
  tests impacted by this session's edits, failure-first via
  fettle/test_runner_opts.py. It writes a result stamp to
  ``.fettle/verify.json``.
- ``run_check`` (Stop gate, milliseconds-world) never runs tests. It checks
  that a *fresh, green* stamp exists for the code edited this session —
  the same freshness model as coverage_gate. Missing, stale, or red stamp
  surfaces as advisory/block with the exact command to run.

This completes the loop: tdd_gate (tests exist) → bdd_gate (tests trace
specs) → tests gate (tests pass) → UAT (a user confirms behavior).

Off by default. Modes: advisory | enforce.
"""

from __future__ import annotations

import contextlib
import json
import os
import shlex
import subprocess
import time
from pathlib import Path

from fettle.dispatcher_types import CheckResult, HookContext
from fettle.paths import classify_file
from fettle.profile import detect_profile
from fettle.test_discovery import discover_test_config
from fettle.test_runner_opts import build_pytest_args, record_failures
from fettle.trace import build_evidence
from fettle.workspace import Workspace, route_file_to_workspace

STAMP_RELPATH = os.path.join(".fettle", "verify.json")
FAILURE_HISTORY_RELPATH = os.path.join(".fettle", "test-failures.json")

# ── Impacted-test mapping (deterministic, name-convention based) ──────────


def _edited_files(edits_path: Path) -> list[str]:
    """Unique file paths from the session edit-tracking file, oldest first."""
    if not edits_path.is_file():
        return []
    seen: dict[str, None] = {}
    try:
        for line in edits_path.read_text().splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            f = entry.get("file", "")
            if isinstance(f, str) and f:
                seen[f] = None
    except OSError:
        return []
    return list(seen)


def _edited_code_files(edits_path: Path) -> list[str]:
    return [
        f for f in _edited_files(edits_path)
        if classify_file(f) in ("implementation", "test") and os.path.isfile(f)
    ]


def impacted_tests(cwd: str, edited: list[str], test_roots: list[str]) -> list[str]:
    """Map edited files to test files by naming convention.

    - An edited file that *is* a test file maps to itself.
    - An edited implementation file ``pkg/foo.py`` maps to any
      ``test_foo.py`` / ``foo_test.py`` under the discovered test roots.

    Returns cwd-relative paths, deduplicated, order-stable. An empty result
    means the mapping found nothing — callers must treat that as "run the
    full suite", never as "nothing to test".
    """
    root = Path(cwd)
    out: dict[str, None] = {}
    for f in edited:
        abs_f = os.path.abspath(f) if not os.path.isabs(f) else f
        try:
            rel = os.path.relpath(abs_f, cwd)
        except ValueError:
            continue
        if rel.startswith(".."):
            continue
        base = os.path.basename(rel)
        if classify_file(rel) == "test":
            out[rel] = None
            continue
        stem = Path(base).stem
        for tr in test_roots:
            tr_path = root / tr
            if not tr_path.is_dir():
                continue
            for pattern in (f"test_{stem}.py", f"{stem}_test.py"):
                for hit in sorted(tr_path.rglob(pattern)):
                    out[str(hit.relative_to(root))] = None
    return list(out)


# ── fettle verify (minutes-world) ─────────────────────────────────────────


def run_verify(
    cwd: str,
    config: dict,
    *,
    full: bool = False,
    session_id: str | None = None,
) -> dict:
    """Run the project's test suite and write the verification stamp.

    Returns the stamp dict (also persisted to .fettle/verify.json):
    ok, command, exit_code, duration_s, scope, impacted, error, ts.
    Never raises — every failure mode lands in the stamp's ``error``.
    """
    gate_cfg = config.get("gates", {}).get("verify", {})
    timeout_s = int(gate_cfg.get("timeout_s", 120))
    scope_cfg = str(gate_cfg.get("scope", "impacted"))

    edits_path = _edits_path(session_id)
    edited = _edited_code_files(edits_path) if edits_path else []
    affected = _affected_workspaces(cwd, edited)
    if len(affected) > 1 or affected and affected[0][0].path != ".":
        return _run_workspace_verification(
            cwd, affected, timeout_s=timeout_s, session_id=session_id,
        )

    tc = discover_test_config(cwd)
    stamp: dict = {
        "ok": False, "command": "", "exit_code": -1, "duration_s": 0.0,
        "scope": "full", "impacted": [], "error": "", "ts": time.time(),
        # binding fields (WP-7): which session verified WHAT, exactly
        "session_id": session_id or "",
        "head_sha": _head_sha(cwd),
        "dirty_digest": _dirty_digest(cwd),
    }
    if not tc.command:
        stamp["error"] = (
            "no test command discovered — set [profile] test_command "
            "in .fettle.toml"
        )
        _write_stamp(cwd, stamp)
        return stamp

    argv = shlex.split(tc.command)
    scope = "full"
    impacted: list[str] = []
    if not full and scope_cfg == "impacted" and tc.framework == "pytest":
        impacted = impacted_tests(cwd, edited, tc.test_roots or ["tests"])
        if impacted:
            scope = "impacted"
            # Replace any positional test-root path from discovery with the
            # impacted set (exact match only — "pytest" ends with "test").
            argv = [a for a in argv if a.rstrip("/") not in (tc.test_roots or [])]
            argv += build_pytest_args(
                mode="changed",
                files=impacted,
                failure_history=os.path.join(cwd, FAILURE_HISTORY_RELPATH),
                parallel=bool(gate_cfg.get("parallel", False)),
            )

    stamp["command"] = " ".join(argv)
    stamp["scope"] = scope
    stamp["impacted"] = impacted

    start = time.monotonic()
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout_s,
        )
        stamp["exit_code"] = proc.returncode
        stamp["ok"] = proc.returncode == 0
        if proc.returncode != 0:
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-15:]
            stamp["error"] = "\n".join(tail)
            _record_pytest_failures(cwd, proc.stdout)
    except subprocess.TimeoutExpired:
        stamp["error"] = f"test run exceeded timeout ({timeout_s}s) — result unknown"
    except (OSError, FileNotFoundError) as e:
        stamp["error"] = f"could not launch test command: {e}"
    stamp["duration_s"] = round(time.monotonic() - start, 2)
    stamp["ts"] = time.time()
    _write_stamp(cwd, stamp)
    return stamp


def _affected_workspaces(cwd: str, edited: list[str]) -> list[tuple[Workspace, list[str]]]:
    """Group edited code by its canonical workspace."""
    if not edited:
        return []
    root = Path(cwd).resolve()
    profile = detect_profile(cwd, use_cache=False)
    grouped: dict[str, tuple[Workspace, list[str]]] = {}
    for file_path in edited:
        try:
            relative = Path(file_path).resolve().relative_to(root).as_posix()
        except ValueError:
            continue
        workspace = route_file_to_workspace(relative, profile.workspaces)
        if workspace is None:
            continue
        grouped.setdefault(workspace.path, (workspace, []))[1].append(relative)
    return [grouped[path] for path in sorted(grouped)]


def _run_workspace_verification(
    cwd: str,
    affected: list[tuple[Workspace, list[str]]],
    *,
    timeout_s: int,
    session_id: str | None,
) -> dict:
    """Run each affected workspace's configured full test suite."""
    records: list[dict] = []
    for workspace, edited in affected:
        workspace_root = Path(cwd) if workspace.path == "." else Path(cwd) / workspace.path
        record = {
            "path": workspace.path,
            "command": workspace.test_command,
            "exit_code": -1,
            "ok": False,
            "scope": "full",
            "edited": edited,
            "error": "",
            "head_sha": _head_sha(cwd),
            "dirty_digest": _dirty_digest(str(workspace_root)),
        }
        if not workspace.test_command:
            record["error"] = "no test command discovered for workspace"
            records.append(record)
            continue
        start = time.monotonic()
        try:
            proc = subprocess.run(
                shlex.split(workspace.test_command), cwd=str(workspace_root),
                capture_output=True, text=True, timeout=timeout_s,
            )
            record["exit_code"] = proc.returncode
            record["ok"] = proc.returncode == 0
            if proc.returncode != 0:
                record["error"] = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-15:])
        except subprocess.TimeoutExpired:
            record["error"] = f"test run exceeded timeout ({timeout_s}s) — result unknown"
        except (OSError, FileNotFoundError) as error:
            record["error"] = f"could not launch test command: {error}"
        record["duration_s"] = round(time.monotonic() - start, 2)
        evidence = build_evidence(
            "verify", command=record["command"], exit_code=record["exit_code"],
            duration_ms=record["duration_s"] * 1000, scope="full", workspace=workspace.path,
        )
        record["evidence_id"] = evidence["evidence_id"]
        records.append(record)

    failed = [record for record in records if not record["ok"]]
    stamp = {
        "ok": not failed,
        "command": " && ".join(record["command"] for record in records),
        "exit_code": max((record["exit_code"] for record in failed), default=0),
        "duration_s": round(sum(record.get("duration_s", 0.0) for record in records), 2),
        "scope": "workspace",
        "impacted": [],
        "error": "\n".join(
            f"[{record['path']}] {record['error']}" for record in failed
        ),
        "ts": time.time(),
        "session_id": session_id or "",
        "head_sha": _head_sha(cwd),
        "dirty_digest": _dirty_digest(cwd),
        "workspaces": records,
    }
    _write_stamp(cwd, stamp)
    return stamp


def _record_pytest_failures(cwd: str, stdout: str) -> None:
    """Persist failed test ids for failure-first ordering on the next run."""
    failed = [
        line.split()[1]
        for line in stdout.splitlines()
        if line.startswith("FAILED ") and len(line.split()) > 1
    ]
    if failed:
        with contextlib.suppress(OSError):
            record_failures(os.path.join(cwd, FAILURE_HISTORY_RELPATH), failed)


def _write_stamp(cwd: str, stamp: dict) -> None:
    evidence = build_evidence(
        "verify", command=stamp.get("command", ""), exit_code=stamp.get("exit_code"),
        duration_ms=float(stamp.get("duration_s", 0)) * 1000, scope=stamp.get("scope", ""),
    )
    stamp["evidence_id"] = evidence["evidence_id"]
    path = Path(cwd) / STAMP_RELPATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stamp, indent=2) + "\n")
    except OSError:
        pass  # gate will report the missing stamp — failure stays visible


def _edits_path(session_id: str | None) -> Path | None:
    if not session_id:
        return None
    from fettle.config import state_dir
    return state_dir(session_id) / "edits.jsonl"


# ── Stamp binding (WP-7, audit M-04) ──────────────────────────────────


def _git_out(cwd: str, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        return proc.stdout if proc.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _head_sha(cwd: str) -> str:
    return _git_out(cwd, "rev-parse", "HEAD").strip()


def _dirty_digest(cwd: str) -> str:
    """Fingerprint of the uncommitted state: status listing + tracked diffs.

    Known limitation: content changes inside files that stay untracked do
    not alter the digest — the mtime freshness check remains the primary
    signal; this digest only *redeems* an mtime-stale stamp when the tree
    provably matches the verified one.
    """
    import hashlib
    material = (
        _git_out(cwd, "status", "--porcelain")
        + _git_out(cwd, "diff", "HEAD")
    )
    return hashlib.sha256(material.encode("utf-8", "replace")).hexdigest()[:16]


def _tree_matches_stamp(cwd: str, stamp: dict) -> bool:
    head = str(stamp.get("head_sha") or "")
    return (bool(head)
            and head == _head_sha(cwd)
            and str(stamp.get("dirty_digest") or "") == _dirty_digest(cwd))


# ── Stop gate (milliseconds-world) ────────────────────────────────────────


def run_check(ctx: HookContext) -> CheckResult:
    """Stop hook — demand a fresh, green ``fettle verify`` stamp."""
    cfg = ctx.config.get("gates", {}).get("verify", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    edits_path = _edits_path(ctx.session_id or "unknown")
    if edits_path is None or not edits_path.is_file():
        return CheckResult.allow()
    edited = _edited_code_files(edits_path)
    if not edited:
        return CheckResult.allow()  # docs-only session — nothing to verify

    stamp_path = ctx.cwd / STAMP_RELPATH
    problem = ""
    if not stamp_path.is_file():
        problem = "no verification run recorded this session"
    else:
        try:
            stamp = json.loads(stamp_path.read_text())
        except (json.JSONDecodeError, OSError):
            stamp = None
        if not isinstance(stamp, dict):
            problem = "verification stamp is unreadable"
        elif str(stamp.get("session_id") or "") != (ctx.session_id or ""):
            # WP-7: a stamp from another session (or a hand-written one
            # without a session) proves nothing about THIS session's edits.
            problem = "verification stamp was written by another session"
        elif (stamp_path.stat().st_mtime < edits_path.stat().st_mtime
              and not _tree_matches_stamp(str(ctx.cwd), stamp)):
            problem = "code was edited after the last verification run (stale)"
        elif not stamp.get("ok", False):
            detail = str(stamp.get("error", "")).strip()
            problem = "last verification run failed" + (
                f":\n{detail}" if detail else ""
            )
        elif stamp.get("workspaces"):
            affected = _affected_workspaces(str(ctx.cwd), edited)
            needed = {workspace.path for workspace, _files in affected}
            verified = {
                str(record.get("path"))
                for record in stamp.get("workspaces", [])
                if isinstance(record, dict) and record.get("ok", False)
            }
            missing = sorted(needed - verified)
            if missing:
                problem = "the last verification run omitted affected workspace(s): " + ", ".join(missing)
        elif stamp.get("scope") == "impacted":
            # WP-7: everything edited this session must fall inside the
            # verified scope. Full-suite stamps are always a superset; an
            # impacted stamp must cover the impacted set as of NOW — and a
            # now-unmappable edit demands the full suite.
            tc = discover_test_config(str(ctx.cwd))
            needed = impacted_tests(str(ctx.cwd), edited, tc.test_roots or ["tests"])
            verified = set(stamp.get("impacted") or [])
            if not needed or not set(needed) <= verified:
                problem = ("the last verification run did not cover every "
                           "file edited this session")

    if not problem:
        return CheckResult.allow()

    msg = (
        f"Verify gate: {len(edited)} code file(s) edited this session but the "
        f"test suite is not verified green — {problem}\n"
        f"Run: fettle verify"
    )
    hso = {
        "hookEventName": ctx.input.hook_event_name,
        "additionalContext": msg,
    }
    if cfg.get("mode", "advisory") == "enforce":
        return CheckResult.block(msg, hook_specific_output=hso)
    return CheckResult.advisory(msg, hook_specific_output=hso)
