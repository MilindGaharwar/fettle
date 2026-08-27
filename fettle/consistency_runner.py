"""P55/SC3 bounded execution for repository-owned consistency adapters."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path

from fettle.consistency_compare import ComparisonError, fingerprint_value
from fettle.graph_types import canonical_digest
from fettle.paths import is_within_repo
from fettle.state_consistency import (
    AdapterManifest,
    ConsistencyContract,
    validate_executable_contract,
)

MAX_OUTPUT_BYTES = 64 * 1024


def _json_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _drain(stream, chunks: list[bytes], overflow: list[bool]) -> None:
    retained = 0
    while True:
        chunk = stream.read(8192)
        if not chunk:
            break
        remaining = MAX_OUTPUT_BYTES + 1 - retained
        if remaining > 0:
            kept = chunk[:remaining]
            chunks.append(kept)
            retained += len(kept)
        if retained > MAX_OUTPUT_BYTES or len(chunk) > remaining:
            overflow[0] = True


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _source_identity(root: Path) -> tuple[str, str]:
    revision = _git(root, "rev-parse", "HEAD") or "unversioned"
    dirty = _git(root, "status", "--porcelain")
    return revision, canonical_digest({"revision": revision, "dirty": dirty})


def _error_result(contract: ConsistencyContract, kind: str, message: str) -> dict:
    return {
        "schema_version": 1,
        "contract_id": contract.id,
        "contract_digest": contract.digest,
        "outcome": "config_error",
        "primary_error": {"phase": "configuration", "kind": kind, "message": message},
        "operations": [],
        "canonical_observation": None,
        "observer_observations": [],
        "cleanup": {"state": "not_run"},
        "rerun": f"fettle consistency run {contract.id}",
    }


def _resolve_environment(
    manifest: AdapterManifest,
    supplied: dict[str, str],
    generated: dict[str, str],
) -> tuple[dict[str, str] | None, str]:
    env: dict[str, str] = {}
    for name in manifest.env:
        if name in generated:
            env[name] = generated[name]
        elif name in supplied:
            env[name] = supplied[name]
        else:
            return None, f"required environment variable {name!r} is unavailable"
    return env, ""


def _run_operation(
    root: Path,
    phase: str,
    manifest: AdapterManifest,
    environment: dict[str, str],
    *,
    timeout_s: float | None = None,
) -> tuple[dict, dict | None]:
    cwd = (root / manifest.cwd).resolve()
    started = time.monotonic()
    command_digest = canonical_digest(list(manifest.argv))
    try:
        process_env = {
            key: os.environ[key] for key in ("PATH", "SYSTEMROOT") if key in os.environ
        }
        process_env.update(environment)
        process = subprocess.Popen(
            list(manifest.argv), cwd=cwd, env=process_env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []
        stdout_overflow = [False]
        stderr_overflow = [False]
        assert process.stdout is not None and process.stderr is not None
        readers = [
            threading.Thread(target=_drain,
                             args=(process.stdout, stdout_chunks, stdout_overflow), daemon=True),
            threading.Thread(target=_drain,
                             args=(process.stderr, stderr_chunks, stderr_overflow), daemon=True),
        ]
        for reader in readers:
            reader.start()
        try:
            operation_timeout = manifest.timeout_s if timeout_s is None else min(
                manifest.timeout_s, timeout_s
            )
            process.wait(timeout=operation_timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            timed_out = True
        except KeyboardInterrupt:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise
        for reader in readers:
            reader.join()
        stdout = b"".join(stdout_chunks)
        output_overflow = stdout_overflow[0] or stderr_overflow[0]
    except OSError as exc:
        elapsed = int((time.monotonic() - started) * 1000)
        return ({
            "phase": phase, "state": "tool_error", "duration_ms": elapsed,
            "command_digest": command_digest, "output_digest": "",
        }, {"phase": phase, "kind": "unavailable", "message": str(exc)})

    elapsed = int((time.monotonic() - started) * 1000)
    output_digest = "sha256:" + hashlib.sha256(stdout).hexdigest()
    operation = {
        "phase": phase,
        "state": "tool_error" if timed_out or process.returncode else "pass",
        "duration_ms": elapsed,
        "command_digest": command_digest,
        "output_digest": output_digest,
        "exit_code": process.returncode,
    }
    if timed_out:
        return operation, {"phase": phase, "kind": "timeout",
                           "message": f"adapter exceeded {operation_timeout:g}s timeout"}
    if process.returncode:
        return operation, {"phase": phase, "kind": "exit",
                           "message": f"adapter exited {process.returncode}"}
    if output_overflow:
        operation["state"] = "tool_error"
        return operation, {"phase": phase, "kind": "oversized_output",
                           "message": f"adapter output exceeded {MAX_OUTPUT_BYTES} bytes"}
    try:
        payload = json.loads(
            stdout,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite number {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        operation["state"] = "unknown"
        return operation, {"phase": phase, "kind": "malformed_output",
                           "message": "adapter did not emit valid JSON"}
    if not isinstance(payload, dict):
        operation["state"] = "unknown"
        return operation, {"phase": phase, "kind": "malformed_output",
                           "message": "adapter output must be a JSON object"}
    expected_marker = "fettle-observation" if (
        phase == "canonical_read" or phase.startswith("observer:")
    ) else "fettle-operation"
    if payload.get(expected_marker) != "v1":
        operation["state"] = "unknown"
        return operation, {
            "phase": phase, "kind": "malformed_output",
            "message": f"adapter output must declare {expected_marker}: v1",
        }
    return operation, payload


def _observation(
    observer: str,
    surface: str,
    payload: dict,
    comparator_kind: str,
) -> dict | None:
    if payload.get("fettle-observation") != "v1" or "value" not in payload:
        return None
    value = payload["value"]
    try:
        fingerprint = fingerprint_value(value, comparator_kind)
    except ComparisonError:
        return None
    return {
        "observer": observer,
        "surface": surface,
        "fingerprint": fingerprint,
    }


def execute_contract(
    root: str | Path,
    contract: ConsistencyContract,
    *,
    policy: dict,
    environment: dict[str, str] | None = None,
) -> dict:
    """Execute bounded phases and evaluate immediate/eventual consistency."""
    root_path = Path(root).resolve()
    readiness = validate_executable_contract(contract)
    if readiness:
        return _error_result(contract, "invalid_contract", readiness[0].message)

    supplied = dict(os.environ if environment is None else environment)
    run_id = uuid.uuid4().hex
    generated = {"FETTLE_RUN_ID": run_id, "FETTLE_SUBJECT_ID": uuid.uuid4().hex}
    resolved: dict[str, tuple[AdapterManifest, dict[str, str]]] = {}
    for name, manifest in contract.adapters.items():
        cwd = (root_path / manifest.cwd).resolve()
        if not is_within_repo(cwd, root_path):
            return _error_result(contract, "path_escape",
                                 f"adapter {name!r} working directory escapes repository")
        env, error = _resolve_environment(manifest, supplied, generated)
        if error:
            return _error_result(contract, "missing_environment", error)
        assert env is not None
        resolved[name] = manifest, env

    revision, source_digest = _source_identity(root_path)
    operations: list[dict] = []
    canonical = None
    observations: list[dict] = []
    primary_error = None
    cleanup = {"state": "not_run"}

    phases = []
    if contract.setup_adapter:
        phases.append(("setup", contract.setup_adapter, None))
    phases.extend([
        ("mutation", contract.mutation_adapter, None),
        ("canonical_read", contract.canonical_read_adapter, None),
    ])
    try:
        for phase, adapter_name, _observer in phases:
            manifest, env = resolved[adapter_name]
            operation, payload = _run_operation(root_path, phase, manifest, env)
            operations.append(operation)
            if operation["state"] != "pass":
                primary_error = payload
                break
            assert payload is not None
            if phase == "canonical_read":
                canonical = _observation(
                    "canonical", "canonical", payload, contract.comparator_kind
                )
                if canonical is None:
                    primary_error = {"phase": phase, "kind": "malformed_output",
                                     "message": "canonical read emitted no comparable json-v1 observation"}
                    break
        if primary_error is None and canonical is not None:
            evaluation_started = time.monotonic()
            deadline = evaluation_started + contract.deadline_ms / 1000
            pending = {observer["id"]: observer for observer in contract.observers}
            attempts = {observer_id: 0 for observer_id in pending}
            latest: dict[str, dict] = {}
            consistency_deadline_reached = False
            while pending:
                if latest and time.monotonic() >= deadline:
                    break
                for observer_id, observer in tuple(pending.items()):
                    phase = f"observer:{observer_id}"
                    manifest, env = resolved[observer["adapter"]]
                    remaining = deadline - time.monotonic()
                    deadline_limited = remaining < manifest.timeout_s
                    operation, payload = _run_operation(
                        root_path,
                        phase,
                        manifest,
                        env,
                        timeout_s=max(remaining, 0.001),
                    )
                    operations.append(operation)
                    attempts[observer_id] += 1
                    if operation["state"] != "pass":
                        if (
                            contract.model == "eventual"
                            and deadline_limited
                            and latest.get(observer_id) is not None
                            and payload is not None
                            and payload.get("kind") == "timeout"
                        ):
                            operation["state"] = "deadline"
                            consistency_deadline_reached = True
                        else:
                            primary_error = payload
                        break
                    assert payload is not None
                    observed = _observation(
                        observer_id,
                        observer.get("surface", ""),
                        payload,
                        contract.comparator_kind,
                    )
                    if observed is None:
                        primary_error = {
                            "phase": phase,
                            "kind": "malformed_output",
                            "message": "observer emitted no comparable json-v1 observation",
                        }
                        break
                    observed["attempts"] = attempts[observer_id]
                    observed["duration_ms"] = int(
                        (time.monotonic() - evaluation_started) * 1000
                    )
                    latest[observer_id] = observed
                    if observed["fingerprint"] == canonical["fingerprint"]:
                        observed["state"] = "converged"
                        pending.pop(observer_id)
                if (primary_error or consistency_deadline_reached or not pending
                        or contract.model == "immediate"):
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                poll_interval = contract.poll_interval_ms / 1000
                if remaining < poll_interval:
                    time.sleep(remaining)
                    break
                time.sleep(poll_interval)

            elapsed_ms = int((time.monotonic() - evaluation_started) * 1000)
            for observer_id, observed in latest.items():
                if observer_id in pending:
                    observed["state"] = (
                        "divergent" if contract.model == "immediate" else "stale"
                    )
                    observed["duration_ms"] = elapsed_ms
            observations = [
                latest[observer["id"]]
                for observer in contract.observers
                if observer["id"] in latest
            ]
    finally:
        manifest, env = resolved[contract.cleanup_adapter]
        cleanup_op, cleanup_payload = _run_operation(root_path, "cleanup", manifest, env)
        operations.append(cleanup_op)
        cleanup = {"state": cleanup_op["state"]}
        if cleanup_payload and cleanup_op["state"] != "pass":
            cleanup["error"] = cleanup_payload

    if primary_error:
        outcome = "unknown" if primary_error["kind"] == "malformed_output" else "tool_error"
    elif contract.model == "immediate" and any(
        observation["state"] == "divergent" for observation in observations
    ):
        outcome = "divergent"
    elif contract.model == "eventual" and any(
        observation["state"] == "stale" for observation in observations
    ):
        outcome = "stale"
    else:
        outcome = "converged"
    if cleanup["state"] != "pass":
        outcome = "tool_error"
    return {
        "schema_version": 1,
        "run_id": run_id,
        "contract_id": contract.id,
        "contract_digest": contract.digest,
        "source_revision": revision,
        "source_digest": source_digest,
        "policy_digest": _json_digest(policy),
        "adapter_digest": canonical_digest({
            name: manifest.implementation_digest
            for name, manifest in sorted(contract.adapters.items())
        }),
        "outcome": outcome,
        "primary_error": primary_error,
        "operations": operations,
        "canonical_observation": canonical,
        "observer_observations": observations,
        "cleanup": cleanup,
        "rerun": f"fettle consistency run {contract.id}",
    }
