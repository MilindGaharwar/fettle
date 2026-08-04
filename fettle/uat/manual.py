"""Manual UAT fallback + operator attestation (S5.4).

When automation can't run (no runner, no browser driver, privileged
steps), the operator gets an easy-to-follow walkthrough generated from
the same spec scenarios the agent would have used — numbered steps, the
exact expectation, and the attest command to record what they saw.
Operator evidence is a labeled peer of agent evidence, never silently
mixed (source: "operator").
"""

from __future__ import annotations

import json
import time
from pathlib import Path

ATTEST_NAME = "uat-attestations.json"

_OUTCOMES = frozenset({"matches", "differs", "could-not-attempt"})


def format_manual_guide(scenarios: list[dict]) -> str:
    """Numbered, human-first walkthrough generated from GWT scenarios."""
    if not scenarios:
        return ("No active spec scenarios found.\n"
                "Manual UAT needs at least one active spec with GWT scenarios "
                "(see 'fettle spec lint').")
    lines = ["Manual UAT walkthrough — do each scenario, then record what you saw.",
             ""]
    for s in scenarios:
        lines.append(f"Scenario {s['id']}: {s['title']}")
        n = 1
        expectation = ""
        for step in s["steps"]:
            low = step.lower()
            if low.startswith("given"):
                lines.append(f"  {n}. Set up: {step[5:].strip()}")
            elif low.startswith("when"):
                lines.append(f"  {n}. Do: {step[4:].strip()}")
            elif low.startswith("then"):
                expectation = step[4:].strip()
                lines.append(f"  {n}. Check: {expectation}")
            else:
                lines.append(f"  {n}. {step}")
            n += 1
        lines.append(f"  Record it: fettle uat attest {s['id']} "
                     "--outcome matches|differs|could-not-attempt "
                     '--observed "<what you actually saw>"')
        lines.append("")
    return "\n".join(lines)


def _attest_path(root: str) -> Path:
    return Path(root) / ".fettle" / ATTEST_NAME


def load_attestations(root: str) -> list[dict]:
    try:
        data = json.loads(_attest_path(root).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def record_attestation(root: str, scenario_id: str, outcome: str,
                       observed: str, operator: str = "") -> tuple[dict, str]:
    """Append an operator attestation. Returns (entry, error)."""
    if outcome not in _OUTCOMES:
        return {}, (f"outcome must be one of: {', '.join(sorted(_OUTCOMES))} "
                    f"(got {outcome!r})")
    if not observed.strip():
        return {}, ("--observed is required: describe what you actually saw, "
                    "verbatim where possible — attestations without evidence "
                    "are not accepted")
    from fettle.uat.session import collect_scenarios
    known = {s["id"] for s in collect_scenarios(root)}
    if scenario_id not in known:
        return {}, (f"unknown scenario '{scenario_id}' — active scenarios: "
                    f"{', '.join(sorted(known)) or '(none)'}")
    entry = {
        "scenario_id": scenario_id,
        "outcome": outcome,
        "observed": observed.strip(),
        "source": "operator",
        "operator": operator or "unknown",
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    from fettle.trace import build_evidence
    entry["evidence_id"] = build_evidence(
        "uat_attestation", exit_code=0 if outcome == "matches" else 1,
        scope=scenario_id,
    )["evidence_id"]
    entries = load_attestations(root)
    entries.append(entry)
    path = _attest_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        return {}, f"cannot write attestation: {exc}"
    return entry, ""
