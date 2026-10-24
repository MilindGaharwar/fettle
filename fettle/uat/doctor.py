"""UAT capability probe — `fettle uat doctor` (S5.1).

Answers: for each surface this repo has, can a UAT session actually run
today? Every gap produces the three-part block from design doc 10 §5 —
what's not possible, why, how to fix it, and (where automation has a
manual peer) what to do by hand. An incomplete capability must never
read as ready (Stage 0 posture).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import shlex
import shutil


@dataclass
class Capability:
    surface: str
    ready: bool
    detail: str            # one-line status
    why: str = ""          # gap explanation (when not ready)
    fix: str = ""          # exact command/config change (when not ready)
    manual: list[str] = field(default_factory=list)  # numbered manual steps


def _playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            return Path(playwright.chromium.executable_path).is_file()
    except (ImportError, OSError, RuntimeError):
        return False


def probe_contract(root: str, config: dict, path: str, approval: str) -> Capability:
    import subprocess
    import uuid

    from fettle.uat.controller import _execute, _profile, _source, capability_error, load_contract
    from fettle.uat.session import collect_scenarios

    error = ""
    surface = "cli"
    try:
        contract = load_contract(path, approval, collect_scenarios(root))
        surface = contract.get("surface", "cli")
        if contract["schema_version"] == 2:
            from fettle.uat.network_controller import runtime

            if config.get("uat", {}).get("start_command") or config.get("uat", {}).get("evaluator_runner"):
                raise ValueError("use approved product startup; configured host startup/evaluator is unsupported")
            _source(root)
            runtime(contract)
            return Capability(surface=surface, ready=True,
                              detail=f"isolated {surface} runtime available; behavioral checks occur during run")
        error = capability_error()
        if error:
            raise ValueError(error)
        if config.get("uat", {}).get("start_command") or config.get("uat", {}).get("evaluator_runner"):
            raise ValueError("read-only capture does not support restart/model-evaluator requirements")
        entries = _source(root)
        nonce = uuid.uuid4().hex
        action = {"scenario_id": "__probe__", "argv": ["/bin/echo", nonce], "timeout_s": 3}
        observation = _execute(root, action, _profile(root, entries, [*contract["actions"], action]))
        if (observation["error"] or observation["exit_code"] != 0
                or observation["stdout"] != nonce + "\n" or observation["stderr"]):
            raise ValueError("native sandbox startup probe failed; no unsandboxed fallback")
    except (OSError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        error = (capability_error() if surface == "cli" else "") or str(exc)
    return Capability(
        surface=surface, ready=not error,
        detail="read-only CLI controller prerequisites verified" if not error else f"{surface} capture blocked",
        why=error, fix="review contract, approval digest and qualified runtime availability" if error else "",
    )


def probe(root: str, config: dict) -> tuple[list[Capability], str]:
    """Capability check per resolved surface. Returns (capabilities, error)."""
    from fettle.runners import detect_runners, get_uat_runner
    from fettle.uat.surfaces import resolve_surfaces

    surfaces, err = resolve_surfaces(root, config)
    if err:
        return [], err

    uat_cfg = config.get("uat", {})
    startup_error = ""
    if uat_cfg.get("start_command"):
        try:
            arguments = shlex.split(uat_cfg["start_command"])
            executable = arguments[0] if arguments else ""
            local = Path(root) / executable
            available = (local.is_file() and os.access(local, os.X_OK)
                         if "/" in executable else bool(shutil.which(executable)))
            if not executable or not available:
                startup_error = "configured start_command executable is unavailable"
        except (TypeError, ValueError):
            startup_error = "configured start_command is malformed"
    runner_name = uat_cfg.get("runner", "claude")
    runners = detect_runners()
    runner_ok = runners.get(runner_name, False)
    permission_error = ""
    try:
        get_uat_runner(runner_name)
    except ValueError as exc:
        permission_error = str(exc)

    caps: list[Capability] = []
    if not surfaces:
        caps.append(Capability(
            surface="(none)", ready=False,
            detail="no user-facing surface detected",
            why="no cli/api/web/library markers found in this repo",
            fix='declare surfaces explicitly: [uat] surfaces = ["cli"] in .fettle.toml',
        ))
        return caps, ""

    for s in surfaces:
        name = s["name"]
        if startup_error:
            caps.append(Capability(
                surface=name, ready=False, detail="application startup unavailable",
                why=startup_error, fix="repair [uat].start_command, then rerun fettle uat doctor",
            ))
            continue
        if permission_error:
            caps.append(Capability(
                surface=name, ready=False, detail="permission-preserving runner unavailable",
                why=permission_error, fix="configure [uat] runner = 'claude' or 'codex'",
            ))
            continue
        if not runner_ok:
            caps.append(Capability(
                surface=name, ready=False,
                detail=f"agent runner '{runner_name}' unavailable",
                why=f"the '{runner_name}' CLI is not on PATH "
                    f"(available: {', '.join(k for k, v in runners.items() if v) or 'none'})",
                fix=f"install the {runner_name} CLI, or set [uat] runner to an available one",
                manual=[f"run the {name} surface scenarios by hand — "
                        f"fettle uat attest records your observations (S5.4)"],
            ))
            continue
        if name == "web":
            if not _playwright_available():
                caps.append(Capability(
                    surface="web", ready=False,
                    detail="browser automation unavailable",
                    why="Playwright or its Chromium runtime is unavailable",
                    fix="reinstall finefettle, then run: playwright install",
                    manual=["start the app and walk each spec scenario in a browser",
                            "record what you saw: fettle uat attest <spec-id>/<S-n>"],
                ))
                continue
            if not uat_cfg.get("app_url") and not uat_cfg.get("start_command"):
                caps.append(Capability(
                    surface="web", ready=False,
                    detail="no way to reach the app",
                    why="[uat] has neither app_url (running instance) nor start_command",
                    fix='set [uat] app_url = "http://localhost:3000" or '
                        'start_command = "npm run dev" in .fettle.toml',
                ))
                continue
        if name == "api" and not uat_cfg.get("app_url") and not uat_cfg.get("start_command"):
            caps.append(Capability(
                surface="api", ready=False,
                detail="no way to reach the API",
                why="[uat] has neither app_url nor start_command",
                fix='set [uat] app_url or start_command in .fettle.toml',
            ))
            continue
        caps.append(Capability(surface=name, ready=True,
                               detail=f"ready (runner: {runner_name}; {s['evidence']})"))
    return caps, ""


def format_report(surfaces: list[dict], caps: list[Capability]) -> str:
    """Human-first report; gaps use the three-part block (doc 10 §5)."""
    lines: list[str] = ["Detected surfaces (override via [uat].surfaces):"]
    if surfaces:
        lines += [f"  - {s['name']:<8} ({s['evidence']})" for s in surfaces]
    else:
        lines.append("  (none)")
    lines.append("")
    for c in caps:
        if c.ready:
            lines.append(f"\u2713 {c.surface}: {c.detail}")
            continue
        lines.append(f"\u2717 Cannot run UAT on the {c.surface} surface")
        lines.append(f"  Why:  {c.why}")
        lines.append(f"  Fix:  {c.fix}")
        if c.manual:
            lines.append("  Or do it manually:")
            lines += [f"    {i}. {step}" for i, step in enumerate(c.manual, 1)]
    return "\n".join(lines)
