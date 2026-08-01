"""UAT session core (S5.2) — Probe → Isolate → Explore → Checkpoint.

Runs a UAT exploration session for cli/api surfaces: verifies capability,
provisions an isolated `uat-<timestamp>` worktree with a claim, builds a
persona prompt from the active specs' GWT scenarios, launches the agent
runner, and writes a resumable checkpoint plus the raw transcript for the
reconciler (S5.3). Failures return, never raise (D-S4.1 posture).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

CHECKPOINT_NAME = "uat-session.json"

#: Surfaces the session core can always drive. web needs playwright (S5.5).
DRIVABLE_SURFACES = frozenset({"cli", "api", "library"})

_CONSENT_TEXT = (
    "UAT sessions launch an autonomous agent with permission checks disabled "
    "inside an isolated worktree. It will run commands and, for web surfaces, "
    "drive a browser against your app. Re-run with --yes to consent."
)

_PROMPT_HEADER = """\
You are a first-time user performing acceptance testing of this software.
You have never seen the codebase. Interact ONLY through the {surface} \
surface as a real user would — do not read source code to infer behavior, \
do not fix anything, do not modify any file.

{access}

For each scenario below, attempt it exactly as described and record what \
actually happened. For every scenario output a block in this exact format:

SCENARIO: <scenario-id>
OBSERVED: <what you actually saw, verbatim where possible>
OUTCOME: <matches | differs | could-not-attempt>
NOTES: <anything surprising, confusing, or broken from a user's view>

