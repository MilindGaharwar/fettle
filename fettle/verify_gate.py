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
import hashlib
import json
import os
import shlex
import subprocess
import tempfile
import time
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fettle import __version__
from fettle.dispatcher_types import CheckResult, HookContext
from fettle.evidence import (
    EvidenceArtifact,
    EvidenceValidationContext,
    Validity,
    validate_artifact,
)
from fettle.paths import classify_file
from fettle.profile import detect_profile
from fettle.test_discovery import discover_test_config
from fettle.test_runner_opts import build_pytest_args, record_failures
from fettle.trace import build_evidence
from fettle.workspace import Workspace, route_file_to_workspace

STAMP_RELPATH = os.path.join(".fettle", "verify.json")
EVIDENCE_RELPATH = os.path.join(".fettle", "verify-evidence.json")
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
    """Return edited implementation/tests, including files deleted after editing."""
    return [
        f for f in _edited_files(edits_path)
        if classify_file(f) in ("implementation", "test")
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
            cwd,
            affected,
            timeout_s=timeout_s,
            session_id=session_id,
            impacted=not full and scope_cfg == "impacted",
            parallel=bool(gate_cfg.get("parallel", False)),
            config=config,
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
        _write_stamp(cwd, stamp, config)
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
    _write_stamp(cwd, stamp, config)
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
    impacted: bool,
    parallel: bool,
    config: dict | None = None,
) -> dict:
    """Run reliable impacted tests or each affected workspace's full suite."""
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
            "impacted": [],
            "head_sha": _head_sha(cwd),
            "dirty_digest": _dirty_digest(str(workspace_root)),
        }
        if not workspace.test_command:
            record["error"] = "no test command discovered for workspace"
            records.append(record)
            continue
        argv = shlex.split(workspace.test_command)
        if impacted and workspace.language == "python":
            workspace_files = [str(Path(cwd) / file_path) for file_path in edited]
            mapped = impacted_tests(
                str(workspace_root), workspace_files, workspace.test_roots or ["tests"],
            )
            if mapped:
                record["scope"] = "impacted"
                record["impacted"] = mapped
                argv = [
                    arg for arg in argv
                    if arg.rstrip("/") not in (workspace.test_roots or [])
                ]
                argv += build_pytest_args(
                    mode="changed",
                    files=mapped,
                    failure_history=str(workspace_root / FAILURE_HISTORY_RELPATH),
                    parallel=parallel,
                )
                record["command"] = shlex.join(argv)
        start = time.monotonic()
        try:
            proc = subprocess.run(
                argv, cwd=str(workspace_root),
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
            duration_ms=record["duration_s"] * 1000, scope=record["scope"], workspace=workspace.path,
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
    _write_stamp(cwd, stamp, config or {})
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


def _write_stamp(cwd: str, stamp: dict, config: dict) -> None:
    evidence = build_evidence(
        "verify", command=stamp.get("command", ""), exit_code=stamp.get("exit_code"),
        duration_ms=float(stamp.get("duration_s", 0)) * 1000, scope=stamp.get("scope", ""),
    )
    stamp["evidence_id"] = evidence["evidence_id"]
    try:
        artifact = _verification_artifact(cwd, stamp, config)
        _write_bytes_atomic(Path(cwd) / EVIDENCE_RELPATH, artifact.to_bytes())
        stamp["canonical_evidence"] = _artifact_reference(artifact)
        stamp["canonical_observation_id"] = artifact.observation_id
    except (OSError, TypeError, ValueError):
        stamp.pop("canonical_evidence", None)
        stamp.pop("canonical_observation_id", None)
        stamp["ok"] = False
        stamp["canonical_evidence_error"] = "unavailable"
        detail = "canonical evidence could not be persisted"
        stamp["error"] = "\n".join(filter(None, (str(stamp.get("error") or ""), detail)))
    path = Path(cwd) / STAMP_RELPATH
    try:
        _write_bytes_atomic(path, (json.dumps(stamp, indent=2) + "\n").encode())
    except OSError:
        pass  # gate will report the missing stamp — failure stays visible


def _json_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    )
    normalized = unicodedata.normalize("NFC", encoded).encode("utf-8")
    return "sha256:" + hashlib.sha256(normalized).hexdigest()


def _policy_digest(config: dict) -> str:
    return _json_digest(config)


def _source_snapshot(cwd: str) -> tuple[str, str]:
    revision = _head_sha(cwd)
    status = _git_out(cwd, "status", "--porcelain=v1", "--untracked-files=all")
    untracked: list[dict[str, str]] = []
    root = Path(cwd).resolve()
    for line in status.splitlines():
        if not line.startswith("?? "):
            continue
        relative = line[3:]
        if relative == ".fettle" or relative.startswith(".fettle/"):
            continue
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
            digest = hashlib.sha256()
            with candidate.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except (OSError, ValueError):
            continue
        untracked.append({
            "path": relative.replace("\\", "/"),
            "digest": digest.hexdigest(),
        })
    snapshot = {
        "revision": revision,
        "status": "\n".join(
            line for line in status.splitlines()
            if line[3:] != ".fettle" and not line[3:].startswith(".fettle/")
        ),
        "diff": _git_out(cwd, "diff", "HEAD", "--binary"),
        "untracked": sorted(untracked, key=lambda item: item["path"]),
    }
    return _json_digest(snapshot), revision


