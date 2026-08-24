"""UAT reconciler (S5.3) — transcript → per-scenario verdicts.

Turns a raw exploration transcript into evidence: each spec scenario gets
exactly one verdict. UNOBSERVED is first-class — a scenario the agent
never reported on is a gap, not a pass. Agent claims are distrusted:
a "matches" outcome with empty or parroted evidence downgrades to
INDETERMINATE (auto-answer detection, doc 10 §4).

Verdicts: CONFIRMED | CONTRADICTED | BLOCKED | UNOBSERVED | INDETERMINATE
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import UTC, datetime
from dataclasses import dataclass
from pathlib import Path

from fettle import __version__
from fettle.evidence import EvidenceArtifact

REPORT_NAME = "uat-report.json"
REPORT_EVIDENCE_NAME = "uat-report.evidence.json"

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
            if _CANDIDATE_RE.match(line.strip()):
                break  # P73: charter findings start a new section
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


def reconcile(
    scenarios: list[dict],
    transcript: str,
    artifacts: dict[str, dict] | None = None,
    require_artifacts: bool = False,
) -> list[Verdict]:
    """One verdict per scenario. `scenarios` as from collect_scenarios().

    P72: when ``require_artifacts`` is set (session reconciliation), a
    CONFIRMED verdict must be backed by a captured observation artifact
    whose block hash still matches the transcript — otherwise it degrades
    to INDETERMINATE. Missing artifact or drift is never read as success.
    """
    blocks = parse_transcript(transcript)
    artifacts = artifacts or {}
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
            continue
        if mapped == "CONFIRMED":
            gate = _confirm_gate(sid, block, s, artifacts, require_artifacts)
            if gate is not None:
                verdicts.append(gate)
                continue
        if mapped == "CONFIRMED" and _looks_parroted(block["observed"], s):
            verdicts.append(Verdict(sid, "INDETERMINATE", observed=block["observed"],
                                    note="claimed match without independent evidence "
                                         "(auto-answer suspected)"))
        else:
            verdicts.append(Verdict(sid, mapped, observed=block["observed"],
                                    note=block["notes"]))
    return verdicts


def _confirm_gate(
    sid: str, block: dict, scenario: dict,
    artifacts: dict[str, dict], require_artifacts: bool,
) -> Verdict | None:
    """P72: CONFIRMED must survive artifact verification; None = pass through."""
    artifact = artifacts.get(sid)
    if require_artifacts and artifact is None:
        return Verdict(
            sid, "INDETERMINATE", observed=block["observed"],
            note="claimed match but no observation artifact was retained",
        )
    if artifact is not None:
        from fettle.uat.artifacts import block_sha

        if artifact.get("block_sha") != block_sha(block):
            return Verdict(
                sid, "INDETERMINATE", observed=block["observed"],
                note="transcript drifted from the captured observation artifact",
            )
    return None


_CANDIDATE_RE = re.compile(r"^CANDIDATE:\s*(.+)$")


def _outside_scenario_blocks(transcript: str) -> str:
    """Mask SCENARIO verdict blocks so candidate scanning skips them."""
    matches = list(_BLOCK_RE.finditer(transcript))
    if not matches:
        return transcript
    parts: list[str] = []
    last = 0
    for m in matches:
        parts.append(transcript[last:m.start()])
        last = m.end()
    parts.append(transcript[last:])
    return "\n".join(parts)


def parse_candidates(transcript: str) -> list[dict]:
    """P73: exploration findings for human review — never verdicts."""
    candidates: list[dict] = []
    current: dict | None = None
    for raw in _outside_scenario_blocks(transcript).splitlines():
        stripped = raw.strip()
        m = _CANDIDATE_RE.match(stripped)
        if m:
            if current:
                candidates.append(current)
            current = {"candidate_id": m.group(1).strip(),
                       "observed": "", "why_interesting": ""}
            continue
        if current is None or not stripped:
            continue
        low = stripped.lower()
        if low.startswith("observed:"):
            current["observed"] = stripped[len("observed:"):].strip()
        elif low.startswith("why-interesting:"):
            current["why_interesting"] = stripped[16:].strip()
        elif current.get("observed"):
            current["observed"] += " " + stripped
    if current:
        candidates.append(current)
    return candidates


def write_report(
    worktree: str,
    session: dict,
    verdicts: list[Verdict],
    candidates: list[dict] | None = None,
) -> tuple[str, str]:
    """Persist the evidence artifact. Returns (path, error).

    P73: ``candidates`` are exploration findings recorded verbatim for human
    review; they never influence verdicts.
    """
    path = Path(worktree) / ".fettle" / REPORT_NAME
    from fettle.trace import build_evidence
    evidence_id = build_evidence(
        "uat_report", exit_code=0 if all(v.verdict == "CONFIRMED" for v in verdicts) else 1,
        scope=session.get("surface", ""),
    )["evidence_id"]
    data = {
        "session_id": session.get("session_id", ""),
        "surface": session.get("surface", ""),
        "evidence_id": evidence_id,
        "candidate_scenarios": candidates or [],
        "verdicts": [{"scenario_id": v.scenario_id, "verdict": v.verdict,
                       "observed": v.observed, "note": v.note} for v in verdicts],
        "completion": {
            "complete": bool(verdicts) and all(v.verdict == "CONFIRMED" for v in verdicts),
            "required_total": len(verdicts),
            "required_confirmed": sum(v.verdict == "CONFIRMED" for v in verdicts),
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if session.get("canonical_evidence", True):
            try:
                _write_report_evidence(worktree, session, data)
            except (OSError, TypeError, ValueError) as exc:
                return str(path), (
                    "canonical UAT report evidence unavailable: "
                    + (str(exc) or type(exc).__name__)
                )
        return str(path), ""
    except OSError as exc:
        return "", f"cannot write UAT report: {exc}"


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _producer_digest() -> str:
    return "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = ""
    finally:
        if temporary:
            with contextlib.suppress(OSError):
                os.unlink(temporary)


def _write_report_evidence(worktree: str, session: dict, report: dict) -> None:
    report_path = Path(worktree) / ".fettle" / REPORT_NAME
    report_digest = "sha256:" + hashlib.sha256(report_path.read_bytes()).hexdigest()
    completion = report["completion"]
    verdicts = [
        {"scenario_id": item["scenario_id"], "verdict": item["verdict"]}
        for item in report["verdicts"]
    ]
    artifact = EvidenceArtifact.create(
        kind="fettle.uat.report",
        producer={
            "id": "fettle.uat.report",
            "version": __version__,
            "implementation_digest": _producer_digest(),
        },
        result_state="pass" if completion["complete"] else "violation",
        completeness="complete",
        trust_class="derived",
        source={"snapshot_digest": _digest({
            "session_id": report["session_id"],
            "session_evidence": session.get("canonical_evidence_reference"),
        })},
        policy_digest=_digest({"canonical_evidence": True}),
        scope_digest=_digest({
            "surface": report["surface"],
            "scenario_ids": [item["scenario_id"] for item in verdicts],
        }),
        observation_id="uat-report-" + uuid.uuid4().hex,
        observed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        payload={
            "session_id": str(report["session_id"]),
            "surface": str(report["surface"]),
            "report": {"path": REPORT_NAME, "digest": report_digest},
            "verdicts": verdicts,
            "completion": completion,
            "redacted_lines": int(session.get("redacted_lines") or 0),
        },
    )
    evidence_path = Path(worktree) / ".fettle" / REPORT_EVIDENCE_NAME
    _write_bytes_atomic(evidence_path, artifact.to_bytes())


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
    from fettle.uat.artifacts import load_scenario_artifacts

    verdicts = reconcile(
        scenarios, transcript,
        artifacts=load_scenario_artifacts(worktree),
        require_artifacts=True,
    )
    _, err = write_report(worktree, cp, verdicts,
                          candidates=parse_candidates(transcript))
    return verdicts, cp, err
