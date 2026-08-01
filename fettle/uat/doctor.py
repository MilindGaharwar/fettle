"""UAT capability probe — `fettle uat doctor` (S5.1).

Answers: for each surface this repo has, can a UAT session actually run
today? Every gap produces the three-part block from design doc 10 §5 —
what's not possible, why, how to fix it, and (where automation has a
manual peer) what to do by hand. An incomplete capability must never
read as ready (Stage 0 posture).
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def probe(root: str, config: dict) -> tuple[list[Capability], str]:
    """Capability check per resolved surface. Returns (capabilities, error)."""
    from fettle.runners import detect_runners
    from fettle.uat.surfaces import resolve_surfaces

    surfaces, err = resolve_surfaces(root, config)
    if err:
        return [], err

    uat_cfg = config.get("uat", {})
    runner_name = uat_cfg.get("runner", "claude")
    runners = detect_runners()
    runner_ok = runners.get(runner_name, False)

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
                    why="playwright is not installed (optional extra — core stays stdlib-only)",
                    fix="pip install 'finefettle[uat]'  — then re-run",
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
