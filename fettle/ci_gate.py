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
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from fettle import __version__
from fettle.dispatcher_types import CheckResult, Decision, HookContext
from fettle.evidence import (
    EvidenceArtifact,
    EvidenceValidationContext,
    Validity,
    validate_artifact,
)
from fettle.finding import ResultState
from fettle.overrides import OverrideContext, load_override_ledger, select_override
from fettle.trace import build_evidence, log_decision

STAMP_RELPATH = os.path.join(".fettle", "ci-status.json")
EVIDENCE_RELPATH = os.path.join(".fettle", "ci-evidence.json")
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


def policy_digest(config: dict) -> str:
    """Content identity of the effective policy governing the CI verdict."""
    gate_cfg = config.get("gates", {}).get("ci", {})
    canonical = json.dumps(gate_cfg, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


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
        _write_stamp(cwd, stamp, config)
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
            _write_stamp(cwd, stamp, config)
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
            "id": r.get("databaseId"),
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
    _write_stamp(cwd, stamp, config)
    return stamp


def _write_stamp(cwd: str, stamp: dict, config: dict) -> None:
    evidence = build_evidence(
        "ci", exit_code=0 if stamp.get("ok") else 1, scope=stamp.get("sha", ""),
    )
    stamp["evidence_id"] = evidence["evidence_id"]
    try:
        artifact = _ci_artifact(stamp, config)
        _write_bytes_atomic(Path(cwd) / EVIDENCE_RELPATH, artifact.to_bytes())
        stamp["canonical_evidence"] = _artifact_reference(artifact)
        stamp["canonical_observation_id"] = artifact.observation_id
    except (OSError, TypeError, ValueError):
        stamp.pop("canonical_evidence", None)
        stamp.pop("canonical_observation_id", None)
        stamp["ok"] = False
        stamp["canonical_evidence_error"] = "unavailable"
        detail = "canonical CI evidence could not be persisted"
        stamp["error"] = "\n".join(filter(None, (str(stamp.get("error") or ""), detail)))
    path = Path(cwd) / STAMP_RELPATH
    stamp_written = False
    try:
        _write_bytes_atomic(path, (json.dumps(stamp, indent=2) + "\n").encode())
        stamp_written = True
    except OSError:
        pass  # gate reports the missing stamp — failure stays visible
    if stamp_written and "canonical_evidence" in stamp:
        _log_canonical_inspection(
            cwd, stamp, Validity.VALID, accepted=bool(stamp.get("ok")),
        )


def _json_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )
    normalized = unicodedata.normalize("NFC", encoded).encode("utf-8")
    return "sha256:" + hashlib.sha256(normalized).hexdigest()


def _scope_projection(stamp: dict) -> list[dict[str, object]]:
    return sorted((
        {
            "id": run.get("id"),
            "name": str(run.get("name") or ""),
        }
        for run in stamp.get("runs", []) if isinstance(run, dict)
    ), key=lambda run: (str(run["name"]), str(run["id"])))


def _producer_digest() -> str:
    return "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _ci_artifact(stamp: dict, config: dict) -> EvidenceArtifact:
    revision = str(stamp.get("sha") or "")
    source = {"snapshot_digest": _json_digest({"revision": revision})}
    if revision:
        source["revision"] = revision
    overall = str(stamp.get("overall") or "error")
    if overall == "success":
        result_state = "pass"
    elif overall == "failure":
        result_state = "violation"
    elif overall == "error":
        result_state = "tool_error"
    else:
        result_state = "unknown"
    complete = overall in {"success", "failure"}
    run_ids = [
        run.get("id") for run in stamp.get("runs", [])
        if isinstance(run, dict) and isinstance(run.get("id"), int)
    ]
    return EvidenceArtifact.create(
        kind="fettle.ci",
        producer={
            "id": "fettle.ci",
            "version": __version__,
            "implementation_digest": _producer_digest(),
        },
        result_state=result_state,
        completeness="complete" if complete else "unknown",
        trust_class="external",
        source=source,
        policy_digest=policy_digest(config),
        scope_digest=_json_digest(_scope_projection(stamp)),
        observation_id="ci-" + uuid.uuid4().hex,
        observed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        payload={
            "overall": overall,
            "provider": "github-actions",
            "run_ids": run_ids,
            "toolchain": "github-actions-api",
        },
    )


