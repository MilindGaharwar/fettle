"""WP-G — Shared discipline link helper.

Loads 2-sentence reminders from discipline skills and manages cooldown.
Used by loop_detect (WP-C pilot) and future triggers (scope_creep, etc).
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path


_FALLBACK_REMINDERS: dict[str, str] = {
    "discipline-debugging": (
        "Pause and inspect the evidence before repeating the same action. "
        "Form a new hypothesis, then choose a tool call that tests it."
    ),
    "discipline-planning": (
        "Define the blast radius before expanding scope. "
        "List what existing features could break and verify after each change."
    ),
    "discipline-testing": (
        "Test error paths, not just the happy path. "
        "What happens when the API is down, data is empty, or input is invalid?"
    ),
    "discipline-coding": (
        "Stop at the first rung of the ladder that holds: YAGNI, reuse, stdlib, existing dep, one-liner. "
        "Two rungs work — take the higher one."
    ),
}

DEFAULT_FALLBACK = (
    "Pause and consider whether the current approach is working. "
    "If not, try a fundamentally different strategy."
)

TRIGGER_SKILL_MAP: dict[str, str] = {
    "loop_detect": "discipline-debugging",
    "scope_creep": "discipline-planning",
    "quality_gate_tests": "discipline-testing",
    "lean_sniffers": "discipline-coding",
}


def get_reminder(
    config: dict,
    trigger_name: str,
    state_dir: str,
    session_id: str,
) -> str:
    """Get a discipline reminder for a trigger, respecting cooldown.

    Returns empty string if cooldown hasn't expired or link is disabled.
    """
    disc_cfg = config.get("gates", {}).get("discipline_link", {})
    if not disc_cfg.get("enabled", True):
        return ""

    skill_name = TRIGGER_SKILL_MAP.get(trigger_name, "")
    if not skill_name:
        return ""

    cooldown_s = float(disc_cfg.get("cooldown_seconds", 300))
    if not _cooldown_expired(state_dir, session_id, trigger_name, cooldown_s):
        return ""

    return _load_snippet(disc_cfg, skill_name)


def _cooldown_expired(state_dir: str, session_id: str, trigger: str, cooldown_s: float) -> bool:
    safe_id = re.sub(r"[^a-zA-Z0-9_.\-]", "_", session_id)
    marker = Path(state_dir) / f"{safe_id}.disc-{trigger}-ts"
    now = time.time()
    if marker.is_file():
        try:
            last = float(marker.read_text().strip())
            if now - last < cooldown_s:
                return False
        except (ValueError, OSError):
            pass
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(now))
    except OSError:
        pass
    return True


def _load_snippet(disc_cfg: dict, skill_name: str) -> str:
    skills_path = Path(os.path.expanduser(
        disc_cfg.get("skills_path", "~/.claude/plugins/disciplines/skills")
    ))
    skill_file = skills_path / skill_name / "SKILL.md"

    fallback = _FALLBACK_REMINDERS.get(skill_name, DEFAULT_FALLBACK)

    if not skill_file.is_file():
        return fallback

    try:
        text = skill_file.read_text(encoding="utf-8")
        if text.startswith("---"):
            _, _, text = text.partition("---\n")
            _, _, text = text.partition("---\n")
        text = " ".join(
            line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
        sentences = re.findall(r"[^.!?]+[.!?]", text)
        return " ".join(sentences[:2]).strip() if len(sentences) >= 2 else fallback
    except OSError:
        return fallback
