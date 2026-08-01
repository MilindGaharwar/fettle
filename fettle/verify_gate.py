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
from fettle.test_discovery import discover_test_config
from fettle.test_runner_opts import build_pytest_args, record_failures

STAMP_RELPATH = os.path.join(".fettle", "verify.json")
FAILURE_HISTORY_RELPATH = os.path.join(".fettle", "test-failures.json")

_CODE_EXTENSIONS = (".py", ".rs", ".go", ".ts", ".tsx", ".js", ".jsx")


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
        if f.endswith(_CODE_EXTENSIONS) and os.path.isfile(f)
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
        if base.startswith("test_") or base.removesuffix(".py").endswith("_test"):
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

    tc = discover_test_config(cwd)
    stamp: dict = {
        "ok": False, "command": "", "exit_code": -1, "duration_s": 0.0,
        "scope": "full", "impacted": [], "error": "", "ts": time.time(),
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
        edits_path = _edits_path(session_id)
        edited = _edited_code_files(edits_path) if edits_path else []
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
        elif stamp_path.stat().st_mtime < edits_path.stat().st_mtime:
            problem = "code was edited after the last verification run (stale)"
        elif not stamp.get("ok", False):
            detail = str(stamp.get("error", "")).strip()
            problem = "last verification run failed" + (
                f":\n{detail}" if detail else ""
            )

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
