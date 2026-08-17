"""Checkout-independent conformance harness for an installed Fettle wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from fettle import __version__
from fettle.installed_artifact_contract import load_capability_policy, validate_report


HOSTS = ("claude-code", "codex-cli", "gemini-cli", "opencode")
_STEP_NAMES = {
    "claude-code": "claude-code",
    "codex-cli": "codex",
    "gemini-cli": "gemini",
    "opencode": "opencode",
}


def _python() -> Path:
    return Path(sys.executable).resolve()


def _module_root() -> Path:
    return Path(__file__).resolve().parent


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _load_strict_json(path: Path) -> Mapping[str, object]:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    value = json.loads(path.read_bytes(), object_pairs_hook=reject_duplicates)
    if not isinstance(value, Mapping):
        raise ValueError(f"{path.name} must contain an object")
    return value


def load_live_evidence() -> dict[str, dict[str, object]]:
    document = _load_strict_json(Path(__file__).with_name("installed-host-evidence.json"))
    if set(document) != {"schema_version", "hosts"} or document["schema_version"] != "1":
        raise ValueError("installed host evidence has an invalid schema")
    raw_hosts = document["hosts"]
    if not isinstance(raw_hosts, Mapping) or set(raw_hosts) != set(HOSTS):
        raise ValueError("installed host evidence has an invalid host set")
    hosts: dict[str, dict[str, object]] = {}
    fields = {"state", "observed_at", "host_version", "reference"}
    for name, raw in raw_hosts.items():
        if not isinstance(raw, Mapping) or set(raw) != fields:
            raise ValueError(f"{name} live evidence has missing or unknown fields")
        if raw["state"] not in {"pass", "blocked"}:
            raise ValueError(f"{name} live evidence has an invalid state")
        if raw["state"] == "pass" and not isinstance(raw["observed_at"], str):
            raise ValueError(f"{name} passing live evidence needs observed_at")
        if raw["state"] == "blocked" and raw["observed_at"] is not None:
            raise ValueError(f"{name} blocked live evidence cannot have observed_at")
        if not all(isinstance(raw[field], str) and raw[field] for field in ("host_version", "reference")):
            raise ValueError(f"{name} live evidence identity is incomplete")
        hosts[str(name)] = dict(raw)
    return hosts


def _environment(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_STATE_HOME": str(home / ".local" / "state"),
        "PYTHONPATH": "",
    })
    return env


def _run_json(command: list[str], *, cwd: Path, env: dict[str, str]) -> object:
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True, timeout=120, check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[:500]
        raise ValueError(f"command failed ({result.returncode}): {detail}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"command returned invalid JSON: {exc}") from exc


def _bridge_root(project: Path, env: dict[str, str]) -> Path:
    value = _run_json(
        [
            sys.executable, "-c",
            "import json; from fettle.bridge import bridge_base; print(json.dumps(str(bridge_base())))",
        ],
        cwd=project,
        env=env,
    )
    if not isinstance(value, str) or not value:
        raise ValueError("installed bridge root is invalid")
    return Path(value)


def _run_init(work_root: Path, env: dict[str, str]) -> dict[str, object]:
    home = Path(env["HOME"])
    project = work_root / "project"
    project.mkdir(parents=True)
    for host_dir in (
        home / ".claude", home / ".codex", home / ".gemini",
        home / ".config" / "opencode",
    ):
        host_dir.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(project)], check=True, timeout=30)
    bridge_root = _bridge_root(project, env)
    dry_steps = _run_json(
        [sys.executable, "-m", "fettle", "init", "--dry-run", "--json"], cwd=project, env=env,
    )
    dry_run_bridge_written = bridge_root.exists()
    steps = _run_json(
        [sys.executable, "-m", "fettle", "init", "--json"], cwd=project, env=env,
    )
    if not isinstance(dry_steps, list) or not isinstance(steps, list):
        raise ValueError("fettle init JSON must be an array")
    by_name = {
        item.get("name"): item for item in steps
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    registrations = {}
    for host, step_name in _STEP_NAMES.items():
        step = by_name.get(step_name)
        registrations[host] = (
            "pass" if isinstance(step, dict) and step.get("status") in {"ok", "created"} else "blocked"
        )
    manifests = list(bridge_root.glob("*/manifest.json"))
    if len(manifests) != 1:
        raise ValueError("installed bridge manifest is missing or ambiguous")
    return {
        "dry_run_bridge_written": dry_run_bridge_written,
        "bridge_manifest": manifests[0],
        "registrations": registrations,
        "project": project,
    }


def _doctor_bridge_passes(project: Path, env: dict[str, str]) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "fettle", "doctor", "--json"],
        cwd=project, env=env, capture_output=True, text=True, timeout=120, check=False,
    )
    try:
        payload = json.loads(result.stdout)
        checks = payload.get("checks", [])
    except (json.JSONDecodeError, AttributeError):
        return False
    bridge = [check for check in checks if isinstance(check, dict) and check.get("name") == "bridge"]
    return len(bridge) == 1 and bridge[0].get("ok") is True


def _dispatcher_probe(payload: dict[str, object], project: Path, env: dict[str, str]) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "fettle.dispatcher"], cwd=project, env=env,
        input=json.dumps(payload), capture_output=True, text=True, timeout=30, check=False,
    )
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    specific = output.get("hookSpecificOutput") if isinstance(output, dict) else None
    return result.returncode in {0, 2} and isinstance(specific, dict) and specific.get("hookEventName") == "PostToolUse"


def _command_binds_python(command: object) -> bool:
    if not isinstance(command, str):
        return False
    try:
        arguments = shlex.split(command)
    except ValueError:
        return False
    return len(arguments) == 3 and Path(arguments[0]).absolute() == Path(sys.executable).absolute() and arguments[1:] == ["-m", "fettle.dispatcher"]


def _registered_commands(path: Path, event: str) -> list[object]:
    document = _load_strict_json(path)
    hooks = document.get("hooks")
    if not isinstance(hooks, Mapping) or not isinstance(hooks.get(event), list):
        return []
    return [
        hook.get("command")
        for group in hooks[event]
        if isinstance(group, Mapping)
        for hook in group.get("hooks", [])
        if isinstance(hook, Mapping)
    ]


def _probe_transports(project: Path, env: dict[str, str]) -> dict[str, str]:
    home = Path(env["HOME"])
    common = {"cwd": str(project), "session_id": "installed-artifact-canary"}
    payloads = {
        "claude-code": {**common, "hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": "app.py"}},
        "codex-cli": {**common, "hook_event_name": "PostToolUse", "tool_name": "apply_patch", "tool_input": {"command": "*** Update File: app.py"}, "turn_id": "canary-turn"},
        "gemini-cli": {**common, "hook_event_name": "AfterTool", "tool_name": "write_file", "tool_input": {"file_path": "app.py"}},
        "opencode": {"type": "tool.execute.after", "tool": "write", "args": {"filePath": "app.py"}, "directory": str(project), "sessionID": "installed-artifact-canary"},
    }
    bridge_roots = list(_bridge_root(project, env).glob("*"))
    if len(bridge_roots) != 1:
        return {host: "blocked" for host in HOSTS}
    bridge_root = bridge_roots[0]
    bindings = {
        "claude-code": (home / ".claude" / "plugins" / "fettle").resolve() == bridge_root.resolve(),
        "codex-cli": any(_command_binds_python(command) for command in _registered_commands(home / ".codex" / "hooks.json", "PostToolUse")),
        "gemini-cli": any(_command_binds_python(command) for command in _registered_commands(home / ".gemini" / "settings.json", "AfterTool")),
        "opencode": json.dumps(os.path.abspath(sys.executable)) in (bridge_root / "opencode" / "fettle.ts").read_text(),
    }
    return {
        host: "pass" if bindings[host] and _dispatcher_probe(payloads[host], project, env) else "blocked"
        for host in HOSTS
    }


def run_canary(
    *, stage: str, wheel: Path, output: Path, work_root: Path,
    checkout_root: Path, pipx_version: str,
) -> dict[str, object]:
    del output
    if stage not in {"candidate", "public"}:
        raise ValueError("stage must be candidate or public")
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise ValueError("wheel must be an existing .whl file")
    if _inside(_module_root(), checkout_root):
        raise ValueError("canary module resolved from the source checkout")
    if _inside(work_root, checkout_root):
        raise ValueError("canary work root must be outside the source checkout")
    work_root.mkdir(parents=True, exist_ok=True)
    home = work_root / "home"
    home.mkdir()
    env = _environment(home)
    init = _run_init(work_root, env)
    if init["dry_run_bridge_written"]:
        raise ValueError("fettle init dry-run wrote the installed bridge")
    registrations = init["registrations"]
    for host in HOSTS:
        if registrations.get(host) != "pass":
            raise ValueError(f"{host} registration did not pass")
    project = init.get("project", work_root / "project")
    if not _doctor_bridge_passes(project, env):
        raise ValueError("fettle doctor did not validate the installed bridge")
    transports = _probe_transports(project, env)
    for host in HOSTS:
        if transports.get(host) != "pass":
            raise ValueError(f"{host} transport did not pass")
    manifest = Path(init["bridge_manifest"])
    live = load_live_evidence()
    report: dict[str, object] = {
        "schema_version": "1",
        "stage": stage,
        "package": {
            "name": "finefettle", "version": __version__,
            "wheel": {
                "filename": wheel.name,
                "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                "size": wheel.stat().st_size,
            },
        },
        "environment": {
            "python": platform.python_version(), "os": platform.system().lower(),
            "architecture": platform.machine(), "pipx": pipx_version,
            "checkout_independent": True,
        },
        "bridge": {
            "state": "pass", "version": __version__,
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        },
        "doctor": "pass",
        "hosts": {
            host: {"registration": "pass", "transport": transports[host], "live_evidence": live[host]}
            for host in HOSTS
        },
    }
    validate_report(report, policy=load_capability_policy())
    return report


def _write_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run installed-artifact conformance")
    parser.add_argument("--stage", required=True, choices=("candidate", "public"))
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("--checkout-root", required=True, type=Path)
    parser.add_argument("--pipx-version", required=True)
    args = parser.parse_args(argv)
    try:
        report = run_canary(
            stage=args.stage, wheel=args.wheel, output=args.output,
            work_root=args.work_root, checkout_root=args.checkout_root,
            pipx_version=args.pipx_version,
        )
        _write_atomic(args.output, report)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"installed artifact canary failed: {exc}", file=sys.stderr)
        return 1
    print(f"installed artifact canary passed: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