If you cannot attempt a scenario, say so with OUTCOME: could-not-attempt \
and explain exactly what blocked you. Never guess or fabricate output.
Scenarios:
"""


@dataclass
class SessionResult:
    session_id: str
    surface: str
    worktree: str = ""
    transcript_path: str = ""
    scenario_ids: list[str] = field(default_factory=list)
    status: str = "error"  # completed | error | timeout
    error: str = ""


def collect_scenarios(root: str) -> list[dict]:
    """GWT scenarios from active specs: [{id, title, steps, requirement_texts}]."""
    from fettle.spec_model import discover_specs

    out: list[dict] = []
    for spec, _findings in discover_specs(root):
        if spec is None or spec.status != "active":
            continue
        for scen in spec.scenarios:
            out.append({
                "id": f"{spec.spec_id}/{scen.id}",
                "title": scen.title,
                "steps": list(scen.texts),
                "requirements": [spec.requirements.get(r, "") for r in scen.traces],
            })
    return out


def build_prompt(surface: str, scenarios: list[dict], uat_cfg: dict) -> str:
    """Persona prompt (doc 10 §3 Explore): real-user framing + GWT scenarios."""
    if uat_cfg.get("app_url"):
        access = f"The application is reachable at: {uat_cfg['app_url']}"
    elif uat_cfg.get("start_command"):
        access = (f"Start the application yourself with: {uat_cfg['start_command']}\n"
                  "Wait for it to be ready before testing; stop it when done.")
    else:
        access = ("Discover the entry point the way a user would (README, --help); "
                  "if none is documented, that itself is a finding.")
    if surface == "web":
        access += ("\nUse playwright (already installed) to drive a real browser "
                   "against the app — navigate, click, and read the page exactly "
                   "as a person would. Never bypass the UI by calling APIs or "
                   "reading the database directly.\n"
                   "If a step needs credentials or a permission grant you do not "
                   "have, STOP that scenario and report OUTCOME: could-not-attempt "
                   "with exactly what is needed. Never invent or reuse credentials.")
    parts = [_PROMPT_HEADER.format(surface=surface, access=access)]
    for s in scenarios:
        parts.append(f"\n### {s['id']}: {s['title']}")
        parts.extend(f"- {step}" for step in s["steps"])
    return "\n".join(parts) + "\n"


def _checkpoint_path(worktree: str) -> Path:
    return Path(worktree) / ".fettle" / CHECKPOINT_NAME


def load_checkpoint(worktree: str) -> dict | None:
    """Read a session checkpoint; None when absent or unreadable."""
    try:
        return json.loads(_checkpoint_path(worktree).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_checkpoint(worktree: str, data: dict) -> str:
    path = _checkpoint_path(worktree)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return ""
    except OSError as exc:
        return f"cannot write checkpoint: {exc}"


def _redact_secrets(transcript: str) -> tuple[str, int]:
    """Secrets never persist through the transcript (doc 10 §4)."""
    from fettle.boundary_scan import scan_text
    findings = [f for f in scan_text(transcript) if "secret" in f.message.lower()
                or "key" in f.message.lower() or "token" in f.message.lower()]
    if not findings:
        return transcript, 0
    lines = transcript.splitlines()
    hit_lines = {f.line for f in findings if 1 <= f.line <= len(lines)}
    for i in hit_lines:
        lines[i - 1] = "[REDACTED: possible secret removed from transcript]"
    return "\n".join(lines) + "\n", len(hit_lines)


def run_session(root: str, config: dict, surface: str,
                runner=None, session_id: str = "",
                consent: bool = False) -> SessionResult:
    """Full session for one surface. Returns a SessionResult, never raises.

    `runner` may be any object with .run(prompt, cwd, timeout_s) (test seam);
    defaults to the configured agent runner. `consent` must be explicit —
    sessions run an agent with permission checks disabled.
    """
    from fettle.runners import get_runner
    from fettle.uat.doctor import probe
    from fettle.work_items import claim_item
    from fettle.worktrees import create_worktree

    uat_cfg = config.get("uat", {})
    session_id = session_id or f"uat-{time.strftime('%Y%m%d-%H%M%S')}"
    result = SessionResult(session_id=session_id, surface=surface)

    if not consent:
        result.error = _CONSENT_TEXT
        return result

    if surface == "web":
        from fettle.uat.doctor import _playwright_available
        if not _playwright_available():
            result.error = ("web surface needs browser automation: "
                            "pip install 'finefettle[uat]' — or run "
                            "'fettle uat manual' for hand-testing steps")
            return result
    elif surface not in DRIVABLE_SURFACES:
        result.error = (f"surface '{surface}' is not drivable "
                        f"(supported: {', '.join(sorted(DRIVABLE_SURFACES | {'web'}))}); "
                        "run 'fettle uat doctor' for manual steps")
        return result

    caps, err = probe(root, config)
    if err:
        result.error = err
        return result
    cap = next((c for c in caps if c.surface == surface), None)
    if cap is None or not cap.ready:
        result.error = (f"capability gap on '{surface}': "
                        f"{cap.why if cap else 'surface not detected'} — "
                        "run 'fettle uat doctor'")
        return result

    scenarios = collect_scenarios(root)
    if not scenarios:
        result.error = ("no active spec scenarios found — UAT needs at least one "
                        "active spec with GWT scenarios (see 'fettle spec lint')")
        return result
    result.scenario_ids = [s["id"] for s in scenarios]

    wt_path, err = create_worktree(root, session_id, config)
    if err:
        result.error = f"worktree provisioning failed: {err}"
        return result
    result.worktree = str(wt_path)
    claim_err = claim_item(root, session_id, session_id, str(wt_path))
    if claim_err:
        result.error = f"claim failed: {claim_err}"
        return result

    prompt = build_prompt(surface, scenarios, uat_cfg)
    checkpoint = {
        "session_id": session_id, "surface": surface,
        "scenario_ids": result.scenario_ids, "status": "running",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    err = _write_checkpoint(str(wt_path), checkpoint)
    if err:
        result.error = err
        return result

    if runner is None:
        try:
            runner = get_runner(uat_cfg.get("runner", "claude"))
        except ValueError as exc:
            result.error = str(exc)
            return result
    run = runner.run(prompt, cwd=str(wt_path),
                     timeout_s=int(uat_cfg.get("timeout_s", 1800)))

    transcript_path = Path(wt_path) / ".fettle" / f"{session_id}-transcript.txt"
    try:
        clean, redacted = _redact_secrets(run.transcript)
        transcript_path.write_text(clean, encoding="utf-8")
        result.transcript_path = str(transcript_path)
        if redacted:
            checkpoint["redacted_lines"] = redacted
    except OSError as exc:
        result.error = f"cannot persist transcript: {exc}"

    if run.error:
        result.status = "timeout" if "timed out" in run.error else "error"
        result.error = result.error or run.error
    elif not result.error:
        result.status = "completed"
    checkpoint.update(status=result.status, transcript=result.transcript_path,
                      error=result.error)
    _write_checkpoint(str(wt_path), checkpoint)
    return result