def _artifact_reference(artifact: EvidenceArtifact) -> dict:
    return {
        "artifact_digest": artifact.artifact_digest,
        "kind": artifact.kind,
        "schema_version": artifact.schema_version,
        "expected": {
            "source_snapshot_digest": artifact.source["snapshot_digest"],
            "policy_digest": artifact.policy_digest,
            "scope_digest": artifact.scope_digest,
            "producer_id": artifact.producer["id"],
        },
    }


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = ""
    finally:
        if temporary:
            with contextlib.suppress(OSError):
                os.unlink(temporary)


def _canonical_evidence_validity(
    cwd: str,
    config: dict,
    stamp: dict,
    *,
    artifact_value: object | None = None,
) -> Validity:
    reference = stamp.get("canonical_evidence")
    if not isinstance(reference, dict):
        return Validity.MALFORMED
    if reference.get("schema_version") != "1" or reference.get("kind") != "fettle.ci":
        return Validity.UNSUPPORTED
    expected = reference.get("expected")
    if not isinstance(expected, dict):
        return Validity.MALFORMED
    revision = str(stamp.get("sha") or "")
    context = EvidenceValidationContext(
        kind="fettle.ci",
        source_snapshot_digest=_json_digest({"revision": revision}),
        source_revision=revision or None,
        policy_digest=policy_digest(config),
        scope_digest=_json_digest(_scope_projection(stamp)),
        producer_id="fettle.ci",
        producer_versions=frozenset({__version__}),
        producer_implementation_digest=_producer_digest(),
        allowed_trust_classes=frozenset({"external"}),
        recovery_action="fettle ci wait",
    )
    if artifact_value is None:
        path = Path(cwd) / EVIDENCE_RELPATH
        if not path.is_file():
            return Validity.MISSING
        try:
            artifact_value = path.read_bytes()
        except OSError:
            return Validity.UNAVAILABLE
    result = validate_artifact(artifact_value, context)
    if result.validity != Validity.VALID:
        return result.validity
    try:
        artifact = (
            artifact_value.to_dict() if isinstance(artifact_value, EvidenceArtifact)
            else json.loads(artifact_value) if isinstance(artifact_value, (bytes, str))
            else artifact_value
        )
        artifact_digest = artifact["artifact_digest"]
        observation_id = artifact["observation_id"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return Validity.MALFORMED
    if reference.get("artifact_digest") != artifact_digest:
        return Validity.TAMPERED
    if stamp.get("canonical_observation_id") != observation_id:
        return Validity.DUPLICATE_ID
    requested = {
        "source_snapshot_digest": context.source_snapshot_digest,
        "policy_digest": context.policy_digest,
        "scope_digest": context.scope_digest,
        "producer_id": context.producer_id,
    }
    if expected != requested:
        return Validity.MALFORMED
    return Validity.VALID


def _log_canonical_inspection(
    cwd: str,
    stamp: dict,
    validity: Validity,
    *,
    accepted: bool,
) -> None:
    reference = stamp.get("canonical_evidence")
    if not isinstance(reference, dict):
        return
    expected = reference.get("expected")
    if not isinstance(expected, dict):
        expected = {}
    scope = ", ".join(
        str(run.get("name") or "?")
        for run in stamp.get("runs", []) if isinstance(run, dict)
    ) or "no workflows"
    overall = str(stamp.get("overall") or "error")
    complete = "complete" if overall in {"success", "failure"} else "unknown"
    reason = (
        "exact bindings matched" if accepted
        else str(stamp.get("error") or "remote CI result was not accepted")
    )
    if validity != Validity.VALID:
        reason = f"canonical CI evidence is {validity.value}"
    evidence = dict(reference)
    evidence.update({
        "availability": "available" if validity != Validity.MISSING else "missing",
        "inspection": {
            "producer": "fettle.ci",
            "scope": scope,
            "source_binding": str(expected.get("source_snapshot_digest") or "unknown"),
            "policy_binding": str(expected.get("policy_digest") or "unknown"),
            "result": "pass" if overall == "success" else (
                "violation" if overall == "failure" else "unknown"
            ),
            "completeness": complete,
            "freshness": "current" if validity == Validity.VALID else "stale",
            "validity": validity.value,
            "accepted": accepted,
            "reason": reason,
            "recovery_action": "" if accepted else "fettle ci wait",
        },
    })
    log_decision(
        hook="ci_gate", status="pass" if accepted else "unknown",
        file=cwd, evidence=[evidence],
    )


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
    stamp: dict | None = None
    stamp_ts: float | None = None
    try:
        push_ts = float(push.get("ts", ""))
        if not math.isfinite(push_ts):
            raise ValueError
    except (TypeError, ValueError):
        push_ts = None
        problem = "last push timestamp is invalid"
    if problem:
        pass
    elif not stamp_path.is_file():
        problem = "remote CI status was never checked"
    else:
        try:
            stamp = json.loads(stamp_path.read_text())
        except (json.JSONDecodeError, OSError):
            stamp = None
        if not isinstance(stamp, dict):
            problem = "CI status stamp is unreadable"
        else:
            try:
                stamp_ts = float(stamp.get("ts", 0))
                if not math.isfinite(stamp_ts):
                    raise ValueError
            except (TypeError, ValueError):
                problem = "CI status timestamp is invalid"
        if not problem and stamp.get("sha") != push.get("sha"):
            problem = "CI status is for a different commit than the last push"
        elif not problem and stamp_ts is not None and push_ts is not None and stamp_ts < push_ts:
            problem = "CI status predates the last push (stale)"
        elif not problem and not stamp.get("ok", False):
            detail = str(stamp.get("error", "")).strip()
            repro = str(stamp.get("reproduce", "")).strip()
            problem = f"remote CI is not green ({stamp.get('overall', '?')})"
            if detail:
                problem += f":\n{detail}"
            if repro:
                problem += f"\nReproduce locally: {repro}"
        elif not problem and "canonical_evidence" in stamp:
            validity = _canonical_evidence_validity(str(ctx.cwd), ctx.config, stamp)
            if validity != Validity.VALID:
                problem = f"canonical CI evidence is {validity.value}"
                _log_canonical_inspection(str(ctx.cwd), stamp, validity, accepted=False)

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
        evidence_id = str((stamp or {}).get("evidence_id", "")).strip()
        if (
            isinstance(stamp, dict)
            and stamp.get("sha") == push.get("sha")
            and stamp_ts is not None
            and push_ts is not None
            and stamp_ts >= push_ts
            and not stamp.get("ok", False)
            and evidence_id
        ):
            ledger = load_override_ledger(ctx.cwd)
            if ledger.invalid:
                msg += "\nCanonical override ledger is invalid; override evaluation failed closed."
                hso["additionalContext"] = msg
            else:
                selection = select_override(ledger.records, OverrideContext(
                    check_id="ci.verdict",
                    scope=".",
                    revision=str(push.get("sha", "")),
                    policy_digest=policy_digest(ctx.config),
                    evidence_id=evidence_id,
                    surface="ci",
                ))
                if selection.status == "overridden" and selection.record is not None:
                    record = selection.record
                    override_msg = (
                        f"CI gate OVERRIDDEN by {record.actor}: {record.reason}\n"
                        f"Override: {record.override_id} (expires {record.expiry})\n{msg}"
                    )
                    override_hso = dict(hso, additionalContext=override_msg)
                    if log_decision(
                        hook="ci_gate",
                        status="overridden",
                        file=str(ctx.cwd),
                        evidence=[{"kind": "ci", "evidence_id": evidence_id,
                                   "scope": str(push.get("sha", ""))}],
                        overrides=[record.to_dict()],
                        session_id=ctx.session_id or "",
                    ):
                        return CheckResult(
                            decision=Decision.ADVISORY,
                            message=override_msg,
                            hook_specific_output=override_hso,
                            result_state=ResultState.OVERRIDDEN,
                        )
                    msg += "\nOverride audit write failed; override evaluation failed closed."
                    hso["additionalContext"] = msg
        return CheckResult.block(msg, hook_specific_output=hso)
    return CheckResult.advisory(msg, hook_specific_output=hso)
