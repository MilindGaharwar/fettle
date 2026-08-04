"""[gates.ci] — remote CI verification gate (Stage 8).

Born from a real incident: 8 consecutive red CI runs accumulated while the
local pre-push suite stayed green (environment divergence) and nothing in
the loop ever looked at the remote verdict. This gate makes that class of
failure impossible to repeat: an agent cannot pass Stop after a `git push`
without the remote CI verdict being known — and green.

Two worlds, one contract (same split as verify_gate / coverage_gate):

- ``record_push`` (PostToolUse Bash, milliseconds-world) passively records
  every `git push` this session — the pushed HEAD sha, timestamped — into
  the session state dir. It never blocks and never touches the network.
- ``fettle ci status|wait`` (CLI, minutes-world) queries GitHub Actions for
  the workflow runs of that sha (``gh`` when available, stdlib urllib as a
  fallback), optionally polling until completion, and writes a result stamp
  to ``.fettle/ci-status.json``. Red runs are fed through the v0.5.0
  ci_ingest/ci_diagnose machinery: classified, stored, and answered with a
  local reproduction command.
- ``run_check`` (Stop gate, milliseconds-world) never queries the network.
  It checks that a *fresh, green* stamp exists for the last pushed sha.
  Missing, stale (older than the push, or for a different sha), pending, or
  red surfaces as advisory/block with the exact command to run.

Off by default. Modes: advisory | enforce.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from fettle.dispatcher_types import CheckResult, HookContext
from fettle.trace import build_evidence

STAMP_RELPATH = os.path.join(".fettle", "ci-status.json")
FAILURE_HISTORY_RELPATH = os.path.join(".fettle", "ci-failures.json")
PUSHES_FILENAME = "pushes.jsonl"

_GIT_PUSH_RE = re.compile(r"\bgit(?:\s+-C\s+\S+|\s+-\S+)*\s+push\b")
_GITHUB_REMOTE_RE = re.compile(
    r"(?:git@github\.com:|https://github\.com/)([^/\s]+/[^/\s]+?)(?:\.git)?/?$"
)
# WP-12 (audit M-05): the slug is interpolated into an api.github.com URL —
# only plain owner/repo shapes may pass (no '?', '#', '..', '%').
_REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

_GREEN_CONCLUSIONS = frozenset({"success", "skipped", "neutral"})


# ── Plumbing (each a seam for tests) ──────────────────────────────────────


def _head_sha(cwd: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _github_repo(cwd: str) -> str | None:
    """``owner/repo`` for the origin remote, or None for non-GitHub remotes."""
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    m = _GITHUB_REMOTE_RE.search(proc.stdout.strip())
    slug = m.group(1) if m else None
    return slug if slug and _REPO_SLUG_RE.fullmatch(slug) else None


def _query_runs(cwd: str, sha: str) -> tuple[list[dict] | None, str]:
    """Workflow runs for a commit: ``(runs, error)``.

    ``runs`` is None when the query itself failed (no tooling, no network,
    no GitHub remote) — distinct from an empty list (queried fine, no runs).
    """
    if shutil.which("gh"):
        try:
            proc = subprocess.run(
                ["gh", "run", "list", "--commit", sha, "--limit", "20",
                 "--json", "databaseId,workflowName,status,conclusion,url"],
                cwd=cwd, capture_output=True, text=True, timeout=60,
            )
            if proc.returncode == 0:
                return json.loads(proc.stdout or "[]"), ""
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass  # fall through to the REST API
    repo = _github_repo(cwd)
    if not repo:
        return None, "origin is not a GitHub remote (and gh query failed)"
    url = f"https://api.github.com/repos/{repo}/actions/runs?head_sha={sha}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "fettle-ci-gate",
    })
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return None, f"could not query GitHub Actions: {e}"
    return [
        {
            "databaseId": r.get("id"),
            "workflowName": r.get("name", ""),
            "status": r.get("status", ""),
            "conclusion": r.get("conclusion") or "",
            "url": r.get("html_url", ""),
        }
        for r in payload.get("workflow_runs", [])
    ], ""


def summarize(runs: list[dict]) -> tuple[str, str]:
    """Reduce runs to ``(overall, detail)``.

    overall: success | failure | pending | no-runs. Anything not green is
    named in detail — silence is never a pass.
    """
    if not runs:
        return "no-runs", "no workflow runs found for this commit"
    pending = [r for r in runs if r.get("status") != "completed"]
    if pending:
        names = ", ".join(r.get("workflowName", "?") for r in pending)
        return "pending", f"still running: {names}"
    bad = [r for r in runs if r.get("conclusion") not in _GREEN_CONCLUSIONS]
    if bad:
        detail = "; ".join(
            f"{r.get('workflowName', '?')}: {r.get('conclusion', '?')} ({r.get('url', '')})"
            for r in bad
        )
        return "failure", detail
    return "success", f"{len(runs)} run(s) green"


def _ingest_failure(cwd: str, run_id: object) -> str:
    """Classify a red run's log via ci_ingest; return a reproduction hint."""
    if not (run_id and shutil.which("gh")):
        return ""
    try:
        proc = subprocess.run(
            ["gh", "run", "view", str(run_id), "--log-failed"],
            cwd=cwd, capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0 or not proc.stdout:
        return ""
    from fettle.ci_diagnose import diagnose_failure
    from fettle.ci_ingest import CIFailure, classify_failure, store_failure

    log_tail = "\n".join(proc.stdout.splitlines()[-200:])
    failure = CIFailure(
        run_id=str(run_id),
        classification=classify_failure(log_tail),
        summary=log_tail[-500:].strip(),
        commit=_head_sha(cwd) or "",
    )
    with contextlib.suppress(OSError):
        store_failure(os.path.join(cwd, FAILURE_HISTORY_RELPATH), failure)
    return diagnose_failure(failure).reproduction_command


# ── fettle ci status|wait (minutes-world) ─────────────────────────────────


def run_ci_status(
    cwd: str,
    config: dict,
    *,
    wait: bool = False,
    sha: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Query (and optionally await) the CI verdict for a commit; write stamp.

    Returns the stamp dict, also persisted to .fettle/ci-status.json:
    ok, sha, overall, runs, reproduce, error, ts. Never raises.
    ``progress`` (CLI only) receives a one-line status per poll.
    """
    gate_cfg = config.get("gates", {}).get("ci", {})
    timeout_s = int(gate_cfg.get("timeout_s", 900))
    poll_s = max(1, int(gate_cfg.get("poll_s", 15)))

    stamp: dict = {
        "ok": False, "sha": sha or "", "overall": "error", "runs": [],
        "reproduce": "", "error": "", "ts": time.time(),
    }
    sha = sha or _head_sha(cwd)
    if not sha:
        stamp["error"] = "not a git repository (could not resolve HEAD)"
        _write_stamp(cwd, stamp)
        return stamp
    stamp["sha"] = sha

    deadline = time.monotonic() + timeout_s
    start = time.monotonic()
    # Right after a push, GitHub needs a few seconds to *create* the runs;
    # in wait mode, treat early "no-runs" as pending for a grace period.
    no_runs_grace = time.monotonic() + 60
    overall, detail = "pending", ""
    runs: list[dict] = []
    while True:
        queried, err = _query_runs(cwd, sha)
        if queried is None:
            stamp["overall"], stamp["error"] = "error", err
            _write_stamp(cwd, stamp)
            return stamp
        runs = queried
        overall, detail = summarize(runs)
        still_waiting = overall == "pending" or (
            overall == "no-runs" and time.monotonic() < no_runs_grace
        )
        if not still_waiting or not wait or time.monotonic() >= deadline:
            break
        if progress is not None:
            elapsed = int(time.monotonic() - start)
            done = sum(1 for r in runs if r.get("status") == "completed")
            state = (
                f"{done}/{len(runs)} runs completed" if runs
                else "waiting for runs to appear"
            )
            progress(f"  … {state} ({elapsed}s elapsed, next poll in {poll_s}s)")
        time.sleep(min(poll_s, max(0.0, deadline - time.monotonic())))

    if overall == "pending" and wait:
        detail = f"CI still pending after {timeout_s}s — {detail}"

    stamp["overall"] = overall
    stamp["ok"] = overall == "success"
    stamp["runs"] = [
        {
            "name": r.get("workflowName", ""),
            "status": r.get("status", ""),
            "conclusion": r.get("conclusion", ""),
            "url": r.get("url", ""),
        }
        for r in runs
    ]
    if overall != "success":
        stamp["error"] = detail
    if overall == "failure":
        red = next(
            (r for r in runs if r.get("conclusion") not in _GREEN_CONCLUSIONS),
            None,
        )
        stamp["reproduce"] = _ingest_failure(cwd, (red or {}).get("databaseId"))
    stamp["ts"] = time.time()
    _write_stamp(cwd, stamp)
    return stamp


def _write_stamp(cwd: str, stamp: dict) -> None:
    evidence = build_evidence(
        "ci", exit_code=0 if stamp.get("ok") else 1, scope=stamp.get("sha", ""),
    )
    stamp["evidence_id"] = evidence["evidence_id"]
    path = Path(cwd) / STAMP_RELPATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stamp, indent=2) + "\n")
    except OSError:
        pass  # gate reports the missing stamp — failure stays visible


# ── Push recorder (PostToolUse Bash, milliseconds-world) ──────────────────


def _pushes_path(session_id: str | None) -> Path | None:
    if not session_id:
        return None
    from fettle.config import state_dir
    return state_dir(session_id) / PUSHES_FILENAME


def record_push(ctx: HookContext) -> CheckResult:
    """Record a `git push` issued this session. Passive: never blocks."""
    if not ctx.config.get("gates", {}).get("ci", {}).get("enabled", False):
        return CheckResult.allow()
    command = ctx.tool_input.get("command", "")
    if not command or not _GIT_PUSH_RE.search(command):
        return CheckResult.allow()
    sha = _head_sha(str(ctx.cwd))
    if not sha:
        return CheckResult.allow()
    path = _pushes_path(ctx.session_id or "unknown")
    if path is None:
        return CheckResult.allow()
    entry = {"sha": sha, "ts": time.time(), "command": command[:200]}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # recording is best-effort; the CLI path still works
    return CheckResult.allow()


def _last_push(session_id: str | None) -> dict | None:
    path = _pushes_path(session_id)
    if path is None or not path.is_file():
        return None
    last: dict | None = None
    try:
        for line in path.read_text().splitlines():
            with contextlib.suppress(json.JSONDecodeError):
                entry = json.loads(line)
                if isinstance(entry, dict) and entry.get("sha"):
                    last = entry
    except OSError:
        return None
    return last


# ── Stop gate (milliseconds-world) ────────────────────────────────────────


def run_check(ctx: HookContext) -> CheckResult:
    """Stop hook — a push this session demands a fresh, green CI stamp."""
    cfg = ctx.config.get("gates", {}).get("ci", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    push = _last_push(ctx.session_id or "unknown")
    if push is None:
        return CheckResult.allow()  # nothing pushed — nothing to verify

    stamp_path = ctx.cwd / STAMP_RELPATH
    problem = ""
    if not stamp_path.is_file():
        problem = "remote CI status was never checked"
    else:
        try:
            stamp = json.loads(stamp_path.read_text())
        except (json.JSONDecodeError, OSError):
            stamp = None
        if not isinstance(stamp, dict):
            problem = "CI status stamp is unreadable"
        elif stamp.get("sha") != push.get("sha"):
            problem = "CI status is for a different commit than the last push"
        elif float(stamp.get("ts", 0)) < float(push.get("ts", 0)):
            problem = "CI status predates the last push (stale)"
        elif not stamp.get("ok", False):
            detail = str(stamp.get("error", "")).strip()
            repro = str(stamp.get("reproduce", "")).strip()
            problem = f"remote CI is not green ({stamp.get('overall', '?')})"
            if detail:
                problem += f":\n{detail}"
            if repro:
                problem += f"\nReproduce locally: {repro}"

    if not problem:
        return CheckResult.allow()

    sha = str(push.get("sha", ""))[:12]
    msg = (
        f"CI gate: commit {sha} was pushed this session but the remote "
        f"verdict is not verified green — {problem}\n"
        f"Run: fettle ci wait"
    )
    hso = {
        "hookEventName": ctx.input.hook_event_name,
        "additionalContext": msg,
    }
    if cfg.get("mode", "advisory") == "enforce":
        return CheckResult.block(msg, hook_specific_output=hso)
    return CheckResult.advisory(msg, hook_specific_output=hso)