def _scope_projection(stamp: dict) -> dict:
    projection: dict = {
        "scope": str(stamp.get("scope") or ""),
        "impacted": sorted(str(path) for path in stamp.get("impacted") or []),
    }
    if stamp.get("workspaces"):
        projection["workspaces"] = sorted((
            {
                "path": str(record.get("path") or ""),
                "scope": str(record.get("scope") or ""),
                "impacted": sorted(str(path) for path in record.get("impacted") or []),
            }
            for record in stamp["workspaces"] if isinstance(record, dict)
        ), key=lambda record: record["path"])
    return projection


def _producer_digest() -> str:
    return "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _verification_artifact(cwd: str, stamp: dict, config: dict) -> EvidenceArtifact:
    source_digest, revision = _source_snapshot(cwd)
    source = {"snapshot_digest": source_digest}
    if revision:
        source["revision"] = revision
    exit_code = stamp.get("exit_code")
    if stamp.get("ok"):
        result_state = "pass"
    elif isinstance(exit_code, int) and exit_code >= 0:
        result_state = "violation"
    else:
        result_state = "tool_error"
    return EvidenceArtifact.create(
        kind="fettle.verify",
        producer={
            "id": "fettle.verify",
            "version": __version__,
            "implementation_digest": _producer_digest(),
        },
        result_state=result_state,
        completeness="complete" if isinstance(exit_code, int) and exit_code >= 0 else "unknown",
        trust_class="authoritative",
        source=source,
        policy_digest=_policy_digest(config),
        scope_digest=_json_digest(_scope_projection(stamp)),
        observation_id="verify-" + uuid.uuid4().hex,
        observed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        payload={
            "exit_code": exit_code if isinstance(exit_code, int) else -1,
            "scope": str(stamp.get("scope") or ""),
        },
    )


def _artifact_reference(artifact: EvidenceArtifact) -> dict:
    expected = {
        "source_snapshot_digest": artifact.source["snapshot_digest"],
        "policy_digest": artifact.policy_digest,
        "scope_digest": artifact.scope_digest,
        "producer_id": artifact.producer["id"],
    }
    return {
        "artifact_digest": artifact.artifact_digest,
        "kind": artifact.kind,
        "schema_version": artifact.schema_version,
        "expected": expected,
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
    finally:
        with contextlib.suppress(OSError):
            os.unlink(temporary)


def _canonical_evidence_validity(cwd: str, config: dict, stamp: dict) -> Validity:
    reference = stamp.get("canonical_evidence")
    if not isinstance(reference, dict):
        return Validity.MALFORMED
    if (
        reference.get("schema_version") != "1"
        or reference.get("kind") != "fettle.verify"
    ):
        return Validity.UNSUPPORTED
    expected = reference.get("expected")
    if not isinstance(expected, dict):
        return Validity.MALFORMED
    source_digest, revision = _source_snapshot(cwd)
    context = EvidenceValidationContext(
        kind="fettle.verify",
        source_snapshot_digest=source_digest,
        source_revision=revision or None,
        policy_digest=_policy_digest(config),
        scope_digest=_json_digest(_scope_projection(stamp)),
        producer_id="fettle.verify",
        producer_versions=frozenset({__version__}),
        producer_implementation_digest=_producer_digest(),
        recovery_action="fettle verify",
    )
    path = Path(cwd) / EVIDENCE_RELPATH
    if not path.is_file():
        return Validity.MISSING
    try:
        content = path.read_bytes()
    except OSError:
        return Validity.UNAVAILABLE
    result = validate_artifact(content, context)
    if result.validity != Validity.VALID:
        return result.validity
    try:
        artifact_data = json.loads(content)
        artifact_digest = artifact_data["artifact_digest"]
        observation_id = artifact_data["observation_id"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return Validity.MALFORMED
    if reference.get("artifact_digest") != artifact_digest:
        return Validity.TAMPERED
    if stamp.get("canonical_observation_id") != observation_id:
        return Validity.DUPLICATE_ID
    requested = {
        "source_snapshot_digest": source_digest,
        "policy_digest": context.policy_digest,
        "scope_digest": context.scope_digest,
        "producer_id": context.producer_id,
    }
    if expected != requested:
        return Validity.MALFORMED
    return Validity.VALID


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
            # The stamp writer always embeds a canonical reference (or forces
            # ok=false) — a green stamp without one is forged or pre-canonical.
            if "canonical_evidence" not in stamp:
                problem = "canonical verification evidence is missing"
            else:
                validity = _canonical_evidence_validity(str(ctx.cwd), ctx.config, stamp)
                if validity != Validity.VALID:
                    problem = f"canonical verification evidence is {validity.value}"

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
