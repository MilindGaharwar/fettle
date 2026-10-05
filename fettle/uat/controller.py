"""Operator-approved read-only CLI observations, isolated from the tested process."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import selectors
import subprocess
import sys
import time
import uuid
from contextlib import ExitStack
from pathlib import Path

from fettle.uat.session import _digest, _file_digest, _redact_secrets, _write_bytes_atomic

MAX_OUTPUT = 65536
MAX_CONTRACT = 1048576
MAX_RECEIPT = 16 * MAX_CONTRACT
MODE = "readonly-cli-v1"


def _store_root() -> Path:
    return Path.home() / ".local" / "state" / "fettle" / "uat-capture"


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate contract field: {key}")
        result[key] = value
    return result


def load_contract(path: str, approval: str, scenarios: list[dict]) -> dict:
    contract_path = Path(path)
    if not contract_path.is_file() or contract_path.stat().st_size > MAX_CONTRACT:
        raise ValueError("contract must be a bounded regular file")
    with contract_path.open("rb") as handle:
        content = handle.read(MAX_CONTRACT + 1)
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    if len(content) > MAX_CONTRACT or approval != digest:
        raise ValueError("contract is too large or differs from approved sha256; review and approve it")
    contract = json.loads(content, object_pairs_hook=_unique_object)
    if _redact_secrets(content.decode("utf-8"))[1]:
        raise ValueError("possible secret in contract; use synthetic acceptance inputs")
    if isinstance(contract, dict) and contract.get("schema_version") == 2:
        from fettle.uat.network_controller import validate_contract

        validate_contract(contract, scenarios)
        return contract
    if (not isinstance(contract, dict)
            or set(contract) != {"schema_version", "scenario_digest", "actions"}
            or type(contract["schema_version"]) is not int
            or contract["schema_version"] != 1
            or contract["scenario_digest"] != _digest(scenarios)):
        raise ValueError("invalid or stale version-1 CLI contract; bind current active scenarios")
    actions = contract["actions"]
    if not isinstance(actions, list) or not actions or len(actions) > 100:
        raise ValueError("contract needs 1-100 scenario actions")
    for action in actions:
        _validate_action(action)
    if sorted(action["scenario_id"] for action in actions) != sorted(s["id"] for s in scenarios):
        raise ValueError("contract must cover every active scenario exactly once")
    if _redact_secrets(content.decode("utf-8"))[1]:
        raise ValueError("possible secret in contract; use synthetic acceptance inputs")
    return contract


def _validate_action(action: dict) -> None:
    if (not isinstance(action, dict)
            or set(action) != {"scenario_id", "argv", "timeout_s", "expect"}
            or not isinstance(action["scenario_id"], str)):
        raise ValueError("invalid CLI action fields")
    arguments = action["argv"]
    if (not isinstance(arguments, list) or not 1 <= len(arguments) <= 100
            or any(not isinstance(arg, str) or "\0" in arg for arg in arguments)
            or not Path(arguments[0]).is_absolute()
            or not Path(arguments[0]).is_file()
            or not os.access(arguments[0], os.X_OK)):
        raise ValueError("argv requires an absolute available executable and string arguments")
    if type(action["timeout_s"]) is not int or not 1 <= action["timeout_s"] <= 60:
        raise ValueError("action timeout_s must be an integer from 1 to 60")
    expected = action["expect"]
    if (not isinstance(expected, dict) or set(expected) != {"exit_code", "stdout", "stderr"}
            or type(expected["exit_code"]) is not int or not 0 <= expected["exit_code"] <= 255
            or any(not isinstance(expected[name], str) or len(expected[name].encode()) > MAX_OUTPUT
                   for name in ("stdout", "stderr"))):
        raise ValueError("expect requires an exit code from 0 to 255 and bounded exact output strings")


def _source(root: str) -> dict:
    from fettle.source_snapshot import working_snapshot

    result = working_snapshot(root)
    if result["status"] != "completed":
        raise ValueError(result.get("message", "source snapshot unavailable"))
    entries = {name: entry for name, entry in result["snapshot"]["entries"].items()
               if name.split("/", 1)[0] not in {".fettle", ".git"}}
    if not entries or any(entry.get("mode") == "120000" for entry in entries.values()):
        raise ValueError("CLI capture needs nonempty regular source files; symlink inputs unsupported")
    if any(not (Path(root) / name).resolve().is_relative_to(Path(root).resolve()) for name in entries):
        raise ValueError("source input escapes product root")
    return entries


def _runtime(actions: list[dict]) -> dict:
    return {
        "platform": platform.platform(),
        "executables": {str(Path(action["argv"][0]).resolve()):
                        _file_digest(Path(action["argv"][0]).resolve()) for action in actions},
        "controller": _file_digest(Path(__file__)),
        "sandbox": _file_digest(Path("/usr/bin/sandbox-exec")),
    }


def capability_error() -> str:
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        return "read-only CLI capture requires qualified macOS sandbox-exec; no unsandboxed fallback"
    return ""


def _profile(root: str, entries: dict, actions: list[dict]) -> str:
    literals = [str((Path(root) / name).resolve()) for name in entries]
    literals.extend(str(Path(action["argv"][0]).resolve()) for action in actions)
    reads = " ".join(f"(literal {json.dumps(name)})" for name in literals)
    return (
        "(version 1)(deny default)(allow process-exec)(allow sysctl-read)"
        "(allow file-read*)"
        f"(deny file-read* (subpath {json.dumps(str(Path.home().parent.resolve()))})"
        f" (subpath {json.dumps(str(Path(root).resolve()))})"
        ' (subpath "/private/tmp"))'
        "(allow file-read-metadata)"
        f"(allow file-read* {reads} "
        '(subpath "/System")(subpath "/usr/lib")(subpath "/usr/share")'
        '(subpath "/opt/homebrew")(subpath "/Library/Apple")'
        '(literal "/dev/null")(literal "/dev/urandom")(literal "/dev/random"))'
        "(deny file-write*)"
        '(allow file-write* (literal "/dev/dtracehelper"))'
        "(deny network*)"
        "(deny process-fork)"
        f"(deny file-read* (subpath {json.dumps(str(_store_root().resolve()))})"
        ")"
    )


def _execute(root: str, action: dict, profile: str) -> dict:
    output = {"stdout": bytearray(), "stderr": bytearray()}
    error = ""
    deadline = time.monotonic() + action["timeout_s"]
    environment = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
                   "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
                   "PYTHONNOUSERSITE": "1"}
    with subprocess.Popen(
        ["/usr/bin/sandbox-exec", "-p", profile, *action["argv"]],
        cwd=root, env=environment, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
    ) as process:
        assert process.stdout is not None and process.stderr is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            try:
                while selector.get_map() or process.poll() is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        error = "command timed out; no acceptance evidence"
                        break
                    for key, _ in selector.select(min(remaining, 0.1)):
                        chunk = os.read(key.fd, 8192)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        output[key.data].extend(chunk)
                        if sum(len(value) for value in output.values()) > MAX_OUTPUT:
                            error = "command output limit exceeded; no acceptance evidence"
                            break
                    if error:
                        break
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
        exit_code = process.returncode
    if exit_code < 0:
        error = error or "command terminated by signal or sandbox denial; review authorized action"
    try:
        decoded = {name: bytes(value[:MAX_OUTPUT]).decode("utf-8") for name, value in output.items()}
    except UnicodeDecodeError:
        decoded = {"stdout": "", "stderr": ""}
        error = "non-UTF-8 output is unsupported by this contract"
    if exit_code > 0 and "Operation not permitted" in decoded["stderr"]:
        error = error or "command denied by read-only sandbox; review authorized action"
    if any(_redact_secrets(text)[1] for text in decoded.values()):
        decoded = {"stdout": "", "stderr": ""}
        error = "possible secret output suppressed; use synthetic acceptance inputs"
    return {"scenario_id": action["scenario_id"], "attempt": 1,
            "exit_code": exit_code, **decoded, "error": error}


def capture(root: str, config: dict, contract_path: str, approval: str) -> dict:
    from fettle.uat.session import collect_scenarios

    root = str(Path(root).resolve())
    scenarios = collect_scenarios(root)
    contract = load_contract(contract_path, approval, scenarios)
    networked = contract["schema_version"] == 2
    error = "" if networked else capability_error()
    if error:
        raise ValueError(error)
    if config.get("uat", {}).get("start_command") or config.get("uat", {}).get("evaluator_runner"):
        raise ValueError("read-only capture cannot satisfy configured restart or model-evaluator requirements")
    store = _store_root().resolve()
    if store.is_relative_to(root):
        raise ValueError("controller evidence store must be outside the product tree")
    entries = _source(root)
    if networked:
        from fettle.uat import network_controller

        runtime = network_controller.runtime(contract)
        observations = network_controller.execute(root, contract, entries)
        current_runtime = network_controller.runtime(contract)
    else:
        runtime = _runtime(contract["actions"])
        profile = _profile(root, entries, contract["actions"])
        observations = [_execute(root, action, profile) for action in contract["actions"]]
        current_runtime = _runtime(contract["actions"])
    if _source(root) != entries or current_runtime != runtime:
        raise ValueError("source or runtime changed during capture; rerun UAT")
    load_contract(contract_path, approval, collect_scenarios(root))
    envelope: dict = {
        "schema_version": 1, "mode": network_controller.MODE if networked else MODE,
        "session_id": "uat-" + uuid.uuid4().hex,
        "root": root, "source_digest": _digest(entries), "runtime": runtime,
        "policy_digest": _digest(config), "contract_digest": _digest(scenarios),
        "oracle_path": str(Path(contract_path).resolve()), "oracle_digest": approval,
        "contract": contract, "observations": observations,
    }
    store.mkdir(mode=0o700, parents=True, exist_ok=True)
    _write_bytes_atomic(store / (envelope["session_id"] + ".json"),
                        (json.dumps(envelope, sort_keys=True) + "\n").encode())
    return envelope


def validate_proposal(path: str, contract: dict) -> None:
    proposal_path = Path(path)
    if proposal_path.is_symlink() or not proposal_path.is_file() or proposal_path.stat().st_size > MAX_CONTRACT:
        raise ValueError("proposal must be a bounded regular JSON file")
    with proposal_path.open("rb") as handle:
        content = handle.read(MAX_CONTRACT + 1)
    if len(content) > MAX_CONTRACT:
        raise ValueError("proposal exceeds capture budget")
    proposal = json.loads(content, object_pairs_hook=_unique_object)
    actions = []
    for action in contract["actions"]:
        proposed = {key: value for key, value in action.items() if key != "expect"}
        if "steps" in proposed:
            proposed["steps"] = [{key: value for key, value in step.items() if key != "expect"}
                                 for step in proposed["steps"]]
        actions.append(proposed)
    expected = {"schema_version": 1, "scenario_digest": contract["scenario_digest"], "actions": actions}
    if _digest(proposal) != _digest(expected):
        raise ValueError("proposal differs from approved actions or coverage; review contract, never auto-approve")


def run_contract_session(root: str, config: dict, contract_path: str,
                         approval: str, consent: bool, surface: str = "cli", *, proposal_path: str | None = None):
    from fettle.uat.session import SessionResult, _write_checkpoint

    root = str(Path(root).resolve())
    result = SessionResult(session_id="", surface=surface)
    if not consent:
        result.error = "review the contract and supply --approve-contract sha256:<digest> and --yes"
        return result
    resources = ExitStack()
    try:
        from fettle.uat.session import collect_scenarios
        from fettle.uat.network_controller import MODE as NETWORK_MODE

        if surface == "cli" and capability_error():
            raise ValueError(capability_error())
        contract = load_contract(contract_path, approval, collect_scenarios(root))
        if contract.get("surface", "cli") != surface:
            raise ValueError("requested surface differs from the approved contract")
        if proposal_path is not None:
            validate_proposal(proposal_path, contract)
        mode = NETWORK_MODE if contract["schema_version"] == 2 else MODE
        evidence_dir = Path(root) / ".fettle"
        if evidence_dir.resolve() != evidence_dir:
            raise ValueError("evidence directory must not be a symlink")

        def invalidate_checkpoint():
            error = _write_checkpoint(root, {"status": "running", "surface": surface, "capture_mode": mode})
            if error:
                raise ValueError(error)

        if contract["schema_version"] == 2:
            from fettle.uat.recovery import lease

            resources.enter_context(lease(root, contract["context"], on_acquired=invalidate_checkpoint))
        else:
            invalidate_checkpoint()
        envelope = capture(root, config, contract_path, approval)
        result.session_id = envelope["session_id"]
        result.worktree = root
        from fettle.uat.session import collect_scenarios

        result.scenario_ids = [scenario["id"] for scenario in collect_scenarios(root)]
        errors = [observation["error"] for observation in envelope["observations"] if observation["error"]]
        result.status = "error" if errors else "completed"
        result.error = "; ".join(errors)
        checkpoint = {
            "session_id": result.session_id, "surface": surface, "status": result.status,
            "scenario_ids": result.scenario_ids, "error": result.error,
            "capture_mode": mode, "capture_digest": _digest(envelope),
            "contract_digest": envelope["contract_digest"], "policy_digest": envelope["policy_digest"],
            "canonical_evidence": True,
            "canonical_evidence_reference": {"kind": f"fettle.uat.{surface}-observation",
                                             "artifact_digest": _digest(envelope)},
        }
        error = _write_checkpoint(root, checkpoint)
        if error:
            raise ValueError(error)
    except (OSError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        result.status = "error"
        result.error = f"{surface.upper()} capture unavailable: {exc}; review contract and rerun"
    finally:
        try:
            resources.close()
        except (OSError, TypeError, ValueError, subprocess.SubprocessError) as exc:
            result.status = "error"
            result.error = f"resource recovery incomplete: {exc}; rerun approved capture"
            _write_checkpoint(root, {"status": "error", "surface": surface, "error": result.error})
    return result


def validate_capture(root: str, session: dict) -> tuple[list[dict], str]:
    from fettle.config import load_config
    from fettle.uat.session import collect_scenarios

    try:
        session_id = session.get("session_id", "")
        if not isinstance(session_id, str) or not re.fullmatch(r"uat-[0-9a-f]{32}", session_id):
            raise ValueError("invalid controller session identity")
        receipt = _store_root() / (session_id + ".json")
        if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size > MAX_RECEIPT:
            raise ValueError("controller receipt is not a bounded regular file")
        envelope = json.loads(receipt.read_bytes(), object_pairs_hook=_unique_object)
        if not isinstance(envelope, dict):
            raise ValueError("malformed controller receipt")
        scenarios = collect_scenarios(root)
        contract = load_contract(envelope["oracle_path"], envelope["oracle_digest"], scenarios)
        from fettle.uat import network_controller

        networked = contract["schema_version"] == 2
        mode = network_controller.MODE if networked else MODE
        surface = contract.get("surface", "cli")
        runtime = network_controller.runtime(contract) if networked else _runtime(contract["actions"])
        if (envelope["schema_version"] != 1 or envelope["mode"] != mode
                or envelope["session_id"] != session_id
                or envelope["root"] != str(Path(root).resolve())
                or envelope["source_digest"] != _digest(_source(root))
                or envelope["policy_digest"] != _digest(load_config(root, strict=True))
                or envelope["contract_digest"] != _digest(scenarios)
                or envelope["runtime"] != runtime
                or envelope["contract"] != contract
                or session.get("capture_digest") != _digest(envelope)
                or session.get("scenario_ids") != [scenario["id"] for scenario in scenarios]
                or session.get("surface") != surface
                or session.get("capture_mode") != mode
                or session.get("canonical_evidence_reference") != {
                    "kind": f"fettle.uat.{surface}-observation", "artifact_digest": _digest(envelope)}):
            raise ValueError("controller observation context is stale or inconsistent")
        observations = envelope["observations"]
        observation_keys = {"scenario_id", "attempt", "exit_code", "stdout", "stderr", "error"}
        if networked and surface == "web":
            observation_keys.add("artifacts")
        if (not isinstance(observations, list) or len(observations) != len(contract["actions"])
              or any(not isinstance(observed, dict)
                  or set(observed) != observation_keys
                  or observed["scenario_id"] != action["scenario_id"]
                  or type(observed["attempt"]) is not int or observed["attempt"] != 1
                  or type(observed["exit_code"]) is not int
                  or any(not isinstance(observed[name], str) for name in ("stdout", "stderr", "error"))
                  or any(len(observed[name].encode()) > MAX_OUTPUT for name in ("stdout", "stderr"))
                  or observed["exit_code"] < 0 and not observed["error"]
                       for action, observed in zip(contract["actions"], observations, strict=True))):
            raise ValueError("controller observation coverage is incomplete")
        verdicts = []
        for action, observed in zip(contract["actions"], observations, strict=True):
            if networked and surface == "web":
                network_controller.validate_artifacts(contract, action, observed)
            expected = network_controller.expected(action) if networked else action["expect"]
            matched = all(observed[key] == value for key, value in expected.items())
            verdicts.append({
                "scenario_id": action["scenario_id"],
                "verdict": "BLOCKED" if observed["error"] else "CONFIRMED" if matched else "CONTRADICTED",
                "observed": observed["stdout"],
                "note": observed["error"] or "controller-captured exit/stdout/stderr evaluated against approved oracle",
            })
        return verdicts, ""
    except (KeyError, OSError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        return [], f"controller evidence unavailable or invalid: {exc}; rerun approved UAT contract"
