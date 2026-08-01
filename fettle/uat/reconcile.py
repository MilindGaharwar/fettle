"""UAT reconciler (S5.3) — transcript → per-scenario verdicts.

Turns a raw exploration transcript into evidence: each spec scenario gets
exactly one verdict. UNOBSERVED is first-class — a scenario the agent
never reported on is a gap, not a pass. Agent claims are distrusted:
a "matches" outcome with empty or parroted evidence downgrades to
INDETERMINATE (auto-answer detection, doc 10 §4).

Verdicts: CONFIRMED | CONTRADICTED | BLOCKED | UNOBSERVED | INDETERMINATE
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

REPORT_NAME = "uat-report.json"

VERDICTS = ("CONFIRMED", "CONTRADICTED", "BLOCKED", "UNOBSERVED", "INDETERMINATE")

_BLOCK_RE = re.compile(r"^SCENARIO:\s*(\S+)\s*$", re.MULTILINE)
_FIELD_RE = re.compile(r"^(OBSERVED|OUTCOME|NOTES):\s*(.*)$")

_OUTCOME_MAP = {
    "matches": "CONFIRMED",
    "differs": "CONTRADICTED",
    "could-not-attempt": "BLOCKED",
}


@dataclass
class Verdict:
    scenario_id: str
    verdict: str
    observed: str = ""
    note: str = ""


def parse_transcript(text: str) -> dict[str, dict]:
    """Extract SCENARIO blocks: {id: {observed, outcome, notes}}.

    Later blocks for the same id win (the agent may retry a scenario).
    Malformed blocks are kept with whatever fields parsed.
    """
    blocks: dict[str, dict] = {}
    matches = list(_BLOCK_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entry = {"observed": "", "outcome": "", "notes": ""}
        current: str | None = None
        for line in text[m.end():end].splitlines():
            f = _FIELD_RE.match(line.strip())
            if f:
                current = f.group(1).lower()
                entry[current] = f.group(2).strip()
            elif current and line.strip():
                entry[current] += "\n" + line.strip()  # multi-line field
        blocks[m.group(1)] = entry
    return blocks


def _looks_parroted(observed: str, scenario: dict) -> bool:
    """Auto-answer heuristic: no evidence, or evidence == the expectation."""
    obs = observed.strip().strip('"').lower()
    if not obs:
        return True
    for step in scenario.get("steps", []):
        if step.lower().startswith("then"):
            expectation = step[4:].strip().strip('"').lower()
            if obs == expectation or obs == step.lower():
                return True
    return False


def reconcile(scenarios: list[dict], transcript: str) -> list[Verdict]:
    """One verdict per scenario. `scenarios` as from collect_scenarios()."""
    blocks = parse_transcript(transcript)
    verdicts: list[Verdict] = []
    for s in scenarios:
        sid = s["id"]
        block = blocks.get(sid)
        if block is None:
            verdicts.append(Verdict(sid, "UNOBSERVED",
                                    note="agent never reported on this scenario"))
            continue
        mapped = _OUTCOME_MAP.get(block["outcome"].strip().lower())
        if mapped is None:
            verdicts.append(Verdict(sid, "INDETERMINATE", observed=block["observed"],
                                    note=f"unrecognized outcome {block['outcome']!r}"))
        elif mapped == "CONFIRMED" and _looks_parroted(block["observed"], s):
            verdicts.append(Verdict(sid, "INDETERMINATE", observed=block["observed"],
                                    note="claimed match without independent evidence "
                                         "(auto-answer suspected)"))
        else:
            verdicts.append(Verdict(sid, mapped, observed=block["observed"],
                                    note=block["notes"]))
    return verdicts


def write_report(worktree: str, session: dict, verdicts: list[Verdict]) -> tuple[str, str]:
    """Persist the evidence artifact. Returns (path, error)."""
    path = Path(worktree) / ".fettle" / REPORT_NAME
    data = {
        "session_id": session.get("session_id", ""),
        "surface": session.get("surface", ""),
        "verdicts": [{"scenario_id": v.scenario_id, "verdict": v.verdict,
                      "observed": v.observed, "note": v.note} for v in verdicts],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return str(path), ""
    except OSError as exc:
        return "", f"cannot write UAT report: {exc}"


def format_verdicts(verdicts: list[Verdict]) -> str:
    """Human summary: counts + one line per scenario, problems expanded."""
    counts = {v: 0 for v in VERDICTS}
    for v in verdicts:
        counts[v.verdict] += 1
    header = "  ".join(f"{k}: {n}" for k, n in counts.items() if n)
    lines = [f"UAT verdicts — {header or 'no scenarios'}"]
    marks = {"CONFIRMED": "\u2713", "CONTRADICTED": "\u2717", "BLOCKED": "\u25cb",
             "UNOBSERVED": "?", "INDETERMINATE": "~"}
    for v in verdicts:
        lines.append(f"  {marks[v.verdict]} {v.scenario_id}: {v.verdict}")
        if v.verdict != "CONFIRMED":
            if v.observed:
                lines.append(f"      observed: {v.observed.splitlines()[0]}")
            if v.note:
                lines.append(f"      note: {v.note}")
    return "\n".join(lines)


def reconcile_session(root: str, worktree: str) -> tuple[list[Verdict], dict, str]:
    """Reconcile a completed session from its checkpoint + transcript.

    Returns (verdicts, checkpoint, error). Writes the report artifact.
    """
    from fettle.uat.session import collect_scenarios, load_checkpoint

    cp = load_checkpoint(worktree)
    if cp is None:
        return [], {}, f"no session checkpoint found in {worktree}"
    transcript_path = cp.get("transcript", "")
    if not transcript_path:
        return [], cp, "session has no transcript (did the run complete?)"
    try:
        transcript = Path(transcript_path).read_text(encoding="utf-8")
    except OSError as exc:
        return [], cp, f"cannot read transcript: {exc}"
    scenarios = [s for s in collect_scenarios(root)
                 if s["id"] in set(cp.get("scenario_ids", []))]
    verdicts = reconcile(scenarios, transcript)
    _, err = write_report(worktree, cp, verdicts)
    return verdicts, cp, err
