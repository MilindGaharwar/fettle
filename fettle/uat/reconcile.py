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
from collections.abc import Mapping

from fettle import __version__
from fettle.evidence import (
    EvidenceArtifact,
    EvidenceValidationContext,
    EvidenceValidationResult,
    ResultState,
    Validity,
    parse_artifact,
    validate_artifact,
)
from fettle.trace import log_evidenced_decision

REPORT_NAME = "uat-report.json"
REPORT_EVIDENCE_NAME = "uat-report.evidence.json"

VERDICTS = ("CONFIRMED", "CONTRADICTED", "BLOCKED", "UNOBSERVED", "INDETERMINATE")

_BLOCK_RE = re.compile(r"^SCENARIO:\s*(\S+)\s*$", re.MULTILINE)
_FIELD_RE = re.compile(r"^(OBSERVED|OUTCOME|NOTES):\s*(.*)$")
_RESTART_RE = re.compile(r"^RESTART_PROBE:\s*$", re.MULTILINE)
_RESTART_FIELD_RE = re.compile(r"^(BEFORE|AFTER|OUTCOME|NOTES):\s*(.*)$")

_OUTCOME_MAP = {
    "matches": "CONFIRMED",
    "differs": "CONTRADICTED",
    "could-not-attempt": "BLOCKED",
}

_JUDGMENT_SEVERITIES = frozenset({"low", "medium", "high", "critical"})


@dataclass
class Verdict:
    scenario_id: str
    verdict: str
    observed: str = ""
    note: str = ""


def parse_transcript(text: str) -> dict[str, dict]:
    """Extract SCENARIO blocks: {id: {observed, outcome, notes}}.

    Conflicting retries remain unresolved without independent attempt evidence.
    Malformed blocks are kept with whatever fields parsed.
    """
    blocks: dict[str, dict] = {}
    matches = list(_BLOCK_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entry = {"observed": "", "outcome": "", "notes": ""}
        current: str | None = None
        for line in text[m.end():end].splitlines():
            if _RESTART_RE.match(line.strip()):
                break
            if _CANDIDATE_RE.match(line.strip()):
                break  # P73: charter findings start a new section
            f = _FIELD_RE.match(line.strip())
            if f:
                current = f.group(1).lower()
                entry[current] = f.group(2).strip()
            elif current and line.strip():
                entry[current] += "\n" + line.strip()  # multi-line field
        sid = m.group(1)
        if sid in blocks and blocks[sid] != entry:
            entry["outcome"] = "conflicting-attempts"
            entry["notes"] = "conflicting reports require independent attempt evidence"
        blocks[sid] = entry
    return blocks


def parse_restart_probe(text: str) -> dict | None:
    """Extract the final structured P75 restart probe from a transcript."""
    matches = list(_RESTART_RE.finditer(text))
    if not matches:
        return None
    entry = {"before": "", "after": "", "outcome": "", "notes": ""}
    current: str | None = None
    for line in text[matches[-1].end():].splitlines():
        if _BLOCK_RE.match(line.strip()) or _CANDIDATE_RE.match(line.strip()):
            break
        field = _RESTART_FIELD_RE.match(line.strip())
        if field:
            current = field.group(1).lower()
            entry[current] = field.group(2).strip()
        elif current and line.strip():
            entry[current] += "\n" + line.strip()
    return entry


def reconcile_restart_probe(worktree: str, session: dict, transcript: str) -> Verdict | None:
    """Reconcile configured restart evidence; None means not applicable."""
    probe = session.get("restart_probe") or {"status": "NOT_APPLICABLE"}
    if not isinstance(probe, dict):
        return Verdict("__lifecycle__/restart-persistence", "INDETERMINATE",
                       note="malformed restart evidence; rerun UAT")
    if probe.get("status") == "NOT_APPLICABLE":
        return None
    sid = "__lifecycle__/restart-persistence"
    if probe.get("status") != "captured":
        return Verdict(sid, "INDETERMINATE",
                       note="configured session has no complete restart evidence")
    path = Path(worktree) / ".fettle" / "uat-restart-probe.json"
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Verdict(sid, "INDETERMINATE",
                       note="restart evidence artifact is missing or malformed")
    block = parse_restart_probe(transcript)
    if (not isinstance(artifact, dict) or block is None
            or artifact.get("block") != block
            or artifact.get("block_sha") != _digest(block)):
        return Verdict(sid, "INDETERMINATE",
                       note="restart evidence drifted from the retained artifact")
    if not block.get("before") or not block.get("after"):
        return Verdict(sid, "INDETERMINATE", note="restart evidence is incomplete")
    outcome = block.get("outcome", "").strip().lower()
    mapped = {"persisted": "CONFIRMED", "lost": "CONTRADICTED",
              "could-not-attempt": "BLOCKED"}.get(outcome)
    if mapped is None:
        return Verdict(sid, "INDETERMINATE", observed=block.get("after", ""),
                       note=f"unrecognized restart outcome {outcome!r}")
    if mapped == "CONFIRMED":
        return Verdict(sid, "INDETERMINATE", observed=block["after"],
                       note="restart claim lacks independent process and state evidence")
    return Verdict(sid, mapped, observed=block["after"], note=block.get("notes", ""))


def evaluate_judgment(
    worktree: str,
    transcript: str,
    artifacts: dict[str, dict],
    runner,
    timeout_s: int = 600,
) -> dict:
    """Run and validate an independent, artifact-bound judgment pass."""
    references = [
        {"scenario_id": sid, "block_sha": artifact.get("block_sha", ""),
         "block": artifact.get("block", {})}
        for sid, artifact in sorted(artifacts.items())
    ]
    prompt = (
        "You are an independent reviewer of a completed UAT session. Hunt for "
        "passes for the wrong reason and missed confusion or friction. Do not "
        "change primary verdicts. Return only JSON as "
        '{"findings":[{"scenario_id":"...","severity":"low|medium|high|critical",'
        '"summary":"...","artifact_sha":"..."}]}. Every finding must cite '
        "one exact artifact SHA from the supplied references.\n\n"
        f"ARTIFACTS:\n{json.dumps(references, sort_keys=True)}\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )
    from fettle.spawn import governed_run
    run = governed_run(runner, prompt, str(Path(worktree)), timeout_s)
    if run.error or run.exit_code != 0:
        return {"status": "tool_error", "findings": [],
                "error": run.error or f"evaluator exited {run.exit_code}; rerun UAT judgment"}
    try:
        payload = json.loads(run.transcript)
        raw_findings = payload["findings"]
        if not isinstance(raw_findings, list):
            raise TypeError("findings must be a list")
    except (KeyError, TypeError, ValueError) as exc:
        return {"status": "indeterminate", "findings": [],
                "error": f"malformed evaluator output: {exc}"}

    findings = []
    for finding in raw_findings:
        if not isinstance(finding, dict):
            return {"status": "indeterminate", "findings": [],
                    "error": "evaluator finding must be an object"}
        sid = str(finding.get("scenario_id") or "")
        severity = str(finding.get("severity") or "").lower()
        summary = str(finding.get("summary") or "").strip()
        artifact_sha = str(finding.get("artifact_sha") or "")
        artifact = artifacts.get(sid)
        if (severity not in _JUDGMENT_SEVERITIES or not summary
                or artifact is None or artifact.get("block_sha") != artifact_sha):
            return {"status": "indeterminate", "findings": [],
                    "error": "evaluator finding lacks valid severity or exact artifact reference"}
        findings.append({
            "scenario_id": sid,
            "severity": severity,
            "summary": summary,
            "artifact": {"scenario_id": sid, "block_sha": artifact_sha},
            "resolution": "operator-attestation-required",
        })
    return {"status": "completed", "findings": findings, "error": ""}


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

    Transcript blocks and their retained copies are claims, not execution
    observations. Matches remain INDETERMINATE until an independent capture
    and contract-oracle path is qualified. Missing or drifting claims also
    remain non-pass.
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
        verdicts.append(Verdict(sid, mapped, observed=block["observed"],
                                note=block["notes"]))
    return verdicts


def _confirm_gate(
    sid: str, block: dict, scenario: dict,
    artifacts: dict[str, dict], require_artifacts: bool,
) -> Verdict | None:
    """Diagnose invalid claims without granting them execution authority."""
    if _looks_parroted(block["observed"], scenario):
        return Verdict(sid, "INDETERMINATE", observed=block["observed"],
                       note="claimed match without independent evidence (auto-answer suspected)")
    artifact = artifacts.get(sid)
    if require_artifacts and artifact is None:
        return Verdict(
            sid, "INDETERMINATE", observed=block["observed"],
            note="claimed match but no observation artifact was retained",
        )
    if artifact is not None:
        from fettle.uat.artifacts import block_sha

        if (not isinstance(artifact, dict)
                or not isinstance(artifact.get("block"), dict)
                or artifact.get("block_sha") != block_sha(artifact["block"])
                or artifact.get("scenario_id") != sid
                or artifact.get("steps") != scenario.get("steps", [])):
            return Verdict(sid, "INDETERMINATE", observed=block["observed"],
                           note="artifact content or scenario contract is invalid")
        if artifact.get("block_sha") != block_sha(block):
            return Verdict(
                sid, "INDETERMINATE", observed=block["observed"],
                note="transcript drifted from the captured observation artifact",
            )
    return Verdict(sid, "INDETERMINATE", observed=block["observed"],
                   note="agent claim lacks independent execution evidence; "
                        "retain observations and rerun with a qualified capture driver")


_CANDIDATE_RE = re.compile(r"^CANDIDATE:\s*(.+)$")


def _outside_scenario_blocks(transcript: str) -> str:
    """Mask scenario and restart verdict sections during candidate scanning."""
    parts: list[str] = []
    in_verdict_block = False
    for line in transcript.splitlines():
        stripped = line.strip()
        if _BLOCK_RE.match(stripped) or _RESTART_RE.match(stripped):
            in_verdict_block = True
        elif _CANDIDATE_RE.match(stripped):
            in_verdict_block = False
        if not in_verdict_block:
            parts.append(line)
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


def _completion(verdicts: list[dict], session: dict, judgment: dict, session_error: str) -> dict:
    if (not isinstance(verdicts, list) or not isinstance(judgment, dict)
            or any(not isinstance(item, dict) or not isinstance(item.get("scenario_id"), str)
                   or item.get("verdict") not in VERDICTS for item in verdicts)):
        raise ValueError("malformed UAT verdicts or judgment")
    product = [item for item in verdicts if not item["scenario_id"].startswith("__")]
    product_ids = [item["scenario_id"] for item in product]
    required = session.get("scenario_ids") or []
    valid_inventory = (isinstance(required, list) and bool(required)
                       and all(isinstance(sid, str) and sid for sid in required)
                       and len(set(required)) == len(required))
    exact_coverage = (valid_inventory and len(set(product_ids)) == len(product_ids)
                      and set(product_ids) == set(required))
    judgment_pass = (judgment.get("status") == "NOT_APPLICABLE"
                     or judgment.get("status") == "completed" and judgment.get("findings") == [])
    return {
        "complete": bool(exact_coverage and not session_error and judgment_pass
                         and all(item["verdict"] == "CONFIRMED" for item in verdicts)),
        "required_total": len(required) if valid_inventory else len(product),
        "required_confirmed": sum(item["verdict"] == "CONFIRMED" for item in product),
    }


def write_report(
    worktree: str,
    session: dict,
    verdicts: list[Verdict],
    candidates: list[dict] | None = None,
    judgment: dict | None = None,
) -> tuple[str, str]:
    """Persist the evidence artifact. Returns (path, error).

    P73: ``candidates`` are exploration findings recorded verbatim for human
    review; they never influence verdicts.
    """
    path = Path(worktree) / ".fettle" / REPORT_NAME
    verdicts = [
        Verdict(verdict.scenario_id, "INDETERMINATE", verdict.observed,
                "caller-supplied confirmation lacks independent execution evidence")
        if verdict.verdict == "CONFIRMED" else verdict
        for verdict in verdicts
    ]
    if session.get("capture_mode"):
        from fettle.uat.controller import validate_capture

        captured, capture_error = validate_capture(worktree, session)
        if not capture_error:
            verdicts = [Verdict(**item) for item in captured]
    from fettle.trace import build_evidence
    judgment = judgment or {"status": "NOT_APPLICABLE", "findings": []}
    session_error = _session_error(worktree, session)
    projected = [{"scenario_id": verdict.scenario_id, "verdict": verdict.verdict,
                  "observed": verdict.observed, "note": verdict.note} for verdict in verdicts]
    completion = _completion(projected, session, judgment, session_error)
    evidence_id = build_evidence(
        "uat_report", exit_code=0 if completion["complete"] else 1,
        scope=session.get("surface", ""),
    )["evidence_id"]
    data = {
        "session_id": session.get("session_id", ""),
        "surface": session.get("surface", ""),
        "evidence_id": evidence_id,
        "candidate_scenarios": candidates or [],
        "judgment": judgment,
        "session_error": session_error,
        "verdicts": projected,
        "completion": completion,
        "lifecycle": {
            "restart_probe": next((
                {"verdict": v.verdict, "observed": v.observed, "note": v.note}
                for v in verdicts
                if v.scenario_id == "__lifecycle__/restart-persistence"
            ), {"verdict": "NOT_APPLICABLE",
                "note": "restart probe not configured"}),
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_bytes_atomic(path, (json.dumps(data, indent=2) + "\n").encode())
        if session.get("canonical_evidence", True):
            try:
                _write_report_evidence(worktree, session, data)
            except (OSError, TypeError, ValueError) as exc:
                error = (
                    "canonical UAT report evidence unavailable: "
                    + (str(exc) or type(exc).__name__)
                )
                data["session_error"] = error
                data["completion"]["complete"] = False
                _write_bytes_atomic(path, (json.dumps(data, indent=2) + "\n").encode())
                return str(path), error
            evidence_data = json.loads(
                (Path(worktree) / ".fettle" / REPORT_EVIDENCE_NAME).read_text(encoding="utf-8")
            )
            reference = {
                "artifact_digest": evidence_data["artifact_digest"],
                "kind": evidence_data["kind"],
                "schema_version": evidence_data["schema_version"],
                "expected": {
                    "source_snapshot_digest": evidence_data["source"]["snapshot_digest"],
                    "policy_digest": evidence_data["policy_digest"],
                    "scope_digest": evidence_data["scope_digest"],
                    "producer_id": evidence_data["producer"]["id"],
                },
                "availability": "available",
            }
            with contextlib.suppress(Exception):
                log_evidenced_decision(
                    worktree,
                    hook="uat_report",
                    status=evidence_data["result_state"],
                    evidence=[reference],
                    tool="fettle uat report",
                    file=str(path),
                    session_id=str(data["session_id"]),
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
    judgment = report["judgment"]
    unresolved = (judgment.get("status") in {"tool_error", "indeterminate"}
                  or bool(report.get("session_error")))
    artifact = EvidenceArtifact.create(
        kind="fettle.uat.report",
        producer={
            "id": "fettle.uat.report",
            "version": __version__,
            "implementation_digest": _producer_digest(),
        },
        result_state=(
            "unknown" if unresolved else "pass" if completion["complete"] else "violation"
        ),
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


def validate_canonical_evidence(worktree: str, report: dict) -> EvidenceValidationResult:
    """Validate the canonical UAT sidecar and its complete report projection."""
    recovery = "fettle uat report"

    def failure(validity: Validity) -> EvidenceValidationResult:
        return EvidenceValidationResult(validity, ResultState.UNKNOWN, recovery)

    report_path = Path(worktree) / ".fettle" / REPORT_NAME
    evidence_path = Path(worktree) / ".fettle" / REPORT_EVIDENCE_NAME
    if not evidence_path.is_file():
        return failure(Validity.MISSING)
    try:
        content = evidence_path.read_bytes()
        artifact = parse_artifact(content)
        payload = artifact.payload
        verdicts = report["verdicts"]
        completion = report["completion"]
        judgment = report["judgment"]
        if (not isinstance(judgment, dict) or not isinstance(completion, dict)
            or not isinstance(verdicts, list)
            or any(not isinstance(item, dict) or not isinstance(item.get("scenario_id"), str)
                   or item.get("verdict") not in VERDICTS for item in verdicts)):
            return failure(Validity.MALFORMED)
        projected_verdicts = [
            {"scenario_id": item["scenario_id"], "verdict": item["verdict"]}
            for item in verdicts
        ]
        judgment_status = judgment.get("status")
        from fettle.uat.session import load_checkpoint

        session = load_checkpoint(worktree) or {}
        session_error = _session_error(worktree, session)
        if session.get("capture_mode"):
            from fettle.uat.controller import validate_capture

            captured, capture_error = validate_capture(worktree, session)
            if capture_error or verdicts != captured:
                return failure(Validity.TAMPERED)
        elif any(item["verdict"] == "CONFIRMED" for item in verdicts):
            return failure(Validity.TAMPERED)
        unresolved = (judgment_status in {"tool_error", "indeterminate"}
                  or bool(session_error))
        expected_completion = _completion(verdicts, session, judgment, session_error)
        if completion != expected_completion:
            return failure(Validity.TAMPERED)
        expected_state = (
            ResultState.UNKNOWN if unresolved
            else ResultState.PASS if completion["complete"]
            else ResultState.VIOLATION
        )
        retained_verdicts = payload.get("verdicts")
        retained_completion = payload.get("completion")
        retained_report = payload.get("report")
        if (not isinstance(retained_verdicts, (list, tuple))
                or not isinstance(retained_completion, Mapping)
                or not isinstance(retained_report, Mapping)):
            return failure(Validity.MALFORMED)
        if (
            payload.get("session_id") != str(report["session_id"])
            or payload.get("surface") != str(report["surface"])
            or list(retained_verdicts) != projected_verdicts
            or dict(retained_completion) != completion
            or retained_report.get("digest")
            != "sha256:" + hashlib.sha256(report_path.read_bytes()).hexdigest()
            or artifact.result_state != expected_state
        ):
            return failure(Validity.TAMPERED)
        context = EvidenceValidationContext(
            kind="fettle.uat.report",
            source_snapshot_digest=_digest({
                "session_id": report["session_id"],
                "session_evidence": session.get("canonical_evidence_reference"),
            }),
            source_revision=None,
            policy_digest=_digest({"canonical_evidence": True}),
            scope_digest=_digest({
                "surface": report["surface"],
                "scenario_ids": [item["scenario_id"] for item in verdicts],
            }),
            producer_id="fettle.uat.report",
            producer_versions=frozenset({__version__}),
            producer_implementation_digest=_producer_digest(),
            allowed_trust_classes=frozenset({"derived"}),
            recovery_action=recovery,
        )
        return validate_artifact(content, context)
    except (KeyError, OSError, TypeError, ValueError):
        return failure(Validity.MALFORMED)


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
    if cp.get("capture_mode"):
        from fettle.uat.controller import validate_capture

        captured, capture_error = validate_capture(worktree, cp)
        if Path(root).resolve() != Path(worktree).resolve():
            return [], cp, "controller report must be inspected from its original product root"
        if capture_error:
            return [], cp, capture_error
        verdicts = [Verdict(**item) for item in captured]
        judgment = {"status": "NOT_APPLICABLE", "findings": []}
        cp["session_error"] = _session_error(worktree, cp)
        cp["judgment"] = judgment
        _, err = write_report(worktree, cp, verdicts, judgment=judgment)
        cp["acceptance_complete"] = not err and _completion(
            captured, cp, judgment, cp["session_error"],
        )["complete"]
        return verdicts, cp, err
    transcript_path = cp.get("transcript", "")
    if not isinstance(transcript_path, str) or not transcript_path:
        return [], cp, "session has no transcript (did the run complete?)"
    try:
        if not Path(transcript_path).resolve().is_relative_to(
                (Path(worktree) / ".fettle").resolve()):
            return [], cp, "session transcript escapes retained evidence directory"
        transcript = Path(transcript_path).read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        return [], cp, f"cannot read transcript: {exc}"
    scenario_ids = cp.get("scenario_ids")
    if (not isinstance(scenario_ids, list) or not scenario_ids
            or any(not isinstance(sid, str) or not sid for sid in scenario_ids)
            or len(set(scenario_ids)) != len(scenario_ids)):
        return [], cp, "session requires a nonempty unique scenario inventory; rerun UAT"
    try:
        scenarios = collect_scenarios(root)
    except ValueError as exc:
        return [], cp, str(exc)
    if set(scenario_ids) != {scenario["id"] for scenario in scenarios}:
        return [], cp, "required scenario coverage changed or is incomplete; rerun UAT"
    if cp.get("contract_digest") != _digest(scenarios):
        cp["validation_error"] = "scenario contract is missing or changed; rerun UAT"
    from fettle.uat.artifacts import load_scenario_artifacts

    artifacts = load_scenario_artifacts(worktree)
    verdicts = reconcile(
        scenarios, transcript,
        artifacts=artifacts,
        require_artifacts=True,
    )
    restart_verdict = reconcile_restart_probe(worktree, cp, transcript)
    if restart_verdict is not None:
        verdicts.append(restart_verdict)
    judgment = {"status": "NOT_APPLICABLE", "findings": []}
    evaluator_name = str(cp.get("evaluator_runner") or "")
    if evaluator_name:
        from fettle.runners import get_uat_runner

        try:
            evaluator = get_uat_runner(evaluator_name)
            judgment = evaluate_judgment(
                worktree, transcript, artifacts, evaluator,
                timeout_s=int(cp.get("evaluator_timeout_s") or 600),
            )
        except (TypeError, ValueError) as exc:
            judgment = {"status": "tool_error", "findings": [], "error": str(exc)}
    cp["judgment"] = judgment
    cp["judgment_pass"] = (
        judgment["status"] == "NOT_APPLICABLE"
        or (judgment["status"] == "completed" and not judgment["findings"])
    )
    cp["session_error"] = _session_error(worktree, cp)
    _, err = write_report(worktree, cp, verdicts,
                          candidates=parse_candidates(transcript), judgment=judgment)
    cp["acceptance_complete"] = not err and _completion(
        [{"scenario_id": verdict.scenario_id, "verdict": verdict.verdict} for verdict in verdicts],
        cp, judgment, cp["session_error"],
    )["complete"]
    return verdicts, cp, err


def _session_error(worktree: str, session: dict) -> str:
    from fettle.uat.session import (
        SESSION_EVIDENCE_NAME, _producer_digest as session_producer_digest,
        collect_scenarios,
    )

    if session.get("status") != "completed" or session.get("error"):
        return "session did not complete successfully; rerun UAT"
    for field in ("artifact_error", "canonical_evidence_error", "validation_error"):
        if session.get(field):
            return str(session[field])
    if session.get("capture_mode"):
        from fettle.uat.controller import validate_capture

        _, error = validate_capture(worktree, session)
        return error
    capture = session.get("web_capture")
    if session.get("surface") == "web" and (
            not isinstance(capture, dict) or capture.get("status") != "completed"):
        return "required web capture is missing or failed; rerun UAT"
    try:
        scenarios = collect_scenarios(worktree)
        if not scenarios or session.get("contract_digest") != _digest(scenarios):
            return "session contract is missing or stale; rerun UAT"
        scenario_ids = session.get("scenario_ids")
        if scenario_ids != [scenario["id"] for scenario in scenarios]:
            return "session scenario inventory is invalid; rerun UAT"
        transcript = Path(session["transcript"]).resolve()
        if not transcript.is_relative_to((Path(worktree) / ".fettle").resolve()):
            return "session transcript escapes retained evidence directory"
        digest = "sha256:" + hashlib.sha256(transcript.read_bytes()).hexdigest()
        content = (Path(worktree) / ".fettle" / SESSION_EVIDENCE_NAME).read_bytes()
        artifact = parse_artifact(content)
        reference = session["canonical_evidence_reference"]
        retained_ids = artifact.payload.get("scenario_ids")
        retained_transcript = artifact.payload.get("transcript")
        if (not isinstance(retained_ids, (list, tuple))
                or not isinstance(retained_transcript, Mapping)):
            return "session evidence has malformed payload; rerun UAT"
        if (artifact.artifact_digest != reference["artifact_digest"]
                or artifact.payload.get("status") != "completed"
                or artifact.payload.get("session_id") != session.get("session_id")
                or list(retained_ids) != scenario_ids
                or retained_transcript.get("digest") != digest):
            return "session evidence conflicts with checkpoint; rerun UAT"
        validation = validate_artifact(content, EvidenceValidationContext(
            kind="fettle.uat.session",
            source_snapshot_digest=_digest({
                "session_id": session.get("session_id", ""),
                "transcript_digest": digest,
                "contract_digest": session.get("contract_digest"),
            }),
            source_revision=None,
            policy_digest=session["policy_digest"],
            scope_digest=_digest({"surface": session.get("surface", ""),
                                  "scenario_ids": scenario_ids}),
            producer_id="fettle.uat.session",
            producer_versions=frozenset({__version__}),
            producer_implementation_digest=session_producer_digest(),
            allowed_trust_classes=frozenset({"derived"}),
            recovery_action="fettle uat run",
        ))
        if validation.validity != Validity.VALID or validation.result_state != ResultState.PASS:
            return "session evidence is invalid or incomplete; rerun UAT"
    except (KeyError, OSError, TypeError, ValueError):
        return "session evidence is missing or malformed; rerun UAT"
    return ""
